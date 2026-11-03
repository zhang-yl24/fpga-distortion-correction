(* PAP_BLE_DEF="C" *)    V_FFASYN /* CLMS_171_367 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \core_reset[0]/opit_0/FF2/FF  (
            .Q (core_reset[0]),
            .CE (1'b1),
            .CK (core_clk),
            .D (1'b1),
            .SR (\CLMA_75_264/ntRS ));

(* PAP_BLE_DEF="D" *)    V_FFASYN /* CLMS_171_367 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \core_reset[1]/opit_0/FF3/FF  (
            .Q (core_reset[1]),
            .CE (1'b1),
            .CK (core_clk),
            .D (core_reset[0]),
            .SR (\CLMA_75_264/ntRS ));

(* PAP_BLE_DEF="A" *)    V_FFSYN /* CLMA_285_402 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/rd_binary[9]/opit_0_inv_AQ/FF0/FF  (
            .Q (\system/display_fifo/rd_binary [9]),
            .CE (ntR1190),
            .CK (ntclkbufg_0),
            .D (\system/display_fifo/next_rd [9]),
            .SR (ntR3541));

(* PAP_BLE_DEF="A" *)    V_FFSYN /* CLMS_285_397 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/rd_gray[0]/opit_0_inv_L6Q_LUT6DL5Q_perm/FFAPP0/FF  (
            .Q (\system/display_fifo/rd_gray [0]),
            .CE (\CLMS_285_397/ntCE ),
            .CK (ntclkbufg_0),
            .D (\CLMS_285_397/ntQC0 ),
            .SR (\CLMS_285_397/ntRSCO ));

(* PAP_BLE_DEF="B" *)    V_FFSYN /* CLMS_285_397 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/rd_gray[2]/opit_0_inv_L6Q_LUT6DQL5Q_perm/FF1/FF  (
            .Q (\system/display_fifo/rd_gray [2]),
            .CE (\CLMS_285_397/ntCE ),
            .CK (ntclkbufg_0),
            .D (\CLMS_285_397/ntQD1 ),
            .SR (\CLMS_285_397/ntRSCO ));

(* PAP_BLE_DEF="B" *)    V_FFSYN /* CLMS_285_397 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/rd_gray[2]/opit_0_inv_L6Q_LUT6DQL5Q_perm/FFAPP1/FF  (
            .Q (\system/display_fifo/rd_gray [1]),
            .CE (\CLMS_285_397/ntCE ),
            .CK (ntclkbufg_0),
            .D (\CLMS_285_397/ntQC1 ),
            .SR (\CLMS_285_397/ntRSCO ));

(* PAP_BLE_DEF="D" *)    V_FFSYN /* CLMA_285_402 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/rd_gray[4]/opit_0_inv_L6Q_LUT6DQL5Q_perm/FF3/FF  (
            .Q (\system/display_fifo/rd_gray [4]),
            .CE (ntR1190),
            .CK (ntclkbufg_0),
            .D (\CLMA_285_402/ntQD3 ),
            .SR (ntR3541));

(* PAP_BLE_DEF="D" *)    V_FFSYN /* CLMA_285_402 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/rd_gray[4]/opit_0_inv_L6Q_LUT6DQL5Q_perm/FFAPP3/FF  (
            .Q (\system/display_fifo/rd_gray [3]),
            .CE (ntR1190),
            .CK (ntclkbufg_0),
            .D (\CLMA_285_402/ntQC3 ),
            .SR (ntR3541));

(* PAP_BLE_DEF="C" *)    V_FFSYN /* CLMA_285_402 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/rd_gray[6]/opit_0_inv_L6Q_LUT6DQL5Q_perm/FF2/FF  (
            .Q (\system/display_fifo/rd_gray [6]),
            .CE (ntR1190),
            .CK (ntclkbufg_0),
            .D (\CLMA_285_402/ntQD2 ),
            .SR (ntR3541));

(* PAP_BLE_DEF="C" *)    V_FFSYN /* CLMA_285_402 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/rd_gray[6]/opit_0_inv_L6Q_LUT6DQL5Q_perm/FFAPP2/FF  (
            .Q (\system/display_fifo/rd_gray [5]),
            .CE (ntR1190),
            .CK (ntclkbufg_0),
            .D (\CLMA_285_402/ntQC2 ),
            .SR (ntR3541));

(* PAP_BLE_DEF="B" *)    V_FFSYN /* CLMA_285_402 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/rd_gray[8]/opit_0_inv_L6Q_LUT6DQL5Q_perm/FF1/FF  (
            .Q (\system/display_fifo/rd_gray [8]),
            .CE (ntR1190),
            .CK (ntclkbufg_0),
            .D (\CLMA_285_402/ntQD1 ),
            .SR (ntR3541));

(* PAP_BLE_DEF="B" *)    V_FFSYN /* CLMA_285_402 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/rd_gray[8]/opit_0_inv_L6Q_LUT6DQL5Q_perm/FFAPP1/FF  (
            .Q (\system/display_fifo/rd_gray [7]),
            .CE (ntR1190),
            .CK (ntclkbufg_0),
            .D (\CLMA_285_402/ntQC1 ),
            .SR (ntR3541));

(* PAP_BLE_DEF="A" *)    V_FFSYN /* CLMA_273_402 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/rd_gray_w1[0]/opit_0_inv/FF0/FF  (
            .Q (\system/display_fifo/rd_gray_w1 [0]),
            .CE (1'b1),
            .CK (core_clk),
            .D (\system/display_fifo/rd_gray [0]),
            .SR (ntR3095));

(* PAP_BLE_DEF="C" *)    V_FFSYN /* CLMA_267_426 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/rd_gray_w1[1]/opit_0_inv/FF2/FF  (
            .Q (\system/display_fifo/rd_gray_w1 [1]),
            .CE (1'b1),
            .CK (core_clk),
            .D (\system/display_fifo/rd_gray [1]),
            .SR (\CLMA_267_426/ntRSCO ));

(* PAP_BLE_DEF="C" *)    V_FFSYN /* CLMA_273_402 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/rd_gray_w1[2]/opit_0_inv/FF2/FF  (
            .Q (\system/display_fifo/rd_gray_w1 [2]),
            .CE (1'b1),
            .CK (core_clk),
            .D (\system/display_fifo/rd_gray [2]),
            .SR (ntR3095));

(* PAP_BLE_DEF="A" *)    V_FFSYN /* CLMA_267_426 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/rd_gray_w1[3]/opit_0_inv/FF0/FF  (
            .Q (\system/display_fifo/rd_gray_w1 [3]),
            .CE (1'b1),
            .CK (core_clk),
            .D (\system/display_fifo/rd_gray [3]),
            .SR (\CLMA_267_426/ntRSCO ));

(* PAP_BLE_DEF="A" *)    V_FFSYN /* CLMA_267_366 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/rd_gray_w1[4]/opit_0_inv/FF0/FF  (
            .Q (\system/display_fifo/rd_gray_w1 [4]),
            .CE (1'b1),
            .CK (core_clk),
            .D (\system/display_fifo/rd_gray [4]),
            .SR (ntR2137));

(* PAP_BLE_DEF="A" *)    V_FFSYN /* CLMA_267_300 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/rd_gray_w1[5]/opit_0_inv/FF0/FF  (
            .Q (\system/display_fifo/rd_gray_w1 [5]),
            .CE (1'b1),
            .CK (core_clk),
            .D (\system/display_fifo/rd_gray [5]),
            .SR (\CLMA_267_300/ntRSCO ));

(* PAP_BLE_DEF="C" *)    V_FFSYN /* CLMA_267_372 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/rd_gray_w1[6]/opit_0_inv/FF2/FF  (
            .Q (\system/display_fifo/rd_gray_w1 [6]),
            .CE (1'b1),
            .CK (core_clk),
            .D (\system/display_fifo/rd_gray [6]),
            .SR (ntR2137));

(* PAP_BLE_DEF="A" *)    V_FFSYN /* CLMA_267_378 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/rd_gray_w1[7]/opit_0_inv/FF0/FF  (
            .Q (\system/display_fifo/rd_gray_w1 [7]),
            .CE (1'b1),
            .CK (core_clk),
            .D (\system/display_fifo/rd_gray [7]),
            .SR (ntR2138));

(* PAP_BLE_DEF="C" *)    V_FFSYN /* CLMA_267_378 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/rd_gray_w1[8]/opit_0_inv/FF2/FF  (
            .Q (\system/display_fifo/rd_gray_w1 [8]),
            .CE (1'b1),
            .CK (core_clk),
            .D (\system/display_fifo/rd_gray [8]),
            .SR (ntR2138));

(* PAP_BLE_DEF="A" *)    V_FFSYN /* CLMA_267_372 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/rd_gray_w1[9]/opit_0_inv/FF0/FF  (
            .Q (\system/display_fifo/rd_gray_w1 [9]),
            .CE (1'b1),
            .CK (core_clk),
            .D (\system/display_fifo/rd_binary [9]),
            .SR (ntR2137));

(* PAP_BLE_DEF="B" *)    V_FFSYN /* CLMA_273_402 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/rd_gray_w2[0]/opit_0_inv/FF1/FF  (
            .Q (\system/display_fifo/rd_gray_w2 [0]),
            .CE (1'b1),
            .CK (core_clk),
            .D (\system/display_fifo/rd_gray_w1 [0]),
            .SR (ntR3095));

(* PAP_BLE_DEF="D" *)    V_FFSYN /* CLMA_267_426 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/rd_gray_w2[1]/opit_0_inv/FF3/FF  (
            .Q (\system/display_fifo/rd_gray_w2 [1]),
            .CE (1'b1),
            .CK (core_clk),
            .D (\system/display_fifo/rd_gray_w1 [1]),
            .SR (\CLMA_267_426/ntRSCO ));

(* PAP_BLE_DEF="D" *)    V_FFSYN /* CLMA_273_402 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/rd_gray_w2[2]/opit_0_inv/FF3/FF  (
            .Q (\system/display_fifo/rd_gray_w2 [2]),
            .CE (1'b1),
            .CK (core_clk),
            .D (\system/display_fifo/rd_gray_w1 [2]),
            .SR (ntR3095));

(* PAP_BLE_DEF="B" *)    V_FFSYN /* CLMA_267_426 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/rd_gray_w2[3]/opit_0_inv/FF1/FF  (
            .Q (\system/display_fifo/rd_gray_w2 [3]),
            .CE (1'b1),
            .CK (core_clk),
            .D (\system/display_fifo/rd_gray_w1 [3]),
            .SR (\CLMA_267_426/ntRSCO ));

(* PAP_BLE_DEF="B" *)    V_FFSYN /* CLMA_267_366 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/rd_gray_w2[4]/opit_0_inv/FF1/FF  (
            .Q (\system/display_fifo/rd_gray_w2 [4]),
            .CE (1'b1),
            .CK (core_clk),
            .D (\system/display_fifo/rd_gray_w1 [4]),
            .SR (ntR2137));

(* PAP_BLE_DEF="B" *)    V_FFSYN /* CLMA_267_300 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/rd_gray_w2[5]/opit_0_inv/FF1/FF  (
            .Q (\system/display_fifo/rd_gray_w2 [5]),
            .CE (1'b1),
            .CK (core_clk),
            .D (\system/display_fifo/rd_gray_w1 [5]),
            .SR (\CLMA_267_300/ntRSCO ));

(* PAP_BLE_DEF="D" *)    V_FFSYN /* CLMA_267_372 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/rd_gray_w2[6]/opit_0_inv/FF3/FF  (
            .Q (\system/display_fifo/rd_gray_w2 [6]),
            .CE (1'b1),
            .CK (core_clk),
            .D (\system/display_fifo/rd_gray_w1 [6]),
            .SR (ntR2137));

(* PAP_BLE_DEF="B" *)    V_FFSYN /* CLMA_267_378 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/rd_gray_w2[7]/opit_0_inv/FF1/FF  (
            .Q (\system/display_fifo/rd_gray_w2 [7]),
            .CE (1'b1),
            .CK (core_clk),
            .D (\system/display_fifo/rd_gray_w1 [7]),
            .SR (ntR2138));

(* PAP_BLE_DEF="D" *)    V_FFSYN /* CLMA_267_378 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/rd_gray_w2[8]/opit_0_inv/FF3/FF  (
            .Q (\system/display_fifo/rd_gray_w2 [8]),
            .CE (1'b1),
            .CK (core_clk),
            .D (\system/display_fifo/rd_gray_w1 [8]),
            .SR (ntR2138));

(* PAP_BLE_DEF="B" *)    V_FFSYN /* CLMA_267_372 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/rd_gray_w2[9]/opit_0_inv/FF1/FF  (
            .Q (\system/display_fifo/rd_gray_w2 [9]),
            .CE (1'b1),
            .CK (core_clk),
            .D (\system/display_fifo/rd_gray_w1 [9]),
            .SR (ntR2137));

(* PAP_BLE_DEF="C" *)    V_FFASYN /* CLMA_195_541 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/rd_reset_sync[0]/opit_0/FFAPP2/FF  (
            .Q (\system/display_fifo/rd_reset_sync [0]),
            .CE (1'b1),
            .CK (ntclkbufg_0),
            .D (1'b1),
            .SR (\CLMA_75_264/ntRS ));

(* PAP_BLE_DEF="D" *)    V_FFASYN /* CLMA_195_541 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/rd_reset_sync[1]/opit_0/FFAPP3/FF  (
            .Q (\system/display_fifo/rd_reset_sync [1]),
            .CE (1'b1),
            .CK (ntclkbufg_0),
            .D (\system/display_fifo/rd_reset_sync [0]),
            .SR (\CLMA_75_264/ntRS ));

(* PAP_BLE_DEF="A" *)    V_FFSYN /* CLMA_273_396 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/wr_binary[9]/opit_0_inv_AQ/FF0/FF  (
            .Q (\system/display_fifo/wr_binary [9]),
            .CE (ntR1188),
            .CK (core_clk),
            .D (\system/display_fifo/next_wr [9]),
            .SR (ntR3094));

(* PAP_BLE_DEF="B" *)    V_FFSYN /* CLMA_273_396 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/wr_gray[0]/opit_0_inv_L6Q_perm/FF1/FF  (
            .Q (\system/display_fifo/wr_gray [0]),
            .CE (ntR1188),
            .CK (core_clk),
            .D (\CLMA_273_396/ntQD1 ),
            .SR (ntR3094));

(* PAP_BLE_DEF="A" *)    V_FFSYN /* CLMA_273_373 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/wr_gray[1]/opit_0_inv_L6Q_perm/FF0/FF  (
            .Q (\system/display_fifo/wr_gray [1]),
            .CE (\CLMA_273_378/ntCE ),
            .CK (core_clk),
            .D (\CLMA_273_373/ntQD0 ),
            .SR (\CLMA_273_373/ntRSCO ));

(* PAP_BLE_DEF="B" *)    V_FFSYN /* CLMA_273_373 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/wr_gray[2]/opit_0_inv_L6Q_perm/FF1/FF  (
            .Q (\system/display_fifo/wr_gray [2]),
            .CE (\CLMA_273_378/ntCE ),
            .CK (core_clk),
            .D (\CLMA_273_373/ntQD1 ),
            .SR (\CLMA_273_373/ntRSCO ));

(* PAP_BLE_DEF="C" *)    V_FFSYN /* CLMA_273_373 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/wr_gray[3]/opit_0_inv_L6Q_perm/FF2/FF  (
            .Q (\system/display_fifo/wr_gray [3]),
            .CE (\CLMA_273_378/ntCE ),
            .CK (core_clk),
            .D (\CLMA_273_373/ntQD2 ),
            .SR (\CLMA_273_373/ntRSCO ));

(* PAP_BLE_DEF="D" *)    V_FFSYN /* CLMA_273_373 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/wr_gray[4]/opit_0_inv_L6Q_perm/FF3/FF  (
            .Q (\system/display_fifo/wr_gray [4]),
            .CE (\CLMA_273_378/ntCE ),
            .CK (core_clk),
            .D (\CLMA_273_373/ntQD3 ),
            .SR (\CLMA_273_373/ntRSCO ));

(* PAP_BLE_DEF="D" *)    V_FFSYN /* CLMA_273_378 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/wr_gray[5]/opit_0_inv_L6Q_perm/FF3/FF  (
            .Q (\system/display_fifo/wr_gray [5]),
            .CE (\CLMA_273_378/ntCE ),
            .CK (core_clk),
            .D (\CLMA_273_378/ntQD3 ),
            .SR (ntR3092));

(* PAP_BLE_DEF="C" *)    V_FFSYN /* CLMA_273_378 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/wr_gray[6]/opit_0_inv_L6Q_perm/FF2/FF  (
            .Q (\system/display_fifo/wr_gray [6]),
            .CE (\CLMA_273_378/ntCE ),
            .CK (core_clk),
            .D (\CLMA_273_378/ntQD2 ),
            .SR (ntR3092));

(* PAP_BLE_DEF="A" *)    V_FFSYN /* CLMA_273_378 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/wr_gray[7]/opit_0_inv_L6Q_perm/FF0/FF  (
            .Q (\system/display_fifo/wr_gray [7]),
            .CE (\CLMA_273_378/ntCE ),
            .CK (core_clk),
            .D (\CLMA_273_378/ntQD0 ),
            .SR (ntR3092));

(* PAP_BLE_DEF="B" *)    V_FFSYN /* CLMA_273_378 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/wr_gray[8]/opit_0_inv_L6Q_perm/FF1/FF  (
            .Q (\system/display_fifo/wr_gray [8]),
            .CE (\CLMA_273_378/ntCE ),
            .CK (core_clk),
            .D (\CLMA_273_378/ntQD1 ),
            .SR (ntR3092));

(* PAP_BLE_DEF="A" *)    V_FFSYN /* CLMA_273_258 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/wr_gray_r1[0]/opit_0_inv/FF0/FF  (
            .Q (\system/display_fifo/wr_gray_r1 [0]),
            .CE (1'b1),
            .CK (ntclkbufg_0),
            .D (\system/display_fifo/wr_gray [0]),
            .SR (ntR3885));

(* PAP_BLE_DEF="C" *)    V_FFSYN /* CLMA_273_379 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/wr_gray_r1[1]/opit_0_inv/FF2/FF  (
            .Q (\system/display_fifo/wr_gray_r1 [1]),
            .CE (1'b1),
            .CK (ntclkbufg_0),
            .D (\system/display_fifo/wr_gray [1]),
            .SR (\CLMA_273_379/ntRSCO ));

(* PAP_BLE_DEF="A" *)    V_FFSYN /* CLMA_273_379 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/wr_gray_r1[2]/opit_0_inv/FF0/FF  (
            .Q (\system/display_fifo/wr_gray_r1 [2]),
            .CE (1'b1),
            .CK (ntclkbufg_0),
            .D (\system/display_fifo/wr_gray [2]),
            .SR (\CLMA_273_379/ntRSCO ));

(* PAP_BLE_DEF="A" *)    V_FFSYN /* CLMA_273_372 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/wr_gray_r1[3]/opit_0_inv/FF0/FF  (
            .Q (\system/display_fifo/wr_gray_r1 [3]),
            .CE (1'b1),
            .CK (ntclkbufg_0),
            .D (\system/display_fifo/wr_gray [3]),
            .SR (\CLMA_273_372/ntRSCO ));

(* PAP_BLE_DEF="C" *)    V_FFSYN /* CLMA_273_372 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/wr_gray_r1[4]/opit_0_inv/FF2/FF  (
            .Q (\system/display_fifo/wr_gray_r1 [4]),
            .CE (1'b1),
            .CK (ntclkbufg_0),
            .D (\system/display_fifo/wr_gray [4]),
            .SR (\CLMA_273_372/ntRSCO ));

(* PAP_BLE_DEF="C" *)    V_FFSYN /* CLMA_273_258 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/wr_gray_r1[5]/opit_0_inv/FF2/FF  (
            .Q (\system/display_fifo/wr_gray_r1 [5]),
            .CE (1'b1),
            .CK (ntclkbufg_0),
            .D (\system/display_fifo/wr_gray [5]),
            .SR (ntR3885));

(* PAP_BLE_DEF="A" *)    V_FFSYN /* CLMA_273_252 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/wr_gray_r1[6]/opit_0_inv/FF0/FF  (
            .Q (\system/display_fifo/wr_gray_r1 [6]),
            .CE (1'b1),
            .CK (ntclkbufg_0),
            .D (\system/display_fifo/wr_gray [6]),
            .SR (ntR3885));

(* PAP_BLE_DEF="C" *)    V_FFSYN /* CLMS_267_379 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/wr_gray_r1[7]/opit_0_inv/FF2/FF  (
            .Q (\system/display_fifo/wr_gray_r1 [7]),
            .CE (1'b1),
            .CK (ntclkbufg_0),
            .D (\system/display_fifo/wr_gray [7]),
            .SR (\CLMS_267_379/ntRSCO ));

(* PAP_BLE_DEF="A" *)    V_FFSYN /* CLMS_267_379 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/wr_gray_r1[8]/opit_0_inv/FF0/FF  (
            .Q (\system/display_fifo/wr_gray_r1 [8]),
            .CE (1'b1),
            .CK (ntclkbufg_0),
            .D (\system/display_fifo/wr_gray [8]),
            .SR (\CLMS_267_379/ntRSCO ));

(* PAP_BLE_DEF="A" *)    V_FFSYN /* CLMA_273_318 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/wr_gray_r1[9]/opit_0_inv/FF0/FF  (
            .Q (\system/display_fifo/wr_gray_r1 [9]),
            .CE (1'b1),
            .CK (ntclkbufg_0),
            .D (\system/display_fifo/wr_binary [9]),
            .SR (\CLMA_273_318/ntRSCO ));

(* PAP_BLE_DEF="B" *)    V_FFSYN /* CLMA_273_258 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/wr_gray_r2[0]/opit_0_inv/FF1/FF  (
            .Q (\system/display_fifo/wr_gray_r2 [0]),
            .CE (1'b1),
            .CK (ntclkbufg_0),
            .D (\system/display_fifo/wr_gray_r1 [0]),
            .SR (ntR3885));

(* PAP_BLE_DEF="D" *)    V_FFSYN /* CLMA_273_379 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/wr_gray_r2[1]/opit_0_inv/FF3/FF  (
            .Q (\system/display_fifo/wr_gray_r2 [1]),
            .CE (1'b1),
            .CK (ntclkbufg_0),
            .D (\system/display_fifo/wr_gray_r1 [1]),
            .SR (\CLMA_273_379/ntRSCO ));

(* PAP_BLE_DEF="B" *)    V_FFSYN /* CLMA_273_379 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/wr_gray_r2[2]/opit_0_inv/FF1/FF  (
            .Q (\system/display_fifo/wr_gray_r2 [2]),
            .CE (1'b1),
            .CK (ntclkbufg_0),
            .D (\system/display_fifo/wr_gray_r1 [2]),
            .SR (\CLMA_273_379/ntRSCO ));

(* PAP_BLE_DEF="B" *)    V_FFSYN /* CLMA_273_372 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/wr_gray_r2[3]/opit_0_inv/FF1/FF  (
            .Q (\system/display_fifo/wr_gray_r2 [3]),
            .CE (1'b1),
            .CK (ntclkbufg_0),
            .D (\system/display_fifo/wr_gray_r1 [3]),
            .SR (\CLMA_273_372/ntRSCO ));

(* PAP_BLE_DEF="D" *)    V_FFSYN /* CLMA_273_372 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/wr_gray_r2[4]/opit_0_inv/FF3/FF  (
            .Q (\system/display_fifo/wr_gray_r2 [4]),
            .CE (1'b1),
            .CK (ntclkbufg_0),
            .D (\system/display_fifo/wr_gray_r1 [4]),
            .SR (\CLMA_273_372/ntRSCO ));

(* PAP_BLE_DEF="D" *)    V_FFSYN /* CLMA_273_258 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/wr_gray_r2[5]/opit_0_inv/FF3/FF  (
            .Q (\system/display_fifo/wr_gray_r2 [5]),
            .CE (1'b1),
            .CK (ntclkbufg_0),
            .D (\system/display_fifo/wr_gray_r1 [5]),
            .SR (ntR3885));

(* PAP_BLE_DEF="B" *)    V_FFSYN /* CLMA_273_252 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/wr_gray_r2[6]/opit_0_inv/FF1/FF  (
            .Q (\system/display_fifo/wr_gray_r2 [6]),
            .CE (1'b1),
            .CK (ntclkbufg_0),
            .D (\system/display_fifo/wr_gray_r1 [6]),
            .SR (ntR3885));

(* PAP_BLE_DEF="D" *)    V_FFSYN /* CLMS_267_379 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/wr_gray_r2[7]/opit_0_inv/FF3/FF  (
            .Q (\system/display_fifo/wr_gray_r2 [7]),
            .CE (1'b1),
            .CK (ntclkbufg_0),
            .D (\system/display_fifo/wr_gray_r1 [7]),
            .SR (\CLMS_267_379/ntRSCO ));

(* PAP_BLE_DEF="B" *)    V_FFSYN /* CLMS_267_379 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/wr_gray_r2[8]/opit_0_inv/FF1/FF  (
            .Q (\system/display_fifo/wr_gray_r2 [8]),
            .CE (1'b1),
            .CK (ntclkbufg_0),
            .D (\system/display_fifo/wr_gray_r1 [8]),
            .SR (\CLMS_267_379/ntRSCO ));

(* PAP_BLE_DEF="B" *)    V_FFSYN /* CLMA_273_318 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/wr_gray_r2[9]/opit_0_inv/FF1/FF  (
            .Q (\system/display_fifo/wr_gray_r2 [9]),
            .CE (1'b1),
            .CK (ntclkbufg_0),
            .D (\system/display_fifo/wr_gray_r1 [9]),
            .SR (\CLMA_273_318/ntRSCO ));

(* PAP_BLE_DEF="A" *)    V_FFSYN /* CLMS_225_493 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/input_link/input_dma/capture/pixels/rd_binary[6]/opit_0_inv_L6Q_perm/FF0/FF  (
            .Q (\system/input_link/input_dma/capture/pixels/rd_binary [6]),
            .CE (\CLMS_225_493/ntCE ),
            .CK (core_clk),
            .D (\CLMS_225_493/ntQD0 ),
            .SR (\CLMS_225_493/ntRSCO ));

(* PAP_BLE_DEF="D" *)    V_FFSYN /* CLMA_231_486 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/input_link/input_dma/capture/pixels/rd_gray[0]/opit_0_inv_L6Q_perm/FF3/FF  (
            .Q (\system/input_link/input_dma/capture/pixels/rd_gray [0]),
            .CE (\CLMS_225_493/ntCE ),
            .CK (core_clk),
            .D (\CLMA_231_486/ntQD3 ),
            .SR (\CLMA_231_486/ntRSCO ));

(* PAP_BLE_DEF="D" *)    V_FFSYN /* CLMA_231_498 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/input_link/input_dma/capture/pixels/rd_gray[1]/opit_0_inv_L6Q_perm/FF3/FF  (
            .Q (\system/input_link/input_dma/capture/pixels/rd_gray [1]),
            .CE (\CLMS_225_493/ntCE ),
            .CK (core_clk),
            .D (\CLMA_231_498/ntQD3 ),
            .SR (\CLMA_231_498/ntRSCO ));

(* PAP_BLE_DEF="A" *)    V_FFSYN /* CLMA_231_486 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/input_link/input_dma/capture/pixels/rd_gray[2]/opit_0_inv_L6Q_perm/FF0/FF  (
            .Q (\system/input_link/input_dma/capture/pixels/rd_gray [2]),
            .CE (\CLMS_225_493/ntCE ),
            .CK (core_clk),
            .D (\CLMA_231_486/ntQD0 ),
            .SR (\CLMA_231_486/ntRSCO ));

(* PAP_BLE_DEF="B" *)    V_FFSYN /* CLMA_231_486 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/input_link/input_dma/capture/pixels/rd_gray[3]/opit_0_inv_L6Q_perm/FF1/FF  (
            .Q (\system/input_link/input_dma/capture/pixels/rd_gray [3]),
            .CE (\CLMS_225_493/ntCE ),
            .CK (core_clk),
            .D (\CLMA_231_486/ntQD1 ),
            .SR (\CLMA_231_486/ntRSCO ));

(* PAP_BLE_DEF="A" *)    V_FFSYN /* CLMA_231_498 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/input_link/input_dma/capture/pixels/rd_gray[4]/opit_0_inv_L6Q_perm/FF0/FF  (
            .Q (\system/input_link/input_dma/capture/pixels/rd_gray [4]),
            .CE (\CLMS_225_493/ntCE ),
            .CK (core_clk),
            .D (\CLMA_231_498/ntQD0 ),
            .SR (\CLMA_231_498/ntRSCO ));

(* PAP_BLE_DEF="B" *)    V_FFSYN /* CLMS_225_493 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/input_link/input_dma/capture/pixels/rd_gray[5]/opit_0_inv_L6Q_perm/FF1/FF  (
            .Q (\system/input_link/input_dma/capture/pixels/rd_gray [5]),
            .CE (\CLMS_225_493/ntCE ),
            .CK (core_clk),
            .D (\CLMS_225_493/ntQD1 ),
            .SR (\CLMS_225_493/ntRSCO ));

(* PAP_BLE_DEF="C" *)    V_FFSYN /* CLMA_231_492 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/input_link/input_dma/capture/pixels/rd_gray_w1[0]/opit_0_inv/FF2/FF  (
            .Q (\system/input_link/input_dma/capture/pixels/rd_gray_w1 [0]),
            .CE (1'b1),
            .CK (ntclkbufg_0),
            .D (\system/input_link/input_dma/capture/pixels/rd_gray [0]),
            .SR (\CLMA_231_492/ntRSCO ));

(* PAP_BLE_DEF="A" *)    V_FFSYN /* CLMA_231_492 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/input_link/input_dma/capture/pixels/rd_gray_w1[1]/opit_0_inv/FF0/FF  (
            .Q (\system/input_link/input_dma/capture/pixels/rd_gray_w1 [1]),
            .CE (1'b1),
            .CK (ntclkbufg_0),
            .D (\system/input_link/input_dma/capture/pixels/rd_gray [1]),
            .SR (\CLMA_231_492/ntRSCO ));

(* PAP_BLE_DEF="A" *)    V_FFSYN /* CLMS_225_487 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/input_link/input_dma/capture/pixels/rd_gray_w1[2]/opit_0_inv/FF0/FF  (
            .Q (\system/input_link/input_dma/capture/pixels/rd_gray_w1 [2]),
            .CE (1'b1),
            .CK (ntclkbufg_0),
            .D (\system/input_link/input_dma/capture/pixels/rd_gray [2]),
            .SR (\CLMS_225_487/ntRSCO ));

(* PAP_BLE_DEF="C" *)    V_FFSYN /* CLMS_225_487 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/input_link/input_dma/capture/pixels/rd_gray_w1[3]/opit_0_inv/FF2/FF  (
            .Q (\system/input_link/input_dma/capture/pixels/rd_gray_w1 [3]),
            .CE (1'b1),
            .CK (ntclkbufg_0),
            .D (\system/input_link/input_dma/capture/pixels/rd_gray [3]),
            .SR (\CLMS_225_487/ntRSCO ));

(* PAP_BLE_DEF="A" *)    V_FFSYN /* CLMA_219_517 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/input_link/input_dma/capture/pixels/rd_gray_w1[4]/opit_0_inv/FF0/FF  (
            .Q (\system/input_link/input_dma/capture/pixels/rd_gray_w1 [4]),
            .CE (1'b1),
            .CK (ntclkbufg_0),
            .D (\system/input_link/input_dma/capture/pixels/rd_gray [4]),
            .SR (\CLMA_219_517/ntRSCO ));

(* PAP_BLE_DEF="A" *)    V_FFSYN /* CLMA_219_493 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/input_link/input_dma/capture/pixels/rd_gray_w1[5]/opit_0_inv/FF0/FF  (
            .Q (\system/input_link/input_dma/capture/pixels/rd_gray_w1 [5]),
            .CE (1'b1),
            .CK (ntclkbufg_0),
            .D (\system/input_link/input_dma/capture/pixels/rd_gray [5]),
            .SR (\CLMA_219_493/ntRSCO ));

(* PAP_BLE_DEF="C" *)    V_FFSYN /* CLMA_219_493 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/input_link/input_dma/capture/pixels/rd_gray_w1[6]/opit_0_inv/FF2/FF  (
            .Q (\system/input_link/input_dma/capture/pixels/rd_gray_w1 [6]),
            .CE (1'b1),
            .CK (ntclkbufg_0),
            .D (\system/input_link/input_dma/capture/pixels/rd_binary [6]),
            .SR (\CLMA_219_493/ntRSCO ));

(* PAP_BLE_DEF="D" *)    V_FFSYN /* CLMA_231_492 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/input_link/input_dma/capture/pixels/rd_gray_w2[0]/opit_0_inv/FF3/FF  (
            .Q (\system/input_link/input_dma/capture/pixels/rd_gray_w2 [0]),
            .CE (1'b1),
            .CK (ntclkbufg_0),
            .D (\system/input_link/input_dma/capture/pixels/rd_gray_w1 [0]),
            .SR (\CLMA_231_492/ntRSCO ));

(* PAP_BLE_DEF="B" *)    V_FFSYN /* CLMA_231_492 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/input_link/input_dma/capture/pixels/rd_gray_w2[1]/opit_0_inv/FF1/FF  (
            .Q (\system/input_link/input_dma/capture/pixels/rd_gray_w2 [1]),
            .CE (1'b1),
            .CK (ntclkbufg_0),
            .D (\system/input_link/input_dma/capture/pixels/rd_gray_w1 [1]),
            .SR (\CLMA_231_492/ntRSCO ));

(* PAP_BLE_DEF="B" *)    V_FFSYN /* CLMS_225_487 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/input_link/input_dma/capture/pixels/rd_gray_w2[2]/opit_0_inv/FF1/FF  (
            .Q (\system/input_link/input_dma/capture/pixels/rd_gray_w2 [2]),
            .CE (1'b1),
            .CK (ntclkbufg_0),
            .D (\system/input_link/input_dma/capture/pixels/rd_gray_w1 [2]),
            .SR (\CLMS_225_487/ntRSCO ));

(* PAP_BLE_DEF="D" *)    V_FFSYN /* CLMS_225_487 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/input_link/input_dma/capture/pixels/rd_gray_w2[3]/opit_0_inv/FF3/FF  (
            .Q (\system/input_link/input_dma/capture/pixels/rd_gray_w2 [3]),
            .CE (1'b1),
            .CK (ntclkbufg_0),
            .D (\system/input_link/input_dma/capture/pixels/rd_gray_w1 [3]),
            .SR (\CLMS_225_487/ntRSCO ));

(* PAP_BLE_DEF="B" *)    V_FFSYN /* CLMA_219_517 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/input_link/input_dma/capture/pixels/rd_gray_w2[4]/opit_0_inv/FF1/FF  (
            .Q (\system/input_link/input_dma/capture/pixels/rd_gray_w2 [4]),
            .CE (1'b1),
            .CK (ntclkbufg_0),
            .D (\system/input_link/input_dma/capture/pixels/rd_gray_w1 [4]),
            .SR (\CLMA_219_517/ntRSCO ));

(* PAP_BLE_DEF="B" *)    V_FFSYN /* CLMA_219_493 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/input_link/input_dma/capture/pixels/rd_gray_w2[5]/opit_0_inv/FF1/FF  (
            .Q (\system/input_link/input_dma/capture/pixels/rd_gray_w2 [5]),
            .CE (1'b1),
            .CK (ntclkbufg_0),
            .D (\system/input_link/input_dma/capture/pixels/rd_gray_w1 [5]),
            .SR (\CLMA_219_493/ntRSCO ));

(* PAP_BLE_DEF="D" *)    V_FFSYN /* CLMA_219_493 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/input_link/input_dma/capture/pixels/rd_gray_w2[6]/opit_0_inv/FF3/FF  (
            .Q (\system/input_link/input_dma/capture/pixels/rd_gray_w2 [6]),
            .CE (1'b1),
            .CK (ntclkbufg_0),
            .D (\system/input_link/input_dma/capture/pixels/rd_gray_w1 [6]),
            .SR (\CLMA_219_493/ntRSCO ));

(* PAP_BLE_DEF="D" *)    V_FFSYN /* CLMA_243_498 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/input_link/input_dma/capture/pixels/wr_gray[0]/opit_0_inv_L6Q_LUT6DQL5Q_perm/FF3/FF  (
            .Q (\system/input_link/input_dma/capture/pixels/wr_gray [0]),
            .CE (\CLMA_243_498/ntCE ),
            .CK (ntclkbufg_0),
            .D (\CLMA_243_498/ntQD3 ),
            .SR (\CLMA_243_498/ntRSCO ));

(* PAP_BLE_DEF="A" *)    V_FFSYN /* CLMA_243_498 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/input_link/input_dma/capture/pixels/wr_gray[1]/opit_0_inv_L6Q_LUT6DQL5Q_perm/FF0/FF  (
            .Q (\system/input_link/input_dma/capture/pixels/wr_gray [1]),
            .CE (\CLMA_243_498/ntCE ),
            .CK (ntclkbufg_0),
            .D (\CLMA_243_498/ntQD0 ),
            .SR (\CLMA_243_498/ntRSCO ));

(* PAP_BLE_DEF="B" *)    V_FFSYN /* CLMA_243_498 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/input_link/input_dma/capture/pixels/wr_gray[2]/opit_0_inv_L6Q_LUT6DQL5Q_perm/FF1/FF  (
            .Q (\system/input_link/input_dma/capture/pixels/wr_gray [2]),
            .CE (\CLMA_243_498/ntCE ),
            .CK (ntclkbufg_0),
            .D (\CLMA_243_498/ntQD1 ),
            .SR (\CLMA_243_498/ntRSCO ));

(* PAP_BLE_DEF="B" *)    V_FFSYN /* CLMA_243_498 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/input_link/input_dma/capture/pixels/wr_gray[2]/opit_0_inv_L6Q_LUT6DQL5Q_perm/FFAPP1/FF  (
            .Q (\system/input_link/input_dma/capture/pixels/wr_gray [3]),
            .CE (\CLMA_243_498/ntCE ),
            .CK (ntclkbufg_0),
            .D (\CLMA_243_498/ntQC1 ),
            .SR (\CLMA_243_498/ntRSCO ));

(* PAP_BLE_DEF="A" *)    V_FFSYN /* CLMA_231_511 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/input_link/input_dma/capture/pixels/wr_gray[4]/opit_0_inv_L6Q_LUT6DQL5Q_perm/FF0/FF  (
            .Q (\system/input_link/input_dma/capture/pixels/wr_gray [4]),
            .CE (\CLMA_243_498/ntCE ),
            .CK (ntclkbufg_0),
            .D (\CLMA_231_511/ntQD0 ),
            .SR (\CLMA_231_511/ntRSCO ));

(* PAP_BLE_DEF="B" *)    V_FFSYN /* CLMA_231_511 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/input_link/input_dma/capture/pixels/wr_gray[5]/opit_0_inv_L6Q_LUT6DQL5Q_perm/FF1/FF  (
            .Q (\system/input_link/input_dma/capture/pixels/wr_gray [5]),
            .CE (\CLMA_243_498/ntCE ),
            .CK (ntclkbufg_0),
            .D (\CLMA_231_511/ntQD1 ),
            .SR (\CLMA_231_511/ntRSCO ));

(* PAP_BLE_DEF="B" *)    V_FFSYN /* CLMA_231_511 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/input_link/input_dma/capture/pixels/wr_gray[5]/opit_0_inv_L6Q_LUT6DQL5Q_perm/FFAPP1/FF  (
            .Q (\system/input_link/input_dma/capture/pixels/wr_binary [6]),
            .CE (\CLMA_243_498/ntCE ),
            .CK (ntclkbufg_0),
            .D (\CLMA_231_511/ntQC1 ),
            .SR (\CLMA_231_511/ntRSCO ));

(* PAP_BLE_DEF="A" *)    V_FFSYN /* CLMA_231_547 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/input_link/input_dma/capture/pixels/wr_gray_r1[0]/opit_0_inv/FF0/FF  (
            .Q (\system/input_link/input_dma/capture/pixels/wr_gray_r1 [0]),
            .CE (1'b1),
            .CK (core_clk),
            .D (\system/input_link/input_dma/capture/pixels/wr_gray [0]),
            .SR (ntR1595));

(* PAP_BLE_DEF="A" *)    V_FFSYN /* CLMA_231_553 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/input_link/input_dma/capture/pixels/wr_gray_r1[1]/opit_0_inv/FF0/FF  (
            .Q (\system/input_link/input_dma/capture/pixels/wr_gray_r1 [1]),
            .CE (1'b1),
            .CK (core_clk),
            .D (\system/input_link/input_dma/capture/pixels/wr_gray [1]),
            .SR (ntR1595));

(* PAP_BLE_DEF="A" *)    V_FFSYN /* CLMA_231_444 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/input_link/input_dma/capture/pixels/wr_gray_r1[2]/opit_0_inv/FF0/FF  (
            .Q (\system/input_link/input_dma/capture/pixels/wr_gray_r1 [2]),
            .CE (1'b1),
            .CK (core_clk),
            .D (\system/input_link/input_dma/capture/pixels/wr_gray [2]),
            .SR (\CLMA_231_444/ntRSCO ));

(* PAP_BLE_DEF="C" *)    V_FFSYN /* CLMA_231_444 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/input_link/input_dma/capture/pixels/wr_gray_r1[3]/opit_0_inv/FF2/FF  (
            .Q (\system/input_link/input_dma/capture/pixels/wr_gray_r1 [3]),
            .CE (1'b1),
            .CK (core_clk),
            .D (\system/input_link/input_dma/capture/pixels/wr_gray [3]),
            .SR (\CLMA_231_444/ntRSCO ));

(* PAP_BLE_DEF="C" *)    V_FFSYN /* CLMA_231_510 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/input_link/input_dma/capture/pixels/wr_gray_r1[4]/opit_0_inv/FF2/FF  (
            .Q (\system/input_link/input_dma/capture/pixels/wr_gray_r1 [4]),
            .CE (1'b1),
            .CK (core_clk),
            .D (\system/input_link/input_dma/capture/pixels/wr_gray [4]),
            .SR (\CLMA_231_510/ntRSCO ));

(* PAP_BLE_DEF="A" *)    V_FFSYN /* CLMA_231_510 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/input_link/input_dma/capture/pixels/wr_gray_r1[5]/opit_0_inv/FF0/FF  (
            .Q (\system/input_link/input_dma/capture/pixels/wr_gray_r1 [5]),
            .CE (1'b1),
            .CK (core_clk),
            .D (\system/input_link/input_dma/capture/pixels/wr_gray [5]),
            .SR (\CLMA_231_510/ntRSCO ));

(* PAP_BLE_DEF="C" *)    V_FFSYN /* CLMA_231_553 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/input_link/input_dma/capture/pixels/wr_gray_r1[6]/opit_0_inv/FF2/FF  (
            .Q (\system/input_link/input_dma/capture/pixels/wr_gray_r1 [6]),
            .CE (1'b1),
            .CK (core_clk),
            .D (\system/input_link/input_dma/capture/pixels/wr_binary [6]),
            .SR (ntR1595));

(* PAP_BLE_DEF="B" *)    V_FFSYN /* CLMA_231_547 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/input_link/input_dma/capture/pixels/wr_gray_r2[0]/opit_0_inv/FF1/FF  (
            .Q (\system/input_link/input_dma/capture/pixels/wr_gray_r2 [0]),
            .CE (1'b1),
            .CK (core_clk),
            .D (\system/input_link/input_dma/capture/pixels/wr_gray_r1 [0]),
            .SR (ntR1595));

(* PAP_BLE_DEF="B" *)    V_FFSYN /* CLMA_231_553 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/input_link/input_dma/capture/pixels/wr_gray_r2[1]/opit_0_inv/FF1/FF  (
            .Q (\system/input_link/input_dma/capture/pixels/wr_gray_r2 [1]),
            .CE (1'b1),
            .CK (core_clk),
            .D (\system/input_link/input_dma/capture/pixels/wr_gray_r1 [1]),
            .SR (ntR1595));

(* PAP_BLE_DEF="B" *)    V_FFSYN /* CLMA_231_444 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/input_link/input_dma/capture/pixels/wr_gray_r2[2]/opit_0_inv/FF1/FF  (
            .Q (\system/input_link/input_dma/capture/pixels/wr_gray_r2 [2]),
            .CE (1'b1),
            .CK (core_clk),
            .D (\system/input_link/input_dma/capture/pixels/wr_gray_r1 [2]),
            .SR (\CLMA_231_444/ntRSCO ));

(* PAP_BLE_DEF="D" *)    V_FFSYN /* CLMA_231_444 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/input_link/input_dma/capture/pixels/wr_gray_r2[3]/opit_0_inv/FF3/FF  (
            .Q (\system/input_link/input_dma/capture/pixels/wr_gray_r2 [3]),
            .CE (1'b1),
            .CK (core_clk),
            .D (\system/input_link/input_dma/capture/pixels/wr_gray_r1 [3]),
            .SR (\CLMA_231_444/ntRSCO ));

(* PAP_BLE_DEF="D" *)    V_FFSYN /* CLMA_231_510 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/input_link/input_dma/capture/pixels/wr_gray_r2[4]/opit_0_inv/FF3/FF  (
            .Q (\system/input_link/input_dma/capture/pixels/wr_gray_r2 [4]),
            .CE (1'b1),
            .CK (core_clk),
            .D (\system/input_link/input_dma/capture/pixels/wr_gray_r1 [4]),
            .SR (\CLMA_231_510/ntRSCO ));

(* PAP_BLE_DEF="B" *)    V_FFSYN /* CLMA_231_510 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/input_link/input_dma/capture/pixels/wr_gray_r2[5]/opit_0_inv/FF1/FF  (
            .Q (\system/input_link/input_dma/capture/pixels/wr_gray_r2 [5]),
            .CE (1'b1),
            .CK (core_clk),
            .D (\system/input_link/input_dma/capture/pixels/wr_gray_r1 [5]),
            .SR (\CLMA_231_510/ntRSCO ));

(* PAP_BLE_DEF="D" *)    V_FFSYN /* CLMA_231_553 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/input_link/input_dma/capture/pixels/wr_gray_r2[6]/opit_0_inv/FF3/FF  (
            .Q (\system/input_link/input_dma/capture/pixels/wr_gray_r2 [6]),
            .CE (1'b1),
            .CK (core_clk),
            .D (\system/input_link/input_dma/capture/pixels/wr_gray_r1 [6]),
            .SR (ntR1595));
