// Real fisheye2 calibration approximated over native 640x480; no rotation.
localparam signed [23:0] CAL_OUT_CX=24'sh013176;
localparam signed [23:0] CAL_OUT_CY=24'sh00f5d2;
localparam signed [23:0] CAL_SRC_CX=24'sh013176;
localparam signed [23:0] CAL_SRC_CY=24'sh00f5d2;
localparam signed [23:0] CAL_SRC_FX=24'sh025bd5;
localparam signed [23:0] CAL_SRC_FY=24'sh025b25;
localparam signed [31:0] CAL_INV_FX=32'sh001b221f;
localparam signed [31:0] CAL_INV_FY=32'sh001b2a0b;
localparam signed [31:0] CAL_K1=32'sh00057007;
localparam signed [31:0] CAL_K2=32'shffef399e;
localparam signed [31:0] CAL_K3=32'sh000b7d54;
localparam signed [31:0] CAL_P1=32'sh00000000;
localparam signed [31:0] CAL_P2=32'sh00000000;
