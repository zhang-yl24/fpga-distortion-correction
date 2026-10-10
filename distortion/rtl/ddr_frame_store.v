`timescale 1ns/1ps
// One complete RGB565 frame: prefetch a whole 16-beat burst before AW,
// since this DDR IP cannot backpressure its W channel. Validate source frame
// metadata, then read the entire frame back and compare rolling checksums.
// This module does not yet arbitrate a concurrent HDMI or remapping reader.
module ddr_frame_store #(parameter FRAME_BEATS=19200,TIMEOUT_BITS=26)(
    input clk,rst_n,
    input [9:0] fifo_available,input fifo_ready,
    output wire fifo_rd_en,
    input fifo_valid,input [257:0] fifo_data,
    input source_done,source_valid,input [31:0] source_checksum,
    output wire [27:0] awaddr,araddr,
    output wire [3:0] awlen,arlen,
    output wire awvalid,arvalid,input awready,arready,
    output wire [255:0] wdata,output wire [31:0] wstrb,
    input wready,wlast,input [255:0] rdata,input rvalid,rlast,input [3:0] rid,
    output reg [3:0] state,output reg done,failed,output reg [7:0] fault,
    output reg [31:0] written_beats,read_beats,write_checksum,read_checksum
);
    localparam WAIT=0,FILL=1,AW=2,WRITE=3,META=4,DRAIN=5,AR=6,READ=7,NEXT=8,COMPLETE=9,FAULT=10;
    reg [255:0] burst[0:15];
    reg [4:0] issued,received;
    reg [3:0] beat_index;
    reg [5:0] drain_count;
    reg [TIMEOUT_BITS-1:0] watchdog;
    function [31:0] checksum_beat;
        input [31:0] previous;
        input [255:0] data;
        reg [31:0] accum;integer lane;
        begin
            accum=previous;
            for(lane=0;lane<16;lane=lane+1)
                accum={accum[30:0],accum[31]} ^ {16'b0,data[lane*16+:16]};
            checksum_beat=accum;
        end
    endfunction
    assign fifo_rd_en=state==FILL && issued<16 && fifo_ready;
    assign awaddr=(written_beats>>4)<<7;
    assign araddr=(read_beats>>4)<<7;
    assign awlen=15;assign arlen=15;
    assign awvalid=state==AW;assign arvalid=state==AR;
    assign wdata=burst[beat_index];assign wstrb=32'hFFFFFFFF;
    wire progress=fifo_rd_en || (state==FILL && fifo_valid) ||
        (state==AW && awready) || (state==WRITE && wready) ||
        (state==AR && arready) || (state==READ && rvalid);
    always @(posedge clk) begin
        if(!rst_n) begin
            state<=WAIT;done<=0;failed<=0;fault<=0;issued<=0;received<=0;beat_index<=0;
            drain_count<=0;watchdog<=0;written_beats<=0;read_beats<=0;write_checksum<=0;read_checksum<=0;
        end else begin
            if(progress || state==DRAIN || state==NEXT || state==COMPLETE || state==FAULT) watchdog<=0;
            else watchdog<=watchdog+1'b1;
            case(state)
                WAIT: if(fifo_available>=16) begin state<=FILL;issued<=0;received<=0;end
                      else if(source_done && !source_valid) begin failed<=1;fault<=8'h11;state<=FAULT;end
                FILL: begin
                    if(fifo_rd_en) issued<=issued+1'b1;
                    if(fifo_valid) begin
                        if(fifo_data[257] != (written_beats==0 && received==0) ||
                           fifo_data[256] != (written_beats+received==FRAME_BEATS-1)) begin
                            failed<=1;fault<=8'h12;state<=FAULT;
                        end else begin
                            burst[received[3:0]]<=fifo_data[255:0];received<=received+1'b1;
                            if(received==15) begin state<=AW;beat_index<=0;end
                        end
                    end
                end
                AW: if(awready) state<=WRITE;
                WRITE: if(wready) begin
                    written_beats<=written_beats+1'b1;
                    write_checksum<=checksum_beat(write_checksum,wdata);
                    if(wlast != (beat_index==15)) begin failed<=1;fault<=8'h02;state<=FAULT;end
                    else if(beat_index==15) begin
                        beat_index<=0;
                        if(written_beats==FRAME_BEATS-1) state<=META;
                        else state<=WAIT;
                    end else beat_index<=beat_index+1'b1;
                end
                META: if(source_done) begin
                    if(!source_valid || source_checksum!=write_checksum) begin failed<=1;fault<=8'h13;state<=FAULT;end
                    else begin drain_count<=0;state<=DRAIN;end
                end
                DRAIN: if(drain_count==31) state<=AR;else drain_count<=drain_count+1'b1;
                AR: if(arready) begin state<=READ;beat_index<=0;end
                READ: if(rvalid) begin
                    read_beats<=read_beats+1'b1;
                    read_checksum<=checksum_beat(read_checksum,rdata);
                    if(rlast != (beat_index==15) || rid!=0) begin failed<=1;fault<=8'h03;state<=FAULT;end
                    else if(beat_index==15) state<=NEXT;
                    else beat_index<=beat_index+1'b1;
                end
                NEXT: if(read_beats==FRAME_BEATS) begin
                    if(read_checksum!=source_checksum) begin failed<=1;fault<=8'h14;state<=FAULT;end
                    else begin done<=1;state<=COMPLETE;end
                end else state<=AR;
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
