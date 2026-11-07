"""Reuse the saved first-pass proof, generate real bits, program SRAM and measure camera FPS."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time

WORK=Path(__file__).resolve().parent
REPO=WORK.parents[2]
LAB=REPO/'output/new-next-probe-20261104/assoc2way256-fastpipe-a'
sys.path[:0]=[str(REPO/'distortion/tools'),str(REPO/'.venv/Lib/site-packages')]
import hdmi_camera_fisheye_assoc2way256_fastpipev4_bitstream as bit
import hdmi_camera_fisheye_assoc2way256_fastpipev4_program as program

AUTHORITY=WORK/'release-v4-authority-a.json'
STOP=LAB/'second-pass-stop-observation-v4-a.json'
STOP_SHA='9a4b170674f8c2c34d195d55eeb81e52f3bf2f0333fa13cf36576467336ed089'
FIRST=LAB/'first-pass-physical-proof-observation-v4-a.json'
FIRST_SHA='43835c7f8119bfd25ba2ba1192b56782445e18a0d92ae83a1a2b9021f71573d1'
PROOF=WORK/'final-proof-v2-b.json'
PROOF_SHA='4e331eb3b6bf21e12b5f9446e03e477156fefeeeddaeb760ab5eb3224a3b85e0'
ROOT_OBSERVATION=LAB/'firstpass-proof-root-observation-v4-a.json'
ROOT_OBSERVATION_SHA='5e340b69684247559c8f043c73abda0c74014315b999c20c58d0eb3f5774358f'

def remaining(deadline):
    return (deadline-datetime.now(timezone.utc)).total_seconds()

def stop_state(stopped,launch,ended):
    bit.require(stopped.get('Schema')=='fastpipe-user-requested-second-pass-stop-observation-v4-a' and
        stopped.get('SecondPassIntentionallyInterrupted') is True and stopped.get('SecondPassPassed') is False and
        all(stopped.get(k) is True for k in ('FirstPassProofPreserved','UserRequestedSkipRedundantRecomputation',
            'WorkerAbsent','PDSAbsent','PDriveReleased','OriginalExitReceiptPreserved')),
        'actual user-requested interruption and subsequent cleanup required')
    bit.require(type(stopped.get('ActualExitCode')) is int and stopped['ActualExitCode']==-1 and
        ended.get('ExitCode')==stopped['ActualExitCode'] and launch.get('PID')==ended.get('PID')==stopped.get('PID') and
        launch.get('CreationUTC')==ended.get('CreationUTC')==stopped.get('CreationUTC') and
        launch.get('ProcessHandleRetained') is True and ended.get('ProcessHandleRetained') is True,
        'original actual interrupted exit must remain unchanged')
    return True

def handoff(authority_sha):
    bit.require(bit.sha(AUTHORITY)==authority_sha,'exact approved v4 authority required')
    approved=bit.read(AUTHORITY)
    permission=approved.get('RootHandoff',{})
    bit.require(approved.get('Schema')=='fastpipe-saved-firstpass-release-authority-v4' and
        permission.get('UserAuthorizedVolatileSRAM') is True and permission.get('UserNotifiedBeforeExecution') is True and
        approved.get('FlashAuthorized') is False,'same-session SRAM authorization and notification required')
    bit.require(approved.get('RootObservation')=={'Path':str(ROOT_OBSERVATION),'SHA256':ROOT_OBSERVATION_SHA} and
        bit.sha(ROOT_OBSERVATION)==ROOT_OBSERVATION_SHA,'exact root first-pass/interruption observation required')
    observed=bit.read(ROOT_OBSERVATION)
    bit.require(observed.get('Schema')=='fastpipe-firstpass-proof-root-observation-v4' and observed.get('ExitCode')==-1 and
        all(observed.get(k) is True for k in ('SecondVerificationInterrupted','FirstPassCompleted','WorkerAbsent','PDSAbsent','PDriveReleased')),
        'root confirms saved first pass and actual interrupted second pass')
    for path,digest in ((STOP,STOP_SHA),(FIRST,FIRST_SHA),(PROOF,PROOF_SHA)):
        bit.require(bit.sha(path)==digest,'actual saved first-pass/stop evidence changed')
    stopped=bit.read(STOP);first=bit.read(FIRST)
    launch=bit.read(stopped['ActualLaunchReceipt']['Path']);ended=bit.read(stopped['ActualExitReceipt']['Path'])
    for record in (stopped['ActualLaunchReceipt'],stopped['ActualExitReceipt'],stopped['UserStopRequest']):
        bit.require(bit.ref(record['Path'])==record,'actual interruption source changed')
    stop_state(stopped,launch,ended)
    bit.require(observed['OriginalStopObservation']=={'Path':str(STOP),'SHA256':STOP_SHA} and
        observed['ActualLaunchReceipt']==stopped['ActualLaunchReceipt'] and observed['ActualExitReceipt']==stopped['ActualExitReceipt'],
        'root observation changed actual interruption identity')
    bit.require(first.get('FirstPassProofComplete') is True and first.get('NativeResultsAllActualExitZero') is True and
        first['FirstPassProof']==stopped['FirstPassProof']=={'Path':str(PROOF),'SHA256':PROOF_SHA},'completed first-pass proof identity differs')
    bit.require(stopped['FirstPassObservation']=={'Path':str(FIRST),'SHA256':FIRST_SHA},'first-pass observation differs')
    selected=approved['SelectedReleaseInputs']
    bit.require(selected['PhysicalProof']==first['FirstPassProof'],'saved first-pass proof must be selected')
    for path in (Path(__file__).resolve(),Path(program.__file__).resolve(),Path(bit.__file__).resolve(),LAB/'launch_release_v4_a.ps1'):
        bit.require(approved['InputSHA256'].get(str(path))==bit.sha(path),'release source not fixed in authority: '+str(path))
    import psutil
    bit.require(not psutil.pid_exists(stopped['PID']) and not Path('P:/').exists(),'prior worker or P alias remains')
    active=[p.info for p in psutil.process_iter(['pid','name']) if (p.info['name'] or '').lower() in
        ('pds.exe','pds_shell.exe','cdt_js.exe','cdt_cmd.exe','cdt_cfg_shell.exe')]
    bit.require(not active,'existing EDA/JTAG owner remains')
    return approved

def note(stage,**values):
    value=dict(Stage=stage,ObservedUTC=datetime.now(timezone.utc).isoformat(),**values)
    print(json.dumps(value),flush=True)
    bit.write(WORK/('release-v4-event-'+str(time.time_ns())+'.json'),value)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--authority-sha',required=True)
    parser.add_argument('--deadline-utc',default='2026-11-04T10:00:00Z')
    parser.add_argument('--maximum-bit-seconds',type=int,default=10800)
    args=parser.parse_args();deadline=datetime.fromisoformat(args.deadline_utc.replace('Z','+00:00'))
    bit.require(deadline.tzinfo is not None and 60<=args.maximum_bit_seconds<=10800,'valid deadline and bit budget required')
    approved=handoff(args.authority_sha)
    bit.require(remaining(deadline)>=180,'insufficient time for real bit/SRAM/30-second camera measurement')
    request={'Schema':bit.REQUEST_SCHEMA,'Target':bit.TARGET,**approved['SelectedReleaseInputs'],
             'Authority':{'Path':str(AUTHORITY),'SHA256':args.authority_sha}}
    request_path=WORK/'bit-request-v4-a.json';bit.write(request_path,request)
    maximum=min(args.maximum_bit_seconds,int(remaining(deadline))-150)
    bit.require(maximum>=60,'insufficient bit generation budget')
    owned=False
    try:
        result=subprocess.run(['subst.exe','P:',str(REPO)],capture_output=True,
            creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        bit.require(result.returncode==0 and os.path.samefile('P:/',REPO),'owned P alias creation failed');owned=True
        note('bit-prepare',MaximumSeconds=maximum,SecondPassExitCode=-1,FirstPassProofReused=True)
        bit.prepare(request_path,WORK/'bit-v4-a',maximum=maximum)
        note('bit-execute',Started=True)
        generated=bit.execute(WORK/'bit-v4-a')
        bit.require(generated.get('Verified') is True,'real bit generation and fresh STA verification failed')
        note('bit-verified',Bitstream=generated['Bitstream'])
        bit.require(remaining(deadline)>=140,'deadline leaves insufficient SRAM and 30-second camera time')
        plan=program.prepare(WORK/'bit-v4-a',WORK/'program-v4-a')
        bit.require(plan['Operation']=='volatile_sram_only' and plan['FlashWritten'] is False,'volatile SRAM only')
        receipt=program.execute(WORK/'program-v4-a/plan.json',board_powered=True,user_notified=True,timeout=90)
        bit.require(receipt.get('Passed') is True and receipt.get('DoneConfirmed') is True and
            receipt.get('ExpectedDeviceAndIDConfirmed') is True and receipt.get('FlashWritten') is False and
            receipt.get('CleanupErrors')==[],'actual SRAM programming unsuccessful')
        note('sram-programmed',Passed=True,Bitstream=receipt['Bitstream'],FlashWritten=False)
        bit.require(remaining(deadline)>=46,'deadline leaves insufficient camera settling and acquisition time')
        time.sleep(15)
        import measure_hdmi_fisheye_fps as fps
        measured=fps.measure(WORK/'fps-corrected-v4-a',WORK/'program-v4-a/receipt.json',seconds=30,port='COM7')
        bit.require(measured.get('passed') is True,'actual corrected camera acquisition failed')
        note('camera-fps30',Passed=True,Host=measured['independent_host_summary'],
             Nominal=measured['nominal_clock_summary'],Target30FPSNotAssumed=True)
    finally:
        if owned:
            bit.require(os.path.samefile('P:/',REPO),'owned P alias changed before cleanup')
            subprocess.run(['subst.exe','P:','/D'],check=True,capture_output=True,
                creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))

if __name__=='__main__':main()
