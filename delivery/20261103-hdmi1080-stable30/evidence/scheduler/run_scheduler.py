from pathlib import Path
import subprocess,json,re,time,hashlib
root=Path('D:/fpga-stable/scheduler');viv=Path('D:/Vicado/Vivado/2017.4/bin')
results=[]
def run(command,work,name):
 st=time.monotonic();r=subprocess.run([str(x) for x in command],cwd=work,capture_output=True,text=True)
 (work/(name+'.log')).write_text(r.stdout+r.stderr)
 if r.returncode or 'Fatal:' in r.stdout:raise RuntimeError(str(command)+'\n'+(r.stdout+r.stderr)[-5000:])
 return r.stdout+r.stderr
for banks in (2,3):
 work=root/('sim'+str(banks));work.mkdir(exist_ok=True)
 cmd=[viv/'xvlog.bat','--sv',root/('bank-current.v' if banks==2 else 'bank-three.v'),root/'engine-stub.v',root/'tb_scheduler.sv']
 if banks==3:cmd+=['--define','THREE']
 run(cmd,work,'compile');run([viv/'xelab.bat','tb_scheduler','--snapshot','schedule','--timescale','1ns/1ps'],work,'elaborate')
 for process in (2252,2575,3000):
  for phase in (0,700,1400,2100,2800):
   name=f'p{process}-phase{phase}'
   argsfile=work/(name+'.args');argsfile.write_text(f'--runall\n--testplusarg PHASE={phase}\n--testplusarg PROCESS={process}\n')
   log=run([viv/'xsim.bat','schedule','-f',argsfile],work,name)
   m=re.search(r'SCHED_RESULT (.*)',log);assert m,log[-1000:]
   assert f'STUB_PROCESS={process}' in log,log[-1000:]
   row={k:int(v) for k,v in re.findall(r'(\w+)=(\d+)',m[1])};results.append(row);print(row,flush=True)
(root/'scheduler-results.json').write_text(json.dumps(results,indent=2)+'\n')
