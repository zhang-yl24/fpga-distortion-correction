`timescale 1ns/1ps
module tb_gamma_frozen_native;
    `include "D:/English/FPGA/distortion/build/gamma_frozen_native_sim/config.vh"
    reg cam_clk=0,core_clk=0;always #11 cam_clk=~cam_clk;always #4 core_clk=~core_clk;
    reg rst_n=0,ready=0,vsync=0,href=0;reg [7:0] data=0;
    wire [27:0] awaddr,araddr;wire [3:0] awlen,arlen;wire awvalid,arvalid;
    wire [255:0] wdata;wire [31:0] wstrb;
    reg awready=0,arready=0,wready=0,wlast=0,rvalid=0,rlast=0;
    reg [255:0] rdata=0;reg [3:0] rid=0;
    wire byte_valid,failed;reg byte_ready=0,byte_done=0;wire [7:0] byte_data,fault;
    wire [31:0] pairs_completed;
    gamma_frozen_capture #(.WIDTH(640),.HEIGHT(480),.BANK_STRIDE(262144)) dut(
        .cam_clk(cam_clk),.core_clk(core_clk),.rst_n(rst_n),.ready(ready),.vsync(vsync),.href(href),.data(data),
        .cfg_out_cx(`CAP_OUT_CX),.cfg_out_cy(`CAP_OUT_CY),.cfg_src_cx(`CAP_SRC_CX),.cfg_src_cy(`CAP_SRC_CY),.cfg_src_fx(`CAP_SRC_FX),.cfg_src_fy(`CAP_SRC_FY),.cfg_inv_fx(`CAP_INV_FX),.cfg_inv_fy(`CAP_INV_FY),.cfg_k1(`CAP_K1),.cfg_k2(`CAP_K2),.cfg_k3(`CAP_K3),.cfg_p1(`CAP_P1),.cfg_p2(`CAP_P2),
        .awaddr(awaddr),.araddr(araddr),.awlen(awlen),.arlen(arlen),.awvalid(awvalid),.arvalid(arvalid),
        .awready(awready),.arready(arready),.wdata(wdata),.wstrb(wstrb),.wready(wready),.wlast(wlast),
        .rdata(rdata),.rvalid(rvalid),.rlast(rlast),.rid(rid),.byte_valid(byte_valid),.byte_ready(byte_ready),
        .byte_done(byte_done),.byte_data(byte_data),.failed(failed),.fault(fault),.pairs_completed(pairs_completed));
    reg [255:0] memory[0:51967],source[0:57599],golden[0:57599],frozen[0:51967],tones[0:57599],locked_source[0:19199];
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
            if(byte_valid && byte_ready) begin $fwrite(file_handle,"%c",byte_data);bytes=bytes+1;txwait=1+(bytes%3);end
            if(dut.engine_start) begin
                active_phase=pairs_completed;
                if(memory[0]!==source[active_phase*19200]) $fatal(1,"Unknown frozen source phase=%0d",active_phase);
                if(dut.process_pass==0) for(i=0;i<19200;i=i+1) locked_source[i]=memory[i];
            end
            if(dut.engine_start || dut.engine_done || dut.export_start) for(i=0;i<19200;i=i+1)
                if(memory[i]!==locked_source[i]) $fatal(1,"Source changed between before/after processing or export");
            if(awvalid && awready) begin
                wbase=awaddr/8;wi=0;wlen=awlen;writing=1;
                if((awlen!=15 && awlen!=7) || awaddr%64 || !(awaddr<153600 || (awaddr>=262144 && awaddr<415744))) $fatal(1,"Capture validation write range");
                if(dut.state!=1 && dut.state!=2) $fatal(1,"Write to exported immutable pair");
            end
            if(wready) begin
                if(!writing || wstrb!==32'hFFFFFFFF) $fatal(1,"Invalid W stream");
                if(wbase>=32768 && wdata!==(dut.process_pass==2 ? tones[active_phase*19200+(wbase-32768)+wi]:golden[active_phase*19200+(wbase-32768)+wi])) $fatal(1,"Validation result mismatch");
                memory[wbase+wi]=wdata;if(wi==wlen) writing=0;wi=wi+1;
            end
            if(dut.engine_done) for(i=0;i<19200;i=i+1) begin frozen[i]=memory[i];frozen[32768+i]=memory[32768+i];end
            if(dut.export_start || dut.export_done) for(i=0;i<19200;i=i+1)
                if(memory[i]!==frozen[i] || memory[32768+i]!==frozen[32768+i]) $fatal(1,"Raw/result pair changed during UART transfer");
            if(arvalid && arready) begin
                rbase=araddr/8;ri=0;rlen=arlen;reading=1;
                if((arlen!=15 && arlen!=7) || araddr%64 || !(araddr<153600 || (araddr>=262144 && araddr<415744))) $fatal(1,"Capture validation read range");
            end
            if(rvalid) begin if(ri==rlen) reading=0;ri=ri+1;end
            if(failed) $fatal(1,"Validation pipeline fault=%h",fault);
        end
    end
    integer camera_frame=0,row,col;reg [15:0] pixel;
    initial forever begin
        wait(rst_n && ready);
        @(negedge cam_clk);vsync=1;href=0;repeat(6) @(negedge cam_clk);vsync=0;repeat(4) @(negedge cam_clk);
        for(row=0;row<480;row=row+1) begin
            for(col=0;col<640;col=col+1) begin
                pixel=source[(pairs_completed%3)*19200+(row*640+col)/16][((row*640+col)%16)*16+:16];
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
        wait(pairs_completed==3);if(bytes!=9*(614400+44)) $fatal(1,"UART byte count mismatch");
        $fclose(file_handle);
        $display("PASS native frozen Gamma capture: three dark/bright/neutral source transactions, nine complete CRC packets, two bypass warmup passes, enhanced pixels, immutable source and export banks, DDR/UART stalls.");$finish;
    end
    initial begin #2000000000;$fatal(1,"Pair export timeout state=%0d pairs=%0d",dut.state,pairs_completed);end
endmodule
