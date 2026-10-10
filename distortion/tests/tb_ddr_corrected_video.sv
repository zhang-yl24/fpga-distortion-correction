`timescale 1ns/1ps
module tb_ddr_corrected_video;
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
    wire [31:0] processed_frames,last_process_cycles,cache_hits,cache_misses,completed_queries,latest_result_checksum;
    reg signed [23:0] cfg_src_cx=3968;
    reg signed [31:0] cfg_k1=0;
    ddr_corrected_video #(.WIDTH(32),.HEIGHT(16),.BANK_STRIDE(512),
        .HT(80),.VT(40),.HS(4),.VS(2),.X0(6),.Y0(4),.AW(64),.AH(24)) dut(
        .cam_clk(cam_clk),.core_clk(core_clk),.pix_clk(pix_clk),.rst_n(rst_n),.ready(ready),
        .vsync(vsync),.href(href),.data(data),
        .cfg_out_cx(24'sd3968),.cfg_out_cy(24'sd1920),.cfg_src_cx(cfg_src_cx),.cfg_src_cy(24'sd1920),
        .cfg_src_fx(24'sd8192),.cfg_src_fy(24'sd8192),.cfg_inv_fx(32'sh02000000),.cfg_inv_fy(32'sh02000000),
        .cfg_k1(cfg_k1),.cfg_k2(32'sd0),.cfg_k3(32'sd0),.cfg_p1(32'sd0),.cfg_p2(32'sd0),
        .awaddr(awaddr),.araddr(araddr),.awlen(awlen),.arlen(arlen),.awvalid(awvalid),.arvalid(arvalid),
        .awready(awready),.arready(arready),.wdata(wdata),.wstrb(wstrb),.wready(wready),.wlast(wlast),
        .rdata(rdata),.rvalid(rvalid),.rlast(rlast),.rid(rid),.hs(hs),.vs(vs),.de(de),.r(r),.g(g),.b(b),
        .display_valid(display_valid),.output_frames(output_frames),.underflows(underflows),
        .pixel_mismatches(pixel_mismatches),.pixel_checksum(pixel_checksum),
        .captured_frames(captured_frames),.ownership_errors(ownership_errors),.read_frames(read_frames),
        .read_checksum(read_checksum),.latest_source_checksum(latest_source_checksum),.failed(failed),.fault(fault),
        .processed_frames(processed_frames),.last_process_cycles(last_process_cycles),
        .cache_hits(cache_hits),.cache_misses(cache_misses),.completed_queries(completed_queries),.latest_result_checksum(latest_result_checksum));
    reg [255:0] memory[0:191],source[0:95],golden[0:95],source_locked[0:31];
    reg [31:0] crcs[0:2];
    integer wbase=0,rbase=0,wi=0,ri=0,cycle=0,mode=0;
    reg writing=0,reading=0;
    integer active_phase=0,phase_mask=0,verified_pixels=0,committed_frames=0,i;
    reg [27:0] held_ar,held_aw;reg held_ar_valid=0,held_aw_valid=0;
    // Configure each upcoming transaction according to the actually captured
    // source (camera can run faster than processing). Then perturb parameters
    // during SCAN to confirm the engine accepted and locked its own copy.
    always @(negedge core_clk) begin
        if(rst_n && ((dut.source_pending && !dut.processing) || dut.engine_start)) begin
            if(memory[0]===source[0]) active_phase=0;
            else if(memory[0]===source[32]) active_phase=1;
            else if(memory[0]===source[64]) active_phase=2;
            else $fatal(1,"Unknown captured source");
            cfg_src_cx=active_phase==0 ? 3968:4096;
            cfg_k1=active_phase==0 ? 0:-524288;
        end else if(dut.processing && dut.engine.index>100) begin cfg_src_cx=0;cfg_k1=0;end
        cycle=cycle+1;
        awready=rst_n && ready && !writing && cycle%5!=0;
        arready=rst_n && ready && !reading && cycle%7!=0;
        wready=rst_n && ready && writing && cycle%3!=0;wlast=wready && wi==15;
        rvalid=rst_n && ready && reading && cycle%4!=0;rlast=rvalid && ri==15;
        rdata=reading ? memory[rbase+ri] : 0;rid=0;
        if(mode==1 && reading && rbase<32 && ri==3) rid=1;
    end
    always @(posedge core_clk) begin
        if(!rst_n) begin writing=0;reading=0;wi=0;ri=0;held_ar_valid=0;held_aw_valid=0;end
        else begin
            if(held_ar_valid && (!arvalid || araddr!==held_ar)) $fatal(1,"AR changed while stalled");
            if(held_aw_valid && (!awvalid || awaddr!==held_aw)) $fatal(1,"AW changed while stalled");
            held_ar_valid=arvalid && !arready;held_ar=araddr;
            held_aw_valid=awvalid && !awready;held_aw=awaddr;
            if(dut.engine_start) begin
                for(i=0;i<32;i=i+1) source_locked[i]=memory[i];
            end
            if(awvalid && awready) begin
                wbase=awaddr/8;wi=0;writing=1;
                if(awlen!=15 || awaddr%128 || !(awaddr<256 || (awaddr>=512 && awaddr<768) || (awaddr>=1024 && awaddr<1280))) $fatal(1,"Write outside three banks");
                if((wbase<32 && dut.processing) || (wbase>=64 && !dut.processing)) $fatal(1,"Wrong source/result write owner");
            end
            if(wready) begin
                if(!writing || wstrb!==32'hFFFFFFFF) $fatal(1,"Invalid W stream");
                if(wbase>=64) begin
                    if(wdata!==golden[active_phase*32+(wbase%64)+wi]) $fatal(1,"Corrected beat differs from independent integer model phase=%0d beat=%0d actual=%h expected=%h source=%h",active_phase,(wbase%64)+wi,wdata,golden[active_phase*32+(wbase%64)+wi],memory[0]);
                    verified_pixels=verified_pixels+16;
                end
                memory[wbase+wi]=wdata;
                if(wi==15) writing=0;
                wi=wi+1;
            end
            if(arvalid && arready) begin
                rbase=araddr/8;ri=0;reading=1;
                if(arlen!=15 || araddr%128 || !(araddr<256 || (araddr>=512 && araddr<768) || (araddr>=1024 && araddr<1280))) $fatal(1,"Read outside three banks");
            end
            if(rvalid) begin if(ri==15) reading=0;ri=ri+1;end
            if(writing && reading && wbase/64==rbase/64) $fatal(1,"Read/write bank collision");
            if(dut.engine_done && !failed) begin
                if(dut.engine_crc!==crcs[active_phase]) $fatal(1,"Publication CRC differs from Python zlib");
                for(i=0;i<32;i=i+1) if(memory[i]!==source_locked[i]) $fatal(1,"Source overwritten during remap");
                phase_mask=phase_mask|(1<<active_phase);committed_frames=committed_frames+1;
            end
            if(mode==0 && (failed || underflows || pixel_mismatches || ownership_errors))
                $fatal(1,"Corrected video fault=%h uf=%0d mf=%0d ow=%0d",fault,underflows,pixel_mismatches,ownership_errors);
        end
    end
    integer camera_frame=0,row,col;reg [15:0] pixel;
    initial forever begin
        wait(rst_n && ready);
        @(negedge cam_clk);vsync=1;href=0;
        repeat(6) @(negedge cam_clk);vsync=0;
        repeat(4) @(negedge cam_clk);
        for(row=0;row<16;row=row+1) begin
            for(col=0;col<32;col=col+1) begin
                pixel=source[(camera_frame%3)*32+(row*32+col)/16][((row*32+col)%16)*16+:16];
                href=1;data=pixel[7:0];@(negedge cam_clk);data=pixel[15:8];@(negedge cam_clk);
            end
            href=0;repeat(4) @(negedge cam_clk);
        end
        camera_frame=camera_frame+1;
    end
    integer px,py,word_index,lane,pixels_seen=0;reg [15:0] expected_pixel;reg [23:0] expected_rgb;
    always @(posedge pix_clk) begin
        if(rst_n && dut.output_video.consume) begin
            px=dut.output_video.x-22;py=dut.output_video.y-8;
            word_index=(dut.front_bank ? 128:64)+(py*32+px)/16;lane=(py*32+px)%16;
            expected_pixel=memory[word_index][lane*16+:16];
            expected_rgb={expected_pixel[15:11],expected_pixel[15:13],expected_pixel[10:5],expected_pixel[10:9],expected_pixel[4:0],expected_pixel[4:2]};
            #1;if({r,g,b}!==expected_rgb || !de) $fatal(1,"Corrected HDMI output mismatch");
            pixels_seen=pixels_seen+1;
        end
    end
    task reset_system;
        begin rst_n=0;ready=0;repeat(12) @(negedge core_clk);rst_n=1;repeat(12) @(negedge core_clk);ready=1;end
    endtask
    initial begin
        $readmemh("source.mem",source);$readmemh("result.mem",golden);$readmemh("crcs.mem",crcs);
        reset_system();
        // output_frames advances at a frame boundary, before that frame's last
        // displayed pixel. Faster remapping must still wait for actual pixel
        // coverage; a refresh count alone does not prove twelve full images.
        wait(phase_mask==7 && processed_frames>=6 && output_frames>=12 && verified_pixels>=6*512 && pixels_seen>=12*512);
        if(!display_valid || !cache_hits || !cache_misses || !last_process_cycles) $fatal(1,"Missing end-to-end coverage display=%0d pixels=%0d hits=%0d misses=%0d cycles=%0d",display_valid,pixels_seen,cache_hits,cache_misses,last_process_cycles);
        $display("INFO: identity/nonlinear changing source frames, three-bank ownership and HDMI passed");
        mode=1;reset_system();wait(failed);
        if(processed_frames || display_valid || dut.pending || dut.front_valid) $fatal(1,"Malformed source burst published a partial frame");
        $display("INFO: malformed source response quarantined without publication");
        mode=0;reset_system();wait(dut.processing && dut.engine.index>180);reset_system();
        wait(processed_frames>=3 && output_frames>=6);
        $display("PASS corrected DDR video: independent camera/core/pixel clocks, identity and nonlinear Python integer-model frames, changing repeated source bank, immutable source, alternating result/front banks, complete CRC publication, every HDMI pixel checked, burst stalls, malformed response quarantine and mid-processing reset recovery.");
        $finish;
    end
    initial begin #20000000;$fatal(1,"Corrected video test timeout phase_mask=%0d processed=%0d output=%0d",phase_mask,processed_frames,output_frames);end
endmodule
