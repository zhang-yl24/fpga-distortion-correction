from pathlib import Path
root=Path(__file__).resolve().parents[1];board=root/'board'
t=(board/'ddr_check.v').read_text().replace('module ddr_check(', 'module camera_ddr(')
start=t.index('    ddr_integrity_test memory_test(');end=t.index('    // Request/ack held-bus CDC:',start)
t=t[:start]+'''    (* async_reg="true" *) reg [1:0] camera_ready_ddr=0;
    always @(posedge core_clk)
        if(!ddr_reset_sync[1]) camera_ready_ddr<=0;
        else camera_ready_ddr<={camera_ready_ddr[0],camera_ready};
    wire store_arm=test_reset_sync[1] && camera_ready_ddr[1];
    wire [9:0] fifo_available;
    wire fifo_ready,fifo_valid,fifo_rd_en,source_done,source_valid;
    wire [257:0] fifo_data;
    wire [31:0] source_checksum,write_checksum,read_checksum;
    camera_ddr_bridge bridge(.cam_clk(cam_pclk),.ddr_clk(core_clk),.rst_n(rst_n),.arm(store_arm),
        .vsync(!cam_vsync),.href(!cam_href),.data(cam_data),
        .fifo_rd_en(fifo_rd_en),.fifo_data(fifo_data),.fifo_valid(fifo_valid),.fifo_ready(fifo_ready),
        .fifo_available(fifo_available),.source_done(source_done),.source_valid(source_valid),.source_checksum(source_checksum));
    ddr_frame_store memory_store(.clk(core_clk),.rst_n(store_arm),
        .fifo_available(fifo_available),.fifo_ready(fifo_ready),.fifo_rd_en(fifo_rd_en),
        .fifo_valid(fifo_valid),.fifo_data(fifo_data),.source_done(source_done),
        .source_valid(source_valid),.source_checksum(source_checksum),
        .awaddr(axi_awaddr),.araddr(axi_araddr),.awlen(axi_awlen),.arlen(axi_arlen),
        .awvalid(axi_awvalid),.arvalid(axi_arvalid),.awready(axi_awready),.arready(axi_arready),
        .wdata(axi_wdata),.wstrb(axi_wstrb),.wready(axi_wready),.wlast(axi_wusero_last),
        .rdata(axi_rdata),.rvalid(axi_rvalid),.rlast(axi_rlast),.rid(axi_rid),
        .state(test_state),.done(test_done),.failed(test_failed),.fault(test_fault),
        .written_beats(test_written),.read_beats(test_read),.write_checksum(write_checksum),.read_checksum(read_checksum));
    assign test_errors={31'b0,test_failed};
    assign test_first_bad=0;
    assign test_passes={7'b0,test_done};
''' +t[end:]
# Expand the held-bus snapshot with source and actual DDR-read checksums.
t=t.replace('reg [145:0] held_status=0,ddr_status=0;', 'reg [145:0] held_status=0,ddr_status=0;\n    reg [63:0] held_checksums=0,ddr_checksums=0,report_checksums=0;')
t=t.replace('snapshot_ack<=0;held_status<=0;', 'snapshot_ack<=0;held_status<=0;held_checksums<=0;')
t=t.replace('                snapshot_ack<=request_sync[1];', '                held_checksums<={source_checksum,read_checksum};\n                snapshot_ack<=request_sync[1];')
t=t.replace('ack_seen<=0;ddr_status<=0;', 'ack_seen<=0;ddr_status<=0;ddr_checksums<=0;')
t=t.replace('begin ddr_status<=held_status;ack_seen<=ack_sync[1];end', 'begin ddr_status<=held_status;ddr_checksums<=held_checksums;ack_seen<=ack_sync[1];end')
t=t.replace('snapshot_request<=0;report_ddr_status<=0;', 'snapshot_request<=0;report_checksums<=0;report_ddr_status<=0;')
t=t.replace('snapshot_request<=!snapshot_request;report_ddr_status<=ddr_status;', 'snapshot_request<=!snapshot_request;report_checksums<=ddr_checksums;report_ddr_status<=ddr_status;')
old='                198:message=13;199:message=10;';assert old in t
entries=[];i=198
for label,lo in [(' CS=',32),(' RS=',0)]:
    for c in label:entries.append(f'                {i}:message="{c}";');i+=1
    for nib in reversed(range(8)):
        entries.append(f'                {i}:message=hexchar(report_checksums[{lo+nib*4+3}:{lo+nib*4}]);');i+=1
