"""Run frozen arbiter regression and a directed old/new pin comparison, CPU only."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import re
import time

from run_fill8_rowpipe_cache_samecycle_sim import run_tool
from simulation_tools import resolve_vivado_bin

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'work/hdmi-camera-fisheye-fill8r2-20261103-a'
OLD=ROOT/'rtl/ddr_read_arbiter.v'
NEW=ROOT/'rtl/experimental/ddr_read_arbiter_fill8r2.v'
BENCH=ROOT/'tests/tb_fill8r2_read_arbiter_compare.sv'
FROZEN_BENCH=ROOT/'tests/tb_ddr_read_arbiter.sv'
PIN='de0c11db399033511048ef18a90345881f8f13d2458b81ff6daa131f79393ec7'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()

def run(output):
 output=Path(output).resolve()
 if output.exists()or not output.is_relative_to(BASE.resolve()):raise ValueError('fresh isolated r2 output required')
 if sha(NEW)!=PIN:raise ValueError('reviewed r2 arbiter source changed')
 output.mkdir(parents=True)
 sources=[OLD,NEW,BENCH,FROZEN_BENCH,Path(__file__),Path(__file__).with_name('simulation_tools.py'),
  Path(__file__).with_name('run_fill8_rowpipe_cache_samecycle_sim.py')]
 watched={str(p):sha(p)for p in sources}
 value={'Schema':'hdmi-camera-fisheye-fill8r2-read-arbiter-simulation-v1','Passed':False,
  'SourceSHA256':watched,'HardwareAccessed':False,'PDSAccessed':False,
  'StartedUTC':datetime.now(timezone.utc).isoformat(),'Cases':{}}
 try:
  binary=resolve_vivado_bin(ROOT.parent);deadline=time.monotonic()+180
  for kind,source in [('frozen',OLD),('candidate',NEW),('compare',None)]:
   work=output/kind;work.mkdir();args=['--sv'];top='tb_ddr_read_arbiter'
   if kind=='compare':
    for original,module in [(OLD,'baseline_read_arbiter'),(NEW,'candidate_read_arbiter')]:
     text=original.read_text();adapted,n=re.subn(r'\bmodule ddr_read_arbiter\b','module '+module,text)
     if n!=1:raise ValueError('expected sole module adapter')
     p=work/(module+'.v');p.write_text(adapted,encoding='utf-8');args.append(str(p))
    args.append(str(BENCH));top='tb_fill8r2_read_arbiter_compare'
   else:args += [str(source),str(FROZEN_BENCH)]
   run_tool(binary,'xvlog.bat',args,work,deadline,'compile')
   run_tool(binary,'xelab.bat',[top,'-s','arbiter_tb'],work,deadline,'elaborate')
   run_tool(binary,'xsim.bat',['arbiter_tb','-runall','-log','simulation.log'],work,deadline,'simulate')
   text=(work/'simulation.log').read_text(errors='replace')
   token='PASS fill8r2 read arbiter per-cycle'if kind=='compare'else'PASS DDR read arbitration:'
   if token not in text or '$finish called'not in text or re.search(r'(?im)^\s*(?:fatal|error):',text):raise ValueError('required simulation result missing: '+kind)
   summary=json.loads((work/'comparison-summary.json').read_text())if kind=='compare'else{'Passed':True,'FrozenBenchUnchanged':True}
   if kind=='compare'and not(summary['passed']is True and summary['pin_comparisons']>40000 and summary['random_cycles']==20000 and summary['samecycle_responses']==2 and summary['fault_cases']==6 and summary['reset_cases']>100):raise ValueError('directed coverage missing')
   value['Cases'][kind]=summary
  value['Passed']=True
 except BaseException as e:value['Error']=type(e).__name__+': '+str(e)
 value['InputDrift']=[p for p,h in watched.items()if sha(p)!=h]
 if value['InputDrift']:value['Passed']=False
 value['EndedUTC']=datetime.now(timezone.utc).isoformat()
 value['ArtifactsSHA256']={str(p.relative_to(output)):sha(p)for p in output.rglob('*')if p.is_file()and p.suffix in('.json','.log','.v')}
 (output/'simulation.json').write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')
 return value

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 v=run(a.output);print(json.dumps(v,indent=2));raise SystemExit(0 if v['Passed']else 1)
