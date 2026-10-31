"""Plan, or explicitly execute, one source-bound CAM2 raw SRAM download.

Default behavior validates files/review declarations and writes a new Tcl plan
under the already approved offline scratch root. Only --execute starts PDS.
No Flash operation, unrelated server termination, automatic alternative target,
legacy status update or modification of an input binding occurs.
"""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import copy
import ctypes
import json
import math
import os
import re
import struct
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from native_camera_capture import load_json, sha, validate_live_binding

TARGET = 'raw_camera_capture_cam2_ref'
DEVICE = 'PG2L100H'
DEVICE_ID = '0x00602899'
PORT = 65420
APPROVED = ROOT/'build/offline-20261024'
FREQUENCIES = ('10MHz', '5MHz', '1MHz', '500KHz', '100KHz')


def _new_json(path, value):
    with Path(path).open('x', encoding='utf-8') as stream:
        stream.write(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False)+'\n')


def _path_from(record, base):
    path = Path(record['path'])
    return (path if path.is_absolute() else Path(base)/path).resolve()


def validate_program_binding(binding_path):
    """Pre-program phase deliberately does not require prior programming."""
    path = Path(binding_path).resolve()
    before = sha(path)
    binding = load_json(path)
    record = validate_live_binding(binding, base_dir=path.parent, require_programmed=False)
    if binding['eye'] != 'CAM2' or binding['image_size'] != [640, 480]:
        raise ValueError('only the CAM2 640x480 raw reference candidate is supported')
    manifest_path = _path_from(binding['build_binding']['validated_build'], path.parent)
    bitstream = _path_from(binding['build_binding']['bitstream'], path.parent)
    manifest = load_json(manifest_path)
    if manifest.get('Target') != TARGET or manifest.get('Device') != DEVICE or manifest.get('SCBV') != 'High Voltage':
        raise ValueError('validated manifest must identify the exact PG2L100H high-voltage raw CAM2 target')
    if bitstream.name != TARGET+'.sbit':
        raise ValueError('only the named raw CAM2 SRAM bitstream is supported')
    prepared_path = ROOT/f'board/{TARGET}-sources.json'
    prepared = load_json(prepared_path)
    if prepared.get('target') != TARGET or prepared.get('RawCaptureContract') != manifest.get('RawCaptureContract'):
        raise ValueError('raw capture contract differs from the prepared reference candidate')
    expected_sources = prepared.get('SourceSHA256')
    actual_sources = manifest['SourceSHA256']
    if not isinstance(expected_sources, dict) or not expected_sources or set(expected_sources) != set(actual_sources):
        raise ValueError('validated source closure differs from the prepared raw candidate')
    if any(str(actual_sources[name]).lower() != str(digest).lower() for name, digest in expected_sources.items()):
        raise ValueError('validated source hashes differ from the prepared raw candidate')
    if sha(path) != before:
        raise ValueError('binding changed during validation')
    return {'binding_path': str(path), 'binding_file_sha256': before, 'binding': binding,
            'validated_build': record, 'bitstream_path': str(bitstream),
            'prepared_source_manifest': str(prepared_path), 'prepared_source_manifest_sha256': sha(prepared_path),
            'source_sha256': {str(source.relative_to(ROOT)): sha(source) for source in
                (Path(__file__), ROOT/'tools/native_camera_capture.py', ROOT/'tools/camera_eye_pin_audit.py', ROOT/'tools/frame_protocol.py')}}


def resolve_pds_bin(value=None):
    if value is None:
        config_path = ROOT.parent/'team-config.local.json'
        config = load_json(config_path) if config_path.is_file() else {}
        value = os.environ.get('FPGA_PDS_BIN') or config.get('pds_bin') or r'E:\Pango\PDS_2022.2-SP6.4\bin'
    path = Path(value)
    path = (path if path.is_absolute() else ROOT.parent/path).resolve()
    if not path.is_dir() or any(not (path/name).is_file() for name in ('cdt_js.exe', 'cdt_cfg_shell.exe')):
        raise ValueError('PDS bin must already contain cdt_js.exe and cdt_cfg_shell.exe; no installation is attempted')
    return path


def _tcl_path(path):
    value = str(Path(path).resolve()).replace('\\', '/')
    if any(char in value for char in '{}\r\n'):
        raise ValueError('path cannot be represented safely as a literal Tcl filename')
    return '{'+value+'}'


