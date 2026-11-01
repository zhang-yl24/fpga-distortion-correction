// Current640x480 CAM2 lens; output f240, angle0 only. Not hardware acceptance.
// Profile SHA256 94181c07a4456f511853f51022eba1b55965b115e1569f3fcbad460a2d92999e
// Mapping SHA256 38c0301fb8e1096dd49523555443a1b591ec0a62eb3c238be35f0a544c4a912e
localparam signed [23:0] CAL_OUT_CX=24'sd81792;
localparam signed [23:0] CAL_OUT_CY=24'sd61312;
localparam signed [23:0] CAL_SRC_CX=24'sd82234;
localparam signed [23:0] CAL_SRC_CY=24'sd64062;
localparam signed [23:0] CAL_SRC_FX=24'sd40848;
localparam signed [23:0] CAL_SRC_FY=24'sd40921;
localparam signed [31:0] CAL_INV_FX=32'sd4473924;
localparam signed [31:0] CAL_INV_FY=32'sd4473924;
localparam signed [31:0] CAL_K1=-32'sd674237;
localparam signed [31:0] CAL_K2=32'sd121875;
localparam signed [31:0] CAL_K3=-32'sd11577;
localparam signed [31:0] CAL_P1=32'sd0;
localparam signed [31:0] CAL_P2=32'sd0;
localparam CAL_RADIUS_Q22=11610104;
