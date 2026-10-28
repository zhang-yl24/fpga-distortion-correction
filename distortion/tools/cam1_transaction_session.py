"""Fixed CAM1 register-transaction SRAM diagnostic; default plan, no Flash/RAW/TX."""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import json
import math
import re
import time
import uuid

import program_native_raw as hw
import program_idle_heartbeat as idle
import native_camera_capture as receiver
import bounded_diagnostic as bounded
import cam1_transaction_protocol as protocol

ROOT = Path(__file__).resolve().parents[1]
TARGET = 'cam1_transaction_probe'
PINS = {'clk_27m': 'D18', 'uart_txd': 'C24', 'cam_rst_n': 'T20',
        'cam_scl': 'W21', 'cam_sda': 'U14', 'led0': 'A20'}
CONTRACT = {'protocol': 'PGCAMD01', 'packet_bytes': 64, 'crc32_cover_bytes': 56,
    'baud': 921600, 'clock_hz': 27000000, 'quarter_cycles': 68, 'pad_mask': 0x7ff0,
    'readonly_failed_probe_addresses': [0x300a, 0x300b, 0x3018],
    'raw_frames': False, 'ddr_outputs': False, 'hdmi_outputs': False}


def limits(port, seconds, frequency):
    if not isinstance(port, str) or not re.fullmatch(r'COM[1-9][0-9]*', port):
        raise ValueError('explicit Windows COM port required')
    if type(seconds) not in (int, float) or not math.isfinite(seconds) or not 10 <= seconds <= 20:
        raise ValueError('receive-only session must be finite10..20seconds')
    if frequency not in ('1MHz', '5MHz'):
        raise ValueError('this diagnostic permits only1MHz or5MHz JTAG')


def helpers():
    names = ['cam1_transaction_session.py', 'cam1_transaction_protocol.py', 'program_native_raw.py',
             'program_idle_heartbeat.py', 'native_camera_capture.py', 'bounded_diagnostic.py',
             'build_cam1_transaction_probe.py']
    return {'tools/'+name: hw.sha(ROOT/'tools'/name) for name in names}


