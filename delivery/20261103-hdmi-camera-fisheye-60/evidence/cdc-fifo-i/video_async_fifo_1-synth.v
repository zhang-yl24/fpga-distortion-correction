module video_async_fifo_1
(
    input [255:0] wr_data,
    input [1:0] wr_reset_sync,
    input N107,
    input \core_reset[1]_inv_1 ,
    input nt_pixclk_in,
    input rd_en,
    input rst_n_inv,
    input wr_clk,
    output [255:0] rd_data,
    output [1:0] rd_reset_sync,
    output [9:0] wr_used,
    output rd_ready,
    output \rd_reset_sync[1]_inv_1 ,
    output rd_valid,
    output wr_ready
);
    wire [9:0] N93;
    wire [10:0] \N94.co ;
    wire [9:0] N112;
    wire [9:0] N134;
    wire _N14250;
    wire _N14251;
    wire _N14252;
    wire _N14253;
    wire _N14254;
    wire _N14255;
    wire _N14256;
    wire _N14257;
    wire _N15177;
    wire _N15178;
    wire _N15179;
    wire _N15180;
    wire _N15181;
    wire _N15182;
    wire _N15183;
    wire _N15184;
    wire _N132590;
    wire _N132592;
    wire _N132594;
    wire _N133433;
    wire _N133435;
    wire _N133437;
    wire _N142128;
    wire _N142179;
    wire _N142259;
    wire _N142749;
    wire [9:0] next_rd;
    wire [9:0] next_wr;
    wire [9:0] rd_binary;
    wire \rd_binary[0]_inv ;
    wire [9:0] rd_gray;
    wire [9:0] rd_gray_w1;
    wire [9:0] rd_gray_w2;
    wire [9:0] wr_binary;
    wire \wr_binary[0]_inv ;
    wire [9:0] wr_gray;
    wire [9:0] wr_gray_r1;
    wire [9:0] wr_gray_r2;
    wire \memory_0_ECC_PARITY[0]_floating ;
    wire \memory_0_ECC_PARITY[1]_floating ;
    wire \memory_0_ECC_PARITY[2]_floating ;
    wire \memory_0_ECC_PARITY[3]_floating ;
    wire \memory_0_ECC_PARITY[4]_floating ;
    wire \memory_0_ECC_PARITY[5]_floating ;
    wire \memory_0_ECC_PARITY[6]_floating ;
    wire \memory_0_ECC_PARITY[7]_floating ;
    wire \memory_0_ECC_RDADDR[0]_floating ;
    wire \memory_0_ECC_RDADDR[1]_floating ;
    wire \memory_0_ECC_RDADDR[2]_floating ;
    wire \memory_0_ECC_RDADDR[3]_floating ;
    wire \memory_0_ECC_RDADDR[4]_floating ;
    wire \memory_0_ECC_RDADDR[5]_floating ;
    wire \memory_0_ECC_RDADDR[6]_floating ;
    wire \memory_0_ECC_RDADDR[7]_floating ;
    wire \memory_0_ECC_RDADDR[8]_floating ;
    wire \memory_1_ECC_PARITY[0]_floating ;
    wire \memory_1_ECC_PARITY[1]_floating ;
    wire \memory_1_ECC_PARITY[2]_floating ;
    wire \memory_1_ECC_PARITY[3]_floating ;
    wire \memory_1_ECC_PARITY[4]_floating ;
    wire \memory_1_ECC_PARITY[5]_floating ;
    wire \memory_1_ECC_PARITY[6]_floating ;
    wire \memory_1_ECC_PARITY[7]_floating ;
    wire \memory_1_ECC_RDADDR[0]_floating ;
    wire \memory_1_ECC_RDADDR[1]_floating ;
    wire \memory_1_ECC_RDADDR[2]_floating ;
    wire \memory_1_ECC_RDADDR[3]_floating ;
    wire \memory_1_ECC_RDADDR[4]_floating ;
    wire \memory_1_ECC_RDADDR[5]_floating ;
    wire \memory_1_ECC_RDADDR[6]_floating ;
    wire \memory_1_ECC_RDADDR[7]_floating ;
    wire \memory_1_ECC_RDADDR[8]_floating ;
    wire \memory_2_ECC_PARITY[0]_floating ;
    wire \memory_2_ECC_PARITY[1]_floating ;
    wire \memory_2_ECC_PARITY[2]_floating ;
    wire \memory_2_ECC_PARITY[3]_floating ;
    wire \memory_2_ECC_PARITY[4]_floating ;
    wire \memory_2_ECC_PARITY[5]_floating ;
    wire \memory_2_ECC_PARITY[6]_floating ;
    wire \memory_2_ECC_PARITY[7]_floating ;
    wire \memory_2_ECC_RDADDR[0]_floating ;
    wire \memory_2_ECC_RDADDR[1]_floating ;
    wire \memory_2_ECC_RDADDR[2]_floating ;
    wire \memory_2_ECC_RDADDR[3]_floating ;
    wire \memory_2_ECC_RDADDR[4]_floating ;
    wire \memory_2_ECC_RDADDR[5]_floating ;
    wire \memory_2_ECC_RDADDR[6]_floating ;
    wire \memory_2_ECC_RDADDR[7]_floating ;
    wire \memory_2_ECC_RDADDR[8]_floating ;
    wire \memory_3_DOA[8]_floating ;
    wire \memory_3_DOA[17]_floating ;
    wire \memory_3_DOA[26]_floating ;
    wire \memory_3_DOA[35]_floating ;
    wire \memory_3_DOB[8]_floating ;
    wire \memory_3_DOB[9]_floating ;
    wire \memory_3_DOB[10]_floating ;
    wire \memory_3_DOB[11]_floating ;
    wire \memory_3_DOB[12]_floating ;
    wire \memory_3_DOB[13]_floating ;
    wire \memory_3_DOB[14]_floating ;
    wire \memory_3_DOB[15]_floating ;
    wire \memory_3_DOB[16]_floating ;
    wire \memory_3_DOB[17]_floating ;
    wire \memory_3_DOB[18]_floating ;
    wire \memory_3_DOB[19]_floating ;
    wire \memory_3_DOB[20]_floating ;
    wire \memory_3_DOB[21]_floating ;
    wire \memory_3_DOB[22]_floating ;
    wire \memory_3_DOB[23]_floating ;
    wire \memory_3_DOB[24]_floating ;
    wire \memory_3_DOB[25]_floating ;
    wire \memory_3_DOB[26]_floating ;
    wire \memory_3_DOB[27]_floating ;
    wire \memory_3_DOB[28]_floating ;
    wire \memory_3_DOB[29]_floating ;
    wire \memory_3_DOB[30]_floating ;
    wire \memory_3_DOB[31]_floating ;
    wire \memory_3_DOB[32]_floating ;
    wire \memory_3_DOB[33]_floating ;
    wire \memory_3_DOB[34]_floating ;
    wire \memory_3_DOB[35]_floating ;
    wire \memory_3_ECC_PARITY[0]_floating ;
    wire \memory_3_ECC_PARITY[1]_floating ;
    wire \memory_3_ECC_PARITY[2]_floating ;
    wire \memory_3_ECC_PARITY[3]_floating ;
    wire \memory_3_ECC_PARITY[4]_floating ;
    wire \memory_3_ECC_PARITY[5]_floating ;
    wire \memory_3_ECC_PARITY[6]_floating ;
    wire \memory_3_ECC_PARITY[7]_floating ;
    wire \memory_3_ECC_RDADDR[0]_floating ;
    wire \memory_3_ECC_RDADDR[1]_floating ;
    wire \memory_3_ECC_RDADDR[2]_floating ;
    wire \memory_3_ECC_RDADDR[3]_floating ;
    wire \memory_3_ECC_RDADDR[4]_floating ;
    wire \memory_3_ECC_RDADDR[5]_floating ;
    wire \memory_3_ECC_RDADDR[6]_floating ;
    wire \memory_3_ECC_RDADDR[7]_floating ;
    wire \memory_3_ECC_RDADDR[8]_floating ;

    GTP_LUT6  #( .INIT(64'h7FBFDFEFF7FBFDFE)) N9_3 (
            .Z (_N133433),
            .I0 (rd_gray_w2[0]),
            .I1 (rd_gray_w2[1]),
            .I2 (rd_gray_w2[2]),
            .I3 (wr_gray[0]),
            .I4 (wr_gray[1]),
            .I5 (wr_gray[2]));
	// LUT = (I2&~I5)|(I1&~I4)|(I0&~I3)|(~I2&I5)|(~I1&I4)|(~I0&I3) ;

    GTP_LUT6  #( .INIT(64'h7FBFDFEFF7FBFDFE)) N9_5 (
            .Z (_N133435),
            .I0 (rd_gray_w2[3]),
            .I1 (rd_gray_w2[4]),
            .I2 (rd_gray_w2[5]),
            .I3 (wr_gray[3]),
            .I4 (wr_gray[4]),
            .I5 (wr_gray[5]));
	// LUT = (I2&~I5)|(I1&~I4)|(I0&~I3)|(~I2&I5)|(~I1&I4)|(~I0&I3) ;

    GTP_LUT6  #( .INIT(64'hF7FBFDFE7FBFDFEF)) N9_7 (
            .Z (_N133437),
            .I0 (rd_gray_w2[6]),
            .I1 (rd_gray_w2[7]),
            .I2 (rd_gray_w2[8]),
            .I3 (wr_gray[6]),
            .I4 (wr_gray[7]),
            .I5 (wr_gray[8]));
	// LUT = (~I2&~I5)|(I1&~I4)|(I0&~I3)|(~I1&I4)|(~I0&I3)|(I2&I5) ;

    GTP_LUT6  #( .INIT(64'h7FBFDFEFF7FBFDFE)) N10_3 (
            .Z (_N132590),
            .I0 (rd_gray[0]),
            .I1 (rd_gray[1]),
            .I2 (rd_gray[2]),
            .I3 (wr_gray_r2[0]),
            .I4 (wr_gray_r2[1]),
            .I5 (wr_gray_r2[2]));
	// LUT = (I2&~I5)|(I1&~I4)|(I0&~I3)|(~I2&I5)|(~I1&I4)|(~I0&I3) ;

    GTP_LUT6  #( .INIT(64'h7FBFDFEFF7FBFDFE)) N10_5 (
            .Z (_N132592),
            .I0 (rd_gray[3]),
            .I1 (rd_gray[4]),
            .I2 (rd_gray[5]),
            .I3 (wr_gray_r2[3]),
            .I4 (wr_gray_r2[4]),
            .I5 (wr_gray_r2[5]));
	// LUT = (I2&~I5)|(I1&~I4)|(I0&~I3)|(~I2&I5)|(~I1&I4)|(~I0&I3) ;

    GTP_LUT6  #( .INIT(64'h7FBFDFEFF7FBFDFE)) N10_7 (
            .Z (_N132594),
            .I0 (rd_gray[6]),
            .I1 (rd_gray[7]),
            .I2 (rd_gray[8]),
            .I3 (wr_gray_r2[6]),
            .I4 (wr_gray_r2[7]),
            .I5 (wr_gray_r2[8]));
	// LUT = (I2&~I5)|(I1&~I4)|(I0&~I3)|(~I2&I5)|(~I1&I4)|(~I0&I3) ;

    GTP_LUT6  #( .INIT(64'hAAAAAAAAAAAAAA82)) N11 (
            .Z (wr_ready),
            .I0 (wr_reset_sync[1]),
            .I1 (rd_gray_w2[9]),
            .I2 (wr_gray[9]),
            .I3 (_N133433),
            .I4 (_N133435),
            .I5 (_N133437));
	// LUT = (I0&I3)|(I0&I4)|(I0&I5)|(I0&~I1&~I2)|(I0&I1&I2) ;
	// ../../../compiled/rtl/video_async_fifo.v:34

    GTP_LUT6  #( .INIT(64'hCCCCCCCCCCCCCC48)) N12 (
            .Z (rd_ready),
            .I0 (rd_gray[9]),
            .I1 (rd_reset_sync[1]),
            .I2 (wr_gray_r2[9]),
            .I3 (_N132590),
            .I4 (_N132592),
            .I5 (_N132594));
	// LUT = (I1&I3)|(I1&I4)|(I1&I5)|(I0&I1&~I2)|(~I0&I1&I2) ;
	// ../../../compiled/rtl/video_async_fifo.v:35

    GTP_LUT4  #( .INIT(16'h6996)) N65 (
            .Z (N93[6]),
            .I0 (rd_gray_w2[6]),
            .I1 (rd_gray_w2[7]),
            .I2 (rd_gray_w2[8]),
            .I3 (rd_gray_w2[9]));
	// LUT = (I0&~I1&~I2&~I3)|(~I0&I1&~I2&~I3)|(~I0&~I1&I2&~I3)|(I0&I1&I2&~I3)|(~I0&~I1&~I2&I3)|(I0&I1&~I2&I3)|(I0&~I1&I2&I3)|(~I0&I1&I2&I3) ;
	// ../../../compiled/rtl/video_async_fifo.v:42

    GTP_LUT4  #( .INIT(16'h6996)) N77 (
            .Z (N93[3]),
            .I0 (N93[6]),
            .I1 (rd_gray_w2[3]),
            .I2 (rd_gray_w2[4]),
            .I3 (rd_gray_w2[5]));
	// LUT = (I0&~I1&~I2&~I3)|(~I0&I1&~I2&~I3)|(~I0&~I1&I2&~I3)|(I0&I1&I2&~I3)|(~I0&~I1&~I2&I3)|(I0&I1&~I2&I3)|(I0&~I1&I2&I3)|(~I0&I1&I2&I3) ;
	// ../../../compiled/rtl/video_async_fifo.v:42

    GTP_LUT6CARRY /* \N94.fsub_0  */ #(
            .INIT(64'hFFFFFFFF00000000),
            .I5_TO_CARRY("FALSE"),
            .I5_TO_LUT("FALSE"))
        \N94.fsub_0  (
            .COUT (\N94.co [0]),
            .Z (_N142749),
            .CIN (),
            .I0 (),
            .I1 (),
            .I2 (),
            .I3 (),
            .I4 (),
            .I5 ());
	// LUT = CIN ;
	// CARRY = (1'b0) ? CIN : (1'b1) ;
	// ../../../compiled/rtl/video_async_fifo.v:46

    GTP_LUT6CARRY /* \N94.fsub_1  */ #(
            .INIT(64'h9669699669969669),
            .I5_TO_CARRY("TRUE"),
            .I5_TO_LUT("FALSE"))
        \N94.fsub_1  (
            .COUT (\N94.co [1]),
            .Z (wr_used[0]),
            .CIN (\N94.co [0]),
            .I0 (N93[3]),
            .I1 (rd_gray_w2[0]),
            .I2 (rd_gray_w2[1]),
            .I3 (rd_gray_w2[2]),
            .I4 (wr_binary[0]),
            .I5 (wr_binary[0]));
	// LUT = ~CIN^I4^I3^I2^I1^I0 ;
	// CARRY = (~I4^I3^I2^I1^I0) ? CIN : I5 ;
	// ../../../compiled/rtl/video_async_fifo.v:46

    GTP_LUT6CARRY /* \N94.fsub_2  */ #(
            .INIT(64'h6996699696699669),
            .I5_TO_CARRY("TRUE"),
            .I5_TO_LUT("FALSE"))
        \N94.fsub_2  (
            .COUT (\N94.co [2]),
            .Z (wr_used[1]),
            .CIN (\N94.co [1]),
            .I0 (N93[3]),
            .I1 (rd_gray_w2[1]),
            .I2 (rd_gray_w2[2]),
            .I3 (wr_binary[1]),
            .I4 (),
            .I5 (wr_binary[1]));
	// LUT = ~CIN^I3^I2^I1^I0 ;
	// CARRY = (~I3^I2^I1^I0) ? CIN : I5 ;
	// ../../../compiled/rtl/video_async_fifo.v:46

    GTP_LUT6CARRY /* \N94.fsub_3  */ #(
            .INIT(64'h9696969669696969),
            .I5_TO_CARRY("TRUE"),
            .I5_TO_LUT("FALSE"))
        \N94.fsub_3  (
            .COUT (\N94.co [3]),
            .Z (wr_used[2]),
            .CIN (\N94.co [2]),
            .I0 (N93[3]),
            .I1 (rd_gray_w2[2]),
            .I2 (wr_binary[2]),
            .I3 (),
            .I4 (),
            .I5 (wr_binary[2]));
	// LUT = ~CIN^I2^I1^I0 ;
	// CARRY = (~I2^I1^I0) ? CIN : I5 ;
	// ../../../compiled/rtl/video_async_fifo.v:46

    GTP_LUT6CARRY /* \N94.fsub_4  */ #(
            .INIT(64'h9669699669969669),
            .I5_TO_CARRY("TRUE"),
            .I5_TO_LUT("FALSE"))
        \N94.fsub_4  (
            .COUT (\N94.co [4]),
            .Z (wr_used[3]),
            .CIN (\N94.co [3]),
            .I0 (N93[6]),
            .I1 (rd_gray_w2[3]),
            .I2 (rd_gray_w2[4]),
            .I3 (rd_gray_w2[5]),
            .I4 (wr_binary[3]),
            .I5 (wr_binary[3]));
	// LUT = ~CIN^I4^I3^I2^I1^I0 ;
	// CARRY = (~I4^I3^I2^I1^I0) ? CIN : I5 ;
	// ../../../compiled/rtl/video_async_fifo.v:46

    GTP_LUT6CARRY /* \N94.fsub_5  */ #(
            .INIT(64'h6996699696699669),
            .I5_TO_CARRY("TRUE"),
            .I5_TO_LUT("FALSE"))
        \N94.fsub_5  (
            .COUT (\N94.co [5]),
            .Z (wr_used[4]),
            .CIN (\N94.co [4]),
            .I0 (N93[6]),
            .I1 (rd_gray_w2[4]),
            .I2 (rd_gray_w2[5]),
            .I3 (wr_binary[4]),
            .I4 (),
            .I5 (wr_binary[4]));
	// LUT = ~CIN^I3^I2^I1^I0 ;
	// CARRY = (~I3^I2^I1^I0) ? CIN : I5 ;
	// ../../../compiled/rtl/video_async_fifo.v:46

    GTP_LUT6CARRY /* \N94.fsub_6  */ #(
            .INIT(64'h9696969669696969),
            .I5_TO_CARRY("TRUE"),
            .I5_TO_LUT("FALSE"))
        \N94.fsub_6  (
            .COUT (\N94.co [6]),
            .Z (wr_used[5]),
            .CIN (\N94.co [5]),
            .I0 (N93[6]),
            .I1 (rd_gray_w2[5]),
            .I2 (wr_binary[5]),
            .I3 (),
            .I4 (),
            .I5 (wr_binary[5]));
	// LUT = ~CIN^I2^I1^I0 ;
	// CARRY = (~I2^I1^I0) ? CIN : I5 ;
	// ../../../compiled/rtl/video_async_fifo.v:46

    GTP_LUT6CARRY /* \N94.fsub_7  */ #(
            .INIT(64'h9669699669969669),
            .I5_TO_CARRY("TRUE"),
            .I5_TO_LUT("FALSE"))
        \N94.fsub_7  (
            .COUT (\N94.co [7]),
            .Z (wr_used[6]),
            .CIN (\N94.co [6]),
            .I0 (rd_gray_w2[6]),
            .I1 (rd_gray_w2[7]),
            .I2 (rd_gray_w2[8]),
            .I3 (rd_gray_w2[9]),
            .I4 (wr_binary[6]),
            .I5 (wr_binary[6]));
	// LUT = ~CIN^I4^I3^I2^I1^I0 ;
	// CARRY = (~I4^I3^I2^I1^I0) ? CIN : I5 ;
	// ../../../compiled/rtl/video_async_fifo.v:46

    GTP_LUT6CARRY /* \N94.fsub_8  */ #(
            .INIT(64'h6996699696699669),
            .I5_TO_CARRY("TRUE"),
            .I5_TO_LUT("FALSE"))
        \N94.fsub_8  (
            .COUT (\N94.co [8]),
            .Z (wr_used[7]),
            .CIN (\N94.co [7]),
            .I0 (rd_gray_w2[7]),
            .I1 (rd_gray_w2[8]),
            .I2 (rd_gray_w2[9]),
            .I3 (wr_binary[7]),
            .I4 (),
            .I5 (wr_binary[7]));
	// LUT = ~CIN^I3^I2^I1^I0 ;
	// CARRY = (~I3^I2^I1^I0) ? CIN : I5 ;
	// ../../../compiled/rtl/video_async_fifo.v:46

    GTP_LUT6CARRY /* \N94.fsub_9  */ #(
            .INIT(64'h9696969669696969),
            .I5_TO_CARRY("TRUE"),
            .I5_TO_LUT("FALSE"))
        \N94.fsub_9  (
            .COUT (\N94.co [9]),
            .Z (wr_used[8]),
            .CIN (\N94.co [8]),
            .I0 (rd_gray_w2[8]),
            .I1 (rd_gray_w2[9]),
            .I2 (wr_binary[8]),
            .I3 (),
            .I4 (),
            .I5 (wr_binary[8]));
	// LUT = ~CIN^I2^I1^I0 ;
	// CARRY = (~I2^I1^I0) ? CIN : I5 ;
	// ../../../compiled/rtl/video_async_fifo.v:46

    GTP_LUT6CARRY /* \N94.fsub_10  */ #(
            .INIT(64'h6666666699999999),
            .I5_TO_CARRY("TRUE"),
            .I5_TO_LUT("FALSE"))
        \N94.fsub_10  (
            .COUT (_N142179),
            .Z (wr_used[9]),
            .CIN (\N94.co [9]),
            .I0 (rd_gray_w2[9]),
            .I1 (wr_binary[9]),
            .I2 (),
            .I3 (),
            .I4 (),
            .I5 ());
	// LUT = ~CIN^I1^I0 ;
	// CARRY = (~I1^I0) ? CIN : I5 ;
	// ../../../compiled/rtl/video_async_fifo.v:46

    GTP_LUT6CARRY /* N96_1_1 */ #(
            .INIT(64'h6666666600000000),
            .I5_TO_CARRY("TRUE"),
            .I5_TO_LUT("TRUE"))
        N96_1_1 (
            .COUT (_N14250),
            .Z (next_wr[1]),
            .CIN (),
            .I0 (wr_binary[0]),
            .I1 (wr_binary[1]),
            .I2 (),
            .I3 (),
            .I4 (),
            .I5 (1'b1));
	// LUT = I1^I0 ;
	// CARRY = (1'b0) ? CIN : I5 ;
	// ../../../compiled/rtl/video_async_fifo.v:47

    GTP_LUT6CARRY /* N96_1_2 */ #(
            .INIT(64'h7878787880808080),
            .I5_TO_CARRY("TRUE"),
            .I5_TO_LUT("FALSE"))
        N96_1_2 (
            .COUT (_N14251),
            .Z (next_wr[2]),
            .CIN (_N14250),
            .I0 (wr_binary[0]),
            .I1 (wr_binary[1]),
            .I2 (wr_binary[2]),
            .I3 (),
            .I4 (),
            .I5 (1'b0));
	// LUT = (I0&I1&I2&~CIN)|(I0&I1&~I2&CIN)|(~I1&I2&CIN)|(~I0&I2&CIN) ;
	// CARRY = (I0&I1&I2) ? CIN : I5 ;
	// ../../../compiled/rtl/video_async_fifo.v:47

    GTP_LUT6CARRY /* N96_1_3 */ #(
            .INIT(64'h55555555AAAAAAAA),
            .I5_TO_CARRY("TRUE"),
            .I5_TO_LUT("FALSE"))
        N96_1_3 (
            .COUT (_N14252),
            .Z (next_wr[3]),
            .CIN (_N14251),
            .I0 (wr_binary[3]),
            .I1 (),
            .I2 (),
            .I3 (),
            .I4 (),
            .I5 (1'b0));
	// LUT = CIN^I0 ;
	// CARRY = (I0) ? CIN : I5 ;
	// ../../../compiled/rtl/video_async_fifo.v:47

    GTP_LUT6CARRY /* N96_1_4 */ #(
            .INIT(64'h55555555AAAAAAAA),
            .I5_TO_CARRY("TRUE"),
            .I5_TO_LUT("FALSE"))
        N96_1_4 (
            .COUT (_N14253),
            .Z (next_wr[4]),
            .CIN (_N14252),
            .I0 (wr_binary[4]),
            .I1 (),
            .I2 (),
            .I3 (),
            .I4 (),
            .I5 (1'b0));
	// LUT = CIN^I0 ;
	// CARRY = (I0) ? CIN : I5 ;
	// ../../../compiled/rtl/video_async_fifo.v:47

    GTP_LUT6CARRY /* N96_1_5 */ #(
            .INIT(64'h55555555AAAAAAAA),
            .I5_TO_CARRY("TRUE"),
            .I5_TO_LUT("FALSE"))
        N96_1_5 (
            .COUT (_N14254),
            .Z (next_wr[5]),
            .CIN (_N14253),
            .I0 (wr_binary[5]),
            .I1 (),
            .I2 (),
            .I3 (),
            .I4 (),
            .I5 (1'b0));
	// LUT = CIN^I0 ;
	// CARRY = (I0) ? CIN : I5 ;
	// ../../../compiled/rtl/video_async_fifo.v:47

    GTP_LUT6CARRY /* N96_1_6 */ #(
            .INIT(64'h55555555AAAAAAAA),
            .I5_TO_CARRY("TRUE"),
            .I5_TO_LUT("FALSE"))
        N96_1_6 (
            .COUT (_N14255),
            .Z (next_wr[6]),
            .CIN (_N14254),
            .I0 (wr_binary[6]),
            .I1 (),
            .I2 (),
            .I3 (),
            .I4 (),
            .I5 (1'b0));
	// LUT = CIN^I0 ;
	// CARRY = (I0) ? CIN : I5 ;
	// ../../../compiled/rtl/video_async_fifo.v:47

    GTP_LUT6CARRY /* N96_1_7 */ #(
            .INIT(64'h55555555AAAAAAAA),
            .I5_TO_CARRY("TRUE"),
            .I5_TO_LUT("FALSE"))
        N96_1_7 (
            .COUT (_N14256),
            .Z (next_wr[7]),
            .CIN (_N14255),
            .I0 (wr_binary[7]),
            .I1 (),
            .I2 (),
            .I3 (),
            .I4 (),
            .I5 (1'b0));
	// LUT = CIN^I0 ;
	// CARRY = (I0) ? CIN : I5 ;
	// ../../../compiled/rtl/video_async_fifo.v:47

    GTP_LUT6CARRY /* N96_1_8 */ #(
            .INIT(64'h55555555AAAAAAAA),
            .I5_TO_CARRY("TRUE"),
            .I5_TO_LUT("FALSE"))
        N96_1_8 (
            .COUT (_N14257),
            .Z (next_wr[8]),
            .CIN (_N14256),
            .I0 (wr_binary[8]),
            .I1 (),
            .I2 (),
            .I3 (),
            .I4 (),
            .I5 (1'b0));
	// LUT = CIN^I0 ;
	// CARRY = (I0) ? CIN : I5 ;
	// ../../../compiled/rtl/video_async_fifo.v:47

    GTP_LUT6CARRY /* N96_1_9 */ #(
            .INIT(64'h55555555AAAAAAAA),
            .I5_TO_CARRY("TRUE"),
            .I5_TO_LUT("FALSE"))
        N96_1_9 (
            .COUT (_N142128),
            .Z (next_wr[9]),
            .CIN (_N14257),
            .I0 (wr_binary[9]),
            .I1 (),
            .I2 (),
            .I3 (),
            .I4 (),
            .I5 ());
	// LUT = CIN^I0 ;
	// CARRY = (I0) ? CIN : I5 ;
	// ../../../compiled/rtl/video_async_fifo.v:47

    GTP_LUT6CARRY /* N98_1_1 */ #(
            .INIT(64'h6666666600000000),
            .I5_TO_CARRY("TRUE"),
            .I5_TO_LUT("TRUE"))
        N98_1_1 (
            .COUT (_N15177),
            .Z (next_rd[1]),
            .CIN (),
            .I0 (rd_binary[0]),
            .I1 (rd_binary[1]),
            .I2 (),
            .I3 (),
            .I4 (),
            .I5 (1'b1));
	// LUT = I1^I0 ;
	// CARRY = (1'b0) ? CIN : I5 ;
	// ../../../compiled/rtl/video_async_fifo.v:47

    GTP_LUT6CARRY /* N98_1_2 */ #(
            .INIT(64'h7878787880808080),
            .I5_TO_CARRY("TRUE"),
            .I5_TO_LUT("FALSE"))
        N98_1_2 (
            .COUT (_N15178),
            .Z (next_rd[2]),
            .CIN (_N15177),
            .I0 (rd_binary[0]),
            .I1 (rd_binary[1]),
            .I2 (rd_binary[2]),
            .I3 (),
            .I4 (),
            .I5 (1'b0));
	// LUT = (I0&I1&I2&~CIN)|(I0&I1&~I2&CIN)|(~I1&I2&CIN)|(~I0&I2&CIN) ;
	// CARRY = (I0&I1&I2) ? CIN : I5 ;
	// ../../../compiled/rtl/video_async_fifo.v:47

    GTP_LUT6CARRY /* N98_1_3 */ #(
            .INIT(64'h55555555AAAAAAAA),
            .I5_TO_CARRY("TRUE"),
            .I5_TO_LUT("FALSE"))
        N98_1_3 (
            .COUT (_N15179),
            .Z (next_rd[3]),
            .CIN (_N15178),
            .I0 (rd_binary[3]),
            .I1 (),
            .I2 (),
            .I3 (),
            .I4 (),
            .I5 (1'b0));
	// LUT = CIN^I0 ;
	// CARRY = (I0) ? CIN : I5 ;
	// ../../../compiled/rtl/video_async_fifo.v:47

    GTP_LUT6CARRY /* N98_1_4 */ #(
            .INIT(64'h55555555AAAAAAAA),
            .I5_TO_CARRY("TRUE"),
            .I5_TO_LUT("FALSE"))
        N98_1_4 (
            .COUT (_N15180),
            .Z (next_rd[4]),
            .CIN (_N15179),
            .I0 (rd_binary[4]),
            .I1 (),
            .I2 (),
            .I3 (),
            .I4 (),
            .I5 (1'b0));
	// LUT = CIN^I0 ;
	// CARRY = (I0) ? CIN : I5 ;
	// ../../../compiled/rtl/video_async_fifo.v:47

    GTP_LUT6CARRY /* N98_1_5 */ #(
            .INIT(64'h55555555AAAAAAAA),
            .I5_TO_CARRY("TRUE"),
            .I5_TO_LUT("FALSE"))
        N98_1_5 (
            .COUT (_N15181),
            .Z (next_rd[5]),
            .CIN (_N15180),
            .I0 (rd_binary[5]),
            .I1 (),
            .I2 (),
            .I3 (),
            .I4 (),
            .I5 (1'b0));
	// LUT = CIN^I0 ;
	// CARRY = (I0) ? CIN : I5 ;
	// ../../../compiled/rtl/video_async_fifo.v:47

    GTP_LUT6CARRY /* N98_1_6 */ #(
            .INIT(64'h55555555AAAAAAAA),
            .I5_TO_CARRY("TRUE"),
            .I5_TO_LUT("FALSE"))
        N98_1_6 (
            .COUT (_N15182),
            .Z (next_rd[6]),
            .CIN (_N15181),
            .I0 (rd_binary[6]),
            .I1 (),
            .I2 (),
            .I3 (),
            .I4 (),
            .I5 (1'b0));
	// LUT = CIN^I0 ;
	// CARRY = (I0) ? CIN : I5 ;
	// ../../../compiled/rtl/video_async_fifo.v:47

    GTP_LUT6CARRY /* N98_1_7 */ #(
            .INIT(64'h55555555AAAAAAAA),
            .I5_TO_CARRY("TRUE"),
            .I5_TO_LUT("FALSE"))
        N98_1_7 (
            .COUT (_N15183),
            .Z (next_rd[7]),
            .CIN (_N15182),
            .I0 (rd_binary[7]),
            .I1 (),
            .I2 (),
            .I3 (),
            .I4 (),
            .I5 (1'b0));
	// LUT = CIN^I0 ;
	// CARRY = (I0) ? CIN : I5 ;
	// ../../../compiled/rtl/video_async_fifo.v:47

    GTP_LUT6CARRY /* N98_1_8 */ #(
            .INIT(64'h55555555AAAAAAAA),
            .I5_TO_CARRY("TRUE"),
            .I5_TO_LUT("FALSE"))
        N98_1_8 (
            .COUT (_N15184),
            .Z (next_rd[8]),
            .CIN (_N15183),
            .I0 (rd_binary[8]),
            .I1 (),
            .I2 (),
            .I3 (),
            .I4 (),
            .I5 (1'b0));
	// LUT = CIN^I0 ;
	// CARRY = (I0) ? CIN : I5 ;
	// ../../../compiled/rtl/video_async_fifo.v:47

    GTP_LUT6CARRY /* N98_1_9 */ #(
            .INIT(64'h55555555AAAAAAAA),
            .I5_TO_CARRY("TRUE"),
            .I5_TO_LUT("FALSE"))
        N98_1_9 (
            .COUT (_N142259),
            .Z (next_rd[9]),
            .CIN (_N15184),
            .I0 (rd_binary[9]),
            .I1 (),
            .I2 (),
            .I3 (),
            .I4 (),
            .I5 ());
	// LUT = CIN^I0 ;
	// CARRY = (I0) ? CIN : I5 ;
	// ../../../compiled/rtl/video_async_fifo.v:47

    GTP_LUT1  #( .INIT(2'b01)) N112_0_inv (
            .Z (N112[0]),
            .I0 (wr_binary[1]));
	// LUT = ~I0 ;

(* PAP_LUT_PAIR="system/display_fifo/N112_2" *)    GTP_LUT6D  #( .INIT(64'h666666663C3C3C3C)) N112_1 (
            .Z (N112[1]),
            .Z5 (N112[2]),
            .I0 (next_wr[1]),
            .I1 (next_wr[2]),
            .I2 (next_wr[3]),
            .I3 (),
            .I4 (),
            .I5 (1'b1));
	// LUT = I1^I0 ;
	// Z5 = I2^I1 ;
	// ../../../compiled/rtl/video_async_fifo.v:54

(* PAP_LUT_PAIR="system/display_fifo/N112_4" *)    GTP_LUT6D  #( .INIT(64'h666666663C3C3C3C)) N112_3 (
            .Z (N112[3]),
            .Z5 (N112[4]),
            .I0 (next_wr[3]),
            .I1 (next_wr[4]),
            .I2 (next_wr[5]),
            .I3 (),
            .I4 (),
            .I5 (1'b1));
	// LUT = I1^I0 ;
	// Z5 = I2^I1 ;
	// ../../../compiled/rtl/video_async_fifo.v:54

(* PAP_LUT_PAIR="system/display_fifo/N112_6" *)    GTP_LUT6D  #( .INIT(64'h666666663C3C3C3C)) N112_5 (
            .Z (N112[5]),
            .Z5 (N112[6]),
            .I0 (next_wr[5]),
            .I1 (next_wr[6]),
            .I2 (next_wr[7]),
            .I3 (),
            .I4 (),
            .I5 (1'b1));
	// LUT = I1^I0 ;
	// Z5 = I2^I1 ;
	// ../../../compiled/rtl/video_async_fifo.v:54

(* PAP_LUT_PAIR="system/display_fifo/N112_8" *)    GTP_LUT6D  #( .INIT(64'h666666663C3C3C3C)) N112_7 (
            .Z (N112[7]),
            .Z5 (N112[8]),
            .I0 (next_wr[7]),
            .I1 (next_wr[8]),
            .I2 (next_wr[9]),
            .I3 (),
            .I4 (),
            .I5 (1'b1));
	// LUT = I1^I0 ;
	// Z5 = I2^I1 ;
	// ../../../compiled/rtl/video_async_fifo.v:54

    GTP_LUT1  #( .INIT(2'b01)) N134_0_inv (
            .Z (N134[0]),
            .I0 (rd_binary[1]));
	// LUT = ~I0 ;

(* PAP_LUT_PAIR="system/display_fifo/N134_2" *)    GTP_LUT6D  #( .INIT(64'h666666663C3C3C3C)) N134_1 (
            .Z (N134[1]),
            .Z5 (N134[2]),
            .I0 (next_rd[1]),
            .I1 (next_rd[2]),
            .I2 (next_rd[3]),
            .I3 (),
            .I4 (),
            .I5 (1'b1));
	// LUT = I1^I0 ;
	// Z5 = I2^I1 ;
	// ../../../compiled/rtl/video_async_fifo.v:65

(* PAP_LUT_PAIR="system/display_fifo/N134_4" *)    GTP_LUT6D  #( .INIT(64'h666666663C3C3C3C)) N134_3 (
            .Z (N134[3]),
            .Z5 (N134[4]),
            .I0 (next_rd[3]),
            .I1 (next_rd[4]),
            .I2 (next_rd[5]),
            .I3 (),
            .I4 (),
            .I5 (1'b1));
	// LUT = I1^I0 ;
	// Z5 = I2^I1 ;
	// ../../../compiled/rtl/video_async_fifo.v:65

(* PAP_LUT_PAIR="system/display_fifo/N134_6" *)    GTP_LUT6D  #( .INIT(64'h666666663C3C3C3C)) N134_5 (
            .Z (N134[5]),
            .Z5 (N134[6]),
            .I0 (next_rd[5]),
            .I1 (next_rd[6]),
            .I2 (next_rd[7]),
            .I3 (),
            .I4 (),
            .I5 (1'b1));
	// LUT = I1^I0 ;
	// Z5 = I2^I1 ;
	// ../../../compiled/rtl/video_async_fifo.v:65

(* PAP_LUT_PAIR="system/display_fifo/N134_8" *)    GTP_LUT6D  #( .INIT(64'h666666663C3C3C3C)) N134_7 (
            .Z (N134[7]),
            .Z5 (N134[8]),
            .I0 (next_rd[7]),
            .I1 (next_rd[8]),
            .I2 (next_rd[9]),
            .I3 (),
            .I4 (),
            .I5 (1'b1));
	// LUT = I1^I0 ;
	// Z5 = I2^I1 ;
	// ../../../compiled/rtl/video_async_fifo.v:65

    GTP_DRM36K_E1 /* memory_0 */ #(
            .GRS_EN("TRUE"),
            .CSA_MASK(3'b111),
            .CSB_MASK(3'b111),
            .DATA_WIDTH_A(72),
            .DATA_WIDTH_B(72),
            .WRITE_MODE_A("NORMAL_WRITE"),
            .WRITE_MODE_B("NORMAL_WRITE"),
            .DOA_REG(0),
            .DOB_REG(0),
            .DOA_REG_CLKINV(0),
            .DOB_REG_CLKINV(0),
            .RSTA_VAL(36'b000000000000000000000000000000000000),
            .RSTB_VAL(36'b000000000000000000000000000000000000),
            .RST_TYPE("SYNC"),
            .RAM_MODE("SIMPLE_DUAL_PORT"),
            .RAM_CASCADE("NONE"),
            .ECC_READ_EN("FALSE"),
            .ECC_WRITE_EN("FALSE"),
            .INIT_00(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_01(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_02(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_03(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_04(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_05(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_06(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_07(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_08(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_09(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_0A(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_0B(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_0C(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_0D(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_0E(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_0F(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_10(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_11(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_12(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_13(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_14(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_15(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_16(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_17(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_18(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_19(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_1A(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_1B(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_1C(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_1D(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_1E(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_1F(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_20(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_21(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_22(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_23(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_24(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_25(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_26(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_27(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_28(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_29(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_2A(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_2B(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_2C(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_2D(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_2E(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_2F(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_30(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_31(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_32(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_33(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_34(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_35(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_36(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_37(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_38(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_39(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_3A(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_3B(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_3C(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_3D(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_3E(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_3F(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_40(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_41(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_42(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_43(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_44(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_45(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_46(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_47(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_48(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_49(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_4A(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_4B(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_4C(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_4D(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_4E(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_4F(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_50(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_51(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_52(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_53(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_54(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_55(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_56(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_57(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_58(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_59(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_5A(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_5B(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_5C(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_5D(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_5E(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_5F(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_60(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_61(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_62(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_63(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_64(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_65(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_66(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_67(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_68(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_69(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_6A(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_6B(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_6C(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_6D(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_6E(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_6F(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_70(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_71(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_72(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_73(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_74(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_75(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_76(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_77(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_78(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_79(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_7A(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_7B(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_7C(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_7D(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_7E(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_7F(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_FILE("NONE"),
            .BLOCK_X(0),
            .BLOCK_Y(0),
            .RAM_DATA_WIDTH(18),
            .RAM_ADDR_WIDTH(11),
            .INIT_FORMAT("BIN"))
        memory_0 (
            .DOA ({rd_data[35], rd_data[34], rd_data[33], rd_data[32], rd_data[31], rd_data[30], rd_data[29], rd_data[28], rd_data[27], rd_data[26], rd_data[25], rd_data[24], rd_data[23], rd_data[22], rd_data[21], rd_data[20], rd_data[19], rd_data[18], rd_data[17], rd_data[16], rd_data[15], rd_data[14], rd_data[13], rd_data[12], rd_data[11], rd_data[10], rd_data[9], rd_data[8], rd_data[7], rd_data[6], rd_data[5], rd_data[4], rd_data[3], rd_data[2], rd_data[1], rd_data[0]}),
            .DOB ({rd_data[71], rd_data[70], rd_data[69], rd_data[68], rd_data[67], rd_data[66], rd_data[65], rd_data[64], rd_data[63], rd_data[62], rd_data[61], rd_data[60], rd_data[59], rd_data[58], rd_data[57], rd_data[56], rd_data[55], rd_data[54], rd_data[53], rd_data[52], rd_data[51], rd_data[50], rd_data[49], rd_data[48], rd_data[47], rd_data[46], rd_data[45], rd_data[44], rd_data[43], rd_data[42], rd_data[41], rd_data[40], rd_data[39], rd_data[38], rd_data[37], rd_data[36]}),
            .ECC_PARITY (),
            .ECC_RDADDR (),
            .ADDRA ({1'b1, wr_binary[8], wr_binary[7], wr_binary[6], wr_binary[5], wr_binary[4], wr_binary[3], wr_binary[2], wr_binary[1], wr_binary[0], 1'b1, 1'b1, 1'b1, 1'b1, 1'b1, 1'b1}),
            .ADDRB ({1'b1, rd_binary[8], rd_binary[7], rd_binary[6], rd_binary[5], rd_binary[4], rd_binary[3], rd_binary[2], rd_binary[1], rd_binary[0], 1'b1, 1'b1, 1'b1, 1'b1, 1'b1, 1'b1}),
            .BWEA ({1'b1, 1'b1, 1'b1, 1'b1, 1'b1, 1'b1, 1'b1, 1'b1}),
            .BWEB ({1'b1, 1'b1, 1'b1, 1'b1}),
            .CSA ({1'b1, 1'b1, 1'b1}),
            .CSB ({1'b1, 1'b1, 1'b1}),
            .DIA ({wr_data[35], wr_data[34], wr_data[33], wr_data[32], wr_data[31], wr_data[30], wr_data[29], wr_data[28], wr_data[27], wr_data[26], wr_data[25], wr_data[24], wr_data[23], wr_data[22], wr_data[21], wr_data[20], wr_data[19], wr_data[18], wr_data[17], wr_data[16], wr_data[15], wr_data[14], wr_data[13], wr_data[12], wr_data[11], wr_data[10], wr_data[9], wr_data[8], wr_data[7], wr_data[6], wr_data[5], wr_data[4], wr_data[3], wr_data[2], wr_data[1], wr_data[0]}),
            .DIB ({wr_data[71], wr_data[70], wr_data[69], wr_data[68], wr_data[67], wr_data[66], wr_data[65], wr_data[64], wr_data[63], wr_data[62], wr_data[61], wr_data[60], wr_data[59], wr_data[58], wr_data[57], wr_data[56], wr_data[55], wr_data[54], wr_data[53], wr_data[52], wr_data[51], wr_data[50], wr_data[49], wr_data[48], wr_data[47], wr_data[46], wr_data[45], wr_data[44], wr_data[43], wr_data[42], wr_data[41], wr_data[40], wr_data[39], wr_data[38], wr_data[37], wr_data[36]}),
            .COUTA (),
            .COUTB (),
            .ECC_DBITERR (),
            .ECC_SBITERR (),
            .ADDRA_HOLD (1'b0),
            .ADDRB_HOLD (1'b0),
            .CEA (wr_reset_sync[1]),
            .CEB (rd_en),
            .CINA (),
            .CINB (),
            .CLKA (wr_clk),
            .CLKB (nt_pixclk_in),
            .INJECT_DBITERR (1'b1),
            .INJECT_SBITERR (1'b1),
            .ORCEA (1'b1),
            .ORCEB (1'b1),
            .RSTA (1'b0),
            .RSTB (1'b0),
            .WEA (N107),
            .WEB (1'b0));
	// ../../../compiled/rtl/video_async_fifo.v:48

    GTP_DRM36K_E1 /* memory_1 */ #(
            .GRS_EN("TRUE"),
            .CSA_MASK(3'b111),
            .CSB_MASK(3'b111),
            .DATA_WIDTH_A(72),
            .DATA_WIDTH_B(72),
            .WRITE_MODE_A("NORMAL_WRITE"),
            .WRITE_MODE_B("NORMAL_WRITE"),
            .DOA_REG(0),
            .DOB_REG(0),
            .DOA_REG_CLKINV(0),
            .DOB_REG_CLKINV(0),
            .RSTA_VAL(36'b000000000000000000000000000000000000),
            .RSTB_VAL(36'b000000000000000000000000000000000000),
            .RST_TYPE("SYNC"),
            .RAM_MODE("SIMPLE_DUAL_PORT"),
            .RAM_CASCADE("NONE"),
            .ECC_READ_EN("FALSE"),
            .ECC_WRITE_EN("FALSE"),
            .INIT_00(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_01(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_02(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_03(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_04(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_05(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_06(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_07(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_08(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_09(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_0A(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_0B(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_0C(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_0D(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_0E(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_0F(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_10(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_11(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_12(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_13(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_14(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_15(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_16(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_17(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_18(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_19(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_1A(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_1B(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_1C(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_1D(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_1E(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_1F(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_20(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_21(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_22(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_23(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_24(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_25(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_26(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_27(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_28(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_29(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_2A(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_2B(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_2C(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_2D(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_2E(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_2F(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_30(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_31(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_32(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_33(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_34(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_35(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_36(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_37(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_38(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_39(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_3A(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_3B(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_3C(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_3D(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_3E(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_3F(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_40(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_41(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_42(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_43(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_44(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_45(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_46(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_47(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_48(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_49(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_4A(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_4B(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_4C(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_4D(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_4E(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_4F(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_50(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_51(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_52(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_53(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_54(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_55(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_56(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_57(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_58(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_59(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_5A(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_5B(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_5C(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_5D(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_5E(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_5F(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_60(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_61(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_62(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_63(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_64(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_65(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_66(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_67(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_68(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_69(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_6A(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_6B(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_6C(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_6D(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_6E(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_6F(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_70(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_71(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_72(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_73(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_74(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_75(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_76(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_77(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_78(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_79(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_7A(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_7B(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_7C(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_7D(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_7E(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_7F(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_FILE("NONE"),
            .BLOCK_X(0),
            .BLOCK_Y(0),
            .RAM_DATA_WIDTH(18),
            .RAM_ADDR_WIDTH(11),
            .INIT_FORMAT("BIN"))
        memory_1 (
            .DOA ({rd_data[107], rd_data[106], rd_data[105], rd_data[104], rd_data[103], rd_data[102], rd_data[101], rd_data[100], rd_data[99], rd_data[98], rd_data[97], rd_data[96], rd_data[95], rd_data[94], rd_data[93], rd_data[92], rd_data[91], rd_data[90], rd_data[89], rd_data[88], rd_data[87], rd_data[86], rd_data[85], rd_data[84], rd_data[83], rd_data[82], rd_data[81], rd_data[80], rd_data[79], rd_data[78], rd_data[77], rd_data[76], rd_data[75], rd_data[74], rd_data[73], rd_data[72]}),
            .DOB ({rd_data[143], rd_data[142], rd_data[141], rd_data[140], rd_data[139], rd_data[138], rd_data[137], rd_data[136], rd_data[135], rd_data[134], rd_data[133], rd_data[132], rd_data[131], rd_data[130], rd_data[129], rd_data[128], rd_data[127], rd_data[126], rd_data[125], rd_data[124], rd_data[123], rd_data[122], rd_data[121], rd_data[120], rd_data[119], rd_data[118], rd_data[117], rd_data[116], rd_data[115], rd_data[114], rd_data[113], rd_data[112], rd_data[111], rd_data[110], rd_data[109], rd_data[108]}),
            .ECC_PARITY (),
            .ECC_RDADDR (),
            .ADDRA ({1'b1, wr_binary[8], wr_binary[7], wr_binary[6], wr_binary[5], wr_binary[4], wr_binary[3], wr_binary[2], wr_binary[1], wr_binary[0], 1'b1, 1'b1, 1'b1, 1'b1, 1'b1, 1'b1}),
            .ADDRB ({1'b1, rd_binary[8], rd_binary[7], rd_binary[6], rd_binary[5], rd_binary[4], rd_binary[3], rd_binary[2], rd_binary[1], rd_binary[0], 1'b1, 1'b1, 1'b1, 1'b1, 1'b1, 1'b1}),
            .BWEA ({1'b1, 1'b1, 1'b1, 1'b1, 1'b1, 1'b1, 1'b1, 1'b1}),
            .BWEB ({1'b1, 1'b1, 1'b1, 1'b1}),
            .CSA ({1'b1, 1'b1, 1'b1}),
            .CSB ({1'b1, 1'b1, 1'b1}),
            .DIA ({wr_data[107], wr_data[106], wr_data[105], wr_data[104], wr_data[103], wr_data[102], wr_data[101], wr_data[100], wr_data[99], wr_data[98], wr_data[97], wr_data[96], wr_data[95], wr_data[94], wr_data[93], wr_data[92], wr_data[91], wr_data[90], wr_data[89], wr_data[88], wr_data[87], wr_data[86], wr_data[85], wr_data[84], wr_data[83], wr_data[82], wr_data[81], wr_data[80], wr_data[79], wr_data[78], wr_data[77], wr_data[76], wr_data[75], wr_data[74], wr_data[73], wr_data[72]}),
            .DIB ({wr_data[143], wr_data[142], wr_data[141], wr_data[140], wr_data[139], wr_data[138], wr_data[137], wr_data[136], wr_data[135], wr_data[134], wr_data[133], wr_data[132], wr_data[131], wr_data[130], wr_data[129], wr_data[128], wr_data[127], wr_data[126], wr_data[125], wr_data[124], wr_data[123], wr_data[122], wr_data[121], wr_data[120], wr_data[119], wr_data[118], wr_data[117], wr_data[116], wr_data[115], wr_data[114], wr_data[113], wr_data[112], wr_data[111], wr_data[110], wr_data[109], wr_data[108]}),
            .COUTA (),
            .COUTB (),
            .ECC_DBITERR (),
            .ECC_SBITERR (),
            .ADDRA_HOLD (1'b0),
            .ADDRB_HOLD (1'b0),
            .CEA (wr_reset_sync[1]),
            .CEB (rd_en),
            .CINA (),
            .CINB (),
            .CLKA (wr_clk),
            .CLKB (nt_pixclk_in),
            .INJECT_DBITERR (1'b1),
            .INJECT_SBITERR (1'b1),
            .ORCEA (1'b1),
            .ORCEB (1'b1),
            .RSTA (1'b0),
            .RSTB (1'b0),
            .WEA (N107),
            .WEB (1'b0));
	// ../../../compiled/rtl/video_async_fifo.v:48

    GTP_DRM36K_E1 /* memory_2 */ #(
            .GRS_EN("TRUE"),
            .CSA_MASK(3'b111),
            .CSB_MASK(3'b111),
            .DATA_WIDTH_A(72),
            .DATA_WIDTH_B(72),
            .WRITE_MODE_A("NORMAL_WRITE"),
            .WRITE_MODE_B("NORMAL_WRITE"),
            .DOA_REG(0),
            .DOB_REG(0),
            .DOA_REG_CLKINV(0),
            .DOB_REG_CLKINV(0),
            .RSTA_VAL(36'b000000000000000000000000000000000000),
            .RSTB_VAL(36'b000000000000000000000000000000000000),
            .RST_TYPE("SYNC"),
            .RAM_MODE("SIMPLE_DUAL_PORT"),
            .RAM_CASCADE("NONE"),
            .ECC_READ_EN("FALSE"),
            .ECC_WRITE_EN("FALSE"),
            .INIT_00(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_01(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_02(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_03(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_04(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_05(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_06(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_07(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_08(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_09(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_0A(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_0B(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_0C(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_0D(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_0E(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_0F(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_10(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_11(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_12(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_13(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_14(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_15(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_16(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_17(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_18(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_19(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_1A(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_1B(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_1C(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_1D(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_1E(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_1F(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_20(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_21(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_22(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_23(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_24(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_25(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_26(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_27(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_28(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_29(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_2A(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_2B(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_2C(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_2D(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_2E(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_2F(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_30(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_31(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_32(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_33(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_34(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_35(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_36(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_37(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_38(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_39(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_3A(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_3B(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_3C(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_3D(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_3E(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_3F(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_40(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_41(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_42(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_43(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_44(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_45(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_46(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_47(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_48(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_49(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_4A(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_4B(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_4C(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_4D(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_4E(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_4F(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_50(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_51(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_52(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_53(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_54(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_55(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_56(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_57(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_58(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_59(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_5A(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_5B(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_5C(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_5D(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_5E(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_5F(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_60(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_61(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_62(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_63(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_64(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_65(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_66(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_67(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_68(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_69(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_6A(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_6B(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_6C(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_6D(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_6E(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_6F(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_70(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_71(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_72(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_73(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_74(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_75(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_76(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_77(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_78(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_79(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_7A(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_7B(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_7C(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_7D(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_7E(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_7F(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_FILE("NONE"),
            .BLOCK_X(0),
            .BLOCK_Y(0),
            .RAM_DATA_WIDTH(18),
            .RAM_ADDR_WIDTH(11),
            .INIT_FORMAT("BIN"))
        memory_2 (
            .DOA ({rd_data[179], rd_data[178], rd_data[177], rd_data[176], rd_data[175], rd_data[174], rd_data[173], rd_data[172], rd_data[171], rd_data[170], rd_data[169], rd_data[168], rd_data[167], rd_data[166], rd_data[165], rd_data[164], rd_data[163], rd_data[162], rd_data[161], rd_data[160], rd_data[159], rd_data[158], rd_data[157], rd_data[156], rd_data[155], rd_data[154], rd_data[153], rd_data[152], rd_data[151], rd_data[150], rd_data[149], rd_data[148], rd_data[147], rd_data[146], rd_data[145], rd_data[144]}),
            .DOB ({rd_data[215], rd_data[214], rd_data[213], rd_data[212], rd_data[211], rd_data[210], rd_data[209], rd_data[208], rd_data[207], rd_data[206], rd_data[205], rd_data[204], rd_data[203], rd_data[202], rd_data[201], rd_data[200], rd_data[199], rd_data[198], rd_data[197], rd_data[196], rd_data[195], rd_data[194], rd_data[193], rd_data[192], rd_data[191], rd_data[190], rd_data[189], rd_data[188], rd_data[187], rd_data[186], rd_data[185], rd_data[184], rd_data[183], rd_data[182], rd_data[181], rd_data[180]}),
            .ECC_PARITY (),
            .ECC_RDADDR (),
            .ADDRA ({1'b1, wr_binary[8], wr_binary[7], wr_binary[6], wr_binary[5], wr_binary[4], wr_binary[3], wr_binary[2], wr_binary[1], wr_binary[0], 1'b1, 1'b1, 1'b1, 1'b1, 1'b1, 1'b1}),
            .ADDRB ({1'b1, rd_binary[8], rd_binary[7], rd_binary[6], rd_binary[5], rd_binary[4], rd_binary[3], rd_binary[2], rd_binary[1], rd_binary[0], 1'b1, 1'b1, 1'b1, 1'b1, 1'b1, 1'b1}),
            .BWEA ({1'b1, 1'b1, 1'b1, 1'b1, 1'b1, 1'b1, 1'b1, 1'b1}),
            .BWEB ({1'b1, 1'b1, 1'b1, 1'b1}),
            .CSA ({1'b1, 1'b1, 1'b1}),
            .CSB ({1'b1, 1'b1, 1'b1}),
            .DIA ({wr_data[179], wr_data[178], wr_data[177], wr_data[176], wr_data[175], wr_data[174], wr_data[173], wr_data[172], wr_data[171], wr_data[170], wr_data[169], wr_data[168], wr_data[167], wr_data[166], wr_data[165], wr_data[164], wr_data[163], wr_data[162], wr_data[161], wr_data[160], wr_data[159], wr_data[158], wr_data[157], wr_data[156], wr_data[155], wr_data[154], wr_data[153], wr_data[152], wr_data[151], wr_data[150], wr_data[149], wr_data[148], wr_data[147], wr_data[146], wr_data[145], wr_data[144]}),
            .DIB ({wr_data[215], wr_data[214], wr_data[213], wr_data[212], wr_data[211], wr_data[210], wr_data[209], wr_data[208], wr_data[207], wr_data[206], wr_data[205], wr_data[204], wr_data[203], wr_data[202], wr_data[201], wr_data[200], wr_data[199], wr_data[198], wr_data[197], wr_data[196], wr_data[195], wr_data[194], wr_data[193], wr_data[192], wr_data[191], wr_data[190], wr_data[189], wr_data[188], wr_data[187], wr_data[186], wr_data[185], wr_data[184], wr_data[183], wr_data[182], wr_data[181], wr_data[180]}),
            .COUTA (),
            .COUTB (),
            .ECC_DBITERR (),
            .ECC_SBITERR (),
            .ADDRA_HOLD (1'b0),
            .ADDRB_HOLD (1'b0),
            .CEA (wr_reset_sync[1]),
            .CEB (rd_en),
            .CINA (),
            .CINB (),
            .CLKA (wr_clk),
            .CLKB (nt_pixclk_in),
            .INJECT_DBITERR (1'b1),
            .INJECT_SBITERR (1'b1),
            .ORCEA (1'b1),
            .ORCEB (1'b1),
            .RSTA (1'b0),
            .RSTB (1'b0),
            .WEA (N107),
            .WEB (1'b0));
	// ../../../compiled/rtl/video_async_fifo.v:48

    GTP_DRM36K_E1 /* memory_3 */ #(
            .GRS_EN("TRUE"),
            .CSA_MASK(3'b111),
            .CSB_MASK(3'b111),
            .DATA_WIDTH_A(64),
            .DATA_WIDTH_B(64),
            .WRITE_MODE_A("NORMAL_WRITE"),
            .WRITE_MODE_B("NORMAL_WRITE"),
            .DOA_REG(0),
            .DOB_REG(0),
            .DOA_REG_CLKINV(0),
            .DOB_REG_CLKINV(0),
            .RSTA_VAL(36'b000000000000000000000000000000000000),
            .RSTB_VAL(36'b000000000000000000000000000000000000),
            .RST_TYPE("SYNC"),
            .RAM_MODE("SIMPLE_DUAL_PORT"),
            .RAM_CASCADE("NONE"),
            .ECC_READ_EN("FALSE"),
            .ECC_WRITE_EN("FALSE"),
            .INIT_00(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_01(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_02(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_03(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_04(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_05(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_06(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_07(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_08(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_09(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_0A(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_0B(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_0C(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_0D(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_0E(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_0F(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_10(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_11(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_12(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_13(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_14(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_15(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_16(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_17(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_18(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_19(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_1A(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_1B(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_1C(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_1D(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_1E(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_1F(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_20(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_21(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_22(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_23(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_24(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_25(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_26(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_27(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_28(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_29(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_2A(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_2B(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_2C(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_2D(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_2E(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_2F(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_30(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_31(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_32(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_33(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_34(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_35(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_36(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_37(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_38(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_39(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_3A(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_3B(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_3C(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_3D(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_3E(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_3F(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_40(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_41(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_42(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_43(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_44(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_45(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_46(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_47(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_48(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_49(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_4A(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_4B(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_4C(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_4D(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_4E(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_4F(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_50(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_51(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_52(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_53(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_54(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_55(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_56(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_57(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_58(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_59(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_5A(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_5B(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_5C(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_5D(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_5E(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_5F(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_60(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_61(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_62(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_63(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_64(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_65(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_66(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_67(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_68(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_69(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_6A(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_6B(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_6C(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_6D(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_6E(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_6F(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_70(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_71(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_72(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_73(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_74(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_75(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_76(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_77(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_78(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_79(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_7A(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_7B(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_7C(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_7D(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_7E(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_7F(288'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000),
            .INIT_FILE("NONE"),
            .BLOCK_X(0),
            .BLOCK_Y(0),
            .RAM_DATA_WIDTH(18),
            .RAM_ADDR_WIDTH(11),
            .INIT_FORMAT("BIN"))
        memory_3 (
            .DOA ({\memory_3_DOA[35]_floating , rd_data[247], rd_data[246], rd_data[245], rd_data[244], rd_data[243], rd_data[242], rd_data[241], rd_data[240], \memory_3_DOA[26]_floating , rd_data[239], rd_data[238], rd_data[237], rd_data[236], rd_data[235], rd_data[234], rd_data[233], rd_data[232], \memory_3_DOA[17]_floating , rd_data[231], rd_data[230], rd_data[229], rd_data[228], rd_data[227], rd_data[226], rd_data[225], rd_data[224], \memory_3_DOA[8]_floating , rd_data[223], rd_data[222], rd_data[221], rd_data[220], rd_data[219], rd_data[218], rd_data[217], rd_data[216]}),
            .DOB ({\memory_3_DOB[35]_floating , \memory_3_DOB[34]_floating , \memory_3_DOB[33]_floating , \memory_3_DOB[32]_floating , \memory_3_DOB[31]_floating , \memory_3_DOB[30]_floating , \memory_3_DOB[29]_floating , \memory_3_DOB[28]_floating , \memory_3_DOB[27]_floating , \memory_3_DOB[26]_floating , \memory_3_DOB[25]_floating , \memory_3_DOB[24]_floating , \memory_3_DOB[23]_floating , \memory_3_DOB[22]_floating , \memory_3_DOB[21]_floating , \memory_3_DOB[20]_floating , \memory_3_DOB[19]_floating , \memory_3_DOB[18]_floating , \memory_3_DOB[17]_floating , \memory_3_DOB[16]_floating , \memory_3_DOB[15]_floating , \memory_3_DOB[14]_floating , \memory_3_DOB[13]_floating , \memory_3_DOB[12]_floating , \memory_3_DOB[11]_floating , \memory_3_DOB[10]_floating , \memory_3_DOB[9]_floating , \memory_3_DOB[8]_floating , rd_data[255], rd_data[254], rd_data[253], rd_data[252], rd_data[251], rd_data[250], rd_data[249], rd_data[248]}),
            .ECC_PARITY (),
            .ECC_RDADDR (),
            .ADDRA ({1'b1, wr_binary[8], wr_binary[7], wr_binary[6], wr_binary[5], wr_binary[4], wr_binary[3], wr_binary[2], wr_binary[1], wr_binary[0], 1'b1, 1'b1, 1'b1, 1'b1, 1'b1, 1'b1}),
            .ADDRB ({1'b1, rd_binary[8], rd_binary[7], rd_binary[6], rd_binary[5], rd_binary[4], rd_binary[3], rd_binary[2], rd_binary[1], rd_binary[0], 1'b1, 1'b1, 1'b1, 1'b1, 1'b1, 1'b1}),
            .BWEA ({1'b1, 1'b1, 1'b1, 1'b1, 1'b1, 1'b1, 1'b1, 1'b1}),
            .BWEB ({1'b1, 1'b1, 1'b1, 1'b1}),
            .CSA ({1'b1, 1'b1, 1'b1}),
            .CSB ({1'b1, 1'b1, 1'b1}),
            .DIA ({1'b1, wr_data[247], wr_data[246], wr_data[245], wr_data[244], wr_data[243], wr_data[242], wr_data[241], wr_data[240], 1'b1, wr_data[239], wr_data[238], wr_data[237], wr_data[236], wr_data[235], wr_data[234], wr_data[233], wr_data[232], 1'b1, wr_data[231], wr_data[230], wr_data[229], wr_data[228], wr_data[227], wr_data[226], wr_data[225], wr_data[224], 1'b1, wr_data[223], wr_data[222], wr_data[221], wr_data[220], wr_data[219], wr_data[218], wr_data[217], wr_data[216]}),
            .DIB ({1'b1, 1'b1, 1'b1, 1'b1, 1'b1, 1'b1, 1'b1, 1'b1, 1'b1, 1'b1, 1'b1, 1'b1, 1'b1, 1'b1, 1'b1, 1'b1, 1'b1, 1'b1, 1'b1, 1'b1, 1'b1, 1'b1, 1'b1, 1'b1, 1'b1, 1'b1, 1'b1, 1'b1, wr_data[255], wr_data[254], wr_data[253], wr_data[252], wr_data[251], wr_data[250], wr_data[249], wr_data[248]}),
            .COUTA (),
            .COUTB (),
            .ECC_DBITERR (),
            .ECC_SBITERR (),
            .ADDRA_HOLD (1'b0),
            .ADDRB_HOLD (1'b0),
            .CEA (wr_reset_sync[1]),
            .CEB (rd_en),
            .CINA (),
            .CINB (),
            .CLKA (wr_clk),
            .CLKB (nt_pixclk_in),
            .INJECT_DBITERR (1'b1),
            .INJECT_SBITERR (1'b1),
            .ORCEA (1'b1),
            .ORCEB (1'b1),
            .RSTA (1'b0),
            .RSTB (1'b0),
            .WEA (N107),
            .WEB (1'b0));
	// ../../../compiled/rtl/video_async_fifo.v:48

    GTP_DFF_RE  #( .GRS_EN("TRUE"), .INIT(1'b0)) \rd_binary[0]  (
            .Q (rd_binary[0]),
            .CE (rd_en),
            .CLK (nt_pixclk_in),
            .D (\rd_binary[0]_inv ),
            .R (\rd_reset_sync[1]_inv_1 ));
	// ../../../compiled/rtl/video_async_fifo.v:58

    GTP_DFF_RE  #( .GRS_EN("TRUE"), .INIT(1'b0)) \rd_binary[1]  (
            .Q (rd_binary[1]),
            .CE (rd_en),
            .CLK (nt_pixclk_in),
            .D (next_rd[1]),
            .R (\rd_reset_sync[1]_inv_1 ));
	// ../../../compiled/rtl/video_async_fifo.v:58

    GTP_DFF_RE  #( .GRS_EN("TRUE"), .INIT(1'b0)) \rd_binary[2]  (
            .Q (rd_binary[2]),
            .CE (rd_en),
            .CLK (nt_pixclk_in),
            .D (next_rd[2]),
            .R (\rd_reset_sync[1]_inv_1 ));
	// ../../../compiled/rtl/video_async_fifo.v:58

    GTP_DFF_RE  #( .GRS_EN("TRUE"), .INIT(1'b0)) \rd_binary[3]  (
            .Q (rd_binary[3]),
            .CE (rd_en),
            .CLK (nt_pixclk_in),
            .D (next_rd[3]),
            .R (\rd_reset_sync[1]_inv_1 ));
	// ../../../compiled/rtl/video_async_fifo.v:58

    GTP_DFF_RE  #( .GRS_EN("TRUE"), .INIT(1'b0)) \rd_binary[4]  (
            .Q (rd_binary[4]),
            .CE (rd_en),
            .CLK (nt_pixclk_in),
            .D (next_rd[4]),
            .R (\rd_reset_sync[1]_inv_1 ));
	// ../../../compiled/rtl/video_async_fifo.v:58

    GTP_DFF_RE  #( .GRS_EN("TRUE"), .INIT(1'b0)) \rd_binary[5]  (
            .Q (rd_binary[5]),
            .CE (rd_en),
            .CLK (nt_pixclk_in),
            .D (next_rd[5]),
            .R (\rd_reset_sync[1]_inv_1 ));
	// ../../../compiled/rtl/video_async_fifo.v:58

    GTP_DFF_RE  #( .GRS_EN("TRUE"), .INIT(1'b0)) \rd_binary[6]  (
            .Q (rd_binary[6]),
            .CE (rd_en),
            .CLK (nt_pixclk_in),
            .D (next_rd[6]),
            .R (\rd_reset_sync[1]_inv_1 ));
	// ../../../compiled/rtl/video_async_fifo.v:58

    GTP_DFF_RE  #( .GRS_EN("TRUE"), .INIT(1'b0)) \rd_binary[7]  (
            .Q (rd_binary[7]),
            .CE (rd_en),
            .CLK (nt_pixclk_in),
            .D (next_rd[7]),
            .R (\rd_reset_sync[1]_inv_1 ));
	// ../../../compiled/rtl/video_async_fifo.v:58

    GTP_DFF_RE  #( .GRS_EN("TRUE"), .INIT(1'b0)) \rd_binary[8]  (
            .Q (rd_binary[8]),
            .CE (rd_en),
            .CLK (nt_pixclk_in),
            .D (next_rd[8]),
            .R (\rd_reset_sync[1]_inv_1 ));
	// ../../../compiled/rtl/video_async_fifo.v:58

    GTP_LUT1  #( .INIT(2'b01)) \rd_binary[9:0]_inv  (
            .Z (\rd_binary[0]_inv ),
            .I0 (rd_binary[0]));
	// LUT = ~I0 ;

    GTP_DFF_RE  #( .GRS_EN("TRUE"), .INIT(1'b0)) \rd_binary[9]  (
            .Q (rd_binary[9]),
            .CE (rd_en),
            .CLK (nt_pixclk_in),
            .D (next_rd[9]),
            .R (\rd_reset_sync[1]_inv_1 ));
	// ../../../compiled/rtl/video_async_fifo.v:58

    GTP_DFF_RE  #( .GRS_EN("TRUE"), .INIT(1'b0)) \rd_gray[0]  (
            .Q (rd_gray[0]),
            .CE (rd_en),
            .CLK (nt_pixclk_in),
            .D (N134[0]),
            .R (\rd_reset_sync[1]_inv_1 ));
	// ../../../compiled/rtl/video_async_fifo.v:58
	// SDC constraint : (object CLK) (id 1025) (cell from) (11 : D:/f60-run/physical-i/compiled/board/gray-pointer-cdc.fdc)
	// SDC constraint : (object CLK) (id 1024) (cell from) (10 : D:/f60-run/physical-i/compiled/board/gray-pointer-cdc.fdc)

    GTP_DFF_RE  #( .GRS_EN("TRUE"), .INIT(1'b0)) \rd_gray[1]  (
            .Q (rd_gray[1]),
            .CE (rd_en),
            .CLK (nt_pixclk_in),
            .D (N134[1]),
            .R (\rd_reset_sync[1]_inv_1 ));
	// ../../../compiled/rtl/video_async_fifo.v:58
	// SDC constraint : (object CLK) (id 1025) (cell from) (11 : D:/f60-run/physical-i/compiled/board/gray-pointer-cdc.fdc)
	// SDC constraint : (object CLK) (id 1024) (cell from) (10 : D:/f60-run/physical-i/compiled/board/gray-pointer-cdc.fdc)

    GTP_DFF_RE  #( .GRS_EN("TRUE"), .INIT(1'b0)) \rd_gray[2]  (
            .Q (rd_gray[2]),
            .CE (rd_en),
            .CLK (nt_pixclk_in),
            .D (N134[2]),
            .R (\rd_reset_sync[1]_inv_1 ));
	// ../../../compiled/rtl/video_async_fifo.v:58
	// SDC constraint : (object CLK) (id 1025) (cell from) (11 : D:/f60-run/physical-i/compiled/board/gray-pointer-cdc.fdc)
	// SDC constraint : (object CLK) (id 1024) (cell from) (10 : D:/f60-run/physical-i/compiled/board/gray-pointer-cdc.fdc)

    GTP_DFF_RE  #( .GRS_EN("TRUE"), .INIT(1'b0)) \rd_gray[3]  (
            .Q (rd_gray[3]),
            .CE (rd_en),
            .CLK (nt_pixclk_in),
            .D (N134[3]),
            .R (\rd_reset_sync[1]_inv_1 ));
	// ../../../compiled/rtl/video_async_fifo.v:58
	// SDC constraint : (object CLK) (id 1025) (cell from) (11 : D:/f60-run/physical-i/compiled/board/gray-pointer-cdc.fdc)
	// SDC constraint : (object CLK) (id 1024) (cell from) (10 : D:/f60-run/physical-i/compiled/board/gray-pointer-cdc.fdc)

    GTP_DFF_RE  #( .GRS_EN("TRUE"), .INIT(1'b0)) \rd_gray[4]  (
            .Q (rd_gray[4]),
            .CE (rd_en),
            .CLK (nt_pixclk_in),
            .D (N134[4]),
            .R (\rd_reset_sync[1]_inv_1 ));
	// ../../../compiled/rtl/video_async_fifo.v:58
	// SDC constraint : (object CLK) (id 1025) (cell from) (11 : D:/f60-run/physical-i/compiled/board/gray-pointer-cdc.fdc)
	// SDC constraint : (object CLK) (id 1024) (cell from) (10 : D:/f60-run/physical-i/compiled/board/gray-pointer-cdc.fdc)

    GTP_DFF_RE  #( .GRS_EN("TRUE"), .INIT(1'b0)) \rd_gray[5]  (
            .Q (rd_gray[5]),
            .CE (rd_en),
            .CLK (nt_pixclk_in),
            .D (N134[5]),
            .R (\rd_reset_sync[1]_inv_1 ));
	// ../../../compiled/rtl/video_async_fifo.v:58
	// SDC constraint : (object CLK) (id 1025) (cell from) (11 : D:/f60-run/physical-i/compiled/board/gray-pointer-cdc.fdc)
	// SDC constraint : (object CLK) (id 1024) (cell from) (10 : D:/f60-run/physical-i/compiled/board/gray-pointer-cdc.fdc)

    GTP_DFF_RE  #( .GRS_EN("TRUE"), .INIT(1'b0)) \rd_gray[6]  (
            .Q (rd_gray[6]),
            .CE (rd_en),
            .CLK (nt_pixclk_in),
            .D (N134[6]),
            .R (\rd_reset_sync[1]_inv_1 ));
	// ../../../compiled/rtl/video_async_fifo.v:58
	// SDC constraint : (object CLK) (id 1025) (cell from) (11 : D:/f60-run/physical-i/compiled/board/gray-pointer-cdc.fdc)
	// SDC constraint : (object CLK) (id 1024) (cell from) (10 : D:/f60-run/physical-i/compiled/board/gray-pointer-cdc.fdc)

    GTP_DFF_RE  #( .GRS_EN("TRUE"), .INIT(1'b0)) \rd_gray[7]  (
            .Q (rd_gray[7]),
            .CE (rd_en),
            .CLK (nt_pixclk_in),
            .D (N134[7]),
            .R (\rd_reset_sync[1]_inv_1 ));
	// ../../../compiled/rtl/video_async_fifo.v:58
	// SDC constraint : (object CLK) (id 1025) (cell from) (11 : D:/f60-run/physical-i/compiled/board/gray-pointer-cdc.fdc)
	// SDC constraint : (object CLK) (id 1024) (cell from) (10 : D:/f60-run/physical-i/compiled/board/gray-pointer-cdc.fdc)

    GTP_DFF_RE  #( .GRS_EN("TRUE"), .INIT(1'b0)) \rd_gray[8]  (
            .Q (rd_gray[8]),
            .CE (rd_en),
            .CLK (nt_pixclk_in),
            .D (N134[8]),
            .R (\rd_reset_sync[1]_inv_1 ));
	// ../../../compiled/rtl/video_async_fifo.v:58
	// SDC constraint : (object CLK) (id 1025) (cell from) (11 : D:/f60-run/physical-i/compiled/board/gray-pointer-cdc.fdc)
	// SDC constraint : (object CLK) (id 1024) (cell from) (10 : D:/f60-run/physical-i/compiled/board/gray-pointer-cdc.fdc)

    GTP_DFF_RE  #( .GRS_EN("TRUE"), .INIT(1'b0)) \rd_gray[9]  (
            .Q (rd_gray[9]),
            .CE (rd_en),
            .CLK (nt_pixclk_in),
            .D (next_rd[9]),
            .R (\rd_reset_sync[1]_inv_1 ));
	// ../../../compiled/rtl/video_async_fifo.v:58
	// SDC constraint : (object CLK) (id 1025) (cell from) (11 : D:/f60-run/physical-i/compiled/board/gray-pointer-cdc.fdc)
	// SDC constraint : (object CLK) (id 1024) (cell from) (10 : D:/f60-run/physical-i/compiled/board/gray-pointer-cdc.fdc)

(* PAP_ASYNC_REG="TRUE", PAP_SRL_STYLE="registers" *)    GTP_DFF_R  #( .GRS_EN("TRUE"), .INIT(1'b0)) \rd_gray_w1[0]  (
            .Q (rd_gray_w1[0]),
            .CLK (wr_clk),
            .D (rd_gray[0]),
            .R (\core_reset[1]_inv_1 ));
	// ../../../compiled/rtl/video_async_fifo.v:48
	// SDC constraint : (object D) (id 1025) (cell to) (11 : D:/f60-run/physical-i/compiled/board/gray-pointer-cdc.fdc)
	// SDC constraint : (object D) (id 1024) (cell to) (10 : D:/f60-run/physical-i/compiled/board/gray-pointer-cdc.fdc)
	// SDC constraint : (object R) (id 1025) (cell to) (11 : D:/f60-run/physical-i/compiled/board/gray-pointer-cdc.fdc)
	// SDC constraint : (object R) (id 1024) (cell to) (10 : D:/f60-run/physical-i/compiled/board/gray-pointer-cdc.fdc)

(* PAP_ASYNC_REG="TRUE", PAP_SRL_STYLE="registers" *)    GTP_DFF_R  #( .GRS_EN("TRUE"), .INIT(1'b0)) \rd_gray_w1[1]  (
            .Q (rd_gray_w1[1]),
            .CLK (wr_clk),
            .D (rd_gray[1]),
            .R (\core_reset[1]_inv_1 ));
	// ../../../compiled/rtl/video_async_fifo.v:48
	// SDC constraint : (object D) (id 1025) (cell to) (11 : D:/f60-run/physical-i/compiled/board/gray-pointer-cdc.fdc)
	// SDC constraint : (object D) (id 1024) (cell to) (10 : D:/f60-run/physical-i/compiled/board/gray-pointer-cdc.fdc)
	// SDC constraint : (object R) (id 1025) (cell to) (11 : D:/f60-run/physical-i/compiled/board/gray-pointer-cdc.fdc)
	// SDC constraint : (object R) (id 1024) (cell to) (10 : D:/f60-run/physical-i/compiled/board/gray-pointer-cdc.fdc)

(* PAP_ASYNC_REG="TRUE", PAP_SRL_STYLE="registers" *)    GTP_DFF_R  #( .GRS_EN("TRUE"), .INIT(1'b0)) \rd_gray_w1[2]  (
            .Q (rd_gray_w1[2]),
            .CLK (wr_clk),
            .D (rd_gray[2]),
            .R (\core_reset[1]_inv_1 ));
	// ../../../compiled/rtl/video_async_fifo.v:48
	// SDC constraint : (object D) (id 1025) (cell to) (11 : D:/f60-run/physical-i/compiled/board/gray-pointer-cdc.fdc)
	// SDC constraint : (object D) (id 1024) (cell to) (10 : D:/f60-run/physical-i/compiled/board/gray-pointer-cdc.fdc)
	// SDC constraint : (object R) (id 1025) (cell to) (11 : D:/f60-run/physical-i/compiled/board/gray-pointer-cdc.fdc)
	// SDC constraint : (object R) (id 1024) (cell to) (10 : D:/f60-run/physical-i/compiled/board/gray-pointer-cdc.fdc)

(* PAP_ASYNC_REG="TRUE", PAP_SRL_STYLE="registers" *)    GTP_DFF_R  #( .GRS_EN("TRUE"), .INIT(1'b0)) \rd_gray_w1[3]  (
            .Q (rd_gray_w1[3]),
            .CLK (wr_clk),
            .D (rd_gray[3]),
            .R (\core_reset[1]_inv_1 ));
	// ../../../compiled/rtl/video_async_fifo.v:48
	// SDC constraint : (object D) (id 1025) (cell to) (11 : D:/f60-run/physical-i/compiled/board/gray-pointer-cdc.fdc)
	// SDC constraint : (object D) (id 1024) (cell to) (10 : D:/f60-run/physical-i/compiled/board/gray-pointer-cdc.fdc)
	// SDC constraint : (object R) (id 1025) (cell to) (11 : D:/f60-run/physical-i/compiled/board/gray-pointer-cdc.fdc)
	// SDC constraint : (object R) (id 1024) (cell to) (10 : D:/f60-run/physical-i/compiled/board/gray-pointer-cdc.fdc)

(* PAP_ASYNC_REG="TRUE", PAP_SRL_STYLE="registers" *)    GTP_DFF_R  #( .GRS_EN("TRUE"), .INIT(1'b0)) \rd_gray_w1[4]  (
            .Q (rd_gray_w1[4]),
            .CLK (wr_clk),
            .D (rd_gray[4]),
            .R (\core_reset[1]_inv_1 ));
	// ../../../compiled/rtl/video_async_fifo.v:48
	// SDC constraint : (object D) (id 1025) (cell to) (11 : D:/f60-run/physical-i/compiled/board/gray-pointer-cdc.fdc)
	// SDC constraint : (object D) (id 1024) (cell to) (10 : D:/f60-run/physical-i/compiled/board/gray-pointer-cdc.fdc)
	// SDC constraint : (object R) (id 1025) (cell to) (11 : D:/f60-run/physical-i/compiled/board/gray-pointer-cdc.fdc)
	// SDC constraint : (object R) (id 1024) (cell to) (10 : D:/f60-run/physical-i/compiled/board/gray-pointer-cdc.fdc)

(* PAP_ASYNC_REG="TRUE", PAP_SRL_STYLE="registers" *)    GTP_DFF_R  #( .GRS_EN("TRUE"), .INIT(1'b0)) \rd_gray_w1[5]  (
            .Q (rd_gray_w1[5]),
            .CLK (wr_clk),
            .D (rd_gray[5]),
            .R (\core_reset[1]_inv_1 ));
	// ../../../compiled/rtl/video_async_fifo.v:48
	// SDC constraint : (object D) (id 1025) (cell to) (11 : D:/f60-run/physical-i/compiled/board/gray-pointer-cdc.fdc)
	// SDC constraint : (object D) (id 1024) (cell to) (10 : D:/f60-run/physical-i/compiled/board/gray-pointer-cdc.fdc)
	// SDC constraint : (object R) (id 1025) (cell to) (11 : D:/f60-run/physical-i/compiled/board/gray-pointer-cdc.fdc)
	// SDC constraint : (object R) (id 1024) (cell to) (10 : D:/f60-run/physical-i/compiled/board/gray-pointer-cdc.fdc)

(* PAP_ASYNC_REG="TRUE", PAP_SRL_STYLE="registers" *)    GTP_DFF_R  #( .GRS_EN("TRUE"), .INIT(1'b0)) \rd_gray_w1[6]  (
            .Q (rd_gray_w1[6]),
            .CLK (wr_clk),
            .D (rd_gray[6]),
            .R (\core_reset[1]_inv_1 ));
	// ../../../compiled/rtl/video_async_fifo.v:48
	// SDC constraint : (object D) (id 1025) (cell to) (11 : D:/f60-run/physical-i/compiled/board/gray-pointer-cdc.fdc)
	// SDC constraint : (object D) (id 1024) (cell to) (10 : D:/f60-run/physical-i/compiled/board/gray-pointer-cdc.fdc)
	// SDC constraint : (object R) (id 1025) (cell to) (11 : D:/f60-run/physical-i/compiled/board/gray-pointer-cdc.fdc)
	// SDC constraint : (object R) (id 1024) (cell to) (10 : D:/f60-run/physical-i/compiled/board/gray-pointer-cdc.fdc)

(* PAP_ASYNC_REG="TRUE", PAP_SRL_STYLE="registers" *)    GTP_DFF_R  #( .GRS_EN("TRUE"), .INIT(1'b0)) \rd_gray_w1[7]  (
            .Q (rd_gray_w1[7]),
            .CLK (wr_clk),
            .D (rd_gray[7]),
            .R (\core_reset[1]_inv_1 ));
	// ../../../compiled/rtl/video_async_fifo.v:48
	// SDC constraint : (object D) (id 1025) (cell to) (11 : D:/f60-run/physical-i/compiled/board/gray-pointer-cdc.fdc)
	// SDC constraint : (object D) (id 1024) (cell to) (10 : D:/f60-run/physical-i/compiled/board/gray-pointer-cdc.fdc)
	// SDC constraint : (object R) (id 1025) (cell to) (11 : D:/f60-run/physical-i/compiled/board/gray-pointer-cdc.fdc)
	// SDC constraint : (object R) (id 1024) (cell to) (10 : D:/f60-run/physical-i/compiled/board/gray-pointer-cdc.fdc)

(* PAP_ASYNC_REG="TRUE", PAP_SRL_STYLE="registers" *)    GTP_DFF_R  #( .GRS_EN("TRUE"), .INIT(1'b0)) \rd_gray_w1[8]  (
            .Q (rd_gray_w1[8]),
            .CLK (wr_clk),
            .D (rd_gray[8]),
            .R (\core_reset[1]_inv_1 ));
	// ../../../compiled/rtl/video_async_fifo.v:48
	// SDC constraint : (object D) (id 1025) (cell to) (11 : D:/f60-run/physical-i/compiled/board/gray-pointer-cdc.fdc)
	// SDC constraint : (object D) (id 1024) (cell to) (10 : D:/f60-run/physical-i/compiled/board/gray-pointer-cdc.fdc)
	// SDC constraint : (object R) (id 1025) (cell to) (11 : D:/f60-run/physical-i/compiled/board/gray-pointer-cdc.fdc)
	// SDC constraint : (object R) (id 1024) (cell to) (10 : D:/f60-run/physical-i/compiled/board/gray-pointer-cdc.fdc)

(* PAP_ASYNC_REG="TRUE", PAP_SRL_STYLE="registers" *)    GTP_DFF_R  #( .GRS_EN("TRUE"), .INIT(1'b0)) \rd_gray_w1[9]  (
            .Q (rd_gray_w1[9]),
            .CLK (wr_clk),
            .D (rd_gray[9]),
            .R (\core_reset[1]_inv_1 ));
	// ../../../compiled/rtl/video_async_fifo.v:48
	// SDC constraint : (object D) (id 1025) (cell to) (11 : D:/f60-run/physical-i/compiled/board/gray-pointer-cdc.fdc)
	// SDC constraint : (object D) (id 1024) (cell to) (10 : D:/f60-run/physical-i/compiled/board/gray-pointer-cdc.fdc)
	// SDC constraint : (object R) (id 1025) (cell to) (11 : D:/f60-run/physical-i/compiled/board/gray-pointer-cdc.fdc)
	// SDC constraint : (object R) (id 1024) (cell to) (10 : D:/f60-run/physical-i/compiled/board/gray-pointer-cdc.fdc)

(* PAP_ASYNC_REG="TRUE", PAP_SRL_STYLE="registers" *)    GTP_DFF_R  #( .GRS_EN("TRUE"), .INIT(1'b0)) \rd_gray_w2[0]  (
            .Q (rd_gray_w2[0]),
            .CLK (wr_clk),
            .D (rd_gray_w1[0]),
            .R (\core_reset[1]_inv_1 ));
	// ../../../compiled/rtl/video_async_fifo.v:48

(* PAP_ASYNC_REG="TRUE", PAP_SRL_STYLE="registers" *)    GTP_DFF_R  #( .GRS_EN("TRUE"), .INIT(1'b0)) \rd_gray_w2[1]  (
            .Q (rd_gray_w2[1]),
            .CLK (wr_clk),
            .D (rd_gray_w1[1]),
            .R (\core_reset[1]_inv_1 ));
	// ../../../compiled/rtl/video_async_fifo.v:48

(* PAP_ASYNC_REG="TRUE", PAP_SRL_STYLE="registers" *)    GTP_DFF_R  #( .GRS_EN("TRUE"), .INIT(1'b0)) \rd_gray_w2[2]  (
            .Q (rd_gray_w2[2]),
            .CLK (wr_clk),
            .D (rd_gray_w1[2]),
            .R (\core_reset[1]_inv_1 ));
	// ../../../compiled/rtl/video_async_fifo.v:48

(* PAP_ASYNC_REG="TRUE", PAP_SRL_STYLE="registers" *)    GTP_DFF_R  #( .GRS_EN("TRUE"), .INIT(1'b0)) \rd_gray_w2[3]  (
            .Q (rd_gray_w2[3]),
            .CLK (wr_clk),
            .D (rd_gray_w1[3]),
            .R (\core_reset[1]_inv_1 ));
	// ../../../compiled/rtl/video_async_fifo.v:48

(* PAP_ASYNC_REG="TRUE", PAP_SRL_STYLE="registers" *)    GTP_DFF_R  #( .GRS_EN("TRUE"), .INIT(1'b0)) \rd_gray_w2[4]  (
            .Q (rd_gray_w2[4]),
            .CLK (wr_clk),
            .D (rd_gray_w1[4]),
            .R (\core_reset[1]_inv_1 ));
	// ../../../compiled/rtl/video_async_fifo.v:48

(* PAP_ASYNC_REG="TRUE", PAP_SRL_STYLE="registers" *)    GTP_DFF_R  #( .GRS_EN("TRUE"), .INIT(1'b0)) \rd_gray_w2[5]  (
            .Q (rd_gray_w2[5]),
            .CLK (wr_clk),
            .D (rd_gray_w1[5]),
            .R (\core_reset[1]_inv_1 ));
	// ../../../compiled/rtl/video_async_fifo.v:48

(* PAP_ASYNC_REG="TRUE", PAP_SRL_STYLE="registers" *)    GTP_DFF_R  #( .GRS_EN("TRUE"), .INIT(1'b0)) \rd_gray_w2[6]  (
            .Q (rd_gray_w2[6]),
            .CLK (wr_clk),
            .D (rd_gray_w1[6]),
            .R (\core_reset[1]_inv_1 ));
	// ../../../compiled/rtl/video_async_fifo.v:48

(* PAP_ASYNC_REG="TRUE", PAP_SRL_STYLE="registers" *)    GTP_DFF_R  #( .GRS_EN("TRUE"), .INIT(1'b0)) \rd_gray_w2[7]  (
            .Q (rd_gray_w2[7]),
            .CLK (wr_clk),
            .D (rd_gray_w1[7]),
            .R (\core_reset[1]_inv_1 ));
	// ../../../compiled/rtl/video_async_fifo.v:48

(* PAP_ASYNC_REG="TRUE", PAP_SRL_STYLE="registers" *)    GTP_DFF_R  #( .GRS_EN("TRUE"), .INIT(1'b0)) \rd_gray_w2[8]  (
            .Q (rd_gray_w2[8]),
            .CLK (wr_clk),
            .D (rd_gray_w1[8]),
            .R (\core_reset[1]_inv_1 ));
	// ../../../compiled/rtl/video_async_fifo.v:48

(* PAP_ASYNC_REG="TRUE", PAP_SRL_STYLE="registers" *)    GTP_DFF_R  #( .GRS_EN("TRUE"), .INIT(1'b0)) \rd_gray_w2[9]  (
            .Q (rd_gray_w2[9]),
            .CLK (wr_clk),
            .D (rd_gray_w1[9]),
            .R (\core_reset[1]_inv_1 ));
	// ../../../compiled/rtl/video_async_fifo.v:48

(* PAP_ASYNC_REG="TRUE", PAP_SRL_STYLE="registers" *)    GTP_DFF_C  #( .GRS_EN("TRUE"), .INIT(1'b0)) \rd_reset_sync[0]  (
            .Q (rd_reset_sync[0]),
            .C (rst_n_inv),
            .CLK (nt_pixclk_in),
            .D (1'b1));
	// ../../../compiled/rtl/video_async_fifo.v:26

(* PAP_ASYNC_REG="TRUE", PAP_SRL_STYLE="registers" *)    GTP_DFF_C  #( .GRS_EN("TRUE"), .INIT(1'b0)) \rd_reset_sync[1]  (
            .Q (rd_reset_sync[1]),
            .C (rst_n_inv),
            .CLK (nt_pixclk_in),
            .D (rd_reset_sync[0]));
	// ../../../compiled/rtl/video_async_fifo.v:26

    GTP_INV \rd_reset_sync[1]_inv_1_vname  (
            .Z (\rd_reset_sync[1]_inv_1 ),
            .I (rd_reset_sync[1]));

    GTP_DFF_R  #( .GRS_EN("TRUE"), .INIT(1'b0)) rd_valid_vname (
            .Q (rd_valid),
            .CLK (nt_pixclk_in),
            .D (rd_en),
            .R (\rd_reset_sync[1]_inv_1 ));
	// ../../../compiled/rtl/video_async_fifo.v:58

    GTP_DFF_RE  #( .GRS_EN("TRUE"), .INIT(1'b0)) \wr_binary[0]  (
            .Q (wr_binary[0]),
            .CE (N107),
            .CLK (wr_clk),
            .D (\wr_binary[0]_inv ),
            .R (\core_reset[1]_inv_1 ));
	// ../../../compiled/rtl/video_async_fifo.v:48

    GTP_DFF_RE  #( .GRS_EN("TRUE"), .INIT(1'b0)) \wr_binary[1]  (
            .Q (wr_binary[1]),
            .CE (N107),
            .CLK (wr_clk),
            .D (next_wr[1]),
            .R (\core_reset[1]_inv_1 ));
	// ../../../compiled/rtl/video_async_fifo.v:48

    GTP_DFF_RE  #( .GRS_EN("TRUE"), .INIT(1'b0)) \wr_binary[2]  (
            .Q (wr_binary[2]),
            .CE (N107),
            .CLK (wr_clk),
            .D (next_wr[2]),
            .R (\core_reset[1]_inv_1 ));
	// ../../../compiled/rtl/video_async_fifo.v:48

    GTP_DFF_RE  #( .GRS_EN("TRUE"), .INIT(1'b0)) \wr_binary[3]  (
            .Q (wr_binary[3]),
            .CE (N107),
            .CLK (wr_clk),
            .D (next_wr[3]),
            .R (\core_reset[1]_inv_1 ));
	// ../../../compiled/rtl/video_async_fifo.v:48

    GTP_DFF_RE  #( .GRS_EN("TRUE"), .INIT(1'b0)) \wr_binary[4]  (
            .Q (wr_binary[4]),
            .CE (N107),
            .CLK (wr_clk),
            .D (next_wr[4]),
            .R (\core_reset[1]_inv_1 ));
	// ../../../compiled/rtl/video_async_fifo.v:48

    GTP_DFF_RE  #( .GRS_EN("TRUE"), .INIT(1'b0)) \wr_binary[5]  (
            .Q (wr_binary[5]),
            .CE (N107),
            .CLK (wr_clk),
            .D (next_wr[5]),
            .R (\core_reset[1]_inv_1 ));
	// ../../../compiled/rtl/video_async_fifo.v:48

    GTP_DFF_RE  #( .GRS_EN("TRUE"), .INIT(1'b0)) \wr_binary[6]  (
            .Q (wr_binary[6]),
            .CE (N107),
            .CLK (wr_clk),
            .D (next_wr[6]),
            .R (\core_reset[1]_inv_1 ));
	// ../../../compiled/rtl/video_async_fifo.v:48

    GTP_DFF_RE  #( .GRS_EN("TRUE"), .INIT(1'b0)) \wr_binary[7]  (
            .Q (wr_binary[7]),
            .CE (N107),
            .CLK (wr_clk),
            .D (next_wr[7]),
            .R (\core_reset[1]_inv_1 ));
	// ../../../compiled/rtl/video_async_fifo.v:48

    GTP_DFF_RE  #( .GRS_EN("TRUE"), .INIT(1'b0)) \wr_binary[8]  (
            .Q (wr_binary[8]),
            .CE (N107),
            .CLK (wr_clk),
            .D (next_wr[8]),
            .R (\core_reset[1]_inv_1 ));
	// ../../../compiled/rtl/video_async_fifo.v:48

    GTP_LUT1  #( .INIT(2'b01)) \wr_binary[9:0]_inv  (
            .Z (\wr_binary[0]_inv ),
            .I0 (wr_binary[0]));
	// LUT = ~I0 ;

    GTP_DFF_RE  #( .GRS_EN("TRUE"), .INIT(1'b0)) \wr_binary[9]  (
            .Q (wr_binary[9]),
            .CE (N107),
            .CLK (wr_clk),
            .D (next_wr[9]),
            .R (\core_reset[1]_inv_1 ));
	// ../../../compiled/rtl/video_async_fifo.v:48

    GTP_DFF_RE  #( .GRS_EN("TRUE"), .INIT(1'b0)) \wr_gray[0]  (
            .Q (wr_gray[0]),
            .CE (N107),
            .CLK (wr_clk),
            .D (N112[0]),
            .R (\core_reset[1]_inv_1 ));
	// ../../../compiled/rtl/video_async_fifo.v:48
	// SDC constraint : (object CLK) (id 1027) (cell from) (13 : D:/f60-run/physical-i/compiled/board/gray-pointer-cdc.fdc)
	// SDC constraint : (object CLK) (id 1026) (cell from) (12 : D:/f60-run/physical-i/compiled/board/gray-pointer-cdc.fdc)

    GTP_DFF_RE  #( .GRS_EN("TRUE"), .INIT(1'b0)) \wr_gray[1]  (
            .Q (wr_gray[1]),
            .CE (N107),
            .CLK (wr_clk),
            .D (N112[1]),
            .R (\core_reset[1]_inv_1 ));
	// ../../../compiled/rtl/video_async_fifo.v:48
	// SDC constraint : (object CLK) (id 1027) (cell from) (13 : D:/f60-run/physical-i/compiled/board/gray-pointer-cdc.fdc)
	// SDC constraint : (object CLK) (id 1026) (cell from) (12 : D:/f60-run/physical-i/compiled/board/gray-pointer-cdc.fdc)

    GTP_DFF_RE  #( .GRS_EN("TRUE"), .INIT(1'b0)) \wr_gray[2]  (
            .Q (wr_gray[2]),
            .CE (N107),
            .CLK (wr_clk),
            .D (N112[2]),
            .R (\core_reset[1]_inv_1 ));
	// ../../../compiled/rtl/video_async_fifo.v:48
	// SDC constraint : (object CLK) (id 1027) (cell from) (13 : D:/f60-run/physical-i/compiled/board/gray-pointer-cdc.fdc)
	// SDC constraint : (object CLK) (id 1026) (cell from) (12 : D:/f60-run/physical-i/compiled/board/gray-pointer-cdc.fdc)

    GTP_DFF_RE  #( .GRS_EN("TRUE"), .INIT(1'b0)) \wr_gray[3]  (
            .Q (wr_gray[3]),
            .CE (N107),
            .CLK (wr_clk),
            .D (N112[3]),
            .R (\core_reset[1]_inv_1 ));
	// ../../../compiled/rtl/video_async_fifo.v:48
	// SDC constraint : (object CLK) (id 1027) (cell from) (13 : D:/f60-run/physical-i/compiled/board/gray-pointer-cdc.fdc)
	// SDC constraint : (object CLK) (id 1026) (cell from) (12 : D:/f60-run/physical-i/compiled/board/gray-pointer-cdc.fdc)

    GTP_DFF_RE  #( .GRS_EN("TRUE"), .INIT(1'b0)) \wr_gray[4]  (
            .Q (wr_gray[4]),
            .CE (N107),
            .CLK (wr_clk),
            .D (N112[4]),
            .R (\core_reset[1]_inv_1 ));
	// ../../../compiled/rtl/video_async_fifo.v:48
	// SDC constraint : (object CLK) (id 1027) (cell from) (13 : D:/f60-run/physical-i/compiled/board/gray-pointer-cdc.fdc)
	// SDC constraint : (object CLK) (id 1026) (cell from) (12 : D:/f60-run/physical-i/compiled/board/gray-pointer-cdc.fdc)

    GTP_DFF_RE  #( .GRS_EN("TRUE"), .INIT(1'b0)) \wr_gray[5]  (
            .Q (wr_gray[5]),
            .CE (N107),
            .CLK (wr_clk),
            .D (N112[5]),
            .R (\core_reset[1]_inv_1 ));
	// ../../../compiled/rtl/video_async_fifo.v:48
	// SDC constraint : (object CLK) (id 1027) (cell from) (13 : D:/f60-run/physical-i/compiled/board/gray-pointer-cdc.fdc)
	// SDC constraint : (object CLK) (id 1026) (cell from) (12 : D:/f60-run/physical-i/compiled/board/gray-pointer-cdc.fdc)

    GTP_DFF_RE  #( .GRS_EN("TRUE"), .INIT(1'b0)) \wr_gray[6]  (
            .Q (wr_gray[6]),
            .CE (N107),
            .CLK (wr_clk),
            .D (N112[6]),
            .R (\core_reset[1]_inv_1 ));
	// ../../../compiled/rtl/video_async_fifo.v:48
	// SDC constraint : (object CLK) (id 1027) (cell from) (13 : D:/f60-run/physical-i/compiled/board/gray-pointer-cdc.fdc)
	// SDC constraint : (object CLK) (id 1026) (cell from) (12 : D:/f60-run/physical-i/compiled/board/gray-pointer-cdc.fdc)

    GTP_DFF_RE  #( .GRS_EN("TRUE"), .INIT(1'b0)) \wr_gray[7]  (
            .Q (wr_gray[7]),
            .CE (N107),
            .CLK (wr_clk),
            .D (N112[7]),
            .R (\core_reset[1]_inv_1 ));
	// ../../../compiled/rtl/video_async_fifo.v:48
	// SDC constraint : (object CLK) (id 1027) (cell from) (13 : D:/f60-run/physical-i/compiled/board/gray-pointer-cdc.fdc)
	// SDC constraint : (object CLK) (id 1026) (cell from) (12 : D:/f60-run/physical-i/compiled/board/gray-pointer-cdc.fdc)

    GTP_DFF_RE  #( .GRS_EN("TRUE"), .INIT(1'b0)) \wr_gray[8]  (
            .Q (wr_gray[8]),
            .CE (N107),
            .CLK (wr_clk),
            .D (N112[8]),
            .R (\core_reset[1]_inv_1 ));
	// ../../../compiled/rtl/video_async_fifo.v:48
	// SDC constraint : (object CLK) (id 1027) (cell from) (13 : D:/f60-run/physical-i/compiled/board/gray-pointer-cdc.fdc)
	// SDC constraint : (object CLK) (id 1026) (cell from) (12 : D:/f60-run/physical-i/compiled/board/gray-pointer-cdc.fdc)

    GTP_DFF_RE  #( .GRS_EN("TRUE"), .INIT(1'b0)) \wr_gray[9]  (
            .Q (wr_gray[9]),
            .CE (N107),
            .CLK (wr_clk),
            .D (next_wr[9]),
            .R (\core_reset[1]_inv_1 ));
	// ../../../compiled/rtl/video_async_fifo.v:48
	// SDC constraint : (object CLK) (id 1027) (cell from) (13 : D:/f60-run/physical-i/compiled/board/gray-pointer-cdc.fdc)
	// SDC constraint : (object CLK) (id 1026) (cell from) (12 : D:/f60-run/physical-i/compiled/board/gray-pointer-cdc.fdc)

(* PAP_ASYNC_REG="TRUE", PAP_SRL_STYLE="registers" *)    GTP_DFF_R  #( .GRS_EN("TRUE"), .INIT(1'b0)) \wr_gray_r1[0]  (
            .Q (wr_gray_r1[0]),
            .CLK (nt_pixclk_in),
            .D (wr_gray[0]),
            .R (\rd_reset_sync[1]_inv_1 ));
	// ../../../compiled/rtl/video_async_fifo.v:58
	// SDC constraint : (object D) (id 1027) (cell to) (13 : D:/f60-run/physical-i/compiled/board/gray-pointer-cdc.fdc)
	// SDC constraint : (object D) (id 1026) (cell to) (12 : D:/f60-run/physical-i/compiled/board/gray-pointer-cdc.fdc)
	// SDC constraint : (object R) (id 1027) (cell to) (13 : D:/f60-run/physical-i/compiled/board/gray-pointer-cdc.fdc)
	// SDC constraint : (object R) (id 1026) (cell to) (12 : D:/f60-run/physical-i/compiled/board/gray-pointer-cdc.fdc)

(* PAP_ASYNC_REG="TRUE", PAP_SRL_STYLE="registers" *)    GTP_DFF_R  #( .GRS_EN("TRUE"), .INIT(1'b0)) \wr_gray_r1[1]  (
            .Q (wr_gray_r1[1]),
            .CLK (nt_pixclk_in),
            .D (wr_gray[1]),
            .R (\rd_reset_sync[1]_inv_1 ));
	// ../../../compiled/rtl/video_async_fifo.v:58
	// SDC constraint : (object D) (id 1027) (cell to) (13 : D:/f60-run/physical-i/compiled/board/gray-pointer-cdc.fdc)
	// SDC constraint : (object D) (id 1026) (cell to) (12 : D:/f60-run/physical-i/compiled/board/gray-pointer-cdc.fdc)
	// SDC constraint : (object R) (id 1027) (cell to) (13 : D:/f60-run/physical-i/compiled/board/gray-pointer-cdc.fdc)
	// SDC constraint : (object R) (id 1026) (cell to) (12 : D:/f60-run/physical-i/compiled/board/gray-pointer-cdc.fdc)

(* PAP_ASYNC_REG="TRUE", PAP_SRL_STYLE="registers" *)    GTP_DFF_R  #( .GRS_EN("TRUE"), .INIT(1'b0)) \wr_gray_r1[2]  (
            .Q (wr_gray_r1[2]),
            .CLK (nt_pixclk_in),
            .D (wr_gray[2]),
            .R (\rd_reset_sync[1]_inv_1 ));
	// ../../../compiled/rtl/video_async_fifo.v:58
	// SDC constraint : (object D) (id 1027) (cell to) (13 : D:/f60-run/physical-i/compiled/board/gray-pointer-cdc.fdc)
	// SDC constraint : (object D) (id 1026) (cell to) (12 : D:/f60-run/physical-i/compiled/board/gray-pointer-cdc.fdc)
	// SDC constraint : (object R) (id 1027) (cell to) (13 : D:/f60-run/physical-i/compiled/board/gray-pointer-cdc.fdc)
	// SDC constraint : (object R) (id 1026) (cell to) (12 : D:/f60-run/physical-i/compiled/board/gray-pointer-cdc.fdc)

(* PAP_ASYNC_REG="TRUE", PAP_SRL_STYLE="registers" *)    GTP_DFF_R  #( .GRS_EN("TRUE"), .INIT(1'b0)) \wr_gray_r1[3]  (
            .Q (wr_gray_r1[3]),
            .CLK (nt_pixclk_in),
            .D (wr_gray[3]),
            .R (\rd_reset_sync[1]_inv_1 ));
	// ../../../compiled/rtl/video_async_fifo.v:58
	// SDC constraint : (object D) (id 1027) (cell to) (13 : D:/f60-run/physical-i/compiled/board/gray-pointer-cdc.fdc)
	// SDC constraint : (object D) (id 1026) (cell to) (12 : D:/f60-run/physical-i/compiled/board/gray-pointer-cdc.fdc)
	// SDC constraint : (object R) (id 1027) (cell to) (13 : D:/f60-run/physical-i/compiled/board/gray-pointer-cdc.fdc)
	// SDC constraint : (object R) (id 1026) (cell to) (12 : D:/f60-run/physical-i/compiled/board/gray-pointer-cdc.fdc)

(* PAP_ASYNC_REG="TRUE", PAP_SRL_STYLE="registers" *)    GTP_DFF_R  #( .GRS_EN("TRUE"), .INIT(1'b0)) \wr_gray_r1[4]  (
            .Q (wr_gray_r1[4]),
            .CLK (nt_pixclk_in),
            .D (wr_gray[4]),
            .R (\rd_reset_sync[1]_inv_1 ));
	// ../../../compiled/rtl/video_async_fifo.v:58
	// SDC constraint : (object D) (id 1027) (cell to) (13 : D:/f60-run/physical-i/compiled/board/gray-pointer-cdc.fdc)
	// SDC constraint : (object D) (id 1026) (cell to) (12 : D:/f60-run/physical-i/compiled/board/gray-pointer-cdc.fdc)
	// SDC constraint : (object R) (id 1027) (cell to) (13 : D:/f60-run/physical-i/compiled/board/gray-pointer-cdc.fdc)
	// SDC constraint : (object R) (id 1026) (cell to) (12 : D:/f60-run/physical-i/compiled/board/gray-pointer-cdc.fdc)

(* PAP_ASYNC_REG="TRUE", PAP_SRL_STYLE="registers" *)    GTP_DFF_R  #( .GRS_EN("TRUE"), .INIT(1'b0)) \wr_gray_r1[5]  (
            .Q (wr_gray_r1[5]),
            .CLK (nt_pixclk_in),
            .D (wr_gray[5]),
            .R (\rd_reset_sync[1]_inv_1 ));
	// ../../../compiled/rtl/video_async_fifo.v:58
	// SDC constraint : (object D) (id 1027) (cell to) (13 : D:/f60-run/physical-i/compiled/board/gray-pointer-cdc.fdc)
	// SDC constraint : (object D) (id 1026) (cell to) (12 : D:/f60-run/physical-i/compiled/board/gray-pointer-cdc.fdc)
	// SDC constraint : (object R) (id 1027) (cell to) (13 : D:/f60-run/physical-i/compiled/board/gray-pointer-cdc.fdc)
	// SDC constraint : (object R) (id 1026) (cell to) (12 : D:/f60-run/physical-i/compiled/board/gray-pointer-cdc.fdc)

(* PAP_ASYNC_REG="TRUE", PAP_SRL_STYLE="registers" *)    GTP_DFF_R  #( .GRS_EN("TRUE"), .INIT(1'b0)) \wr_gray_r1[6]  (
            .Q (wr_gray_r1[6]),
            .CLK (nt_pixclk_in),
            .D (wr_gray[6]),
            .R (\rd_reset_sync[1]_inv_1 ));
	// ../../../compiled/rtl/video_async_fifo.v:58
	// SDC constraint : (object D) (id 1027) (cell to) (13 : D:/f60-run/physical-i/compiled/board/gray-pointer-cdc.fdc)
	// SDC constraint : (object D) (id 1026) (cell to) (12 : D:/f60-run/physical-i/compiled/board/gray-pointer-cdc.fdc)
	// SDC constraint : (object R) (id 1027) (cell to) (13 : D:/f60-run/physical-i/compiled/board/gray-pointer-cdc.fdc)
	// SDC constraint : (object R) (id 1026) (cell to) (12 : D:/f60-run/physical-i/compiled/board/gray-pointer-cdc.fdc)

(* PAP_ASYNC_REG="TRUE", PAP_SRL_STYLE="registers" *)    GTP_DFF_R  #( .GRS_EN("TRUE"), .INIT(1'b0)) \wr_gray_r1[7]  (
            .Q (wr_gray_r1[7]),
            .CLK (nt_pixclk_in),
            .D (wr_gray[7]),
            .R (\rd_reset_sync[1]_inv_1 ));
	// ../../../compiled/rtl/video_async_fifo.v:58
	// SDC constraint : (object D) (id 1027) (cell to) (13 : D:/f60-run/physical-i/compiled/board/gray-pointer-cdc.fdc)
	// SDC constraint : (object D) (id 1026) (cell to) (12 : D:/f60-run/physical-i/compiled/board/gray-pointer-cdc.fdc)
	// SDC constraint : (object R) (id 1027) (cell to) (13 : D:/f60-run/physical-i/compiled/board/gray-pointer-cdc.fdc)
	// SDC constraint : (object R) (id 1026) (cell to) (12 : D:/f60-run/physical-i/compiled/board/gray-pointer-cdc.fdc)

(* PAP_ASYNC_REG="TRUE", PAP_SRL_STYLE="registers" *)    GTP_DFF_R  #( .GRS_EN("TRUE"), .INIT(1'b0)) \wr_gray_r1[8]  (
            .Q (wr_gray_r1[8]),
            .CLK (nt_pixclk_in),
            .D (wr_gray[8]),
            .R (\rd_reset_sync[1]_inv_1 ));
	// ../../../compiled/rtl/video_async_fifo.v:58
	// SDC constraint : (object D) (id 1027) (cell to) (13 : D:/f60-run/physical-i/compiled/board/gray-pointer-cdc.fdc)
	// SDC constraint : (object D) (id 1026) (cell to) (12 : D:/f60-run/physical-i/compiled/board/gray-pointer-cdc.fdc)
	// SDC constraint : (object R) (id 1027) (cell to) (13 : D:/f60-run/physical-i/compiled/board/gray-pointer-cdc.fdc)
	// SDC constraint : (object R) (id 1026) (cell to) (12 : D:/f60-run/physical-i/compiled/board/gray-pointer-cdc.fdc)

(* PAP_ASYNC_REG="TRUE", PAP_SRL_STYLE="registers" *)    GTP_DFF_R  #( .GRS_EN("TRUE"), .INIT(1'b0)) \wr_gray_r1[9]  (
            .Q (wr_gray_r1[9]),
            .CLK (nt_pixclk_in),
            .D (wr_gray[9]),
            .R (\rd_reset_sync[1]_inv_1 ));
	// ../../../compiled/rtl/video_async_fifo.v:58
	// SDC constraint : (object D) (id 1027) (cell to) (13 : D:/f60-run/physical-i/compiled/board/gray-pointer-cdc.fdc)
	// SDC constraint : (object D) (id 1026) (cell to) (12 : D:/f60-run/physical-i/compiled/board/gray-pointer-cdc.fdc)
	// SDC constraint : (object R) (id 1027) (cell to) (13 : D:/f60-run/physical-i/compiled/board/gray-pointer-cdc.fdc)
	// SDC constraint : (object R) (id 1026) (cell to) (12 : D:/f60-run/physical-i/compiled/board/gray-pointer-cdc.fdc)

(* PAP_ASYNC_REG="TRUE", PAP_SRL_STYLE="registers" *)    GTP_DFF_R  #( .GRS_EN("TRUE"), .INIT(1'b0)) \wr_gray_r2[0]  (
            .Q (wr_gray_r2[0]),
            .CLK (nt_pixclk_in),
            .D (wr_gray_r1[0]),
            .R (\rd_reset_sync[1]_inv_1 ));
	// ../../../compiled/rtl/video_async_fifo.v:58

(* PAP_ASYNC_REG="TRUE", PAP_SRL_STYLE="registers" *)    GTP_DFF_R  #( .GRS_EN("TRUE"), .INIT(1'b0)) \wr_gray_r2[1]  (
            .Q (wr_gray_r2[1]),
            .CLK (nt_pixclk_in),
            .D (wr_gray_r1[1]),
            .R (\rd_reset_sync[1]_inv_1 ));
	// ../../../compiled/rtl/video_async_fifo.v:58

(* PAP_ASYNC_REG="TRUE", PAP_SRL_STYLE="registers" *)    GTP_DFF_R  #( .GRS_EN("TRUE"), .INIT(1'b0)) \wr_gray_r2[2]  (
            .Q (wr_gray_r2[2]),
            .CLK (nt_pixclk_in),
            .D (wr_gray_r1[2]),
            .R (\rd_reset_sync[1]_inv_1 ));
	// ../../../compiled/rtl/video_async_fifo.v:58

(* PAP_ASYNC_REG="TRUE", PAP_SRL_STYLE="registers" *)    GTP_DFF_R  #( .GRS_EN("TRUE"), .INIT(1'b0)) \wr_gray_r2[3]  (
            .Q (wr_gray_r2[3]),
            .CLK (nt_pixclk_in),
            .D (wr_gray_r1[3]),
            .R (\rd_reset_sync[1]_inv_1 ));
	// ../../../compiled/rtl/video_async_fifo.v:58

(* PAP_ASYNC_REG="TRUE", PAP_SRL_STYLE="registers" *)    GTP_DFF_R  #( .GRS_EN("TRUE"), .INIT(1'b0)) \wr_gray_r2[4]  (
            .Q (wr_gray_r2[4]),
            .CLK (nt_pixclk_in),
            .D (wr_gray_r1[4]),
            .R (\rd_reset_sync[1]_inv_1 ));
	// ../../../compiled/rtl/video_async_fifo.v:58

(* PAP_ASYNC_REG="TRUE", PAP_SRL_STYLE="registers" *)    GTP_DFF_R  #( .GRS_EN("TRUE"), .INIT(1'b0)) \wr_gray_r2[5]  (
            .Q (wr_gray_r2[5]),
            .CLK (nt_pixclk_in),
            .D (wr_gray_r1[5]),
            .R (\rd_reset_sync[1]_inv_1 ));
	// ../../../compiled/rtl/video_async_fifo.v:58

(* PAP_ASYNC_REG="TRUE", PAP_SRL_STYLE="registers" *)    GTP_DFF_R  #( .GRS_EN("TRUE"), .INIT(1'b0)) \wr_gray_r2[6]  (
            .Q (wr_gray_r2[6]),
            .CLK (nt_pixclk_in),
            .D (wr_gray_r1[6]),
            .R (\rd_reset_sync[1]_inv_1 ));
	// ../../../compiled/rtl/video_async_fifo.v:58

(* PAP_ASYNC_REG="TRUE", PAP_SRL_STYLE="registers" *)    GTP_DFF_R  #( .GRS_EN("TRUE"), .INIT(1'b0)) \wr_gray_r2[7]  (
            .Q (wr_gray_r2[7]),
            .CLK (nt_pixclk_in),
            .D (wr_gray_r1[7]),
            .R (\rd_reset_sync[1]_inv_1 ));
	// ../../../compiled/rtl/video_async_fifo.v:58

(* PAP_ASYNC_REG="TRUE", PAP_SRL_STYLE="registers" *)    GTP_DFF_R  #( .GRS_EN("TRUE"), .INIT(1'b0)) \wr_gray_r2[8]  (
            .Q (wr_gray_r2[8]),
            .CLK (nt_pixclk_in),
            .D (wr_gray_r1[8]),
            .R (\rd_reset_sync[1]_inv_1 ));
	// ../../../compiled/rtl/video_async_fifo.v:58

(* PAP_ASYNC_REG="TRUE", PAP_SRL_STYLE="registers" *)    GTP_DFF_R  #( .GRS_EN("TRUE"), .INIT(1'b0)) \wr_gray_r2[9]  (
            .Q (wr_gray_r2[9]),
            .CLK (nt_pixclk_in),
            .D (wr_gray_r1[9]),
            .R (\rd_reset_sync[1]_inv_1 ));
	// ../../../compiled/rtl/video_async_fifo.v:58


endmodule