`timescale 1ns/1ps
module tb_writer_pingpong;
    localparam WIDTH=96,HEIGHT=16,PIXELS=WIDTH*HEIGHT,BEATS=PIXELS/16;
    reg clk=0,rst_n=0,frame_valid=0,frame_tiled=0,in_valid=0;
    always #4 clk=~clk;
    reg [27:0] frame_base=28'd1024;
    reg [31:0] frame_id=32'd56;
    reg [23:0] in_rgb=0,in_tag=0;
    wire frame_ready,in_ready,awvalid,done,failed;
    wire [27:0] awaddr;
    wire [3:0] awlen;
    wire [255:0] wdata;
    wire [31:0] wstrb,accepted_pixels,written_beats,last_checksum,completed_id;
    wire [7:0] fault;
    reg awready,wready,wlast;
    ddr_adaptive_result_writer_capture_local #(.WIDTH(WIDTH),.HEIGHT(HEIGHT),.TIMEOUT_BITS(10)) dut(.*);

    function [23:0] rgb;
        input integer tag;
        begin rgb={8'((tag*17+3)%256),8'((tag*7+11)%256),8'((tag*29+5)%256)};end
    endfunction
    function [15:0] packed_pixel;
        input integer tag;reg [23:0] p;
        begin p=rgb(tag);packed_pixel={p[23:19],p[15:10],p[7:3]};end
    endfunction
    // Independent serial polynomial reference, RGB565 little endian.
    function [31:0] crc_pixel;
        input [31:0] previous;input [15:0] pixel;reg [31:0] c;integer k;
        begin c=previous;for(k=0;k<16;k=k+1) c=(c>>1)^((c[0]^pixel[k])?32'hEDB88320:0);crc_pixel=c;end
    endfunction

    integer test_case=0,tile_mode=0,cycle=0,start_cycle=0,stalls=0,checked=0,bursts=0;
    integer bus_beat=0,j,out_index=0,full_stalls=0,simultaneous=0;
    reg bus_busy=0,held_aw=0,held_data=0;
    reg [27:0] saved_aw;
    reg [255:0] saved_data;
    reg [31:0] expected_crc;
    wire hold_address=(test_case==2 || test_case==4 || test_case==12) && cycle<900;
    wire hold_write=(test_case==3 || test_case==5 || test_case==13) && cycle<900 || test_case==7 && cycle<1500;
    wire hold_simultaneous=test_case==10 && bus_busy && bus_beat==15 && bursts==1 && accepted_pixels<511;
    wire random_aw=test_case==1 && cycle%7==0;
    wire random_w=test_case==1 && (cycle%3==0 || cycle%19<5);
    always @* begin
        awready=rst_n && !bus_busy && !hold_address && !random_aw;
        wready=rst_n && (bus_busy || (awvalid && awready)) && !hold_write && !random_w && !hold_simultaneous;
        wlast=wready && ((bus_busy ? bus_beat:0)==15);
        if(test_case==6 && wready && bus_beat==3) wlast=1;
        if(test_case==14 && wready && bus_beat==15) wlast=0;
    end
    always @(posedge clk) begin
        if(!rst_n) begin
            cycle=0;bus_busy=0;bus_beat=0;out_index=0;checked=0;bursts=0;
            held_aw=0;held_data=0;stalls=0;full_stalls=0;simultaneous=0;
        end else begin
            cycle=cycle+1;
            if(frame_valid && frame_ready) begin
                start_cycle=cycle;checked=0;bursts=0;out_index=0;stalls=0;
            end
            if(in_valid && !in_ready && !failed) stalls=stalls+1;
            if(in_valid && !in_ready && accepted_pixels==512 && !failed) full_stalls=full_stalls+1;
            if(in_valid && in_ready && accepted_pixels[7:0]==255 && wready && bus_beat==15)
                simultaneous=simultaneous+1;
            if(held_aw && (!awvalid || awaddr!==saved_aw || awlen!==15))
                $fatal(1,"AW changed/retracted while reserved, case=%0d",test_case);
            if(held_data && wdata!==saved_data) $fatal(1,"W payload moved during backpressure");
            held_aw=awvalid && !awready;saved_aw=awaddr;
            held_data=bus_busy && !wready;saved_data=wdata;
            if(awvalid && awready) begin
                if(bus_busy || awlen!==15 || awaddr!==frame_base+bursts*128)
                    $fatal(1,"AW sequence mismatch addr=%0d burst=%0d",awaddr,bursts);
                bus_busy=1;bus_beat=0;out_index=bursts*256;bursts=bursts+1;
            end
            if(wready) begin
                if(!bus_busy) $fatal(1,"Write beat without accepted AW");
                if(wstrb!==32'hFFFFFFFF) $fatal(1,"Partial write strobe");
                for(j=0;j<16;j=j+1)
                    if(wdata[j*16+:16]!==packed_pixel(out_index+j))
                        $fatal(1,"Pixel mismatch at %0d got=%h expected=%h",out_index+j,wdata[j*16+:16],packed_pixel(out_index+j));
                checked=checked+1;out_index=out_index+16;
                if(bus_beat==15) begin bus_busy=0;bus_beat=0;end
                else bus_beat=bus_beat+1;
            end
            if(failed && done) $fatal(1,"Failed frame was published");
        end
    end
    task reset_system;
        begin
            @(negedge clk);rst_n=0;frame_valid=0;in_valid=0;
            repeat(5) @(negedge clk);rst_n=1;
            repeat(3) @(negedge clk);
        end
    endtask
    task begin_frame;
        begin
            wait(frame_ready);@(negedge clk);frame_tiled=tile_mode;frame_valid=1;
            @(negedge clk);frame_valid=0;frame_tiled=!tile_mode;
        end
    endtask
    task send_one;
        input integer tag;
        begin
            @(negedge clk);in_valid=1;in_tag=tag;in_rgb=rgb(tag);
            do @(posedge clk); while(!in_ready);
        end
    endtask
    task send_good_frame;
        integer n,sy,tx,yy,xx;
        begin
            if(tile_mode==0) for(n=0;n<PIXELS;n=n+1) send_one(n);
            else for(sy=0;sy<HEIGHT;sy=sy+8) for(tx=0;tx<WIDTH;tx=tx+8)
                for(yy=0;yy<8;yy=yy+1) for(xx=0;xx<8;xx=xx+1) send_one((sy+yy)*WIDTH+tx+xx);
            @(negedge clk);in_valid=0;
        end
    endtask
    task expect_success;
        begin
            wait(done);#1;
            if(failed || checked!=BEATS || accepted_pixels!=PIXELS || written_beats!=BEATS ||
               completed_id!=frame_id || last_checksum!==expected_crc)
                $fatal(1,"Completed frame metadata or CRC mismatch pixels=%0d beats=%0d crc=%08x expected=%08x",accepted_pixels,written_beats,last_checksum,expected_crc);
            $display("METRIC case=%0d tile=%0d cycles=%0d input_stalls=%0d pixels=%0d beats=%0d crc=%08x",test_case,tile_mode,cycle-start_cycle,stalls,accepted_pixels,written_beats,last_checksum);
            if((test_case==2 || test_case==3) && tile_mode==0 && full_stalls==0)
                $display("NOTE baseline can stall before it accepts a second bank");
        end
    endtask
    integer n,ignore_arg;
    initial begin
        ignore_arg=$value$plusargs("CASE%d",test_case);
        ignore_arg=$value$plusargs("TILE%d",tile_mode);
        expected_crc=32'hFFFFFFFF;
        for(n=0;n<PIXELS;n=n+1) expected_crc=crc_pixel(expected_crc,packed_pixel(n));
        expected_crc=~expected_crc;
        reset_system();begin_frame();
        if(test_case<=3 || test_case==10 || test_case==11) begin
            send_good_frame();expect_success();
            if(test_case==10 && simultaneous==0) $fatal(1,"Concurrent bank fill/drain was not exercised");
            // No reset between frames; opposite selector value was held after
            // frame acceptance, and a second transaction reuses both banks.
            @(negedge clk);frame_id=57;
            if(test_case==11) tile_mode=!tile_mode;
            begin_frame();send_good_frame();expect_success();
        end else if(test_case==4 || test_case==5) begin
            for(n=0;n<300;n=n+1) send_one(n);
            send_one(999);@(negedge clk);in_valid=0;wait(failed);
            if(fault!==8'h32 || accepted_pixels!=300) $fatal(1,"Incorrect tag-fault accounting");
            wait(cycle>950);repeat(40) @(negedge clk);
            if(bus_busy || awvalid || checked!=16 || bursts!=1 || done || frame_ready || in_ready)
                $fatal(1,"Fault did not retain/finish one committed burst checked=%0d bursts=%0d",checked,bursts);
        end else if(test_case==6 || test_case==7 || test_case==14) begin
            fork
                begin send_good_frame();end
                begin wait(failed);end
            join_any
            disable fork;
            @(negedge clk);in_valid=0;
            if(fault!==(test_case==7 ? 8'h01:8'h02)) $fatal(1,"Wrong transport fault");
            wait(cycle>1550);repeat(40) @(negedge clk);
            if(bus_busy || awvalid || checked!=16 || bursts!=1 || done || frame_ready || in_ready)
                $fatal(1,"Transport fault did not preserve committed payload");
        end else if(test_case==8) begin
            send_one(1);@(negedge clk);in_valid=0;wait(failed);repeat(40) @(negedge clk);
            if(fault!==8'h32 || accepted_pixels || checked || bursts || done) $fatal(1,"Invalid first tag escaped");
        end else if(test_case==9 || test_case==12 || test_case==13) begin
            for(n=0;n<270;n=n+1) send_one(n);
            if(test_case==12 && (!awvalid || bus_busy)) $fatal(1,"Reset-AW case lacks pending AW");
            if(test_case==13 && !bus_busy) $fatal(1,"Reset-W case lacks committed write");
            reset_system();test_case=0;begin_frame();send_good_frame();expect_success();
        end
        $display("PASS writer case=%0d tile=%0d",test_case,tile_mode);$finish;
    end
    initial begin #2000000;$fatal(1,"Writer test timeout");end
endmodule

