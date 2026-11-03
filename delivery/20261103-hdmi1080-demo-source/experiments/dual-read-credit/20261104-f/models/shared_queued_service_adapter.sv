`timescale 1ns/1ps
// Adapter only: explicit new Q2-L32-A test model, never an old-model result.
module shared_queued_service_adapter #(parameter CMD_CYCLES=2,TURN_CYCLES=2)(
 input clk,rst_n,input[27:0]awaddr,input[3:0]awlen,input awvalid,output awready,
 input[255:0]wdata,input[31:0]wstrb,output wready,wlast,
 input[27:0]araddr,input[3:0]arlen,input arvalid,output arready,
 output[255:0]rdata,output rvalid,rlast,output[3:0]rid,
 output[27:0]backend_read_addr,input[255:0]backend_read_data,
 output write_commit,output[27:0]write_commit_addr,output[255:0]write_commit_data,output[31:0]write_commit_strb,
 output[31:0]cycles,read_commands,write_commands,read_beats,write_beats,turn_wait_cycles,command_wait_cycles,
 output failed,output[7:0]fault
);
 wire [63:0] t,nar,naw,nr,nw,nref,nstop,nturn;
 wire refresh_active,stop_active;
 wire [27:0] raw_read_address;
 // Original one-pending model shares its address register with writes.
 // Only a valid R beat consumes the read backend; all valid addresses are checked.
 assign backend_read_addr=rvalid ? raw_read_address:28'd0;
 `ifdef ONE_PENDING_MODEL
 ddr_shared_pressure_model #(.R_LATENCY(32)) model(
 `else
 ddr_ordered_two_credit_model #(.R_LATENCY(32)) model(
 `endif
 .clk(clk),.rst_n(rst_n),.araddr(araddr),.arlen(arlen),.arvalid(arvalid),.arready(arready),
 .awaddr(awaddr),.awlen(awlen),.awvalid(awvalid),.awready(awready),.wdata(wdata),.wstrb(wstrb),.wready(wready),.wlast(wlast),
 .rdata(rdata),.rvalid(rvalid),.rlast(rlast),.rid(rid),.mem_raddr(raw_read_address),.mem_rdata(backend_read_data),
 .mem_waddr(write_commit_addr),.mem_we(write_commit),.mem_wdata(write_commit_data),.mem_wstrb(write_commit_strb),
 .refresh_active(refresh_active),.stop_active(stop_active),.tick(t),.read_commands(nar),.write_commands(naw),.read_beats(nr),.write_beats(nw),
 .refresh_cycles(nref),.stop_cycles(nstop),.turn_wait_cycles(nturn));
 assign cycles=t[31:0];assign read_commands=nar[31:0];assign write_commands=naw[31:0];
 assign read_beats=nr[31:0];assign write_beats=nw[31:0];assign turn_wait_cycles=nturn[31:0];
 assign command_wait_cycles=0;assign failed=0;assign fault=0;
endmodule