def validate_target(build_dir):
    base = Path(build_dir).resolve()
    if not base.is_dir() or not base.is_relative_to(hw.APPROVED.resolve()):
        raise ValueError('fixed diagnostic build must be inside approved scratch')
    mp = base/'validated-build.json'
    m = hw.load_json(mp)
    required = {'Target': TARGET, 'Device': 'PG2L100H', 'Package': 'FBG676',
                'SCBV': 'High Voltage', 'UnusedIO': 'UNUSED'}
    if any(m.get(key) != value for key, value in required.items()):
        raise ValueError('wrong target/device/contract; no generic target download permitted')
    canonical = lambda value: json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)
    if canonical(m.get('DiagnosticContract')) != canonical(CONTRACT):
        raise ValueError('diagnostic contract value/types differ')
    prepared = ROOT/f'board/{TARGET}-sources.json'
    declaration = hw.load_json(prepared)
    sources = declaration.get('source_files') if type(declaration) is dict else None
    bound = m.get('SourceSHA256', {})
    minimum = {f'board/{TARGET}.v', f'board/{TARGET}.fdc', f'board/{TARGET}-pins.json',
        f'board/build-{TARGET}.tcl',
        'rtl/experimental/ov5640_cadence_diagnostic_init.v', 'rtl/reg16_i2c.v',
        'rtl/uart_tx.v', 'board/ov5640_cadence_trial_commands.vh'}
    if (type(sources) is not list or any(type(name) is not str for name in sources)
            or len(sources) != len(set(sources)) or set(sources) != set(bound)
            or set(bound) != minimum or declaration.get('Target') != TARGET
            or declaration.get('SourceSHA256') != bound
            or canonical(declaration.get('DiagnosticContract')) != canonical(CONTRACT)
            or Path(m.get('PreparedSourceManifest', '')).resolve() != prepared.resolve()
            or m.get('PreparedSourceManifestSHA256', '').lower() != hw.sha(prepared).lower()):
        raise ValueError('fixed diagnostic dependency closure differs')
    for name, expected in bound.items():
        path = (ROOT/name).resolve()
        if not path.is_relative_to(ROOT) or not path.is_file() or hw.sha(path).lower() != expected.lower():
            raise ValueError('routed source missing/changed/escaped: '+name)
    pins = hw.load_json(ROOT/f'board/{TARGET}-pins.json')
    if pins != PINS:
        raise ValueError('diagnostic must use only the six reviewed CAM1 pins')
    artifacts = [('Bitstream', 'SHA256', base/'generate_bitstream'/f'{TARGET}.sbit'),
        ('TimingReport', 'TimingSHA256', base/'place_route'/f'{TARGET}_timing_summary_after_hold_fix.txt'),
        ('PinReport', 'PinReportSHA256', base/'place_route'/f'{TARGET}_prr.prt')]
    for name, key, path in artifacts:
        if (Path(m.get(name, '')).resolve() != path or not path.is_file()
                or path.stat().st_size == 0 or hw.sha(path).lower() != m.get(key, '').lower()):
            raise ValueError('named final artifact path/hash differs: '+name)
    timing = artifacts[1][2].read_text(encoding='utf-8', errors='replace')
    if not re.search(r'(?m)^\s*(?:Design Summary\s*:\s*)?All Constraints Met\.\s*$', timing):
        raise ValueError('final after-hold constraints not met')
    if bounded._routed_pins(artifacts[2][2]) != PINS:
        raise ValueError('actual routed pins differ from reviewed six pins')
    # Independent builder gate also checks electrical/direction attributes and
    # the exact original CAM1 pin references plus init/top simulation evidence.
    import build_cam1_transaction_probe as builder
    builder.validate_target(base)
    return {'target': TARGET, 'build_dir': str(base), 'bitstream_path': str(artifacts[0][2]),
        'bitstream_sha256': hw.sha(artifacts[0][2]), 'manifest_path': str(mp),
        'manifest_sha256': hw.sha(mp), 'source_sha256': bound,
        'diagnostic_contract': CONTRACT, 'helper_source_sha256': helpers()}


