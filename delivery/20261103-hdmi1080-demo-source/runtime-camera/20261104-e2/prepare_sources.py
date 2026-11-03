# Reconstruct ordinary sources only. This never compiles, simulates or opens hardware.
from pathlib import Path
import argparse,json,hashlib,re,shutil
from verify_delivery import ROOT,verify,read,project_bytes
def safe(s):
 p=Path(s)
 if p.is_absolute()or '..'in p.parts:raise ValueError('Unsafe source path')
 return p
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--dependencies',required=True,type=Path);ap.add_argument('--output',required=True,type=Path);ap.add_argument('--enable-runtime',action='store_true');a=ap.parse_args()
 verify();out=a.output.resolve();deps=a.dependencies.resolve()
 if out.exists():raise SystemExit('Output must not exist')
 m=read(ROOT/'SOURCE_BINDING.json')
 for r in m['files']:
  if r['disposition']=='external_dependency_not_published':
   p=deps/safe(r['path'])
   if not p.is_file()or hashlib.sha256(p.read_bytes()).hexdigest()!=r['original_sha256']:raise SystemExit('Missing dependency/hash mismatch: '+r['path'])
 out.mkdir(parents=True)
 for r in m['files']:
  p=out/safe(r['path']);p.parent.mkdir(parents=True,exist_ok=True)
  if r['disposition']=='external_dependency_not_published':shutil.copyfile(deps/r['path'],p);continue
  b=project_bytes(r);t=b.decode('utf-8')
  for x in r['include_changes']:
   old=chr(96)+'include "'+x['target']+'"';new=chr(96)+'include "'+(out/x['target']).as_posix()+'"'
   assert old in t;t=t.replace(old,new)
  if a.enable_runtime and p.name=='board1080_cfg100_top.v':
   t,n=re.subn(r'(parameter\s+(?:integer\s+)?CAMERA_RUNTIME_GAMMA\s*=\s*)0',r'\g<1>1',t);assert n==1
  p.write_bytes(t.encode('utf-8'))
 files=[{'path':p.relative_to(out).as_posix(),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}for p in out.rglob('*')if p.is_file()]
 (out/'PREPARATION.json').write_text(json.dumps({'source_only':True,'runtime_topflag':int(a.enable_runtime),'new_compile_sim_PDS_hardware':False,'files':files},indent=2),encoding='utf-8')
 print(json.dumps({'sources':len(files),'runtime_topflag':int(a.enable_runtime),'compile_sim_PDS_hardware':False}))
if __name__=='__main__':main()
