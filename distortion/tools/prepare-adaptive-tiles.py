"""Keep raster locality near 0/180 degrees; use tiles for large rotation."""
from pathlib import Path
import json,re,shutil,hashlib
root=Path(__file__).resolve().parents[1]
def save(rel,text):
    p=root/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text,encoding='utf-8')
def rep(text,old,new):
    assert text.count(old)==1,(old,text.count(old));return text.replace(old,new)
writer=(root/'rtl/experimental/ddr_stripe_result_writer.v').read_text().replace('module ddr_stripe_result_writer','module ddr_adaptive_result_writer')
writer=rep(writer,'input clk,rst_n,input frame_valid,output frame_ready,','input clk,rst_n,input frame_valid,frame_tiled,output frame_ready,')
writer=rep(writer,'reg [2:0] state;','reg [2:0] state;reg tiled;')
writer=rep(writer,'state==COLLECT && in_valid && !failed','state==COLLECT && tiled && in_valid && !failed')
writer=rep(writer,'state<=IDLE;base<=0;', 'state<=IDLE;tiled<=0;base<=0;')
writer=rep(writer,'base<=frame_base;identity<=frame_id;', 'tiled<=frame_tiled;base<=frame_base;identity<=frame_id;')
writer=rep(writer,'in_tag!=expected_tag[TAG_W-1:0] || write_index>=STRIPE_PIXELS',
    'in_tag!=expected_tag[TAG_W-1:0] || (tiled && write_index>=STRIPE_PIXELS)')
writer=rep(writer,"accepted_pixels<=accepted_pixels+1'b1;collected<=collected+1'b1;",
    "accepted_pixels<=accepted_pixels+1'b1;collected<=collected+1'b1;\n                        if(tiled) begin")
writer=rep(writer,'if(collected==STRIPE_PIXELS-1) begin read_index<=0;slot<=0;state<=READ;end',
    '''if(collected==STRIPE_PIXELS-1) begin read_index<=0;slot<=0;state<=READ;end
                        end else begin
                            expected_tag<=expected_tag+1'b1;
                            burst[slot[7:4]][slot[3:0]*16+:16]<=pixel;
                            crc<=video_crc32_pixel(crc,pixel);slot<=slot+1'b1;
                            if(slot==255) begin beat<=0;state<=ADDRESS;end
                        end''')
writer=rep(writer,'else if(read_index==STRIPE_PIXELS) begin', 'else if(!tiled) state<=COLLECT;\n                        else if(read_index==STRIPE_PIXELS) begin')
save('rtl/experimental/ddr_adaptive_result_writer.v',writer)
engine=(root/'rtl/experimental/tiled_frame_engine.v').read_text().replace('module tiled_frame_engine','module adaptive_tiled_frame_engine').replace('ddr_stripe_result_writer #','ddr_adaptive_result_writer #')
engine=rep(engine,'rotated_remap_core #(.WIDTH(WIDTH),.HEIGHT(HEIGHT),', 'rotated_remap_core #(.WIDTH(WIDTH),.HEIGHT(HEIGHT),.INDEX_BITS(4),')
engine=rep(engine,'reg [1:0] state;', 'reg tiled_mode;\n    wire use_tiles=cfg_rot_sin>32\'sd1048576 || cfg_rot_sin< -32\'sd1048576;\n    reg [1:0] state;')
engine=rep(engine,'.frame_base(output_base),.frame_id(frame_id),', '.frame_base(output_base),.frame_id(frame_id),.frame_tiled(use_tiles),')
engine=rep(engine,'state<=IDLE;index<=0;', 'state<=IDLE;tiled_mode<=0;index<=0;')
engine=rep(engine,'else begin index<=0;', 'else begin tiled_mode<=use_tiles;index<=0;')
engine=rep(engine,"if(column[2:0]!=7)","if(!tiled_mode) begin\n                        raster_tag<=raster_tag+1'b1;\n                        if(column==WIDTH-1) begin column<=0;row<=row+1'b1;end else column<=column+1'b1;\n                    end else if(column[2:0]!=7)")
save('rtl/experimental/adaptive_tiled_frame_engine.v',engine)
cache=(root/'rtl/experimental/ddr_neighbour_cache_tiled.v').read_text()
save('rtl/experimental/ddr_adaptive_cache.v',cache)
video=(root/'rtl/experimental/ddr_tiled_video.v').read_text().replace('module ddr_tiled_video','module ddr_adaptive_video').replace('tiled_frame_engine #','adaptive_tiled_frame_engine #')
video=rep(video,'localparam FRAME_BEATS=WIDTH*HEIGHT/16;',
    'localparam FRAME_BEATS=WIDTH*HEIGHT/16;\n    localparam VALID_BANK_LAYOUT=WIDTH>=8 && WIDTH<=4095 && HEIGHT>=8 && HEIGHT<=4095 && WIDTH%8==0 && HEIGHT%8==0 && BANK_STRIDE>=WIDTH*HEIGHT/2 && BANK_STRIDE%128==0 && BANK_STRIDE<=67108864;')
