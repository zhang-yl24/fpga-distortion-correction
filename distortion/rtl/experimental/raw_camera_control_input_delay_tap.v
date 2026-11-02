// One input buffer per physical control pad. The monitor observes its output
// before the fixed delay; capture observes the same delay as all eight data bits.
module raw_camera_control_input_delay_tap(
    input wire pad_href,
    input wire pad_vsync,
    output wire monitor_href,
    output wire monitor_vsync,
    output wire capture_href,
    output wire capture_vsync
);
    wire [1:0] pad_control = {pad_vsync, pad_href};
    wire [1:0] buffered_control;
    wire [1:0] capture_control;
    assign monitor_href = buffered_control[0];
    assign monitor_vsync = buffered_control[1];
    assign capture_href = capture_control[0];
    assign capture_vsync = capture_control[1];
    genvar bit_index;
    generate
        for (bit_index=0; bit_index<2; bit_index=bit_index+1) begin : control_bit
            GTP_INBUF #(.IOSTANDARD("LVCMOS33"), .TERM_DDR("ON")) input_buffer(
                .I(pad_control[bit_index]), .O(buffered_control[bit_index]));
            GTP_ZEROHOLDDELAY #(.ZHOLD_SET("1500ps")) input_delay(
                .DI(buffered_control[bit_index]), .DO(capture_control[bit_index]));
        end
    endgenerate
endmodule
