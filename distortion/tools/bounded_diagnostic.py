"""Bounded headless SRAM diagnostics for two explicit targets, then heartbeat.

Default is file validation and plans only. Execution is volatile SRAM only,
then 10--20 seconds of receive-only UART, COM closure and an independent fixed
heartbeat programming attempt in finally. camera_isp_probe_d5 initializes/writes
the sensor and HDMI before its register scanner reads; it is not write-free.
This host finally block is not a hardware watchdog and produces no raw-frame
or physical identity certification.
"""
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

ROOT = Path(__file__).resolve().parents[1]
CODE_ROOT = ROOT
TARGETS = ('thermal_idle', 'camera_isp_probe_d5')
DIAGNOSTIC_FREQUENCIES = tuple(value for value in hw.FREQUENCIES if value != '100KHz')
CAMERA_BIT_SHA = 'ABACC9BA80B292213D9E26382506E90F033CF3D5105713230C59257FAC1B6E54'
CAMERA_ARTIFACT_SHA = {
    'validated-build.json': '576B761E389EEEB78F105A3F9D378D14000D9F4C4374E94B699C21ABA0D492DC',
    'place_route/camera_isp_probe_timing_summary_after_hold_fix.txt': '5A04DD712D5B4C2246BC2B867E0D23B40BBEF23EFD9DC3AACE5BBA8C39D3AB7A',
    'place_route/camera_isp_probe_prr.prt': '6ED99778C613CB95E4C5DA55F5D1BB5D89C3046AF6A34FE93E49F1F579972B4F',
}
THERMAL_FILES = (
    'rtl/logos2_temperature_monitor.v', 'rtl/adc_temperature_reader.v', 'rtl/uart_tx.v',
    'rtl/thermal_idle_telemetry.v', 'board/thermal_idle.v', 'board/thermal_idle.fdc',
    'board/thermal_idle-pins.json', 'board/build-thermal_idle.tcl',
)
THERMAL_CONTRACT = {'protocol': 'THERMAL_IDLE_V1', 'uart_baud': 921600, 'clock_hz': 27000000,
    'period_cycles': 13500000, 'camera_outputs': False, 'ddr_outputs': False, 'hdmi_outputs': False}
THERMAL_PINS = {'clk_27m': 'D18', 'uart_txd': 'C24', 'led[0]': 'A20', 'led[1]': 'C18',
    'led[2]': 'C19', 'led[3]': 'E18', 'led[4]': 'A17', 'led[5]': 'A18', 'led[6]': 'C17', 'led[7]': 'B17'}


def _helpers():
    return {str(path.relative_to(CODE_ROOT)): hw.sha(path) for path in
        (Path(__file__), CODE_ROOT/'tools/program_native_raw.py', CODE_ROOT/'tools/program_idle_heartbeat.py',
         CODE_ROOT/'tools/native_camera_capture.py')}


def _limits(target, port, seconds, frequency):
    if target not in TARGETS:
        raise ValueError('only thermal_idle and the D5-corrected camera_isp_probe_d5 are permitted; the legacy AA22 probe is forbidden')
    if not isinstance(port, str) or not re.fullmatch(r'COM[1-9][0-9]*', port):
        raise ValueError('an explicit Windows COM port is required')
    if type(seconds) not in (int, float) or not math.isfinite(seconds) or not 10 <= seconds <= 20:
        raise ValueError('headless diagnostic reception must be finite within 10..20 seconds')
    if frequency not in DIAGNOSTIC_FREQUENCIES:
        raise ValueError('SRAM diagnostics require at least 500KHz within the bounded program timeout; 100KHz is scan-only')


def _fixed_file(base, name):
    path = (Path(base)/name).resolve()
    if not path.is_relative_to(Path(base).resolve()) or not path.is_file():
        raise ValueError('required diagnostic artifact is missing or escaped: '+name)
    return path


