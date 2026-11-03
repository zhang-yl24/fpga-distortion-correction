"""Run registered-return and raw-ownership tests against the frozen arbiter."""
from pathlib import Path
import argparse,hashlib,json,os,re,subprocess,time
ROOT=Path(__file__).resolve().parent
CASES=[('legacy','tb_ddr_read_arbiter','tb_legacy_registered.sv','PASS DDR read arbitration'),
       ('integration','tb_ddr_readstage_integration','tb_readstage_integration.sv','PASS READSTAGE INTEGRATION'),
       ('guard','tb_readstage_guard','tb_readstage_guard.sv','PASS READSTAGE GUARD checks=11')]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);p.add_argument('--vivado-bin',type=Path,default=Path('D:/Vicado/Vivado/2017.4/bin'));a=p.parse_args()
 work=a.work.resolve();work.mkdir(parents=True,exist_ok=False);tmp=work/'temp';tmp.mkdir()
 env=dict(os.environ,TEMP=str(tmp),TMP=str(tmp));report=dict(passed=False,hardware_accessed=False,physical_implementation_accessed=False,cases=[])
 try:
  for name,top,bench,marker in CASES:
   stage=work/name;stage.mkdir();files=[ROOT/'sources/ddr_read_return_register.v',ROOT/'sources/ddr_read_arbiter.v',ROOT/'tests'/bench]
   sources={str(p.relative_to(ROOT)):sha(p) for p in files};case=dict(name=name,passed=False,source_sha256=sources,commands=[]);report['cases'].append(case)
   for tool,args in [('xvlog.bat',['--sv',*[str(p) for p in files]]),('xelab.bat',[top,'-s','read_test']),('xsim.bat',['read_test','-runall'])]:
    command=[str(a.vivado_bin/tool),*args];start=time.monotonic();r=subprocess.run(command,cwd=stage,env=env,capture_output=True,text=True,errors='replace',timeout=180)
    text=r.stdout+r.stderr;log=stage/(tool+'.log');log.write_text(text,encoding='utf-8');case['commands'].append(dict(argv=command,returncode=r.returncode,seconds=time.monotonic()-start,log_sha256=sha(log)))
    if r.returncode or re.search(r'(?im)^\s*(?:fatal|error)(?:\s|:|\[)',text):raise RuntimeError(text[-4000:])
   if marker not in text:raise RuntimeError('Expected PASS marker absent')
   if sources!={str(p.relative_to(ROOT)):sha(p) for p in files}:raise RuntimeError('Source drift')
   case['pass_lines']=[s for s in text.splitlines() if s.startswith('PASS')];case['passed']=True;print(name,'PASS',flush=True)
  report['passed']=True
 finally:(work/'results.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
 print(json.dumps(report,indent=2))
if __name__=='__main__':main()
