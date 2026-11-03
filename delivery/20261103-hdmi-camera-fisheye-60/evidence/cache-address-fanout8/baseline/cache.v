`timescale 1ns/1ps
// DDR direct-fill candidate. Native timing and board verification remain required.
// Same port interface with distinct module names; the frozen original may
// coexist in a simulation source closure but is not the instantiated candidate. Two 64-bit even/odd true-dual-port organizations;
// each has one upper-row and one lower-row read port. Four same-parity pixels per word;
// each DDR beat writes both ports of both arrays, removing the scatter phase.
// Cache capacity stays 256 bytes per line; no full-burst staging registers.
// A miss drains fast hits, locks the query, then saves each neighbour BEFORE
// selecting the next; four mutually conflicting lines need not coexist.
// Registered-ready boundary: upstream coordinates cannot feed all_hit/ready
// back into mapper/rotation global stall clock enables. This FIFO has two
// complete query registers; its ready uses ONLY registered occupancy/loaded,
// frame_valid and the inner registered failure. It deliberately has no
// full+pop lookahead, bypass, or combinational inner_ready dependency.
module ddr_neighbour_cache_scatter4_rowpipe #(
    parameter WIDTH=640,HEIGHT=480,TAG_W=24,INDEX_BITS=3,TIMEOUT_BITS=26,PREDECODE=1,ROW_PADDED_INDEX=0,REGISTERED_RETURN=0
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
    output wire [31:0] hits,misses,completed_queries
);
    reg frame_loaded;
    reg [1:0] queue_count;
    reg read_pointer,write_pointer;
    reg signed [23:0] queue_x[0:1],queue_y[0:1];
    reg [TAG_W-1:0] queue_tag[0:1];
    // End signed coordinate/address arithmetic at the public FIFO register.
    // Tag lookup sees registered numbers even when upstream ready is stalled.
    reg [127:0] queue_numbers[0:1];
    reg [3:0] queue_bounds[0:1];
    wire signed [16:0] enqueue_x=$signed(in_x[23:8]),enqueue_y=$signed(in_y[23:8]);
    wire signed [31:0] enqueue_signed_x={{15{enqueue_x[16]}},enqueue_x};
    wire signed [31:0] enqueue_signed_y={{15{enqueue_y[16]}},enqueue_y};
    localparam signed [31:0] ENQUEUE_WIDTH=WIDTH;
    wire signed [31:0] enqueue_row=enqueue_signed_y*ENQUEUE_WIDTH;
    wire [127:0] enqueue_numbers;
    wire [3:0] enqueue_bounds;
    genvar e;
    generate for(e=0;e<4;e=e+1)begin: enqueue_decode
        wire signed [16:0] ix=enqueue_x+(e%2),iy=enqueue_y+(e/2);
        localparam signed [31:0] OFFSET=(e/2)*WIDTH+(e%2);
        assign enqueue_numbers[e*32+:32]=enqueue_row+enqueue_signed_x+OFFSET;
        assign enqueue_bounds[e]=ix>=0 && ix<WIDTH && iy>=0 && iy<HEIGHT;
    end endgenerate
    wire inner_frame_ready,inner_in_ready;
    wire queue_empty=queue_count==0;
    assign frame_ready=queue_empty && inner_frame_ready && !failed;
    assign in_ready=frame_loaded && !frame_valid && !failed && queue_count<2;
    wire push=in_valid && in_ready;
    wire pop=!queue_empty && inner_in_ready && !failed;
    wire accept_frame=frame_valid && frame_ready;
    // Pending frame_valid stops NEW admissions but never stops queued heads.
    // The inner frame request is hidden until the FIFO is empty, then its own
    // frame_ready also waits for processing and downstream results to drain.
    ddr_compact_neighbour_cache_core_scatter4_rowpipe #(.WIDTH(WIDTH),.HEIGHT(HEIGHT),.TAG_W(TAG_W),
        .INDEX_BITS(INDEX_BITS),.TIMEOUT_BITS(TIMEOUT_BITS),.PREDECODE(PREDECODE),.ROW_PADDED_INDEX(ROW_PADDED_INDEX),.REGISTERED_RETURN(REGISTERED_RETURN)) inner(
        .clk(clk),.rst_n(rst_n),.frame_valid(frame_valid && queue_empty),
        .frame_ready(inner_frame_ready),.frame_base(frame_base),
        .in_valid(!queue_empty && !failed),.in_ready(inner_in_ready),
        .in_x(queue_x[read_pointer]),.in_y(queue_y[read_pointer]),.in_tag(queue_tag[read_pointer]),
        .in_numbers(queue_numbers[read_pointer]),.in_bounds_decoded(queue_bounds[read_pointer]),
        .out_valid(out_valid),.out_ready(out_ready),.p00(p00),.p10(p10),.p01(p01),.p11(p11),
        .fx(fx),.fy(fy),.out_tag(out_tag),.araddr(araddr),.arlen(arlen),.arvalid(arvalid),.arready(arready),
        .rdata(rdata),.rvalid(rvalid),.rlast(rlast),.rid(rid),.failed(failed),.fault(fault),
        .hits(hits),.misses(misses),.completed_queries(completed_queries));
    always @(posedge clk)begin
        if(!rst_n)begin
            frame_loaded<=0;queue_count<=0;read_pointer<=0;write_pointer<=0;
        end else begin
            if(accept_frame)begin
                frame_loaded<=1;queue_count<=0;read_pointer<=0;write_pointer<=0;
            end else begin
                case({push,pop})
                    2'b10:queue_count<=queue_count+1'b1;
                    2'b01:queue_count<=queue_count-1'b1;
                    default:queue_count<=queue_count;
                endcase
                if(push)begin
                    queue_x[write_pointer]<=in_x;queue_y[write_pointer]<=in_y;queue_tag[write_pointer]<=in_tag;
                    queue_numbers[write_pointer]<=enqueue_numbers;queue_bounds[write_pointer]<=enqueue_bounds;
                    write_pointer<=!write_pointer;
                end
                if(pop)read_pointer<=!read_pointer;
            end
        end
    end
endmodule

// Private core includes an elastic decoded-query boundary. Coordinate mux and
// signed pixel-number arithmetic end at these registers; tag lookup/compare
// and RAM address selection start from the registered numbers, not raw XY.
module ddr_compact_neighbour_cache_core_scatter4_rowpipe #(
    parameter WIDTH=640,HEIGHT=480,TAG_W=24,INDEX_BITS=3,TIMEOUT_BITS=26,PREDECODE=0,ROW_PADDED_INDEX=0,REGISTERED_RETURN=0
)(
    input clk,rst_n,
    input frame_valid,output wire frame_ready,input [27:0] frame_base,
    input in_valid,output wire in_ready,input signed [23:0] in_x,in_y,
    input [TAG_W-1:0] in_tag,
    input [127:0] in_numbers,input [3:0] in_bounds_decoded,
    output wire out_valid,input out_ready,output wire [23:0] p00,p10,p01,p11,
    output wire [7:0] fx,fy,output wire [TAG_W-1:0] out_tag,
    output wire [27:0] araddr,output wire [3:0] arlen,output wire arvalid,input arready,
    input [255:0] rdata,input rvalid,rlast,input [3:0] rid,
    output reg failed,output reg [7:0] fault,
    output wire [31:0] hits,misses,completed_queries
);
    localparam LINES=1<<INDEX_BITS,ADDRESS_BITS=INDEX_BITS+4;
    // Rows containing 1..16 complete 128-pixel lines may reserve 16 index
    // slots each. Other widths explicitly retain the linear mapping. DDR
    // addresses and tags always describe the original, unpadded source image.
    localparam PADDED_INDEX_ACTIVE=ROW_PADDED_INDEX!=0 && WIDTH>=128 && WIDTH<=2048 && WIDTH%128==0;
    function [INDEX_BITS-1:0] cache_line_index;
        input signed [16:0] column,row;
        input [31:0] linear_number;
        reg signed [31:0] padded_index;
        begin
            padded_index=($signed(row)<<<4)+($signed(column)>>>7);
            cache_line_index=PADDED_INDEX_ACTIVE ? padded_index[INDEX_BITS-1:0]:linear_number[7+:INDEX_BITS];
        end
    endfunction
    localparam IDLE=0,SELECT=1,AR=2,FILL=3,SCATTER=4,LOAD=5,PICK=6,RESULT=7,FAULT=8,CHECK=9,SLOW_LOOKUP=10;
    reg [3:0] state;
    reg frame_loaded,address_pending;
    reg [27:0] base;
    reg [LINES-1:0] valid_lines;
    reg [24:0] tags[0:LINES-1];
    reg signed [16:0] slow_x,slow_y;
    reg [1:0] neighbour;
    reg [7:0] slow_fx,slow_fy;
    reg [TAG_W-1:0] slow_tag;
    reg [23:0] slow_pixel[0:3];
    reg [24:0] selected_block;
    reg [INDEX_BITS-1:0] selected_line;
    reg [ADDRESS_BITS-1:0] selected_pixel_address;
    reg selected_parity;
    reg [1:0] selected_lane;
    reg [2:0] fill_beat;
    wire [2:0] scatter_group=fill_beat; // Diagnostic alias: one group per DDR beat.
    reg [TIMEOUT_BITS-1:0] watchdog;
    reg [31:0] hit_count,miss_count,complete_count;
    reg v0,v1;
    reg [3:0] bounds0,parity0;
    reg [1:0] lane0[0:3];
    reg [7:0] fx0,fy0,fx1,fy1;
    reg [TAG_W-1:0] tag0,tag1;
    reg [23:0] fast_pixel[0:3];
    // One added elastic stage: signed row product ends here, before X and
    // neighbour-offset additions in the existing decoded-query boundary.
    reg pre_valid;
    reg signed [31:0] pre_row;
    reg signed [16:0] pre_x,pre_y;
    reg [7:0] pre_fx,pre_fy;
    reg [TAG_W-1:0] pre_tag;
    reg [3:0] pre_bounds;
    reg [127:0] pre_numbers;
    // Two complete decoded entries decouple admission from metadata lookup.
    // Full has no same-cycle pop lookahead, so tag compare never reaches the
    // pre-stage CE or public ready. Occupancy one sustains simultaneous push/pop.
    reg [1:0] decoded_count;
    reg decoded_read,decoded_write;
    reg signed [16:0] decoded_x[0:1],decoded_y[0:1];
    reg [7:0] decoded_fx[0:1],decoded_fy[0:1];
    reg [TAG_W-1:0] decoded_tag[0:1];
    reg [127:0] decoded_numbers[0:1];
    // Index head is a direct register, with one tail register behind it.
    // This removes the circular FIFO read-pointer mux from metadata lookup;
    // the remaining payload keeps its existing two-slot storage and controls.
    reg [4*INDEX_BITS-1:0] decoded_index_head,decoded_index_tail;
    reg [3:0] decoded_bound_queue[0:1];
    reg [24:0] query_cached_tag[0:3];
    reg [3:0] query_cached_valid;
    reg [24:0] selected_cached_tag;
    reg selected_cached_valid;
    reg query_valid;
    reg signed [16:0] query_x,query_y;
    reg [7:0] query_fx,query_fy;
    reg [TAG_W-1:0] query_tag;
    reg [3:0] in_bounds;
    reg [31:0] pixel_number[0:3];
    reg [INDEX_BITS-1:0] query_line_index[0:3];
    wire signed [16:0] x0=$signed(in_x[23:8]),y0=$signed(in_y[23:8]);
    localparam signed [31:0] ROW_WIDTH=WIDTH;
    wire signed [31:0] signed_y={{15{y0[16]}},y0};
    wire signed [31:0] pre_signed_x={{15{pre_x[16]}},pre_x};
    wire [3:0] decoded_bounds,line_hit;
    wire [31:0] decoded_number[0:3];
    wire [ADDRESS_BITS-1:0] pixel_address[0:3];
    wire all_hit=&line_hit;
    wire stage1_ready=!v1 || out_ready;
    wire stage0_ready=!v0 || stage1_ready;
    wire empty=!v0 && !v1;
    wire accept_query;
    // Both old-frame elastic heads must drain before a new base is accepted.
    assign frame_ready=state==IDLE && empty && !pre_valid && decoded_count==0 && !query_valid && !failed;
    // A pending next frame blocks fresh inputs, not old pre/query movement.
    wire pre_to_decoded=pre_valid && !failed && state==IDLE && decoded_count<2;
    wire pre_to_query=decoded_count!=0 && !failed && state==IDLE &&
        (!query_valid || accept_query);
    assign in_ready=frame_loaded && !frame_valid && !failed && state==IDLE &&
        (!pre_valid || pre_to_decoded);
    wire accept_frame=frame_valid && frame_ready;
    // A pending next-frame request blocks new input but never the registered
    // old-frame query. This is necessary for FIFO/query/result drain.
    wire accept_fast=query_valid && !failed && state==IDLE && all_hit && stage0_ready;
    wire accept_slow=query_valid && !failed && state==IDLE && !all_hit && empty;
    assign accept_query=accept_fast || accept_slow;
    wire decode_query=in_valid && in_ready;
    wire consume_fast=v1 && out_ready && !failed;
    wire consume_slow=state==RESULT && out_ready && !failed;
    assign out_valid=!failed && (v1 || state==RESULT);
    assign p00=v1 ? fast_pixel[0]:slow_pixel[0];
    assign p10=v1 ? fast_pixel[1]:slow_pixel[1];
    assign p01=v1 ? fast_pixel[2]:slow_pixel[2];
    assign p11=v1 ? fast_pixel[3]:slow_pixel[3];
    assign fx=v1 ? fx1:slow_fx;
    assign fy=v1 ? fy1:slow_fy;
    assign out_tag=v1 ? tag1:slow_tag;
    assign hits=hit_count;assign misses=miss_count;assign completed_queries=complete_count;
    assign araddr=base+({3'b0,selected_block}<<6);
    assign arlen=7;
    // Once asserted, ARVALID survives timeout/fault until its handshake. Reset
    // is the recovery boundary; an asserted DDR transaction is never withdrawn.
    assign arvalid=address_pending;
    wire accept_address=address_pending && arready;
    // A registered return bundle can first become visible one edge after AR.
    // In that mode FILL alone owns reception, removing shared ARREADY from
    // RAM write enables. Default mode also accepts an AR-edge first R beat.
    wire receiving=state==FILL || (REGISTERED_RETURN==0 && state==AR && accept_address);
    wire progress=accept_address || (state==FILL && rvalid);
    wire signed [16:0] nx=slow_x+$signed({16'b0,neighbour[0]});
    wire signed [16:0] ny=slow_y+$signed({16'b0,neighbour[1]});
    wire neighbour_in_bounds=nx>=0 && nx<WIDTH && ny>=0 && ny<HEIGHT;
    wire [31:0] selected_number=ny*WIDTH+nx;
    function [23:0] expand565(input [15:0] p);
        expand565={p[15:11],p[15:13],p[10:5],p[10:9],p[4:0],p[4:2]};
    endfunction
    genvar n;
    generate for(n=0;n<4;n=n+1)begin: neighbour_input
        wire signed [16:0] ix=x0+(n%2),iy=y0+(n/2);
        assign decoded_bounds[n]=ix>=0 && ix<WIDTH && iy>=0 && iy<HEIGHT;
        localparam signed [31:0] NEIGHBOUR_OFFSET=(n/2)*WIDTH+(n%2);
        assign decoded_number[n]=pre_row+pre_signed_x+NEIGHBOUR_OFFSET;
        assign pixel_address[n]={query_line_index[n],pixel_number[n][6:3]};
        assign line_hit[n]=!in_bounds[n] || (query_cached_valid[n] &&
            query_cached_tag[n]==pixel_number[n][31:7]);
        // Synchronous metadata read. A younger head may have been looked up
        // on the same edge that its predecessor missed. Refresh it after the
        // slow transaction, when every fill and tag publication has completed.
        wire refresh_query=consume_slow && query_valid;
        // Select the held query for the whole RESULT state. The read enable
        // still waits for consumption; out_ready no longer selects the wide
        // metadata mux address. Enabled reads are identical: decoded in IDLE,
        // held query in RESULT, with no reads in the intervening slow states.
        wire [INDEX_BITS-1:0] metadata_index=(state==RESULT) ? query_line_index[n]:
            decoded_index_head[n*INDEX_BITS+:INDEX_BITS];
        always @(posedge clk)begin
            if(pre_to_query || refresh_query)begin
                query_cached_tag[n]<=tags[metadata_index];
                query_cached_valid[n]<=valid_lines[metadata_index];
            end
        end
    end endgenerate
    // The slow path uses its own synchronous tag port as well. Tag RAM/read
    // outputs have no reset; valid bits and transaction-valid state gate use.
    always @(posedge clk)begin
        if(state==SLOW_LOOKUP)begin
            selected_cached_tag<=tags[selected_line];
            selected_cached_valid<=valid_lines[selected_line];
        end
    end
    wire [ADDRESS_BITS-1:0] even_upper=pixel_number[0][0] ? pixel_address[1]:pixel_address[0];
    wire [ADDRESS_BITS-1:0] odd_upper=pixel_number[0][0] ? pixel_address[0]:pixel_address[1];
    wire [ADDRESS_BITS-1:0] even_lower=pixel_number[2][0] ? pixel_address[3]:pixel_address[2];
    wire [ADDRESS_BITS-1:0] odd_lower=pixel_number[2][0] ? pixel_address[2]:pixel_address[3];
    // Two mutually exclusive read/write ports per even/odd array. No RAM
    // or read-register reset; scatter uses both ports, normal reads use A/B.
    wire scatter_write=rst_n && !failed && receiving && rvalid && rid==0 && rlast==(fill_beat==7);
    wire read_enable=rst_n && !failed && (accept_fast || state==LOAD);
    wire read_lower=rst_n && accept_fast;
    wire [ADDRESS_BITS-1:0] write_address_a={selected_line,fill_beat,1'b0};
    wire [ADDRESS_BITS-1:0] write_address_b={selected_line,fill_beat,1'b1};
    // Fill and read states own disjoint RAM operations. Preselect the fill
    // address throughout AR/FILL; protocol checks continue to gate writes.
    // This keeps the beat/RID/RLAST/return-valid checks off the RAM address mux.
    wire fill_address_phase=state==AR || state==FILL;
    wire [ADDRESS_BITS-1:0] even_a=fill_address_phase ? write_address_a:state==LOAD ? selected_pixel_address:even_upper;
    wire [ADDRESS_BITS-1:0] odd_a=fill_address_phase ? write_address_a:state==LOAD ? selected_pixel_address:odd_upper;
    wire [ADDRESS_BITS-1:0] even_b=fill_address_phase ? write_address_b:even_lower;
    wire [ADDRESS_BITS-1:0] odd_b=fill_address_phase ? write_address_b:odd_lower;
    wire [63:0] fill_even_a={rdata[111:96],rdata[79:64],rdata[47:32],rdata[15:0]};
    wire [63:0] fill_odd_a ={rdata[127:112],rdata[95:80],rdata[63:48],rdata[31:16]};
    wire [63:0] fill_even_b={rdata[239:224],rdata[207:192],rdata[175:160],rdata[143:128]};
    wire [63:0] fill_odd_b ={rdata[255:240],rdata[223:208],rdata[191:176],rdata[159:144]};
    (* ram_style="block" *) reg [63:0] even_pixels[0:LINES*16-1];
    (* ram_style="block" *) reg [63:0] odd_pixels[0:LINES*16-1];
    reg [63:0] even_q_upper,odd_q_upper,even_q_lower,odd_q_lower;
    always @(posedge clk)begin
        if(scatter_write)even_pixels[even_a]<=fill_even_a;
        else if(read_enable)even_q_upper<=even_pixels[even_a];
    end
    always @(posedge clk)begin
        if(scatter_write)even_pixels[even_b]<=fill_even_b;
        else if(read_lower)even_q_lower<=even_pixels[even_b];
    end
    always @(posedge clk)begin
        if(scatter_write)odd_pixels[odd_a]<=fill_odd_a;
        else if(read_enable)odd_q_upper<=odd_pixels[odd_a];
    end
    always @(posedge clk)begin
        if(scatter_write)odd_pixels[odd_b]<=fill_odd_b;
        else if(read_lower)odd_q_lower<=odd_pixels[odd_b];
    end
    wire [63:0] selected_words=selected_parity ? odd_q_upper:even_q_upper;
    wire [15:0] selected_word=selected_words[selected_lane*16 +: 16];
    integer i;
    always @(posedge clk)begin
        if(!rst_n)begin
            state<=IDLE;frame_loaded<=0;address_pending<=0;base<=0;valid_lines<=0;
            slow_x<=0;slow_y<=0;neighbour<=0;slow_fx<=0;slow_fy<=0;slow_tag<=0;
            selected_block<=0;selected_line<=0;selected_pixel_address<=0;selected_parity<=0;selected_lane<=0;
            fill_beat<=0;watchdog<=0;failed<=0;fault<=0;
            hit_count<=0;miss_count<=0;complete_count<=0;
            v0<=0;v1<=0;bounds0<=0;parity0<=0;fx0<=0;fy0<=0;fx1<=0;fy1<=0;tag0<=0;tag1<=0;
            pre_valid<=0;pre_row<=0;pre_x<=0;pre_y<=0;pre_fx<=0;pre_fy<=0;pre_tag<=0;pre_bounds<=0;pre_numbers<=0;
            decoded_count<=0;decoded_read<=0;decoded_write<=0;
            query_valid<=0;query_x<=0;query_y<=0;query_fx<=0;query_fy<=0;query_tag<=0;in_bounds<=0;
            for(i=0;i<4;i=i+1)begin slow_pixel[i]<=0;fast_pixel[i]<=0;pixel_number[i]<=0;query_line_index[i]<=0;lane0[i]<=0;end
        end else begin
            // Same-cycle consume/refill sustains one decoded fast hit per clk.
            // If lookup or the DDR slow path stalls, the complete decoded head
            // remains unchanged even while the external FIFO receives input.
            if(decode_query)begin
                // Sign extend BEFORE multiplication. No17-bit shift/truncate.
                pre_valid<=1;pre_row<=signed_y*ROW_WIDTH;pre_x<=x0;pre_y<=y0;
                pre_fx<=in_x[7:0];pre_fy<=in_y[7:0];pre_tag<=in_tag;
                pre_bounds<=PREDECODE ? in_bounds_decoded:decoded_bounds;pre_numbers<=in_numbers;
            end else if(pre_to_decoded)pre_valid<=0;
            case({pre_to_decoded,pre_to_query})
                2'b10:decoded_count<=decoded_count+1'b1;
                2'b01:decoded_count<=decoded_count-1'b1;
                default:decoded_count<=decoded_count;
            endcase
            if(pre_to_query && decoded_count==2)decoded_index_head<=decoded_index_tail;
            if(pre_to_decoded)begin
                decoded_x[decoded_write]<=pre_x;decoded_y[decoded_write]<=pre_y;
                decoded_fx[decoded_write]<=pre_fx;decoded_fy[decoded_write]<=pre_fy;
                decoded_tag[decoded_write]<=pre_tag;decoded_bound_queue[decoded_write]<=pre_bounds;
                for(i=0;i<4;i=i+1)begin
                    decoded_numbers[decoded_write][i*32+:32]<=PREDECODE ? pre_numbers[i*32+:32]:decoded_number[i];
                    if(decoded_count==0 || pre_to_query)
                        decoded_index_head[i*INDEX_BITS+:INDEX_BITS]<=cache_line_index(
                            pre_x+(i%2),pre_y+(i/2),PREDECODE ? pre_numbers[i*32+:32]:decoded_number[i]);
                    else decoded_index_tail[i*INDEX_BITS+:INDEX_BITS]<=cache_line_index(
                            pre_x+(i%2),pre_y+(i/2),PREDECODE ? pre_numbers[i*32+:32]:decoded_number[i]);
                end
                decoded_write<=!decoded_write;
            end
            if(pre_to_query)begin
                decoded_read<=!decoded_read;
                query_valid<=1;query_x<=decoded_x[decoded_read];query_y<=decoded_y[decoded_read];
                query_fx<=decoded_fx[decoded_read];query_fy<=decoded_fy[decoded_read];
                query_tag<=decoded_tag[decoded_read];in_bounds<=decoded_bound_queue[decoded_read];
                for(i=0;i<4;i=i+1)begin
                    pixel_number[i]<=decoded_numbers[decoded_read][i*32+:32];
                    query_line_index[i]<=decoded_index_head[i*INDEX_BITS+:INDEX_BITS];
                end
            end else if(accept_query)query_valid<=0;
            if(address_pending && arready)address_pending<=0;
            if(progress || (state!=AR && state!=FILL))watchdog<=0;
            else watchdog<=watchdog+1'b1;
            if(stage1_ready)begin
                v1<=v0;fx1<=fx0;fy1<=fy0;tag1<=tag0;
                if(v0)begin
                    fast_pixel[0]<=bounds0[0] ? expand565(parity0[0] ? odd_q_upper[lane0[0]*16 +: 16]:even_q_upper[lane0[0]*16 +: 16]):24'd0;
                    fast_pixel[1]<=bounds0[1] ? expand565(parity0[1] ? odd_q_upper[lane0[1]*16 +: 16]:even_q_upper[lane0[1]*16 +: 16]):24'd0;
                    fast_pixel[2]<=bounds0[2] ? expand565(parity0[2] ? odd_q_lower[lane0[2]*16 +: 16]:even_q_lower[lane0[2]*16 +: 16]):24'd0;
                    fast_pixel[3]<=bounds0[3] ? expand565(parity0[3] ? odd_q_lower[lane0[3]*16 +: 16]:even_q_lower[lane0[3]*16 +: 16]):24'd0;
                end
            end
            if(stage0_ready)v0<=accept_fast;
            if(accept_fast)begin
                bounds0<=in_bounds;fx0<=query_fx;fy0<=query_fy;tag0<=query_tag;
                for(i=0;i<4;i=i+1)begin parity0[i]<=pixel_number[i][0];lane0[i]<=pixel_number[i][2:1];end
                hit_count<=hit_count+{31'd0,in_bounds[0]}+{31'd0,in_bounds[1]}+
                    {31'd0,in_bounds[2]}+{31'd0,in_bounds[3]};
            end
            if(consume_fast || consume_slow)complete_count<=complete_count+1'b1;
            case(state)
                IDLE:begin
                    if(accept_frame)begin base<=frame_base;valid_lines<=0;frame_loaded<=1;end
                    else if(accept_slow)begin
                        slow_x<=query_x;slow_y<=query_y;
                        slow_fx<=query_fx;slow_fy<=query_fy;slow_tag<=query_tag;
                        neighbour<=0;state<=SELECT;
                    end
                end
                SELECT:begin
                    if(!neighbour_in_bounds)begin
                        slow_pixel[neighbour]<=0;
                        if(neighbour==3)state<=RESULT;else neighbour<=neighbour+1'b1;
                    end else begin
                        selected_block<=selected_number[31:7];selected_line<=cache_line_index(nx,ny,selected_number);
                        selected_pixel_address<={cache_line_index(nx,ny,selected_number),selected_number[6:3]};
                        selected_parity<=selected_number[0];selected_lane<=selected_number[2:1];
                        // Slow address arithmetic ends here. The next cycle
                        // reads/compares the current tag and invalidates only
                        // the registered line, never a combinational ny*WIDTH.
                        state<=SLOW_LOOKUP;
                    end
                end
                SLOW_LOOKUP:state<=CHECK;
                CHECK:begin
                        if(selected_cached_valid && selected_cached_tag==selected_block)begin
                            hit_count<=hit_count+1'b1;state<=LOAD;
                        end else begin
                            valid_lines[selected_line]<=0;
                            miss_count<=miss_count+1'b1;fill_beat<=0;address_pending<=1;state<=AR;
                        end
                end
                AR:if(accept_address)state<=FILL;
                FILL:begin end

                LOAD:state<=PICK;
                PICK:begin
                    slow_pixel[neighbour]<=expand565(selected_word);
                    if(neighbour==3)state<=RESULT;
                    else begin neighbour<=neighbour+1'b1;state<=SELECT;end
                end
                RESULT:if(out_ready)state<=IDLE;
                FAULT:state<=FAULT;
                default:begin failed<=1;fault<=8'hff;state<=FAULT;end
            endcase
            if(!failed && rvalid)begin
                if(!receiving)begin failed<=1;fault<=8'h04;state<=FAULT;valid_lines[selected_line]<=0;end
                else if(rid!=0 || rlast!=(fill_beat==7))begin failed<=1;fault<=8'h03;state<=FAULT;valid_lines[selected_line]<=0;end
                else begin
                    if(fill_beat==7)begin
                        // The final four 64-bit RAM writes commit on this edge.
                        // Expose the line only after all 8 reserved beats pass checks.
                        valid_lines[selected_line]<=1;tags[selected_line]<=selected_block;state<=LOAD;
                    end
                    else fill_beat<=fill_beat+1'b1;
                end
            end
            if(!failed && &watchdog && !progress && (state==AR || state==FILL))begin
                failed<=1;fault<=8'h01;state<=FAULT;valid_lines[selected_line]<=0;
            end
        end
    end
endmodule
