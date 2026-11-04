# Reconstruct sources only. Never compile, simulate, execute PDS or open serial.
from pathlib import Path
import argparse,json,hashlib,re,shutil
from verify_delivery import ROOT,verify,project_bytes
def rel(s):
    p=Path(s)
    if p.is_absolute()or '..'in p.parts:raise ValueError('Unsafe source path')
    return p
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--dependencies',required=True,type=Path)
    ap.add_argument('--output',required=True,type=Path);ap.add_argument('--enable-runtime',action='store_true');a=ap.parse_args()
    verify();out=a.output.resolve();deps=a.dependencies.resolve()
    if out.exists():raise SystemExit('Output must not exist')
    m=json.loads((ROOT/'SOURCE_BINDING.json').read_text(encoding='utf-8'))
    for r in m['files']:
        if r['disposition']=='external_dependency_not_published':
            p=deps/rel(r['path'])
            if not p.is_file()or hashlib.sha256(p.read_bytes()).hexdigest()!=r['original_sha256']:raise SystemExit('Missing dependency/hash mismatch: '+r['path'])
    out.mkdir(parents=True)
    for r in m['files']:
        p=out/rel(r['path']);p.parent.mkdir(parents=True,exist_ok=True)
        if r['disposition']=='external_dependency_not_published':shutil.copyfile(deps/r['path'],p);continue
        b=project_bytes(r)
        if r['include_changes']:
            t=b.decode('utf-8')
            for x in r['include_changes']:
                old=chr(96)+'include "'+x['target']+'"';new=chr(96)+'include "'+(out/x['target']).as_posix()+'"'
                assert old in t;t=t.replace(old,new)
            b=t.encode('utf-8')
        if a.enable_runtime and p.name=='board1080_cfg100_top.v':
            t,n=re.subn(r'(parameter\s+(?:integer\s+)?CAMERA_RUNTIME_GAMMA\s*=\s*)0',r'\g<1>1',b.decode('utf-8'))
            assert n==1;b=t.encode('utf-8')
        p.write_bytes(b)
    files=[{'path':p.relative_to(out).as_posix(),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}for p in out.rglob('*')if p.is_file()]
    (out/'PREPARATION.json').write_text(json.dumps({'source_only':True,'compile_sim_PDS_or_hardware':False,'runtime_topflag':int(a.enable_runtime),'files':files},indent=2),encoding='utf-8')
    print(json.dumps({'sources':len(files),'runtime_topflag':int(a.enable_runtime),'compile_sim_PDS_or_hardware':False}))
if __name__=='__main__':main()
