`timescale 1ns/1ps
// Standard 1080p60 at 148.5MHz or 720p60 at 74.25MHz. No camera-image claim.
module video_pattern #(parameter MODE_720P=0)(input clk, input rst_n, output reg hs,vs,de,
    output reg [7:0] r,g,b);
    reg [11:0] x,y;
    reg [23:0] color;
    localparam HS=MODE_720P ? 40:44, HT=MODE_720P ? 1650:2200;
    localparam VS=5, VT=MODE_720P ? 750:1125;
    localparam X0=MODE_720P ? 260:192, Y0=MODE_720P ? 25:41;
    localparam WIDTH=MODE_720P ? 1280:1920, HEIGHT=MODE_720P ? 720:1080;
    localparam BAR=WIDTH/8;
    wire active=(x>=X0 && x<X0+WIDTH && y>=Y0 && y<Y0+HEIGHT);
    wire [11:0] ax=x-X0;
    always @* begin
        if(ax<BAR) color=24'hffffff;
        else if(ax<2*BAR) color=24'hffff00;
        else if(ax<3*BAR) color=24'h00ffff;
        else if(ax<4*BAR) color=24'h00ff00;
        else if(ax<5*BAR) color=24'hff00ff;
        else if(ax<6*BAR) color=24'hff0000;
        else if(ax<7*BAR) color=24'h0000ff;
        else color=24'h000000;
    end
    always @(posedge clk) begin
        if(!rst_n) begin x<=0; y<=0; hs<=0; vs<=0; de<=0; r<=0; g<=0; b<=0; end
        else begin
            if(x==HT-1) begin x<=0; y<= y==VT-1 ? 0:y+1'b1; end
            else x<=x+1'b1;
            hs<=x<HS; vs<=y<VS; de<=active;
            {r,g,b}<=active ? color:24'h000000;
        end
    end
endmodule
