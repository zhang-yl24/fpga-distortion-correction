`timescale 1ns/1ps
module tb_camera_ddr_store;
    reg cam_clk=0,clk=0;always #11 cam_clk=~cam_clk;always #4 clk=~clk;
    reg rst_n=0,arm=0,vsync=0,href=0;reg [7:0] data=0;
    wire [9:0] fifo_available;wire fifo_ready,fifo_valid,fifo_rd_en;
    wire [257:0] fifo_data;wire source_done,source_valid;wire [31:0] source_checksum;
    camera_ddr_bridge #(.WIDTH(16),.HEIGHT(32)) bridge(
        .cam_clk(cam_clk),.ddr_clk(clk),.rst_n(rst_n),.arm(arm),.vsync(vsync),.href(href),.data(data),
        .fifo_rd_en(fifo_rd_en),.fifo_data(fifo_data),.fifo_valid(fifo_valid),.fifo_ready(fifo_ready),
        .fifo_available(fifo_available),.source_done(source_done),.source_valid(source_valid),.source_checksum(source_checksum));
    wire [27:0] awaddr,araddr;wire [3:0] awlen,arlen,state;wire awvalid,arvalid;
    wire [255:0] wdata;wire [31:0] wstrb,written_beats,read_beats,write_checksum,read_checksum;
    wire done,failed;wire [7:0] fault;
    reg awready=0,arready=0,wready=0,wlast=0,rvalid=0,rlast=0;
    reg [255:0] rdata=0;reg [3:0] rid=0;
    ddr_frame_store #(.FRAME_BEATS(32),.TIMEOUT_BITS(14)) store(.*);
    reg [255:0] memory[0:31];integer write_base=0,read_base=0,windex=0,rindex=0,cycle=0;
    reg writing=0,reading=0,corrupt=0;
    function [15:0] value;
        input integer pixel;
        begin value=16'h1234 ^ (pixel*37);end
    endfunction
    always @(posedge clk) begin
        if(!rst_n) begin writing=0;reading=0;windex=0;rindex=0;end
        else begin
            if(awvalid && awready) begin writing=1;windex=0;write_base=awaddr/8;end
            if(wready) begin
                if(!writing || wstrb!==32'hFFFFFFFF) $fatal(1,"Unexpected write");
                memory[write_base+windex]=wdata;
                if(windex==15) writing=0;
                windex=windex+1;
            end
            if(arvalid && arready) begin reading=1;rindex=0;read_base=araddr/8;end
            if(rvalid) begin if(rindex==15) reading=0;rindex=rindex+1;end
        end
    end
    always @(negedge clk) begin
        cycle=cycle+1;
        awready=rst_n && !writing && cycle%5!=0;
        arready=rst_n && !reading && cycle%7!=0;
        wready=rst_n && writing && cycle%3!=0;wlast=wready && windex==15;
        rvalid=rst_n && reading && cycle%4!=0;rlast=rvalid && rindex==15;
        rdata=reading ? memory[read_base+rindex] : 0;
        if(corrupt && read_base==16 && rindex==3) rdata[147]=!rdata[147];
    end
    task sync_frame;
        begin
            @(negedge cam_clk);href=0;vsync=1;
            repeat(4) @(negedge cam_clk);vsync=0;
            repeat(4) @(negedge cam_clk);
        end
    endtask
    task send_frame;
        input malformed;
        integer row,col;reg [15:0] pixel;
        begin
            sync_frame();
            for(row=0;row<32;row=row+1) begin
                for(col=0;col<16-(malformed && row==31);col=col+1) begin
                    pixel=value(row*16+col);
                    href=1;data=pixel[7:0];@(negedge cam_clk);
                    data=pixel[15:8];@(negedge cam_clk);
                end
                href=0;repeat(4) @(negedge cam_clk);
            end
            sync_frame();
        end
    endtask
    task restart;
        begin
            rst_n=0;arm=0;href=0;vsync=0;repeat(8) @(negedge cam_clk);
            rst_n=1;repeat(8) @(negedge cam_clk);arm=1;repeat(8) @(negedge cam_clk);
        end
    endtask
    task await_finish;
        integer timeout;
        begin
            timeout=0;
            while(!done && !failed && timeout<30000) begin @(negedge clk);timeout=timeout+1;end
            if(timeout==30000) $fatal(1,"DMA timeout state=%d",state);
        end
    endtask
    integer word,lane;
    initial begin
        restart();send_frame(0);await_finish();
        if(!done || failed || written_beats!=32 || read_beats!=32 || !source_valid ||
           source_checksum!==write_checksum || source_checksum!==read_checksum) $fatal(1,"Good frame rejected fault=%h",fault);
        for(word=0;word<32;word=word+1)
            for(lane=0;lane<16;lane=lane+1)
                if(memory[word][lane*16+:16]!==value(word*16+lane)) $fatal(1,"Pixel placement mismatch");
        corrupt=1;restart();send_frame(0);await_finish();
        if(!failed || fault!=8'h14 || done) $fatal(1,"Corrupted readback accepted");
        corrupt=0;restart();send_frame(1);await_finish();
        if(!failed || done || source_valid) $fatal(1,"Short final row committed");
        restart();send_frame(0);await_finish();
        if(!done || failed) $fatal(1,"Reset recovery failed");
        $display("PASS camera-DDR: low-byte-first DVP, pixel packing, async FIFO, full burst prefetch, exact DDR pixel addresses, source/write/read checksum, corruption rejection, malformed-frame rejection and reset recovery.");
        $finish;
    end
endmodule
