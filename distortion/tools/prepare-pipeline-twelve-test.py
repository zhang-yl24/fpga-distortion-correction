"""Reuse sealed twelve-angle oracle inputs with the isolated hit pipeline."""
from pathlib import Path
import hashlib
import json
import shutil
root=Path(__file__).resolve().parents[1]
work=root/'build/pipeline_twelve_native_sim';work.mkdir(exist_ok=True)
for p in (root/'build/adaptive_twelve_native_sim').glob('*.mem'):shutil.copy2(p,work/p.name)
shutil.copy2(root/'build/adaptive_twelve_native_sim/reference.json',work/'reference.json')
tb=(root/'tests/tb_adaptive_twelve_native_regression.sv').read_text()
tb=tb.replace('tb_adaptive_twelve','tb_pipeline_twelve').replace('adaptive_tiled_frame_engine','pipeline_hit_frame_engine')
tb=tb.replace('arlen!=15 || araddr[6:0]!=0','arlen!=7 || araddr[5:0]!=0').replace('rleft<=16;','rleft<=8;')
tb=tb.replace('PASS adaptive native regression:','PASS pipeline twelve native regression:')
test=root/'tests/tb_pipeline_twelve_native_regression.sv';test.write_text(tb)
runner=(root/'tools/run-adaptive-twelve-native-sim.ps1').read_text(encoding='utf-8-sig')
runner=runner.replace('adaptive_twelve','pipeline_twelve').replace('adaptive-twelve','pipeline-twelve')
runner=runner.replace("'ddr_adaptive_cache','adaptive_tiled_frame_engine'", "'ddr_pipeline_hit_cache','ddr_pipeline_serial_cache','pipeline_hit_frame_engine'")
runner=runner.replace('PASS adaptive native regression:','PASS pipeline twelve native regression:')
(root/'tools/run-pipeline-twelve-native-sim.ps1').write_text(runner,encoding='utf-8-sig')
paths=[root/'rtl'/f'{n}.v' for n in ('bilinear_rgb','ddr_remap_sample','mul32_pipe','pixel_inverse_rotation','bounded_brown_inverse_mapper','rotated_remap_core')]
paths+=[root/'rtl/experimental'/f'{n}.v' for n in ('ddr_pipeline_hit_cache','ddr_pipeline_serial_cache','pipeline_hit_frame_engine','ddr_adaptive_result_writer')]
paths+=[root/'rtl/video_crc32.vh',root/'board/calibration-trial.vh',root/'board/rotation-domain.vh',test,work/'reference.json']+list(work.glob('*.mem'))
hashes={};snapshot=work/'source-snapshot'
for p in paths:
    rel=str(p.relative_to(root));destination=snapshot/rel;destination.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(p,destination);hashes[rel]=hashlib.sha256(p.read_bytes()).hexdigest()
(snapshot/'files-sha256.json').write_text(json.dumps(hashes,indent=2)+'\n')
recorder=(root/'tools/record-twelve-angle-regression.py').read_text()
recorder=recorder.replace('adaptive_twelve','pipeline_twelve').replace('PASS adaptive native regression:','PASS pipeline twelve native regression:').replace('adaptive-twelve-native-check.json','pipeline-twelve-native-check.json')
(root/'tools/record-pipeline-twelve-regression.py').write_text(recorder)
print('Prepared twelve-angle native hit-pipeline test from unchanged sealed oracles.')
