"""Stage a separate calibrated three-bank target; preserve working capture/live targets."""
from pathlib import Path
import re

root = Path(__file__).resolve().parents[1]
board = root / 'board'
s = (root / 'rtl/ddr_live_video.v').read_text()
s = s.replace('// Two-bank ownership: writer -> pending -> frame-boundary reader -> free.\n// Writer pauses while a complete bank is pending; this bounds throughput to\n// capture/hand-off cadence but never overwrites the displayed frame.',
'''// Source bank 0 is frozen until the remap engine finishes. Result banks 1/2
// alternate through processing -> pending -> frame-boundary front -> free.
// No coordinate lookup table: staged coefficients feed the arithmetic core.''')
s = s.replace('module ddr_live_video #(', 'module ddr_corrected_video #(')
s = s.replace('    input vsync,href,input [7:0] data,', '''    input vsync,href,input [7:0] data,
    input signed [23:0] cfg_out_cx,cfg_out_cy,cfg_src_cx,cfg_src_cy,cfg_src_fx,cfg_src_fy,
    input signed [31:0] cfg_inv_fx,cfg_inv_fy,cfg_k1,cfg_k2,cfg_k3,cfg_p1,cfg_p2,
    output reg [31:0] processed_frames,last_process_cycles,
    output wire [31:0] cache_hits,cache_misses,completed_queries,
    output reg [31:0] latest_result_checksum,''')
s = s.replace('    reg [31:0] front_checksum;', '''    reg [31:0] front_checksum,pending_checksum,source_id;
    reg source_pending,processing,engine_start;
    reg [31:0] process_cycles;
    wire engine_ready,engine_done,engine_failed,read_arb_failed,write_arb_failed;
    wire [7:0] engine_fault,read_arb_fault,write_arb_fault;
    wire [31:0] engine_crc,engine_id;
    wire [27:0] engine_base;
    wire [27:0] camera_awaddr,result_awaddr,display_araddr,sample_araddr;
    wire [3:0] camera_awlen,result_awlen,display_arlen,sample_arlen;
    wire camera_awvalid,camera_awready,result_awvalid,result_awready;
    wire display_arvalid,display_arready,sample_arvalid,sample_arready;
    wire [255:0] camera_wdata,result_wdata,display_rdata,sample_rdata;
    wire [31:0] camera_wstrb,result_wstrb;
    wire camera_wready,camera_wlast,result_wready,result_wlast;
    wire display_rvalid,display_rlast,sample_rvalid,sample_rlast;
    wire [3:0] display_rid,sample_rid;''')
s = s.replace('wire [27:0] write_base=write_bank ? BANK_STRIDE:0;', 'wire [27:0] write_base=0;')
# Only replace each individual client connection block, never shared bus ports.
start = s.index('    ddr_video_writer #(')
end = s.index('    wire request_toggle;', start)
w = s[start:end]
for name in ('awaddr','awlen','awvalid','awready','wdata','wstrb','wready','wlast'):
    w = w.replace(f'.{name}({name})', f'.{name}(camera_{name})')
s = s[:start]+w+s[end:]
start = s.index('    ddr_video_reader #(')
end = s.index('    video_async_fifo display_fifo', start)
r = s[start:end]
for name in ('araddr','arlen','arvalid','arready','rdata','rvalid','rlast','rid'):
    r = r.replace(f'.{name}({name})', f'.{name}(display_{name})')
