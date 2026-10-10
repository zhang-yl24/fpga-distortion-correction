`timescale 1ns/1ps
module tb_adaptive_native_regression;
    reg clk=0;always #4 clk=~clk;
    reg rst_n=0,frame_valid=0;wire frame_ready;
    `include "D:/English/FPGA/distortion/board/calibration-trial.vh"
    `include "D:/English/FPGA/distortion/board/rotation-domain.vh"
    reg signed [31:0] rot_cos,rot_sin;reg [63:0] rotations[0:5];
    reg signed [23:0] src_cx=CAL_SRC_CX;
    reg signed [31:0] k1=CAL_K1;
    wire [27:0] araddr,awaddr;wire [3:0] arlen,awlen;wire arvalid,awvalid;
    reg arready=0,awready=0,wready=0,wlast=0;
    reg [255:0] rdata=0;reg rvalid=0,rlast=0;
    wire [255:0] wdata;wire [31:0] wstrb;
    wire done,failed;wire [7:0] fault;wire [27:0] completed_base;
    wire [31:0] completed_id,completed_crc,hits,misses,queries;
    integer phase=0;
    adaptive_tiled_frame_engine #(.WIDTH(640),.HEIGHT(480),.TIMEOUT_BITS(16),.MAX_RADIUS_Q22(ROT_MAX_R2_Q22)) dut(
        .clk(clk),.rst_n(rst_n),.frame_valid(frame_valid),.frame_ready(frame_ready),
        .source_base(28'd0),.output_base(28'd262144),.frame_id(phase+4),
        .cfg_out_cx(CAL_OUT_CX),.cfg_out_cy(CAL_OUT_CY),.cfg_src_cx(src_cx),.cfg_src_cy(CAL_SRC_CY),
        .cfg_src_fx(CAL_SRC_FX),.cfg_src_fy(CAL_SRC_FY),.cfg_inv_fx(CAL_INV_FX),.cfg_inv_fy(CAL_INV_FY),
        .cfg_k1(k1),.cfg_k2(CAL_K2),.cfg_k3(CAL_K3),.cfg_p1(CAL_P1),.cfg_p2(CAL_P2),
        .cfg_rot_cx(24'sd81792),.cfg_rot_cy(24'sd61312),.cfg_rot_cos(rot_cos),.cfg_rot_sin(rot_sin),
        .araddr(araddr),.arlen(arlen),.arvalid(arvalid),.arready(arready),.rdata(rdata),.rvalid(rvalid),.rlast(rlast),.rid(4'd0),
        .awaddr(awaddr),.awlen(awlen),.awvalid(awvalid),.awready(awready),.wdata(wdata),.wstrb(wstrb),.wready(wready),.wlast(wlast),
        .done(done),.failed(failed),.fault(fault),.completed_base(completed_base),.completed_id(completed_id),.completed_crc(completed_crc),
        .hits(hits),.misses(misses),.completed_queries(queries));
    reg [255:0] memory[0:65535],source[0:115199],golden[0:115199];reg [31:0] crcs[0:5];
    integer ticks=0,rleft=0,rindex=0,wleft=0,windex=0,checked=0,reads=0;
    integer begin_ticks,begin_hits,begin_misses,begin_reads,report;
    reg readheld=0,writeheld=0,dataheld=0;
    reg [27:0] savedar,savedaw;reg [255:0] saveddata;
    always @(negedge clk) begin
        ticks=ticks+1;
        arready=rst_n && rleft==0 && ticks%7>=3;
        awready=rst_n && wleft==0 && ticks%9>=4;
        rvalid=rst_n && rleft!=0 && ticks%5!=0;
        rlast=rleft==1;if(rvalid) rdata=memory[rindex];
        wready=rst_n && wleft!=0 && ticks%6!=0;wlast=wleft==1;
    end
    always @(posedge clk) begin
        if(!rst_n) begin rleft<=0;wleft<=0;readheld<=0;writeheld<=0;dataheld<=0;end
        else begin
            if(failed) $fatal(1,"Native remap fault %h",fault);
            if(readheld && (!arvalid || araddr!==savedar)) $fatal(1,"AR changed while stalled");
            if(writeheld && (!awvalid || awaddr!==savedaw)) $fatal(1,"AW changed while stalled");
            if(dataheld && wdata!==saveddata) $fatal(1,"Output data changed while stalled");
            readheld<=arvalid && !arready;savedar<=araddr;
            writeheld<=awvalid && !awready;savedaw<=awaddr;
            dataheld<=wleft!=0 && !wready;saveddata<=wdata;
            if(arvalid && arready) begin
                if(arlen!=15 || araddr[6:0]!=0 || rleft!=0 || araddr>=153600) $fatal(1,"Read outside source frame");
                rleft<=16;rindex<=araddr>>3;reads<=reads+1;
            end
            if(rvalid) begin rleft<=rleft-1;rindex<=rindex+1;end
            if(awvalid && awready) begin
                if(awlen!=15 || awaddr[6:0]!=0 || wleft!=0 || awaddr<262144 || awaddr>=415744) $fatal(1,"Write outside result bank");
                wleft<=16;windex<=awaddr>>3;
            end
            if(wready) begin
                if(wstrb!==32'hffffffff || wdata!==golden[phase*19200+windex-32768])
                    $fatal(1,"Native reference mismatch phase=%0d beat=%0d",phase,windex-32768);
                memory[windex]<=wdata;windex<=windex+1;wleft<=wleft-1;checked<=checked+1;
                if(checked%4096==4095) $display("Native progress phase=%0d output_pixels=%0d",phase,(checked+1)*16);
            end
        end
    end
    integer i;
    initial begin
        $readmemh("source.mem",source);$readmemh("result.mem",golden);$readmemh("crcs.mem",crcs);$readmemh("rotations.mem",rotations);
        report=$fopen("cycles.csv","w");$fdisplay(report,"phase,cycles,cache_hits,cache_misses,read_bursts,pixels,crc32");
        repeat(8) @(negedge clk);rst_n=1;
        for(phase=0;phase<6;phase=phase+1) begin
            for(i=0;i<19200;i=i+1) memory[i]=source[phase*19200+i];
            wait(frame_ready);@(negedge clk);src_cx=CAL_SRC_CX;k1=CAL_K1;{rot_cos,rot_sin}=rotations[phase];frame_valid=1;
            begin_ticks=ticks;begin_hits=hits;begin_misses=misses;begin_reads=reads;
            do @(posedge clk);while(!frame_ready);
            @(negedge clk);frame_valid=0;src_cx=0;k1=0;rot_cos=0;rot_sin=0;
            wait(done);
            if(completed_base!=262144 || completed_id!=phase+4 || completed_crc!==crcs[phase]) $fatal(1,"Wrong native frame metadata");
            if(checked!=(phase+1)*19200 || queries!=(phase+1)*307200) $fatal(1,"Incomplete native output");
            for(i=0;i<19200;i=i+1) begin
                if(memory[32768+i]!==golden[phase*19200+i]) $fatal(1,"Committed result differs");
                if(memory[i]!==source[phase*19200+i]) $fatal(1,"Source overwritten");
            end
            $fdisplay(report,"%0d,%0d,%0d,%0d,%0d,307200,%08x",phase,ticks-begin_ticks,hits-begin_hits,misses-begin_misses,reads-begin_reads,completed_crc);
            $display("PASS native frame %0d: 307200 real-camera pixels, CRC=%08x, cycles=%0d, misses=%0d",phase,completed_crc,ticks-begin_ticks,misses-begin_misses);
            @(negedge clk);
        end
        $fclose(report);
        $display("PASS adaptive native regression: 1843200 real-camera pixels, arithmetic coordinates, bilinear RGB565, immutable source, same-bank cache invalidation, locked parameters, complete DDR writes and synthetic stalls.");$finish;
    end
    initial begin #900000000;$fatal(1,"Native regression timeout");end
endmodule
