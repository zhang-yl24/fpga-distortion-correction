`timescale 1ns/1ps
// Independent experimental1080 reader; original public module stays frozen.
// Native-resolution centered image. Each HDMI frame requests one locked DDR
// bank; four local beat slots hide the synchronous async-FIFO read latency.
// Geometry/timing must fit the original12bit raster counters; WIDTH is a
// multiple of16, and the complete image must fit AW/AH within HT/VT.
// The default is1080p timing; actual148.5MHz timing/CDC closure is separate.
module ddr_video_output_1080_core #(
    parameter WIDTH=1920,HEIGHT=1080,HT=2200,VT=1125,HS=44,VS=5,
    X0=192,Y0=41,AW=1920,AH=1080
)(
    input clk,rst_n,
    output reg request_toggle,
    input grant_toggle,grant_valid,input [31:0] grant_checksum,
    input fifo_ready,fifo_valid,input [255:0] fifo_data,output wire fifo_rd_en,
    output reg hs,vs,de,output reg [7:0] r,g,b,
    output reg display_valid,result_toggle,
    output reg [31:0] completed_frames,underflows,mismatches,last_checksum
);
    `include "D:/English/FPGA/distortion/rtl/video_crc32.vh"
    localparam WX=X0+(AW-WIDTH)/2,WY=Y0+(AH-HEIGHT)/2,FRAME_BEATS=WIDTH*HEIGHT/16;
    // Count the inclusive terminal value FRAME_BEATS, not just beat indices.
    //1080RGB565 requires129600, so16bits wraps before the final request.
    function integer count_bits;
        input integer maximum;integer remaining;
        begin
            remaining=maximum;count_bits=0;
            while(remaining>0)begin count_bits=count_bits+1;remaining=remaining>>1;end
        end
    endfunction
    localparam REQUEST_COUNT_BITS=count_bits(FRAME_BEATS)<17 ? 17:count_bits(FRAME_BEATS);
    (* async_reg="true" *) reg [1:0] reset_sync=0,grant_sync=0;
    always @(posedge clk or negedge rst_n)
        if(!rst_n) reset_sync<=0;else reset_sync<={reset_sync[0],1'b1};
    reg [11:0] x,y;
    reg [255:0] words[0:3];
    reg [1:0] head,tail;
    reg [2:0] queued,inflight;
    reg [REQUEST_COUNT_BITS-1:0] requested_words;
    reg grant_seen,frame_active,broken;
    reg [31:0] checksum,expected;
    wire active=x>=X0 && x<X0+AW && y>=Y0 && y<Y0+AH;
    wire picture=x>=WX && x<WX+WIDTH && y>=WY && y<WY+HEIGHT;
    wire [11:0] column=x-WX;
    wire [15:0] pixel=words[head][column[3:0]*16+:16];
    wire consume=picture && frame_active && !broken && queued!=0;
    wire pop=consume && column[3:0]==15;
    wire [31:0] next_checksum=video_crc32_pixel(checksum,pixel);
    assign fifo_rd_en=reset_sync[1] && frame_active && !broken && fifo_ready &&
        requested_words<FRAME_BEATS && queued+inflight<4;
    always @(posedge clk) begin
        if(!reset_sync[1]) begin
            x<=0;y<=0;head<=0;tail<=0;queued<=0;inflight<=0;requested_words<=0;
            grant_sync<=0;grant_seen<=0;request_toggle<=0;frame_active<=0;broken<=0;
            checksum<=32'hFFFFFFFF;expected<=0;hs<=0;vs<=0;de<=0;r<=0;g<=0;b<=0;
            display_valid<=0;result_toggle<=0;completed_frames<=0;underflows<=0;mismatches<=0;last_checksum<=32'hFFFFFFFF;
        end else begin
            grant_sync<={grant_sync[0],grant_toggle};
            if(x==HT-1) begin x<=0;y<=y==VT-1 ? 0:y+1'b1;end else x<=x+1'b1;
            hs<=x<HS;vs<=y<VS;de<=active;
            r<=consume ? {pixel[15:11],pixel[15:13]}:0;
            g<=consume ? {pixel[10:5],pixel[10:9]}:0;
            b<=consume ? {pixel[4:0],pixel[4:2]}:0;
            if(fifo_rd_en) requested_words<=requested_words+1'b1;
            case({fifo_rd_en,fifo_valid})
                2'b10:inflight<=inflight+1'b1;
                2'b01:inflight<=inflight-1'b1;
                default:inflight<=inflight;
            endcase
            if(fifo_valid) begin words[tail]<=fifo_data;tail<=tail+1'b1;end
            if(pop) head<=head+1'b1;
            case({fifo_valid,pop})
                2'b10:queued<=queued+1'b1;
                2'b01:queued<=queued-1'b1;
                default:queued<=queued;
            endcase
            if(consume) begin
                checksum<=next_checksum;
                if(x==WX+WIDTH-1 && y==WY+HEIGHT-1) begin
                    last_checksum<=~next_checksum;completed_frames<=completed_frames+1'b1;
                    result_toggle<=!result_toggle;
                    if(~next_checksum!=expected) begin mismatches<=mismatches+1'b1;broken<=1;end
                    else display_valid<=1;
                    frame_active<=0;
                end
            end else if(picture && frame_active && !broken && queued==0) begin
                underflows<=underflows+1'b1;broken<=1;frame_active<=0;
            end
            if(grant_sync[1]!=grant_seen) begin
                grant_seen<=grant_sync[1];frame_active<=grant_valid && !broken;expected<=grant_checksum;
            end
            if(x==0 && y==0) begin
                request_toggle<=!request_toggle;frame_active<=0;checksum<=32'hFFFFFFFF;requested_words<=0;
                // A complete frame must have consumed all words, with no return
                // still in flight. Never discard stale words and shift the image.
                if(queued!=0 || inflight!=0) begin underflows<=underflows+1'b1;broken<=1;end
            end
        end
    end
endmodule
