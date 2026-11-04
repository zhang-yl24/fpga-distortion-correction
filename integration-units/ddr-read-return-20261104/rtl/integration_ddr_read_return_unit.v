`timescale 1ns/1ps
// ISOLATED SOURCE-ONLY UNIT. Not selected by any FPGA board build.
// Both blocks share one transaction-domain reset. No implicit running reset,
// request gating, AR withdrawal, RREADY or CDC is introduced here.
module integration_ddr_read_return_unit #(parameter TIMEOUT_BITS=26)(
    input clk,rst_n,display_urgent,
    input [27:0] c0_araddr,c1_araddr,input [3:0] c0_arlen,c1_arlen,
    input c0_arvalid,c1_arvalid,output c0_arready,c1_arready,
    output [255:0] c0_rdata,c1_rdata,output c0_rvalid,c1_rvalid,
    output c0_rlast,c1_rlast,output [3:0] c0_rid,c1_rid,
    output [27:0] araddr,output [3:0] arlen,output arvalid,input arready,
    input [255:0] rdata,input rvalid,rlast,input [3:0] rid,
    output failed,output [7:0] fault,output busy,
    output arbiter_failed,return_protocol_fault,
    output [7:0] arbiter_fault,return_fault,
    output [31:0] bursts0,bursts1
);
    wire [255:0] registered_rdata;
    wire registered_rvalid,registered_rlast;
    wire [3:0] registered_rid;
    ddr_read_return_register return_stage(
        .clk(clk),.rst_n(rst_n),.arvalid(arvalid),.arready(arready),
        .in_rdata(rdata),.in_rvalid(rvalid),.in_rlast(rlast),.in_rid(rid),
        .out_rdata(registered_rdata),.out_rvalid(registered_rvalid),
        .out_rlast(registered_rlast),.out_rid(registered_rid),
        .protocol_fault(return_protocol_fault),.fault_code(return_fault));
    ddr_read_arbiter #(.TIMEOUT_BITS(TIMEOUT_BITS)) read_arbiter(
        .clk(clk),.rst_n(rst_n),.display_urgent(display_urgent),
        .c0_araddr(c0_araddr),.c1_araddr(c1_araddr),.c0_arlen(c0_arlen),.c1_arlen(c1_arlen),
        .c0_arvalid(c0_arvalid),.c1_arvalid(c1_arvalid),.c0_arready(c0_arready),.c1_arready(c1_arready),
        .c0_rdata(c0_rdata),.c1_rdata(c1_rdata),.c0_rvalid(c0_rvalid),.c1_rvalid(c1_rvalid),
        .c0_rlast(c0_rlast),.c1_rlast(c1_rlast),.c0_rid(c0_rid),.c1_rid(c1_rid),
        .araddr(araddr),.arlen(arlen),.arvalid(arvalid),.arready(arready),
        .rdata(registered_rdata),.rvalid(registered_rvalid),.rlast(registered_rlast),.rid(registered_rid),
        .failed(arbiter_failed),.fault(arbiter_fault),.busy(busy),.bursts0(bursts0),.bursts1(bursts1));
    // Preserve the original published integration bench's arbiter-first code.
    // Both independent flags/codes remain visible if both faults are asserted.
    assign failed=arbiter_failed || return_protocol_fault;
    assign fault=arbiter_failed ? arbiter_fault:return_fault;
endmodule