entries.append(f'                {i}:message=13;{i+1}:message=10;')
t=t.replace(old,'\n'.join(entries)).replace('if(report_index==199)',f'if(report_index=={i+1})')
(board/'camera_ddr.v').write_text(t)
fdc=(board/'ddr_check.fdc').read_text().replace('-group [get_clocks {clk_27m pixel_clk camera_pclk}] -group', '-group [get_clocks {clk_27m pixel_clk}] -group')
fdc+='''
# CAM <-> DDR crossings use two-flop Gray pointers and held frame metadata.
# Do NOT false-path these clocks. Bound all data paths to 8 ns, below both
# source periods; this also bounds Gray-bit skew below one source cycle.
set_max_delay -datapath_only -from [get_clocks camera_pclk] -to [get_clocks ddrphy_sysclk] 8.0
set_max_delay -datapath_only -from [get_clocks ddrphy_sysclk] -to [get_clocks camera_pclk] 8.0
set_min_delay -from [get_clocks camera_pclk] -to [get_clocks ddrphy_sysclk] 0.0
set_min_delay -from [get_clocks ddrphy_sysclk] -to [get_clocks camera_pclk] 0.0
'''
(board/'camera_ddr.fdc').write_text(fdc)
(board/'camera_ddr-pins.json').write_text((board/'ddr_check-pins.json').read_text())
build=(board/'build-ddr_check.tcl').read_text().replace('/board/ddr_check.v}','/board/camera_ddr.v}').replace('/board/ddr_check.fdc}','/board/camera_ddr.fdc}').replace('top_module ddr_check','top_module camera_ddr')
build=build.replace('add_design {D:/English/FPGA/distortion/rtl/ddr_integrity_test.v}', '\n'.join(f'add_design {{D:/English/FPGA/distortion/rtl/{n}.v}}' for n in ('rgb565_burst_pack','video_async_fifo','camera_ddr_bridge','ddr_frame_store')))
(board/'build-camera_ddr.tcl').write_text(build)
(board/'program-camera_ddr.tcl').write_text((board/'program-ddr_check.tcl').read_text().replace('ddr_check','camera_ddr'))
for name in ('build-pds.ps1','program-heartbeat.ps1','read-telemetry.ps1'):
    p=root/'tools'/name;s=p.read_text(encoding='utf-8-sig');lines=s.splitlines(keepends=True)
    lines[0]=lines[0].replace("'ddr_check')", "'ddr_check','camera_ddr')");s=''.join(lines)
    s=s.replace("'preview','ddr_check')", "'preview','ddr_check','camera_ddr')")
    if name=='build-pds.ps1' and "throw 'Camera DDR source is newer than bitstream'" not in s:
        s=s.replace("    if($Target -eq 'camera_diag') {",'''    if($Target -eq 'camera_ddr') {
        foreach($src in @('board\\camera_ddr.v','board\\camera_ddr.fdc','board\\build-camera_ddr.tcl','rtl\\camera_preview.v','rtl\\rgb565_burst_pack.v','rtl\\video_async_fifo.v','rtl\\camera_ddr_bridge.v','rtl\\ddr_frame_store.v','platform\\video_base\\ipcore\\ddr3_test\\ddr3_test.idf')) {
            if((Get-Item (Join-Path $projectRoot $src)).LastWriteTime -gt $bitFile.LastWriteTime){throw 'Camera DDR source is newer than bitstream'}
        }
    }
    if($Target -eq 'camera_diag') {''')
    p.write_text(s,encoding='utf-8-sig')
print(f'Prepared camera_ddr: one complete 640x480 frame stored/read back (19200 beats); {i+2} UART bytes; existing live preview retained.')
