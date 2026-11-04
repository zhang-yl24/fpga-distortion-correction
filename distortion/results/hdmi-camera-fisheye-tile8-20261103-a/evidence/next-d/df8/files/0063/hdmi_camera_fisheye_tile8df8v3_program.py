"""Prepare/validate or explicitly execute one HDMI fisheye diagnostic SRAM event.

Every file is verified before/after scan and programming. Only owned JTAG
processes are managed; no Flash, UART traffic, bitstream generation or fallback
image is provided. DONE is not bitwise configuration readback or pixel proof.
"""
import argparse
import json
import math
from pathlib import Path

import hdmi_camera_fisheye_tile8df8v3_bitstream as bit
import program_native_raw as hw

SELF = Path(__file__).resolve()
TARGET = bit.TARGET
SCHEMA = 'hdmi-camera-fisheye-tile8df8v3-sram-plan-v1'
EXEC_SCHEMA = 'hdmi-camera-fisheye-tile8df8v3-sram-execution-v1'
PRIOR_CAMERA_RECEIPT = bit.ROOT/'work/hdmi-camera-snapshot-20261102-a/captures-b/first-b-receive.json'
DISPLAY_CONFIRMATION = bit.ROOT/'work/direct-20261102-a/user-display-confirmed-a.json'
DISPLAY_BIT_SHA256 = '33aca64d692778a9ba316828c32b9b816a0878de701e8e7fd4febcc703335156'
require, sha, read, write = bit.require, bit.sha, bit.read, bit.write


def scripts(bitfile):
    values = hw._scripts({'bitstream_path': str(bitfile)}, '1MHz')
    require(set(values) == {'scan', 'program'} and all('flash' not in t.lower() for t in values.values()),
            'only exact volatile SRAM scripts allowed')
    return values


def bind_display_confirmation(path,watched):
    """Bind the user's existing same-board/direct-display observation.

    This is prior-board/cabling evidence, not a claim that the new snapshot
    candidate has already displayed or exported a frame. No UART probe runs.
    """
    path=bit.add(watched,path);value=read(path)
    require(value.get('Schema')=='hdmi-camera-direct-user-display-observation-v1' and
            value.get('Source')=='explicit_user_reply' and value.get('RealCameraMotionObservedByUser')is True and
            value.get('StableDisplayConfirmedByUser')is True and value.get('BitstreamSHA256')==DISPLAY_BIT_SHA256,
            'existing user-confirmed direct display on this board required')
    receipt_path=bit.binding(value['ProgramReceipt'],watched);receipt=read(receipt_path)
    require(receipt.get('Schema')=='hdmi-camera-direct-sram-execution-v1' and
            receipt.get('Target')=='hdmi_camera_direct_top' and receipt.get('Passed')is True and
            receipt.get('DoneConfirmed')is True and receipt.get('ExpectedDeviceAndIDConfirmed')is True and
            receipt.get('FlashWritten')is False and receipt.get('CleanupErrors')==[] and
            receipt.get('Bitstream',{}).get('SHA256')==DISPLAY_BIT_SHA256 and
            receipt.get('Bitstream',{}).get('Bytes')==bit.EXPECTED_BIT_BYTES,
            'prior successful direct SRAM receipt differs')
    bit.add(watched,receipt['Bitstream']['Path'],DISPLAY_BIT_SHA256)
    return bit.ref(path)


def bind_prior_camera(path,watched):
    """Bind prior successful same-board image reception without opening UART."""
    path=bit.add(watched,path);value=read(path)
    require(value.get('schema')=='hdmi-source-snapshot-receive-v1'and value.get('passed')is True and
        value.get('source_kind')=='physical_hdmi_camera'and value.get('uart_transmit_bytes')==0 and
        value.get('crc_rejected_packets')==0 and value.get('frames'),
        'existing successful physical HDMI image receipt required')
    binding=value['source_binding'];firmware=binding['firmware'];paths={}
    for key in ('bitstream','program_receipt','physical_proof'):
        record=firmware[key];require(set(record)=={'path','sha256'},'prior camera lowercase path/sha256 reference required')
        paths[key]=bit.add(watched,record['path'],record['sha256'])
    prior=read(paths['program_receipt']);proof=read(paths['physical_proof'])
    require(prior.get('Target')=='hdmi_camera_snapshot_top'and prior.get('Passed')is True and
        prior.get('DoneConfirmed')is True and prior.get('ExpectedDeviceAndIDConfirmed')is True and
        prior.get('FlashWritten')is False and prior.get('CleanupErrors')==[] and
        prior['Bitstream']['SHA256']==sha(paths['bitstream'])and proof.get('Passed')is True and
        proof.get('Target')=='hdmi_camera_snapshot_top'and prior['FinalADFSHA256']==proof['FinalADF']['SHA256'],
        'prior successful snapshot firmware provenance differs')
    frame=value['frames'][0];metadata_path=bit.add(watched,frame['metadata']);metadata=read(metadata_path)
    require(metadata.get('schema')=='hdmi-source-snapshot-frame-v1'and metadata.get('source_kind')=='physical_hdmi_camera'and
        metadata.get('camera_id')==binding['camera_id']and metadata.get('lens_id')==binding['lens_id'],
        'prior received image identity differs')
    for key in ('image','payload'):
        record=metadata[key];bit.add(watched,record['path'],record['sha256'])
    return bit.ref(path)


