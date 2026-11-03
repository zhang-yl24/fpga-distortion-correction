`timescale 1ns/1ps
// Target the edges where an unpublished payload becomes a reserved burst.
module tb_writer_fault_collision;
    reg clk=0,rst_n=0,abort=0,frame_valid=0,in_valid=0;
    always #4 clk=~clk;
    reg [27:0] frame_base=28'd1024;
    reg [31:0] frame_id=32'd91;
    reg [23:0] in_rgb=0,in_tag=0;
    wire frame_ready,in_ready,awvalid,done,failed;
    wire [27:0] awaddr;
    wire [3:0] awlen;
    wire [255:0] wdata;
    wire [31:0] wstrb,accepted_pixels,written_beats,last_checksum,completed_id;
    wire [7:0] fault;
    reg allow_aw=0,allow_w=0,bus_busy=0;
    integer bus_beat=0,bursts=0,beats=0,j;
    wire awready=allow_aw && !bus_busy;
    wire wready=allow_w && (bus_busy || (awvalid && awready));
    wire wlast=wready && (bus_busy ? bus_beat==15:1'b0);
    ddr_raster_result_writer_pingpong #(.WIDTH(96),.HEIGHT(16),.TIMEOUT_BITS(10)) dut(.*);

    function [23:0] rgb(input integer tag);
        begin rgb={8'((tag*17+3)%256),8'((tag*7+11)%256),8'((tag*29+5)%256)};end
    endfunction
    function [15:0] pixel(input integer tag);
        reg [23:0] p;begin p=rgb(tag);pixel={p[23:19],p[15:10],p[7:3]};end
    endfunction
    reg held_aw=0,held_data=0;
    reg [255:0] saved_data;
    always @(posedge clk) begin
        if(!rst_n) begin bus_busy=0;bus_beat=0;bursts=0;beats=0;held_aw=0;held_data=0;end
        else begin
            if(held_aw && (!awvalid || awaddr!==1024 || awlen!==15)) $fatal(1,"Reserved AW changed on fault");
            if(held_data && wdata!==saved_data) $fatal(1,"Reserved payload changed on fault/stall");
            held_aw=awvalid && !awready;
            held_data=(awvalid || bus_busy) && !wready;saved_data=wdata;
            if(awvalid && awready) begin
                if(bus_busy || bursts!=0 || awaddr!==1024 || awlen!==15) $fatal(1,"Unexpected AW after fault");
                bursts=bursts+1;bus_busy=1;bus_beat=0;
            end
            if(wready) begin
                if(!bus_busy || wstrb!==32'hffffffff) $fatal(1,"Unowned/partial W");
                for(j=0;j<16;j=j+1)
                    if(wdata[16*j+:16]!==pixel(bus_beat*16+j)) $fatal(1,"Committed data corrupted beat=%0d lane=%0d",bus_beat,j);
                beats=beats+1;
                if(bus_beat==15) begin bus_busy=0;bus_beat=0;end else bus_beat=bus_beat+1;
            end
            if(done) $fatal(1,"Incomplete faulted frame published");
        end
    end
    task send_pixel(input integer tag);
        begin
            @(negedge clk);in_valid=1;in_tag=tag;in_rgb=rgb(tag);
            do @(posedge clk); while(!in_ready);
        end
    endtask
    integer boundary,kind,n,checks=0,prefetch_checks=0,payload_checks=0;
    initial begin
        for(kind=0;kind<2;kind=kind+1) for(boundary=0;boundary<5;boundary=boundary+1) begin
            @(negedge clk);rst_n=0;abort=0;in_valid=0;frame_valid=0;allow_aw=0;allow_w=0;
            repeat(4) @(negedge clk);rst_n=1;
            @(negedge clk);frame_valid=1;
            @(negedge clk);frame_valid=0;
            for(n=0;n<256;n=n+1) send_pixel(n);
            @(negedge clk);in_valid=0;
            if(boundary==0) begin
                if(dut.tx_state!==0 || !dut.full[dut.send_bank] || awvalid) $fatal(1,"No idle/full collision");
            end else begin
                wait(awvalid);@(negedge clk);
                if(boundary==2) begin allow_aw=1;allow_w=1;end
                if(boundary>=3) begin
                    allow_aw=1;allow_w=1;
                    do @(negedge clk); while(!bus_busy || bus_beat!=(boundary==3 ? 4:15));
                end
            end
            if(kind==0) abort=1;
            else begin
                if(!in_ready) $fatal(1,"Tag collision must be accepted");
                in_valid=1;in_tag=999;in_rgb=24'hffffff;
            end
            @(posedge clk);#1;
            if(!failed || fault!==(kind==0 ? 8'h33:8'h32) || accepted_pixels!=256)
                $fatal(1,"Fault/accounting mismatch boundary=%0d kind=%0d",boundary,kind);
            if(dut.cmd_pending!==0) $fatal(1,"Faulting pixel published a local command");
            if(boundary==0) begin
                if(awvalid || bursts || beats) $fatal(1,"Fault edge published idle burst");
                for(j=0;j<16;j=j+1) if(wdata[j*16+:16]!==pixel(j)) $fatal(1,"Idle prefetch value mismatch");
                prefetch_checks=prefetch_checks+1;
            end
            @(negedge clk);abort=0;in_valid=0;allow_aw=0;allow_w=0;
            repeat(7) @(negedge clk);
            allow_aw=1;allow_w=1;
            repeat(40) @(negedge clk);
            if(bus_busy || awvalid || done || frame_ready || in_ready ||
               bursts!=(boundary==0 ? 0:1) || beats!=(boundary==0 ? 0:16) ||
               written_beats!=beats || accepted_pixels!=256)
                $fatal(1,"Fault drain ownership failed boundary=%0d kind=%0d",boundary,kind);
            checks=checks+1;payload_checks=payload_checks+beats*16;
            $display("METRIC collision kind=%0d boundary=%0d bursts=%0d beats=%0d",kind,boundary,bursts,beats);
        end
        $display("PASS writer fault collisions checks=%0d idle_prefetch=%0d pixels=%0d",checks,prefetch_checks,payload_checks);$finish;
    end
    initial begin #2000000;$fatal(1,"Collision test timeout");end
endmodule
