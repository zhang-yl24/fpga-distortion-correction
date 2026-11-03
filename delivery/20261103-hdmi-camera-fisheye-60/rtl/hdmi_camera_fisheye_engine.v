`timescale 1ns/1ps
// Two independent, frame-locked row ranges share the unchanged DDR contract.
// Each lane reorders tiles back to raster before writing its contiguous range.
// The complete frame is published only after both lanes and both buses finish.
module hdmi_camera_fisheye_engine #(
    parameter WIDTH=1920,HEIGHT=1080,TIMEOUT_BITS=26,TILE_W=8,TILE_H=8,CACHE_INDEX_BITS=9,
    TOP_CACHE_INDEX_BITS=CACHE_INDEX_BITS,BOTTOM_CACHE_INDEX_BITS=CACHE_INDEX_BITS,
    TOP_ROW_PADDED_INDEX=0,BOTTOM_ROW_PADDED_INDEX=0,
    NATIVE_TOP_ROWS=640,
    TOP_ROWS=(WIDTH==1920 && HEIGHT==1080)?NATIVE_TOP_ROWS:((HEIGHT/2+TILE_H-1)/TILE_H)*TILE_H
)(
    input clk,rst_n,input frame_valid,output frame_ready,input cfg_corrected,
    input [27:0] source_base,output_base,input [31:0] frame_id,
    output [27:0] araddr,output [3:0] arlen,output arvalid,input arready,
    input [255:0] rdata,input rvalid,rlast,input [3:0] rid,
    output [27:0] awaddr,output [3:0] awlen,output awvalid,input awready,
    output [255:0] wdata,output [31:0] wstrb,input wready,wlast,
    output reg done,failed,output reg [7:0] fault,
    output reg [27:0] completed_base,output reg [31:0] completed_id,completed_crc,
    output [31:0] hits,misses,completed_queries
);
    localparam BOTTOM_ROWS=HEIGHT-TOP_ROWS;
    localparam BOTTOM_BYTES=WIDTH*BOTTOM_ROWS*2;
    wire [1:0] ready_lane,done_lane,failed_lane;
    wire [7:0] fault_lane[0:1];
    wire [27:0] laraddr[0:1],lawaddr[0:1],lbase[0:1];
    wire [3:0] larlen[0:1],lawlen[0:1],lrid[0:1];
    wire [1:0] larvalid,larready,lawvalid,lawready,lrvalid,lrlast,lwready,lwlast;
    wire [255:0] lrdata[0:1],lwdata[0:1];
    wire [31:0] lwstrb[0:1],lid[0:1],lcrc[0:1],lhits[0:1],lmisses[0:1],lqueries[0:1];
    wire read_failed,write_failed,read_busy,write_busy;
    wire [7:0] read_fault,write_fault;
    reg active,launch,cfg_hold;
    reg [1:0] finished;
    reg [27:0] base_hold,source_hold;
    reg [31:0] id_hold,crc0_hold,crc1_hold;
    wire [28:0] source_end={1'b0,source_base}+WIDTH*HEIGHT/2;
    wire [28:0] output_end={1'b0,output_base}+WIDTH*HEIGHT/2;
    wire layout_ok=WIDTH>=TILE_W && WIDTH%TILE_W==0 && HEIGHT>=2*TILE_H && HEIGHT%TILE_H==0 &&
        TOP_ROWS>0 && BOTTOM_ROWS>0 && TOP_ROWS%TILE_H==0 && BOTTOM_ROWS%TILE_H==0 &&
        (WIDTH*TOP_ROWS)%256==0 && (WIDTH*BOTTOM_ROWS)%256==0 &&
        source_base[6:0]==0 && output_base[6:0]==0 &&
        source_end<=29'h10000000 && output_end<=29'h10000000 &&
        (source_end<={1'b0,output_base} || output_end<={1'b0,source_base});
    assign frame_ready=!active && &ready_lane && !read_busy && !write_busy && !failed;
    assign hits=lhits[0]+lhits[1];
    assign misses=lmisses[0]+lmisses[1];
    assign completed_queries=lqueries[0]+lqueries[1];
    genvar lane;
    generate for(lane=0;lane<2;lane=lane+1)begin: lanes
        localparam Y0=(lane==0)?0:TOP_ROWS;
        localparam ROWS=(lane==0)?TOP_ROWS:BOTTOM_ROWS;
        hdmi_camera_fisheye_lane #(.WIDTH(WIDTH),.HEIGHT(HEIGHT),.Y_START(Y0),.LANE_HEIGHT(ROWS),
            .TILE_W(TILE_W),.TILE_H(TILE_H),
            .CACHE_INDEX_BITS((lane==0)?TOP_CACHE_INDEX_BITS:BOTTOM_CACHE_INDEX_BITS),
            .ROW_PADDED_INDEX((lane==0)?TOP_ROW_PADDED_INDEX:BOTTOM_ROW_PADDED_INDEX),
            .TIMEOUT_BITS(TIMEOUT_BITS)) worker(
            .clk(clk),.rst_n(rst_n),.frame_valid(launch),.frame_ready(ready_lane[lane]),.cfg_corrected(cfg_hold),
            .source_base(source_hold),.output_base(base_hold+WIDTH*Y0/2),.frame_id(id_hold),
            .araddr(laraddr[lane]),.arlen(larlen[lane]),.arvalid(larvalid[lane]),.arready(larready[lane]),
            .rdata(lrdata[lane]),.rvalid(lrvalid[lane]),.rlast(lrlast[lane]),.rid(lrid[lane]),
            .awaddr(lawaddr[lane]),.awlen(lawlen[lane]),.awvalid(lawvalid[lane]),.awready(lawready[lane]),
            .wdata(lwdata[lane]),.wstrb(lwstrb[lane]),.wready(lwready[lane]),.wlast(lwlast[lane]),
            .done(done_lane[lane]),.failed(failed_lane[lane]),.fault(fault_lane[lane]),
            .completed_base(lbase[lane]),.completed_id(lid[lane]),.completed_crc(lcrc[lane]),
            .hits(lhits[lane]),.misses(lmisses[lane]),.completed_queries(lqueries[lane]));
    end endgenerate
    ddr_read_arbiter #(.TIMEOUT_BITS(TIMEOUT_BITS)) lane_reads(
        .clk(clk),.rst_n(rst_n),.display_urgent(1'b0),
        .c0_araddr(laraddr[0]),.c1_araddr(laraddr[1]),.c0_arlen(larlen[0]),.c1_arlen(larlen[1]),
        .c0_arvalid(larvalid[0]),.c1_arvalid(larvalid[1]),.c0_arready(larready[0]),.c1_arready(larready[1]),
        .c0_rdata(lrdata[0]),.c1_rdata(lrdata[1]),.c0_rvalid(lrvalid[0]),.c1_rvalid(lrvalid[1]),
        .c0_rlast(lrlast[0]),.c1_rlast(lrlast[1]),.c0_rid(lrid[0]),.c1_rid(lrid[1]),
        .araddr(araddr),.arlen(arlen),.arvalid(arvalid),.arready(arready),.rdata(rdata),.rvalid(rvalid),.rlast(rlast),.rid(rid),
        .failed(read_failed),.fault(read_fault),.busy(read_busy),.bursts0(),.bursts1());
    ddr_write_arbiter #(.TIMEOUT_BITS(TIMEOUT_BITS)) lane_writes(
        .clk(clk),.rst_n(rst_n),.c0_awaddr(lawaddr[0]),.c1_awaddr(lawaddr[1]),.c0_awlen(lawlen[0]),.c1_awlen(lawlen[1]),
        .c0_awvalid(lawvalid[0]),.c1_awvalid(lawvalid[1]),.c0_awready(lawready[0]),.c1_awready(lawready[1]),
        .c0_wdata(lwdata[0]),.c1_wdata(lwdata[1]),.c0_wstrb(lwstrb[0]),.c1_wstrb(lwstrb[1]),
        .c0_wready(lwready[0]),.c1_wready(lwready[1]),.c0_wlast(lwlast[0]),.c1_wlast(lwlast[1]),
        .awaddr(awaddr),.awlen(awlen),.awvalid(awvalid),.awready(awready),.wdata(wdata),.wstrb(wstrb),.wready(wready),.wlast(wlast),
        .failed(write_failed),.fault(write_fault),.busy(write_busy),.bursts0(),.bursts1());

    // Constant elaboration-time GF(2) transform, equivalent to zlib crc32_combine.
    // Inputs here are the complemented, standard CRC32 values of both ranges.
    function [31:0] matrix_times;
        input [1023:0] matrix;input [31:0] vector;integer i;reg [31:0] value;
        begin value=0;for(i=0;i<32;i=i+1)if(vector[i])value=value^matrix[i*32+:32];matrix_times=value;end
    endfunction
    function [31:0] crc_column;
        input integer column;
        reg [1023:0] matrix,squared;reg [31:0] vector;integer i,n;
        begin
            matrix=0;matrix[0+:32]=32'hEDB88320;
            for(i=1;i<32;i=i+1)matrix[i*32+:32]=32'b1<<(i-1);
            vector=32'b1<<column;n=BOTTOM_BYTES*8;
            while(n>0)begin
                if(n%2)vector=matrix_times(matrix,vector);
                for(i=0;i<32;i=i+1)squared[i*32+:32]=matrix_times(matrix,matrix[i*32+:32]);
                matrix=squared;n=n/2;
            end
            crc_column=vector;
        end
    endfunction
    wire [31:0] contribution[0:31];wire [31:0] combined_crc;
    genvar c;
    generate for(c=0;c<32;c=c+1)begin: crc_columns
        localparam [31:0] COLUMN=crc_column(c);
        assign contribution[c]=COLUMN & {32{crc0_hold[c]}};
    end endgenerate
    assign combined_crc=crc1_hold ^
        contribution[0]^contribution[1]^contribution[2]^contribution[3]^contribution[4]^contribution[5]^contribution[6]^contribution[7]^
        contribution[8]^contribution[9]^contribution[10]^contribution[11]^contribution[12]^contribution[13]^contribution[14]^contribution[15]^
        contribution[16]^contribution[17]^contribution[18]^contribution[19]^contribution[20]^contribution[21]^contribution[22]^contribution[23]^
        contribution[24]^contribution[25]^contribution[26]^contribution[27]^contribution[28]^contribution[29]^contribution[30]^contribution[31];
    always @(posedge clk)begin
        if(!rst_n)begin
            active<=0;launch<=0;cfg_hold<=0;finished<=0;base_hold<=0;source_hold<=0;id_hold<=0;crc0_hold<=0;crc1_hold<=0;
            done<=0;failed<=0;fault<=0;completed_base<=0;completed_id<=0;completed_crc<=0;
        end else begin
            done<=0;launch<=0;
            if(frame_valid && frame_ready)begin
                if(!layout_ok)begin failed<=1;fault<=8'h40;end
                else begin active<=1;launch<=1;finished<=0;base_hold<=output_base;source_hold<=source_base;cfg_hold<=cfg_corrected;id_hold<=frame_id;end
            end
            if(done_lane[0])begin
                finished[0]<=1;crc0_hold<=lcrc[0];
                if(!active || finished[0] || lid[0]!=id_hold || lbase[0]!=base_hold)begin failed<=1;fault<=8'h44;end
            end
            if(done_lane[1])begin
                finished[1]<=1;crc1_hold<=lcrc[1];
                if(!active || finished[1] || lid[1]!=id_hold || lbase[1]!=base_hold+WIDTH*TOP_ROWS/2)begin failed<=1;fault<=8'h45;end
            end
            if(active && &finished && !(|done_lane) && !read_busy && !write_busy && !failed && !(|failed_lane) && !read_failed && !write_failed)begin
                active<=0;done<=1;completed_base<=base_hold;completed_id<=id_hold;completed_crc<=combined_crc;
            end
            if((|failed_lane) || read_failed || write_failed)begin
                failed<=1;done<=0;
                fault<=failed_lane[0]?fault_lane[0]:failed_lane[1]?fault_lane[1]:read_failed?(8'hC0|read_fault):(8'hD0|write_fault);
            end
        end
    end
endmodule
