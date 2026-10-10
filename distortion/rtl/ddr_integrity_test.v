`timescale 1ns/1ps
// Pango HMIC_S user interface: WREADY consumes an unconditional data beat;
// WLAST is an OUTPUT from the controller, and R has no backpressure input.
// Address units are 32-bit DDR words (vendor wr_cmd_trans advances 128 for
// a 16 x 256-bit burst). This is not a generic AXI master.
// Write the entire region BEFORE reading it to detect aliased addresses.
module ddr_integrity_test #(
    parameter BLOCKS=256, PASSES=4, TIMEOUT_BITS=20
)(
    input clk, rst_n,
    output wire [27:0] awaddr, araddr,
    output wire [3:0] awlen, arlen,
    output wire awvalid, arvalid,
    input awready, arready,
    output wire [255:0] wdata,
    output wire [31:0] wstrb,
    input wready, wlast,
    input [255:0] rdata, input rvalid, rlast,
    input [3:0] rid,
    output reg [3:0] state,
    output reg done, failed,
    output reg [7:0] fault,
    output reg [31:0] written_beats, read_beats, errors,
    output reg [27:0] first_bad_address,
    output reg [7:0] completed_passes
);
    localparam IDLE=0, AW=1, WRITE=2, SETTLE=3, AR=4,
               READ=5, NEXT=6, COMPLETE=7, FAULT=8;
    reg [15:0] block_index;
    reg [3:0] beat_index;
    reg [7:0] pass_index;
    reg [5:0] settle_count;
    reg [TIMEOUT_BITS-1:0] watchdog;
    function [255:0] pattern;
        input [15:0] block_number;
        input [3:0] beat_number;
        input [7:0] pass_number;
        integer lane;
        reg [31:0] salt;
        begin
            case(pass_number[1:0])
                0:salt=32'hA5C369F0;
                1:salt=32'h5A3C960F;
                2:salt=32'h00000000;
                3:salt=32'hFFFFFFFF;
            endcase
            for(lane=0;lane<8;lane=lane+1)
                pattern[lane*32+:32]={block_number,beat_number,lane[3:0],8'h5A} ^ salt;
        end
    endfunction
    assign awaddr={5'b0,block_index,7'b0};
    assign araddr={5'b0,block_index,7'b0};
    assign awlen=4'd15;
    assign arlen=4'd15;
    assign awvalid=state==AW;
    assign arvalid=state==AR;
    assign wdata=pattern(block_index,beat_index,pass_index);
    assign wstrb=32'hFFFFFFFF;
    wire progress=(state==AW && awready) || (state==WRITE && wready) ||
                  (state==AR && arready) || (state==READ && rvalid);
    always @(posedge clk) begin
        if(!rst_n) begin
            state<=IDLE;done<=0;failed<=0;fault<=0;block_index<=0;beat_index<=0;
            pass_index<=0;settle_count<=0;watchdog<=0;
            written_beats<=0;read_beats<=0;errors<=0;first_bad_address<=0;completed_passes<=0;
        end else begin
            if(progress || state==IDLE || state==SETTLE || state==NEXT ||
               state==COMPLETE || state==FAULT) watchdog<=0;
            else watchdog<=watchdog+1'b1;
            case(state)
                IDLE: state<=AW;
                AW: if(awready) begin state<=WRITE;beat_index<=0;end
                WRITE: if(wready) begin
                    written_beats<=written_beats+1'b1;
                    if(wlast != (beat_index==15)) begin
                        failed<=1;fault<=8'h02;state<=FAULT;
                    end else if(beat_index==15) begin
                        beat_index<=0;
                        if(block_index==BLOCKS-1) begin
                            block_index<=0;settle_count<=0;state<=SETTLE;
                        end else begin block_index<=block_index+1'b1;state<=AW;end
                    end else beat_index<=beat_index+1'b1;
                end
                // No B response exists on this IP. Completed WLAST + a short
                // drain interval precedes read requests; data comparison verifies it.
                SETTLE: if(settle_count==31) state<=AR;
                        else settle_count<=settle_count+1'b1;
                AR: if(arready) begin state<=READ;beat_index<=0;end
                READ: if(rvalid) begin
                    read_beats<=read_beats+1'b1;
                    if(rdata != pattern(block_index,beat_index,pass_index)) begin
                        errors<=errors+1'b1;
                        if(errors==0) first_bad_address<=araddr+{21'b0,beat_index,3'b0};
                    end
                    if(rlast != (beat_index==15) || rid!=0) begin
                        failed<=1;fault<=8'h03;state<=FAULT;
                    end else if(beat_index==15) state<=NEXT;
                    else beat_index<=beat_index+1'b1;
                end
                NEXT: begin
                    beat_index<=0;
                    if(block_index==BLOCKS-1) begin
                        completed_passes<=completed_passes+1'b1;
                        if(errors!=0) begin failed<=1;fault<=8'h04;state<=FAULT;end
                        else if(pass_index==PASSES-1) begin done<=1;state<=COMPLETE;end
                        else begin pass_index<=pass_index+1'b1;block_index<=0;state<=AW;end
                    end else begin block_index<=block_index+1'b1;state<=AR;end
                end
                COMPLETE: state<=COMPLETE;
                FAULT: state<=FAULT;
                default: begin failed<=1;fault<=8'hFF;state<=FAULT;end
            endcase
            if(&watchdog && !progress && state!=COMPLETE && state!=FAULT) begin
                failed<=1;fault<=8'h01;state<=FAULT;
            end
        end
    end
endmodule
