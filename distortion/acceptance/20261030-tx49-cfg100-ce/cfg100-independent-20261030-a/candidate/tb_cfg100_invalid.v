module tb_cfg100_invalid;
    wire q;
    cfg100_startup_hold #(.SETTLE_CYCLES(0)) invalid_dut(1'b0,1'b0,1'b0,q);
endmodule
