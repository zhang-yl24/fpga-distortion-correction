`timescale 1ns/1ps
`include "D:/English/FPGA/distortion/build/pipeline_parity_query_sim/counts.vh"
module tb_pipeline_hit_query;
    localparam N=`REMAP_QUERIES,TOTAL=`REMAP_TOTAL,BANK_STRIDE=262144;
    reg clk=0;always #4 clk=~clk;
    reg rst_n=0,frame_valid=0,in_valid=0;
    reg [27:0] frame_base=0;
    reg signed [23:0] in_x=0,in_y=0;
    reg [23:0] in_tag=0;
    wire frame_ready,in_ready,out_valid;reg out_ready=0;
    wire [23:0] out_rgb,out_tag;
    wire [27:0] araddr;wire [3:0] arlen;wire arvalid,arready;
    reg [255:0] rdata=0;reg rvalid=0,rlast=0;reg [3:0] rid=0;
    wire failed;wire [7:0] fault;wire [31:0] hits,misses,completed_queries;
    reg signed [31:0] rot_cos,rot_sin;reg [63:0] rotations[0:2];
    rotated_remap_core #(.INDEX_BITS(5),.TIMEOUT_BITS(10),.MAX_RADIUS_Q22(1976439)) dut( .clk(clk),.rst_n(rst_n),.frame_valid(frame_valid),.frame_ready(frame_ready),.frame_base(frame_base),
        .cfg_rot_cx(24'sd81792),.cfg_rot_cy(24'sd61312),.cfg_rot_cos(rot_cos),.cfg_rot_sin(rot_sin),
        .in_valid(in_valid),.in_ready(in_ready),.in_u(in_x),.in_v(in_y),.in_tag(in_tag),
        .out_valid(out_valid),.out_ready(out_ready),.out_rgb(out_rgb),.out_tag(out_tag),
        .araddr(araddr),.arlen(arlen),.arvalid(arvalid),.arready(arready),.rdata(rdata),.rvalid(rvalid),.rlast(rlast),.rid(rid),
        .failed(failed),.fault(fault),.hits(hits),.misses(misses),.completed_queries(completed_queries),.cfg_out_cx(24'sh013176),.cfg_out_cy(24'sh00f5d2),.cfg_src_cx(24'sh013176),.cfg_src_cy(24'sh00f5d2),.cfg_src_fx(24'sh025bd5),.cfg_src_fy(24'sh025b25),.cfg_inv_fx(32'sh001b221f),.cfg_inv_fy(32'sh001b2a0b),.cfg_k1(32'sh00057007),.cfg_k2(32'shffef399e),.cfg_k3(32'sh000b7d54),.cfg_p1(32'sh00000000),.cfg_p2(32'sh00000000));
    reg [255:0] frame0[0:19199],frame1[0:19199],frame2[0:19199];
    reg [167:0] vectors[0:TOTAL-1];
    reg [48:0] mapped[0:TOTAL-1];
    integer ticks=0,received=0,samples=0,burst_count=0,phase=0,mode=0;
    integer beat=0,base_word=0,bank=0,delay_count=0;
    reg active=0,checking=1;
    assign arready=rst_n && !active && ticks%7!=0 && ticks%7!=1 && mode!=3;
    reg held=0,arheld=0;
    reg [47:0] held_output;
    reg [31:0] held_address;
    always @(posedge clk) begin
        if(!rst_n) begin
            ticks<=0;held<=0;arheld<=0;
        end else begin
            ticks<=ticks+1;
            if(held && (!out_valid || {out_tag,out_rgb}!==held_output))
                $fatal(1,"Output changed while backpressured");
            held<=out_valid && !out_ready;held_output<={out_tag,out_rgb};
            if(arheld && (!arvalid || {araddr,arlen}!==held_address))
                $fatal(1,"DDR address changed before AR handshake");
            arheld<=arvalid && !arready;held_address<={araddr,arlen};
            if(checking && dut.mapped_valid && dut.mapped_ready) begin
                if({dut.mapped_black,dut.mapped_x,dut.mapped_y}!==mapped[dut.mapped_tag])
                    $fatal(1,"Composed mapper coordinate mismatch tag=%0d",dut.mapped_tag);
            end
            if(checking && out_valid && out_ready) begin
                if(out_tag!==received || out_rgb!==vectors[received][23:0])
                    $fatal(1,"RGB/tag mismatch query %0d tag=%0d RGB=%h expected=%h",received,out_tag,out_rgb,vectors[received][23:0]);
                received<=received+1;
            end
            if(checking && dut.sampler.sample_valid && dut.sampler.sample_ready) begin
                if({dut.sampler.p00,dut.sampler.p10,dut.sampler.p01,dut.sampler.p11}!==vectors[dut.sampler.sample_tag][119:24])
                    $fatal(1,"Independent neighbours mismatch tag=%0d got=%h expected=%h",dut.sampler.sample_tag,{dut.sampler.p00,dut.sampler.p10,dut.sampler.p01,dut.sampler.p11},vectors[dut.sampler.sample_tag][119:24]);
                samples<=samples+1;
            end
            if(checking && failed) $fatal(1,"Unexpected sampler fault %h",fault);
        end
    end
    // Registered DDR response with variable latency, inter-beat bubbles and
    // eight unbackpressurable responses; no read-ready signal is available.
    always @(posedge clk) begin
        if(!rst_n) begin
            active<=0;beat<=0;base_word<=0;bank<=0;delay_count<=0;
            rvalid<=0;rlast<=0;rid<=0;rdata<=0;burst_count<=0;
        end else begin
            rvalid<=0;rlast<=0;rid<=0;
            if(arvalid && arready) begin
                if(active || arlen!=7 || araddr[5:0]!=0)
                    $fatal(1,"Invalid/outstanding/unaligned DDR burst addr=%h",araddr);
                active<=1;beat<=0;delay_count<=3+(ticks%5);
                bank<=araddr>=BANK_STRIDE;
                base_word<=(araddr>=BANK_STRIDE ? araddr-BANK_STRIDE:araddr)>>3;
                burst_count<=burst_count+1;
            end
            if(active && mode!=3) begin
                if(delay_count>0) delay_count<=delay_count-1;
                else if(ticks%11!=0 && ticks%11!=1 && ticks%11!=2) begin
                    if(base_word+beat>=19200) $fatal(1,"Read outside full frame");
                    rvalid<=1;rlast<=beat==7 || (mode==1 && beat==3);
                    rid<=mode==2 && beat==5 ? 4'h9:0;
                    rdata<=bank ? frame1[base_word+beat] : phase==2 ? frame2[base_word+beat]:frame0[base_word+beat];
                    if(beat==7) active<=0;else beat<=beat+1;
                end
            end
            if(mode==4 && !active) begin rvalid<=1;rdata<=0;end
        end
    end
    always @(negedge clk) out_ready=rst_n && (ticks%17>=4);
    task select_frame(input [27:0] address);
        begin
            @(negedge clk);{rot_cos,rot_sin}=rotations[phase<3 ? phase:0];frame_valid=1;frame_base=address;
            do @(posedge clk); while(!frame_ready);
            @(negedge clk);frame_valid=0;
        end
    endtask
    task send_query(input integer index);
        begin
            @(negedge clk);in_valid=1;
            in_x=vectors[index][167:144];in_y=vectors[index][143:120];in_tag=index;
            do @(posedge clk);while(!in_ready);
            @(negedge clk);in_valid=0;
        end
    endtask
    task reset_all;
        begin
            @(negedge clk);rst_n=0;in_valid=0;frame_valid=0;
            repeat(8) @(posedge clk);
            @(negedge clk);rst_n=1;
        end
    endtask
    task fault_case(input integer kind,input [7:0] expected);
        begin
            checking=0;mode=0;phase=0;reset_all();select_frame(0);mode=kind;
            if(kind!=4) send_query(0);
            wait(failed);#1;
            if(fault!=expected || (kind!=3 && arvalid) || in_ready || dut.sampler.sample_valid)
                $fatal(1,"Fault %0d not safely rejected code=%h",kind,fault);
            repeat(25) @(posedge clk);
            if(!failed || fault!=expected) $fatal(1,"Fault did not remain latched");
        end
    endtask
    integer q;
    initial begin
        $readmemh("frame0.mem",frame0);$readmemh("frame1.mem",frame1);$readmemh("frame2.mem",frame2);
        $readmemh("rotations.mem",rotations);$readmemh("vectors.mem",vectors);$readmemh("mapped.mem",mapped);
        reset_all();
        for(phase=0;phase<3;phase=phase+1) begin
            select_frame(phase==1 ? BANK_STRIDE:0);
            for(q=phase*N;q<(phase+1)*N;q=q+1) send_query(q);
            wait(received==(phase+1)*N);
            if(samples!=(phase+1)*N) $fatal(1,"Lost neighbour packet");
            $display("INFO frame %0d matched %0d queries, hit=%0d miss=%0d",phase,N,hits,misses);
        end
        if(hits<=misses || misses!=burst_count) $fatal(1,"Cache not reused or bursts not accounted");
        if(completed_queries!=TOTAL) $fatal(1,"Completion count wrong");
        $display("INFO three frames passed; injecting protocol and timeout faults");
        fault_case(1,8'h03);fault_case(2,8'h03);fault_case(3,8'h01);fault_case(4,8'h04);
        // Reset during an outstanding DDR transaction: no stale cache tag/output.
        checking=0;mode=0;phase=0;reset_all();select_frame(0);send_query(0);
        wait(active);repeat(3) @(posedge clk);reset_all();
        received=0;samples=0;checking=1;select_frame(0);
        for(q=0;q<64;q=q+1) send_query(q);
        wait(received==64);
        $display("PASS pipeline hit composed rotation -> bounded Brown -> DDR neighbours -> bilinear: %0d Python golden queries, four neighbours and RGB888 each compared; signed floor, borders, burst boundaries, cache conflicts, bank switch, same-bank new frame, variable DDR stalls, output backpressure, malformed RLAST/RID, timeout, unsolicited responses and mid-burst reset recovery.",TOTAL);
        $finish;
    end
    initial begin #100000000;$fatal(1,"Global remap simulation timeout received=%0d state=%0d",received,dut.sampler.cache.backend.state);end
endmodule
