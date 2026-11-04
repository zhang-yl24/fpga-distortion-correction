// Capture controls use the same fixed native delay as the eight RGB565 data bits.
// The admission monitor keeps its original raw control/data path in the top.
module raw_camera_control_input_delay(
    input wire pad_href,
    input wire pad_vsync,
    output wire capture_href,
    output wire capture_vsync
);
    wire [1:0] pad_control = {pad_vsync, pad_href};
    wire [1:0] capture_control;
    assign capture_href = capture_control[0];
    assign capture_vsync = capture_control[1];
    genvar bit_index;
    generate
        for (bit_index=0; bit_index<2; bit_index=bit_index+1) begin : control_bit
            wire buffered_control;
            GTP_INBUF #(.IOSTANDARD("LVCMOS33"), .TERM_DDR("ON")) input_buffer(
                .I(pad_control[bit_index]), .O(buffered_control));
            GTP_ZEROHOLDDELAY #(.ZHOLD_SET("1500ps")) input_delay(
                .DI(buffered_control), .DO(capture_control[bit_index]));
        end
    endgenerate
endmodule
