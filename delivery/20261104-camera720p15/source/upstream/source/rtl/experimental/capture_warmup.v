`timescale 1ns/1ps
// Keep frozen acquisition disarmed while the sensor emits startup frames.
// A loss of camera/DDR readiness restarts the full continuous-ready interval.
module capture_warmup #(parameter CLOCK_HZ=125000000,DELAY_MS=2000)(
    input clk,rst_n,ready,output armed
);
    localparam WAIT_CYCLES=(CLOCK_HZ/1000)*DELAY_MS;
    localparam COUNT_BITS=$clog2(WAIT_CYCLES+1);
    reg [COUNT_BITS-1:0] count;
    assign armed=rst_n && ready && count==WAIT_CYCLES;
    always @(posedge clk) begin
        if(!rst_n || !ready) count<=0;
        else if(count<WAIT_CYCLES) count<=count+1'b1;
    end
endmodule
