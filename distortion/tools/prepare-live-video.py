from pathlib import Path
import re
root=Path(__file__).resolve().parents[1];board=root/'board'
t=(board/'camera_ddr.v').read_text().replace('module camera_ddr(', 'module live_video(')
t=t.replace('// OV5640 DVP/VGA/RGB565 setup + critical register readback + HDMI pattern.', '// Continuous native 640x480 camera2 -> two DDR banks -> 720p HDMI, with CRC32 at source, DDR read and output.')
start=t.index('    wire [9:0] fifo_available;');end=t.index('    // Request/ack held-bus CDC:',start)
t=t[:start]+'''    wire preview_ready,live_failed;
    wire [7:0] live_fault;
    wire [31:0] live_captured,live_read,live_output,live_underflow,live_mismatch,live_ownership;
    wire [31:0] live_source_crc,live_read_crc,live_pixel_crc;
    ddr_live_video pipeline(.cam_clk(cam_pclk),.core_clk(core_clk),.pix_clk(pix_clk),
        .rst_n(rst_n && pll_lock),.ready(store_arm),.vsync(!cam_vsync),.href(!cam_href),.data(cam_data),
        .awaddr(axi_awaddr),.araddr(axi_araddr),.awlen(axi_awlen),.arlen(axi_arlen),
        .awvalid(axi_awvalid),.arvalid(axi_arvalid),.awready(axi_awready),.arready(axi_arready),
        .wdata(axi_wdata),.wstrb(axi_wstrb),.wready(axi_wready),.wlast(axi_wusero_last),
        .rdata(axi_rdata),.rvalid(axi_rvalid),.rlast(axi_rlast),.rid(axi_rid),
        .hs(hs_out),.vs(vs_out),.de(de_out),.r(r_out),.g(g_out),.b(b_out),
        .display_valid(preview_ready),.output_frames(live_output),.underflows(live_underflow),
        .pixel_mismatches(live_mismatch),.pixel_checksum(live_pixel_crc),
        .captured_frames(live_captured),.ownership_errors(live_ownership),.read_frames(live_read),
        .read_checksum(live_read_crc),.latest_source_checksum(live_source_crc),.failed(live_failed),.fault(live_fault));
''' +t[end:]
start=t.index('    // Request/ack held-bus CDC:');end=t.index('        ddr3_test u_ddr3_test_h',start)
t=t[:start]+'''    // CORE -> PIX -> CORE -> SYS held-bus snapshot. Multi-bit counters
    // are captured coherently, never sampled directly while they change.
    reg snapshot_request=0,snapshot_ack=0;
    (* async_reg="true" *) reg [1:0] request_sync=0,ack_sync=0;
    (* async_reg="true" *) reg [1:0] init_sync=0,ddr_pll_sync=0;
    (* async_reg="true" *) reg [1:0] pixel_snapshot_reset=0,pixel_request_sync=0,pixel_ack_sync=0;
    reg pixel_snapshot_request=0,pixel_snapshot_ack=0;
    reg [128:0] pixel_held=0,held_pixel_status=0,pixel_status=0,report_pixel_status=0;
    reg [145:0] held_status=0,ddr_status=0,report_ddr_status=0;
    reg [63:0] held_checksums=0,ddr_checksums=0,report_checksums=0;
    reg ack_seen=0;
    always @(posedge pix_clk or negedge rst_n)
        if(!rst_n) pixel_snapshot_reset<=0;else pixel_snapshot_reset<={pixel_snapshot_reset[0],1'b1};
    always @(posedge pix_clk) begin
        if(!pixel_snapshot_reset[1]) begin pixel_request_sync<=0;pixel_snapshot_ack<=0;pixel_held<=0;end
        else begin
            pixel_request_sync<={pixel_request_sync[0],pixel_snapshot_request};
            if(pixel_request_sync[1]!=pixel_snapshot_ack) begin
                pixel_held<={preview_ready,live_output,live_underflow,live_mismatch,live_pixel_crc};
                pixel_snapshot_ack<=pixel_request_sync[1];
            end
        end
    end
    wire snapshot_failed=live_failed || pixel_held[95:64]!=0 || pixel_held[63:32]!=0;
    wire [7:0] snapshot_fault=live_failed ? live_fault:pixel_held[95:64]!=0 ? 8'h41:pixel_held[63:32]!=0 ? 8'h42:8'h00;
    always @(posedge core_clk) begin
        if(!ddr_reset_sync[1]) begin
            request_sync<=0;snapshot_ack<=0;held_status<=0;held_checksums<=0;held_pixel_status<=0;
            pixel_ack_sync<=0;pixel_snapshot_request<=0;
        end else begin
            request_sync<={request_sync[0],snapshot_request};
            pixel_ack_sync<={pixel_ack_sync[0],pixel_snapshot_ack};
            if(request_sync[1]!=snapshot_ack) pixel_snapshot_request<=request_sync[1];
            if(request_sync[1]!=snapshot_ack && pixel_ack_sync[1]==request_sync[1]) begin
                held_status<={4'h9,pixel_held[128],snapshot_failed,snapshot_fault,live_captured,live_read,live_ownership,28'b0,8'b0};
                held_checksums<={live_source_crc,live_read_crc};held_pixel_status<=pixel_held;
                snapshot_ack<=request_sync[1];
            end
        end
    end
    always @(posedge clk_27m) begin
        if(!rst_n) begin ack_sync<=0;ack_seen<=0;ddr_status<=0;ddr_checksums<=0;pixel_status<=0;init_sync<=0;ddr_pll_sync<=0;end
        else begin
            ack_sync<={ack_sync[0],snapshot_ack};
            init_sync<={init_sync[0],ddr_init_done};ddr_pll_sync<={ddr_pll_sync[0],ddr_pll_lock};
            if(ack_sync[1]!=ack_seen) begin
                ddr_status<=held_status;ddr_checksums<=held_checksums;pixel_status<=held_pixel_status;ack_seen<=ack_sync[1];
            end
        end
    end
    reg report_ddr_init,report_ddr_pll;
''' +t[end:]
start=t.index('    wire preview_ready;',t.index('    bringup_pll video_pll'))
end=t.index('    assign led=',start)
t=t[:start]+t[end:]
t=t.replace('assign led={ddr_status[141],preview_ready,', 'assign led={ddr_status[140],preview_ready,')
# Replace the UART format; preserve the proven transmitter and cadence.
start=t.index('    function [7:0] message;');end=t.index('    reg [1:0] report_state;',start)
fields=[('CAM=',('hex','report_id',0,4)),(' E=',('hex','report_errors',0,2)),
        (' I=',('bit','report_camera_ready')),(' H=',('bit','report_hd_ready')),(' D=',('bit','report_ddr_init')),
        (' V=',('bit','report_pixel_status[128]')),(' C=',('hex','report_edges',0,6)),
        (' F=',('hex','report_frames',0,8)),(' P=',('hex','report_pixels',0,8)),(' L=',('hex','report_lines',0,4)),
        (' WF=',('hex','report_ddr_status',100,8)),(' RF=',('hex','report_ddr_status',68,8)),
        (' PF=',('hex','report_pixel_status',96,8)),(' UF=',('hex','report_pixel_status',64,8)),
        (' MF=',('hex','report_pixel_status',32,8)),(' OW=',('hex','report_ddr_status',36,8)),
        (' X=',('hex','report_ddr_status',132,2)),
        (' CS=',('hex','report_checksums',32,8)),(' RS=',('hex','report_checksums',0,8)),(' PS=',('hex','report_pixel_status',0,8))]
