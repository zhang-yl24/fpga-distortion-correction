`timescale 1ns/1ps
// Passive final-scan observer. No video ready, FIFO, DDR, ownership, or reset outputs.
// Coordinates, RGB, markers and identity must describe the SAME registered pixel.
// mailbox_data is held from publish until ack crosses two flops. A busy mailbox
// drops only telemetry; the observer continues processing every video pixel.
module scan_signature_capture #(
    parameter integer WIDTH=1920, HEIGHT=1080
)(
    input wire pix_clk, rst_n,
    input wire pixel_valid, frame_start, frame_last, abort,
    input wire [15:0] pixel_x, pixel_y,
    input wire [23:0] pixel_rgb,
    input wire metadata_valid,
    input wire [31:0] session_id, scan_epoch, frame_id, param_id,
    input wire bank,
    input wire [7:0] mode,
    output reg [959:0] mailbox_data,
    output reg mailbox_request,
    input wire mailbox_ack,
    output reg [31:0] dropped, aborted, malformed
);
    `include "reuse/crc_byte.vh"
    localparam [31:0] PIXELS=WIDTH*HEIGHT;
    localparam CONFIG_OK=WIDTH>=4 && HEIGHT>=4 && WIDTH<=65535 && HEIGHT<=65535 && PIXELS>0;
    (* async_reg="true" *) reg [1:0] release_sync=0, ack_sync=0;
    always @(posedge pix_clk or negedge rst_n)
        if(!rst_n)release_sync<=0;else release_sync<={release_sync[0],1'b1};

    function [31:0] sat_inc(input [31:0] v);
        begin sat_inc=(&v) ? v:v+1'b1;end
    endfunction
    function [15:0] sample_x(input integer i);
        begin case(i)
            0,2:sample_x=0; 1,3:sample_x=WIDTH-1;
            4,6:sample_x=WIDTH/2;5:sample_x=WIDTH/2-1;
            default:sample_x=1;
        endcase end
    endfunction
    function [15:0] sample_y(input integer i);
        begin case(i)
            0,1:sample_y=0;2,3:sample_y=HEIGHT-1;
            4,5:sample_y=HEIGHT/2;6:sample_y=HEIGHT/2-1;
            default:sample_y=1;
        endcase end
    endfunction

    reg active;
    reg [31:0] count, crc, next_sequence, frame_sequence;
    reg [15:0] cursor_x,cursor_y;
    reg [31:0] held_session,held_epoch,held_frame,held_param;
    reg held_bank;
    reg [7:0] held_mode,sample_mask;
    reg [447:0] samples;
    wire start_pixel=pixel_valid && frame_start;
    wire candidate=active || start_pixel;
    wire [31:0] count_before=start_pixel ? 0:count;
    wire [31:0] crc_before=start_pixel ? 32'hffffffff:crc;
    // Existing reflected IEEE byte-CRC function; R then G then B, no blanking.
    wire [31:0] next_crc=crc_byte(crc_byte(crc_byte(crc_before,
        pixel_rgb[23:16]),pixel_rgb[15:8]),pixel_rgb[7:0]);
    wire bad_pixel=!CONFIG_OK || !metadata_valid || session_id==0 || frame_id==0 || mode[7:2]!=0 ||
        pixel_x!=(start_pixel ? 16'd0:cursor_x) ||
        pixel_y!=(start_pixel ? 16'd0:cursor_y) ||
        pixel_x>=WIDTH || pixel_y>=HEIGHT ||
        (!start_pixel && (session_id!=held_session || scan_epoch!=held_epoch ||
            frame_id!=held_frame || param_id!=held_param || bank!=held_bank || mode!=held_mode));
    reg [447:0] samples_after;
    reg [7:0] mask_after;
    reg [959:0] record_after;
    integer i;
    always @* begin
        samples_after=start_pixel ? 448'b0:samples;
        mask_after=start_pixel ? 8'b0:sample_mask;
        for(i=0;i<8;i=i+1)begin
            if(pixel_x==sample_x(i) && pixel_y==sample_y(i))begin
                samples_after[i*56+:16]=pixel_x;
                samples_after[i*56+16+:16]=pixel_y;
                samples_after[i*56+32+:8]=pixel_rgb[23:16];
                samples_after[i*56+40+:8]=pixel_rgb[15:8];
                samples_after[i*56+48+:8]=pixel_rgb[7:0];
                mask_after[i]=1'b1;
            end
        end
        record_after=0;
        record_after[0+:64]=64'h3130304749534750; // "PGSIG001"
        record_after[64+:8]=1; // protocol version
        record_after[72+:8]=2; // canonical RGB888 R,G,B bytes
        record_after[80+:8]=1; // final registered digital scan tap
        record_after[88+:8]=1; // COMPLETE (no partial records are published)
        record_after[96+:16]=128;
        record_after[112+:8]=8;
        record_after[120+:8]={7'b0,start_pixel ? bank:held_bank};
        record_after[128+:32]=start_pixel ? session_id:held_session;
        record_after[160+:32]=start_pixel ? scan_epoch:held_epoch;
        record_after[192+:32]=start_pixel ? frame_id:held_frame;
        record_after[224+:32]=start_pixel ? param_id:held_param;
        record_after[256+:32]=start_pixel ? next_sequence:frame_sequence;
        record_after[288+:32]=count_before+1'b1;
        record_after[320+:32]=~next_crc;
        record_after[352+:32]=dropped;
        record_after[384+:32]=aborted;
        record_after[416+:32]=malformed;
        record_after[448+:16]=WIDTH;
        record_after[464+:16]=HEIGHT;
        record_after[480+:8]=mask_after;
        record_after[488+:8]=start_pixel ? mode:held_mode;
        record_after[512+:448]=samples_after;
    end

    always @(posedge pix_clk or negedge rst_n)begin
        if(!rst_n)begin
            ack_sync<=0;active<=0;count<=0;crc<=32'hffffffff;
            next_sequence<=0;frame_sequence<=0;cursor_x<=0;cursor_y<=0;
            held_session<=0;held_epoch<=0;held_frame<=0;held_param<=0;held_bank<=0;held_mode<=0;
            sample_mask<=0;samples<=0;mailbox_data<=0;mailbox_request<=0;
            dropped<=0;aborted<=0;malformed<=0;
        end else if(!release_sync[1])begin
            ack_sync<=0;active<=0;count<=0;crc<=32'hffffffff;
            next_sequence<=0;frame_sequence<=0;cursor_x<=0;cursor_y<=0;
            held_session<=0;held_epoch<=0;held_frame<=0;held_param<=0;held_bank<=0;held_mode<=0;
            sample_mask<=0;samples<=0;mailbox_data<=0;mailbox_request<=0;
            dropped<=0;aborted<=0;malformed<=0;
        end else begin
            ack_sync<={ack_sync[0],mailbox_ack};
            if(start_pixel)begin frame_sequence<=next_sequence;next_sequence<=next_sequence+1'b1;end
            // Abort has priority even when a final pixel appears on the same edge.
            if(abort)begin
                if(candidate)aborted<=sat_inc(aborted);
                active<=0;
            end else if((frame_start || frame_last) && !pixel_valid)begin
                malformed<=sat_inc(malformed);active<=0;
            end else if(pixel_valid)begin
                if(!candidate || bad_pixel)begin
                    malformed<=sat_inc(malformed);active<=0;
                end else begin
                    if(start_pixel)begin
                        if(active)malformed<=sat_inc(malformed); // abandoned half frame
                        held_session<=session_id;held_epoch<=scan_epoch;held_frame<=frame_id;
                        held_param<=param_id;held_bank<=bank;held_mode<=mode;
                    end
                    crc<=next_crc;count<=count_before+1'b1;
                    samples<=samples_after;sample_mask<=mask_after;
                    if(pixel_x==WIDTH-1)begin cursor_x<=0;cursor_y<=pixel_y+1'b1;end
                    else begin cursor_x<=pixel_x+1'b1;cursor_y<=pixel_y;end
                    if(frame_last)begin
                        active<=0;
                        if(count_before+1'b1!=PIXELS || mask_after!=8'hff)malformed<=sat_inc(malformed);
                        else if(mailbox_request!=ack_sync[1])dropped<=sat_inc(dropped);
                        else begin mailbox_data<=record_after;mailbox_request<=!mailbox_request;end
                    end else if(count_before+1'b1==PIXELS)begin
                        malformed<=sat_inc(malformed);active<=0; // missing frame_last
                    end else active<=1;
                end
            end
        end
    end
endmodule