def prepare_plan(build_dir, workdir, *, port, seconds=12., frequency='5MHz'):
    limits(port, seconds, frequency)
    base = Path(workdir).resolve()
    if not base.is_dir() or not base.is_relative_to(hw.APPROVED.resolve()):
        raise ValueError('existing approved scratch directory required')
    validation = validate_target(build_dir)
    idle.validate_heartbeat()
    work = base/('cam1-transaction-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'-'+uuid.uuid4().hex[:8])
    work.mkdir(exist_ok=False)
    program = work/'diagnostic-program'
    program.mkdir()
    scripts = hw._scripts(validation, frequency)
    for stage, text in scripts.items():
        with (program/(stage+'.tcl')).open('x', encoding='utf-8') as stream:
            stream.write(text)
    nested = {'target': TARGET, 'operation': 'volatile_sram_only', 'validation': validation,
        'workdir': str(program), 'frequency': frequency, 'pds_bin': str(hw.resolve_pds_bin()),
        'tcl': {stage: {'path': str(program/(stage+'.tcl')), 'sha256': hw.sha(program/(stage+'.tcl'))} for stage in scripts}}
    plan = {'schema': 1, 'target': TARGET, 'operation': 'bounded_cam1_transaction_then_heartbeat',
        'executed': False, 'hardware_accessed': False, 'requires_explicit_execute_flag': True,
        'workdir': str(work), 'port': port, 'baud': 921600, 'seconds': seconds, 'frequency': frequency,
        'diagnostic_plan': nested, 'idle_plan': idle.prepare_plan(work, frequency=frequency),
        'source_sha256': helpers(), 'limits': 'Original full sensor initialization writes; three bounded '
        'read-only probes after retained failure. No raw capture, DDR, HDMI or UART commands. SRAM only; '
        'receive-only bounded session followed by fixed heartbeat is not a host-death watchdog.'}
    hw._new_json(work/'plan.json', plan)
    return plan


def _check_program_plan(plan, outer, frequency=None):
    if plan.get('target') != TARGET or plan.get('operation') != 'volatile_sram_only':
        raise ValueError('fixed diagnostic SRAM target required')
    if plan.get('frequency') not in ('1MHz', '5MHz') or (frequency is not None and plan['frequency'] != frequency):
        raise ValueError('nested programming frequency differs from the bounded session')
    bounded._check_tcl(plan, outer, plan['frequency'], hw._scripts)
    if validate_target(plan['validation']['build_dir']) != plan['validation']:
        raise ValueError('bound build/source/helper changed after planning')


def execute_program(plan):
    owned = []
    result = {'schema': 1, 'target': TARGET, 'operation': 'volatile_sram_only',
        'executed': True, 'hardware_accessed': False, 'programming_attempted': False,
        'done_confirmed': False, 'passed': False, 'workdir': plan['workdir']}
    try:
        _check_program_plan(plan, Path(plan['workdir']).parent)
        if hw.listening_pids(hw.PORT):
            raise RuntimeError('JTAG server port occupied; no other owner is used/stopped')
        pds = Path(plan['pds_bin'])
        server = hw._start_owned([str(pds/'cdt_js.exe'), '-port', str(hw.PORT), '-work_dir', plan['workdir']],
            Path(plan['workdir']), owned, 'server')
        result['hardware_accessed'] = True
        hw._await_owned_server(server)
        hw._owned_server_check(server)
        hw._check_scan(hw._client(plan, 'scan', owned, 90.))
        _check_program_plan(plan, Path(plan['workdir']).parent)
        previous = server
        server = hw._program_server_after_scan(server, plan, owned)
        result['server_restarted_after_scan'] = server is not previous
        result['programming_attempted'] = True
        hw._check_program(hw._client(plan, 'program', owned, 90.))
        _check_program_plan(plan, Path(plan['workdir']).parent)
        result.update(passed=True, done_confirmed=True)
    except (Exception, KeyboardInterrupt) as error:
        result['error'] = type(error).__name__+': '+str(error)
    finally:
        result['owned_pids'] = [process.pid for process in owned]
        result['terminated_owned_pids'], result['cleanup_errors'] = hw._stop_owned(owned)
        result['passed'] &= not result['cleanup_errors']
        result['logs'] = {str(path): hw.sha(path) for path in Path(plan['workdir']).glob('*.log')}
        result['checked_at_utc'] = datetime.now(timezone.utc).isoformat()
        hw._new_json(Path(plan['workdir'])/'receipt.json', result)
    return result


def execute_plan(plan):
    work = Path(plan['workdir']).resolve()
    limits(plan['port'], plan['seconds'], plan['frequency'])
    if (not work.is_dir() or not work.is_relative_to(hw.APPROVED.resolve()) or (work/'result.json').exists()
            or hw.load_json(work/'plan.json') != plan or plan.get('target') != TARGET
            or plan.get('operation') != 'bounded_cam1_transaction_then_heartbeat'
            or plan.get('baud') != 921600 or plan.get('source_sha256') != helpers()):
        raise ValueError('fresh unmodified fixed diagnostic session plan required')
    _check_program_plan(plan['diagnostic_plan'], work, plan['frequency'])
    if (plan['idle_plan'].get('target') != 'heartbeat'
            or plan['idle_plan'].get('operation') != 'volatile_sram_only'
            or idle.validate_heartbeat() != plan['idle_plan']['validation']):
        raise ValueError('fixed heartbeat exit changed')
    bounded._check_tcl(plan['idle_plan'], work, plan['frequency'], idle._scripts)
    result = {'schema': 1, 'target': TARGET, 'executed': True, 'hardware_accessed': False,
        'passed': False, 'workdir': str(work), 'diagnostic_program': None, 'idle_program': None,
        'idle_restoration_attempted': False, 'idle_done_confirmed': False, 'raw_frame_certified': False}
    chunks = None
    entered = False
    wire = work/'received-diagnostic-wire.bin'
    started = time.monotonic()
    try:
        entered = True
        result['diagnostic_program'] = execute_program(plan['diagnostic_plan'])
        program = result['diagnostic_program']
        result['hardware_accessed'] = bool(program.get('hardware_accessed'))
        if not program.get('passed') or not program.get('done_confirmed'):
            raise RuntimeError('diagnostic SRAM/DONE unconfirmed; COM stays closed')
        chunks = receiver.serial_chunks(plan['port'], 921600, plan['seconds'])
        with wire.open('xb') as stream:
            for data in chunks:
                stream.write(data)
        if (helpers() != plan['source_sha256'] or
                validate_target(plan['diagnostic_plan']['validation']['build_dir']) != plan['diagnostic_plan']['validation']):
            raise RuntimeError('source/build/helper changed during diagnostic reception')
        result['sources_unchanged_during_session'] = True
    except (Exception, KeyboardInterrupt) as error:
        result['error'] = type(error).__name__+': '+str(error)
    finally:
        if chunks is not None:
            try:
                chunks.close()
            except (Exception, KeyboardInterrupt) as error:
                result['serial_close_error'] = str(error)
        if entered and result['diagnostic_program'] is None:
            try:
                result['diagnostic_program'] = hw.load_json(Path(plan['diagnostic_plan']['workdir'])/'receipt.json')
            except (Exception, KeyboardInterrupt) as error:
                result['programming_state_unknown'] = True
                result['program_receipt_error'] = str(error)
        program = result['diagnostic_program']
        if not isinstance(program, dict):
            result['programming_state_unknown'] = True
            program = {}
        attempted = (result.get('programming_state_unknown') or type(program.get('programming_attempted')) is not bool
            or program.get('programming_attempted') or program.get('done_confirmed') or program.get('passed'))
        result['hardware_accessed'] |= bool(program.get('hardware_accessed'))
        if attempted:
            result['idle_restoration_attempted'] = True
            try:
                result['idle_program'] = idle.execute_plan(plan['idle_plan'], timeout_seconds=90.)
                result['hardware_accessed'] |= bool(result['idle_program'].get('hardware_accessed'))
                result['idle_done_confirmed'] = bool(result['idle_program'].get('passed') and result['idle_program'].get('done_confirmed'))
            except (Exception, KeyboardInterrupt) as error:
                result['idle_error'] = str(error)
        if wire.is_file():
            result['wire'] = {'path': str(wire), 'bytes': wire.stat().st_size, 'sha256': hw.sha(wire)}
        result['passed'] = bool(program.get('passed') and result.get('wire', {}).get('bytes', 0)
            and result['idle_done_confirmed'] and 'error' not in result and 'serial_close_error' not in result)
        result['elapsed_seconds'] = time.monotonic()-started
        result['checked_at_utc'] = datetime.now(timezone.utc).isoformat()
        result['limits'] = 'Programming and bounded receive only; decoder separately verifies packets. '
        'Sensor ready, wiring, physical eyes, temperatures and optical calibration are not certified. '
        'Heartbeat is a confirmed SRAM event only, not continuous supervision or a host-death watchdog.'
        hw._new_json(work/'result.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build-dir', type=Path, required=True)
    parser.add_argument('--workdir', type=Path, required=True)
    parser.add_argument('--port', required=True)
    parser.add_argument('--seconds', type=float, default=12.)
    parser.add_argument('--frequency', choices=('1MHz', '5MHz'), default='5MHz')
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    plan = prepare_plan(args.build_dir, args.workdir, port=args.port, seconds=args.seconds, frequency=args.frequency)
    print(json.dumps({'plan': str(Path(plan['workdir'])/'plan.json'), 'executing': args.execute}), flush=True)
    result = execute_plan(plan) if args.execute else plan
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0 if not args.execute or result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
