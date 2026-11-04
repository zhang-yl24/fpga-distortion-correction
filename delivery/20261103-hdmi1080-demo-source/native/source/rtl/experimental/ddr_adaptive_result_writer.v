`timescale 1ns/1ps
// Accept 8x8 tile order, drain one eight-row stripe in raster order.
// RGB565 quantization, raster CRC and 16-beat DDR bursts match the proven
// display contract. One stripe is buffered; upstream stalls during drain.
module ddr_adaptive_result_writer_capture_local #(parameter WIDTH=640,HEIGHT=480,TAG_W=24,TIMEOUT_BITS=26)(
    input clk,rst_n,input frame_valid,frame_tiled,output frame_ready,
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
    reg [2:0] state;reg tiled;
    reg [27:0] base;
    reg [31:0] identity,crc,expected_tag,stripe_base,collected;
    reg [RAM_BITS:0] read_index;
    reg [15:0] stripe[0:STRIPE_PIXELS-1],pixel_q;
    reg [255:0] burst[0:15];
    reg [7:0] slot;reg [3:0] beat;reg [5:0] drain;
    reg [TIMEOUT_BITS-1:0] watchdog;
    reg flush_pending;
    reg [15:0] cmd_pending;
    reg [15:0] cmd_pixel[0:15];
    reg [3:0] cmd_lane[0:15];
    wire [15:0] pixel={in_rgb[23:19],in_rgb[15:10],in_rgb[7:3]};
    wire [31:0] write_index=expected_tag-stripe_base;
    wire writing=state==WRITE || (state==ADDRESS && !flush_pending && awready);
    `include "C:/Users/22955/Documents/Codex/2026-10-26/task-2/controlled-blanking-function-native-20261102-a/native/source/rtl/video_crc32.vh"
    assign frame_ready=state==IDLE && !failed;
    assign in_ready=state==COLLECT && !failed;
    assign awaddr=base+(written_beats<<3);assign awlen=15;
    assign awvalid=state==ADDRESS && !flush_pending;
    assign wdata=burst[beat];assign wstrb=32'hFFFFFFFF;
    // No reset on RAM. Each stripe is fully validated before it can drain.
    always @(posedge clk) begin
        if(state==COLLECT && tiled && in_valid && !failed && in_tag==expected_tag[TAG_W-1:0] && write_index<STRIPE_PIXELS)
            stripe[write_index[RAM_BITS-1:0]]<=pixel;
        if(state==READ) pixel_q<=stripe[read_index[RAM_BITS-1:0]];
    end
    always @(posedge clk) begin
        if(!rst_n) begin
            state<=IDLE;tiled<=0;base<=0;identity<=0;crc<=32'hFFFFFFFF;
            expected_tag<=0;stripe_base<=0;collected<=0;read_index<=0;
            slot<=0;beat<=0;drain<=0;watchdog<=0;done<=0;failed<=0;fault<=0;flush_pending<=0;
            accepted_pixels<=0;written_beats<=0;last_checksum<=0;completed_id<=0;
        end else begin
            done<=0;
            if(state==WRITE && !wready) watchdog<=watchdog+1'b1;else watchdog<=0;
            case(state)
                IDLE: if(frame_valid) begin
                    if(WIDTH<8 || WIDTH%8!=0 || HEIGHT<8 || HEIGHT%8!=0 ||
                       FRAME_PIXELS%256!=0 || frame_base[6:0]!=0) begin failed<=1;fault<=8'h08;state<=FAULT;end
                    else begin
                        tiled<=frame_tiled;base<=frame_base;identity<=frame_id;crc<=32'hFFFFFFFF;
                        expected_tag<=0;stripe_base<=0;collected<=0;read_index<=0;
                        accepted_pixels<=0;written_beats<=0;slot<=0;flush_pending<=0;state<=COLLECT;
                    end
                end
                COLLECT: if(in_valid) begin
                    if(in_tag!=expected_tag[TAG_W-1:0] || (tiled && write_index>=STRIPE_PIXELS)) begin
                        failed<=1;fault<=8'h32;state<=FAULT;
                    end else begin
                        accepted_pixels<=accepted_pixels+1'b1;collected<=collected+1'b1;
                        if(tiled) begin
                        // Tag is the global raster index; expected sequence is
                        // tile-x, tile-y, then the next horizontal 8x8 tile.
                        if(collected[2:0]!=7) expected_tag<=expected_tag+1'b1;
                        else if(collected[5:3]!=7) expected_tag<=expected_tag+WIDTH-7;
                        else if(collected==STRIPE_PIXELS-1) expected_tag<=expected_tag+1'b1;
                        else expected_tag<=expected_tag-7*WIDTH+1;
                        if(collected==STRIPE_PIXELS-1) begin read_index<=0;slot<=0;state<=READ;end
                        end else begin
                            expected_tag<=expected_tag+1'b1;
                            crc<=video_crc32_pixel(crc,pixel);slot<=slot+1'b1;
                            if(slot==255) begin beat<=0;flush_pending<=1;state<=ADDRESS;end
                        end
                    end
                end
                READ: state<=PACK;
                PACK: begin
                    crc<=video_crc32_pixel(crc,pixel_q);read_index<=read_index+1'b1;slot<=slot+1'b1;
                    if(slot==255) begin beat<=0;flush_pending<=1;state<=ADDRESS;end else state<=READ;
                end
                ADDRESS: if(flush_pending) flush_pending<=0; else if(awready) state<=WRITE;
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
                        else if(!tiled) state<=COLLECT;
                        else if(read_index==STRIPE_PIXELS) begin
                            stripe_base<=stripe_base+STRIPE_PIXELS;collected<=0;state<=COLLECT;
                        end else state<=READ;
                    end else beat<=beat+1'b1;
                end
            end
            if(state==WRITE && &watchdog && !wready) begin failed<=1;fault<=8'h01;state<=FAULT;end
        end
    end
    // One registered command per256-bit word. Original reset/failed admission
    // checks are retained here and in the unchanged controller. No async reset.
    wire cmd_issue=rst_n && !failed &&
        ((state==COLLECT && !tiled && in_valid) || state==PACK);
    wire [15:0] cmd_issue_pixel=state==PACK ? pixel_q : pixel;
    genvar command_word;
    generate for(command_word=0;command_word<16;command_word=command_word+1)begin: local_command
        always @(posedge clk)begin
            if(!rst_n || failed)cmd_pending[command_word]<=0;
            else begin
                cmd_pending[command_word]<=cmd_issue && slot[7:4]==command_word;
                if(cmd_issue && slot[7:4]==command_word)begin
                    cmd_pixel[command_word]<=cmd_issue_pixel;
                    cmd_lane[command_word]<=slot[3:0];
                end
            end
        end
        // The private payload commit is one edge later. A pre-reset/fault token
        // may update an unpublished slot on that edge; command-valid is cleared
        // synchronously and the controller prevents AW/done. Full refill+FLUSH
        // is mandatory before any subsequent publication. Do not treat this as
        // exact internal burst contents equality during reset/fault.
        always @(posedge clk)begin
            if(cmd_pending[command_word])
                burst[command_word][cmd_lane[command_word]*16+:16]<=cmd_pixel[command_word];
        end
    end endgenerate
endmodule
