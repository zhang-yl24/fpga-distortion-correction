"""Scan and read the known FPGA ID using an owned local JTAG server.

This script contains no file assignment, programming, Flash or camera-register
commands. Successful FPGA identification does not identify the attached sensor.
"""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
import program_native_raw as program


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workdir', type=Path, required=True)
    parser.add_argument('--frequency', choices=program.FREQUENCIES, default='1MHz')
    args = parser.parse_args()
    approved = program.APPROVED.resolve()
    base = args.workdir.resolve()
    if not base.is_dir() or not base.is_relative_to(approved):
        parser.error('workdir must already exist within the approved offline scratch tree')
    work = base/('live-scan-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
    work.mkdir()
    source = (ROOT.parent/'hardware_check/scan-only.tcl').read_text(encoding='utf-8')
    if '-freq 1MHz' not in source:
        raise ValueError('scan Tcl must have one explicit reference frequency')
    source = source.replace('-freq 1MHz', '-freq '+args.frequency)
    if any(word in source for word in ('cfg_program', 'cfg_assign_file', 'cfg_flash', 'cfg_erase')):
        raise ValueError('scan Tcl includes a mutation command')
    script = work/'scan.tcl'
    script.write_text(source, encoding='utf-8')
    plan = {'workdir': str(work), 'pds_bin': str(program.resolve_pds_bin()),
            'tcl': {'scan': {'path': str(script), 'sha256': program.sha(script)}}}
    owned = []
    result = {'schema': 1, 'operation': 'jtag_scan_and_id_read_only',
              'configuration_written': False, 'camera_registers_written': False,
              'passed': False, 'workdir': str(work), 'hardware_accessed': False,
              'frequency': args.frequency}
    try:
        if program.listening_pids(program.PORT):
            raise RuntimeError('JTAG server is occupied; no process started')
        server = program._start_owned([str(Path(plan['pds_bin'])/'cdt_js.exe'), '-port',
            str(program.PORT), '-work_dir', str(work)], work, owned, 'server')
        result['hardware_accessed'] = True
        program._await_owned_server(server)
        program._owned_server_check(server)
        text = program._client(plan, 'scan', owned, 60)
        program._check_scan(text)
        result.update(passed=True, device=program.DEVICE, idcode=program.DEVICE_ID,
                      scan_log_sha256=program.sha(work/'scan.out.log'))
    except Exception as error:
        result['error'] = str(error)
    finally:
        result['owned_pids'] = [process.pid for process in owned]
        stopped, errors = program._stop_owned(owned)
        result['terminated_owned_pids'], result['cleanup_errors'] = stopped, errors
        result['source_sha256'] = {str(path.relative_to(ROOT)): program.sha(path) for path in
                                  (Path(__file__), ROOT/'tools/program_native_raw.py')}
        result['checked_at_utc'] = datetime.now(timezone.utc).isoformat()
        (work/'scan-result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result['passed'] and not result['cleanup_errors'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
