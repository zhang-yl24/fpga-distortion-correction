`timescale 1ns/1ps
// This is the Pango DDR IP's AW + WREADY/WLAST interface, not generic AXI:
// the IP requests each write beat and has no application B response port.
// Select whole bursts fairly and never interleave their write data.
module ddr_write_arbiter #(parameter TIMEOUT_BITS=26)(
    input clk,rst_n,
    input [27:0] c0_awaddr,c1_awaddr,input [3:0] c0_awlen,c1_awlen,
    input c0_awvalid,c1_awvalid,output c0_awready,c1_awready,
    input [255:0] c0_wdata,c1_wdata,input [31:0] c0_wstrb,c1_wstrb,
    output c0_wready,c1_wready,c0_wlast,c1_wlast,
    output [27:0] awaddr,output [3:0] awlen,output awvalid,input awready,
    output [255:0] wdata,output [31:0] wstrb,input wready,wlast,
    output reg failed,output reg [7:0] fault,output busy,
    output reg [31:0] bursts0,bursts1
);
    localparam IDLE=0,ADDRESS=1,WRITE=2,FAULT=3;
    reg [1:0] state;reg owner,last_owner;reg [27:0] address;
    reg [3:0] length,beat;reg [TIMEOUT_BITS-1:0] watchdog;
    wire choose1=c1_awvalid && (!c0_awvalid || !last_owner);
    wire accepted=state==ADDRESS && awready;
    wire transfer=(state==WRITE || accepted) && !failed;
    assign busy=state!=IDLE || failed;
    assign awaddr=address;assign awlen=length;assign awvalid=state==ADDRESS;
    assign c0_awready=accepted && !owner && !failed;
    assign c1_awready=accepted && owner && !failed;
    assign wdata=owner ? c1_wdata:c0_wdata;assign wstrb=owner ? c1_wstrb:c0_wstrb;
    assign c0_wready=transfer && !owner && wready;
    assign c1_wready=transfer && owner && wready;
    assign c0_wlast=wlast;assign c1_wlast=wlast;
    always @(posedge clk) begin
        if(!rst_n) begin
            state<=IDLE;owner<=0;last_owner<=1;address<=0;length<=0;beat<=0;
            watchdog<=0;failed<=0;fault<=0;bursts0<=0;bursts1<=0;
        end else begin
            if(state==WRITE && !wready) watchdog<=watchdog+1'b1;else watchdog<=0;
            case(state)
                IDLE: if(c0_awvalid || c1_awvalid) begin
                    owner<=choose1;address<=choose1 ? c1_awaddr:c0_awaddr;
                    length<=choose1 ? c1_awlen:c0_awlen;beat<=0;state<=ADDRESS;
                end
                ADDRESS: if(awready) state<=failed ? FAULT:WRITE;
                WRITE: if(&watchdog && !wready) begin failed<=1;fault<=8'h01;state<=FAULT;end
                FAULT: state<=FAULT;
            endcase
            if(transfer && wready) begin
                if(wlast!=(beat==length)) begin failed<=1;fault<=8'h02;state<=FAULT;end
                else if(beat==length) begin
                    state<=IDLE;last_owner<=owner;
                    if(owner) bursts1<=bursts1+1'b1;else bursts0<=bursts0+1'b1;
                end else beat<=beat+1'b1;
            end else if(wready && !failed) begin
                failed<=1;fault<=8'h04;
                if(state!=ADDRESS || awready) state<=FAULT;
            end
        end
    end
endmodule
