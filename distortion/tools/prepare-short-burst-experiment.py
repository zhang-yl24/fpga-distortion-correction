"""Isolated eight-beat cache experiment; never modifies board build sources."""
from pathlib import Path
import hashlib,json,shutil
root=Path(__file__).resolve().parents[1]
def replace(text,old,new):
    assert old in text,old
    return text.replace(old,new)
cache=(root/'rtl/experimental/ddr_adaptive_cache.v').read_text()
cache=replace(cache,'Sixteen direct-mapped 512-byte lines','Thirty-two direct-mapped 256-byte lines')
cache=replace(cache,'unbackpressurable 16-beat','unbackpressurable 8-beat')
cache=replace(cache,'INDEX_BITS=4','INDEX_BITS=5')
cache=replace(cache,'reg [3:0] beat_index,pixel_lane,fill_beat;','reg [2:0] beat_index,fill_beat;reg [3:0] pixel_lane;')
for old,new in [('LINES*16','LINES*8'),('block_number<<7','block_number<<6'),('arlen=15','arlen=7'),('fill_beat==15','fill_beat==7'),('pixel_index[31:8]','pixel_index[31:7]'),('pixel_index[8 +: INDEX_BITS]','pixel_index[7 +: INDEX_BITS]'),('pixel_index[7:4]','pixel_index[6:4]')]:
    cache=replace(cache,old,new)
cache_path=root/'rtl/experimental/ddr_short_burst_cache.v';cache_path.write_text(cache)
engine=(root/'rtl/experimental/adaptive_tiled_frame_engine.v').read_text().replace('adaptive_tiled_frame_engine','short_burst_frame_engine')
engine=replace(engine,'.INDEX_BITS(4)','.INDEX_BITS(5)')
engine_path=root/'rtl/experimental/short_burst_frame_engine.v';engine_path.write_text(engine)
tb=(root/'tests/tb_adaptive_native_regression.sv').read_text().replace('tb_adaptive_native_regression','tb_short_burst_native_regression').replace('adaptive_tiled_frame_engine','short_burst_frame_engine').replace('PASS adaptive native regression','PASS short burst native regression')
tb=replace(tb,'arlen!=15 || araddr[6:0]!=0','arlen!=7 || araddr[5:0]!=0')
tb=replace(tb,'rleft<=16;rindex<=araddr>>3','rleft<=8;rindex<=araddr>>3')
(root/'tests/tb_short_burst_native_regression.sv').write_text(tb)
runner=(root/'tools/run-adaptive-native-sim.ps1').read_text().replace('adaptive_native_sim','short_burst_native_sim').replace('tb_adaptive_native_regression','tb_short_burst_native_regression').replace("'ddr_adaptive_cache'","'ddr_short_burst_cache'").replace("'adaptive_tiled_frame_engine'","'short_burst_frame_engine'").replace('PASS adaptive native regression','PASS short burst native regression')
(root/'tools/run-short-burst-native-sim.ps1').write_text(runner,encoding='utf-8-sig')
work=root/'build/short_burst_native_sim';work.mkdir(parents=True,exist_ok=True)
for src in (root/'build/adaptive_native_sim').glob('*.mem'):shutil.copy2(src,work/src.name)
shutil.copy2(root/'build/rotated_native_sim/reference.json',work/'reference.json')
snapshot=work/'source-snapshot';snapshot.mkdir(exist_ok=True)
files=(cache_path,engine_path,root/'rtl/experimental/ddr_adaptive_result_writer.v')
for p in files:shutil.copy2(p,snapshot/p.name)
(snapshot/'files-sha256.json').write_text(json.dumps({p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in files},indent=2))
print('Prepared isolated eight-beat, 32-line cache simulation. Existing board RTL/Tcl/constraints are unchanged; no board target or physical compatibility claim.')