s = s[:start]+r+s[end:]
start = s.index('    reg ownership_failed;')
s = s[:start]+'''    wire transaction_rst_n=core_rst_n && ready;
    wire [27:0] result_base=write_bank ? 2*BANK_STRIDE:BANK_STRIDE;
    remap_frame_engine #(.WIDTH(WIDTH),.HEIGHT(HEIGHT)) engine(
        .clk(core_clk),.rst_n(transaction_rst_n),.frame_valid(engine_start),.frame_ready(engine_ready),
        .source_base(28'b0),.output_base(result_base),.frame_id(source_id),
        .cfg_out_cx(cfg_out_cx),.cfg_out_cy(cfg_out_cy),.cfg_src_cx(cfg_src_cx),.cfg_src_cy(cfg_src_cy),
        .cfg_src_fx(cfg_src_fx),.cfg_src_fy(cfg_src_fy),.cfg_inv_fx(cfg_inv_fx),.cfg_inv_fy(cfg_inv_fy),
        .cfg_k1(cfg_k1),.cfg_k2(cfg_k2),.cfg_k3(cfg_k3),.cfg_p1(cfg_p1),.cfg_p2(cfg_p2),
        .araddr(sample_araddr),.arlen(sample_arlen),.arvalid(sample_arvalid),.arready(sample_arready),
        .rdata(sample_rdata),.rvalid(sample_rvalid),.rlast(sample_rlast),.rid(sample_rid),
        .awaddr(result_awaddr),.awlen(result_awlen),.awvalid(result_awvalid),.awready(result_awready),
        .wdata(result_wdata),.wstrb(result_wstrb),.wready(result_wready),.wlast(result_wlast),
        .done(engine_done),.failed(engine_failed),.fault(engine_fault),
        .completed_base(engine_base),.completed_id(engine_id),.completed_crc(engine_crc),
        .hits(cache_hits),.misses(cache_misses),.completed_queries(completed_queries));
    ddr_read_arbiter read_bus(.clk(core_clk),.rst_n(transaction_rst_n),.display_urgent(display_used<64),
        .c0_araddr(display_araddr),.c1_araddr(sample_araddr),.c0_arlen(display_arlen),.c1_arlen(sample_arlen),
        .c0_arvalid(display_arvalid),.c1_arvalid(sample_arvalid),.c0_arready(display_arready),.c1_arready(sample_arready),
        .c0_rdata(display_rdata),.c1_rdata(sample_rdata),.c0_rvalid(display_rvalid),.c1_rvalid(sample_rvalid),
        .c0_rlast(display_rlast),.c1_rlast(sample_rlast),.c0_rid(display_rid),.c1_rid(sample_rid),
        .araddr(araddr),.arlen(arlen),.arvalid(arvalid),.arready(arready),
        .rdata(rdata),.rvalid(rvalid),.rlast(rlast),.rid(rid),
        .failed(read_arb_failed),.fault(read_arb_fault),.busy(),.bursts0(),.bursts1());
    ddr_write_arbiter write_bus(.clk(core_clk),.rst_n(transaction_rst_n),
        .c0_awaddr(camera_awaddr),.c1_awaddr(result_awaddr),.c0_awlen(camera_awlen),.c1_awlen(result_awlen),
        .c0_awvalid(camera_awvalid),.c1_awvalid(result_awvalid),.c0_awready(camera_awready),.c1_awready(result_awready),
        .c0_wdata(camera_wdata),.c1_wdata(result_wdata),.c0_wstrb(camera_wstrb),.c1_wstrb(result_wstrb),
        .c0_wready(camera_wready),.c1_wready(result_wready),.c0_wlast(camera_wlast),.c1_wlast(result_wlast),
        .awaddr(awaddr),.awlen(awlen),.awvalid(awvalid),.awready(awready),
        .wdata(wdata),.wstrb(wstrb),.wready(wready),.wlast(wlast),
        .failed(write_arb_failed),.fault(write_arb_fault),.busy(),.bursts0(),.bursts1());
    reg ownership_failed;
    assign failed=writer_failed || reader_failed || engine_failed || read_arb_failed || write_arb_failed || ownership_failed;
    assign fault=ownership_failed ? 8'h31:engine_failed ? engine_fault:read_arb_failed ? (8'h50|read_arb_fault):
        write_arb_failed ? (8'h60|write_arb_fault):writer_failed ? writer_fault:reader_failed ? reader_fault:8'h00;
    always @(posedge core_clk) begin
        if(!core_rst_n) begin
            capture_active<=0;write_bank<=0;pending<=0;front_bank<=1;front_valid<=0;front_checksum<=0;
            restart_wait<=0;captured_frames<=0;ownership_errors<=0;ownership_failed<=0;latest_source_checksum<=0;
            grant_toggle<=0;grant_valid<=0;grant_checksum<=0;reader_base<=0;reader_expected<=0;
            reader_start<=0;request_sync<=0;request_seen<=0;
            source_pending<=0;processing<=0;engine_start<=0;pending_checksum<=0;source_id<=0;
            processed_frames<=0;last_process_cycles<=0;process_cycles<=0;latest_result_checksum<=0;
        end else begin
            request_sync<={request_sync[0],request_toggle};reader_start<=0;engine_start<=0;
            if(ready && !capture_active && !source_pending && !processing && !failed) begin
                if(restart_wait==64) begin capture_active<=1;restart_wait<=0;end
                else restart_wait<=restart_wait+1'b1;
            end
            if(capture_active && writer_done) begin
                source_pending<=1;capture_active<=0;captured_frames<=captured_frames+1'b1;
                latest_source_checksum<=source_checksum;source_id<=captured_frames+1'b1;
            end
            if(ready && source_pending && !processing && !pending && engine_ready && !failed) begin
                source_pending<=0;processing<=1;engine_start<=1;process_cycles<=0;
            end
            if(processing) process_cycles<=process_cycles+1'b1;
            if(processing && engine_done && !failed) begin
                processing<=0;pending<=1;pending_checksum<=engine_crc;latest_result_checksum<=engine_crc;
                processed_frames<=processed_frames+1'b1;last_process_cycles<=process_cycles;restart_wait<=0;
                if(engine_base!=result_base || engine_id!=source_id) begin
                    ownership_failed<=1;ownership_errors<=ownership_errors+1'b1;
                end
            end
            if(request_sync[1]!=request_seen) begin
                request_seen<=request_sync[1];grant_toggle<=request_sync[1];grant_valid<=0;
                if(ready && !failed && (front_valid || pending)) begin
                    if(!reader_idle) begin ownership_failed<=1;ownership_errors<=ownership_errors+1'b1;end
                    else begin
                        grant_valid<=1;reader_start<=1;
                        if(pending) begin
                            front_bank<=write_bank;front_valid<=1;front_checksum<=pending_checksum;
                            reader_base<=result_base;reader_expected<=pending_checksum;grant_checksum<=pending_checksum;
                            write_bank<=!write_bank;pending<=0;
                        end else begin
                            reader_base<=front_bank ? 2*BANK_STRIDE:BANK_STRIDE;
                            reader_expected<=front_checksum;grant_checksum<=front_checksum;
                        end
                    end
                end
            end
            if((capture_active && (source_pending || processing)) ||
               (processing && front_valid && write_bank==front_bank)) begin
                ownership_failed<=1;ownership_errors<=ownership_errors+1'b1;
            end
        end
    end
endmodule
'''
(root/'rtl/ddr_corrected_video.v').write_text(s)

