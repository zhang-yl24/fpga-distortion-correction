// Resource-only shell: serialize internal buses so they are not mapped to 557
// package I/Os. This shell is not a board design or a DDR controller model.
module remap_synthesis_top(input clk,rst_n,serial_in,output reg serial_out);
    reg [365:0] inputs;
    always @(posedge clk) if(!rst_n) inputs<=0;else inputs<={inputs[364:0],serial_in};
    wire frame_ready,in_ready,out_valid,arvalid,failed;
    wire [23:0] out_rgb,out_tag;
    wire [27:0] araddr;
    wire [3:0] arlen;
    wire [7:0] fault;
    wire [31:0] hits,misses,completed_queries;
    ddr_remap_sample sampler(.clk(clk),.rst_n(rst_n),
        .frame_valid(inputs[0]),.frame_base(inputs[1+:28]),.frame_ready(frame_ready),
        .in_valid(inputs[29]),.in_ready(in_ready),.in_x(inputs[30+:24]),.in_y(inputs[54+:24]),.in_tag(inputs[78+:24]),
        .out_valid(out_valid),.out_ready(inputs[102]),.out_rgb(out_rgb),.out_tag(out_tag),
        .araddr(araddr),.arlen(arlen),.arvalid(arvalid),.arready(inputs[103]),
        .rdata(inputs[104+:256]),.rvalid(inputs[360]),.rlast(inputs[361]),.rid(inputs[362+:4]),
        .failed(failed),.fault(fault),.hits(hits),.misses(misses),.completed_queries(completed_queries));
    always @(posedge clk) serial_out<=^{frame_ready,in_ready,out_valid,out_rgb,out_tag,araddr,arlen,arvalid,failed,fault,hits,misses,completed_queries};
endmodule
