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
    output [15:0] last_pixels_per_line,last_lines
);
    (* async_reg="true" *) reg [1:0] p_reset=0,r_reset=0;
    always @(posedge pix_clk or negedge rst_n)
        if(!rst_n)p_reset<=0;else p_reset<={p_reset[0],1'b1};
    always @(posedge ref_clk or negedge rst_n)
        if(!rst_n)r_reset<=0;else r_reset<={r_reset[0],1'b1};
    reg polarity_known,vs_inactive,hs_inactive,vs_previous,hs_previous;
    reg saw_hs,saw_vs,timing_seen;
    reg [31:0] hs_ticks,frame_ticks;
    reg [15:0] hs_lines;
    reg [7:0] timing_fault;
    assign normalized_vs=polarity_known && (pix_vs^vs_inactive);
    wire normalized_hs=polarity_known && (pix_hs^hs_inactive);
    wire vs_rise=normalized_vs&&!vs_previous,hs_rise=normalized_hs&&!hs_previous;
    wire [16:0] finalized_hs={1'b0,hs_lines}+hs_rise;
    always @(posedge pix_clk or negedge rst_n)begin
        if(!rst_n)begin
            polarity_known<=0;vs_inactive<=0;hs_inactive<=0;vs_previous<=0;hs_previous<=0;
            saw_hs<=0;saw_vs<=0;timing_seen<=0;hs_ticks<=0;frame_ticks<=0;hs_lines<=0;timing_fault<=0;
        end else if(!p_reset[1])begin
            polarity_known<=0;vs_inactive<=0;hs_inactive<=0;vs_previous<=0;hs_previous<=0;
            saw_hs<=0;saw_vs<=0;timing_seen<=0;hs_ticks<=0;frame_ticks<=0;hs_lines<=0;timing_fault<=0;
        end else begin
            if(pix_de && !polarity_known)begin
                polarity_known<=1;vs_inactive<=pix_vs;hs_inactive<=pix_hs;
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
    wire geometry_ready,geometry_failed;
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
        .frame_fresh(unused_frame_fresh),.snapshot_fresh(unused_snapshot_fresh));
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
endmodule
