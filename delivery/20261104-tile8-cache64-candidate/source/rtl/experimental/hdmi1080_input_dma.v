`timescale 1ns/1ps
// Minimal offline MS7200-style pixel -> RGB565 -> CDC -> linear DDR producer.
// No chip init/lock/pin/polarity claim. One reserved frame at a time; throughput
// and source-clock loss require later integration/measurement. All address
// units are 4 bytes. Each 16-beat burst is fully buffered before AWVALID.
// The existing Pango shim consumes W when WREADY, and returns WLAST; there is
// no B channel here. A future AXI adapter MUST supply/validate its own B response.
// rst_n is a COORDINATED core+capture+DDR transaction reset, not a safe local
// cancellation of a previously accepted AW. Domain clock-stop is not watched.
module hdmi1080_input_dma #(
    parameter WIDTH=1920,HEIGHT=1080,BANK_STRIDE=1048576,FIFO_ADDR_BITS=6
)(
    input pix_clk,sys_clk,rst_n,enable,
    input pix_vsync_active,pix_de,input [23:0] pix_rgb,
    input [1:0] source_writable,input source_released,released_bank,
    output reg source_valid,input source_ready,output reg source_bank,
    output reg [31:0] source_id,source_crc,source_pixels,
    output [1:0] capture_reserved,
    output [27:0] awaddr,output [3:0] awlen,output awvalid,input awready,
    output [255:0] wdata,output [31:0] wstrb,input wready,wlast,
    output write_active,output reg failed,output reg [7:0] fault,
    output reg [31:0] accepted_frames,dropped_frames,overflow_frames,
    output [31:0] no_free_frames,output reg [7:0] last_drop_fault
);
    localparam N=WIDTH*HEIGHT,FRAME_BEATS=N/16,FRAME_UNITS=N/2;
    localparam LAYOUT_OK=WIDTH>=16 && HEIGHT>=2 && WIDTH%16==0 && N%256==0 &&
        N<=16777216 && BANK_STRIDE>=FRAME_UNITS && BANK_STRIDE%128==0 &&
        2*BANK_STRIDE<=268435456 && FIFO_ADDR_BITS>=2 && FIFO_ADDR_BITS<=10;
    localparam COLLECT=0,ADDRESS=1,WRITE=2;
    (* async_reg="true" *) reg [1:0] sys_reset;
    always @(posedge sys_clk or negedge rst_n)
        if(!rst_n)sys_reset<=0;else sys_reset<={sys_reset[0],1'b1};
    wire sr=sys_reset[1];
    reg [1:0] owned,committed;
    assign capture_reserved=owned;
    reg active,active_bank;reg [31:0] active_id,next_id,written_beats,crc_state;
    reg crc_busy;reg [2:0] crc_step;reg [255:0] crc_word;
    reg [1:0] state;
    reg [4:0] buffered;reg [3:0] write_index;
    reg [255:0] burst_buffer[0:15];
    reg end_seen,end_good,end_bank;reg [31:0] end_id,end_pixels,end_crc;
    reg [7:0] end_fault;reg [2:0] end_settle;
    reg aborting;
    wire [1:0] free_bank=source_writable & ~owned;
    wire grant_bank=!free_bank[0];
    wire grant_valid=sr && enable && LAYOUT_OK && !failed && !active && !source_valid && |free_bank;
    wire grant_ready,fifo_valid,fifo_idle,cap_done_valid,cap_done_good,cap_done_bank;
    wire [255:0] fifo_data;
    wire [31:0] cap_done_id,cap_done_pixels,cap_done_crc;
    wire [7:0] cap_done_fault;
    wire cap_done_ready=active && end_seen && end_settle==0 && fifo_idle && !crc_busy &&
        state==COLLECT && (aborting || buffered==0) && !source_valid;
    wire fifo_ready=active && state==COLLECT && !source_valid &&
        (aborting || (buffered<16 && !crc_busy));
    hdmi1080_capture_cdc #(.WIDTH(WIDTH),.HEIGHT(HEIGHT),.FIFO_ADDR_BITS(FIFO_ADDR_BITS)) capture(
        .pix_clk(pix_clk),.sys_clk(sys_clk),.rst_n(rst_n),.enable(enable),
        .pix_vsync_active(pix_vsync_active),.pix_de(pix_de),.pix_rgb(pix_rgb),
        .grant_valid(grant_valid),.grant_ready(grant_ready),.grant_bank(grant_bank),.grant_id(next_id),
        .fifo_valid(fifo_valid),.fifo_ready(fifo_ready),.fifo_data(fifo_data),.fifo_idle(fifo_idle),
        .done_valid(cap_done_valid),.done_ready(cap_done_ready),.done_good(cap_done_good),.done_bank(cap_done_bank),
        .done_id(cap_done_id),.done_pixels(cap_done_pixels),.done_crc(cap_done_crc),.done_fault(cap_done_fault),
        .no_grant_frames(no_free_frames));
    assign awaddr=(active_bank ? BANK_STRIDE:0)+written_beats*8;
    assign awlen=15;
    assign awvalid=sr && active && state==ADDRESS;
    // The shared Pango write arbiter may transfer beat0 ON the AW handshake.
    // Preserve the same index/last accounting for that cycle and later beats.
    wire writing=sr && active && (state==WRITE || (state==ADDRESS && awready));
    assign write_active=writing;
    assign wdata=burst_buffer[write_index];
    assign wstrb=32'hffffffff;
    function [31:0] crc_byte(input [31:0] c,input [7:0] b);
        reg [31:0] x;integer k;
        begin x=c^b;for(k=0;k<8;k=k+1)x=x[0] ? (x>>1)^32'hedb88320:x>>1;crc_byte=x;end
    endfunction
    function [31:0] crc_four_bytes(input [31:0] c,input [31:0] data);
        reg [31:0] x;integer j;
        begin x=c;for(j=0;j<4;j=j+1)x=crc_byte(x,data[j*8+:8]);crc_four_bytes=x;end
    endfunction
    always @(posedge sys_clk or negedge rst_n)begin
        if(!rst_n)begin
            owned<=0;committed<=0;active<=0;active_bank<=0;active_id<=0;next_id<=1;
            written_beats<=0;crc_state<=32'hffffffff;state<=COLLECT;buffered<=0;write_index<=0;
            crc_busy<=0;crc_step<=0;crc_word<=0;
            end_seen<=0;end_good<=0;end_bank<=0;end_id<=0;end_pixels<=0;end_crc<=0;end_fault<=0;end_settle<=0;aborting<=0;
            source_valid<=0;source_bank<=0;source_id<=0;source_crc<=0;source_pixels<=0;
            failed<=0;fault<=0;accepted_frames<=0;dropped_frames<=0;overflow_frames<=0;last_drop_fault<=0;
        end else if(!sr)begin
            owned<=0;committed<=0;active<=0;active_bank<=0;active_id<=0;next_id<=1;
            written_beats<=0;crc_state<=32'hffffffff;state<=COLLECT;buffered<=0;write_index<=0;
            crc_busy<=0;crc_step<=0;crc_word<=0;
            end_seen<=0;end_good<=0;end_bank<=0;end_id<=0;end_pixels<=0;end_crc<=0;end_fault<=0;end_settle<=0;aborting<=0;
            source_valid<=0;source_bank<=0;source_id<=0;source_crc<=0;source_pixels<=0;
            failed<=0;fault<=0;accepted_frames<=0;dropped_frames<=0;overflow_frames<=0;last_drop_fault<=0;
        end else begin
            if(!LAYOUT_OK)begin failed<=1;fault<=8'h80;end
            if(source_released)begin
                if(!owned[released_bank] || !committed[released_bank])begin failed<=1;fault<=8'h82;end
                else begin owned[released_bank]<=0;committed[released_bank]<=0;end
            end
            if(source_valid && source_ready)begin
                source_valid<=0;committed[source_bank]<=1;accepted_frames<=accepted_frames+1'b1;
            end
            if(grant_valid && grant_ready)begin
                owned[grant_bank]<=1;active<=1;active_bank<=grant_bank;active_id<=next_id;next_id<=next_id+1'b1;
                written_beats<=0;crc_state<=32'hffffffff;state<=COLLECT;buffered<=0;write_index<=0;
                crc_busy<=0;crc_step<=0;
                end_seen<=0;end_settle<=0;aborting<=0;
            end
            if(active && cap_done_valid && !end_seen)begin
                end_seen<=1;end_good<=cap_done_good;end_bank<=cap_done_bank;end_id<=cap_done_id;
                end_pixels<=cap_done_pixels;end_crc<=cap_done_crc;end_fault<=cap_done_fault;end_settle<=3;
                if(!cap_done_good)aborting<=1;
            end else if(end_settle!=0)end_settle<=end_settle-1'b1;
            if(active)begin
                // Four bytes/cycle for8 cycles, over a held beat. No next pop,
                // AW or commit may pass this registered checksum transaction.
                if(crc_busy)begin
                    if(aborting)crc_busy<=0;
                    else begin
                        crc_state<=crc_four_bytes(crc_state,crc_word[crc_step*32+:32]);
                        if(crc_step==7)crc_busy<=0;else crc_step<=crc_step+1'b1;
                    end
                end
                case(state)
                    COLLECT:begin
                        if(fifo_valid && fifo_ready)begin
                            if(!aborting)begin
                                burst_buffer[buffered[3:0]]<=fifo_data;buffered<=buffered+1'b1;
                                crc_word<=fifo_data;crc_busy<=1;crc_step<=0;
                            end
                        end
                        if(aborting)buffered<=0;
                        else if(buffered==16 && !crc_busy && !(cap_done_valid && !cap_done_good))begin
                            if(written_beats+16>FRAME_BEATS)begin aborting<=1;last_drop_fault<=8'h40;end
                            else begin state<=ADDRESS;write_index<=0;end
                        end
                    end
                    ADDRESS:if(awready)state<=WRITE;
                    WRITE:begin end
                    default:begin failed<=1;fault<=8'h83;aborting<=1;end
                endcase
                // After the ADDRESS assignment so a transfer always owns the
                // final state/index decision, including zero-latency beat0.
                if(writing && wready)begin
                    if(wlast!=(write_index==15))begin failed<=1;fault<=8'h81;aborting<=1;end
                    if(write_index==15)begin state<=COLLECT;buffered<=0;written_beats<=written_beats+16;end
                    else write_index<=write_index+1'b1;
                end
            end
            if(cap_done_ready && cap_done_valid)begin
                active<=0;buffered<=0;
                if(!aborting && !failed && end_good && end_bank==active_bank && end_id==active_id &&
                   end_pixels==N && written_beats==FRAME_BEATS && ~crc_state==end_crc)begin
                    source_valid<=1;source_bank<=active_bank;source_id<=active_id;
                    source_crc<=end_crc;source_pixels<=end_pixels;
                end else begin
                    owned[active_bank]<=0;dropped_frames<=dropped_frames+1'b1;
                    last_drop_fault<=end_fault!=0 ? end_fault:8'h40;
                    if(end_fault[3])overflow_frames<=overflow_frames+1'b1;
                end
            end
        end
    end
endmodule