video=rep(video,'if(ready && !capture_active && !source_pending &&', 'if(VALID_BANK_LAYOUT && ready && !capture_active && !source_pending &&')
video=rep(video,'if((capture_active && (source_pending', 'if(!VALID_BANK_LAYOUT || (capture_active && (source_pending')
save('rtl/experimental/ddr_adaptive_video.v',video)
# Integration and six-angle native checks retain independent saved oracles.
for kind in ('video','native'):
    old=root/f'tools/run-tiled-{kind}-sim.ps1'
    runner=old.read_text().replace('tiled_'+kind+'_sim','adaptive_'+kind+'_sim').replace('tb_ddr_tiled','tb_ddr_adaptive').replace('tb_tiled_native','tb_adaptive_native')
    runner=runner.replace("'ddr_neighbour_cache_tiled'","'ddr_adaptive_cache'").replace("'tiled_frame_engine'","'adaptive_tiled_frame_engine'").replace("'ddr_stripe_result_writer'","'ddr_adaptive_result_writer'").replace("'ddr_tiled_video'","'ddr_adaptive_video'")
    runner=runner.replace('PASS tiled','PASS adaptive')
    save(f'tools/run-adaptive-{kind}-sim.ps1',runner)
    work=root/f'build/adaptive_{kind}_sim';work.mkdir(parents=True,exist_ok=True)
    for p in (root/f'build/tiled_{kind}_sim').glob('*.mem'):shutil.copy2(p,work/p.name)
    source=root/('tests/tb_ddr_tiled_video.sv' if kind=='video' else 'tests/tb_tiled_native_regression.sv')
    text=source.read_text().replace('tb_ddr_tiled','tb_ddr_adaptive').replace('tb_tiled_native','tb_adaptive_native').replace('ddr_tiled_video','ddr_adaptive_video').replace('tiled_frame_engine #','adaptive_tiled_frame_engine #').replace('PASS tiled','PASS adaptive')
    if kind=='video':
        text=rep(text,'wire [27:0] awaddr,araddr;wire [3:0] awlen,arlen;wire awvalid,arvalid;', '''wire bad_failed,bad_aw,bad_ar;wire [7:0] bad_fault;
    ddr_adaptive_video #(.WIDTH(32),.HEIGHT(16),.BANK_STRIDE(128)) bad_layout(
        .cam_clk(cam_clk),.core_clk(core_clk),.pix_clk(pix_clk),.rst_n(rst_n),.ready(ready),
        .vsync(1'b0),.href(1'b0),.data(8'b0),.cfg_rotation_valid(1'b1),
        .awready(1'b0),.arready(1'b0),.wready(1'b0),.wlast(1'b0),.rdata(256'b0),.rvalid(1'b0),.rlast(1'b0),.rid(4'b0),
        .failed(bad_failed),.fault(bad_fault),.awvalid(bad_aw),.arvalid(bad_ar));
    wire [27:0] awaddr,araddr;wire [3:0] awlen,arlen;wire awvalid,arvalid;''')
        text=rep(text,'if(bank_mask!=3)', 'if(!bad_failed || bad_fault!=8\'h31 || bad_aw || bad_ar) $fatal(1,"Overlapping bank layout was not quarantined");\n        if(bank_mask!=3)')
    save('tests/'+source.name.replace('tiled','adaptive'),text)
    snapshot=work/'source-snapshot';snapshot.mkdir(exist_ok=True)
    files=[root/'rtl/experimental'/n for n in ('ddr_adaptive_result_writer.v','adaptive_tiled_frame_engine.v','ddr_adaptive_cache.v')]
    if kind=='video':files.append(root/'rtl/experimental/ddr_adaptive_video.v')
    for p in files:shutil.copy2(p,snapshot/p.name)
    (snapshot/'files-sha256.json').write_text(json.dumps({p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in files},indent=2))
target='corrected_adaptive'
save(f'board/{target}.v',(root/'board/corrected_tiled.v').read_text().replace('corrected_tiled',target).replace('ddr_tiled_video','ddr_adaptive_video'))
tcl=(root/'board/build-corrected_tiled.tcl').read_text().replace('corrected_tiled',target).replace('/ddr_tiled_video.v}','/ddr_adaptive_video.v}').replace('/ddr_neighbour_cache_tiled.v}','/ddr_adaptive_cache.v}').replace('/tiled_frame_engine.v}','/adaptive_tiled_frame_engine.v}').replace('/ddr_stripe_result_writer.v}','/ddr_adaptive_result_writer.v}')
save(f'board/build-{target}.tcl',tcl)
for suffix in ('.fdc','-pins.json'):shutil.copy2(root/'board'/('corrected_tiled'+suffix),root/'board'/(target+suffix))
save(f'board/program-{target}.tcl',(root/'board/program-corrected_tiled.tcl').read_text().replace('corrected_tiled',target))
sources=re.findall(r'^add_design \{([^}]+)\}',tcl,re.M)
sources += [str(root/'board'/f'{target}.fdc'),str(root/'board'/f'build-{target}.tcl')]
sources += [str(root/p) for p in ('board/calibration-trial.vh','board/ov5640_commands.vh','board/ms7210_commands.vh','rtl/video_crc32.vh','board/rotation-domain.vh','rtl/cordic-constants.vh')]
save(f'board/{target}-sources.json',json.dumps([str(Path(s).relative_to(root)) for s in sources],indent=2)+'\n')
for name in ('build-pds.ps1','program-heartbeat.ps1','read-telemetry.ps1'):
    p=root/'tools'/name;text=p.read_text(encoding='utf-8-sig')
    text=re.sub(r"(?:@|ValidateSet)\(([^)\n]*'corrected_tiled'[^)\n]*)\)",lambda m:m[0] if "'corrected_adaptive'" in m[0] else m[0][:-1]+",'corrected_adaptive')",text)
    p.write_text(text,encoding='utf-8-sig')
print('Prepared frame-locked adaptive raster/tile traversal and all six real-image angle oracles.')
