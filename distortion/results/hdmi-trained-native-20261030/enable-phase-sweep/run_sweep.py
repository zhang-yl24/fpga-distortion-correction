"""Run original trained observer/CDC monitor at eight live-raster reset phases."""
from datetime import datetime,timezone
from pathlib import Path
import hashlib,json,re,sys,time
ROOT=Path('D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion')
WORK=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'tools'))
from simulation_tools import resolve_vivado_bin
from run_gamma_pipeline_d5_sim import tool
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
sources=[ROOT/'rtl/experimental/hdmi1080_input_status_trained.v',ROOT/'rtl/experimental/dvp_mode_admission_monitor_cdc.v',WORK/'tb_trained_enable_phase.sv']
bound={str(p):sha(p) for p in [*sources,Path(__file__),ROOT/'tools/simulation_tools.py',ROOT/'tools/run_gamma_pipeline_d5_sim.py']}
report=dict(Schema='trained-enable-reset-phase-sweep-v1',Passed=False,StartedUTC=datetime.now(timezone.utc).isoformat(),InputSHA256=bound,Commands=[],HardwareAccessed=False,PDSAccessed=False,Limits='Eight digital live-raster reset phases at small geometry. This can reject a deterministic monotonic-enable epoch bug, not prove board waveform, analog reset/CDC or physical VS presence.')
start=time.monotonic()
try:
  tools=resolve_vivado_bin(ROOT.parent)
  for name,args,stage in [('xvlog.bat',['--sv',*[str(p) for p in sources]],'compile'),('xelab.bat',['tb_trained_enable_phase','-s','trained_phase_tb'],'elaborate'),('xsim.bat',['trained_phase_tb','-runall','-log','simulation.log'],'simulate')]:
    item=dict(Stage=stage,Argv=[str(tools/name),*args],ReturnCode=None);report['Commands'].append(item)
    tool(tools,name,args,WORK,start+180,stage);item['ReturnCode']=0
  log=(WORK/'simulation.log').read_text(encoding='utf-8',errors='replace')
  lines=re.findall(r'(?m)^TRAINED_ENABLE_PHASE_PASS .+$',log)
  if len(lines)!=8 or 'TRAINED_ENABLE_PHASE_SWEEP_PASS' not in log or re.search(r'(?im)^\s*(fatal|error):',log):raise ValueError('sweep assertions did not pass')
  report.update(Passed=True,Cases=lines,Summary=re.findall(r'(?m)^TRAINED_ENABLE_PHASE_SUMMARY .+$',log))
except Exception as error:report['Error']=type(error).__name__+': '+str(error)
finally:
  report['InputDrift']=[name for name,wanted in bound.items() if sha(name)!=wanted]
  report['Passed']=report['Passed'] and not report['InputDrift']
  report['EndedUTC']=datetime.now(timezone.utc).isoformat();report['ElapsedSeconds']=round(time.monotonic()-start,3)
  report['EvidenceSHA256']={p.name:sha(p) for p in WORK.iterdir() if p.is_file() and p.suffix in ('.py','.sv','.log')}
  with (WORK/'simulation-result.json').open('x',encoding='utf-8') as stream:json.dump(report,stream,indent=2)
print(json.dumps({key:report.get(key) for key in ('Passed','Error','InputDrift','ElapsedSeconds')}))
raise SystemExit(0 if report['Passed'] else 1)
