`timescale 1ns/1ps
// PDS/ADS native register preservation and SRL-disable attributes.
// PAP_ASYNC_REG is applied per instance by the isolated FDC build helper.
// DVP observer only. Inputs are ALREADY normalized active-high; no pin/polarity
// inference, PLL-lock claim, pixel storage, or reset of downstream transactions.
// Default geometry is RGB565 1280x720: exactly2560 byte clocks per720 lines.
// PCLK counts in its own domain. Registered Gray counters and a held req/ack
// snapshot cross to ref_clk. Integration must constrain Gray skew/max-delay and
// the held bus; this standalone digital test is not physical CDC sign-off.
// Isolated CDC/RDC repair: only two local reset synchronizers use raw rst_n.
// Business state resets synchronously in its own clock domain. Enable crosses
// as data, never as an asynchronous reset. Re-enable waits for evidence that
// the source observed disable: a stopped source cannot authorize an old frame.
// Common reset is still required for independent clock/reset recovery.
// Held snapshot is sampled once into ref_snapshot, then consumed one ref tick
// later. Its raw bits never drive reference-domain comparison/age logic.
module dvp_mode_admission_monitor_cdc #(
    parameter BYTES_PER_LINE=2560,LINES_PER_FRAME=720,
    parameter ACTIVITY_WINDOW_REF_CYCLES=27000,SNAPSHOT_INTERVAL_REF_CYCLES=27000,
    parameter STARTUP_REF_CYCLES=2700000,
    parameter MAX_PCLK_IDLE_REF_CYCLES=270000,MAX_VSYNC_IDLE_REF_CYCLES=2700000,
    parameter MAX_HREF_IDLE_REF_CYCLES=2700000,MAX_FRAME_IDLE_REF_CYCLES=2700000,
    parameter MAX_SNAPSHOT_IDLE_REF_CYCLES=270000
)(
    input ref_clk,pclk,rst_n,enable,vsync_active,href_active,
    output wire raw_authorize,failed,output wire [7:0] fault,
    output reg [31:0] good_frames,bad_frames,pclk_edges_per_window,
    output reg [15:0] last_frame_lines,last_line_bytes,
    output wire pclk_fresh,vsync_fresh,href_fresh,frame_fresh,snapshot_fresh
);
    localparam VALID_PARAMETERS=BYTES_PER_LINE>=2 && BYTES_PER_LINE<=65534 &&
        BYTES_PER_LINE%2==0 && LINES_PER_FRAME>=1 && LINES_PER_FRAME<=65534 &&
        ACTIVITY_WINDOW_REF_CYCLES>=1 && SNAPSHOT_INTERVAL_REF_CYCLES>=1 &&
        STARTUP_REF_CYCLES>=1 && MAX_PCLK_IDLE_REF_CYCLES>=1 &&
        MAX_VSYNC_IDLE_REF_CYCLES>=1 && MAX_HREF_IDLE_REF_CYCLES>=1 &&
        MAX_FRAME_IDLE_REF_CYCLES>=1 && MAX_SNAPSHOT_IDLE_REF_CYCLES>=1;
    // Source faults:11long byte count,12short/odd count,13line count,
    //14VSYNC truncates an active line,15HREF asserted during VSYNC blank.
    // Ref faults:C0PCLK stopped,C1VSYNC stale,C2HREF stale,C3good frame stale,
    // C4snapshot stale,C5startup without good frame;80source fault awaiting bus.
    (* syn_preserve=1, syn_srlstyle="registers" *) reg [1:0] p_reset=0,r_reset=0;
    always @(posedge pclk or negedge rst_n)
        if(!rst_n)p_reset<=0;else p_reset<={p_reset[0],1'b1};
    always @(posedge ref_clk or negedge rst_n)
        if(!rst_n)r_reset<=0;else r_reset<={r_reset[0],1'b1};
    (* syn_preserve=1, syn_srlstyle="registers" *) reg [1:0] p_enable,r_enable,source_running_sync;
    reg source_running,disabled_seen,enable_epoch_ready;
    wire p_run=p_reset[1] && p_enable[1];
    wire r_run=r_reset[1] && r_enable[1] && enable_epoch_ready;
    always @(posedge pclk) begin
        if(!p_reset[1]) begin p_enable<=0;source_running<=0;end
        else begin p_enable<={p_enable[0],enable};source_running<=p_enable[1];end
    end
    always @(posedge ref_clk) begin
        if(!r_reset[1]) begin
            r_enable<=0;source_running_sync<=0;disabled_seen<=1;enable_epoch_ready<=0;
        end else begin
            r_enable<={r_enable[0],enable};
            // Local reset is the validity guard while PCLK is stopped: the
            // synchronous business registers may still contain old-epoch bits.
            source_running_sync<={source_running_sync[0],source_running && p_reset[1]};
            if(!r_enable[1]) begin
                enable_epoch_ready<=0;disabled_seen<=!source_running_sync[1];
            end else begin
                if(!source_running_sync[1])disabled_seen<=1;
                if(disabled_seen && source_running_sync[1])enable_epoch_ready<=1;
            end
        end
    end
    reg [31:0] edge_binary,edge_gray,source_good_frames,source_bad_frames;
    reg [15:0] vs_binary,vs_gray,href_binary,href_gray;
    reg vs_previous,href_previous,frame_started,frame_bad,source_healthy;
    reg [15:0] byte_count,line_count,source_last_lines,source_last_bytes;
    reg [7:0] source_fault;
    reg source_failed;
    always @(posedge pclk)
        if(!p_run)source_failed<=0;else source_failed<=source_fault!=0;
    wire vs_rise=vsync_active && !vs_previous;
    wire href_rise=href_active && !href_previous;
    wire href_fall=!href_active && href_previous;
    wire [16:0] finalized_lines={1'b0,line_count}+href_fall;
    wire boundary_line_ok=!href_active &&
        ((!href_previous && byte_count==0) || (href_fall && byte_count==BYTES_PER_LINE));
    wire boundary_good=!frame_bad && boundary_line_ok && finalized_lines==LINES_PER_FRAME;
    always @(posedge pclk) begin
        if(!p_run)begin
            edge_binary<=0;edge_gray<=0;vs_binary<=0;vs_gray<=0;href_binary<=0;href_gray<=0;
            vs_previous<=0;href_previous<=0;frame_started<=0;frame_bad<=0;source_healthy<=0;
            byte_count<=0;line_count<=0;source_last_lines<=0;source_last_bytes<=0;
            source_good_frames<=0;source_bad_frames<=0;source_fault<=0;
        end else begin
            edge_binary<=edge_binary+1'b1;
            edge_gray<=edge_binary^(edge_binary>>1);
            vs_gray<=vs_binary^(vs_binary>>1);href_gray<=href_binary^(href_binary>>1);
            vs_previous<=vsync_active;href_previous<=href_active;
            if(vs_rise)vs_binary<=vs_binary+1'b1;
            if(href_rise)href_binary<=href_binary+1'b1;
            if(vs_rise)begin
                if(frame_started)begin
                    source_last_lines<=finalized_lines[15:0];
                    if(href_fall)source_last_bytes<=byte_count;
                    if(boundary_good)begin
                        source_good_frames<=source_good_frames+1'b1;
                        if(source_fault==0)source_healthy<=1;
                    end else begin
                        source_bad_frames<=source_bad_frames+1'b1;source_healthy<=0;
                        if(source_fault==0)source_fault<=!boundary_line_ok ? 8'h14:8'h13;
                    end
                end
                frame_started<=1;frame_bad<=0;line_count<=0;byte_count<=0;
                if(href_active)begin
                    frame_bad<=1;source_healthy<=0;
                    if(source_fault==0)source_fault<=frame_started ? 8'h14:8'h15;
                end
            end else if(frame_started)begin
                if(vsync_active && href_active)begin
                    frame_bad<=1;source_healthy<=0;
                    if(source_fault==0)source_fault<=8'h15;
                end else if(!vsync_active && href_active)begin
                    if(byte_count<BYTES_PER_LINE+1)byte_count<=byte_count+1'b1;
                    if(byte_count>=BYTES_PER_LINE)begin
                        frame_bad<=1;source_healthy<=0;
                        if(source_fault==0)source_fault<=8'h11;
                    end else if(line_count>=LINES_PER_FRAME)begin
                        frame_bad<=1;source_healthy<=0;
                        if(source_fault==0)source_fault<=8'h13;
                    end
                end else if(href_fall)begin
                    source_last_bytes<=byte_count;byte_count<=0;
                    if(line_count<LINES_PER_FRAME+1)line_count<=line_count+1'b1;
                    if(byte_count!=BYTES_PER_LINE)begin
                        frame_bad<=1;source_healthy<=0;
                        if(source_fault==0)source_fault<=8'h12;
                    end else if(line_count>=LINES_PER_FRAME)begin
                        frame_bad<=1;source_healthy<=0;
                        if(source_fault==0)source_fault<=8'h13;
                    end
                end
            end
        end
    end

    reg snapshot_request,snapshot_ack;
    (* syn_preserve=1, syn_srlstyle="registers" *) reg [1:0] request_sync,ack_sync;
    reg [104:0] held_snapshot;
    always @(posedge pclk)begin
        if(!p_run)begin request_sync<=0;snapshot_ack<=0;held_snapshot<=0;end
        else begin
            request_sync<={request_sync[0],snapshot_request};
            if(request_sync[1]!=snapshot_ack)begin
                held_snapshot<={source_good_frames,source_bad_frames,source_last_lines,
                    source_last_bytes,source_fault,source_healthy};
                snapshot_ack<=request_sync[1];
            end
        end
    end
    (* syn_preserve=1, syn_srlstyle="registers" *) reg [31:0] edge_meta,edge_sync;
    (* syn_preserve=1, syn_srlstyle="registers" *) reg [15:0] vs_meta,vs_sync,href_meta,href_sync;
    (* syn_preserve=1, syn_srlstyle="registers" *) reg [1:0] healthy_sync,failed_sync;
    function [31:0] decode32(input [31:0] g);
        integer i;
        begin decode32[31]=g[31];for(i=30;i>=0;i=i-1)decode32[i]=decode32[i+1]^g[i];end
    endfunction
    function [15:0] decode16(input [15:0] g);
        integer i;
        begin decode16[15]=g[15];for(i=14;i>=0;i=i-1)decode16[i]=decode16[i+1]^g[i];end
    endfunction
    wire [31:0] sampled_edges=decode32(edge_sync);
    wire [15:0] sampled_vs=decode16(vs_sync),sampled_href=decode16(href_sync);
    reg [31:0] previous_edges,window_edges,pclk_age,vsync_age,href_age,frame_age,snapshot_age;
    reg [31:0] window_timer,snapshot_timer,startup_timer;
    reg [15:0] previous_vs,previous_href;
    reg edge_seen,vs_seen,href_seen,frame_seen,snapshot_seen,ack_seen,settle,held_healthy;
    reg [104:0] ref_snapshot;
    reg snapshot_apply;
    reg [7:0] held_fault,ref_fault;
    assign pclk_fresh=edge_seen && pclk_age<MAX_PCLK_IDLE_REF_CYCLES;
    assign vsync_fresh=vs_seen && vsync_age<MAX_VSYNC_IDLE_REF_CYCLES;
    assign href_fresh=href_seen && href_age<MAX_HREF_IDLE_REF_CYCLES;
    assign frame_fresh=frame_seen && frame_age<MAX_FRAME_IDLE_REF_CYCLES;
    assign snapshot_fresh=snapshot_seen && snapshot_age<MAX_SNAPSHOT_IDLE_REF_CYCLES;
    assign failed=r_run && ((ref_fault!=0) || failed_sync[1] || (held_fault!=0));
    assign fault=!r_run ? 8'h00:held_fault!=0 ? held_fault:failed_sync[1] ? 8'h80:ref_fault;
    assign raw_authorize=r_run && !failed && healthy_sync[1] && held_healthy &&
        good_frames!=0 && pclk_fresh && vsync_fresh && href_fresh && frame_fresh && snapshot_fresh;
    always @(posedge ref_clk)begin
        if(!r_run)begin
            edge_meta<=0;edge_sync<=0;vs_meta<=0;vs_sync<=0;href_meta<=0;href_sync<=0;
            healthy_sync<=0;failed_sync<=0;ack_sync<=0;snapshot_request<=0;ack_seen<=0;settle<=0;
            ref_snapshot<=0;snapshot_apply<=0;
            good_frames<=0;bad_frames<=0;last_frame_lines<=0;last_line_bytes<=0;
            held_healthy<=0;held_fault<=0;ref_fault<=0;pclk_edges_per_window<=0;
            previous_edges<=0;previous_vs<=0;previous_href<=0;window_edges<=0;
            pclk_age<=0;vsync_age<=0;href_age<=0;frame_age<=0;snapshot_age<=0;
            window_timer<=0;snapshot_timer<=0;startup_timer<=0;
            edge_seen<=0;vs_seen<=0;href_seen<=0;frame_seen<=0;snapshot_seen<=0;
        end else begin
            edge_meta<=edge_gray;edge_sync<=edge_meta;vs_meta<=vs_gray;vs_sync<=vs_meta;
            href_meta<=href_gray;href_sync<=href_meta;healthy_sync<={healthy_sync[0],source_healthy};
            failed_sync<={failed_sync[0],source_failed};ack_sync<={ack_sync[0],snapshot_ack};
            previous_edges<=sampled_edges;previous_vs<=sampled_vs;previous_href<=sampled_href;
            if(sampled_edges!=previous_edges)begin pclk_age<=0;edge_seen<=1;end
            else if(pclk_age<MAX_PCLK_IDLE_REF_CYCLES)pclk_age<=pclk_age+1'b1;
            if(sampled_vs!=previous_vs)begin vsync_age<=0;vs_seen<=1;end
            else if(vsync_age<MAX_VSYNC_IDLE_REF_CYCLES)vsync_age<=vsync_age+1'b1;
            if(sampled_href!=previous_href)begin href_age<=0;href_seen<=1;end
            else if(href_age<MAX_HREF_IDLE_REF_CYCLES)href_age<=href_age+1'b1;
            if(frame_age<MAX_FRAME_IDLE_REF_CYCLES)frame_age<=frame_age+1'b1;
            if(snapshot_age<MAX_SNAPSHOT_IDLE_REF_CYCLES)snapshot_age<=snapshot_age+1'b1;
            if(window_timer==ACTIVITY_WINDOW_REF_CYCLES-1)begin
                window_timer<=0;pclk_edges_per_window<=sampled_edges-window_edges;window_edges<=sampled_edges;
            end else window_timer<=window_timer+1'b1;
            if(snapshot_timer<SNAPSHOT_INTERVAL_REF_CYCLES-1)snapshot_timer<=snapshot_timer+1'b1;
            if(snapshot_request==ack_seen && !settle && !snapshot_apply && snapshot_timer==SNAPSHOT_INTERVAL_REF_CYCLES-1)begin
                snapshot_request<=!snapshot_request;snapshot_timer<=0;
            end
            if(snapshot_apply)begin
                {good_frames,bad_frames,last_frame_lines,last_line_bytes,held_fault,held_healthy}<=ref_snapshot;
                if(ref_snapshot[104:73]!=good_frames)begin frame_age<=0;frame_seen<=1;end
                snapshot_age<=0;snapshot_seen<=1;snapshot_apply<=0;
            end
            if(settle)begin
                ref_snapshot<=held_snapshot;snapshot_apply<=1;
                ack_seen<=ack_sync[1];settle<=0;
            end else if(ack_sync[1]!=ack_seen)settle<=1;
            if(!frame_seen && startup_timer<STARTUP_REF_CYCLES)startup_timer<=startup_timer+1'b1;
            if(ref_fault==0)begin
                if(!VALID_PARAMETERS)ref_fault<=8'h01;
                else if(frame_seen)begin
                    if(!pclk_fresh)ref_fault<=8'hc0;
                    else if(!snapshot_fresh)ref_fault<=8'hc4;
                    else if(!vsync_fresh)ref_fault<=8'hc1;
                    else if(!href_fresh)ref_fault<=8'hc2;
                    else if(!frame_fresh)ref_fault<=8'hc3;
                end else if(startup_timer>=STARTUP_REF_CYCLES-1)ref_fault<=8'hc5;
            end
        end
    end
endmodule
