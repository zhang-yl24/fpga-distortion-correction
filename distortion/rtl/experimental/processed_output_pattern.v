`timescale 1ns/1ps
// Controlled DIGITAL source for the independent processing/output candidate.
// Not a camera. enable is synchronous to clk and sampled only when idle or at
// the end of a complete raster; withdrawing it never truncates an active frame.
// At the board's 27MHz source clock, the default raster is about10.91frames/s.
module processed_output_pattern #(
    parameter WIDTH=1920,HEIGHT=1080,HT=2200,VT=1125,VS=5,X0=192,Y0=41
)(
    input clk,rst_n,enable,
    output vsync_active,de,output [23:0] rgb,
    output reg [31:0] frame_counter
);
    localparam CONFIG_OK=WIDTH>=1 && HEIGHT>=1 && HT>=1 && HT<=4096 &&
        VT>=1 && VT<=4096 && VS>=1 && VS<=Y0 && X0>=0 && Y0>=1 &&
        X0+WIDTH<=HT && Y0+HEIGHT<=VT;
    localparam CX=WIDTH>=256 ? WIDTH/256:0;
    localparam CY=HEIGHT>=256 ? HEIGHT/256:0;
    (* async_reg="true" *) reg [1:0] reset_sync=0;
    reg running=0;
    reg [11:0] x=0,y=0;
    always @(posedge clk or negedge rst_n)
        if(!rst_n)reset_sync<=0;
        else reset_sync<={reset_sync[0],1'b1};
    always @(posedge clk or negedge rst_n)begin
        if(!rst_n)begin running<=0;x<=0;y<=0;frame_counter<=0;end
        else if(!reset_sync[1] || !CONFIG_OK)begin running<=0;x<=0;y<=0;frame_counter<=0;end
        else if(!running)begin
            x<=0;y<=0;
            if(enable)begin running<=1;frame_counter<=frame_counter+1'b1;end
        end else if(x==HT-1)begin
            x<=0;
            if(y==VT-1)begin
                y<=0;
                if(enable)frame_counter<=frame_counter+1'b1;
                else running<=0;
            end else y<=y+1'b1;
        end else x<=x+1'b1;
    end
    wire [11:0] ax=x-X0,ay=y-Y0;
    assign vsync_active=running && y<VS;
    assign de=running && x>=X0 && x<X0+WIDTH && y>=Y0 && y<Y0+HEIGHT;
    function [23:0] pattern_rgb(input [11:0] px,py);
        reg light_square;
        reg [4:0] red,blue;
        reg [5:0] green;
        begin
            light_square=px[5]^py[5];
            red=(light_square ? 5'd20:5'd4)+{2'b00,px[2:0]};
            green=6'd8+{1'b0,py[4:0]};
            blue=(light_square ? 5'd4:5'd20)+{2'b00,py[2:0]};
            if(px==0 || px==WIDTH-1 || py==0 || py==HEIGHT-1)
                pattern_rgb=24'hffffff;
            else if((px>=WIDTH/2-CX && px<=WIDTH/2+CX) ||
                    (py>=HEIGHT/2-CY && py<=HEIGHT/2+CY))
                pattern_rgb=24'hff0000;
            else if(px[4:0]==0 || py[4:0]==0)
                pattern_rgb=24'h00ff00;
            else pattern_rgb={{red,red[4:2]},{green,green[5:4]},{blue,blue[4:2]}};
        end
    endfunction
    assign rgb=de ? pattern_rgb(ax,ay):24'd0;
endmodule
