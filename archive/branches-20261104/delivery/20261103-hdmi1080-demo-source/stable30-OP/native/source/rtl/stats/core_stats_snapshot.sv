`timescale 1ns/1ps
// Passive core-domain observation only. No data-path ready, reset, lease or
// DDR control output. Inputs and local counters are sampled BEFORE this edge's
// NBA updates, so a same-edge completion is visible on the next request.
module core_stats_snapshot #(parameter integer CORE_HZ=125000000,LIGHT=0,BODY_BITS=LIGHT ? 640:1120,FAULT_DETAIL_ENABLE=0)(
    input clk,rst_n,
    input request_valid,output request_ready,input [31:0] ticket,nonce,
    output reg response_valid,input response_ready,output reg [BODY_BITS-1:0] response_body,
    input last_valid,input [31:0] last_cycles,last_id,last_param_id,last_mode,
    input [31:0] captured,processed,presented,scan_good,scan_repeat,scan_blank,
    input [31:0] dropped,overflow,no_free,last_presented_id,
    input [7:0] last_drop_fault,
    input source_stalled,processing,pending,display_lease,read_busy,write_busy,
    input snapshot_busy,failed,
    input [23:0] fault_detail
);
    // Split carry avoids a new 64-bit carry chain. Both halves are core_clk.
    reg [31:0] tick_lo,tick_hi,snapshot_sequence;
    wire [31:0] source_wait,process_busy,pending_wait,lease_busy,read_cycles,write_cycles,snapshot_cycles;
    // These diagnostic counters do not elaborate in the production light profile.
    generate if(!LIGHT)begin: detail_counters
        reg [31:0] sw,pb,pw,lb,rc,wc,sc;
        assign source_wait=sw;assign process_busy=pb;assign pending_wait=pw;assign lease_busy=lb;
        assign read_cycles=rc;assign write_cycles=wc;assign snapshot_cycles=sc;
        always @(posedge clk)begin
            if(!rst_n)begin sw<=0;pb<=0;pw<=0;lb<=0;rc<=0;wc<=0;sc<=0;end
            else begin
                if(source_stalled)sw<=sw+1'b1;
                if(processing)pb<=pb+1'b1;
                if(pending)pw<=pw+1'b1;
                if(display_lease)lb<=lb+1'b1;
                if(read_busy)rc<=rc+1'b1;
                if(write_busy)wc<=wc+1'b1;
                if(snapshot_busy)sc<=sc+1'b1;
            end
        end
    end else begin: detail_disabled
        assign source_wait=0;assign process_busy=0;assign pending_wait=0;assign lease_busy=0;
        assign read_cycles=0;assign write_cycles=0;assign snapshot_cycles=0;
    end endgenerate
    reg [1119:0] assembled;
    always @* begin
    assembled=0;
    assembled[0+:64]=LIGHT ? 64'h3230544154534750:64'h3130544154534750; // PGSTAT02 / PGSTAT01 LE
    assembled[64+:8]=LIGHT ? 2:1;assembled[72+:8]=1;
    assembled[80+:16]=LIGHT ? 84:144;
    assembled[96+:32]=ticket;assembled[128+:32]=nonce;
    assembled[160+:32]=LIGHT ? {29'b0,1'b1,1'b1,last_valid}:{28'b0,1'b1,1'b1,1'b1,last_valid};
    assembled[192+:32]=CORE_HZ;
    assembled[224+:32]=snapshot_sequence;
    assembled[256+:64]={tick_hi,tick_lo};
    assembled[320+:32]=last_valid ? last_cycles:0;
    assembled[352+:32]=last_valid ? last_id:0;
    assembled[384+:32]=last_valid ? last_param_id:0;
    assembled[416+:32]=last_valid ? last_mode:0;
    assembled[448+:32]=captured;assembled[480+:32]=processed;
    assembled[512+:32]=presented;
    if(LIGHT)begin
        assembled[544+:32]=scan_repeat;
        assembled[576+:32]=dropped;
        // Diagnostic PGSTAT02 extension only; default-off legacy high bits remain zero.
        assembled[608+:32]={(FAULT_DETAIL_ENABLE ? fault_detail:24'b0),snapshot_busy,failed,write_busy,read_busy,display_lease,pending,processing,source_stalled};
    end else begin
    assembled[544+:32]=scan_good;
    assembled[576+:32]=scan_repeat;assembled[608+:32]=scan_blank;
    assembled[640+:32]=dropped;assembled[672+:32]=overflow;
    assembled[704+:32]=no_free;assembled[736+:32]=last_presented_id;
    assembled[768+:32]={24'b0,last_drop_fault};
    assembled[800+:32]={24'b0,snapshot_busy,failed,write_busy,read_busy,display_lease,pending,processing,source_stalled};
    assembled[832+:32]=source_wait;assembled[864+:32]=process_busy;
    assembled[896+:32]=pending_wait;assembled[928+:32]=lease_busy;
    assembled[960+:32]=read_cycles;assembled[992+:32]=write_cycles;
    assembled[1024+:32]=snapshot_cycles;
    // byte132 stage_valid_mask and byte136 reserved stay zero.
    // No physical HDMI or invented cross-domain stage timestamp.
    end
    end
    assign request_ready=!response_valid;
    always @(posedge clk) begin
        if(!rst_n) begin
            tick_lo<=0;tick_hi<=0;snapshot_sequence<=0;response_valid<=0;response_body<=0;
        end else begin
            tick_lo<=tick_lo+1'b1;
            if(&tick_lo)tick_hi<=tick_hi+1'b1;
            if(response_valid && response_ready)response_valid<=0;
            if(request_valid && request_ready)begin
                response_valid<=1;snapshot_sequence<=snapshot_sequence+1'b1;
                response_body<=assembled[BODY_BITS-1:0];
            end
        end
    end
endmodule
