"""Validate a diagnostic camera SRAM plan; program only after new power confirmation.

Default is read-only validation. --execute and --board-powered are both required
for one volatile SRAM programming event using an owned JTAG server. No Flash or
UART actions occur. Programmer DONE does not establish camera/AC/CDC acceptance.
"""
from datetime import datetime,timezone
from pathlib import Path
import argparse
import json
import math
import re

import prepare_camera_vga_program as program

bit,hw=program.bit,program.native
require=bit.require


def validate(plan_path):
    path=Path(plan_path).absolute();work=path.parent
    require(path==path.resolve() and path.name=='plan.json' and work.parent==bit.BUILD and
            re.fullmatch(r'program-[A-Za-z0-9_-]+',work.name),'canonical camera program-* plan required')
    before=bit.sha(path);plan=bit.load(path)
    expected={'Schema':'camera-vga-sram-plan-v1','Target':bit.TARGET,'Operation':'volatile_sram_only',
              'ExpectedDevice':hw.DEVICE,'ExpectedDeviceID':hw.DEVICE_ID,'CableIndex':0,'Frequency':'1MHz','ServerPort':hw.PORT,
              'PreparedOnly':True,'ExecutionSupported':True,'RequiresExplicitExecuteAndBoardPowered':True,
              'RequiresNewPowerConfirmation':True,'UserMustBeNotifiedBeforeBoardSession':True,
              'DDRProcessingIncluded':True,'PhysicalInputCaptureIncluded':True,'CameraInterface':'CAM2_OV5640_DVP_RGB565',
              'DiagnosticOnly':True,'ExternalIOAccepted':False,'CDCPhysicalAccepted':False,'HardwareReleaseAllowed':False}
    for k,v in expected.items():require(type(plan.get(k)) is type(v) and plan[k]==v,'camera SRAM plan identity differs: '+k)
    require(plan['WorkDirectory']==str(work),'SRAM plan directory differs')
    for k in ('HardwareAccessed','Executed','ProgrammingAttempted','DoneConfirmed','FlashWritten'):
        require(plan.get(k) is False,'prepared SRAM plan must remain unexecuted: '+k)
    bit_work=bit.work_path(plan['BitstreamWorkDirectory']);verified=bit.verify(bit_work)
    require(verified.get('Verified') is True and verified.get('FinalADFSHA256')==bit.ADF_SHA and
            verified['Bitstream']==plan['Bitstream'] and plan['FinalADFSHA256']==bit.ADF_SHA,'camera bit identity differs')
    pds=hw.resolve_pds_bin(bit.PDS.parent);require(plan['PDSBin']==str(pds),'fixed PDS directory differs')
    bindings,cdc,pin=program.bound_inputs(bit_work,verified,pds,plan['CDCEvidence']['Path'],plan['PinEvidence']['Path'])
    require(bindings==plan['BoundInputSHA256'] and cdc==plan['CDCEvidence'] and pin==plan['PinEvidence'],
            'camera source/evidence complete bindings differ')
    require(all(bit.sha(name)==h for name,h in bindings.items()),'bound camera input drift')
    require(set(plan['Tcl'])=={'scan','program'},'exact scan and program scripts required')
    for stage,text in hw._scripts({'bitstream_path':verified['Bitstream']['Path']},'1MHz').items():
        entry=plan['Tcl'][stage];script=Path(entry['Path'])
        require(script==work/(stage+'.tcl') and script.resolve()==script and bit.sha(script)==entry['SHA256'] and
                script.read_text(encoding='utf-8')==text,'fixed camera SRAM recipe changed: '+stage)
    require(bit.sha(path)==before,'plan drift during validation');return plan


