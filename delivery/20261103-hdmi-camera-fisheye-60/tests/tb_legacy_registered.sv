`timescale 1ns/1ps
module tb_ddr_read_arbiter;
    reg clk=0;always #4 clk=~clk;
    reg rst_n=0,urgent=0;integer mode=0,ticks=0;
    integer seq0=0,seq1=0,p0=0,p1=0;reg active0=0,active1=0;
    function [3:0] len(input integer seq);
        case(seq%4) 0:len=0;1:len=1;2:len=7;3:len=15;endcase
    endfunction
    wire [27:0] a0=28'h1000+(seq0<<7),a1=28'h2000+(seq1<<7);
    wire v0=seq0<12 && !active0,v1=mode==0 && seq1<12 && !active1;
    wire ready0,ready1,rv0,rv1,rl0,rl1;wire [255:0] rd0,rd1;wire [3:0] rid0,rid1;
    wire [27:0] address;wire [3:0] length;wire valid;reg ready=0;
    reg [255:0] data;reg rvalid=0,rlast=0;reg [3:0] rid=0;
    wire failed,busy;wire [7:0] fault;wire arbiter_failed,stage_failed;wire [7:0] arbiter_fault,stage_fault;
    assign failed=arbiter_failed || stage_failed;assign fault=arbiter_failed ? arbiter_fault:stage_fault;wire [31:0] bursts0,bursts1;
    wire [255:0] stage_data;wire stage_valid,stage_last;wire [3:0] stage_id;
    ddr_read_return_register stage(.clk(clk),.rst_n(rst_n),.arvalid(valid),.arready(ready),
        .in_rdata(data),.in_rvalid(rvalid),.in_rlast(rlast),.in_rid(rid),
        .out_rdata(stage_data),.out_rvalid(stage_valid),.out_rlast(stage_last),.out_rid(stage_id),.protocol_fault(stage_failed),.fault_code(stage_fault));
    ddr_read_arbiter #(.TIMEOUT_BITS(7)) dut(.clk(clk),.rst_n(rst_n),.display_urgent(urgent),
        .c0_araddr(a0),.c1_araddr(a1),.c0_arlen(len(seq0)),.c1_arlen(len(seq1)),
        .c0_arvalid(v0),.c1_arvalid(v1),.c0_arready(ready0),.c1_arready(ready1),
        .c0_rdata(rd0),.c1_rdata(rd1),.c0_rvalid(rv0),.c1_rvalid(rv1),
        .c0_rlast(rl0),.c1_rlast(rl1),.c0_rid(rid0),.c1_rid(rid1),
        .araddr(address),.arlen(length),.arvalid(valid),.arready(ready),
        .rdata(stage_data),.rvalid(stage_valid),.rlast(stage_last),.rid(stage_id),
        .failed(arbiter_failed),.fault(arbiter_fault),.busy(busy),.bursts0(bursts0),.bursts1(bursts1));
    integer left=0,response_beat=0,checked=0;reg [27:0] response_addr;
    reg held=0;reg [27:0] heldaddr;reg [3:0] heldlen;
    function [255:0] pattern(input [27:0] addr,input integer beat);
        pattern={8{32'hCA000000 | (addr<<4) | beat}};
    endfunction
    always @(negedge clk) begin
        ticks=ticks+1;urgent=mode==0 && ticks%89<9;
        ready=rst_n && left==0 && ticks%7>=3 && mode!=5;
        rvalid=rst_n && left!=0 && ticks%5!=0 && mode!=3;
        if(mode==4) rvalid=rst_n && !busy;
        rlast=left==1 || (mode==1 && left==2);
        rid=mode==2 ? 1:0;data=pattern(response_addr,response_beat);
    end
    always @(posedge clk) begin
        if(!rst_n) begin
            left<=0;response_beat<=0;held<=0;seq0<=0;seq1<=0;active0<=0;active1<=0;p0<=0;p1<=0;
        end else begin
            if(held && (!valid || address!==heldaddr || length!==heldlen)) $fatal(1,"AR changed while stalled");
            held<=valid && !ready;heldaddr<=address;heldlen<=length;
            if(ready0 && ready1 || rv0 && rv1) $fatal(1,"One read response reached two clients");
            if(ready0) begin active0<=1;p0<=0;end
            if(ready1) begin active1<=1;p1<=0;end
            if(valid && ready) begin
                if(left!=0 || !(ready0 || ready1)) $fatal(1,"Overlapping or unowned read burst");
                left<=length+1;response_addr<=address;response_beat<=0;
            end
            if(rvalid && left!=0) begin left<=left-1;response_beat<=response_beat+1;end
            if(rv0) begin
                if(!active0) $fatal(1,"Client 0 received unsolicited data");
                if(mode==0 && (rd0!==pattern(a0,p0) || rid0!=0 || rl0!=(p0==len(seq0)))) $fatal(1,"Client 0 burst mixed or corrupted");
                p0<=p0+1;checked<=checked+1;
                if(rl0) begin active0<=0;seq0<=seq0+1;end
            end
            if(rv1) begin
                if(!active1) $fatal(1,"Client 1 received unsolicited data");
                if(mode==0 && (rd1!==pattern(a1,p1) || rid1!=0 || rl1!=(p1==len(seq1)))) $fatal(1,"Client 1 burst mixed or corrupted");
                p1<=p1+1;checked<=checked+1;
                if(rl1) begin active1<=0;seq1<=seq1+1;end
            end
        end
    end
    task reset;
        begin @(negedge clk);rst_n=0;repeat(8) @(negedge clk);rst_n=1;end
    endtask
    initial begin
        reset;wait(bursts0==12 && bursts1==12);
        if(failed || checked!=162) $fatal(1,"Read fairness/beat accounting failed");
        mode=1;reset;seq0=1;wait(failed);if(fault!=3) $fatal(1,"Bad RLAST not quarantined");
        repeat(30) @(posedge clk);if(valid || rv0 || rv1) $fatal(1,"Read fault allowed a new owner");
        mode=2;reset;wait(failed);if(fault!=3) $fatal(1,"Bad RID not quarantined");
        mode=3;reset;wait(failed);if(fault!=1) $fatal(1,"Missing read response not timed out");
        mode=4;reset;wait(failed);if(fault!=8'h40 || rv0 || rv1) $fatal(1,"Unsolicited R routed to a client");
        mode=5;reset;wait(valid);repeat(200) @(posedge clk);
        if(failed || !valid || address!=28'h1000) $fatal(1,"AR was withdrawn before acceptance");
        mode=0;reset;wait(left>3);reset;checked=0;wait(bursts0==12 && bursts1==12);
        if(failed || checked!=162) $fatal(1,"Mid-burst reset did not recover");
        $display("PASS DDR read arbitration: two simultaneous clients, 1/2/8/16-beat bursts, exclusive response routing, display urgency, fair whole-burst grants, address/response stalls, RLAST/RID faults, timeout, unsolicited data and reset recovery.");$finish;
    end
    initial begin #20000000;$fatal(1,"Read-arbiter test timed out");end
endmodule
