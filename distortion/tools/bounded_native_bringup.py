"""One bounded CAM2 raw acquisition with verified heartbeat restoration.

Default mode only prepares source-bound plans. --execute programs volatile
SRAM, receives at most three frames, closes COM and attempts the fixed idle
SRAM in finally. This host process is not a hardware watchdog: power loss,
host death or a broken JTAG cable can still prevent restoration.
"""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import json
import math
import time

import native_camera_capture as capture
import program_native_raw as raw
import program_idle_heartbeat as idle


def _check_limits(port, frames, seconds, baud=921600):
    if type(frames) is not int or not 1 <= frames <= 3:
        raise ValueError('one short test may request only 1..3 frames')
    if type(seconds) not in (int, float) or not math.isfinite(seconds) or not 10 <= seconds <= 45:
        raise ValueError('capture duration must be finite within 10..45 seconds')
    if not isinstance(port, str) or not port.startswith('COM') or not port[3:].isdigit():
        raise ValueError('an explicitly selected Windows COM port is required')
    if type(baud) is not int or baud != 921600:
        raise ValueError('the bounded native receiver uses the fixed verified 921600 baud')


def _helper_hashes():
    return {str(path.relative_to(raw.ROOT)): raw.sha(path) for path in
            (Path(__file__), raw.ROOT/'tools/program_native_raw.py',
             raw.ROOT/'tools/program_idle_heartbeat.py', raw.ROOT/'tools/native_camera_capture.py')}


def _check_exit_plan(plan):
    """Validate the exact exit Tcl before entering the active raw design."""
    exit_plan = plan['idle_plan']
    work = Path(exit_plan['workdir']).resolve()
    if (exit_plan.get('target') != 'heartbeat' or exit_plan.get('operation') != 'volatile_sram_only' or
            not work.is_relative_to(Path(plan['workdir']).resolve()) or (work/'receipt.json').exists() or
            exit_plan.get('frequency') != plan['frequency']):
        raise ValueError('idle exit must be the fresh fixed heartbeat plan inside this bounded invocation')
    for stage, text in idle._scripts(exit_plan['validation'], exit_plan['frequency']).items():
        item = exit_plan['tcl'][stage]
        path = Path(item['path']).resolve()
        if path != work/(stage+'.tcl') or path.read_text(encoding='utf-8') != text or raw.sha(path) != item['sha256']:
            raise ValueError('idle exit Tcl changed; refusing to enter the raw configuration')
    raw.resolve_pds_bin(exit_plan['pds_bin'])


