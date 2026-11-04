`timescale 1ns/1ps
// One outstanding held bundle, acknowledged only by the physical consumer's
// completion. s_done cannot be an old UART stop event for a newly queued byte.
module held_completion_cdc #(parameter WIDTH=8)(
    input s_clk,d_clk,rst_n,input s_valid,output s_ready,
    input [WIDTH-1:0] s_data,output reg s_done,output s_idle,
    output d_valid,input d_done,output [WIDTH-1:0] d_data
);
    wire raw_ready;reg outstanding,saw_busy;
    assign s_ready=raw_ready && !outstanding;
    assign s_idle=raw_ready && !outstanding;
    held_bundle_cdc #(.WIDTH(WIDTH)) held(
        .s_clk(s_clk),.d_clk(d_clk),.rst_n(rst_n),
        .s_valid(s_valid && !outstanding),.s_ready(raw_ready),.s_data(s_data),
        .d_valid(d_valid),.d_ready(d_done),.d_data(d_data));
    always @(posedge s_clk or negedge rst_n) begin
        if(!rst_n) begin outstanding<=0;saw_busy<=0;s_done<=0;end
        else begin
            s_done<=0;
            if(s_valid && s_ready)begin outstanding<=1;saw_busy<=0;end
            if(outstanding && !raw_ready)saw_busy<=1;
            if(outstanding && saw_busy && raw_ready)begin outstanding<=0;saw_busy<=0;s_done<=1;end
        end
    end
endmodule

