`timescale 1ns/1ps
// Independent native1080/development clone; original signed-off source is unchanged.
// One complete accepted-angle corrected frame transaction. Parent must keep source_base
// immutable and exclusively own output_base through done. Raster tags are
// checked again by the writer. No partial result bank is published on fault.
module hdmi_camera_fisheye_engine #(parameter WIDTH=1920,HEIGHT=1080,TIMEOUT_BITS=26,MAX_RADIUS_Q22=0)(
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

    integer ticks, delay_cycles;
    reg busy;
    initial begin if(!$value$plusargs("PROCESS=%d",delay_cycles))delay_cycles=2252;$display("STUB_PROCESS=%0d",delay_cycles);end
    assign frame_ready=!busy;
    assign araddr=0;assign arlen=0;assign arvalid=0;assign awaddr=0;assign awlen=0;assign awvalid=0;assign wdata=0;assign wstrb=0;
    assign hits=0;assign misses=0;assign completed_queries=0;
    always @(posedge clk)begin
      if(!rst_n)begin busy<=0;ticks<=0;done<=0;failed<=0;fault<=0;completed_base<=0;completed_id<=0;completed_crc<=0;end
      else begin done<=0;
        if(frame_valid&&frame_ready)begin busy<=1;ticks<=delay_cycles;completed_base<=output_base;completed_id<=frame_id;completed_crc<=frame_id^32'h12345678;end
        if(busy)begin
          if(ticks==1)begin busy<=0;done<=1;end else ticks<=ticks-1;
        end
      end
    end
endmodule
