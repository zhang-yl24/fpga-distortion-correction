`timescale 1ns/1ps
// Source-clocked 1080p60 consumer. The default raster is 2200 x 1125;
// this source alone makes no physical clock, pin, DDR or HDMI claim.
// grant_* is a held bundle: publish before grant_toggle and retain until the
// synchronized grant_ack_toggle. done_* stays held until done_ack_toggle has
// crossed two flops. A fault never overwrites an unacknowledged good record;
// failed is an independent sticky veto and MUST qualify every parent release.
// fifo_ready is synchronous FIFO rd_ready; each rd_en has one later valid/data
// response. Faults discard queued/return data and keep draining until a COMMON
// consumer/FIFO/DDR-domain reset. draining is a MODE, not an empty indication.
module ddr_video_output_1080_board #(
    parameter WIDTH=1920,HEIGHT=1080,HT=2200,VT=1125,HS=44,VS=5,
    X0=192,Y0=41,AW=1920,AH=1080
)(
    input clk,rst_n,enable,abort,input [7:0] abort_fault,
    output reg request_toggle,output reg [31:0] request_epoch,
    input grant_toggle,grant_valid,input [31:0] grant_epoch,grant_checksum,grant_id,
    input grant_bank,output reg grant_ack_toggle,
    input done_ack_toggle,
    input fifo_ready,fifo_valid,input [255:0] fifo_data,output fifo_rd_en,
    output reg hs,vs,de,output reg [7:0] r,g,b,output reg display_valid,
    output reg done_toggle,done_good,output reg [31:0] done_epoch,done_id,done_crc,
    output reg done_bank,output reg [31:0] consumed_pixels,
    output reg frame_active,output reg [31:0] active_id,output reg active_bank,
    output reg frame_start,frame_last,pixel_valid,
    output reg failed,output reg [7:0] fault,output draining,
    output reg [31:0] completed_frames,underflows,mismatches
);
    `include "D:/English/FPGA/distortion/rtl/video_crc32.vh"
    localparam WX=X0+(AW-WIDTH)/2,WY=Y0+(AH-HEIGHT)/2;
    localparam FRAME_PIXELS=WIDTH*HEIGHT,FRAME_BEATS=FRAME_PIXELS/16;
    localparam CONFIG_OK=WIDTH>=16 && HEIGHT>=1 && WIDTH%16==0 &&
        HT>=1 && HT<=4096 && VT>=1 && VT<=4096 && X0>=0 && Y0>=0 &&
        AW>=WIDTH && AH>=HEIGHT && X0+AW<=HT && Y0+AH<=VT &&
        (WY>0 || WX>0) && HS>=0 && HS<=HT && VS>=0 && VS<=VT;
    function integer count_bits(input integer maximum);
        integer n;
        begin n=maximum;count_bits=0;while(n>0)begin count_bits=count_bits+1;n=n>>1;end end
    endfunction
    localparam COUNT_BITS=count_bits(FRAME_BEATS)<17 ? 17:count_bits(FRAME_BEATS);
    (* PAP_ASYNC_REG=1, syn_srlstyle="registers" *) reg [1:0] reset_sync=0,grant_sync=0,done_ack_sync=0;
    always @(posedge clk or negedge rst_n)
        if(!rst_n)reset_sync<=0;else reset_sync<={reset_sync[0],1'b1};
    reg [11:0] x,y;
    reg grant_seen,request_open;
    reg [31:0] lease_epoch,expected_crc,pixel_count,checksum;
    reg last_good_valid;reg [31:0] last_good_id,last_good_crc;reg last_good_bank;
    // Four explicit words avoid an inferred async memory read and a 16:1
    // pixel mux on the CRC feedback path. The active word shifts by one
    // RGB565 pixel; at each word boundary the remaining words shift forward.
    reg [255:0] word0,word1,word2,word3;
    reg completion_pending,final_counts_latched;
    // Position-only lookahead: WIDTH is a multiple of 16, so a picture
    // pixel at offset 14 is followed by offset 15 in the same active row.
    // Ownership, queue occupancy and failure remain live on the pop edge.
    reg word_end_position_q,picture_position_q;
    reg [2:0] queued;reg [7:0] inflight;
    reg [COUNT_BITS-1:0] requested_words,received_words;
    wire boundary=x==0 && y==0;
    wire active_area=x>=X0 && x<X0+AW && y>=Y0 && y<Y0+AH;
    // Position-only lookahead tracks the same next coordinates as the raster.
    // A legal picture excludes (0,0), so reset starts outside the picture.
    // Current ownership and all same-edge fault vetoes remain independent.
    wire [11:0] next_x=x==HT-1 ? 12'd0:x+12'd1;
    wire [11:0] next_y=x==HT-1 ? (y==VT-1 ? 12'd0:y+12'd1):y;
    wire picture=picture_position_q;
    wire pre_active=y<WY || (y==WY && x<WX);
    wire first_position=x==WX && y==WY;
    wire last_position=x==WX+WIDTH-1 && y==WY+HEIGHT-1;
    wire [11:0] column=x-WX;
    wire [15:0] pixel=word0[15:0];
    wire consume=picture && frame_active && queued!=0 && !failed;
    wire pop=word_end_position_q && frame_active && queued!=0 && !failed;
    wire [31:0] next_checksum=video_crc32_pixel(checksum,pixel);
    wire done_pending=done_toggle!=done_ack_sync[1];
    wire grant_event=grant_sync[1]!=grant_seen;
    wire [31:0] id_difference=grant_id-last_good_id;
    wire id_is_newer=id_difference!=0 && !id_difference[31];
    wire bad_id=grant_id==0 || (last_good_valid && grant_id!=last_good_id && !id_is_newer) ||
        (last_good_valid && grant_id==last_good_id && (grant_bank!=last_good_bank || grant_checksum!=last_good_crc));
    wire grant_allowed=request_open && pre_active && !frame_active && !completion_pending && !done_pending &&
        grant_epoch==request_epoch && enable;
    wire final_counts_ok=pixel_count==FRAME_PIXELS-1 && requested_words==FRAME_BEATS &&
        received_words==FRAME_BEATS && queued==1 && inflight==0 && !fifo_valid && !fifo_ready && !done_pending;
    // Fault priority is fixed. In particular, no successful completion may
    // outrun a same-edge abort, unsolicited response or invalid grant.
    reg [7:0] fault_now;
    always @* begin
        fault_now=0;
        if(!CONFIG_OK)fault_now=8'h01;
        else if(abort)fault_now=abort_fault!=0 ? abort_fault:8'h40;
        else if(!enable && (frame_active || completion_pending || request_open))fault_now=8'h07;
        else if(fifo_valid && inflight==0)fault_now=8'h04;
        else if(grant_event && !grant_allowed)fault_now=grant_epoch!=request_epoch ? 8'h05:8'h03;
        else if(grant_event && grant_valid && bad_id)fault_now=8'h06;
        else if(boundary && (frame_active || queued!=0 || inflight!=0))fault_now=8'h08;
        else if(first_position && request_open)fault_now=8'h03;
        else if(picture && frame_active && queued==0)fault_now=8'h02;
        else if(fifo_valid && queued>=4 && !pop)fault_now=8'h09;
        else if(completion_pending && !final_counts_latched)fault_now=8'h08;
        else if(completion_pending && (queued!=0 || inflight!=0 || fifo_valid || fifo_ready))fault_now=8'h08;
        else if(completion_pending && ~checksum!=expected_crc)fault_now=8'h0a;
    end
    assign draining=failed;
    assign fifo_rd_en=reset_sync[1] && fifo_ready &&
        (failed ? inflight<4 : frame_active && requested_words<FRAME_BEATS && queued+inflight<4);
    // No payload reset. Every live queue slot is written by an owned FIFO
    // response before use. Enqueue targets the post-pop tail so simultaneous
    // pop and return work for all queue depths, including replacement of the
    // only word. Source words on the right side are the pre-edge values.
    // Payload may move on the edge that detects a fault. The control block
    // vetoes that edge's RGB/valid/good result and clears queue ownership;
    // failed then quarantines this private storage until common reset.
    // Keeping fault_now out of these wide enables avoids a ready/fault path
    // from the FIFO to every payload bit. Unacknowledged done metadata is
    // stored independently and never written by this block.
    always @(posedge clk)begin
        if(reset_sync[1] && !failed)begin
            if(pop)begin word0<=word1;word1<=word2;word2<=word3;end
            else if(consume)word0<={16'd0,word0[255:16]};
            if(fifo_valid)begin
                case(queued-(pop ? 3'd1:3'd0))
                    0:word0<=fifo_data;
                    1:word1<=fifo_data;
                    2:word2<=fifo_data;
                    3:word3<=fifo_data;
                endcase
            end
        end
    end
    always @(posedge clk)begin
        if(!reset_sync[1])begin
            x<=0;y<=0;word_end_position_q<=0;picture_position_q<=0;completion_pending<=0;final_counts_latched<=0;queued<=0;inflight<=0;requested_words<=0;received_words<=0;
            grant_sync<=0;done_ack_sync<=0;grant_seen<=0;grant_ack_toggle<=0;
            request_toggle<=0;request_epoch<=0;request_open<=0;lease_epoch<=0;
            expected_crc<=0;checksum<=32'hffffffff;pixel_count<=0;
            last_good_valid<=0;last_good_id<=0;last_good_crc<=0;last_good_bank<=0;
            frame_active<=0;active_id<=0;active_bank<=0;frame_start<=0;frame_last<=0;pixel_valid<=0;
            done_toggle<=0;done_good<=0;done_epoch<=0;done_id<=0;done_bank<=0;done_crc<=0;consumed_pixels<=0;
            failed<=0;fault<=0;hs<=0;vs<=0;de<=0;r<=0;g<=0;b<=0;display_valid<=0;
            completed_frames<=0;underflows<=0;mismatches<=0;
        end else begin
            grant_sync<={grant_sync[0],grant_toggle};done_ack_sync<={done_ack_sync[0],done_ack_toggle};
            x<=next_x;y<=next_y;
            picture_position_q<=next_x>=WX && next_x<WX+WIDTH && next_y>=WY && next_y<WY+HEIGHT;
            word_end_position_q<=picture && column[3:0]==14;
            hs<=x<HS;vs<=y<VS;de<=active_area;
            frame_start<=0;frame_last<=0;pixel_valid<=0;r<=0;g<=0;b<=0;
            // Only the done toggle publishes these private fields. Prefetch
            // the current lease snapshot independently of the fault tree;
            // publication on this edge consumes the same pre-edge CRC/count.
            // An unacknowledged result owns the bundle and forbids updates.
            if(!done_pending && (frame_active || completion_pending))begin
                done_epoch<=lease_epoch;done_id<=active_id;done_bank<=active_bank;
                done_crc<=~checksum;consumed_pixels<=pixel_count;
            end
            // Prepare the next epoch independently of the wide fault tree.
            // Only request_toggle publishes it; that toggle retains the
            // same-edge fault veto below. Never alter an open held request.
            if(boundary && enable && !failed && !done_pending && !completion_pending &&
               !request_open && !frame_active && queued==0 && inflight==0)
                request_epoch<=request_epoch+1'b1;
            if(grant_event)begin grant_seen<=grant_sync[1];grant_ack_toggle<=grant_sync[1];end
            // Account every accepted FIFO request even on the edge that faults.
            // Unsolicited data is discarded without wrapping the inflight count.
            case({fifo_rd_en,fifo_valid && inflight!=0})
                2'b10:inflight<=inflight+1'b1;
                2'b01:inflight<=inflight-1'b1;
                default:inflight<=inflight;
            endcase
            if(failed)begin
                frame_active<=0;completion_pending<=0;request_open<=0;queued<=0;display_valid<=0;
                if(!done_pending)done_good<=0;
            end else if(fault_now!=0)begin
                failed<=1;fault<=fault_now;display_valid<=0;frame_active<=0;request_open<=0;
                queued<=0;completion_pending<=0;
                if(fault_now==8'h02)underflows<=underflows+1'b1;
                if(fault_now==8'h0a)mismatches<=mismatches+1'b1;
                // No unacknowledged result bundle is overwritten. An active
                // lease cannot normally coexist with an older pending result.
                if((frame_active || completion_pending) && !done_pending)begin
                    done_toggle<=!done_toggle;done_good<=0;
                end else if(!done_pending)done_good<=0;
            end else begin
                if(fifo_rd_en)requested_words<=requested_words+1'b1;
                if(fifo_valid)received_words<=received_words+1'b1;
                case({fifo_valid,pop})
                    2'b10:queued<=queued+1'b1;
                    2'b01:queued<=queued-1'b1;
                    default:queued<=queued;
                endcase
                if(boundary)begin
                    display_valid<=0;
                    if(enable && !done_pending && !completion_pending && !request_open)begin
                        request_toggle<=!request_toggle;request_open<=1;
                    end
                end
                if(!enable)display_valid<=0;
                if(grant_event)begin
                    request_open<=0;display_valid<=0;
                    if(grant_valid)begin
                        frame_active<=1;active_id<=grant_id;active_bank<=grant_bank;lease_epoch<=grant_epoch;
                        expected_crc<=grant_checksum;checksum<=32'hffffffff;pixel_count<=0;
                        requested_words<=0;received_words<=0;queued<=0;completion_pending<=0;final_counts_latched<=0;
                    end
                end
                if(completion_pending)begin
                    completion_pending<=0;display_valid<=1;
                    completed_frames<=completed_frames+1'b1;
                    done_toggle<=!done_toggle;done_good<=1;
                    last_good_valid<=1;last_good_id<=active_id;last_good_bank<=active_bank;last_good_crc<=~checksum;
                end
                if(consume)begin
                    r<={pixel[15:11],pixel[15:13]};g<={pixel[10:5],pixel[10:9]};b<={pixel[4:0],pixel[4:2]};
                    pixel_valid<=1;frame_start<=pixel_count==0;
                    checksum<=next_checksum;pixel_count<=pixel_count+1'b1;
                    if(last_position)begin
                        // The final pixel is emitted in its raster position.
                        // Final counts and CRC are checked from registers on
                        // the next cycle, before any good result is published.
                        // This removes pixel_count -> comparison -> fault ->
                        // pixel_count enable from the per-pixel feedback path.
                        final_counts_latched<=final_counts_ok;
                        frame_last<=1;frame_active<=0;completion_pending<=1;
                    end
                end
            end
        end
    end
endmodule
