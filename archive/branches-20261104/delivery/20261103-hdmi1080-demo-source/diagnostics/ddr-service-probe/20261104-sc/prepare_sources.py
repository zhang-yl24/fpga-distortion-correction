# Stage the seven project RTL sources only. Never compile, simulate or open hardware.
from pathlib import Path
import argparse,json,hashlib
from verify_delivery import ROOT,read,verify,source_bytes
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--output',required=True,type=Path);a=ap.parse_args();verify();out=a.output.resolve()
 if out.exists():raise SystemExit('Output must not exist')
 out.mkdir(parents=True);files=[]
 for row in read(ROOT/'SOURCE_BINDING.json')['projects']:
  rel=Path(row['path']);assert not rel.is_absolute()and '..'not in rel.parts
  p=out/rel;p.parent.mkdir(parents=True,exist_ok=True);b=source_bytes(row);p.write_bytes(b);files.append({'path':rel.as_posix(),'sha256':hashlib.sha256(b).hexdigest()})
 (out/'PREPARATION.json').write_text(json.dumps({'source_only':True,'vendor_dependencies_included':False,'compile_sim_EDA_hardware':False,'files':files},indent=2),encoding='utf-8')
 print(json.dumps({'project_RTL_sources':len(files),'compile_sim_EDA_hardware':False}))
if __name__=='__main__':main()
