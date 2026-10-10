`timescale 1ns/1ps
// Direct neighbour reference and measured hit initiation interval.
module tb_pipeline_hit_stream;
    reg clk=0;always #4 clk=~clk;
    reg rst_n=0,frame_valid=0,in_valid=0,out_ready=0;
    reg signed [23:0] in_x=0,in_y=0;
    reg [23:0] in_tag=0;
    wire frame_ready,in_ready,out_valid,failed;
    wire [7:0] fault,fx,fy;
    wire [23:0] p00,p10,p01,p11,out_tag;
    wire [27:0] araddr;wire [3:0] arlen;wire arvalid;
    reg [255:0] rdata=0;reg rvalid=0,rlast=0;
    reg active=0;integer beat=0,start_word=0,ticks=0,received=0,burst_count=0;
    wire arready=!active && ticks%5!=0;
    reg signed [23:0] expected_x[0:160],expected_y[0:160];
    ddr_neighbour_cache #(.INDEX_BITS(5),.TIMEOUT_BITS(12)) dut(
        .clk(clk),.rst_n(rst_n),.frame_valid(frame_valid),.frame_ready(frame_ready),.frame_base(28'd0),
        .in_valid(in_valid),.in_ready(in_ready),.in_x(in_x),.in_y(in_y),.in_tag(in_tag),
        .out_valid(out_valid),.out_ready(out_ready),.p00(p00),.p10(p10),.p01(p01),.p11(p11),.fx(fx),.fy(fy),.out_tag(out_tag),
        .araddr(araddr),.arlen(arlen),.arvalid(arvalid),.arready(arready),
        .rdata(rdata),.rvalid(rvalid),.rlast(rlast),.rid(4'd0),.failed(failed),.fault(fault),.hits(),.misses(),.completed_queries());
    function [15:0] pattern(input integer index);
        pattern=((index*37)^16'h913a)&16'hffff;
    endfunction
    function [23:0] pixel(input integer x,input integer y);
        reg [15:0] p;
        begin
            if(x<0 || x>=640 || y<0 || y>=480) pixel=0;
            else begin p=pattern(y*640+x);pixel={p[15:11],p[15:13],p[10:5],p[10:9],p[4:0],p[4:2]};end
        end
    endfunction
    integer j,x,y;
    reg held=0;reg [135:0] held_value;
    always @(posedge clk) begin
        ticks<=ticks+1;
        rvalid<=0;rlast<=0;
        if(arvalid && arready) begin
            if(active || arlen!=7 || araddr[5:0]!=0) $fatal(1,"Bad burst");
            active<=1;beat<=0;start_word<=araddr/8;burst_count<=burst_count+1;
        end
        if(active && ticks%7>=2) begin
            rvalid<=1;rlast<=beat==7;
            for(j=0;j<16;j=j+1) rdata[j*16 +:16]<=pattern((start_word+beat)*16+j);
            if(beat==7) active<=0;else beat<=beat+1;
        end
        if(rst_n) begin
            if(failed) $fatal(1,"Unexpected fault %h",fault);
            if(held && (!out_valid || {p00,p10,p01,p11,fx,fy,out_tag}!==held_value)) $fatal(1,"Held output changed");
            held<=out_valid && !out_ready;held_value<={p00,p10,p01,p11,fx,fy,out_tag};
            if(out_valid && out_ready) begin
                if(out_tag!==received) $fatal(1,"Order mismatch expected=%0d actual=%0d",received,out_tag);
                x=$signed(expected_x[received])>>>8;y=$signed(expected_y[received])>>>8;
                if({p00,p10,p01,p11}!=={pixel(x,y),pixel(x+1,y),pixel(x,y+1),pixel(x+1,y+1)} ||
                    fx!==expected_x[received][7:0] || fy!==expected_y[received][7:0]) $fatal(1,"Neighbour mismatch %0d",received);
                received<=received+1;
            end
        end
    end
    task drive(input integer tag,input integer qx,input integer qy);
        begin
            @(negedge clk);in_valid=1;in_x=qx;in_y=qy;in_tag=tag;
            expected_x[tag]=qx;expected_y[tag]=qy;
            do @(posedge clk);while(!in_ready);
        end
    endtask
    integer q,last_accept=-1,hit_bursts,start_tick;
    initial begin
        repeat(8) @(posedge clk);@(negedge clk);rst_n=1;frame_valid=1;
        do @(posedge clk);while(!frame_ready);
        @(negedge clk);frame_valid=0;out_ready=1;
        drive(0,33*256+17,3*256+23);
        @(negedge clk);in_valid=0;wait(received==1);
        hit_bursts=burst_count;start_tick=ticks;
        for(q=1;q<=128;q=q+1) begin
            drive(q,(33+(q%30))*256+(q%256),3*256+(q*7%256));
            if(q<=64 && last_accept>=0 && ticks-last_accept!=1) $fatal(1,"Hit initiation interval >1 at %0d",q);
            last_accept=ticks;
            if(q>=64) begin @(negedge clk);in_valid=0;out_ready=q%5!=0;repeat(q%3) @(posedge clk);out_ready=1;end
        end
        @(negedge clk);in_valid=0;out_ready=1;wait(received==129);
        if(burst_count!=hit_bursts) $fatal(1,"Hot hit stream issued DDR read");
        $display("INFO 64 hot hits accepted on consecutive cycles; 128 hit packets checked with output stalls, DDR reads=%0d",hit_bursts);
        // Miss arriving behind hit packets drains them before the slow backend.
        for(q=129;q<=160;q=q+1) begin
            drive(q,(q%3==0 ? -1:500)*256+127,(q%3==1 ? 479:120)*256+201);
        end
        @(negedge clk);in_valid=0;wait(received==161);
        if(dut.completed_queries!=161) $fatal(1,"Wrong completion count");
        $display("PASS pipeline hit stream: 161 ordered four-neighbour/fraction/tag packets, 64 consecutive-cycle hot accepts, no DDR reads for hot stream, output hold/stalls and hit-to-miss drain with signed border zero.");
        $finish;
    end
    initial begin #10000000;$fatal(1,"Stream timeout");end
endmodule
