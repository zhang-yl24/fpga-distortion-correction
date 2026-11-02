"""Prepare/validate or explicitly execute one HDMI camera direct diagnostic SRAM event.

Every file is verified before/after scan and programming. Only owned JTAG
processes are managed; no Flash, UART traffic, bitstream generation or fallback
image is provided. DONE is not bitwise configuration readback or pixel proof.
"""
import argparse
import json
import math
from pathlib import Path

import hdmi_camera_direct_bitstream as bit
import program_native_raw as hw

SELF = Path(__file__).resolve()
TARGET = bit.TARGET
SCHEMA = 'hdmi-camera-direct-sram-plan-v1'
EXEC_SCHEMA = 'hdmi-camera-direct-sram-execution-v1'
require, sha, read, write = bit.require, bit.sha, bit.read, bit.write


def scripts(bitfile):
    values = hw._scripts({'bitstream_path': str(bitfile)}, '1MHz')
    require(set(values) == {'scan', 'program'} and all('flash' not in t.lower() for t in values.values()),
            'only exact volatile SRAM scripts allowed')
    return values


def recipe(bit_work, work):
    bit_work, work = bit.build.work_path(bit_work), bit.build.work_path(work)
    require(work.name.startswith('program-'), 'program-* direct child required')
    checked = bit.verify(bit_work)
    plan = read(bit_work / 'bitstream-plan.json')
    require(checked['Verified'] is True and checked['Target'] == TARGET
            and Path(checked['Bitstream']['Path']) == bit_work / bit.BIT
            and checked['FinalADFSHA256'] == plan['FinalADFSHA256'], 'current verified direct diagnostic bit required')
    build_plan = bit.build.validate(plan['BuildPlan']['Path'])
    pds = hw.resolve_pds_bin(Path(build_plan['Command'][0]).parent)
    watched = dict(plan['InputSHA256'])
    for name, digest in checked['EvidenceSHA256'].items():
        p = bit_work / name
        require(p.resolve().is_relative_to(bit_work), 'bit artifact escapes verified work')
        bit.add(watched, p, digest)
    for p in (SELF, Path(bit.__file__), Path(hw.__file__), pds / 'cdt_js.exe', pds / 'cdt_cfg_shell.exe',
              bit.ROOT / 'tools/native_camera_capture.py', bit.ROOT / 'tools/frame_protocol.py',
              bit.ROOT / 'tools/camera_eye_pin_audit.py'):
        bit.add(watched, p)
    tcl = scripts(checked['Bitstream']['Path'])
    value = {'Schema': SCHEMA, 'Target': TARGET, 'WorkDirectory': str(work), 'BitstreamWorkDirectory': str(bit_work),
             'Bitstream': checked['Bitstream'], 'FinalADFSHA256': checked['FinalADFSHA256'],
             'Operation': 'volatile_sram_only', 'ExpectedDevice': hw.DEVICE, 'ExpectedDeviceID': hw.DEVICE_ID,
             'CableIndex': 0, 'Frequency': '1MHz', 'ServerPort': hw.PORT, 'PDSBin': str(pds),
             'BoundInputSHA256': watched, 'Tcl': {k: {'Path': str(work / (k + '.tcl')),
                 'SHA256': bit.hashlib.sha256(v.encode('utf-8')).hexdigest()} for k, v in tcl.items()},
             'PreparedOnly': True, 'Executed': False, 'HardwareAccessed': False, 'FlashWritten': False,
             'RequiresExplicitExecute': True, 'RequiresCurrentSessionBoardPower': True,
             'UserMustBeNotifiedBeforeExecution': True, 'SameSessionAuthorizationMayBeReused': True,
             'HardwareReleaseAllowed': False, 'PixelsVerified': False, 'ExternalACAccepted': False,
             'Limits': 'This candidate attempts real camera RGB888 via common27-bit sampling and source-clock forwarding. Volatile SRAM scan/program/DONE only; '
                       'no configuration bitwise readback, observed real pixel acceptance, image export, lens calibration, external AC or analog CDC/MTBF acceptance.'}
    require(not bit.drift(watched), 'SRAM preparation input drift')
    return value, tcl


def prepare(bit_work, work):
    value, tcl = recipe(bit_work, work)
    work = Path(value['WorkDirectory'])
    require(not work.exists(), 'fresh SRAM stage required')
    work.mkdir()
    for name, text in tcl.items():
        (work / (name + '.tcl')).write_text(text, encoding='utf-8', newline='\n')
    write(work / 'plan.json', value)
    return value


def validate(path):
    path = Path(path).absolute()
    require(path == path.resolve() and path.name == 'plan.json', 'canonical exact SRAM plan required')
    value = read(path)
    require(value.get('Schema') == SCHEMA and value.get('Target') == TARGET, 'current direct SRAM identity required')
    expected, tcl = recipe(value['BitstreamWorkDirectory'], path.parent)
    require(value == expected, 'SRAM plan differs from full verified recipe')
    for name, text in tcl.items():
        require((path.parent / (name + '.tcl')).read_bytes() == text.encode('utf-8'), 'SRAM script drift')
    return value


