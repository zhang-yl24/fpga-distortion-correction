`timescale 1ns/1ps
module compact_cache_exerciser #(parameter WIDTH=640,CONFLICT=0)(output reg finished=0);
    localparam HEIGHT=8,BANK_STRIDE=262144;
    reg clk=0;always #4 clk=~clk;
    reg rst_n=0,frame_valid=0,in_valid=0,out_ready=0;
    reg [27:0] frame_base=0;reg signed [23:0] in_x=0,in_y=0;reg [24:0] in_tag=0;
    wire frame_ready,in_ready,out_valid;wire [23:0] p00,p10,p01,p11;
    wire [7:0] fx,fy;wire [24:0] tag;
    wire [27:0] araddr;wire [3:0] arlen;wire arvalid;reg arready=0;
    reg [255:0] rdata=0;reg rvalid=0,rlast=0;reg [3:0] rid=0;
    wire failed;wire [7:0] fault;wire [31:0] hits,misses,completed;
    ddr_neighbour_cache #(.WIDTH(WIDTH),.HEIGHT(HEIGHT),.TAG_W(25),.INDEX_BITS(3),.TIMEOUT_BITS(7)) dut(
        .clk(clk),.rst_n(rst_n),.frame_valid(frame_valid),.frame_ready(frame_ready),.frame_base(frame_base),
        .in_valid(in_valid),.in_ready(in_ready),.in_x(in_x),.in_y(in_y),.in_tag(in_tag),
        .out_valid(out_valid),.out_ready(out_ready),.p00(p00),.p10(p10),.p01(p01),.p11(p11),
        .fx(fx),.fy(fy),.out_tag(tag),.araddr(araddr),.arlen(arlen),.arvalid(arvalid),.arready(arready),
        .rdata(rdata),.rvalid(rvalid),.rlast(rlast),.rid(rid),.failed(failed),.fault(fault),
        .hits(hits),.misses(misses),.completed_queries(completed));
    integer ticks=0,left=0,beat=0,burst_pixel=0,burst_bank=0,bursts=0;
    integer sent=0,received=0,active_bank=0,mode=0;
    reg checking=1,stall_output=0,full_rate=0;
    reg [136:0] expected[0:1023],held_output;
    reg out_held=0,ar_held=0;reg [31:0] held_address;
    function [15:0] word565(input integer position,input integer bank);
        word565=(position*73+16'h5a3+bank*16'h3333)&16'hffff;
    endfunction
    function [23:0] rgb(input integer x,input integer y,input integer bank);
        reg [15:0] p;
        begin
            if(x<0 || x>=WIDTH || y<0 || y>=HEIGHT)rgb=0;
            else begin p=word565(y*WIDTH+x,bank);rgb={p[15:11],p[15:13],p[10:5],p[10:9],p[4:0],p[4:2]};end
        end
    endfunction
    always @(negedge clk)begin
        arready=rst_n && left==0 && ticks%7>=2 && mode!=3;
        rvalid=rst_n && left>0 && ticks%5!=0 && mode!=4;
        rlast=left==1 || (mode==1 && beat==3);rid=mode==2 && beat==5 ? 4'h9:0;
        for(integer lane=0;lane<16;lane=lane+1)rdata[lane*16 +:16]=word565(burst_pixel+beat*16+lane,burst_bank);
        if(mode==5 && rst_n && left==0)rvalid=1;
        out_ready=rst_n && !stall_output && (full_rate || ticks%11>=3);
    end
    always @(posedge clk)begin
        ticks<=ticks+1;
        if(!rst_n)begin
            left<=0;beat<=0;bursts<=0;sent<=0;received<=0;active_bank<=0;
            out_held<=0;ar_held<=0;
        end else begin
            if(ar_held && (!arvalid || {araddr,arlen}!==held_address))$fatal(1,"AR changed under stall WIDTH%0d",WIDTH);
            ar_held<=arvalid && !arready;held_address<={araddr,arlen};
            if(checking)begin
                if(failed)$fatal(1,"Unexpected cache fault WIDTH%0d fault%h",WIDTH,fault);
                if(out_held && (!out_valid || {p00,p10,p01,p11,fx,fy,tag}!==held_output))$fatal(1,"Output changed under backpressure");
                if(in_valid && in_ready)begin
                    expected[sent]<={rgb($signed(in_x)>>>8,$signed(in_y)>>>8,active_bank),
                        rgb(($signed(in_x)>>>8)+1,$signed(in_y)>>>8,active_bank),
                        rgb($signed(in_x)>>>8,($signed(in_y)>>>8)+1,active_bank),
                        rgb(($signed(in_x)>>>8)+1,($signed(in_y)>>>8)+1,active_bank),in_x[7:0],in_y[7:0],in_tag};
                    sent<=sent+1;
                end
                if(out_valid && out_ready)begin
                    if(received>=sent || {p00,p10,p01,p11,fx,fy,tag}!==expected[received])
                        $fatal(1,"Neighbour/fraction/25bit tag mismatch WIDTH%0d query%0d got%h expected%h",WIDTH,received,{p00,p10,p01,p11,fx,fy,tag},expected[received]);
                    received<=received+1;
                end
            end
            out_held<=checking && out_valid && !out_ready;held_output<={p00,p10,p01,p11,fx,fy,tag};
            if(frame_valid && frame_ready)active_bank<=frame_base==BANK_STRIDE;
            if(arvalid && arready)begin
                if(left!=0 || arlen!=7 || araddr[5:0]!=0)$fatal(1,"Wrong DDR reservation/burst");
                burst_bank<=araddr>=BANK_STRIDE;
                burst_pixel<=(araddr>=BANK_STRIDE ? araddr-BANK_STRIDE:araddr)*2;
                if((araddr>=BANK_STRIDE ? araddr-BANK_STRIDE:araddr)*2+127>=WIDTH*HEIGHT)$fatal(1,"Read outside source");
                left<=8;beat<=0;bursts<=bursts+1;
            end
            if(rvalid && left>0)begin left<=left-1;beat<=beat+1;end
        end
    end
    task reset_all;
        begin
            @(negedge clk);rst_n=0;frame_valid=0;in_valid=0;mode=0;stall_output=0;full_rate=0;
            repeat(8)@(negedge clk);rst_n=1;repeat(2)@(negedge clk);
        end
    endtask
    task select_frame(input [27:0] address);
        begin
            @(negedge clk);frame_valid=1;frame_base=address;
            do @(posedge clk);while(!frame_ready);
            @(negedge clk);frame_valid=0;
        end
    endtask
    task query(input integer x,input integer y,input [24:0] qtag);
        begin
            @(negedge clk);in_valid=1;in_x=x;in_y=y;in_tag=qtag;
            do @(posedge clk);while(!in_ready);
            @(negedge clk);in_valid=0;in_x=24'sh7fff00;in_y=24'sh7fff00;in_tag=0;
            frame_base=28'h1234500; // Non-handshaken changes must not affect locked source base.
        end
    endtask
    task drain;
        integer timeout;
        begin
            timeout=0;while(received<sent && timeout<10000)begin @(negedge clk);timeout=timeout+1;end
            if(received!=sent || completed!=received)$fatal(1,"Query did not terminate under conflicts/backpressure");
        end
    endtask
    task fault_case(input integer kind,input [7:0] code);
        begin
            checking=0;reset_all();select_frame(0);mode=kind;
            if(kind!=5)query(127*256+63,0,25'h1000011);
            wait(failed);repeat(3)@(negedge clk);
            if(fault!=code || in_ready || frame_ready || out_valid)$fatal(1,"Fault not quarantined kind%0d code%h",kind,fault);
            if(kind==3 && !arvalid)$fatal(1,"Timed-out stalled AR was withdrawn");
            if(dut.valid_lines[dut.selected_line])$fatal(1,"Faulted fill committed a valid line");
            repeat(15)@(negedge clk);if(!failed || fault!=code)$fatal(1,"Fault not sticky");
        end
    endtask
    integer before_bursts,before_ticks,goal,yfast;
    initial begin
        reset_all();select_frame(0);
        query(127*256+53,0,25'h1000001);drain();
        if(bursts!=4)$fatal(1,"Four independent boundary neighbours not fetched");
        query(-1,-1,25'h1000002);drain();
        query((WIDTH-1)*256+200,(HEIGHT-1)*256+63,25'h1000003);drain();
        before_bursts=bursts;select_frame(0);query((WIDTH-1)*256+200,(HEIGHT-1)*256+63,25'h1000004);drain();
        if(bursts<=before_bursts)$fatal(1,"Same bank reuse did not invalidate tags");
        select_frame(BANK_STRIDE);query((WIDTH-1)*256+200,(HEIGHT-1)*256+63,25'h1000005);drain();
        yfast=CONFLICT ? HEIGHT-1:0;
        query(17*256+29,yfast*256+77,25'h1000006);drain();before_bursts=bursts;
        full_rate=1;goal=sent+80;before_ticks=ticks;
        @(negedge clk);in_valid=1;
        for(integer j=0;j<80;j=j+1)begin
            in_x=(17+j%32)*256+29;in_y=yfast*256+77;in_tag=25'h1000100+j;
            do @(posedge clk);while(!in_ready);
            @(negedge clk);
        end
        in_valid=0;drain();
        if(bursts!=before_bursts || ticks-before_ticks>86 || sent!=goal)$fatal(1,"Fast all-hit pipeline lost throughput or refilled WIDTH%0d",WIDTH);
        stall_output=1;query(17*256+29,yfast*256+77,25'h1000201);query(18*256+29,yfast*256+77,25'h1000202);
        frame_valid=1;frame_base=0;repeat(12)@(negedge clk);
        if(frame_ready)$fatal(1,"Bank change accepted before backpressured results drained");
        stall_output=0;do @(posedge clk);while(!frame_ready);@(negedge clk);frame_valid=0;drain();
        $display("PASS compact cache WIDTH%0d: locked conflict neighbours, negative/border zero, same/new-bank invalidation,25bit tags,80fast hit queries and backpressure",WIDTH);
        fault_case(1,8'h03);fault_case(2,8'h03);fault_case(3,8'h01);fault_case(4,8'h01);fault_case(5,8'h04);
        $display("PASS compact cache WIDTH%0d: RLAST/RID,AR/FILL timeout,unsolicitedR quarantine and ARVALID hold",WIDTH);
        finished=1;
    end
    initial begin #3000000;$fatal(1,"Compact directed timeout WIDTH%0d",WIDTH);end
endmodule

module tb_compact_neighbour_cache;
    wire normal_done,conflict_done;
    compact_cache_exerciser #(.WIDTH(640),.CONFLICT(0)) normal(normal_done);
    compact_cache_exerciser #(.WIDTH(1024),.CONFLICT(1)) conflict(conflict_done);
    initial begin wait(normal_done && conflict_done);$display("PASS compact unified neighbour cache directed regression");$finish;end
endmodule
