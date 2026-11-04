// Explicit isolated opt-in. Else branch is the byte-identical baseline source.
`ifdef EXPERIMENTAL_DUAL_READ_CREDIT
`timescale 1ns/1ps
// Independent complete runtime-cache candidate. No oracle/lifetime table is
// used. One active and one pending generation per line; a third generation
// stalls the scout atomically while the earlier foreground prefix drains.
// A pending victim lease is granted only after all old-generation references
// admitted to the query FIFO have been externally consumed. Per-generation
// references are counted at scout admission, not just foreground issue.
// Full qids still check output order; FIFO pointers never identify leases.
// DDR reset must be
// coordinated: this UI has no response epoch/transaction-ID output on AR.
module d256_runtime_prefetch_cache #(
    parameter WIDTH=1920,HEIGHT=1080,INDEX_BITS=7,TAG_W=24,
    QUERY_DEPTH=256,LOOKAHEAD=QUERY_DEPTH,IDLE_FLUSH_CYCLES=16,TIMEOUT_BITS=16,COMPACT_COORDS=0,AREA_PROFILE=0,CANDIDATE_KEY_PIPE=0,HEAD_PREDECODE=0,LOCAL_INFLIGHT_MASK=0,FILL_SCATTER16=0,FILL_STREAM=0,FILL_SCATTER8=0,JOB_DONE_EDGE_SELECT=0
)(
    input clk,rst_n,
    input frame_valid,output wire frame_ready,input [27:0] frame_base,
    input in_valid,output wire in_ready,input signed [23:0] in_x,in_y,
    input [TAG_W-1:0] in_tag,
    output wire out_valid,input out_ready,output wire [23:0] p00,p10,p01,p11,
    output wire [7:0] fx,fy,output wire [TAG_W-1:0] out_tag,
    output wire [27:0] araddr,output wire [3:0] arlen,output wire arvalid,input arready,
    input [255:0] rdata,input rvalid,rlast,input [3:0] rid,
    output wire failed,output wire [7:0] fault,
    output reg [31:0] hits,misses,completed_queries
);
    localparam LINES=1<<INDEX_BITS,BPR=WIDTH/128,QID_W=24;
    localparam BLOCK_W=$clog2(WIDTH*HEIGHT/128)<1 ? 1:$clog2(WIDTH*HEIGHT/128);
    localparam ROW_W=$clog2(HEIGHT)<1 ? 1:$clog2(HEIGHT);
    localparam COL_W=$clog2(BPR)<1 ? 1:$clog2(BPR);
    localparam REF_W=$clog2(QUERY_DEPTH+16),LEASE_W=8+4*INDEX_BITS;
    localparam X_INT_W=$clog2(WIDTH+2),Y_INT_W=$clog2(HEIGHT+2);
    localparam X_COORD_W=8+X_INT_W,Y_COORD_W=8+Y_INT_W;
    localparam FIFO_COORD_W=COMPACT_COORDS ? X_COORD_W+Y_COORD_W:48;
    localparam BASE_TOKEN_W=FIFO_COORD_W+TAG_W;
    localparam HEAD_META_W=4+4*INDEX_BITS+2*BLOCK_W+1;
    localparam TOKEN_W=BASE_TOKEN_W+(HEAD_PREDECODE ? HEAD_META_W:0),STORE_TAG_W=TAG_W+QID_W+LEASE_W;
    localparam KEY_W=1+QID_W+INDEX_BITS,GROUPS=(LINES+7)/8;
    localparam PARAM_OK=WIDTH>=128 && WIDTH<=8192 && WIDTH%128==0 && HEIGHT>=2 && HEIGHT<=8192 &&
        WIDTH*HEIGHT<=16777216 && INDEX_BITS>=2 && INDEX_BITS<=10 && QUERY_DEPTH>=8 &&
        (QUERY_DEPTH&(QUERY_DEPTH-1))==0 && LOOKAHEAD>=1 && LOOKAHEAD<=QUERY_DEPTH &&
        IDLE_FLUSH_CYCLES>=1 && IDLE_FLUSH_CYCLES<=255 && AREA_PROFILE==2;
    reg local_failed,loaded,started;
    reg [7:0] local_fault,idle_age;
    reg [27:0] active_base;
    reg [31:0] epoch,next_fill_ticket;
    reg [QID_W:0] admitted_count,issued_count,retired_count;
    wire store_failed;wire [7:0] store_fault;
    assign failed=local_failed || store_failed;
    assign fault=local_failed ? local_fault:store_fault;
    wire accept_frame=frame_valid && frame_ready;

    reg [LINES-1:0] active_valid,pending_valid,active_generation;
    reg [BLOCK_W-1:0] active_tag[0:LINES-1],pending_tag[0:LINES-1];
    reg [REF_W-1:0] active_refs[0:LINES-1],pending_refs[0:LINES-1];
    reg [QID_W-1:0] pending_first_use[0:LINES-1];
    reg [ROW_W-1:0] pending_row[0:LINES-1];
    reg [COL_W-1:0] pending_col[0:LINES-1];

    // No coordinate/directory decision feeds the external ready boundary.
    reg [1:0] skid_count;
    reg skid_rp,skid_wp;
    reg signed [23:0] skid_x[0:1],skid_y[0:1];
    reg [TAG_W-1:0] skid_tag[0:1];
    assign in_ready=loaded && !frame_valid && !failed && skid_count<2;
    wire skid_push=in_valid && in_ready;
    reg decoded_valid;
    reg signed [23:0] decoded_x,decoded_y;
    reg [TAG_W-1:0] decoded_tag;
    reg [3:0] decoded_bounds;
    reg [BLOCK_W-1:0] decoded_block[0:3];
    reg [INDEX_BITS-1:0] decoded_line[0:3];
    reg [ROW_W-1:0] decoded_row[0:3];
    reg [COL_W-1:0] decoded_col[0:3];
    wire [3:0] incoming_bounds;
    wire [BLOCK_W-1:0] incoming_block[0:3];
    wire [INDEX_BITS-1:0] incoming_line[0:3];
    wire [ROW_W-1:0] incoming_row[0:3];
    wire [COL_W-1:0] incoming_col[0:3];
    genvar n;
    generate for(n=0;n<4;n=n+1)begin: scout_decode
        wire signed [16:0] x=$signed(skid_x[skid_rp][23:8])+(n%2);
        wire signed [16:0] y=$signed(skid_y[skid_rp][23:8])+(n/2);
        wire [31:0] local_line=(y>>>1)*BPR+(x>>>7);
        assign incoming_bounds[n]=x>=0 && x<WIDTH && y>=0 && y<HEIGHT;
        assign incoming_block[n]=y*BPR+(x>>>7);
        assign incoming_line[n]={y[0],local_line[INDEX_BITS-2:0]};
        assign incoming_row[n]=y[ROW_W-1:0];
        assign incoming_col[n]=x>>>7;
    end endgenerate
    reg generations_ok;
    reg [3:0] first_ref,new_ref;
    reg [2:0] inbound_inc,miss_inc,hit_inc;
    integer a,b;
    always @*begin
        generations_ok=1;first_ref=0;new_ref=0;inbound_inc=0;miss_inc=0;
        for(a=0;a<4;a=a+1)begin
            if(decoded_bounds[a])begin
                inbound_inc=inbound_inc+1'b1;first_ref[a]=1;
                for(b=0;b<a;b=b+1)
                    if(decoded_bounds[b] && decoded_block[b]==decoded_block[a])first_ref[a]=0;
                if(pending_valid[decoded_line[a]])begin
                    if(pending_tag[decoded_line[a]]!=decoded_block[a])generations_ok=0;
                end else if(first_ref[a] && !(active_valid[decoded_line[a]] &&
                    active_tag[decoded_line[a]]==decoded_block[a]))begin
                    new_ref[a]=1;miss_inc=miss_inc+1'b1;
                end
            end
        end
        hit_inc=inbound_inc-miss_inc;
    end
    wire fifo_in_ready,fifo_out_valid,fifo_out_ready,fifo_empty;
    wire [TOKEN_W-1:0] fifo_out_data,fifo_in_data;
    wire [BASE_TOKEN_W-1:0] fifo_payload;
    wire signed [23:0] fifo_head_x,fifo_head_y;
    wire [TAG_W-1:0] fifo_head_tag;
    // Exact useful integer range[-1,limit-1], original frac8 and user tag.
    // -1 uses the all-ones integer code. Far-OOB uses all-ones-minus1,
    // which is >=limit because 2**INT_W>=limit+2. Restore -1 with sign
    // extension and every other code with zero extension; no bias adders.
    // Invalid-axis coordinates are semantically canonicalized, not raw-lossless.
    generate if(COMPACT_COORDS)begin: compact_coords_codec
        wire signed [16:0] integer_x=$signed(decoded_x[23:8]);
        wire signed [16:0] integer_y=$signed(decoded_y[23:8]);
        localparam [X_INT_W-1:0] X_FAR={X_INT_W{1'b1}}-1'b1;
        localparam [Y_INT_W-1:0] Y_FAR={Y_INT_W{1'b1}}-1'b1;
        wire [X_INT_W-1:0] code_x=(integer_x>=-1 && integer_x<WIDTH) ?
            decoded_x[8+:X_INT_W]:X_FAR;
        wire [Y_INT_W-1:0] code_y=(integer_y>=-1 && integer_y<HEIGHT) ?
            decoded_y[8+:Y_INT_W]:Y_FAR;
        wire [X_INT_W-1:0] head_code_x=fifo_out_data[8+:X_INT_W];
        wire [Y_INT_W-1:0] head_code_y=fifo_out_data[X_COORD_W+8+:Y_INT_W];
        wire head_negative_x=&head_code_x,head_negative_y=&head_code_y;
        assign fifo_payload={decoded_tag,code_y,decoded_y[7:0],code_x,decoded_x[7:0]};
        assign fifo_head_x={{(16-X_INT_W){head_negative_x}},head_code_x,fifo_out_data[7:0]};
        assign fifo_head_y={{(16-Y_INT_W){head_negative_y}},head_code_y,fifo_out_data[X_COORD_W+:8]};
    end else begin: legacy_coords_codec
        assign fifo_payload={decoded_tag,decoded_y,decoded_x};
        assign fifo_head_x=fifo_out_data[23:0];
        assign fifo_head_y=fifo_out_data[47:24];
    end endgenerate
    // The low coordinate/tag payload and its timing are unchanged. The
    // descriptor comes from the same decoded registers and scout_commit as
    // the lease admission, so no extra token or outstanding stage is added.
    generate if(HEAD_PREDECODE)begin: pack_head_descriptor
        assign fifo_in_data={decoded_bounds,decoded_line[3],decoded_line[2],decoded_line[1],decoded_line[0],
            decoded_block[2],decoded_block[0],(&decoded_x[14:8]),fifo_payload};
    end else begin: original_fifo_payload
        assign fifo_in_data=fifo_payload;
    end endgenerate
    assign fifo_head_tag=fifo_out_data[FIFO_COORD_W+:TAG_W];
    wire scout_commit=decoded_valid && generations_ok && fifo_in_ready &&
        !admitted_count[QID_W] && !failed;
    wire generation_blocked=decoded_valid && !generations_ok && !failed;
    wire decode_load=skid_count!=0 && (!decoded_valid || scout_commit) && !failed;
    sync_token_fifo #(.WIDTH(TOKEN_W),.DEPTH(QUERY_DEPTH)) query_fifo(
        .clk(clk),.rst_n(rst_n),.clear(accept_frame || failed),
        .in_valid(scout_commit),.in_ready(fifo_in_ready),.in_data(fifo_in_data),
        .out_valid(fifo_out_valid),.out_ready(fifo_out_ready),.out_data(fifo_out_data),.empty(fifo_empty));

    // A registered foreground decode separates arithmetic from directory/tag
    // lookup. Head references never migrate to a newer directory generation.
    reg head_valid;
    reg signed [23:0] head_x,head_y;
    reg [TAG_W-1:0] head_tag;
    reg [3:0] head_bounds;
    reg [BLOCK_W-1:0] head_block[0:3];
    reg [INDEX_BITS-1:0] head_line[0:3];
    wire [3:0] next_head_bounds;
    wire [BLOCK_W-1:0] next_head_block[0:3];
    wire [INDEX_BITS-1:0] next_head_line[0:3];
    generate if(HEAD_PREDECODE)begin: fifo_head_descriptor
        wire cross_block=fifo_out_data[BASE_TOKEN_W];
        wire [BLOCK_W-1:0] top_block=fifo_out_data[BASE_TOKEN_W+1+:BLOCK_W];
        wire [BLOCK_W-1:0] bottom_block=fifo_out_data[BASE_TOKEN_W+1+BLOCK_W+:BLOCK_W];
        assign next_head_bounds=fifo_out_data[BASE_TOKEN_W+1+2*BLOCK_W+4*INDEX_BITS+:4];
        for(n=0;n<4;n=n+1)begin: neighbour
            assign next_head_line[n]=fifo_out_data[BASE_TOKEN_W+1+2*BLOCK_W+n*INDEX_BITS+:INDEX_BITS];
            if(n%2==0)begin: left
                assign next_head_block[n]=(n/2==0) ? top_block:bottom_block;
            end else begin: right
                assign next_head_block[n]=((n/2==0) ? top_block:bottom_block)+cross_block;
            end
        end
    end else begin: original_head_math
        for(n=0;n<4;n=n+1)begin: head_decode
            wire signed [16:0] x=$signed(fifo_head_x[23:8])+(n%2);
            wire signed [16:0] y=$signed(fifo_head_y[23:8])+(n/2);
            wire [31:0] local_line=(y>>>1)*BPR+(x>>>7);
            assign next_head_bounds[n]=x>=0 && x<WIDTH && y>=0 && y<HEIGHT;
            assign next_head_block[n]=y*BPR+(x>>>7);
            assign next_head_line[n]={y[0],local_line[INDEX_BITS-2:0]};
        end
    end endgenerate
    wire [3:0] resident,has_request;
    generate for(n=0;n<4;n=n+1)begin: head_directory
        assign resident[n]=!head_bounds[n] || (active_valid[head_line[n]] &&
            active_tag[head_line[n]]==head_block[n]);
        assign has_request[n]=resident[n] || (pending_valid[head_line[n]] &&
            pending_tag[head_line[n]]==head_block[n]);
    end endgenerate
    wire all_resident=&resident;
    wire demand_blocked=head_valid && !all_resident && !failed;
    wire store_in_ready,store_out_valid;
    wire [STORE_TAG_W-1:0] store_out_tag;
    wire store_query_valid=head_valid && started && all_resident && !failed;
    wire store_query_accept=store_query_valid && store_in_ready;
    assign fifo_out_ready=(!head_valid || store_query_accept) && !failed;
    wire head_load=fifo_out_valid && fifo_out_ready;
    wire retire_identity_ok=store_out_tag[TAG_W+:QID_W]==retired_count[QID_W-1:0];
    reg [3:0] head_unique;
    wire [3:0] head_generations;
    wire [4*INDEX_BITS-1:0] head_lines_packed;
    integer h,z;
    always @*begin
        head_unique=head_bounds;
        for(h=0;h<4;h=h+1)for(z=0;z<h;z=z+1)
            if(head_bounds[h] && head_bounds[z] && head_block[h]==head_block[z])head_unique[h]=0;
    end
    generate for(n=0;n<4;n=n+1)begin: pack_leases
        assign head_generations[n]=active_generation[head_line[n]];
        assign head_lines_packed[n*INDEX_BITS+:INDEX_BITS]=head_line[n];
    end endgenerate
    wire [3:0] retire_mask=store_out_tag[TAG_W+QID_W+:4];
    wire [4*INDEX_BITS-1:0] retire_lines=store_out_tag[TAG_W+QID_W+4+:4*INDEX_BITS];
    wire [3:0] retire_generations=store_out_tag[TAG_W+QID_W+4+4*INDEX_BITS+:4];
    reg retire_lease_ok;
    integer r;
    reg [INDEX_BITS-1:0] lease_line;
    always @*begin
        retire_lease_ok=1;lease_line=0;
        for(r=0;r<4;r=r+1)if(retire_mask[r])begin
            lease_line=retire_lines[r*INDEX_BITS+:INDEX_BITS];
            if(!active_valid[lease_line] || active_refs[lease_line]==0 ||
                active_generation[lease_line]!=retire_generations[r])retire_lease_ok=0;
        end
    end
    assign out_valid=store_out_valid && retire_identity_ok && retire_lease_ok && !failed;
    assign out_tag=store_out_tag[TAG_W-1:0];
    wire retire=out_valid && out_ready;

    // Oldest eligible pending generation. Balanced8-leaf tournaments register
    // before a balanced group merge; there is no linear128-comparator chain.
    wire [KEY_W-1:0] invalid_key={KEY_W{1'b1}};
    wire [KEY_W-1:0] leaves[0:LINES-1];
    reg [KEY_W-1:0] group_keys[0:GROUPS-1];
    reg job_hold;
    reg [1:0] inflight_count;
    reg inflight_rp,inflight_wp;
    reg [INDEX_BITS-1:0] owner_line[0:1];
    reg [BLOCK_W-1:0] owner_tag[0:1];
    reg [31:0] owner_ticket[0:1];
    wire fill_inflight=inflight_count!=0;
    wire [INDEX_BITS-1:0] inflight_line=owner_line[inflight_rp];
    wire [BLOCK_W-1:0] inflight_tag=owner_tag[inflight_rp];
    wire [31:0] inflight_ticket=owner_ticket[inflight_rp];
    // Optional exact duplicate of the existing binary inflight owner. Each
    // bit is sampled at the ORIGINAL fill_accept edge, never a cycle later.
    // Fault quarantine holds both representations; reset/valid frame/done
    // clear them at the same original priority points below.
    reg [LINES-1:0] local_inflight_owned;
    reg [INDEX_BITS-1:0] job_line;
    reg [BLOCK_W-1:0] job_tag;
    reg [QID_W-1:0] job_first;
    reg [ROW_W-1:0] job_row;
    reg [COL_W-1:0] job_col;
    reg [31:0] job_ticket;
    genvar d,g,k,j;
    generate for(d=0;d<LINES;d=d+1)begin: eligible
        wire ok=pending_valid[d] && (!active_valid[d] || active_refs[d]==0) &&
            !(LOCAL_INFLIGHT_MASK ? local_inflight_owned[d]:
                ((fill_inflight && inflight_line==d) || (inflight_count==2 && owner_line[!inflight_rp]==d)));
        assign leaves[d]=ok ? {1'b0,pending_first_use[d],d[INDEX_BITS-1:0]}:invalid_key;
    end endgenerate
    generate for(g=0;g<GROUPS;g=g+1)begin: grouped_minimum
        wire [KEY_W-1:0] tree[1:15];
        for(k=0;k<8;k=k+1)begin: leaf
            if(g*8+k<LINES)assign tree[8+k]=leaves[g*8+k];
            else assign tree[8+k]=invalid_key;
        end
        for(j=1;j<8;j=j+1)begin: merge
            assign tree[j]=tree[j*2]<=tree[j*2+1] ? tree[j*2]:tree[j*2+1];
        end
        always @(posedge clk)
            if(!rst_n || accept_frame || failed)group_keys[g]<=invalid_key;
            else group_keys[g]<=tree[1];
    end endgenerate
    wire [KEY_W-1:0] merged[1:2*GROUPS-1];
    generate for(g=0;g<GROUPS;g=g+1)begin: merge_leaf
        assign merged[GROUPS+g]=group_keys[g];
    end endgenerate
    generate for(j=1;j<GROUPS;j=j+1)begin: merge_groups
        assign merged[j]=merged[j*2]<=merged[j*2+1] ? merged[j*2]:merged[j*2+1];
    end endgenerate
    // Optional balanced control-only pipeline. Query data/DDR/store stages
    // and every live lease/identity/fault revalidation remain unchanged.
    wire [KEY_W-1:0] candidate_key;
    generate if(CANDIDATE_KEY_PIPE==2)begin: registered_selection
        localparam MID_COUNT=GROUPS>=4 ? 4:1;
        reg [KEY_W-1:0] mid_key[0:MID_COUNT-1];
        reg [KEY_W-1:0] root_key;
        wire [KEY_W-1:0] upper[1:2*MID_COUNT-1];
        genvar m,t;
        for(m=0;m<MID_COUNT;m=m+1)begin: mid_stage
            always @(posedge clk)
                if(!rst_n || accept_frame || failed)mid_key[m]<=invalid_key;
                else mid_key[m]<=merged[MID_COUNT+m];
            assign upper[MID_COUNT+m]=mid_key[m];
        end
        for(t=1;t<MID_COUNT;t=t+1)begin: upper_min
            assign upper[t]=upper[t*2]<=upper[t*2+1] ? upper[t*2]:upper[t*2+1];
        end
        always @(posedge clk)
            if(!rst_n || accept_frame || failed)root_key<=invalid_key;
            else root_key<=upper[1];
        assign candidate_key=root_key;
    end else begin: original_selection
        assign candidate_key=merged[1];
    end endgenerate
    wire [INDEX_BITS-1:0] candidate_line=candidate_key[INDEX_BITS-1:0];
    wire [QID_W-1:0] candidate_first=candidate_key[INDEX_BITS+:QID_W];
    // One physical control-directory read is sufficient in mutually exclusive
    // scheduler phases. No pipeline/state/depth or full-QID width changes.
    // Payload/scout/head/retire read ports remain separate and unchanged.
    wire control_pending_valid,control_active_valid;
    wire [REF_W-1:0] control_active_refs;
    wire [BLOCK_W-1:0] control_pending_tag;
    wire [QID_W-1:0] control_first;
    wire [ROW_W-1:0] control_row;
    wire [COL_W-1:0] control_col;
    wire candidate_current;
    wire job_current;
    wire control_done_pending_valid;
    wire [BLOCK_W-1:0] control_done_pending_tag;
    // Dual refill scheduling requires independent candidate/job/done reads.
    // Only target AREA_PROFILE2 is admitted by PARAM_OK.
    generate begin: independent_control_reads
        assign control_pending_valid=pending_valid[candidate_line];
        assign control_active_valid=active_valid[candidate_line];
        assign control_active_refs=active_refs[candidate_line];
        assign control_pending_tag=pending_tag[candidate_line];
        assign control_first=pending_first_use[candidate_line];
        assign control_row=pending_row[candidate_line];
        assign control_col=pending_col[candidate_line];
        assign candidate_current=!candidate_key[KEY_W-1] && !local_inflight_owned[candidate_line] && pending_valid[candidate_line] &&
            pending_first_use[candidate_line]==candidate_first &&
            (!active_valid[candidate_line] || active_refs[candidate_line]==0);
        assign job_current=!local_inflight_owned[job_line] && pending_valid[job_line] && pending_tag[job_line]==job_tag &&
            pending_first_use[job_line]==job_first && (!active_valid[job_line] || active_refs[job_line]==0);
        assign control_done_pending_valid=pending_valid[inflight_line];
        assign control_done_pending_tag=pending_tag[inflight_line];
    end endgenerate

    wire store_fill_ready,store_fill_busy,store_fill_done;
    wire [24:0] store_completed_block;
    wire [31:0] store_completed_ticket;
    wire store_fill_valid=job_hold && job_current && !failed;
    wire fill_accept=store_fill_valid && store_fill_ready;
    wire fill_done_good=store_fill_done && fill_inflight &&
        store_completed_block=={{(25-BLOCK_W){1'b0}},inflight_tag} &&
        store_completed_ticket==inflight_ticket && control_done_pending_valid &&
        control_done_pending_tag==inflight_tag && !failed;
    // Default off. Select a DIFFERENT pending line only while consuming the
    // old, identity-validated completion. OLD job_hold is zero here, so no new
    // fill can accept until the following edge. AREA1 shares control reads and
    // must retain the original mutually exclusive selection/completion phases.
    wire job_done_edge_window=JOB_DONE_EDGE_SELECT && AREA_PROFILE!=1 &&
        fill_done_good && candidate_line!=inflight_line;
    wire job_select_window=inflight_count<2 || fill_done_good;
    quad_parity_prefetch_store #(.SCATTER8(FILL_SCATTER8),.SCATTER16(FILL_SCATTER16),.STREAM_FILL(FILL_STREAM),.WIDTH(WIDTH),.HEIGHT(HEIGHT),.INDEX_BITS(INDEX_BITS),
        .TAG_W(STORE_TAG_W),.TIMEOUT_BITS(TIMEOUT_BITS)) store(
        .clk(clk),.rst_n(rst_n),.abort(local_failed),.in_valid(store_query_valid),.in_ready(store_in_ready),
        .in_x(head_x),.in_y(head_y),
        .in_tag({head_generations,head_lines_packed,head_unique,issued_count[QID_W-1:0],head_tag}),
        .out_valid(store_out_valid),.out_ready(out_ready && retire_identity_ok && retire_lease_ok && !failed),
        .p00(p00),.p10(p10),.p01(p01),.p11(p11),.fx(fx),.fy(fy),.out_tag(store_out_tag),
        .fill_valid(store_fill_valid),.fill_ready(store_fill_ready),.fill_safe(job_current && !failed),
        .fill_base(active_base),.fill_row({{(13-ROW_W){1'b0}},job_row}),
        .fill_col_block({{(13-COL_W){1'b0}},job_col}),.fill_ticket(job_ticket),
        .fill_busy(store_fill_busy),.fill_done(store_fill_done),.completed_block(store_completed_block),
        .completed_ticket(store_completed_ticket),.araddr(araddr),.arlen(arlen),.arvalid(arvalid),.arready(arready),
        .rdata(rdata),.rvalid(rvalid),.rlast(rlast),.rid(rid),.failed(store_failed),.fault(store_fault));

    assign frame_ready=!failed && skid_count==0 && !decoded_valid && fifo_empty && !head_valid &&
        issued_count==retired_count && !store_out_valid && !job_hold && !fill_inflight &&
        !store_fill_busy && !(|pending_valid);
    reg [LINES-1:0] add_active,add_pending,sub_active;
    integer u;
    always @*begin
        add_active=0;add_pending=0;sub_active=0;
        if(scout_commit)for(u=0;u<4;u=u+1)if(first_ref[u])begin
            if(pending_valid[decoded_line[u]])add_pending[decoded_line[u]]=1;
            else if(active_valid[decoded_line[u]] && active_tag[decoded_line[u]]==decoded_block[u])
                add_active[decoded_line[u]]=1;
        end
        if(retire)for(u=0;u<4;u=u+1)if(retire_mask[u])
            sub_active[retire_lines[u*INDEX_BITS+:INDEX_BITS]]=1;
    end
    // AREA_PROFILE2 rewrites only the existing local reference arithmetic.
    // Native Map retained a second carry layer for subtracting sub_active.
    // Encode +1/0/-1 as one modular operand, select publication base first,
    // and use one REF_W-bit adder. Keep old write enables and pub priority.
    wire [REF_W-1:0] area_active_next[0:LINES-1];
    genvar ref_line;
    generate for(ref_line=0;ref_line<LINES;ref_line=ref_line+1)begin: local_ref_alu
        if(AREA_PROFILE==2)begin: single_adder
            wire publishing=fill_done_good && inflight_line==ref_line;
            wire add_one=publishing ? add_pending[ref_line]:add_active[ref_line];
            wire sub_one=!publishing && sub_active[ref_line];
            wire [REF_W-1:0] base_value=publishing ? pending_refs[ref_line]:active_refs[ref_line];
            wire [REF_W-1:0] step={{(REF_W-1){sub_one && !add_one}},add_one^sub_one};
            assign area_active_next[ref_line]=base_value+step;
        end else begin: unused
            assign area_active_next[ref_line]={REF_W{1'b0}};
        end
    end endgenerate
    integer i;
    always @(posedge clk)begin
        if(!rst_n)begin
            local_failed<=0;local_fault<=0;loaded<=0;started<=0;active_base<=0;epoch<=0;idle_age<=0;
            admitted_count<=0;issued_count<=0;retired_count<=0;next_fill_ticket<=1;
            skid_count<=0;skid_rp<=0;skid_wp<=0;decoded_valid<=0;decoded_bounds<=0;head_valid<=0;head_bounds<=0;
            active_valid<=0;pending_valid<=0;active_generation<=0;inflight_count<=0;inflight_rp<=0;inflight_wp<=0;job_hold<=0;
            local_inflight_owned<=0;
            owner_line[0]<=0;owner_line[1]<=0;owner_tag[0]<=0;owner_tag[1]<=0;owner_ticket[0]<=0;owner_ticket[1]<=0;job_line<=0;job_tag<=0;
            job_first<=0;job_row<=0;job_col<=0;job_ticket<=0;
            hits<=0;misses<=0;completed_queries<=0;
        end else if(failed)begin
            // Quarantine never publishes a new generation or result. The port
            // store retains any already asserted AR until its handshake.
            loaded<=0;started<=0;skid_count<=0;decoded_valid<=0;head_valid<=0;
            active_valid<=0;pending_valid<=0;job_hold<=0;
        end else if(accept_frame)begin
            if(!PARAM_OK || frame_base[6:0]!=0 || ({1'b0,frame_base}+WIDTH*HEIGHT/2)>29'h10000000)begin
                local_failed<=1;local_fault<=8'h40;
            end else begin
                loaded<=1;started<=0;active_base<=frame_base;epoch<=epoch+1'b1;idle_age<=0;
                admitted_count<=0;issued_count<=0;retired_count<=0;
                skid_count<=0;skid_rp<=0;skid_wp<=0;decoded_valid<=0;head_valid<=0;
                active_valid<=0;pending_valid<=0;active_generation<=0;job_hold<=0;inflight_count<=0;inflight_rp<=0;inflight_wp<=0;
                local_inflight_owned<=0;
            end
        end else begin
            case({skid_push,decode_load})
                2'b10:skid_count<=skid_count+1'b1;
                2'b01:skid_count<=skid_count-1'b1;
                default:skid_count<=skid_count;
            endcase
            if(skid_push)begin skid_x[skid_wp]<=in_x;skid_y[skid_wp]<=in_y;skid_tag[skid_wp]<=in_tag;skid_wp<=!skid_wp;end
            if(decode_load)begin
                skid_rp<=!skid_rp;decoded_valid<=1;decoded_x<=skid_x[skid_rp];decoded_y<=skid_y[skid_rp];
                decoded_tag<=skid_tag[skid_rp];decoded_bounds<=incoming_bounds;
                for(i=0;i<4;i=i+1)begin
                    decoded_block[i]<=incoming_block[i];decoded_line[i]<=incoming_line[i];
                    decoded_row[i]<=incoming_row[i];decoded_col[i]<=incoming_col[i];
                end
            end else if(scout_commit)decoded_valid<=0;
            if(head_load)begin
                head_valid<=1;head_x<=fifo_head_x;head_y<=fifo_head_y;
                head_tag<=fifo_head_tag;head_bounds<=next_head_bounds;
                for(i=0;i<4;i=i+1)begin head_block[i]<=next_head_block[i];head_line[i]<=next_head_line[i];end
            end else if(store_query_accept)head_valid<=0;
            if(store_query_accept)issued_count<=issued_count+1'b1;
            if(retire)begin retired_count<=retired_count+1'b1;completed_queries<=completed_queries+1'b1;end
            // Prefill creates the actual horizon. Short transactions and A/B/A
            // must not deadlock waiting to reach the lookahead threshold.
            if(in_valid || skid_count!=0 || decoded_valid)idle_age<=0;
            else if(!started && admitted_count!=0 && idle_age<255)idle_age<=idle_age+1'b1;
            if(!started && (admitted_count>=LOOKAHEAD || generation_blocked || frame_valid ||
                (admitted_count!=0 && idle_age>=IDLE_FLUSH_CYCLES)))started<=1;
            if(!job_hold && job_select_window && candidate_current)begin
                job_hold<=1;job_line<=candidate_line;job_tag<=control_pending_tag;
                job_first<=candidate_first;job_row<=control_row;job_col<=control_col;
                job_ticket<=next_fill_ticket;
            end
            // FIFO acceptance order is also scatter/completion order. Full
            // tickets and directory generations keep their original meaning.
            case({fill_accept,fill_done_good})
                2'b10:inflight_count<=inflight_count+1'b1;
                2'b01:inflight_count<=inflight_count-1'b1;
                default:inflight_count<=inflight_count;
            endcase
            // Merge per-line set/clear; completing the old owner cannot erase
            // a different lease accepted on the same edge.
            for(i=0;i<LINES;i=i+1)
                local_inflight_owned[i]<=(local_inflight_owned[i] &&
                    !(fill_done_good && inflight_line==i)) || (fill_accept && job_line==i);
            if(fill_accept)begin
                owner_line[inflight_wp]<=job_line;owner_tag[inflight_wp]<=job_tag;
                owner_ticket[inflight_wp]<=job_ticket;inflight_wp<=!inflight_wp;
                job_hold<=0;next_fill_ticket<=next_fill_ticket+1'b1;active_valid[job_line]<=0;
            end
            if(fill_done_good)begin
                inflight_rp<=!inflight_rp;
                active_valid[inflight_line]<=1;active_tag[inflight_line]<=inflight_tag;
                active_generation[inflight_line]<=!active_generation[inflight_line];pending_valid[inflight_line]<=0;
            end
            // Unique-per-query references bound a line's count by the total
            // outstanding tokens: QUERY_DEPTH + head1 + store5 < DEPTH+16.
            // Same-edge pending join/publish and active add/retire are merged.
            for(i=0;i<LINES;i=i+1)begin
                if(AREA_PROFILE==2)begin
                    if((fill_done_good && inflight_line==i) ||
                        (active_valid[i] && (add_active[i] || sub_active[i])))
                        active_refs[i]<=area_active_next[i];
                end else begin
                    if(fill_done_good && inflight_line==i)
                        active_refs[i]<=pending_refs[i]+add_pending[i];
                    else if(active_valid[i] && (add_active[i] || sub_active[i]))
                        active_refs[i]<=active_refs[i]+add_active[i]-sub_active[i];
                end
                if(add_pending[i])pending_refs[i]<=pending_refs[i]+1'b1;
            end
            if(scout_commit)begin
                admitted_count<=admitted_count+1'b1;hits<=hits+hit_inc;misses<=misses+miss_inc;
                for(i=0;i<4;i=i+1)if(first_ref[i])begin
                    if(!pending_valid[decoded_line[i]] && !(active_valid[decoded_line[i]] &&
                        active_tag[decoded_line[i]]==decoded_block[i]))begin
                        pending_valid[decoded_line[i]]<=1;pending_tag[decoded_line[i]]<=decoded_block[i];
                        pending_first_use[decoded_line[i]]<=admitted_count[QID_W-1:0];
                        pending_refs[decoded_line[i]]<=1;
                        pending_row[decoded_line[i]]<=decoded_row[i];pending_col[decoded_line[i]]<=decoded_col[i];
                    end
                end
            end
            if(decoded_valid && admitted_count[QID_W])begin local_failed<=1;local_fault<=8'h45;end
            if(head_valid && !(&has_request))begin local_failed<=1;local_fault<=8'h46;end
            if(store_out_valid && !retire_identity_ok)begin local_failed<=1;local_fault<=8'h43;end
            if(store_out_valid && !retire_lease_ok)begin local_failed<=1;local_fault<=8'h48;end
            if(store_fill_done && !fill_done_good)begin local_failed<=1;local_fault<=8'h42;end
            if(job_hold && !job_current)begin local_failed<=1;local_fault<=8'h47;end
        end
    end
endmodule

`else
`timescale 1ns/1ps
// Independent complete runtime-cache candidate. No oracle/lifetime table is
// used. One active and one pending generation per line; a third generation
// stalls the scout atomically while the earlier foreground prefix drains.
// A pending victim lease is granted only after all old-generation references
// admitted to the query FIFO have been externally consumed. Per-generation
// references are counted at scout admission, not just foreground issue.
// Full qids still check output order; FIFO pointers never identify leases.
// DDR reset must be
// coordinated: this UI has no response epoch/transaction-ID output on AR.
module d256_runtime_prefetch_cache #(
    parameter WIDTH=1920,HEIGHT=1080,INDEX_BITS=7,TAG_W=24,
    QUERY_DEPTH=256,LOOKAHEAD=QUERY_DEPTH,IDLE_FLUSH_CYCLES=16,TIMEOUT_BITS=16,COMPACT_COORDS=0,AREA_PROFILE=0,CANDIDATE_KEY_PIPE=0,HEAD_PREDECODE=0,LOCAL_INFLIGHT_MASK=0,FILL_SCATTER16=0,FILL_STREAM=0,FILL_SCATTER8=0,JOB_DONE_EDGE_SELECT=0
)(
    input clk,rst_n,
    input frame_valid,output wire frame_ready,input [27:0] frame_base,
    input in_valid,output wire in_ready,input signed [23:0] in_x,in_y,
    input [TAG_W-1:0] in_tag,
    output wire out_valid,input out_ready,output wire [23:0] p00,p10,p01,p11,
    output wire [7:0] fx,fy,output wire [TAG_W-1:0] out_tag,
    output wire [27:0] araddr,output wire [3:0] arlen,output wire arvalid,input arready,
    input [255:0] rdata,input rvalid,rlast,input [3:0] rid,
    output wire failed,output wire [7:0] fault,
    output reg [31:0] hits,misses,completed_queries
);
    localparam LINES=1<<INDEX_BITS,BPR=WIDTH/128,QID_W=24;
    localparam BLOCK_W=$clog2(WIDTH*HEIGHT/128)<1 ? 1:$clog2(WIDTH*HEIGHT/128);
    localparam ROW_W=$clog2(HEIGHT)<1 ? 1:$clog2(HEIGHT);
    localparam COL_W=$clog2(BPR)<1 ? 1:$clog2(BPR);
    localparam REF_W=$clog2(QUERY_DEPTH+16),LEASE_W=8+4*INDEX_BITS;
    localparam X_INT_W=$clog2(WIDTH+2),Y_INT_W=$clog2(HEIGHT+2);
    localparam X_COORD_W=8+X_INT_W,Y_COORD_W=8+Y_INT_W;
    localparam FIFO_COORD_W=COMPACT_COORDS ? X_COORD_W+Y_COORD_W:48;
    localparam BASE_TOKEN_W=FIFO_COORD_W+TAG_W;
    localparam HEAD_META_W=4+4*INDEX_BITS+2*BLOCK_W+1;
    localparam TOKEN_W=BASE_TOKEN_W+(HEAD_PREDECODE ? HEAD_META_W:0),STORE_TAG_W=TAG_W+QID_W+LEASE_W;
    localparam KEY_W=1+QID_W+INDEX_BITS,GROUPS=(LINES+7)/8;
    localparam PARAM_OK=WIDTH>=128 && WIDTH<=8192 && WIDTH%128==0 && HEIGHT>=2 && HEIGHT<=8192 &&
        WIDTH*HEIGHT<=16777216 && INDEX_BITS>=2 && INDEX_BITS<=10 && QUERY_DEPTH>=8 &&
        (QUERY_DEPTH&(QUERY_DEPTH-1))==0 && LOOKAHEAD>=1 && LOOKAHEAD<=QUERY_DEPTH &&
        IDLE_FLUSH_CYCLES>=1 && IDLE_FLUSH_CYCLES<=255;
    reg local_failed,loaded,started;
    reg [7:0] local_fault,idle_age;
    reg [27:0] active_base;
    reg [31:0] epoch,next_fill_ticket;
    reg [QID_W:0] admitted_count,issued_count,retired_count;
    wire store_failed;wire [7:0] store_fault;
    assign failed=local_failed || store_failed;
    assign fault=local_failed ? local_fault:store_fault;
    wire accept_frame=frame_valid && frame_ready;

    reg [LINES-1:0] active_valid,pending_valid,active_generation;
    reg [BLOCK_W-1:0] active_tag[0:LINES-1],pending_tag[0:LINES-1];
    reg [REF_W-1:0] active_refs[0:LINES-1],pending_refs[0:LINES-1];
    reg [QID_W-1:0] pending_first_use[0:LINES-1];
    reg [ROW_W-1:0] pending_row[0:LINES-1];
    reg [COL_W-1:0] pending_col[0:LINES-1];

    // No coordinate/directory decision feeds the external ready boundary.
    reg [1:0] skid_count;
    reg skid_rp,skid_wp;
    reg signed [23:0] skid_x[0:1],skid_y[0:1];
    reg [TAG_W-1:0] skid_tag[0:1];
    assign in_ready=loaded && !frame_valid && !failed && skid_count<2;
    wire skid_push=in_valid && in_ready;
    reg decoded_valid;
    reg signed [23:0] decoded_x,decoded_y;
    reg [TAG_W-1:0] decoded_tag;
    reg [3:0] decoded_bounds;
    reg [BLOCK_W-1:0] decoded_block[0:3];
    reg [INDEX_BITS-1:0] decoded_line[0:3];
    reg [ROW_W-1:0] decoded_row[0:3];
    reg [COL_W-1:0] decoded_col[0:3];
    wire [3:0] incoming_bounds;
    wire [BLOCK_W-1:0] incoming_block[0:3];
    wire [INDEX_BITS-1:0] incoming_line[0:3];
    wire [ROW_W-1:0] incoming_row[0:3];
    wire [COL_W-1:0] incoming_col[0:3];
    genvar n;
    generate for(n=0;n<4;n=n+1)begin: scout_decode
        wire signed [16:0] x=$signed(skid_x[skid_rp][23:8])+(n%2);
        wire signed [16:0] y=$signed(skid_y[skid_rp][23:8])+(n/2);
        wire [31:0] local_line=(y>>>1)*BPR+(x>>>7);
        assign incoming_bounds[n]=x>=0 && x<WIDTH && y>=0 && y<HEIGHT;
        assign incoming_block[n]=y*BPR+(x>>>7);
        assign incoming_line[n]={y[0],local_line[INDEX_BITS-2:0]};
        assign incoming_row[n]=y[ROW_W-1:0];
        assign incoming_col[n]=x>>>7;
    end endgenerate
    reg generations_ok;
    reg [3:0] first_ref,new_ref;
    reg [2:0] inbound_inc,miss_inc,hit_inc;
    integer a,b;
    always @*begin
        generations_ok=1;first_ref=0;new_ref=0;inbound_inc=0;miss_inc=0;
        for(a=0;a<4;a=a+1)begin
            if(decoded_bounds[a])begin
                inbound_inc=inbound_inc+1'b1;first_ref[a]=1;
                for(b=0;b<a;b=b+1)
                    if(decoded_bounds[b] && decoded_block[b]==decoded_block[a])first_ref[a]=0;
                if(pending_valid[decoded_line[a]])begin
                    if(pending_tag[decoded_line[a]]!=decoded_block[a])generations_ok=0;
                end else if(first_ref[a] && !(active_valid[decoded_line[a]] &&
                    active_tag[decoded_line[a]]==decoded_block[a]))begin
                    new_ref[a]=1;miss_inc=miss_inc+1'b1;
                end
            end
        end
        hit_inc=inbound_inc-miss_inc;
    end
    wire fifo_in_ready,fifo_out_valid,fifo_out_ready,fifo_empty;
    wire [TOKEN_W-1:0] fifo_out_data,fifo_in_data;
    wire [BASE_TOKEN_W-1:0] fifo_payload;
    wire signed [23:0] fifo_head_x,fifo_head_y;
    wire [TAG_W-1:0] fifo_head_tag;
    // Exact useful integer range[-1,limit-1], original frac8 and user tag.
    // -1 uses the all-ones integer code. Far-OOB uses all-ones-minus1,
    // which is >=limit because 2**INT_W>=limit+2. Restore -1 with sign
    // extension and every other code with zero extension; no bias adders.
    // Invalid-axis coordinates are semantically canonicalized, not raw-lossless.
    generate if(COMPACT_COORDS)begin: compact_coords_codec
        wire signed [16:0] integer_x=$signed(decoded_x[23:8]);
        wire signed [16:0] integer_y=$signed(decoded_y[23:8]);
        localparam [X_INT_W-1:0] X_FAR={X_INT_W{1'b1}}-1'b1;
        localparam [Y_INT_W-1:0] Y_FAR={Y_INT_W{1'b1}}-1'b1;
        wire [X_INT_W-1:0] code_x=(integer_x>=-1 && integer_x<WIDTH) ?
            decoded_x[8+:X_INT_W]:X_FAR;
        wire [Y_INT_W-1:0] code_y=(integer_y>=-1 && integer_y<HEIGHT) ?
            decoded_y[8+:Y_INT_W]:Y_FAR;
        wire [X_INT_W-1:0] head_code_x=fifo_out_data[8+:X_INT_W];
        wire [Y_INT_W-1:0] head_code_y=fifo_out_data[X_COORD_W+8+:Y_INT_W];
        wire head_negative_x=&head_code_x,head_negative_y=&head_code_y;
        assign fifo_payload={decoded_tag,code_y,decoded_y[7:0],code_x,decoded_x[7:0]};
        assign fifo_head_x={{(16-X_INT_W){head_negative_x}},head_code_x,fifo_out_data[7:0]};
        assign fifo_head_y={{(16-Y_INT_W){head_negative_y}},head_code_y,fifo_out_data[X_COORD_W+:8]};
    end else begin: legacy_coords_codec
        assign fifo_payload={decoded_tag,decoded_y,decoded_x};
        assign fifo_head_x=fifo_out_data[23:0];
        assign fifo_head_y=fifo_out_data[47:24];
    end endgenerate
    // The low coordinate/tag payload and its timing are unchanged. The
    // descriptor comes from the same decoded registers and scout_commit as
    // the lease admission, so no extra token or outstanding stage is added.
    generate if(HEAD_PREDECODE)begin: pack_head_descriptor
        assign fifo_in_data={decoded_bounds,decoded_line[3],decoded_line[2],decoded_line[1],decoded_line[0],
            decoded_block[2],decoded_block[0],(&decoded_x[14:8]),fifo_payload};
    end else begin: original_fifo_payload
        assign fifo_in_data=fifo_payload;
    end endgenerate
    assign fifo_head_tag=fifo_out_data[FIFO_COORD_W+:TAG_W];
    wire scout_commit=decoded_valid && generations_ok && fifo_in_ready &&
        !admitted_count[QID_W] && !failed;
    wire generation_blocked=decoded_valid && !generations_ok && !failed;
    wire decode_load=skid_count!=0 && (!decoded_valid || scout_commit) && !failed;
    sync_token_fifo #(.WIDTH(TOKEN_W),.DEPTH(QUERY_DEPTH)) query_fifo(
        .clk(clk),.rst_n(rst_n),.clear(accept_frame || failed),
        .in_valid(scout_commit),.in_ready(fifo_in_ready),.in_data(fifo_in_data),
        .out_valid(fifo_out_valid),.out_ready(fifo_out_ready),.out_data(fifo_out_data),.empty(fifo_empty));

    // A registered foreground decode separates arithmetic from directory/tag
    // lookup. Head references never migrate to a newer directory generation.
    reg head_valid;
    reg signed [23:0] head_x,head_y;
    reg [TAG_W-1:0] head_tag;
    reg [3:0] head_bounds;
    reg [BLOCK_W-1:0] head_block[0:3];
    reg [INDEX_BITS-1:0] head_line[0:3];
    wire [3:0] next_head_bounds;
    wire [BLOCK_W-1:0] next_head_block[0:3];
    wire [INDEX_BITS-1:0] next_head_line[0:3];
    generate if(HEAD_PREDECODE)begin: fifo_head_descriptor
        wire cross_block=fifo_out_data[BASE_TOKEN_W];
        wire [BLOCK_W-1:0] top_block=fifo_out_data[BASE_TOKEN_W+1+:BLOCK_W];
        wire [BLOCK_W-1:0] bottom_block=fifo_out_data[BASE_TOKEN_W+1+BLOCK_W+:BLOCK_W];
        assign next_head_bounds=fifo_out_data[BASE_TOKEN_W+1+2*BLOCK_W+4*INDEX_BITS+:4];
        for(n=0;n<4;n=n+1)begin: neighbour
            assign next_head_line[n]=fifo_out_data[BASE_TOKEN_W+1+2*BLOCK_W+n*INDEX_BITS+:INDEX_BITS];
            if(n%2==0)begin: left
                assign next_head_block[n]=(n/2==0) ? top_block:bottom_block;
            end else begin: right
                assign next_head_block[n]=((n/2==0) ? top_block:bottom_block)+cross_block;
            end
        end
    end else begin: original_head_math
        for(n=0;n<4;n=n+1)begin: head_decode
            wire signed [16:0] x=$signed(fifo_head_x[23:8])+(n%2);
            wire signed [16:0] y=$signed(fifo_head_y[23:8])+(n/2);
            wire [31:0] local_line=(y>>>1)*BPR+(x>>>7);
            assign next_head_bounds[n]=x>=0 && x<WIDTH && y>=0 && y<HEIGHT;
            assign next_head_block[n]=y*BPR+(x>>>7);
            assign next_head_line[n]={y[0],local_line[INDEX_BITS-2:0]};
        end
    end endgenerate
    wire [3:0] resident,has_request;
    generate for(n=0;n<4;n=n+1)begin: head_directory
        assign resident[n]=!head_bounds[n] || (active_valid[head_line[n]] &&
            active_tag[head_line[n]]==head_block[n]);
        assign has_request[n]=resident[n] || (pending_valid[head_line[n]] &&
            pending_tag[head_line[n]]==head_block[n]);
    end endgenerate
    wire all_resident=&resident;
    wire demand_blocked=head_valid && !all_resident && !failed;
    wire store_in_ready,store_out_valid;
    wire [STORE_TAG_W-1:0] store_out_tag;
    wire store_query_valid=head_valid && started && all_resident && !failed;
    wire store_query_accept=store_query_valid && store_in_ready;
    assign fifo_out_ready=(!head_valid || store_query_accept) && !failed;
    wire head_load=fifo_out_valid && fifo_out_ready;
    wire retire_identity_ok=store_out_tag[TAG_W+:QID_W]==retired_count[QID_W-1:0];
    reg [3:0] head_unique;
    wire [3:0] head_generations;
    wire [4*INDEX_BITS-1:0] head_lines_packed;
    integer h,z;
    always @*begin
        head_unique=head_bounds;
        for(h=0;h<4;h=h+1)for(z=0;z<h;z=z+1)
            if(head_bounds[h] && head_bounds[z] && head_block[h]==head_block[z])head_unique[h]=0;
    end
    generate for(n=0;n<4;n=n+1)begin: pack_leases
        assign head_generations[n]=active_generation[head_line[n]];
        assign head_lines_packed[n*INDEX_BITS+:INDEX_BITS]=head_line[n];
    end endgenerate
    wire [3:0] retire_mask=store_out_tag[TAG_W+QID_W+:4];
    wire [4*INDEX_BITS-1:0] retire_lines=store_out_tag[TAG_W+QID_W+4+:4*INDEX_BITS];
    wire [3:0] retire_generations=store_out_tag[TAG_W+QID_W+4+4*INDEX_BITS+:4];
    reg retire_lease_ok;
    integer r;
    reg [INDEX_BITS-1:0] lease_line;
    always @*begin
        retire_lease_ok=1;lease_line=0;
        for(r=0;r<4;r=r+1)if(retire_mask[r])begin
            lease_line=retire_lines[r*INDEX_BITS+:INDEX_BITS];
            if(!active_valid[lease_line] || active_refs[lease_line]==0 ||
                active_generation[lease_line]!=retire_generations[r])retire_lease_ok=0;
        end
    end
    assign out_valid=store_out_valid && retire_identity_ok && retire_lease_ok && !failed;
    assign out_tag=store_out_tag[TAG_W-1:0];
    wire retire=out_valid && out_ready;

    // Oldest eligible pending generation. Balanced8-leaf tournaments register
    // before a balanced group merge; there is no linear128-comparator chain.
    wire [KEY_W-1:0] invalid_key={KEY_W{1'b1}};
    wire [KEY_W-1:0] leaves[0:LINES-1];
    reg [KEY_W-1:0] group_keys[0:GROUPS-1];
    reg fill_inflight,job_hold;
    // Optional exact duplicate of the existing binary inflight owner. Each
    // bit is sampled at the ORIGINAL fill_accept edge, never a cycle later.
    // Fault quarantine holds both representations; reset/valid frame/done
    // clear them at the same original priority points below.
    reg [LINES-1:0] local_inflight_owned;
    reg [INDEX_BITS-1:0] inflight_line,job_line;
    reg [BLOCK_W-1:0] inflight_tag,job_tag;
    reg [QID_W-1:0] job_first;
    reg [ROW_W-1:0] job_row;
    reg [COL_W-1:0] job_col;
    reg [31:0] inflight_ticket,job_ticket;
    genvar d,g,k,j;
    generate for(d=0;d<LINES;d=d+1)begin: eligible
        wire ok=pending_valid[d] && (!active_valid[d] || active_refs[d]==0) &&
            !(LOCAL_INFLIGHT_MASK ? local_inflight_owned[d]:
                (fill_inflight && inflight_line==d));
        assign leaves[d]=ok ? {1'b0,pending_first_use[d],d[INDEX_BITS-1:0]}:invalid_key;
    end endgenerate
    generate for(g=0;g<GROUPS;g=g+1)begin: grouped_minimum
        wire [KEY_W-1:0] tree[1:15];
        for(k=0;k<8;k=k+1)begin: leaf
            if(g*8+k<LINES)assign tree[8+k]=leaves[g*8+k];
            else assign tree[8+k]=invalid_key;
        end
        for(j=1;j<8;j=j+1)begin: merge
            assign tree[j]=tree[j*2]<=tree[j*2+1] ? tree[j*2]:tree[j*2+1];
        end
        always @(posedge clk)
            if(!rst_n || accept_frame || failed)group_keys[g]<=invalid_key;
            else group_keys[g]<=tree[1];
    end endgenerate
    wire [KEY_W-1:0] merged[1:2*GROUPS-1];
    generate for(g=0;g<GROUPS;g=g+1)begin: merge_leaf
        assign merged[GROUPS+g]=group_keys[g];
    end endgenerate
    generate for(j=1;j<GROUPS;j=j+1)begin: merge_groups
        assign merged[j]=merged[j*2]<=merged[j*2+1] ? merged[j*2]:merged[j*2+1];
    end endgenerate
    // Optional balanced control-only pipeline. Query data/DDR/store stages
    // and every live lease/identity/fault revalidation remain unchanged.
    wire [KEY_W-1:0] candidate_key;
    generate if(CANDIDATE_KEY_PIPE==2)begin: registered_selection
        localparam MID_COUNT=GROUPS>=4 ? 4:1;
        reg [KEY_W-1:0] mid_key[0:MID_COUNT-1];
        reg [KEY_W-1:0] root_key;
        wire [KEY_W-1:0] upper[1:2*MID_COUNT-1];
        genvar m,t;
        for(m=0;m<MID_COUNT;m=m+1)begin: mid_stage
            always @(posedge clk)
                if(!rst_n || accept_frame || failed)mid_key[m]<=invalid_key;
                else mid_key[m]<=merged[MID_COUNT+m];
            assign upper[MID_COUNT+m]=mid_key[m];
        end
        for(t=1;t<MID_COUNT;t=t+1)begin: upper_min
            assign upper[t]=upper[t*2]<=upper[t*2+1] ? upper[t*2]:upper[t*2+1];
        end
        always @(posedge clk)
            if(!rst_n || accept_frame || failed)root_key<=invalid_key;
            else root_key<=upper[1];
        assign candidate_key=root_key;
    end else begin: original_selection
        assign candidate_key=merged[1];
    end endgenerate
    wire [INDEX_BITS-1:0] candidate_line=candidate_key[INDEX_BITS-1:0];
    wire [QID_W-1:0] candidate_first=candidate_key[INDEX_BITS+:QID_W];
    // One physical control-directory read is sufficient in mutually exclusive
    // scheduler phases. No pipeline/state/depth or full-QID width changes.
    // Payload/scout/head/retire read ports remain separate and unchanged.
    wire control_pending_valid,control_active_valid;
    wire [REF_W-1:0] control_active_refs;
    wire [BLOCK_W-1:0] control_pending_tag;
    wire [QID_W-1:0] control_first;
    wire [ROW_W-1:0] control_row;
    wire [COL_W-1:0] control_col;
    wire candidate_current;
    wire job_current;
    wire control_done_pending_valid;
    wire [BLOCK_W-1:0] control_done_pending_tag;
    generate if(AREA_PROFILE==1)begin: shared_control_read
        wire [INDEX_BITS-1:0] read_line=job_hold ? job_line:
            fill_inflight ? inflight_line:candidate_line;
        assign control_pending_valid=pending_valid[read_line];
        assign control_active_valid=active_valid[read_line];
        assign control_active_refs=active_refs[read_line];
        assign control_pending_tag=pending_tag[read_line];
        assign control_first=pending_first_use[read_line];
        assign control_row=pending_row[read_line];
        assign control_col=pending_col[read_line];
        // candidate_current is consumed only with !job_hold&&!fill_inflight;
        // job_current only by job_hold-guarded fill/guard paths. fill_safe can
        // vary outside a valid job: the store uses it only in fill_ready and
        // accepts a fill only with fill_valid, which itself requires job_hold.
        assign candidate_current=!candidate_key[KEY_W-1] && control_pending_valid &&
            control_first==candidate_first && (!control_active_valid || control_active_refs==0);
        assign job_current=control_pending_valid && control_pending_tag==job_tag &&
            control_first==job_first && (!control_active_valid || control_active_refs==0);
        assign control_done_pending_valid=control_pending_valid;
        assign control_done_pending_tag=control_pending_tag;
    end else begin: original_control_reads
        assign control_pending_valid=pending_valid[candidate_line];
        assign control_active_valid=active_valid[candidate_line];
        assign control_active_refs=active_refs[candidate_line];
        assign control_pending_tag=pending_tag[candidate_line];
        assign control_first=pending_first_use[candidate_line];
        assign control_row=pending_row[candidate_line];
        assign control_col=pending_col[candidate_line];
        assign candidate_current=!candidate_key[KEY_W-1] && pending_valid[candidate_line] &&
            pending_first_use[candidate_line]==candidate_first &&
            (!active_valid[candidate_line] || active_refs[candidate_line]==0);
        assign job_current=pending_valid[job_line] && pending_tag[job_line]==job_tag &&
            pending_first_use[job_line]==job_first && (!active_valid[job_line] || active_refs[job_line]==0);
        assign control_done_pending_valid=pending_valid[inflight_line];
        assign control_done_pending_tag=pending_tag[inflight_line];
    end endgenerate

    wire store_fill_ready,store_fill_busy,store_fill_done;
    wire [24:0] store_completed_block;
    wire [31:0] store_completed_ticket;
    wire store_fill_valid=job_hold && job_current && !failed;
    wire fill_accept=store_fill_valid && store_fill_ready;
    wire fill_done_good=store_fill_done && fill_inflight &&
        store_completed_block=={{(25-BLOCK_W){1'b0}},inflight_tag} &&
        store_completed_ticket==inflight_ticket && control_done_pending_valid &&
        control_done_pending_tag==inflight_tag && !failed;
    // Default off. Select a DIFFERENT pending line only while consuming the
    // old, identity-validated completion. OLD job_hold is zero here, so no new
    // fill can accept until the following edge. AREA1 shares control reads and
    // must retain the original mutually exclusive selection/completion phases.
    wire job_done_edge_window=JOB_DONE_EDGE_SELECT && AREA_PROFILE!=1 &&
        fill_done_good && candidate_line!=inflight_line;
    wire job_select_window=!fill_inflight || job_done_edge_window;
    quad_parity_prefetch_store #(.SCATTER8(FILL_SCATTER8),.SCATTER16(FILL_SCATTER16),.STREAM_FILL(FILL_STREAM),.WIDTH(WIDTH),.HEIGHT(HEIGHT),.INDEX_BITS(INDEX_BITS),
        .TAG_W(STORE_TAG_W),.TIMEOUT_BITS(TIMEOUT_BITS)) store(
        .clk(clk),.rst_n(rst_n),.in_valid(store_query_valid),.in_ready(store_in_ready),
        .in_x(head_x),.in_y(head_y),
        .in_tag({head_generations,head_lines_packed,head_unique,issued_count[QID_W-1:0],head_tag}),
        .out_valid(store_out_valid),.out_ready(out_ready && retire_identity_ok && retire_lease_ok && !failed),
        .p00(p00),.p10(p10),.p01(p01),.p11(p11),.fx(fx),.fy(fy),.out_tag(store_out_tag),
        .fill_valid(store_fill_valid),.fill_ready(store_fill_ready),.fill_safe(job_current && !failed),
        .fill_base(active_base),.fill_row({{(13-ROW_W){1'b0}},job_row}),
        .fill_col_block({{(13-COL_W){1'b0}},job_col}),.fill_ticket(job_ticket),
        .fill_busy(store_fill_busy),.fill_done(store_fill_done),.completed_block(store_completed_block),
        .completed_ticket(store_completed_ticket),.araddr(araddr),.arlen(arlen),.arvalid(arvalid),.arready(arready),
        .rdata(rdata),.rvalid(rvalid),.rlast(rlast),.rid(rid),.failed(store_failed),.fault(store_fault));

    assign frame_ready=!failed && skid_count==0 && !decoded_valid && fifo_empty && !head_valid &&
        issued_count==retired_count && !store_out_valid && !job_hold && !fill_inflight &&
        !store_fill_busy && !(|pending_valid);
    reg [LINES-1:0] add_active,add_pending,sub_active;
    integer u;
    always @*begin
        add_active=0;add_pending=0;sub_active=0;
        if(scout_commit)for(u=0;u<4;u=u+1)if(first_ref[u])begin
            if(pending_valid[decoded_line[u]])add_pending[decoded_line[u]]=1;
            else if(active_valid[decoded_line[u]] && active_tag[decoded_line[u]]==decoded_block[u])
                add_active[decoded_line[u]]=1;
        end
        if(retire)for(u=0;u<4;u=u+1)if(retire_mask[u])
            sub_active[retire_lines[u*INDEX_BITS+:INDEX_BITS]]=1;
    end
    // AREA_PROFILE2 rewrites only the existing local reference arithmetic.
    // Native Map retained a second carry layer for subtracting sub_active.
    // Encode +1/0/-1 as one modular operand, select publication base first,
    // and use one REF_W-bit adder. Keep old write enables and pub priority.
    wire [REF_W-1:0] area_active_next[0:LINES-1];
    genvar ref_line;
    generate for(ref_line=0;ref_line<LINES;ref_line=ref_line+1)begin: local_ref_alu
        if(AREA_PROFILE==2)begin: single_adder
            wire publishing=fill_done_good && inflight_line==ref_line;
            wire add_one=publishing ? add_pending[ref_line]:add_active[ref_line];
            wire sub_one=!publishing && sub_active[ref_line];
            wire [REF_W-1:0] base_value=publishing ? pending_refs[ref_line]:active_refs[ref_line];
            wire [REF_W-1:0] step={{(REF_W-1){sub_one && !add_one}},add_one^sub_one};
            assign area_active_next[ref_line]=base_value+step;
        end else begin: unused
            assign area_active_next[ref_line]={REF_W{1'b0}};
        end
    end endgenerate
    integer i;
    always @(posedge clk)begin
        if(!rst_n)begin
            local_failed<=0;local_fault<=0;loaded<=0;started<=0;active_base<=0;epoch<=0;idle_age<=0;
            admitted_count<=0;issued_count<=0;retired_count<=0;next_fill_ticket<=1;
            skid_count<=0;skid_rp<=0;skid_wp<=0;decoded_valid<=0;decoded_bounds<=0;head_valid<=0;head_bounds<=0;
            active_valid<=0;pending_valid<=0;active_generation<=0;fill_inflight<=0;job_hold<=0;
            if(LOCAL_INFLIGHT_MASK)local_inflight_owned<=0;
            inflight_line<=0;inflight_tag<=0;inflight_ticket<=0;job_line<=0;job_tag<=0;
            job_first<=0;job_row<=0;job_col<=0;job_ticket<=0;
            hits<=0;misses<=0;completed_queries<=0;
        end else if(failed)begin
            // Quarantine never publishes a new generation or result. The port
            // store retains any already asserted AR until its handshake.
            loaded<=0;started<=0;skid_count<=0;decoded_valid<=0;head_valid<=0;
            active_valid<=0;pending_valid<=0;job_hold<=0;
        end else if(accept_frame)begin
            if(!PARAM_OK || frame_base[6:0]!=0 || ({1'b0,frame_base}+WIDTH*HEIGHT/2)>29'h10000000)begin
                local_failed<=1;local_fault<=8'h40;
            end else begin
                loaded<=1;started<=0;active_base<=frame_base;epoch<=epoch+1'b1;idle_age<=0;
                admitted_count<=0;issued_count<=0;retired_count<=0;
                skid_count<=0;skid_rp<=0;skid_wp<=0;decoded_valid<=0;head_valid<=0;
                active_valid<=0;pending_valid<=0;active_generation<=0;job_hold<=0;fill_inflight<=0;
                if(LOCAL_INFLIGHT_MASK)local_inflight_owned<=0;
            end
        end else begin
            case({skid_push,decode_load})
                2'b10:skid_count<=skid_count+1'b1;
                2'b01:skid_count<=skid_count-1'b1;
                default:skid_count<=skid_count;
            endcase
            if(skid_push)begin skid_x[skid_wp]<=in_x;skid_y[skid_wp]<=in_y;skid_tag[skid_wp]<=in_tag;skid_wp<=!skid_wp;end
            if(decode_load)begin
                skid_rp<=!skid_rp;decoded_valid<=1;decoded_x<=skid_x[skid_rp];decoded_y<=skid_y[skid_rp];
                decoded_tag<=skid_tag[skid_rp];decoded_bounds<=incoming_bounds;
                for(i=0;i<4;i=i+1)begin
                    decoded_block[i]<=incoming_block[i];decoded_line[i]<=incoming_line[i];
                    decoded_row[i]<=incoming_row[i];decoded_col[i]<=incoming_col[i];
                end
            end else if(scout_commit)decoded_valid<=0;
            if(head_load)begin
                head_valid<=1;head_x<=fifo_head_x;head_y<=fifo_head_y;
                head_tag<=fifo_head_tag;head_bounds<=next_head_bounds;
                for(i=0;i<4;i=i+1)begin head_block[i]<=next_head_block[i];head_line[i]<=next_head_line[i];end
            end else if(store_query_accept)head_valid<=0;
            if(store_query_accept)issued_count<=issued_count+1'b1;
            if(retire)begin retired_count<=retired_count+1'b1;completed_queries<=completed_queries+1'b1;end
            // Prefill creates the actual horizon. Short transactions and A/B/A
            // must not deadlock waiting to reach the lookahead threshold.
            if(in_valid || skid_count!=0 || decoded_valid)idle_age<=0;
            else if(!started && admitted_count!=0 && idle_age<255)idle_age<=idle_age+1'b1;
            if(!started && (admitted_count>=LOOKAHEAD || generation_blocked || frame_valid ||
                (admitted_count!=0 && idle_age>=IDLE_FLUSH_CYCLES)))started<=1;
            if(!job_hold && job_select_window && !store_fill_busy && candidate_current)begin
                job_hold<=1;job_line<=candidate_line;job_tag<=control_pending_tag;
                job_first<=candidate_first;job_row<=control_row;job_col<=control_col;
                job_ticket<=next_fill_ticket;
            end
            if(fill_accept)begin
                if(LOCAL_INFLIGHT_MASK)for(i=0;i<LINES;i=i+1)
                    local_inflight_owned[i]<=(job_line==i);
                job_hold<=0;fill_inflight<=1;inflight_line<=job_line;inflight_tag<=job_tag;
                inflight_ticket<=job_ticket;next_fill_ticket<=next_fill_ticket+1'b1;active_valid[job_line]<=0;
            end
            if(fill_done_good)begin
                if(LOCAL_INFLIGHT_MASK)local_inflight_owned<=0;
                fill_inflight<=0;active_valid[inflight_line]<=1;active_tag[inflight_line]<=inflight_tag;
                active_generation[inflight_line]<=!active_generation[inflight_line];pending_valid[inflight_line]<=0;
            end
            // Unique-per-query references bound a line's count by the total
            // outstanding tokens: QUERY_DEPTH + head1 + store5 < DEPTH+16.
            // Same-edge pending join/publish and active add/retire are merged.
            for(i=0;i<LINES;i=i+1)begin
                if(AREA_PROFILE==2)begin
                    if((fill_done_good && inflight_line==i) ||
                        (active_valid[i] && (add_active[i] || sub_active[i])))
                        active_refs[i]<=area_active_next[i];
                end else begin
                    if(fill_done_good && inflight_line==i)
                        active_refs[i]<=pending_refs[i]+add_pending[i];
                    else if(active_valid[i] && (add_active[i] || sub_active[i]))
                        active_refs[i]<=active_refs[i]+add_active[i]-sub_active[i];
                end
                if(add_pending[i])pending_refs[i]<=pending_refs[i]+1'b1;
            end
            if(scout_commit)begin
                admitted_count<=admitted_count+1'b1;hits<=hits+hit_inc;misses<=misses+miss_inc;
                for(i=0;i<4;i=i+1)if(first_ref[i])begin
                    if(!pending_valid[decoded_line[i]] && !(active_valid[decoded_line[i]] &&
                        active_tag[decoded_line[i]]==decoded_block[i]))begin
                        pending_valid[decoded_line[i]]<=1;pending_tag[decoded_line[i]]<=decoded_block[i];
                        pending_first_use[decoded_line[i]]<=admitted_count[QID_W-1:0];
                        pending_refs[decoded_line[i]]<=1;
                        pending_row[decoded_line[i]]<=decoded_row[i];pending_col[decoded_line[i]]<=decoded_col[i];
                    end
                end
            end
            if(decoded_valid && admitted_count[QID_W])begin local_failed<=1;local_fault<=8'h45;end
            if(head_valid && !(&has_request))begin local_failed<=1;local_fault<=8'h46;end
            if(store_out_valid && !retire_identity_ok)begin local_failed<=1;local_fault<=8'h43;end
            if(store_out_valid && !retire_lease_ok)begin local_failed<=1;local_fault<=8'h48;end
            if(store_fill_done && !fill_done_good)begin local_failed<=1;local_fault<=8'h42;end
            if(job_hold && !job_current)begin local_failed<=1;local_fault<=8'h47;end
        end
    end
endmodule

`endif
