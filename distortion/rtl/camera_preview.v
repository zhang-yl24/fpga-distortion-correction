`timescale 1ns/1ps
// First-image preview: 640x480 -> 160x120 by sampling every fourth pixel/row.
// Two 32K-word BRAM banks; held-bank toggle/ack switches only at HDMI frame start.
// VGA acquisition and sensor clock remain unchanged. Full-resolution path uses DDR.
module camera_preview #(
    parameter SRC_W=640,SRC_H=480,
    HT=1650,VT=750,HS=40,VS=5,X0=260,Y0=25,AW=1280,AH=720
)(input cam_clk,rst_n,cam_ready,vsync,href,input [7:0] data,
    input pix_clk,output reg hs,vs,de,output reg [7:0] r,g,b,
    output reg display_valid);
    localparam DW=SRC_W/4,DH=SRC_H/4,WORDS=DW*DH;
    localparam WX=X0+(AW-SRC_W)/2,WY=Y0+(AH-SRC_H)/2;
    reg [15:0] memory[0:65535];
    (* async_reg="true" *) reg [1:0] cam_reset_sync=0,pix_reset_sync=0;
    always @(posedge cam_clk or negedge rst_n)
        if(!rst_n) cam_reset_sync<=0;else cam_reset_sync<={cam_reset_sync[0],1'b1};
    always @(posedge pix_clk or negedge rst_n)
        if(!rst_n) pix_reset_sync<=0;else pix_reset_sync<={pix_reset_sync[0],1'b1};
    reg [1:0] cap_reset=0;
    always @(posedge cam_clk or negedge rst_n)
        if(!rst_n) cap_reset<=0;else cap_reset<={cap_reset[0],cam_ready};
    wire pixel_valid,frame_start,line_end,odd;
    wire [15:0] pixel;wire [31:0] frame_count,frame_pixels;
    dvp_rgb565_capture #(.HIGH_BYTE_FIRST(0)) receiver(.pclk(cam_clk),.rst(!cap_reset[1]),
        .vsync(vsync),.href(href),.data(data),.pixel_valid(pixel_valid),.pixel(pixel),
        .frame_start(frame_start),.line_end(line_end),.odd_line_error(odd),
        .frame_count(frame_count),.last_frame_pixels(frame_pixels));
    reg [11:0] column,row;
    reg [14:0] write_address;
    reg writing,write_bank,held_bank,request,invalid_frame;
    reg acknowledge;
    (* async_reg="true" *) reg [1:0] ack_sync;
    wire memory_write=cap_reset[1] && writing && !invalid_frame && pixel_valid &&
        column<SRC_W && row<SRC_H && column[1:0]==0 && row[1:0]==0;
    // No reset on the memory array, allowing dual-clock block-RAM inference.
    always @(posedge cam_clk)
        if(memory_write) memory[{write_bank,write_address}]<=pixel;
    always @(posedge cam_clk) begin
        if(!cam_reset_sync[1]) begin
            column<=0;row<=0;write_address<=0;writing<=0;write_bank<=0;held_bank<=1;
            request<=0;ack_sync<=0;invalid_frame<=0;
        end else begin
            ack_sync<={ack_sync[0],acknowledge};
            if(!cap_reset[1]) begin writing<=0;column<=0;row<=0;write_address<=0;invalid_frame<=0;end
            else if(frame_start) begin
                if(writing && !invalid_frame && row==SRC_H && column==0 &&
                    write_address==WORDS && frame_pixels==SRC_W*SRC_H) begin
                    held_bank<=write_bank;request<=!request;writing<=0;
                end else if(request==ack_sync[1]) begin
                    write_bank<=!held_bank;writing<=1;
                end
                column<=0;row<=0;write_address<=0;invalid_frame<=0;
            end else if(writing) begin
                if(odd) invalid_frame<=1;
                if(pixel_valid) begin
                    column<=column+1'b1;
                    if(column>=SRC_W || row>=SRC_H) invalid_frame<=1;
                    if(memory_write) write_address<=write_address+1'b1;
                end
                if(line_end) begin
                    if(column!=SRC_W) invalid_frame<=1;
                    row<=row+1'b1;column<=0;
                end
            end
        end
    end
    (* async_reg="true" *) reg [1:0] request_sync;
    reg [11:0] x,y;
    reg read_bank;
    wire active=x>=X0 && x<X0+AW && y>=Y0 && y<Y0+AH;
    wire picture=x>=WX && x<WX+SRC_W && y>=WY && y<WY+SRC_H;
    wire [11:0] px=(x-WX)>>2,py=(y-WY)>>2;
    wire [14:0] read_address=py*DW+px;
    reg [15:0] read_pixel;
    reg hs_d,vs_d,de_d,picture_d;
    always @(posedge pix_clk) read_pixel<=memory[{read_bank,read_address}];
    always @(posedge pix_clk) begin
        if(!pix_reset_sync[1]) begin
            x<=0;y<=0;read_bank<=1;request_sync<=0;acknowledge<=0;display_valid<=0;
            hs_d<=0;vs_d<=0;de_d<=0;picture_d<=0;hs<=0;vs<=0;de<=0;r<=0;g<=0;b<=0;
        end else begin
            request_sync<={request_sync[0],request};
            if(x==0 && y==0 && request_sync[1]!=acknowledge) begin
                read_bank<=held_bank;acknowledge<=request_sync[1];display_valid<=1;
            end
            if(x==HT-1) begin x<=0;y<=y==VT-1 ? 0:y+1'b1;end else x<=x+1'b1;
            hs_d<=x<HS;vs_d<=y<VS;de_d<=active;picture_d<=picture && display_valid;
            hs<=hs_d;vs<=vs_d;de<=de_d;
            r<=picture_d ? {read_pixel[15:11],read_pixel[15:13]}:0;
            g<=picture_d ? {read_pixel[10:5],read_pixel[10:9]}:0;
            b<=picture_d ? {read_pixel[4:0],read_pixel[4:2]}:0;
        end
    end
endmodule
