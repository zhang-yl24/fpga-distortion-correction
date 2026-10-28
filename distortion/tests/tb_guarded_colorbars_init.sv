`timescale 1ns/1ps
// Reuse the complete reviewed SCCB sensor model with the guarded board's
// actual DYNAMIC_PAD_MASK=1 specialization; do not edit the old fixture.
module tb_guarded_colorbars_init;
    tb_ov5640_colorbars fixture();
    defparam fixture.dut.DYNAMIC_PAD_MASK=1;
    initial begin
        #1;if(fixture.dut.DYNAMIC_PAD_MASK!=1)$fatal(1,"Guarded colorbar specialization was not applied");
    end
endmodule
