`timescale 1ns/1ps
// Raster throughput candidate. The tile fallback below retains the sealed
// capture_local implementation. Mode is selected only at frame acceptance.
module ddr_adaptive_result_writer_capture_local #(
    parameter WIDTH=640,HEIGHT=480,TAG_W=24,TIMEOUT_BITS=26
)(
    input clk,rst_n,input frame_valid,frame_tiled,output frame_ready,
    input [27:0] frame_base,input [31:0] frame_id,
    input in_valid,output in_ready,input [23:0] in_rgb,input [TAG_W-1:0] in_tag,
    output [27:0] awaddr,output [3:0] awlen,output awvalid,input awready,
    output [255:0] wdata,output [31:0] wstrb,input wready,wlast,
    output done,failed,output [7:0] fault,
    output [31:0] accepted_pixels,written_beats,last_checksum,completed_id
);
    reg tiled;
    wire r_frame_ready,t_frame_ready,r_in_ready,t_in_ready;
    wire [27:0] r_awaddr,t_awaddr;
    wire [3:0] r_awlen,t_awlen;
    wire r_awvalid,t_awvalid,r_done,t_done,r_failed,t_failed;
    wire [255:0] r_wdata,t_wdata;
    wire [31:0] r_wstrb,t_wstrb;
    wire [7:0] r_fault,t_fault;
    wire [31:0] r_pixels,t_pixels,r_beats,t_beats,r_crc,t_crc,r_id,t_id;
    assign frame_ready=r_frame_ready && t_frame_ready && !failed;
    wire start=frame_valid && frame_ready;
    always @(posedge clk) begin
        if(!rst_n) tiled<=0;
        else if(start) tiled<=frame_tiled;
    end
    assign in_ready=tiled ? t_in_ready:r_in_ready;
    assign awaddr=tiled ? t_awaddr:r_awaddr;
    assign awlen=tiled ? t_awlen:r_awlen;
    assign awvalid=tiled ? t_awvalid:r_awvalid;
    assign wdata=tiled ? t_wdata:r_wdata;
    assign wstrb=tiled ? t_wstrb:r_wstrb;
    assign done=tiled ? t_done:r_done;
    assign failed=tiled ? t_failed:r_failed;
    assign fault=tiled ? t_fault:r_fault;
    assign accepted_pixels=tiled ? t_pixels:r_pixels;
    assign written_beats=tiled ? t_beats:r_beats;
    assign last_checksum=tiled ? t_crc:r_crc;
    assign completed_id=tiled ? t_id:r_id;
    ddr_raster_result_writer_pingpong #(.WIDTH(WIDTH),.HEIGHT(HEIGHT),.TAG_W(TAG_W),.TIMEOUT_BITS(TIMEOUT_BITS)) raster(
        .clk(clk),.rst_n(rst_n),.frame_valid(start && !frame_tiled),.frame_ready(r_frame_ready),
        .frame_base(frame_base),.frame_id(frame_id),.in_valid(in_valid && !tiled),.in_ready(r_in_ready),.in_rgb(in_rgb),.in_tag(in_tag),
        .awaddr(r_awaddr),.awlen(r_awlen),.awvalid(r_awvalid),.awready(awready && !tiled),
        .wdata(r_wdata),.wstrb(r_wstrb),.wready(wready && !tiled),.wlast(wlast),
        .done(r_done),.failed(r_failed),.fault(r_fault),.accepted_pixels(r_pixels),.written_beats(r_beats),.last_checksum(r_crc),.completed_id(r_id));
    ddr_adaptive_result_writer_tile_fallback #(.WIDTH(WIDTH),.HEIGHT(HEIGHT),.TAG_W(TAG_W),.TIMEOUT_BITS(TIMEOUT_BITS)) tile(
        .clk(clk),.rst_n(rst_n),.frame_valid(start && frame_tiled),.frame_tiled(1'b1),.frame_ready(t_frame_ready),
        .frame_base(frame_base),.frame_id(frame_id),.in_valid(in_valid && tiled),.in_ready(t_in_ready),.in_rgb(in_rgb),.in_tag(in_tag),
        .awaddr(t_awaddr),.awlen(t_awlen),.awvalid(t_awvalid),.awready(awready && tiled),
        .wdata(t_wdata),.wstrb(t_wstrb),.wready(wready && tiled),.wlast(wlast),
        .done(t_done),.failed(t_failed),.fault(t_fault),.accepted_pixels(t_pixels),.written_beats(t_beats),.last_checksum(t_crc),.completed_id(t_id));
endmodule

// Two fully owned 512-byte banks. Collection overlaps the previous burst's
// address/data service. No RAM reset; a whole bank plus its registered payload
// commit precedes publication. AW/W obligations survive source/timeout faults.
// rst_n is the coordinated system reset, including the downstream DDR client.
module ddr_raster_result_writer_pingpong #(
    parameter WIDTH=640,HEIGHT=480,TAG_W=24,TIMEOUT_BITS=26
)(
    input clk,rst_n,input frame_valid,output frame_ready,
    input [27:0] frame_base,input [31:0] frame_id,
    input in_valid,output in_ready,input [23:0] in_rgb,input [TAG_W-1:0] in_tag,
    output [27:0] awaddr,output [3:0] awlen,output awvalid,input awready,
    output [255:0] wdata,output [31:0] wstrb,input wready,wlast,
    output reg done,failed,output reg [7:0] fault,
    output reg [31:0] accepted_pixels,written_beats,last_checksum,completed_id
);
    localparam FRAME_PIXELS=WIDTH*HEIGHT,FRAME_BEATS=FRAME_PIXELS/16;
    localparam TX_IDLE=0,TX_ADDRESS=1,TX_WRITE=2;
    reg active,draining,fill_bank,send_bank;
    reg [1:0] full,tx_state;
    reg [7:0] slot;
    reg [3:0] beat;
    reg [5:0] drain;
    reg [27:0] base,address;
    reg [31:0] identity,crc;
    reg [TIMEOUT_BITS-1:0] watchdog;
    reg [255:0] burst[0:31];
    // Publish a registered beat to the DDR boundary. The full send bank
    // remains owned until all 16 beats complete, including stalled/faulted AW.
    reg [255:0] send_data;
    wire [3:0] next_beat=beat+1'b1;
    reg [31:0] cmd_pending;
    reg [15:0] cmd_pixel[0:31];
    reg [3:0] cmd_lane[0:31];
    wire [15:0] pixel={in_rgb[23:19],in_rgb[15:10],in_rgb[7:3]};
    wire take=in_valid && in_ready;
    wire bad_tag=take && in_tag!=accepted_pixels[TAG_W-1:0];
    wire issue=take && !bad_tag;
    wire transfer=tx_state==TX_WRITE || (tx_state==TX_ADDRESS && awready);
    wire last_transfer=transfer && wready && beat==15;
    `include "video_crc32.vh"
    assign frame_ready=!active && !failed;
    assign in_ready=active && !draining && !failed && !full[fill_bank] && accepted_pixels<FRAME_PIXELS;
    assign awaddr=address;
    assign awlen=15;
    // Once asserted, AW remains asserted until accepted, including after fault.
    assign awvalid=tx_state==TX_ADDRESS;
    assign wdata=send_data;
    assign wstrb=32'hFFFFFFFF;

    always @(posedge clk) begin
        if(!rst_n) begin
            active<=0;draining<=0;fill_bank<=0;send_bank<=0;full<=0;tx_state<=TX_IDLE;
            slot<=0;beat<=0;drain<=0;base<=0;address<=0;identity<=0;crc<=32'hFFFFFFFF;
            watchdog<=0;done<=0;failed<=0;fault<=0;
            accepted_pixels<=0;written_beats<=0;last_checksum<=0;completed_id<=0;
        end else begin
            done<=0;
            // Report a stalled committed write, then keep its payload alive so
            // a recovering downstream can finish the reserved burst.
            if(tx_state==TX_WRITE && !wready) begin
                if(!(&watchdog)) watchdog<=watchdog+1'b1;
                else if(!failed) begin failed<=1;fault<=8'h01;end
            end else watchdog<=0;

            if(frame_valid && frame_ready) begin
                if(WIDTH<8 || WIDTH%8!=0 || HEIGHT<8 || HEIGHT%8!=0 ||
                   FRAME_PIXELS%256!=0 || frame_base[6:0]!=0) begin
                    failed<=1;fault<=8'h08;
                end else begin
                    active<=1;draining<=0;fill_bank<=0;send_bank<=0;full<=0;tx_state<=TX_IDLE;
                    slot<=0;beat<=0;drain<=0;base<=frame_base;address<=frame_base;
                    identity<=frame_id;crc<=32'hFFFFFFFF;accepted_pixels<=0;written_beats<=0;
                end
            end
            if(take) begin
                if(bad_tag) begin failed<=1;fault<=8'h32;end
                else begin
                    accepted_pixels<=accepted_pixels+1'b1;
                    crc<=video_crc32_pixel(crc,pixel);
                    slot<=slot+1'b1;
                    if(slot==255) begin full[fill_bank]<=1;fill_bank<=!fill_bank;end
                end
            end
            case(tx_state)
                TX_IDLE: if(active && full[send_bank] && !failed && !bad_tag && !draining) begin
                    // The last registered command commits on this edge; AW is
                    // first visible afterward, so no stale final pixel escapes.
                    address<=base+(written_beats<<3);beat<=0;tx_state<=TX_ADDRESS;
                    send_data<=burst[{send_bank,4'd0}];
                end
                TX_ADDRESS: if(awready) tx_state<=TX_WRITE;
                TX_WRITE: tx_state<=TX_WRITE;
            endcase
            if(transfer && wready) begin
                written_beats<=written_beats+1'b1;
                if(wlast!=(beat==15) && !failed && !bad_tag) begin failed<=1;fault<=8'h02;end
                if(beat==15) begin
                    full[send_bank]<=0;send_bank<=!send_bank;tx_state<=TX_IDLE;
                    if(written_beats==FRAME_BEATS-1) begin draining<=1;drain<=0;end
                end else begin
                    beat<=next_beat;send_data<=burst[{send_bank,next_beat}];
                end
            end
            if(draining && !failed) begin
                if(drain==31) begin
                    last_checksum<=~crc;completed_id<=identity;done<=1;active<=0;draining<=0;
                end else drain<=drain+1'b1;
            end
        end
    end

    // Retain the sealed writer's local registered command structure. Each
    // word owns its payload write; no wide variable pixel write-enable fanout.
    genvar word_index;
    generate for(word_index=0;word_index<32;word_index=word_index+1) begin: local_command
        always @(posedge clk) begin
            if(!rst_n || failed) cmd_pending[word_index]<=0;
            else begin
                cmd_pending[word_index]<=issue && {fill_bank,slot[7:4]}==word_index;
                if(issue && {fill_bank,slot[7:4]}==word_index) begin
                    cmd_pixel[word_index]<=pixel;cmd_lane[word_index]<=slot[3:0];
                end
            end
        end
        always @(posedge clk) begin
            if(cmd_pending[word_index]) burst[word_index][cmd_lane[word_index]*16+:16]<=cmd_pixel[word_index];
        end
    end endgenerate
endmodule
`timescale 1ns/1ps
// Accept 8x8 tile order, drain one eight-row stripe in raster order.
// RGB565 quantization, raster CRC and 16-beat DDR bursts match the proven
// display contract. One stripe is buffered; upstream stalls during drain.
module ddr_adaptive_result_writer_tile_fallback #(parameter WIDTH=640,HEIGHT=480,TAG_W=24,TIMEOUT_BITS=26)(
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
    `include "video_crc32.vh"
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

