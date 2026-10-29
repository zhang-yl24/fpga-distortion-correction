`timescale 1ns/1ps
// Independent scatter4 candidate; no physical RAM/STA claim.
// Same port interface with distinct module names; the frozen original may
// coexist in a simulation source closure but is not the instantiated candidate. Two16bit even/odd true-dual-port organizations;
// each has one upper-row and one lower-row read port. No replicated row RAM and
// no independent fallback cache. Logical INDEX3 storage=2048bytes plus256byte
// DDR burst staging. Physical DRM/FF/timing await separate PDS measurement.
// A miss drains fast hits, locks the query, then saves each neighbour BEFORE
// selecting the next; four mutually conflicting lines need not coexist.
// Registered-ready boundary: upstream coordinates cannot feed all_hit/ready
// back into mapper/rotation global stall clock enables. This FIFO has two
// complete query registers; its ready uses ONLY registered occupancy/loaded,
// frame_valid and the inner registered failure. It deliberately has no
// full+pop lookahead, bypass, or combinational inner_ready dependency.
module ddr_neighbour_cache_scatter4 #(
    parameter WIDTH=640,HEIGHT=480,TAG_W=24,INDEX_BITS=3,TIMEOUT_BITS=26
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
    ddr_compact_neighbour_cache_core_scatter4 #(.WIDTH(WIDTH),.HEIGHT(HEIGHT),.TAG_W(TAG_W),
        .INDEX_BITS(INDEX_BITS),.TIMEOUT_BITS(TIMEOUT_BITS)) inner(
        .clk(clk),.rst_n(rst_n),.frame_valid(frame_valid && queue_empty),
        .frame_ready(inner_frame_ready),.frame_base(frame_base),
        .in_valid(!queue_empty && !failed),.in_ready(inner_in_ready),
        .in_x(queue_x[read_pointer]),.in_y(queue_y[read_pointer]),.in_tag(queue_tag[read_pointer]),
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
module ddr_compact_neighbour_cache_core_scatter4 #(
    parameter WIDTH=640,HEIGHT=480,TAG_W=24,INDEX_BITS=3,TIMEOUT_BITS=26
)(
    input clk,rst_n,
    input frame_valid,output wire frame_ready,input [27:0] frame_base,
    input in_valid,output wire in_ready,input signed [23:0] in_x,in_y,
    input [TAG_W-1:0] in_tag,
    output wire out_valid,input out_ready,output wire [23:0] p00,p10,p01,p11,
    output wire [7:0] fx,fy,output wire [TAG_W-1:0] out_tag,
    output wire [27:0] araddr,output wire [3:0] arlen,output wire arvalid,input arready,
    input [255:0] rdata,input rvalid,rlast,input [3:0] rid,
    output reg failed,output reg [7:0] fault,
    output wire [31:0] hits,misses,completed_queries
);
    localparam LINES=1<<INDEX_BITS,ADDRESS_BITS=INDEX_BITS+6;
    localparam IDLE=0,SELECT=1,AR=2,FILL=3,SCATTER=4,LOAD=5,PICK=6,RESULT=7,FAULT=8,CHECK=9;
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
    reg [2:0] fill_beat;
    reg [4:0] scatter_group;
    (* ram_style="registers" *) reg [255:0] fill_buffer[0:7];
    reg [TIMEOUT_BITS-1:0] watchdog;
    reg [31:0] hit_count,miss_count,complete_count;
    reg v0,v1;
    reg [3:0] bounds0,parity0;
    reg [7:0] fx0,fy0,fx1,fy1;
    reg [TAG_W-1:0] tag0,tag1;
    reg [23:0] fast_pixel[0:3];
    reg query_valid;
    reg signed [16:0] query_x,query_y;
    reg [7:0] query_fx,query_fy;
    reg [TAG_W-1:0] query_tag;
    reg [3:0] in_bounds;
    reg [31:0] pixel_number[0:3];
    wire signed [16:0] x0=$signed(in_x[23:8]),y0=$signed(in_y[23:8]);
    wire [3:0] decoded_bounds,line_hit;
    wire [31:0] decoded_number[0:3];
    wire [ADDRESS_BITS-1:0] pixel_address[0:3];
    wire all_hit=&line_hit;
    wire stage1_ready=!v1 || out_ready;
    wire stage0_ready=!v0 || stage1_ready;
    wire empty=!v0 && !v1;
    wire accept_query;
    assign frame_ready=state==IDLE && empty && !query_valid && !failed;
    assign in_ready=frame_loaded && !frame_valid && !failed && state==IDLE &&
        (!query_valid || accept_query);
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
    wire receiving=state==FILL || (state==AR && accept_address);
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
        assign decoded_number[n]=iy*WIDTH+ix;
        assign pixel_address[n]=pixel_number[n][1 +: ADDRESS_BITS];
        assign line_hit[n]=!in_bounds[n] || (valid_lines[pixel_number[n][7 +: INDEX_BITS]] &&
            tags[pixel_number[n][7 +: INDEX_BITS]]==pixel_number[n][31:7]);
    end endgenerate
    wire [ADDRESS_BITS-1:0] even_upper=pixel_number[0][0] ? pixel_address[1]:pixel_address[0];
    wire [ADDRESS_BITS-1:0] odd_upper=pixel_number[0][0] ? pixel_address[0]:pixel_address[1];
    wire [ADDRESS_BITS-1:0] even_lower=pixel_number[2][0] ? pixel_address[3]:pixel_address[2];
    wire [ADDRESS_BITS-1:0] odd_lower=pixel_number[2][0] ? pixel_address[2]:pixel_address[3];
    // Two mutually exclusive read/write ports per even/odd array. No RAM
    // or read-register reset; scatter uses both ports, normal reads use A/B.
    wire scatter_write=rst_n && state==SCATTER && !failed;
    wire read_enable=rst_n && !failed && (accept_fast || state==LOAD);
    wire read_lower=rst_n && accept_fast;
    wire [ADDRESS_BITS-1:0] write_address_a={selected_line,scatter_group,1'b0};
    wire [ADDRESS_BITS-1:0] write_address_b={selected_line,scatter_group,1'b1};
    wire [ADDRESS_BITS-1:0] even_a=scatter_write ? write_address_a:state==LOAD ? selected_pixel_address:even_upper;
    wire [ADDRESS_BITS-1:0] odd_a=scatter_write ? write_address_a:state==LOAD ? selected_pixel_address:odd_upper;
    wire [ADDRESS_BITS-1:0] even_b=scatter_write ? write_address_b:even_lower;
    wire [ADDRESS_BITS-1:0] odd_b=scatter_write ? write_address_b:odd_lower;
    wire [63:0] fill_quad=fill_buffer[scatter_group[4:2]][scatter_group[1:0]*64 +:64];
    (* ram_style="block" *) reg [15:0] even_pixels[0:LINES*64-1];
    (* ram_style="block" *) reg [15:0] odd_pixels[0:LINES*64-1];
    reg [15:0] even_q_upper,odd_q_upper,even_q_lower,odd_q_lower;
    always @(posedge clk)begin
        if(scatter_write)even_pixels[even_a]<=fill_quad[15:0];
        else if(read_enable)even_q_upper<=even_pixels[even_a];
    end
    always @(posedge clk)begin
        if(scatter_write)even_pixels[even_b]<=fill_quad[47:32];
        else if(read_lower)even_q_lower<=even_pixels[even_b];
    end
    always @(posedge clk)begin
        if(scatter_write)odd_pixels[odd_a]<=fill_quad[31:16];
        else if(read_enable)odd_q_upper<=odd_pixels[odd_a];
    end
    always @(posedge clk)begin
        if(scatter_write)odd_pixels[odd_b]<=fill_quad[63:48];
        else if(read_lower)odd_q_lower<=odd_pixels[odd_b];
    end
    wire [15:0] selected_word=selected_parity ? odd_q_upper:even_q_upper;
    integer i;
    always @(posedge clk)begin
        if(!rst_n)begin
            state<=IDLE;frame_loaded<=0;address_pending<=0;base<=0;valid_lines<=0;
            slow_x<=0;slow_y<=0;neighbour<=0;slow_fx<=0;slow_fy<=0;slow_tag<=0;
            selected_block<=0;selected_line<=0;selected_pixel_address<=0;selected_parity<=0;
            fill_beat<=0;scatter_group<=0;watchdog<=0;failed<=0;fault<=0;
            hit_count<=0;miss_count<=0;complete_count<=0;
            v0<=0;v1<=0;bounds0<=0;parity0<=0;fx0<=0;fy0<=0;fx1<=0;fy1<=0;tag0<=0;tag1<=0;
            query_valid<=0;query_x<=0;query_y<=0;query_fx<=0;query_fy<=0;query_tag<=0;in_bounds<=0;
            for(i=0;i<4;i=i+1)begin slow_pixel[i]<=0;fast_pixel[i]<=0;pixel_number[i]<=0;end
        end else begin
            // Same-cycle consume/refill sustains one decoded fast hit per clk.
            // If lookup or the DDR slow path stalls, the complete decoded head
            // remains unchanged even while the external FIFO receives input.
            if(decode_query)begin
                query_valid<=1;query_x<=x0;query_y<=y0;
                query_fx<=in_x[7:0];query_fy<=in_y[7:0];query_tag<=in_tag;in_bounds<=decoded_bounds;
                for(i=0;i<4;i=i+1)pixel_number[i]<=decoded_number[i];
            end else if(accept_query)query_valid<=0;
            if(address_pending && arready)address_pending<=0;
            if(progress || (state!=AR && state!=FILL))watchdog<=0;
            else watchdog<=watchdog+1'b1;
            if(stage1_ready)begin
                v1<=v0;fx1<=fx0;fy1<=fy0;tag1<=tag0;
                if(v0)begin
                    fast_pixel[0]<=bounds0[0] ? expand565(parity0[0] ? odd_q_upper:even_q_upper):24'd0;
                    fast_pixel[1]<=bounds0[1] ? expand565(parity0[1] ? odd_q_upper:even_q_upper):24'd0;
                    fast_pixel[2]<=bounds0[2] ? expand565(parity0[2] ? odd_q_lower:even_q_lower):24'd0;
                    fast_pixel[3]<=bounds0[3] ? expand565(parity0[3] ? odd_q_lower:even_q_lower):24'd0;
                end
            end
            if(stage0_ready)v0<=accept_fast;
            if(accept_fast)begin
                bounds0<=in_bounds;fx0<=query_fx;fy0<=query_fy;tag0<=query_tag;
                for(i=0;i<4;i=i+1)parity0[i]<=pixel_number[i][0];
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
                        selected_block<=selected_number[31:7];selected_line<=selected_number[7 +: INDEX_BITS];
                        selected_pixel_address<=selected_number[1 +: ADDRESS_BITS];selected_parity<=selected_number[0];
                        // Slow address arithmetic ends here. The next cycle
                        // reads/compares the current tag and invalidates only
                        // the registered line, never a combinational ny*WIDTH.
                        state<=CHECK;
                    end
                end
                CHECK:begin
                        if(valid_lines[selected_line] && tags[selected_line]==selected_block)begin
                            hit_count<=hit_count+1'b1;state<=LOAD;
                        end else begin
                            valid_lines[selected_line]<=0;
                            miss_count<=miss_count+1'b1;fill_beat<=0;address_pending<=1;state<=AR;
                        end
                end
                AR:if(accept_address)state<=FILL;
                FILL:begin end
                SCATTER:begin
                    if(scatter_group==31)begin
                        valid_lines[selected_line]<=1;tags[selected_line]<=selected_block;state<=LOAD;
                    end else scatter_group<=scatter_group+1'b1;
                end
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
                    fill_buffer[fill_beat]<=rdata;
                    if(fill_beat==7)begin scatter_group<=0;state<=SCATTER;end
                    else fill_beat<=fill_beat+1'b1;
                end
            end
            if(!failed && &watchdog && !progress && (state==AR || state==FILL))begin
                failed<=1;fault<=8'h01;state<=FAULT;valid_lines[selected_line]<=0;
            end
        end
    end
endmodule
