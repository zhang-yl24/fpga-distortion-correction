`timescale 1ns/1ps
// Independent input/core interface link; existing signed core is unchanged.
// core_* is the lens1080_bank_core source handshake plus its result writer.
// This module DOES NOT instantiate the mapper/display/HDMI chip controller.
// All AW addresses are 4-byte units. Shared writes use whole-burst arbitration.
module hdmi1080_input_write_link #(
    parameter WIDTH=1920,HEIGHT=1080,BANK_STRIDE=1048576,FIFO_ADDR_BITS=6
)(
    input pix_clk,sys_clk,rst_n,enable,
    input pix_vsync_active,pix_de,input [23:0] pix_rgb,
    input [2:0] core_source_writable,
    input core_source_released,input [1:0] core_released_bank,
    output core_source_valid,input core_source_ready,output [1:0] core_source_bank,
    output [31:0] core_source_id,source_crc,source_pixels,
    output [2:0] capture_reserved,
    input core_failed,input [7:0] core_fault,
    input [27:0] core_awaddr,input [3:0] core_awlen,
    input core_awvalid,output core_awready,
    input [255:0] core_wdata,input [31:0] core_wstrb,
    output core_wready,core_wlast,
    output [27:0] awaddr,output [3:0] awlen,
    output awvalid,input awready,
    output [255:0] wdata,output [31:0] wstrb,input wready,wlast,
    output failed,output [7:0] fault,output write_busy,
    output [31:0] capture_bursts,result_bursts,
    output [31:0] accepted_frames,dropped_frames,overflow_frames,no_free_frames,
    output [7:0] last_drop_fault
);
    wire input_failed,arb_failed;
    wire [7:0] input_fault,arb_fault;
    reg contract_failed;
    wire dma_valid,dma_ready;wire [1:0] dma_bank;
    wire [31:0] dma_id;
    wire [27:0] dma_awaddr;wire [3:0] dma_awlen;
    wire dma_awvalid,dma_awready,dma_wready,dma_wlast;
    wire [255:0] dma_wdata;wire [31:0] dma_wstrb;
    wire input_write_active;
    wire complete_metadata=dma_bank<3 && source_pixels==WIDTH*HEIGHT && capture_reserved[dma_bank];
    assign failed=contract_failed || input_failed || arb_failed || core_failed;
    assign fault=arb_failed ? arb_fault:input_failed ? input_fault:
        contract_failed ? 8'h91:core_failed ? core_fault:8'h00;
    assign core_source_valid=dma_valid && complete_metadata && !failed;
    assign dma_ready=core_source_ready && complete_metadata && !failed;
    assign core_source_bank=dma_bank;assign core_source_id=dma_id;
    always @(posedge sys_clk or negedge rst_n)
        if(!rst_n)contract_failed<=0;
        else if(dma_valid && !complete_metadata)contract_failed<=1;

    hdmi1080_input_dma #(.WIDTH(WIDTH),.HEIGHT(HEIGHT),.BANK_STRIDE(BANK_STRIDE),
        .FIFO_ADDR_BITS(FIFO_ADDR_BITS)) input_dma(
        .pix_clk(pix_clk),.sys_clk(sys_clk),.rst_n(rst_n),.enable(enable && !failed),
        .pix_vsync_active(pix_vsync_active),.pix_de(pix_de),.pix_rgb(pix_rgb),
        .source_writable(core_source_writable),.source_released(core_source_released),
        .released_bank(core_released_bank),.source_valid(dma_valid),.source_ready(dma_ready),
        .source_bank(dma_bank),.source_id(dma_id),.source_crc(source_crc),.source_pixels(source_pixels),
        .capture_reserved(capture_reserved),.awaddr(dma_awaddr),.awlen(dma_awlen),
        .awvalid(dma_awvalid),.awready(dma_awready),.wdata(dma_wdata),.wstrb(dma_wstrb),
        .wready(dma_wready),.wlast(dma_wlast),.write_active(input_write_active),
        .failed(input_failed),.fault(input_fault),.accepted_frames(accepted_frames),
        .dropped_frames(dropped_frames),.overflow_frames(overflow_frames),
        .no_free_frames(no_free_frames),.last_drop_fault(last_drop_fault));
    // Do not gate/withdraw an issued AW or W on a new admission fault.
    // The unmodified arbiter holds its owner/address and routes WREADY/WLAST.
    ddr_write_arbiter shared_writes(
        .clk(sys_clk),.rst_n(rst_n),
        .c0_awaddr(dma_awaddr),.c0_awlen(dma_awlen),.c0_awvalid(dma_awvalid),.c0_awready(dma_awready),
        .c0_wdata(dma_wdata),.c0_wstrb(dma_wstrb),.c0_wready(dma_wready),.c0_wlast(dma_wlast),
        .c1_awaddr(core_awaddr),.c1_awlen(core_awlen),.c1_awvalid(core_awvalid),.c1_awready(core_awready),
        .c1_wdata(core_wdata),.c1_wstrb(core_wstrb),.c1_wready(core_wready),.c1_wlast(core_wlast),
        .awaddr(awaddr),.awlen(awlen),.awvalid(awvalid),.awready(awready),
        .wdata(wdata),.wstrb(wstrb),.wready(wready),.wlast(wlast),
        .failed(arb_failed),.fault(arb_fault),.busy(write_busy),
        .bursts0(capture_bursts),.bursts1(result_bursts));
endmodule
