`timescale 1ns/1ps
module tb_ddr_live_video_wide;
    reg cam_clk=0,core_clk=0,pix_clk=0;
    always #11 cam_clk=~cam_clk;always #4 core_clk=~core_clk;always #7 pix_clk=~pix_clk;
    reg rst_n=0,ready=0,vsync=0,href=0;reg [7:0] data=0;
    wire [27:0] awaddr,araddr;wire [3:0] awlen,arlen;wire awvalid,arvalid;
    wire [255:0] wdata;wire [31:0] wstrb;
    reg awready=0,arready=0,wready=0,wlast=0,rvalid=0,rlast=0;
    reg [255:0] rdata=0;reg [3:0] rid=0;
    wire hs,vs,de;wire [7:0] r,g,b;
    wire display_valid,failed;wire [7:0] fault;
    wire [31:0] output_frames,underflows,pixel_mismatches,pixel_checksum;
    wire [31:0] captured_frames,ownership_errors,read_frames,read_checksum,latest_source_checksum;
    ddr_live_video #(.WIDTH(64),.HEIGHT(192),.BANK_STRIDE(8192),
        .HT(160),.VT(224),.HS(4),.VS(2),.X0(6),.Y0(4),.AW(128),.AH(208)) dut(.*);
    reg [255:0] memory[0:2047];
    integer wbase=0,rbase=0,wi=0,ri=0,cycle=0;
    reg writing=0,reading=0,stall_reads=0,corrupt_reads=0;
    always @(posedge core_clk) begin
        if(!rst_n) begin writing=0;reading=0;wi=0;ri=0;end
        else begin
            if(awvalid && awready) begin
                wbase=awaddr/8;wi=0;writing=1;
                if(awlen!=15 || awaddr%128 || awaddr>=14336) $fatal(1,"Write range/length");
            end
            if(wready) begin
                if(!writing || wstrb!==32'hFFFFFFFF) $fatal(1,"Invalid W stream");
                memory[wbase+wi]=wdata;
                if(wi==15) writing=0;
                wi=wi+1;
            end
            if(arvalid && arready) begin
                rbase=araddr/8;ri=0;reading=1;
                if(arlen!=15 || araddr%128 || araddr>=14336) $fatal(1,"Read range/length");
            end
            if(rvalid) begin if(ri==15) reading=0;ri=ri+1;end
            if(writing && reading && (wbase/1024)==(rbase/1024)) $fatal(1,"Read/write bank collision");
        end
    end
    always @(negedge core_clk) begin
        cycle=cycle+1;
        awready=rst_n && !writing && cycle%5!=0;
        arready=rst_n && !reading && cycle%7!=0;
        wready=rst_n && writing && cycle%3!=0;wlast=wready && wi==15;
        rvalid=rst_n && reading && !stall_reads && cycle%4!=0;rlast=rvalid && ri==15;
        rdata=reading ? memory[rbase+ri] : 0;
        if(corrupt_reads && ri==3) rdata[147]=!rdata[147];
    end
    function [15:0] value;
        input integer frame,pixel;
        begin value=16'h3297 ^ ((frame+1)*(pixel*37+977));end
    endfunction
    reg camera_running=1,malformed=0;
    integer camera_frame=0,row,col;
    reg [15:0] pixel;
    initial forever begin
        wait(rst_n && ready && camera_running);
        @(negedge cam_clk);vsync=1;href=0;
        repeat(6) @(negedge cam_clk);vsync=0;
        repeat(4) @(negedge cam_clk);
        for(row=0;row<192;row=row+1) begin
            for(col=0;col<64-(malformed && row==191);col=col+1) begin
                pixel=value(camera_frame,row*64+col);href=1;data=pixel[7:0];@(negedge cam_clk);
                data=pixel[15:8];@(negedge cam_clk);
            end
            href=0;repeat(4) @(negedge cam_clk);
        end
        camera_frame=camera_frame+1;
    end
    // Compare every native-resolution output pixel against the bank locked by
    // this HDMI frame, independently of the streaming checksum implementation.
    integer px,py,word_index,lane,pixels_seen=0;
    reg [15:0] expected_pixel;reg [7:0] expected_r,expected_g,expected_b;
    always @(posedge pix_clk) begin
        if(rst_n && dut.output_video.consume && !corrupt_reads) begin
            px=dut.output_video.x-38;py=dut.output_video.y-12;
            word_index=(dut.front_bank ? 1024:0)+(py*64+px)/16;lane=(py*64+px)%16;
            expected_pixel=memory[word_index][lane*16+:16];
            expected_r={expected_pixel[15:11],expected_pixel[15:13]};
            expected_g={expected_pixel[10:5],expected_pixel[10:9]};
            expected_b={expected_pixel[4:0],expected_pixel[4:2]};
            #1;
            if({r,g,b}!={expected_r,expected_g,expected_b} || !de) $fatal(1,"Output pixel mismatch");
            pixels_seen=pixels_seen+1;
        end
    end
    task reset_system;
        begin
            rst_n=0;ready=0;repeat(12) @(negedge core_clk);
            rst_n=1;repeat(12) @(negedge core_clk);ready=1;
        end
    endtask
    task wait_frames;
        input integer count;integer ticks;
        begin
            ticks=0;
            while(output_frames<count && !failed && underflows==0 && pixel_mismatches==0 && ticks<3000000) begin
                @(negedge core_clk);ticks=ticks+1;
            end
            if(output_frames<count) $fatal(1,"Video progress failed frames=%d cap=%d fault=%h uf=%d mismatch=%d",output_frames,captured_frames,fault,underflows,pixel_mismatches);
        end
    endtask
    reg [31:0] first_source;
    initial begin
        reset_system();wait_frames(2);first_source=latest_source_checksum;wait_frames(12);
        if(failed || underflows || pixel_mismatches || ownership_errors || captured_frames<3 ||
           read_frames<12 || !display_valid || pixels_seen<12*12288 || latest_source_checksum==first_source)
            $fatal(1,"Continuous motion/ownership verification failed");
        $display("INFO: twelve changing complete output frames passed; testing underflow");
        // Disable responses after a clean reset: the display must detect empty
        // input instead of replaying stale words as though a new frame succeeded.
        stall_reads=1;reset_system();
        wait(underflows!=0);
        if(display_valid) $fatal(1,"Underrun displayed a valid frame");
        $display("INFO: underflow detected; testing recovery and periodic read corruption");
        stall_reads=0;reset_system();wait_frames(3);
        corrupt_reads=1;reset_system();wait(failed || pixel_mismatches!=0);
        if(fault!=8'h14 && pixel_mismatches==0) $fatal(1,"Read corruption not detected");
        $display("INFO: periodic multi-bit corruption detected; testing final recovery");
        corrupt_reads=0;reset_system();wait_frames(3);
        $display("PASS wide live DDR video (768 beats per frame > 512 FIFO depth): independent clocks, changing camera frames, 12 native-resolution output frames, every output pixel compared, two-bank ownership, concurrent DDR read/write, burst stalls, underflow/corruption rejection and reset recovery.");
        $finish;
    end
    initial begin #50000000;$fatal(1,"Global testbench timeout");end
endmodule
