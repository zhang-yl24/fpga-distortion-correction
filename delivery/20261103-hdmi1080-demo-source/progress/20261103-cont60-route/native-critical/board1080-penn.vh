// DEVELOPMENT ONLY: exact Penn frame240 contract, same-K, 1920x1080, 0deg.
// Contract SHA256 4be4883514d792116e4a0b8866356699314dd981e7ee312ddecf4261efd8d63b.
// Pixel/focal Q8, inverse focal Q30, Brown Q22; zero-based pixel centres.
// Gamma is fixed OFF. Resource scope is this fixed-Gamma/identity-rotation
// candidate with dynamic raw/corrected selection, not full dynamic Gamma.
localparam signed [23:0] B1080_OUT_CX=24'sh03d4e0,B1080_OUT_CY=24'sh020bf0;
localparam signed [23:0] B1080_SRC_CX=24'sh03d4e0,B1080_SRC_CY=24'sh020bf0;
localparam signed [23:0] B1080_SRC_FX=24'sh07a7d6,B1080_SRC_FY=24'sh07a763;
localparam signed [31:0] B1080_INV_FX=32'sh00085c21,B1080_INV_FY=32'sh00085c9f;
localparam signed [31:0] B1080_K1=32'sh000d9a17,B1080_K2=32'shffe28b97,B1080_K3=32'sh00000000;
localparam signed [31:0] B1080_P1=32'sh00000000,B1080_P2=32'sh00000000;
localparam signed [23:0] B1080_ROT_CX=24'sd251104,B1080_ROT_CY=24'sd134128;
localparam signed [31:0] B1080_ROT_COS=32'sd1073741824,B1080_ROT_SIN=32'sd0;
localparam B1080_GAMMA_ENABLE=1'b0;
localparam integer B1080_RADIUS_Q22=1387217;
