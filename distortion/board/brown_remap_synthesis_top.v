// Standalone synthesis shell, not a physical board bitstream.
module brown_remap_synthesis_top(input clk,rst_n,serial_in,output reg serial_out);
    reg [733:0] inputs;
    // Payload-only test shift chain: load all 734 bits before offering a frame.
    // Removing its unnecessary reset avoids a synthetic external-reset fanout.
    always @(posedge clk) inputs<={inputs[732:0],serial_in};
    wire signed [23:0] cfg_out_cx,cfg_out_cy,cfg_src_cx,cfg_src_cy,cfg_src_fx,cfg_src_fy;
    wire signed [31:0] cfg_inv_fx,cfg_inv_fy,cfg_k1,cfg_k2,cfg_k3,cfg_p1,cfg_p2;
    assign {cfg_out_cx,cfg_out_cy,cfg_src_cx,cfg_src_cy,cfg_src_fx,cfg_src_fy,cfg_inv_fx,cfg_inv_fy,cfg_k1,cfg_k2,cfg_k3,cfg_p1,cfg_p2}=inputs[29+:368];
    wire frame_ready,in_ready,out_valid,arvalid,failed;
    wire [23:0] out_rgb,out_tag;wire [27:0] araddr;wire [3:0] arlen;
    wire [7:0] fault;wire [31:0] hits,misses,completed_queries;
    brown_remap_core core(.clk(clk),.rst_n(rst_n),
        .frame_valid(inputs[0]),.frame_base(inputs[1+:28]),.frame_ready(frame_ready),
        .cfg_out_cx(cfg_out_cx),.cfg_out_cy(cfg_out_cy),.cfg_src_cx(cfg_src_cx),.cfg_src_cy(cfg_src_cy),.cfg_src_fx(cfg_src_fx),.cfg_src_fy(cfg_src_fy),
        .cfg_inv_fx(cfg_inv_fx),.cfg_inv_fy(cfg_inv_fy),.cfg_k1(cfg_k1),.cfg_k2(cfg_k2),.cfg_k3(cfg_k3),.cfg_p1(cfg_p1),.cfg_p2(cfg_p2),
        .in_valid(inputs[397]),.in_ready(in_ready),.in_u(inputs[398+:24]),.in_v(inputs[422+:24]),.in_tag(inputs[446+:24]),
        .out_valid(out_valid),.out_ready(inputs[470]),.out_rgb(out_rgb),.out_tag(out_tag),
        .araddr(araddr),.arlen(arlen),.arvalid(arvalid),.arready(inputs[471]),
        .rdata(inputs[472+:256]),.rvalid(inputs[728]),.rlast(inputs[729]),.rid(inputs[730+:4]),
        .failed(failed),.fault(fault),.hits(hits),.misses(misses),.completed_queries(completed_queries));
    always @(posedge clk) serial_out<=^{frame_ready,in_ready,out_valid,out_rgb,out_tag,araddr,arlen,arvalid,failed,fault,hits,misses,completed_queries};
endmodule
