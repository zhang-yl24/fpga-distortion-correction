`timescale 1ns/1ps
// Optional raster-only writer. Two sealed 256-pixel banks let collection of
// the next burst overlap the current AW/W transaction. The DDR UI is the same
// project contract: 4-byte address units, sixteen 256-bit beats, no B channel.
// A fault stops admissions/new AW, but an already asserted AW and active W
// transaction remain owned and drain. Recovery requires coordinated reset.
module ddr_raster_overlap_writer #(
    parameter WIDTH=640,HEIGHT=480,TAG_W=24,TIMEOUT_BITS=26,RAM_BUFFER=0
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
    localparam TX_IDLE=0,TX_ADDRESS=1,TX_WRITE=2;
    reg frame_active,collect_done,collect_bank,tx_bank,next_tx_bank;
    reg [1:0] bank_busy,bank_full;
    reg seal_valid,seal_bank;
    reg [7:0] slot;
    reg [1:0] tx_state;
    reg [3:0] tx_beat;
    reg [27:0] base,tx_address;
    reg [31:0] identity,expected_tag,crc;
    reg drain_pending;reg [5:0] drain;
    reg [TIMEOUT_BITS-1:0] watchdog;
    `include "video_crc32.vh"

    wire layout_ok=WIDTH>=8 && WIDTH%8==0 && HEIGHT>=8 && HEIGHT%8==0 &&
        FRAME_PIXELS>0 && FRAME_PIXELS%256==0 && frame_base[6:0]==0;
    assign frame_ready=!frame_active && !failed && tx_state==TX_IDLE &&
        !seal_valid && bank_busy==0 && bank_full==0 && !drain_pending;
    wire frame_fire=frame_valid && frame_ready;
    // No speculative same-edge credit is used when a full bank is released.
    assign in_ready=frame_active && !failed && !drain_pending && !collect_done &&
        (slot!=0 || !bank_busy[collect_bank]);
    wire pixel_fire=in_valid && in_ready;
    wire bad_tag=pixel_fire && in_tag!=expected_tag[TAG_W-1:0];
    wire good_pixel=pixel_fire && !bad_tag;
    wire [15:0] pixel={in_rgb[23:19],in_rgb[15:10],in_rgb[7:3]};
    wire accepted_aw=tx_state==TX_ADDRESS && awready;
    wire writing=tx_state==TX_WRITE || accepted_aw;
    wire transfer=writing && wready;
    wire bad_wlast=transfer && wlast!=(tx_beat==15);
    wire timed_out=tx_state==TX_WRITE && (&watchdog) && !wready;
    assign awaddr=tx_address;assign awlen=15;
    // In particular, failed must not withdraw a previously asserted address.
    assign awvalid=tx_state==TX_ADDRESS;
    assign wstrb=32'hFFFFFFFF;

    always @(posedge clk)begin
        if(!rst_n)begin
            frame_active<=0;collect_done<=0;collect_bank<=0;tx_bank<=0;next_tx_bank<=0;
            bank_busy<=0;bank_full<=0;seal_valid<=0;seal_bank<=0;slot<=0;
            tx_state<=TX_IDLE;tx_beat<=0;base<=0;tx_address<=0;identity<=0;expected_tag<=0;
            crc<=32'hFFFFFFFF;drain_pending<=0;drain<=0;watchdog<=0;
            done<=0;failed<=0;fault<=0;accepted_pixels<=0;written_beats<=0;last_checksum<=0;completed_id<=0;
        end else begin
            done<=0;
            if(tx_state==TX_WRITE && !wready)watchdog<=watchdog+1'b1;else watchdog<=0;
            if(frame_fire)begin
                if(!layout_ok || frame_tiled)begin failed<=1;fault<=8'h08;end
                else begin
                    frame_active<=1;collect_done<=0;collect_bank<=0;tx_bank<=0;next_tx_bank<=0;
                    bank_busy<=0;bank_full<=0;seal_valid<=0;seal_bank<=0;slot<=0;
                    tx_state<=TX_IDLE;tx_beat<=0;base<=frame_base;tx_address<=frame_base;
                    identity<=frame_id;expected_tag<=0;crc<=32'hFFFFFFFF;
                    drain_pending<=0;drain<=0;watchdog<=0;accepted_pixels<=0;written_beats<=0;
                end
            end else begin
                // One cycle of sealing is the old local-command commit edge.
                // AW can only start after the full flag becomes visible.
                seal_valid<=0;
                if(seal_valid && !failed && !bad_tag)bank_full[seal_bank]<=1;
                if(good_pixel)begin
                    if(slot==0)bank_busy[collect_bank]<=1;
                    accepted_pixels<=accepted_pixels+1'b1;expected_tag<=expected_tag+1'b1;
                    if(accepted_pixels==FRAME_PIXELS-1)collect_done<=1;
                    crc<=video_crc32_pixel(crc,pixel);slot<=slot+1'b1;
                    if(slot==255)begin
                        seal_valid<=1;seal_bank<=collect_bank;collect_bank<=!collect_bank;
                    end
                end
                case(tx_state)
                    TX_IDLE:if(frame_active && !drain_pending && !failed && !bad_tag && bank_full[next_tx_bank])begin
                        tx_bank<=next_tx_bank;tx_beat<=0;tx_address<=base+(written_beats<<3);tx_state<=TX_ADDRESS;
                    end
                    TX_ADDRESS:if(awready)tx_state<=TX_WRITE;
                    TX_WRITE:begin end
                    default:begin failed<=1;fault<=8'h08;end
                endcase
                // Completion remains physical W acceptance. Data/control of a
                // sealed bank never depend on the other bank's bad input tag.
                if(transfer)begin
                    written_beats<=written_beats+1'b1;
                    if(tx_beat==15)begin
                        tx_state<=TX_IDLE;bank_busy[tx_bank]<=0;bank_full[tx_bank]<=0;
                        next_tx_bank<=!next_tx_bank;
                        if(written_beats==FRAME_BEATS-1 && !failed && !bad_tag && !bad_wlast)begin
                            if(accepted_pixels!=FRAME_PIXELS)begin failed<=1;fault<=8'h08;end
                            else begin drain_pending<=1;drain<=0;end
                        end
                    end else tx_beat<=tx_beat+1'b1;
                end
                if(drain_pending && !failed && !bad_tag && !bad_wlast)begin
                    if(drain==31)begin
                        last_checksum<=~crc;completed_id<=identity;done<=1;
                        frame_active<=0;drain_pending<=0;
                    end else drain<=drain+1'b1;
                end
                // First failure is sticky. Protocol failure has priority over
                // a simultaneous input tag failure; active AW/W still drains.
                if(!failed)begin
                    if(bad_wlast)begin failed<=1;fault<=8'h02;end
                    else if(bad_tag)begin failed<=1;fault<=8'h32;end
                    else if(timed_out)begin failed<=1;fault<=8'h01;end
                end
            end
        end
    end

    // Single-variable storage candidate. Core FSM/lease/CRC/fault logic above
    // is byte-for-byte the frozen6331536 implementation. RAM_BUFFER0 retains
    // the old per-word commands and FF-friendly variable-part-select array.
    wire cmd_issue=rst_n && !failed && good_pixel;
    wire [4:0] cmd_word={collect_bank,slot[7:4]};
    genvar command_word,lane;
    generate if(!RAM_BUFFER)begin: original_registers
        reg [255:0] burst[0:31];
        reg [31:0] cmd_pending;
        reg [15:0] cmd_pixel[0:31];
        reg [3:0] cmd_lane[0:31];
        assign wdata=burst[{tx_bank,tx_beat}];
        for(command_word=0;command_word<32;command_word=command_word+1)begin: local_command
            always @(posedge clk)begin
                if(!rst_n || failed)cmd_pending[command_word]<=0;
                else begin
                    cmd_pending[command_word]<=cmd_issue && cmd_word==command_word;
                    if(cmd_issue && cmd_word==command_word)begin
                        cmd_pixel[command_word]<=pixel;cmd_lane[command_word]<=slot[3:0];
                    end
                end
            end
            always @(posedge clk)begin
                if(cmd_pending[command_word])burst[command_word][cmd_lane[command_word]*16+:16]<=cmd_pixel[command_word];
            end
        end
    end else begin: lane_ram
        // One registered write command: one full16-bit lane write per edge.
        // Data/address feed only16 lane ports; no memory/reset/fault read-modify
        // write and no new dependency enters the external in_ready cone.
        reg write_pending;
        reg [4:0] write_word;
        reg [3:0] write_lane;
        reg [15:0] write_pixel;
        always @(posedge clk)begin
            if(!rst_n || failed)write_pending<=0;
            else begin
                write_pending<=cmd_issue;
                if(cmd_issue)begin
                    write_word<=cmd_word;write_lane<=slot[3:0];write_pixel<=pixel;
                end
            end
        end
        // Launch reads beat0 at the EXISTING TX_IDLE->TX_ADDRESS edge, so AW
        // may still accept W0 on its first edge. Each real transfer prefetches
        // its successor; stalled W holds the current registered data.
        wire read_first=tx_state==TX_IDLE && frame_active && !drain_pending &&
            !failed && !bad_tag && bank_full[next_tx_bank];
        wire read_next=transfer && tx_beat!=15;
        wire read_enable=rst_n && (read_first || read_next);
        wire [4:0] read_word=read_first ? {next_tx_bank,4'd0}:{tx_bank,(tx_beat+4'd1)};
        for(lane=0;lane<16;lane=lane+1)begin: pixel_lane
            // Canonical1R1W synchronous-read RAM, no reset and full-word write.
            // No vendor primitive or RAM-style hint: Map must establish whether
            // this tiny32x16 shape becomes LUTRAM, fragmented DRM, or FFs.
            reg [15:0] pixels[0:31];
            reg [15:0] read_pixel;
            always @(posedge clk)begin
                if(write_pending && write_lane==lane)pixels[write_word]<=write_pixel;
            end
            always @(posedge clk)begin
                if(read_enable)read_pixel<=pixels[read_word];
            end
            assign wdata[lane*16+:16]=read_pixel;
        end
        // read_next is deliberately NOT gated by failed: an already asserted
        // AW or accepted W burst remains owned and must keep draining. A command
        // immediately before reset/fault may commit to an unpublished bank, as
        // in the baseline; only a coordinated reset recovers the frame state.
    end endgenerate
endmodule
