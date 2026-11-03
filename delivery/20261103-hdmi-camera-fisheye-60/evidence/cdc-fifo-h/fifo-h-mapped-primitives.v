(* PAP_BLE_DEF="C" *)    V_LUT6CARRY /* CLMA_207_606 */ #(
            .INIT(64'hFFFFFFFFFFFFFFFF),
            .I5_TO_CARRY("TRUE"),
            .I5_TO_LUT("TRUE"))
        \VCC_788/FYC/LUT6CARRY  (
            .COUT (),
            .Z (_VCC788),
            .Z5 (),
            .CIN (1'b0),
            .I0 (1'b1),
            .I1 (1'b1),
            .I2 (1'b1),
            .I3 (1'b1),
            .I4 (1'b1),
            .I5 (1'b1));

(* PAP_BLE_DEF="A" *)    V_FFASYN /* CLMA_207_606 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \core_reset[0]/opit_0/FFAPP0/FF  (
            .Q (core_reset[0]),
            .CE (1'b1),
            .CK (core_clk),
            .D (_VCC788),
            .SR (\CLMS_225_781/ntRS ));

(* PAP_BLE_DEF="B" *)    V_FFASYN /* CLMA_207_606 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \core_reset[1]/opit_0/FFAPP1/FF  (
            .Q (core_reset[1]),
            .CE (1'b1),
            .CK (core_clk),
            .D (core_reset[0]),
            .SR (\CLMS_225_781/ntRS ));

(* PAP_BLE_DEF="D" *)    V_FFSYN /* CLMS_309_523 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/rd_gray[0]/opit_0_inv_L5Q_perm/FFAPP3/FF  (
            .Q (\system/display_fifo/rd_gray [0]),
            .CE (\CLMS_309_523/ntCE ),
            .CK (ntclkbufg_0),
            .D (\CLMS_309_523/ntQC3 ),
            .SR (\CLMS_309_523/ntRSCO ));

(* PAP_BLE_DEF="C" *)    V_FFSYN /* CLMS_309_523 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/rd_gray[1]/opit_0_inv/FF2/FF  (
            .Q (\system/display_fifo/rd_gray [1]),
            .CE (\CLMS_309_523/ntCE ),
            .CK (ntclkbufg_0),
            .D (\system/display_fifo/N134 [1]),
            .SR (\CLMS_309_523/ntRSCO ));

(* PAP_BLE_DEF="D" *)    V_FFSYN /* CLMS_309_523 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/rd_gray[2]/opit_0_inv/FF3/FF  (
            .Q (\system/display_fifo/rd_gray [2]),
            .CE (\CLMS_309_523/ntCE ),
            .CK (ntclkbufg_0),
            .D (\system/display_fifo/N134 [2]),
            .SR (\CLMS_309_523/ntRSCO ));

(* PAP_BLE_DEF="A" *)    V_FFSYN /* CLMA_315_528 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/rd_gray[3]/opit_0_inv/FFAPP0/FF  (
            .Q (\system/display_fifo/rd_gray [3]),
            .CE (ntR593),
            .CK (ntclkbufg_0),
            .D (\system/display_fifo/N134 [3]),
            .SR (ntR1744));

(* PAP_BLE_DEF="B" *)    V_FFSYN /* CLMA_315_528 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/rd_gray[4]/opit_0_inv/FF1/FF  (
            .Q (\system/display_fifo/rd_gray [4]),
            .CE (ntR593),
            .CK (ntclkbufg_0),
            .D (\system/display_fifo/N134 [4]),
            .SR (ntR1744));

(* PAP_BLE_DEF="C" *)    V_FFSYN /* CLMA_315_528 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/rd_gray[5]/opit_0_inv/FF2/FF  (
            .Q (\system/display_fifo/rd_gray [5]),
            .CE (ntR593),
            .CK (ntclkbufg_0),
            .D (\system/display_fifo/N134 [5]),
            .SR (ntR1744));

(* PAP_BLE_DEF="D" *)    V_FFSYN /* CLMA_315_528 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/rd_gray[6]/opit_0_inv/FF3/FF  (
            .Q (\system/display_fifo/rd_gray [6]),
            .CE (ntR593),
            .CK (ntclkbufg_0),
            .D (\system/display_fifo/N134 [6]),
            .SR (ntR1744));

(* PAP_BLE_DEF="A" *)    V_FFSYN /* CLMS_309_523 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/rd_gray[7]/opit_0_inv/FF0/FF  (
            .Q (\system/display_fifo/rd_gray [7]),
            .CE (\CLMS_309_523/ntCE ),
            .CK (ntclkbufg_0),
            .D (\system/display_fifo/N134 [7]),
            .SR (\CLMS_309_523/ntRSCO ));

(* PAP_BLE_DEF="B" *)    V_FFSYN /* CLMS_309_523 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/rd_gray[8]/opit_0_inv/FF1/FF  (
            .Q (\system/display_fifo/rd_gray [8]),
            .CE (\CLMS_309_523/ntCE ),
            .CK (ntclkbufg_0),
            .D (\system/display_fifo/N134 [8]),
            .SR (\CLMS_309_523/ntRSCO ));

(* PAP_BLE_DEF="D" *)    V_FFSYN /* CLMA_315_528 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/rd_gray[9]/opit_0_inv_L5Q_perm/FFAPP3/FF  (
            .Q (\system/display_fifo/rd_gray [9]),
            .CE (ntR593),
            .CK (ntclkbufg_0),
            .D (\CLMA_315_528/ntQC3 ),
            .SR (ntR1744));

(* PAP_BLE_DEF="A" *)    V_FFSYN /* CLMA_303_504 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/rd_gray_w1[0]/opit_0_inv/FF0/FF  (
            .Q (\system/display_fifo/rd_gray_w1 [0]),
            .CE (1'b1),
            .CK (core_clk),
            .D (\system/display_fifo/rd_gray [0]),
            .SR (ntR1745));

(* PAP_BLE_DEF="C" *)    V_FFSYN /* CLMA_303_504 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/rd_gray_w1[1]/opit_0_inv/FF2/FF  (
            .Q (\system/display_fifo/rd_gray_w1 [1]),
            .CE (1'b1),
            .CK (core_clk),
            .D (\system/display_fifo/rd_gray [1]),
            .SR (ntR1745));

(* PAP_BLE_DEF="A" *)    V_FFSYN /* CLMS_291_517 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/rd_gray_w1[2]/opit_0_inv/FF0/FF  (
            .Q (\system/display_fifo/rd_gray_w1 [2]),
            .CE (1'b1),
            .CK (core_clk),
            .D (\system/display_fifo/rd_gray [2]),
            .SR (\CLMS_291_517/ntRSCO ));

(* PAP_BLE_DEF="A" *)    V_FFSYN /* CLMA_303_528 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/rd_gray_w1[3]/opit_0_inv/FF0/FF  (
            .Q (\system/display_fifo/rd_gray_w1 [3]),
            .CE (1'b1),
            .CK (core_clk),
            .D (\system/display_fifo/rd_gray [3]),
            .SR (\CLMA_303_528/ntRSCO ));

(* PAP_BLE_DEF="C" *)    V_FFSYN /* CLMA_303_528 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/rd_gray_w1[4]/opit_0_inv/FF2/FF  (
            .Q (\system/display_fifo/rd_gray_w1 [4]),
            .CE (1'b1),
            .CK (core_clk),
            .D (\system/display_fifo/rd_gray [4]),
            .SR (\CLMA_303_528/ntRSCO ));

(* PAP_BLE_DEF="C" *)    V_FFSYN /* CLMS_291_517 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/rd_gray_w1[5]/opit_0_inv/FF2/FF  (
            .Q (\system/display_fifo/rd_gray_w1 [5]),
            .CE (1'b1),
            .CK (core_clk),
            .D (\system/display_fifo/rd_gray [5]),
            .SR (\CLMS_291_517/ntRSCO ));

(* PAP_BLE_DEF="A" *)    V_FFSYN /* CLMA_303_510 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/rd_gray_w1[6]/opit_0_inv/FF0/FF  (
            .Q (\system/display_fifo/rd_gray_w1 [6]),
            .CE (1'b1),
            .CK (core_clk),
            .D (\system/display_fifo/rd_gray [6]),
            .SR (ntR1745));

(* PAP_BLE_DEF="C" *)    V_FFSYN /* CLMA_303_510 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/rd_gray_w1[7]/opit_0_inv/FF2/FF  (
            .Q (\system/display_fifo/rd_gray_w1 [7]),
            .CE (1'b1),
            .CK (core_clk),
            .D (\system/display_fifo/rd_gray [7]),
            .SR (ntR1745));

(* PAP_BLE_DEF="A" *)    V_FFSYN /* CLMA_303_516 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/rd_gray_w1[8]/opit_0_inv/FF0/FF  (
            .Q (\system/display_fifo/rd_gray_w1 [8]),
            .CE (1'b1),
            .CK (core_clk),
            .D (\system/display_fifo/rd_gray [8]),
            .SR (ntR1746));

(* PAP_BLE_DEF="C" *)    V_FFSYN /* CLMA_303_516 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/rd_gray_w1[9]/opit_0_inv/FF2/FF  (
            .Q (\system/display_fifo/rd_gray_w1 [9]),
            .CE (1'b1),
            .CK (core_clk),
            .D (\system/display_fifo/rd_gray [9]),
            .SR (ntR1746));

(* PAP_BLE_DEF="B" *)    V_FFSYN /* CLMA_303_504 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/rd_gray_w2[0]/opit_0_inv/FF1/FF  (
            .Q (\system/display_fifo/rd_gray_w2 [0]),
            .CE (1'b1),
            .CK (core_clk),
            .D (\system/display_fifo/rd_gray_w1 [0]),
            .SR (ntR1745));

(* PAP_BLE_DEF="D" *)    V_FFSYN /* CLMA_303_504 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/rd_gray_w2[1]/opit_0_inv/FF3/FF  (
            .Q (\system/display_fifo/rd_gray_w2 [1]),
            .CE (1'b1),
            .CK (core_clk),
            .D (\system/display_fifo/rd_gray_w1 [1]),
            .SR (ntR1745));

(* PAP_BLE_DEF="B" *)    V_FFSYN /* CLMS_291_517 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/rd_gray_w2[2]/opit_0_inv/FF1/FF  (
            .Q (\system/display_fifo/rd_gray_w2 [2]),
            .CE (1'b1),
            .CK (core_clk),
            .D (\system/display_fifo/rd_gray_w1 [2]),
            .SR (\CLMS_291_517/ntRSCO ));

(* PAP_BLE_DEF="B" *)    V_FFSYN /* CLMA_303_528 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/rd_gray_w2[3]/opit_0_inv/FF1/FF  (
            .Q (\system/display_fifo/rd_gray_w2 [3]),
            .CE (1'b1),
            .CK (core_clk),
            .D (\system/display_fifo/rd_gray_w1 [3]),
            .SR (\CLMA_303_528/ntRSCO ));

(* PAP_BLE_DEF="D" *)    V_FFSYN /* CLMA_303_528 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/rd_gray_w2[4]/opit_0_inv/FF3/FF  (
            .Q (\system/display_fifo/rd_gray_w2 [4]),
            .CE (1'b1),
            .CK (core_clk),
            .D (\system/display_fifo/rd_gray_w1 [4]),
            .SR (\CLMA_303_528/ntRSCO ));

(* PAP_BLE_DEF="D" *)    V_FFSYN /* CLMS_291_517 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/rd_gray_w2[5]/opit_0_inv/FF3/FF  (
            .Q (\system/display_fifo/rd_gray_w2 [5]),
            .CE (1'b1),
            .CK (core_clk),
            .D (\system/display_fifo/rd_gray_w1 [5]),
            .SR (\CLMS_291_517/ntRSCO ));

(* PAP_BLE_DEF="B" *)    V_FFSYN /* CLMA_303_510 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/rd_gray_w2[6]/opit_0_inv/FF1/FF  (
            .Q (\system/display_fifo/rd_gray_w2 [6]),
            .CE (1'b1),
            .CK (core_clk),
            .D (\system/display_fifo/rd_gray_w1 [6]),
            .SR (ntR1745));

(* PAP_BLE_DEF="D" *)    V_FFSYN /* CLMA_303_510 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/rd_gray_w2[7]/opit_0_inv/FF3/FF  (
            .Q (\system/display_fifo/rd_gray_w2 [7]),
            .CE (1'b1),
            .CK (core_clk),
            .D (\system/display_fifo/rd_gray_w1 [7]),
            .SR (ntR1745));

(* PAP_BLE_DEF="B" *)    V_FFSYN /* CLMA_303_516 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/rd_gray_w2[8]/opit_0_inv/FF1/FF  (
            .Q (\system/display_fifo/rd_gray_w2 [8]),
            .CE (1'b1),
            .CK (core_clk),
            .D (\system/display_fifo/rd_gray_w1 [8]),
            .SR (ntR1746));

(* PAP_BLE_DEF="D" *)    V_FFSYN /* CLMA_303_516 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/rd_gray_w2[9]/opit_0_inv/FF3/FF  (
            .Q (\system/display_fifo/rd_gray_w2 [9]),
            .CE (1'b1),
            .CK (core_clk),
            .D (\system/display_fifo/rd_gray_w1 [9]),
            .SR (ntR1746));

(* PAP_BLE_DEF="A" *)    V_FFASYN /* CLMS_201_721 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/rd_reset_sync[0]/opit_0/FF0/FF  (
            .Q (\system/display_fifo/rd_reset_sync [0]),
            .CE (1'b1),
            .CK (ntclkbufg_0),
            .D (1'b1),
            .SR (\CLMS_225_781/ntRS ));

(* PAP_BLE_DEF="B" *)    V_FFASYN /* CLMS_201_721 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/rd_reset_sync[1]/opit_0/FF1/FF  (
            .Q (\system/display_fifo/rd_reset_sync [1]),
            .CE (1'b1),
            .CK (ntclkbufg_0),
            .D (\system/display_fifo/rd_reset_sync [0]),
            .SR (\CLMS_225_781/ntRS ));

(* PAP_BLE_DEF="A" *)    V_FFSYN /* CLMS_309_517 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/wr_gray[0]/opit_0_inv/FFAPP0/FF  (
            .Q (\system/display_fifo/wr_gray [0]),
            .CE (ntR1177),
            .CK (core_clk),
            .D (\system/display_fifo/N112 [0]),
            .SR (ntR3064));

(* PAP_BLE_DEF="B" *)    V_FFSYN /* CLMS_309_517 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/wr_gray[1]/opit_0_inv/FFAPP1/FF  (
            .Q (\system/display_fifo/wr_gray [1]),
            .CE (ntR1177),
            .CK (core_clk),
            .D (\system/display_fifo/N112 [1]),
            .SR (ntR3064));

(* PAP_BLE_DEF="C" *)    V_FFSYN /* CLMS_309_517 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/wr_gray[2]/opit_0_inv/FF2/FF  (
            .Q (\system/display_fifo/wr_gray [2]),
            .CE (ntR1177),
            .CK (core_clk),
            .D (\system/display_fifo/N112 [2]),
            .SR (ntR3064));

(* PAP_BLE_DEF="B" *)    V_FFSYN /* CLMS_309_505 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/wr_gray[3]/opit_0_inv/FFAPP1/FF  (
            .Q (\system/display_fifo/wr_gray [3]),
            .CE (\CLMS_309_505/ntCE ),
            .CK (core_clk),
            .D (\system/display_fifo/N112 [3]),
            .SR (ntR3063));

(* PAP_BLE_DEF="A" *)    V_FFSYN /* CLMA_309_504 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/wr_gray[4]/opit_0_inv/FF0/FF  (
            .Q (\system/display_fifo/wr_gray [4]),
            .CE (\CLMS_309_505/ntCE ),
            .CK (core_clk),
            .D (\system/display_fifo/N112 [4]),
            .SR (\CLMA_309_504/ntRSCO ));

(* PAP_BLE_DEF="B" *)    V_FFSYN /* CLMA_309_504 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/wr_gray[5]/opit_0_inv/FF1/FF  (
            .Q (\system/display_fifo/wr_gray [5]),
            .CE (\CLMS_309_505/ntCE ),
            .CK (core_clk),
            .D (\system/display_fifo/N112 [5]),
            .SR (\CLMA_309_504/ntRSCO ));

(* PAP_BLE_DEF="C" *)    V_FFSYN /* CLMA_309_504 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/wr_gray[6]/opit_0_inv/FF2/FF  (
            .Q (\system/display_fifo/wr_gray [6]),
            .CE (\CLMS_309_505/ntCE ),
            .CK (core_clk),
            .D (\system/display_fifo/N112 [6]),
            .SR (\CLMA_309_504/ntRSCO ));

(* PAP_BLE_DEF="D" *)    V_FFSYN /* CLMA_309_504 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/wr_gray[7]/opit_0_inv/FF3/FF  (
            .Q (\system/display_fifo/wr_gray [7]),
            .CE (\CLMS_309_505/ntCE ),
            .CK (core_clk),
            .D (\system/display_fifo/N112 [7]),
            .SR (\CLMA_309_504/ntRSCO ));

(* PAP_BLE_DEF="D" *)    V_FFSYN /* CLMA_309_504 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/wr_gray[8]/opit_0_inv_L5Q_perm/FFAPP3/FF  (
            .Q (\system/display_fifo/wr_gray [8]),
            .CE (\CLMS_309_505/ntCE ),
            .CK (core_clk),
            .D (\CLMA_309_504/ntQC3 ),
            .SR (\CLMA_309_504/ntRSCO ));

(* PAP_BLE_DEF="C" *)    V_FFSYN /* CLMS_309_505 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/wr_gray[9]/opit_0_inv/FFAPP2/FF  (
            .Q (\system/display_fifo/wr_gray [9]),
            .CE (\CLMS_309_505/ntCE ),
            .CK (core_clk),
            .D (\system/display_fifo/next_wr [9]),
            .SR (ntR3063));

(* PAP_BLE_DEF="A" *)    V_FFSYN /* CLMS_327_523 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/wr_gray_r1[0]/opit_0_inv/FF0/FF  (
            .Q (\system/display_fifo/wr_gray_r1 [0]),
            .CE (1'b1),
            .CK (ntclkbufg_0),
            .D (\system/display_fifo/wr_gray [0]),
            .SR (\CLMS_327_523/ntRSCO ));

(* PAP_BLE_DEF="A" *)    V_FFSYN /* CLMA_303_498 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/wr_gray_r1[1]/opit_0_inv/FF0/FF  (
            .Q (\system/display_fifo/wr_gray_r1 [1]),
            .CE (1'b1),
            .CK (ntclkbufg_0),
            .D (\system/display_fifo/wr_gray [1]),
            .SR (\CLMA_303_498/ntRSCO ));

(* PAP_BLE_DEF="C" *)    V_FFSYN /* CLMA_303_498 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/wr_gray_r1[2]/opit_0_inv/FF2/FF  (
            .Q (\system/display_fifo/wr_gray_r1 [2]),
            .CE (1'b1),
            .CK (ntclkbufg_0),
            .D (\system/display_fifo/wr_gray [2]),
            .SR (\CLMA_303_498/ntRSCO ));

(* PAP_BLE_DEF="A" *)    V_FFSYN /* CLMA_303_522 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/wr_gray_r1[3]/opit_0_inv/FF0/FF  (
            .Q (\system/display_fifo/wr_gray_r1 [3]),
            .CE (1'b1),
            .CK (ntclkbufg_0),
            .D (\system/display_fifo/wr_gray [3]),
            .SR (\CLMA_303_522/ntRSCO ));

(* PAP_BLE_DEF="C" *)    V_FFSYN /* CLMS_327_523 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/wr_gray_r1[4]/opit_0_inv/FF2/FF  (
            .Q (\system/display_fifo/wr_gray_r1 [4]),
            .CE (1'b1),
            .CK (ntclkbufg_0),
            .D (\system/display_fifo/wr_gray [4]),
            .SR (\CLMS_327_523/ntRSCO ));

(* PAP_BLE_DEF="C" *)    V_FFSYN /* CLMA_303_522 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/wr_gray_r1[5]/opit_0_inv/FF2/FF  (
            .Q (\system/display_fifo/wr_gray_r1 [5]),
            .CE (1'b1),
            .CK (ntclkbufg_0),
            .D (\system/display_fifo/wr_gray [5]),
            .SR (\CLMA_303_522/ntRSCO ));

(* PAP_BLE_DEF="A" *)    V_FFSYN /* CLMS_291_505 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/wr_gray_r1[6]/opit_0_inv/FF0/FF  (
            .Q (\system/display_fifo/wr_gray_r1 [6]),
            .CE (1'b1),
            .CK (ntclkbufg_0),
            .D (\system/display_fifo/wr_gray [6]),
            .SR (\CLMS_291_505/ntRSCO ));

(* PAP_BLE_DEF="A" *)    V_FFSYN /* CLMA_309_510 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/wr_gray_r1[7]/opit_0_inv/FF0/FF  (
            .Q (\system/display_fifo/wr_gray_r1 [7]),
            .CE (1'b1),
            .CK (ntclkbufg_0),
            .D (\system/display_fifo/wr_gray [7]),
            .SR (\CLMA_309_510/ntRSCO ));

(* PAP_BLE_DEF="C" *)    V_FFSYN /* CLMA_309_510 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/wr_gray_r1[8]/opit_0_inv/FF2/FF  (
            .Q (\system/display_fifo/wr_gray_r1 [8]),
            .CE (1'b1),
            .CK (ntclkbufg_0),
            .D (\system/display_fifo/wr_gray [8]),
            .SR (\CLMA_309_510/ntRSCO ));

(* PAP_BLE_DEF="C" *)    V_FFSYN /* CLMS_291_505 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/wr_gray_r1[9]/opit_0_inv/FF2/FF  (
            .Q (\system/display_fifo/wr_gray_r1 [9]),
            .CE (1'b1),
            .CK (ntclkbufg_0),
            .D (\system/display_fifo/wr_gray [9]),
            .SR (\CLMS_291_505/ntRSCO ));

(* PAP_BLE_DEF="B" *)    V_FFSYN /* CLMS_327_523 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/wr_gray_r2[0]/opit_0_inv/FF1/FF  (
            .Q (\system/display_fifo/wr_gray_r2 [0]),
            .CE (1'b1),
            .CK (ntclkbufg_0),
            .D (\system/display_fifo/wr_gray_r1 [0]),
            .SR (\CLMS_327_523/ntRSCO ));

(* PAP_BLE_DEF="B" *)    V_FFSYN /* CLMA_303_498 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/wr_gray_r2[1]/opit_0_inv/FF1/FF  (
            .Q (\system/display_fifo/wr_gray_r2 [1]),
            .CE (1'b1),
            .CK (ntclkbufg_0),
            .D (\system/display_fifo/wr_gray_r1 [1]),
            .SR (\CLMA_303_498/ntRSCO ));

(* PAP_BLE_DEF="D" *)    V_FFSYN /* CLMA_303_498 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/wr_gray_r2[2]/opit_0_inv/FF3/FF  (
            .Q (\system/display_fifo/wr_gray_r2 [2]),
            .CE (1'b1),
            .CK (ntclkbufg_0),
            .D (\system/display_fifo/wr_gray_r1 [2]),
            .SR (\CLMA_303_498/ntRSCO ));

(* PAP_BLE_DEF="B" *)    V_FFSYN /* CLMA_303_522 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/wr_gray_r2[3]/opit_0_inv/FF1/FF  (
            .Q (\system/display_fifo/wr_gray_r2 [3]),
            .CE (1'b1),
            .CK (ntclkbufg_0),
            .D (\system/display_fifo/wr_gray_r1 [3]),
            .SR (\CLMA_303_522/ntRSCO ));

(* PAP_BLE_DEF="D" *)    V_FFSYN /* CLMS_327_523 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/wr_gray_r2[4]/opit_0_inv/FF3/FF  (
            .Q (\system/display_fifo/wr_gray_r2 [4]),
            .CE (1'b1),
            .CK (ntclkbufg_0),
            .D (\system/display_fifo/wr_gray_r1 [4]),
            .SR (\CLMS_327_523/ntRSCO ));

(* PAP_BLE_DEF="D" *)    V_FFSYN /* CLMA_303_522 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/wr_gray_r2[5]/opit_0_inv/FF3/FF  (
            .Q (\system/display_fifo/wr_gray_r2 [5]),
            .CE (1'b1),
            .CK (ntclkbufg_0),
            .D (\system/display_fifo/wr_gray_r1 [5]),
            .SR (\CLMA_303_522/ntRSCO ));

(* PAP_BLE_DEF="B" *)    V_FFSYN /* CLMS_291_505 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/wr_gray_r2[6]/opit_0_inv/FF1/FF  (
            .Q (\system/display_fifo/wr_gray_r2 [6]),
            .CE (1'b1),
            .CK (ntclkbufg_0),
            .D (\system/display_fifo/wr_gray_r1 [6]),
            .SR (\CLMS_291_505/ntRSCO ));

(* PAP_BLE_DEF="B" *)    V_FFSYN /* CLMA_309_510 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/wr_gray_r2[7]/opit_0_inv/FF1/FF  (
            .Q (\system/display_fifo/wr_gray_r2 [7]),
            .CE (1'b1),
            .CK (ntclkbufg_0),
            .D (\system/display_fifo/wr_gray_r1 [7]),
            .SR (\CLMA_309_510/ntRSCO ));

(* PAP_BLE_DEF="D" *)    V_FFSYN /* CLMA_309_510 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/wr_gray_r2[8]/opit_0_inv/FF3/FF  (
            .Q (\system/display_fifo/wr_gray_r2 [8]),
            .CE (1'b1),
            .CK (ntclkbufg_0),
            .D (\system/display_fifo/wr_gray_r1 [8]),
            .SR (\CLMA_309_510/ntRSCO ));

(* PAP_BLE_DEF="D" *)    V_FFSYN /* CLMS_291_505 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/wr_gray_r2[9]/opit_0_inv/FF3/FF  (
            .Q (\system/display_fifo/wr_gray_r2 [9]),
            .CE (1'b1),
            .CK (ntclkbufg_0),
            .D (\system/display_fifo/wr_gray_r1 [9]),
            .SR (\CLMS_291_505/ntRSCO ));

(* PAP_BLE_DEF="D" *)    V_FFSYN /* CLMA_219_768 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/input_link/input_dma/capture/pixels/rd_gray[0]/opit_0_inv/FF3/FF  (
            .Q (\system/input_link/input_dma/capture/pixels/rd_gray [0]),
            .CE (\CLMS_207_649/ntCE ),
            .CK (core_clk),
            .D (\system/input_link/input_dma/capture/pixels/N110 [0]),
            .SR (\CLMA_219_768/ntRSCO ));

(* PAP_BLE_DEF="C" *)    V_FFSYN /* CLMA_219_768 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/input_link/input_dma/capture/pixels/rd_gray[1]/opit_0_inv/FF2/FF  (
            .Q (\system/input_link/input_dma/capture/pixels/rd_gray [1]),
            .CE (\CLMS_207_649/ntCE ),
            .CK (core_clk),
            .D (\system/input_link/input_dma/capture/pixels/N110 [1]),
            .SR (\CLMA_219_768/ntRSCO ));

(* PAP_BLE_DEF="B" *)    V_FFSYN /* CLMA_219_768 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/input_link/input_dma/capture/pixels/rd_gray[2]/opit_0_inv/FF1/FF  (
            .Q (\system/input_link/input_dma/capture/pixels/rd_gray [2]),
            .CE (\CLMS_207_649/ntCE ),
            .CK (core_clk),
            .D (\system/input_link/input_dma/capture/pixels/N110 [2]),
            .SR (\CLMA_219_768/ntRSCO ));

(* PAP_BLE_DEF="A" *)    V_FFSYN /* CLMA_219_768 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/input_link/input_dma/capture/pixels/rd_gray[3]/opit_0_inv/FF0/FF  (
            .Q (\system/input_link/input_dma/capture/pixels/rd_gray [3]),
            .CE (\CLMS_207_649/ntCE ),
            .CK (core_clk),
            .D (\system/input_link/input_dma/capture/pixels/N110 [3]),
            .SR (\CLMA_219_768/ntRSCO ));

(* PAP_BLE_DEF="B" *)    V_FFSYN /* CLMA_219_673 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/input_link/input_dma/capture/pixels/rd_gray[4]/opit_0_inv/FF1/FF  (
            .Q (\system/input_link/input_dma/capture/pixels/rd_gray [4]),
            .CE (\CLMS_207_649/ntCE ),
            .CK (core_clk),
            .D (\system/input_link/input_dma/capture/pixels/N110 [4]),
            .SR (\CLMA_219_673/ntRSCO ));

(* PAP_BLE_DEF="C" *)    V_FFSYN /* CLMA_219_673 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/input_link/input_dma/capture/pixels/rd_gray[5]/opit_0_inv/FF2/FF  (
            .Q (\system/input_link/input_dma/capture/pixels/rd_gray [5]),
            .CE (\CLMS_207_649/ntCE ),
            .CK (core_clk),
            .D (\system/input_link/input_dma/capture/pixels/N110 [5]),
            .SR (\CLMA_219_673/ntRSCO ));

(* PAP_BLE_DEF="D" *)    V_FFSYN /* CLMA_219_673 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/input_link/input_dma/capture/pixels/rd_gray[6]/opit_0_inv/FF3/FF  (
            .Q (\system/input_link/input_dma/capture/pixels/rd_gray [6]),
            .CE (\CLMS_207_649/ntCE ),
            .CK (core_clk),
            .D (\system/input_link/input_dma/capture/pixels/next_rd [6]),
            .SR (\CLMA_219_673/ntRSCO ));

(* PAP_BLE_DEF="A" *)    V_FFSYN /* CLMA_219_774 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/input_link/input_dma/capture/pixels/rd_gray_w1[0]/opit_0_inv/FF0/FF  (
            .Q (\system/input_link/input_dma/capture/pixels/rd_gray_w1 [0]),
            .CE (1'b1),
            .CK (ntclkbufg_0),
            .D (\system/input_link/input_dma/capture/pixels/rd_gray [0]),
            .SR (\CLMA_219_774/ntRSCO ));

(* PAP_BLE_DEF="C" *)    V_FFSYN /* CLMA_219_774 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/input_link/input_dma/capture/pixels/rd_gray_w1[1]/opit_0_inv/FF2/FF  (
            .Q (\system/input_link/input_dma/capture/pixels/rd_gray_w1 [1]),
            .CE (1'b1),
            .CK (ntclkbufg_0),
            .D (\system/input_link/input_dma/capture/pixels/rd_gray [1]),
            .SR (\CLMA_219_774/ntRSCO ));

(* PAP_BLE_DEF="A" *)    V_FFSYN /* CLMA_243_750 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/input_link/input_dma/capture/pixels/rd_gray_w1[2]/opit_0_inv/FF0/FF  (
            .Q (\system/input_link/input_dma/capture/pixels/rd_gray_w1 [2]),
            .CE (1'b1),
            .CK (ntclkbufg_0),
            .D (\system/input_link/input_dma/capture/pixels/rd_gray [2]),
            .SR (\CLMA_243_750/ntRSCO ));

(* PAP_BLE_DEF="C" *)    V_FFSYN /* CLMA_243_750 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/input_link/input_dma/capture/pixels/rd_gray_w1[3]/opit_0_inv/FF2/FF  (
            .Q (\system/input_link/input_dma/capture/pixels/rd_gray_w1 [3]),
            .CE (1'b1),
            .CK (ntclkbufg_0),
            .D (\system/input_link/input_dma/capture/pixels/rd_gray [3]),
            .SR (\CLMA_243_750/ntRSCO ));

(* PAP_BLE_DEF="A" *)    V_FFSYN /* CLMA_231_678 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/input_link/input_dma/capture/pixels/rd_gray_w1[4]/opit_0_inv/FF0/FF  (
            .Q (\system/input_link/input_dma/capture/pixels/rd_gray_w1 [4]),
            .CE (1'b1),
            .CK (ntclkbufg_0),
            .D (\system/input_link/input_dma/capture/pixels/rd_gray [4]),
            .SR (\CLMA_231_678/ntRSCO ));

(* PAP_BLE_DEF="C" *)    V_FFSYN /* CLMA_231_678 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/input_link/input_dma/capture/pixels/rd_gray_w1[5]/opit_0_inv/FF2/FF  (
            .Q (\system/input_link/input_dma/capture/pixels/rd_gray_w1 [5]),
            .CE (1'b1),
            .CK (ntclkbufg_0),
            .D (\system/input_link/input_dma/capture/pixels/rd_gray [5]),
            .SR (\CLMA_231_678/ntRSCO ));

(* PAP_BLE_DEF="A" *)    V_FFSYN /* CLMA_231_691 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/input_link/input_dma/capture/pixels/rd_gray_w1[6]/opit_0_inv/FF0/FF  (
            .Q (\system/input_link/input_dma/capture/pixels/rd_gray_w1 [6]),
            .CE (1'b1),
            .CK (ntclkbufg_0),
            .D (\system/input_link/input_dma/capture/pixels/rd_gray [6]),
            .SR (\CLMA_231_691/ntRSCO ));

(* PAP_BLE_DEF="B" *)    V_FFSYN /* CLMA_219_774 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/input_link/input_dma/capture/pixels/rd_gray_w2[0]/opit_0_inv/FF1/FF  (
            .Q (\system/input_link/input_dma/capture/pixels/rd_gray_w2 [0]),
            .CE (1'b1),
            .CK (ntclkbufg_0),
            .D (\system/input_link/input_dma/capture/pixels/rd_gray_w1 [0]),
            .SR (\CLMA_219_774/ntRSCO ));

(* PAP_BLE_DEF="D" *)    V_FFSYN /* CLMA_219_774 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/input_link/input_dma/capture/pixels/rd_gray_w2[1]/opit_0_inv/FF3/FF  (
            .Q (\system/input_link/input_dma/capture/pixels/rd_gray_w2 [1]),
            .CE (1'b1),
            .CK (ntclkbufg_0),
            .D (\system/input_link/input_dma/capture/pixels/rd_gray_w1 [1]),
            .SR (\CLMA_219_774/ntRSCO ));

(* PAP_BLE_DEF="B" *)    V_FFSYN /* CLMA_243_750 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/input_link/input_dma/capture/pixels/rd_gray_w2[2]/opit_0_inv/FF1/FF  (
            .Q (\system/input_link/input_dma/capture/pixels/rd_gray_w2 [2]),
            .CE (1'b1),
            .CK (ntclkbufg_0),
            .D (\system/input_link/input_dma/capture/pixels/rd_gray_w1 [2]),
            .SR (\CLMA_243_750/ntRSCO ));

(* PAP_BLE_DEF="D" *)    V_FFSYN /* CLMA_243_750 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/input_link/input_dma/capture/pixels/rd_gray_w2[3]/opit_0_inv/FF3/FF  (
            .Q (\system/input_link/input_dma/capture/pixels/rd_gray_w2 [3]),
            .CE (1'b1),
            .CK (ntclkbufg_0),
            .D (\system/input_link/input_dma/capture/pixels/rd_gray_w1 [3]),
            .SR (\CLMA_243_750/ntRSCO ));

(* PAP_BLE_DEF="B" *)    V_FFSYN /* CLMA_231_678 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/input_link/input_dma/capture/pixels/rd_gray_w2[4]/opit_0_inv/FF1/FF  (
            .Q (\system/input_link/input_dma/capture/pixels/rd_gray_w2 [4]),
            .CE (1'b1),
            .CK (ntclkbufg_0),
            .D (\system/input_link/input_dma/capture/pixels/rd_gray_w1 [4]),
            .SR (\CLMA_231_678/ntRSCO ));

(* PAP_BLE_DEF="D" *)    V_FFSYN /* CLMA_231_678 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/input_link/input_dma/capture/pixels/rd_gray_w2[5]/opit_0_inv/FF3/FF  (
            .Q (\system/input_link/input_dma/capture/pixels/rd_gray_w2 [5]),
            .CE (1'b1),
            .CK (ntclkbufg_0),
            .D (\system/input_link/input_dma/capture/pixels/rd_gray_w1 [5]),
            .SR (\CLMA_231_678/ntRSCO ));

(* PAP_BLE_DEF="B" *)    V_FFSYN /* CLMA_231_691 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/input_link/input_dma/capture/pixels/rd_gray_w2[6]/opit_0_inv/FF1/FF  (
            .Q (\system/input_link/input_dma/capture/pixels/rd_gray_w2 [6]),
            .CE (1'b1),
            .CK (ntclkbufg_0),
            .D (\system/input_link/input_dma/capture/pixels/rd_gray_w1 [6]),
            .SR (\CLMA_231_691/ntRSCO ));

(* PAP_BLE_DEF="A" *)    V_FFSYN /* CLMA_225_732 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/input_link/input_dma/capture/pixels/wr_gray[0]/opit_0_inv/FF0/FF  (
            .Q (\system/input_link/input_dma/capture/pixels/wr_gray [0]),
            .CE (\CLMS_183_637/ntCE ),
            .CK (ntclkbufg_0),
            .D (\system/input_link/input_dma/capture/pixels/N88 [0]),
            .SR (\CLMA_225_732/ntRSCO ));

(* PAP_BLE_DEF="D" *)    V_FFSYN /* CLMA_225_732 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/input_link/input_dma/capture/pixels/wr_gray[1]/opit_0_inv/FF3/FF  (
            .Q (\system/input_link/input_dma/capture/pixels/wr_gray [1]),
            .CE (\CLMS_183_637/ntCE ),
            .CK (ntclkbufg_0),
            .D (\system/input_link/input_dma/capture/pixels/N88 [1]),
            .SR (\CLMA_225_732/ntRSCO ));

(* PAP_BLE_DEF="B" *)    V_FFSYN /* CLMA_225_732 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/input_link/input_dma/capture/pixels/wr_gray[2]/opit_0_inv/FF1/FF  (
            .Q (\system/input_link/input_dma/capture/pixels/wr_gray [2]),
            .CE (\CLMS_183_637/ntCE ),
            .CK (ntclkbufg_0),
            .D (\system/input_link/input_dma/capture/pixels/N88 [2]),
            .SR (\CLMA_225_732/ntRSCO ));

(* PAP_BLE_DEF="C" *)    V_FFSYN /* CLMA_225_732 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/input_link/input_dma/capture/pixels/wr_gray[3]/opit_0_inv/FF2/FF  (
            .Q (\system/input_link/input_dma/capture/pixels/wr_gray [3]),
            .CE (\CLMS_183_637/ntCE ),
            .CK (ntclkbufg_0),
            .D (\system/input_link/input_dma/capture/pixels/N88 [3]),
            .SR (\CLMA_225_732/ntRSCO ));

(* PAP_BLE_DEF="C" *)    V_FFSYN /* CLMA_225_672 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/input_link/input_dma/capture/pixels/wr_gray[4]/opit_0_inv/FF2/FF  (
            .Q (\system/input_link/input_dma/capture/pixels/wr_gray [4]),
            .CE (\CLMS_183_637/ntCE ),
            .CK (ntclkbufg_0),
            .D (\system/input_link/input_dma/capture/pixels/N88 [4]),
            .SR (\CLMA_225_672/ntRSCO ));

(* PAP_BLE_DEF="B" *)    V_FFSYN /* CLMA_225_672 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/input_link/input_dma/capture/pixels/wr_gray[5]/opit_0_inv/FF1/FF  (
            .Q (\system/input_link/input_dma/capture/pixels/wr_gray [5]),
            .CE (\CLMS_183_637/ntCE ),
            .CK (ntclkbufg_0),
            .D (\system/input_link/input_dma/capture/pixels/N88 [5]),
            .SR (\CLMA_225_672/ntRSCO ));

(* PAP_BLE_DEF="D" *)    V_FFSYN /* CLMA_225_672 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/input_link/input_dma/capture/pixels/wr_gray[6]/opit_0_inv/FF3/FF  (
            .Q (\system/input_link/input_dma/capture/pixels/wr_gray [6]),
            .CE (\CLMS_183_637/ntCE ),
            .CK (ntclkbufg_0),
            .D (\system/input_link/input_dma/capture/pixels/next_wr [6]),
            .SR (\CLMA_225_672/ntRSCO ));

(* PAP_BLE_DEF="A" *)    V_FFSYN /* CLMA_231_672 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/input_link/input_dma/capture/pixels/wr_gray_r1[0]/opit_0_inv/FF0/FF  (
            .Q (\system/input_link/input_dma/capture/pixels/wr_gray_r1 [0]),
            .CE (1'b1),
            .CK (core_clk),
            .D (\system/input_link/input_dma/capture/pixels/wr_gray [0]),
            .SR (\CLMA_231_672/ntRSCO ));

(* PAP_BLE_DEF="A" *)    V_FFSYN /* CLMA_231_703 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/input_link/input_dma/capture/pixels/wr_gray_r1[1]/opit_0_inv/FF0/FF  (
            .Q (\system/input_link/input_dma/capture/pixels/wr_gray_r1 [1]),
            .CE (1'b1),
            .CK (core_clk),
            .D (\system/input_link/input_dma/capture/pixels/wr_gray [1]),
            .SR (\CLMA_231_703/ntRSCO ));

(* PAP_BLE_DEF="A" *)    V_FFSYN /* CLMA_231_751 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/input_link/input_dma/capture/pixels/wr_gray_r1[2]/opit_0_inv/FF0/FF  (
            .Q (\system/input_link/input_dma/capture/pixels/wr_gray_r1 [2]),
            .CE (1'b1),
            .CK (core_clk),
            .D (\system/input_link/input_dma/capture/pixels/wr_gray [2]),
            .SR (\CLMA_231_751/ntRSCO ));

(* PAP_BLE_DEF="C" *)    V_FFSYN /* CLMA_231_751 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/input_link/input_dma/capture/pixels/wr_gray_r1[3]/opit_0_inv/FF2/FF  (
            .Q (\system/input_link/input_dma/capture/pixels/wr_gray_r1 [3]),
            .CE (1'b1),
            .CK (core_clk),
            .D (\system/input_link/input_dma/capture/pixels/wr_gray [3]),
            .SR (\CLMA_231_751/ntRSCO ));

(* PAP_BLE_DEF="A" *)    V_FFSYN /* CLMS_225_679 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/input_link/input_dma/capture/pixels/wr_gray_r1[4]/opit_0_inv/FF0/FF  (
            .Q (\system/input_link/input_dma/capture/pixels/wr_gray_r1 [4]),
            .CE (1'b1),
            .CK (core_clk),
            .D (\system/input_link/input_dma/capture/pixels/wr_gray [4]),
            .SR (\CLMS_225_679/ntRSCO ));

(* PAP_BLE_DEF="C" *)    V_FFSYN /* CLMS_225_679 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/input_link/input_dma/capture/pixels/wr_gray_r1[5]/opit_0_inv/FF2/FF  (
            .Q (\system/input_link/input_dma/capture/pixels/wr_gray_r1 [5]),
            .CE (1'b1),
            .CK (core_clk),
            .D (\system/input_link/input_dma/capture/pixels/wr_gray [5]),
            .SR (\CLMS_225_679/ntRSCO ));

(* PAP_BLE_DEF="C" *)    V_FFSYN /* CLMA_231_672 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/input_link/input_dma/capture/pixels/wr_gray_r1[6]/opit_0_inv/FF2/FF  (
            .Q (\system/input_link/input_dma/capture/pixels/wr_gray_r1 [6]),
            .CE (1'b1),
            .CK (core_clk),
            .D (\system/input_link/input_dma/capture/pixels/wr_gray [6]),
            .SR (\CLMA_231_672/ntRSCO ));

(* PAP_BLE_DEF="B" *)    V_FFSYN /* CLMA_231_672 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/input_link/input_dma/capture/pixels/wr_gray_r2[0]/opit_0_inv/FF1/FF  (
            .Q (\system/input_link/input_dma/capture/pixels/wr_gray_r2 [0]),
            .CE (1'b1),
            .CK (core_clk),
            .D (\system/input_link/input_dma/capture/pixels/wr_gray_r1 [0]),
            .SR (\CLMA_231_672/ntRSCO ));

(* PAP_BLE_DEF="B" *)    V_FFSYN /* CLMA_231_703 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/input_link/input_dma/capture/pixels/wr_gray_r2[1]/opit_0_inv/FF1/FF  (
            .Q (\system/input_link/input_dma/capture/pixels/wr_gray_r2 [1]),
            .CE (1'b1),
            .CK (core_clk),
            .D (\system/input_link/input_dma/capture/pixels/wr_gray_r1 [1]),
            .SR (\CLMA_231_703/ntRSCO ));

(* PAP_BLE_DEF="B" *)    V_FFSYN /* CLMA_231_751 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/input_link/input_dma/capture/pixels/wr_gray_r2[2]/opit_0_inv/FF1/FF  (
            .Q (\system/input_link/input_dma/capture/pixels/wr_gray_r2 [2]),
            .CE (1'b1),
            .CK (core_clk),
            .D (\system/input_link/input_dma/capture/pixels/wr_gray_r1 [2]),
            .SR (\CLMA_231_751/ntRSCO ));

(* PAP_BLE_DEF="D" *)    V_FFSYN /* CLMA_231_751 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/input_link/input_dma/capture/pixels/wr_gray_r2[3]/opit_0_inv/FF3/FF  (
            .Q (\system/input_link/input_dma/capture/pixels/wr_gray_r2 [3]),
            .CE (1'b1),
            .CK (core_clk),
            .D (\system/input_link/input_dma/capture/pixels/wr_gray_r1 [3]),
            .SR (\CLMA_231_751/ntRSCO ));

(* PAP_BLE_DEF="B" *)    V_FFSYN /* CLMS_225_679 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/input_link/input_dma/capture/pixels/wr_gray_r2[4]/opit_0_inv/FF1/FF  (
            .Q (\system/input_link/input_dma/capture/pixels/wr_gray_r2 [4]),
            .CE (1'b1),
            .CK (core_clk),
            .D (\system/input_link/input_dma/capture/pixels/wr_gray_r1 [4]),
            .SR (\CLMS_225_679/ntRSCO ));

(* PAP_BLE_DEF="D" *)    V_FFSYN /* CLMS_225_679 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/input_link/input_dma/capture/pixels/wr_gray_r2[5]/opit_0_inv/FF3/FF  (
            .Q (\system/input_link/input_dma/capture/pixels/wr_gray_r2 [5]),
            .CE (1'b1),
            .CK (core_clk),
            .D (\system/input_link/input_dma/capture/pixels/wr_gray_r1 [5]),
            .SR (\CLMS_225_679/ntRSCO ));

(* PAP_BLE_DEF="D" *)    V_FFSYN /* CLMA_231_672 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/input_link/input_dma/capture/pixels/wr_gray_r2[6]/opit_0_inv/FF3/FF  (
            .Q (\system/input_link/input_dma/capture/pixels/wr_gray_r2 [6]),
            .CE (1'b1),
            .CK (core_clk),
            .D (\system/input_link/input_dma/capture/pixels/wr_gray_r1 [6]),
            .SR (\CLMA_231_672/ntRSCO ));
