from pathlib import Path
import json,subprocess,os,re,time,hashlib
ROOT=Path(__file__).resolve().parent;work=ROOT/'guard-b';work.mkdir(exist_ok=False)
tmp=work/'temp';tmp.mkdir();env=dict(os.environ,TEMP=str(tmp),TMP=str(tmp))
files=[ROOT/'sources/ddr_read_return_register.v',ROOT/'sources/ddr_read_arbiter.v',ROOT/'tests/tb_readstage_guard.sv']
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
report=dict(passed=False,hardware_accessed=False,source_sha256={str(p):sha(p) for p in files},commands=[])
try:
 for tool,args in [('xvlog.bat',['--sv',*[str(p) for p in files]]),('xelab.bat',['tb_readstage_guard','-s','read_test']),('xsim.bat',['read_test','-runall'])]:
  cmd=[str(Path('D:/Vicado/Vivado/2017.4/bin')/tool),*args];start=time.monotonic()
  r=subprocess.run(cmd,cwd=work,env=env,capture_output=True,text=True,errors='replace',timeout=180);t=r.stdout+r.stderr
  log=work/(tool+'.log');log.write_text(t,encoding='utf-8');report['commands'].append(dict(argv=cmd,returncode=r.returncode,seconds=time.monotonic()-start,log_sha256=sha(log)))
  if r.returncode or re.search(r'(?im)^\s*(?:fatal|error)(?:\s|:|\[)',t):raise RuntimeError(t[-3000:])
 if 'PASS READSTAGE GUARD' not in t:raise RuntimeError('PASS marker absent')
 report['passed']=True;report['pass_lines']=[s for s in t.splitlines() if s.startswith('PASS')]
finally:(work/'results.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps(report,indent=2))
