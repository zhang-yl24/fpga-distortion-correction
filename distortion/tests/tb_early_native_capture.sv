`timescale 1ns/1ps
module tb_early_native_capture;
    reg cam_clk=0,core_clk=0;
    always #11 cam_clk=~cam_clk;always #4 core_clk=~core_clk;
    reg rst_n=0,arm=0,vsync=0,href=0;reg [7:0] data=0;
    wire [257:0] fifo_data;wire fifo_valid,fifo_ready,pop;
    wire [9:0] available;wire source_done,source_valid;
    wire [31:0] source_checksum,written_beats,write_checksum;
    wire [27:0] awaddr;wire [3:0] awlen,state;wire awvalid,done,failed;
    wire [7:0] fault;wire [255:0] wdata;wire [31:0] wstrb;
    reg awready=0,wready=0,wlast=0;
    reg [255:0] source[0:19199];
    `include "checksum.vh"
    camera_live_bridge_early bridge(.cam_clk(cam_clk),.ddr_clk(core_clk),.rst_n(rst_n),.arm(arm),
        .vsync(vsync),.href(href),.data(data),.fifo_rd_en(pop),.fifo_data(fifo_data),
        .fifo_valid(fifo_valid),.fifo_ready(fifo_ready),.fifo_available(available),
        .source_done(source_done),.source_valid(source_valid),.source_checksum(source_checksum));
    ddr_video_writer writer(.clk(core_clk),.rst_n(rst_n),.base_address(28'b0),
        .fifo_available(available),.fifo_ready(fifo_ready),.fifo_rd_en(pop),.fifo_valid(fifo_valid),.fifo_data(fifo_data),
        .source_done(source_done),.source_valid(source_valid),.source_checksum(source_checksum),
        .awaddr(awaddr),.awlen(awlen),.awvalid(awvalid),.awready(awready),
        .wdata(wdata),.wstrb(wstrb),.wready(wready),.wlast(wlast),
        .state(state),.done(done),.failed(failed),.fault(fault),.written_beats(written_beats),.write_checksum(write_checksum));
    integer cycle=0,base=0,lane=0,beats=0;reg writing=0;
    always @(negedge core_clk) begin
        cycle=cycle+1;awready=rst_n && !writing && cycle%7!=0;
        wready=rst_n && writing && cycle%3!=0;wlast=wready && lane==15;
    end
    always @(posedge core_clk) begin
        if(!rst_n) begin writing=0;base=0;lane=0;beats=0;end
        else begin
            if(awvalid && awready) begin
                if(awlen!=15 || awaddr%128 || awaddr/8!=beats) $fatal(1,"Native capture burst address");
                base=awaddr/8;lane=0;writing=1;
            end
            if(wready) begin
                if(wdata!==source[base+lane] || wstrb!==32'hFFFFFFFF) $fatal(1,"Native capture byte/lane mismatch at beat %0d",base+lane);
                beats=beats+1;if(lane==15) writing=0;lane=lane+1;
            end
        end
    end
    task reset_system;
        begin rst_n=0;arm=0;href=0;vsync=0;repeat(12) @(negedge cam_clk);rst_n=1;arm=1;repeat(12) @(negedge cam_clk);end
    endtask
    task send_frame(input integer rows,input integer short_last);
        reg [15:0] pixel;
        begin
            @(negedge cam_clk);vsync=1;repeat(8) @(negedge cam_clk);vsync=0;repeat(8) @(negedge cam_clk);
            for(integer y=0;y<rows;y=y+1) begin
                for(integer x=0;x<640-((y==rows-1 && short_last==1)?1:0);x=x+1) begin
                    pixel=source[(y*640+x)/16][((y*640+x)%16)*16+:16];
                    href=1;data=pixel[7:0];@(negedge cam_clk);
                    if(!(short_last==2 && y==rows-1 && x==639)) begin
                        data=pixel[15:8];@(negedge cam_clk);
                    end
                end
                href=0;repeat(16) @(negedge cam_clk);
            end
        end
    endtask
    initial begin
        $readmemh("source.mem",source);
        reset_system();send_frame(480,0);
        // No next VSYNC is sent: completion must follow last line alone.
        repeat(4000) @(negedge core_clk);
        if(!done || failed || !source_valid || beats!=19200 || source_checksum!==EXPECTED_CRC || ~write_checksum!==EXPECTED_CRC)
            $fatal(1,"Native early publication/CRC failed done=%0d fault=%h beats=%0d",done,fault,beats);
        @(negedge cam_clk);vsync=1;repeat(30) @(negedge cam_clk);vsync=0;
        if(beats!=19200 || !done) $fatal(1,"Frozen source changed after next VSYNC");
        reset_system();send_frame(480,1);repeat(4000) @(negedge core_clk);
        if(done || !failed || source_valid || !source_done) $fatal(1,"Short final line published");
        reset_system();send_frame(480,2);repeat(4000) @(negedge core_clk);
        if(done || !failed || source_valid || !source_done) $fatal(1,"Odd-byte final line published");
        reset_system();send_frame(100,0);reset_system();send_frame(480,0);repeat(4000) @(negedge core_clk);
        if(!done || failed || beats!=19200 || source_checksum!==EXPECTED_CRC) $fatal(1,"Reset left stale native FIFO/source");
        $display("PASS early native capture: two real 640x480 sources byte-exact with Python CRC, completion before next VSYNC, frozen metadata, 639-pixel and odd-byte final lines rejected, mid-frame reset recovery and DDR burst stalls.");$finish;
    end
    initial begin #80000000;$fatal(1,"Native early timeout");end
endmodule
