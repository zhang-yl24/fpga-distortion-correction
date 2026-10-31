`timescale 1ps/1ps
// Real independent top and complete production System. Only clocks/PHY/TX
// configuration status use explicit test-only stubs. Small geometry is not FPS.
`define D dut.u_ddr3_test_h
`define S dut.system
module tb_processed_output;
    localparam W=32,H=16,N=W*H,FB=N/16,HT=128,VT=40,HS=4,VS=2,X0=16,Y0=4;
    reg clk_27m=0,clk_p=0,reset_n=0;
    integer phase=0,delay_ps;
    initial forever begin phase=phase+500000;delay_ps=phase/27;phase=phase%27;#(delay_ps)clk_27m=~clk_27m;end
    always #4000 clk_p=~clk_p;
    wire pix_clk,hs,vs,de;wire[7:0]r,g,b,led;tri hd_scl,hd_sda;
    processed_output_top #(.WIDTH(W),.HEIGHT(H),.HT(HT),.VT(VT),.HS(HS),.VS(VS),.X0(X0),.Y0(Y0)) dut(
        .clk_27m(clk_27m),.clk_p(clk_p),.clk_n(!clk_p),.reset_n(reset_n),
        .pix_clk(pix_clk),.hs_out(hs),.vs_out(vs),.de_out(de),.r_out(r),.g_out(g),.b_out(b),
        .hd_scl(hd_scl),.hd_sda(hd_sda),.led(led));
    `include "oracle.vh"
    `include "relocated-headers/rtl/video_crc32.vh"
    reg [15:0] golden[0:N-1];reg [255:0] source_words[0:FB-1],result_words[0:FB-1];
    reg normal=0,normal_drain=0;
    integer commits=0,releases=0,publications=0,unique_scans=0,repeated_scans=0,scanned_pixels=0;
    integer source_reservations[0:1],source_epoch[0:1],result_epoch[0:1];
    integer source_written[0:63],result_written[0:63],scan_seen[0:63],released[0:63];
    integer events,scan_file,summary,i,f,bank,off,source_reuses=0,result_reuses=0;
    reg previous_commit=0,previous_release=0,previous_publish=0;
    integer output_ticks=0,raster_origin=0,out_x=0,out_y=0,scan_count=0,scan_start=0,scan_id=0;
    reg raster_seen=0,previous_vs=0;reg [31:0]scan_crc=32'hffffffff;reg[15:0]observed;
    integer cold_reference_cycles=0,startup_cases=0,runtime_cases=0,sticky_cases=0,held_aw_cases=0,drained_cases=0;
    reg [27:0] held_address;reg [7:0] expected_fault;
    function automatic [23:0] expand565(input[15:0]v);
        expand565={{v[15:11],v[15:13]},{v[10:5],v[10:9]},{v[4:0],v[4:2]}};
    endfunction
    function automatic [31:0] crc_byte(input[31:0]c,input[7:0]v);
        reg[31:0]a;integer n;
        begin a=c^v;for(n=0;n<8;n=n+1)a=a[0]?(a>>1)^32'hedb88320:a>>1;crc_byte=a;end
    endfunction
    task all_ready;
        begin
            dut.video_pll.test_lock=1;`D.test_pll_lock=1;`D.test_init_done=1;
            dut.hdmi_configuration.test_ready=1;dut.hdmi_configuration.test_error=0;
            `D.hold_aw=0;`D.hold_w=0;`D.hold_ar=0;
        end
    endtask
    task common_reset;
        begin
            reset_n=0;
            release dut.system_failed;
            release dut.pattern.enable;
            release `S.capture_admit;
            release `S.scan_enable;
            release `S.input_link.input_dma.grant_valid;
            all_ready;
            repeat(12)@(negedge clk_27m);
            if(dut.pipeline_release||dut.pipeline_reset_n||dut.board_failed)$fatal(1,"manual common reset did not clear board epoch");
            reset_n=1;
            @(posedge dut.global_reset_n);
            repeat(8)@(negedge clk_27m);
        end
    endtask
    task blocked(input integer which);
        begin
            repeat(12)@(negedge clk_27m);
            if(dut.pipeline_release||dut.pipeline_reset_n)$fatal(1,"missing startup qualifier released pipeline case=%0d",which);
            startup_cases=startup_cases+1;
            $fdisplay(events,"startup_blocked,%0d,%0t,%h",which,$time,dut.board_fault);
        end
    endtask
    always @(posedge dut.core_clk)begin
        if(normal&&dut.pipeline_reset_n)begin
            if(dut.board_failed||dut.system_failed)$fatal(1,"normal actual top/System fault board=%h system=%h",dut.board_fault,dut.system_fault);
            if(`S.input_link.input_dma.grant_valid&&`S.input_link.input_dma.grant_ready)begin
                f=`S.input_link.input_dma.next_id;bank=`S.input_link.input_dma.grant_bank;
                if(f<1||f>63||`S.capture_reserved[bank]||(source_epoch[bank]>0&&!released[source_epoch[bank]]))$fatal(1,"source bank reserved before prior production release");
                if(source_reservations[bank]>0)source_reuses=source_reuses+1;
                source_reservations[bank]=source_reservations[bank]+1;source_epoch[bank]=f;
            end
            if(`D.wready)begin
                bank=`D.wbank;off=`D.windex-bank*FB;
                if(dut.wdata!==(bank<2?source_words[off]:result_words[off]))$fatal(1,"actual source/result DDR W differs from CPU bank=%0d beat=%0d got=%h",bank,off,dut.wdata);
                if(bank<2)begin
                    f=source_epoch[bank];source_written[f]=source_written[f]+1;
                    if(!`S.capture_reserved[bank]||(`S.processing&&`S.bank_core.active_source==bank))$fatal(1,"capture wrote locked source bank");
                end else begin
                    f=`S.bank_core.accepted_id;result_written[f]=result_written[f]+1;
                    if(result_epoch[bank-2]!=f)begin
                        if(off!=0||(result_epoch[bank-2]>0&&scan_seen[result_epoch[bank-2]]==0))$fatal(1,"result bank reused before production scan");
                        if(result_epoch[bank-2]>0)result_reuses=result_reuses+1;
                        result_epoch[bank-2]=f;
                    end
                    if(`S.display_active&&`S.write_bank==`S.front_bank)$fatal(1,"result W hit display lease bank");
                end
            end
            #1;
            if(`S.source_commit&&!previous_commit)begin
                f=`S.source_commit_id;
                if(f<1||f>63||`S.source_pixels!=N||`S.source_crc!==SOURCE_CRC||source_written[f]!=FB)$fatal(1,"production source commit pixels/CRC/actual writes differ");
                commits=commits+1;$fdisplay(events,"commit,%0d,%0t,%h",f,$time,`S.source_crc);
            end
            if(`S.source_release&&!previous_release)begin
                f=`S.source_release_id;
                if(released[f]||result_written[f]!=FB||`S.bank_core.arvalid||`S.bank_core.awvalid)$fatal(1,"production source released before result/source transaction drain");
                released[f]=1;releases=releases+1;
                $fdisplay(events,"release,%0d,%0t,%h",f,$time,`S.bank_core.engine_crc);
            end
            if(`S.result_publish&&!previous_publish)publications=publications+1;
            previous_commit=`S.source_commit;previous_release=`S.source_release;previous_publish=`S.result_publish;
        end
    end
    always @(posedge pix_clk)begin
        if(!dut.pipeline_reset_n)begin raster_seen=0;previous_vs=0;output_ticks=0;scan_id=0;end
        else if(normal)begin
            #1;output_ticks=output_ticks+1;
            if(vs&&!previous_vs)begin
                if(raster_seen&&output_ticks-raster_origin!=HT*VT)$fatal(1,"output raster period changed");
                raster_origin=output_ticks;raster_seen=1;
            end
            previous_vs=vs;
            if(raster_seen)begin
                out_x=(output_ticks-raster_origin)%HT;out_y=((output_ticks-raster_origin)/HT)%VT;
                if(hs!==(out_x<HS)||vs!==(out_y<VS)||de!==(out_x>=X0&&out_x<X0+W&&out_y>=Y0&&out_y<Y0+H))$fatal(1,"actual board HS/VS/DE mismatch");
            end
            if(`S.pix_pixel_valid)begin
                if(!de)$fatal(1,"actual production pixel outside DE");
                if(`S.pix_frame_start)begin
                    if(scan_id!=0)$fatal(1,"overlapping output frames");
                    scan_id=`S.pix_frame_id;scan_count=0;scan_start=output_ticks;scan_crc=32'hffffffff;
                    if(scan_id<1||scan_id>63||result_epoch[`S.pix_frame_bank]!=scan_id||out_x!=X0||out_y!=Y0)$fatal(1,"production frame ID/bank/ROI mismatch");
                end
                if(`S.pix_frame_id!=scan_id||scan_count>=N||output_ticks-scan_start!=(scan_count/W)*HT+scan_count%W)$fatal(1,"actual frame pixel count/cadence");
                if({r,g,b}!==expand565(golden[scan_count]))$fatal(1,"actual DE/RGB differs from independent golden pixel=%0d got=%h expected=%h",scan_count,{r,g,b},expand565(golden[scan_count]));
                observed={r[7:3],g[7:2],b[7:3]};scan_crc=crc_byte(crc_byte(scan_crc,observed[7:0]),observed[15:8]);
                $fdisplay(scan_file,"%0d,%0d,%04h",scan_id,scan_count,observed);
                scan_count=scan_count+1;scanned_pixels=scanned_pixels+1;
                if(`S.pix_frame_last)begin
                    if(scan_count!=N||~scan_crc!==RESULT_CRC)$fatal(1,"actual scan CRC/count differs");
                    if(scan_seen[scan_id]==0)unique_scans=unique_scans+1;else repeated_scans=repeated_scans+1;
                    scan_seen[scan_id]=scan_seen[scan_id]+1;
                    $fdisplay(events,"scan,%0d,%0t,%h",scan_id,$time,~scan_crc);scan_id=0;
                end
            end else if({r,g,b}!==0)$fatal(1,"blank/invalid scan pixels are not black");
        end
    end
    // A whole simulation bound independent of software process deadlines.
    initial begin #(64'd400000000000);$fatal(1,"bounded400ms small simulation deadline");end
    initial begin
        $readmemh("expected.mem",golden);$readmemh("source-beats.mem",source_words);$readmemh("result-beats.mem",result_words);
        events=$fopen("events.csv","w");scan_file=$fopen("scanned-pixels.csv","w");
        $fdisplay(events,"event,case_or_id,time_ps,detail");$fdisplay(scan_file,"frame_id,pixel,rgb565");
        for(i=0;i<2;i=i+1)begin source_reservations[i]=0;source_epoch[i]=0;result_epoch[i]=0;end
        for(i=0;i<64;i=i+1)begin source_written[i]=0;result_written[i]=0;scan_seen[i]=0;released[i]=0;end
        repeat(12)@(negedge clk_27m);reset_n=1;
        while(!dut.global_reset_n)begin @(negedge clk_27m);cold_reference_cycles=cold_reference_cycles+1;end
        if(cold_reference_cycles<1048576||cold_reference_cycles>1048600)$fatal(1,"cold startup was shortened");
        dut.video_pll.test_lock=1;dut.hdmi_configuration.test_ready=1;blocked(0);
        dut.video_pll.test_lock=0;repeat(8)@(negedge clk_27m);`D.test_pll_lock=1;`D.test_init_done=1;blocked(1);
        dut.hdmi_configuration.test_ready=0;repeat(8)@(negedge clk_27m);dut.video_pll.test_lock=1;blocked(2);
        dut.hdmi_configuration.test_error=1;dut.hdmi_configuration.test_ready=1;
        repeat(8)@(negedge clk_27m);
        if(!dut.board_failed||dut.board_fault!=8'ha7||dut.pipeline_release)$fatal(1,"startup TXerror did not win simultaneous ready");
        dut.hdmi_configuration.test_error=0;repeat(8)@(negedge clk_27m);
        if(!dut.board_failed||dut.pipeline_release)$fatal(1,"startup TXerror not sticky");
        startup_cases=startup_cases+1;
        normal=1;common_reset;wait(dut.pipeline_release);
        wait(unique_scans>=8&&repeated_scans>=1&&source_reuses>=1&&result_reuses>=1);
        // TEST-ONLY graceful stop: withhold NEW DMA grants, keep full source
        // rasters until the current capture closes at its terminal VS edge.
        force `S.input_link.input_dma.grant_valid=0;
        wait(!`S.input_link.input_dma.active&&!`S.input_link.input_dma.source_valid&&
            !`S.input_link.input_dma.capture.done_valid&&`S.input_link.input_dma.capture.fifo_idle);
        // Capture completion raises source_valid in the same NBA event that
        // clears active. Settle the complete source-commit/start handshake
        // before testing processing/pending; neither transient zero is idle.
        repeat(30)@(negedge dut.core_clk);
        force `S.capture_admit=0;force dut.pattern.enable=0;
        wait(`S.capture_reserved==0&&!`S.src_valid&&!`S.processing&&!`S.pending&&dut.captured_frames==dut.processed_frames);
        wait(dut.presented_frames==dut.processed_frames);
        force `S.scan_enable=0;
        wait(!`S.lease_active&&!`S.response_busy&&!`S.awaiting_bank_grant&&!`S.display_req_valid&&`S.fifo_used==0&&`S.fifo_available==0&&!`S.read_busy&&!`S.write_busy);
        repeat(30)@(negedge dut.core_clk);
        if(dut.underflows||`S.mismatches||`D.wleft||`D.rleft||`S.capture_reserved!=0||`S.display_active)$fatal(1,"normal directed stop did not fully drain uf=%0d mismatch=%0d w=%0d r=%0d reserved=%0d active=%0d commits=%0d releases=%0d DMAactive=%0d DMAvalid=%0d",dut.underflows,`S.mismatches,`D.wleft,`D.rleft,`S.capture_reserved,`S.display_active,commits,releases,`S.input_link.input_dma.active,`S.input_link.input_dma.source_valid);
        if(commits!=releases||releases!=publications||dut.presented_frames!=publications)$fatal(1,"production source/result/presentation counts differ");
        if(`D.aw_stalls==0||`D.w_stalls==0||`D.ar_stalls==0)$fatal(1,"backpressure coverage missing");
        normal_drain=1;normal=0;
        $display("PROCESSED_OUTPUT_DATA_PASS commits=%0d unique=%0d repeats=%0d pixels=%0d source_reuses=%0d result_reuses=%0d",commits,unique_scans,repeated_scans,scanned_pixels,source_reuses,result_reuses);
        for(i=3;i<=7;i=i+1)begin
            common_reset;wait(dut.pipeline_release);`D.hold_aw=1;
            wait(dut.awvalid&&`D.wleft==0);held_address=dut.awaddr;
            @(negedge clk_27m);
            case(i)
                3:`D.test_init_done=0;
                4:dut.video_pll.test_lock=0;
                5:dut.hdmi_configuration.test_ready=0;
                6:force dut.system_failed=1;
                7:dut.hdmi_configuration.test_error=4'he;
            endcase
            wait(dut.board_failed);expected_fault=8'ha0+i;
            repeat(12)begin
                @(negedge dut.core_clk);
                if(!dut.global_reset_n||!dut.pipeline_reset_n||!dut.pipeline_release||!dut.awvalid||dut.awaddr!==held_address||dut.board_fault!==expected_fault)$fatal(1,"runtime reset/AW/first fault contract case=%0d",i);
            end
            held_aw_cases=held_aw_cases+1;runtime_cases=runtime_cases+1;
            all_ready;release dut.system_failed;
            repeat(20)@(negedge clk_27m);
            if(!dut.board_failed||dut.board_fault!==expected_fault||!dut.pipeline_release)$fatal(1,"runtime fault did not stay sticky");
            sticky_cases=sticky_cases+1;
            wait(!dut.awvalid&&`D.wleft==0&&!`S.write_busy&&`D.rleft==0&&!`S.read_busy&&
                !`S.input_link.input_dma.active&&!`S.input_link.input_dma.capture.done_valid&&`S.input_link.input_dma.capture.fifo_idle);
            drained_cases=drained_cases+1;
            $fdisplay(events,"runtime_preserved_aw_drained,%0d,%0t,%h",i,$time,dut.board_fault);
        end
        reset_n=0;repeat(12)@(negedge clk_27m);
        if(dut.pipeline_release||dut.pipeline_reset_n||dut.board_failed)$fatal(1,"final common reset did not recover epoch");
        summary=$fopen("summary.json","w");
        $fdisplay(summary,"{\"passed\":true,\"cold_reference_cycles\":%0d,\"startup_cases\":%0d,\"runtime_fault_cases\":%0d,\"sticky_fault_cases\":%0d,\"held_aw_cases\":%0d,\"fault_bus_drains\":%0d,\"frames_committed\":%0d,\"frames_processed\":%0d,\"frames_published\":%0d,\"unique_frames_scanned\":%0d,\"repeat_scans\":%0d,\"scanned_pixels\":%0d,\"source_bank_reuses\":%0d,\"result_bank_reuses\":%0d,\"directed_normal_final_drain\":true,\"runtime_fault_sticky_until_common_reset\":true,\"active_display_lease_fault_tested\":false,\"production_system_executed\":true,\"physical_ip_executed\":false}",cold_reference_cycles,startup_cases,runtime_cases,sticky_cases,held_aw_cases,drained_cases,commits,releases,publications,unique_scans,repeated_scans,scanned_pixels,source_reuses,result_reuses);
        $fclose(summary);$fclose(events);$fclose(scan_file);
        $display("PASS processed output: actual top/System, synthetic source, modeled DDR, production bank reuse, independent pixels, real FIFO/scan, startup and sticky fault AW drain");$finish;
    end
endmodule
