`timescale 1ns/1ps
// Exact signed 32x32 product. Three enabled cycles; all stages freeze together.
// Split partial products avoid a combinational cascade of four DSP blocks.
module mul32_pipe(input clk,ce,input signed [31:0] a,b,output reg signed [63:0] p);
    reg [31:0] ll;
    reg signed [32:0] lh,hl;
    reg signed [31:0] hh,hh1;
    reg signed [34:0] middle;
    reg [15:0] low;
    wire signed [34:0] middle_sum=$signed({{2{lh[32]}},lh})+$signed({{2{hl[32]}},hl})+$signed({19'd0,ll[31:16]});
    wire signed [47:0] upper=($signed({{16{hh1[31]}},hh1})<<<16)+$signed({{13{middle[34]}},middle});
    always @(posedge clk) if(ce) begin
        ll<=a[15:0]*b[15:0];
        lh<=$signed({1'b0,a[15:0]})*$signed(b[31:16]);
        hl<=$signed(a[31:16])*$signed({1'b0,b[15:0]});
        hh<=$signed(a[31:16])*$signed(b[31:16]);
        middle<=middle_sum;low<=ll[15:0];hh1<=hh;
        p<={upper,low};
    end
endmodule