entries=[];i=0
for label,spec in fields:
    for c in label:entries.append(f'                {i}:message="{c}";');i+=1
    if spec[0]=='bit':entries.append(f'                {i}:message={spec[1]} ? "1":"0";');i+=1
    else:
        _,expr,lo,n=spec
        for nib in reversed(range(n)):
            entries.append(f'                {i}:message=hexchar({expr}[{lo+nib*4+3}:{lo+nib*4}]);');i+=1
entries.append(f'                {i}:message=13;{i+1}:message=10;')
assert i+1<256
func='    function [7:0] message;\n        input [7:0] idx;\n        begin\n            case(idx)\n'+'\n'.join(entries)+'\n                default:message="?";\n            endcase\n        end\n    endfunction\n'
t=t[:start]+func+t[end:]
t=t.replace('if(report_index==223)',f'if(report_index=={i+1})')
t=t.replace('report_checksums<=0;report_ddr_status<=0;', 'report_checksums<=0;report_pixel_status<=0;report_ddr_status<=0;')
t=t.replace('report_checksums<=ddr_checksums;report_ddr_status<=ddr_status;', 'report_checksums<=ddr_checksums;report_pixel_status<=pixel_status;report_ddr_status<=ddr_status;')
(board/'live_video.v').write_text(t)
fdc=(board/'camera_ddr.fdc').read_text().replace('-group [get_clocks {clk_27m pixel_clk}] -group','-group [get_clocks {clk_27m}] -group')
fdc+='''
# DDR <-> HDMI: Gray FIFO pointers, synchronized frame request/grant, and
# held CRC/snapshot buses. These crossings are timed, not false-pathed.
set_max_delay -datapath_only -from [get_clocks pixel_clk] -to [get_clocks ddrphy_sysclk] 8.0
set_max_delay -datapath_only -from [get_clocks ddrphy_sysclk] -to [get_clocks pixel_clk] 8.0
set_min_delay -from [get_clocks pixel_clk] -to [get_clocks ddrphy_sysclk] 0.0
set_min_delay -from [get_clocks ddrphy_sysclk] -to [get_clocks pixel_clk] 0.0
'''
(board/'live_video.fdc').write_text(fdc)
(board/'live_video-pins.json').write_text((board/'camera_ddr-pins.json').read_text())
build=(board/'build-camera_ddr.tcl').read_text().replace('/board/camera_ddr.v}','/board/live_video.v}').replace('/board/camera_ddr.fdc}','/board/live_video.fdc}').replace('top_module camera_ddr','top_module live_video')
build=build.replace('add_design {D:/English/FPGA/distortion/rtl/camera_ddr_bridge.v}','add_design {D:/English/FPGA/distortion/rtl/camera_live_bridge.v}')
build=build.replace('add_design {D:/English/FPGA/distortion/rtl/ddr_frame_store.v}', '\n'.join(f'add_design {{D:/English/FPGA/distortion/rtl/{n}.v}}' for n in ('ddr_video_writer','ddr_video_reader','ddr_video_output','ddr_live_video')))
build=build.replace('add_design {D:/English/FPGA/distortion/rtl/camera_preview.v}\n','')
(board/'build-live_video.tcl').write_text(build)
(board/'program-live_video.tcl').write_text((board/'program-camera_ddr.tcl').read_text().replace('camera_ddr','live_video'))
for name in ('build-pds.ps1','program-heartbeat.ps1','read-telemetry.ps1'):
    p=root/'tools'/name;s=p.read_text(encoding='utf-8-sig');lines=s.splitlines(keepends=True)
    lines[0]=lines[0].replace("'camera_ddr')", "'camera_ddr','live_video')");s=''.join(lines)
    s=re.sub(r"@\(([^)]*'camera_ddr')\)", lambda m:'@('+m[1]+",'live_video')",s)
    if name=='build-pds.ps1' and "throw 'Live video source is newer than bitstream'" not in s:
        s=s.replace("    if($Target -eq 'camera_diag') {",'''    if($Target -eq 'live_video') {
        foreach($src in @('board\\live_video.v','board\\live_video.fdc','board\\build-live_video.tcl','rtl\\rgb565_burst_pack.v','rtl\\video_async_fifo.v','rtl\\camera_live_bridge.v','rtl\\ddr_video_writer.v','rtl\\ddr_video_reader.v','rtl\\ddr_video_output.v','rtl\\ddr_live_video.v','rtl\\video_crc32.vh','platform\\video_base\\ipcore\\ddr3_test\\ddr3_test.idf')) {
            if((Get-Item (Join-Path $projectRoot $src)).LastWriteTime -gt $bitFile.LastWriteTime){throw 'Live video source is newer than bitstream'}
        }
    }
    if($Target -eq 'camera_diag') {''')
    p.write_text(s,encoding='utf-8-sig')
print(f'Prepared live_video: two DDR banks, native 640x480 display, source/read/pixel CRC32, coherent telemetry ({i+2} bytes).')
