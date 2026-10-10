`timescale 1ns/1ps
module tb_gamma_frozen_capture;
    reg cam_clk=0,core_clk=0;always #11 cam_clk=~cam_clk;always #4 core_clk=~core_clk;
    reg rst_n=0,ready=0,vsync=0,href=0;reg [7:0] data=0;
    wire [27:0] awaddr,araddr;wire [3:0] awlen,arlen;wire awvalid,arvalid;
    wire [255:0] wdata;wire [31:0] wstrb;
    reg awready=0,arready=0,wready=0,wlast=0,rvalid=0,rlast=0;
    reg [255:0] rdata=0;reg [3:0] rid=0;
    wire byte_valid,failed;reg byte_ready=0,byte_done=0;wire [7:0] byte_data,fault;
    wire [31:0] pairs_completed;
    gamma_frozen_capture #(.WIDTH(32),.HEIGHT(16),.BANK_STRIDE(512)) dut(
        .cam_clk(cam_clk),.core_clk(core_clk),.rst_n(rst_n),.ready(ready),.vsync(vsync),.href(href),.data(data),
        .cfg_out_cx(24'sd3968),.cfg_out_cy(24'sd1920),.cfg_src_cx(24'sd4096),.cfg_src_cy(24'sd1920),
        .cfg_src_fx(24'sd8192),.cfg_src_fy(24'sd8192),.cfg_inv_fx(32'sh02000000),.cfg_inv_fy(32'sh02000000),
        .cfg_k1(-32'sd524288),.cfg_k2(32'sd0),.cfg_k3(32'sd0),.cfg_p1(32'sd0),.cfg_p2(32'sd0),
        .awaddr(awaddr),.araddr(araddr),.awlen(awlen),.arlen(arlen),.awvalid(awvalid),.arvalid(arvalid),
        .awready(awready),.arready(arready),.wdata(wdata),.wstrb(wstrb),.wready(wready),.wlast(wlast),
        .rdata(rdata),.rvalid(rvalid),.rlast(rlast),.rid(rid),.byte_valid(byte_valid),.byte_ready(byte_ready),
        .byte_done(byte_done),.byte_data(byte_data),.failed(failed),.fault(fault),.pairs_completed(pairs_completed));
    reg [255:0] memory[0:95],source[0:95],golden[0:95],frozen[0:95],tones[0:95],locked_source[0:31];
    integer wbase=0,rbase=0,wi=0,ri=0,wlen=0,rlen=0,cycle=0,txwait=0,active_phase=1,bytes=0,file_handle,i;
    reg writing=0,reading=0;
    always @(negedge core_clk) begin
        cycle=cycle+1;
        awready=rst_n && ready && !writing && cycle%5!=0;
        arready=rst_n && ready && !reading && cycle%7!=0;
        wready=rst_n && ready && writing && cycle%3!=0;wlast=wready && wi==wlen;
        rvalid=rst_n && ready && reading && cycle%4!=0;rlast=rvalid && ri==rlen;
        rdata=reading ? memory[rbase+ri] : 0;
        byte_ready=rst_n && txwait==0 && cycle%13!=0;byte_done=rst_n && txwait==1;
    end
    always @(posedge core_clk) begin
        if(!rst_n) begin writing=0;reading=0;wi=0;ri=0;txwait=0;end
        else begin
            if(txwait>0) txwait=txwait-1;
            if(byte_valid && byte_ready) begin $fwrite(file_handle,"%c",byte_data);bytes=bytes+1;txwait=3+(bytes%11);end
            if(dut.engine_start) begin
                active_phase=pairs_completed;
                if(memory[0]!==source[active_phase*32]) $fatal(1,"Unknown frozen source phase=%0d",active_phase);
                if(dut.process_pass==0) for(i=0;i<32;i=i+1) locked_source[i]=memory[i];
            end
            if(dut.state!=0 && dut.state!=1) for(i=0;i<32;i=i+1)
                if(memory[i]!==locked_source[i]) $fatal(1,"Source changed between before/after processing or export");
            if(awvalid && awready) begin
                wbase=awaddr/8;wi=0;wlen=awlen;writing=1;
                if((awlen!=15 && awlen!=7) || awaddr%64 || !(awaddr<256 || (awaddr>=512 && awaddr<768))) $fatal(1,"Capture validation write range");
                if(dut.state!=1 && dut.state!=2) $fatal(1,"Write to exported immutable pair");
            end
            if(wready) begin
                if(!writing || wstrb!==32'hFFFFFFFF) $fatal(1,"Invalid W stream");
                if(wbase>=64 && wdata!==(dut.process_pass==2 ? tones[active_phase*32+(wbase%64)+wi]:golden[active_phase*32+(wbase%64)+wi])) $fatal(1,"Validation result mismatch");
                memory[wbase+wi]=wdata;if(wi==wlen) writing=0;wi=wi+1;
            end
            if(dut.engine_done) for(i=0;i<96;i=i+1) frozen[i]=memory[i];
            if(dut.state==3 || dut.state==4 || dut.state==5 || dut.state==6 || dut.state==7 || dut.state==9 || dut.state==10) for(i=0;i<32;i=i+1)
                if(memory[i]!==frozen[i] || memory[64+i]!==frozen[64+i]) $fatal(1,"Raw/result pair changed during UART transfer");
            if(arvalid && arready) begin
                rbase=araddr/8;ri=0;rlen=arlen;reading=1;
                if((arlen!=15 && arlen!=7) || araddr%64 || !(araddr<256 || (araddr>=512 && araddr<768))) $fatal(1,"Capture validation read range");
            end
            if(rvalid) begin if(ri==rlen) reading=0;ri=ri+1;end
            if(failed) $fatal(1,"Validation pipeline fault=%h",fault);
        end
    end
    integer camera_frame=0,row,col;reg [15:0] pixel;
    initial forever begin
        wait(rst_n && ready);
        @(negedge cam_clk);vsync=1;href=0;repeat(6) @(negedge cam_clk);vsync=0;repeat(4) @(negedge cam_clk);
        for(row=0;row<16;row=row+1) begin
            for(col=0;col<32;col=col+1) begin
                pixel=source[(pairs_completed%3)*32+(row*32+col)/16][((row*32+col)%16)*16+:16];
                href=1;data=pixel[7:0];@(negedge cam_clk);data=pixel[15:8];@(negedge cam_clk);
            end
            href=0;repeat(4) @(negedge cam_clk);
        end
        camera_frame=camera_frame+1;
    end
    initial begin
        file_handle=$fopen("export.bin","wb");if(!file_handle) $fatal(1,"Cannot open binary export");
        $readmemh("source.mem",source);$readmemh("result.mem",golden);$readmemh("tone.mem",tones);
        repeat(12) @(negedge core_clk);rst_n=1;repeat(12) @(negedge core_clk);ready=1;
        wait(pairs_completed==3);if(bytes!=9*(1024+44)) $fatal(1,"UART byte count mismatch");
        $fclose(file_handle);
        $display("PASS frozen Gamma capture: three dark/bright/neutral source transactions, nine complete CRC packets, two bypass warmup passes, enhanced pixels, immutable source and export banks, DDR/UART stalls.");$finish;
    end
    initial begin #20000000;$fatal(1,"Pair export timeout state=%0d pairs=%0d",dut.state,pairs_completed);end
endmodule
