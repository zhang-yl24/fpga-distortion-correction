`timescale 1ns/1ps
// Two complete stripe banks convert configured tile order into raster order.
// A synchronous RAM read and elastic pixel register feed owned DDR burst banks.
// Stripe collection, raster drain and DDR transmission can run concurrently.
module ddr_adaptive_result_writer #(
    parameter WIDTH=640,HEIGHT=480,TAG_W=24,TIMEOUT_BITS=26,TILE_W=8,TILE_H=8
)(
    input clk,rst_n,input frame_valid,frame_tiled,output frame_ready,
    input [27:0] frame_base,input [31:0] frame_id,
    input in_valid,output in_ready,input [23:0] in_rgb,input [TAG_W-1:0] in_tag,
    output [27:0] awaddr,output [3:0] awlen,output awvalid,input awready,
    output [255:0] wdata,output [31:0] wstrb,input wready,wlast,
    output done,failed,output [7:0] fault,
    output reg [31:0] accepted_pixels,
    output [31:0] written_beats,last_checksum,completed_id
);
    localparam FRAME_PIXELS=WIDTH*HEIGHT,STRIPE_PIXELS=WIDTH*TILE_H;
    function integer log2ceil;
        input integer value;integer n;
        begin n=value-1;log2ceil=0;while(n>0)begin log2ceil=log2ceil+1;n=n>>1;end end
    endfunction
    localparam STRIPE_BITS=log2ceil(STRIPE_PIXELS),RAM_BITS=STRIPE_BITS+1;
    reg active,tiled,front_failed,fill_bank,read_bank;
    reg [7:0] front_fault;
    reg [1:0] full;
    reg [31:0] expected_tag,read_tag;
    reg [STRIPE_BITS-1:0] write_index,collected,read_index;
    reg [12:0] tile_column,tile_row;
    reg raw_valid,pixel_valid;
    reg [15:0] raw_q,pixel_q;
    reg [TAG_W-1:0] raw_tag,pixel_tag;
    (* ram_style="block" *) reg [15:0] stripes[0:2*STRIPE_PIXELS-1];
    wire r_frame_ready,r_in_ready,r_done,r_failed;
    wire [7:0] r_fault;
    wire [31:0] raster_pixels;
    // Keep the stripe-local tile cursor in a register. Deriving it from two
    // frame-wide counters put a subtract/range chain on the abort and AW path.
    wire [RAM_BITS-1:0] write_address=(fill_bank ? STRIPE_PIXELS:0)+write_index;
    wire [RAM_BITS-1:0] read_address=(read_bank ? STRIPE_PIXELS:0)+read_index;
    wire take=in_valid && in_ready;
    wire bad_tag=take && (tiled ? (in_tag!=expected_tag[TAG_W-1:0] || write_index>=STRIPE_PIXELS):in_tag!=accepted_pixels[TAG_W-1:0]);
    wire [15:0] packed_pixel={in_rgb[23:19],in_rgb[15:10],in_rgb[7:3]};
    wire advance_pixel=!pixel_valid || r_in_ready;
    wire advance_raw=!raw_valid || advance_pixel;
    wire issue_read=active && tiled && !failed && full[read_bank] && advance_raw;
    wire raster_valid=tiled ? pixel_valid:in_valid;
    // Expansion preserves RGB565 bits exactly when the backend repacks them.
    wire [23:0] raster_rgb=tiled ? {pixel_q[15:11],pixel_q[15:13],pixel_q[10:5],pixel_q[10:9],pixel_q[4:0],pixel_q[4:2]}:in_rgb;
    wire [TAG_W-1:0] raster_tag=tiled ? pixel_tag:in_tag;
    assign failed=front_failed || r_failed;
    assign fault=front_failed ? front_fault:r_fault;
    assign frame_ready=!active && !failed && r_frame_ready;
    wire start=frame_valid && frame_ready;
    assign in_ready=active && !failed && accepted_pixels<FRAME_PIXELS && (tiled ? !full[fill_bank]:r_in_ready);
    assign done=r_done && !failed;
    ddr_raster_result_writer_pingpong #(.WIDTH(WIDTH),.HEIGHT(HEIGHT),.TAG_W(TAG_W),.TIMEOUT_BITS(TIMEOUT_BITS)) raster(
        .clk(clk),.rst_n(rst_n),.abort(front_failed || bad_tag),.frame_valid(start),.frame_ready(r_frame_ready),
        .frame_base(frame_base),.frame_id(frame_id),.in_valid(raster_valid && !front_failed),.in_ready(r_in_ready),
        .in_rgb(raster_rgb),.in_tag(raster_tag),.awaddr(awaddr),.awlen(awlen),.awvalid(awvalid),.awready(awready),
        .wdata(wdata),.wstrb(wstrb),.wready(wready),.wlast(wlast),.done(r_done),.failed(r_failed),.fault(r_fault),
        .accepted_pixels(raster_pixels),.written_beats(written_beats),.last_checksum(last_checksum),.completed_id(completed_id));
    // No RAM reset. Ownership requires a complete stripe before any read.
    // Opposite banks may collect/drain on the same edge; the last read is
    // registered before its bank can be reused by the producer.
    always @(posedge clk)begin
        if(rst_n && tiled && take && !bad_tag)stripes[write_address[RAM_BITS-1:0]]<=packed_pixel;
        if(issue_read)raw_q<=stripes[read_address[RAM_BITS-1:0]];
    end
    always @(posedge clk)begin
        if(!rst_n)begin
            active<=0;tiled<=0;front_failed<=0;front_fault<=0;full<=0;fill_bank<=0;read_bank<=0;
            accepted_pixels<=0;expected_tag<=0;write_index<=0;collected<=0;read_index<=0;read_tag<=0;
            tile_column<=0;tile_row<=0;raw_valid<=0;raw_tag<=0;pixel_valid<=0;pixel_tag<=0;
        end else begin
            if(start)begin
                if(frame_tiled && (TILE_W<1 || TILE_H<1 || WIDTH%TILE_W!=0 || HEIGHT%TILE_H!=0 ||
                   WIDTH*TILE_H<256 || WIDTH*TILE_H%256!=0))begin front_failed<=1;front_fault<=8'h08;end
                else begin
                    active<=1;tiled<=frame_tiled;full<=0;fill_bank<=0;read_bank<=0;accepted_pixels<=0;
                    expected_tag<=0;write_index<=0;collected<=0;read_index<=0;read_tag<=0;
                    tile_column<=0;tile_row<=0;raw_valid<=0;pixel_valid<=0;
                end
            end
            if(take)begin
                if(bad_tag)begin front_failed<=1;front_fault<=8'h32;end
                else begin
                    accepted_pixels<=accepted_pixels+1'b1;
                    if(tiled)begin
                        if(collected==STRIPE_PIXELS-1)begin
                            full[fill_bank]<=1;fill_bank<=!fill_bank;collected<=0;write_index<=0;
                            expected_tag<=expected_tag+1'b1;tile_column<=0;tile_row<=0;
                        end else begin
                            collected<=collected+1'b1;
                            if(tile_column!=TILE_W-1)begin
                                expected_tag<=expected_tag+1'b1;write_index<=write_index+1'b1;tile_column<=tile_column+1'b1;
                            end
                            else if(tile_row!=TILE_H-1)begin
                                expected_tag<=expected_tag+WIDTH-TILE_W+1;tile_column<=0;tile_row<=tile_row+1'b1;
                                write_index<=write_index+WIDTH-TILE_W+1;
                            end else begin
                                expected_tag<=expected_tag-(TILE_H-1)*WIDTH+1;tile_column<=0;tile_row<=0;
                                write_index<=write_index-(TILE_H-1)*WIDTH+1;
                            end
                        end
                    end
                end
            end
            if(tiled && advance_pixel)begin
                // This independent elastic register receives a previously
                // captured RAM word. Its enable differs from the RAM read
                // enable, separating the memory clock-to-out from RGB CRC.
                pixel_valid<=raw_valid;
                if(raw_valid)begin pixel_q<=raw_q;pixel_tag<=raw_tag;end
            end
            if(tiled && advance_raw)begin
                raw_valid<=issue_read;
                if(issue_read)begin
                    raw_tag<=read_tag[TAG_W-1:0];read_tag<=read_tag+1'b1;
                    if(read_index==STRIPE_PIXELS-1)begin full[read_bank]<=0;read_bank<=!read_bank;read_index<=0;end
                    else read_index<=read_index+1'b1;
                end
            end
            if(failed)begin raw_valid<=0;pixel_valid<=0;end
            if(r_done && !failed)begin active<=0;raw_valid<=0;pixel_valid<=0;end
        end
    end
endmodule

module ddr_raster_result_writer_pingpong #(
    parameter WIDTH=640,HEIGHT=480,TAG_W=24,TIMEOUT_BITS=26
)(
    input clk,rst_n,input abort,input frame_valid,output frame_ready,
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
    reg [3:0] beat /* synthesis syn_maxfan = 32 */;
    reg [5:0] drain;
    reg [27:0] address;
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
            slot<=0;beat<=0;drain<=0;address<=0;identity<=0;crc<=32'hFFFFFFFF;
            watchdog<=0;done<=0;failed<=0;fault<=0;
            accepted_pixels<=0;written_beats<=0;last_checksum<=0;completed_id<=0;
        end else begin
            done<=0;
            if(abort && !failed)begin failed<=1;fault<=8'h33;end
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
                    slot<=0;beat<=0;drain<=0;address<=frame_base;
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
            // An idle payload is unpublished. Prefetch from registered bank
            // ownership independently of fault checks; only the control below
            // may commit AW. Once AW is visible, its payload stays reserved.
            if(tx_state==TX_IDLE && full[send_bank])
                send_data<=burst[{send_bank,4'd0}];
            case(tx_state)
                TX_IDLE: if(active && full[send_bank] && !failed && !bad_tag && !abort && !draining) begin
                    // The last registered command commits on this edge; AW is
                    // first visible afterward, so no stale final pixel escapes.
                    beat<=0;tx_state<=TX_ADDRESS;
                end
                TX_ADDRESS: if(awready) tx_state<=TX_WRITE;
                TX_WRITE: tx_state<=TX_WRITE;
            endcase
            if(transfer && wready) begin
                written_beats<=written_beats+1'b1;
                if(wlast!=(beat==15) && !failed && !bad_tag) begin failed<=1;fault<=8'h02;end
                if(beat==15) begin
                    full[send_bank]<=0;send_bank<=!send_bank;tx_state<=TX_IDLE;
                    // Burst completion owns address advancement. Pixel tag
                    // checks still veto a new AW on the same cycle, without
                    // driving the address register's clock enable.
                    address<=address+28'd128;
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
            else cmd_pending[word_index]<=issue && {fill_bank,slot[7:4]}==word_index;
            // Only cmd_pending publishes a RAM update. Prefetch the selected
            // private payload independently of ready, reset and fault control.
            // A pending command consumes the previous payload on this edge;
            // the new prefetch becomes visible after that consumption.
            if({fill_bank,slot[7:4]}==word_index) begin
                cmd_pixel[word_index]<=pixel;cmd_lane[word_index]<=slot[3:0];
            end
        end
        always @(posedge clk) begin
            if(cmd_pending[word_index]) burst[word_index][cmd_lane[word_index]*16+:16]<=cmd_pixel[word_index];
        end
    end endgenerate
endmodule
