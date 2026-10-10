"""Separate frozen raw/corrected pair export for actual-board pixel validation."""
from pathlib import Path
import re
root=Path(__file__).resolve().parents[1];board=root/'board'
t=(board/'calibration_capture.v').read_text().replace('module calibration_capture(', 'module corrected_capture(')
start=t.index('    wire [9:0] fifo_available;');end=t.index('        ddr3_test u_ddr3_test_h',start)
t=t[:start]+'''    `include "D:/English/FPGA/distortion/board/calibration-trial.vh"
    wire verify_failed;wire [7:0] verify_fault;wire [31:0] pairs_completed;
    wire serial_valid,serial_ready,serial_done,serial_busy;wire [7:0] serial_data;
    ddr_corrected_capture pipeline(.cam_clk(cam_pclk),.core_clk(core_clk),.rst_n(ddr_reset_sync[1]),.ready(store_arm),
        .vsync(!cam_vsync),.href(!cam_href),.data(cam_data),
        .cfg_out_cx(CAL_OUT_CX),.cfg_out_cy(CAL_OUT_CY),.cfg_src_cx(CAL_SRC_CX),.cfg_src_cy(CAL_SRC_CY),
        .cfg_src_fx(CAL_SRC_FX),.cfg_src_fy(CAL_SRC_FY),.cfg_inv_fx(CAL_INV_FX),.cfg_inv_fy(CAL_INV_FY),
        .cfg_k1(CAL_K1),.cfg_k2(CAL_K2),.cfg_k3(CAL_K3),.cfg_p1(CAL_P1),.cfg_p2(CAL_P2),
        .awaddr(axi_awaddr),.awlen(axi_awlen),.awvalid(axi_awvalid),.awready(axi_awready),
        .wdata(axi_wdata),.wstrb(axi_wstrb),.wready(axi_wready),.wlast(axi_wusero_last),
        .araddr(axi_araddr),.arlen(axi_arlen),.arvalid(axi_arvalid),.arready(axi_arready),
        .rdata(axi_rdata),.rvalid(axi_rvalid),.rlast(axi_rlast),.rid(axi_rid),
        .byte_valid(serial_valid),.byte_ready(serial_ready),.byte_done(serial_done),.byte_data(serial_data),
        .failed(verify_failed),.fault(verify_fault),.pairs_completed(pairs_completed));
    uart_tx #(.CLOCK_HZ(125000000),.BAUD(921600)) serial(.clk(core_clk),.rst_n(ddr_reset_sync[1]),
        .start(serial_valid && serial_ready),.data(serial_data),.tx(uart_txd),.busy(serial_busy),.done(serial_done));
    assign serial_ready=!serial_busy;
''' +t[end:]
t=t.replace('export_failed || test_failed','verify_failed')
(board/'corrected_capture.v').write_text(t)
for suffix in ('.fdc','-pins.json'):
    (board/('corrected_capture'+suffix)).write_text((board/('calibration_capture'+suffix)).read_text())
modules=('ddr_corrected_capture','remap_frame_engine','ddr_result_writer','brown_remap_core','brown_inverse_mapper','mul32_pipe','ddr_remap_sample','ddr_neighbour_cache','bilinear_rgb')
b=(board/'build-calibration_capture.tcl').read_text().replace('calibration_capture','corrected_capture')
b='\n'.join(f'add_design {{D:/English/FPGA/distortion/rtl/{n}.v}}' for n in modules)+'\n'+b
(board/'build-corrected_capture.tcl').write_text(b)
(board/'program-corrected_capture.tcl').write_text((board/'program-calibration_capture.tcl').read_text().replace('calibration_capture','corrected_capture'))
for name in ('build-pds.ps1','program-heartbeat.ps1'):
    p=root/'tools'/name;s=p.read_text(encoding='utf-8-sig')
    s=re.sub(r"(?:@|ValidateSet)\(([^)\n]*'calibration_capture'[^)\n]*)\)",lambda m:m[0] if "'corrected_capture'" in m[0] else m[0][:-1]+",'corrected_capture')",s)
    if name=='build-pds.ps1' and "throw 'Corrected capture source is newer than bitstream'" not in s:
        srcs=['board/corrected_capture.v','board/corrected_capture.fdc','board/build-corrected_capture.tcl','board/calibration-trial.vh','rtl/ddr_uart_frame.v']+[f'rtl/{n}.v' for n in modules]
        paths=','.join("'"+v.replace('/','\\')+"'" for v in srcs)
        s=s.replace("    if($Target -eq 'camera_diag') {",f"    if($Target -eq 'corrected_capture') {{\n        foreach($src in @({paths})) {{\n            if((Get-Item (Join-Path $projectRoot $src)).LastWriteTime -gt $bitFile.LastWriteTime){{throw 'Corrected capture source is newer than bitstream'}}\n        }}\n    }}\n    if($Target -eq 'camera_diag') {{")
    p.write_text(s,encoding='utf-8-sig')
print('Prepared corrected_capture: two immutable native frames exported as even raw / odd corrected IDs, SRAM-only target.')
