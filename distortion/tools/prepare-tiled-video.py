"""Isolated 8x8 traversal, 16-line source cache and eight-row raster reorder."""
from pathlib import Path
import json,re,shutil
root=Path(__file__).resolve().parents[1]
def save(rel,text):
    p=root/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text,encoding='utf-8')
def rep(text,old,new):
    assert text.count(old)==1,(old,text.count(old));return text.replace(old,new)
engine=(root/'rtl/rotated_frame_engine.v').read_text().replace('module rotated_frame_engine','module tiled_frame_engine').replace('ddr_result_writer #','ddr_stripe_result_writer #')
engine=rep(engine,'reg [1:0] state;reg [31:0] index;reg [12:0] column,row;',
    'reg [1:0] state;reg [31:0] index,raster_tag;reg [12:0] column,row,tile_x,stripe_y;')
engine=rep(engine,'WIDTH>0 && HEIGHT>0 && WIDTH<=8192 && HEIGHT<=8192 &&',
    'WIDTH>=8 && HEIGHT>=8 && WIDTH%8==0 && HEIGHT%8==0 && WIDTH<=8192 && HEIGHT<=8192 &&')
engine=rep(engine,'.in_tag(index[23:0])','.in_tag(raster_tag[23:0])')
engine=rep(engine,'state<=IDLE;index<=0;column<=0;row<=0;', 'state<=IDLE;index<=0;column<=0;row<=0;raster_tag<=0;tile_x<=0;stripe_y<=0;')
engine=rep(engine,'else begin index<=0;column<=0;row<=0;destination<=output_base;state<=SCAN;end',
    'else begin index<=0;column<=0;row<=0;raster_tag<=0;tile_x<=0;stripe_y<=0;destination<=output_base;state<=SCAN;end')
engine=rep(engine,"if(column==WIDTH-1) begin column<=0;row<=row+1'b1;end else column<=column+1'b1;",
    '''if(column[2:0]!=7) begin column<=column+1'b1;raster_tag<=raster_tag+1'b1;end
                    else if(row[2:0]!=7) begin column<=tile_x;row<=row+1'b1;raster_tag<=raster_tag+WIDTH-7;end
                    else if(tile_x!=WIDTH-8) begin
                        tile_x<=tile_x+8;column<=tile_x+8;row<=stripe_y;raster_tag<=raster_tag-7*WIDTH+1;
                    end else begin tile_x<=0;column<=0;stripe_y<=stripe_y+8;row<=row+1'b1;raster_tag<=raster_tag+1'b1;end''')