def execute(plan_path,*,board_powered=False,timeout_seconds=90.0):
    require(board_powered is True,'new user-confirmed board power is required before camera hardware access')
    require(type(timeout_seconds) in (int,float) and math.isfinite(timeout_seconds) and 0<timeout_seconds<=300,
            'timeout must be finite in (0,300]')
    path=Path(plan_path).absolute();plan=validate(path);work=path.parent
    require(not (work/'receipt.json').exists() and not list(work.glob('*.log')),'SRAM plan has execution outputs; prepare fresh plan')
    plan_sha,executor_sha=bit.sha(path),bit.sha(__file__)
    adapter={'workdir':str(work),'pds_bin':plan['PDSBin'],'frequency':plan['Frequency'],
             'tcl':{stage:{'path':entry['Path'],'sha256':entry['SHA256']} for stage,entry in plan['Tcl'].items()}}
    result={'Schema':'camera-vga-sram-execution-v1','Target':bit.TARGET,'StartedUTC':datetime.now(timezone.utc).isoformat(),
            'PlanSHA256':plan_sha,'ExecutorSHA256':executor_sha,'WorkDirectory':str(work),'Bitstream':plan['Bitstream'],
            'FinalADFSHA256':plan['FinalADFSHA256'],'Passed':False,'Executed':True,'UserConfirmedBoardPowered':True,
            'NewPowerConfirmationRequired':True,'HardwareAccessed':False,'ProgrammingAttempted':False,'DoneConfirmed':False,
            'FlashWritten':False,'HardwareReleaseAllowed':False,'ServerRestartedAfterScan':False,
            'DiagnosticOnly':True,'ExternalIOAccepted':False,'CDCPhysicalAccepted':False,
            'Limits':'SRAM programming and post-program DONE only. Live camera image, sustained progress, external AC and complete CDC physical signoff require separate evidence.'}
    owned=[]
    def recheck():
        require(bit.sha(path)==plan_sha and bit.sha(__file__)==executor_sha,'SRAM plan/executor changed')
        require(validate(path)==plan,'bound SRAM plan changed during execution')
    try:
        require(not hw.listening_pids(hw.PORT),'JTAG port occupied; no process started or stopped')
        pds=Path(plan['PDSBin'])
        server=hw._start_owned([str(pds/'cdt_js.exe'),'-port',str(hw.PORT),'-work_dir',str(work)],work,owned,'server')
        result['HardwareAccessed']=True;hw._await_owned_server(server);hw._owned_server_check(server)
        hw._check_scan(hw._client(adapter,'scan',owned,timeout_seconds));recheck()
        scanned=server;server=hw._program_server_after_scan(server,adapter,owned)
        result['ServerRestartedAfterScan']=server is not scanned
        hw._owned_server_check(server);recheck();hw._owned_server_check(server)
        result['ProgrammingAttempted']=True
        hw._check_program(hw._client(adapter,'program',owned,timeout_seconds));result['DoneConfirmed']=True
        recheck();result['Passed']=True
    except Exception as error:result['Error']=type(error).__name__+': '+str(error)
    finally:
        result['OwnedPIDs']=[p.pid for p in owned]
        stopped,errors=hw._stop_owned(owned);result['TerminatedOwnedPIDs']=stopped;result['CleanupErrors']=errors
        if errors:result['Passed']=False
        result['Logs']={p.name:bit.sha(p) for p in sorted(work.glob('*.log')) if p.is_file()}
        result['EndedUTC']=datetime.now(timezone.utc).isoformat();hw._new_json(work/'receipt.json',result)
    return result


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',type=Path,required=True)
    p.add_argument('--timeout-seconds',type=float,default=90.0);p.add_argument('--execute',action='store_true')
    p.add_argument('--board-powered',action='store_true',help='operator confirms a new user power-on confirmation for this session')
    args=p.parse_args(argv)
    if args.execute:
        result=execute(args.plan,board_powered=args.board_powered,timeout_seconds=args.timeout_seconds)
        print(json.dumps(result,indent=2,allow_nan=False));return 0 if result['Passed'] else 1
    plan=validate(args.plan);print(json.dumps({'ValidationPassed':True,'Target':plan['Target'],'HardwareAccessed':False,
                                           'BitstreamSHA256':plan['Bitstream']['SHA256']}));return 0


if __name__=='__main__':raise SystemExit(main())
