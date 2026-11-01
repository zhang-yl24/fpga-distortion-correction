"""Current candidate offline build and SRAM plan only; no hardware execution."""
from pathlib import Path
import sys,json,hashlib
base=Path(__file__).resolve().parent
sys.path.insert(0,str(base.parents[1]/'tools'))
import camera_vga_calibrated_bitstream as bit
import camera_vga_calibrated_program as program
request=base/'bit-request-a.json'
assert hashlib.sha256(request.read_bytes()).hexdigest()=='d944e3f766668aa1b0f915496ff5af6668fcaea3487fbd45f585790b27b72ddb'
work=base/'bit-a';target=base/'program-a'
assert not work.exists() and not target.exists()
plan=bit.prepare(request,work,900)
print(json.dumps({'Phase':'prepared','CandidateADFSHA256':plan['CandidateADFSHA256'],'HardwareAccessed':False}),flush=True)
verified=bit.execute(work)
assert verified['Verified'] is True
print(json.dumps({'Phase':'bit_verified','Bitstream':verified['Bitstream'],'HardwareAccessed':False}),flush=True)
prepared=program.prepare(work,target)
assert prepared['HardwareAccessed'] is False and prepared['Executed'] is False
result={'Schema':'calibrated-camera-offline-ready-v1','Target':bit.prep.TARGET,'CreatedUTC':bit.prep.utc(),
'VerifiedBitstream':verified['Bitstream'],'CandidateADFSHA256':verified['CandidateADFSHA256'],
'ProgramPlan':str(target/'plan.json'),'ProgramPlanSHA256':bit.sha(target/'plan.json'),
'BoardPowered':False,'HardwareAccessed':False,'HardwareCorrectionVerified':False,'FlashWritten':False}
bit.inspect.diagnostic.write(base/'offline-ready-a.json',result)
print(json.dumps(result),flush=True)
