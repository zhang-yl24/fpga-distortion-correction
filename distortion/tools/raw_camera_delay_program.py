"""Prepare/validate raw-input-delay SRAM programming; explicit execute uses owned JTAG.

Power must have been confirmed after the most recent shutdown. The operator must notify
the user before execution and assert board power still holds. Volatile SRAM
only; no Flash, UART, builds or automatic programming from prepare/validate.
"""
import argparse
import json
import math
from pathlib import Path

import raw_camera_delay_bitstream as bit
import program_native_raw as hw

prep=bit.prep
require,sha=bit.require,bit.sha
SELF=Path(__file__).resolve()
SCHEMA='raw-camera-delay-sram-plan-v1'


def scripts(bitfile):
    value=hw._scripts({'bitstream_path':str(bitfile)},'1MHz')
    require(set(value)=={'scan','program'} and all('flash' not in text.lower() for text in value.values()),'only native volatile SRAM recipe allowed')
    return value


def recipe(bitwork,work):
    bitwork=prep.work_path(bitwork);work=prep.work_path(work)
    require(work.name.startswith('program-'),'raw-input-delay program-* direct child required')
    verified=bit.verify(bitwork);bitplan,context=bit.validate(bitwork)
    require(verified.get('Verified') is True and verified['Target']==prep.TARGET,'verified raw-input-delay bit required')
    pds=hw.resolve_pds_bin(Path(context['Build']['PDS']['Executable']).parent)
    bindings=dict(bitplan['InputSHA256'])
    for n,h in verified['EvidenceSHA256'].items():
        require(sha(bitwork/n)==h,'bit evidence changed');bindings[str(bitwork/n)]=h
    for file in (SELF,Path(bit.__file__).resolve(),Path(hw.__file__).resolve(),
                 prep.PROJECT/'tools/native_camera_capture.py',prep.PROJECT/'tools/frame_protocol.py',
                 prep.PROJECT/'tools/camera_eye_pin_audit.py',pds/'cdt_js.exe',pds/'cdt_cfg_shell.exe',
                 bitwork/'tool-snapshot.py',bitwork/'audited-final.adf'):
        bindings[str(file)]=sha(file)
    text=scripts(verified['Bitstream']['Path'])
    value={'Schema':SCHEMA,'Target':prep.TARGET,'WorkDirectory':str(work),'BitstreamWorkDirectory':str(bitwork),
        'Operation':'volatile_sram_only','ExpectedDevice':hw.DEVICE,'ExpectedDeviceID':hw.DEVICE_ID,
        'CableIndex':0,'Frequency':'1MHz','ServerPort':hw.PORT,'PDSBin':str(pds),
        'Bitstream':verified['Bitstream'],'CandidateADFSHA256':verified['CandidateADFSHA256'],
        'BoundInputSHA256':bindings,'Tcl':{k:{'Path':str(work/(k+'.tcl')),
            'SHA256':prep.baseline.paths.sha_bytes(v.encode('utf-8'))} for k,v in text.items()},
        'PreparedOnly':True,'HardwareAccessed':False,'Executed':False,'FlashWritten':False,
        'RequiresExplicitExecute':True,'RequiresCurrentSessionBoardPower':True,'UserMustBeNotifiedBeforeExecution':True,
        'CurrentPowerConfirmationRequired':True,'HardwareReleaseAllowed':False,'ExternalACTimingAccepted':False,
        'DiagnosticOnly':True,'CameraInterface':'CAM2_OV5640_DVP_RGB565',
        'Limits':'Volatile SRAM/DONE only. PGFRAME1 payload/CRC/orientation, actual connection, external AC and sustained operation remain separate.'}
    require(all(sha(p)==h for p,h in bindings.items()),'raw-input-delay SRAM evidence drift')
    return value,text


def prepare(bitwork,work):
    value,text=recipe(bitwork,work);work=Path(value['WorkDirectory'])
    require(not work.exists(),'fresh raw-input-delay programming stage required');work.mkdir()
    for k,v in text.items():
        with (work/(k+'.tcl')).open('x',encoding='utf-8',newline='\n') as f:f.write(v)
    value['PreparedUTC']=prep.utc();bit.inspect.diagnostic.write(work/'plan.json',value)
    return value


def validate(path):
    path=bit.inspect.canonical(path,prep.WORK);work=prep.work_path(path.parent);value=bit.read(path)
    require(path.name=='plan.json' and value.get('Schema')==SCHEMA and value.get('Target')==prep.TARGET,'exact raw-input-delay SRAM plan required')
    expected,text=recipe(value['BitstreamWorkDirectory'],work)
    require(set(value)==set(expected)|{'PreparedUTC'} and {k:v for k,v in value.items() if k!='PreparedUTC'}==expected,
            'raw-input-delay SRAM plan differs from complete verified recipe')
    for k,v in text.items():
        require((work/(k+'.tcl')).read_bytes()==v.encode('utf-8'),'SRAM Tcl recipe changed')
    return value


