(* PAP_BLE_DEF="A" *)    V_FFASYN /* CLMS_75_787 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \core_reset[0]/opit_0/FF0/FF  (
            .Q (core_reset[0]),
            .CE (1'b1),
            .CK (core_clk),
            .D (1'b1),
            .SR (\CLMS_75_787/ntRS ));

(* PAP_BLE_DEF="B" *)    V_FFASYN /* CLMS_75_787 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \core_reset[1]/opit_0/FF1/FF  (
            .Q (core_reset[1]),
            .CE (1'b1),
            .CK (core_clk),
            .D (core_reset[0]),
            .SR (\CLMS_75_787/ntRS ));

(* PAP_BLE_DEF="C" *)    V_FFSYN /* CLMA_303_469 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/rd_gray[0]/opit_0_inv/FF2/FF  (
            .Q (\system/display_fifo/rd_gray [0]),
            .CE (\CLMA_303_469/ntCE ),
            .CK (ntclkbufg_0),
            .D (\system/display_fifo/N134 [0]),
            .SR (\CLMA_303_469/ntRSCO ));

(* PAP_BLE_DEF="A" *)    V_FFSYN /* CLMA_303_469 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/rd_gray[1]/opit_0_inv/FF0/FF  (
            .Q (\system/display_fifo/rd_gray [1]),
            .CE (\CLMA_303_469/ntCE ),
            .CK (ntclkbufg_0),
            .D (\system/display_fifo/N134 [1]),
            .SR (\CLMA_303_469/ntRSCO ));

(* PAP_BLE_DEF="B" *)    V_FFSYN /* CLMA_303_469 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/rd_gray[2]/opit_0_inv/FF1/FF  (
            .Q (\system/display_fifo/rd_gray [2]),
            .CE (\CLMA_303_469/ntCE ),
            .CK (ntclkbufg_0),
            .D (\system/display_fifo/N134 [2]),
            .SR (\CLMA_303_469/ntRSCO ));

(* PAP_BLE_DEF="C" *)    V_FFSYN /* CLMA_303_468 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/rd_gray[3]/opit_0_inv/FFAPP2/FF  (
            .Q (\system/display_fifo/rd_gray [3]),
            .CE (\CLMA_303_469/ntCE ),
            .CK (ntclkbufg_0),
            .D (\system/display_fifo/N134 [3]),
            .SR (ntR3653));

(* PAP_BLE_DEF="B" *)    V_FFSYN /* CLMA_303_468 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/rd_gray[4]/opit_0_inv/FFAPP1/FF  (
            .Q (\system/display_fifo/rd_gray [4]),
            .CE (\CLMA_303_469/ntCE ),
            .CK (ntclkbufg_0),
            .D (\system/display_fifo/N134 [4]),
            .SR (ntR3653));

(* PAP_BLE_DEF="D" *)    V_FFSYN /* CLMA_303_468 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/rd_gray[5]/opit_0_inv/FFAPP3/FF  (
            .Q (\system/display_fifo/rd_gray [5]),
            .CE (\CLMA_303_469/ntCE ),
            .CK (ntclkbufg_0),
            .D (\system/display_fifo/N134 [5]),
            .SR (ntR3653));

(* PAP_BLE_DEF="D" *)    V_FFSYN /* CLMA_303_469 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/rd_gray[6]/opit_0_inv/FF3/FF  (
            .Q (\system/display_fifo/rd_gray [6]),
            .CE (\CLMA_303_469/ntCE ),
            .CK (ntclkbufg_0),
            .D (\system/display_fifo/N134 [6]),
            .SR (\CLMA_303_469/ntRSCO ));

(* PAP_BLE_DEF="A" *)    V_FFSYN /* CLMA_303_480 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/rd_gray[7]/opit_0_inv/FFAPP0/FF  (
            .Q (\system/display_fifo/rd_gray [7]),
            .CE (ntR1144),
            .CK (ntclkbufg_0),
            .D (\system/display_fifo/N134 [7]),
            .SR (ntR3654));

(* PAP_BLE_DEF="B" *)    V_FFSYN /* CLMA_303_480 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/rd_gray[8]/opit_0_inv/FF1/FF  (
            .Q (\system/display_fifo/rd_gray [8]),
            .CE (ntR1144),
            .CK (ntclkbufg_0),
            .D (\system/display_fifo/N134 [8]),
            .SR (ntR3654));

(* PAP_BLE_DEF="C" *)    V_FFSYN /* CLMA_303_480 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/rd_gray[9]/opit_0_inv/FF2/FF  (
            .Q (\system/display_fifo/rd_gray [9]),
            .CE (ntR1144),
            .CK (ntclkbufg_0),
            .D (\system/display_fifo/next_rd [9]),
            .SR (ntR3654));

(* PAP_BLE_DEF="A" *)    V_FFSYN /* CLMA_291_462 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/rd_gray_w1[0]/opit_0_inv/FF0/FF  (
            .Q (\system/display_fifo/rd_gray_w1 [0]),
            .CE (1'b1),
            .CK (core_clk),
            .D (\system/display_fifo/rd_gray [0]),
            .SR (ntR2823));

(* PAP_BLE_DEF="C" *)    V_FFSYN /* CLMA_291_462 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/rd_gray_w1[1]/opit_0_inv/FF2/FF  (
            .Q (\system/display_fifo/rd_gray_w1 [1]),
            .CE (1'b1),
            .CK (core_clk),
            .D (\system/display_fifo/rd_gray [1]),
            .SR (ntR2823));

(* PAP_BLE_DEF="A" *)    V_FFSYN /* CLMA_291_450 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/rd_gray_w1[2]/opit_0_inv/FF0/FF  (
            .Q (\system/display_fifo/rd_gray_w1 [2]),
            .CE (1'b1),
            .CK (core_clk),
            .D (\system/display_fifo/rd_gray [2]),
            .SR (ntR2822));

(* PAP_BLE_DEF="A" *)    V_FFSYN /* CLMA_291_504 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/rd_gray_w1[3]/opit_0_inv/FF0/FF  (
            .Q (\system/display_fifo/rd_gray_w1 [3]),
            .CE (1'b1),
            .CK (core_clk),
            .D (\system/display_fifo/rd_gray [3]),
            .SR (ntR2824));

(* PAP_BLE_DEF="A" *)    V_FFSYN /* CLMA_291_510 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/rd_gray_w1[4]/opit_0_inv/FF0/FF  (
            .Q (\system/display_fifo/rd_gray_w1 [4]),
            .CE (1'b1),
            .CK (core_clk),
            .D (\system/display_fifo/rd_gray [4]),
            .SR (ntR2825));

(* PAP_BLE_DEF="C" *)    V_FFSYN /* CLMA_291_510 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/rd_gray_w1[5]/opit_0_inv/FF2/FF  (
            .Q (\system/display_fifo/rd_gray_w1 [5]),
            .CE (1'b1),
            .CK (core_clk),
            .D (\system/display_fifo/rd_gray [5]),
            .SR (ntR2825));

(* PAP_BLE_DEF="A" *)    V_FFSYN /* CLMA_285_522 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/rd_gray_w1[6]/opit_0_inv/FF0/FF  (
            .Q (\system/display_fifo/rd_gray_w1 [6]),
            .CE (1'b1),
            .CK (core_clk),
            .D (\system/display_fifo/rd_gray [6]),
            .SR (ntR2826));

(* PAP_BLE_DEF="C" *)    V_FFSYN /* CLMA_285_522 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/rd_gray_w1[7]/opit_0_inv/FF2/FF  (
            .Q (\system/display_fifo/rd_gray_w1 [7]),
            .CE (1'b1),
            .CK (core_clk),
            .D (\system/display_fifo/rd_gray [7]),
            .SR (ntR2826));

(* PAP_BLE_DEF="A" *)    V_FFSYN /* CLMA_285_528 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/rd_gray_w1[8]/opit_0_inv/FF0/FF  (
            .Q (\system/display_fifo/rd_gray_w1 [8]),
            .CE (1'b1),
            .CK (core_clk),
            .D (\system/display_fifo/rd_gray [8]),
            .SR (ntR2826));

(* PAP_BLE_DEF="C" *)    V_FFSYN /* CLMA_285_528 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/rd_gray_w1[9]/opit_0_inv/FF2/FF  (
            .Q (\system/display_fifo/rd_gray_w1 [9]),
            .CE (1'b1),
            .CK (core_clk),
            .D (\system/display_fifo/rd_gray [9]),
            .SR (ntR2826));

(* PAP_BLE_DEF="B" *)    V_FFSYN /* CLMA_291_462 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/rd_gray_w2[0]/opit_0_inv/FF1/FF  (
            .Q (\system/display_fifo/rd_gray_w2 [0]),
            .CE (1'b1),
            .CK (core_clk),
            .D (\system/display_fifo/rd_gray_w1 [0]),
            .SR (ntR2823));

(* PAP_BLE_DEF="D" *)    V_FFSYN /* CLMA_291_462 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/rd_gray_w2[1]/opit_0_inv/FF3/FF  (
            .Q (\system/display_fifo/rd_gray_w2 [1]),
            .CE (1'b1),
            .CK (core_clk),
            .D (\system/display_fifo/rd_gray_w1 [1]),
            .SR (ntR2823));

(* PAP_BLE_DEF="B" *)    V_FFSYN /* CLMA_291_450 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/rd_gray_w2[2]/opit_0_inv/FF1/FF  (
            .Q (\system/display_fifo/rd_gray_w2 [2]),
            .CE (1'b1),
            .CK (core_clk),
            .D (\system/display_fifo/rd_gray_w1 [2]),
            .SR (ntR2822));

(* PAP_BLE_DEF="B" *)    V_FFSYN /* CLMA_291_504 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/rd_gray_w2[3]/opit_0_inv/FF1/FF  (
            .Q (\system/display_fifo/rd_gray_w2 [3]),
            .CE (1'b1),
            .CK (core_clk),
            .D (\system/display_fifo/rd_gray_w1 [3]),
            .SR (ntR2824));

(* PAP_BLE_DEF="B" *)    V_FFSYN /* CLMA_291_510 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/rd_gray_w2[4]/opit_0_inv/FF1/FF  (
            .Q (\system/display_fifo/rd_gray_w2 [4]),
            .CE (1'b1),
            .CK (core_clk),
            .D (\system/display_fifo/rd_gray_w1 [4]),
            .SR (ntR2825));

(* PAP_BLE_DEF="D" *)    V_FFSYN /* CLMA_291_510 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/rd_gray_w2[5]/opit_0_inv/FF3/FF  (
            .Q (\system/display_fifo/rd_gray_w2 [5]),
            .CE (1'b1),
            .CK (core_clk),
            .D (\system/display_fifo/rd_gray_w1 [5]),
            .SR (ntR2825));

(* PAP_BLE_DEF="B" *)    V_FFSYN /* CLMA_285_522 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/rd_gray_w2[6]/opit_0_inv/FF1/FF  (
            .Q (\system/display_fifo/rd_gray_w2 [6]),
            .CE (1'b1),
            .CK (core_clk),
            .D (\system/display_fifo/rd_gray_w1 [6]),
            .SR (ntR2826));

(* PAP_BLE_DEF="D" *)    V_FFSYN /* CLMA_285_522 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/rd_gray_w2[7]/opit_0_inv/FF3/FF  (
            .Q (\system/display_fifo/rd_gray_w2 [7]),
            .CE (1'b1),
            .CK (core_clk),
            .D (\system/display_fifo/rd_gray_w1 [7]),
            .SR (ntR2826));

(* PAP_BLE_DEF="B" *)    V_FFSYN /* CLMA_285_528 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/rd_gray_w2[8]/opit_0_inv/FF1/FF  (
            .Q (\system/display_fifo/rd_gray_w2 [8]),
            .CE (1'b1),
            .CK (core_clk),
            .D (\system/display_fifo/rd_gray_w1 [8]),
            .SR (ntR2826));

(* PAP_BLE_DEF="D" *)    V_FFSYN /* CLMA_285_528 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/rd_gray_w2[9]/opit_0_inv/FF3/FF  (
            .Q (\system/display_fifo/rd_gray_w2 [9]),
            .CE (1'b1),
            .CK (core_clk),
            .D (\system/display_fifo/rd_gray_w1 [9]),
            .SR (ntR2826));

(* PAP_BLE_DEF="B" *)    V_FFASYN /* CLMA_189_798 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/rd_reset_sync[0]/opit_0/FFAPP1/FF  (
            .Q (\system/display_fifo/rd_reset_sync [0]),
            .CE (1'b1),
            .CK (ntclkbufg_0),
            .D (1'b1),
            .SR (\CLMS_75_787/ntRS ));

(* PAP_BLE_DEF="C" *)    V_FFASYN /* CLMA_189_798 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/rd_reset_sync[1]/opit_0/FFAPP2/FF  (
            .Q (\system/display_fifo/rd_reset_sync [1]),
            .CE (1'b1),
            .CK (ntclkbufg_0),
            .D (\system/display_fifo/rd_reset_sync [0]),
            .SR (\CLMS_75_787/ntRS ));

(* PAP_BLE_DEF="D" *)    V_FFSYN /* CLMA_291_498 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/wr_gray[0]/opit_0_inv_L5Q_perm/FFAPP3/FF  (
            .Q (\system/display_fifo/wr_gray [0]),
            .CE (\CLMS_285_517/ntCE ),
            .CK (core_clk),
            .D (\CLMA_291_498/ntQC3 ),
            .SR (ntR2824));

(* PAP_BLE_DEF="A" *)    V_FFSYN /* CLMA_291_498 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/wr_gray[1]/opit_0_inv/FF0/FF  (
            .Q (\system/display_fifo/wr_gray [1]),
            .CE (\CLMS_285_517/ntCE ),
            .CK (core_clk),
            .D (\system/display_fifo/N112 [1]),
            .SR (ntR2824));

(* PAP_BLE_DEF="B" *)    V_FFSYN /* CLMA_291_498 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/wr_gray[2]/opit_0_inv/FF1/FF  (
            .Q (\system/display_fifo/wr_gray [2]),
            .CE (\CLMS_285_517/ntCE ),
            .CK (core_clk),
            .D (\system/display_fifo/N112 [2]),
            .SR (ntR2824));

(* PAP_BLE_DEF="B" *)    V_FFSYN /* CLMS_285_517 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/wr_gray[3]/opit_0_inv/FF1/FF  (
            .Q (\system/display_fifo/wr_gray [3]),
            .CE (\CLMS_285_517/ntCE ),
            .CK (core_clk),
            .D (\system/display_fifo/N112 [3]),
            .SR (ntR2831));

(* PAP_BLE_DEF="A" *)    V_FFSYN /* CLMS_285_517 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/wr_gray[4]/opit_0_inv/FF0/FF  (
            .Q (\system/display_fifo/wr_gray [4]),
            .CE (\CLMS_285_517/ntCE ),
            .CK (core_clk),
            .D (\system/display_fifo/N112 [4]),
            .SR (ntR2831));

(* PAP_BLE_DEF="C" *)    V_FFSYN /* CLMS_285_517 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/wr_gray[5]/opit_0_inv/FF2/FF  (
            .Q (\system/display_fifo/wr_gray [5]),
            .CE (\CLMS_285_517/ntCE ),
            .CK (core_clk),
            .D (\system/display_fifo/N112 [5]),
            .SR (ntR2831));

(* PAP_BLE_DEF="D" *)    V_FFSYN /* CLMS_285_517 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/wr_gray[6]/opit_0_inv/FF3/FF  (
            .Q (\system/display_fifo/wr_gray [6]),
            .CE (\CLMS_285_517/ntCE ),
            .CK (core_clk),
            .D (\system/display_fifo/N112 [6]),
            .SR (ntR2831));

(* PAP_BLE_DEF="C" *)    V_FFSYN /* CLMA_291_498 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/wr_gray[7]/opit_0_inv/FF2/FF  (
            .Q (\system/display_fifo/wr_gray [7]),
            .CE (\CLMS_285_517/ntCE ),
            .CK (core_clk),
            .D (\system/display_fifo/N112 [7]),
            .SR (ntR2824));

(* PAP_BLE_DEF="D" *)    V_FFSYN /* CLMA_291_498 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/wr_gray[8]/opit_0_inv/FF3/FF  (
            .Q (\system/display_fifo/wr_gray [8]),
            .CE (\CLMS_285_517/ntCE ),
            .CK (core_clk),
            .D (\system/display_fifo/N112 [8]),
            .SR (ntR2824));

(* PAP_BLE_DEF="C" *)    V_FFSYN /* CLMA_291_498 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/wr_gray[9]/opit_0_inv_L6Q_LUT6DL5Q_perm/FFAPP2/FF  (
            .Q (\system/display_fifo/wr_gray [9]),
            .CE (\CLMS_285_517/ntCE ),
            .CK (core_clk),
            .D (\CLMA_291_498/ntQC2 ),
            .SR (ntR2824));

(* PAP_BLE_DEF="A" *)    V_FFSYN /* CLMA_291_492 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/wr_gray_r1[0]/opit_0_inv/FF0/FF  (
            .Q (\system/display_fifo/wr_gray_r1 [0]),
            .CE (1'b1),
            .CK (ntclkbufg_0),
            .D (\system/display_fifo/wr_gray [0]),
            .SR (\CLMA_291_492/ntRSCO ));

(* PAP_BLE_DEF="A" *)    V_FFSYN /* CLMA_291_480 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/wr_gray_r1[1]/opit_0_inv/FF0/FF  (
            .Q (\system/display_fifo/wr_gray_r1 [1]),
            .CE (1'b1),
            .CK (ntclkbufg_0),
            .D (\system/display_fifo/wr_gray [1]),
            .SR (\CLMA_291_480/ntRSCO ));

(* PAP_BLE_DEF="C" *)    V_FFSYN /* CLMA_291_492 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/wr_gray_r1[2]/opit_0_inv/FF2/FF  (
            .Q (\system/display_fifo/wr_gray_r1 [2]),
            .CE (1'b1),
            .CK (ntclkbufg_0),
            .D (\system/display_fifo/wr_gray [2]),
            .SR (\CLMA_291_492/ntRSCO ));

(* PAP_BLE_DEF="A" *)    V_FFSYN /* CLMS_291_511 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/wr_gray_r1[3]/opit_0_inv/FF0/FF  (
            .Q (\system/display_fifo/wr_gray_r1 [3]),
            .CE (1'b1),
            .CK (ntclkbufg_0),
            .D (\system/display_fifo/wr_gray [3]),
            .SR (\CLMS_291_511/ntRSCO ));

(* PAP_BLE_DEF="C" *)    V_FFSYN /* CLMS_291_511 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/wr_gray_r1[4]/opit_0_inv/FF2/FF  (
            .Q (\system/display_fifo/wr_gray_r1 [4]),
            .CE (1'b1),
            .CK (ntclkbufg_0),
            .D (\system/display_fifo/wr_gray [4]),
            .SR (\CLMS_291_511/ntRSCO ));

(* PAP_BLE_DEF="A" *)    V_FFSYN /* CLMS_291_493 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/wr_gray_r1[5]/opit_0_inv/FF0/FF  (
            .Q (\system/display_fifo/wr_gray_r1 [5]),
            .CE (1'b1),
            .CK (ntclkbufg_0),
            .D (\system/display_fifo/wr_gray [5]),
            .SR (\CLMS_291_493/ntRSCO ));

(* PAP_BLE_DEF="C" *)    V_FFSYN /* CLMS_285_529 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/wr_gray_r1[6]/opit_0_inv/FF2/FF  (
            .Q (\system/display_fifo/wr_gray_r1 [6]),
            .CE (1'b1),
            .CK (ntclkbufg_0),
            .D (\system/display_fifo/wr_gray [6]),
            .SR (\CLMS_285_529/ntRSCO ));

(* PAP_BLE_DEF="A" *)    V_FFSYN /* CLMS_285_511 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/wr_gray_r1[7]/opit_0_inv/FF0/FF  (
            .Q (\system/display_fifo/wr_gray_r1 [7]),
            .CE (1'b1),
            .CK (ntclkbufg_0),
            .D (\system/display_fifo/wr_gray [7]),
            .SR (\CLMS_285_511/ntRSCO ));

(* PAP_BLE_DEF="C" *)    V_FFSYN /* CLMS_285_511 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/wr_gray_r1[8]/opit_0_inv/FF2/FF  (
            .Q (\system/display_fifo/wr_gray_r1 [8]),
            .CE (1'b1),
            .CK (ntclkbufg_0),
            .D (\system/display_fifo/wr_gray [8]),
            .SR (\CLMS_285_511/ntRSCO ));

(* PAP_BLE_DEF="A" *)    V_FFSYN /* CLMS_285_529 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/wr_gray_r1[9]/opit_0_inv/FF0/FF  (
            .Q (\system/display_fifo/wr_gray_r1 [9]),
            .CE (1'b1),
            .CK (ntclkbufg_0),
            .D (\system/display_fifo/wr_gray [9]),
            .SR (\CLMS_285_529/ntRSCO ));

(* PAP_BLE_DEF="B" *)    V_FFSYN /* CLMA_291_492 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/wr_gray_r2[0]/opit_0_inv/FF1/FF  (
            .Q (\system/display_fifo/wr_gray_r2 [0]),
            .CE (1'b1),
            .CK (ntclkbufg_0),
            .D (\system/display_fifo/wr_gray_r1 [0]),
            .SR (\CLMA_291_492/ntRSCO ));

(* PAP_BLE_DEF="B" *)    V_FFSYN /* CLMA_291_480 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/wr_gray_r2[1]/opit_0_inv/FF1/FF  (
            .Q (\system/display_fifo/wr_gray_r2 [1]),
            .CE (1'b1),
            .CK (ntclkbufg_0),
            .D (\system/display_fifo/wr_gray_r1 [1]),
            .SR (\CLMA_291_480/ntRSCO ));

(* PAP_BLE_DEF="D" *)    V_FFSYN /* CLMA_291_492 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/wr_gray_r2[2]/opit_0_inv/FF3/FF  (
            .Q (\system/display_fifo/wr_gray_r2 [2]),
            .CE (1'b1),
            .CK (ntclkbufg_0),
            .D (\system/display_fifo/wr_gray_r1 [2]),
            .SR (\CLMA_291_492/ntRSCO ));

(* PAP_BLE_DEF="B" *)    V_FFSYN /* CLMS_291_511 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/wr_gray_r2[3]/opit_0_inv/FF1/FF  (
            .Q (\system/display_fifo/wr_gray_r2 [3]),
            .CE (1'b1),
            .CK (ntclkbufg_0),
            .D (\system/display_fifo/wr_gray_r1 [3]),
            .SR (\CLMS_291_511/ntRSCO ));

(* PAP_BLE_DEF="D" *)    V_FFSYN /* CLMS_291_511 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/wr_gray_r2[4]/opit_0_inv/FF3/FF  (
            .Q (\system/display_fifo/wr_gray_r2 [4]),
            .CE (1'b1),
            .CK (ntclkbufg_0),
            .D (\system/display_fifo/wr_gray_r1 [4]),
            .SR (\CLMS_291_511/ntRSCO ));

(* PAP_BLE_DEF="B" *)    V_FFSYN /* CLMS_291_493 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/wr_gray_r2[5]/opit_0_inv/FF1/FF  (
            .Q (\system/display_fifo/wr_gray_r2 [5]),
            .CE (1'b1),
            .CK (ntclkbufg_0),
            .D (\system/display_fifo/wr_gray_r1 [5]),
            .SR (\CLMS_291_493/ntRSCO ));

(* PAP_BLE_DEF="D" *)    V_FFSYN /* CLMS_285_529 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/wr_gray_r2[6]/opit_0_inv/FF3/FF  (
            .Q (\system/display_fifo/wr_gray_r2 [6]),
            .CE (1'b1),
            .CK (ntclkbufg_0),
            .D (\system/display_fifo/wr_gray_r1 [6]),
            .SR (\CLMS_285_529/ntRSCO ));

(* PAP_BLE_DEF="B" *)    V_FFSYN /* CLMS_285_511 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/wr_gray_r2[7]/opit_0_inv/FF1/FF  (
            .Q (\system/display_fifo/wr_gray_r2 [7]),
            .CE (1'b1),
            .CK (ntclkbufg_0),
            .D (\system/display_fifo/wr_gray_r1 [7]),
            .SR (\CLMS_285_511/ntRSCO ));

(* PAP_BLE_DEF="D" *)    V_FFSYN /* CLMS_285_511 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/wr_gray_r2[8]/opit_0_inv/FF3/FF  (
            .Q (\system/display_fifo/wr_gray_r2 [8]),
            .CE (1'b1),
            .CK (ntclkbufg_0),
            .D (\system/display_fifo/wr_gray_r1 [8]),
            .SR (\CLMS_285_511/ntRSCO ));

(* PAP_BLE_DEF="B" *)    V_FFSYN /* CLMS_285_529 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/display_fifo/wr_gray_r2[9]/opit_0_inv/FF1/FF  (
            .Q (\system/display_fifo/wr_gray_r2 [9]),
            .CE (1'b1),
            .CK (ntclkbufg_0),
            .D (\system/display_fifo/wr_gray_r1 [9]),
            .SR (\CLMS_285_529/ntRSCO ));

(* PAP_BLE_DEF="B" *)    V_FFSYN /* CLMA_171_882 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/input_link/input_dma/capture/pixels/rd_gray[0]/opit_0_inv/FF1/FF  (
            .Q (\system/input_link/input_dma/capture/pixels/rd_gray [0]),
            .CE (\CLMS_171_889/ntCE ),
            .CK (core_clk),
            .D (\system/input_link/input_dma/capture/pixels/N110 [0]),
            .SR (\CLMA_171_882/ntRSCO ));

(* PAP_BLE_DEF="D" *)    V_FFSYN /* CLMS_171_889 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/input_link/input_dma/capture/pixels/rd_gray[1]/opit_0_inv/FF3/FF  (
            .Q (\system/input_link/input_dma/capture/pixels/rd_gray [1]),
            .CE (\CLMS_171_889/ntCE ),
            .CK (core_clk),
            .D (\system/input_link/input_dma/capture/pixels/N110 [1]),
            .SR (\CLMS_171_889/ntRSCO ));

(* PAP_BLE_DEF="A" *)    V_FFSYN /* CLMA_171_882 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/input_link/input_dma/capture/pixels/rd_gray[2]/opit_0_inv/FF0/FF  (
            .Q (\system/input_link/input_dma/capture/pixels/rd_gray [2]),
            .CE (\CLMS_171_889/ntCE ),
            .CK (core_clk),
            .D (\system/input_link/input_dma/capture/pixels/N110 [2]),
            .SR (\CLMA_171_882/ntRSCO ));

(* PAP_BLE_DEF="C" *)    V_FFSYN /* CLMA_171_882 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/input_link/input_dma/capture/pixels/rd_gray[3]/opit_0_inv/FF2/FF  (
            .Q (\system/input_link/input_dma/capture/pixels/rd_gray [3]),
            .CE (\CLMS_171_889/ntCE ),
            .CK (core_clk),
            .D (\system/input_link/input_dma/capture/pixels/N110 [3]),
            .SR (\CLMA_171_882/ntRSCO ));

(* PAP_BLE_DEF="B" *)    V_FFSYN /* CLMS_171_889 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/input_link/input_dma/capture/pixels/rd_gray[4]/opit_0_inv/FF1/FF  (
            .Q (\system/input_link/input_dma/capture/pixels/rd_gray [4]),
            .CE (\CLMS_171_889/ntCE ),
            .CK (core_clk),
            .D (\system/input_link/input_dma/capture/pixels/N110 [4]),
            .SR (\CLMS_171_889/ntRSCO ));

(* PAP_BLE_DEF="C" *)    V_FFSYN /* CLMS_171_889 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/input_link/input_dma/capture/pixels/rd_gray[5]/opit_0_inv/FF2/FF  (
            .Q (\system/input_link/input_dma/capture/pixels/rd_gray [5]),
            .CE (\CLMS_171_889/ntCE ),
            .CK (core_clk),
            .D (\system/input_link/input_dma/capture/pixels/N110 [5]),
            .SR (\CLMS_171_889/ntRSCO ));

(* PAP_BLE_DEF="D" *)    V_FFSYN /* CLMA_171_882 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/input_link/input_dma/capture/pixels/rd_gray[6]/opit_0_inv/FF3/FF  (
            .Q (\system/input_link/input_dma/capture/pixels/rd_gray [6]),
            .CE (\CLMS_171_889/ntCE ),
            .CK (core_clk),
            .D (\system/input_link/input_dma/capture/pixels/next_rd [6]),
            .SR (\CLMA_171_882/ntRSCO ));

(* PAP_BLE_DEF="A" *)    V_FFSYN /* CLMA_165_895 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/input_link/input_dma/capture/pixels/rd_gray_w1[0]/opit_0_inv/FF0/FF  (
            .Q (\system/input_link/input_dma/capture/pixels/rd_gray_w1 [0]),
            .CE (1'b1),
            .CK (ntclkbufg_0),
            .D (\system/input_link/input_dma/capture/pixels/rd_gray [0]),
            .SR (\CLMA_165_895/ntRSCO ));

(* PAP_BLE_DEF="A" *)    V_FFSYN /* CLMA_165_894 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/input_link/input_dma/capture/pixels/rd_gray_w1[1]/opit_0_inv/FF0/FF  (
            .Q (\system/input_link/input_dma/capture/pixels/rd_gray_w1 [1]),
            .CE (1'b1),
            .CK (ntclkbufg_0),
            .D (\system/input_link/input_dma/capture/pixels/rd_gray [1]),
            .SR (\CLMA_165_894/ntRSCO ));

(* PAP_BLE_DEF="A" *)    V_FFSYN /* CLMA_165_883 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/input_link/input_dma/capture/pixels/rd_gray_w1[2]/opit_0_inv/FF0/FF  (
            .Q (\system/input_link/input_dma/capture/pixels/rd_gray_w1 [2]),
            .CE (1'b1),
            .CK (ntclkbufg_0),
            .D (\system/input_link/input_dma/capture/pixels/rd_gray [2]),
            .SR (ntR1540));

(* PAP_BLE_DEF="C" *)    V_FFSYN /* CLMA_165_883 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/input_link/input_dma/capture/pixels/rd_gray_w1[3]/opit_0_inv/FF2/FF  (
            .Q (\system/input_link/input_dma/capture/pixels/rd_gray_w1 [3]),
            .CE (1'b1),
            .CK (ntclkbufg_0),
            .D (\system/input_link/input_dma/capture/pixels/rd_gray [3]),
            .SR (ntR1540));

(* PAP_BLE_DEF="A" *)    V_FFSYN /* CLMA_165_877 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/input_link/input_dma/capture/pixels/rd_gray_w1[4]/opit_0_inv/FF0/FF  (
            .Q (\system/input_link/input_dma/capture/pixels/rd_gray_w1 [4]),
            .CE (1'b1),
            .CK (ntclkbufg_0),
            .D (\system/input_link/input_dma/capture/pixels/rd_gray [4]),
            .SR (ntR1540));

(* PAP_BLE_DEF="C" *)    V_FFSYN /* CLMA_165_877 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/input_link/input_dma/capture/pixels/rd_gray_w1[5]/opit_0_inv/FF2/FF  (
            .Q (\system/input_link/input_dma/capture/pixels/rd_gray_w1 [5]),
            .CE (1'b1),
            .CK (ntclkbufg_0),
            .D (\system/input_link/input_dma/capture/pixels/rd_gray [5]),
            .SR (ntR1540));

(* PAP_BLE_DEF="C" *)    V_FFSYN /* CLMA_165_895 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/input_link/input_dma/capture/pixels/rd_gray_w1[6]/opit_0_inv/FF2/FF  (
            .Q (\system/input_link/input_dma/capture/pixels/rd_gray_w1 [6]),
            .CE (1'b1),
            .CK (ntclkbufg_0),
            .D (\system/input_link/input_dma/capture/pixels/rd_gray [6]),
            .SR (\CLMA_165_895/ntRSCO ));

(* PAP_BLE_DEF="B" *)    V_FFSYN /* CLMA_165_895 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/input_link/input_dma/capture/pixels/rd_gray_w2[0]/opit_0_inv/FF1/FF  (
            .Q (\system/input_link/input_dma/capture/pixels/rd_gray_w2 [0]),
            .CE (1'b1),
            .CK (ntclkbufg_0),
            .D (\system/input_link/input_dma/capture/pixels/rd_gray_w1 [0]),
            .SR (\CLMA_165_895/ntRSCO ));

(* PAP_BLE_DEF="B" *)    V_FFSYN /* CLMA_165_894 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/input_link/input_dma/capture/pixels/rd_gray_w2[1]/opit_0_inv/FF1/FF  (
            .Q (\system/input_link/input_dma/capture/pixels/rd_gray_w2 [1]),
            .CE (1'b1),
            .CK (ntclkbufg_0),
            .D (\system/input_link/input_dma/capture/pixels/rd_gray_w1 [1]),
            .SR (\CLMA_165_894/ntRSCO ));

(* PAP_BLE_DEF="B" *)    V_FFSYN /* CLMA_165_883 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/input_link/input_dma/capture/pixels/rd_gray_w2[2]/opit_0_inv/FF1/FF  (
            .Q (\system/input_link/input_dma/capture/pixels/rd_gray_w2 [2]),
            .CE (1'b1),
            .CK (ntclkbufg_0),
            .D (\system/input_link/input_dma/capture/pixels/rd_gray_w1 [2]),
            .SR (ntR1540));

(* PAP_BLE_DEF="D" *)    V_FFSYN /* CLMA_165_883 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/input_link/input_dma/capture/pixels/rd_gray_w2[3]/opit_0_inv/FF3/FF  (
            .Q (\system/input_link/input_dma/capture/pixels/rd_gray_w2 [3]),
            .CE (1'b1),
            .CK (ntclkbufg_0),
            .D (\system/input_link/input_dma/capture/pixels/rd_gray_w1 [3]),
            .SR (ntR1540));

(* PAP_BLE_DEF="B" *)    V_FFSYN /* CLMA_165_877 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/input_link/input_dma/capture/pixels/rd_gray_w2[4]/opit_0_inv/FF1/FF  (
            .Q (\system/input_link/input_dma/capture/pixels/rd_gray_w2 [4]),
            .CE (1'b1),
            .CK (ntclkbufg_0),
            .D (\system/input_link/input_dma/capture/pixels/rd_gray_w1 [4]),
            .SR (ntR1540));

(* PAP_BLE_DEF="D" *)    V_FFSYN /* CLMA_165_877 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/input_link/input_dma/capture/pixels/rd_gray_w2[5]/opit_0_inv/FF3/FF  (
            .Q (\system/input_link/input_dma/capture/pixels/rd_gray_w2 [5]),
            .CE (1'b1),
            .CK (ntclkbufg_0),
            .D (\system/input_link/input_dma/capture/pixels/rd_gray_w1 [5]),
            .SR (ntR1540));

(* PAP_BLE_DEF="D" *)    V_FFSYN /* CLMA_165_895 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/input_link/input_dma/capture/pixels/rd_gray_w2[6]/opit_0_inv/FF3/FF  (
            .Q (\system/input_link/input_dma/capture/pixels/rd_gray_w2 [6]),
            .CE (1'b1),
            .CK (ntclkbufg_0),
            .D (\system/input_link/input_dma/capture/pixels/rd_gray_w1 [6]),
            .SR (\CLMA_165_895/ntRSCO ));

(* PAP_BLE_DEF="B" *)    V_FFSYN /* CLMA_171_894 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/input_link/input_dma/capture/pixels/wr_gray[0]/opit_0_inv/FF1/FF  (
            .Q (\system/input_link/input_dma/capture/pixels/wr_gray [0]),
            .CE (\CLMS_171_895/ntCE ),
            .CK (ntclkbufg_0),
            .D (\system/input_link/input_dma/capture/pixels/N88 [0]),
            .SR (\CLMA_171_894/ntRSCO ));

(* PAP_BLE_DEF="A" *)    V_FFSYN /* CLMA_171_894 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/input_link/input_dma/capture/pixels/wr_gray[1]/opit_0_inv/FF0/FF  (
            .Q (\system/input_link/input_dma/capture/pixels/wr_gray [1]),
            .CE (\CLMS_171_895/ntCE ),
            .CK (ntclkbufg_0),
            .D (\system/input_link/input_dma/capture/pixels/N88 [1]),
            .SR (\CLMA_171_894/ntRSCO ));

(* PAP_BLE_DEF="D" *)    V_FFSYN /* CLMA_171_894 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/input_link/input_dma/capture/pixels/wr_gray[2]/opit_0_inv/FF3/FF  (
            .Q (\system/input_link/input_dma/capture/pixels/wr_gray [2]),
            .CE (\CLMS_171_895/ntCE ),
            .CK (ntclkbufg_0),
            .D (\system/input_link/input_dma/capture/pixels/N88 [2]),
            .SR (\CLMA_171_894/ntRSCO ));

(* PAP_BLE_DEF="C" *)    V_FFSYN /* CLMA_171_894 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/input_link/input_dma/capture/pixels/wr_gray[3]/opit_0_inv/FF2/FF  (
            .Q (\system/input_link/input_dma/capture/pixels/wr_gray [3]),
            .CE (\CLMS_171_895/ntCE ),
            .CK (ntclkbufg_0),
            .D (\system/input_link/input_dma/capture/pixels/N88 [3]),
            .SR (\CLMA_171_894/ntRSCO ));

(* PAP_BLE_DEF="B" *)    V_FFSYN /* CLMS_171_895 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/input_link/input_dma/capture/pixels/wr_gray[4]/opit_0_inv/FF1/FF  (
            .Q (\system/input_link/input_dma/capture/pixels/wr_gray [4]),
            .CE (\CLMS_171_895/ntCE ),
            .CK (ntclkbufg_0),
            .D (\system/input_link/input_dma/capture/pixels/N88 [4]),
            .SR (\CLMS_171_895/ntRSCO ));

(* PAP_BLE_DEF="C" *)    V_FFSYN /* CLMS_171_895 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/input_link/input_dma/capture/pixels/wr_gray[5]/opit_0_inv/FF2/FF  (
            .Q (\system/input_link/input_dma/capture/pixels/wr_gray [5]),
            .CE (\CLMS_171_895/ntCE ),
            .CK (ntclkbufg_0),
            .D (\system/input_link/input_dma/capture/pixels/N88 [5]),
            .SR (\CLMS_171_895/ntRSCO ));

(* PAP_BLE_DEF="D" *)    V_FFSYN /* CLMS_171_895 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/input_link/input_dma/capture/pixels/wr_gray[6]/opit_0_inv/FF3/FF  (
            .Q (\system/input_link/input_dma/capture/pixels/wr_gray [6]),
            .CE (\CLMS_171_895/ntCE ),
            .CK (ntclkbufg_0),
            .D (\system/input_link/input_dma/capture/pixels/next_wr [6]),
            .SR (\CLMS_171_895/ntRSCO ));

(* PAP_BLE_DEF="A" *)    V_FFSYN /* CLMA_165_888 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/input_link/input_dma/capture/pixels/wr_gray_r1[0]/opit_0_inv/FF0/FF  (
            .Q (\system/input_link/input_dma/capture/pixels/wr_gray_r1 [0]),
            .CE (1'b1),
            .CK (core_clk),
            .D (\system/input_link/input_dma/capture/pixels/wr_gray [0]),
            .SR (ntR2837));

(* PAP_BLE_DEF="C" *)    V_FFSYN /* CLMA_165_888 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/input_link/input_dma/capture/pixels/wr_gray_r1[1]/opit_0_inv/FF2/FF  (
            .Q (\system/input_link/input_dma/capture/pixels/wr_gray_r1 [1]),
            .CE (1'b1),
            .CK (core_clk),
            .D (\system/input_link/input_dma/capture/pixels/wr_gray [1]),
            .SR (ntR2837));

(* PAP_BLE_DEF="A" *)    V_FFSYN /* CLMA_165_882 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/input_link/input_dma/capture/pixels/wr_gray_r1[2]/opit_0_inv/FF0/FF  (
            .Q (\system/input_link/input_dma/capture/pixels/wr_gray_r1 [2]),
            .CE (1'b1),
            .CK (core_clk),
            .D (\system/input_link/input_dma/capture/pixels/wr_gray [2]),
            .SR (ntR2837));

(* PAP_BLE_DEF="C" *)    V_FFSYN /* CLMA_165_882 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/input_link/input_dma/capture/pixels/wr_gray_r1[3]/opit_0_inv/FF2/FF  (
            .Q (\system/input_link/input_dma/capture/pixels/wr_gray_r1 [3]),
            .CE (1'b1),
            .CK (core_clk),
            .D (\system/input_link/input_dma/capture/pixels/wr_gray [3]),
            .SR (ntR2837));

(* PAP_BLE_DEF="A" *)    V_FFSYN /* CLMA_165_889 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/input_link/input_dma/capture/pixels/wr_gray_r1[4]/opit_0_inv/FF0/FF  (
            .Q (\system/input_link/input_dma/capture/pixels/wr_gray_r1 [4]),
            .CE (1'b1),
            .CK (core_clk),
            .D (\system/input_link/input_dma/capture/pixels/wr_gray [4]),
            .SR (\CLMA_165_889/ntRSCO ));

(* PAP_BLE_DEF="C" *)    V_FFSYN /* CLMA_165_889 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/input_link/input_dma/capture/pixels/wr_gray_r1[5]/opit_0_inv/FF2/FF  (
            .Q (\system/input_link/input_dma/capture/pixels/wr_gray_r1 [5]),
            .CE (1'b1),
            .CK (core_clk),
            .D (\system/input_link/input_dma/capture/pixels/wr_gray [5]),
            .SR (\CLMA_165_889/ntRSCO ));

(* PAP_BLE_DEF="A" *)    V_FFSYN /* CLMA_171_906 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/input_link/input_dma/capture/pixels/wr_gray_r1[6]/opit_0_inv/FF0/FF  (
            .Q (\system/input_link/input_dma/capture/pixels/wr_gray_r1 [6]),
            .CE (1'b1),
            .CK (core_clk),
            .D (\system/input_link/input_dma/capture/pixels/wr_gray [6]),
            .SR (\CLMA_171_906/ntRSCO ));

(* PAP_BLE_DEF="B" *)    V_FFSYN /* CLMA_165_888 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/input_link/input_dma/capture/pixels/wr_gray_r2[0]/opit_0_inv/FF1/FF  (
            .Q (\system/input_link/input_dma/capture/pixels/wr_gray_r2 [0]),
            .CE (1'b1),
            .CK (core_clk),
            .D (\system/input_link/input_dma/capture/pixels/wr_gray_r1 [0]),
            .SR (ntR2837));

(* PAP_BLE_DEF="D" *)    V_FFSYN /* CLMA_165_888 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/input_link/input_dma/capture/pixels/wr_gray_r2[1]/opit_0_inv/FF3/FF  (
            .Q (\system/input_link/input_dma/capture/pixels/wr_gray_r2 [1]),
            .CE (1'b1),
            .CK (core_clk),
            .D (\system/input_link/input_dma/capture/pixels/wr_gray_r1 [1]),
            .SR (ntR2837));

(* PAP_BLE_DEF="B" *)    V_FFSYN /* CLMA_165_882 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/input_link/input_dma/capture/pixels/wr_gray_r2[2]/opit_0_inv/FF1/FF  (
            .Q (\system/input_link/input_dma/capture/pixels/wr_gray_r2 [2]),
            .CE (1'b1),
            .CK (core_clk),
            .D (\system/input_link/input_dma/capture/pixels/wr_gray_r1 [2]),
            .SR (ntR2837));

(* PAP_BLE_DEF="D" *)    V_FFSYN /* CLMA_165_882 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/input_link/input_dma/capture/pixels/wr_gray_r2[3]/opit_0_inv/FF3/FF  (
            .Q (\system/input_link/input_dma/capture/pixels/wr_gray_r2 [3]),
            .CE (1'b1),
            .CK (core_clk),
            .D (\system/input_link/input_dma/capture/pixels/wr_gray_r1 [3]),
            .SR (ntR2837));

(* PAP_BLE_DEF="B" *)    V_FFSYN /* CLMA_165_889 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/input_link/input_dma/capture/pixels/wr_gray_r2[4]/opit_0_inv/FF1/FF  (
            .Q (\system/input_link/input_dma/capture/pixels/wr_gray_r2 [4]),
            .CE (1'b1),
            .CK (core_clk),
            .D (\system/input_link/input_dma/capture/pixels/wr_gray_r1 [4]),
            .SR (\CLMA_165_889/ntRSCO ));

(* PAP_BLE_DEF="D" *)    V_FFSYN /* CLMA_165_889 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/input_link/input_dma/capture/pixels/wr_gray_r2[5]/opit_0_inv/FF3/FF  (
            .Q (\system/input_link/input_dma/capture/pixels/wr_gray_r2 [5]),
            .CE (1'b1),
            .CK (core_clk),
            .D (\system/input_link/input_dma/capture/pixels/wr_gray_r1 [5]),
            .SR (\CLMA_165_889/ntRSCO ));

(* PAP_BLE_DEF="B" *)    V_FFSYN /* CLMA_171_906 */ #(
            .GRS_EN("TRUE"),
            .SET_RESET("RESET"),
            .LRS_EN("TRUE"),
            .INIT(1'b0))
        \system/input_link/input_dma/capture/pixels/wr_gray_r2[6]/opit_0_inv/FF1/FF  (
            .Q (\system/input_link/input_dma/capture/pixels/wr_gray_r2 [6]),
            .CE (1'b1),
            .CK (core_clk),
            .D (\system/input_link/input_dma/capture/pixels/wr_gray_r1 [6]),
            .SR (\CLMA_171_906/ntRSCO ));
