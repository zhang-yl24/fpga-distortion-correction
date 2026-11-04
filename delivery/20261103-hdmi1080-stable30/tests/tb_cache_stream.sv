`timescale 1ns/1ps
// Full 1920x1080 raster of fractional coordinates, independently checked
// against a synthetic DDR image. This isolates cache throughput; it excludes
// mapper, result writer, capture/display contention and physical DDR timing.
module tb_cache_stream;
    localparam WIDTH=1920,HEIGHT=1080,QUERIES=WIDTH*HEIGHT;
    reg clk=0; always #4 clk=~clk;
    reg rst_n=0,frame_valid=0,in_valid=0,out_ready=0;
    wire frame_ready,in_ready,out_valid,failed;
    reg signed [23:0] in_x=0,in_y=0;
    reg [24:0] in_tag=0;
    wire [23:0] p00,p10,p01,p11;
    wire [7:0] fx,fy,fault;
    wire [24:0] out_tag;
    wire [27:0] araddr;
    wire [3:0] arlen;
    wire arvalid;
    reg arready=0,rvalid=0,rlast=0;
    reg [255:0] rdata=0;
    wire [31:0] hits,misses,completed_queries;
    ddr_neighbour_cache_scatter4_tag_prefetch_local #(
        .WIDTH(WIDTH),.HEIGHT(HEIGHT),.TAG_W(25),.INDEX_BITS(7),.TIMEOUT_BITS(12)) dut(
        .clk(clk),.rst_n(rst_n),.frame_valid(frame_valid),.frame_ready(frame_ready),.frame_base(28'd0),
        .in_valid(in_valid),.in_ready(in_ready),.in_x(in_x),.in_y(in_y),.in_tag(in_tag),
        .out_valid(out_valid),.out_ready(out_ready),.p00(p00),.p10(p10),.p01(p01),.p11(p11),
        .fx(fx),.fy(fy),.out_tag(out_tag),.araddr(araddr),.arlen(arlen),.arvalid(arvalid),.arready(arready),
        .rdata(rdata),.rvalid(rvalid),.rlast(rlast),.rid(4'd0),.failed(failed),.fault(fault),
        .hits(hits),.misses(misses),.completed_queries(completed_queries));

    integer ticks=0,sent=0,received=0,start_tick=-1;
    integer left=0,beat=0,burst_pixel=0,bursts=0,scatter=0,zero_latency=0;
    reg started=0,held=0,ar_held=0;
    reg [136:0] held_data;
    reg [31:0] held_address;
    function automatic [15:0] word565(input integer pos);
        word565=(pos*73+16'h05a3+(pos>>7)*337+(pos^(pos>>4))*11)&16'hffff;
    endfunction
    function automatic [23:0] golden(input integer x,input integer y);
        reg [15:0] pixel;
        begin
            if(x<0 || x>=WIDTH || y<0 || y>=HEIGHT)golden=0;
            else begin
                pixel=word565(y*WIDTH+x);
                golden={pixel[15:11],pixel[15:13],pixel[10:5],pixel[10:9],pixel[4:0],pixel[4:2]};
            end
        end
    endfunction
    function automatic [24:0] tag(input integer number);
        tag=number ^ 25'h1000000;
    endfunction
    function automatic [7:0] fraction_x(input integer number);
        fraction_x=number*7;
    endfunction
    function automatic [7:0] fraction_y(input integer number);
        fraction_y=number*13;
    endfunction

    always @(negedge clk)begin
        arready=rst_n && left==0 && ticks%7>=2;
        rvalid=rst_n && ((left>0 && ticks%5!=0) || (left==0 && arvalid && arready && ticks%3==0));
        rlast=left==1;
        for(integer lane=0;lane<16;lane=lane+1)
            rdata[lane*16+:16]=word565((left>0 ? burst_pixel+beat*16:araddr*2)+lane);
        out_ready=rst_n && ticks%11>=3;
        in_valid=rst_n && started && sent<QUERIES;
        in_x=(sent%WIDTH)*256+fraction_x(sent);
        in_y=(sent/WIDTH)*256+fraction_y(sent);
        in_tag=tag(sent);
    end
    always @(posedge clk)begin
        ticks<=ticks+1;
        if(rst_n)begin
            if(failed)$fatal(1,"cache full stream fault=%h",fault);
            if(held && (!out_valid || {p00,p10,p01,p11,fx,fy,out_tag}!==held_data))
                $fatal(1,"cache full stream output changed under backpressure");
            held<=out_valid&&!out_ready;held_data<={p00,p10,p01,p11,fx,fy,out_tag};
            if(ar_held && (!arvalid || {araddr,arlen}!==held_address))
                $fatal(1,"cache full stream AR changed under backpressure");
            ar_held<=arvalid&&!arready;held_address<={araddr,arlen};
            if(in_valid&&in_ready)begin
                if(start_tick<0)start_tick<=ticks;
                sent<=sent+1;
            end
            if(out_valid&&out_ready)begin
                if(received>=sent || {p00,p10,p01,p11,fx,fy,out_tag}!=={
                    golden(received%WIDTH,received/WIDTH),golden(received%WIDTH+1,received/WIDTH),
                    golden(received%WIDTH,received/WIDTH+1),golden(received%WIDTH+1,received/WIDTH+1),
                    fraction_x(received),fraction_y(received),tag(received)})
                    $fatal(1,"cache full stream independent pixel/metadata mismatch at query %0d",received);
                received<=received+1;
            end
            if(arvalid&&arready)begin
                if(left!=0 || arlen!=7 || araddr[5:0]!=0 || araddr*2+127>=WIDTH*HEIGHT)
                    $fatal(1,"cache full stream invalid DDR reservation");
                burst_pixel<=araddr*2;
                left<=rvalid ? 7:8;beat<=rvalid ? 1:0;bursts<=bursts+1;
                if(rvalid)zero_latency<=zero_latency+1;
            end
            if(rvalid&&left>0)begin left<=left-1;beat<=beat+1;end
            if(dut.inner.scatter_write)scatter<=scatter+1;
        end
    end
    initial begin
        repeat(6)@(negedge clk);rst_n=1;
        @(negedge clk);frame_valid=1;
        do @(posedge clk);while(!frame_ready);
        @(negedge clk);frame_valid=0;started=1;
        wait(received==QUERIES);
        @(negedge clk);
        if(sent!=QUERIES || completed_queries!=QUERIES || left!=0 || zero_latency==0)
            $fatal(1,"cache full stream incomplete drain/coverage");
        $display("CACHE_METRICS cycles=%0d queries=%0d bursts=%0d scatter=%0d hits=%0d misses=%0d",
            ticks-start_tick,received,bursts,scatter,hits,misses);
        $display("PASS CACHE STREAM all %0d independent four-neighbour outputs, zero-latency first beat coverage=%0d",received,zero_latency);
        $finish;
    end
    initial begin #100000000;$fatal(1,"cache full stream bounded timeout");end
endmodule
