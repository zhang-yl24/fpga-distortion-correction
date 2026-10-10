`timescale 1ns/1ps
// Bus stub exercises wrapper ownership/fail-stop/UART formatting; physical
// SCCB signaling is independently tested with the actual reg16_i2c module.
module reg16_i2c #(parameter QUARTER_CYCLES=68,TIMEOUT_CYCLES=1350000)(
    input clk,rst_n,start,read,input [6:0] device,input [15:0] address,
    input [7:0] write_data,output reg busy,done,output reg [3:0] error,
    output reg [7:0] read_data,inout scl,sda);
    assign scl=1'bz;assign sda=1'bz;
    integer calls=0,count=0;reg inject_fault=0;reg [15:0] held_address;
    always @(posedge clk) begin
        done<=0;
        if(!rst_n) begin busy<=0;error<=0;read_data<=0;calls=0;count=0;end
        else if(start) begin
            if(busy || read!==1'b1 || device!==7'h3c || write_data!==0)
                $fatal(1,"Observer attempted a write or overlapped transactions");
            busy<=1;count=3;held_address<=address;calls=calls+1;
        end else if(busy) begin
            if(count==0) begin
                busy<=0;done<=1;read_data<=held_address[7:0]^8'ha5;
                error<=inject_fault && held_address==16'h4300 ? 4'h2:0;
            end else count=count-1;
        end
    end
endmodule

module tb_camera_state_scan;
    reg clk=0,rst_n=0,enabled=0,byte_ready=0;always #5 clk=~clk;
    tri1 scl,sda;wire byte_valid,failed;wire [7:0] byte_data;wire [3:0] fault;
    ov5640_state_scan #(.CLOCK_HZ(1000),.SCAN_GAP_MS(10000)) dut(.*);
    integer phase=0,rows=0,beats=0;string line="";string expected_tail,actual_tail;reg [15:0] expected_address;
    function [15:0] golden_address(input integer index);
        begin case(index)
            0:golden_address='h5001;1:golden_address='h3406;2:golden_address='h3503;
            3:golden_address='h4300;4:golden_address='h501f;5:golden_address='h503d;
            6:golden_address='h3400;7:golden_address='h3401;8:golden_address='h3402;
            9:golden_address='h3403;10:golden_address='h3404;11:golden_address='h3405;
            12:golden_address='h3500;13:golden_address='h3501;14:golden_address='h3502;
            15:golden_address='h350a;16:golden_address='h350b;17:golden_address='h3a00;
            18:golden_address='h3a19;19:golden_address='h5000;20:golden_address='h3017;
            21:golden_address='h3018;22:golden_address='h3035;23:golden_address='h3036;
            default:$fatal(1,"Unexpected extra scan row");
        endcase end
    endfunction
    always @(negedge clk) begin phase=phase+1;byte_ready=phase%3!=0;end
    always @(posedge clk) if(rst_n && enabled && byte_valid && byte_ready) begin
        line={line,byte_data};beats=beats+1;
        if(byte_data==10) begin
            if(line.len()!=32 || line.substr(0,5)!="ISP T=") $fatal(1,"Bad UART record framing: %s",line);
            expected_address=golden_address(rows);
            if(dut.observer.inject_fault && rows==3)
                expected_tail=$sformatf(" A=%04x V=00 E=2",expected_address);
            else expected_tail=$sformatf(" A=%04x V=%02x E=0",expected_address,expected_address[7:0]^8'ha5);
            actual_tail=line.substr(14,29);
            if(actual_tail.tolower()!=expected_tail.tolower() || line[30]!=13 || line[31]!=10)
                $fatal(1,"Bad scan value/address: %s expected %s",line,expected_tail);
            for(integer i=6;i<14;i=i+1) if(!((line[i]>=48 && line[i]<=57)||(line[i]>=65 && line[i]<=70)))
                $fatal(1,"Invalid time hex encoding");
            rows=rows+1;line="";
        end
    end
    task reset_probe;
        begin @(negedge clk);rst_n=0;enabled=0;line="";rows=0;beats=0;
            repeat(4) @(negedge clk);rst_n=1;end
    endtask
    initial begin
        reset_probe();repeat(30) @(negedge clk);
        if(dut.observer.calls!=0 || byte_valid) $fatal(1,"Scanned before initialization readiness");
        enabled=1;wait(rows==24);repeat(100) @(negedge clk);
        if(failed || dut.observer.calls!=24 || beats!=768) $fatal(1,"Unexpected success scan count/status");
        reset_probe();dut.observer.inject_fault=1;enabled=1;wait(rows==4);
        repeat(100) @(negedge clk);
        if(!failed || fault!=2 || dut.observer.calls!=4) $fatal(1,"Read fault did not halt without retry");
        enabled=0;repeat(4) @(negedge clk);if(failed || byte_valid) $fatal(1,"Readiness loss did not reset scan");
        dut.observer.inject_fault=0;rows=0;beats=0;line="";enabled=1;wait(rows==24);
        if(failed || dut.observer.calls!=24) $fatal(1,"Readiness recovery failed");
        $display("PASS camera state scan: 24 read-only registers, UART stalls/framing, initialization gate, fault halt without retry and readiness recovery.");$finish;
    end
    initial begin #500000;$fatal(1,"State scan timeout");end
endmodule
