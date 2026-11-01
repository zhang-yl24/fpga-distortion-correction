`timescale 1ns/1ps
// Exercise the actual RTL at the production width as well as a short boundary
// case. The oracle counts observed clock edges, independent of DUT counter bits.
module tb_raw_camera_power_ready;
    localparam integer SMALL_EDGES = 1 << 3;
    localparam integer NATIVE_EDGES = 1 << 20;
    localparam integer HOLD_EDGES = 32;
    reg clk = 1'b0;
    wire small_ready, native_ready;
    integer edges = 0;
    integer small_releases = 0, native_releases = 0;
    integer checks = 0;
    time last_rising_edge = 0;

    raw_camera_power_ready #(.COUNT_BITS(3)) dut_small(
        .clk(clk), .power_ready(small_ready));
    raw_camera_power_ready dut_native(
        .clk(clk), .power_ready(native_ready));

    always #5 clk = !clk;

    // Registered output transitions must occur only on a rising clock edge.
    // Time-zero initializer events are checked separately below.
    always @(small_ready) begin
        if ($time != 0) begin
            if (clk !== 1'b1 || $time != last_rising_edge || small_ready !== 1'b1)
                $fatal(1, "small release changed outside its registered rising edge");
            small_releases = small_releases + 1;
        end
    end
    always @(native_ready) begin
        if ($time != 0) begin
            if (clk !== 1'b1 || $time != last_rising_edge || native_ready !== 1'b1)
                $fatal(1, "native release changed outside its registered rising edge");
            native_releases = native_releases + 1;
        end
    end

    always @(posedge clk) begin
        last_rising_edge = $time;
        edges = edges + 1;
        #1; // Inspect registered outputs after nonblocking assignments settle.
        if (small_ready !== (edges >= SMALL_EDGES))
            $fatal(1, "3-bit ready mismatch at rising edge %0d", edges);
        if (native_ready !== (edges >= NATIVE_EDGES))
            $fatal(1, "20-bit ready mismatch at rising edge %0d", edges);
        checks = checks + 2;
        if (edges >= SMALL_EDGES && dut_small.power_count !== 3'b111)
            $fatal(1, "small counter did not stop at terminal count");
        if (edges >= NATIVE_EDGES && dut_native.power_count !== 20'hfffff)
            $fatal(1, "native counter did not stop at terminal count");
    end

    initial begin
        #1;
        if (small_ready !== 1'b0 || native_ready !== 1'b0)
            $fatal(1, "power-up ready state is not low");
        repeat (NATIVE_EDGES + HOLD_EDGES) @(negedge clk);
        if (small_releases != 1 || native_releases != 1)
            $fatal(1, "release count differs from one sticky transition");
        if (edges != NATIVE_EDGES + HOLD_EDGES || checks != 2 * edges)
            $fatal(1, "missing clock-edge checks");
        $display("RAW_CAMERA_POWER_READY_PASS edges=%0d checks=%0d small_release_edge=%0d native_release_edge=%0d hold_edges=%0d",
                 edges, checks, SMALL_EDGES, NATIVE_EDGES, HOLD_EDGES);
        $finish;
    end

    initial begin
        #(10 * (NATIVE_EDGES + HOLD_EDGES + 4));
        $fatal(1, "startup testbench watchdog expired");
    end
endmodule
