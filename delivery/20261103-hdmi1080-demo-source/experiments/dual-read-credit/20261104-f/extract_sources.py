# Select only the already reviewed outer branch into ordinary files; never run HDL or hardware.
from pathlib import Path
import argparse,json,hashlib
from verify_delivery import ROOT,read,verify,extract_outer,legacy_reference
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--output',required=True,type=Path);ap.add_argument('--mode',choices=['legacy','experimental'],default='legacy');a=ap.parse_args();verify();out=a.output.resolve()
 if out.exists():raise SystemExit('Output must not exist')
 out.mkdir(parents=True);files=[]
 for row in read(ROOT/'SOURCE_BINDING.json')['rows']:
  on,off=extract_outer((ROOT/row['package_ref']).read_bytes());b=on if a.mode=='experimental'else off[:-1]
  expected=row['experimental_body_sha256']if a.mode=='experimental'else row['legacy_baseline_sha256'];assert hashlib.sha256(b).hexdigest()==expected
  rel=Path(row['output_path']);assert not rel.is_absolute()and '..'not in rel.parts
  p=out/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b);files.append({'path':rel.as_posix(),'sha256':expected})
 (out/'PREPARATION.json').write_text(json.dumps({'mode':a.mode,'source_only':True,'compile_sim_EDA_hardware':False,'files':files},indent=2),encoding='utf-8')
 print(json.dumps({'mode':a.mode,'module_sources':len(files),'compile_sim_EDA_hardware':False}))
if __name__=='__main__':main()
