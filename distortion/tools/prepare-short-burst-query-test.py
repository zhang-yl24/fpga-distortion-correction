"""Reuse sealed independent query oracles for the isolated eight-beat cache."""
from pathlib import Path
import shutil
root=Path(__file__).resolve().parents[1]
work=root/'build/short_burst_query_sim';work.mkdir(parents=True,exist_ok=True)
for src in (root/'build/rotated_query_sim').glob('*.mem'):shutil.copy2(src,work/src.name)
for name in ('counts.vh','reference.json'):shutil.copy2(root/'build/rotated_query_sim'/name,work/name)
tb=(root/'tests/tb_rotated_ddr_remap.sv').read_text().replace('tb_rotated_ddr_remap','tb_short_burst_query').replace('build/rotated_query_sim/counts.vh','build/short_burst_query_sim/counts.vh')
tb=tb.replace('.TIMEOUT_BITS(10),.MAX_RADIUS_Q22','.INDEX_BITS(5),.TIMEOUT_BITS(10),.MAX_RADIUS_Q22')
tb=tb.replace('arlen!=15 || araddr[6:0]!=0','arlen!=7 || araddr[5:0]!=0').replace('beat==15','beat==7').replace('sixteen unbackpressurable','eight unbackpressurable').replace('PASS composed rotation','PASS short burst composed rotation')
(root/'tests/tb_short_burst_query.sv').write_text(tb)
runner=(root/'tools/run-rotated-query-sim.ps1').read_text().replace('rotated_query_sim','short_burst_query_sim').replace('tb_rotated_ddr_remap','tb_short_burst_query').replace('ddr_neighbour_cache_fast.v','ddr_short_burst_cache.v').replace('PASS composed rotation','PASS short burst composed rotation')
start=runner.index("& 'C:\\Users\\22955\\AppData")
end=runner.index('Push-Location $work',start)
runner=runner[:start]+runner[end:]
(root/'tools/run-short-burst-query-sim.ps1').write_text(runner,encoding='utf-8-sig')
print('Prepared independent neighbor/RGB and eight-beat protocol-fault regression without modifying existing test sources.')
