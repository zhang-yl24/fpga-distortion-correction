# Prepare ordinary sources only; never execute HDL, EDA or hardware.
from pathlib import Path
import argparse,json,hashlib,shutil
from verify_export import ROOT,verify
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--dependencies',required=True,type=Path);ap.add_argument('--output',required=True,type=Path);a=ap.parse_args()
    verify();dst=a.output.resolve();deps=a.dependencies.resolve()
    if dst.exists():raise SystemExit('Output must not exist')
    def relative(s):
        p=Path(s)
        if p.is_absolute()or '..'in p.parts:raise ValueError('Unsafe relative path')
        return p
    m=json.loads((ROOT/'SOURCE_BINDING.json').read_text(encoding='utf-8'))
    for r in m['dependencies']:
        p=deps/r['origin']/relative(r['path'])
        if not p.is_file()or hashlib.sha256(p.read_bytes()).hexdigest()!=r['original_sha256']:raise SystemExit('Dependency missing/hash mismatch: '+r['path'])
    dst.mkdir(parents=True);native=dst/'native'
    for r in m['exports']:
        p=dst/r['origin']/relative(r['path']);p.parent.mkdir(parents=True,exist_ok=True);b=(ROOT/r['export']).read_bytes()
        if r['transformations']:
            t=b.decode('utf-8')
            for c in r['transformations']:
                old=chr(96)+'include "'+c['target']+'"';new=chr(96)+'include "'+(native/c['target']).as_posix()+'"'
                assert old in t;t=t.replace(old,new)
            b=t.encode('utf-8')
        p.write_bytes(b)
    for r in m['dependencies']:
        p=dst/r['origin']/relative(r['path']);p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(deps/r['origin']/r['path'],p)
    (dst/'scripts').mkdir();shutil.copyfile(ROOT/'checked.tcl',dst/'scripts/checked.tcl')
    t=(ROOT/'map.tcl.template').read_text(encoding='utf-8').replace('@NATIVE@',native.as_posix()).replace('@OUT@',dst.as_posix())
    (dst/'map.tcl').write_text(t,encoding='utf-8')
    rows=[{'path':p.relative_to(dst).as_posix(),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}for p in dst.rglob('*')if p.is_file()]
    (dst/'PREPARATION.json').write_text(json.dumps({'source_only':True,'EDA_executed':False,'new_build_needs_own_signoff':True,'files':rows},indent=2),encoding='utf-8')
    print(json.dumps({'prepared':len(rows),'EDA_executed':False}))
if __name__=='__main__':main()
