"""Verify and relocate the candidate's compiled source closure. Does not run EDA."""
import argparse,hashlib,json
from pathlib import Path
HERE=Path(__file__).resolve().parent
def sha(data):return hashlib.sha256(data).hexdigest()
def prepare(output):
 output=Path(output).resolve()
 if output.exists():raise ValueError('select a fresh build directory')
 if any(c in output.as_posix() for c in '{}\r\n\x00'):raise ValueError('invalid Tcl path')
 manifest=json.loads((HERE/'source-manifest.json').read_text())
 files={}
 for name,digest in manifest['files'].items():
  path=Path(name)
  if path.is_absolute() or '..' in path.parts:raise ValueError('invalid manifest path')
  data=(HERE/path).read_bytes()
  if sha(data)!=digest:raise ValueError('hash mismatch: '+name)
  files[name]=data
 prefix=(output/'compiled').as_posix().encode()
 output.mkdir(parents=True)
 prepared={}
 for name,data in files.items():
  if not name.startswith('source/'):continue
  rel=name.removeprefix('source/')
  destination=output/'compiled'/rel
  if len(str(destination))>=260:raise ValueError('use a shorter build path')
  destination.parent.mkdir(parents=True,exist_ok=True)
  data=data.replace(b'@COMPILED@',prefix)
  destination.write_bytes(data);prepared[rel]=sha(data)
 tcl=files['build.tcl.template'].replace(b'@COMPILED@',prefix).replace(b'@BUILD@',output.as_posix().encode())
 (output/'implement.tcl').write_bytes(tcl)
 receipt={'source_manifest_sha256':sha((HERE/'source-manifest.json').read_bytes()),'prepared_files':prepared,'implementation_tcl_sha256':sha(tcl),'eda_executed':False,'hardware_tested':False}
 (output/'prepared-inputs.json').write_text(json.dumps(receipt,indent=2)+'\n')
 print(json.dumps({'prepared':True,'sources':len(prepared),'script':str(output/'implement.tcl')}))
if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True);args=parser.parse_args();prepare(args.output)
