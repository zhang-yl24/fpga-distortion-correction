`timescale 1ns/1ps
// Version 2 of the receive-only HDMI diagnostic packet. The five monitor
// freshness inputs are already in ref_clk and describe recent observer-domain
// activity, not HDMI PHY lock or pixel payload.
module hdmi_diag_uart_v2 #(
    parameter integer REF_CLOCK_HZ=27000000,
    parameter integer BAUD=115200,
    parameter integer REPORT_CYCLES=REF_CLOCK_HZ/2,
    parameter integer CFG_SNAPSHOT_CYCLES=REF_CLOCK_HZ/1000,
    parameter integer CFG_STALE_CYCLES=REF_CLOCK_HZ/100
)(
    input ref_clk, cfg_clk, rst_n,
    input cfg_rx_done, cfg_all_done, cfg_failed, input [3:0] cfg_error,
    input [31:0] cfg_transactions, input [15:0] cfg_last_address,
    input [7:0] cfg_last_value, input [1:0] cfg_last_meta,
    input cfg_lock_ref, video_lock_ref, observer_released,
    input input_qualified, input_failed, input [7:0] input_fault,
    input polarity_known_ref, vs_inactive_ref, hs_inactive_ref,
    input [15:0] measured_width, measured_height,
    input [31:0] pclk_edges_per_window, good_frames, bad_frames,
    input [4:0] observer_freshness,
    output uart_txd,
    output reg record_started, record_done,
    output reg [31:0] record_sequence
);
    (* async_reg="true" *) reg [1:0] ref_reset, cfg_reset;
    always @(posedge ref_clk or negedge rst_n)
        if(!rst_n) ref_reset<=0; else ref_reset<={ref_reset[0],1'b1};
    always @(posedge cfg_clk or negedge rst_n)
        if(!rst_n) cfg_reset<=0; else cfg_reset<={cfg_reset[0],1'b1};
    wire rr=ref_reset[1], cr=cfg_reset[1];
    reg snapshot_request, snapshot_ack;
    (* async_reg="true" *) reg [1:0] request_sync, ack_sync;
    reg [64:0] cfg_held, cfg_snapshot;
    reg ack_seen, settle, snapshot_valid;
    reg [31:0] snapshot_timer, snapshot_age;
    wire snapshot_fresh=snapshot_valid && snapshot_age<CFG_STALE_CYCLES;
    always @(posedge cfg_clk or negedge rst_n) begin
        if(!rst_n) begin request_sync<=0; snapshot_ack<=0; cfg_held<=0; end
        else if(!cr) begin request_sync<=0; snapshot_ack<=0; cfg_held<=0; end
        else begin
            request_sync<={request_sync[0],snapshot_request};
            if(request_sync[1]!=snapshot_ack) begin
                cfg_held<={cfg_rx_done,cfg_all_done,cfg_failed,cfg_error,
                    cfg_transactions,cfg_last_address,cfg_last_value,cfg_last_meta};
                snapshot_ack<=request_sync[1];
            end
        end
    end
    always @(posedge ref_clk or negedge rst_n) begin
        if(!rst_n) begin
            ack_sync<=0; snapshot_request<=0; ack_seen<=0; settle<=0;
            cfg_snapshot<=0; snapshot_valid<=0;
            snapshot_timer<=CFG_SNAPSHOT_CYCLES-1; snapshot_age<=32'hffffffff;
        end else if(!rr) begin
            ack_sync<=0; snapshot_request<=0; ack_seen<=0; settle<=0;
            cfg_snapshot<=0; snapshot_valid<=0;
            snapshot_timer<=CFG_SNAPSHOT_CYCLES-1; snapshot_age<=32'hffffffff;
        end else begin
            ack_sync<={ack_sync[0],snapshot_ack};
            if(snapshot_age!=32'hffffffff) snapshot_age<=snapshot_age+1'b1;
            if(snapshot_timer<CFG_SNAPSHOT_CYCLES-1) snapshot_timer<=snapshot_timer+1'b1;
            if(snapshot_request==ack_seen && !settle && snapshot_timer==CFG_SNAPSHOT_CYCLES-1) begin
                snapshot_request<=!snapshot_request; snapshot_timer<=0;
            end
            if(settle) begin
                cfg_snapshot<=cfg_held; snapshot_valid<=1; snapshot_age<=0;
                ack_seen<=ack_sync[1]; settle<=0;
            end else if(ack_sync[1]!=ack_seen) settle<=1;
        end
    end

    wire rx_done_ref, all_done_ref, failed_ref;
    wire [3:0] error_ref;
    wire [31:0] transactions_ref;
    wire [15:0] address_ref;
    wire [7:0] value_ref;
    wire [1:0] meta_ref;
    assign {rx_done_ref,all_done_ref,failed_ref,error_ref,
        transactions_ref,address_ref,value_ref,meta_ref}=cfg_snapshot;
    wire [15:0] flags={3'b000,hs_inactive_ref,vs_inactive_ref,input_failed,
        input_qualified,polarity_known_ref,observer_released,failed_ref,
        all_done_ref,rx_done_ref,video_lock_ref,cfg_lock_ref,snapshot_fresh,snapshot_valid};
    reg [31:0] ref_ticks, period_count;
    reg pending, active, tail_wait;
    reg [5:0] byte_index;
    reg [447:0] held_body;
    reg [31:0] crc;
    reg [447:0] current_body;
    always @* begin
        current_body=0;
        current_body[0*8+:64]=64'h3130494d44484750;
        current_body[8*8+:32]=record_sequence+1'b1;
        current_body[12*8+:32]=ref_ticks;
        current_body[16*8+:16]=flags;
        current_body[18*8+:8]={4'h0,error_ref};
        current_body[19*8+:8]=input_fault;
        current_body[20*8+:16]=measured_width;
        current_body[22*8+:16]=measured_height;
        current_body[24*8+:32]=pclk_edges_per_window;
        current_body[28*8+:32]=good_frames;
        current_body[32*8+:32]=bad_frames;
        current_body[36*8+:32]=snapshot_age;
        current_body[40*8+:32]=transactions_ref;
        current_body[44*8+:16]=address_ref;
        current_body[46*8+:8]=value_ref;
        current_body[47*8+:8]={6'b0,meta_ref};
        current_body[48*8+:32]=32'h48444902;
        current_body[52*8+:8]={3'b000,observer_freshness};
    end
    function [31:0] crc_byte(input [31:0] c, input [7:0] value);
        reg [31:0] x; integer k;
        begin
            x=c^value;
            for(k=0;k<8;k=k+1) x=x[0] ? (x>>1)^32'hedb88320 : x>>1;
            crc_byte=x;
        end
    endfunction
    wire tx_busy, tx_done;
    wire tx_start=active && !tail_wait && !tx_busy && !tx_done;
    wire [31:0] trailer=32'h31304d48;
    wire [7:0] tx_data=byte_index<56 ? held_body[byte_index*8+:8] :
        byte_index<60 ? ((~crc)>>((byte_index-56)*8)) : (trailer>>((byte_index-60)*8));
    uart_tx #(.CLOCK_HZ(REF_CLOCK_HZ),.BAUD(BAUD)) serial(
        .clk(ref_clk),.rst_n(rst_n && rr),.start(tx_start),.data(tx_data),
        .tx(uart_txd),.busy(tx_busy),.done(tx_done));
    always @(posedge ref_clk or negedge rst_n) begin
        if(!rst_n) begin
            ref_ticks<=0; period_count<=0; pending<=1; active<=0; tail_wait<=0;
            byte_index<=0; held_body<=0; crc<=32'hffffffff;
            record_started<=0; record_done<=0; record_sequence<=0;
        end else if(!rr) begin
            ref_ticks<=0; period_count<=0; pending<=1; active<=0; tail_wait<=0;
            byte_index<=0; held_body<=0; crc<=32'hffffffff;
            record_started<=0; record_done<=0; record_sequence<=0;
        end else begin
            ref_ticks<=ref_ticks+1'b1; record_started<=0; record_done<=0;
            if(period_count==REPORT_CYCLES-1) begin period_count<=0; pending<=1; end
            else period_count<=period_count+1'b1;
            if(!active && pending) begin
                held_body<=current_body; active<=1; pending<=0; tail_wait<=0;
                byte_index<=0; crc<=32'hffffffff;
                record_sequence<=record_sequence+1'b1; record_started<=1;
            end
            if(tx_start) begin
                if(byte_index<56) crc<=crc_byte(crc,tx_data);
                if(byte_index==63) tail_wait<=1;
                else byte_index<=byte_index+1'b1;
            end
            if(active && tail_wait && tx_done) begin
                active<=0; tail_wait<=0; record_done<=1;
            end
        end
    end
endmodule
