`timescale 1ns/1ps
// Independent candidate: two complete eight-row stripes overlap collection
// with raster draining. A synchronous RAM read is followed by a pack stage;
// requests run at one pixel per clock within a stripe/burst. A complete 256
// pixel buffer is immutable from AW presentation through all 16 W transfers.
module ddr_adaptive_result_writer_dualstripe #(
    parameter WIDTH=640,HEIGHT=480,TAG_W=24,TIMEOUT_BITS=26
)(
    input clk,rst_n,input frame_valid,frame_tiled,output frame_ready,
    input [27:0] frame_base,input [31:0] frame_id,
    input in_valid,output in_ready,input [23:0] in_rgb,input [TAG_W-1:0] in_tag,
    output [27:0] awaddr,output [3:0] awlen,output awvalid,input awready,
    output [255:0] wdata,output [31:0] wstrb,input wready,wlast,
    output reg done,failed,output reg [7:0] fault,
    output reg [31:0] accepted_pixels,written_beats,last_checksum,completed_id
);
    localparam FRAME_PIXELS=WIDTH*HEIGHT,FRAME_BEATS=FRAME_PIXELS/16;
    localparam STRIPE_PIXELS=WIDTH*8;
    localparam IDLE=0,PACK=1,ADDRESS=2,WRITE=3,DRAIN=4,FAULT=5;
    function integer log2ceil;
        input integer value;integer n;
        begin n=value-1;log2ceil=0;while(n>0)begin log2ceil=log2ceil+1;n=n>>1;end end
    endfunction
    localparam RAM_BITS=log2ceil(STRIPE_PIXELS);
    reg [2:0] state;
    reg tiled,collect_bank,drain_bank;
    reg [1:0] stripe_full;
    reg [27:0] base;
    reg [31:0] identity,crc,expected_tag,stripe_base,collected;
    reg [RAM_BITS:0] read_index;
    reg [8:0] issued;
    reg [7:0] slot;
    reg [3:0] beat;
    reg [5:0] drain;
    reg [TIMEOUT_BITS-1:0] watchdog;
    reg read_valid,read_last;
    reg [15:0] stripe0[0:STRIPE_PIXELS-1];
    reg [15:0] stripe1[0:STRIPE_PIXELS-1];
    reg [15:0] pixel_q;
    reg [255:0] burst[0:15];

    wire [15:0] pixel={in_rgb[23:19],in_rgb[15:10],in_rgb[7:3]};
    wire [31:0] write_index=expected_tag-stripe_base;
    wire active=state==PACK || state==ADDRESS || state==WRITE;
    assign frame_ready=rst_n && state==IDLE && !failed;
    assign in_ready=rst_n && !failed && accepted_pixels<FRAME_PIXELS &&
        (tiled ? (active && !stripe_full[collect_bank]) : state==PACK);
    wire input_transfer=in_valid && in_ready;
    wire tag_good=in_tag==expected_tag[TAG_W-1:0] && (!tiled || write_index<STRIPE_PIXELS);
    wire tag_error=input_transfer && !tag_good;
    wire collect_pixel=input_transfer && tag_good && tiled;
    wire read_enable=rst_n && state==PACK && tiled && !failed &&
        stripe_full[drain_bank] && read_index<STRIPE_PIXELS && issued<256;
    wire pack_pixel=rst_n && state==PACK && !failed &&
        (tiled ? read_valid : (input_transfer && tag_good));
    wire [15:0] pack_data=tiled ? pixel_q : pixel;
    // Pango W has no WVALID: the first requested beat can coincide with AW.
    wire writing=state==WRITE || (state==ADDRESS && awready);
    assign awaddr=base+(written_beats<<3);
    assign awlen=15;
    assign awvalid=rst_n && state==ADDRESS;
    assign wdata=burst[beat];
    assign wstrb=32'hFFFFFFFF;
    `include "relocated-headers/rtl/video_crc32.vh"

    // Memories and their data outputs deliberately have no reset. Ownership
    // flags are reset; an entire validated stripe precedes every RAM read.
    always @(posedge clk)begin
        if(collect_pixel)begin
            if(collect_bank)stripe1[write_index[RAM_BITS-1:0]]<=pixel;
            else stripe0[write_index[RAM_BITS-1:0]]<=pixel;
        end
        if(read_enable)begin
            if(drain_bank)pixel_q<=stripe1[read_index[RAM_BITS-1:0]];
            else pixel_q<=stripe0[read_index[RAM_BITS-1:0]];
        end
        if(pack_pixel)burst[slot[7:4]][slot[3:0]*16+:16]<=pack_data;
    end

    always @(posedge clk or negedge rst_n)begin
        if(!rst_n)begin
            state<=IDLE;tiled<=0;collect_bank<=0;drain_bank<=0;stripe_full<=0;
            base<=0;identity<=0;crc<=32'hFFFFFFFF;expected_tag<=0;stripe_base<=0;
            collected<=0;read_index<=0;issued<=0;slot<=0;beat<=0;drain<=0;
            watchdog<=0;read_valid<=0;read_last<=0;done<=0;failed<=0;fault<=0;
            accepted_pixels<=0;written_beats<=0;last_checksum<=0;completed_id<=0;
        end else begin
            done<=0;
            read_valid<=read_enable;
            if(read_enable)begin
                read_last<=read_index==STRIPE_PIXELS-1;
                read_index<=read_index+1'b1;
                issued<=issued+1'b1;
            end
            if(state==WRITE && !wready)watchdog<=watchdog+1'b1;
            else watchdog<=0;
            case(state)
                IDLE:if(frame_valid)begin
                    if(WIDTH<8 || WIDTH%8!=0 || HEIGHT<8 || HEIGHT%8!=0 ||
                       FRAME_PIXELS%256!=0 || frame_base[6:0]!=0)begin
                        failed<=1;fault<=8'h08;state<=FAULT;
                    end else begin
                        tiled<=frame_tiled;base<=frame_base;identity<=frame_id;
                        crc<=32'hFFFFFFFF;expected_tag<=0;stripe_base<=0;collected<=0;
                        collect_bank<=0;drain_bank<=0;stripe_full<=0;read_index<=0;
                        issued<=0;slot<=0;beat<=0;drain<=0;read_valid<=0;read_last<=0;
                        accepted_pixels<=0;written_beats<=0;state<=PACK;
                    end
                end
                PACK:begin end
                ADDRESS:if(awready)state<=WRITE;
                WRITE:begin end
                DRAIN:if(drain==31)begin
                    last_checksum<=~crc;completed_id<=identity;done<=1;state<=IDLE;
                end else drain<=drain+1'b1;
                FAULT:state<=FAULT;
            endcase
            if(input_transfer && tag_good)begin
                accepted_pixels<=accepted_pixels+1'b1;
                if(tiled)begin
                    // Collected order is tile-x, tile-y, then horizontal tile.
                    // The tag itself is always the global raster pixel index.
                    if(collected[2:0]!=7)expected_tag<=expected_tag+1'b1;
                    else if(collected[5:3]!=7)expected_tag<=expected_tag+WIDTH-7;
                    else if(collected==STRIPE_PIXELS-1)expected_tag<=expected_tag+1'b1;
                    else expected_tag<=expected_tag-7*WIDTH+1;
                    if(collected==STRIPE_PIXELS-1)begin
                        stripe_full[collect_bank]<=1;
                        collect_bank<=!collect_bank;collected<=0;
                        stripe_base<=stripe_base+STRIPE_PIXELS;
                    end else collected<=collected+1'b1;
                end else expected_tag<=expected_tag+1'b1;
            end
            if(pack_pixel)begin
                crc<=video_crc32_pixel(crc,pack_data);
                slot<=slot+1'b1;
                if(tiled && read_last)begin
                    // The last synchronous return has been captured in burst;
                    // no later read refers to this bank, so collection may reuse it.
                    stripe_full[drain_bank]<=0;
                    drain_bank<=!drain_bank;read_index<=0;
                end
                if(slot==255)begin beat<=0;state<=ADDRESS;end
            end
            if(writing && wready)begin
                if(wlast!=(beat==15))begin
                    failed<=1;if(!failed)fault<=8'h02;state<=FAULT;
                end else begin
                    written_beats<=written_beats+1'b1;
                    if(beat==15)begin
                        if(failed || tag_error)state<=FAULT;
                        else if(written_beats==FRAME_BEATS-1)begin drain<=0;state<=DRAIN;end
                        else begin issued<=0;state<=PACK;end
                    end else beat<=beat+1'b1;
                end
            end
            if(tag_error)begin
                failed<=1;fault<=8'h32;
                // A published AW or an accepted burst is irrevocable. Keep
                // its immutable payload and finish it before quarantining.
                if(state!=ADDRESS && state!=WRITE)state<=FAULT;
            end
            if(state==WRITE && &watchdog && !wready)begin
                failed<=1;if(!failed)fault<=8'h01;state<=FAULT;
            end
        end
    end
endmodule