def recipe(bit_work, work, display_confirmation=DISPLAY_CONFIRMATION,prior_camera_receipt=PRIOR_CAMERA_RECEIPT):
    bit_work, work = bit.build.work_path(bit_work), bit.build.work_path(work)
    require(work.name.startswith('program-'), 'program-* snapshot child required')
    checked = bit.verify(bit_work)
    plan = read(bit_work / 'bitstream-plan.json')
    require(checked['Verified'] is True and checked['Target'] == TARGET
            and Path(checked['Bitstream']['Path']) == bit_work / bit.BIT
            and checked['FinalADFSHA256'] == plan['FinalADFSHA256'], 'current verified snapshot diagnostic bit required')
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
    display=bind_display_confirmation(display_confirmation,watched)
    camera=bind_prior_camera(prior_camera_receipt,watched)
    tcl = scripts(checked['Bitstream']['Path'])
    value = {'Schema': SCHEMA, 'Target': TARGET, 'WorkDirectory': str(work), 'BitstreamWorkDirectory': str(bit_work),
             'Bitstream': checked['Bitstream'], 'FinalADFSHA256': checked['FinalADFSHA256'],
             'Operation': 'volatile_sram_only', 'ExpectedDevice': hw.DEVICE, 'ExpectedDeviceID': hw.DEVICE_ID,
             'PriorDisplayConfirmation':display,'PriorDisplayBitstreamSHA256':DISPLAY_BIT_SHA256,
             'PriorCameraImageReceipt':camera,
             'PriorDisplayScope':'User confirmed motion/stable direct display on the same current board/cabling; no snapshot-image acceptance inherited.',
             'UARTPrecheckRequired':False,
             'CableIndex': 0, 'Frequency': '1MHz', 'ServerPort': hw.PORT, 'PDSBin': str(pds),
             'BoundInputSHA256': watched, 'Tcl': {k: {'Path': str(work / (k + '.tcl')),
                 'SHA256': bit.hashlib.sha256(v.encode('utf-8')).hexdigest()} for k, v in tcl.items()},
             'PreparedOnly': True, 'Executed': False, 'HardwareAccessed': False, 'FlashWritten': False,
             'RequiresExplicitExecute': True, 'RequiresCurrentSessionBoardPower': True,
             'UserMustBeNotifiedBeforeExecution': True, 'SameSessionAuthorizationMayBeReused': True,
             'HardwareReleaseAllowed': False, 'PixelsVerified': False, 'ExternalACAccepted': False,
             'Limits': 'This candidate processes RGB565 DDR frames through C fisheye or exact identity with a frame-boundary key toggle and PGHFPS02 status UART. Volatile SRAM scan/program/DONE only; '
                       'source RTL simulation is not post-route gate simulation. FPS still needs post-download UART measurement using the constrained 125 MHz core-clock basis; '
                       'no configuration bitwise readback, observed real pixel acceptance, image export, lens calibration, external AC or analog CDC/MTBF acceptance.'}
    require(not bit.drift(watched), 'SRAM preparation input drift')
    return value, tcl


def prepare(bit_work, work, display_confirmation=DISPLAY_CONFIRMATION,prior_camera_receipt=PRIOR_CAMERA_RECEIPT):
    value, tcl = recipe(bit_work, work,display_confirmation,prior_camera_receipt)
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
    require(value.get('Schema') == SCHEMA and value.get('Target') == TARGET, 'current snapshot SRAM identity required')
    expected, tcl = recipe(value['BitstreamWorkDirectory'], path.parent,value['PriorDisplayConfirmation']['Path'],
        value['PriorCameraImageReceipt']['Path'])
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
              'PriorDisplayConfirmation':value['PriorDisplayConfirmation'],'UARTPrecheckPerformed':False,
              'PriorCameraImageReceipt':value['PriorCameraImageReceipt'],
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
    p.add_argument('--display-confirmation',type=Path,default=DISPLAY_CONFIRMATION)
    p.add_argument('--prior-camera-receipt',type=Path,default=PRIOR_CAMERA_RECEIPT)
    a = p.parse_args()
    if a.prepare:
        require(a.bit_work and not a.plan and not a.execute, 'prepare needs only bit-work and new directory')
        value = prepare(a.bit_work, a.prepare,a.display_confirmation,a.prior_camera_receipt)
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
