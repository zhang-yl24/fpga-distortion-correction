`timescale 1ns/1ps
// Offline development candidate. VSYNC is an already-normalized active-high
// frame boundary, NOT a measured MS7200 polarity/lock indication. RGB order
// follows the local HDMI reference: {R[7:3],G[7:2],B[7:3]}.
// One reservation/termination mailbox at a time; an unthrottled source is
// discarded as a WHOLE frame on missing reservation, geometry or FIFO error.
// Common rst_n asserts both domains; each releases through two local flops.
// A future board integration must constrain Gray skew and held mailbox buses.
// Independent single-domain reset/clock-stop recovery is NOT implemented.
module hdmi1080_capture_cdc #(
    parameter WIDTH=1920,HEIGHT=1080,FIFO_ADDR_BITS=6
)(
    input pix_clk,sys_clk,rst_n,enable,
    input pix_vsync_active,pix_de,input [23:0] pix_rgb,
    input grant_valid,output grant_ready,input [1:0] grant_bank,input [31:0] grant_id,
    output fifo_valid,input fifo_ready,output [255:0] fifo_data,output fifo_idle,
    output done_valid,input done_ready,output done_good,output [1:0] done_bank,
    output [31:0] done_id,done_pixels,done_crc,output [7:0] done_fault,
    output [31:0] no_grant_frames
);
    (* PAP_ASYNC_REG=1, syn_srlstyle="registers" *) reg [1:0] pix_reset,sys_reset;
    always @(posedge pix_clk or negedge rst_n)
        if(!rst_n)pix_reset<=0;else pix_reset<={pix_reset[0],1'b1};
    always @(posedge sys_clk or negedge rst_n)
        if(!rst_n)sys_reset<=0;else sys_reset<={sys_reset[0],1'b1};
    wire pr=pix_reset[1],sr=sys_reset[1];
    (* PAP_ASYNC_REG=1, syn_srlstyle="registers" *) reg [1:0] enable_pix;
    reg grant_request,grant_busy;reg [1:0] grant_bank_hold;reg [31:0] grant_id_hold;
    reg done_ack;
    (* PAP_ASYNC_REG=1, syn_srlstyle="registers" *) reg [1:0] grant_sync,done_sync,ack_sync;
    reg grant_seen,pending_grant;reg [1:0] pending_bank;reg [31:0] pending_id;
    reg end_request,end_good;reg [1:0] end_bank;reg [31:0] end_id,end_pixels,end_crc;
    reg [7:0] end_fault;
    wire end_wait=end_request!=ack_sync[1];
    assign grant_ready=sr && !grant_busy;
    assign done_valid=sr && done_sync[1]!=done_ack;
    assign done_good=end_good;assign done_bank=end_bank;assign done_id=end_id;
    assign done_pixels=end_pixels;assign done_crc=end_crc;assign done_fault=end_fault;
    always @(posedge sys_clk or negedge rst_n)begin
        if(!rst_n)begin
            grant_request<=0;grant_busy<=0;grant_bank_hold<=0;grant_id_hold<=0;
            done_sync<=0;done_ack<=0;
        end else if(!sr)begin
            grant_request<=0;grant_busy<=0;grant_bank_hold<=0;grant_id_hold<=0;
            done_sync<=0;done_ack<=0;
        end else begin
            done_sync<={done_sync[0],end_request};
            if(grant_valid && grant_ready)begin
                grant_request<=!grant_request;grant_busy<=1;
                grant_bank_hold<=grant_bank;grant_id_hold<=grant_id;
            end
            if(done_valid && done_ready)begin done_ack<=done_sync[1];grant_busy<=0;end
        end
    end

    // Reuse the unchanged synchronous-read FIFO. A pending read is NOT empty:
    // preserve its registered return in a holding word until downstream ready.
    wire [15:0] pixel565={pix_rgb[23:19],pix_rgb[15:10],pix_rgb[7:3]};
    reg [3:0] pack_count;reg [255:0] pack_buffer;
    wire push;
    wire fifo_full,fifo_write_ready,read_empty,read_ready,read_valid;
    wire [255:0] read_data;wire [FIFO_ADDR_BITS:0] unused_available,unused_used;
    reg read_pending,holding_valid;reg [255:0] holding_data;
    wire read_request=sr && !holding_valid && !read_pending && !read_valid && read_ready;
    assign fifo_valid=sr && holding_valid;
    assign fifo_data=holding_data;
    assign fifo_idle=sr && read_empty && !read_pending && !read_valid && !holding_valid;
    video_async_fifo #(.DATA_BITS(256),.ADDR_BITS(FIFO_ADDR_BITS)) pixels(
        .wr_clk(pix_clk),.rd_clk(sys_clk),.rst_n(rst_n),
        .wr_en(push),.wr_data({pixel565,pack_buffer[239:0]}),.wr_full(fifo_full),.wr_ready(fifo_write_ready),
        .rd_en(read_request),.rd_data(read_data),.rd_valid(read_valid),.rd_empty(read_empty),.rd_ready(read_ready),
        .rd_available(unused_available),.wr_used(unused_used));
    always @(posedge sys_clk or negedge rst_n)begin
        if(!rst_n)begin read_pending<=0;holding_valid<=0;holding_data<=0;end
        else if(!sr)begin read_pending<=0;holding_valid<=0;holding_data<=0;end
        else begin
            if(fifo_valid && fifo_ready)holding_valid<=0;
            if(read_request)read_pending<=1;
            if(read_valid)begin holding_valid<=1;holding_data<=read_data;read_pending<=0;end
        end
    end
    function [31:0] crc_byte(input [31:0] c,input [7:0] b);
        reg [31:0] x;integer k;
        begin x=c^b;for(k=0;k<8;k=k+1)x=x[0] ? (x>>1)^32'hedb88320:x>>1;crc_byte=x;end
    endfunction
    reg vs_d,de_d,window_seen,first_de_seen,capturing;reg [1:0] capture_bank;
    reg [31:0] capture_id,pixel_count,row_pixels,line_count,crc_state;
    reg [7:0] bad;
    reg [31:0] no_grant_bin,no_grant_gray;
    (* PAP_ASYNC_REG=1, syn_srlstyle="registers" *) reg [31:0] no_grant_s1,no_grant_s2;
    function [31:0] gray_binary(input [31:0] g);
        integer n;begin gray_binary[31]=g[31];for(n=30;n>=0;n=n-1)gray_binary[n]=gray_binary[n+1]^g[n];end
    endfunction
    assign no_grant_frames=gray_binary(no_grant_s2);
    always @(posedge sys_clk or negedge rst_n)begin
        if(!rst_n)begin no_grant_s1<=0;no_grant_s2<=0;end
        else if(!sr)begin no_grant_s1<=0;no_grant_s2<=0;end
        else begin no_grant_s1<=no_grant_gray;no_grant_s2<=no_grant_s1;end
    end
    wire sof=pix_vsync_active && !vs_d;
    wire begin_capture=window_seen && !first_de_seen && pix_de && !pix_vsync_active &&
        !capturing && pending_grant && !end_wait && enable_pix[1];
    assign push=pr && capturing && pix_de && !sof && !pix_vsync_active &&
        bad==0 && enable_pix[1] && pack_count==15 && fifo_write_ready;
    always @(posedge pix_clk or negedge rst_n)begin
        if(!rst_n)begin
            enable_pix<=0;grant_sync<=0;ack_sync<=0;grant_seen<=0;pending_grant<=0;pending_bank<=0;pending_id<=0;
            end_request<=0;end_good<=0;end_bank<=0;end_id<=0;end_pixels<=0;end_crc<=0;end_fault<=0;
            vs_d<=0;de_d<=0;window_seen<=0;first_de_seen<=0;capturing<=0;capture_bank<=0;capture_id<=0;
            pixel_count<=0;row_pixels<=0;line_count<=0;crc_state<=32'hffffffff;bad<=0;
            pack_count<=0;pack_buffer<=0;no_grant_bin<=0;no_grant_gray<=0;
        end else if(!pr)begin
            enable_pix<=0;grant_sync<=0;ack_sync<=0;grant_seen<=0;pending_grant<=0;pending_bank<=0;pending_id<=0;
            end_request<=0;end_good<=0;end_bank<=0;end_id<=0;end_pixels<=0;end_crc<=0;end_fault<=0;
            vs_d<=0;de_d<=0;window_seen<=0;first_de_seen<=0;capturing<=0;capture_bank<=0;capture_id<=0;
            pixel_count<=0;row_pixels<=0;line_count<=0;crc_state<=32'hffffffff;bad<=0;
            pack_count<=0;pack_buffer<=0;no_grant_bin<=0;no_grant_gray<=0;
        end else begin
            enable_pix<={enable_pix[0],enable};grant_sync<={grant_sync[0],grant_request};ack_sync<={ack_sync[0],done_ack};
            vs_d<=pix_vsync_active;de_d<=pix_de;
            if(grant_sync[1]!=grant_seen)begin
                pending_grant<=1;pending_bank<=grant_bank_hold;pending_id<=grant_id_hold;grant_seen<=grant_sync[1];
            end
            if(sof)begin
                window_seen<=1;first_de_seen<=0;
                if(capturing)begin
                    end_request<=!end_request;end_bank<=capture_bank;end_id<=capture_id;
                    end_pixels<=pixel_count;end_crc<=~crc_state;
                    end_good<=bad==0 && !de_d && !pix_de && line_count==HEIGHT &&
                        pixel_count==WIDTH*HEIGHT && pack_count==0 && enable_pix[1];
                    end_fault<=bad | ((de_d || pix_de) ? 8'h10:8'h00) |
                        ((line_count!=HEIGHT || pixel_count!=WIDTH*HEIGHT || pack_count!=0) ? 8'h04:8'h00) |
                        (!enable_pix[1] ? 8'h20:8'h00);
                    capturing<=0;
                end
            end else begin
                if(window_seen && !first_de_seen && pix_de)begin
                    first_de_seen<=1;
                    if(!begin_capture)begin
                        no_grant_bin<=no_grant_bin+1'b1;
                        no_grant_gray<=((no_grant_bin+1'b1)>>1)^(no_grant_bin+1'b1);
                    end
                end
                if(begin_capture)begin
                    capturing<=1;capture_bank<=pending_bank;capture_id<=pending_id;pending_grant<=0;
                    pixel_count<=1;row_pixels<=1;line_count<=0;bad<=0;
                    crc_state<=crc_byte(crc_byte(32'hffffffff,pixel565[7:0]),pixel565[15:8]);
                    pack_count<=1;pack_buffer<={240'd0,pixel565};
                end else if(capturing)begin
                    if(!enable_pix[1])bad<=bad|8'h20;
                    if(pix_de)begin
                        pixel_count<=pixel_count+1'b1;row_pixels<=row_pixels+1'b1;
                        crc_state<=crc_byte(crc_byte(crc_state,pixel565[7:0]),pixel565[15:8]);
                        if(row_pixels>=WIDTH || line_count>=HEIGHT || pix_vsync_active)bad<=bad|8'h02;
                        if(bad==0 && enable_pix[1])begin
                            pack_buffer[pack_count*16+:16]<=pixel565;
                            if(pack_count==15)begin
                                pack_count<=0;
                                if(!fifo_write_ready)bad<=bad|8'h08;
                            end else pack_count<=pack_count+1'b1;
                        end
                    end
                    if(de_d && !pix_de)begin
                        if(row_pixels!=WIDTH)bad<=bad|8'h01;
                        line_count<=line_count+1'b1;row_pixels<=0;
                    end
                end
            end
        end
    end
endmodule
