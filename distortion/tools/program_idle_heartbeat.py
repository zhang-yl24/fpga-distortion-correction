"""Plan, or explicitly execute, ONLY the previously validated heartbeat SRAM.

No COM access, arbitrary target, Flash command, legacy status/history update,
or use/termination of another invocation's JTAG server is permitted.
"""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import json
import math
import re
import uuid

import program_native_raw as hw

ROOT = Path(__file__).resolve().parents[1]
CODE_ROOT = ROOT
APPROVED = ROOT/'build/offline-20261024'
TARGET = 'heartbeat'
GOLDEN_BIT_SHA256 = 'DF7EEC4B4E38441183B45BAF8B38D8414FDD456A5EB78FB3AEB1FD94B361B360'
SOURCE_SHA256 = {
    'board/heartbeat.v': '1C7B86A5186CF882D55695CE7B1A337E5E36243FB46EFD2E544EBF606C58333E',
    'board/heartbeat.fdc': '18B8E831D8C514B8F2790542615BB8BDE9347DA9F77F688BE4A49F5AEEA43359',
    'board/build-heartbeat.tcl': 'C7C41CA065CC243022002AFF048FCBAB7445D5BFD1C8A49E50404AE14CB867A8',
}
ARTIFACT_SHA256 = {
    'build/heartbeat/validated-build.json': '1AE6CED8DE9990F11FB33589A6607F7BA8BF77CF132EF70ACA8FA071304F8006',
    'build/heartbeat/build.log': 'B8535BF02B4A2599324B77B3102EBD4E6068A30FCBE0C07C2626BD28011371DA',
    'build/heartbeat/place_route/heartbeat_prr.prt': '70950B934BB1EA9E84716D5D60021C195AEF06F318CE4D4834A111864C71CE9D',
    'build/heartbeat/place_route/heartbeat_timing_summary_after_hold_fix.txt': 'A69C12B0F882C13E92C6B9394F78904E07347DE140B04E89C46DA71E0CC70C41',
}
PINS = {'clk_27m': 'D18', 'led[0]': 'A20', 'led[1]': 'C18', 'led[2]': 'C19',
        'led[3]': 'E18', 'led[4]': 'A17', 'led[5]': 'A18', 'led[6]': 'C17', 'led[7]': 'B17'}

# SRAM-ONE: 3,791,112 bytes at 1MHz, Program30.9s and shell output
# window42.79s. Reserve20s shell overhead, then50% margin; do not use UART time.
DEFAULT_CLIENT_TIMEOUT = 90.
MAX_CLIENT_TIMEOUT = 120.
FREQUENCY_HZ = {'100KHz':100_000,'500KHz':500_000,'1MHz':1_000_000,
                '5MHz':5_000_000,'10MHz':10_000_000}


def program_budget(validation, frequency, timeout_seconds):
    """File-only, bounded per-shell budget; not a hardware watchdog."""
    if frequency not in FREQUENCY_HZ:
        raise ValueError('known JTAG frequency required for programming budget')
    size = Path(validation['bitstream_path']).stat().st_size
    if size <= 0:
        raise ValueError('nonempty bitstream required for programming budget')
    wire = size*8/FREQUENCY_HZ[frequency]
    minimum = math.ceil(1.5*(wire+20.))
    if (type(timeout_seconds) not in (int,float) or not math.isfinite(timeout_seconds)
            or not minimum <= timeout_seconds <= MAX_CLIENT_TIMEOUT):
        raise ValueError(f'program client budget must be finite in [{minimum},120] seconds')
    return {'policy':'wire-plus20s-times1.5-v1','bitstream_bytes':size,
        'frequency_hz':FREQUENCY_HZ[frequency],'wire_seconds':wire,
        'minimum_client_seconds':minimum,'client_timeout_seconds':timeout_seconds,
        'server_startup_bound_seconds':20., 'owned_cleanup_bound_seconds':40.,
        'operation_wait_bound_seconds':2*timeout_seconds+20.+40.}


