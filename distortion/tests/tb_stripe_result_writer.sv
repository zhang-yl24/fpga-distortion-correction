`timescale 1ns/1ps
module tb_stripe_result_writer;
    reg clk=0,rst_n=0,frame_valid=0,in_valid=0;
    always #4 clk=~clk;
    wire frame_ready,in_ready;
    reg [23:0] in_rgb=0,in_tag=0;
    wire [27:0] awaddr;wire [3:0] awlen;wire awvalid;
    reg awready=0,wready=0,wlast=0;
    wire [255:0] wdata;wire [31:0] wstrb;
    wire done,failed;wire [7:0] fault;
    wire [31:0] accepted_pixels,written_beats,last_checksum,completed_id;
    ddr_stripe_result_writer #(.WIDTH(96),.HEIGHT(16),.TIMEOUT_BITS(8)) dut(
        .clk(clk),.rst_n(rst_n),.frame_valid(frame_valid),.frame_ready(frame_ready),
        .frame_base(28'd1024),.frame_id(32'd56),.in_valid(in_valid),.in_ready(in_ready),.in_rgb(in_rgb),.in_tag(in_tag),
        .awaddr(awaddr),.awlen(awlen),.awvalid(awvalid),.awready(awready),
        .wdata(wdata),.wstrb(wstrb),.wready(wready),.wlast(wlast),.done(done),.failed(failed),.fault(fault),
        .accepted_pixels(accepted_pixels),.written_beats(written_beats),.last_checksum(last_checksum),.completed_id(completed_id));
    `include "D:/English/FPGA/distortion/build/stripe_writer_sim/checksum.vh"
    function [23:0] rgb;
        input integer tag;
        begin rgb={8'((tag*17+3)%256),8'((tag*7+11)%256),8'((tag*29+5)%256)};end
    endfunction
    function [15:0] packed_pixel;
        input integer tag;reg [23:0] p;
        begin p=rgb(tag);packed_pixel={p[23:19],p[15:10],p[7:3]};end
    endfunction
    integer cycle=0,beat=0,out_index=0,j,mode=0,checked=0;
    reg writing=0,held_aw=0,held_data=0;
    reg [27:0] saved_aw;reg [255:0] saved_data;
    always @(negedge clk) begin
        cycle=cycle+1;
        awready=rst_n && !writing && cycle%7!=0;
        wready=rst_n && writing && mode!=3 && cycle%3!=0;
        wlast=wready && (mode==2 ? beat==3:beat==15);
    end
    always @(posedge clk) begin
        if(!rst_n) begin writing=0;beat=0;out_index=0;checked=0;held_aw=0;held_data=0;end
        else begin
            if(held_aw && (!awvalid || awaddr!==saved_aw)) $fatal(1,"AW retracted or moved during stall");
            if(held_data && wdata!==saved_data) $fatal(1,"W payload changed during stall");
            held_aw=awvalid && !awready;saved_aw=awaddr;
            held_data=writing && !wready && !failed;saved_data=wdata;
            if(awvalid && awready) begin
                if(awlen!=15 || awaddr!=1024+checked*8) $fatal(1,"Raster burst address incorrect");
                writing=1;beat=0;out_index=(awaddr-1024)*2;
            end
            if(wready && !failed) begin
                if(wstrb!==32'hFFFFFFFF) $fatal(1,"Partial write mask");
                for(j=0;j<16;j=j+1)
                    if(wdata[j*16+:16]!==packed_pixel(out_index+j)) $fatal(1,"Reorder mismatch pixel=%0d",out_index+j);
                checked=checked+1;out_index=out_index+16;
                if(beat==15) writing=0;beat=beat+1;
            end
        end
    end
    task reset_system;
        begin rst_n=0;frame_valid=0;in_valid=0;repeat(5) @(negedge clk);rst_n=1;repeat(5) @(negedge clk);end
    endtask
    task begin_frame;
        begin wait(frame_ready);@(negedge clk);frame_valid=1;@(negedge clk);frame_valid=0;end
    endtask
    task send_pixel;
        input integer tag;
        begin
            @(negedge clk);in_valid=1;in_tag=tag;in_rgb=rgb(tag);
            do @(posedge clk);while(!in_ready);
            @(negedge clk);in_valid=0;
        end
    endtask
    task send_frame;
        integer sy,tx,yy,xx;
        begin for(sy=0;sy<16;sy=sy+8) for(tx=0;tx<96;tx=tx+8)
            for(yy=0;yy<8;yy=yy+1) for(xx=0;xx<8;xx=xx+1) send_pixel((sy+yy)*96+tx+xx);end
    endtask
    task check_frame;
        begin wait(done);#1;
            if(failed || checked!=96 || accepted_pixels!=1536 || written_beats!=96 || completed_id!=56 || last_checksum!==EXPECTED_CRC)
                $fatal(1,"Full stripe frame metadata/CRC failed CRC=%08x expected=%08x",last_checksum,EXPECTED_CRC);
        end
    endtask
    integer n;
    initial begin
        reset_system();begin_frame();send_frame();check_frame();
        reset_system();begin_frame();send_pixel(1);wait(failed);
        if(fault!=8'h32 || done || written_beats || accepted_pixels) $fatal(1,"Wrong tag was published");
        reset_system();begin_frame();
        for(n=0;n<5;n=n+1) send_pixel(n);
        reset_system();begin_frame();send_frame();check_frame();
        mode=2;reset_system();begin_frame();
        fork begin send_frame();end begin wait(failed);end join_any
        disable fork;
        if(fault!=8'h02 || done) $fatal(1,"Malformed WLAST was published");
        mode=3;reset_system();begin_frame();
        fork begin send_frame();end begin wait(failed);end join_any
        disable fork;
        if(fault!=8'h01 || done) $fatal(1,"Timed-out write was published");
        $display("PASS stripe reorder: two multi-burst stripes, byte-exact raster data/Python CRC, AW/W stalls, wrong tag rejection, mid-stripe reset, malformed WLAST and timeout quarantine.");$finish;
    end
    initial begin #2000000;$fatal(1,"Stripe test timeout");end
endmodule
