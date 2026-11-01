`timescale 1ps/1ps
// Full 720p byte ingress through the unchanged capture, DMA and write arbiter.
// Synthetic camera and Pango AW/WREADY/WLAST memory model; no physical IP.
module tb_camera720_capture;
    localparam W=1280,H=720,N=W*H,FB=N/16,STRIDE=1048576;
    localparam LINE_TICKS=1892*2,FRAME_LINES=740;
    reg reset_n=1,cam_clk=0,sys_clk=0,enable=0;
    initial begin #1 reset_n=0; end
    always #4000 sys_clk=~sys_clk; // 125 MHz
    // Exact average 48 MHz, alternating integer-picosecond half periods.
    integer phase=0,delay_ps;
    initial begin #1733;forever begin
        phase=phase+1000000;delay_ps=phase/96;phase=phase%96;
        #(delay_ps)cam_clk=~cam_clk;
    end end
    reg cam_vsync=1,cam_href=1;reg[7:0]cam_data=0;
    reg[1:0]writable=0;reg release_valid=0,release_bank=0;
    wire source_valid,source_bank;wire[31:0]source_id,source_crc,source_pixels;
    wire[1:0]reserved;
    reg core_awvalid=0;reg[27:0]core_awaddr=0;
    wire core_awready,core_wready,core_wlast;
    wire[255:0]core_wdata;
    wire[27:0]awaddr;wire[3:0]awlen;wire awvalid,awready,wready,wlast;
    wire[255:0]wdata;wire[31:0]wstrb;wire failed,busy;wire[7:0]fault,last_drop;
    wire[31:0]capture_bursts,result_bursts,accepted,dropped,overflows,no_free;
    camera_vga_input_write_link #(.WIDTH(W),.HEIGHT(H),.BANK_STRIDE(STRIDE),
        .FIFO_ADDR_BITS(6),.VSYNC_ACTIVE_HIGH(0),.HREF_ACTIVE_HIGH(0),.HIGH_BYTE_FIRST(0)) dut(
        .cam_clk(cam_clk),.sys_clk(sys_clk),.rst_n(reset_n),.enable(enable),
        .cam_vsync(cam_vsync),.cam_href(cam_href),.cam_data(cam_data),
        .core_source_writable(writable),.core_source_released(release_valid),.core_released_bank(release_bank),
        .core_source_valid(source_valid),.core_source_ready(1'b1),.core_source_bank(source_bank),
        .core_source_id(source_id),.source_crc(source_crc),.source_pixels(source_pixels),.capture_reserved(reserved),
        .core_failed(1'b0),.core_fault(8'd0),.core_awaddr(core_awaddr),.core_awlen(4'd15),
        .core_awvalid(core_awvalid),.core_awready(core_awready),.core_wdata(core_wdata),
        .core_wstrb(32'hffffffff),.core_wready(core_wready),.core_wlast(core_wlast),
        .awaddr(awaddr),.awlen(awlen),.awvalid(awvalid),.awready(awready),
        .wdata(wdata),.wstrb(wstrb),.wready(wready),.wlast(wlast),
        .failed(failed),.fault(fault),.write_busy(busy),.capture_bursts(capture_bursts),
        .result_bursts(result_bursts),.accepted_frames(accepted),.dropped_frames(dropped),
        .overflow_frames(overflows),.no_free_frames(no_free),.last_drop_fault(last_drop));

    function automatic[15:0] pixel(input integer frame_id,input integer index);
        integer x,y;
        begin x=index%W;y=index/W;
            pixel=(x*73+y*151+frame_id*16'h1234)^((x<<7)|(y>>1))^(frame_id<<(index%7));
        end
    endfunction
    function automatic[255:0] expected_word(input integer frame_id,input integer word_index);
        integer lane;begin
            for(lane=0;lane<16;lane=lane+1)expected_word[lane*16+:16]=pixel(frame_id,word_index*16+lane);
        end
    endfunction
    function automatic[255:0] result_word(input integer transaction,input integer beat_index);
        integer lane;begin
            for(lane=0;lane<8;lane=lane+1)
                result_word[lane*32+:32]=32'h5a000000^(transaction<<8)^(beat_index<<4)^lane;
        end
    endfunction
    integer core_transaction=0,core_beat=0,core_gap=2000;
    reg core_inflight=0,traffic_enable=1;
    assign core_wdata=result_word(core_transaction,core_beat);
    always @(posedge sys_clk)if(reset_n)begin
        if(core_gap>0)core_gap<=core_gap-1;
        if(traffic_enable&&!core_inflight&&!core_awvalid&&core_gap==0)begin
            core_awvalid<=1;core_awaddr<=2*STRIDE+(core_transaction%512)*128;
        end
        if(core_awvalid&&core_awready)begin core_awvalid<=0;core_inflight<=1;end
        if(core_wready)begin
            if(core_wlast!==(core_beat==15))$fatal(1,"modeled result WLAST mismatch");
            if(core_beat==15)begin
                core_beat<=0;core_inflight<=0;core_transaction<=core_transaction+1;core_gap<=2000;
            end else core_beat<=core_beat+1;
        end
    end

    // Full source storage plus exact address/write checks. Background result
    // bursts exercise the production whole-burst arbiter, not the remapper.
    reg[255:0]memory[0:2*FB-1];
    integer cycles=0,mem_left=0,mem_bank=0,mem_index=0,mem_result_beat=0;
    integer epoch[0:1],writes[0:6],peaks[0:6],good_commits[0:1];
    integer commits=0,releases=0,reuses=0,final_bursts=0,aw_stalls=0,w_stalls=0;
    integer contention_cycles=0,zero_latency_beats=0,overflow_stall_cycles=0;
    integer kind=0,scenario=0;reg overflow_latched=0,overflow_release=0;
    wire service_pause=(cycles%50000>=10000&&cycles%50000<11250);
    wire forced_pause=overflow_latched&&!overflow_release;
    wire new_write=awvalid&&awready;
    assign awready=reset_n&&mem_left==0&&!service_pause&&!forced_pause&&cycles%37<24;
    assign wready=reset_n&&!service_pause&&!forced_pause&&cycles%11<8&&
        (mem_left>0||(new_write&&cycles%2==0));
    assign wlast=mem_left>0 ? mem_left==1 : awlen==0;
    integer selected_bank,selected_word,selected_beat,selected_left,frame_no;
    integer output_file,commit_file,event_file,summary_file,i,j;
    reg[1:0]consumer_holds=0;
    always @(posedge sys_clk)if(reset_n)begin
        cycles<=cycles+1;
        if(failed)$fatal(1,"ingress fatal %h",fault);
        if(awvalid&&!awready)aw_stalls=aw_stalls+1;
        if(mem_left>0&&!wready)w_stalls=w_stalls+1;
        if(forced_pause)overflow_stall_cycles=overflow_stall_cycles+1;
        if(dut.dma_awvalid&&core_awvalid)contention_cycles=contention_cycles+1;
        if(dut.input_dma.grant_valid&&dut.input_dma.grant_ready)begin
            frame_no=dut.input_dma.next_id;selected_bank=dut.input_dma.grant_bank;
            if(frame_no<1||frame_no>6||reserved[selected_bank]||consumer_holds[selected_bank])
                $fatal(1,"source grant ownership/id violation");
            if(epoch[selected_bank]!=0)reuses=reuses+1;
            epoch[selected_bank]=frame_no;
        end
        selected_bank=mem_bank;selected_word=mem_index;selected_beat=mem_result_beat;selected_left=mem_left;
        if(new_write)begin
            if(mem_left!=0||awlen!=15||awaddr%128!=0)$fatal(1,"DDR burst layout differs");
            selected_bank=awaddr/STRIDE;selected_word=(awaddr%STRIDE)/8;selected_beat=0;selected_left=16;
            if(selected_bank<2)begin
                frame_no=epoch[selected_bank];
                if(!reserved[selected_bank]||consumer_holds[selected_bank]||selected_word!=writes[frame_no]||selected_word+16>FB)
                    $fatal(1,"source AW extent/sequence/ownership mismatch");
                if(selected_word==FB-16)begin
                    if((awaddr%STRIDE)!=460672)$fatal(1,"final AW not 4-byte UI units");
                    final_bursts=final_bursts+1;
                end
                if(kind==2)overflow_latched<=1;
            end else if(selected_bank!=2||awaddr!=core_awaddr)$fatal(1,"unexpected result address");
        end
        if(wready)begin
            if(selected_left==0||wstrb!==32'hffffffff||wlast!==(selected_left==1))$fatal(1,"DDR beat contract differs");
            if(mem_left==0)zero_latency_beats=zero_latency_beats+1;
            if(selected_bank<2)begin
                frame_no=epoch[selected_bank];
                if(wdata!==expected_word(frame_no,selected_word))
                    $fatal(1,"source payload differs id=%0d word=%0d",frame_no,selected_word);
                memory[selected_bank*FB+selected_word]=wdata;
                $fdisplay(output_file,"%0d,%0d,%0d,%064x",frame_no,selected_bank,selected_word,wdata);
                writes[frame_no]=writes[frame_no]+1;
            end else if(wdata!==result_word(core_transaction,selected_beat))$fatal(1,"arbiter mixed result/source data");
            selected_left=selected_left-1;selected_word=selected_word+1;selected_beat=selected_beat+1;
        end
        mem_left<=selected_left;mem_bank<=selected_bank;mem_index<=selected_word;mem_result_beat<=selected_beat;
        if(source_valid)begin
            if(source_id==3||source_id==4||source_id!=epoch[source_bank]||source_pixels!=N||
               writes[source_id]!=FB||consumer_holds[source_bank]||!dut.input_dma.capture.fifo_idle)
                $fatal(1,"incomplete/bad frame committed");
            for(j=0;j<FB;j=j+1)
                if(memory[source_bank*FB+j]!==expected_word(source_id,j))$fatal(1,"committed DDR contents differ");
            consumer_holds[source_bank]=1;commits=commits+1;good_commits[source_bank]=good_commits[source_bank]+1;
            $fdisplay(commit_file,"%0d,%0d,%0d,%08x,%0d",source_id,source_bank,source_pixels,source_crc,writes[source_id]);
            $display("CAMERA720_COMMIT id=%0d bank=%0d beats=%0d crc=%08x fifo_peak=%0d",source_id,source_bank,writes[source_id],source_crc,peaks[source_id]);
        end
        if(release_valid)begin
            if(!consumer_holds[release_bank])$fatal(1,"release without committed source");
            consumer_holds[release_bank]=0;releases=releases+1;
        end
    end
    always @(posedge cam_clk)if(reset_n&&dut.input_dma.capture.capturing)begin
        if(dut.input_dma.capture.unused_used>64)$fatal(1,"FIFO accounting exceeds depth");
        if(dut.input_dma.capture.unused_used>peaks[scenario])peaks[scenario]=dut.input_dma.capture.unused_used;
    end
    task tick(input bit vs,input bit href,input[7:0]data);
        begin @(negedge cam_clk);cam_vsync=vs;cam_href=href;cam_data=data;end
    endtask
    task run_frame(input integer id,input integer bank,input integer frame_kind);
        integer x,y,rows,wait_count,start_commits,start_drops;
        reg[15:0]value;reg[63:0]start_time;
        begin
            scenario=id;kind=frame_kind;start_commits=commits;start_drops=dropped;
            @(negedge sys_clk);writable=1<<bank;
            wait_count=0;
            while(!dut.input_dma.capture.pending_grant&&wait_count<10000)begin
                tick(1,1,0);wait_count=wait_count+1;
            end
            if(!dut.input_dma.capture.pending_grant||dut.input_dma.capture.pending_id!=id)
                $fatal(1,"reservation did not arrive for frame %0d",id);
            // Withhold future grants; the active sensor is never backpressured.
            @(negedge sys_clk);writable=0;
            tick(0,1,0);start_time=$time;
            repeat(3)tick(0,1,0);
            repeat(4*LINE_TICKS-4)tick(1,1,0);
            rows=frame_kind==0 ? H : frame_kind==1 ? 2 : 8;
            for(y=0;y<rows;y=y+1)begin
                for(x=0;x<W;x=x+1)begin
                    value=pixel(id,y*W+x);tick(1,0,value[7:0]);
                    if(!(frame_kind==1&&y==0&&x==W-1))tick(1,0,value[15:8]);
                end
                repeat(LINE_TICKS-W*2)tick(1,1,0);
                if(frame_kind==1&&y==0)tick(1,1,0);
            end
            if(frame_kind==2)begin
                if(!overflow_latched||dut.input_dma.capture.bad[3]!==1'b1)
                    $fatal(1,"directed overflow was not reached");
                overflow_release=1;
            end
            repeat(16*LINE_TICKS)tick(1,1,0);
            tick(0,1,0);
            if(frame_kind==0&&($time-start_time<64'd58336666666||$time-start_time>64'd58336666668))
                $fatal(1,"full frame HTS/VTS timing differs: %0d",$time-start_time);
            repeat(4)tick(0,1,0);tick(1,1,0);
            wait_count=0;
            while((commits==start_commits&&dropped==start_drops)&&wait_count<100000)begin
                @(negedge sys_clk);wait_count=wait_count+1;
            end
            if(frame_kind==0)begin
                if(commits!=start_commits+1||dropped!=start_drops)$fatal(1,"good frame rejected");
                repeat(20)@(negedge sys_clk);
                release_bank=bank;release_valid=1;@(negedge sys_clk);release_valid=0;
            end else begin
                if(dropped!=start_drops+1||commits!=start_commits||last_drop==0)$fatal(1,"bad frame not quarantined");
                if(frame_kind==1&&(last_drop&8'h41)!=8'h41)$fatal(1,"odd row fault absent");
                if(frame_kind==2&&(!last_drop[3]||overflows!=1))$fatal(1,"overflow fault absent");
                $fdisplay(event_file,"%0d,%0d,%02x,%0d,%0d",id,frame_kind,last_drop,writes[id],peaks[id]);
                $display("CAMERA720_DROP id=%0d fault=%02x beats=%0d fifo_peak=%0d",id,last_drop,writes[id],peaks[id]);
            end
            repeat(20)@(negedge sys_clk);
            if(reserved||dut.input_dma.active||dut.input_dma.source_valid||
               !dut.input_dma.capture.fifo_idle||dut.input_dma.capture.done_valid)
                $fatal(1,"source transaction/FIFO not drained before bank reuse");
        end
    endtask
    initial begin #(64'd400000000000);$fatal(1,"720 capture simulation 400ms deadline");end
    initial begin
        for(i=0;i<2;i=i+1)begin epoch[i]=0;good_commits[i]=0;end
        for(i=0;i<7;i=i+1)begin writes[i]=0;peaks[i]=0;end
        output_file=$fopen("ddr-source-words.csv","w");commit_file=$fopen("commits.csv","w");event_file=$fopen("drops.csv","w");
        $fdisplay(output_file,"frame_id,bank,word,data");$fdisplay(commit_file,"frame_id,bank,pixels,crc,beats");
        $fdisplay(event_file,"frame_id,kind,fault,written_beats,fifo_peak");
        repeat(20)@(negedge cam_clk);reset_n=1;enable=1;
        run_frame(1,0,0);run_frame(2,1,0);run_frame(3,0,1);run_frame(4,1,2);
        run_frame(5,0,0);run_frame(6,1,0);
        traffic_enable=0;enable=0;
        wait(!core_awvalid&&!core_inflight&&mem_left==0&&!busy);
        repeat(20)@(negedge sys_clk);
        if(accepted!=4||commits!=4||releases!=4||good_commits[0]!=2||good_commits[1]!=2||
           dropped!=2||overflows!=1||no_free||reuses!=4||final_bursts!=4||
           !result_bursts||!contention_cycles||!zero_latency_beats||!aw_stalls||!w_stalls||
           reserved||consumer_holds||dut.input_dma.active||!dut.input_dma.capture.fifo_idle)
            $fatal(1,"720 capture coverage or final drain incomplete");
        summary_file=$fopen("summary.json","w");
        $fdisplay(summary_file,"{\"passed\":true,\"width\":1280,\"height\":720,\"pclk_hz\":48000000,\"core_hz\":125000000,\"hts_pixels\":1892,\"vts_lines\":740,\"bank_stride_ui\":1048576,\"ui_bytes\":4,\"frame_beats\":57600,\"frame_bytes\":1843200,\"frame_ui\":460800,\"good_frames\":4,\"bad_frames\":2,\"overflow_frames\":1,\"bank_reuses\":%0d,\"final_bursts\":%0d,\"result_bursts\":%0d,\"capture_bursts\":%0d,\"contention_cycles\":%0d,\"aw_stall_cycles\":%0d,\"w_stall_cycles\":%0d,\"zero_latency_first_beats\":%0d,\"overflow_stall_cycles\":%0d,\"fifo_peaks\":[%0d,%0d,%0d,%0d,%0d,%0d],\"complete_drain\":true}",reuses,final_bursts,result_bursts,capture_bursts,contention_cycles,aw_stalls,w_stalls,zero_latency_beats,overflow_stall_cycles,peaks[1],peaks[2],peaks[3],peaks[4],peaks[5],peaks[6]);
        $fclose(summary_file);$fclose(output_file);$fclose(commit_file);$fclose(event_file);
        $display("PASS camera720 capture: full_frames=4 bad_frames=2 pixels=%0d",4*N);$finish;
    end
endmodule
