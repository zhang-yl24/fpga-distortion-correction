`timescale 1ns/1ps
// Store ordered remapper RGB888 results as RGB565 for the existing HDMI
// reader. Quantization is explicit: R/B top 5 bits, G top 6. A 512-byte
// reserved burst absorbs backpressure; the mapper may stall between bursts.
// Parent owns source/output/display banks, resets all owners together on
// failure, and publishes a result bank ONLY after done. Dimensions must
// contain a whole number of 256-pixel bursts (640x480 does).
module ddr_result_writer #(parameter WIDTH=640,HEIGHT=480,TAG_W=24,TIMEOUT_BITS=26)(
    input clk,rst_n,input frame_valid,output frame_ready,
    input [27:0] frame_base,input [31:0] frame_id,
    input in_valid,output in_ready,input [23:0] in_rgb,input [TAG_W-1:0] in_tag,
    output [27:0] awaddr,output [3:0] awlen,output awvalid,input awready,
    output [255:0] wdata,output [31:0] wstrb,input wready,wlast,
    output reg done,failed,output reg [7:0] fault,
    output reg [31:0] accepted_pixels,written_beats,last_checksum,completed_id
);
    localparam FRAME_PIXELS=WIDTH*HEIGHT;
    localparam IDLE=0,COLLECT=1,ADDRESS=2,WRITE=3,DRAIN=4,FAULT=5;
    reg [2:0] state;reg [27:0] base;reg [31:0] identity,crc;
    reg [7:0] slot;reg [3:0] beat;reg [5:0] drain;
    reg [255:0] burst[0:15];reg [TIMEOUT_BITS-1:0] watchdog;
    wire [15:0] pixel={in_rgb[23:19],in_rgb[15:10],in_rgb[7:3]};
    wire writing=state==WRITE || (state==ADDRESS && awready);
    `include "D:/English/FPGA/distortion/rtl/video_crc32.vh"
    assign frame_ready=state==IDLE && !failed;
    assign in_ready=state==COLLECT && !failed;
    assign awaddr=base+(written_beats<<3);assign awlen=15;assign awvalid=state==ADDRESS;
    assign wdata=burst[beat];assign wstrb=32'hFFFFFFFF;
    always @(posedge clk) begin
        if(!rst_n) begin
            state<=IDLE;base<=0;identity<=0;crc<=32'hFFFFFFFF;slot<=0;beat<=0;drain<=0;
            watchdog<=0;done<=0;failed<=0;fault<=0;accepted_pixels<=0;written_beats<=0;
            last_checksum<=0;completed_id<=0;
        end else begin
            done<=0;
            if(state==WRITE && !wready) watchdog<=watchdog+1'b1;else watchdog<=0;
            case(state)
                IDLE: if(frame_valid) begin
                    if(FRAME_PIXELS<256 || FRAME_PIXELS%256!=0 || frame_base[6:0]!=0) begin
                        failed<=1;fault<=8'h08;state<=FAULT;
                    end else begin
                        base<=frame_base;identity<=frame_id;crc<=32'hFFFFFFFF;
                        accepted_pixels<=0;written_beats<=0;slot<=0;state<=COLLECT;
                    end
                end
                COLLECT: if(in_valid) begin
                    if(in_tag!=accepted_pixels[TAG_W-1:0]) begin failed<=1;fault<=8'h32;state<=FAULT;end
                    else begin
                        burst[slot[7:4]][slot[3:0]*16 +: 16]<=pixel;
                        crc<=video_crc32_pixel(crc,pixel);accepted_pixels<=accepted_pixels+1'b1;
                        slot<=slot+1'b1;
                        if(slot==255) begin beat<=0;state<=ADDRESS;end
                    end
                end
                ADDRESS: if(awready) state<=WRITE;
                WRITE: state<=WRITE;
                DRAIN: if(drain==31) begin
                    last_checksum<=~crc;completed_id<=identity;done<=1;state<=IDLE;
                end else drain<=drain+1'b1;
                FAULT: state<=FAULT;
            endcase
            if(writing && wready) begin
                    if(wlast!=(beat==15)) begin failed<=1;fault<=8'h02;state<=FAULT;end
                    else begin
                        written_beats<=written_beats+1'b1;
                        if(beat==15) begin
                            if(accepted_pixels==FRAME_PIXELS) begin drain<=0;state<=DRAIN;end
                            else state<=COLLECT;
                        end else beat<=beat+1'b1;
                    end
            end
            if(state==WRITE && &watchdog && !wready) begin failed<=1;fault<=8'h01;state<=FAULT;end
        end
    end
endmodule
