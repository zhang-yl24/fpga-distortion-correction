`timescale 1ps/1ps
// Real DVP capture + copied DMA/System control + production bank/mapper/output.
// Only DDR PHY/UI is modeled. Sensor bytes come from independent CPU fixtures.
module tb_camera_vga_system;
    localparam W=32,H=16,N=W*H,FB=N/16,OW=64,OH=32;
    localparam HT=128,VT=48,HS=4,VS=2,X0=16,Y0=4;
    localparam WX=X0+(OW-W)/2,WY=Y0+(OH-H)/2;
    // Force a real asynchronous reset edge at time 0. An initialized 0 alone
    // does not trigger Verilog always @(negedge reset_n) blocks in xsim.
    reg reset_n=1,cam_clk=0,pix_clk=0;
    initial begin #1 reset_n=0; end
    always #16000 cam_clk=~cam_clk;
    integer clock_phase=0,clock_delay;
    initial begin #1733;forever begin
        clock_phase=clock_phase+2000000;clock_delay=clock_phase/297;
        clock_phase=clock_phase%297;#(clock_delay)pix_clk=~pix_clk;
    end end
    wire core_clk;
    reg cam_vsync=1,cam_href=1;reg[7:0]cam_data=0;
    reg capture_admit=0,scan_enable=0,send_frames=1;
    wire[27:0]awaddr,araddr;wire[3:0]awlen,arlen,rid;
    wire awvalid,awready,wready,wlast,arvalid,arready,rvalid,rlast;
    wire[255:0]wdata,rdata;wire[31:0]wstrb;
    wire hs,vs,de,failed;wire[7:0]fault;wire[23:0]rgb;
    wire[31:0]captured,processed,presented,underflows,mismatches;
    camera_vga_video_system #(.WIDTH(W),.HEIGHT(H),.OUTPUT_WIDTH(OW),.OUTPUT_HEIGHT(OH),
        .HT(HT),.VT(VT),.HS(HS),.VS(VS),.X0(X0),.Y0(Y0)) dut(
        .core_clk(core_clk),.cam_clk(cam_clk),.pix_out_clk(pix_clk),.rst_n(reset_n),
        .capture_admit(capture_admit),.scan_enable(scan_enable),.external_fault(1'b0),.external_fault_code(8'd0),
        .cam_vsync(cam_vsync),.cam_href(cam_href),.cam_data(cam_data),
        .cfg_out_cx(24'sd3968),.cfg_out_cy(24'sd1920),.cfg_src_cx(24'sd3968),.cfg_src_cy(24'sd1920),
        .cfg_src_fx(24'sd4096),.cfg_src_fy(24'sd3686),.cfg_inv_fx(32'sd67108864),.cfg_inv_fy(32'sd74573496),
        .cfg_k1(32'sh51eb8),.cfg_k2(-32'shf5c3),.cfg_k3(32'sh20c5),.cfg_p1(32'sh1062),.cfg_p2(-32'shb78),
        .awaddr(awaddr),.awlen(awlen),.awvalid(awvalid),.awready(awready),
        .wdata(wdata),.wstrb(wstrb),.wready(wready),.wlast(wlast),
        .araddr(araddr),.arlen(arlen),.arvalid(arvalid),.arready(arready),
        .rdata(rdata),.rid(rid),.rvalid(rvalid),.rlast(rlast),
        .pix_hs(hs),.pix_vs(vs),.pix_de(de),.pix_rgb(rgb),.failed(failed),.fault(fault),
        .captured_frames(captured),.processed_frames(processed),.presented_frames(presented),
        .underflows(underflows),.mismatches(mismatches));
    // The shared DDR model gates core_clk when its resetn is low, while the
    // production write/read arbiters use synchronous reset. Keep the model
    // clock running so those system-local synchronous resets receive edges;
    // the DUT reset_n remains the transaction reset under test.
    ddr3_test memory(.resetn(1'b1),.ref_clk(1'b0),.core_clk(core_clk),
        .axi_awaddr(awaddr),.axi_awlen(awlen),.axi_awvalid(awvalid),.axi_awready(awready),
        .axi_wdata(wdata),.axi_wstrb(wstrb),.axi_wready(wready),.axi_wusero_last(wlast),
        .axi_araddr(araddr),.axi_arlen(arlen),.axi_arvalid(arvalid),.axi_arready(arready),
        .axi_rdata(rdata),.axi_rid(rid),.axi_rvalid(rvalid),.axi_rlast(rlast));
    reg[255:0]source_words[0:FB-1],result_words[0:FB-1];
    reg[15:0]golden[0:N-1];
    `include "oracle.vh"
    function automatic[15:0] source_pixel(input integer index);
        source_pixel=source_words[index/16][(index%16)*16+:16];
    endfunction
    function automatic[23:0] expand565(input[15:0]v);
        expand565={{v[15:11],v[15:13]},{v[10:5],v[10:9]},{v[4:0],v[4:2]}};
    endfunction
    function automatic[31:0] crc_byte(input[31:0]c,input[7:0]v);
        reg[31:0]a;integer n;
        begin a=c^v;for(n=0;n<8;n=n+1)a=a[0]?(a>>1)^32'hedb88320:a>>1;crc_byte=a;end
    endfunction
    task byte_tick(input bit v,input bit h,input[7:0]d);
        begin @(negedge cam_clk);cam_vsync=v;cam_href=h;cam_data=d;end
    endtask
    integer camera_frames=0;
    task sensor_frame(input bit malformed);
        integer x,y,wait_ticks;reg[15:0]pixel;
        begin : frame_body
            // DVP has no backpressure. Hold blanking until the System's
            // reservation has crossed into the camera domain, then begin at
            // the next frame boundary rather than emitting ungranted frames.
            // A previously active capture publishes its completion on VSYNC;
            // close that frame before waiting for the next bank reservation.
            if(dut.input_link.input_dma.active &&
               !dut.input_link.input_dma.capture.pending_grant)begin
                repeat(2)byte_tick(0,1,0);repeat(2)byte_tick(1,1,0);
            end
            wait_ticks=0;
            while((dut.input_link.input_dma.capture.pending_grant !== 1'b1) &&
                  (dut.input_link.input_dma.grant_valid !== 1'b1) &&
                  send_frames && wait_ticks<100000)begin
                byte_tick(1,1,0);wait_ticks=wait_ticks+1;
            end
            if(!send_frames)disable frame_body;
            if((dut.input_link.input_dma.capture.pending_grant !== 1'b1) &&
               (dut.input_link.input_dma.grant_valid !== 1'b1))
                $fatal(1,"camera grant timeout: enable=%b failed=%b active=%b source_valid=%b sr=%b free=%b grant_valid=%b grant_ready=%b pending=%b",dut.input_link.enable,dut.input_link.input_dma.failed,dut.input_link.input_dma.active,dut.input_link.input_dma.source_valid,dut.input_link.input_dma.sr,dut.input_link.input_dma.free_bank,dut.input_link.input_dma.grant_valid,dut.input_link.input_dma.grant_ready,dut.input_link.input_dma.capture.pending_grant);
            // Raw historical CAM2 polarity: VS and HREF are active LOW.
            repeat(4)byte_tick(0,1,0);repeat(16)byte_tick(1,1,0);
            for(y=0;y<H;y=y+1)begin
                for(x=0;x<W;x=x+1)begin
                    pixel=source_pixel(y*W+x);
                    // Historical sensor mode sends the LOW byte first.
                    byte_tick(1,0,pixel[7:0]);
                    if(!(malformed&&y==0&&x==W-1))byte_tick(1,0,pixel[15:8]);
                end
                repeat(8)byte_tick(1,1,0);
            end
            repeat(32)byte_tick(1,1,0);camera_frames=camera_frames+1;
        end
    endtask
    integer commits=0,releases=0,source_reuses=0,result_reuses=0;
    integer source_epoch[0:1],result_epoch[0:1],source_writes[0:63],result_writes[0:63],scans[0:63];
    reg released[0:63];integer f,bank,off,i,events,scan_file,summary_file;
    reg previous_commit=0,previous_release=0;
    always @(posedge core_clk)if(reset_n)begin
        if(failed)$fatal(1,"camera System fault %h",fault);
        if(dut.input_link.input_dma.grant_valid&&dut.input_link.input_dma.grant_ready)begin
            f=dut.input_link.input_dma.next_id;bank=dut.input_link.input_dma.grant_bank;
            if(f<1||f>63||bank>1||dut.capture_reserved[bank] !== 1'b0)
                $fatal(1,"bad source reservation f=%0d bank=%0d next=%0d reserved=%b",f,bank,dut.input_link.input_dma.next_id,dut.capture_reserved);
            if(source_epoch[bank]>1&&!released[source_epoch[bank]])$fatal(1,"source reused before release");
            if(source_epoch[bank]>0)source_reuses=source_reuses+1;source_epoch[bank]=f;
        end
        if(memory.wready)begin
            bank=memory.wbank;off=memory.windex-bank*FB;
            if(wdata!==(bank<2?source_words[off]:result_words[off]))$fatal(1,"actual DDR source/result differs bank=%0d off=%0d",bank,off);
            if(bank<2)source_writes[source_epoch[bank]]=source_writes[source_epoch[bank]]+1;
            else begin
                f=dut.bank_core.accepted_id;
                if(off==0)begin
                    if(result_epoch[bank-2]>0)result_reuses=result_reuses+1;
                    result_epoch[bank-2]=f;
                end
                result_writes[f]=result_writes[f]+1;
            end
        end
        #1;
        if(dut.source_commit&&!previous_commit)begin
            f=dut.source_commit_id;
            if(f==1||f>63||dut.source_pixels!=N||dut.source_crc!==SOURCE_CRC||source_writes[f]!=FB)
                $fatal(1,"bad/partial source committed, or valid bytes/CRC differ id=%0d",f);
            commits=commits+1;$fdisplay(events,"commit,%0d,%0t,%h",f,$time,dut.source_crc);
        end
        if(dut.source_release&&!previous_release)begin
            f=dut.source_release_id;
            if(released[f]||result_writes[f]!=FB)$fatal(1,"release before result DDR completion");
            releases=releases+1;released[f]=1;$fdisplay(events,"release,%0d,%0t,%h",f,$time,dut.bank_core.engine_crc);
        end
        previous_commit=dut.source_commit;previous_release=dut.source_release;
    end
    integer raster_tick=0,raster_x,raster_y,de_pixels=0,border_pixels=0,complete_rasters=0;
    integer unique_scans=0,repeat_scans=0,scan_id=0,scan_pixel=0,total_pixels=0;
    reg raster_seen=0,previous_vs=0;reg[31:0]scan_crc=32'hffffffff;reg[15:0]observed;
    always @(posedge pix_clk)if(reset_n)begin
        #1;
        if(vs&&!previous_vs)begin
            if(raster_seen)begin
                if(raster_tick!=HT*VT||de_pixels!=OW*OH)$fatal(1,"output DE area shrank to camera size");
                complete_rasters=complete_rasters+1;
            end
            raster_tick=0;de_pixels=0;raster_seen=1;
        end
        if(raster_seen)begin
            raster_x=raster_tick%HT;raster_y=raster_tick/HT;
            if(hs!==(raster_x<HS)||vs!==(raster_y<VS))$fatal(1,"output sync raster differs");
            if(de!==(raster_x>=X0&&raster_x<X0+OW&&raster_y>=Y0&&raster_y<Y0+OH))$fatal(1,"DE is not full output active window");
            if(de)begin
                de_pixels=de_pixels+1;
                if(raster_x<WX||raster_x>=WX+W||raster_y<WY||raster_y>=WY+H)begin
                    if(rgb!==0||dut.pix_pixel_valid)$fatal(1,"camera window border not black");
                    border_pixels=border_pixels+1;
                end
            end
            raster_tick=raster_tick+1;
        end
        previous_vs=vs;
        if(dut.pix_frame_start)begin scan_id=dut.pix_frame_id;scan_pixel=0;scan_crc=32'hffffffff;end
        if(dut.pix_pixel_valid)begin
            observed={rgb[23:19],rgb[15:10],rgb[7:3]};
            if(!de||scan_id<2||scan_id>63||rgb!==expand565(golden[scan_pixel]))$fatal(1,"actual processed RGB/position differs");
            if(raster_x!=WX+scan_pixel%W||raster_y!=WY+scan_pixel/W)$fatal(1,"camera picture not centered");
            scan_crc=crc_byte(crc_byte(scan_crc,observed[7:0]),observed[15:8]);
            $fdisplay(scan_file,"%0d,%0d,%04x",scan_id,scan_pixel,observed);
            scan_pixel=scan_pixel+1;total_pixels=total_pixels+1;
            if(dut.pix_frame_last)begin
                if(scan_pixel!=N||~scan_crc!==RESULT_CRC)$fatal(1,"scan count/CRC differs");
                if(scans[scan_id]==0)unique_scans=unique_scans+1;else repeat_scans=repeat_scans+1;
                scans[scan_id]=scans[scan_id]+1;
            end
        end else if(rgb!==0)$fatal(1,"invalid scan pixel not black");
    end
    initial begin #(64'd20000000000);$fatal(1,"camera integration 20ms deadline");end
    initial begin
        $readmemh("source-beats.mem",source_words);$readmemh("result-beats.mem",result_words);$readmemh("expected.mem",golden);
        events=$fopen("events.csv","w");scan_file=$fopen("scanned-pixels.csv","w");
        $fdisplay(events,"event,id,time_ps,crc");$fdisplay(scan_file,"frame_id,pixel,rgb565");
        for(i=0;i<2;i=i+1)begin source_epoch[i]=0;result_epoch[i]=0;end
        for(i=0;i<64;i=i+1)begin source_writes[i]=0;result_writes[i]=0;released[i]=0;scans[i]=0;end
        repeat(12)@(negedge cam_clk);reset_n=1;capture_admit=1;scan_enable=1;
        repeat(32)@(negedge cam_clk);
        fork
            begin sensor_frame(1);while(send_frames)sensor_frame(0);end
            begin
                wait(unique_scans>=4&&source_reuses>=1&&result_reuses>=1);
                // Test-only stop new reservation while allowing terminal VS.
                force dut.input_link.input_dma.grant_valid=0;
                wait(!dut.input_link.input_dma.active&&!dut.input_link.input_dma.source_valid&&
                    !dut.input_link.input_dma.capture.done_valid&&dut.input_link.input_dma.capture.fifo_idle);
                repeat(30)@(negedge core_clk);capture_admit=0;send_frames=0;
                wait(dut.capture_reserved==0&&!dut.processing&&!dut.pending&&captured==processed&&presented==processed);
                // A free-running producer can publish a new frame at every
                // refresh. Verify repetition only after the input has drained.
                wait(repeat_scans>=1);
                wait(dut.output_video.y==VT-2&&dut.output_video.x==0);
                if(dut.lease_active||dut.response_busy||dut.awaiting_bank_grant||dut.display_req_valid)
                    $fatal(1,"display lease remained past active frame before directed stop");
                scan_enable=0;
                repeat(100)@(negedge core_clk);
                if(failed||underflows||mismatches||memory.wleft||memory.rleft||dut.fifo_used||dut.fifo_available)
                    $fatal(1,"normal camera pipeline did not drain");
                if(dut.input_link.dropped_frames!=1||commits!=releases||commits!=processed||complete_rasters<2||border_pixels==0)
                    $fatal(1,"camera drop/recovery/commit coverage incomplete");
                summary_file=$fopen("summary.json","w");
                $fdisplay(summary_file,"{\"passed\":true,\"malformed_frames_dropped\":1,\"frames_committed\":%0d,\"frames_processed\":%0d,\"unique_frames_scanned\":%0d,\"repeat_scans\":%0d,\"source_bank_reuses\":%0d,\"result_bank_reuses\":%0d,\"scanned_pixels\":%0d,\"full_output_de_verified\":true,\"centered_picture_verified\":true,\"black_border_pixels\":%0d,\"directed_final_drain\":true}",commits,processed,unique_scans,repeat_scans,source_reuses,result_reuses,total_pixels,border_pixels);
                $fclose(summary_file);$fclose(events);$fclose(scan_file);
                $display("PASS camera VGA system: commits=%0d scans=%0d borders=%0d",commits,unique_scans,border_pixels);$finish;
            end
        join
    end
endmodule