def execution_authorization(board_powered,user_notified,timeout):
    require(board_powered is True,'current session board power must be confirmed before hardware access')
    require(user_notified is True,'notify user before this board session')
    require(type(timeout) in (int,float) and math.isfinite(timeout) and 0<timeout<=300,'timeout must be finite in (0,300]')


def execute(path,*,board_powered=False,user_notified=False,timeout=90):
    execution_authorization(board_powered,user_notified,timeout)
    path=Path(path).absolute();value=validate(path);work=path.parent
    require({p.name for p in work.iterdir()}=={'plan.json','scan.tcl','program.tcl'},'fresh prepared SRAM stage required')
    plan_sha=sha(path);tool_sha=sha(SELF)
    adapter={'workdir':str(work),'pds_bin':value['PDSBin'],'frequency':value['Frequency'],
        'tcl':{k:{'path':v['Path'],'sha256':v['SHA256']} for k,v in value['Tcl'].items()}}
    result={'Schema':'raw-camera-delay-sram-execution-v1','Target':prep.TARGET,'StartedUTC':prep.utc(),
        'PlanSHA256':plan_sha,'ExecutorSHA256':tool_sha,'WorkDirectory':str(work),'Bitstream':value['Bitstream'],
        'CandidateADFSHA256':value['CandidateADFSHA256'],'UserConfirmedBoardPowered':True,'UserNotifiedBeforeExecution':True,
        'CurrentPowerConfirmationAsserted':True,'Passed':False,'Executed':True,'HardwareAccessed':False,
        'ProgrammingAttempted':False,'DoneConfirmed':False,'FlashWritten':False,'HardwareReleaseAllowed':False,
        'ExternalACTimingAccepted':False,'DiagnosticOnly':True,'ServerRestartedAfterScan':False}
    owned=[]
    def recheck():
        require(sha(path)==plan_sha and sha(SELF)==tool_sha,'SRAM plan/executor drift')
        require(all(sha(p)==h for p,h in value['BoundInputSHA256'].items()),'bound SRAM input drift')
        for k,v in scripts(value['Bitstream']['Path']).items():
            require((work/(k+'.tcl')).read_bytes()==v.encode('utf-8'),'SRAM script changed during execution')
    try:
        recheck();require(not hw.listening_pids(hw.PORT),'JTAG port occupied; no process started or stopped')
        pds=Path(value['PDSBin']);server=hw._start_owned([str(pds/'cdt_js.exe'),'-port',str(hw.PORT),'-work_dir',str(work)],work,owned,'server')
        result['HardwareAccessed']=True;hw._await_owned_server(server);hw._owned_server_check(server)
        hw._check_scan(hw._client(adapter,'scan',owned,timeout));recheck()
        scanned=server;server=hw._program_server_after_scan(server,adapter,owned)
        result['ServerRestartedAfterScan']=server is not scanned
        hw._owned_server_check(server);recheck();hw._owned_server_check(server)
        result['ProgrammingAttempted']=True
        hw._check_program(hw._client(adapter,'program',owned,timeout));result['DoneConfirmed']=True
        recheck();result['Passed']=True
    except BaseException as error:result['Error']=type(error).__name__+': '+str(error)
    finally:
        result['OwnedPIDs']=[p.pid for p in owned]
        stopped,errors=hw._stop_owned(owned);result['TerminatedOwnedPIDs']=stopped;result['CleanupErrors']=errors
        if errors:result['Passed']=False
        result['Logs']={p.name:sha(p) for p in sorted(work.glob('*.log')) if p.is_file()}
        result['EndedUTC']=prep.utc();hw._new_json(work/'receipt.json',result)
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--bit-work',type=Path);p.add_argument('--prepare',type=Path)
    p.add_argument('--plan',type=Path);p.add_argument('--execute',action='store_true');p.add_argument('--board-powered',action='store_true')
    p.add_argument('--user-notified',action='store_true');p.add_argument('--timeout-seconds',type=float,default=90);a=p.parse_args()
    if a.prepare:
        require(a.bit_work and not a.plan and not a.execute,'prepare needs bit-work only')
        value=prepare(a.bit_work,a.prepare);r={'PreparedOnly':True,'Plan':str(Path(value['WorkDirectory'])/'plan.json'),'HardwareAccessed':False}
    else:
        require(a.plan and not a.bit_work,'exact plan path required')
        if a.execute:r=execute(a.plan,board_powered=a.board_powered,user_notified=a.user_notified,timeout=a.timeout_seconds)
        else:validate(a.plan);r={'Validated':True,'HardwareAccessed':False}
    print(json.dumps(r,indent=2,allow_nan=False));return 0 if r.get('Passed',True) else 1


if __name__=='__main__':raise SystemExit(main())
