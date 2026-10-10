`timescale 1ns/1ps
module tb_gamma_exhaustive;
    reg [15:0] golden[0:196607];
    `include "D:/English/FPGA/distortion/rtl/experimental/gamma_curves.vh"
    integer m,p;reg [15:0] actual;
    initial begin
        $readmemh("golden.mem",golden);
        for(m=0;m<3;m=m+1)for(p=0;p<65536;p=p+1)begin
            actual={gamma5(m,p[15:11]),gamma6(m,p[10:5]),gamma5(m,p[4:0])};
            if(actual!==golden[m*65536+p])$fatal(1,"Gamma lookup mismatch");
        end
        $display("PASS exhaustive Gamma: all 196608 RGB565 values across identity, brighten and dim curves.");$finish;
    end
endmodule
