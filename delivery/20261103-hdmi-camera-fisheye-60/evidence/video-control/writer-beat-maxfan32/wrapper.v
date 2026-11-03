module writer_probe(
input clk,rst_n,abort,frame_valid,
input [27:0] frame_base,input [31:0] frame_id,
input in_valid,input [23:0] in_rgb,input [23:0] in_tag,
input awready,wready,wlast,input [2:0] probe_slice,input [1:0] probe_status,
output frame_ready,in_ready,awvalid,done,failed,
output [27:0] awaddr,output [7:0] fault,
output [31:0] data_slice,status_slice
);
wire [3:0] awlen;wire [255:0] wdata;wire [31:0] wstrb;
wire [31:0] accepted_pixels,written_beats,last_checksum,completed_id;
ddr_raster_result_writer_pingpong #(.WIDTH(1920),.HEIGHT(440)) writer(
.clk(clk),.rst_n(rst_n),.abort(abort),.frame_valid(frame_valid),.frame_ready(frame_ready),
.frame_base(frame_base),.frame_id(frame_id),.in_valid(in_valid),.in_ready(in_ready),
.in_rgb(in_rgb),.in_tag(in_tag),.awaddr(awaddr),.awlen(awlen),.awvalid(awvalid),.awready(awready),
.wdata(wdata),.wstrb(wstrb),.wready(wready),.wlast(wlast),.done(done),.failed(failed),.fault(fault),
.accepted_pixels(accepted_pixels),.written_beats(written_beats),.last_checksum(last_checksum),.completed_id(completed_id));
assign data_slice=wdata[probe_slice*32+:32];
assign status_slice=probe_status==0?accepted_pixels:probe_status==1?written_beats:probe_status==2?last_checksum:completed_id;
endmodule
