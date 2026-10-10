`timescale 1ns/1ps
module tb_uart_tx;
    reg clk=0; always #5 clk=~clk;
    reg rst_n=0,start=0; reg [7:0] data=8'ha6;
    wire tx,busy,done;
    uart_tx #(.CLOCK_HZ(1000),.BAUD(100)) dut(.*);
    initial begin
        #50; @(negedge clk); rst_n=1;
        @(negedge clk); start=1;
        @(negedge tx); #50;
        if(tx!==0) $fatal(1,"Start bit");
        for(integer b=0;b<8;b=b+1) begin #100; if(tx!==data[b]) $fatal(1,"Data bit %0d",b); end
        #100; if(tx!==1) $fatal(1,"Stop bit");
        @(posedge done); @(negedge clk); start=0;
        if(busy) $fatal(1,"Busy stayed high");
        $display("PASS uart_tx 8N1 exact bit period"); $finish;
    end
    initial begin #5000; $fatal(1,"Timeout"); end
endmodule
