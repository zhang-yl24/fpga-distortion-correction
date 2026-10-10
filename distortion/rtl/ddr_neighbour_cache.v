`timescale 1ns/1ps
// Four independent border-zero RGB565 neighbours for a signed Q15.8 query.
// Eight direct-mapped 512-byte lines. One unbackpressurable 16-beat DDR burst
// is reserved in a private cache line before AR; tags become valid at RLAST.
// A frame handshake invalidates all tags even when the same bank is reused.
module ddr_neighbour_cache #(
    parameter WIDTH=640, HEIGHT=480, TAG_W=24, INDEX_BITS=3, TIMEOUT_BITS=26
)(
    input clk,rst_n,
    input frame_valid, output wire frame_ready, input [27:0] frame_base,
    input in_valid, output wire in_ready,
    input signed [23:0] in_x,in_y, input [TAG_W-1:0] in_tag,
    output wire out_valid, input out_ready,
    output reg [23:0] p00,p10,p01,p11,
    output reg [7:0] fx,fy, output reg [TAG_W-1:0] out_tag,
    output wire [27:0] araddr, output wire [3:0] arlen,
    output wire arvalid, input arready,
    input [255:0] rdata, input rvalid,rlast, input [3:0] rid,
    output reg failed, output reg [7:0] fault,
    output reg [31:0] hits,misses,completed_queries
);
    localparam IDLE=0,SELECT=1,LOOKUP=2,AR=3,FILL=4,LOAD=5,PICK=6,RESULT=7,FAULT=8;
    localparam LINES=1<<INDEX_BITS;
    reg [3:0] state;
    reg frame_loaded;
    reg [27:0] base;
    reg signed [16:0] x0,y0;
    reg [1:0] neighbour;
    wire signed [16:0] nx=x0+$signed({16'b0,neighbour[0]});
    wire signed [16:0] ny=y0+$signed({16'b0,neighbour[1]});
    wire in_bounds=(nx>=0 && nx<WIDTH && ny>=0 && ny<HEIGHT);
    wire [31:0] pixel_index=ny*WIDTH+nx;
    reg [23:0] block_number;
    reg [INDEX_BITS-1:0] line_index;
    reg [3:0] beat_index,pixel_lane,fill_beat;
    reg [LINES-1:0] valid_lines;
    reg [23:0] tags [0:LINES-1];
    reg [255:0] cache_data [0:LINES*16-1];
    reg [255:0] cache_q;
    reg [TIMEOUT_BITS-1:0] watchdog;
    reg address_pending;
    wire [15:0] pixel=cache_q[pixel_lane*16 +:16];
    wire [23:0] rgb={pixel[15:11],pixel[15:13],pixel[10:5],pixel[10:9],pixel[4:0],pixel[4:2]};
    assign frame_ready=state==IDLE && !failed;
    assign in_ready=frame_ready && frame_loaded && !frame_valid;
    assign out_valid=state==RESULT && !failed;
    assign araddr=base+(block_number<<7);
    assign arlen=15;
    // Once asserted, ARVALID stays until handshake even if a timeout quarantines
    // the request. Reset is the recovery boundary; never withdraw a stalled AR.
    assign arvalid=address_pending;
    wire progress=(state==AR && arready)||(state==FILL && rvalid);
    // No reset on the memory itself; this is a synchronous simple-dual-port RAM.
    // A faulted burst leaves its cache tag invalid, including its final beat.
    always @(posedge clk) begin
        if(state==FILL && rvalid && !failed && rid==0 && rlast==(fill_beat==15))
            cache_data[{line_index,fill_beat}]<=rdata;
        if(state==LOAD) cache_q<=cache_data[{line_index,beat_index}];
    end
    integer i;
    always @(posedge clk) begin
        if(!rst_n) begin
            state<=IDLE;frame_loaded<=0;base<=0;x0<=0;y0<=0;neighbour<=0;
            block_number<=0;line_index<=0;beat_index<=0;pixel_lane<=0;fill_beat<=0;
            valid_lines<=0;watchdog<=0;failed<=0;fault<=0;address_pending<=0;
            hits<=0;misses<=0;completed_queries<=0;
            p00<=0;p10<=0;p01<=0;p11<=0;fx<=0;fy<=0;out_tag<=0;
        end else begin
            if(address_pending && arready) address_pending<=0;
            if(progress || (state!=AR && state!=FILL)) watchdog<=0;
            else watchdog<=watchdog+1'b1;
            case(state)
                IDLE: begin
                    if(frame_valid) begin base<=frame_base;valid_lines<=0;frame_loaded<=1;end
                    else if(in_valid && in_ready) begin
                        // Arithmetic floor via the signed upper 16 bits, not truncation toward zero.
                        x0<=$signed(in_x[23:8]);y0<=$signed(in_y[23:8]);
                        fx<=in_x[7:0];fy<=in_y[7:0];out_tag<=in_tag;
                        neighbour<=0;state<=SELECT;
                    end
                end
                SELECT: begin
                    if(!in_bounds) begin
                        case(neighbour) 0:p00<=0;1:p10<=0;2:p01<=0;3:p11<=0;endcase
                        if(neighbour==3) state<=RESULT;
                        else neighbour<=neighbour+1'b1;
                    end else begin
                        block_number<=pixel_index[31:8];
                        line_index<=pixel_index[8 +: INDEX_BITS];
                        beat_index<=pixel_index[7:4];pixel_lane<=pixel_index[3:0];state<=LOOKUP;
                    end
                end
                LOOKUP: begin
                    if(valid_lines[line_index] && tags[line_index]==block_number) begin
                        hits<=hits+1'b1;state<=LOAD;
                    end else begin
                        valid_lines[line_index]<=0;misses<=misses+1'b1;fill_beat<=0;address_pending<=1;state<=AR;
                    end
                end
                AR: if(arready) state<=FILL;
                FILL: if(rvalid) begin
                    if(rid!=0 || rlast!=(fill_beat==15)) begin failed<=1;fault<=8'h03;state<=FAULT;end
                    else if(fill_beat==15) begin
                        valid_lines[line_index]<=1;tags[line_index]<=block_number;state<=LOAD;
                    end else fill_beat<=fill_beat+1'b1;
                end
                LOAD: state<=PICK;
                PICK: begin
                    case(neighbour) 0:p00<=rgb;1:p10<=rgb;2:p01<=rgb;3:p11<=rgb;endcase
                    if(neighbour==3) state<=RESULT;
                    else begin neighbour<=neighbour+1'b1;state<=SELECT;end
                end
                RESULT: if(out_ready) begin state<=IDLE;completed_queries<=completed_queries+1'b1;end
                FAULT: state<=FAULT;
                default: begin failed<=1;fault<=8'hFF;state<=FAULT;end
            endcase
            if(!failed && rvalid && state!=FILL) begin failed<=1;fault<=8'h04;state<=FAULT;end
            if(!failed && &watchdog && !progress && (state==AR || state==FILL)) begin failed<=1;fault<=8'h01;state<=FAULT;end
        end
    end
endmodule
