`timescale 1ns/1ps
// Extra boundary test, plus the existing FIFO/conflict/fault exercisers below.
module compact_decoded_query_exerciser(output reg finished=0);
    localparam WIDTH=639,HEIGHT=480;
    reg clk=0;always #4 clk=~clk;
    reg rst_n=0,frame_valid=0,in_valid=0,out_ready=0;
    reg [27:0] frame_base=0;
    reg signed [23:0] in_x=0,in_y=0;reg [24:0] in_tag=0;
    wire frame_ready,in_ready,out_valid,arvalid,failed;
    wire [23:0] p00,p10,p01,p11;wire [7:0] fx,fy,fault;wire [24:0] out_tag;
    wire [27:0] araddr;wire [3:0] arlen;wire [31:0] hits,misses,completed;
    ddr_compact_neighbour_cache_core #(.WIDTH(WIDTH),.HEIGHT(HEIGHT),.TAG_W(25)) dut(
        .clk(clk),.rst_n(rst_n),.frame_valid(frame_valid),.frame_ready(frame_ready),.frame_base(frame_base),
        .in_valid(in_valid),.in_ready(in_ready),.in_x(in_x),.in_y(in_y),.in_tag(in_tag),
        .out_valid(out_valid),.out_ready(out_ready),.p00(p00),.p10(p10),.p01(p01),.p11(p11),
        .fx(fx),.fy(fy),.out_tag(out_tag),.araddr(araddr),.arlen(arlen),.arvalid(arvalid),.arready(1'b0),
        .rdata(256'd0),.rvalid(1'b0),.rlast(1'b0),.rid(4'd0),.failed(failed),.fault(fault),
        .hits(hits),.misses(misses),.completed_queries(completed));
    integer received=0,frames=0;reg checking=0;
    reg [206:0] held_decode;
    reg [37:0] held_selection;reg [27:0] held_read_address;
    wire [206:0] decode_bus={dut.query_x,dut.query_y,dut.query_fx,dut.query_fy,dut.query_tag,
        dut.in_bounds,dut.pixel_number[0],dut.pixel_number[1],dut.pixel_number[2],dut.pixel_number[3]};
    always @(posedge clk)begin
        if(!rst_n)begin received<=0;frames<=0;end
        else begin
            if(failed)$fatal(1,"Unexpected decoded-query fault%h",fault);
            if(frame_valid && frame_ready)begin
                if(checking && frames==1 && received!=3)$fatal(1,"Frame accepted with decoded/results outstanding");
                frames<=frames+1;
            end
            if(checking && out_valid && out_ready)begin
                if(out_tag!==25'h1000101+received || {p00,p10,p01,p11}!==96'd0 || fx!=29 || fy!=77)
                    $fatal(1,"Decoded stall/drain lost ordering, mask, fraction or TAG25");
                received<=received+1;
            end
        end
    end
    task reset_frame;
        begin
            @(negedge clk);rst_n=0;frame_valid=0;in_valid=0;out_ready=0;
            repeat(4)@(negedge clk);rst_n=1;
            @(negedge clk);frame_valid=1;frame_base=0;
            do @(posedge clk);while(!frame_ready);
            @(negedge clk);frame_valid=0;
        end
    endtask
    task send_query(input integer x,input integer y,input [24:0] tag);
        begin
            @(negedge clk);in_valid=1;in_x=x;in_y=y;in_tag=tag;
            do @(posedge clk);while(!in_ready);
            @(negedge clk);in_valid=0;
        end
    endtask
    task arithmetic_case(input integer x,input integer y);
        longint signed xx,yy,number;
        begin
            reset_frame();send_query(x,y,25'h1000001);
            if(!dut.query_valid || dut.query_x!==($signed(x)>>>8) || dut.query_y!==($signed(y)>>>8) ||
                dut.query_fx!==x[7:0] || dut.query_fy!==y[7:0] || dut.query_tag!==25'h1000001)
                $fatal(1,"Decoded XY/fraction/TAG25 differs");
            for(integer j=0;j<4;j=j+1)begin
                xx=($signed(x)>>>8)+(j%2);yy=($signed(y)>>>8)+(j/2);number=yy*639+xx;
                if(dut.pixel_number[j]!==number[31:0] || dut.in_bounds[j]!=(xx>=0 && xx<639 && yy>=0 && yy<480))
                    $fatal(1,"Signed17/32 odd-WIDTH neighbour decode differs at%0d",j);
            end
            held_decode=decode_bus;in_x=24'sh7fffaa;in_y=24'sh800055;in_tag=0;#0.1;
            if(decode_bus!==held_decode)$fatal(1,"Input combinationally changes decoded head");
        end
    endtask
    initial begin
        arithmetic_case(-1,-1);arithmetic_case(0,0);arithmetic_case(638*256+255,479*256+255);
        arithmetic_case(639*256,480*256);arithmetic_case(24'sh7fffff,24'sh7fffff);
        arithmetic_case(-8388608,-8388608);
        $display("PASS decoded signed17/32 odd-WIDTH639 corner/negative/extreme arithmetic and input isolation");
        reset_frame();send_query(127*256+29,3*256+77,25'h1000081);
        wait(dut.state==dut.CHECK);@(negedge clk);
        if(arvalid || misses || dut.selected_block!==25'd15 || dut.selected_line!==3'd7 ||
           dut.selected_pixel_address!==9'd510 || dut.selected_parity!==1'b0)
            $fatal(1,"Slow SELECT did not register signed linear address before tag/miss decision");
        held_selection={dut.selected_block,dut.selected_line,dut.selected_pixel_address,dut.selected_parity};
        in_x=24'sh800000;in_y=24'sh7fffff;in_tag=0;
        @(negedge clk);
        if(dut.state!=dut.AR || !arvalid || misses!=1 || araddr!=28'd960)$fatal(1,"Registered CHECK miss/address transition differs");
        held_read_address=araddr;frame_valid=1;frame_base=262144;
        repeat(12)begin @(negedge clk);
            if(!arvalid || araddr!==held_read_address || frame_ready || in_ready ||
               {dut.selected_block,dut.selected_line,dut.selected_pixel_address,dut.selected_parity}!==held_selection)
                $fatal(1,"Slow CHECK selected fields/AR reservation changed under stall or pending frame");
        end
        // No AR was accepted (arready is tied0); shared reset is the explicit
        // recovery boundary for this isolated blocked-transaction unit case.
        $display("PASS slow SELECT-CHECK registered address/tag boundary, single miss, AR stall and pending-frame ownership");
        reset_frame();checking=1;
        send_query(-100*256+29,-100*256+77,25'h1000101);
        send_query(-100*256+29,-100*256+77,25'h1000102);
        send_query(-100*256+29,-100*256+77,25'h1000103);
        repeat(3)@(negedge clk);
        if(in_ready || !dut.query_valid || !dut.v0 || !dut.v1)$fatal(1,"Decoded elastic stage did not fill under stall");
        held_decode=decode_bus;frame_valid=1;frame_base=262144;
        repeat(12)begin @(negedge clk);in_x=~in_x;in_y=~in_y;in_tag=~in_tag;
            if(in_ready || frame_ready || decode_bus!==held_decode)$fatal(1,"Decoded head changed or new frame bypassed stalled query");end
        out_ready=1;do @(posedge clk);while(!frame_ready);
        @(negedge clk);frame_valid=0;
        if(received!=3 || dut.query_valid || completed!=3)$fatal(1,"Pending frame blocked decoded/query/result drain");
        $display("PASS decoded elastic stall, full-rate consume/refill eligibility and pending-frame complete drain");finished=1;
    end
    initial begin #1000000;$fatal(1,"Decoded-query directed timeout");end
endmodule

module tb_compact_decoded_query;
    wire decoded_done,fifo_done,normal_done,conflict_done;
    compact_decoded_query_exerciser decoded(decoded_done);
    compact_ready_fifo_exerciser fifo(fifo_done);
    compact_cache_exerciser #(.WIDTH(640),.CONFLICT(0)) normal(normal_done);
    compact_cache_exerciser #(.WIDTH(1024),.CONFLICT(1)) conflict(conflict_done);
    initial begin wait(decoded_done && fifo_done && normal_done && conflict_done);
        $display("PASS compact decoded-query/FIFO2/conflict/fault directed regression");$finish;end
endmodule