def _scripts(validation, frequency):
    if frequency not in FREQUENCIES:
        raise ValueError('unsupported JTAG frequency')
    common = ('cfg_set_tcl_break -flag true\n'
              f'cfg_connect -ip 127.0.0.1 -port {PORT}\n'
              f'cfg_set_cable_property -index 0 -freq {frequency}\n'
              'cfg_scan_chain\n')
    end = 'cfg_disconnect\ncfg_close\n'
    return {
        'scan': common+'cfg_read_device_property -mode 0 -device_index 0\n'+end,
        'program': common+f'cfg_assign_file -file {_tcl_path(validation["bitstream_path"])} -device_index 0\n'
                   'cfg_program -device_index 0\ncfg_scan_chain\n'
                   'cfg_read_device_property -mode 3 -device_index 0\n'+end,
    }


def prepare_plan(binding_path, workdir, *, pds_bin=None, frequency='1MHz'):
    if frequency not in FREQUENCIES:
        raise ValueError('unsupported JTAG frequency')
    base, approved = Path(workdir).resolve(), APPROVED.resolve()
    if not approved.is_dir() or not base.is_dir() or not base.is_relative_to(approved):
        raise ValueError('workdir must already exist inside the approved build/offline-20261024 tree')
    validation = validate_program_binding(binding_path)
    pds = resolve_pds_bin(pds_bin)
    name = 'program-native-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'-'+uuid.uuid4().hex[:8]
    run_dir = base/name
    if not run_dir.resolve().is_relative_to(approved):
        raise ValueError('resolved run directory escapes the approved scratch root')
    run_dir.mkdir(exist_ok=False)
    scripts = _scripts(validation, frequency)
    for stage, text in scripts.items():
        with (run_dir/(stage+'.tcl')).open('x', encoding='utf-8') as stream:
            stream.write(text)
    plan = {'schema': 1, 'target': TARGET, 'operation': 'volatile_sram_only',
        'default_mode': 'validation_and_tcl_plan_only', 'executed': False,
        'hardware_accessed': False, 'done_confirmed': False,
        'requires_explicit_execute_flag': True, 'new_module_verified_by_tool': False,
        'workdir': str(run_dir), 'pds_bin': str(pds), 'frequency': frequency,
        'expected_device': DEVICE, 'expected_device_id': DEVICE_ID, 'server_port': PORT,
        'tcl': {stage: {'path': str(run_dir/(stage+'.tcl')), 'sha256': sha(run_dir/(stage+'.tcl'))} for stage in scripts},
        'validation': validation,
        'limits': 'Physical wiring/voltage/eye reviews are operator declarations. Default planning never starts PDS or accesses UART/JTAG. Only the named raw CAM2 candidate may be configured into volatile SRAM; Flash and alternative/idle target downloads are absent. Input binding and old status/evidence stay unchanged.'}
    _new_json(run_dir/'plan.json', plan)
    return plan


def _table_listener_pids(data, family, port):
    """Parse Windows OWNER_PID listener tables without querying other processes."""
    if len(data) < 4 or family not in (4, 6):
        raise ValueError('invalid TCP owner table')
    count = struct.unpack_from('<I', data)[0]
    stride, port_offset, pid_offset = (24, 8, 20) if family == 4 else (56, 20, 52)
    if len(data) < 4+count*stride:
        raise ValueError('truncated TCP owner table')
    pids = set()
    for index in range(count):
        start = 4+index*stride
        if int.from_bytes(data[start+port_offset:start+port_offset+2], 'big') == port:
            pids.add(struct.unpack_from('<I', data, start+pid_offset)[0])
    return pids


def listening_pids(port):
    """Read local IPv4/IPv6 listeners through Windows IP Helper, not CIM."""
    if os.name != 'nt':
        raise RuntimeError('real execution requires Windows TCP ownership checks')
    api = ctypes.WinDLL('iphlpapi', use_last_error=True).GetExtendedTcpTable
    api.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32), ctypes.c_int,
                    ctypes.c_uint32, ctypes.c_uint32, ctypes.c_uint32]
    api.restype = ctypes.c_uint32
    owners = set()
    for address_family, kind in ((2, 4), (23, 6)):
        size = ctypes.c_uint32()
        code = api(None, ctypes.byref(size), True, address_family, 3, 0)
        if code not in (0, 122) or not 4 <= size.value <= 1 << 20:
            raise RuntimeError('cannot establish TCP listener ownership before JTAG access')
        buffer = ctypes.create_string_buffer(size.value)
        code = api(buffer, ctypes.byref(size), True, address_family, 3, 0)
        if code:
            raise RuntimeError('TCP listener table changed or is unavailable; refusing JTAG access')
        owners.update(_table_listener_pids(buffer.raw, kind, port))
    return owners


def _owned_server_check(server):
    if server.poll() is not None:
        raise RuntimeError('owned JTAG server exited; refusing to use another server')
    if listening_pids(PORT) != {server.pid}:
        raise RuntimeError('JTAG listener is not exclusively owned by this invocation')


