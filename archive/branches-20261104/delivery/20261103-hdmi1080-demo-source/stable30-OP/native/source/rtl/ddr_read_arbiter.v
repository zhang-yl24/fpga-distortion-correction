`timescale 1ns/1ps
// Two clients of the board's ID=0, unbackpressurable DDR read interface.
// Each client reserves its entire burst before asserting ARVALID. A grant
// lasts through every response beat; timeout/protocol failures quarantine
// the bus until the parent resets the complete DDR transaction domain.
module ddr_read_arbiter #(parameter TIMEOUT_BITS=26)(
    input clk,rst_n,input display_urgent,
    input [27:0] c0_araddr,c1_araddr,input [3:0] c0_arlen,c1_arlen,
    input c0_arvalid,c1_arvalid,output c0_arready,c1_arready,
    output [255:0] c0_rdata,c1_rdata,output c0_rvalid,c1_rvalid,
    output c0_rlast,c1_rlast,output [3:0] c0_rid,c1_rid,
    output [27:0] araddr,output [3:0] arlen,output arvalid,input arready,
    input [255:0] rdata,input rvalid,rlast,input [3:0] rid,
    output reg failed,output reg [7:0] fault,output busy,
    output reg [31:0] bursts0,bursts1
);
    localparam IDLE=0,ADDRESS=1,READ=2,FAULT=3;
    reg [1:0] state;reg owner,last_owner;reg [27:0] address;
    reg [3:0] length,beat;reg [TIMEOUT_BITS-1:0] watchdog;
    wire choose1=c1_arvalid && (!c0_arvalid || (!display_urgent && !last_owner));
    wire accepted=state==ADDRESS && arready;
    wire response=(state==READ || accepted) && !failed;
    assign busy=state!=IDLE || failed;
    assign araddr=address;assign arlen=length;assign arvalid=state==ADDRESS;
    assign c0_arready=accepted && !owner && !failed;
    assign c1_arready=accepted && owner && !failed;
    assign c0_rdata=rdata;assign c1_rdata=rdata;
    assign c0_rvalid=response && !owner && rvalid;
    assign c1_rvalid=response && owner && rvalid;
    assign c0_rlast=rlast;assign c1_rlast=rlast;
    assign c0_rid=rid;assign c1_rid=rid;
    always @(posedge clk) begin
        if(!rst_n) begin
            state<=IDLE;owner<=0;last_owner<=1;address<=0;length<=0;beat<=0;
            watchdog<=0;failed<=0;fault<=0;bursts0<=0;bursts1<=0;
        end else begin
            if(state==READ && !rvalid) watchdog<=watchdog+1'b1;else watchdog<=0;
            case(state)
                IDLE: if(c0_arvalid || c1_arvalid) begin
                    owner<=choose1;address<=choose1 ? c1_araddr:c0_araddr;
                    length<=choose1 ? c1_arlen:c0_arlen;beat<=0;state<=ADDRESS;
                end
                ADDRESS: if(arready) state<=failed ? FAULT:READ;
                READ: if(&watchdog && !rvalid) begin failed<=1;fault<=8'h01;state<=FAULT;end
                FAULT: state<=FAULT;
            endcase
            if(response && rvalid) begin
                if(rid!=0 || rlast!=(beat==length)) begin failed<=1;fault<=8'h03;state<=FAULT;end
                else if(beat==length) begin
                    state<=IDLE;last_owner<=owner;
                    if(owner) bursts1<=bursts1+1'b1;else bursts0<=bursts0+1'b1;
                end else beat<=beat+1'b1;
            end else if(rvalid && !failed) begin
                failed<=1;fault<=8'h04;
                // Once visible on the bus, ARVALID cannot be withdrawn. Hold
                // the saved command through acceptance, then quarantine it.
                if(state!=ADDRESS || arready) state<=FAULT;
            end
        end
    end
endmodule
