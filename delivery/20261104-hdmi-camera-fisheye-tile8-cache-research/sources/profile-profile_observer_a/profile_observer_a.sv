    // OBSERVATION ONLY: no assignment to DUT, stimulus, clocks or original scoreboards.
    integer p_events,p_stats,p_hist,p_states,p_cycle=0,p_i,p_j,p_slot,p_state;
    integer p_fsm[0:3][0:9];
    integer p_active[0:3],p_arwait[0:3],p_firstwait[0:3],p_gapwait[0:3];
    integer p_cache_r[0:3],p_rdcontend[0:3],p_wrcontend[0:3],p_offerwait[0:3];
    integer p_firsthist[0:7][0:127],p_gaphist[0:7][0:31];
    integer p_bursts[0:7],p_beats[0:7],p_firstsum[0:7],p_gapmiss[0:7];
    integer p_arcycle=0,p_lastbeat=0,p_nbeats=0,p_expectedbeats=0,p_owner=-1,p_latency,p_gap;
    integer p_offers=0,p_accepts=0,p_starts=0,p_dones=0;
    integer p_nofree=0,p_pending_cycles=0,p_display_cycles=0;
    reg p_prev_offer=0,p_prev_pending=0,p_prev_processing=0,p_prev_display=0;
    task automatic profile_event(input [8*36-1:0] kind,input integer id,input integer bankid);
        begin
            $fdisplay(p_events,"%0s,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d",
                kind,$time,p_cycle,id,bankid,tx_frame,processing,pending,display_active,
                dut.bank_core.source_valid,dut.bank_core.source_ready,dut.bank_core.source_writable,
                dut.input_link.input_dma.owned,dut.input_link.input_dma.active,
                dut.input_link.input_dma.source_valid,dut.bank_core.accepted_id);
            $fflush(p_events);
        end
    endtask
    initial begin
        p_events=$fopen("profile-timeline.csv","w");
        $fdisplay(p_events,"event,time_ps,core_cycle,frame_id,bank,input_source_index,processing,pending,display_active,source_valid,source_ready,source_writable,dma_owned,dma_active,dma_source_valid,engine_accepted_id");
        for(p_i=0;p_i<4;p_i=p_i+1)begin
            p_active[p_i]=0;p_arwait[p_i]=0;p_firstwait[p_i]=0;p_gapwait[p_i]=0;
            p_cache_r[p_i]=0;p_rdcontend[p_i]=0;p_wrcontend[p_i]=0;p_offerwait[p_i]=0;
            for(p_j=0;p_j<10;p_j=p_j+1)p_fsm[p_i][p_j]=0;
        end
        for(p_i=0;p_i<8;p_i=p_i+1)begin
            p_bursts[p_i]=0;p_beats[p_i]=0;p_firstsum[p_i]=0;p_gapmiss[p_i]=0;
            for(p_j=0;p_j<128;p_j=p_j+1)p_firsthist[p_i][p_j]=0;
            for(p_j=0;p_j<32;p_j=p_j+1)p_gaphist[p_i][p_j]=0;
        end
    end
    always @(posedge core_clk)begin
        p_cycle=p_cycle+1;
        if(rst_n&&phase_id==0)begin
            if(dut.bank_core.source_valid&&!p_prev_offer)begin
                p_offers=p_offers+1;profile_event("source_offer",dut.bank_core.source_id,dut.bank_core.source_bank);
            end
            p_prev_offer=dut.bank_core.source_valid;
            if(dut.bank_core.source_valid&&dut.bank_core.source_ready)begin
                p_accepts=p_accepts+1;profile_event("source_accept",dut.bank_core.source_id,dut.bank_core.source_bank);
            end
            if(dut.input_link.input_dma.grant_valid&&dut.input_link.input_dma.grant_ready)
                profile_event("capture_reserve",dut.input_link.input_dma.next_id,dut.input_link.input_dma.grant_bank);
            if(dut.bank_core.start&&dut.bank_core.engine_ready)begin
                p_starts=p_starts+1;profile_event("engine_start",dut.bank_core.accepted_id,dut.bank_core.active_source);
            end
            if(dut.bank_core.engine_done)begin
                p_dones=p_dones+1;profile_event("engine_done",dut.bank_core.accepted_id,dut.bank_core.active_source);
            end
            if(dut.bank_core.display_request_valid&&dut.bank_core.display_request_ready)
                profile_event("display_request_accept",dut.bank_core.pending ? dut.bank_core.pending_id:dut.bank_core.front_id,2+(dut.bank_core.pending ? dut.bank_core.write_bank:dut.bank_core.front_bank));
            if(dut.bank_core.display_grant_valid&&dut.bank_core.display_grant_ready)
                profile_event("display_grant_accept",dut.bank_core.display_id,2+dut.bank_core.front_bank);
            if(dut.bank_core.display_done_valid)
                profile_event("display_done",dut.bank_core.front_id,2+dut.bank_core.front_bank);
            if(dut.input_link.input_dma.grant_valid&&!dut.input_link.input_dma.grant_ready)p_nofree=p_nofree+1;
            if(pending)p_pending_cycles=p_pending_cycles+1;
            if(display_active)p_display_cycles=p_display_cycles+1;
            if(processing)begin
                p_slot=dut.bank_core.accepted_id-1;
                if(p_slot<0||p_slot>3)$fatal(1,"profiling active frame identity out of range");
                p_state=dut.bank_core.engine.core.sampler.cache.inner.state;
                if(p_state<0||p_state>9)$fatal(1,"profiling unknown cache FSM state");
                p_active[p_slot]=p_active[p_slot]+1;p_fsm[p_slot][p_state]=p_fsm[p_slot][p_state]+1;
                if(dut.bank_core.arvalid&&!dut.bank_core.arready)p_arwait[p_slot]=p_arwait[p_slot]+1;
                if(dut.bank_core.engine.core.sampler.cache.inner.receiving&&!dut.bank_core.engine.rvalid)begin
                    if(p_nbeats==0&&p_owner==p_slot)p_firstwait[p_slot]=p_firstwait[p_slot]+1;
                    else p_gapwait[p_slot]=p_gapwait[p_slot]+1;
                end
                if(dut.bank_core.engine.rvalid)p_cache_r[p_slot]=p_cache_r[p_slot]+1;
                if(dut.reader.arvalid&&dut.bank_core.arvalid)p_rdcontend[p_slot]=p_rdcontend[p_slot]+1;
                if(dut.input_link.dma_awvalid&&dut.input_link.core_awvalid)p_wrcontend[p_slot]=p_wrcontend[p_slot]+1;
            end
            if(dut.bank_core.source_valid&&!dut.bank_core.source_ready)begin
                p_slot=dut.bank_core.source_id-1;
                if(p_slot>=0&&p_slot<4)p_offerwait[p_slot]=p_offerwait[p_slot]+1;
            end
            if(arvalid&&arready)begin
                if(p_expectedbeats!=0)$fatal(1,"profiling physical read burst overlap");
                p_owner=(araddr/STRIDE<2 ? dut.bank_core.accepted_id-1:4+result_epoch[araddr/STRIDE-2]);
                if(p_owner<0||p_owner>7)$fatal(1,"profiling physical read owner invalid");
                p_arcycle=p_cycle;p_lastbeat=p_cycle;p_nbeats=0;p_expectedbeats=arlen+1;
                p_bursts[p_owner]=p_bursts[p_owner]+1;
            end
            if(rvalid)begin
                if(p_expectedbeats==0||p_owner<0)$fatal(1,"profiling unsolicited physical R");
                if(p_nbeats==0)begin
                    p_latency=p_cycle-p_arcycle;
                    if(p_latency<40||p_latency>45)$fatal(1,"profiling 40-cycle first-R model differs");
                    p_firsthist[p_owner][p_latency]=p_firsthist[p_owner][p_latency]+1;
                    p_firstsum[p_owner]=p_firstsum[p_owner]+p_latency;
                end else begin
                    p_gap=p_cycle-p_lastbeat;
                    if(p_gap<1||p_gap>31)$fatal(1,"profiling R beat gap exceeded bounded cadence");
                    p_gaphist[p_owner][p_gap]=p_gaphist[p_owner][p_gap]+1;
                    p_gapmiss[p_owner]=p_gapmiss[p_owner]+p_gap-1;
                end
                p_nbeats=p_nbeats+1;p_beats[p_owner]=p_beats[p_owner]+1;p_lastbeat=p_cycle;
                if(rlast)begin
                    if(p_nbeats!=p_expectedbeats)$fatal(1,"profiling read burst count mismatch");
                    p_expectedbeats=0;
                end
            end
            #2;
            if(processing!=p_prev_processing)profile_event(processing ? "processing_rise":"processing_fall",dut.bank_core.accepted_id,dut.bank_core.active_source);
            if(pending!=p_prev_pending)profile_event(pending ? "pending_rise":"pending_fall",dut.bank_core.pending_id,2+dut.bank_core.write_bank);
            if(display_active!=p_prev_display)profile_event(display_active ? "display_active_rise":"display_active_fall",dut.bank_core.front_id,2+dut.bank_core.front_bank);
            p_prev_processing=processing;p_prev_pending=pending;p_prev_display=display_active;
        end else begin
            p_prev_offer=0;p_prev_processing=0;p_prev_pending=0;p_prev_display=0;
        end
    end
    task automatic profile_finish;
        integer z,s,total;begin
            if(p_offers!=4||p_accepts!=4||p_starts!=4||p_dones!=4||p_expectedbeats!=0)
                $fatal(1,"profiling complete offer/accept/start/done/drain identities absent");
            p_stats=$fopen("profile-cycles.csv","w");
            $fdisplay(p_stats,"frame_id,processing_cycles,cache_ar_blocked,cache_first_r_wait,cache_later_r_wait,cache_r_beats,read_contention,write_contention,source_offer_wait");
            p_states=$fopen("profile-cache-fsm.csv","w");
            $fdisplay(p_states,"frame_id,state,cycles");
            for(z=0;z<4;z=z+1)begin
                total=0;
                for(s=0;s<10;s=s+1)begin total=total+p_fsm[z][s];$fdisplay(p_states,"%0d,%0d,%0d",z+1,s,p_fsm[z][s]);end
                if(total!=p_active[z]||p_cache_r[z]!=8*fills[z])$fatal(1,"profiling FSM/read count closure differs");
                $fdisplay(p_stats,"%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d",z+1,p_active[z],p_arwait[z],p_firstwait[z],p_gapwait[z],p_cache_r[z],p_rdcontend[z],p_wrcontend[z],p_offerwait[z]);
            end
            p_hist=$fopen("profile-ddr-histograms.csv","w");
            $fdisplay(p_hist,"client,frame_id,metric,cycles,count");
            for(z=0;z<8;z=z+1)begin
                for(s=0;s<128;s=s+1)if(p_firsthist[z][s])$fdisplay(p_hist,"%0s,%0d,ar_to_first_r,%0d,%0d",z<4 ? "cache":"display",z%4+1,s,p_firsthist[z][s]);
                for(s=0;s<32;s=s+1)if(p_gaphist[z][s])$fdisplay(p_hist,"%0s,%0d,r_beat_gap,%0d,%0d",z<4 ? "cache":"display",z%4+1,s,p_gaphist[z][s]);
            end
            $fclose(p_hist);$fclose(p_stats);$fclose(p_states);$fclose(p_events);
            $display("PROFILE_COMPLETE offers=%0d accepts=%0d starts=%0d dones=%0d pending_cycles=%0d display_active_cycles=%0d capture_grant_not_ready=%0d",p_offers,p_accepts,p_starts,p_dones,p_pending_cycles,p_display_cycles,p_nofree);
        end
    endtask
