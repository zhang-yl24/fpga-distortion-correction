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
    QUERY_DEPTH=256,LOOKAHEAD=QUERY_DEPTH,IDLE_FLUSH_CYCLES=16,TIMEOUT_BITS=16,COMPACT_COORDS=0,AREA_PROFILE=0,CANDIDATE_KEY_PIPE=0,HEAD_PREDECODE=0,LOCAL_INFLIGHT_MASK=0,FILL_SCATTER16=0,FILL_STREAM=0,FILL_SCATTER8=0,JOB_DONE_EDGE_SELECT=0,READ_REQUEST_LOOKAHEAD=0,CACHE_ROW_STRIDE=0,AF_AA_ORDINAL_TAG_PACK=0
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
    localparam LINE_STRIDE=CACHE_ROW_STRIDE==0 ? BPR:CACHE_ROW_STRIDE;
    localparam BLOCK_W=$clog2(WIDTH*HEIGHT/128)<1 ? 1:$clog2(WIDTH*HEIGHT/128);
    localparam ROW_W=$clog2(HEIGHT)<1 ? 1:$clog2(HEIGHT);
    localparam COL_W=$clog2(BPR)<1 ? 1:$clog2(BPR);
    // AA: only the exact native geometry admits the line-conditioned code.
    // All other parameter combinations retain the full-width Z path.
    localparam NATIVE_TAG8=WIDTH==1920 && HEIGHT==1080 && INDEX_BITS==7 && CACHE_ROW_STRIDE==2;
    localparam DIR_TAG_W=NATIVE_TAG8 ? 8:BLOCK_W;
    function [10:0] native_tag8_row;
        input [6:0] line;input [7:0] code;
        reg [4:0] row_middle;
        begin row_middle=line[5:1]-{2'b00,code[2:0]};
            native_tag8_row={code[7:3],row_middle,line[6]};end
    endfunction
    function [3:0] native_tag8_col;
        input [6:0] line;input [7:0] code;
        begin native_tag8_col={code[2:0],line[0]};end
    endfunction
    function [13:0] native_tag8_expand;
        input [6:0] line;input [7:0] code;
        reg [13:0] row14;
        begin row14={3'b000,native_tag8_row(line,code)};
            native_tag8_expand=(row14<<4)-row14+{10'b0,native_tag8_col(line,code)};end
    endfunction
    localparam REF_W=$clog2(QUERY_DEPTH+16),LEASE_W=8+4*INDEX_BITS;
    localparam X_INT_W=$clog2(WIDTH+2),Y_INT_W=$clog2(HEIGHT+2);
    localparam X_COORD_W=8+X_INT_W,Y_COORD_W=8+Y_INT_W;
    localparam FIFO_COORD_W=COMPACT_COORDS ? X_COORD_W+Y_COORD_W:48;
    // AF opt-in contract: mask bit24 plus native output-raster tag[20:6].
    // Low6 bits derive from the exact group64/tile8 accepted-query ordinal.
    // Never infer this contract from image dimensions or truncate generic tags.
    localparam AF_PACK_CONFIG_OK=TAG_W==25 && WIDTH==1920 && HEIGHT==1080 &&
        INDEX_BITS==7 && CACHE_ROW_STRIDE==2 && COMPACT_COORDS==1 && HEAD_PREDECODE==0;
    localparam AF_PACK_ENABLED=AF_AA_ORDINAL_TAG_PACK==1 && AF_PACK_CONFIG_OK;
    localparam FIFO_TAG_W=AF_PACK_ENABLED ? 16:TAG_W;
    initial if(AF_AA_ORDINAL_TAG_PACK!=0 && !AF_PACK_ENABLED)
        $fatal(1,"AF raster-tag packing requires explicit native AA configuration");
    localparam BASE_TOKEN_W=FIFO_COORD_W+FIFO_TAG_W;
    localparam HEAD_META_W=4+4*INDEX_BITS+2*BLOCK_W+1;
    localparam TOKEN_W=BASE_TOKEN_W+(HEAD_PREDECODE ? HEAD_META_W:0),STORE_TAG_W=TAG_W+QID_W+LEASE_W;
    // A live pending first-use is at most QUERY_DEPTH+5 ahead of retirement.
    // One extra bit makes that window strictly smaller than half the modulus.
    localparam FIRST_W=($clog2(QUERY_DEPTH+16)+1<QID_W) ? $clog2(QUERY_DEPTH+16)+1:QID_W;
    localparam KEY_W=1+FIRST_W+INDEX_BITS,GROUPS=(LINES+7)/8;
    localparam PARAM_OK=WIDTH>=128 && WIDTH<=8192 && WIDTH%128==0 && HEIGHT>=2 && HEIGHT<=8192 &&
        WIDTH*HEIGHT<=16777216 && INDEX_BITS>=2 && INDEX_BITS<=10 && QUERY_DEPTH>=8 &&
        (QUERY_DEPTH&(QUERY_DEPTH-1))==0 && LOOKAHEAD>=1 && LOOKAHEAD<=QUERY_DEPTH &&
        CACHE_ROW_STRIDE>=0 && CACHE_ROW_STRIDE<=8192 && IDLE_FLUSH_CYCLES>=1 && IDLE_FLUSH_CYCLES<=255 && AREA_PROFILE==2 &&
        (AF_AA_ORDINAL_TAG_PACK==0 || AF_PACK_ENABLED);
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
    // X: logical diagnostic view; physical active tags use independent banks.
    wire [BLOCK_W-1:0] active_tag[0:LINES-1];
    // V: pending_tag is a read-only logical view. Physical target storage is
    // four independently written 32-word banks; generic layouts keep 4 writers.
    wire [BLOCK_W-1:0] pending_tag[0:LINES-1];
    // Z: candidate/job aliases remain diagnostics only. The two scheduler
    // phases share ONE functional read, selected by the existing job_hold.
    wire [BLOCK_W-1:0] candidate_pending_tag_read,job_pending_tag_read,done_pending_tag_read;
    wire [INDEX_BITS-1:0] scheduler_line=job_hold ? job_line:candidate_line;
    wire [BLOCK_W-1:0] scheduler_pending_tag;
    wire [DIR_TAG_W-1:0] scheduler_dir_code,done_dir_code;
    wire [BLOCK_W-1:0] scheduler_functional_tag,done_functional_tag;
    wire [ROW_W-1:0] scheduler_functional_row;
    wire [COL_W-1:0] scheduler_functional_col;
    generate if(NATIVE_TAG8)begin: native_scheduler_decode
        assign scheduler_functional_tag=native_tag8_expand(scheduler_line,scheduler_dir_code);
        assign done_functional_tag=native_tag8_expand(inflight_line,done_dir_code);
        assign scheduler_functional_row=native_tag8_row(scheduler_line,scheduler_dir_code);
        assign scheduler_functional_col=native_tag8_col(scheduler_line,scheduler_dir_code);
    end else begin: full_scheduler_decode
        assign scheduler_functional_tag=scheduler_dir_code;
        assign done_functional_tag=done_dir_code;
        assign scheduler_functional_row=scheduler_dir_code/BPR;
        assign scheduler_functional_col=scheduler_dir_code%BPR;
    end endgenerate
    wire [FIRST_W-1:0] scheduler_first_low=pending_first_use[scheduler_line];
    wire scheduler_pending_valid=pending_valid[scheduler_line];
    wire scheduler_owned=line_owned[scheduler_line];
    // Retirement is a strict prefix of admitted QIDs. A generation is busy
    // exactly until its greatest admitted reference retires; no count ALU is needed.
    localparam LAST_W=($clog2(QUERY_DEPTH+16)<QID_W) ? $clog2(QUERY_DEPTH+16):QID_W;
    reg [LAST_W-1:0] active_last_use[0:LINES-1];
    // Y: pending last-use has one publishing read and one admission write/bank.
    wire [LAST_W-1:0] pending_last_use[0:LINES-1];
    wire [LAST_W-1:0] publishing_pending_last;
    wire [3:0] pending_last_admission,publishing_pending_join_each;
    wire publishing_pending_join=|publishing_pending_join_each;
    // Resident busy and an inflight fill are mutually exclusive per line.
    reg [LINES-1:0] line_owned;
    wire [LINES-1:0] active_busy=line_owned & active_valid;
    reg [FIRST_W-1:0] pending_first_use[0:LINES-1];
    // Per-line row/column are exactly recovered from pending block tags.

    // No coordinate/directory decision feeds the external ready boundary.
    reg [1:0] skid_count;
    reg skid_rp,skid_wp;
    reg signed [23:0] skid_x[0:1],skid_y[0:1];
    reg [TAG_W-1:0] skid_tag[0:1];
    assign in_ready=loaded && !frame_valid && !failed && skid_count<2;
    wire af_input_tag_bad;
    generate if(AF_PACK_ENABLED)begin: af_input_tag_contract
        assign af_input_tag_bad=|in_tag[23:21];
    end else begin: af_generic_tag_contract
        assign af_input_tag_bad=1'b0;
    end endgenerate
    // Keep ready independent of the offending tag: acknowledge the otherwise
    // eligible transfer, fault it, and never enqueue its truncated identity.
    wire af_tag_reject=in_valid && in_ready && af_input_tag_bad;
    wire skid_push=in_valid && in_ready && !af_input_tag_bad;
    reg decoded_valid;
    reg signed [23:0] decoded_x,decoded_y;
    reg [TAG_W-1:0] decoded_tag;
    reg [3:0] decoded_bounds;
    reg [BLOCK_W-1:0] decoded_block[0:3];
    reg [4*INDEX_BITS-1:0] decoded_line_packed /* synthesis syn_maxfan=64 */;
    wire [3:0] incoming_bounds;
    wire [BLOCK_W-1:0] incoming_block[0:3];
    wire [INDEX_BITS-1:0] incoming_line[0:3];
    genvar n;
    generate for(n=0;n<4;n=n+1)begin: scout_decode
        wire signed [16:0] x=$signed(skid_x[skid_rp][23:8])+(n%2);
        wire signed [16:0] y=$signed(skid_y[skid_rp][23:8])+(n/2);
        wire [31:0] local_line=(y>>>1)*LINE_STRIDE+(x>>>7);
        assign incoming_bounds[n]=x>=0 && x<WIDTH && y>=0 && y<HEIGHT;
        assign incoming_block[n]=y*BPR+(x>>>7);
        assign incoming_line[n]={y[0],local_line[INDEX_BITS-2:0]};
    end endgenerate
    // Coordinate codes come from each actual neighbour, including x/y carry.
    // No divide-by15, extra register, token or pipeline stage is introduced.
    wire [DIR_TAG_W-1:0] decoded_dir_code[0:3],head_dir_code[0:3];
    wire [DIR_TAG_W-1:0] scout_pending_dir_read[0:3],head_pending_dir_read[0:3];
    wire [DIR_TAG_W-1:0] scout_active_dir_read[0:3],head_active_dir_read[0:3];
    generate for(n=0;n<4;n=n+1)begin: neighbour_directory_codes
        if(NATIVE_TAG8)begin: native_code
            wire signed [16:0] dx=$signed(decoded_x[23:8])+(n%2);
            wire signed [16:0] dy=$signed(decoded_y[23:8])+(n/2);
            wire signed [16:0] hx=$signed(head_x[23:8])+(n%2);
            wire signed [16:0] hy=$signed(head_y[23:8])+(n/2);
            assign decoded_dir_code[n]={dy[10:6],dx[10:8]};
            assign head_dir_code[n]={hy[10:6],hx[10:8]};
        end else begin: full_code
            assign decoded_dir_code[n]=decoded_block[n];
            assign head_dir_code[n]=head_block[n];
        end
    end endgenerate
    // Full raw-tag aliases below are diagnostics only in the native codec.
    // They have no functional consumers and no keep/debug attributes.
    // Read-only fallback overlay; packed fanout registers and every directory write stay unchanged.
    wire [BLOCK_W-1:0] scout_pending_tag_read[0:3],head_pending_tag_read[0:3];
    // W(U+V): U's active/valid read word shares addresses with V's physical
    // pending-tag memories, but never consumes the logical pending_tag aliases.
    wire [BLOCK_W-1:0] scout_active_tag_read[0:3],head_active_tag_read[0:3];
    wire [3:0] scout_pending_valid_read,scout_active_valid_read;
    wire [3:0] head_pending_valid_read,head_active_valid_read;
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
                if(scout_pending_valid_read[a])begin
                    if(scout_pending_dir_read[a]!=decoded_dir_code[a])generations_ok=0;
                end else if(first_ref[a] && !(scout_active_valid_read[a] &&
                    scout_active_dir_read[a]==decoded_dir_code[a]))begin
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
    wire [FIFO_TAG_W-1:0] fifo_stored_tag;
    wire [8:0] af_next_head_ordinal;
    wire af_decoded_tag_bad;
    generate if(AF_PACK_ENABLED)begin: af_fifo_tag_pack
        assign fifo_stored_tag={decoded_tag[24],decoded_tag[20:6]};
        assign af_decoded_tag_bad=(|decoded_tag[23:21]) ||
            decoded_tag[5:0]!={admitted_count[8:6],admitted_count[2:0]};
        assign fifo_head_tag={fifo_out_data[FIFO_COORD_W+15],3'b000,
            fifo_out_data[FIFO_COORD_W+:15],af_next_head_ordinal[8:6],af_next_head_ordinal[2:0]};
    end else begin: af_fifo_tag_passthrough
        assign fifo_stored_tag=decoded_tag;
        assign af_decoded_tag_bad=1'b0;
        assign fifo_head_tag=fifo_out_data[FIFO_COORD_W+:TAG_W];
    end endgenerate
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
        assign fifo_payload={fifo_stored_tag,code_y,decoded_y[7:0],code_x,decoded_x[7:0]};
        assign fifo_head_x={{(16-X_INT_W){head_negative_x}},head_code_x,fifo_out_data[7:0]};
        assign fifo_head_y={{(16-Y_INT_W){head_negative_y}},head_code_y,fifo_out_data[X_COORD_W+:8]};
    end else begin: legacy_coords_codec
        assign fifo_payload={fifo_stored_tag,decoded_y,decoded_x};
        assign fifo_head_x=fifo_out_data[23:0];
        assign fifo_head_y=fifo_out_data[47:24];
    end endgenerate
    // The low coordinate/tag payload and its timing are unchanged. The
    // descriptor comes from the same decoded registers and scout_commit as
    // the lease admission, so no extra token or outstanding stage is added.
    generate if(HEAD_PREDECODE)begin: pack_head_descriptor
        assign fifo_in_data={decoded_bounds,decoded_line_packed[3*INDEX_BITS+:INDEX_BITS],decoded_line_packed[2*INDEX_BITS+:INDEX_BITS],decoded_line_packed[1*INDEX_BITS+:INDEX_BITS],decoded_line_packed[0*INDEX_BITS+:INDEX_BITS],
            decoded_block[2],decoded_block[0],(&decoded_x[14:8]),fifo_payload};
    end else begin: original_fifo_payload
        assign fifo_in_data=fifo_payload;
    end endgenerate
    wire scout_commit=decoded_valid && generations_ok && fifo_in_ready &&
        !admitted_count[QID_W] && !failed && !af_decoded_tag_bad;
    wire generation_blocked=decoded_valid && !generations_ok && !failed;
    genvar last_port;
    generate for(last_port=0;last_port<4;last_port=last_port+1)begin: pending_last_events
        assign pending_last_admission[last_port]=new_ref[last_port] ||
            (first_ref[last_port] && scout_pending_valid_read[last_port]);
        // Publishing a generation must see a same-edge pending join's newest A.
        assign publishing_pending_join_each[last_port]=scout_commit && first_ref[last_port] &&
            scout_pending_valid_read[last_port] &&
            decoded_line_packed[last_port*INDEX_BITS+:INDEX_BITS]==inflight_line;
    end endgenerate
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
            wire [31:0] local_line=(y>>>1)*LINE_STRIDE+(x>>>7);
            assign next_head_bounds[n]=x>=0 && x<WIDTH && y>=0 && y<HEIGHT;
            assign next_head_block[n]=y*BPR+(x>>>7);
            assign next_head_line[n]={y[0],local_line[INDEX_BITS-2:0]};
        end
    end endgenerate
    wire [3:0] resident,has_request;
    generate for(n=0;n<4;n=n+1)begin: head_directory
        assign resident[n]=!head_bounds[n] || (head_active_valid_read[n] &&
            head_active_dir_read[n]==head_dir_code[n]);
        assign has_request[n]=resident[n] || (head_pending_valid_read[n] &&
            head_pending_dir_read[n]==head_dir_code[n]);
    end endgenerate
    // V: each target bank has one physical write port and five explicit
    // asynchronous read ports. Logical pending_tag aliases are diagnostics only.
    // Same-bank in-bounds neighbours address the SAME line. first_ref makes
    // a new block unique, so each bank receives at most one new_ref per cycle.
    generate if(INDEX_BITS==7 && CACHE_ROW_STRIDE==2)begin: pending_tag_banked_storage
        wire [BLOCK_W-1:0] scout_bank_data[0:3],head_bank_data[0:3];
        wire [BLOCK_W-1:0] scheduler_bank_data[0:3],done_bank_data[0:3];
        wire [DIR_TAG_W-1:0] scout_dir_bank[0:3],head_dir_bank[0:3];
        wire [DIR_TAG_W-1:0] scout_active_dir_bank[0:3],head_active_dir_bank[0:3];
        wire [DIR_TAG_W-1:0] scheduler_dir_bank[0:3],done_dir_bank[0:3];
        wire [1:0] scout_valid_bank[0:3],head_valid_bank[0:3];
        wire [LAST_W-1:0] pending_last_bank_data[0:3];
        localparam ACTIVE_READ_W=BLOCK_W+2;
        wire [ACTIVE_READ_W-1:0] scout_active_bank_data[0:3],head_active_bank_data[0:3];
        genvar bank,word,port;
        for(bank=0;bank<4;bank=bank+1)begin: bank_memory
            reg [DIR_TAG_W-1:0] words[0:31];
            // Raw full-width history is nonfunctional diagnostic state only.
            // Production synthesis must eliminate these shadows and aliases.
            reg [BLOCK_W-1:0] pending_raw_shadow[0:31];
            reg [BLOCK_W-1:0] active_raw_shadow[0:31];
            wire [BLOCK_W-1:0] raw_pending[0:31],raw_active[0:31];
            // X: keep active tags as canonical 1W/2R storage. Valid flags
            // remain a separate 2-bit combinational word, with shared addresses.
            reg [DIR_TAG_W-1:0] active_tags[0:31];
            reg [LAST_W-1:0] pending_lasts[0:31];
            wire [32*2-1:0] valid_words;
            reg [4:0] scout_address,head_address,write_address;
            reg write_valid;
            reg pending_last_write_valid;
            reg [BLOCK_W-1:0] write_tag;
            reg [DIR_TAG_W-1:0] write_code;
            integer request;
            for(word=0;word<32;word=word+1)begin: logical_word
                localparam LINE=(bank/2)*64+word*2+(bank%2);
                if(NATIVE_TAG8)begin: raw_diagnostics
                    assign raw_pending[word]=pending_raw_shadow[word];
                    assign raw_active[word]=active_raw_shadow[word];
                end else begin: full_functional
                    assign raw_pending[word]=words[word];
                    assign raw_active[word]=active_tags[word];
                end
                assign pending_tag[LINE]=raw_pending[word];
                assign active_tag[LINE]=raw_active[word];
                assign pending_last_use[LINE]=pending_lasts[word];
                assign valid_words[word*2+:2]={pending_valid[LINE],active_valid[LINE]};
            end
            always @*begin
                scout_address=0;head_address=0;write_address=0;write_valid=0;write_tag=0;write_code=0;pending_last_write_valid=0;
                for(request=0;request<4;request=request+1)begin
                    if(decoded_bounds[request] &&
                       {decoded_line_packed[request*INDEX_BITS+6],decoded_line_packed[request*INDEX_BITS]}==bank)
                        scout_address=decoded_line_packed[request*INDEX_BITS+1+:5];
                    if(head_bounds[request] && {head_line[request][6],head_line[request][0]}==bank)
                        head_address=head_line[request][5:1];
                    if(pending_last_admission[request] &&
                       {decoded_line_packed[request*INDEX_BITS+6],decoded_line_packed[request*INDEX_BITS]}==bank[1:0])
                        pending_last_write_valid=1;
                    if(new_ref[request] &&
                       {decoded_line_packed[request*INDEX_BITS+6],decoded_line_packed[request*INDEX_BITS]}==bank)begin
                        write_valid=1;write_address=decoded_line_packed[request*INDEX_BITS+1+:5];
                        write_tag=decoded_block[request];write_code=decoded_dir_code[request];
                    end
                end
            end
            always @(posedge clk)
                if(rst_n && !failed && !accept_frame && scout_commit && write_valid)
                    begin words[write_address]<=write_code;
                        pending_raw_shadow[write_address]<=write_tag;end
            always @(posedge clk)
                if(rst_n && !failed && !accept_frame && scout_commit && pending_last_write_valid)
                    pending_lasts[scout_address]<=admitted_count[LAST_W-1:0];
            assign pending_last_bank_data[bank]=pending_lasts[inflight_line[5:1]];
            assign scout_bank_data[bank]=raw_pending[scout_address];
            assign head_bank_data[bank]=raw_pending[head_address];
            assign scout_dir_bank[bank]=words[scout_address];
            assign head_dir_bank[bank]=words[head_address];
            assign scout_active_dir_bank[bank]=active_tags[scout_address];
            assign head_active_dir_bank[bank]=active_tags[head_address];
            always @(posedge clk)
                if(rst_n && !failed && !accept_frame && fill_done_good &&
                   {inflight_line[6],inflight_line[0]}==bank[1:0])
                    begin active_tags[inflight_line[5:1]]<=NATIVE_TAG8 ? done_dir_code:inflight_tag[DIR_TAG_W-1:0];
                        active_raw_shadow[inflight_line[5:1]]<=inflight_tag;end
            assign scout_valid_bank[bank]=valid_words[scout_address*2+:2];
            assign head_valid_bank[bank]=valid_words[head_address*2+:2];
            assign scout_active_bank_data[bank]={valid_words[scout_address*2+:2],raw_active[scout_address]};
            assign head_active_bank_data[bank]={valid_words[head_address*2+:2],raw_active[head_address]};
            assign scheduler_bank_data[bank]=raw_pending[scheduler_line[5:1]];
            assign done_bank_data[bank]=raw_pending[inflight_line[5:1]];
            assign scheduler_dir_bank[bank]=words[scheduler_line[5:1]];
            assign done_dir_bank[bank]=words[inflight_line[5:1]];
        end
        for(port=0;port<4;port=port+1)begin: result_permutation
            wire [1:0] scout_bank={decoded_line_packed[port*INDEX_BITS+6],decoded_line_packed[port*INDEX_BITS]};
            wire [1:0] head_bank={head_line[port][6],head_line[port][0]};
            assign scout_pending_dir_read[port]=decoded_bounds[port] ? scout_dir_bank[scout_bank]:{DIR_TAG_W{1'b0}};
            assign head_pending_dir_read[port]=head_bounds[port] ? head_dir_bank[head_bank]:{DIR_TAG_W{1'b0}};
            assign scout_active_dir_read[port]=decoded_bounds[port] ? scout_active_dir_bank[scout_bank]:{DIR_TAG_W{1'b0}};
            assign head_active_dir_read[port]=head_bounds[port] ? head_active_dir_bank[head_bank]:{DIR_TAG_W{1'b0}};
            assign scout_pending_tag_read[port]=decoded_bounds[port] ? scout_bank_data[scout_bank]:{BLOCK_W{1'b0}};
            assign head_pending_tag_read[port]=head_bounds[port] ? head_bank_data[head_bank]:{BLOCK_W{1'b0}};
            wire [ACTIVE_READ_W-1:0] scout_active_word=decoded_bounds[port] ? scout_active_bank_data[scout_bank]:{ACTIVE_READ_W{1'b0}};
            wire [ACTIVE_READ_W-1:0] head_active_word=head_bounds[port] ? head_active_bank_data[head_bank]:{ACTIVE_READ_W{1'b0}};
            if(NATIVE_TAG8)begin: independent_native_flags
                // The functional2-bit flag read must not carry raw diagnostic
                // tag bits. This also lets software compilation remove shadows.
                assign {scout_pending_valid_read[port],scout_active_valid_read[port]}=decoded_bounds[port] ? scout_valid_bank[scout_bank]:2'b00;
                assign {head_pending_valid_read[port],head_active_valid_read[port]}=head_bounds[port] ? head_valid_bank[head_bank]:2'b00;
                assign scout_active_tag_read[port]=scout_active_word[BLOCK_W-1:0];
                assign head_active_tag_read[port]=head_active_word[BLOCK_W-1:0];
            end else begin: unchanged_full_flags
                assign {scout_pending_valid_read[port],scout_active_valid_read[port],scout_active_tag_read[port]}=scout_active_word;
                assign {head_pending_valid_read[port],head_active_valid_read[port],head_active_tag_read[port]}=head_active_word;
            end
        end
        assign scheduler_pending_tag=scheduler_bank_data[{scheduler_line[6],scheduler_line[0]}];
        assign scheduler_dir_code=scheduler_dir_bank[{scheduler_line[6],scheduler_line[0]}];
        assign done_dir_code=done_dir_bank[{inflight_line[6],inflight_line[0]}];
        // No functional consumer: preserve the former diagnostic observations.
        assign candidate_pending_tag_read=pending_tag[candidate_line];
        assign job_pending_tag_read=pending_tag[job_line];
        assign done_pending_tag_read=done_bank_data[{inflight_line[6],inflight_line[0]}];
        assign publishing_pending_last=pending_last_bank_data[{inflight_line[6],inflight_line[0]}];
    end else begin: original_pending_tag_storage
        reg [BLOCK_W-1:0] words[0:LINES-1];
        reg [BLOCK_W-1:0] active_words[0:LINES-1];
        reg [LAST_W-1:0] pending_last_words[0:LINES-1];
        integer last_request;
        integer request;
        genvar port,word;
        for(word=0;word<LINES;word=word+1)begin: logical_word
            assign pending_tag[word]=words[word];
            assign active_tag[word]=active_words[word];
            assign pending_last_use[word]=pending_last_words[word];
        end
        // The fallback preserves the original last-writer priority for any
        // generic layout, including multiple distinct writes to one line.
        always @(posedge clk)
            if(rst_n && !failed && !accept_frame && scout_commit)
                for(request=0;request<4;request=request+1)
                    if(new_ref[request])words[decoded_line_packed[request*INDEX_BITS+:INDEX_BITS]]<=decoded_block[request];
        always @(posedge clk)
            if(rst_n && !failed && !accept_frame && fill_done_good)
                active_words[inflight_line]<=inflight_tag;
        always @(posedge clk)
            if(rst_n && !failed && !accept_frame && scout_commit)
                for(last_request=0;last_request<4;last_request=last_request+1)
                    if(pending_last_admission[last_request])
                        pending_last_words[decoded_line_packed[last_request*INDEX_BITS+:INDEX_BITS]]<=admitted_count[LAST_W-1:0];
        for(port=0;port<4;port=port+1)begin: read
            assign scout_pending_dir_read[port]=words[decoded_line_packed[port*INDEX_BITS+:INDEX_BITS]];
            assign head_pending_dir_read[port]=words[head_line[port]];
            assign scout_active_dir_read[port]=active_words[decoded_line_packed[port*INDEX_BITS+:INDEX_BITS]];
            assign head_active_dir_read[port]=active_words[head_line[port]];
            assign scout_pending_tag_read[port]=words[decoded_line_packed[port*INDEX_BITS+:INDEX_BITS]];
            assign head_pending_tag_read[port]=words[head_line[port]];
            assign scout_active_tag_read[port]=active_words[decoded_line_packed[port*INDEX_BITS+:INDEX_BITS]];
            assign scout_pending_valid_read[port]=pending_valid[decoded_line_packed[port*INDEX_BITS+:INDEX_BITS]];
            assign scout_active_valid_read[port]=active_valid[decoded_line_packed[port*INDEX_BITS+:INDEX_BITS]];
            assign head_active_tag_read[port]=active_words[head_line[port]];
            assign head_pending_valid_read[port]=pending_valid[head_line[port]];
            assign head_active_valid_read[port]=active_valid[head_line[port]];
        end
        assign scheduler_pending_tag=words[scheduler_line];
        assign scheduler_dir_code=words[scheduler_line];
        assign done_dir_code=words[inflight_line];
        assign candidate_pending_tag_read=words[candidate_line];
        assign job_pending_tag_read=words[job_line];
        assign done_pending_tag_read=words[inflight_line];
        assign publishing_pending_last=pending_last_words[inflight_line];
    end endgenerate
    wire all_resident=&resident;
    wire demand_blocked=head_valid && !all_resident && !failed;
    wire store_in_ready,store_out_valid;
    wire [STORE_TAG_W-1:0] store_out_tag;
    wire store_query_valid=head_valid && started && all_resident && !failed;
    wire store_query_accept=store_query_valid && store_in_ready;
    assign fifo_out_ready=(!head_valid || store_query_accept) && !failed;
    wire head_load=fifo_out_valid && fifo_out_ready;
    // issued_count names the current head. Replacement on its issue edge is
    // the next ordinal; an empty-head load uses the current ordinal.
    assign af_next_head_ordinal=issued_count[8:0]+{8'b0,store_query_accept};
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
            if(!active_valid[lease_line] || !active_busy[lease_line] ||
                active_generation[lease_line]!=retire_generations[r])retire_lease_ok=0;
        end
    end
    assign out_valid=store_out_valid && retire_identity_ok && retire_lease_ok && !failed;
    assign out_tag=store_out_tag[TAG_W-1:0];
    wire retire=out_valid && out_ready;

    // READ_REQUEST_LOOKAHEAD permits the second saved request to become visible
    // while the first response drains. With the unchanged shared read arbiter,
    // at most ONE external DDR read is accepted at a time. No DDR latency,
    // return ordering, burst reservation, ticket or directory contract changes.
    // Do not enable on a direct DDR connection that only supports one credit.
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
    wire [LINES-1:0] local_inflight_owned=line_owned & ~active_valid;
    reg [INDEX_BITS-1:0] job_line /* synthesis syn_maxfan=64 */;
    reg [BLOCK_W-1:0] job_tag;
    reg [QID_W-1:0] job_first;
    reg [ROW_W-1:0] job_row;
    reg [COL_W-1:0] job_col;
    reg [31:0] job_ticket;
    genvar d,g,k,j;
    generate for(d=0;d<LINES;d=d+1)begin: eligible
        wire ok=pending_valid[d] && !line_owned[d];
        if(FIRST_W<QID_W)begin: compressed_first
            wire [FIRST_W-1:0] ordered_first=pending_first_use[d] ^
                {retired_count[FIRST_W-1],{(FIRST_W-1){1'b0}}};
            assign leaves[d]=ok ? {1'b0,ordered_first,d[INDEX_BITS-1:0]}:invalid_key;
        end else begin: original_first
            assign leaves[d]=ok ? {1'b0,pending_first_use[d],d[INDEX_BITS-1:0]}:invalid_key;
        end
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
    wire [KEY_W-1:0] candidate_key /* synthesis syn_maxfan=64 */;
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
    // Bind the half-circle origin to the SAME group/mid/root snapshot as K.
    // Retain full absolute identities at the candidate and held-job boundary.
    wire [QID_W-1:0] candidate_first;
    generate if(FIRST_W<QID_W)begin: first_origin_pipeline
        localparam BASE_W=QID_W-FIRST_W+1;
        reg [BASE_W-1:0] group_base,mid_base,root_base;
        always @(posedge clk)begin
            if(!rst_n || accept_frame || failed)begin group_base<=0;mid_base<=0;root_base<=0;end
            else begin
                group_base<=retired_count[QID_W-1:FIRST_W-1];
                mid_base<=group_base;root_base<=mid_base;
            end
        end
        wire [BASE_W-1:0] selected_base=CANDIDATE_KEY_PIPE==2 ? root_base:group_base;
        assign candidate_first={selected_base,{(FIRST_W-1){1'b0}}}+
            {{(QID_W-FIRST_W){1'b0}},candidate_key[INDEX_BITS+:FIRST_W]};
    end else begin: original_first_identity
        assign candidate_first=candidate_key[INDEX_BITS+:QID_W];
    end endgenerate
    function [QID_W-1:0] expand_live_first;
        input [FIRST_W-1:0] low_first;
        reg [QID_W-FIRST_W:0] half_base;
        begin
            if(FIRST_W<QID_W)begin
                half_base=retired_count[QID_W-1:FIRST_W-1]+
                    (low_first[FIRST_W-1]^retired_count[FIRST_W-1]);
                expand_live_first={half_base,low_first[FIRST_W-2:0]};
            end else expand_live_first=low_first;
        end
    endfunction
    // One physical control-directory read is sufficient in mutually exclusive
    // scheduler phases. No pipeline/state/depth or full-QID width changes.
    // Payload/scout/head/retire read ports remain separate and unchanged.
    wire control_pending_valid,control_active_valid;
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
        assign control_pending_tag=candidate_pending_tag_read;
        assign control_first=expand_live_first(pending_first_use[candidate_line]);
        assign control_row=control_pending_tag / BPR;
        assign control_col=control_pending_tag % BPR;
        // Candidate consumers are guarded by !job_hold; job consumers by
        // job_hold. Completion validation stays on its independent done port.
        assign candidate_current=!candidate_key[KEY_W-1] && !scheduler_owned && scheduler_pending_valid &&
            expand_live_first(scheduler_first_low)==candidate_first;
        assign job_current=!scheduler_owned && scheduler_pending_valid && scheduler_functional_tag==job_tag &&
            expand_live_first(scheduler_first_low)==job_first;
        assign control_done_pending_valid=pending_valid[inflight_line];
        assign control_done_pending_tag=done_functional_tag;
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
    quad_parity_prefetch_store #(.CACHE_ROW_STRIDE(CACHE_ROW_STRIDE),.MAX_READ_OUTSTANDING(READ_REQUEST_LOOKAHEAD ? 2:1),.SCATTER8(FILL_SCATTER8),.SCATTER16(FILL_SCATTER16),.STREAM_FILL(FILL_STREAM),.WIDTH(WIDTH),.HEIGHT(HEIGHT),.INDEX_BITS(INDEX_BITS),
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
            if(scout_pending_valid_read[u])add_pending[decoded_line_packed[u*INDEX_BITS+:INDEX_BITS]]=1;
            else if(scout_active_valid_read[u] && scout_active_dir_read[u]==decoded_dir_code[u])
                add_active[decoded_line_packed[u*INDEX_BITS+:INDEX_BITS]]=1;
        end
        if(retire)for(u=0;u<4;u=u+1)if(retire_mask[u])
            sub_active[retire_lines[u*INDEX_BITS+:INDEX_BITS]]=1;
    end
    // A last-use identity is meaningful only while the generation is busy.
    // During that interval 0 <= last_use-retired <= QUERY_DEPTH+5 < 2**LAST_W.
    wire [LINES-1:0] retiring_last,publishing_line,accepting_fill_line;
    genvar lifetime_line;
    generate for(lifetime_line=0;lifetime_line<LINES;lifetime_line=lifetime_line+1)begin: lifetime_retirement
        assign retiring_last[lifetime_line]=sub_active[lifetime_line] &&
            active_last_use[lifetime_line]==retired_count[LAST_W-1:0];
        assign publishing_line[lifetime_line]=fill_done_good && inflight_line==lifetime_line;
        assign accepting_fill_line[lifetime_line]=fill_accept && job_line==lifetime_line;
    end endgenerate
    integer i;
    always @(posedge clk)begin
        if(!rst_n)begin
            local_failed<=0;local_fault<=0;loaded<=0;started<=0;active_base<=0;epoch<=0;idle_age<=0;
            admitted_count<=0;issued_count<=0;retired_count<=0;next_fill_ticket<=1;
            skid_count<=0;skid_rp<=0;skid_wp<=0;decoded_valid<=0;decoded_bounds<=0;head_valid<=0;head_bounds<=0;
            line_owned<=0;active_valid<=0;pending_valid<=0;active_generation<=0;inflight_count<=0;inflight_rp<=0;inflight_wp<=0;job_hold<=0;
            owner_line[0]<=0;owner_line[1]<=0;owner_tag[0]<=0;owner_tag[1]<=0;owner_ticket[0]<=0;owner_ticket[1]<=0;job_line<=0;job_tag<=0;
            job_first<=0;job_row<=0;job_col<=0;job_ticket<=0;
            hits<=0;misses<=0;completed_queries<=0;
        end else if(failed)begin
            // Quarantine never publishes a new generation or result. The port
            // store retains any already asserted AR until its handshake.
            loaded<=0;started<=0;skid_count<=0;decoded_valid<=0;head_valid<=0;
            line_owned<=line_owned & ~active_valid;active_valid<=0;pending_valid<=0;job_hold<=0;
        end else if(accept_frame)begin
            if(!PARAM_OK || frame_base[6:0]!=0 || ({1'b0,frame_base}+WIDTH*HEIGHT/2)>29'h10000000)begin
                local_failed<=1;local_fault<=8'h40;
            end else begin
                loaded<=1;started<=0;active_base<=frame_base;epoch<=epoch+1'b1;idle_age<=0;
                admitted_count<=0;issued_count<=0;retired_count<=0;
                skid_count<=0;skid_rp<=0;skid_wp<=0;decoded_valid<=0;head_valid<=0;
                line_owned<=0;active_valid<=0;pending_valid<=0;active_generation<=0;job_hold<=0;inflight_count<=0;inflight_rp<=0;inflight_wp<=0;
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
                    decoded_block[i]<=incoming_block[i];decoded_line_packed[i*INDEX_BITS+:INDEX_BITS]<=incoming_line[i];
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
                job_hold<=1;job_line<=candidate_line;job_tag<=scheduler_functional_tag;
                job_first<=candidate_first;job_row<=scheduler_functional_row;job_col<=scheduler_functional_col;
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
            // Inflight ownership is represented by line_owned with active_valid=0.
            if(fill_accept)begin
                owner_line[inflight_wp]<=job_line;owner_tag[inflight_wp]<=job_tag;
                owner_ticket[inflight_wp]<=job_ticket;inflight_wp<=!inflight_wp;
                job_hold<=0;next_fill_ticket[7:0]<=next_fill_ticket[7:0]+1'b1; if(&next_fill_ticket[7:0])next_fill_ticket[15:8]<=next_fill_ticket[15:8]+1'b1; if(&next_fill_ticket[15:0])next_fill_ticket[23:16]<=next_fill_ticket[23:16]+1'b1; if(&next_fill_ticket[23:0])next_fill_ticket[31:24]<=next_fill_ticket[31:24]+1'b1;active_valid[job_line]<=0;
            end
            if(fill_done_good)begin
                inflight_rp<=!inflight_rp;
                active_valid[inflight_line]<=1;
                active_generation[inflight_line]<=!active_generation[inflight_line];pending_valid[inflight_line]<=0;
            end
            // New active admission wins over retiring an earlier last reference.
            // Publication wins and uses a same-edge pending join if one exists.
            line_owned <= (line_owned & ~retiring_last) | add_active | publishing_line | accepting_fill_line;
            for(i=0;i<LINES;i=i+1)begin
                if(publishing_line[i])
                    active_last_use[i] <= publishing_pending_join ? admitted_count[LAST_W-1:0]:publishing_pending_last;
                else if(add_active[i])active_last_use[i]<=admitted_count[LAST_W-1:0];
            end
            if(scout_commit)begin
                admitted_count<=admitted_count+1'b1;hits<=hits+hit_inc;misses<=misses+miss_inc;
                for(i=0;i<4;i=i+1)if(first_ref[i])begin
                    if(!scout_pending_valid_read[i] && !(scout_active_valid_read[i] &&
                        scout_active_dir_read[i]==decoded_dir_code[i]))begin
                        pending_valid[decoded_line_packed[i*INDEX_BITS+:INDEX_BITS]]<=1;
                        pending_first_use[decoded_line_packed[i*INDEX_BITS+:INDEX_BITS]]<=admitted_count[FIRST_W-1:0];
                        // No duplicate coordinate metadata is written.
                    end
                end
            end
            if(decoded_valid && admitted_count[QID_W])begin local_failed<=1;local_fault<=8'h45;end
            if(head_valid && !(&has_request))begin local_failed<=1;local_fault<=8'h46;end
            if(store_out_valid && !retire_identity_ok)begin local_failed<=1;local_fault<=8'h43;end
            if(store_out_valid && !retire_lease_ok)begin local_failed<=1;local_fault<=8'h48;end
            if(store_fill_done && !fill_done_good)begin local_failed<=1;local_fault<=8'h42;end
            if(job_hold && !job_current)begin local_failed<=1;local_fault<=8'h47;end
            // Last assignment wins: a rejected input gets a distinct sticky
            // diagnostic even if another local check also fails on this edge.
            if(af_tag_reject || (decoded_valid && af_decoded_tag_bad))begin local_failed<=1;local_fault<=8'h4a;end
        end
    end
endmodule
