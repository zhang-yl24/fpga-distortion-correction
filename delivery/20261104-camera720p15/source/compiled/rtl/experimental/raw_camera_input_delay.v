// Native Logos2 input delay candidate. STA and physical mapping must verify it.
// All camera data bits use the same setting; no sampling edge or data value changes.
module raw_camera_input_delay(
    input wire [7:0] pad_data,
    output wire [7:0] capture_data
);
    genvar bit_index;
    generate
        for (bit_index=0; bit_index<8; bit_index=bit_index+1) begin : data_bit
            wire buffered_data;
            GTP_INBUF #(.IOSTANDARD("LVCMOS33"), .TERM_DDR("ON")) input_buffer(
                .I(pad_data[bit_index]), .O(buffered_data));
            GTP_ZEROHOLDDELAY #(.ZHOLD_SET("1500ps")) input_delay(
                .DI(buffered_data), .DO(capture_data[bit_index]));
        end
    endgenerate
endmodule
