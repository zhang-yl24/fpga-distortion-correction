`timescale 1ps/1ps
// This is the real system including two mapper/cache/writer lanes. All source
// pixels enter its capture pins; all displayed pixels are independently checked.
module tb_system_contention;
    localparam W=64,H=64,N=W*H,FB=N/16,STRIDE=1048576,MAX_ID=128;
    reg core_clk=0,pix_in_clk=0,pix_out_clk=0,rst_n=0;
    always #4000 core_clk=~core_clk;
    integer in_remainder=0,out_remainder=71,in_delay,out_delay;
    initial forever begin
        in_delay=1000000/297;in_remainder=in_remainder+1000000%297;
        if(in_remainder>=297)begin in_delay=in_delay+1;in_remainder=in_remainder-297;end
        #(in_delay)pix_in_clk=~pix_in_clk;
    end
    initial begin #1123;forever begin
        out_delay=1000000/297;out_remainder=out_remainder+1000000%297;
        if(out_remainder>=297)begin out_delay=out_delay+1;out_remainder=out_remainder-297;end
        #(out_delay)pix_out_clk=~pix_out_clk;
    end end
    reg capture_admit=0,scan_enable=0,cfg_corrected=0,vin_vs=0,vin_de=0;
    reg[23:0]vin_rgb=0;
    wire[27:0]awaddr,araddr;wire[3:0]awlen,arlen;wire awvalid,arvalid;
    wire[255:0]wdata;wire[31:0]wstrb;
    reg[255:0]memory[0:5*FB-1];
    reg rb=0,wb=0;integer read_delay=0,ri=0,rn=0,wi=0,wn=0,ra=0,wa=0;
    integer cycle=0,epoch=0,texture=0;
    wire refresh=cycle%503<9;
    wire arready=rst_n&&!rb&&cycle%7!=0&&cycle%11!=0;
    wire awready=rst_n&&!wb&&cycle%5!=0&&cycle%13!=0;
    // One shared data service per cycle, deterministic backpressure and refresh.
    wire rvalid=rst_n&&rb&&read_delay==0&&!refresh&&cycle%7!=0&&(!wb||cycle%3!=0);
    wire wready=rst_n&&wb&&!rvalid&&!refresh&&cycle%5!=0;
    wire rlast=ri==rn,wlast=wi==wn;
    wire[255:0]rdata=memory[ra+ri];
    wire failed;wire[7:0]fault;
    wire[31:0]captured,processed,presented,scan_good,scan_repeat,scan_blank,underflows,mismatches;
    wire source_commit,source_release,result_publish;wire[31:0]commit_id,source_crc,source_pixels,release_id,publish_id;
    wire[1:0]commit_bank,released_bank,publish_bank;
    wire[23:0]pix_rgb;wire pix_valid,pix_start,pix_last,pix_done_toggle,pix_done_good;
    wire[31:0]pix_id,pix_done_crc;wire pix_bank;
    wire processing,pending,display_active,write_bank,front_bank;wire[2:0]reserved;
    wire read_busy,write_busy;wire[31:0]hits,misses,queries;
    hdmi_camera_fisheye_system #(.WIDTH(W),.HEIGHT(H),.BANK_STRIDE(STRIDE),
        .HT(96),.VT(96),.HS(8),.VS(2),.X0(16),.Y0(24)) dut(
        .core_clk(core_clk),.pix_in_clk(pix_in_clk),.pix_out_clk(pix_out_clk),.rst_n(rst_n),
        .capture_admit(capture_admit),.scan_enable(scan_enable),.external_fault(1'b0),.external_fault_code(8'd0),
        .pix_in_vsync_active(vin_vs),.pix_in_de(vin_de),.pix_in_rgb(vin_rgb),.cfg_corrected(cfg_corrected),
        .awaddr(awaddr),.awlen(awlen),.awvalid(awvalid),.awready(awready),
        .wdata(wdata),.wstrb(wstrb),.wready(wready),.wlast(wlast),
        .araddr(araddr),.arlen(arlen),.arvalid(arvalid),.arready(arready),
        .rdata(rdata),.rvalid(rvalid),.rlast(rlast),.rid(4'd0),
        .pix_hs(),.pix_vs(),.pix_de(),.pix_rgb(pix_rgb),.display_valid(),.failed(failed),.fault(fault),
        .captured_frames(captured),.processed_frames(processed),.presented_frames(presented),
        .scan_good_frames(scan_good),.scan_repeat_frames(scan_repeat),.scan_blank_frames(scan_blank),
        .underflows(underflows),.mismatches(mismatches),.source_commit(source_commit),.source_commit_id(commit_id),
        .source_commit_bank(commit_bank),.source_crc(source_crc),.source_pixels(source_pixels),
        .source_release(source_release),.source_release_id(release_id),.released_bank(released_bank),
        .result_publish(result_publish),.publish_id(publish_id),.publish_bank(publish_bank),.last_process_cycles(),
        .pix_frame_id(pix_id),.pix_frame_bank(pix_bank),.pix_frame_start(pix_start),.pix_frame_last(pix_last),
        .pix_pixel_valid(pix_valid),.pix_done_toggle(pix_done_toggle),.pix_done_good(pix_done_good),.pix_done_crc(pix_done_crc),
        .processing(processing),.pending(pending),.display_active(display_active),.write_bank(write_bank),.front_bank(front_bank),
        .capture_reserved(reserved),.fifo_used(),.fifo_available(),.peak_fifo_used(),
        .cache_hits(hits),.cache_misses(misses),.queries(queries),.read_busy(read_busy),.write_busy(write_busy));

    reg[15:0]gold[0:64*N-1];reg[31:0]raw_crc[0:63],corrected_crc[0:63];
    integer id_texture[0:MAX_ID-1],source_writes[0:MAX_ID-1],result_writes[0:MAX_ID-1],query_base[0:MAX_ID-1];
    reg id_mode[0:MAX_ID-1],committed[0:MAX_ID-1],published[0:MAX_ID-1],shown[0:MAX_ID-1];
    reg[2:0]core_owned;
    integer slot_commits[0:2],commits=0,publishes=0,shown_unique=0,shown_raw=0,shown_corrected=0;
    integer display_pixels=0,done_frames=0,aw_stalls=0,ar_stalls=0,w_stalls=0,r_gaps=0,shared_busy=0;
    integer capture_engine_compete=0,display_sample_compete=0,triple_owned=0,cfg_switch_busy=0;
    integer source_pixel_checks=0,result_pixel_checks=0,source_memory_checks=0,result_memory_checks=0;
    integer current_wid=0,current_wslot=0,read_bursts=0,write_bursts=0;
    reg ar_held=0,aw_held=0,w_held=0;reg[31:0]ar_hold,aw_hold;reg[287:0]w_hold;
    integer j,k,slot,offset,address_index,identifier,logical_slot;
    function[15:0]pattern(input integer at,input integer tex);
        begin pattern=((at*13)^(at>>3)^(tex*16'h4237)^16'h5a31)&16'hffff;end
    endfunction
    function[23:0]expand565(input[15:0]p);
        begin expand565={p[15:11],p[15:13],p[10:5],p[10:9],p[4:0],p[4:2]};end
    endfunction
    function[15:0]expected(input integer id,input integer at);
        begin expected=id_mode[id] ? gold[id_texture[id]*N+at]:pattern(at,id_texture[id]);end
    endfunction
    function[31:0]expected_crc(input integer id);
        begin expected_crc=id_mode[id] ? corrected_crc[id_texture[id]]:raw_crc[id_texture[id]];end
    endfunction
    function[31:0]crc_byte(input[31:0]c,input[7:0]b);
        reg[31:0]x;integer n;
        begin x=c^b;for(n=0;n<8;n=n+1)x=x[0] ? (x>>1)^32'hedb88320:x>>1;crc_byte=x;end
    endfunction

    // Bind the actual capture grant ID to the physical input texture. Frames
    // without a reservation may be dropped as a whole; IDs never assume 1:1.
    always @(posedge pix_in_clk)if(rst_n&&dut.input_link.input_dma.capture.begin_capture)begin
        identifier=dut.input_link.input_dma.capture.pending_id;
        if(identifier<=0||identifier>=MAX_ID||id_texture[identifier]!=-1)$fatal(1,"capture ID reused %0d",identifier);
        id_texture[identifier]=texture;
    end

    always @(posedge core_clk)begin
        if(!rst_n)begin
            rb<=0;wb<=0;read_delay<=0;ri<=0;rn<=0;wi<=0;wn<=0;ra<=0;wa<=0;cycle<=0;
            ar_held<=0;aw_held<=0;w_held<=0;
        end else begin
            cycle<=cycle+1;
            if(cycle>800000)$fatal(1,"system timeout");
            if(failed)$fatal(1,"SYSTEM fault=%h epoch=%0d cycle=%0d core=%h input=%h reader=%h read=%h scan=%h",
                fault,epoch,cycle,dut.bank_fault,dut.input_fault,dut.reader_fault,dut.read_fault,dut.scan_fault);
            if(ar_held&&(!arvalid||{araddr,arlen}!==ar_hold))$fatal(1,"AR changed while held");
            if(aw_held&&(!awvalid||{awaddr,awlen}!==aw_hold))$fatal(1,"AW changed while held");
            if(w_held&&{wdata,wstrb}!==w_hold)$fatal(1,"W changed while held");
            ar_held<=arvalid&&!arready;ar_hold<={araddr,arlen};
            aw_held<=awvalid&&!awready;aw_hold<={awaddr,awlen};
            w_held<=wb&&!wready;w_hold<={wdata,wstrb};
            if(arvalid&&!arready)ar_stalls=ar_stalls+1;
            if(awvalid&&!awready)aw_stalls=aw_stalls+1;
            if(wb&&!wready)w_stalls=w_stalls+1;
            if(rb&&read_delay==0&&!rvalid)r_gaps=r_gaps+1;
            if(rb&&wb)shared_busy=shared_busy+1;
            if((dut.input_link.dma_awvalid&&dut.input_link.core_awvalid)||
               (dut.input_link.shared_writes.busy&&
                ((dut.input_link.shared_writes.owner&&dut.input_link.dma_awvalid)||
                 (!dut.input_link.shared_writes.owner&&dut.input_link.core_awvalid))))
                capture_engine_compete=capture_engine_compete+1;
            if(dut.display_arvalid&&dut.sample_valid)display_sample_compete=display_sample_compete+1;
            if(reserved==7)triple_owned=triple_owned+1;
            // Capture the external mode on its documented transaction edge;
            // subsequent cfg changes must leave this frame's golden fixed.
            if(dut.src_valid&&dut.src_ready)id_mode[dut.src_id]=cfg_corrected;
            if(arvalid&&arready)begin
                slot=araddr/STRIDE;offset=(araddr%STRIDE)/8;
                if(slot>4||araddr%8!=0||offset+arlen>=FB)$fatal(1,"read range %h",araddr);
                if(slot==2||slot==3)begin
                    if(!display_active||slot!=2+front_bank)$fatal(1,"display read lease");
                end else begin
                    logical_slot=slot==4 ? 2:slot;
                    if(!core_owned[logical_slot])$fatal(1,"sample without source lease");
                end
                rb<=1;ra<=slot*FB+offset;rn<=arlen;ri<=0;read_delay<=5+(cycle%9);read_bursts=read_bursts+1;
            end else if(rb&&read_delay>0)read_delay<=read_delay-1;
            if(rvalid)begin if(ri==rn)rb<=0;else ri<=ri+1;end
            if(awvalid&&awready)begin
                slot=awaddr/STRIDE;offset=(awaddr%STRIDE)/8;
                if(slot>4||awaddr%128!=0||awlen!=15||offset+awlen>=FB)$fatal(1,"write range %h",awaddr);
                if(slot==2||slot==3)begin
                    if(!processing||slot!=2+write_bank||(display_active&&slot==2+front_bank))$fatal(1,"result overwrite lease");
                    current_wid=dut.bank_core.accepted_id;
                    if(!committed[current_wid])$fatal(1,"result before commit");
                end else begin
                    logical_slot=slot==4 ? 2:slot;
                    if(core_owned[logical_slot]||!reserved[logical_slot])$fatal(1,"capture overwrite lease");
                    current_wid=dut.input_link.input_dma.active_id;
                end
                if(id_texture[current_wid]<0)$fatal(1,"write before input ID binding");
                current_wslot=slot;wb<=1;wa<=slot*FB+offset;wn<=awlen;wi<=0;write_bursts=write_bursts+1;
            end
            if(wready)begin
                if(wstrb!==32'hffffffff)$fatal(1,"partial write");
                memory[wa+wi]=wdata;
                offset=((wa+wi)%FB)*16;
                for(j=0;j<16;j=j+1)begin
                    if(current_wslot==2||current_wslot==3)begin
                        if(wdata[j*16+:16]!==expected(current_wid,offset+j))
                            $fatal(1,"result pixel id=%0d mode=%0d at=%0d got=%h exp=%h",current_wid,id_mode[current_wid],offset+j,wdata[j*16+:16],expected(current_wid,offset+j));
                        result_writes[current_wid]=result_writes[current_wid]+1;result_pixel_checks=result_pixel_checks+1;
                    end else begin
                        if(wdata[j*16+:16]!==pattern(offset+j,id_texture[current_wid]))$fatal(1,"capture pixel");
                        source_writes[current_wid]=source_writes[current_wid]+1;source_pixel_checks=source_pixel_checks+1;
                    end
                end
                if(wi==wn)wb<=0;else wi<=wi+1;
            end
            if(source_commit)begin
                if(commit_id==0||commit_id>=MAX_ID||committed[commit_id]||core_owned[commit_bank])$fatal(1,"commit identity");
                if(source_pixels!=N||source_writes[commit_id]!=N||source_crc!==raw_crc[id_texture[commit_id]])$fatal(1,"source CRC/count");
                if(dut.bank_core.active_corrected!==id_mode[commit_id])$fatal(1,"mode latch differs from accepted cfg");
                core_owned[commit_bank]=1;committed[commit_id]=1;query_base[commit_id]=queries;
                slot=commit_bank==2 ? 4:commit_bank;
                for(j=0;j<N;j=j+1)begin
                    if(memory[slot*FB+j/16][(j%16)*16+:16]!==pattern(j,id_texture[commit_id]))$fatal(1,"source memory");
                    source_memory_checks=source_memory_checks+1;
                end
                slot_commits[commit_bank]=slot_commits[commit_bank]+1;commits=commits+1;
            end
            if(result_publish)begin
                if(!source_release||!committed[publish_id]||published[publish_id]||release_id!=publish_id||!core_owned[released_bank])$fatal(1,"publish identity/ownership");
                if(result_writes[publish_id]!=N||dut.bank_core.pending_crc!==expected_crc(publish_id)||queries-query_base[publish_id]!=N)$fatal(1,"publish CRC/count id=%0d got=%h exp=%h count=%0d queries=%0d",publish_id,dut.bank_core.pending_crc,expected_crc(publish_id),result_writes[publish_id],queries-query_base[publish_id]);
                for(j=0;j<N;j=j+1)begin
                    if(memory[publish_bank*FB+j/16][(j%16)*16+:16]!==expected(publish_id,j))$fatal(1,"published memory");
                    result_memory_checks=result_memory_checks+1;
                end
                core_owned[released_bank]=0;published[publish_id]=1;publishes=publishes+1;
            end
        end
    end

    integer display_index=0,last_display_id=0;reg[31:0]display_crc=32'hffffffff;reg done_seen=0;
    reg[15:0]got_pixel;
    // Outputs are registered on the rising edge. Check after nonblocking updates.
    always @(negedge pix_out_clk)begin
        if(!rst_n)begin display_index=0;last_display_id=0;display_crc=32'hffffffff;done_seen=0;end
        else begin
            if(pix_valid)begin
                if(!published[pix_id]||pix_id<last_display_id)$fatal(1,"display unpublished/older frame");
                if(pix_start!=(display_index==0)||pix_last!=(display_index==N-1))$fatal(1,"display extent");
                got_pixel={pix_rgb[23:19],pix_rgb[15:10],pix_rgb[7:3]};
                if(pix_rgb!==expand565(expected(pix_id,display_index)))$fatal(1,"display pixel id=%0d at=%0d",pix_id,display_index);
                display_crc=crc_byte(crc_byte(display_crc,got_pixel[7:0]),got_pixel[15:8]);
                display_index=display_index+1;display_pixels=display_pixels+1;
            end
            if(done_seen!=pix_done_toggle)begin
                done_seen=pix_done_toggle;
                if(!pix_done_good||display_index!=N||pix_done_crc!==~display_crc||pix_done_crc!==expected_crc(pix_id))$fatal(1,"display independent CRC/count");
                if(!shown[pix_id])begin
                    shown[pix_id]=1;shown_unique=shown_unique+1;
                    if(id_mode[pix_id])shown_corrected=shown_corrected+1;else shown_raw=shown_raw+1;
                end
                last_display_id=pix_id;display_index=0;display_crc=32'hffffffff;done_frames=done_frames+1;
            end
        end
    end

    task clear_scoreboard;
        integer a;
        begin
            for(a=0;a<MAX_ID;a=a+1)begin
                id_texture[a]=-1;source_writes[a]=0;result_writes[a]=0;id_mode[a]=0;committed[a]=0;published[a]=0;shown[a]=0;
            end
            for(a=0;a<3;a=a+1)slot_commits[a]=0;
            core_owned=0;commits=0;publishes=0;shown_unique=0;shown_raw=0;shown_corrected=0;done_frames=0;display_pixels=0;
            aw_stalls=0;ar_stalls=0;w_stalls=0;r_gaps=0;shared_busy=0;capture_engine_compete=0;display_sample_compete=0;triple_owned=0;cfg_switch_busy=0;
            source_pixel_checks=0;result_pixel_checks=0;source_memory_checks=0;result_memory_checks=0;read_bursts=0;write_bursts=0;
        end
    endtask
    task send_frame(input integer tex);
        integer y,x;reg new_mode;
        begin
            texture=tex;new_mode=(tex/4)%2;
            if(new_mode!=cfg_corrected&&(processing||pending))cfg_switch_busy=cfg_switch_busy+1;
            cfg_corrected=new_mode;
            for(y=0;y<72;y=y+1)for(x=0;x<80;x=x+1)begin
                @(negedge pix_in_clk);vin_vs=y<2;vin_de=y>=6&&y<70&&x>=8&&x<72;
                vin_rgb=vin_de ? expand565(pattern((y-6)*W+x-8,tex)):0;
            end
        end
    endtask
    integer report,frame_number,wait_start,reset_while_active=0;
    task report_epoch;
        begin
            if(commits<10||publishes<8||shown_unique<7||shown_raw<2||shown_corrected<2||
                slot_commits[0]<2||slot_commits[1]<2||slot_commits[2]<2||triple_owned==0||
                aw_stalls==0||ar_stalls==0||w_stalls==0||r_gaps==0||shared_busy==0||
                capture_engine_compete==0||display_sample_compete==0||cfg_switch_busy==0||underflows!=0||mismatches!=0||
                done_frames-shown_unique<2||captured!=commits||processed!=publishes||presented>shown_unique)
                $fatal(1,"coverage epoch=%0d commits=%0d pubs=%0d shown=%0d raw=%0d corr=%0d slots=%0d,%0d,%0d triple=%0d competitors=%0d,%0d switches=%0d",epoch,commits,publishes,shown_unique,shown_raw,shown_corrected,slot_commits[0],slot_commits[1],slot_commits[2],triple_owned,capture_engine_compete,display_sample_compete,cfg_switch_busy);
            $fwrite(report,"{\"epoch\":%0d,\"commits\":%0d,\"publishes\":%0d,\"unique_displayed\":%0d,\"raw_displayed\":%0d,\"corrected_displayed\":%0d,\"display_frames\":%0d,\"display_pixels\":%0d,\"repeat_displayed\":%0d,\"slot_commits\":[%0d,%0d,%0d],\"aw_stalls\":%0d,\"ar_stalls\":%0d,\"w_stalls\":%0d,\"r_gaps\":%0d,\"shared_busy\":%0d,\"capture_engine_compete\":%0d,\"display_sample_compete\":%0d,\"triple_reserved_cycles\":%0d,\"cfg_switch_busy\":%0d,\"source_pixel_checks\":%0d,\"result_pixel_checks\":%0d,\"source_memory_checks\":%0d,\"result_memory_checks\":%0d,\"dropped_input_frames\":%0d,\"no_grant_frames\":%0d,\"underflows\":%0d,\"mismatches\":%0d,\"reset_while_active\":%0d}\n",
                epoch,commits,publishes,shown_unique,shown_raw,shown_corrected,done_frames,display_pixels,done_frames-shown_unique,
                slot_commits[0],slot_commits[1],slot_commits[2],aw_stalls,ar_stalls,w_stalls,r_gaps,shared_busy,
                capture_engine_compete,display_sample_compete,triple_owned,cfg_switch_busy,source_pixel_checks,result_pixel_checks,
                source_memory_checks,result_memory_checks,dut.input_link.dropped_frames,dut.input_link.no_free_frames,underflows,mismatches,reset_while_active);
            $display("SYSTEM EPOCH %0d commits=%0d publishes=%0d unique=%0d raw=%0d corrected=%0d slots=%0d/%0d/%0d",epoch,commits,publishes,shown_unique,shown_raw,shown_corrected,slot_commits[0],slot_commits[1],slot_commits[2]);
        end
    endtask
    initial begin
        $readmemh("corrected.hex",gold);$readmemh("raw-crc.hex",raw_crc);$readmemh("corrected-crc.hex",corrected_crc);
        report=$fopen("system-results.jsonl","w");
        for(k=0;k<5*FB;k=k+1)memory[k]={8{32'hdeadbeef}};
        for(epoch=0;epoch<2;epoch=epoch+1)begin
            rst_n=0;capture_admit=0;scan_enable=0;vin_vs=0;vin_de=0;vin_rgb=0;
            repeat(20)@(negedge core_clk);clear_scoreboard();
            rst_n=1;capture_admit=1;scan_enable=1;
            repeat(40)@(negedge pix_in_clk);
            for(frame_number=0;frame_number<24;frame_number=frame_number+1)send_frame(epoch*32+frame_number);
            // Next SOF closes the last complete capture before admission stops.
            @(negedge pix_in_clk);vin_vs=1;vin_de=0;vin_rgb=0;
            repeat(3)@(negedge pix_in_clk);capture_admit=0;
            wait_start=cycle;
            wait(commits>=12 && shown_unique==publishes && publishes==commits &&
                !processing && !pending && !dut.src_valid && !dut.input_link.input_dma.source_tail_valid);
            wait(done_frames>=shown_unique+2 && dut.scan_repeat_frames>=2);
            wait(!dut.lease_active && display_index==0);
            repeat(20)@(negedge core_clk);
            if(epoch==0)begin
                // Restart input, then interrupt genuine work with a common
                // reset of capture, all consumers and this DDR model.
                capture_admit=1;
                send_frame(24);send_frame(25);
                @(negedge pix_in_clk);vin_vs=1;vin_de=0;
                wait(processing&&(rb||wb));
                @(negedge core_clk);reset_while_active=1;
            end
            report_epoch();
        end
        $fclose(report);$display("PASS SYSTEM CONTENTION real_dual_lane=1 epochs=2");$finish;
    end
endmodule
