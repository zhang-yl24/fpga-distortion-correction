"""Isolated last-line commit experiment; keep proved camera/board sources intact."""
from pathlib import Path
import json,re,shutil
root=Path(__file__).resolve().parents[1]
def write(path,text):
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text,encoding='utf-8')
pack=(root/'rtl/rgb565_burst_pack.v').read_text().replace('module rgb565_burst_pack','module rgb565_burst_pack_early')
pack=pack.replace('if(column!=WIDTH || lane!=0 || row>=HEIGHT)',
    'if(column!=WIDTH || lane!=0 || row>=HEIGHT || (row==HEIGHT-1 && !output_free))')
pack=pack.replace('end else begin row<=row+1\'b1;column<=0;end',
    '''end else begin
                        row<=row+1'b1;column<=0;
                        // Exact known-height frame, final beat accepted or free.
                        // Pulse after final line end; ignore input until VSYNC.
                        if(row==HEIGHT-1) begin frame_complete<=1;active<=0;end
                    end''')
write(root/'rtl/experimental/rgb565_burst_pack_early.v',pack)
bridge=(root/'rtl/camera_live_bridge.v').read_text().replace('module camera_live_bridge','module camera_live_bridge_early').replace('rgb565_burst_pack #','rgb565_burst_pack_early #')
write(root/'rtl/experimental/camera_live_bridge_early.v',bridge)
video=(root/'rtl/ddr_rotated_video.v').read_text().replace('module ddr_rotated_video','module ddr_early_video').replace('camera_live_bridge #','camera_live_bridge_early #')
write(root/'rtl/experimental/ddr_early_video.v',video)
tb=(root/'tests/tb_rgb565_burst_pack.sv').read_text().replace('tb_rgb565_burst_pack','tb_rgb565_burst_pack_early').replace('rgb565_burst_pack #','rgb565_burst_pack_early #')
tb=tb.replace('integer beats=0,phase=0;', 'integer beats=0,phase=0,completions=0;\n    always @(posedge clk) if(rst_n && frame_complete) completions=completions+1;')
tb=tb.replace('if(!frame_complete || dropped_frames!=0)','if(completions!=1 || frame_complete || dropped_frames!=0)')
tb=tb.replace('if(!frame_complete || beats!=4 || dropped_frames!=2)','if(completions!=2 || frame_complete || beats!=4 || dropped_frames!=2)')
tb=tb.replace('PASS burst_pack ', 'PASS early burst_pack last-line commit, ')
write(root/'tests/tb_rgb565_burst_pack_early.sv',tb)
runner=(root/'tools/run-burst-pack-sim.ps1').read_text().replace('burst_pack_sim','early_pack_sim').replace("'rtl\\rgb565_burst_pack.v'","'rtl\\experimental\\rgb565_burst_pack_early.v'").replace('tb_rgb565_burst_pack','tb_rgb565_burst_pack_early')
write(root/'tools/run-early-pack-sim.ps1',runner)
tb=(root/'tests/tb_ddr_rotated_video.sv').read_text().replace('tb_ddr_rotated_video','tb_ddr_early_video').replace('ddr_rotated_video #','ddr_early_video #').replace('PASS rotated DDR video:', 'PASS early DDR video:')
# Extend camera blanking to check commit independent of following VSYNC.
tb=tb.replace('        camera_frame=camera_frame+1;', '        repeat(1200) @(negedge cam_clk);\n        camera_frame=camera_frame+1;')
write(root/'tests/tb_ddr_early_video.sv',tb)
work=root/'build/early_video_sim';work.mkdir(parents=True,exist_ok=True)
for src in (root/'build/rotated_video_sim').glob('*.mem'):shutil.copy2(src,work/src.name)
runner=(root/'tools/run-rotated-video-sim.ps1').read_text()
start=runner.index("& 'C:\\Users");end=runner.index('Push-Location',start)
runner=runner[:start]+runner[end:]
runner=runner.replace('rotated_video_sim','early_video_sim').replace('tb_ddr_rotated_video','tb_ddr_early_video').replace('PASS rotated DDR video:', 'PASS early DDR video:')
runner=runner.replace("'rgb565_burst_pack',",'').replace("'camera_live_bridge',",'').replace("'ddr_rotated_video',",'')
runner=runner.replace("    $files+=Join-Path $root 'rtl\\experimental\\ddr_neighbour_cache_fast.v'", "    $files+=@('ddr_neighbour_cache_fast','rgb565_burst_pack_early','camera_live_bridge_early','ddr_early_video') | ForEach-Object {Join-Path $root ('rtl\\experimental\\'+$_+'.v')}")
write(root/'tools/run-early-video-sim.ps1',runner)
target='corrected_early'
top=(root/'board/corrected_rotate.v').read_text().replace('module corrected_rotate(', 'module corrected_early(').replace('ddr_rotated_video #','ddr_early_video #')
write(root/'board'/f'{target}.v',top)
tcl=(root/'board/build-corrected_rotate.tcl').read_text().replace('corrected_rotate',target)
for old,new in (('rgb565_burst_pack','rgb565_burst_pack_early'),('camera_live_bridge','camera_live_bridge_early'),('ddr_rotated_video','ddr_early_video')):
    tcl=tcl.replace('/rtl/'+old+'.v}', '/rtl/experimental/'+new+'.v}')
write(root/'board'/f'build-{target}.tcl',tcl)
for suffix in ('.fdc','-pins.json'):shutil.copy2(root/'board'/('corrected_rotate'+suffix),root/'board'/(target+suffix))
write(root/'board'/f'program-{target}.tcl',(root/'board/program-corrected_rotate.tcl').read_text().replace('corrected_rotate',target))
sources=re.findall(r'^add_design \{([^}]+)\}',tcl,re.M)
sources += [str(root/'board'/f'{target}.fdc'),str(root/'board'/f'build-{target}.tcl')]
sources += [str(root/p) for p in ('board/calibration-trial.vh','board/ov5640_commands.vh','board/ms7210_commands.vh','rtl/video_crc32.vh','board/rotation-domain.vh','rtl/cordic-constants.vh')]
write(root/'board'/f'{target}-sources.json',json.dumps([str(Path(s).relative_to(root)) for s in sources],indent=2)+'\n')
for name in ('build-pds.ps1','program-heartbeat.ps1','read-telemetry.ps1'):
    path=root/'tools'/name;text=path.read_text(encoding='utf-8-sig')
    text=re.sub(r"(?:@|ValidateSet)\(([^)\n]*'corrected_rotate'[^)\n]*)\)",lambda m:m[0] if "'corrected_early'" in m[0] else m[0][:-1]+",'corrected_early')",text)
    path.write_text(text,encoding='utf-8-sig')
print('Prepared isolated early commit packing, camera bridge, full-video regression and board target.')
