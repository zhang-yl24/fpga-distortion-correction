`timescale 1ns/1ps
// Passive diagnostic only. Existing reference-domain status is sampled together
// once per packet. KEY0/global reset are observations, never this UART's reset.
module startup_status_uart #(
    parameter integer GAP_CLKS=6750000, MAX_PACKETS=120
)(
    input wire clk_27m,
    input wire cfg_lock_ref, video_lock_ref, rx_done_ref, tx_done_ref,
    input wire ddr_init_done, ddr_pll_lock,
    input wire input_qualified, pipeline_release,
    input wire pixclk_in, pix_de,
    input wire polarity_known, input_failed, input wire [7:0] input_fault,
    input wire [7:0] source_fault_ref,ref_fault_code,
    input wire source_fault_valid_ref,ref_fault_valid,
    input wire observer_startup_armed,observer_epoch_reset,
    input wire timing_detail_valid,input wire [135:0] timing_detail,
    input wire [31:0] good_frames,bad_frames,pclk_edges_per_window,
    input wire [15:0] last_pixels_per_line,last_lines,
    input wire key0_n, global_reset_n,
    output wire telemetry_tx
);
    reg [1:0] release_pipe=0;
    always @(posedge clk_27m) release_pipe<={release_pipe[0],1'b1};
    wire local_rst_n=release_pipe[1];
    (* PAP_ASYNC_REG="TRUE", async_reg="true" *) reg [1:0] key_sync=0,global_sync=0,ddr_init_sync=0,ddr_lock_sync=0;
    always @(posedge clk_27m) begin
        key_sync<={key_sync[0],key0_n};
        global_sync<={global_sync[0],global_reset_n};
        ddr_init_sync<={ddr_init_sync[0],ddr_init_done};
        ddr_lock_sync<={ddr_lock_sync[0],ddr_pll_lock};
    end
    reg [23:0] gap_count=0;
    reg [7:0] packet_count=0;
    reg [6:0] byte_index=0;
    reg [543:0] held_payload=0;
    reg [31:0] packet_crc=32'hffffffff;
    reg active=0,tx_start=0;
    reg [7:0] tx_data=0;
    wire tx_busy,tx_done;
    // Raw activity never depends on observer reset, enable or polarity.
    // Only a registered single bit crosses each boundary, never a binary bus.
    reg [7:0] raw_pixel_divider=0;
    reg raw_de_previous=0, raw_de_toggle=0;
    always @(posedge pixclk_in) begin
        raw_pixel_divider<=raw_pixel_divider+1'b1;
        raw_de_previous<=pix_de;
        if(pix_de && !raw_de_previous)raw_de_toggle<=~raw_de_toggle;
    end
    (* PAP_ASYNC_REG="TRUE", async_reg="true" *) reg [1:0] pclk_event_sync=0,de_event_sync=0;
    reg pclk_event_previous=0,de_event_previous=0;
    reg [31:0] raw_pclk_activity=0,raw_de_activity=0;
    always @(posedge clk_27m) begin
        pclk_event_sync<={pclk_event_sync[0],raw_pixel_divider[7]};
        de_event_sync<={de_event_sync[0],raw_de_toggle};
        if(!local_rst_n)begin
            pclk_event_previous<=0;de_event_previous<=0;
            raw_pclk_activity<=0;raw_de_activity<=0;
        end else begin
            pclk_event_previous<=pclk_event_sync[1];
            de_event_previous<=de_event_sync[1];
            if(pclk_event_sync[1]!=pclk_event_previous)raw_pclk_activity<=raw_pclk_activity+1'b1;
            if(de_event_sync[1]!=de_event_previous)raw_de_activity<=raw_de_activity+1'b1;
        end
    end
    reg [31:0] ref_uptime=0,detail_ref_tick=0,release_ref_tick=0;
    reg detail_previous=0,release_previous=0,detail_after_release=0;
    always @(posedge clk_27m)begin
        if(!local_rst_n)begin
            ref_uptime<=0;detail_ref_tick<=0;release_ref_tick<=0;
            detail_previous<=0;release_previous<=0;detail_after_release<=0;
        end else begin
            ref_uptime<=ref_uptime+1'b1;
            detail_previous<=timing_detail_valid;release_previous<=pipeline_release;
            if(!pipeline_release)release_ref_tick<=0;
            else if(!release_previous)release_ref_tick<=ref_uptime;
            if(!timing_detail_valid)begin detail_ref_tick<=0;detail_after_release<=0;end
            else if(!detail_previous)begin detail_ref_tick<=ref_uptime;detail_after_release<=pipeline_release;end
        end
    end
    // Snapshot the timestamp state for this same ref edge, not its NBA-old value.
    wire [31:0] packet_detail_tick = !timing_detail_valid ? 32'd0 :
        (!detail_previous ? ref_uptime : detail_ref_tick);
    wire [31:0] packet_release_tick = !pipeline_release ? 32'd0 :
        (!release_previous ? ref_uptime : release_ref_tick);
    wire packet_detail_after_release = !timing_detail_valid ? 1'b0 :
        (!detail_previous ? pipeline_release : detail_after_release);
    function [31:0] crc_byte;
        input [31:0] crc;
        input [7:0] data;
        reg [31:0] c;
        integer i;
        begin
            c=crc ^ data;
            for(i=0;i<8;i=i+1)c=c[0] ? (c>>1)^32'hedb88320 : (c>>1);
            crc_byte=c;
        end
    endfunction
    function [7:0] marker;
        input [6:0] n;
        begin
            if(n<68)marker=held_payload[n*8+:8];
            else case(n)
                68:marker=~packet_crc[7:0];69:marker=~packet_crc[15:8];
                70:marker=~packet_crc[23:16];71:marker=~packet_crc[31:24];
                default:marker=0;
            endcase
        end
    endfunction
    always @(posedge clk_27m) begin
        if(!local_rst_n) begin
            gap_count<=0;packet_count<=0;byte_index<=0;held_payload<=0;packet_crc<=32'hffffffff;
            active<=0;tx_start<=0;tx_data<=0;
        end else begin
            tx_start<=0;
            if(!active && packet_count<MAX_PACKETS) begin
                if(gap_count==GAP_CLKS-1) begin
                    gap_count<=0;byte_index<=0;active<=1;
                    held_payload[63:0]<=64'h343030504e494750; // PGINP004, byte0 first
                    held_payload[71:64]<={pipeline_release,input_qualified,ddr_lock_sync[1],ddr_init_sync[1],tx_done_ref,rx_done_ref,video_lock_ref,cfg_lock_ref};
                    held_payload[79:72]<={observer_epoch_reset,observer_startup_armed,ref_fault_valid,source_fault_valid_ref,input_failed,polarity_known,global_sync[1],key_sync[1]};
                    held_payload[87:80]<=input_fault;held_payload[95:88]<=8'd72;
                    held_payload[127:96]<=good_frames;held_payload[159:128]<=bad_frames;
                    held_payload[191:160]<=pclk_edges_per_window;
                    held_payload[207:192]<=last_pixels_per_line;held_payload[223:208]<=last_lines;
                    held_payload[255:224]<=raw_pclk_activity;held_payload[287:256]<=raw_de_activity;
                    held_payload[295:288]<=source_fault_ref;held_payload[303:296]<=ref_fault_code;
                    held_payload[311:304]<={3'b0,packet_detail_after_release,timing_detail[125],timing_detail[124],timing_detail[120],timing_detail_valid};
                    held_payload[319:312]<=timing_detail[135:128];
                    held_payload[351:320]<=packet_detail_tick;
                    held_payload[367:352]<=timing_detail[23:8];
                    held_payload[383:368]<=timing_detail[39:24];
                    held_payload[415:384]<=timing_detail[71:40];
                    held_payload[431:416]<=timing_detail[87:72];
                    held_payload[439:432]<=timing_detail[7:0];
                    held_payload[447:440]<={1'b0,(timing_detail[122]^timing_detail[127]),(timing_detail[123]^timing_detail[126]),timing_detail[127],timing_detail[126],timing_detail[123:121]};
                    held_payload[479:448]<=timing_detail[119:88];
                    held_payload[511:480]<=packet_release_tick;
                    held_payload[543:512]<=ref_uptime;
                    packet_crc<=32'hffffffff;
                end else gap_count<=gap_count+1'b1;
            end
            if(active && tx_done) begin
                if(byte_index==71) begin active<=0;packet_count<=packet_count+1'b1;end
                else byte_index<=byte_index+1'b1;
            end
            if(active && !tx_busy && !tx_start && !tx_done) begin
                tx_data<=marker(byte_index);tx_start<=1;
                if(byte_index<68)packet_crc<=crc_byte(packet_crc,marker(byte_index));
            end
        end
    end
    uart_tx #(.CLOCK_HZ(27000000),.BAUD(115200)) beacon(
        .clk(clk_27m),.rst_n(local_rst_n),.start(tx_start),.data(tx_data),
        .tx(telemetry_tx),.busy(tx_busy),.done(tx_done));
endmodule
