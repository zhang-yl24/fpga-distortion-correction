`timescale 1ns/1ps
module tb_video_async_fifo;
    reg wr_clk=0,rd_clk=0;always #7 wr_clk=~wr_clk;always #5 rd_clk=~rd_clk;
    reg rst_n=0,wr_en=0,rd_en=0;
    reg [255:0] wr_data=0;
    wire wr_full,wr_ready,rd_empty,rd_ready,rd_valid;
    wire [255:0] rd_data;
    wire [3:0] rd_available,wr_used;
    video_async_fifo #(.ADDR_BITS(3)) dut(.*);
    reg [255:0] expected[0:8191];
    integer sent=0,received=0,wcycle=0,rcycle=0,target=0;
    reg writer_running=0,reader_running=0,throttle=0;
    function [255:0] test_word;
        input integer n;integer lane;
        begin for(lane=0;lane<8;lane=lane+1) test_word[lane*32+:32]=32'h5A937C10 ^ n ^ (lane<<24);end
    endfunction
    always @(negedge wr_clk) begin
        wcycle=wcycle+1;
        wr_en=writer_running && sent<target && (!throttle || wcycle%5!=0);
        wr_data=test_word(sent);
    end
    always @(posedge wr_clk) begin
        if(rst_n && wr_en && wr_ready) begin expected[sent]=wr_data;sent=sent+1;end
        if(wr_used>8) $fatal(1,"FIFO write count overflow");
    end
    always @(negedge rd_clk) begin
        rcycle=rcycle+1;
        if(rst_n && rd_valid) begin
            if(received>=sent || rd_data!==expected[received]) $fatal(1,"FIFO mismatch at %d",received);
            received=received+1;
        end
        rd_en=reader_running && (!throttle || rcycle%7<3);
        if(rd_available>8) $fatal(1,"FIFO read count overflow");
    end
    task restart;
        begin
            writer_running=0;reader_running=0;rst_n=0;
            repeat(8) @(negedge wr_clk);
            sent=0;received=0;target=0;rst_n=1;
            repeat(8) @(negedge wr_clk);
        end
    endtask
    task await_drain;
        integer timeout;
        begin
            timeout=0;
            while(received<target && timeout<30000) begin @(negedge wr_clk);timeout=timeout+1;end
            if(received!=target || sent!=target) $fatal(1,"FIFO drain timeout sent=%d got=%d",sent,received);
            repeat(8) @(negedge wr_clk);
            if(!rd_empty || wr_full || rd_available || wr_used) $fatal(1,"FIFO flags/counts not empty");
        end
    endtask
    initial begin
        restart();target=8;writer_running=1;
        repeat(25) @(negedge wr_clk);
        if(!wr_full || sent!=8 || received) $fatal(1,"FIFO did not fill exactly");
        target=16;repeat(12) @(negedge wr_clk);
        if(sent!=8) $fatal(1,"FIFO overwrote full queue");
        reader_running=1;await_drain();
        target=4096;throttle=1;await_drain();
        // Reset while data remains queued, then verify no stale data leaks.
        reader_running=0;throttle=0;target=4104;
        repeat(30) @(negedge wr_clk);
        if(!wr_full) $fatal(1,"Expected buffered data before reset");
        restart();target=1024;writer_running=1;reader_running=1;throttle=1;await_drain();
        $display("PASS video async FIFO: unequal clocks, exact-full protection, synchronous read ordering, 4096 transfers/wraps, stalls, empty counts and coordinated reset recovery.");
        $finish;
    end
endmodule
