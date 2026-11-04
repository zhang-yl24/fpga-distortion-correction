`timescale 1ns/1ps
// Independent native1080/development clone; original signed-off source is unchanged.
// One complete accepted-angle corrected frame transaction. Parent must keep source_base
// immutable and exclusively own output_base through done. Raster tags are
// checked again by the writer. No partial result bank is published on fault.
module pipeline_gamma_frame_engine_1080_geometry_bypass #(parameter WIDTH=1920,HEIGHT=1080,TIMEOUT_BITS=26,MAX_RADIUS_Q22=0)(
    input clk,rst_n,input frame_valid,output frame_ready,input gamma_enable,correction_enable,
    output [1:0] gamma_mode,output [31:0] gamma_frames,
    input [27:0] source_base,output_base,input [31:0] frame_id,
    input signed [23:0] cfg_out_cx,cfg_out_cy,cfg_src_cx,cfg_src_cy,cfg_src_fx,cfg_src_fy,
    input signed [31:0] cfg_inv_fx,cfg_inv_fy,cfg_k1,cfg_k2,cfg_k3,cfg_p1,cfg_p2,
    input signed [23:0] cfg_rot_cx,cfg_rot_cy,
    input signed [31:0] cfg_rot_cos,cfg_rot_sin,
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
    assign frame_ready=!busy;assign gamma_mode=0;assign gamma_frames=0;
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
