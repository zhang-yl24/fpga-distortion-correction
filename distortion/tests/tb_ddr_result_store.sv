`timescale 1ns/1ps
module tb_ddr_result_store;
    reg clk=0;always #4 clk=~clk;
    reg rst_n=0,frame_valid=0,in_valid=0;wire frame_ready,in_ready;
    reg [27:0] frame_base=128;reg [31:0] frame_id=1;reg [23:0] in_rgb,in_tag;
    wire [27:0] a1,awaddr;wire [3:0] l1,awlen;wire av1,ar1,awvalid;
    wire [255:0] d1,wdata;wire [31:0] s1,wstrb;wire wr1,wl1;
    wire done,failed;wire [7:0] fault;wire [31:0] pixels,beats,crc,id;
    reg [27:0] a0=4096;reg av0=0;wire ar0,wr0,wl0;
    reg [3:0] c0beat=0;reg c0active=0;reg [31:0] c0burst=0;
    wire [255:0] d0={8{32'hAC000000 | (c0burst<<8) | c0beat}};
    reg awready=0,wready=0,wlast=0;wire afail,busy;wire [7:0] afault;
    wire [31:0] b0,b1;
    ddr_result_writer #(.WIDTH(32),.HEIGHT(16),.TIMEOUT_BITS(10)) writer(
        .clk(clk),.rst_n(rst_n),.frame_valid(frame_valid),.frame_ready(frame_ready),.frame_base(frame_base),.frame_id(frame_id),
        .in_valid(in_valid),.in_ready(in_ready),.in_rgb(in_rgb),.in_tag(in_tag),
        .awaddr(a1),.awlen(l1),.awvalid(av1),.awready(ar1),.wdata(d1),.wstrb(s1),.wready(wr1),.wlast(wl1),
        .done(done),.failed(failed),.fault(fault),.accepted_pixels(pixels),.written_beats(beats),.last_checksum(crc),.completed_id(id));
    ddr_write_arbiter #(.TIMEOUT_BITS(10)) arb(
        .clk(clk),.rst_n(rst_n),.c0_awaddr(a0),.c0_awlen(4'd15),.c0_awvalid(av0),.c0_awready(ar0),
        .c1_awaddr(a1),.c1_awlen(l1),.c1_awvalid(av1),.c1_awready(ar1),
        .c0_wdata(d0),.c0_wstrb(32'hffffffff),.c1_wdata(d1),.c1_wstrb(s1),
        .c0_wready(wr0),.c1_wready(wr1),.c0_wlast(wl0),.c1_wlast(wl1),
        .awaddr(awaddr),.awlen(awlen),.awvalid(awvalid),.awready(awready),.wdata(wdata),.wstrb(wstrb),.wready(wready),.wlast(wlast),
        .failed(afail),.fault(afault),.busy(busy),.bursts0(b0),.bursts1(b1));
    reg [23:0] golden_pixels[0:1535];reg [255:0] golden_beats[0:95];reg [31:0] golden_crcs[0:2];
    integer ticks=0,left=0,burst_index=0,which=0,phase=0,checked=0,mode=0;
    reg held=0;reg [27:0] heldaddr;reg dataheld=0;reg [255:0] helddata;
    always @(negedge clk) begin
        ticks=ticks+1;
        awready=rst_n && left==0 && ticks%7>=3;
        wready=rst_n && left!=0 && ticks%5!=0 && mode!=3;
        wlast=left==1 || (mode==1 && left==12);
    end
    always @(posedge clk) begin
        if(!rst_n) begin
            left<=0;held<=0;dataheld<=0;c0active<=0;c0beat<=0;c0burst<=0;av0<=0;a0<=4096;
        end else begin
            if(held && (!awvalid || awaddr!==heldaddr)) $fatal(1,"AW changed while stalled");
            held<=awvalid && !awready;heldaddr<=awaddr;
            if(dataheld && wdata!==helddata) $fatal(1,"W changed under backpressure");
            dataheld<=left!=0 && !wready && !afail;helddata<=wdata;
            if(mode==0 && c0burst<8 && !c0active && !av0) av0<=1;
            if(ar0) begin av0<=0;c0active<=1;c0beat<=0;end
            if(wr0) begin
                c0beat<=c0beat+1;
                if(wl0) begin c0active<=0;c0burst<=c0burst+1;a0<=a0+128;end
            end
            if(ar0 && ar1 || wr0 && wr1) $fatal(1,"Write clients shared one beat");
            if(awvalid && awready) begin
                if(left!=0 || awlen!=15 || awaddr[6:0]!=0) $fatal(1,"Invalid AW");
                left<=16;
                if(awaddr>=4096) begin which<=0;burst_index<=c0burst;end
                else begin
                    which<=1;burst_index<=(awaddr-frame_base)>>3;
                    if(awaddr!=frame_base+beats*8) $fatal(1,"Result address/unit mismatch");
                end
            end
            if(wready) begin
                if(wstrb!==32'hffffffff) $fatal(1,"Incomplete byte mask");
                if(mode==0) begin
                    if(which==1 && wdata!==golden_beats[phase*32+burst_index+16-left]) $fatal(1,"Result order or RGB565 mismatch");
                    if(which==0 && wdata!=={8{32'hAC000000 | (burst_index<<8) | (16-left)}}) $fatal(1,"Capture burst mixed with result");
                    if(which==1) checked<=checked+1;
                end
                left<=left-1;
            end
        end
    end
    task reset;
        begin @(negedge clk);rst_n=0;in_valid=0;frame_valid=0;repeat(8) @(negedge clk);rst_n=1;end
    endtask
    task begin_frame;
        begin wait(frame_ready);@(negedge clk);frame_valid=1;@(negedge clk);frame_valid=0;end
    endtask
    task send_pixels(input integer count,input integer badtag);
        integer i;
        begin
            for(i=0;i<count;i=i+1) begin
                @(negedge clk);in_valid=1;in_rgb=golden_pixels[phase*512+i];in_tag=i+badtag;
                do @(posedge clk);while(!in_ready);
                @(negedge clk);in_valid=0;
                if(i%11==0) repeat(2) @(negedge clk);
            end
        end
    endtask
    initial begin
        $readmemh("pixels.mem",golden_pixels);$readmemh("beats.mem",golden_beats);$readmemh("crcs.mem",golden_crcs);
        reset;
        for(phase=0;phase<3;phase=phase+1) begin
            frame_base=128+phase*1024;frame_id=phase+1;begin_frame;send_pixels(512,0);wait(done);
            if(failed || afail || pixels!=512 || beats!=32 || crc!==golden_crcs[phase] || id!=phase+1) $fatal(1,"Publication metadata mismatch");
            @(negedge clk);
        end
        wait(b0==8);if(checked!=96 || b1!=6) $fatal(1,"Fair burst accounting failure");
        mode=2;phase=0;reset;begin_frame;send_pixels(1,1);wait(failed);
        if(fault!=8'h32 || done || awvalid) $fatal(1,"Bad pixel tag published a partial frame");
        mode=1;reset;begin_frame;send_pixels(256,0);wait(failed && afail);
        if(fault!=2 || afault!=2 || done) $fatal(1,"Bad WLAST accepted");
        mode=3;reset;begin_frame;send_pixels(256,0);wait(failed && afail);
        if(fault!=1 || afault!=1 || done) $fatal(1,"Missing write response not quarantined");
        mode=2;reset;begin_frame;send_pixels(200,0);reset;
        phase=0;begin_frame;send_pixels(512,0);wait(done);
        if(failed || afail || crc!==golden_crcs[0]) $fatal(1,"Mid-frame reset did not recover");
        $display("PASS result frame storage + write arbitration: three zlib-verified frames, 1536 RGB565 pixels, concurrent capture bursts, whole-burst ownership/fairness, stalls, tag order, WLAST, timeout and reset recovery.");$finish;
    end
    initial begin #20000000;$fatal(1,"Result-store test timed out");end
endmodule
