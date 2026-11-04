"""Bounded actual-engine FIFO interface regression; stub core/writer, no EDA."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,re,sys,time
BASE=Path(__file__).resolve().parent
REPO=BASE.parents[2]
sys.path.insert(0,str(REPO/'distortion/tools'))
from run_fill8_rowpipe_cache_sim import run_tool
from simulation_tools import resolve_vivado_bin
import make_engine_fifo_a as generator
SOURCE=BASE/'rtl/hdmi_camera_fisheye_engine_index10_fifo_a.v'
BENCH=BASE/'tests/tb_engine_fifo_a.sv'
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def run():
 output=BASE/'unit-a';assert not output.exists()
 assert SOURCE.read_bytes()==generator.derive()
 output.mkdir()
 helpers=[Path(__file__).resolve(),Path(generator.__file__).resolve(),REPO/'distortion/tools/run_fill8_rowpipe_cache_sim.py',REPO/'distortion/tools/simulation_tools.py']
 watched={str(p.resolve()):sha(p) for p in [SOURCE,BENCH,generator.SOURCE,*helpers]}
 value=dict(Schema='tile8-assoc2-engine-twoentry-fifo-simulation-v1',Passed=False,SourceSHA256=watched,StartedUTC=datetime.now(timezone.utc).isoformat(),
            PDSAccessed=False,HardwareAccessed=False,FullFrameSimulated=False,ProductionEngineExecuted=True,CoreAndWriterAreInterfaceStubs=True,
            RTLVariablesChanged='Only INDEX10 engine one-entry elastic stage to two-entry registered-occupancy whole-pixel queue; cache unchanged.')
 start=time.monotonic()
 try:
  binary=resolve_vivado_bin(REPO);deadline=start+180
  run_tool(binary,'xvlog.bat',['--sv',str(SOURCE),str(BENCH)],output,deadline,'compile')
  run_tool(binary,'xelab.bat',['tb_engine_fifo_a','-s','engine_fifo_tb'],output,deadline,'elaborate')
  run_tool(binary,'xsim.bat',['engine_fifo_tb','-runall','-log','simulation.log'],output,deadline,'simulate')
  text=(output/'simulation.log').read_text(errors='replace')
  assert '$finish called' in text and not re.search(r'(?im)^\s*(?:fatal|error):',text)
  match=re.search(r'PASS ENGINE_FIFO pushes(\d+) pops(\d+) canceled(\d+) fullpop(\d+) both(\d+) masked(\d+) reset(\d+) fault(\d+) warm(\d+)/(\d+) max(\d+)',text)
  assert match
  fields=('Pushes','Pops','Canceled','FullPopNoLookahead','SimultaneousPushPop','MaskedPixels','QueuedReset','QueuedFault','WarmOutputs','WarmSpanCycles','MaximumOccupancy')
  coverage=dict(zip(fields,map(int,match.groups())))
  assert coverage['Pushes']==coverage['Pops']+coverage['Canceled'] and coverage['WarmOutputs']==64 and coverage['WarmSpanCycles']==63 and coverage['MaximumOccupancy']==2
  assert all(coverage[k]>0 for k in fields)
  value.update(Passed=True,Coverage=coverage,FinalDrainPassed=True,AdmissionReadyIndependentOfWriterReady=True,WholePixelTagMaskedRGBOrderPassed=True)
 except BaseException as error:value['Error']=type(error).__name__+': '+str(error)
 value['InputDrift']=[n for n,d in watched.items() if sha(n)!=d]
 if value['InputDrift']:value['Passed']=False
 value['ElapsedSeconds']=round(time.monotonic()-start,3)
 value['ArtifactsSHA256']={str(p.relative_to(output)):sha(p) for p in output.rglob('*') if p.is_file() and p.suffix in ('.log','.txt','.json')}
 with (output/'simulation.json').open('x',encoding='utf8') as stream:json.dump(value,stream,indent=2);stream.write('\n')
 print(json.dumps({k:value.get(k) for k in ('Passed','Error','ElapsedSeconds','Coverage','InputDrift')}))
 return value['Passed']
if __name__=='__main__':raise SystemExit(0 if run() else 1)
