`timescale 1ns/1ps
module tb_reg16_i2c #(parameter ADDR_LSB_FIRST=0, READ_WITH_STOP=0);
    reg clk=0; always #5 clk=~clk;
    reg rst_n=0, start=0, rd=0;
    reg [6:0] dev=7'h3c;
    reg [15:0] addr=16'h300a;
    reg [7:0] wd=8'ha5;
    wire busy,done; wire [3:0] err; wire [7:0] result;
    tri1 scl,sda;
    reg slave_sda=0, slave_scl=0;
    assign sda=slave_sda ? 1'b0:1'bz;
    assign scl=slave_scl ? 1'b0:1'bz;
    reg16_i2c #(.QUARTER_CYCLES(8),.TIMEOUT_CYCLES(20000),.ADDR_LSB_FIRST(ADDR_LSB_FIRST),.READ_WITH_STOP(READ_WITH_STOP)) dut(
        .clk(clk),.rst_n(rst_n),.start(start),.read(rd),.device(dev),
        .address(addr),.write_data(wd),.busy(busy),.done(done),.error(err),
        .read_data(result),.scl(scl),.sda(sda));
    task automatic wait_start;
        begin @(negedge sda); if(scl!==1) $fatal(1,"Missing START"); end
    endtask
    task automatic receive(input [7:0] expected, input bit ack);
        reg [7:0] v;
        begin
            v=0;
            for(integer b=0;b<8;b=b+1) begin @(posedge scl); v={v[6:0],sda}; end
            if(v!==expected) $fatal(1,"Byte expected %h got %h",expected,v);
            @(negedge scl); slave_sda=ack;
            @(posedge scl); @(negedge scl); slave_sda=0;
        end
    endtask
    task automatic send(input [7:0] v);
        begin
            for(integer b=7;b>=0;b=b-1) begin
                slave_sda=!v[b]; @(posedge scl); @(negedge scl);
            end
            slave_sda=0; @(posedge scl);
            if(sda!==1) $fatal(1,"Master must NACK final read byte");
            @(negedge scl);
        end
    endtask
    task automatic wait_stop;
        begin do @(posedge sda); while(scl!==1); end
    endtask
    task automatic launch(input bit is_read);
        begin @(negedge clk); rd=is_read; start=1; @(negedge clk); start=0; end
    endtask
    initial begin
        #100; @(negedge clk); rst_n=1; repeat(8) @(posedge clk);
        fork
            begin
                wait_start(); receive(8'h78,1); receive(ADDR_LSB_FIRST ? 8'h0a:8'h30,1); receive(ADDR_LSB_FIRST ? 8'h30:8'h0a,1);
                if(READ_WITH_STOP) begin wait_stop(); if(!busy || done) $fatal(1,"Premature completion at intermediate STOP"); end
                wait_start(); receive(8'h79,1); send(8'h56); wait_stop();
            end
            begin launch(1); @(posedge done); if(err || result!==8'h56) $fatal(1,"Read failed"); end
        join
        repeat(10) @(posedge clk);
        fork
            begin wait_start(); receive(8'h78,1); receive(ADDR_LSB_FIRST ? 8'h0a:8'h30,1); receive(ADDR_LSB_FIRST ? 8'h30:8'h0a,1); receive(8'ha5,1); wait_stop(); end
            begin launch(0); @(posedge done); if(err) $fatal(1,"Write failed"); end
        join
        repeat(10) @(posedge clk);
        fork
            begin wait_start(); receive(8'h78,0); wait_stop(); end
            begin launch(1); @(posedge done); if(err!==1) $fatal(1,"NACK not reported"); end
        join
        repeat(10) @(posedge clk);
        fork
            begin
                wait_start(); receive(8'h78,1);
                // Stretch a released SCL between bytes; data must be preserved.
                slave_scl=1; #1500; slave_scl=0;
                receive(ADDR_LSB_FIRST ? 8'h0a:8'h30,1); receive(ADDR_LSB_FIRST ? 8'h30:8'h0a,1);
                if(READ_WITH_STOP) wait_stop();
                wait_start(); receive(8'h79,1); send(8'h40); wait_stop();
            end
            begin launch(1); @(posedge done); if(err || result!==8'h40) $fatal(1,"Stretch failed"); end
        join
        repeat(10) @(posedge clk);
        slave_scl=1; launch(1); @(posedge done);
        if(err!==15 || busy) $fatal(1,"Stuck bus timeout failed");
        if(dut.scl_low || dut.sda_low) $fatal(1,"Outputs not released");
        slave_scl=0;
        $display("PASS reg16_i2c addr_lsb_first=%0d stop_read=%0d read/write, NACK, clock stretch, timeout",ADDR_LSB_FIRST,READ_WITH_STOP); $finish;
    end
    initial begin #2000000; $fatal(1,"Test timeout"); end
endmodule

module tb_i2c_le;
    tb_reg16_i2c #(.ADDR_LSB_FIRST(1)) test();
endmodule

module tb_sccb_stop;
    tb_reg16_i2c #(.READ_WITH_STOP(1)) test();
endmodule
