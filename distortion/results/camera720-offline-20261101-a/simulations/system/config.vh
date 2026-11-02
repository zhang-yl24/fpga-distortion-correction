// Exact identity transport at 1280x720; NOT a camera calibration.
// A new sensor-mode lens profile is required before correction acceptance.
localparam signed [23:0] C720_OUT_CX=24'sd163712;
localparam signed [23:0] C720_OUT_CY=24'sd92032;
localparam signed [23:0] C720_SRC_CX=24'sd163712;
localparam signed [23:0] C720_SRC_CY=24'sd92032;
localparam signed [23:0] C720_SRC_FX=24'sd262144;
localparam signed [23:0] C720_SRC_FY=24'sd262144;
localparam signed [31:0] C720_INV_FX=32'sd1048576;
localparam signed [31:0] C720_INV_FY=32'sd1048576;
localparam signed [31:0] C720_K1=32'sd0;
localparam signed [31:0] C720_K2=32'sd0;
localparam signed [31:0] C720_K3=32'sd0;
localparam signed [31:0] C720_P1=32'sd0;
localparam signed [31:0] C720_P2=32'sd0;
localparam C720_RADIUS_Q22=8388608;
