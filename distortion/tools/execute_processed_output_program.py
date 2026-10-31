"""Validate a processed-output SRAM plan; explicitly execute after board power.

Default operation is offline validation. Hardware execution needs both
--execute and --board-powered, supplied only after the user confirms power.
The owned JTAG server scans one PG2L100H, programs SRAM once at 1MHz and
checks post-program DONE. No Flash or UART operation is present.
"""
from datetime import datetime, timezone
from pathlib import Path
import argparse
import json
import math
import re

import prepare_processed_output_program as program

bit, hw = program.bit, program.native
require = bit.require


def validate(plan_path):
    path = Path(plan_path).absolute()
    work = path.parent
    require(path == path.resolve() and path.name == 'plan.json' and work.parent == bit.BUILD
            and re.fullmatch(r'program-[A-Za-z0-9_-]+', work.name),
            'canonical processed-output program-* plan required')
    before = bit.sha(path)
    plan = bit.load(path)
    expected = dict(Schema='processed-output-sram-plan-v1', Target=bit.TARGET,
                    Operation='volatile_sram_only', ExpectedDevice=hw.DEVICE,
                    ExpectedDeviceID=hw.DEVICE_ID, CableIndex=0, Frequency='1MHz',
                    ServerPort=hw.PORT, PreparedOnly=True, ExecutionSupported=True,
                    RequiresExplicitExecuteAndBoardPowered=True,
                    UserMustBeNotifiedBeforeBoardSession=True,
                    DDRProcessingIncluded=True, PhysicalInputCaptureIncluded=False,
                    HardwareReleaseAllowed=False)
    for name, wanted in expected.items():
        require(type(plan.get(name)) is type(wanted) and plan[name] == wanted,
                'processed-output plan identity differs: ' + name)
    require(plan['WorkDirectory'] == str(work), 'plan work directory differs')
    for name in ('HardwareAccessed', 'Executed', 'ProgrammingAttempted', 'DoneConfirmed', 'FlashWritten'):
        require(plan.get(name) is False, 'prepared plan must remain unexecuted: ' + name)
    bit_work = bit.work_path(plan['BitstreamWorkDirectory'])
    verified = bit.verify(bit_work)
    require(verified.get('Verified') is True and verified.get('FinalADFSHA256') == bit.ADF_SHA,
            'processed-output bitstream verification failed')
    require(verified['Bitstream'] == plan['Bitstream'], 'verified bitstream differs from plan')
    require(plan['FinalADFSHA256'] == bit.ADF_SHA, 'plan ADF differs')
    pds = hw.resolve_pds_bin(bit.export.PDS.parent)
    require(plan['PDSBin'] == str(pds), 'fixed PDS bin differs')
    bindings = program.bound_inputs(bit_work, verified, pds)
    require(bindings == plan['BoundInputSHA256'], 'plan source or evidence binding differs')
    require(all(bit.sha(name) == wanted for name, wanted in bindings.items()), 'bound input changed')
    require(set(plan['Tcl']) == {'scan', 'program'}, 'exact scan and program scripts required')
    source_bit = Path(verified['Bitstream']['Path'])
    for stage, text in hw._scripts({'bitstream_path': str(source_bit)}, '1MHz').items():
        entry = plan['Tcl'][stage]
        script = Path(entry['Path'])
        require(script == work/(stage+'.tcl') and script.resolve() == script
                and bit.sha(script) == entry['SHA256'] and script.read_text(encoding='utf-8') == text,
                'fixed SRAM-only Tcl changed: ' + stage)
    require(bit.sha(path) == before, 'plan changed during validation')
    return plan


