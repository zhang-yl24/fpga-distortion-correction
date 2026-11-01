`timescale 1ns/1ps
// Offline candidate: byte-wide RGB565 DVP ingress for the existing capture
// reservation/FIFO/completion contract. This is NOT a board pin/polarity proof.
// WIDTH must be a positive multiple of 16; FIFO_ADDR_BITS must be >= 2.
// A grant is consumed only by the FIRST active byte after a VSYNC boundary.
// If it arrives later, the entire current frame is discarded. Completion is
// published at the NEXT VSYNC, including partial/failed captures. The consumer
// must drain emitted words and quarantine a bad frame before reusing its bank.
// RGB565 is preserved; lane zero is the earliest pixel; CRC feeds low byte
// then high byte regardless of the sensor's byte order. HREF is line activity,
// not pixel-valid: exactly two active bytes form one pixel.
// Fault bits: 01 row width, 02 excess pixels/rows, 04 frame geometry/partial
// pack, 08 FIFO overflow, 10 VSYNC interrupted HREF, 20 enable lost, 40 odd row.
// Common reset asserts both domains, with local synchronous release. Independent
// reset/clock-stop recovery is NOT provided. A future physical integration must
// constrain the Gray pointers and held mailbox buses and monitor camera clock.
module dvp_rgb565_capture_cdc #(
    parameter WIDTH=1280, HEIGHT=720, FIFO_ADDR_BITS=6,
    parameter VSYNC_ACTIVE_HIGH=1, HREF_ACTIVE_HIGH=1, HIGH_BYTE_FIRST=1
)(
    input cam_clk, sys_clk, rst_n, enable,
    input cam_vsync, cam_href, input [7:0] cam_data,
    input grant_valid, output grant_ready, input grant_bank, input [31:0] grant_id,
    output fifo_valid, input fifo_ready, output [255:0] fifo_data, output fifo_idle,
    output done_valid, input done_ready, output done_good, done_bank,
    output [31:0] done_id, done_pixels, done_crc, output [7:0] done_fault,
    output [31:0] no_grant_frames
);
    wire vs_active=VSYNC_ACTIVE_HIGH ? cam_vsync : !cam_vsync;
    wire href_active=HREF_ACTIVE_HIGH ? cam_href : !cam_href;
    (* async_reg="true" *) reg [1:0] cam_reset, sys_reset;
    always @(posedge cam_clk or negedge rst_n)
        if(!rst_n) cam_reset<=0; else cam_reset<={cam_reset[0],1'b1};
    always @(posedge sys_clk or negedge rst_n)
        if(!rst_n) sys_reset<=0; else sys_reset<={sys_reset[0],1'b1};
    wire cr=cam_reset[1], sr=sys_reset[1];
    (* async_reg="true" *) reg [1:0] enable_cam;
    reg grant_request, grant_busy, grant_bank_hold;
    reg [31:0] grant_id_hold;
    reg done_ack;
    (* async_reg="true" *) reg [1:0] grant_sync, done_sync, ack_sync;
    reg grant_seen, pending_grant, pending_bank;
    reg [31:0] pending_id;
    reg end_request, end_good, end_bank;
    reg [31:0] end_id, end_pixels, end_crc;
    reg [7:0] end_fault;
    wire end_wait=end_request!=ack_sync[1];
    assign grant_ready=sr && !grant_busy;
    assign done_valid=sr && done_sync[1]!=done_ack;
    assign done_good=end_good; assign done_bank=end_bank; assign done_id=end_id;
    assign done_pixels=end_pixels; assign done_crc=end_crc; assign done_fault=end_fault;
    always @(posedge sys_clk or negedge rst_n) begin
        if(!rst_n) begin
            grant_request<=0; grant_busy<=0; grant_bank_hold<=0; grant_id_hold<=0;
            done_sync<=0; done_ack<=0;
        end else if(!sr) begin
            grant_request<=0; grant_busy<=0; grant_bank_hold<=0; grant_id_hold<=0;
            done_sync<=0; done_ack<=0;
        end else begin
            done_sync<={done_sync[0],end_request};
            if(grant_valid && grant_ready) begin
                grant_request<=!grant_request; grant_busy<=1;
                grant_bank_hold<=grant_bank; grant_id_hold<=grant_id;
            end
            if(done_valid && done_ready) begin done_ack<=done_sync[1]; grant_busy<=0; end
        end
    end

    reg half_byte; reg [7:0] first_byte;
    wire [15:0] pixel565=HIGH_BYTE_FIRST ? {first_byte,cam_data} : {cam_data,first_byte};
    reg [3:0] pack_count; reg [255:0] pack_buffer;
    wire push, fifo_full, fifo_write_ready, read_empty, read_ready, read_valid;
    wire [255:0] read_data;
    wire [FIFO_ADDR_BITS:0] unused_available, unused_used;
    reg read_pending, holding_valid; reg [255:0] holding_data;
    wire read_request=sr && !holding_valid && !read_pending && !read_valid && read_ready;
    assign fifo_valid=sr && holding_valid;
    assign fifo_data=holding_data;
    assign fifo_idle=sr && read_empty && !read_pending && !read_valid && !holding_valid;
    // Identical registered-read/holding-word discipline to hdmi1080_capture_cdc.
    video_async_fifo #(.DATA_BITS(256),.ADDR_BITS(FIFO_ADDR_BITS)) pixels(
        .wr_clk(cam_clk),.rd_clk(sys_clk),.rst_n(rst_n),
        .wr_en(push),.wr_data({pixel565,pack_buffer[239:0]}),
        .wr_full(fifo_full),.wr_ready(fifo_write_ready),
        .rd_en(read_request),.rd_data(read_data),.rd_valid(read_valid),
        .rd_empty(read_empty),.rd_ready(read_ready),
        .rd_available(unused_available),.wr_used(unused_used));
    always @(posedge sys_clk or negedge rst_n) begin
        if(!rst_n) begin read_pending<=0; holding_valid<=0; holding_data<=0; end
        else if(!sr) begin read_pending<=0; holding_valid<=0; holding_data<=0; end
        else begin
            if(fifo_valid && fifo_ready) holding_valid<=0;
            if(read_request) read_pending<=1;
            if(read_valid) begin holding_valid<=1; holding_data<=read_data; read_pending<=0; end
        end
    end
    function [31:0] crc_byte(input [31:0] c, input [7:0] b);
        reg [31:0] x; integer k;
        begin
            x=c^b;
            for(k=0;k<8;k=k+1) x=x[0] ? (x>>1)^32'hedb88320 : x>>1;
            crc_byte=x;
        end
    endfunction
    reg vs_d, href_d, window_seen, first_href_seen, capturing, capture_bank;
    reg [31:0] capture_id, pixel_count, row_pixels, line_count, crc_state;
    reg [7:0] bad;
    reg [31:0] no_grant_bin, no_grant_gray;
    (* async_reg="true" *) reg [31:0] no_grant_s1, no_grant_s2;
    function [31:0] gray_binary(input [31:0] g);
        integer n;
        begin gray_binary[31]=g[31]; for(n=30;n>=0;n=n-1) gray_binary[n]=gray_binary[n+1]^g[n]; end
    endfunction
    assign no_grant_frames=gray_binary(no_grant_s2);
    always @(posedge sys_clk or negedge rst_n) begin
        if(!rst_n) begin no_grant_s1<=0; no_grant_s2<=0; end
        else if(!sr) begin no_grant_s1<=0; no_grant_s2<=0; end
        else begin no_grant_s1<=no_grant_gray; no_grant_s2<=no_grant_s1; end
    end
    wire sof=vs_active && !vs_d;
    wire line_end=href_d && !href_active;
    wire begin_capture=window_seen && !first_href_seen && href_active && !vs_active &&
        !capturing && pending_grant && !end_wait && enable_cam[1];
    wire pixel_valid=capturing && href_active && half_byte && !vs_active;
    // Collect all simultaneous causes once; one nonblocking assignment must
    // not accidentally overwrite enable loss with a geometry/overflow cause.
    wire [7:0] cycle_fault=(enable_cam[1] ? 8'h00 : 8'h20) |
        ((href_active && (row_pixels>=WIDTH || line_count>=HEIGHT)) ? 8'h02 : 8'h00) |
        ((line_end && row_pixels!=WIDTH) ? 8'h01 : 8'h00) |
        ((line_end && half_byte) ? 8'h40 : 8'h00) |
        ((pixel_valid && bad==0 && pack_count==15 && !fifo_write_ready) ? 8'h08 : 8'h00);
    wire [7:0] final_fault=bad |
        ((href_d || href_active) ? 8'h10 : 8'h00) |
        (half_byte ? 8'h40 : 8'h00) |
        ((line_count!=HEIGHT || pixel_count!=WIDTH*HEIGHT || pack_count!=0) ? 8'h04 : 8'h00) |
        (enable_cam[1] ? 8'h00 : 8'h20);
    assign push=cr && pixel_valid && !sof && bad==0 && cycle_fault==0 &&
        pack_count==15 && fifo_write_ready;
    always @(posedge cam_clk or negedge rst_n) begin
        if(!rst_n) begin
            enable_cam<=0; grant_sync<=0; ack_sync<=0; grant_seen<=0;
            pending_grant<=0; pending_bank<=0; pending_id<=0;
            end_request<=0; end_good<=0; end_bank<=0; end_id<=0;
            end_pixels<=0; end_crc<=0; end_fault<=0;
            vs_d<=0; href_d<=0; window_seen<=0; first_href_seen<=0;
            capturing<=0; capture_bank<=0; capture_id<=0;
            pixel_count<=0; row_pixels<=0; line_count<=0; crc_state<=32'hffffffff;
            bad<=0; half_byte<=0; first_byte<=0; pack_count<=0; pack_buffer<=0;
            no_grant_bin<=0; no_grant_gray<=0;
        end else if(!cr) begin
            enable_cam<=0; grant_sync<=0; ack_sync<=0; grant_seen<=0;
            pending_grant<=0; pending_bank<=0; pending_id<=0;
            end_request<=0; end_good<=0; end_bank<=0; end_id<=0;
            end_pixels<=0; end_crc<=0; end_fault<=0;
            vs_d<=0; href_d<=0; window_seen<=0; first_href_seen<=0;
            capturing<=0; capture_bank<=0; capture_id<=0;
            pixel_count<=0; row_pixels<=0; line_count<=0; crc_state<=32'hffffffff;
            bad<=0; half_byte<=0; first_byte<=0; pack_count<=0; pack_buffer<=0;
            no_grant_bin<=0; no_grant_gray<=0;
        end else begin
            enable_cam<={enable_cam[0],enable};
            grant_sync<={grant_sync[0],grant_request}; ack_sync<={ack_sync[0],done_ack};
            vs_d<=vs_active; href_d<=href_active;
            if(grant_sync[1]!=grant_seen) begin
                pending_grant<=1; pending_bank<=grant_bank_hold;
                pending_id<=grant_id_hold; grant_seen<=grant_sync[1];
            end
            if(sof) begin
                window_seen<=1; first_href_seen<=href_active; half_byte<=0;
                // HREF already active at VSYNC cannot be treated as a fresh
                // first byte when VSYNC later falls. Wait for a clean frame.
                if(capturing) begin
                    end_request<=!end_request; end_bank<=capture_bank; end_id<=capture_id;
                    end_pixels<=pixel_count; end_crc<=~crc_state;
                    end_good<=final_fault==0; end_fault<=final_fault; capturing<=0;
                end
            end else begin
                if(window_seen && !first_href_seen && href_active) begin
                    first_href_seen<=1;
                    if(!begin_capture) begin
                        no_grant_bin<=no_grant_bin+1'b1;
                        no_grant_gray<=((no_grant_bin+1'b1)>>1)^(no_grant_bin+1'b1);
                    end
                end
                if(begin_capture) begin
                    capturing<=1; capture_bank<=pending_bank; capture_id<=pending_id; pending_grant<=0;
                    pixel_count<=0; row_pixels<=0; line_count<=0; bad<=0; crc_state<=32'hffffffff;
                    half_byte<=1; first_byte<=cam_data; pack_count<=0; pack_buffer<=0;
                end else if(capturing) begin
                    bad<=bad|cycle_fault;
                    if(href_active && !vs_active) begin
                        half_byte<=!half_byte;
                        if(!half_byte) first_byte<=cam_data;
                        else begin
                            pixel_count<=pixel_count+1'b1; row_pixels<=row_pixels+1'b1;
                            crc_state<=crc_byte(crc_byte(crc_state,pixel565[7:0]),pixel565[15:8]);
                            if(bad==0 && cycle_fault==0) begin
                                pack_buffer[pack_count*16+:16]<=pixel565;
                                pack_count<=pack_count+1'b1;
                            end
                        end
                    end
                    if(line_end) begin
                        line_count<=line_count+1'b1; row_pixels<=0; half_byte<=0;
                    end
                end else half_byte<=0;
            end
        end
    end
endmodule
