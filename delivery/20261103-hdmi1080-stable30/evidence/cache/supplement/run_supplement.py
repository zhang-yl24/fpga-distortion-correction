from pathlib import Path
import hashlib,json,os,re,subprocess,time
ROOT=Path(__file__).resolve().parent
work=ROOT/'run-a';work.mkdir(exist_ok=False)
tmp=work/'temp';tmp.mkdir();env=dict(os.environ,TEMP=str(tmp),TMP=str(tmp))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
report=dict(passed=False,hardware_accessed=False,cases=[])
try:
 for name,top,bench,marker in [('signed','tb_cache_directed',ROOT/'tb_cache_signed_lockstep.sv','PASS SIGNED FIFO PREDECODE edge_queries=64'),('priority','tb_cache_priority',ROOT.parent/'tests/tb_cache_priority_lockstep.sv','PASS CACHE PRIORITY checks=7')]:
  directory=work/name;directory.mkdir()
  files=[ROOT.parent/'sources/experiment.v',ROOT.parent/'sources/reference.v',bench]
  case=dict(name=name,passed=False,source_sha256={str(p):sha(p) for p in files},commands=[]);report['cases'].append(case)
  for tool,args in [('xvlog.bat',['--sv','-d','PACKED32',*[str(p) for p in files]]),('xelab.bat',[top,'-s','cache_test']),('xsim.bat',['cache_test','-runall'])]:
   command=[str(Path('D:/Vicado/Vivado/2017.4/bin')/tool),*args];start=time.monotonic()
   proc=subprocess.run(command,cwd=directory,env=env,capture_output=True,text=True,errors='replace',timeout=180)
   text=proc.stdout+proc.stderr;log=directory/(tool+'.log');log.write_text(text,encoding='utf-8')
   case['commands'].append(dict(argv=command,returncode=proc.returncode,seconds=time.monotonic()-start,log_sha256=sha(log)))
   if proc.returncode or re.search(r'(?im)^\s*(?:fatal|error)(?:\s|:|\[)',text):raise RuntimeError(text[-4000:])
  if marker not in text or 'LOCKSTEP cycles=' not in text:raise RuntimeError('Completion missing')
  case['pass_lines']=[s for s in text.splitlines() if s.startswith(('PASS','LOCKSTEP'))];case['passed']=True
  print(name,'PASS',flush=True)
 report['passed']=True
finally:(work/'results.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps(report,indent=2))
