`timescale 1ns/1ps
// One-clock boundary for the unbackpressurable single-outstanding DDR return.
// Transaction-domain reset covers DDR, this stage, arbiter and clients together.
// The raw owner guard preserves unsolicited-return detection before latency is
// added. Its sticky error is connected to the system external-fault input;
// it must never trigger an implicit running reset or withdraw an accepted AR.
module ddr_read_return_register(
    input clk,rst_n,
    input arvalid,arready,
    input [255:0] in_rdata,input in_rvalid,in_rlast,input [3:0] in_rid,
    output reg [255:0] out_rdata,output reg out_rvalid,out_rlast,output reg [3:0] out_rid,
    output reg protocol_fault,output reg [7:0] fault_code
);
    reg raw_reserved;
    wire accept_address=arvalid && arready;
    wire response_owned=raw_reserved || accept_address;
    wire unsolicited=in_rvalid && !response_owned;
    wire overlapping_address=accept_address && raw_reserved && !(in_rvalid && in_rlast);
    // Payload registers have no reset or enable mux. Valid qualifies the bundle.
    always @(posedge clk)begin
        out_rdata<=in_rdata;out_rlast<=in_rlast;out_rid<=in_rid;
        if(!rst_n)begin
            out_rvalid<=0;raw_reserved<=0;protocol_fault<=0;fault_code<=0;
        end else begin
            out_rvalid<=in_rvalid && response_owned && !protocol_fault && !overlapping_address;
            if(accept_address)raw_reserved<=1;
            if(in_rvalid && in_rlast && response_owned)
                raw_reserved<=raw_reserved && accept_address;
            if(!protocol_fault)begin
                if(unsolicited)begin protocol_fault<=1;fault_code<=8'h40;end
                else if(overlapping_address)begin protocol_fault<=1;fault_code<=8'h41;end
            end
        end
    end
endmodule