def validate_program_budget(plan):
    bound = plan.get('program_budget')
    if not isinstance(bound,dict) or 'client_timeout_seconds' not in bound:
        raise ValueError('explicit sealed programming budget required; no legacy-plan migration')
    expected = program_budget(plan['validation'],plan['frequency'],bound['client_timeout_seconds'])
    if bound != expected:
        raise ValueError('sealed programming budget differs from bit/frequency/policy')
    return bound


def _file(name):
    path = (ROOT/name).resolve()
    if not path.is_relative_to(ROOT.resolve()) or not path.is_file():
        raise ValueError('missing or escaped heartbeat file: '+name)
    return path


def validate_heartbeat():
    """Read-only pinning of the exact shipped heartbeat, not a new build."""
    bit = _file('build/heartbeat/generate_bitstream/heartbeat.sbit')
    if hw.sha(bit).upper() != GOLDEN_BIT_SHA256:
        raise ValueError('heartbeat bitstream differs from the fixed validated SHA256')
    for name, expected in {**SOURCE_SHA256, **ARTIFACT_SHA256}.items():
        if hw.sha(_file(name)).upper() != expected:
            raise ValueError('heartbeat bound file changed: '+name)
    manifest_path = _file('build/heartbeat/validated-build.json')
    manifest = hw.load_json(manifest_path)
    if (manifest.get('Device') != 'PG2L100H' or manifest.get('Package') != 'FBG676' or
        manifest.get('SCBV') != 'High Voltage' or manifest.get('UnusedIO') != 'UNUSED' or
        str(manifest.get('SHA256', '')).upper() != GOLDEN_BIT_SHA256):
        raise ValueError('heartbeat manifest is not the exact PG2L100H FBG676 high-voltage SRAM baseline')
    if Path(manifest.get('Bitstream', '')).name != 'heartbeat.sbit':
        raise ValueError('heartbeat manifest names an unrelated bitstream')
    timing = _file('build/heartbeat/place_route/heartbeat_timing_summary_after_hold_fix.txt')
    if not re.search(r'(?m)^Design Summary\s*:\s*All Constraints Met\.\s*$', timing.read_text(errors='replace')):
        raise ValueError('heartbeat final timing has not met all constraints')
    build_log = _file('build/heartbeat/build.log').read_text(errors='replace')
    if re.search(r'(?m)^E:', build_log) or not re.search(
            r'(?m)^Executing : gen_bit_stream -scbv \{High Voltage\} -unused_io_status UNUSED successfully\.\s*$', build_log):
        raise ValueError('heartbeat bitstream generation was not completed successfully')
    # The fixed recipe contains exactly one source and one constraint, no IP.
    recipe = _file('board/build-heartbeat.tcl').read_text()
    design = re.findall(r'(?m)^add_design\s+([^\r\n]+)', recipe)
    constraints = re.findall(r'(?m)^add_constraint\s+([^\r\n]+)', recipe)
    if len(design) != 1 or not design[0].endswith('/board/heartbeat.v') or len(constraints) != 1 or not constraints[0].endswith('/board/heartbeat.fdc'):
        raise ValueError('heartbeat source dependency closure is not the fixed one-source design')
    active = {}
    for line in _file('build/heartbeat/place_route/heartbeat_prr.prt').read_text().splitlines():
        fields = line.split('|')
        if len(fields) >= 7 and fields[4]:
            port = fields[4]
            if port in active:
                raise ValueError('duplicate active heartbeat pin: '+port)
            active[port] = fields[0]
            if fields[5] != ('input' if port == 'clk_27m' else 'output') or fields[6] != 'YES':
                raise ValueError('heartbeat pin direction/used status differs: '+port)
    if active != PINS:
        raise ValueError('routed heartbeat pin report must contain exactly the nine fixed clock/LED pins')
    helpers = (Path(__file__), CODE_ROOT/'tools/program_native_raw.py', CODE_ROOT/'tools/native_camera_capture.py',
               CODE_ROOT/'tools/camera_eye_pin_audit.py', CODE_ROOT/'tools/frame_protocol.py')
    return {'target': TARGET, 'bitstream_path': str(bit), 'bitstream_sha256': GOLDEN_BIT_SHA256,
        'manifest_path': str(manifest_path), 'device': 'PG2L100H', 'package': 'FBG676', 'scbv': 'High Voltage',
        'timing_report': str(timing), 'timing_sha256': hw.sha(timing), 'verified_pins': dict(PINS),
        'source_sha256': dict(SOURCE_SHA256), 'artifact_sha256': dict(ARTIFACT_SHA256),
        'helper_source_sha256': {str(path.relative_to(CODE_ROOT)): hw.sha(path) for path in helpers},
        'source_binding_method': 'Fixed handoff-source and artifact hashes supplement the historical manifest, which lacks SourceSHA256/TimingSHA256.'}