# Copy the exact reviewed header into this target, retaining provenance in JSON.
(board/'calibration-trial.vh').write_text((root/'results/calibration-fpga-candidate-20261006/calibration-candidate.vh').read_text())
t=(board/'live_video.v').read_text().replace('module live_video(', 'module corrected_video(')
t=t.replace('// Continuous native 640x480 camera2 -> two DDR banks -> 720p HDMI, with CRC32 at source, DDR read and output.',
'''// Native camera2 -> frozen source DDR -> arithmetic remap/bilinear -> two result banks -> HDMI.
// First calibration trial: matched input/output K, bounded radial surrogate, no rotation.''')
t=t.replace('    ddr_live_video pipeline(', '''    `include "D:/English/FPGA/distortion/board/calibration-trial.vh"
    wire [31:0] corrected_frames,process_cycles,cache_hits,cache_misses,completed_queries,result_crc;
    ddr_corrected_video pipeline(''')
t=t.replace('.data(cam_data),\n        .awaddr', '''.data(cam_data),
        .cfg_out_cx(CAL_OUT_CX),.cfg_out_cy(CAL_OUT_CY),.cfg_src_cx(CAL_SRC_CX),.cfg_src_cy(CAL_SRC_CY),
        .cfg_src_fx(CAL_SRC_FX),.cfg_src_fy(CAL_SRC_FY),.cfg_inv_fx(CAL_INV_FX),.cfg_inv_fy(CAL_INV_FY),
        .cfg_k1(CAL_K1),.cfg_k2(CAL_K2),.cfg_k3(CAL_K3),.cfg_p1(CAL_P1),.cfg_p2(CAL_P2),
        .processed_frames(corrected_frames),.last_process_cycles(process_cycles),
        .cache_hits(cache_hits),.cache_misses(cache_misses),.completed_queries(completed_queries),.latest_result_checksum(result_crc),
        .awaddr''')
t=t.replace('    reg ack_seen=0;', '    reg [159:0] held_engine=0,engine_status=0,report_engine=0;\n    reg ack_seen=0;')
t=t.replace('pixel_snapshot_request<=0;', 'pixel_snapshot_request<=0;held_engine<=0;')
t=t.replace('held_checksums<={live_source_crc,live_read_crc};', 'held_engine<={corrected_frames,process_cycles,cache_hits,cache_misses,result_crc};\n                held_checksums<={live_source_crc,live_read_crc};')
t=t.replace('ack_seen<=0;ddr_status<=0;', 'ack_seen<=0;engine_status<=0;ddr_status<=0;')
t=t.replace('ddr_status<=held_status;', 'engine_status<=held_engine;ddr_status<=held_status;')
t=t.replace('report_pixel_status<=0;', 'report_pixel_status<=0;report_engine<=0;')
t=t.replace('report_checksums<=ddr_checksums;', 'report_engine<=engine_status;report_checksums<=ddr_checksums;')
start=t.index('    function [7:0] message;');end=t.index('    reg [1:0] report_state;',start)
fields=[('CAM=',('hex','report_id',0,4)),(' E=',('hex','report_errors',0,2)),
        (' I=',('bit','report_camera_ready')),(' H=',('bit','report_hd_ready')),(' D=',('bit','report_ddr_init')),
        (' V=',('bit','report_pixel_status[128]')),
        (' WF=',('hex','report_ddr_status',100,8)),(' CF=',('hex','report_engine',128,8)),
        (' PF=',('hex','report_pixel_status',96,8)),(' UF=',('hex','report_pixel_status',64,8)),
        (' MF=',('hex','report_pixel_status',32,8)),(' OW=',('hex','report_ddr_status',36,8)),
        (' X=',('hex','report_ddr_status',132,2)),(' CS=',('hex','report_checksums',32,8)),
        (' RC=',('hex','report_engine',0,8)),(' RS=',('hex','report_checksums',0,8)),(' PS=',('hex','report_pixel_status',0,8)),
        (' CY=',('hex','report_engine',96,8)),(' HT=',('hex','report_engine',64,8)),(' MS=',('hex','report_engine',32,8))]
