"""Independent final-commit collision bench on root's immutable lab candidate."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,sys,time
HERE=Path(__file__).resolve().parent
REPO=HERE.parents[2]
sys.path.insert(0,str(REPO/'distortion/tools'))
from run_fill8_rowpipe_cache_sim import run_tool
from simulation_tools import resolve_vivado_bin
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def main():
 source=HERE/'combined-cache-probe-c.v';bench=REPO/'distortion/tests/tb_directfill_commit_collision_peer.sv'
 if sha(source)!='2828700483c478688cddf249608456f4f1253c5091687c11accc98a833b2df6e':raise ValueError('rootlab source changed')
 if sha(bench)!='bd7736f98ec4ac8ebd24df1bf3e72dffa8ea72d09aad1e4d818be882d740f2ab':raise ValueError('independent collision oracle changed')
 work=HERE/'combined-peer-collision-a';work.mkdir(exist_ok=False)
 inputs={str(p):sha(p) for p in (source,bench,Path(__file__).resolve(),REPO/'distortion/tools/run_fill8_rowpipe_cache_sim.py',REPO/'distortion/tools/simulation_tools.py')}
 started=time.monotonic();result={'Schema':'combined-cache-independent-final-commit-collision-peer-v1','Passed':False,
 'ExperimentalOnly':True,'StartedUTC':datetime.now(timezone.utc).isoformat(),'InputSHA256':inputs,
 'OriginalProductionRTLModified':False,'NativeEDAExecuted':False,'HardwareAccessed':False}
 try:
  binary=resolve_vivado_bin(REPO);deadline=started+180
  run_tool(binary,'xvlog.bat',['--sv',str(source),str(bench)],work,deadline,'compile')
  run_tool(binary,'xelab.bat',['tb_directfill_commit_collision_peer','-s','combined_peer_collision'],work,deadline,'elaborate')
  run_tool(binary,'xsim.bat',['combined_peer_collision','-runall','-log','simulation.log'],work,deadline,'simulate')
  text=(work/'simulation.log').read_text(errors='replace')
  if 'PASS DIRECTFILL PEER real final-commit/fault/reset collisions' not in text:raise ValueError('missing true collision completion')
  summary=json.loads((work/'peer-commit-summary.json').read_text())
  if summary.get('Passed') is not True or summary.get('Cases')!=4 or summary.get('IndependentRAMPixelsChecked')!=864:raise ValueError('collision coverage incomplete')
  result['Summary']=summary;result['Passed']=True
 except Exception as error:result['Error']=type(error).__name__+': '+str(error)
 result['InputDrift']=[n for n,h in inputs.items() if sha(Path(n))!=h]
 result['Passed']=result['Passed'] and not result['InputDrift'];result['ElapsedSeconds']=time.monotonic()-started
 result['ArtifactsSHA256']={p.name:sha(p) for p in work.iterdir() if p.is_file() and p.suffix in ('.json','.csv','.log')}
 with (work/'simulation.json').open('x') as f:json.dump(result,f,indent=2);f.write('\n')
 print(json.dumps({'Passed':result['Passed'],'Summary':result.get('Summary'),'Error':result.get('Error'),'ElapsedSeconds':result['ElapsedSeconds']}))
 raise SystemExit(0 if result['Passed'] else 1)

if __name__=='__main__':main()
