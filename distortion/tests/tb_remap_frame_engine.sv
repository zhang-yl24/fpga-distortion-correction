`timescale 1ns/1ps
module tb_remap_frame_engine;
    reg clk=0;always #4 clk=~clk;
    reg rst_n=0,frame_valid=0;wire frame_ready;
    reg [27:0] source_base=0,output_base=2048;reg [31:0] frame_id=1;
    reg signed [23:0] src_cx=3968;reg signed [31:0] k1=0;
    wire [27:0] a1,araddr,awaddr;wire [3:0] l1,arlen,awlen;
    wire av1,ar1,arvalid,awvalid;reg arready=0,awready=0;
    reg [255:0] rdata=0;reg rvalid=0,rlast=0;reg [3:0] rid=0;
    wire [255:0] coredata,wdata;wire corerv,corerl;wire [3:0] corerid;wire [31:0] wstrb;
    reg wready=0,wlast=0;
    wire done,failed;wire [7:0] fault;wire [27:0] completed_base;
    wire [31:0] completed_id,completed_crc,hits,misses,queries;
    remap_frame_engine #(.WIDTH(32),.HEIGHT(16),.TIMEOUT_BITS(12)) dut(
        .clk(clk),.rst_n(rst_n),.frame_valid(frame_valid),.frame_ready(frame_ready),
        .source_base(source_base),.output_base(output_base),.frame_id(frame_id),
        .cfg_out_cx(24'sd3968),.cfg_out_cy(24'sd1920),.cfg_src_cx(src_cx),.cfg_src_cy(24'sd1920),
        .cfg_src_fx(24'sd8192),.cfg_src_fy(24'sd8192),.cfg_inv_fx(32'sh02000000),.cfg_inv_fy(32'sh02000000),
        .cfg_k1(k1),.cfg_k2(32'sd0),.cfg_k3(32'sd0),.cfg_p1(32'sd0),.cfg_p2(32'sd0),
        .araddr(a1),.arlen(l1),.arvalid(av1),.arready(ar1),.rdata(coredata),.rvalid(corerv),.rlast(corerl),.rid(corerid),
        .awaddr(awaddr),.awlen(awlen),.awvalid(awvalid),.awready(awready),.wdata(wdata),.wstrb(wstrb),.wready(wready),.wlast(wlast),
        .done(done),.failed(failed),.fault(fault),.completed_base(completed_base),.completed_id(completed_id),.completed_crc(completed_crc),
        .hits(hits),.misses(misses),.completed_queries(queries));
    // Simultaneous HDMI-like traffic must not steal remapper cache responses.
    integer display_seq=0,display_pixel=0;reg display_active=0;
    wire display_valid=display_seq<40 && !display_active;
    wire display_ready,display_rvalid;wire [255:0] display_data;wire display_last;
    wire arb_failed,arb_busy;wire [7:0] arb_fault;wire [31:0] b0,b1;
    ddr_read_arbiter #(.TIMEOUT_BITS(12)) arb(.clk(clk),.rst_n(rst_n),.display_urgent(display_seq%7==0),
        .c0_araddr(28'd8192),.c1_araddr(a1),.c0_arlen(4'd15),.c1_arlen(l1),
        .c0_arvalid(display_valid),.c1_arvalid(av1),.c0_arready(display_ready),.c1_arready(ar1),
        .c0_rdata(display_data),.c1_rdata(coredata),.c0_rvalid(display_rvalid),.c1_rvalid(corerv),
        .c0_rlast(display_last),.c1_rlast(corerl),.c0_rid(),.c1_rid(corerid),
        .araddr(araddr),.arlen(arlen),.arvalid(arvalid),.arready(arready),.rdata(rdata),.rvalid(rvalid),.rlast(rlast),.rid(rid),
        .failed(arb_failed),.fault(arb_fault),.busy(arb_busy),.bursts0(b0),.bursts1(b1));
    reg [255:0] memory[0:2047],source[0:95],golden[0:95];reg [31:0] crcs[0:2];
    integer ticks=0,rleft=0,rindex=0,wleft=0,windex=0,phase=0,checked=0,mode=0;
    reg readheld=0,writeheld=0,dataheld=0;reg [27:0] savedar,savedaw;reg [255:0] saveddata;
    always @(negedge clk) begin
        ticks=ticks+1;
        arready=rst_n && rleft==0 && ticks%7>=3;
        awready=rst_n && wleft==0 && ticks%9>=4;
        rvalid=rst_n && rleft!=0 && ticks%5!=0;
        rlast=rleft==1;rid=0;
        if(mode==1 && rindex<256) rid=1;
        if(rvalid) rdata=memory[rindex];
        wready=rst_n && wleft!=0 && ticks%6!=0;
        wlast=wleft==1;
    end
    always @(posedge clk) begin
        if(!rst_n) begin
            rleft<=0;wleft<=0;readheld<=0;writeheld<=0;dataheld<=0;
            display_seq<=0;display_active<=0;display_pixel<=0;
        end else begin
            if(readheld && (!arvalid || araddr!==savedar)) $fatal(1,"Read command changed under contention");
            readheld<=arvalid && !arready;savedar<=araddr;
            if(writeheld && (!awvalid || awaddr!==savedaw)) $fatal(1,"Write command changed under contention");
            writeheld<=awvalid && !awready;savedaw<=awaddr;
            if(dataheld && wdata!==saveddata) $fatal(1,"Frame engine changed a stalled output beat");
            dataheld<=wleft!=0 && !wready;saveddata<=wdata;
            if(display_ready) begin display_active<=1;display_pixel<=0;end
            if(display_rvalid) begin
                if(display_data!==memory[1024+display_pixel]) $fatal(1,"Remap response leaked to display");
                display_pixel<=display_pixel+1;
                if(display_last) begin display_active<=0;display_seq<=display_seq+1;end
            end
            if(arvalid && arready) begin
                if(arlen!=15 || araddr[6:0]!=0 || rleft!=0) $fatal(1,"Bad shared read request");
                rleft<=16;rindex<=araddr>>3;
            end
            if(rvalid) begin rleft<=rleft-1;rindex<=rindex+1;end
            if(awvalid && awready) begin
                if(awlen!=15 || awaddr[6:0]!=0 || wleft!=0 || awaddr<output_base || awaddr>=output_base+256) $fatal(1,"Output write outside reserved bank");
                wleft<=16;windex<=awaddr>>3;
            end
            if(wready) begin
                if(wstrb!==32'hffffffff || wdata!==golden[phase*32+windex-(output_base>>3)]) $fatal(1,"Whole-frame integer reference mismatch phase=%0d beat=%0d",phase,windex-(output_base>>3));
                memory[windex]<=wdata;windex<=windex+1;wleft<=wleft-1;checked<=checked+1;
            end
            if(mode==0 && (failed || arb_failed)) $fatal(1,"Unexpected frame engine fault %h/%h",fault,arb_fault);
        end
    end
    task reset;
        begin @(negedge clk);rst_n=0;frame_valid=0;repeat(8) @(negedge clk);rst_n=1;end
    endtask
    task begin_frame;
        begin
            wait(frame_ready);@(negedge clk);frame_valid=1;
            do @(posedge clk);while(!frame_ready);
            @(negedge clk);frame_valid=0;
        end
    endtask
    integer i;
    initial begin
        $readmemh("source.mem",source);$readmemh("result.mem",golden);$readmemh("crcs.mem",crcs);
        for(i=0;i<2048;i=i+1) memory[i]={8{32'h98765400 | (i&255)}};
        reset;
        for(phase=0;phase<3;phase=phase+1) begin
            source_base=phase==1 ? 1024:0;output_base=2048+phase*1024;frame_id=phase+1;
            src_cx=phase==0 ? 3968:4096;k1=phase==0 ? 0:-524288;
            for(i=0;i<32;i=i+1) memory[(source_base>>3)+i]=source[phase*32+i];
            begin_frame;
            // Inputs may change after the handshake: the accepted frame's
            // parameters and source/output identity must already be locked.
            @(negedge clk);src_cx=0;k1=0;
            wait(done);
            if(completed_base!=output_base || completed_id!=phase+1 || completed_crc!==crcs[phase]) $fatal(1,"Wrong frame publication metadata");
            for(i=0;i<32;i=i+1) if(memory[(output_base>>3)+i]!==golden[phase*32+i]) $fatal(1,"Committed frame contains partial/old data");
            @(negedge clk);
        end
        wait(display_seq==40);if(checked!=96) $fatal(1,"Whole-frame output accounting failure");
        mode=2;reset;source_base=2048;output_base=2048;begin_frame;wait(failed);
        if(fault!=8'h40 || done || av1 || awvalid) $fatal(1,"Aliased source/output bank was accepted");
        reset;source_base=4;output_base=2048;begin_frame;wait(failed);
        if(fault!=8'h40 || done || av1 || awvalid) $fatal(1,"Unaligned bank was accepted");
        mode=1;phase=0;reset;source_base=0;output_base=2048;src_cx=3968;k1=0;frame_id=99;begin_frame;wait(failed);
        if(done || completed_id==99) $fatal(1,"Faulted source burst published a corrected frame");
        mode=0;reset;checked=0;
        for(i=0;i<32;i=i+1) memory[i]=source[i];
        begin_frame;wait(dut.index>180);reset;begin_frame;wait(done);
        if(completed_crc!==crcs[0] || completed_id!=99) $fatal(1,"Interrupted whole frame did not recover");
        $display("PASS complete remap frame engine: identity/nonlinear/same-bank frames, 1536 independent integer-model pixels, locked parameters, shared display reads, CRC32 publication, bank overlap/alignment rejection, DDR stalls, malformed source response and mid-frame reset recovery.");$finish;
    end
    initial begin #20000000;$fatal(1,"Whole-frame remap test timed out");end
endmodule
