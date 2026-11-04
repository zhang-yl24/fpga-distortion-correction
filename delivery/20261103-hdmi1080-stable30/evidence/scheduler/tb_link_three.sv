`timescale 1ns/1ps
// Small integration test: actual input/CDC/DMA + unchanged shared write arbiter.
// The core side is an explicit ownership/result-writer PROXY, not a mapper.
module tb_hdmi1080_input_write_link;
    localparam WIDTH=32,HEIGHT=16,N=WIDTH*HEIGHT,FB=N/16,STRIDE=1048576,RESULT_BURSTS=128;
    reg pix_clk=0,sys_clk=0;always #7 pix_clk=~pix_clk;always #4 sys_clk=~sys_clk;
    reg rst_n=0,enable=1,vs=0,de=0;reg [23:0] rgb=0;
    reg [2:0] processing_mask=0;
    wire source_valid;wire [1:0] source_bank;reg source_ready=0,released=0;reg [1:0] released_bank=0;
    wire [31:0] source_id,source_crc,source_pixels;
    wire [2:0] reserved;
    wire [2:0] core_writable=~(processing_mask | (source_valid ? (3'b001<<source_bank):3'b000));
    reg result_writing=0;integer result_bursts_done=0,result_beat=0;
    wire [27:0] core_awaddr=2*STRIDE+(result_bursts_done%2)*128;
    wire core_awvalid=rst_n && !result_writing && result_bursts_done<RESULT_BURSTS;
    wire core_awready,core_wready,core_wlast;
    wire [255:0] core_wdata;
    wire [27:0] awaddr;wire [3:0] awlen;wire awvalid;reg awready=0,wready=0,wlast=0;
    wire [255:0] wdata;wire [31:0] wstrb;
    wire failed,busy;wire [7:0] fault,last_drop;
    wire [31:0] cb,rb,accepted,dropped,overflow,no_free;
    hdmi1080_input_write_link #(.WIDTH(WIDTH),.HEIGHT(HEIGHT),.FIFO_ADDR_BITS(6)) dut(
        .pix_clk(pix_clk),.sys_clk(sys_clk),.rst_n(rst_n),.enable(enable),
        .pix_vsync_active(vs),.pix_de(de),.pix_rgb(rgb),
        .core_source_writable(core_writable),.core_source_released(released),.core_released_bank(released_bank),
        .core_source_valid(source_valid),.core_source_ready(source_ready),.core_source_bank(source_bank),
        .core_source_id(source_id),.source_crc(source_crc),.source_pixels(source_pixels),.capture_reserved(reserved),
        .core_failed(1'b0),.core_fault(8'b0),.core_awaddr(core_awaddr),.core_awlen(4'd15),
        .core_awvalid(core_awvalid),.core_awready(core_awready),.core_wdata(core_wdata),.core_wstrb(32'hffffffff),
        .core_wready(core_wready),.core_wlast(core_wlast),.awaddr(awaddr),.awlen(awlen),.awvalid(awvalid),.awready(awready),
        .wdata(wdata),.wstrb(wstrb),.wready(wready),.wlast(wlast),.failed(failed),.fault(fault),.write_busy(busy),
        .capture_bursts(cb),.result_bursts(rb),.accepted_frames(accepted),.dropped_frames(dropped),
        .overflow_frames(overflow),.no_free_frames(no_free),.last_drop_fault(last_drop));

    function automatic [23:0] source_rgb(input integer pos,input integer version);
        source_rgb=(pos*24'h010307+version*24'h291b53)^(pos<<9);
    endfunction
    function automatic [15:0] source565(input integer pos,input integer version);
        reg [23:0] c;integer rr,gg,bb;
        begin c=source_rgb(pos,version);rr=(c>>16)&255;gg=(c>>8)&255;bb=c&255;
            source565=((rr/8)*2048)+((gg/4)*32)+(bb/8);end
    endfunction
    function automatic [255:0] source_word(input integer off,input integer version);
        for(integer lane=0;lane<16;lane=lane+1)source_word[lane*16+:16]=source565(off*16+lane,version);
    endfunction
    function automatic [255:0] result_word(input integer off);
        for(integer lane=0;lane<16;lane=lane+1)result_word[lane*16+:16]=16'h9001^((off*16+lane)*37);
    endfunction
    assign core_wdata=result_word((core_awaddr-2*STRIDE)/8+result_beat);
    function automatic [31:0] expected_crc(input integer version);
        reg [31:0] c;reg [15:0] p;reg [7:0] b;
        begin c=32'hffffffff;
            for(integer j=0;j<N;j=j+1)begin
                p=source565(j,version);
                for(integer by=0;by<2;by=by+1)begin
                    b=p>>(8*by);c=c^b;
                    for(integer bitn=0;bitn<8;bitn=bitn+1)c=c[0] ? (c>>1)^32'hedb88320:c>>1;
                end
            end
            expected_crc=~c;
        end
    endfunction

    integer ticks=0,left=0,beat_address=0,bank=0,off=0,sbank=0;
    integer source_writes[0:2];integer commits=0;
    integer cov_aw_stall=0,cov_w_stall=0,cov_contention=0,cov_commit_stall=0,cov_both_owned=0;
    integer cov_same_input=0,cov_same_result=0,cov_result_writes=0;
    reg held_aw=0,held_w=0,held_source=0;
    reg [31:0] saved_aw;reg [255:0] saved_w;reg [129:0] saved_source;
    always @(negedge sys_clk)begin
        awready=rst_n && left==0 && ticks%7>=2;
        // Deliberately exercise the legal native AW + first W same cycle.
        wready=rst_n && ((awvalid&&awready) || (left>0&&ticks%5!=0));
        wlast=left==1;
    end
    always @(posedge sys_clk)begin
        if(!rst_n)begin
            result_writing<=0;result_bursts_done<=0;result_beat<=0;processing_mask<=0;
            ticks<=0;left=0;source_writes[0]=0;source_writes[1]=0;source_writes[2]=0;commits=0;
            held_aw<=0;held_w<=0;held_source<=0;
        end else begin
            ticks<=ticks+1;
            if(ticks>200000)$fatal(1,"link cycle budget exceeded");
            if(failed)$fatal(1,"link fault %h",fault);
            if(held_aw && (!awvalid || {awaddr,awlen}!==saved_aw))$fatal(1,"shared AW changed while held");
            if(held_w && wdata!==saved_w)$fatal(1,"shared W changed while held");
            if(held_source && (!source_valid || {source_bank,source_id,source_crc,source_pixels,32'b0}!==saved_source))
                $fatal(1,"core commit metadata changed while held");
            held_aw<=awvalid&&!awready;saved_aw<={awaddr,awlen};
            held_w<=left>0&&!wready;saved_w<=wdata;
            held_source<=source_valid&&!source_ready;saved_source<={source_bank,source_id,source_crc,source_pixels,32'b0};
            if(awvalid&&!awready)cov_aw_stall=cov_aw_stall+1;
            if(left>0&&!wready)cov_w_stall=cov_w_stall+1;
            if(dut.dma_awvalid&&core_awvalid)cov_contention=cov_contention+1;
            if(reserved==7)cov_both_owned=cov_both_owned+1;
            if(source_valid&&!source_ready)cov_commit_stall=cov_commit_stall+1;
            if(core_awvalid&&core_awready)result_writing<=1;
            if(core_wready)begin
                if(core_wlast)begin result_writing<=0;result_beat<=0;result_bursts_done<=result_bursts_done+1;end
                else result_beat<=result_beat+1;
            end
            if(awvalid&&awready)begin
                if(left!=0 || awlen!=15 || awaddr%128!=0)$fatal(1,"shared burst overlap/alignment/length");
                bank=awaddr/STRIDE;off=awaddr%STRIDE;sbank=bank==4?2:bank;
                if(bank<0 || bank>4 || bank==3 || off+128>N/2)$fatal(1,"bank/frame boundary exceeded");
                if((bank<2 || bank==4) && (processing_mask[sbank] || !reserved[sbank]))$fatal(1,"capture wrote core-owned or unreserved bank");
                if((bank<2 || bank==4) && off!=source_writes[sbank]*8)$fatal(1,"capture AW skipped/overwrote frame beats");
                left=16;beat_address=awaddr/8;
                if(wready)begin
                    if((bank<2 || bank==4))cov_same_input=cov_same_input+1;else cov_same_result=cov_same_result+1;
                end
            end
            if(wready)begin
                if(left==0 || wlast!=(left==1) || wstrb!==32'hffffffff)$fatal(1,"W without owner/last/strb");
                bank=beat_address/(STRIDE/8);off=beat_address%(STRIDE/8);sbank=bank==4?2:bank;
                if((bank<2 || bank==4))begin
                    if(wdata!==source_word(off,sbank+1))$fatal(1,"capture exact pixel/ordering mismatch bank%0d beat%0d",bank,off);
                    source_writes[sbank]=source_writes[sbank]+1;
                end else begin
                    if(wdata!==result_word(off))$fatal(1,"result-owner write mixed with capture data");
                    cov_result_writes=cov_result_writes+1;
                end
                left=left-1;beat_address=beat_address+1;
            end
            if(source_valid)begin
                if(source_pixels!=N || source_writes[source_bank]!=FB || source_crc!==expected_crc(source_bank+1) || !reserved[source_bank])
                    $fatal(1,"commit before full capture count/CRC/drain/reservation");
            end
            if(source_valid&&source_ready)begin
                if(source_bank!=commits || source_id!=commits+1)$fatal(1,"source bank/id order differs");
                processing_mask[source_bank]<=1;commits=commits+1;
            end
            if(released)processing_mask[released_bank]<=0;
        end
    end
    task automatic boundary;
        begin @(negedge pix_clk);de=0;vs=1;repeat(4)@(negedge pix_clk);vs=0;repeat(24)@(negedge pix_clk);end
    endtask
    task automatic frame(input integer version);
        begin
            boundary();
            for(integer y=0;y<HEIGHT;y=y+1)begin
                for(integer x=0;x<WIDTH;x=x+1)begin de=1;rgb=source_rgb(y*WIDTH+x,version);@(negedge pix_clk);end
                de=0;repeat(5)@(negedge pix_clk);
            end
            boundary();
        end
    endtask
    task automatic accept_source(input integer expected_bank);
        begin
            wait(source_valid);repeat(20)@(negedge sys_clk);
            if(source_bank!=expected_bank)$fatal(1,"offered wrong source bank");
            source_ready=1;@(negedge sys_clk);source_ready=0;
        end
    endtask
    initial begin
        repeat(12)@(negedge sys_clk);rst_n=1;repeat(30)@(negedge pix_clk);
        frame(1);accept_source(0);
        frame(2);accept_source(1);frame(3);accept_source(2);
        enable=0;
        wait(result_bursts_done==RESULT_BURSTS);wait(!busy&&left==0);repeat(12)@(negedge sys_clk);
        if(reserved!=7 || processing_mask!=7 || accepted!=3 || dropped!=0 || overflow!=0 || cb!=6 || rb!=RESULT_BURSTS)
            $fatal(1,"final two-owner accounting differs");
        released_bank=0;released=1;@(negedge sys_clk);released=0;repeat(4)@(negedge sys_clk);
        if(reserved[0] || !reserved[1])$fatal(1,"release freed the wrong source owner");
        released_bank=1;released=1;@(negedge sys_clk);released=0;repeat(4)@(negedge sys_clk);
        released_bank=2;released=1;@(negedge sys_clk);released=0;repeat(4)@(negedge sys_clk);
        if(reserved!=0 || processing_mask!=0 || source_valid || busy || left!=0)$fatal(1,"final ownership/write drain incomplete");
        if(cov_aw_stall==0 || cov_w_stall==0 || cov_contention==0 || cov_commit_stall==0 || cov_both_owned==0 ||
           cov_same_input==0 || cov_same_result==0 || cov_result_writes==0)$fatal(1,"link mandatory pressure vacuous");
        $display("INPUT_LINK_COVERAGE AWstall=%0d Wstall=%0d contention=%0d commitstall=%0d both_owned=%0d same_input=%0d same_result=%0d result_beats=%0d ticks=%0d",
            cov_aw_stall,cov_w_stall,cov_contention,cov_commit_stall,cov_both_owned,cov_same_input,cov_same_result,cov_result_writes,ticks);
        $display("PASS hdmi1080 input write link: exact three32x16 source frames/CRC,128 result bursts, real shared arbiter, same-cycle AW-W, nonzero pressure, held commit and release drain; core is proxy");
        $finish;
    end
    initial begin #2000000;$fatal(1,"bounded link simulation timeout");end
endmodule
