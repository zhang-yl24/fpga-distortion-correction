"""Mixed eight/sixteen-beat camera/remap/HDMI simulation; no board target."""
from pathlib import Path
import hashlib
import json
import shutil

root = Path(__file__).resolve().parents[1]
video = (root / 'rtl/experimental/ddr_adaptive_video.v').read_text()
video = video.replace('ddr_adaptive_video', 'ddr_paired_video').replace('adaptive_tiled_frame_engine', 'paired_cache_frame_engine')
video_path = root / 'rtl/experimental/ddr_paired_video.v'
video_path.write_text(video)
tb = (root / 'tests/tb_ddr_adaptive_video.sv').read_text()
tb = tb.replace('ddr_adaptive', 'ddr_paired').replace('PASS adaptive DDR video', 'PASS paired DDR video')
tb = tb.replace('integer wbase=0,rbase=0,wi=0,ri=0,cycle=0,mode=0;', 'integer wbase=0,rbase=0,wi=0,ri=0,read_beats=16,cycle=0,mode=0;')
tb = tb.replace('rlast=rvalid && ri==15;', 'rlast=rvalid && ri==read_beats-1;')
tb = tb.replace('rbase=araddr/8;ri=0;reading=1;', 'rbase=araddr/8;ri=0;reading=1;read_beats=arlen+1;')
tb = tb.replace('if(arlen!=15 || araddr%128 || !(', 'if(((araddr<1024) ? (arlen!=7 || araddr%64) : (arlen!=15 || araddr%128)) || !(')
tb = tb.replace('if(ri==15) reading=0;', 'if(ri==read_beats-1) reading=0;')
assert 'read_beats=arlen+1' in tb and 'arlen!=7' in tb
(root / 'tests/tb_ddr_paired_video.sv').write_text(tb)
runner = (root / 'tools/run-adaptive-video-sim.ps1').read_text()
runner = runner.replace('adaptive_video_sim', 'paired_cache_video_sim').replace('tb_ddr_adaptive_video', 'tb_ddr_paired_video')
runner = runner.replace("'ddr_adaptive_cache'", "'ddr_paired_cache'").replace("'adaptive_tiled_frame_engine'", "'paired_cache_frame_engine'")
runner = runner.replace("'ddr_adaptive_video'", "'ddr_paired_video'").replace('PASS adaptive DDR video', 'PASS paired DDR video')
(root / 'tools/run-paired-cache-video-sim.ps1').write_text(runner, encoding='utf-8-sig')
work = root / 'build/paired_cache_video_sim'
work.mkdir(exist_ok=True)
for p in (root / 'build/adaptive_video_sim').glob('*.mem'):
    shutil.copy2(p, work / p.name)
snapshot = work / 'source-snapshot'
snapshot.mkdir(exist_ok=True)
paths = [video_path, root / 'rtl/experimental/ddr_paired_cache.v', root / 'rtl/experimental/paired_cache_frame_engine.v', root / 'tests/tb_ddr_paired_video.sv']
hashes = {}
for p in paths:
    shutil.copy2(p, snapshot / p.name)
    hashes[p.name] = hashlib.sha256(p.read_bytes()).hexdigest()
(snapshot / 'files-sha256.json').write_text(json.dumps(hashes, indent=2) + '\n')
print('Prepared mixed 8-beat source-cache and 16-beat video/write arbitration test; current board sources unchanged.')