def execute(plan_path, *, board_powered=False, timeout_seconds=90.0):
    require(board_powered is True, 'user-confirmed board power is required before hardware access')
    require(type(timeout_seconds) in (int, float) and math.isfinite(timeout_seconds)
            and 0 < timeout_seconds <= 300, 'timeout must be finite and in (0, 300]')
    path = Path(plan_path).absolute()
    plan = validate(path)
    work = path.parent
    require(not (work/'receipt.json').exists() and not list(work.glob('*.log')),
            'plan has prior execution outputs; prepare a fresh plan')
    plan_sha, executor_sha = bit.sha(path), bit.sha(__file__)
    adapter = dict(workdir=str(work), pds_bin=plan['PDSBin'], frequency=plan['Frequency'],
                   tcl={stage: dict(path=entry['Path'], sha256=entry['SHA256'])
                        for stage, entry in plan['Tcl'].items()})
    result = dict(Schema='processed-output-sram-execution-v1', Target=bit.TARGET,
                  StartedUTC=datetime.now(timezone.utc).isoformat(), PlanSHA256=plan_sha,
                  ExecutorSHA256=executor_sha, WorkDirectory=str(work),
                  Bitstream=plan['Bitstream'], FinalADFSHA256=plan['FinalADFSHA256'],
                  Passed=False, Executed=True, UserConfirmedBoardPowered=True,
                  HardwareAccessed=False, ProgrammingAttempted=False, DoneConfirmed=False,
                  FlashWritten=False, HardwareReleaseAllowed=False, ServerRestartedAfterScan=False,
                  Limits='SRAM configuration event and post-program DONE only. Display, DDR processing, '
                         'physical CDC/AC and sustained frame progress require separate observation.')
    owned = []

    def recheck():
        require(bit.sha(path) == plan_sha and bit.sha(__file__) == executor_sha,
                'plan or executor changed during execution')
        require(validate(path) == plan, 'bound plan changed during execution')

    try:
        require(not hw.listening_pids(hw.PORT), 'JTAG server port is occupied; no process started or stopped')
        pds = Path(plan['PDSBin'])
        server = hw._start_owned([str(pds/'cdt_js.exe'), '-port', str(hw.PORT),
                                  '-work_dir', str(work)], work, owned, 'server')
        result['HardwareAccessed'] = True
        hw._await_owned_server(server)
        hw._owned_server_check(server)
        hw._check_scan(hw._client(adapter, 'scan', owned, timeout_seconds))
        recheck()
        scanned = server
        server = hw._program_server_after_scan(server, adapter, owned)
        result['ServerRestartedAfterScan'] = server is not scanned
        hw._owned_server_check(server)
        recheck()
        # Revalidate server ownership after the potentially long offline checks.
        hw._owned_server_check(server)
        result['ProgrammingAttempted'] = True
        hw._check_program(hw._client(adapter, 'program', owned, timeout_seconds))
        result['DoneConfirmed'] = True
        recheck()
        result['Passed'] = True
    except Exception as error:
        result['Error'] = type(error).__name__ + ': ' + str(error)
    finally:
        result['OwnedPIDs'] = [process.pid for process in owned]
        stopped, errors = hw._stop_owned(owned)
        result['TerminatedOwnedPIDs'], result['CleanupErrors'] = stopped, errors
        if errors:
            result['Passed'] = False
        result['Logs'] = {source.name: bit.sha(source) for source in sorted(work.glob('*.log')) if source.is_file()}
        result['EndedUTC'] = datetime.now(timezone.utc).isoformat()
        hw._new_json(work/'receipt.json', result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--timeout-seconds', type=float, default=90.0)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--board-powered', action='store_true',
                        help='operator confirms user has powered the board for this session')
    args = parser.parse_args(argv)
    try:
        if args.execute:
            result = execute(args.plan, board_powered=args.board_powered,
                             timeout_seconds=args.timeout_seconds)
            print(json.dumps(result, indent=2, allow_nan=False))
            return 0 if result['Passed'] else 1
        plan = validate(args.plan)
        print(json.dumps(dict(ValidationPassed=True, Target=plan['Target'], HardwareAccessed=False,
                              BitstreamSHA256=plan['Bitstream']['SHA256'])))
        return 0
    except (ValueError, OSError, KeyError) as error:
        parser.error(str(error))


if __name__ == '__main__':
    raise SystemExit(main())
