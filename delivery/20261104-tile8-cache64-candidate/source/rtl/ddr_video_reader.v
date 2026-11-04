`timescale 1ns/1ps
// Independent read master. Reserve room for all sixteen unbackpressurable
// response beats before AR. At most one burst is outstanding.
module ddr_video_reader #(parameter FRAME_BEATS=19200,TIMEOUT_BITS=26)(
    input clk,rst_n,start,input [27:0] base_address,input [31:0] expected_checksum,
    input [9:0] fifo_used,input fifo_ready,
    output wire fifo_wr_en,output wire [255:0] fifo_data,
    output wire [27:0] araddr,output wire [3:0] arlen,
    output wire arvalid,input arready,
    input [255:0] rdata,input rvalid,rlast,input [3:0] rid,
    output wire idle,output reg done,failed,output reg [7:0] fault,
    output reg [31:0] read_beats,last_checksum,completed_frames
);
    localparam IDLE=0,ROOM=1,AR=2,READ=3,CHECK=4,FAULT=5;
    reg [2:0] state;reg [27:0] base;
    reg [31:0] checksum,expected;reg [3:0] beat_index;
    reg [TIMEOUT_BITS-1:0] watchdog;
    `include "@COMPILED@/rtl/video_crc32.vh"
    assign idle=state==IDLE;
    assign araddr=base+((read_beats>>4)<<7);assign arlen=15;
    assign arvalid=state==AR;
    assign fifo_wr_en=state==READ && rvalid && fifo_ready;
    assign fifo_data=rdata;
    wire progress=(state==AR && arready)||(state==READ && rvalid);
    always @(posedge clk) begin
        if(!rst_n) begin
            state<=IDLE;base<=0;checksum<=32'hFFFFFFFF;expected<=0;beat_index<=0;
            watchdog<=0;done<=0;failed<=0;fault<=0;read_beats<=0;last_checksum<=32'hFFFFFFFF;completed_frames<=0;
        end else begin
            done<=0;
            if(progress || state==IDLE || state==CHECK || state==FAULT) watchdog<=0;
            else watchdog<=watchdog+1'b1;
            case(state)
                IDLE: if(start) begin
                    base<=base_address;expected<=expected_checksum;checksum<=32'hFFFFFFFF;read_beats<=0;state<=ROOM;
                end
                ROOM: if(fifo_used<=496 && fifo_ready) state<=AR;
                AR: if(arready) begin state<=READ;beat_index<=0;end
                READ: if(rvalid) begin
                    checksum<=video_crc32_beat(checksum,rdata);read_beats<=read_beats+1'b1;
                    if(!fifo_ready) begin failed<=1;fault<=8'h21;state<=FAULT;end
                    else if(rlast != (beat_index==15) || rid!=0) begin failed<=1;fault<=8'h03;state<=FAULT;end
                    else if(beat_index==15) begin
                        if(read_beats==FRAME_BEATS-1) state<=CHECK;else state<=ROOM;
                    end else beat_index<=beat_index+1'b1;
                end
                CHECK: begin
                    last_checksum<=~checksum;
                    if(~checksum!=expected) begin failed<=1;fault<=8'h14;state<=FAULT;end
                    else begin completed_frames<=completed_frames+1'b1;done<=1;state<=IDLE;end
                end
                FAULT: state<=FAULT;
                default: begin failed<=1;fault<=8'hFF;state<=FAULT;end
            endcase
            if(&watchdog && !progress && state!=IDLE && state!=FAULT) begin failed<=1;fault<=8'h01;state<=FAULT;end
        end
    end
endmodule