def prepare_plan(binding_path, workdir, *, port, frames=1, seconds=35., frequency='1MHz'):
    _check_limits(port, frames, seconds)
    base = Path(workdir).resolve()
    if not base.is_dir() or not base.is_relative_to(raw.APPROVED.resolve()):
        raise ValueError('workdir must already exist within approved offline scratch')
    # Verify both artifacts before any programming or COM opening is possible.
    raw.validate_program_binding(binding_path)
    idle.validate_heartbeat()
    work = base/('bounded-native-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
    work.mkdir(exist_ok=False)
    raw_plan = raw.prepare_plan(binding_path, work, frequency=frequency)
    idle_plan = idle.prepare_plan(work, frequency=frequency)
    plan = {'schema': 1, 'operation': 'bounded_native_then_heartbeat',
        'executed': False, 'hardware_accessed': False, 'workdir': str(work),
        'port': port, 'baud': 921600, 'frames': frames, 'seconds': seconds,
        'frequency': frequency, 'source_sha256': _helper_hashes(),
        'raw_plan': raw_plan, 'idle_plan': idle_plan,
        'limits': 'Host finally protection only, not a hardware watchdog or unattended long-run authorization. Raw capture has no calibrated lens parameters; no HDMI sink is required.'}
    raw._new_json(work/'plan.json', plan)
    return plan


def execute_plan(plan):
    work = Path(plan['workdir']).resolve()
    if (plan.get('operation') != 'bounded_native_then_heartbeat' or
            not work.is_dir() or not work.is_relative_to(raw.APPROVED.resolve()) or
            (work/'result.json').exists()):
        raise ValueError('a fresh bounded-native plan in approved scratch is required')
    _check_limits(plan['port'], plan['frames'], plan['seconds'], plan['baud'])
    if capture.load_json(work/'plan.json') != plan or plan.get('source_sha256') != _helper_hashes():
        raise ValueError('bounded configuration or helper source changed after planning')
    # Revalidate the idle exit before entering the active configuration.
    if idle.validate_heartbeat() != plan['idle_plan']['validation']:
        raise ValueError('idle exit artifacts or helpers changed since planning')
    if raw.validate_program_binding(plan['raw_plan']['validation']['binding_path']) != plan['raw_plan']['validation']:
        raise ValueError('raw binding or helpers changed since planning')
    _check_exit_plan(plan)
    result = {'schema': 1, 'operation': plan['operation'], 'executed': True,
        'passed': False, 'hardware_accessed': False, 'workdir': str(work),
        'raw_program': None, 'capture_summary': None, 'idle_program': None,
        'idle_restoration_attempted': False, 'idle_done_confirmed': False,
        'hardware_watchdog_installed': False, 'temperature_measured': False}
    active_attempted = False
    raw_execution_entered = False
    chunks = None
    wire_path = work/'received-wire.bin'
    wire_bytes = 0
    started = time.monotonic()
    try:
        raw_execution_entered = True
        result['raw_program'] = raw.execute_plan(plan['raw_plan'], timeout_seconds=90.)
        result['hardware_accessed'] = result['raw_program']['hardware_accessed']
        active_attempted = result['raw_program'].get('programming_attempted', False)
        if not result['raw_program']['passed'] or not result['raw_program']['done_confirmed']:
            raise RuntimeError('raw SRAM programming/DONE was not confirmed; COM remains unopened')
        binding_path = Path(result['raw_program']['session_binding_path'])
        binding_before = capture.sha(binding_path)
        binding = capture.load_json(binding_path)
        build_record = capture.validate_live_binding(binding, base_dir=binding_path.parent)
        chunks = capture.serial_chunks(plan['port'], plan['baud'], plan['seconds'])
        with wire_path.open('xb') as wire:
            def recorded_chunks():
                nonlocal wire_bytes
                for data in chunks:
                    wire.write(data)
                    wire_bytes += len(data)
                    yield data
            summary = capture.receive_chunks(recorded_chunks(), binding, work,
                'native-'+work.name.removeprefix('bounded-native-'), frames=plan['frames'],
                source_kind='physical_native_camera', build_record=build_record)
        summary['binding_file_sha256'] = binding_before
        summary['binding_unchanged_during_capture'] = capture.sha(binding_path) == binding_before
        summary['passed'] &= summary['binding_unchanged_during_capture']
        summary['wire_record'] = {'path': str(wire_path), 'sha256': capture.sha(wire_path), 'bytes': wire_bytes}
        summary['source_sha256'] = {str(path.relative_to(raw.ROOT)): capture.sha(path) for path in
            (Path(__file__), raw.ROOT/'tools/native_camera_capture.py', raw.ROOT/'tools/frame_protocol.py')}
        capture_path = work/'capture-summary.json'
        raw._new_json(capture_path, summary)
        result['capture_summary'] = {'path': str(capture_path), 'sha256': capture.sha(capture_path),
                                     'passed': summary['passed'], 'saved_frames': summary['saved_frames']}
        result['session_binding_path'] = str(binding_path)
    except (Exception, KeyboardInterrupt) as error:
        result['error'] = type(error).__name__+': '+str(error)
    finally:
        # COM must close before any exit programming. A failed close must not
        # bypass the independent heartbeat attempt.
        if chunks is not None:
            try:
                chunks.close()
            except (Exception, KeyboardInterrupt) as error:
                result['serial_close_error'] = type(error).__name__+': '+str(error)
        # KeyboardInterrupt inside raw programming can prevent its return;
        # its own finally still saves the programming-attempt receipt.
        receipt_path = Path(plan['raw_plan']['workdir'])/'receipt.json'
        if result['raw_program'] is None and raw_execution_entered:
            try:
                if receipt_path.is_file():
                    result['raw_program'] = capture.load_json(receipt_path)
                else:
                    raise ValueError('raw execution returned no receipt')
            except (Exception, KeyboardInterrupt) as error:
                result['raw_receipt_error'] = type(error).__name__+': '+str(error)
                result['programming_state_unknown'] = True
                # Missing/corrupt evidence cannot prove the raw design never
                # became active. Attempt the already-authorized fixed exit.
                active_attempted = True
        if isinstance(result['raw_program'], dict):
            active_attempted |= bool(result['raw_program'].get('programming_attempted') or
                                     result['raw_program'].get('passed') or result['raw_program'].get('done_confirmed'))
            result['hardware_accessed'] |= bool(result['raw_program'].get('hardware_accessed'))
        if active_attempted:
            result['idle_restoration_attempted'] = True
            try:
                result['idle_program'] = idle.execute_plan(plan['idle_plan'], timeout_seconds=90.)
                result['hardware_accessed'] |= bool(result['idle_program'].get('hardware_accessed'))
                result['idle_done_confirmed'] = bool(result['idle_program']['passed'] and result['idle_program']['done_confirmed'])
            except (Exception, KeyboardInterrupt) as error:
                result['idle_error'] = type(error).__name__+': '+str(error)
        if wire_path.is_file():
            result['wire_record'] = {'path': str(wire_path), 'sha256': capture.sha(wire_path), 'bytes': wire_path.stat().st_size}
        result['elapsed_seconds'] = time.monotonic()-started
        result['checked_at_utc'] = datetime.now(timezone.utc).isoformat()
        result['passed'] = bool(result['raw_program'] and result['raw_program'].get('passed') and
            result['capture_summary'] and result['capture_summary']['passed'] and
            result['idle_done_confirmed'] and 'serial_close_error' not in result and 'error' not in result)
        result['limits'] = 'The host completed this bounded attempt only. Idle needs fresh cfg_program and post-program DONE, not merely a closed COM port. No physical eye pairing, checkerboard calibration, temperature, HDMI output or later configuration persistence is established.'
        raw._new_json(work/'result.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binding', type=Path, required=True)
    parser.add_argument('--workdir', type=Path, required=True)
    parser.add_argument('--port', required=True)
    parser.add_argument('--frames', type=int, default=1)
    parser.add_argument('--seconds', type=float, default=35.)
    parser.add_argument('--frequency', choices=raw.FREQUENCIES, default='1MHz')
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    plan = prepare_plan(args.binding, args.workdir, port=args.port, frames=args.frames,
                        seconds=args.seconds, frequency=args.frequency)
    print(json.dumps({'plan': str(Path(plan['workdir'])/'plan.json'), 'executing': args.execute}), flush=True)
    result = execute_plan(plan) if args.execute else plan
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    return 0 if not args.execute or result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
