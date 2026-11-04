"""Explicit saved-verification SRAM continuation; no STA or bit generation rerun."""
import argparse
from pathlib import Path
import json
import os
import subprocess
import sys
import time

WORK=Path(__file__).resolve().parent
REPO=WORK.parents[2]
LAB=REPO/'output/new-next-probe-20261104/assoc2way256-fastpipe-a'
sys.path[:0]=[str(REPO/'distortion/tools'),str(REPO/'.venv/Lib/site-packages')]
import psutil
import hdmi_camera_fisheye_assoc2way256_fastpipev4_bitstream as bit
import hdmi_camera_fisheye_assoc2way256_fastpipev4_program as program
import measure_hdmi_fisheye_fps as fps

def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--verification-sha',required=True)
 p.add_argument('--authority-sha',required=True)
 p.add_argument('--previous-worker-pid',type=int,default=24952)
 args=p.parse_args()
 require=bit.require
 require(not psutil.pid_exists(args.previous_worker_pid),'previous worker must actually stop before continuation')
 active=[x.info for x in psutil.process_iter(['pid','name'])if(x.info['name']or'').lower()in
         ('pds.exe','pds_shell.exe','cdt_js.exe','cdt_cmd.exe','cdt_cfg_shell.exe')]
 require(not active,'exclusive native/JTAG ownership required')
 require(not Path('P:/').exists()or os.path.samefile('P:/',REPO),'existing alias points outside exact repository')
 bitwork=WORK/'bit-v4-a';programwork=WORK/'program-v4-reuse-a';fpswork=WORK/'fps-corrected-v4-reuse-a'
 require(not programwork.exists()and not fpswork.exists(),'fresh program and measurement directories required')
 authority_path=WORK/'release-v4-authority-a.json';verification_path=bitwork/'verification.json'
 require(bit.sha(authority_path)==args.authority_sha and bit.sha(verification_path)==args.verification_sha,'exact completed authority/verification required')
 authority=bit.read(authority_path);checked=bit.read(verification_path);plan=bit.read(bitwork/'bitstream-plan.json')
 require(authority.get('Schema')==bit.AUTHORITY_SCHEMA and authority.get('FlashAuthorized')is False and
         all(authority.get('RootHandoff',{}).get(k)is True for k in ('UserAuthorizedVolatileSRAM','UserNotifiedBeforeExecution')),
         'existing volatile SRAM authorization required')
 require(checked.get('Schema')=='hdmi-camera-fisheye-assoc2way256fastpipev4-bitstream-verification-v1'and
         checked.get('Verified')is True and all(checked.get('FreshSTA',{}).get(k)is True for k in
         ('STAAllTenPassed','ClockAndSummaryIdentityPreserved','AllExceptionPathsPreserved')),'actual successful bit verification required')
 require(checked['Bitstream']['SHA256']=='e92cb8d00f11b1d4d1c239bd457fd9095289ac38c9215c9cfcf7e738d7eda26e','exact completed bit required')
 witness_path=Path(plan['ClosureWitness']['Path']);require(bit.ref(witness_path)==plan['ClosureWitness'],'bound closure witness changed')
 witness=bit.read(witness_path);request_path=Path(plan['Request']['Path'])
 expected=dict(authority['InputSHA256']);expected[str(authority_path)]=args.authority_sha;expected[str(request_path)]=bit.sha(request_path)
 require(witness.get('Schema')==bit.WITNESS_SCHEMA and witness.get('Authority')==bit.ref(authority_path)and
         witness.get('Request')==bit.ref(request_path)and witness.get('InputSHA256')==expected and
         witness.get('AllSHA256VerifiedOnce')is True and witness.get('FullPhysicalOrSimulationRederived')is False,
         'exact completed one-pass SHA witness required')
 states=witness['FileIdentity'];require(set(states)==set(expected),'witness file identities incomplete')
 for name,digest in expected.items():
  require(bit.file_identity(name)==states[name],'once-checked closure identity changed: '+name)
  bit._SHA_IDENTITIES[name]=(states[name],digest)
 require(plan['SavedAuthority']==bit.ref(authority_path)and plan['InputSHA256'].get(str(witness_path))==bit.sha(witness_path),
         'bit plan authority/witness role differs')
 evidence={str((bitwork/name).resolve()):digest for name,digest in checked['EvidenceSHA256'].items()}
 require(all(Path(name).is_relative_to(bitwork)for name in evidence),'verified bit artifact escaped work')
 require(not bit.drift(evidence),'completed verified bit artifacts changed')
 require(bit.sha(checked['Bitstream']['Path'])==checked['Bitstream']['SHA256']and
         bit.bit_header(Path(checked['Bitstream']['Path']).read_bytes())==checked['Bitstream']['Header'],'exact actual bit header differs')
 execution=bit.read(bitwork/'execution-result.json');gate=bit.read(bitwork/'pre-bit-audit.json')
 require(type(execution.get('ExitCode'))is int and execution['ExitCode']==0 and execution.get('TimedOut')is False and
         execution.get('InputDrift')==[] and not execution.get('Error')and gate.get('GatePassed')is True and
         gate.get('Checks')==checked['FreshSTA'] and gate.get('FinalADFSHA256')==checked['FinalADFSHA256'],
         'actual native success and gate evidence differ')
 build_record=plan['BuildPlan'];require(bit.sha(build_record['Path'])==build_record['SHA256'],'saved build changed')
 bit._SAVED_BUILDS[build_record['Path']]=bit.read(build_record['Path'])
 calls=[]
 def reused_verify(work):
  require(Path(work).resolve()==bitwork and bit.sha(verification_path)==args.verification_sha and
          not bit.drift(evidence)and not bit.drift(plan['InputSHA256']),'saved verification reuse drift')
  calls.append(bit.utc())
  return checked
 # Explicitly replace only the repeated verification entry point in this new
 # interpreter. Original frozen files and original SRAM functions stay exact.
 bit.verify=reused_verify
 claim=WORK/'saved-verification-program-continuation-v4-b.json'
 bit.write(claim,{'Schema':'fastpipe-saved-bit-verification-continuation-v4-b','CreatedUTC':bit.utc(),
  'Source':bit.ref(Path(__file__)),'SavedVerification':bit.ref(verification_path),'Authority':bit.ref(authority_path),
  'ReusedVerification':True,'STAReexecuted':False,'BitstreamRegenerated':False,'PreviousWorkerPID':args.previous_worker_pid,
  'PreviousWorkerAbsentObserved':True,'ProgramDirectory':str(programwork),'MeasurementDirectory':str(fpswork),
  'OriginalProgramSource':bit.ref(Path(program.__file__)),'HardwareAccessed':False})
 owned=False
 try:
  if not Path('P:/').exists():
   result=subprocess.run(['subst.exe','P:',str(REPO)],capture_output=True,text=True)
   require(result.returncode==0,'own alias creation failed')
  require(os.path.samefile('P:/',REPO),'exact stopped-worker alias required');owned=True
  program.prepare(bitwork,programwork)
  result=program.execute(programwork/'plan.json',board_powered=True,user_notified=True,timeout=90)
  require(result.get('Passed')is True and result.get('DoneConfirmed')is True and result.get('ExpectedDeviceAndIDConfirmed')is True and
          result.get('FlashWritten')is False,'actual volatile SRAM programming failed')
  time.sleep(15)
  measured=fps.measure(fpswork,programwork/'receipt.json',seconds=30,port='COM7')
  require(measured.get('passed')is True,'actual camera acquisition failed')
  print(json.dumps({'Passed':True,'ReusedVerification':True,'ReuseChecks':len(calls),
   'ProgramReceipt':bit.ref(programwork/'receipt.json'),'MeasurementReceipt':bit.ref(fpswork/'receipt.json')}),flush=True)
 finally:
  if owned:
   require(os.path.samefile('P:/',REPO),'owned alias changed')
   subprocess.run(['subst.exe','P:','/D'],check=True,capture_output=True)

if __name__=='__main__':main()
