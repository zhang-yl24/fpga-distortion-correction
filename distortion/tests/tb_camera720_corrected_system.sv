`timescale 1ps/1ps
// Full 720p DVP -> actual camera_vga_video_system -> actual 1080p30 scan.
// Independent source and corrected reference streams; config.vh is test input.
// Synthetic coefficients are test-only and never constitute lens acceptance.
// Only camera byte stimulus and the external DDR UI are modeled.
module tb_camera720_corrected_system;
    localparam W=1280,H=720,N=W*H,FB=N/16,FU=N/2,STRIDE=1048576,FRAMES=2;
    localparam OW=1920,OH=1080,HT=2200,VT=1125,HS=44,VS=5,X0=192,Y0=41;
    localparam WX=X0+(OW-W)/2,WY=Y0+(OH-H)/2,LINE_TICKS=1892*2;
    `include "config.vh"
    reg reset_n=1,core_clk=0,cam_clk=0,pix_clk=0;
    initial begin #1;reset_n=0;end
    always #4000 core_clk=~core_clk;
    integer cam_phase=0,cam_delay,pix_phase=0,pix_delay;
    initial begin #1733;forever begin
        cam_phase=cam_phase+1000000;cam_delay=cam_phase/96;cam_phase=cam_phase%96;
        #(cam_delay)cam_clk=~cam_clk;
    end end
    initial begin #1201;forever begin
        pix_phase=pix_phase+2000000;pix_delay=pix_phase/297;pix_phase=pix_phase%297;
        #(pix_delay)pix_clk=~pix_clk;
    end end
    reg cam_vsync=1,cam_href=1;reg[7:0]cam_data=0;
    reg capture_admit=0,scan_enable=0;
    wire[27:0]awaddr,araddr;wire[3:0]awlen,arlen;
    wire awvalid,arvalid;wire[255:0]wdata;wire[31:0]wstrb;
    reg awready=0,wready=0,arready=0,rvalid=0,rlast=0;reg[255:0]rdata=0;
    wire hs,vs,de,failed;wire[7:0]fault;wire[23:0]rgb;
    wire[31:0]captured,processed,presented,underflows,mismatches;
    integer wleft=0,windex=0,wbank=0,rleft=0,rindex=0,rbank=0,ticks=0;
    wire wlast=wleft==1;
    camera_vga_video_system #(.WIDTH(W),.HEIGHT(H),.BANK_STRIDE(STRIDE),
        .MAX_RADIUS_Q22(C720_RADIUS_Q22),.OUTPUT_WIDTH(OW),.OUTPUT_HEIGHT(OH),
        .HT(HT),.VT(VT),.HS(HS),.VS(VS),.X0(X0),.Y0(Y0),
        .VSYNC_ACTIVE_HIGH(0),.HREF_ACTIVE_HIGH(0),.HIGH_BYTE_FIRST(0)) dut(
        .core_clk(core_clk),.cam_clk(cam_clk),.pix_out_clk(pix_clk),.rst_n(reset_n),
        .capture_admit(capture_admit),.scan_enable(scan_enable),.external_fault(1'b0),.external_fault_code(8'd0),
        .cam_vsync(cam_vsync),.cam_href(cam_href),.cam_data(cam_data),
        .cfg_out_cx(C720_OUT_CX),.cfg_out_cy(C720_OUT_CY),.cfg_src_cx(C720_SRC_CX),.cfg_src_cy(C720_SRC_CY),
        .cfg_src_fx(C720_SRC_FX),.cfg_src_fy(C720_SRC_FY),.cfg_inv_fx(C720_INV_FX),.cfg_inv_fy(C720_INV_FY),
        .cfg_k1(C720_K1),.cfg_k2(C720_K2),.cfg_k3(C720_K3),.cfg_p1(C720_P1),.cfg_p2(C720_P2),
        .awaddr(awaddr),.awlen(awlen),.awvalid(awvalid),.awready(awready),
        .wdata(wdata),.wstrb(wstrb),.wready(wready),.wlast(wlast),
        .araddr(araddr),.arlen(arlen),.arvalid(arvalid),.arready(arready),
        .rdata(rdata),.rid(4'd0),.rvalid(rvalid),.rlast(rlast),
        .pix_hs(hs),.pix_vs(vs),.pix_de(de),.pix_rgb(rgb),.failed(failed),.fault(fault),
        .captured_frames(captured),.processed_frames(processed),.presented_frames(presented),
        .underflows(underflows),.mismatches(mismatches));

    reg[255:0]memory[0:4*FB-1],source_words[0:FRAMES*FB-1],corrected_words[0:FRAMES*FB-1];
    reg[15:0]source_pixels[0:FRAMES*N-1],golden[0:FRAMES*N-1];
    reg[31:0]source_crc_ref[0:FRAMES-1],corrected_crc_ref[0:FRAMES-1];
    integer source_epoch[0:1],result_epoch[0:1];
    integer source_writes[0:FRAMES],result_writes[0:FRAMES],scans[0:FRAMES];
    reg released[0:FRAMES];
    integer source_reuses=0,result_reuses=0,commits=0,releases=0,source_beats=0,result_beats=0,read_beats=0;
    integer aw_stalls=0,w_stalls=0,ar_stalls=0,read_contention=0,write_contention=0;
    integer capture_process_overlap=0,process_scan_overlap=0,capture_scan_overlap=0;
    integer capture_fifo_peak=0,display_fifo_peak=0,final_source_bursts=0,final_result_bursts=0;
    integer bank,off,id,i,event_file,pixel_file,summary_file;
    reg held_aw=0,held_ar=0,held_w=0;reg[27:0]saved_aw=0,saved_ar=0;
    reg[3:0]saved_awlen=0,saved_arlen=0;reg[255:0]saved_w=0;
    always @(negedge core_clk)begin
        ticks=ticks+1;
        awready=reset_n&&wleft==0&&ticks%19>=4;
        wready=reset_n&&wleft>0&&ticks%7!=0;
        arready=reset_n&&rleft==0&&ticks%13>=3;
        rvalid=reset_n&&rleft>0&&ticks%6!=0;rlast=rleft==1;
        if(rvalid)rdata=memory[rindex];
    end
    always @(posedge core_clk)if(reset_n)begin
        if(failed)$fatal(1,"720 system fault %02x at cycle %0d",fault,ticks);
        if(held_aw&&(!awvalid||awaddr!==saved_aw||awlen!==saved_awlen))$fatal(1,"stalled AW withdrawn");
        if(held_ar&&(!arvalid||araddr!==saved_ar||arlen!==saved_arlen))$fatal(1,"stalled AR withdrawn");
        if(held_w&&wdata!==saved_w)$fatal(1,"stalled W payload changed");
        held_aw<=awvalid&&!awready;saved_aw<=awaddr;saved_awlen<=awlen;
        held_ar<=arvalid&&!arready;saved_ar<=araddr;saved_arlen<=arlen;
        held_w<=wleft>0&&!wready;saved_w<=wdata;
        if(awvalid&&!awready)aw_stalls=aw_stalls+1;
        if(wleft>0&&!wready)w_stalls=w_stalls+1;
        if(arvalid&&!arready)ar_stalls=ar_stalls+1;
        if(dut.sample_valid&&dut.display_arvalid)read_contention=read_contention+1;
        if(dut.input_link.dma_awvalid&&dut.result_awvalid)write_contention=write_contention+1;
        if(dut.input_link.input_dma.active&&dut.processing)capture_process_overlap=capture_process_overlap+1;
        if(dut.processing&&dut.display_active)process_scan_overlap=process_scan_overlap+1;
        if(dut.input_link.input_dma.active&&dut.display_active)capture_scan_overlap=capture_scan_overlap+1;
        if(dut.fifo_used>display_fifo_peak)display_fifo_peak=dut.fifo_used;
        if(dut.input_link.input_dma.grant_valid&&dut.input_link.input_dma.grant_ready)begin
            id=dut.input_link.input_dma.next_id;bank=dut.input_link.input_dma.grant_bank;
            if(id<1||id>FRAMES||dut.capture_reserved[bank])$fatal(1,"source reservation out of range");
            if(source_epoch[bank]!=0)begin
                if(!released[source_epoch[bank]])$fatal(1,"source bank reused while owned");
                source_reuses=source_reuses+1;
            end
            source_epoch[bank]=id;
        end
        if(awvalid&&awready)begin
            bank=awaddr/STRIDE;off=awaddr%STRIDE;
            if(wleft||awlen!=15||bank>3||off%128||off+128>FU)$fatal(1,"720 AW extent/alignment");
            if(off==FU-128)begin
                if(off!=460672)$fatal(1,"720 UI address units differ");
                if(bank<2)final_source_bursts=final_source_bursts+1;else final_result_bursts=final_result_bursts+1;
            end
            wbank<=bank;wleft<=16;windex<=bank*FB+(off>>3);
        end
        if(wready)begin
            if(wleft==0||wstrb!==32'hffffffff)$fatal(1,"DDR W contract differs");
            off=windex-wbank*FB;
            id=wbank<2?source_epoch[wbank]:dut.bank_core.accepted_id;
            if(id<1||id>FRAMES)$fatal(1,"DDR frame epoch out of range");
            if(wbank<2 && wdata!==source_words[(id-1)*FB+off])
                $fatal(1,"DDR source differs bank=%0d id=%0d off=%0d",wbank,id,off);
            if(wbank>=2 && wdata!==corrected_words[(id-1)*FB+off])
                $fatal(1,"DDR corrected result differs bank=%0d id=%0d off=%0d",wbank,id,off);
            memory[windex]<=wdata;wleft<=wleft-1;windex<=windex+1;
            if(wbank<2)begin source_writes[id]=source_writes[id]+1;source_beats=source_beats+1;end
            else begin
                if(off==0)begin
                    if(result_epoch[wbank-2]!=0)result_reuses=result_reuses+1;
                    result_epoch[wbank-2]=id;
                end
                result_writes[id]=result_writes[id]+1;result_beats=result_beats+1;
            end
        end
        if(arvalid&&arready)begin
            bank=araddr/STRIDE;off=araddr%STRIDE;
            if(rleft||bank>3||off%8||off+(arlen+1)*8>FU)$fatal(1,"720 AR extent/alignment");
            rbank<=bank;rleft<=arlen+1;rindex<=bank*FB+(off>>3);
        end
        if(rvalid)begin rleft<=rleft-1;rindex<=rindex+1;read_beats=read_beats+1;end
        if(rleft&&wleft&&rbank==wbank)$fatal(1,"concurrent R/W on same bank");
        #1;
        if(dut.source_commit)begin
            id=dut.source_commit_id;
            if(id<1||id>FRAMES||source_writes[id]!=FB||dut.source_pixels!=N||dut.source_crc!==source_crc_ref[id-1])
                $fatal(1,"720 source completion count/CRC differs");
            commits=commits+1;
            $fdisplay(event_file,"commit,%0d,%0d,%08x",id,ticks,dut.source_crc);
            $display("SYSTEM720_COMMIT id=%0d crc=%08x tick=%0d",id,dut.source_crc,ticks);
        end
        if(dut.source_release)begin
            id=dut.source_release_id;
            if(id<1||id>FRAMES||released[id]||result_writes[id]!=FB||dut.bank_core.engine_crc!==corrected_crc_ref[id-1])
                $fatal(1,"720 source release before complete correct result");
            released[id]=1;releases=releases+1;
            $fdisplay(event_file,"release,%0d,%0d,%08x",id,ticks,dut.bank_core.engine_crc);
        end
        if(ticks%2000000==0)$display("SYSTEM720_PROGRESS tick=%0d captured=%0d processed=%0d presented=%0d",ticks,captured,processed,presented);
    end
    always @(posedge cam_clk)if(reset_n&&dut.input_link.input_dma.capture.capturing)
        if(dut.input_link.input_dma.capture.unused_used>capture_fifo_peak)
            capture_fifo_peak=dut.input_link.input_dma.capture.unused_used;

    function automatic[23:0] expand565(input[15:0]v);
        expand565={{v[15:11],v[15:13]},{v[10:5],v[10:9]},{v[4:0],v[4:2]}};
    endfunction
    integer raster_tick=0,raster_x,raster_y,de_pixels=0,border_pixels=0,complete_rasters=0;
    integer unique_scans=0,repeat_scans=0,scan_id=0,scan_pixel=0,total_pixels=0,done_checks=0;
    reg raster_seen=0,previous_vs=0,previous_done=0;reg[15:0]observed;
    always @(posedge pix_clk)if(reset_n)begin
        #1;
        if(vs&&!previous_vs)begin
            if(raster_seen)begin
                if(raster_tick!=HT*VT||de_pixels!=OW*OH)$fatal(1,"1080p30 raster/DE count differs");
                complete_rasters=complete_rasters+1;
            end
            raster_tick=0;de_pixels=0;raster_seen=1;
        end
        if(raster_seen)begin
            raster_x=raster_tick%HT;raster_y=raster_tick/HT;
            if(hs!==(raster_x<HS)||vs!==(raster_y<VS))$fatal(1,"1080p30 sync differs");
            if(de!==(raster_x>=X0&&raster_x<X0+OW&&raster_y>=Y0&&raster_y<Y0+OH))$fatal(1,"full DE differs");
            if(de)begin
                de_pixels=de_pixels+1;
                if(raster_x<WX||raster_x>=WX+W||raster_y<WY||raster_y>=WY+H)begin
                    if(rgb!==0||dut.pix_pixel_valid)$fatal(1,"720 centered black border differs");
                    border_pixels=border_pixels+1;
                end
            end
            raster_tick=raster_tick+1;
        end
        previous_vs=vs;
        if(dut.pix_frame_start)begin scan_id=dut.pix_frame_id;scan_pixel=0;end
        if(dut.pix_pixel_valid)begin
            observed={rgb[23:19],rgb[15:10],rgb[7:3]};
            if(!de||scan_id<1||scan_id>FRAMES||scan_pixel>=N||rgb!==expand565(golden[(scan_id-1)*N+scan_pixel]))
                $fatal(1,"720 actual RGB differs id=%0d pixel=%0d",scan_id,scan_pixel);
            if(raster_x!=WX+scan_pixel%W||raster_y!=WY+scan_pixel/W)$fatal(1,"720 image location differs");
            $fdisplay(pixel_file,"%0d %04x",scan_id,observed);
            scan_pixel=scan_pixel+1;total_pixels=total_pixels+1;
            if(dut.pix_frame_last)begin
                if(scan_pixel!=N)$fatal(1,"720 complete scan pixel count differs");
                if(scans[scan_id]==0)unique_scans=unique_scans+1;else repeat_scans=repeat_scans+1;
                scans[scan_id]=scans[scan_id]+1;
                $display("SYSTEM720_SCAN id=%0d pixels=%0d",scan_id,scan_pixel);
            end
        end else if(rgb!==0)$fatal(1,"invalid pixel is not black");
        if(dut.pix_done_toggle!=previous_done)begin
            if(!dut.pix_done_good||dut.pix_done_crc!==corrected_crc_ref[scan_id-1])$fatal(1,"720 scan CRC differs");
            done_checks=done_checks+1;previous_done=dut.pix_done_toggle;
        end
    end

    task byte_tick(input bit v,input bit h,input[7:0]d);
        begin @(negedge cam_clk);cam_vsync=v;cam_href=h;cam_data=d;end
    endtask
    task sensor_frame(input integer frame_id);
        integer x,y,wait_ticks;reg[15:0]pixel;reg[63:0]started;
        begin
            wait_ticks=0;
            while(!dut.input_link.input_dma.capture.pending_grant&&wait_ticks<1000000)begin
                byte_tick(1,1,0);wait_ticks=wait_ticks+1;
            end
            if(!dut.input_link.input_dma.capture.pending_grant||dut.input_link.input_dma.capture.pending_id!=frame_id)
                $fatal(1,"720 source reservation missing for frame %0d",frame_id);
            byte_tick(0,1,0);started=$time;repeat(3)byte_tick(0,1,0);
            repeat(4*LINE_TICKS-4)byte_tick(1,1,0);
            for(y=0;y<H;y=y+1)begin
                for(x=0;x<W;x=x+1)begin
                    pixel=source_pixels[(frame_id-1)*N+y*W+x];
                    byte_tick(1,0,pixel[7:0]);byte_tick(1,0,pixel[15:8]);
                end
                repeat(LINE_TICKS-2*W)byte_tick(1,1,0);
            end
            // Directed shutdown prevents an extra unconsumed reservation;
            // the accepted final frame and DDR/UI work remain untouched.
            if(frame_id==FRAMES)force dut.input_link.input_dma.grant_valid=0;
            repeat(16*LINE_TICKS)byte_tick(1,1,0);byte_tick(0,1,0);
            if($time-started<64'd58336666666||$time-started>64'd58336666668)
                $fatal(1,"720 line/frame blanking period differs");
            repeat(4)byte_tick(0,1,0);byte_tick(1,1,0);
        end
    endtask
    initial begin #(64'd450000000000);$fatal(1,"720 system 450ms simulation deadline");end
    initial begin
        $readmemh("source-beats.mem",source_words);$readmemh("corrected-beats.mem",corrected_words);
        $readmemh("source-pixels.mem",source_pixels);$readmemh("expected.mem",golden);
        $readmemh("source-crcs.mem",source_crc_ref);$readmemh("corrected-crcs.mem",corrected_crc_ref);
        for(i=0;i<2;i=i+1)begin source_epoch[i]=0;result_epoch[i]=0;end
        for(i=0;i<=FRAMES;i=i+1)begin source_writes[i]=0;result_writes[i]=0;scans[i]=0;released[i]=0;end
        event_file=$fopen("events.csv","w");pixel_file=$fopen("scan-pixels.mem","w");
        if(!event_file||!pixel_file)$fatal(1,"cannot open evidence output");
        $fdisplay(event_file,"event,id,core_cycle,crc32");
        repeat(20)@(negedge cam_clk);reset_n=1;capture_admit=1;scan_enable=1;
        sensor_frame(1);sensor_frame(2);
        wait(commits==FRAMES);@(negedge core_clk);capture_admit=0;
        wait(captured==FRAMES&&processed==FRAMES&&presented==FRAMES&&unique_scans==FRAMES&&
             dut.capture_reserved==0&&!dut.processing&&!dut.pending);
        wait(dut.output_video.y==VT-2&&dut.output_video.x==0);
        if(dut.lease_active||dut.response_busy||dut.awaiting_bank_grant||dut.display_req_valid)
            $fatal(1,"display lease persisted after complete active frame");
        scan_enable=0;repeat(100)@(negedge core_clk);
        if(failed||underflows||mismatches||wleft||rleft||dut.fifo_used||dut.fifo_available||
           dut.input_link.input_dma.active||dut.input_link.input_dma.source_valid||
           !dut.input_link.input_dma.capture.fifo_idle||dut.input_link.input_dma.capture.done_valid||
           dut.input_link.dropped_frames||commits!=FRAMES||releases!=FRAMES||
           source_beats!=FRAMES*FB||result_beats!=FRAMES*FB||final_source_bursts!=FRAMES||final_result_bursts!=FRAMES||
           !aw_stalls||!w_stalls||!ar_stalls||!read_contention||!write_contention||
           !capture_process_overlap||!process_scan_overlap||!capture_scan_overlap||complete_rasters<3||
           capture_fifo_peak>64||display_fifo_peak>512||done_checks!=unique_scans+repeat_scans)
            $fatal(1,"720 final drain/coverage incomplete src_reuse=%0d result_reuse=%0d rc=%0d wc=%0d",source_reuses,result_reuses,read_contention,write_contention);
        summary_file=$fopen("summary.json","w");
        $fdisplay(summary_file,"{\"passed\":true,\"frames\":2,\"width\":1280,\"height\":720,\"source_beats\":%0d,\"result_beats\":%0d,\"read_beats\":%0d,\"unique_scans\":%0d,\"repeat_scans\":%0d,\"scanned_pixels\":%0d,\"source_bank_reuses\":%0d,\"result_bank_reuses\":%0d,\"aw_stalls\":%0d,\"w_stalls\":%0d,\"ar_stalls\":%0d,\"read_contention_cycles\":%0d,\"write_contention_cycles\":%0d,\"capture_process_overlap\":%0d,\"process_scan_overlap\":%0d,\"capture_scan_overlap\":%0d,\"capture_fifo_peak\":%0d,\"display_fifo_peak\":%0d,\"complete_rasters\":%0d,\"black_border_pixels\":%0d,\"scan_crc_checks\":%0d,\"underflows\":0,\"crc_mismatches\":0,\"final_drain\":true}",source_beats,result_beats,read_beats,unique_scans,repeat_scans,total_pixels,source_reuses,result_reuses,aw_stalls,w_stalls,ar_stalls,read_contention,write_contention,capture_process_overlap,process_scan_overlap,capture_scan_overlap,capture_fifo_peak,display_fifo_peak,complete_rasters,border_pixels,done_checks);
        $fclose(summary_file);$fclose(event_file);$fclose(pixel_file);
        $display("PASS camera720 corrected system: frames=%0d scan_pixels=%0d",commits,total_pixels);$finish;
    end
endmodule
