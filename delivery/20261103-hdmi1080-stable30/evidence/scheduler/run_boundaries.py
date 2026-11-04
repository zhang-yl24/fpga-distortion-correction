from pathlib import Path
import subprocess,json,re
root=Path('D:/fpga-stable/scheduler');work=root/'sim3';viv=Path('D:/Vicado/Vivado/2017.4/bin')
rows=[]
for process,outperiod,phase in [(2252,3330,1400),(3000,3330,2100),(2252,3340,1400),(3340,3333,1400),(3700,3333,1400)]:
 name=f'boundary-p{process}-out{outperiod}-phase{phase}';f=work/(name+'.args');f.write_text(f'--runall\n--testplusarg PHASE={phase}\n--testplusarg PROCESS={process}\n--testplusarg OUT_PERIOD={outperiod}\n')
 r=subprocess.run([str(viv/'xsim.bat'),'schedule','-f',str(f)],cwd=work,capture_output=True,text=True)
 (work/(name+'.log')).write_text(r.stdout+r.stderr);assert r.returncode==0 and 'Fatal:' not in r.stdout
 assert f'STUB_PROCESS={process}' in r.stdout
 m=re.search(r'SCHED_RESULT (.*)',r.stdout);assert m
 row={k:int(v) for k,v in re.findall(r'(\w+)=(\d+)',m[1])};rows.append(row);print(row,flush=True)
(root/'boundary-results.json').write_text(json.dumps(rows,indent=2)+'\n')
