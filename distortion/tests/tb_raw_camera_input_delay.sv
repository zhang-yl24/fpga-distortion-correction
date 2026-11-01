`timescale 1ps/1ps
// Exercise actual vendor models: all byte values, both edge polarities, and
// no early output transition before the configured nominal delay expires.
module tb_raw_camera_input_delay;
    reg [7:0] data_in = 0;
    wire [7:0] data_out;
    reg [7:0] previous;
    integer value, checks = 0;
    raw_camera_input_delay dut(.pad_data(data_in), .capture_data(data_out));
    initial begin
        #2000;
        if (data_out !== 8'h00) $fatal(1, "input delay failed initial settling");
        for (value=0; value<256; value=value+1) begin
            previous = data_in;
            data_in = value[7:0] ^ 8'ha5;
            #1499;
            if (data_out !== previous) $fatal(1, "early input transition at value %0d", value);
            checks = checks + 1;
            #2;
            if (data_out !== data_in) $fatal(1, "byte changed/delayed beyond nominal boundary at value %0d", value);
            checks = checks + 1;
            #2499;
            if (data_out !== data_in) $fatal(1, "unstable delayed byte at value %0d", value);
            checks = checks + 1;
        end
        if (checks != 768) $fatal(1, "incomplete input delay coverage");
        $display("RAW_CAMERA_INPUT_DELAY_PASS values=256 checks=768 bits=8 nominal_delay_ps=1500");
        $finish;
    end
    initial begin
        #1100000;
        $fatal(1, "input delay test watchdog expired");
    end
endmodule
