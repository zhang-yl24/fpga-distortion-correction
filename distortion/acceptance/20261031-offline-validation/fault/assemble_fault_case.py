"""Recreate an exact fault-test input using immutable base and new bytes only."""
from pathlib import Path
import argparse, hashlib, json, shutil

def main():
 p=argparse.ArgumentParser();p.add_argument('--repo-root',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
 here=Path(__file__).resolve().parent;spec=json.loads((here/'ASSEMBLY.json').read_text(encoding='utf-8'))
 assert not a.out.exists(), 'Output must be a new isolated directory.'
 jobs=[]
 for f in spec['reuse']:
  src=a.repo_root/f['base_repo_path'];jobs.append((src,f))
 for f in spec['new']:jobs.append((here/spec['new_root']/f['path'],f))
 for src,f in jobs:
  assert src.is_file() and src.stat().st_size==f['bytes'],str(src)
  assert hashlib.sha256(src.read_bytes()).hexdigest()==f['sha256'],str(src)
  target=a.out/f['path'];assert not Path(f['path']).is_absolute() and '..' not in Path(f['path']).parts
  target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,target)
 shutil.copyfile(here/'ORIGINAL_INPUT_MANIFEST.json',a.out/'manifest.json')
 assert len(jobs)==spec['output_file_count']==69
 print(json.dumps({'status':'PASS_EXACT_ASSEMBLY','files':len(jobs),'base_reused':len(spec['reuse']),'new':len(spec['new']),'HDL_run':False}))

if __name__=='__main__':main()
