`timescale 1ns/1ps
// Accept 8x8 tile order, drain one eight-row stripe in raster order.
// RGB565 quantization, raster CRC and 16-beat DDR bursts match the proven
// display contract. One stripe is buffered; upstream stalls during drain.
module ddr_stripe_result_writer #(parameter WIDTH=640,HEIGHT=480,TAG_W=24,TIMEOUT_BITS=26)(
    input clk,rst_n,input frame_valid,output frame_ready,
    input [27:0] frame_base,input [31:0] frame_id,
    input in_valid,output in_ready,input [23:0] in_rgb,input [TAG_W-1:0] in_tag,
    output [27:0] awaddr,output [3:0] awlen,output awvalid,input awready,
    output [255:0] wdata,output [31:0] wstrb,input wready,wlast,
    output reg done,failed,output reg [7:0] fault,
    output reg [31:0] accepted_pixels,written_beats,last_checksum,completed_id
);
    localparam FRAME_PIXELS=WIDTH*HEIGHT,FRAME_BEATS=FRAME_PIXELS/16,STRIPE_PIXELS=WIDTH*8;
    localparam IDLE=0,COLLECT=1,READ=2,PACK=3,ADDRESS=4,WRITE=5,DRAIN=6,FAULT=7;
    function integer log2ceil;
        input integer value;integer n;
        begin n=value-1;log2ceil=0;while(n>0) begin log2ceil=log2ceil+1;n=n>>1;end end
    endfunction
    localparam RAM_BITS=log2ceil(STRIPE_PIXELS);
    reg [2:0] state;
    reg [27:0] base;
    reg [31:0] identity,crc,expected_tag,stripe_base,collected;
    reg [RAM_BITS:0] read_index;
    reg [15:0] stripe[0:STRIPE_PIXELS-1],pixel_q;
    reg [255:0] burst[0:15];
    reg [7:0] slot;reg [3:0] beat;reg [5:0] drain;
    reg [TIMEOUT_BITS-1:0] watchdog;
    wire [15:0] pixel={in_rgb[23:19],in_rgb[15:10],in_rgb[7:3]};
    wire [31:0] write_index=expected_tag-stripe_base;
    wire writing=state==WRITE || (state==ADDRESS && awready);
    `include "D:/English/FPGA/distortion/rtl/video_crc32.vh"
    assign frame_ready=state==IDLE && !failed;
    assign in_ready=state==COLLECT && !failed;
    assign awaddr=base+(written_beats<<3);assign awlen=15;
    assign awvalid=state==ADDRESS;
    assign wdata=burst[beat];assign wstrb=32'hFFFFFFFF;
    // No reset on RAM. Each stripe is fully validated before it can drain.
    always @(posedge clk) begin
        if(state==COLLECT && in_valid && !failed && in_tag==expected_tag[TAG_W-1:0] && write_index<STRIPE_PIXELS)
            stripe[write_index[RAM_BITS-1:0]]<=pixel;
        if(state==READ) pixel_q<=stripe[read_index[RAM_BITS-1:0]];
    end
    always @(posedge clk) begin
        if(!rst_n) begin
            state<=IDLE;base<=0;identity<=0;crc<=32'hFFFFFFFF;
            expected_tag<=0;stripe_base<=0;collected<=0;read_index<=0;
            slot<=0;beat<=0;drain<=0;watchdog<=0;done<=0;failed<=0;fault<=0;
            accepted_pixels<=0;written_beats<=0;last_checksum<=0;completed_id<=0;
        end else begin
            done<=0;
            if(state==WRITE && !wready) watchdog<=watchdog+1'b1;else watchdog<=0;
            case(state)
                IDLE: if(frame_valid) begin
                    if(WIDTH<8 || WIDTH%8!=0 || HEIGHT<8 || HEIGHT%8!=0 ||
                       FRAME_PIXELS%256!=0 || frame_base[6:0]!=0) begin failed<=1;fault<=8'h08;state<=FAULT;end
                    else begin
                        base<=frame_base;identity<=frame_id;crc<=32'hFFFFFFFF;
                        expected_tag<=0;stripe_base<=0;collected<=0;read_index<=0;
                        accepted_pixels<=0;written_beats<=0;slot<=0;state<=COLLECT;
                    end
                end
                COLLECT: if(in_valid) begin
                    if(in_tag!=expected_tag[TAG_W-1:0] || write_index>=STRIPE_PIXELS) begin
                        failed<=1;fault<=8'h32;state<=FAULT;
                    end else begin
                        accepted_pixels<=accepted_pixels+1'b1;collected<=collected+1'b1;
                        // Tag is the global raster index; expected sequence is
                        // tile-x, tile-y, then the next horizontal 8x8 tile.
                        if(collected[2:0]!=7) expected_tag<=expected_tag+1'b1;
                        else if(collected[5:3]!=7) expected_tag<=expected_tag+WIDTH-7;
                        else if(collected==STRIPE_PIXELS-1) expected_tag<=expected_tag+1'b1;
                        else expected_tag<=expected_tag-7*WIDTH+1;
                        if(collected==STRIPE_PIXELS-1) begin read_index<=0;slot<=0;state<=READ;end
                    end
                end
                READ: state<=PACK;
                PACK: begin
                    burst[slot[7:4]][slot[3:0]*16+:16]<=pixel_q;
                    crc<=video_crc32_pixel(crc,pixel_q);read_index<=read_index+1'b1;slot<=slot+1'b1;
                    if(slot==255) begin beat<=0;state<=ADDRESS;end else state<=READ;
                end
                ADDRESS: if(awready) state<=WRITE;
                WRITE: state<=WRITE;
                DRAIN: if(drain==31) begin last_checksum<=~crc;completed_id<=identity;done<=1;state<=IDLE;end
                       else drain<=drain+1'b1;
                FAULT: state<=FAULT;
            endcase
            if(writing && wready) begin
                if(wlast!=(beat==15)) begin failed<=1;fault<=8'h02;state<=FAULT;end
                else begin
                    written_beats<=written_beats+1'b1;
                    if(beat==15) begin
                        if(written_beats==FRAME_BEATS-1) begin drain<=0;state<=DRAIN;end
                        else if(read_index==STRIPE_PIXELS) begin
                            stripe_base<=stripe_base+STRIPE_PIXELS;collected<=0;state<=COLLECT;
                        end else state<=READ;
                    end else beat<=beat+1'b1;
                end
            end
            if(state==WRITE && &watchdog && !wready) begin failed<=1;fault<=8'h01;state<=FAULT;end
        end
    end
endmodule
