`timescale 1ns/1ps
// One acquisition transaction into a selected DDR bank. Parent re-arms the
// capture FIFO only after ownership of the old display bank has been released.
module ddr_video_writer #(parameter FRAME_BEATS=19200,TIMEOUT_BITS=26)(
    input clk,rst_n,input [27:0] base_address,
    input [9:0] fifo_available,input fifo_ready,
    output wire fifo_rd_en,input fifo_valid,input [257:0] fifo_data,
    input source_done,source_valid,input [31:0] source_checksum,
    output wire [27:0] awaddr,output wire [3:0] awlen,
    output wire awvalid,input awready,
    output wire [255:0] wdata,output wire [31:0] wstrb,input wready,wlast,
    output reg [3:0] state,output reg done,failed,output reg [7:0] fault,
    output reg [31:0] written_beats,write_checksum
);
    localparam WAIT=0,FILL=1,AW=2,WRITE=3,META=4,DRAIN=5,COMPLETE=6,FAULT=7;
    reg [255:0] burst[0:15];reg [4:0] issued,received;
    reg [3:0] beat_index;reg [5:0] drain_count;
    reg [TIMEOUT_BITS-1:0] watchdog;
    `include "D:/English/FPGA/distortion/rtl/video_crc32.vh"
    assign fifo_rd_en=state==FILL && issued<16 && fifo_ready;
    assign awaddr=base_address+((written_beats>>4)<<7);
    assign awlen=15;assign awvalid=state==AW;
    assign wdata=burst[beat_index];assign wstrb=32'hFFFFFFFF;
    wire progress=fifo_rd_en || (state==FILL && fifo_valid) ||
        (state==AW && awready) || (state==WRITE && wready);
    always @(posedge clk) begin
        if(!rst_n) begin
            state<=WAIT;done<=0;failed<=0;fault<=0;issued<=0;received<=0;beat_index<=0;
            drain_count<=0;watchdog<=0;written_beats<=0;write_checksum<=32'hFFFFFFFF;
        end else begin
            if(progress || state==DRAIN || state==COMPLETE || state==FAULT) watchdog<=0;
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
                    write_checksum<=video_crc32_beat(write_checksum,wdata);
                    if(wlast != (beat_index==15)) begin failed<=1;fault<=8'h02;state<=FAULT;end
                    else if(beat_index==15) begin
                        beat_index<=0;
                        if(written_beats==FRAME_BEATS-1) state<=META;else state<=WAIT;
                    end else beat_index<=beat_index+1'b1;
                end
                META: if(source_done) begin
                    if(!source_valid || source_checksum!=~write_checksum) begin failed<=1;fault<=8'h13;state<=FAULT;end
                    else begin drain_count<=0;state<=DRAIN;end
                end
                DRAIN: if(drain_count==31) begin done<=1;state<=COMPLETE;end
                       else drain_count<=drain_count+1'b1;
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
