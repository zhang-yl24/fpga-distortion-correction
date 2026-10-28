`timescale 1ns/1ps
module compact_ready_fifo_exerciser(output reg finished=0);
    localparam WIDTH=640,HEIGHT=2,STRIDE=262144;
    reg clk=0;always #4 clk=~clk;
    reg rst_n=0,frame_valid=0,in_valid=0,out_ready=0,allow_ar=0,bad_rid=0;
    reg [27:0] frame_base=0;reg signed [23:0] in_x=0,in_y=0;reg [24:0] in_tag=0;
    wire frame_ready,in_ready,out_valid,arvalid,failed;
    wire [23:0] p00,p10,p01,p11;wire [7:0] fx,fy,fault;wire [24:0] out_tag;
    wire [27:0] araddr;wire [3:0] arlen;reg arready=0;
    reg [255:0] rdata=0;reg rvalid=0,rlast=0;reg [3:0] rid=0;
    wire [31:0] hits,misses,completed;
    ddr_neighbour_cache #(.WIDTH(WIDTH),.HEIGHT(HEIGHT),.TAG_W(25),.INDEX_BITS(5),.TIMEOUT_BITS(10)) dut(
        .clk(clk),.rst_n(rst_n),.frame_valid(frame_valid),.frame_ready(frame_ready),.frame_base(frame_base),
        .in_valid(in_valid),.in_ready(in_ready),.in_x(in_x),.in_y(in_y),.in_tag(in_tag),
        .out_valid(out_valid),.out_ready(out_ready),.p00(p00),.p10(p10),.p01(p01),.p11(p11),
        .fx(fx),.fy(fy),.out_tag(out_tag),.araddr(araddr),.arlen(arlen),.arvalid(arvalid),.arready(arready),
        .rdata(rdata),.rvalid(rvalid),.rlast(rlast),.rid(rid),.failed(failed),.fault(fault),
        .hits(hits),.misses(misses),.completed_queries(completed));
    integer sent=0,received=0,bank=0,frame_count=0,left=0,beat=0,read_pixel=0,read_bank=0;
    reg checking=1;reg [136:0] expected[0:31],held;reg was_held=0;
    function [15:0] pixel(input integer pos,input integer b);
        pixel=(pos*73+16'h5a3+b*16'h3333)&16'hffff;
    endfunction
    function [23:0] rgb(input integer x,input integer y,input integer b);
        reg [15:0] p;
        begin
            if(x<0 || x>=WIDTH || y<0 || y>=HEIGHT)rgb=0;
            else begin p=pixel(y*WIDTH+x,b);rgb={p[15:11],p[15:13],p[10:5],p[10:9],p[4:0],p[4:2]};end
        end
    endfunction
    always @(negedge clk)begin
        arready=rst_n && allow_ar && left==0;
        rvalid=rst_n && left!=0;rlast=left==1;rid=bad_rid ? 4'h9:0;
        for(integer j=0;j<16;j=j+1)rdata[j*16 +:16]=pixel(read_pixel+beat*16+j,read_bank);
    end
    always @(posedge clk)begin
        if(!rst_n)begin sent<=0;received<=0;bank<=0;frame_count<=0;left<=0;beat<=0;was_held<=0;end
        else begin
            if(frame_valid && frame_ready)begin
                if(frame_count==1 && received<3)$fatal(1,"New source bank accepted before all old queued queries/results drained");
                bank<=frame_base==STRIDE;frame_count<=frame_count+1;
            end
            if(dut.queue_count>2)$fatal(1,"FIFO occupancy overflow");
            if(frame_ready && dut.queue_count!=0)$fatal(1,"Frame ready with pending queued query");
            if(checking)begin
                if(failed)$fatal(1,"Unexpected FIFO cache fault%h",fault);
                if(in_valid && in_ready)begin
                    expected[sent]<={rgb($signed(in_x)>>>8,$signed(in_y)>>>8,bank),
                        rgb(($signed(in_x)>>>8)+1,$signed(in_y)>>>8,bank),
                        rgb($signed(in_x)>>>8,($signed(in_y)>>>8)+1,bank),
                        rgb(($signed(in_x)>>>8)+1,($signed(in_y)>>>8)+1,bank),in_x[7:0],in_y[7:0],in_tag};
                    sent<=sent+1;
                end
                if(was_held && (!out_valid || {p00,p10,p01,p11,fx,fy,out_tag}!==held))$fatal(1,"Queued output changed under backpressure");
                if(out_valid && out_ready)begin
                    if(received>=sent || {p00,p10,p01,p11,fx,fy,out_tag}!==expected[received])
                        $fatal(1,"FIFO ordering/bank/coordinates/25bit metadata differ at%0d",received);
                    received<=received+1;
                end
            end
            was_held<=checking && out_valid && !out_ready;held<={p00,p10,p01,p11,fx,fy,out_tag};
            if(arvalid && arready)begin
                if(arlen!=7 || araddr[5:0]!=0 || left!=0)$fatal(1,"Bad DDR request");
                left<=8;beat<=0;read_bank<=araddr>=STRIDE;
                read_pixel<=(araddr>=STRIDE ? araddr-STRIDE:araddr)*2;
            end
            if(rvalid && left!=0)begin left<=left-1;beat<=beat+1;end
        end
    end
    task reset_all;
        begin
            @(negedge clk);rst_n=0;in_valid=0;frame_valid=0;allow_ar=0;out_ready=0;bad_rid=0;
            repeat(8)@(negedge clk);rst_n=1;repeat(2)@(negedge clk);
        end
    endtask
    task select_bank(input [27:0] address);
        begin @(negedge clk);frame_valid=1;frame_base=address;
            do @(posedge clk);while(!frame_ready);@(negedge clk);frame_valid=0;end
    endtask
    task enqueue(input integer x,input integer y,input [24:0] tag);
        begin @(negedge clk);in_valid=1;in_x=x;in_y=y;in_tag=tag;
            do @(posedge clk);while(!in_ready);@(negedge clk);in_valid=0;end
    endtask
    initial begin
        reset_all();
        for(integer i=0;i<4;i=i+1)begin in_x=i*12345;in_y=-i*999;#0.1;if(in_ready)$fatal(1,"Ready before first frame handshake");end
        select_bank(0);enqueue(29,77,25'h1000001);wait(arvalid);
        enqueue(10*256+11,67,25'h1000002);
        if(dut.queue_count!=1 || dut.inner_in_ready || !in_ready)$fatal(1,"Registered queue spare slot incorrectly depends on inner ready");
        for(integer i=0;i<8;i=i+1)begin
            in_x=i%2 ? -1:24'sh7fff00;in_y=i*971;in_tag=25'h1000fff^i;#0.1;
            if(!in_ready || dut.queue_count!=1)$fatal(1,"Input ready combinationally depends on current XY/tag");
        end
        enqueue(127*256+23,81,25'h1000003);
        if(dut.queue_count!=2 || in_ready)$fatal(1,"FIFO2 did not apply full backpressure");
        frame_base=STRIDE;frame_valid=1;
        repeat(8)begin @(negedge clk);in_x=~in_x;in_y=~in_y;
            if(in_ready || frame_ready || dut.queue_count!=2)$fatal(1,"Full/pending-frame state changed combinationally");end
        allow_ar=1;wait(out_valid);repeat(12)@(negedge clk);
        if(frame_ready || received || dut.queue_count!=2)$fatal(1,"Downstream backpressure lost queued ownership");
        out_ready=1;
        do @(posedge clk);while(!frame_ready);
        @(negedge clk);frame_valid=0;
        if(received!=3 || dut.queue_count!=0)$fatal(1,"Frame pending prevented FIFO drain");
        enqueue(1*256+15,99,25'h1000004);wait(received==4);@(negedge clk);
        if(completed!=4)$fatal(1,"Lost query completion");
        $display("PASS FIFO2 ready boundary: no XY/inner-ready combinational dependency, loaded-only admission, full backpressure, ordered25bit metadata, pending-frame drain and bank handoff");
        checking=0;reset_all();select_bank(0);enqueue(29,77,25'h1000011);wait(arvalid);
        enqueue(10*256+11,67,25'h1000012);enqueue(127*256+23,81,25'h1000013);
        bad_rid=1;allow_ar=1;out_ready=1;wait(failed);repeat(3)@(negedge clk);
        if(fault!=8'h03 || in_ready || frame_ready || out_valid || dut.queue_count!=2)$fatal(1,"Failure not propagated with queued queries quarantined");
        $display("PASS FIFO2 queued fault quarantine");finished=1;
    end
    initial begin #1000000;$fatal(1,"FIFO2 ready regression timeout");end
endmodule

module tb_compact_ready_fifo2;
    wire fifo_done,normal_done,conflict_done;
    compact_ready_fifo_exerciser fifo(fifo_done);
    compact_cache_exerciser #(.WIDTH(640),.CONFLICT(0)) normal(normal_done);
    compact_cache_exerciser #(.WIDTH(1024),.CONFLICT(1)) conflict(conflict_done);
    initial begin wait(fifo_done && normal_done && conflict_done);$display("PASS compact FIFO2 ready and preserved private algorithm regression");$finish;end
endmodule
