// Explicit isolated opt-in. Else branch is the byte-identical baseline source.
`ifdef EXPERIMENTAL_DUAL_READ_CREDIT
`timescale 1ns/1ps
// EXPERIMENTAL. Two accepted ID0 bursts, ordered unbackpressurable returns.
// A client reserves its entire burst before asserting valid. The pending AR
// is a held selection, never an accepted third credit. No replay after fault.
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
    reg address_pending,address_exposed,pending_owner,last_owner;
    reg [27:0] address;
    reg [3:0] length,beat;
    reg [1:0] outstanding;
    reg rp,wp;
    reg owners[0:1];reg [3:0] lengths[0:1];
    reg [TIMEOUT_BITS-1:0] watchdog;
    wire choose1=c1_arvalid && (!c0_arvalid || (!display_urgent && !last_owner));
    wire head_final=rvalid && outstanding!=0 && rid==0 &&
        rlast && beat==lengths[rp];
    // A valid last beat releases one response reservation on this edge.
    // If this exposes AR and ARREADY is low, the pop makes capacity permanent.
    wire capacity=outstanding<2 || head_final;
    assign arvalid=address_pending && (address_exposed || (!failed && capacity));
    assign araddr=address;assign arlen=length;
    wire accepted=arvalid && arready;
    wire response_known=outstanding!=0 || accepted;
    wire owner=outstanding!=0 ? owners[rp]:pending_owner;
    wire [3:0] response_length=outstanding!=0 ? lengths[rp]:length;
    wire [3:0] response_beat=outstanding!=0 ? beat:4'd0;
    wire bad_return=rvalid && (!response_known || rid!=0 || rlast!=(response_beat==response_length));
    wire response=response_known && !failed && !bad_return;
    wire push=accepted && !failed && !bad_return;
    wire pop=response && rvalid && rlast;
    assign c0_arready=push && !pending_owner;
    assign c1_arready=push && pending_owner;
    assign c0_rdata=rdata;assign c1_rdata=rdata;
    assign c0_rvalid=response && !owner && rvalid;
    assign c1_rvalid=response && owner && rvalid;
    assign c0_rlast=rlast;assign c1_rlast=rlast;
    assign c0_rid=rid;assign c1_rid=rid;
    assign busy=failed || address_pending || outstanding!=0;
    // Diagnostic compatibility only; response ownership always uses the FIFO.
    wire [1:0] state=failed ? 2'd3:(arvalid ? 2'd1:(outstanding!=0 ? 2'd2:2'd0));
    always @(posedge clk)begin
        if(!rst_n)begin
            address_pending<=0;address_exposed<=0;pending_owner<=0;last_owner<=1;
            address<=0;length<=0;beat<=0;outstanding<=0;rp<=0;wp<=0;
            owners[0]<=0;owners[1]<=0;lengths[0]<=0;lengths[1]<=0;
            watchdog<=0;failed<=0;fault<=0;bursts0<=0;bursts1<=0;
        end else begin
            if(arvalid)address_exposed<=1;
            if(accepted)begin address_pending<=0;address_exposed<=0;end
            if(!failed)begin
                if(!address_pending && (c0_arvalid || c1_arvalid))begin
                    address_pending<=1;pending_owner<=choose1;
                    address<=choose1 ? c1_araddr:c0_araddr;
                    length<=choose1 ? c1_arlen:c0_arlen;
                end
                if(push)begin
                    owners[wp]<=pending_owner;lengths[wp]<=length;wp<=!wp;
                    last_owner<=pending_owner;
                end
                if(pop)begin
                    rp<=!rp;beat<=0;
                    if(owner)bursts1<=bursts1+1'b1;else bursts0<=bursts0+1'b1;
                end else if(response && rvalid)beat<=response_beat+1'b1;
                case({push,pop})
                    2'b10:outstanding<=outstanding+1'b1;
                    2'b01:outstanding<=outstanding-1'b1;
                    default:outstanding<=outstanding;
                endcase
                if(accepted || (response && rvalid) || (!address_pending && outstanding==0))watchdog<=0;
                else watchdog<=watchdog+1'b1;
                if(bad_return)begin failed<=1;fault<=response_known ? 8'h03:8'h04;end
                else if(&watchdog && !accepted && !(response && rvalid) &&
                    (address_pending || outstanding!=0))begin failed<=1;fault<=8'h01;end
            end
        end
    end
endmodule

`else
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

`endif
