module cache_address_probe(
 input clk,rst_n,input [31:0] config_data,input [2:0] config_select,input config_write,
 input frame_valid,in_valid,out_ready,arready,rvalid,rlast,input [3:0] rid,
 input [3:0] observe_select,output reg [31:0] observe,
 output wire frame_ready,in_ready,out_valid,arvalid,failed,
 output wire [27:0] araddr,output wire [3:0] arlen
);
 reg [27:0] frame_base;reg signed [23:0] in_x,in_y;reg [23:0] in_tag;reg [255:0] rdata;
 wire [23:0] p00,p10,p01,p11,out_tag;wire [7:0] fx,fy,fault;
 wire [31:0] hits,misses,completed_queries;
 always @(posedge clk)begin
  if(!rst_n)begin frame_base<=0;in_x<=0;in_y<=0;in_tag<=0;rdata<=0;end
  else if(config_write)case(config_select)
   0:frame_base<=config_data[27:0];1:in_x<=config_data[23:0];2:in_y<=config_data[23:0];
   3:in_tag<=config_data[23:0];4:rdata<={rdata[223:0],config_data};
  endcase
 end
 always @*begin
  case(observe_select)
   0:observe={8'd0,p00};1:observe={8'd0,p10};2:observe={8'd0,p01};3:observe={8'd0,p11};
   4:observe={8'd0,out_tag};5:observe={8'd0,fx,fy,fault};6:observe=hits;
   7:observe=misses;8:observe=completed_queries;default:observe=0;
  endcase
 end
 ddr_neighbour_cache_scatter4_rowpipe #(.WIDTH(1920),.HEIGHT(1080),.TAG_W(24),.INDEX_BITS(10),.PREDECODE(1),.ROW_PADDED_INDEX(1),.REGISTERED_RETURN(1)) cache(
 .clk(clk),
 .rst_n(rst_n),
 .frame_valid(frame_valid),
 .frame_ready(frame_ready),
 .frame_base(frame_base),
 .in_valid(in_valid),
 .in_ready(in_ready),
 .in_x(in_x),
 .in_y(in_y),
 .in_tag(in_tag),
 .out_valid(out_valid),
 .out_ready(out_ready),
 .p00(p00),
 .p10(p10),
 .p01(p01),
 .p11(p11),
 .fx(fx),
 .fy(fy),
 .out_tag(out_tag),
 .araddr(araddr),
 .arlen(arlen),
 .arvalid(arvalid),
 .arready(arready),
 .rdata(rdata),
 .rvalid(rvalid),
 .rlast(rlast),
 .rid(rid),
 .failed(failed),
 .fault(fault),
 .hits(hits),
 .misses(misses),
 .completed_queries(completed_queries)
 );
endmodule