def execution_authorization(board_powered, user_notified, timeout):
    require(board_powered is True and user_notified is True, 'current-session power and user notification required')
    require(type(timeout) in (int, float) and math.isfinite(timeout) and 0 < timeout <= 300,
            'timeout must be finite in(0,300]')


def execute(path, *, board_powered=False, user_notified=False, timeout=90):
    execution_authorization(board_powered, user_notified, timeout)
    value = validate(path)
    path = Path(path).resolve()
    work = path.parent
    require({p.name for p in work.iterdir()} == {'plan.json', 'scan.tcl', 'program.tcl'}, 'fresh never-executed SRAM stage required')
    plan_sha, tool_sha = sha(path), sha(SELF)
    adapter = {'workdir': str(work), 'pds_bin': value['PDSBin'], 'frequency': value['Frequency'],
               'tcl': {k: {'path': v['Path'], 'sha256': v['SHA256']} for k, v in value['Tcl'].items()}}
    result = {'Schema': EXEC_SCHEMA, 'Target': TARGET, 'StartedUTC': bit.utc(), 'PlanSHA256': plan_sha,
              'ExecutorSHA256': tool_sha, 'WorkDirectory': str(work), 'Bitstream': value['Bitstream'],
              'FinalADFSHA256': value['FinalADFSHA256'], 'UserConfirmedBoardPowered': True,
              'UserNotifiedBeforeExecution': True, 'SessionAuthorizationReused': True, 'Passed': False,
              'HardwareAccessed': False, 'ProgrammingAttempted': False, 'DoneConfirmed': False,
              'ExpectedDeviceAndIDConfirmed': False,
              'FlashWritten': False, 'HardwareReleaseAllowed': False, 'BitwiseConfigurationReadbackPerformed': False,
              'PixelsVerified': False, 'ServerRestartedAfterScan': False}
    # Exclusive claim is persisted before the first process or device access.
    write(work / 'execution-claim.json', result)
    owned = []

    def recheck():
        require(sha(path) == plan_sha and sha(SELF) == tool_sha and not bit.drift(value['BoundInputSHA256']),
                'SRAM plan/executor/source drift')
        for name, text in scripts(value['Bitstream']['Path']).items():
            require((work / (name + '.tcl')).read_bytes() == text.encode('utf-8'), 'SRAM scripts changed during execution')

    try:
        recheck()
        require(not hw.listening_pids(hw.PORT), 'JTAG port occupied; no existing process will be stopped')
        pds = Path(value['PDSBin'])
        server = hw._start_owned([str(pds / 'cdt_js.exe'), '-port', str(hw.PORT), '-work_dir', str(work)], work, owned, 'server')
        result['HardwareAccessed'] = True
        hw._await_owned_server(server)
        hw._owned_server_check(server)
        hw._check_scan(hw._client(adapter, 'scan', owned, timeout))
        result['ExpectedDeviceAndIDConfirmed'] = True
        recheck()
        old_server = server
        server = hw._program_server_after_scan(server, adapter, owned)
        result['ServerRestartedAfterScan'] = server is not old_server
        hw._owned_server_check(server)
        recheck()
        hw._owned_server_check(server)
        result['ProgrammingAttempted'] = True
        hw._check_program(hw._client(adapter, 'program', owned, timeout))
        result['DoneConfirmed'] = True
        recheck()
        result['Passed'] = True
    except BaseException as error:
        result['Error'] = type(error).__name__ + ': ' + str(error)
    finally:
        result['OwnedPIDs'] = [p.pid for p in owned]
        stopped, errors = hw._stop_owned(owned)
        result.update(TerminatedOwnedPIDs=stopped, CleanupErrors=errors,
                      Logs={p.name: sha(p) for p in sorted(work.glob('*.log')) if p.is_file()}, EndedUTC=bit.utc())
        if errors:
            result['Passed'] = False
        write(work / 'receipt.json', result)
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--bit-work', type=Path)
    p.add_argument('--prepare', type=Path)
    p.add_argument('--plan', type=Path)
    p.add_argument('--execute', action='store_true')
    p.add_argument('--board-powered', action='store_true')
    p.add_argument('--user-notified', action='store_true')
    p.add_argument('--timeout-seconds', type=float, default=90)
    a = p.parse_args()
    if a.prepare:
        require(a.bit_work and not a.plan and not a.execute, 'prepare needs only bit-work and new directory')
        value = prepare(a.bit_work, a.prepare)
        result = {'Prepared': True, 'Plan': str(Path(value['WorkDirectory']) / 'plan.json'), 'HardwareAccessed': False}
    else:
        require(a.plan and not a.bit_work, 'exact SRAM plan required')
        if a.execute:
            result = execute(a.plan, board_powered=a.board_powered, user_notified=a.user_notified, timeout=a.timeout_seconds)
        else:
            validate(a.plan)
            result = {'Validated': True, 'HardwareAccessed': False}
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0 if result.get('Passed', True) else 1


if __name__ == '__main__':
    raise SystemExit(main())
