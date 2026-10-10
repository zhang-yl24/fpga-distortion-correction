"""Prepare isolated replicated hit pipeline; no active board sources touched."""
from pathlib import Path
import shutil
root=Path(__file__).resolve().parents[1]
serial=root/'rtl/experimental/ddr_pipeline_serial_cache.v'
serial.write_text((root/'rtl/experimental/ddr_paired_cache.v').read_text().replace(
    'module ddr_neighbour_cache #(', 'module ddr_serial_neighbour_cache #('))
engine=root/'rtl/experimental/pipeline_hit_frame_engine.v'
engine.write_text((root/'rtl/experimental/paired_cache_frame_engine.v').read_text().replace(
    'paired_cache_frame_engine','pipeline_hit_frame_engine'))
for kind in ('native','query','video'):
    source=root/f'build/paired_cache_{kind}_sim'
    destination=root/f'build/pipeline_hit_{kind}_sim'
    destination.mkdir(exist_ok=True)
    for p in source.glob('*.mem'):shutil.copy2(p,destination/p.name)
    for name in ('counts.vh','reference.json'):
        if (source/name).exists():shutil.copy2(source/name,destination/name)
    old_tb={'native':'tb_paired_cache_native_regression.sv',
            'query':'tb_paired_cache_query.sv','video':'tb_ddr_paired_video.sv'}[kind]
    new_tb=old_tb.replace('paired_cache','pipeline_hit').replace('ddr_paired','ddr_pipeline_hit')
    tb=(root/'tests'/old_tb).read_text().replace('paired_cache','pipeline_hit').replace('ddr_paired','ddr_pipeline_hit')
    tb=tb.replace('paired cache','pipeline hit').replace('paired DDR','pipeline hit DDR')
    tb=tb.replace('dut.sampler.cache.state','dut.sampler.cache.backend.state')
    (root/'tests'/new_tb).write_text(tb)
    runner=(root/f'tools/run-paired-cache-{kind}-sim.ps1').read_text(encoding='utf-8-sig')
    runner=runner.replace('paired_cache','pipeline_hit').replace('ddr_paired','ddr_pipeline_hit')
    runner=runner.replace('paired cache','pipeline hit').replace('paired DDR','pipeline hit DDR')
    runner=runner.replace("'ddr_pipeline_hit'", "'ddr_pipeline_hit_cache','ddr_pipeline_serial_cache'")
    runner=runner.replace("$files+=Join-Path $root 'rtl\\experimental\\ddr_pipeline_hit.v'", "$files+=@('ddr_pipeline_hit_cache','ddr_pipeline_serial_cache') | ForEach-Object {Join-Path $root ('rtl\\experimental\\'+$_+'.v')}")
    (root/f'tools/run-pipeline-hit-{kind}-sim.ps1').write_text(runner,encoding='utf-8-sig')
video=(root/'rtl/experimental/ddr_paired_video.v').read_text().replace('ddr_paired_video','ddr_pipeline_hit_video').replace('paired_cache_frame_engine','pipeline_hit_frame_engine')
(root/'rtl/experimental/ddr_pipeline_hit_video.v').write_text(video)
print('Prepared pipeline-hit native/query/video tests; board targets unchanged.')
