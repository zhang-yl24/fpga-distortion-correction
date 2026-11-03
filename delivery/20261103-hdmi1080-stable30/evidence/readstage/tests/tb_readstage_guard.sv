`timescale 1ns/1ps
module tb_readstage_guard;
    reg clk=0;always #4 clk=~clk;
    reg rst_n=0,av=0,ar=0,rv=0,rl=0;reg [3:0] rid=0;reg [255:0] data=0;
    wire [255:0] outdata;wire outvalid,outlast,failed;wire [3:0] outid;wire [7:0] fault;
    integer checks=0;
    ddr_read_return_register dut(.clk(clk),.rst_n(rst_n),.arvalid(av),.arready(ar),
        .in_rdata(data),.in_rvalid(rv),.in_rlast(rl),.in_rid(rid),
        .out_rdata(outdata),.out_rvalid(outvalid),.out_rlast(outlast),.out_rid(outid),
        .protocol_fault(failed),.fault_code(fault));
    task tick;begin @(posedge clk);#1;end endtask
    task clear;
        begin @(negedge clk);rst_n=0;av=0;ar=0;rv=1;rl=1;rid=15;data={256{1'b1}};
            tick;if(outvalid || failed)$fatal(1,"Reset must suppress raw/staged valid and fault");
            @(negedge clk);rst_n=1;rv=0;rl=0;rid=0;tick;
            if(outvalid || failed)$fatal(1,"Reset left stale valid/fault");checks=checks+1;
        end
    endtask
    initial begin
        clear;
        // Raw same-edge AR and first beat, followed by contiguous beats.
        @(negedge clk);av=1;ar=1;rv=1;rl=0;data={8{32'h12340000}};
        tick;if(!outvalid || outlast || outdata!=={8{32'h12340000}} || outid!=0 || failed)$fatal(1,"Same-edge first beat lost");
        @(negedge clk);av=0;data={8{32'h12340001}};
        tick;if(!outvalid || outdata!=={8{32'h12340001}} || failed)$fatal(1,"Continuous beat lost");
        @(negedge clk);rl=1;rid=9;data={8{32'h12340002}};
        tick;if(!outvalid || !outlast || outid!=9 || outdata!=={8{32'h12340002}} || failed)$fatal(1,"Last beat or illegal RID was changed");checks=checks+1;
        // Reset while raw and staged responses are asserted.
        clear;
        @(negedge clk);rv=1;rl=1;av=0;ar=1;
        tick;if(!failed || fault!=8'h40 || outvalid)$fatal(1,"Raw unsolicited response escaped");
        @(negedge clk);av=1;rv=1;rl=1;
        tick;if(!failed || fault!=8'h40 || outvalid)$fatal(1,"Next AR masked prior raw fault");checks=checks+1;
        clear;
        @(negedge clk);av=1;ar=1;rv=0;
        tick;if(failed)$fatal(1,"Valid reservation rejected");
        @(negedge clk);av=1;ar=1;rv=0;
        tick;if(!failed || fault!=8'h41 || outvalid)$fatal(1,"Overlapping raw AR not rejected");checks=checks+1;
        clear;
        @(negedge clk);av=1;ar=1;rv=1;rl=1;rid=0;
        tick;if(!outvalid || !outlast || failed)$fatal(1,"Single beat same-edge response failed");
        @(negedge clk);av=0;rv=1;
        tick;if(!failed || fault!=8'h40 || outvalid)$fatal(1,"Completed single beat retained a stale owner");checks=checks+1;
        clear;
        @(negedge clk);av=1;ar=1;rv=0;rl=0;tick;
        @(negedge clk);av=1;rv=1;rl=1;data={8{32'habcd0000}};tick;
        if(failed || !outvalid)$fatal(1,"Final old beat and next AR were not conserved");
        @(negedge clk);av=0;rv=1;rl=1;data={8{32'habcd0001}};tick;
        if(failed || !outvalid || outdata!=={8{32'habcd0001}})$fatal(1,"Next owner after final swap lost");checks=checks+1;
        clear;
        if(checks!=11)$fatal(1,"Guard test coverage accounting failed");
        $display("PASS READSTAGE GUARD checks=%0d raw-owned/zero-latency/continuous/metadata/reset/unsolicited/overlap/sticky",checks);$finish;
    end
    initial begin #100000;$fatal(1,"Guard test timeout");end
endmodule
