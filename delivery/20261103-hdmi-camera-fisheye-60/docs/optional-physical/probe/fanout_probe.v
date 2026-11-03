module fanout_probe(input clk,input [3:0] cal,input [63:0] din,output [63:0] dout);
probe_ddr u_ddr3_test_h(clk,cal,din,dout);
endmodule
module probe_ddr(input clk,input [3:0] cal,input [63:0] din,output [63:0] dout);
probe_phy u_ddrphy_top(clk,cal,din,dout);
endmodule
module probe_phy(input clk,input [3:0] cal,input [63:0] din,output [63:0] dout);
probe_slice ddrphy_slice_top(clk,cal,din,dout);
endmodule
module probe_slice(input clk,input [3:0] cal,input [63:0] din,output reg [63:0] dout);
wire all_group_ca_dly = |cal;
always @(posedge clk) if(all_group_ca_dly) dout<=din;
endmodule
