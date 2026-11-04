`timescale 1ns/1ps
// Verify that speculative private payload changes never publish a RAM write.
module tb_writer_publication;
    reg clk=0,rst_n=0,abort=0,frame_valid=0,in_valid=0;
    always #4 clk=~clk;
    reg [27:0] frame_base=1024;
    reg [31:0] frame_id=101;
    reg [23:0] in_rgb=0,in_tag=0;
    wire frame_ready,in_ready,awvalid,done,failed;
    wire [27:0] awaddr;
    wire [3:0] awlen;
    wire [255:0] wdata;
    wire [31:0] wstrb,accepted_pixels,written_beats,last_checksum,completed_id;
    wire [7:0] fault;
    reg allow_bus=0,bus_busy=0;
    integer bus_beat=0;
    wire awready=rst_n && allow_bus && !bus_busy;
    wire wready=rst_n && allow_bus && (bus_busy || awvalid && awready);
    wire wlast=wready && bus_busy && bus_beat==15;
    ddr_raster_result_writer_pingpong #(.WIDTH(64),.HEIGHT(16),.TIMEOUT_BITS(14)) dut(.*);

    function [23:0] rgb(input integer n);
        begin rgb={8'((n*29+31)%256),8'((n*11+19)%256),8'((n*17+7)%256)};end
    endfunction
    function [15:0] pack(input [23:0] p);
        begin pack={p[23:19],p[15:10],p[7:3]};end
    endfunction
    always @(posedge clk) begin
        if(!rst_n)begin bus_busy=0;bus_beat=0;end
        else begin
            if(awvalid && awready)begin bus_busy=1;bus_beat=0;end
            if(wready)begin
                if(bus_beat==15)begin bus_busy=0;bus_beat=0;end
                else bus_beat=bus_beat+1;
            end
        end
    end

    reg [255:0] expected_burst[0:31];
    reg expected_pending=0;
    integer expected_word=0,expected_lane=0;
    reg [15:0] expected_pixel=0;
    reg new_pending;
    integer new_word,new_lane,k,selected_word;
    reg [15:0] new_pixel;
    reg [31:0] pending_mask;
    integer edges=0,retirements=0,idle_edges=0,stalled_edges=0,fault_edges=0,reset_edges=0;
    integer pending_reset=0,pending_bad_tag=0,pending_abort=0,bank_wraps=0,invalid_prefetch=0;
    // Acceptance uses only the public input protocol and frame pixel count.
    // Burst RAM keeps its contents across reset; an already pending write may
    // retire on the reset edge, exactly as the frozen interface specifies.
    always @(posedge clk) begin
        if(expected_pending)begin
            expected_burst[expected_word][16*expected_lane+:16]=expected_pixel;
            retirements=retirements+1;
            if(!rst_n)pending_reset=pending_reset+1;
            if(rst_n && in_valid && in_ready && in_tag!=accepted_pixels)pending_bad_tag=pending_bad_tag+1;
            if(rst_n && abort)pending_abort=pending_abort+1;
        end
        new_pending=rst_n && !failed && in_valid && in_ready && in_tag==accepted_pixels;
        new_word=(accepted_pixels/16)%32;new_lane=accepted_pixels%16;new_pixel=pack(in_rgb);
        pending_mask=0;if(new_pending)pending_mask[new_word]=1;
        if(new_pending && accepted_pixels[7:0]==255)bank_wraps=bank_wraps+1;
        if(!in_valid)idle_edges=idle_edges+1;
        if(in_valid && !in_ready && rst_n && !failed)stalled_edges=stalled_edges+1;
        if(failed)fault_edges=fault_edges+1;
        if(!rst_n)reset_edges=reset_edges+1;
        selected_word={dut.fill_bank,dut.slot[7:4]};
        #1;
        if(dut.cmd_pending!==pending_mask)$fatal(1,"Published command differs from accepted input");
        if(new_pending && (dut.cmd_pixel[new_word]!==new_pixel || dut.cmd_lane[new_word]!==new_lane))
            $fatal(1,"Published payload or lane differs from its accepted pixel");
        if(selected_word>=0 && selected_word<32 && dut.cmd_pixel[selected_word]===new_pixel && !new_pending)
            invalid_prefetch=invalid_prefetch+1;
        for(k=0;k<32;k=k+1)
            if(dut.burst[k]!==expected_burst[k])$fatal(1,"Unpublished or corrupt burst update word=%0d edge=%0d",k,edges);
        expected_pending=new_pending;expected_word=new_word;expected_lane=new_lane;expected_pixel=new_pixel;
        edges=edges+1;
    end
    task reset_writer;
        begin
            @(negedge clk);rst_n=0;frame_valid=0;in_valid=0;abort=0;allow_bus=0;
            repeat(3)begin @(negedge clk);in_rgb=in_rgb+24'h123457;end
            rst_n=1;repeat(2)@(negedge clk);
            frame_valid=1;@(negedge clk);frame_valid=0;
        end
    endtask
    task send_pixel(input integer n);
        begin
            @(negedge clk);in_valid=1;in_tag=n;in_rgb=rgb(n);
            do @(posedge clk);while(!in_ready);
        end
    endtask
    integer scenario,n,checks=0;
    initial begin
        // Full-bank backpressure: arbitrary input data changes while no input
        // can be accepted. Then reuse both banks and finish a complete frame.
        reset_writer();
        for(n=0;n<512;n=n+1)send_pixel(n);
        @(negedge clk);in_tag=512;
        repeat(19)begin in_rgb=in_rgb+24'h034519;@(negedge clk);if(in_ready)$fatal(1,"Both-bank stall not covered");end
        in_valid=0;allow_bus=1;
        for(n=512;n<1024;n=n+1)send_pixel(n);
        @(negedge clk);in_valid=0;
        wait(done);@(negedge clk);if(failed)$fatal(1,"Healthy frame faulted");checks=checks+1;
        // Fault/reset collide with a previous accepted publication, including
        // the final command of a bank. Abort+valid keeps frozen issue semantics.
        for(scenario=0;scenario<7;scenario=scenario+1)begin
            reset_writer();
            for(n=0;n<(scenario<4 ? 17:256);n=n+1)send_pixel(n);
            @(negedge clk);
            if(scenario==0 || scenario==4)begin in_valid=1;in_tag=999;in_rgb=24'hff5533;end
            else if(scenario==1 || scenario==5)begin in_valid=0;abort=1;in_rgb=24'h0055ff;end
            else if(scenario==2 || scenario==6)begin rst_n=0;in_valid=0;in_rgb=24'hf00f33;end
            else begin abort=1;in_valid=1;in_tag=17;in_rgb=rgb(17);end
            @(negedge clk);in_valid=0;abort=0;
            repeat(11)begin in_rgb=in_rgb+24'h439527;@(negedge clk);end
            if(scenario!=2 && scenario!=6 && !failed)$fatal(1,"Expected fault missing");
            checks=checks+1;
        end
        if(retirements<1000 || stalled_edges<10 || fault_edges<50 || reset_edges<10 ||
           pending_reset<2 || pending_bad_tag<2 || pending_abort<3 || bank_wraps<7 || invalid_prefetch<50)
            $fatal(1,"Publication coverage was vacuous");
        $display("METRIC publication edges=%0d retired=%0d invalid_prefetch=%0d stalled=%0d fault=%0d reset=%0d",edges,retirements,invalid_prefetch,stalled_edges,fault_edges,reset_edges);
        $display("METRIC collision pending_reset=%0d pending_bad_tag=%0d pending_abort=%0d bank_wraps=%0d",pending_reset,pending_bad_tag,pending_abort,bank_wraps);
        $display("PASS writer publication checks=%0d",checks);$finish;
    end
    initial begin #2000000;$fatal(1,"Publication test timeout");end
endmodule
