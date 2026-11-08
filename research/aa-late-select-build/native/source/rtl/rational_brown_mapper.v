`timescale 1ns/1ps
// Independent calibrated rational Brown + nonzero tangential experiment.
// Derived from 623e7a20 C pipeline structure; no active-source changes.
// 23 enabled stages, II=1; data, multipliers, ROM, tags freeze together.
// cfg_corrected is locked only after complete drain. Identity is bit-exact Q8.
module rational_brown_mapper #(
    parameter TAG_W=24
)(
    input clk,rst,input cfg_valid,output cfg_ready,input cfg_corrected,
    input in_black,in_valid,output in_ready,input signed [23:0] in_u,in_v,
    input [TAG_W-1:0] in_tag,
    output out_valid,input out_ready,output signed [23:0] out_x,out_y,
    output out_black,output [TAG_W-1:0] out_tag
);
    `include "source/profile/board/rational_brown_profile.vh"
    localparam signed [31:0] OCX=RATIONAL_OUT_CX;
    localparam signed [31:0] OCY=RATIONAL_OUT_CY;
    localparam signed [31:0] SCX=RATIONAL_SRC_CX;
    localparam signed [31:0] SCY=RATIONAL_SRC_CY;
    localparam signed [31:0] SFX=RATIONAL_SRC_FX;
    localparam signed [31:0] SFY=RATIONAL_SRC_FY;
    localparam signed [31:0] IFX=RATIONAL_INV_FX;
    localparam signed [31:0] IFY=RATIONAL_INV_FY;
    reg configured,corrected;
    reg [22:0] valid,black;
    reg [TAG_W-1:0] tags[0:22];
    reg signed [23:0] identity_x[0:22],identity_y[0:22];
    wire advance=!valid[22] || out_ready;
    assign cfg_ready=!rst && !(|valid);
    assign in_ready=!rst && configured && advance && !cfg_valid;
    assign out_valid=valid[22];assign out_black=black[22];assign out_tag=tags[22];
    assign out_x=out_black ? 24'sh800000:(corrected ? result_x:identity_x[22]);
    assign out_y=out_black ? 24'sh800000:(corrected ? result_y:identity_y[22]);
    function signed [64:0] widen(input signed [31:0] x);widen={{33{x[31]}},x};endfunction
    function signed [64:0] rounded(input signed [63:0] x,input integer bits);
        rounded=($signed({x[63],x})>>>bits)+$signed({64'd0,x[bits-1]});
    endfunction
    function overflow32(input signed [64:0] x);overflow32=x[64:31]!={34{x[31]}};endfunction
    function overflow24(input signed [64:0] x);overflow24=x[64:23]!={42{x[23]}};endfunction
    function signed [31:0] bounded32(input signed [64:0] x);
        bounded32=overflow32(x)?(x[64]?32'sh80000000:32'sh7fffffff):x[31:0];
    endfunction
    reg signed [31:0] du,dv,nx,ny,xx,yy,xy,r2,radial,xd,yd;
    reg signed [31:0] xy9,xy10,xx9,yy9,txf,tyf,tx,ty;
    reg signed [31:0] tx_delay[0:2],ty_delay[0:2];
    wire signed [63:0] square_xy_product,txa,txb,tya,tyb;
    wire signed [64:0] tx_sum=($signed({txa[63],txa})<<<1)+$signed({txb[63],txb});
    wire signed [64:0] ty_sum=$signed({tya[63],tya})+($signed({tyb[63],tyb})<<<1);
    function signed [64:0] rounded65(input signed [64:0] x,input integer bits);
        rounded65=(x>>>bits)+$signed({64'd0,x[bits-1]});
    endfunction
    wire signed [64:0] tx_next=rounded65(tx_sum,22),ty_next=rounded65(ty_sum,22);
    wire signed [64:0] xd_next=rounded(dist_x_product,30)+widen(tx_delay[2]);
    wire signed [64:0] yd_next=rounded(dist_y_product,30)+widen(ty_delay[2]);
    reg signed [31:0] nx_delay[0:9],ny_delay[0:9];
    wire signed [63:0] norm_x_product,norm_y_product,square_x_product,square_y_product;
    wire signed [63:0] interpolation_product,dist_x_product,dist_y_product,source_x_product,source_y_product;
    wire signed [64:0] r2_next=widen(xx)+widen(yy);
    wire [8:0] rom_address=r2<0 ? 9'd0:(r2>=33554432 ? 9'd511:r2[24:16]);
    wire [16:0] rom_fraction=r2<0 ? 17'd0:(r2>=33554432 ? 17'd65536:{1'b0,r2[15:0]});
    wire [31:0] rom_base;
    wire signed [31:0] rom_delta;
    reg [16:0] fraction;
    reg signed [31:0] base_delay[0:2];
    reg signed [23:0] result_x,result_y;
    wire signed [64:0] radial_next=widen(base_delay[2])+rounded(interpolation_product,16);
    wire signed [64:0] final_x=rounded(source_x_product,22)+widen(SCX);
    wire signed [64:0] final_y=rounded(source_y_product,22)+widen(SCY);
    mul32_pipe normalize_x(.clk(clk),.ce(advance),.a(du),.b(IFX),.p(norm_x_product));
    mul32_pipe normalize_y(.clk(clk),.ce(advance),.a(dv),.b(IFY),.p(norm_y_product));
    mul32_pipe square_x(.clk(clk),.ce(advance),.a(nx),.b(nx),.p(square_x_product));
    mul32_pipe square_y(.clk(clk),.ce(advance),.a(ny),.b(ny),.p(square_y_product));
    mul32_pipe square_xy(.clk(clk),.ce(advance),.a(nx),.b(ny),.p(square_xy_product));
    mul32_pipe tangential_xa(.clk(clk),.ce(advance),.a(RATIONAL_P1),.b(xy10),.p(txa));
    mul32_pipe tangential_xb(.clk(clk),.ce(advance),.a(RATIONAL_P2),.b(txf),.p(txb));
    mul32_pipe tangential_ya(.clk(clk),.ce(advance),.a(RATIONAL_P1),.b(tyf),.p(tya));
    mul32_pipe tangential_yb(.clk(clk),.ce(advance),.a(RATIONAL_P2),.b(xy10),.p(tyb));
    rational_brown_radial_rom radial_rom(.clk(clk),.ce(advance),.address(rom_address),.base_q30(rom_base),.delta_q30(rom_delta));
    mul32_pipe interpolate(.clk(clk),.ce(advance),.a(rom_delta),.b($signed({15'd0,fraction})),.p(interpolation_product));
    mul32_pipe distort_x(.clk(clk),.ce(advance),.a(nx_delay[9]),.b(radial),.p(dist_x_product));
    mul32_pipe distort_y(.clk(clk),.ce(advance),.a(ny_delay[9]),.b(radial),.p(dist_y_product));
    mul32_pipe source_x(.clk(clk),.ce(advance),.a(xd),.b(SFX),.p(source_x_product));
    mul32_pipe source_y(.clk(clk),.ce(advance),.a(yd),.b(SFY),.p(source_y_product));
    integer i;
    always @(posedge clk)begin
        if(rst)begin configured<=0;corrected<=0;valid<=0;black<=0;end
        else begin
            if(cfg_valid && cfg_ready)begin configured<=1;corrected<=cfg_corrected;end
            if(advance)begin
                valid<={valid[21:0],in_valid && in_ready};black<={black[21:0],in_black};
                tags[0]<=in_tag;identity_x[0]<=in_u;identity_y[0]<=in_v;
                for(i=1;i<23;i=i+1)begin tags[i]<=tags[i-1];identity_x[i]<=identity_x[i-1];identity_y[i]<=identity_y[i-1];end
                if(corrected)begin
                    black[4]<=black[3] || overflow32(rounded(norm_x_product,16)) || overflow32(rounded(norm_y_product,16));
                    black[8]<=black[7] || overflow32(rounded(square_x_product,22)) || overflow32(rounded(square_y_product,22)) || overflow32(rounded(square_xy_product,22));
                    black[9]<=black[8] || overflow32(r2_next) || r2_next<0 || r2_next>33554432;
                    black[10]<=black[9] || overflow32(widen(r2)+(widen(xx9)<<<1)) || overflow32(widen(r2)+(widen(yy9)<<<1));
                    black[14]<=black[13] || overflow32(tx_next) || overflow32(ty_next) || overflow32(radial_next) || radial_next<0 || radial_next>1073741824;
                    black[18]<=black[17] || overflow32(xd_next) || overflow32(yd_next);
                    black[22]<=black[21] || overflow24(final_x) || overflow24(final_y);
                end
            end
        end
        if(advance)begin
            du<=$signed({{8{in_u[23]}},in_u})-OCX;dv<=$signed({{8{in_v[23]}},in_v})-OCY;
            nx<=bounded32(rounded(norm_x_product,16));ny<=bounded32(rounded(norm_y_product,16));
            xx<=bounded32(rounded(square_x_product,22));yy<=bounded32(rounded(square_y_product,22));
            r2<=bounded32(r2_next);fraction<=rom_fraction;
            xy<=bounded32(rounded(square_xy_product,22));xy9<=xy;xy10<=xy9;xx9<=xx;yy9<=yy;
            txf<=bounded32(widen(r2)+(widen(xx9)<<<1));tyf<=bounded32(widen(r2)+(widen(yy9)<<<1));
            tx<=bounded32(tx_next);ty<=bounded32(ty_next);
            tx_delay[0]<=tx;ty_delay[0]<=ty;
            for(i=1;i<3;i=i+1)begin tx_delay[i]<=tx_delay[i-1];ty_delay[i]<=ty_delay[i-1];end
            base_delay[0]<=$signed(rom_base);base_delay[1]<=base_delay[0];base_delay[2]<=base_delay[1];
            radial<=bounded32(radial_next);xd<=bounded32(xd_next);yd<=bounded32(yd_next);
            result_x<=final_x[23:0];result_y<=final_y[23:0];
            nx_delay[0]<=nx;ny_delay[0]<=ny;
            for(i=1;i<10;i=i+1)begin nx_delay[i]<=nx_delay[i-1];ny_delay[i]<=ny_delay[i-1];end
        end
    end
endmodule

