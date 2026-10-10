`timescale 1ns/1ps
// Pin-verified minimal bring-up. Camera/FMC pins are deliberately not driven.
module heartbeat(input wire clk_27m, output wire [7:0] led);
    reg [24:0] counter = 0;
    reg toggle = 0;
    always @(posedge clk_27m) begin
        if(counter==25'd13499999) begin counter<=0;toggle<=~toggle;end
        else counter<=counter+1'b1;
    end
    assign led={7'b0000000,toggle};
endmodule
