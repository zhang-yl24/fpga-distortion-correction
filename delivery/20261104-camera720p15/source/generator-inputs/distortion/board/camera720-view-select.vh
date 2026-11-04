// Runtime view selection, all signals in the processing clock domain.
// The existing remapper latches the entire configuration at accept_frame.
// Do not replace this with a pixel mux or change live mapper registers.
// Identity uses power-of-two focal values for exact RGB565 source coordinates;
// zeroing only the distortion coefficients would retain the corrected zoom.
wire signed [23:0] view_out_cx=C720_OUT_CX;
wire signed [23:0] view_out_cy=C720_OUT_CY;
wire signed [23:0] view_src_cx=corrected_requested ? C720_SRC_CX : 24'sd163712;
wire signed [23:0] view_src_cy=corrected_requested ? C720_SRC_CY : 24'sd92032;
wire signed [23:0] view_src_fx=corrected_requested ? C720_SRC_FX : 24'sd262144;
wire signed [23:0] view_src_fy=corrected_requested ? C720_SRC_FY : 24'sd262144;
wire signed [31:0] view_inv_fx=corrected_requested ? C720_INV_FX : 32'sd1048576;
wire signed [31:0] view_inv_fy=corrected_requested ? C720_INV_FY : 32'sd1048576;
wire signed [31:0] view_k1=corrected_requested ? C720_K1 : 32'sd0;
wire signed [31:0] view_k2=corrected_requested ? C720_K2 : 32'sd0;
wire signed [31:0] view_k3=corrected_requested ? C720_K3 : 32'sd0;
wire signed [31:0] view_p1=corrected_requested ? C720_P1 : 32'sd0;
wire signed [31:0] view_p2=corrected_requested ? C720_P2 : 32'sd0;
