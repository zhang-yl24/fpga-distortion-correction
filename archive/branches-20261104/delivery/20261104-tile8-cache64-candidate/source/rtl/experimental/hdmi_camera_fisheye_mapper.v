`timescale 1ns/1ps
// Exact C fisheye radial model through a bounded Q30 ROM approximation.
// 23 enabled stages, II=1; data, multipliers, ROM, tags freeze together.
// cfg_corrected is locked only after complete drain. Identity is bit-exact Q8.
module hdmi_camera_fisheye_mapper #(
    parameter TAG_W=24,WIDTH=1920,HEIGHT=1080
)(
    input clk,rst,input cfg_valid,output cfg_ready,input cfg_corrected,
    input in_black,in_valid,output in_ready,input signed [23:0] in_u,in_v,
    input [TAG_W-1:0] in_tag,
    output out_valid,input out_ready,output signed [23:0] out_x,out_y,
    output out_black,output [TAG_W-1:0] out_tag
);
    `include "@COMPILED@/board/hdmi-camera-fisheye-profile.vh"
    localparam signed [63:0] WIDE_WIDTH=WIDTH,WIDE_HEIGHT=HEIGHT;
    localparam signed [31:0] OCX=((FISHEYE_OUT_CX+64'sd128)*WIDE_WIDTH+960)/1920-128;
    localparam signed [31:0] OCY=((FISHEYE_OUT_CY+64'sd128)*WIDE_HEIGHT+540)/1080-128;
    localparam signed [31:0] SCX=((FISHEYE_SRC_CX+64'sd128)*WIDE_WIDTH+960)/1920-128;
    localparam signed [31:0] SCY=((FISHEYE_SRC_CY+64'sd128)*WIDE_HEIGHT+540)/1080-128;
    localparam signed [31:0] SFX=(FISHEYE_SRC_FX*WIDE_WIDTH+960)/1920;
    localparam signed [31:0] SFY=(FISHEYE_SRC_FY*WIDE_HEIGHT+540)/1080;
    localparam signed [31:0] IFX=(FISHEYE_INV_FX*64'sd1920+WIDTH/2)/WIDTH;
    localparam signed [31:0] IFY=(FISHEYE_INV_FY*64'sd1080+HEIGHT/2)/HEIGHT;
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
    function signed [64:0] widen(input signed [31:0] x);widen=x;endfunction
    function signed [64:0] rounded(input signed [63:0] x,input integer bits);
        rounded=($signed({x[63],x})>>>bits)+$signed({1'b0,x[bits-1]});
    endfunction
    function overflow32(input signed [64:0] x);overflow32=x[64:31]!={34{x[31]}};endfunction
    function overflow24(input signed [64:0] x);overflow24=x[64:23]!={42{x[23]}};endfunction
    function signed [31:0] bounded32(input signed [64:0] x);
        bounded32=overflow32(x)?(x[64]?32'sh80000000:32'sh7fffffff):x[31:0];
    endfunction
    reg signed [31:0] du,dv,nx,ny,xx,yy,r2,radial,xd,yd;
    reg signed [31:0] nx_delay[0:9],ny_delay[0:9];
    wire signed [63:0] norm_x_product,norm_y_product,square_x_product,square_y_product;
    wire signed [63:0] interpolation_product,dist_x_product,dist_y_product,source_x_product,source_y_product;
    wire signed [64:0] r2_next=widen(xx)+widen(yy);
    wire [9:0] rom_address=r2<0 ? 10'd0:(r2>=33554432 ? 10'd1023:r2[24:15]);
    wire [15:0] rom_fraction=r2<0 ? 16'd0:(r2>=33554432 ? 16'd32768:{1'b0,r2[14:0]});
    wire [31:0] rom_base;
    wire signed [31:0] rom_delta;
    reg [15:0] fraction;
    reg signed [31:0] base_delay[0:2];
    reg signed [23:0] result_x,result_y;
    wire signed [64:0] radial_next=widen(base_delay[2])+rounded(interpolation_product,15);
    wire signed [64:0] final_x=rounded(source_x_product,22)+widen(SCX);
    wire signed [64:0] final_y=rounded(source_y_product,22)+widen(SCY);
    mul32_pipe normalize_x(.clk(clk),.ce(advance),.a(du),.b(IFX),.p(norm_x_product));
    mul32_pipe normalize_y(.clk(clk),.ce(advance),.a(dv),.b(IFY),.p(norm_y_product));
    mul32_pipe square_x(.clk(clk),.ce(advance),.a(nx),.b(nx),.p(square_x_product));
    mul32_pipe square_y(.clk(clk),.ce(advance),.a(ny),.b(ny),.p(square_y_product));
    hdmi_camera_fisheye_rom radial_rom(.clk(clk),.ce(advance),.address(rom_address),.base_q30(rom_base),.delta_q30(rom_delta));
    mul32_pipe interpolate(.clk(clk),.ce(advance),.a(rom_delta),.b($signed({16'd0,fraction})),.p(interpolation_product));
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
                    black[8]<=black[7] || overflow32(rounded(square_x_product,22)) || overflow32(rounded(square_y_product,22));
                    black[9]<=black[8] || overflow32(r2_next) || r2_next<0 || r2_next>33554432;
                    black[14]<=black[13] || overflow32(radial_next) || radial_next<0 || radial_next>1073741824;
                    black[18]<=black[17] || overflow32(rounded(dist_x_product,30)) || overflow32(rounded(dist_y_product,30));
                    black[22]<=black[21] || overflow24(final_x) || overflow24(final_y);
                end
            end
        end
        if(advance)begin
            du<=$signed({in_u[23],in_u})-OCX;dv<=$signed({in_v[23],in_v})-OCY;
            nx<=bounded32(rounded(norm_x_product,16));ny<=bounded32(rounded(norm_y_product,16));
            xx<=bounded32(rounded(square_x_product,22));yy<=bounded32(rounded(square_y_product,22));
            r2<=bounded32(r2_next);fraction<=rom_fraction;
            base_delay[0]<=$signed(rom_base);base_delay[1]<=base_delay[0];base_delay[2]<=base_delay[1];
            radial<=bounded32(radial_next);xd<=bounded32(rounded(dist_x_product,30));yd<=bounded32(rounded(dist_y_product,30));
            result_x<=final_x[23:0];result_y<=final_y[23:0];
            nx_delay[0]<=nx;ny_delay[0]<=ny;
            for(i=1;i<10;i=i+1)begin nx_delay[i]<=nx_delay[i-1];ny_delay[i]<=ny_delay[i-1];end
        end
    end
endmodule
