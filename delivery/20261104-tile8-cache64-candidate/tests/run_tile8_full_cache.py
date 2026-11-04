import sys,time,json,re,runpy
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from run_fill8_rowpipe_cache_samecycle_sim import run_tool
HERE=Path(__file__).resolve().parent
out=HERE/'tile8-full-cache';out.mkdir(exist_ok=False)
model=runpy.run_path(str(HERE/'evaluate_tile8_cache.py'))
sx,sy,order=model['sx'],model['sy'],model['order']
with (out/'coordinates.mem').open('w') as f:
 for x,y in zip(sx.reshape(-1)[order],sy.reshape(-1)[order]):f.write(f'{int(x)&0xffffff:06x}{int(y)&0xffffff:06x}\n')
deadline=time.monotonic()+900
import os
binary=Path(os.environ['FPGA_VIVADO_BIN'])
source=HERE.parent/'source/rtl/experimental/ddr_neighbour_cache_scatter16_rowpipe_fill8r3.v'
run_tool(binary,'xvlog.bat',['--sv',str(source),str(HERE/'tb_tile8_cache_full.sv')],out,deadline,'compile')
run_tool(binary,'xelab.bat',['tb_tile8_cache_full','-s','full_tb'],out,deadline,'elaborate')
run_tool(binary,'xsim.bat',['full_tb','-runall','-log','simulation.log'],out,deadline,'simulate')
text=(out/'simulation.log').read_text()
assert 'PASS FULL BOTH' in text and '$finish called' in text
rows=[dict(zip(('index_bits','pixels','block_reads','cycles'),map(int,m))) for m in re.findall(r'PASS FULL bits=(\d+) pixels=(\d+) block_reads=(\d+) cycles=(\d+)',text)]
assert len(rows)==2
for row in rows:
 expected=next(r for r in model['results'] if r['index_bits']==row['index_bits'])
 assert row['block_reads']==expected['block_reads'] and row['pixels']==2073600
report={'passed':True,'hardware_fps_verified':False,'results':rows,'oracle':'all four RGB neighbours and fractional coordinates, every pixel; deterministic DDR and output stalls'}
(out/'results.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
