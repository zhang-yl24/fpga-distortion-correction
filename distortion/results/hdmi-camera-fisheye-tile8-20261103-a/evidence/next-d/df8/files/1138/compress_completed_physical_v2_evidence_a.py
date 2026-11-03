"""Reversible NTFS compression for completed revised S3v2 physical stage evidence, byte identity checked."""
import argparse
import re
import ctypes
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess

base=Path(__file__).resolve().parent
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--stage',required=True);parser.add_argument('--tag',required=True);args=parser.parse_args()
if not all(re.fullmatch(r'[A-Za-z0-9_-]+',v)for v in(args.stage,args.tag)):raise ValueError('simple stage/tag required')
output=base/('compression-physical-v2-'+args.stage+'-'+args.tag+'.json')
if output.exists():raise ValueError('fresh compression receipt required')
roots=[base/args.stage]
if any(root!=root.resolve()or root.parent!=base or not root.is_dir()for root in roots):raise ValueError('one completed canonical S3 native stage required')
for root in roots:
    receipt=root/'result.json'
    value=json.loads(receipt.read_text(encoding='utf-8-sig'))
    if value.get('Schema') not in {'hdmi-camera-fisheye-tile8df8-native-inspection-v1','hdmi-camera-fisheye-tile8df8v2-scoped-native-inspection-v1','hdmi-camera-fisheye-tile8df8v2-targeted-native-query-v1','hdmi-camera-fisheye-tile8df8v2-physical-application-v1'} or value.get('ExitCode')!=0 or value.get('ExecutionPassed')is not True or value.get('Cleanup',{}).get('Complete')is not True or value.get('InputDrift')!=[] or value.get('TimedOut')is not False or not value.get('FinishedUTC'):raise ValueError('completed actual S3 native stage required: '+str(root))
def sha(p):
    h=hashlib.sha256()
    with p.open('rb')as f:
        for chunk in iter(lambda:f.read(8*1024*1024),b''):h.update(chunk)
    return h.hexdigest()
def free():
    available=ctypes.c_ulonglong();total=ctypes.c_ulonglong();actual=ctypes.c_ulonglong()
    if not ctypes.windll.kernel32.GetDiskFreeSpaceExW(str(base.anchor),ctypes.byref(available),ctypes.byref(total),ctypes.byref(actual)):
        raise ctypes.WinError()
    return {'AvailableToCallerBytes':available.value,'ActualFreeBytes':actual.value,'VolumeTotalBytes':total.value}
def allocation(p):
    high=ctypes.c_uint32();ctypes.set_last_error(0)
    low=ctypes.windll.kernel32.GetCompressedFileSizeW(str(p),ctypes.byref(high))
    if low==-1 and ctypes.get_last_error():raise ctypes.WinError()
    return (high.value<<32)|(low&0xffffffff)
paths=sorted(p for root in roots for p in root.rglob('*')if p.is_file()and p.suffix.lower()in('.db','.rtr')and p.stat().st_size>100_000_000)
value={'Schema':'hdmi-camera-fisheye-tile8df8v2-completed-physical-evidence-compression-v1','Passed':False,
    'StartedUTC':datetime.now(timezone.utc).isoformat(),'ScopedDirectories':[str(p)for p in roots],
    'FileCount':len(paths),'FreeBefore':free(),'Files':[],'ContentMutationRequested':False,
    'DeletedOrMovedFiles':False,'ActiveS3OrFrozenCEvidenceCompressed':False,
    'NativeCompletionReceipt':str(roots[0]/'result.json'),
    'NativeCompletionReceiptSHA256':sha(roots[0]/'result.json'),
    'TimingAccepted':False,'HardwareAccessed':False,'EDAExecuted':False}
compact=Path(os.environ['SystemRoot'])/'System32/compact.exe'
for p in paths:
    if p!=p.resolve()or not any(p.is_relative_to(root)for root in roots):raise ValueError('scope violation')
    row={'Path':str(p),'LogicalBytes':p.stat().st_size,'SHA256Before':sha(p),'AllocatedBytesBefore':allocation(p)}
    result=subprocess.run([str(compact),'/C','/I','/Q',str(p)],capture_output=True,
        creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    row.update(CompactCommand=[str(compact),'/C','/I','/Q',str(p)],CompactExitCode=result.returncode,
        CompactStdout=result.stdout.decode('mbcs',errors='replace'),CompactStderr=result.stderr.decode('mbcs',errors='replace'),
        SHA256After=sha(p),AllocatedBytesAfter=allocation(p),LogicalBytesAfter=p.stat().st_size)
    row['ByteIdentityPreserved']=row['SHA256Before']==row['SHA256After']and row['LogicalBytes']==row['LogicalBytesAfter']
    value['Files'].append(row)
    print(json.dumps({k:row[k]for k in('Path','CompactExitCode','ByteIdentityPreserved','AllocatedBytesBefore','AllocatedBytesAfter')}),flush=True)
    if not row['ByteIdentityPreserved']:raise ValueError('evidence bytes changed')
value.update(FreeAfter=free(),EndedUTC=datetime.now(timezone.utc).isoformat(),
    Passed=all(r['ByteIdentityPreserved']and r['CompactExitCode']==0 for r in value['Files']))
value['ActualFreeChangeBytes']=value['FreeAfter']['ActualFreeBytes']-value['FreeBefore']['ActualFreeBytes']
value['AllocatedBytesSaved']=sum(r['AllocatedBytesBefore']-r['AllocatedBytesAfter']for r in value['Files'])
output.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps({k:value[k]for k in('Passed','FileCount','ActualFreeChangeBytes','AllocatedBytesSaved')}),flush=True)