save('rtl/experimental/tiled_frame_engine.v',engine)
cache=(root/'rtl/experimental/ddr_neighbour_cache_fast.v').read_text().replace('INDEX_BITS=3','INDEX_BITS=4').replace('Eight direct-mapped','Sixteen direct-mapped')
save('rtl/experimental/ddr_neighbour_cache_tiled.v',cache)
video=(root/'rtl/experimental/ddr_overlap_video.v').read_text().replace('module ddr_overlap_video','module ddr_tiled_video').replace('rotated_frame_engine #','tiled_frame_engine #')
save('rtl/experimental/ddr_tiled_video.v',video)
tb=(root/'tests/tb_ddr_overlap_video.sv').read_text().replace('tb_ddr_overlap','tb_ddr_tiled').replace('ddr_overlap_video','ddr_tiled_video').replace('PASS overlap DDR video:','PASS tiled DDR video:')
save('tests/tb_ddr_tiled_video.sv',tb)
work=root/'build/tiled_video_sim';work.mkdir(parents=True,exist_ok=True)
for p in (root/'build/overlap_video_sim').glob('*.mem'):shutil.copy2(p,work/p.name)
runner=(root/'tools/run-overlap-video-sim.ps1').read_text().replace('overlap_video_sim','tiled_video_sim').replace('tb_ddr_overlap','tb_ddr_tiled').replace('PASS overlap DDR video:','PASS tiled DDR video:')
runner=runner.replace("'rotated_frame_engine',",'').replace("'ddr_result_writer',",'')
runner=runner.replace("'ddr_neighbour_cache_fast'","'ddr_neighbour_cache_tiled','tiled_frame_engine','ddr_stripe_result_writer'").replace("'ddr_overlap_video'","'ddr_tiled_video'")
save('tools/run-tiled-video-sim.ps1',runner)
# Use already sealed independent real-camera oracles; preserve their sources.
native=root/'build/tiled_native_sim';native.mkdir(parents=True,exist_ok=True)
for p in (root/'build/rotated_native_sim').glob('*.mem'):shutil.copy2(p,native/p.name)
shutil.copy2(root/'build/rotated_native_sim/reference.json',native/'reference.json')
tb=(root/'tests/tb_rotated_native_regression.sv').read_text().replace('tb_rotated_native_regression','tb_tiled_native_regression').replace('rotated_frame_engine #','tiled_frame_engine #').replace('PASS rotated native regression:','PASS tiled native regression:')
save('tests/tb_tiled_native_regression.sv',tb)
runner=(root/'tools/run-rotated-native-sim.ps1').read_text()
start=runner.index("& 'C:\\Users");end=runner.index('Push-Location',start);runner=runner[:start]+runner[end:]
runner=runner.replace('rotated_native_sim','tiled_native_sim').replace('tb_rotated_native_regression','tb_tiled_native_regression').replace('PASS rotated native regression:','PASS tiled native regression:')
runner=runner.replace(",'ddr_result_writer','rotated_frame_engine'",'')
runner=runner.replace("$files+=Join-Path $root 'rtl\\experimental\\ddr_neighbour_cache_fast.v'", "$files+=@('ddr_neighbour_cache_tiled','tiled_frame_engine','ddr_stripe_result_writer') | ForEach-Object {Join-Path $root ('rtl\\experimental\\'+$_+'.v')}")
save('tools/run-tiled-native-sim.ps1',runner)
target='corrected_tiled'
save(f'board/{target}.v',(root/'board/corrected_overlap.v').read_text().replace('corrected_overlap',target).replace('ddr_overlap_video','ddr_tiled_video'))
tcl=(root/'board/build-corrected_overlap.tcl').read_text().replace('corrected_overlap',target).replace('/ddr_overlap_video.v}','/ddr_tiled_video.v}').replace('/ddr_neighbour_cache_fast.v}','/ddr_neighbour_cache_tiled.v}')
tcl=tcl.replace('/rtl/rotated_frame_engine.v}','/rtl/experimental/tiled_frame_engine.v}').replace('/rtl/ddr_result_writer.v}','/rtl/experimental/ddr_stripe_result_writer.v}')
save(f'board/build-{target}.tcl',tcl)
for suffix in ('.fdc','-pins.json'):shutil.copy2(root/'board'/('corrected_overlap'+suffix),root/'board'/(target+suffix))
save(f'board/program-{target}.tcl',(root/'board/program-corrected_overlap.tcl').read_text().replace('corrected_overlap',target))
sources=re.findall(r'^add_design \{([^}]+)\}',tcl,re.M)
sources += [str(root/'board'/f'{target}.fdc'),str(root/'board'/f'build-{target}.tcl')]
sources += [str(root/p) for p in ('board/calibration-trial.vh','board/ov5640_commands.vh','board/ms7210_commands.vh','rtl/video_crc32.vh','board/rotation-domain.vh','rtl/cordic-constants.vh')]
save(f'board/{target}-sources.json',json.dumps([str(Path(s).relative_to(root)) for s in sources],indent=2)+'\n')
for name in ('build-pds.ps1','program-heartbeat.ps1','read-telemetry.ps1'):
    p=root/'tools'/name;text=p.read_text(encoding='utf-8-sig')
    text=re.sub(r"(?:@|ValidateSet)\(([^)\n]*'corrected_overlap'[^)\n]*)\)",lambda m:m[0] if "'corrected_tiled'" in m[0] else m[0][:-1]+",'corrected_tiled')",text)
    p.write_text(text,encoding='utf-8-sig')
print('Prepared isolated tile traversal, stripe reorder, larger cache and two integration regressions.')