def _routed_pins(path):
    active = {}
    for line in path.read_text(encoding='utf-8', errors='replace').splitlines():
        fields = line.split('|')
        if len(fields) >= 7 and fields[4]:
            port = fields[4]
            if fields[6] != 'YES' or port in active:
                raise ValueError('duplicate/inactive routed diagnostic port: '+port)
            active[port] = fields[0]
    return active


def _validate_probe_clone(prepared):
    legacy = ROOT/'build/camera_isp_probe/validated-build.json'
    if hw.sha(legacy).upper() != CAMERA_ARTIFACT_SHA['validated-build.json']:
        raise ValueError('fixed legacy reference manifest changed; cannot verify the exact D5 clone')
    source_hashes = hw.load_json(legacy)['SourceSHA256']
    original_names = hw.load_json(ROOT/'board/camera_isp_probe-sources.json')
    names = [name.replace('camera_isp_probe', 'camera_isp_probe_d5') for name in original_names]
    if len(original_names) != 16 or prepared != names:
        raise ValueError('D5 probe must clone the exact legacy 16-file prepared dependency list')
    for old_name, new_name in zip(original_names, names):
        old_path, new_path = _fixed_file(ROOT, old_name), _fixed_file(ROOT, new_name)
        if hw.sha(old_path).lower() != source_hashes[old_name].lower():
            raise ValueError('fixed legacy probe reference source changed: '+old_name)
        if old_name == new_name:
            continue
        if old_name.endswith('-sources.json'):
            continue
        if old_name.endswith('-pins.json'):
            pins = hw.load_json(old_path)
            pins['cam_data[5]'] = 'AA23'
            if hw.load_json(new_path) != pins:
                raise ValueError('D5 clone pin map contains changes beyond cam_data[5] AA23')
        else:
            original = old_path.read_text(encoding='utf-8-sig')
            if old_name.endswith('.fdc'):
                line = 'define_attribute {p:cam_data[5]} {PAP_IO_LOC} {AA22}'
                if original.count(line) != 1:
                    raise ValueError('legacy D5 constraint is not the expected unique AA22 line')
                expected = original.replace(line, line.replace('{AA22}', '{AA23}'))
            elif old_name.endswith('.v'):
                expected = original.replace('module camera_isp_probe(', 'module camera_isp_probe_d5(')
            else:
                expected = original.replace('camera_isp_probe', 'camera_isp_probe_d5')
            if new_path.read_text(encoding='utf-8-sig') != expected:
                raise ValueError('probe source differs from the exact target-name/D5-only clone: '+new_name)
    return set(names)


