"""R3 independent pixel oracle plus cycle-exact frozen scatter16 comparison."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import re
import time

from run_fill8_rowpipe_cache_samecycle_sim import run_tool,validate
from simulation_tools import resolve_vivado_bin

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'work/hdmi-camera-fisheye-fill8r3-20261103-a'
NEW=ROOT/'rtl/experimental/ddr_neighbour_cache_scatter16_rowpipe_fill8r3.v'
OLD=ROOT/'rtl/experimental/ddr_neighbour_cache_scatter16_rowpipe.v'
BENCH=ROOT/'tests/tb_fill8r3_rowpipe_cache.sv'
PIN='ccddbc0293698184a3695744d7fca88350969ccc5f69cb1762b39eac84a0d294'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()

def run(output):
 output=Path(output).resolve()
 if output.exists()or not output.is_relative_to(BASE.resolve()):raise ValueError('fresh R3 output required')
 if sha(NEW)!=PIN or sha(OLD)!='ebf3566e39589e7c383d5cf753675c440823b19b4eabfdd9bd33b68c37561091':raise ValueError('reviewed source changed')
 output.mkdir(parents=True)
 watched={str(p.resolve()):sha(p)for p in(NEW,OLD,BENCH,Path(__file__),Path(__file__).with_name('run_fill8_rowpipe_cache_samecycle_sim.py'),Path(__file__).with_name('simulation_tools.py'))}
 value={'Schema':'hdmi-camera-fisheye-fill8r3-independent-cache-simulation-v1','Passed':False,
  'SourceSHA256':watched,'HardwareAccessed':False,'PDSAccessed':False,
  'StartedUTC':datetime.now(timezone.utc).isoformat(),'Oracle':'Independent RGB565 coordinate oracle plus frozen scatter16 all public outputs each edge, same-cycle counts and 32-bit wrap.'}
 try:
  text=OLD.read_text();text=text.replace('ddr_compact_neighbour_cache_core_scatter16_rowpipe','baseline_cache_core').replace('ddr_neighbour_cache_scatter16_rowpipe','baseline_cache')
  baseline=output/'baseline_cache.v';baseline.write_text(text,encoding='utf-8',newline='\n')
  binary=resolve_vivado_bin(ROOT.parent);deadline=time.monotonic()+180
  run_tool(binary,'xvlog.bat',['--sv',str(NEW),str(baseline),str(BENCH)],output,deadline,'compile')
  run_tool(binary,'xelab.bat',['tb_fill8_rowpipe_cache','-s','r3_tb'],output,deadline,'elaborate')
  run_tool(binary,'xsim.bat',['r3_tb','-runall','-log','simulation.log'],output,deadline,'simulate')
  value['IndependentOracleCases']=validate(output,8)
  eq={str(width):json.loads((output/f'equivalence-{width}.json').read_text())for width in(639,1920)}
  for row in eq.values():
   if row['passed']is not True or row['public_pin_comparisons']<1000 or row['count_wrap_checks']!=1:raise ValueError('public equivalence/wrap coverage absent')
  value['SameCyclePublicEquivalence']=eq;value['Passed']=True
 except BaseException as e:value['Error']=type(e).__name__+': '+str(e)
 value['InputDrift']=[p for p,h in watched.items()if sha(p)!=h]
 if value['InputDrift']:value['Passed']=False
 value['EndedUTC']=datetime.now(timezone.utc).isoformat()
 value['ArtifactsSHA256']={str(p.relative_to(output)):sha(p)for p in output.rglob('*')if p.is_file()and p.suffix in('.log','.json','.v')}
 (output/'simulation.json').write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')
 return value

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 v=run(a.output);print(json.dumps({k:v.get(k)for k in('Passed','Error','InputDrift','IndependentOracleCases','SameCyclePublicEquivalence')},indent=2));raise SystemExit(0 if v['Passed']else 1)
