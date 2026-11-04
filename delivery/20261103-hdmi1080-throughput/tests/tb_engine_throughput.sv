`timescale 1ns/1ps
// Isolated processing engine with deterministic behavioral DDR pressure.
// Preloaded source; this bench does not model capture/display arbitration.
module tb_engine_throughput;
    `include "engine_config.vh"
    localparam N=W*H, BEATS=N/16, BASE=28'h0200000;
    reg clk=0; always #4 clk=~clk;
    reg rst_n=0,frame_valid=0;
    wire frame_ready,done,failed; wire [7:0] fault;
    wire [27:0] araddr,awaddr,completed_base;
    wire [3:0] arlen,awlen; wire arvalid,awvalid;
    reg arready=0,awready=0,rvalid=0,rlast=0,wready=0,wlast=0;
    reg [255:0] rdata=0; wire [255:0] wdata; wire [31:0] wstrb;
    wire [31:0] completed_id,completed_crc,hits,misses,queries,gamma_frames;
    wire [1:0] gamma_mode;
    pipeline_gamma_frame_engine_1080_geometry_bypass #(.WIDTH(W),.HEIGHT(H),.MAX_RADIUS_Q22(RADIUS)) dut(
        .clk(clk),.rst_n(rst_n),.frame_valid(frame_valid),.frame_ready(frame_ready),
        .gamma_enable(1'b0),.correction_enable(1'b1),.gamma_mode(gamma_mode),.gamma_frames(gamma_frames),
        .source_base(28'd0),.output_base(BASE),.frame_id(32'd101),
        .cfg_out_cx(CX),.cfg_out_cy(CY),.cfg_src_cx(CX),.cfg_src_cy(CY),
        .cfg_src_fx(FX),.cfg_src_fy(FY),.cfg_inv_fx(IFX),.cfg_inv_fy(IFY),
        .cfg_k1(K1),.cfg_k2(K2),.cfg_k3(32'sd0),.cfg_p1(32'sd0),.cfg_p2(32'sd0),
        .cfg_rot_cx(CX),.cfg_rot_cy(CY),.cfg_rot_cos(32'sd1073741824),.cfg_rot_sin(32'sd0),
        .araddr(araddr),.arlen(arlen),.arvalid(arvalid),.arready(arready),
        .rdata(rdata),.rvalid(rvalid),.rlast(rlast),.rid(4'd0),
        .awaddr(awaddr),.awlen(awlen),.awvalid(awvalid),.awready(awready),
        .wdata(wdata),.wstrb(wstrb),.wready(wready),.wlast(wlast),
        .done(done),.failed(failed),.fault(fault),.completed_base(completed_base),
        .completed_id(completed_id),.completed_crc(completed_crc),.hits(hits),.misses(misses),.completed_queries(queries));
    reg [15:0] expected[0:N-1]; reg expected_mask[0:N-1];
    integer ticks=0,start_tick=0,finish_tick=0,rleft=0,rindex=0,wleft=0,windex=0;
    integer checked=0,mask_checked=0,reads=0,writes=0,coordinate_stall=0,tone_stall=0,scatter_cycles=0;
    integer ar_stall=0,aw_stall=0,w_stall=0,summary,output_file;
    reg active=0,heldar=0,heldaw=0,heldw=0;
    reg [27:0] saved_ar,saved_aw;reg [255:0] saved_w;
    function automatic [15:0] source_pixel(input integer index);
        source_pixel=((index*73)^(index>>3)^((index/W)*997))&65535;
    endfunction
    function automatic [255:0] source_word(input integer word_index);
        integer lane;begin
            for(lane=0;lane<16;lane=lane+1)source_word[lane*16+:16]=source_pixel(word_index*16+lane);
        end
    endfunction
    function automatic [255:0] expected_word(input integer word_index);
        integer lane;begin
            for(lane=0;lane<16;lane=lane+1)expected_word[lane*16+:16]=expected[word_index*16+lane];
        end
    endfunction
    always @(negedge clk)begin
        ticks=ticks+1;
        if(ticks>30000000)$fatal(1,"engine cycle timeout");
        arready=rst_n && rleft==0 && (!PRESSURE || ticks%7>=2);
        awready=rst_n && wleft==0 && (!PRESSURE || ticks%9>=3);
        rvalid=rst_n && rleft!=0 && (!PRESSURE || ticks%5!=0);
        rlast=rleft==1;
        if(rvalid)rdata=source_word(rindex);
        wready=rst_n && wleft!=0 && (!PRESSURE || ticks%6!=0);
        wlast=wleft==1;
    end
    always @(posedge clk)begin
        if(!rst_n)begin rleft<=0;wleft<=0;heldar<=0;heldaw<=0;heldw<=0;end
        else begin
            if(failed)$fatal(1,"engine failed fault=%h",fault);
            if(heldar && (!arvalid || araddr!==saved_ar))$fatal(1,"unstable AR");
            if(heldaw && (!awvalid || awaddr!==saved_aw))$fatal(1,"unstable AW");
            if(heldw && wdata!==saved_w)$fatal(1,"unstable W under pressure");
            heldar<=arvalid&&!arready;saved_ar<=araddr;
            heldaw<=awvalid&&!awready;saved_aw<=awaddr;
            heldw<=wleft!=0&&!wready;saved_w<=wdata;
            if(frame_valid&&frame_ready)begin start_tick=ticks;active<=1;end
            if(active)begin
                if(dut.coordinate_valid&&!dut.coordinate_ready)coordinate_stall=coordinate_stall+1;
                if(dut.tone_valid&&!dut.tone_ready)tone_stall=tone_stall+1;
                if(dut.core.sampler.cache.inner.state==4)scatter_cycles=scatter_cycles+1;
                if(arvalid&&!arready)ar_stall=ar_stall+1;
                if(awvalid&&!awready)aw_stall=aw_stall+1;
                if(wleft!=0&&!wready)w_stall=w_stall+1;
                if(dut.result_valid&&dut.result_ready)begin
                    if(dut.result_tag>=N || dut.result_masked!==expected_mask[dut.result_tag])$fatal(1,"independent mask mismatch tag=%d",dut.result_tag);
                    mask_checked=mask_checked+1;
                end
            end
            if(arvalid&&arready)begin
                if(rleft!=0 || arlen!=7 || araddr%64 || araddr+64>N/2)$fatal(1,"invalid source burst");
                rleft<=8;rindex<=araddr>>3;reads=reads+1;
            end
            if(rvalid)begin rleft<=rleft-1;rindex<=rindex+1;end
            if(awvalid&&awready)begin
                if(wleft!=0 || awlen!=15 || awaddr!=BASE+writes*128)$fatal(1,"invalid result burst");
                wleft<=16;windex<=(awaddr-BASE)>>3;writes=writes+1;
            end
            if(wready)begin
                if(windex>=BEATS || wstrb!==32'hffffffff || wdata!==expected_word(windex))
                    $fatal(1,"independent golden mismatch beat=%0d actual=%h expected=%h",windex,wdata,expected_word(windex));
                $fdisplay(output_file,"%064x",wdata);
                wleft<=wleft-1;windex<=windex+1;checked=checked+1;
            end
            if(done)begin
                active<=0;finish_tick=ticks;
                if(checked!=BEATS || mask_checked!=N || queries!=N || rleft!=0 || wleft!=0 || awvalid || arvalid ||
                    completed_base!=BASE || completed_id!=101 || completed_crc!==EXPECTED_CRC || gamma_mode!=0)
                    $fatal(1,"incomplete/drain/CRC mismatch checked=%0d queries=%0d crc=%h expected=%h",checked,queries,completed_crc,EXPECTED_CRC);
                if(scatter_cycles!=SCATTER_PER_FILL*misses || reads!=misses)$fatal(1,"fill/scatter mismatch");
                summary=$fopen("engine-summary.json","w");
                $fdisplay(summary,"{\"passed\":true,\"width\":%0d,\"height\":%0d,\"pixels\":%0d,\"cycles\":%0d,\"hits\":%0d,\"fills\":%0d,\"coordinate_stall\":%0d,\"writer_input_stall\":%0d,\"scatter_cycles\":%0d,\"ar_stall\":%0d,\"aw_stall\":%0d,\"w_stall\":%0d,\"crc32\":\"%08x\",\"pressure\":%0d,\"hardware_verified\":false}",W,H,N,finish_tick-start_tick,hits,misses,coordinate_stall,tone_stall,scatter_cycles,ar_stall,aw_stall,w_stall,completed_crc,PRESSURE);
                $fclose(summary);$fclose(output_file);
                $display("PASS ENGINE_THROUGHPUT pixels=%0d cycles=%0d crc=%08x",N,finish_tick-start_tick,completed_crc);
                $finish;
            end
        end
    end
    initial begin
        $readmemh("expected.mem",expected);$readmemh("masks.mem",expected_mask);
        output_file=$fopen("output.mem","w");
        repeat(12)@(negedge clk);rst_n=1;
        wait(frame_ready);@(negedge clk);frame_valid=1;
        do @(posedge clk);while(!frame_ready);
        @(negedge clk);frame_valid=0;
    end
endmodule
