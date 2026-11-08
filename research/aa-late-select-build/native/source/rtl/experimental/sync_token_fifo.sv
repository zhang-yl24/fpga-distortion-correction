`timescale 1ns/1ps
// Single-clock, synchronous-read token FIFO with two elastic read registers.
// All payload accesses are clocked; no asynchronous BRAM peek is required.
// total includes RAM and both read stages. Ready depends only on occupancy.
module sync_token_fifo #(parameter WIDTH=73,DEPTH=256)(
    input clk,rst_n,clear,
    input in_valid,output wire in_ready,input [WIDTH-1:0] in_data,
    output wire out_valid,input out_ready,output wire [WIDTH-1:0] out_data,
    output wire empty
);
    localparam AW=$clog2(DEPTH),CW=AW+1;
    (* ram_style="block" *) reg [WIDTH-1:0] mem[0:DEPTH-1];
    reg [AW-1:0] rp,wp;
    reg [CW-1:0] total,ram_count;
    reg v0,v1;
    reg [WIDTH-1:0] ram_q,data1;
    wire ready1=!v1 || out_ready,ready0=!v0 || ready1;
    assign in_ready=total<DEPTH;
    assign out_valid=v1;
    assign out_data=data1;
    assign empty=total==0;
    wire push=in_valid && in_ready;
    wire pop=out_valid && out_ready;
    wire fetch=ram_count!=0 && ready0;
    always @(posedge clk)begin
        if(rst_n && !clear)begin
            if(push)mem[wp]<=in_data;
            if(fetch)ram_q<=mem[rp];
        end
    end
    always @(posedge clk)begin
        if(!rst_n || clear)begin rp<=0;wp<=0;total<=0;ram_count<=0;v0<=0;v1<=0;end
        else begin
            case({push,pop})
                2'b10:total<=total+1'b1;
                2'b01:total<=total-1'b1;
                default:total<=total;
            endcase
            case({push,fetch})
                2'b10:ram_count<=ram_count+1'b1;
                2'b01:ram_count<=ram_count-1'b1;
                default:ram_count<=ram_count;
            endcase
            if(push)wp<=wp+1'b1;
            if(fetch)rp<=rp+1'b1;
            if(ready0)v0<=fetch;
            if(ready1)begin v1<=v0;if(v0)data1<=ram_q;end
        end
    end
endmodule
