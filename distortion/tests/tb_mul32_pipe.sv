`timescale 1ns/1ps
module tb_mul32_pipe;
    reg clk=0;always #4 clk=~clk;
    reg ce=0;reg signed [31:0] a=0,b=0;
    wire signed [63:0] p;
    mul32_pipe dut(.*);
    reg signed [63:0] expected[0:2];
    reg signed [31:0] extremes[0:6];
    reg signed [63:0] held;
    integer i,j,n=0,checked=0;
    task step(input reg enable,input reg signed [31:0] av,bv);
        begin
            @(negedge clk);ce=enable;a=av;b=bv;held=p;
            @(posedge clk);
            if(enable) begin
                expected[2]=expected[1];expected[1]=expected[0];expected[0]=$signed(av)*$signed(bv);n=n+1;
            end
            #1;
            if(enable && n>=3) begin
                if(p!==expected[2]) $fatal(1,"Exact multiplier mismatch %h expected %h",p,expected[2]);
                checked=checked+1;
            end
            if(!enable && p!==held) $fatal(1,"Multiplier changed while CE=0");
        end
    endtask
    initial begin
        extremes[0]=32'h80000000;extremes[1]=32'h7fffffff;extremes[2]=-1;extremes[3]=0;
        extremes[4]=1;extremes[5]=32'h0000ffff;extremes[6]=32'hffff0000;
        for(i=0;i<7;i=i+1) for(j=0;j<7;j=j+1) step(1,extremes[i],extremes[j]);
        for(i=0;i<20000;i=i+1) step(i%17!=0,$random,$random);
        step(1,0,0);step(1,0,0);step(1,0,0);
        $display("PASS signed 32x32 pipelined multiplier: %0d full-range products, signed extremes and enable stalls.",checked);$finish;
    end
endmodule
