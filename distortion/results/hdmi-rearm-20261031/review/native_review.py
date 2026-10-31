"""Isolated native review of the completed trained diagnostic; no hardware."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,importlib.util,json,re,shutil,subprocess,sys,time
ROOT=Path(r'D:\GravityLRT\thu\semester_4.5\FPGAchina\fpga-distortion-correction\distortion')
BASE=Path(__file__).resolve().parent
SOURCE=ROOT/'build/hdmi-uart-diagnostic/trained-pds-rearm-1031-a'
TOP='hdmi_uart_rearm_diag'
EXE=Path('D:/pango/PDS_2023.2/bin/pds_shell.exe')
sys.path.insert(0,str(ROOT/'tools'))
import audit_ddr_final_timing as timing
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(path,value):
 with Path(path).open('x',encoding='utf-8',newline='\n') as f:json.dump(value,f,indent=2);f.write('\n')
def load(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def lit(path):return '{'+Path(path).resolve().as_posix()+'}'
def bound_inputs():
 p=load(SOURCE/'build-plan.json');e=load(SOURCE/'execution.json')
 assert e['ReturnCode']==0 and e['Passed'] is True and e['SourceDrift']==[] and e['PlanUnchanged'] is True
 assert p['Target']==TOP and e['Target']==TOP and len(p['Pins'])==46 and len(p['InputSHA256'])==19
 assert len(p['FrozenInputSHA256'])==p['FrozenSourceCount']==12
 assert e['PlanSHA256']==sha(SOURCE/'build-plan.json')
 for name,wanted in p['InputSHA256'].items():assert sha(ROOT/name)==wanted,name
 for name,wanted in p['FrozenInputSHA256'].items():assert sha(SOURCE/name)==wanted,name
 assert sha(SOURCE/'build.tcl')==p['TclSHA256']
 assert sha(SOURCE/'hdmi_uart_diag.fdc')==p['FDCSHA256']
 paths=[SOURCE/'build-plan.json',SOURCE/'execution.json',SOURCE/'build.tcl',SOURCE/'hdmi_uart_diag.fdc',SOURCE/f'place_route/{TOP}_pnr.adf',SOURCE/f'place_route/{TOP}_route.netlist',Path(__file__),EXE]
 return p,{str(path):sha(path) for path in paths}|{str(ROOT/name):wanted for name,wanted in p['InputSHA256'].items()}|{str(SOURCE/name):wanted for name,wanted in p['FrozenInputSHA256'].items()}
def run(script,work,stem,marker):
 command=[str(EXE),'-file',str(script),'-work_dir',str(work),'-project_name',TOP]
 inputs={str(script):sha(script),str(work/'input.adf'):sha(work/'input.adf')}
 start=time.monotonic();started=datetime.now(timezone.utc).isoformat()
 with (work/(stem+'-stdout.log')).open('xb') as out,(work/(stem+'-stderr.log')).open('xb') as err:
  proc=subprocess.Popen(command,cwd=work,stdout=out,stderr=err,creationflags=subprocess.CREATE_NO_WINDOW)
  try:code=proc.wait(timeout=240)
  except subprocess.TimeoutExpired:
   proc.terminate();code=proc.wait(timeout=15);raise
 text=(work/(stem+'-stdout.log')).read_text(encoding='utf-8',errors='replace')
 result=dict(Command=command,OwnedPID=proc.pid,ReturnCode=code,StartedUTC=started,ElapsedSeconds=round(time.monotonic()-start,3),HardwareAccessed=False,BitstreamRequested=False,MarkerFound=marker in text,ActualStartedStages=re.findall(r'Process "([^"]+)" started\.',text),InputSHA256=inputs,InputDrift=[name for name,wanted in inputs.items() if sha(name)!=wanted],LogSHA256={name:sha(work/name) for name in (stem+'-stdout.log',stem+'-stderr.log')})
 write(work/(stem+'-execution.json'),result)
 assert code==0 and marker in text and not re.search(r'(?im)^\s*(?:E:|F:|ERROR\b|FATAL\b)',text),result
 return result
def mapping():
 spec=importlib.util.spec_from_file_location('mapped',ROOT/'results/hdmi-input-observer-20261030/audit-scripts/verify_mapping.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 m.MODULE_PREFIX={'hdmi1080_input_status_interval_trained':'input_status/','dvp_mode_admission_monitor_activity_cdc':'input_status/geometry/'}
 result=m.review(SOURCE)
 write(BASE/'mapping-review.json',result)
 assert result['independent_plain_registers_verified']
 with (SOURCE/f'report_timing/{TOP}.rtr').open(encoding='utf-8-sig') as f:tables,clocks=timing.parse_summaries(f)
 timing_summary={c:{k:dict(FailingChecks=sum(v['FailingChecks'] for v in tables[(c,k)].values()),WorstSlackNS=min(v['WorstSlackNS'] for v in tables[(c,k)].values())) for k in timing.KINDS} for c in ('slow','fast')}
 write(BASE/'unscoped-timing-summary.json',timing_summary)
 print(json.dumps({'Mapping':result['route_mapping_counts'],'Warnings':len(result['pap_async_reg_rejection_warnings']),'Timing':timing_summary}))
 return result
def export():
 plan,inputs=bound_inputs();mapping()
 work=BASE/'functional-export';work.mkdir()
 sourceadf=SOURCE/f'place_route/{TOP}_pnr.adf'
 shutil.copyfile(sourceadf,work/'input.adf');shutil.copyfile(SOURCE/'hdmi_uart_diag.fdc',work/'context.fdc')
 text=(SOURCE/'build.tcl').read_text(encoding='utf-8')
 for raw in re.findall(r'(?m)^add_design \{([^}]+)\}$',text):
  path=Path(raw);relative=path.relative_to(SOURCE/'frozen-inputs');dest=work/'sources'/relative;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,dest);text=text.replace(lit(path),lit(dest))
 text=text.replace(lit(SOURCE/'hdmi_uart_diag.fdc'),lit(work/'context.fdc'))
 index=text.index('report_timing -force_to_run ')
 text=text[:index]+'report_timing -force_to_run -input_db_file '+lit(work/'input.adf')+' -delay_type min_max -max_path 5\n'
 text+='if {[info script] ne {}} {\n gen_netlist -force_to_run -input_db_file '+lit(work/'input.adf')+' -func_sim_only\n puts {TRAINED_FUNCTIONAL_EXPORT_COMPLETE}\n flush stdout\n}\n'
 (work/'export.tcl').write_text(text,encoding='utf-8',newline='\n')
 write(work/'export-plan.json',dict(InputSHA256=inputs,SourceADFSHA256=sha(sourceadf),SourceADF=str(sourceadf),CopiedInputSHA256={str(p):sha(p) for p in work.rglob('*') if p.is_file()}))
 e=run(work/'export.tcl',work,'native','TRAINED_FUNCTIONAL_EXPORT_COMPLETE')
 assert e['ActualStartedStages']==['Report Timing','Generate Netlist']
 assert sha(sourceadf)==sha(work/'input.adf')
 assert not [name for name,wanted in inputs.items() if sha(name)!=wanted]
 print(json.dumps(e))
if __name__=='__main__':
 export()