entries=[];i=0
for label,spec in fields:
    for c in label: entries.append(f'                {i}:message="{c}";');i+=1
    if spec[0]=='bit': entries.append(f'                {i}:message={spec[1]} ? "1":"0";');i+=1
    else:
        _,expr,lo,n=spec
        for nib in reversed(range(n)):
            entries.append(f'                {i}:message=hexchar({expr}[{lo+nib*4+3}:{lo+nib*4}]);');i+=1
entries.append(f'                {i}:message=13;{i+1}:message=10;')
assert i+1<256
func='    function [7:0] message;\n        input [7:0] idx;\n        begin\n            case(idx)\n'+'\n'.join(entries)+'\n                default:message="?";\n            endcase\n        end\n    endfunction\n'
t=t[:start]+func+t[end:]
t=re.sub(r'if\(report_index==\d+\)',f'if(report_index=={i+1})',t)
(board/'corrected_video.v').write_text(t)
for suffix in ('fdc','-pins.json'):
    a='live_video'+suffix if suffix.startswith('-') else 'live_video.'+suffix
    b='corrected_video'+suffix if suffix.startswith('-') else 'corrected_video.'+suffix
    (board/b).write_text((board/a).read_text())
modules=('ddr_corrected_video','remap_frame_engine','ddr_read_arbiter','ddr_write_arbiter',
         'ddr_result_writer','brown_remap_core','brown_inverse_mapper','mul32_pipe','ddr_remap_sample','ddr_neighbour_cache','bilinear_rgb')
b=(board/'build-live_video.tcl').read_text().replace('live_video','corrected_video')
b=b.replace('\npnr\n','\npnr -optimize_multi_corner_timing -fix_hold_violation -fix_hold_violation_iterations 20\n')
b=b.replace('add_design {D:/English/FPGA/distortion/rtl/ddr_corrected_video.v}', '\n'.join(f'add_design {{D:/English/FPGA/distortion/rtl/{m}.v}}' for m in modules))
(board/'build-corrected_video.tcl').write_text(b)
(board/'program-corrected_video.tcl').write_text((board/'program-live_video.tcl').read_text().replace('live_video','corrected_video'))
for name in ('build-pds.ps1','program-heartbeat.ps1','read-telemetry.ps1'):
    p=root/'tools'/name
    text=p.read_text(encoding='utf-8-sig')
    text=text.replace("if($Target -eq 'live_video','corrected_video')", "if($Target -eq 'live_video')")
    text=re.sub(r"(?:@|ValidateSet)\(([^)\n]*'live_video'[^)\n]*)\)",lambda m:m[0] if "'corrected_video'" in m[0] else m[0][:-1]+",'corrected_video')",text)
    if name=='build-pds.ps1' and "throw 'Correction source is newer than bitstream'" not in text:
        sources=['board/corrected_video.v','board/corrected_video.fdc','board/build-corrected_video.tcl','board/calibration-trial.vh']+[f'rtl/{m}.v' for m in modules]
        paths=','.join("'"+v.replace('/', '\\')+"'" for v in sources)
        text=text.replace("    if($Target -eq 'camera_diag') {",f"    if($Target -eq 'corrected_video') {{\n        foreach($src in @({paths})) {{\n            if((Get-Item (Join-Path $projectRoot $src)).LastWriteTime -gt $bitFile.LastWriteTime){{throw 'Correction source is newer than bitstream'}}\n        }}\n    }}\n    if($Target -eq 'camera_diag') {{")
    p.write_text(text,encoding='utf-8-sig')
print(f'Prepared corrected_video: source bank0/result banks1,2, staged arithmetic coefficients, coherent diagnostics {i+2} bytes.')
