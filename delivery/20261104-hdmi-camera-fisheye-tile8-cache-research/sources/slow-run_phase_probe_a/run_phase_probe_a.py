"""New bounded XSim scheduling probe; frozen bank/DMA RTL, stub engine/lease."""
import argparse,csv,hashlib,json,sys,time
from pathlib import Path
from datetime import datetime,timezone
HERE=Path(__file__).resolve().parent
REPO=HERE.parents[2]
ROOT=REPO/'distortion'
sys.path.insert(0,str(ROOT/'tools'))
from run_fill8_rowpipe_cache_sim import run_tool
from simulation_tools import resolve_vivado_bin

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def run(name,smoke=False):
 work=HERE/name
 if work.exists():raise ValueError('fresh output required')
 work.mkdir()
 sources=[ROOT/'rtl/video_async_fifo.v',ROOT/'rtl/experimental/hdmi1080_capture_cdc.v',
 ROOT/'rtl/experimental/hdmi1080_input_dma.v',ROOT/'rtl/experimental/hdmi_camera_fisheye_bank_tile8.v',HERE/'tb_phase_probe_a.sv']
 inputs={str(p):sha(p) for p in [*sources,Path(__file__),ROOT/'tools/run_fill8_rowpipe_cache_sim.py',ROOT/'tools/simulation_tools.py']}
 started=time.monotonic();deadline=started+1200;binary=resolve_vivado_bin(REPO)
 receipt={'Schema':'tile8-phase-probe-real-bank-dma-stub-engine-v1','Passed':False,'InputSHA256':inputs,
 'StartedUTC':datetime.now(timezone.utc).isoformat(),'TimeScaleVsBoard':1000,'RealInputCaptureDMAAndBankRTL':True,
 'EngineIsDurationStub':True,'DisplayReaderAndLeaseAreTimingModel':True,'RealDDRArbitrationOrPixelsValidated':False,
 'HDLSimulationExecuted':True,'EDAExecuted':False,'HardwareAccessed':False,'Cases':[]}
 try:
  run_tool(binary,'xvlog.bat',['--sv',*map(str,sources)],work,deadline,'compile')
  run_tool(binary,'xelab.bat',['tb_phase_probe_a','-s','phase_probe'],work,deadline,'elaborate')
  cases=[(4433,0)] if smoke else [(p,phase) for p in (5541,4433,4150,3750,3000) for phase in (0,521,1042,1563,2084,2604,3125,3646)]
  for index,(proc,phase) in enumerate(cases):
   run_tool(binary,'xsim.bat',['phase_probe','-runall','-testplusarg','PROC='+str(proc),'-testplusarg','PHASE='+str(phase),'-log','simulation.log'],work,deadline,'simulate-'+str(index))
   text=(work/'simulation.log').read_text(errors='replace')
   if 'PASS PHASE PROBE' not in text:raise ValueError('no actual complete marker')
   value=json.loads((work/'summary.json').read_text());rows=list(csv.DictReader((work/'events.csv').open()))
   if value['process_stub_cycles']!=proc or value['phase']!=phase or value['last_measured_process_cycles']!=proc+1:
    raise ValueError('actual measured engine duration/phase differs from requested stimulus')
   value['NormalizedBoardUniqueFPS']=value['unique']/16*30
   value['NormalizedProcessMS']=value['last_measured_process_cycles']*1000/125000
   value['Events']=len(rows)
   for file in ('summary.json','events.csv','simulation.log'):(work/file).rename(work/(str(index).zfill(2)+'-'+file))
   receipt['Cases'].append(value)
   print(json.dumps({'Case':index,**value}),flush=True)
  receipt['Passed']=True
 except BaseException as error:receipt['Error']=type(error).__name__+': '+str(error)
 receipt['InputDrift']=[n for n,h in inputs.items() if sha(Path(n))!=h]
 receipt['Passed']=receipt['Passed'] and not receipt['InputDrift']
 receipt['ElapsedSeconds']=time.monotonic()-started
 receipt['ArtifactsSHA256']={p.name:sha(p) for p in work.iterdir() if p.is_file() and p.suffix in ('.json','.csv','.log')}
 (work/'simulation.json').write_text(json.dumps(receipt,indent=2)+'\n')
 print(json.dumps({'Passed':receipt['Passed'],'Cases':len(receipt['Cases']),'ElapsedSeconds':receipt['ElapsedSeconds'],'Error':receipt.get('Error')}),flush=True)
 return receipt['Passed']

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--name',required=True);p.add_argument('--smoke',action='store_true');a=p.parse_args()
 if not a.name.replace('-','').isalnum():raise ValueError('safe new child name required')
 raise SystemExit(0 if run(a.name,a.smoke) else 1)