def _await_owned_server(server, seconds=10.):
    deadline = time.monotonic()+seconds
    while True:
        if server.poll() is not None:
            raise RuntimeError('owned JTAG server exited during startup')
        owners = listening_pids(PORT)
        if owners == {server.pid}:
            return
        if owners:
            raise RuntimeError('JTAG server port became occupied by another process')
        if time.monotonic() >= deadline:
            raise RuntimeError('owned JTAG server did not acquire its listener')
        time.sleep(.1)


def _start_owned(command, work, owned, stage):
    out, err = [work/(stage+suffix) for suffix in ('.out.log', '.err.log')]
    with out.open('xb') as stdout, err.open('xb') as stderr:
        process = subprocess.Popen(command, cwd=work, stdin=subprocess.DEVNULL,
            stdout=stdout, stderr=stderr, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    owned.append(process)
    return process


def _program_server_after_scan(server, plan, owned):
    """Use a surviving owned server or start one fresh programming server.

    Some PDS versions exit cdt_js after the scan client's cfg_close. An exit
    is not device-scan failure. Never attach to a replacement listener owned
    by somebody else, and never repeat an already attempted cfg_program.
    """
    if server.poll() is None:
        _owned_server_check(server)
        return server
    if listening_pids(PORT):
        raise RuntimeError('JTAG server port is occupied after scan server exited; refusing another owner')
    work, pds = Path(plan['workdir']), Path(plan['pds_bin'])
    replacement = _start_owned([str(pds/'cdt_js.exe'), '-port', str(PORT), '-work_dir', str(work)],
                               work, owned, 'server-program')
    _await_owned_server(replacement)
    _owned_server_check(replacement)
    return replacement


def _client(plan, stage, owned, timeout_seconds):
    work, pds = Path(plan['workdir']), Path(plan['pds_bin'])
    script = plan['tcl'][stage]
    if sha(script['path']) != script['sha256']:
        raise ValueError('prepared Tcl changed: '+stage)
    client = _start_owned([str(pds/'cdt_cfg_shell.exe'), '-file', script['path'], '-work_dir', str(work)], work, owned, stage)
    code = client.wait(timeout=timeout_seconds)
    text = (work/(stage+'.out.log')).read_text(encoding='utf-8', errors='replace')
    error = (work/(stage+'.err.log')).read_bytes()
    if code != 0 or error or re.search(r'(?im)\b(error|failed|fatal)\b', text):
        raise RuntimeError('JTAG '+stage+' failed; retained stdout/stderr are authoritative')
    return text


def _check_scan(text):
    devices = re.findall(r'(?m)^\s*(PG\w+)\s*$', text)
    ids = re.findall(r'(?im)^\s*The ID value is:\s*(0x[0-9a-f]{8})\s*$', text)
    if devices != [DEVICE] or [value.lower() for value in ids] != [DEVICE_ID]:
        raise RuntimeError('unexpected JTAG device or ID; no cfg_program is permitted')


def _check_program(text):
    success = re.search(r'(?m)^Executing : cfg_program\b[^\r\n]* successfully\.\s*$', text)
    devices = re.findall(r'(?m)^\s*(PG\w+)\s*$', text)
    if not success or not devices or any(device != DEVICE for device in devices):
        raise RuntimeError('cfg_program success and matching device DONE were not both confirmed')
    # The Tcl performs a pre-program scan and a separate post-program scan.
    # A pre-existing DONE=1 must never hide a later failed configuration.
    scans = re.findall(r'(?ms)^Executing : cfg_scan_chain\s*$(.*?)^Executing : cfg_scan_chain successfully\.\s*$', text[success.end():])
    if not scans:
        raise RuntimeError('a completed post-program scan is required for DONE confirmation')
    for scan in scans:
        post_devices = re.findall(r'(?m)^\s*(PG\w+)\s*$', scan)
        done = re.findall(r'(?m)^\s*This device configure situation \(done bit\):\s*([01])\s*$', scan)
        if post_devices != [DEVICE] or done != ['1']:
            raise RuntimeError('post-program device/DONE confirmation failed')
    if len(scans) != 1:
        raise RuntimeError('cfg_program success and matching device DONE were not both confirmed')


def _stop_owned(owned):
    terminated, errors = [], []
    for process in reversed(owned):
        try:
            if process.poll() is None:
                process.terminate()
                terminated.append(process.pid)
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
        except Exception as error:
            errors.append({'owned_pid': process.pid, 'error': str(error)})
    return terminated, errors


def execute_plan(plan, *, timeout_seconds=90.):
    """Hardware boundary: callers must enter only after explicit --execute."""
    if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, (int, float)) or not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
        raise ValueError('timeout_seconds must be finite and positive')
    work = Path(plan['workdir']).resolve()
    if not work.is_dir() or not work.is_relative_to(APPROVED.resolve()):
        raise ValueError('execution workdir must be inside approved scratch')
    if (work/'receipt.json').exists():
        raise ValueError('this plan already has an execution receipt; use a new invocation')
    result = {'schema': 1, 'target': TARGET, 'operation': 'volatile_sram_only',
        'executed': True, 'hardware_accessed': False, 'done_confirmed': False, 'passed': False,
        'programming_attempted': False,
        'server_restarted_after_scan': False,
        'workdir': str(work), 'original_binding_file_sha256': plan['validation']['binding_file_sha256'],
        'owned_pids': [], 'limits': 'DONE confirms this SRAM configuration event only. It does not prove later configuration persistence, native camera data, wiring, optical quality, synchronization or Flash boot. No legacy status file is updated.'}
    owned = []
    try:
        if plan.get('target') != TARGET or plan.get('operation') != 'volatile_sram_only':
            raise ValueError('only the named raw CAM2 SRAM plan may execute')
        current = validate_program_binding(plan['validation']['binding_path'])
        if current != plan['validation']:
            raise ValueError('binding/build/helper sources changed after planning')
        for stage, text in _scripts(current, plan['frequency']).items():
            path = Path(plan['tcl'][stage]['path']).resolve()
            if path != work/(stage+'.tcl') or path.read_text(encoding='utf-8') != text:
                raise ValueError('Tcl differs from the fixed SRAM-only command plan')
        resolve_pds_bin(plan['pds_bin'])
        if listening_pids(PORT):
            raise RuntimeError('JTAG server port is occupied; no process was started or stopped')
        pds = Path(plan['pds_bin'])
        server = _start_owned([str(pds/'cdt_js.exe'), '-port', str(PORT), '-work_dir', str(work)], work, owned, 'server')
        result['hardware_accessed'] = True
        _await_owned_server(server)
        _owned_server_check(server)
        _check_scan(_client(plan, 'scan', owned, timeout_seconds))
        # Recheck every source and bound file after scanning and before program.
        if validate_program_binding(plan['validation']['binding_path']) != plan['validation']:
            raise ValueError('bound files changed before programming')
        scanned_server = server
        server = _program_server_after_scan(server, plan, owned)
        result['server_restarted_after_scan'] = server is not scanned_server
        result['programming_attempted'] = True
        _check_program(_client(plan, 'program', owned, timeout_seconds))
        if validate_program_binding(plan['validation']['binding_path']) != plan['validation']:
            raise ValueError('bound files changed during programming')
        result['done_confirmed'] = True
        result['passed'] = True
    except Exception as error:
        result['error'] = str(error)
    finally:
        result['owned_pids'] = [process.pid for process in owned]
        stopped, errors = _stop_owned(owned)
        result['terminated_owned_pids'] = stopped
        result['cleanup_errors'] = errors
        if errors:
            result['passed'] = False
        result['logs'] = {str(path): sha(path) for path in work.glob('*.log') if path.is_file()}
        result['checked_at_utc'] = datetime.now(timezone.utc).isoformat()
        _new_json(work/'receipt.json', result)
    if result['passed']:
        binding = copy.deepcopy(plan['validation']['binding'])
        binding['connection_review']['programmed_bound_bitstream'] = True
        binding['programming_receipt'] = {'path': str(work/'receipt.json'), 'sha256': sha(work/'receipt.json'),
            'scope': 'this invocation cfg_program success and DONE only; later FPGA state is not continuously observed'}
        _new_json(work/'session-binding.json', binding)
        result['session_binding_path'] = str(work/'session-binding.json')
        result['session_binding_sha256'] = sha(work/'session-binding.json')
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binding', type=Path, required=True)
    parser.add_argument('--workdir', type=Path, required=True, help='existing directory under approved build/offline-20261024')
    parser.add_argument('--pds-bin', type=Path, help='existing PDS bin directory; otherwise configured local path')
    parser.add_argument('--frequency', choices=FREQUENCIES, default='1MHz')
    parser.add_argument('--timeout-seconds', type=float, default=90.)
    parser.add_argument('--execute', action='store_true', help='explicitly access JTAG and configure only the named raw SRAM target')
    args = parser.parse_args(argv)
    try:
        if not math.isfinite(args.timeout_seconds) or args.timeout_seconds <= 0:
            raise ValueError('timeout must be finite and positive')
        plan = prepare_plan(args.binding, args.workdir, pds_bin=args.pds_bin, frequency=args.frequency)
        result = execute_plan(plan, timeout_seconds=args.timeout_seconds) if args.execute else plan
        print(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False))
        return 0 if not args.execute or result['passed'] else 1
    except (ValueError, OSError) as error:
        parser.error(str(error))


if __name__ == '__main__':
    raise SystemExit(main())
