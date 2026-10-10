"""Dedicated SRAM target: frozen native frame -> CRC-protected binary UART.

Derive physical camera/DDR/HDMI wiring from the already validated camera_ddr
target. Do not alter existing live_video sources or bitstreams.
"""
from pathlib import Path
import re
root=Path(__file__).resolve().parents[1];board=root/'board'
t=(board/'camera_ddr.v').read_text().replace('module camera_ddr(', 'module calibration_capture(')
a=t.index('    wire [9:0] fifo_available;');b=t.index('        ddr3_test u_ddr3_test_h',a)
t=t[:a]+'''    wire [9:0] fifo_available;
    wire fifo_ready,fifo_valid,fifo_rd_en,source_done,source_valid;
    wire [257:0] fifo_data;
    wire [31:0] source_checksum,write_checksum;
    reg capture_active=0,export_start=0;
    reg [1:0] cycle_state=0;
    reg [6:0] reset_wait=0;
    reg [31:0] frame_id=0;
    wire export_done,export_failed,export_idle;wire [7:0] export_fault;
    wire capture_rst_n=rst_n && capture_active;
    camera_live_bridge bridge(.cam_clk(cam_pclk),.ddr_clk(core_clk),.rst_n(capture_rst_n),.arm(store_arm),
        .vsync(!cam_vsync),.href(!cam_href),.data(cam_data),
        .fifo_rd_en(fifo_rd_en),.fifo_data(fifo_data),.fifo_valid(fifo_valid),.fifo_ready(fifo_ready),
        .fifo_available(fifo_available),.source_done(source_done),.source_valid(source_valid),.source_checksum(source_checksum));
    ddr_video_writer memory_store(.clk(core_clk),.rst_n(store_arm && capture_active),.base_address(28'b0),
        .fifo_available(fifo_available),.fifo_ready(fifo_ready),.fifo_rd_en(fifo_rd_en),
        .fifo_valid(fifo_valid),.fifo_data(fifo_data),.source_done(source_done),
        .source_valid(source_valid),.source_checksum(source_checksum),
        .awaddr(axi_awaddr),.awlen(axi_awlen),.awvalid(axi_awvalid),.awready(axi_awready),
        .wdata(axi_wdata),.wstrb(axi_wstrb),.wready(axi_wready),.wlast(axi_wusero_last),
        .state(test_state),.done(test_done),.failed(test_failed),.fault(test_fault),
        .written_beats(test_written),.write_checksum(write_checksum));
    wire serial_valid,serial_ready,serial_done,serial_busy;wire [7:0] serial_data;
    ddr_uart_frame exporter(.clk(core_clk),.rst_n(store_arm && capture_active),.start(export_start),
        .base_address(28'b0),.frame_id(frame_id),.source_crc(source_checksum),
        .araddr(axi_araddr),.arlen(axi_arlen),.arvalid(axi_arvalid),.arready(axi_arready),
        .rdata(axi_rdata),.rvalid(axi_rvalid),.rlast(axi_rlast),.rid(axi_rid),
        .byte_valid(serial_valid),.byte_ready(serial_ready),.byte_done(serial_done),.byte_data(serial_data),
        .idle(export_idle),.done(export_done),.failed(export_failed),.fault(export_fault));
    uart_tx #(.CLOCK_HZ(125000000),.BAUD(921600)) serial(.clk(core_clk),.rst_n(ddr_reset_sync[1]),
        .start(serial_valid && serial_ready),.data(serial_data),.tx(uart_txd),.busy(serial_busy),.done(serial_done));
    assign serial_ready=!serial_busy;
    always @(posedge core_clk) begin
        if(!ddr_reset_sync[1]) begin capture_active<=0;export_start<=0;cycle_state<=0;reset_wait<=0;frame_id<=0;end
        else begin
            export_start<=0;
            case(cycle_state)
                0:if(store_arm) begin
                    if(reset_wait==64) begin capture_active<=1;reset_wait<=0;cycle_state<=1;frame_id<=frame_id+1'b1;end
                    else reset_wait<=reset_wait+1'b1;
                end
                1:if(test_done) begin export_start<=1;cycle_state<=2;end
                2:if(export_done) begin capture_active<=0;cycle_state<=0;reset_wait<=0;end
                default:cycle_state<=0;
            endcase
        end
    end
''' +t[b:]
# The existing UART formatter and status snapshot logic are unused in this
# binary target. Remove them so there is exactly one physical UART driver.
a=t.index('    assign led=');t=t[:a]+'''    assign led={export_failed || test_failed,preview_ready,|hd_error,|cam_errors,pll_lock,hd_ready,cam_match,heart};
endmodule
'''
(board/'calibration_capture.v').write_text(t)
(board/'calibration_capture.fdc').write_text((board/'camera_ddr.fdc').read_text())
(board/'calibration_capture-pins.json').write_text((board/'camera_ddr-pins.json').read_text())
build=(board/'build-camera_ddr.tcl').read_text().replace('camera_ddr.v}', 'calibration_capture.v}').replace('camera_ddr.fdc}', 'calibration_capture.fdc}').replace('top_module camera_ddr','top_module calibration_capture')
build=build.replace('/rtl/camera_ddr_bridge.v}', '/rtl/camera_live_bridge.v}').replace('/rtl/ddr_frame_store.v}', '/rtl/ddr_video_writer.v}')
build='add_design {D:/English/FPGA/distortion/rtl/ddr_uart_frame.v}\n'+build
(board/'build-calibration_capture.tcl').write_text(build)
(board/'program-calibration_capture.tcl').write_text((board/'program-camera_ddr.tcl').read_text().replace('camera_ddr','calibration_capture'))
for name in ('build-pds.ps1','program-heartbeat.ps1'):
    p=root/'tools'/name;s=p.read_text(encoding='utf-8-sig');lines=s.splitlines(keepends=True)
    lines[0]=lines[0].replace("'live_video')", "'live_video','calibration_capture')");s=''.join(lines)
    s=re.sub(r"@\(([^)]*'live_video')\)",lambda m:'@('+m[1]+",'calibration_capture')",s)
    if name=='build-pds.ps1' and "throw 'Calibration capture source is newer than bitstream'" not in s:
        s=s.replace("    if($Target -eq 'camera_diag') {",'''    if($Target -eq 'calibration_capture') {
        foreach($src in @('board\\calibration_capture.v','board\\calibration_capture.fdc','board\\build-calibration_capture.tcl','rtl\\ddr_uart_frame.v','rtl\\camera_live_bridge.v','rtl\\ddr_video_writer.v','rtl\\camera_preview.v','rtl\\rgb565_burst_pack.v','rtl\\video_async_fifo.v','rtl\\video_crc32.vh','platform\\video_base\\ipcore\\ddr3_test\\ddr3_test.idf')) {
            if((Get-Item (Join-Path $projectRoot $src)).LastWriteTime -gt $bitFile.LastWriteTime){throw 'Calibration capture source is newer than bitstream'}
        }
    }
    if($Target -eq 'camera_diag') {''')
    p.write_text(s,encoding='utf-8-sig')
print('Prepared calibration_capture: frozen 640x480 RGB565, 921600-baud binary UART, header/source/payload CRC32, re-arm after final UART stop bit.')