def _scripts(validation, frequency):
    # Reuse only command generation, not the raw target's authorization path.
    return hw._scripts(validation, frequency)


def prepare_plan(workdir, *, pds_bin=None, frequency='1MHz', timeout_seconds=None):
    if timeout_seconds is None:
        raise ValueError('caller must explicitly bind recovery timeout; legacy callers cannot prepare hardware plans')
    base, approved = Path(workdir).resolve(), APPROVED.resolve()
    if not base.is_dir() or not approved.is_dir() or not base.is_relative_to(approved):
        raise ValueError('workdir must already exist inside the approved offline-20261024 tree')
    validation = validate_heartbeat()
    budget = program_budget(validation,frequency,timeout_seconds)
    pds = hw.resolve_pds_bin(pds_bin)
    scripts = _scripts(validation, frequency)
    run = base/('program-idle-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'-'+uuid.uuid4().hex[:8])
    if not run.resolve().is_relative_to(approved):
        raise ValueError('idle plan directory escapes approved scratch')
    run.mkdir(exist_ok=False)
    for stage, text in scripts.items():
        with (run/(stage+'.tcl')).open('x', encoding='utf-8') as stream:
            stream.write(text)
    result = {'schema': 1, 'target': TARGET, 'operation': 'volatile_sram_only',
        'executed': False, 'hardware_accessed': False, 'done_confirmed': False,
        'requires_explicit_execute_flag': True, 'workdir': str(run), 'pds_bin': str(pds),
        'frequency': frequency, 'validation': validation, 'program_budget':budget,
        'tcl': {stage: {'path': str(run/(stage+'.tcl')), 'sha256': hw.sha(run/(stage+'.tcl'))} for stage in scripts},
        'limits': 'Plan only. Only the fixed heartbeat SRAM baseline is eligible. No raw/alternative target, Flash, legacy status write or unrelated-process termination is implemented.'}
    hw._new_json(run/'plan.json', result)
    return result


def execute_plan(plan, *, timeout_seconds=None):
    """Explicit hardware boundary; no serial connection is ever opened."""
    budget = validate_program_budget(plan)
    sealed_timeout = budget['client_timeout_seconds']
    if timeout_seconds is not None and (type(timeout_seconds) not in (int,float)
            or not math.isfinite(timeout_seconds) or timeout_seconds != sealed_timeout):
        raise ValueError('explicit timeout_seconds differs from sealed programming budget')
    timeout_seconds = sealed_timeout
    work = Path(plan['workdir']).resolve()
    if not work.is_dir() or not work.is_relative_to(APPROVED.resolve()) or (work/'receipt.json').exists():
        raise ValueError('execution needs a fresh plan inside approved scratch')
    if hw.load_json(work/'plan.json') != plan:
        raise ValueError('heartbeat disk plan differs from sealed execution plan')
    result = {'schema': 1, 'target': TARGET, 'operation': 'volatile_sram_only', 'executed': True,
        'hardware_accessed': False, 'programming_attempted': False, 'server_restarted_after_scan': False,
        'done_confirmed': False, 'passed': False, 'workdir': str(work), 'program_budget':budget,
        'limits': 'Successful cfg_program plus fresh post-program DONE confirms this heartbeat SRAM event only; later state and temperature are not continuously observed. No legacy status/history is changed.'}
    owned = []
    try:
        if plan.get('target') != TARGET or plan.get('operation') != 'volatile_sram_only':
            raise ValueError('only the fixed heartbeat SRAM plan can execute')
        current = validate_heartbeat()
        if current != plan['validation']:
            raise ValueError('heartbeat/helper files changed after planning')
        for stage, text in _scripts(current, plan['frequency']).items():
            path = Path(plan['tcl'][stage]['path']).resolve()
            if path != work/(stage+'.tcl') or path.read_text(encoding='utf-8') != text or hw.sha(path) != plan['tcl'][stage]['sha256']:
                raise ValueError('Tcl differs from the fixed heartbeat SRAM command plan')
        pds = hw.resolve_pds_bin(plan['pds_bin'])
        if hw.listening_pids(hw.PORT):
            raise RuntimeError('JTAG server port is occupied; no process was started or stopped')
        server = hw._start_owned([str(pds/'cdt_js.exe'), '-port', str(hw.PORT), '-work_dir', str(work)], work, owned, 'server')
        result['hardware_accessed'] = True
        hw._await_owned_server(server)
        hw._owned_server_check(server)
        hw._check_scan(hw._client(plan, 'scan', owned, timeout_seconds))
        if validate_heartbeat() != plan['validation']:
            raise ValueError('heartbeat bound files changed before program')
        scanned_server = server
        server = hw._program_server_after_scan(server, plan, owned)
        result['server_restarted_after_scan'] = server is not scanned_server
        result['programming_attempted'] = True
        hw._check_program(hw._client(plan, 'program', owned, timeout_seconds))
        if validate_heartbeat() != plan['validation']:
            raise ValueError('heartbeat bound files changed during program')
        result['done_confirmed'] = True
        result['passed'] = True
        result['bitstream_sha256'] = GOLDEN_BIT_SHA256
    except Exception as error:
        result['error'] = str(error)
    finally:
        result['owned_pids'] = [p.pid for p in owned]
        result['terminated_owned_pids'], result['cleanup_errors'] = hw._stop_owned(owned)
        if result['cleanup_errors']:
            result['passed'] = False
        result['logs'] = {str(path): hw.sha(path) for path in work.glob('*.log') if path.is_file()}
        result['checked_at_utc'] = datetime.now(timezone.utc).isoformat()
        hw._new_json(work/'receipt.json', result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workdir', type=Path, required=True, help='existing approved offline scratch directory')
    parser.add_argument('--pds-bin', type=Path)
    parser.add_argument('--frequency', choices=hw.FREQUENCIES, default='1MHz')
    parser.add_argument('--timeout-seconds', type=float, default=DEFAULT_CLIENT_TIMEOUT)
    parser.add_argument('--execute', action='store_true', help='explicitly configure only fixed heartbeat volatile SRAM')
    args = parser.parse_args(argv)
    try:
        if not math.isfinite(args.timeout_seconds) or not 0 < args.timeout_seconds <= 120:
            raise ValueError('timeout must be finite in (0,120]')
        plan = prepare_plan(args.workdir, pds_bin=args.pds_bin, frequency=args.frequency,
                            timeout_seconds=args.timeout_seconds)
        result = execute_plan(plan, timeout_seconds=args.timeout_seconds) if args.execute else plan
        print(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False))
        return 0 if not args.execute or result['passed'] else 1
    except (ValueError, OSError) as error:
        parser.error(str(error))


if __name__ == '__main__':
    raise SystemExit(main())
