"""Explicitly admitted cloud-only test; no device, network or installed-tool changes."""
from pathlib import Path
import sys,json,hashlib,argparse,os,shutil
sys.dont_write_bytecode=True
from bounded_process import command
from check_fault import verify
R=Path(__file__).resolve().parent
def check_inputs():
 m=json.loads((R/'manifest.json').read_text())
 for e in m['files']:
  p=R/e['path'];assert p.is_file() and p.stat().st_size==e['bytes'] and hashlib.sha256(p.read_bytes()).hexdigest()==e['sha256'],e['path']
 b=json.loads((R/'FINAL_SOURCE_BINDING.json').read_text());assert len(b['source_files'])==37
 for e in b['source_files']:assert hashlib.sha256((R/e['path']).read_bytes()).hexdigest()==e['sha256']
 return {'manifest_files':len(m['files']),'frozen_RTL_headers':37,'HDL':'NOT_RUN','HardwareReleaseAllowed':False}
def main():
 p=argparse.ArgumentParser();p.add_argument('--rtl',action='store_true');p.add_argument('--out',required=True);p.add_argument('--admitted-seconds',type=int)
 a=p.parse_args();result=check_inputs()
 if not a.rtl:print(json.dumps(result,indent=2));return
 assert os.name=='posix' and a.admitted_seconds and 1<=a.admitted_seconds<=900
 out=Path(a.out).resolve();assert not out.exists() and not any(str(out)==x or str(out).startswith(x+'/') for x in ['/tmp','/dev/shm'])
 out.mkdir(parents=True)
 for f in (R/'vectors').iterdir():
  if f.suffix in ('.mem','.vh'):os.symlink(f,out/f.name)
 sources=[str(R/n) for n in (R/'sources.f').read_text().splitlines() if n];assert len(sources)==34
 result['HDL']='RUNNING'
 try:
  command(['iverilog','-g2012','-s','tb_b4_real_system','-I',str(out),'-I',str(R/'ce'),'-I',str(R/'b4/rtl'),'-I',str(R/'tests'),'-o',str(out/'fault.vvp'),*sources,str(R/'tests/tb_b4_fault_recovery.sv')],out,'compile',90)
  command(['vvp',str(out/'fault.vvp')],out,'simulate',a.admitted_seconds)
  result['oracle']=verify(R,out);result['HDL']='PASS'
 except BaseException as exc:
  result.update(HDL='FAIL_OR_INCOMPLETE',error=type(exc).__name__+': '+str(exc));raise
 finally:
  try:result['postcheck']=check_inputs()
  except BaseException as exc:result.update(HDL='FAIL_OR_INCOMPLETE',postcheck_error=str(exc))
  (out/'result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
 print(json.dumps(result,indent=2))
if __name__=='__main__':main()