def validate_target(target, *, thermal_build_dir=None, probe_build_dir=None):
    if target == 'camera_isp_probe':
        raise ValueError('legacy camera_isp_probe is a known AA22/D5 candidate and is forbidden')
    if target not in TARGETS:
        raise ValueError('unlisted diagnostic target')
    prepared_path = _fixed_file(ROOT, 'board/'+target+'-sources.json')
    prepared = hw.load_json(prepared_path)
    if target == 'camera_isp_probe_d5':
        if thermal_build_dir is not None:
            raise ValueError('D5 probe cannot use a thermal artifact directory')
        if probe_build_dir is None:
            raise ValueError('D5 probe requires its explicitly selected approved build directory')
        base = Path(probe_build_dir).resolve()
        if not base.is_dir() or not base.is_relative_to(hw.APPROVED.resolve()):
            raise ValueError('probe build directory must already exist inside approved scratch')
        expected_names = _validate_probe_clone(prepared)
    else:
        if probe_build_dir is not None:
            raise ValueError('thermal idle cannot use a probe artifact directory')
        if thermal_build_dir is None:
            raise ValueError('thermal_idle needs its explicitly selected approved build directory')
        base = Path(thermal_build_dir).resolve()
        if not base.is_dir() or not base.is_relative_to(hw.APPROVED.resolve()):
            raise ValueError('thermal build directory must already exist inside approved scratch')
        if (not isinstance(prepared, dict) or prepared.get('target') != target or
                set(prepared.get('source_files', [])) != set(THERMAL_FILES) or
                prepared.get('ThermalIdleContract') != THERMAL_CONTRACT):
            raise ValueError('thermal prepared source set or no-camera/DDR/HDMI contract differs')
        expected_names = set(THERMAL_FILES)
    manifest_path = _fixed_file(base, 'validated-build.json')
    manifest = hw.load_json(manifest_path)
    if manifest.get('Device') != 'PG2L100H' or manifest.get('Package') != 'FBG676' or manifest.get('SCBV') != 'High Voltage' or manifest.get('UnusedIO') != 'UNUSED':
        raise ValueError('diagnostic build must be PG2L100H FBG676 High Voltage with unused IO UNUSED')
    if target == 'thermal_idle' and (manifest.get('Target') != target or manifest.get('ThermalIdleContract') != THERMAL_CONTRACT):
        raise ValueError('thermal build target or contract differs')
    if target == 'camera_isp_probe_d5' and manifest.get('Target') != target:
        raise ValueError('camera ISP manifest target differs')
    bit = _fixed_file(base, 'generate_bitstream/'+target+'.sbit')
    if Path(manifest.get('Bitstream', '')).resolve() != bit:
        raise ValueError('manifest points outside the fixed target bitstream location')
    bit_sha = hw.sha(bit)
    if bit_sha.lower() != str(manifest.get('SHA256', '')).lower():
        raise ValueError('diagnostic bitstream SHA256 differs from its bound/fixed artifact')
    sources = manifest.get('SourceSHA256')
    if not isinstance(sources, dict) or not sources:
        raise ValueError('diagnostic build must have full source hashes')
    if target == 'thermal_idle':
        expected = prepared.get('SourceSHA256')
        if not isinstance(expected, dict) or set(expected) != expected_names:
            raise ValueError('thermal prepared source hashes do not close the fixed eight-file source set')
        allowed_names = [expected_names, expected_names | {'board/thermal_idle-sources.json'}]
        if set(sources) not in allowed_names or any(str(sources[name]).lower() != str(expected[name]).lower() for name in expected):
            raise ValueError('thermal build source closure differs from prepared dependencies')
        if 'board/thermal_idle-sources.json' in sources and str(sources['board/thermal_idle-sources.json']).lower() != hw.sha(prepared_path).lower():
            raise ValueError('thermal prepared manifest hash differs')
    elif set(sources) != expected_names:
        raise ValueError('camera ISP build closure differs from the fixed 16 prepared files')
    for name, expected in sources.items():
        path = _fixed_file(ROOT, name)
        if hw.sha(path).lower() != str(expected).lower():
            raise ValueError('diagnostic source changed: '+name)
    pins_path = _fixed_file(ROOT, 'board/'+target+'-pins.json')
    pins = hw.load_json(pins_path)
    if not isinstance(pins, dict) or len(pins) != len(set(pins.values())):
        raise ValueError('diagnostic pin map has collisions')
    if target == 'thermal_idle' and pins != THERMAL_PINS:
        raise ValueError('thermal target must have exactly fixed clock/LED/UART pins')
    if target == 'camera_isp_probe_d5' and pins.get('cam_data[5]') != 'AA23':
        raise ValueError('camera ISP CAM2 D5 must remain AA23')
    routed = _fixed_file(base, 'place_route/'+target+'_prr.prt')
    if _routed_pins(routed) != pins:
        raise ValueError('actual routed active ports/pins differ from the fixed board map')
    final_timing = _fixed_file(base, 'place_route/'+target+'_timing_summary_after_hold_fix.txt')
    if not re.search(r'(?m)^Design Summary\s*:\s*All Constraints Met\.\s*$', final_timing.read_text(encoding='utf-8', errors='replace')):
        raise ValueError('final after-hold timing has not met all constraints')
    declared_timing = Path(manifest.get('TimingReport', '')).resolve()
    allowed_timing = {final_timing, (base/'report_timing'/(target+'.rtr')).resolve()}
    if declared_timing not in allowed_timing or not declared_timing.is_file() or hw.sha(declared_timing).lower() != str(manifest.get('TimingSHA256', '')).lower():
        raise ValueError('manifest timing report path/hash is not the fixed target timing artifact')
    return {'target': target, 'build_dir': str(base), 'bitstream_path': str(bit), 'bitstream_sha256': bit_sha,
        'manifest_path': str(manifest_path), 'manifest_sha256': hw.sha(manifest_path),
        'prepared_source_manifest_sha256': hw.sha(prepared_path), 'source_sha256': dict(sources),
        'final_after_hold_timing_sha256': hw.sha(final_timing), 'routed_pins_sha256': hw.sha(routed),
        'verified_pins': pins, 'helper_source_sha256': _helpers(),
        'camera_initialization_writes_registers': target == 'camera_isp_probe_d5',
        'raw_frame_role_certified': False, 'diagnostic_temperature_or_register_values_verified': False}


