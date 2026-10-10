`timescale 1ns/1ps
module tb_ddr_integrity_test;
    reg clk=0;always #4 clk=~clk;
    reg rst_n=0;
    wire [27:0] awaddr,araddr;
    wire [3:0] awlen,arlen,state;
    wire awvalid,arvalid;
    reg awready=0,arready=0,wready=0,wlast=0,rvalid=0,rlast=0;
    reg [255:0] rdata=0;
    wire [255:0] wdata;
    wire [31:0] wstrb,written_beats,read_beats,errors;
    wire [27:0] first_bad_address;
    wire done,failed;wire [7:0] fault,completed_passes;
    reg [3:0] rid=0;
    ddr_integrity_test #(.BLOCKS(4),.PASSES(4),.TIMEOUT_BITS(8)) dut(.*);
    reg [255:0] mem[0:63];
    integer cycle=0,write_base=0,read_base=0,windex=0,rindex=0;
    reg writing=0,reading=0,corrupt=0,hang=0,alias_address=0;
    always @(posedge clk) begin
        if(!rst_n) begin writing=0;reading=0;windex=0;rindex=0;end
        else begin
            if(awvalid && awready) begin
                writing=1;windex=0;write_base=alias_address ? 0 : awaddr/8;
                if(awlen!=15 || awaddr%128) $fatal(1,"Wrong write length/alignment");
            end
            if(wready) begin
                if(!writing || wstrb!==32'hFFFFFFFF) $fatal(1,"Unexpected write");
                mem[write_base+windex]=wdata;
                if(windex==15) writing=0;
                windex=windex+1;
            end
            if(arvalid && arready) begin
                reading=1;rindex=0;read_base=alias_address ? 0 : araddr/8;
                if(arlen!=15 || araddr%128) $fatal(1,"Wrong read length/alignment");
            end
            if(rvalid) begin
                if(rindex==15) reading=0;
                rindex=rindex+1;
            end
        end
    end
    // Deterministic bubbles independently exercise address, write, and read stalls.
    always @(negedge clk) begin
        cycle=cycle+1;
        awready=rst_n && !hang && !writing && cycle%5!=0;
        arready=rst_n && !hang && !reading && cycle%7!=0;
        wready=rst_n && !hang && writing && cycle%3!=0;
        wlast=wready && windex==15;
        rvalid=rst_n && !hang && reading && cycle%4!=0;
        rlast=rvalid && rindex==15;
        rdata=reading ? mem[read_base+rindex] : 0;
        if(corrupt && read_base==32 && rindex==5) rdata[147]=!rdata[147];
    end
    task reset_test;
        begin rst_n=0;repeat(4) @(negedge clk);rst_n=1;end
    endtask
    task await_finish;
        integer timeout;
        begin
            timeout=0;
            while(!done && !failed && timeout<20000) begin @(negedge clk);timeout=timeout+1;end
            if(timeout==20000) $fatal(1,"Testbench timeout");
        end
    endtask
    initial begin
        reset_test();await_finish();
        if(!done || failed || errors || written_beats!=256 || read_beats!=256 || completed_passes!=4)
            $fatal(1,"Good memory rejected counts=%d/%d",written_beats,read_beats);
        corrupt=1;reset_test();await_finish();
        if(!failed || fault!=4 || errors!=1 || first_bad_address!=296 || done)
            $fatal(1,"Corruption not detected errors=%d first=%d",errors,first_bad_address);
        corrupt=0;alias_address=1;reset_test();await_finish();
        if(!failed || fault!=4 || errors!=48) $fatal(1,"Address alias missed");
        alias_address=0;hang=1;reset_test();await_finish();
        if(!failed || fault!=1 || written_beats || read_beats) $fatal(1,"Timeout missed");
        hang=0;reset_test();await_finish();
        if(!done || failed) $fatal(1,"Reset recovery failed");
        $display("PASS DDR integrity: four patterns, address/write/read stalls, corrupted lane, address alias, timeout and reset recovery.");
        $finish;
    end
endmodule
