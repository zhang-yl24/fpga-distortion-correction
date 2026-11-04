`timescale 1ns/1ps
// Digital MODE OBSERVER, not an MS7200 PHY-lock/colour-format detector.
// Infer inactive HS/VS from DE-active pixels, then require fixed1080 geometry,
//2200x1125 pixel timing and nominal74.25MHz activity. Reference board capture
//samples on PCLK rising edges; its AC edge/delay contract remains unverified.
// Sticky observer faults never reset downstream FIFOs or DDR transactions.
module hdmi1080_input_status #(
    parameter WIDTH=1920,HEIGHT=1080,HTOTAL=2200,VTOTAL=1125,
    parameter ACTIVITY_REF_CYCLES=27000,PCLK_WINDOW_MIN=73500,PCLK_WINDOW_MAX=75000
)(
    input ref_clk,pix_clk,rst_n,pix_vs,pix_hs,pix_de,
    output normalized_vs,output qualified,failed,output [7:0] fault,
    output polarity_known_ref,vs_inactive_ref,hs_inactive_ref,
    output [31:0] good_frames,bad_frames,pclk_edges_per_window,
    output [15:0] last_pixels_per_line,last_lines,
    output [7:0] source_fault_ref_debug,ref_fault_debug,
    output source_fault_valid_ref_debug,ref_fault_valid_debug,
    output wire source_domain_reset_n_debug,snapshot_seen_ref_debug,
    output reg timing_detail_ref_valid_debug=0,
    output reg [135:0] timing_detail_ref_debug=0,
    output wire functional_qualified,functional_failed,hard_overlap_fault_ref,
    output wire [31:0] qualify_reason_ref_debug
);
    (* async_reg="true" *) reg [1:0] p_reset=0,r_reset=0;
    always @(posedge pix_clk or negedge rst_n)
        if(!rst_n)p_reset<=0;else p_reset<={p_reset[0],1'b1};
    always @(posedge ref_clk or negedge rst_n)
        if(!rst_n)r_reset<=0;else r_reset<={r_reset[0],1'b1};
    reg polarity_known,vs_inactive,hs_inactive,vs_previous,hs_previous;
    reg training_line_active,training_line_bad,training_vs,training_hs;
    reg candidate_valid,candidate_vs,candidate_hs;
    reg [16:0] training_pixels;
    reg saw_hs,saw_vs,timing_seen;
    reg [31:0] hs_ticks,frame_ticks;
    reg [15:0] hs_lines;
    reg [7:0] timing_fault;
    // Independent hard21: a prior22/23 must never mask a later DE overlap.
    reg hard_overlap_pix=0;
    (* PAP_ASYNC_REG=1,async_reg="true" *) reg [1:0] hard_overlap_sync=0;
    always @(posedge pix_clk or negedge rst_n)begin
        if(!rst_n)hard_overlap_pix<=0;
        else if(!p_reset[1])hard_overlap_pix<=0;
        else if(polarity_known && pix_de && (pix_vs!=vs_inactive || pix_hs!=hs_inactive))hard_overlap_pix<=1;
    end
    always @(posedge ref_clk or negedge rst_n)begin
        if(!rst_n)hard_overlap_sync<=0;
        else if(!r_reset[1])hard_overlap_sync<=0;
        else hard_overlap_sync<={hard_overlap_sync[0],hard_overlap_pix};
    end
    assign normalized_vs=polarity_known && (pix_vs^vs_inactive);
    wire normalized_hs=polarity_known && (pix_hs^hs_inactive);
    wire vs_rise=normalized_vs&&!vs_previous,hs_rise=normalized_hs&&!hs_previous;
    wire [16:0] finalized_hs={1'b0,hs_lines}+hs_rise;
    always @(posedge pix_clk or negedge rst_n)begin
        if(!rst_n)begin
            polarity_known<=0;vs_inactive<=0;hs_inactive<=0;vs_previous<=0;hs_previous<=0;
            training_line_active<=0;training_line_bad<=0;training_vs<=0;training_hs<=0;
            candidate_valid<=0;candidate_vs<=0;candidate_hs<=0;training_pixels<=0;
            saw_hs<=0;saw_vs<=0;timing_seen<=0;hs_ticks<=0;frame_ticks<=0;hs_lines<=0;timing_fault<=0;
        end else if(!p_reset[1])begin
            polarity_known<=0;vs_inactive<=0;hs_inactive<=0;vs_previous<=0;hs_previous<=0;
            training_line_active<=0;training_line_bad<=0;training_vs<=0;training_hs<=0;
            candidate_valid<=0;candidate_vs<=0;candidate_hs<=0;training_pixels<=0;
            saw_hs<=0;saw_vs<=0;timing_seen<=0;hs_ticks<=0;frame_ticks<=0;hs_lines<=0;timing_fault<=0;
        end else begin
            if(!polarity_known)begin
                if(pix_de)begin
                    if(!training_line_active)begin
                        training_line_active<=1;training_line_bad<=0;training_pixels<=1;
                        training_vs<=pix_vs;training_hs<=pix_hs;
                    end else begin
                        if(training_pixels<WIDTH+1)training_pixels<=training_pixels+1'b1;
                        if(pix_vs!=training_vs || pix_hs!=training_hs)training_line_bad<=1;
                    end
                end else if(training_line_active)begin
                    training_line_active<=0;training_pixels<=0;
                    if(!training_line_bad && training_pixels==WIDTH)begin
                        if(candidate_valid && candidate_vs==training_vs && candidate_hs==training_hs)begin
                            polarity_known<=1;vs_inactive<=training_vs;hs_inactive<=training_hs;
                        end else begin
                            candidate_valid<=1;candidate_vs<=training_vs;candidate_hs<=training_hs;
                        end
                    end else candidate_valid<=0;
                end
            end
            vs_previous<=normalized_vs;hs_previous<=normalized_hs;
            if(polarity_known && pix_de && (pix_vs!=vs_inactive || pix_hs!=hs_inactive) && timing_fault==0)
                timing_fault<=8'h21;
            if(polarity_known)begin
                if(saw_hs && hs_ticks<HTOTAL+1)hs_ticks<=hs_ticks+1'b1;
                if(hs_rise)begin
                    if(saw_hs && hs_ticks+1!=HTOTAL && timing_fault==0)timing_fault<=8'h22;
                    saw_hs<=1;hs_ticks<=0;
                end
                if(saw_vs && frame_ticks<HTOTAL*VTOTAL+1)frame_ticks<=frame_ticks+1'b1;
                if(vs_rise)begin
                    if(saw_vs)begin
                        if(frame_ticks+1!=HTOTAL*VTOTAL || finalized_hs!=VTOTAL)begin
                            if(timing_fault==0)timing_fault<=8'h23;
                        end else timing_seen<=1;
                    end
                    saw_vs<=1;frame_ticks<=0;hs_lines<=0;
                end else if(saw_vs && hs_rise && hs_lines<VTOTAL+1)hs_lines<=hs_lines+1'b1;
            end
        end
    end
    // Passive first timing-event tuple. Original timing_fault assignment and
    // priority above are unchanged: later VS23 overrides HS22 overrides DE21.
    reg [7:0] timing_event_debug;
    always @*begin
        timing_event_debug=0;
        if(polarity_known && pix_de && (pix_vs!=vs_inactive || pix_hs!=hs_inactive) && timing_fault==0)
            timing_event_debug=8'h21;
        if(polarity_known)begin
            if(hs_rise && saw_hs && hs_ticks+1!=HTOTAL && timing_fault==0)timing_event_debug=8'h22;
            if(vs_rise && saw_vs && (frame_ticks+1!=HTOTAL*VTOTAL || finalized_hs!=VTOTAL) && timing_fault==0)
                timing_event_debug=8'h23;
        end
    end
    reg [15:0] measured_hperiod=0,measured_vlines=0;
    reg [31:0] measured_vperiod=0;
    reg measured_hvalid=0,measured_vvalid=0;
    // [7:0]event, [23:8]Hperiod, [39:24]Vlines, [71:40]Vperiod,
    // [87:72]Hphase, [119:88]Vphase, [127:120]flags.
    // flags0 event-valid;1 DE;2 normalizedHS;3 normalizedVS;4 H-valid;5 V-valid;6 VS-inactive;7 HS-inactive.
    reg [127:0] timing_event_tuple_pix=0;
    always @(posedge pix_clk or negedge rst_n)begin
        if(!rst_n)begin
            measured_hperiod<=0;measured_vlines<=0;measured_vperiod<=0;
            measured_hvalid<=0;measured_vvalid<=0;timing_event_tuple_pix<=0;
        end else if(!p_reset[1])begin
            measured_hperiod<=0;measured_vlines<=0;measured_vperiod<=0;
            measured_hvalid<=0;measured_vvalid<=0;timing_event_tuple_pix<=0;
        end else begin
            if(polarity_known && hs_rise && saw_hs)begin
                measured_hperiod<=hs_ticks+1;measured_hvalid<=1;
            end
            if(polarity_known && vs_rise && saw_vs)begin
                measured_vlines<=finalized_hs;measured_vperiod<=frame_ticks+1;measured_vvalid<=1;
            end
            if(timing_event_debug!=0 && !timing_event_tuple_pix[120])begin
                timing_event_tuple_pix[7:0]<=timing_event_debug;
                timing_event_tuple_pix[23:8]<=(hs_rise && saw_hs) ? hs_ticks+1:measured_hperiod;
                timing_event_tuple_pix[39:24]<=(vs_rise && saw_vs) ? finalized_hs:measured_vlines;
                timing_event_tuple_pix[71:40]<=(vs_rise && saw_vs) ? frame_ticks+1:measured_vperiod;
                timing_event_tuple_pix[87:72]<=hs_ticks+1;
                timing_event_tuple_pix[119:88]<=frame_ticks+1;
                timing_event_tuple_pix[127:120]<={hs_inactive,vs_inactive,(measured_vvalid || (vs_rise && saw_vs)),
                    (measured_hvalid || (hs_rise && saw_hs)),normalized_vs,normalized_hs,pix_de,1'b1};
            end
        end
    end
    reg timing_detail_settle=0;
    // First-fault held-bundle contract: pixel tuple/raw code stop changing at
    // fault and remain held until the SAME common rst_n resets both domains.
    // Existing2FF timing_bad_sync, then one extra ref edge, precede the capture.
    always @(posedge ref_clk or negedge rst_n)begin
        if(!rst_n)begin timing_detail_settle<=0;timing_detail_ref_valid_debug<=0;timing_detail_ref_debug<=0;end
        else if(!r_reset[1])begin timing_detail_settle<=0;timing_detail_ref_valid_debug<=0;timing_detail_ref_debug<=0;end
        else if(timing_bad_sync[1] && !timing_detail_ref_valid_debug)begin
            if(!timing_detail_settle)timing_detail_settle<=1;
            else begin
                timing_detail_ref_debug<={timing_fault,timing_event_tuple_pix};
                timing_detail_ref_valid_debug<=1;
            end
        end
    end
    wire geometry_ready,geometry_failed;
    wire [15:0] geometry_reason_ref;
    wire [7:0] geometry_fault;
    wire unused_pclk_fresh,unused_vs_fresh,unused_de_fresh,unused_frame_fresh,unused_snapshot_fresh;
    // One RGB888 pixel per DE/PCLK edge; BYTES_PER_LINE is an inherited port
    //name only. No claim of two-byte DVP sampling is made by this observer.
    dvp_mode_admission_monitor #(.BYTES_PER_LINE(WIDTH),.LINES_PER_FRAME(HEIGHT),
        .ACTIVITY_WINDOW_REF_CYCLES(ACTIVITY_REF_CYCLES),.SNAPSHOT_INTERVAL_REF_CYCLES(27000),
        .STARTUP_REF_CYCLES(27000000),.MAX_PCLK_IDLE_REF_CYCLES(27000),
        .MAX_VSYNC_IDLE_REF_CYCLES(2700000),.MAX_HREF_IDLE_REF_CYCLES(2700000),
        .MAX_FRAME_IDLE_REF_CYCLES(2700000),.MAX_SNAPSHOT_IDLE_REF_CYCLES(270000)) geometry(
        .ref_clk(ref_clk),.pclk(pix_clk),.rst_n(rst_n),.enable(polarity_known),
        .vsync_active(normalized_vs),.href_active(pix_de),
        .raw_authorize(geometry_ready),.failed(geometry_failed),.fault(geometry_fault),
        .good_frames(good_frames),.bad_frames(bad_frames),.pclk_edges_per_window(pclk_edges_per_window),
        .last_frame_lines(last_lines),.last_line_bytes(last_pixels_per_line),
        .pclk_fresh(unused_pclk_fresh),.vsync_fresh(unused_vs_fresh),.href_fresh(unused_de_fresh),
        .frame_fresh(unused_frame_fresh),.snapshot_fresh(unused_snapshot_fresh),
        .source_fault_ref_debug(source_fault_ref_debug),.ref_fault_debug(ref_fault_debug),
        .source_fault_valid_ref_debug(source_fault_valid_ref_debug),.ref_fault_valid_debug(ref_fault_valid_debug),
        .source_domain_reset_n_debug(source_domain_reset_n_debug),.snapshot_seen_ref_debug(snapshot_seen_ref_debug),
        .qualify_reason_ref_debug(geometry_reason_ref));
    (* async_reg="true" *) reg [1:0] polarity_sync,vs_level_sync,hs_level_sync,timing_good_sync,timing_bad_sync;
    reg rate_seen,rate_failed;
    wire rate_good=pclk_edges_per_window>=PCLK_WINDOW_MIN && pclk_edges_per_window<=PCLK_WINDOW_MAX;
    assign polarity_known_ref=polarity_sync[1];assign vs_inactive_ref=vs_level_sync[1];assign hs_inactive_ref=hs_level_sync[1];
    assign failed=geometry_failed || timing_bad_sync[1] || rate_failed;
    // The private timing_fault code is deliberately not sampled as a changing
    //multibit bus. Its synchronized sticky predicate has the public code24.
    assign fault=geometry_failed ? geometry_fault:timing_bad_sync[1] ? 8'h24:rate_failed ? 8'h25:8'h00;
    assign qualified=r_reset[1] && polarity_sync[1] && timing_good_sync[1] && geometry_ready &&
        good_frames>=2 && rate_seen && rate_good && !failed;
    always @(posedge ref_clk or negedge rst_n)begin
        if(!rst_n)begin
            polarity_sync<=0;vs_level_sync<=0;hs_level_sync<=0;timing_good_sync<=0;timing_bad_sync<=0;
            rate_seen<=0;rate_failed<=0;
        end else if(!r_reset[1])begin
            polarity_sync<=0;vs_level_sync<=0;hs_level_sync<=0;timing_good_sync<=0;timing_bad_sync<=0;
            rate_seen<=0;rate_failed<=0;
        end else begin
            polarity_sync<={polarity_sync[0],polarity_known};vs_level_sync<={vs_level_sync[0],vs_inactive};
            hs_level_sync<={hs_level_sync[0],hs_inactive};timing_good_sync<={timing_good_sync[0],timing_seen};
            timing_bad_sync<={timing_bad_sync[0],timing_fault!=0};
            if(rate_good)rate_seen<=1;
            if(rate_seen && !rate_good)rate_failed<=1;
        end
    end
    // Additional functional-diagnostic outputs only. Strict failed/qualified/
    // fault above retain their original expressions and first-error evidence.
    assign hard_overlap_fault_ref=hard_overlap_sync[1];
    assign functional_failed=geometry_failed || rate_failed || hard_overlap_sync[1];
    assign functional_qualified=r_reset[1] && polarity_sync[1] && geometry_ready &&
        good_frames>=2 && rate_seen && rate_good && !functional_failed;
    // bit16..29 shadow predicates; strict-only timing bits remain diagnostic.
    assign qualify_reason_ref_debug={2'b00,!functional_qualified,!qualified,
        functional_failed,failed,!timing_good_sync[1],timing_bad_sync[1],
        hard_overlap_sync[1],rate_failed,geometry_failed,!rate_good,
        !rate_seen,(good_frames<2),!polarity_sync[1],!r_reset[1],geometry_reason_ref};
endmodule
