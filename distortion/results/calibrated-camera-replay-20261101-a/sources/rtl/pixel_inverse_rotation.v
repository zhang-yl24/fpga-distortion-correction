`timescale 1ns/1ps
// Output-to-input 2D rotation before camera projection, no image resampling.
// Pixel Q15.8, sine/cosine Q2.30; round nearest with ties toward +infinity.
// Six enabled stages; cfg handshake requires the previous frame to drain.
module pixel_inverse_rotation #(parameter TAG_W=24)(
    input clk,rst,input cfg_valid,output cfg_ready,
    input signed [23:0] cfg_cx,cfg_cy,
    input signed [31:0] cfg_cos,cfg_sin,
    input in_valid,output in_ready,input signed [23:0] in_u,in_v,input [TAG_W-1:0] in_tag,
    output out_valid,input out_ready,output signed [23:0] out_u,out_v,
    output out_black,output [TAG_W-1:0] out_tag
);
    reg configured;
    reg signed [23:0] cx,cy;
    reg signed [31:0] cosine,sine,du,dv;
    reg [5:0] valid;
    reg [TAG_W-1:0] tags[0:5];
    wire advance=!valid[5] || out_ready;
    assign cfg_ready=!rst && !(|valid);
    assign in_ready=!rst && configured && advance && !cfg_valid;
    assign out_valid=valid[5];assign out_tag=tags[5];
    wire signed [63:0] cdu,sdv,sdu,cdv;
    mul32_pipe m0(.clk(clk),.ce(advance),.a(du),.b(cosine),.p(cdu));
    mul32_pipe m1(.clk(clk),.ce(advance),.a(dv),.b(sine),.p(sdv));
    mul32_pipe m2(.clk(clk),.ce(advance),.a(du),.b(sine),.p(sdu));
    mul32_pipe m3(.clk(clk),.ce(advance),.a(dv),.b(cosine),.p(cdv));
    reg signed [64:0] sum_u,sum_v;
    function signed [64:0] wide(input signed [63:0] n);wide=n;endfunction
    function signed [31:0] pixel32(input signed [23:0] n);pixel32=n;endfunction
    wire signed [64:0] rounded_u=(sum_u>>>30)+$signed({1'b0,sum_u[29]})+pixel32(cx);
    wire signed [64:0] rounded_v=(sum_v>>>30)+$signed({1'b0,sum_v[29]})+pixel32(cy);
    wire overflow_u=rounded_u[64:23]!={42{rounded_u[23]}};
    wire overflow_v=rounded_v[64:23]!={42{rounded_v[23]}};
    reg black;
    reg signed [23:0] result_u,result_v;
    assign out_black=black;
    assign out_u=black ? 24'sh800000:result_u;
    assign out_v=black ? 24'sh800000:result_v;
    integer i;
    always @(posedge clk) begin
        if(rst) begin configured<=0;valid<=0;black<=0;end
        else begin
            if(cfg_valid && cfg_ready) begin
                cx<=cfg_cx;cy<=cfg_cy;cosine<=cfg_cos;sine<=cfg_sin;configured<=1;
            end
            if(advance) begin
                valid<={valid[4:0],in_valid && in_ready};
                tags[0]<=in_tag;
                for(i=1;i<6;i=i+1) tags[i]<=tags[i-1];
                du<=pixel32(in_u)-pixel32(cx);dv<=pixel32(in_v)-pixel32(cy);
                sum_u<=wide(cdu)+wide(sdv);sum_v<=-wide(sdu)+wide(cdv);
                result_u<=rounded_u[23:0];result_v<=rounded_v[23:0];
                black<=overflow_u || overflow_v;
            end
        end
    end
endmodule
