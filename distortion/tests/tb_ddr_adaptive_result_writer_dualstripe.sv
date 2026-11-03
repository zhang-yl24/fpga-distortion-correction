`timescale 1ns/1ps
module tb_ddr_adaptive_result_writer_dualstripe;
    `include "dualstripe_writer_config.vh"
    localparam PIXELS=WIDTH*HEIGHT,STRIPE=WIDTH*8,BEATS=PIXELS/16,BASE=1024;
    reg clk=0,rst_n=0,frame_valid=0,frame_tiled=0,in_valid=0;
    reg [23:0] in_rgb=0,in_tag=0;
    reg [27:0] frame_base=BASE;
    reg [31:0] frame_id=0;
    wire frame_ready,in_ready,awvalid,done,failed;
    wire [27:0] awaddr;wire [3:0] awlen;
    wire [255:0] wdata;wire [31:0] wstrb;
    reg awready=0,wready=0,wlast=0;
    wire [7:0] fault;wire [31:0] accepted_pixels,written_beats,last_checksum,completed_id;
    ddr_adaptive_result_writer_dualstripe #(.WIDTH(WIDTH),.HEIGHT(HEIGHT),.TIMEOUT_BITS(10)) dut(
        .clk(clk),.rst_n(rst_n),.frame_valid(frame_valid),.frame_tiled(frame_tiled),.frame_ready(frame_ready),
        .frame_base(frame_base),.frame_id(frame_id),.in_valid(in_valid),.in_ready(in_ready),.in_rgb(in_rgb),.in_tag(in_tag),
        .awaddr(awaddr),.awlen(awlen),.awvalid(awvalid),.awready(awready),.wdata(wdata),.wstrb(wstrb),
        .wready(wready),.wlast(wlast),.done(done),.failed(failed),.fault(fault),.accepted_pixels(accepted_pixels),
        .written_beats(written_beats),.last_checksum(last_checksum),.completed_id(completed_id));
    always #4 clk=~clk;
    // 0 arbitrary stalls; 1 held AW; 2 held W; 3 early LAST;
    // 4 missing LAST; 5 manual W; 6 no-stall transport/input.
    integer mode=0,salt=0,case_id=0,cycle=0,checked=0,bus_beat=0;
    integer j,out_index=0,last_write_cycle=-1,same_aw_w=0,overlap_cycles=0;
    integer aw_stalls=0,w_stalls=0,pack_run=0,max_pack_run=0,fd;
    reg bus_active=0,held_aw=0,held_w=0,allow_w=0;
    reg [27:0] saved_aw;
    reg [255:0] saved_w;
    function [23:0] rgb;
        input integer tag;
        begin rgb={8'((tag*17+3+salt*37)%256),8'((tag*7+11+salt*19)%256),8'((tag*29+5+salt*23)%256)};end
    endfunction
    function [15:0] pixel;
        input integer tag;reg [23:0] value;
        begin value=rgb(tag);pixel={value[23:19],value[15:10],value[7:3]};end
    endfunction
    function [31:0] oracle_crc;
        integer n,b;reg[31:0] c;reg[15:0] p;
        begin
            c=32'hffffffff;
            for(n=0;n<PIXELS;n=n+1)begin
                p=pixel(n);
                for(b=0;b<16;b=b+1)c=(c>>1)^((c[0]^p[b])?32'hedb88320:0);
            end
            oracle_crc=~c;
        end
    endfunction
    function integer tag_for;
        input integer ordinal;input integer tiled;
        integer stripe_offset,sy,tx,yy,xx;
        begin
            if(!tiled)tag_for=ordinal;
            else begin stripe_offset=ordinal%STRIPE;sy=(ordinal/STRIPE)*8;tx=(stripe_offset/64)*8;
                yy=(stripe_offset/8)%8;xx=stripe_offset%8;tag_for=(sy+yy)*WIDTH+tx+xx;end
        end
    endfunction
    always @(negedge clk)begin
        awready=rst_n && !bus_active && mode!=1 && (mode==6 || cycle%7!=0 && cycle%13!=0);
        wready=rst_n && (bus_active || awvalid && awready) && mode!=2 &&
            (mode==5 ? allow_w : mode==6 || cycle%3!=0 && cycle%11!=0);
        wlast=wready && (mode==3 ? bus_beat==3 : mode==4 ? 1'b0 : bus_beat==15);
    end
    always @(posedge clk)begin
        cycle=cycle+1;
        if(!rst_n)begin
            bus_active=0;bus_beat=0;checked=0;out_index=0;last_write_cycle=-1;
            held_aw=0;held_w=0;same_aw_w=0;overlap_cycles=0;aw_stalls=0;w_stalls=0;pack_run=0;max_pack_run=0;
        end else begin
            if(frame_valid && frame_ready)begin
                checked=0;out_index=0;last_write_cycle=-1;same_aw_w=0;overlap_cycles=0;
                aw_stalls=0;w_stalls=0;pack_run=0;max_pack_run=0;
            end
            if(held_aw && (!awvalid || awaddr!==saved_aw))$fatal(1,"AW moved/retracted across stall/fault");
            if(held_w && wdata!==saved_w)$fatal(1,"immutable burst changed under W stall");
            held_aw=awvalid && !awready;saved_aw=awaddr;
            held_w=bus_active && !wready;saved_w=wdata;
            if(awvalid && !awready)aw_stalls=aw_stalls+1;
            if(bus_active && !wready)w_stalls=w_stalls+1;
            if(dut.collect_pixel && (dut.read_enable || dut.pack_pixel || bus_active || awvalid))overlap_cycles=overlap_cycles+1;
            if(dut.pack_pixel)begin pack_run=pack_run+1;if(pack_run>max_pack_run)max_pack_run=pack_run;end
            else pack_run=0;
            if(dut.collect_pixel && dut.stripe_full[dut.collect_bank])$fatal(1,"ready/draining stripe overwritten");
            if(dut.read_enable && !dut.stripe_full[dut.drain_bank])$fatal(1,"unvalidated stripe read");
            if(awvalid && awready)begin
                if(bus_active || awlen!=15 || awaddr!=BASE+checked*8)$fatal(1,"AW address/count/ownership mismatch");
                if(accepted_pixels<256)$fatal(1,"AW before complete 256 pixels");
                bus_active=1;bus_beat=0;out_index=checked*16;
                if(wready)same_aw_w=same_aw_w+1;
            end
            if(bus_active && wready)begin
                if(wstrb!==32'hffffffff)$fatal(1,"partial write strobe");
                for(j=0;j<16;j=j+1)
                    if(wdata[j*16+:16]!==pixel(out_index+j))$fatal(1,"raster oracle mismatch case=%0d pixel=%0d",case_id,out_index+j);
                $fdisplay(fd,"W %0d %0d %0d %064x",case_id,salt,checked,wdata);
                checked=checked+1;out_index=out_index+16;last_write_cycle=cycle;
                if(bus_beat==15 || wlast)bus_active=0;
                bus_beat=bus_beat+1;
            end
        end
    end
    task reset_system;
        begin
            @(negedge clk);#1;rst_n=0;frame_valid=0;in_valid=0;allow_w=0;
            #1;if(done || failed || accepted_pixels || written_beats || awvalid)$fatal(1,"asynchronous reset did not clear control");
            repeat(3)@(negedge clk);rst_n=1;repeat(2)@(negedge clk);
        end
    endtask
    task begin_frame;
        input integer tiled;
        begin
            wait(frame_ready);@(negedge clk);frame_tiled=tiled;frame_valid=1;frame_id=case_id;
            @(negedge clk);frame_valid=0;frame_tiled=!tiled;
            $fdisplay(fd,"BEGIN %0d %0d %0d",case_id,salt,tiled);
        end
    endtask
    task send_tag;
        input integer tag;
        begin
            @(negedge clk);in_valid=1;in_tag=tag;in_rgb=rgb(tag);
            do @(posedge clk);while(!in_ready);
        end
    endtask
    task send_count;
        input integer count;input integer tiled;
        integer n;
        begin
            for(n=0;n<count;n=n+1)begin
                if(mode!=6 && n%19==5)begin @(negedge clk);in_valid=0;end
                send_tag(tag_for(n,tiled));
            end
            @(negedge clk);in_valid=0;
        end
    endtask
    task check_frame;
        reg[31:0] crc_expected;
        begin
            wait(done);#1;crc_expected=oracle_crc();
            if(failed || checked!=BEATS || accepted_pixels!=PIXELS || written_beats!=BEATS ||
                completed_id!=case_id || last_checksum!==crc_expected || cycle-last_write_cycle!=32)
                $fatal(1,"completed frame/count/CRC/drain mismatch c=%0d checks=%0d crc=%08x/%08x age=%0d",case_id,checked,last_checksum,crc_expected,cycle-last_write_cycle);
            $fdisplay(fd,"DONE %0d %08x %0d %0d %0d %0d %0d",case_id,last_checksum,checked,same_aw_w,overlap_cycles,aw_stalls,w_stalls);
            $display("FRAME case=%0d width=%0d pixels=%0d overlap=%0d sameAW=%0d maxPackRun=%0d",case_id,WIDTH,PIXELS,overlap_cycles,same_aw_w,max_pack_run);
            @(negedge clk);case_id=case_id+1;
        end
    endtask
    task require_quarantine;
        input[7:0] expected_fault;
        integer prior_count;
        begin
            wait(failed);#1;
            if(fault!=expected_fault || done || frame_ready || in_ready)$fatal(1,"fault quarantine mismatch");
            repeat(40)@(negedge clk);
            if(done || !failed || fault!=expected_fault || awvalid)$fatal(1,"fault published or did not quarantine");
            prior_count=checked;repeat(5)@(negedge clk);if(checked!=prior_count)$fatal(1,"write after quarantine");
            $fdisplay(fd,"FAULT %0d %02x %0d",case_id,fault,checked);case_id=case_id+1;
        end
    endtask
    integer n,before_count;
    reg[27:0] frozen_aw;
    reg[255:0] frozen_data;
    initial begin
        fd=$fopen("writes.txt","w");
        // Full consecutive frames with new values, both input modes and stalls.
        mode=0;salt=1;reset_system();begin_frame(1);send_count(PIXELS,1);check_frame();
        salt=2;begin_frame(0);send_count(PIXELS,0);check_frame();
        mode=6;salt=3;begin_frame(1);send_count(PIXELS,1);check_frame();
        if(max_pack_run<((STRIPE<256)?STRIPE:256))$fatal(1,"RAM issue/PACK not one pixel per cycle");
        if(STRIPE>=256 && !overlap_cycles)$fatal(1,"two-stripe collection/drain overlap absent");
        if(DO_FAULTS)begin
            // Hold the first AW long enough to fill both banks. The third
            // stripe cannot overwrite either full bank, even with valid held.
            mode=1;salt=4;reset_system();begin_frame(1);
            fork
                begin send_count(PIXELS,1);end
                begin
                    wait(awvalid);repeat(2*STRIPE+100)@(negedge clk);
                    if(accepted_pixels!=2*STRIPE || in_ready || dut.stripe_full!=2'b11)$fatal(1,"full-bank backpressure/ownership failed");
                    mode=0;
                end
            join
            check_frame();
            // Duplicate and omitted tags never create a completed stripe.
            mode=0;reset_system();begin_frame(1);send_tag(0);send_tag(0);@(negedge clk);in_valid=0;require_quarantine(8'h32);
            reset_system();begin_frame(1);send_tag(1);@(negedge clk);in_valid=0;require_quarantine(8'h32);
            // Fault while AW is stalled: preserve AW and the packed payload,
            // accept its first W with AW, finish this burst, never publish.
            mode=1;reset_system();begin_frame(1);send_count(STRIPE,1);wait(awvalid);
            frozen_aw=awaddr;frozen_data=wdata;send_tag(STRIPE+1);@(negedge clk);in_valid=0;
            repeat(20)begin @(negedge clk);if(!awvalid || awaddr!==frozen_aw || wdata!==frozen_data)$fatal(1,"tag-fault retracted held AW");end
            mode=0;wait(checked==16);require_quarantine(8'h32);
            // Tag fault, AW acceptance and the first requested W all coincide.
            mode=1;reset_system();begin_frame(1);send_count(STRIPE,1);wait(awvalid);
            mode=6;send_tag(STRIPE+1);@(negedge clk);in_valid=0;
            if(!failed || checked<1 || !same_aw_w)$fatal(1,"first-W/AW/tag-fault overlap not exercised");
            wait(checked==16);require_quarantine(8'h32);
            // Fault on the last requested W of an outstanding burst.
            mode=5;reset_system();begin_frame(1);send_count(STRIPE,1);wait(bus_active);
            @(posedge clk);#1;allow_w=1;wait(bus_beat==15);#1;allow_w=0;
            repeat(2)@(posedge clk);#1;allow_w=1;
            send_tag(STRIPE+1);@(negedge clk);in_valid=0;
            wait(failed);if(checked!=16)$fatal(1,"last-W/tag-fault overlap not exercised");require_quarantine(8'h32);
            // Malformed early/final LAST and a bounded W timeout.
            mode=3;reset_system();begin_frame(0);send_count(256,0);require_quarantine(8'h02);
            mode=4;reset_system();begin_frame(0);send_count(256,0);require_quarantine(8'h02);
            mode=2;reset_system();begin_frame(0);send_count(256,0);require_quarantine(8'h01);
            // Async reset while collecting, with a pending synchronous read,
            // and with AW/W outstanding; old banks/payload must not leak.
            mode=0;reset_system();begin_frame(1);send_count(7,1);reset_system();
            begin_frame(1);send_count(STRIPE,1);wait(dut.read_valid);reset_system();
            mode=1;begin_frame(0);send_count(256,0);wait(awvalid);reset_system();
            mode=2;begin_frame(0);send_count(256,0);wait(bus_active);reset_system();
            mode=0;salt=5;begin_frame(1);send_count(PIXELS,1);check_frame();
            // Illegal frame layout and stale input after a valid last pixel.
            frame_base=BASE+1;reset_system();begin_frame(0);require_quarantine(8'h08);frame_base=BASE;
            mode=0;salt=6;reset_system();begin_frame(0);send_count(PIXELS,0);
            if(in_ready)$fatal(1,"extra pixel accepted after last frame input");check_frame();
        end
        $display("PASS dualstripe writer width=%0d height=%0d faults=%0d",WIDTH,HEIGHT,DO_FAULTS);
        $fclose(fd);$finish;
    end
    initial begin #50000000;$fatal(1,"dualstripe writer test timed out");end
endmodule
