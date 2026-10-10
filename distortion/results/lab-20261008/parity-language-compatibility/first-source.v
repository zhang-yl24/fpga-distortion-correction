`timescale 1ns/1ps
// Isolated even/odd pixel bank experiment, two row-read replicas.
// Four 128-bit memories cost 16KiB plus the unchanged 8KiB fallback.
// Hits retain the same elastic two-stage protocol. Board resources and
// timing require separate measurement; no hardware claim from this RTL.
module ddr_neighbour_cache #(
    parameter WIDTH=640, HEIGHT=480, TAG_W=24, INDEX_BITS=5, TIMEOUT_BITS=26
)(
    input clk,rst_n,
    input frame_valid, output wire frame_ready, input [27:0] frame_base,
    input in_valid, output wire in_ready,
    input signed [23:0] in_x,in_y, input [TAG_W-1:0] in_tag,
    output wire out_valid, input out_ready,
    output wire [23:0] p00,p10,p01,p11,
    output wire [7:0] fx,fy, output wire [TAG_W-1:0] out_tag,
    output wire [27:0] araddr, output wire [3:0] arlen,
    output wire arvalid, input arready,
    input [255:0] rdata, input rvalid,rlast, input [3:0] rid,
    output wire failed, output wire [7:0] fault,
    output wire [31:0] hits,misses,completed_queries
);
    localparam LINES=1<<INDEX_BITS;
    reg loaded,slow_busy,read_active;
    reg [27:0] base;
    reg [LINES-1:0] valid_lines;
    reg [23:0] tags[0:LINES-1];
    reg [23:0] fill_block;
    reg [INDEX_BITS-1:0] fill_line;
    reg [2:0] fill_beat;
    reg v0,v1;
    reg [3:0] bounds0;
    reg [3:0] lane0[0:3];
    reg [7:0] fx0,fy0,fx1,fy1;
    reg [TAG_W-1:0] tag0,tag1;
    reg [23:0] pixels1[0:3];
    reg [31:0] hit_count,fast_completed;
    wire backend_frame_ready,backend_in_ready,backend_valid;
    wire [23:0] bp00,bp10,bp01,bp11;
    wire [7:0] bfx,bfy;
    wire [TAG_W-1:0] btag;
    wire [31:0] backend_hits,backend_completed;
    wire signed [16:0] x0=$signed(in_x[23:8]);
    wire signed [16:0] y0=$signed(in_y[23:8]);
    wire [3:0] in_bounds,line_hit;
    wire [31:0] pixel_number[0:3];
    wire [INDEX_BITS-1:0] line_number[0:3];
    wire [INDEX_BITS+2:0] word_number[0:3];
    wire all_hit=&line_hit;
    wire stage1_ready=!v1 || out_ready;
    wire stage0_ready=!v0 || stage1_ready;
    wire empty=!v0 && !v1;
    assign frame_ready=empty && !slow_busy && backend_frame_ready && !failed;
    wire accept_frame=frame_valid && frame_ready;
    assign in_ready=loaded && !frame_valid && !slow_busy && !failed &&
        (all_hit ? stage0_ready : (empty && backend_in_ready));
    wire accept_fast=in_valid && in_ready && all_hit;
    wire accept_slow=in_valid && in_ready && !all_hit;
    wire consume_fast=v1 && out_ready && !failed;
    wire consume_slow=slow_busy && backend_valid && out_ready && !failed;
    assign out_valid=!failed && (v1 || (slow_busy && backend_valid));
    assign p00=v1 ? pixels1[0]:bp00;
    assign p10=v1 ? pixels1[1]:bp10;
    assign p01=v1 ? pixels1[2]:bp01;
    assign p11=v1 ? pixels1[3]:bp11;
    assign fx=v1 ? fx1:bfx;
    assign fy=v1 ? fy1:bfy;
    assign out_tag=v1 ? tag1:btag;
    assign hits=backend_hits+hit_count;
    assign completed_queries=backend_completed+fast_completed;
    function [23:0] expand565(input [15:0] p);
        expand565={p[15:11],p[15:13],p[10:5],p[10:9],p[4:0],p[4:2]};
    endfunction
    wire [127:0] bank_q[0:3];
    genvar n;
    generate for(n=0;n<4;n=n+1) begin: neighbour
        wire signed [16:0] nx=x0+(n%2);
        wire signed [16:0] ny=y0+(n/2);
        assign in_bounds[n]=nx>=0 && nx<WIDTH && ny>=0 && ny<HEIGHT;
        assign pixel_number[n]=ny*WIDTH+nx;
        assign line_number[n]=pixel_number[n][7 +: INDEX_BITS];
        assign word_number[n]=pixel_number[n][4 +: INDEX_BITS+3];
        assign line_hit[n]=!in_bounds[n] || (valid_lines[line_number[n]] &&
            tags[line_number[n]]==pixel_number[n][31:7]);
        wire [127:0] chosen=lane0[n][0] ? bank_q[2*(n/2)+1]:bank_q[2*(n/2)];
        always @(posedge clk)
            if(rst_n && stage1_ready && v0)
                pixels1[n]<=bounds0[n] ? expand565(chosen[lane0[n][3:1]*16 +:16]):24'd0;
    end
    for(n=0;n<4;n=n+1) begin: parity_bank
        // Horizontally adjacent pixels always occupy opposite parity banks,
        // including word/line boundaries. Top/bottom use independent copies.
        localparam LEFT=2*(n/2);
        wire [INDEX_BITS+2:0] address=(pixel_number[LEFT][0]==(n%2)) ? word_number[LEFT]:word_number[LEFT+1];
        wire [127:0] fill_data;
        for(genvar lane=0;lane<8;lane=lane+1) begin: fill_lane
            assign fill_data[lane*16 +:16]=rdata[(2*lane+(n%2))*16 +:16];
        end
        reg [127:0] memory[0:LINES*8-1];
        reg [127:0] q;
        assign bank_q[n]=q;
        always @(posedge clk) begin
            if(read_active && rvalid && !failed && rid==0 && rlast==(fill_beat==7))
                memory[{fill_line,fill_beat}]<=fill_data;
            if(accept_fast) q<=memory[address];
        end
    end endgenerate
    ddr_serial_neighbour_cache #(.WIDTH(WIDTH),.HEIGHT(HEIGHT),.TAG_W(TAG_W),
        .INDEX_BITS(INDEX_BITS),.TIMEOUT_BITS(TIMEOUT_BITS)) backend(
        .clk(clk),.rst_n(rst_n),.frame_valid(accept_frame),.frame_ready(backend_frame_ready),.frame_base(frame_base),
        .in_valid(accept_slow),.in_ready(backend_in_ready),.in_x(in_x),.in_y(in_y),.in_tag(in_tag),
        .out_valid(backend_valid),.out_ready(out_ready && slow_busy),
        .p00(bp00),.p10(bp10),.p01(bp01),.p11(bp11),.fx(bfx),.fy(bfy),.out_tag(btag),
        .araddr(araddr),.arlen(arlen),.arvalid(arvalid),.arready(arready),
        .rdata(rdata),.rvalid(rvalid),.rlast(rlast),.rid(rid),
        .failed(failed),.fault(fault),.hits(backend_hits),.misses(misses),.completed_queries(backend_completed));
    integer i;
    wire [27:0] relative_address=araddr-base;
    always @(posedge clk) begin
        if(!rst_n) begin
            loaded<=0;slow_busy<=0;read_active<=0;base<=0;valid_lines<=0;
            fill_block<=0;fill_line<=0;fill_beat<=0;
            v0<=0;v1<=0;bounds0<=0;fx0<=0;fy0<=0;fx1<=0;fy1<=0;tag0<=0;tag1<=0;
            hit_count<=0;fast_completed<=0;
            for(i=0;i<4;i=i+1) lane0[i]<=0;
        end else begin
            if(stage1_ready) begin
                v1<=v0;fx1<=fx0;fy1<=fy0;tag1<=tag0;
            end
            if(stage0_ready) v0<=accept_fast;
            if(accept_fast) begin
                bounds0<=in_bounds;fx0<=in_x[7:0];fy0<=in_y[7:0];tag0<=in_tag;
                for(i=0;i<4;i=i+1) lane0[i]<=pixel_number[i][3:0];
                hit_count<=hit_count+{31'd0,in_bounds[0]}+{31'd0,in_bounds[1]}+
                    {31'd0,in_bounds[2]}+{31'd0,in_bounds[3]};
            end
            if(consume_fast) fast_completed<=fast_completed+1'b1;
            if(accept_slow) slow_busy<=1;
            if(consume_slow) slow_busy<=0;
            if(accept_frame) begin loaded<=1;base<=frame_base;valid_lines<=0;end
            if(arvalid && arready) begin
                read_active<=1;fill_block<=relative_address>>6;
                fill_line<=relative_address[6 +: INDEX_BITS];fill_beat<=0;
                valid_lines[relative_address[6 +: INDEX_BITS]]<=0;
            end
            if(read_active && rvalid && !failed) begin
                if(rid!=0 || rlast!=(fill_beat==7)) read_active<=0;
                else if(fill_beat==7) begin
                    read_active<=0;valid_lines[fill_line]<=1;tags[fill_line]<=fill_block;
                end else fill_beat<=fill_beat+1'b1;
            end
        end
    end
endmodule