def _check_tcl(nested, outer_work, frequency, provider):
    folder = Path(nested['workdir']).resolve()
    if not folder.is_relative_to(outer_work) or (folder/'receipt.json').exists() or nested.get('frequency') != frequency:
        raise ValueError('diagnostic/idle program plan must be fresh and inside this invocation')
    for stage, text in provider(nested['validation'], frequency).items():
        path = Path(nested['tcl'][stage]['path']).resolve()
        if path != folder/(stage+'.tcl') or path.read_text(encoding='utf-8') != text or hw.sha(path) != nested['tcl'][stage]['sha256']:
            raise ValueError('diagnostic/idle Tcl changed after planning')
    hw.resolve_pds_bin(nested['pds_bin'])


def prepare_plan(target, workdir, *, port, seconds=12., frequency='1MHz', thermal_build_dir=None, probe_build_dir=None):
    _limits(target, port, seconds, frequency)
    base = Path(workdir).resolve()
    if not base.is_dir() or not base.is_relative_to(hw.APPROVED.resolve()):
        raise ValueError('workdir must already exist inside approved scratch')
    validation = validate_target(target, thermal_build_dir=thermal_build_dir, probe_build_dir=probe_build_dir)
    idle.validate_heartbeat()
    pds = hw.resolve_pds_bin()
    work = base/('bounded-diagnostic-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'-'+uuid.uuid4().hex[:8])
    work.mkdir(exist_ok=False)
    program_dir = work/'diagnostic-program'
    program_dir.mkdir()
    scripts = hw._scripts(validation, frequency)
    for stage, text in scripts.items():
        (program_dir/(stage+'.tcl')).write_text(text, encoding='utf-8')
    nested = {'target': target, 'operation': 'volatile_sram_only', 'validation': validation,
        'frequency': frequency, 'workdir': str(program_dir), 'pds_bin': str(pds),
        'tcl': {stage: {'path': str(program_dir/(stage+'.tcl')), 'sha256': hw.sha(program_dir/(stage+'.tcl'))} for stage in scripts}}
    plan = {'schema': 1, 'operation': 'bounded_headless_diagnostic_then_heartbeat', 'target': target,
        'hardware_accessed': False, 'executed': False, 'workdir': str(work), 'port': port, 'baud': 921600,
        'seconds': seconds, 'frequency': frequency, 'thermal_build_dir': str(thermal_build_dir) if thermal_build_dir else None,
        'probe_build_dir': str(probe_build_dir) if probe_build_dir else None,
        'diagnostic_plan': nested, 'idle_plan': idle.prepare_plan(work, frequency=frequency), 'source_sha256': _helpers(),
        'limits': 'Plan only. camera_isp_probe_d5 initializes/writes sensor and HDMI, then reads ISP state. thermal_idle has no camera/DDR/HDMI outputs. Execution is bounded receive-only UART with independent heartbeat finally, not a watchdog, raw-frame certification or actual-temperature acceptance.'}
    hw._new_json(work/'plan.json', plan)
    return plan


def _execute_program(plan):
    """Own both scan and post-scan program servers; no target-general CLI."""
    owned = []
    result = {'target': plan['target'], 'hardware_accessed': False, 'programming_attempted': False,
              'passed': False, 'done_confirmed': False}
    try:
        if plan['target'] not in TARGETS or plan.get('operation') != 'volatile_sram_only':
            raise ValueError('unlisted SRAM diagnostic plan')
        if hw.listening_pids(hw.PORT):
            raise RuntimeError('JTAG server port is occupied; no unrelated process is used/stopped')
        pds = Path(plan['pds_bin'])
        server = hw._start_owned([str(pds/'cdt_js.exe'), '-port', str(hw.PORT), '-work_dir', plan['workdir']],
                                 Path(plan['workdir']), owned, 'server')
        result['hardware_accessed'] = True
        hw._await_owned_server(server)
        hw._owned_server_check(server)
        hw._check_scan(hw._client(plan, 'scan', owned, 90.))
        kwargs = {'thermal_build_dir': plan['validation']['build_dir']} if plan['target'] == 'thermal_idle' else {'probe_build_dir': plan['validation']['build_dir']}
        if validate_target(plan['target'], **kwargs) != plan['validation']:
            raise ValueError('diagnostic artifacts changed after scanning')
        previous = server
        server = hw._program_server_after_scan(server, plan, owned)
        result['server_restarted_after_scan'] = server is not previous
        result['programming_attempted'] = True
        hw._check_program(hw._client(plan, 'program', owned, 90.))
        if validate_target(plan['target'], **kwargs) != plan['validation']:
            raise ValueError('diagnostic artifacts changed during programming')
        result.update(passed=True, done_confirmed=True)
    except (Exception, KeyboardInterrupt) as error:
        result['error'] = type(error).__name__+': '+str(error)
    finally:
        result['owned_pids'] = [process.pid for process in owned]
        result['terminated_owned_pids'], result['cleanup_errors'] = hw._stop_owned(owned)
        result['passed'] &= not result['cleanup_errors']
        result['logs'] = {str(path): hw.sha(path) for path in Path(plan['workdir']).glob('*.log')}
        hw._new_json(Path(plan['workdir'])/'receipt.json', result)
    return result


def execute_plan(plan):
    work = Path(plan['workdir']).resolve()
    _limits(plan['target'], plan['port'], plan['seconds'], plan['frequency'])
    if (not work.is_dir() or not work.is_relative_to(hw.APPROVED.resolve()) or
            (work/'result.json').exists() or plan.get('operation') != 'bounded_headless_diagnostic_then_heartbeat' or
            plan.get('baud') != 921600 or hw.load_json(work/'plan.json') != plan or _helpers() != plan['source_sha256']):
        raise ValueError('fresh unmodified fixed diagnostic plan is required')
    if validate_target(plan['target'], thermal_build_dir=plan['thermal_build_dir'], probe_build_dir=plan['probe_build_dir']) != plan['diagnostic_plan']['validation']:
        raise ValueError('diagnostic artifact validation changed')
    if idle.validate_heartbeat() != plan['idle_plan']['validation']:
        raise ValueError('fixed heartbeat exit changed')
    if (plan['diagnostic_plan'].get('target') != plan['target'] or plan['diagnostic_plan'].get('operation') != 'volatile_sram_only' or
            plan['idle_plan'].get('target') != 'heartbeat' or plan['idle_plan'].get('operation') != 'volatile_sram_only'):
        raise ValueError('diagnostic/exit target metadata changed')
    _check_tcl(plan['diagnostic_plan'], work, plan['frequency'], hw._scripts)
    _check_tcl(plan['idle_plan'], work, plan['frequency'], idle._scripts)
    result = {'schema': 1, 'target': plan['target'], 'executed': True, 'passed': False, 'hardware_accessed': False,
        'diagnostic_program': None, 'idle_program': None, 'idle_restoration_attempted': False,
        'idle_done_confirmed': False, 'raw_frame_role_certified': False, 'temperature_measured': False,
        'sensor_register_writes_independently_observed': False, 'hardware_watchdog_installed': False,
        'workdir': str(work)}
    entered, chunks, started = False, None, time.monotonic()
    wire = work/'received-status-wire.bin'
    try:
        entered = True
        result['diagnostic_program'] = _execute_program(plan['diagnostic_plan'])
        program = result['diagnostic_program']
        result['hardware_accessed'] = bool(program.get('hardware_accessed'))
        if not program['passed'] or not program['done_confirmed']:
            raise RuntimeError('diagnostic SRAM program/DONE unconfirmed; COM remains unopened')
        chunks = receiver.serial_chunks(plan['port'], 921600, plan['seconds'])
        with wire.open('xb') as stream:
            for data in chunks:
                stream.write(data)
        result['wire_record'] = {'path': str(wire), 'bytes': wire.stat().st_size, 'sha256': hw.sha(wire)}
    except (Exception, KeyboardInterrupt) as error:
        result['error'] = type(error).__name__+': '+str(error)
    finally:
        if chunks is not None:
            try:
                chunks.close()
            except (Exception, KeyboardInterrupt) as error:
                result['serial_close_error'] = type(error).__name__+': '+str(error)
        if result['diagnostic_program'] is None and entered:
            try:
                receipt = hw.load_json(Path(plan['diagnostic_plan']['workdir'])/'receipt.json')
                if not isinstance(receipt, dict) or type(receipt.get('programming_attempted')) is not bool:
                    raise ValueError('diagnostic programming receipt is not a valid attempt record')
                result['diagnostic_program'] = receipt
            except (Exception, KeyboardInterrupt) as error:
                result['programming_state_unknown'] = True
                result['program_receipt_error'] = type(error).__name__+': '+str(error)
        program = result['diagnostic_program'] or {}
        attempted = bool(program.get('programming_attempted') or program.get('done_confirmed') or program.get('passed') or result.get('programming_state_unknown'))
        result['camera_initialization_may_write_registers'] = plan['target'] == 'camera_isp_probe_d5' and attempted
        result['hardware_accessed'] |= bool(program.get('hardware_accessed'))
        if attempted:
            result['idle_restoration_attempted'] = True
            try:
                result['idle_program'] = idle.execute_plan(plan['idle_plan'], timeout_seconds=90.)
                result['hardware_accessed'] |= bool(result['idle_program'].get('hardware_accessed'))
                result['idle_done_confirmed'] = bool(result['idle_program']['passed'] and result['idle_program']['done_confirmed'])
            except (Exception, KeyboardInterrupt) as error:
                result['idle_error'] = type(error).__name__+': '+str(error)
        if wire.is_file():
            result['wire_record'] = {'path': str(wire), 'bytes': wire.stat().st_size, 'sha256': hw.sha(wire)}
        result['passed'] = bool(program.get('passed') and result.get('wire_record', {}).get('bytes', 0) > 0 and
            result['idle_done_confirmed'] and 'error' not in result and 'serial_close_error' not in result)
        result['elapsed_seconds'] = time.monotonic()-started
        result['checked_at_utc'] = datetime.now(timezone.utc).isoformat()
        result['limits'] = 'This receipt covers programming, bounded status bytes and heartbeat restoration only. Payload telemetry/CRC, actual ADC validity, temperature and ISP register values require separate decoding; this receipt never certifies raw frames or actual physical eye identity. Camera ISP target initializes/writes before its scanner reads. Host finally cannot protect against host death, lost JTAG or loss of power.'
        hw._new_json(work/'result.json', result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target', choices=TARGETS, required=True)
    parser.add_argument('--workdir', type=Path, required=True)
    parser.add_argument('--thermal-build-dir', type=Path)
    parser.add_argument('--probe-build-dir', type=Path)
    parser.add_argument('--port', required=True)
    parser.add_argument('--seconds', type=float, default=12.)
    parser.add_argument('--frequency', choices=DIAGNOSTIC_FREQUENCIES, default='1MHz')
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args(argv)
    plan = prepare_plan(args.target, args.workdir, port=args.port, seconds=args.seconds,
                        frequency=args.frequency, thermal_build_dir=args.thermal_build_dir, probe_build_dir=args.probe_build_dir)
    result = execute_plan(plan) if args.execute else plan
    print(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False))
    return 0 if not args.execute or result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
