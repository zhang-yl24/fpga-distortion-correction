`timescale 1ns/1ps
// Single outstanding held-bundle crossing. Both endpoints require COMMON reset.
// Physical data settle/max-delay and CDC constraints still need implementation QA.
module held_bundle_cdc #(parameter integer WIDTH=64)(
    input wire s_clk,d_clk,rst_n,
    input wire s_valid,output wire s_ready,input wire [WIDTH-1:0] s_data,
    output reg d_valid,input wire d_ready,output reg [WIDTH-1:0] d_data
);
    (* PAP_ASYNC_REG=1 *) reg [1:0] s_release=0,d_release=0,ack_sync=0,request_sync=0;
    reg request_toggle,ack_toggle;
    reg [WIDTH-1:0] held;
    assign s_ready=s_release[1] && request_toggle==ack_sync[1];
    always @(posedge s_clk or negedge rst_n)
        if(!rst_n)s_release<=0;else s_release<={s_release[0],1'b1};
    always @(posedge d_clk or negedge rst_n)
        if(!rst_n)d_release<=0;else d_release<={d_release[0],1'b1};
    always @(posedge s_clk or negedge rst_n)begin
        if(!rst_n)begin ack_sync<=0;request_toggle<=0;held<=0;end
        else if(!s_release[1])begin ack_sync<=0;request_toggle<=0;held<=0;end
        else begin
            ack_sync<={ack_sync[0],ack_toggle};
            if(s_valid && s_ready)begin held<=s_data;request_toggle<=!request_toggle;end
        end
    end
    always @(posedge d_clk or negedge rst_n)begin
        if(!rst_n)begin request_sync<=0;ack_toggle<=0;d_valid<=0;d_data<=0;end
        else if(!d_release[1])begin request_sync<=0;ack_toggle<=0;d_valid<=0;d_data<=0;end
        else begin
            request_sync<={request_sync[0],request_toggle};
            if(!d_valid && request_sync[1]!=ack_toggle)begin d_data<=held;d_valid<=1;end
            if(d_valid && d_ready)begin d_valid<=0;ack_toggle<=request_sync[1];end
        end
    end
endmodule
