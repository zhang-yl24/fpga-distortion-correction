`timescale 1ns/1ps
// Pixel-domain logical control only. No raw UART or asynchronous input may
// connect here without a held-bundle adapter. Every output is telemetry-local.
module session_arm_gate_v3(
    input wire pix_clk,rst_n,
    input wire load_valid,output wire load_ready,
    input wire [31:0] load_ticket,load_nonce,
    output reg ack_valid,input wire ack_ready,
    output reg [31:0] ack_ticket,ack_nonce,ack_epoch,
    output reg [7:0] ack_status,
    input wire pixel_valid,frame_start,video_abort,
    input wire [31:0] scan_epoch,
    output wire capture_enable,capture_abort,
    output wire [31:0] capture_session
);
    localparam [7:0] ARMED=8'h01,BAD_ARGUMENT=8'h10,STALE_TICKET=8'h11,
        NONCE_REUSE=8'h12,DUPLICATE=8'h13,ABORTED=8'h14;
    (* async_reg="true" *) reg [1:0] release_sync=0;
    reg armed,pending,have_ticket;
    reg [31:0] active_nonce,pending_ticket,pending_nonce,last_ticket,last_nonce;
    wire fire=load_valid && load_ready;
    wire bad_argument=load_ticket==0 || load_nonce==0;
    wire duplicate=have_ticket && load_ticket==last_ticket && load_nonce==last_nonce;
    wire stale=have_ticket && load_ticket<=last_ticket;
    wire reuse_nonce=have_ticket && load_nonce==last_nonce;
    wire new_load=fire && !bad_argument && !duplicate && !stale && !reuse_nonce;
    wire activate=release_sync[1] && pending && !ack_valid &&
        pixel_valid && frame_start && !fire && !video_abort;
    assign load_ready=release_sync[1] && !ack_valid && !video_abort;
    assign capture_enable=release_sync[1] && (armed || activate) && !new_load && !video_abort;
    assign capture_abort=new_load || video_abort;
    assign capture_session=activate ? pending_nonce:active_nonce;
    always @(posedge pix_clk or negedge rst_n)
        if(!rst_n)release_sync<=0;else release_sync<={release_sync[0],1'b1};
    always @(posedge pix_clk or negedge rst_n)begin
        if(!rst_n)begin
            armed<=0;pending<=0;have_ticket<=0;active_nonce<=0;pending_ticket<=0;pending_nonce<=0;
            last_ticket<=0;last_nonce<=0;ack_valid<=0;ack_ticket<=0;ack_nonce<=0;ack_epoch<=0;ack_status<=0;
        end else if(!release_sync[1])begin
            armed<=0;pending<=0;have_ticket<=0;active_nonce<=0;pending_ticket<=0;pending_nonce<=0;
            last_ticket<=0;last_nonce<=0;ack_valid<=0;ack_ticket<=0;ack_nonce<=0;ack_epoch<=0;ack_status<=0;
        end else begin
            if(ack_valid && ack_ready)ack_valid<=0;
            if(video_abort)begin
                armed<=0;
                if(pending && !ack_valid)begin
                    ack_valid<=1;ack_ticket<=pending_ticket;ack_nonce<=pending_nonce;
                    ack_epoch<=0;ack_status<=ABORTED;
                end
                pending<=0;
            end else if(fire)begin
                if(new_load)begin
                    armed<=0;pending<=1;pending_ticket<=load_ticket;pending_nonce<=load_nonce;
                    have_ticket<=1;last_ticket<=load_ticket;last_nonce<=load_nonce;
                end else begin
                    ack_valid<=1;ack_ticket<=load_ticket;ack_nonce<=load_nonce;ack_epoch<=0;
                    if(bad_argument)ack_status<=BAD_ARGUMENT;
                    else if(duplicate)ack_status<=DUPLICATE;
                    else if(stale)ack_status<=STALE_TICKET;
                    else ack_status<=NONCE_REUSE;
                end
            end else if(activate)begin
                armed<=1;pending<=0;active_nonce<=pending_nonce;
                ack_valid<=1;ack_ticket<=pending_ticket;ack_nonce<=pending_nonce;
                ack_epoch<=scan_epoch;ack_status<=ARMED;
            end
        end
    end
endmodule
