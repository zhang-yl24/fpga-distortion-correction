// PRIVATE BOARD1080 SYNTHETIC/DEVELOPMENT model. Same13 integers as the
// independently verified native CPU fixtures. These are NOT camera/lens K/D,
//not a calibration transfer, and never authorize new-lens hardware acceptance.
localparam signed [23:0] B1080_OUT_CX=24'sh03bf80,B1080_OUT_CY=24'sh021b80;
localparam signed [23:0] B1080_SRC_CX=24'sh03bf80,B1080_SRC_CY=24'sh021b80;
localparam signed [23:0] B1080_SRC_FX=24'sh03c000,B1080_SRC_FY=24'sh03cc00;
localparam signed [31:0] B1080_INV_FX=32'sh00111111,B1080_INV_FY=32'sh0010db21;
localparam signed [31:0] B1080_K1=32'sh00051eb8,B1080_K2=32'shffff0a3d,B1080_K3=32'sh000020c5;
localparam signed [31:0] B1080_P1=32'sh00001062,B1080_P2=32'shfffff488;
localparam integer B1080_RADIUS_Q22=8388608;
