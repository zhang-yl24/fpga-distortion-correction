`timescale 1ns/1ps
// Measures received DVP activity without assuming the camera frame rate.
// Gray counter crosses PCLK -> sysclk. Frame metadata uses a held-data handshake.
module dvp_monitor #(parameter WINDOW_CYCLES=27000)(
    input sysclk,rst_n,pclk,vsync,href,input [7:0] data,
    output reg [23:0] edges_per_window,
    output reg [31:0] frames,last_pixels,last_checksum,
    output reg [15:0] last_lines,output reg last_odd,
    output pixel_valid,output [15:0] pixel,output frame_start
);
    reg [1:0] pixel_reset=0;
    always @(posedge pclk or negedge rst_n)
        if(!rst_n) pixel_reset<=0;
        else pixel_reset<={pixel_reset[0],1'b1};
    wire line_end,odd;
    wire [31:0] frame_count,frame_pixels;
    dvp_rgb565_capture #(.HIGH_BYTE_FIRST(0)) capture(
        .pclk(pclk),.rst(!pixel_reset[1]),.vsync(vsync),.href(href),.data(data),
        .pixel_valid(pixel_valid),.pixel(pixel),.frame_start(frame_start),
        .line_end(line_end),.odd_line_error(odd),.frame_count(frame_count),.last_frame_pixels(frame_pixels));
    reg [23:0] edge_binary,edge_gray;
    reg edge_carry;
    reg [15:0] lines,held_lines;
    reg [31:0] held_frames,held_pixels,held_checksum,checksum;
    reg frame_odd,held_odd,request;
    reg acknowledge;
    (* async_reg="true" *) reg [1:0] ack_sync;
    always @(posedge pclk or negedge rst_n) begin
        if(!rst_n) begin
            edge_binary<=0;edge_gray<=0;edge_carry<=0;lines<=0;frame_odd<=0;
            held_lines<=0;held_frames<=0;held_pixels<=0;held_checksum<=0;checksum<=0;
            held_odd<=0;request<=0;ack_sync<=0;
        end else begin
            edge_binary[11:0]<=edge_binary[11:0]+1'b1;
            if(edge_carry) edge_binary[23:12]<=edge_binary[23:12]+1'b1;
            edge_carry<=edge_binary[11:0]==12'hffe;
            // Register Gray from the preceding binary count, keeping the
            // carry path out of the encoding path. Fixed one-edge latency.
            edge_gray<=edge_binary ^ (edge_binary>>1);
            ack_sync<={ack_sync[0],acknowledge};
            if(line_end) lines<=lines+1'b1;
            if(odd) frame_odd<=1;
            if(pixel_valid) checksum<={checksum[30:0],checksum[31]} ^ {16'b0,pixel};
            if(frame_start) begin
                if(request==ack_sync[1]) begin
                    held_lines<=lines;held_frames<=frame_count;held_pixels<=frame_pixels;
                    held_odd<=frame_odd;held_checksum<=checksum;request<=!request;
                end
                lines<=0;frame_odd<=0;checksum<=0;
            end
        end
    end
    (* async_reg="true" *) reg [23:0] gray_meta,gray_sync;
    (* async_reg="true" *) reg [1:0] request_sync;
    reg [23:0] previous_edges;
    reg [31:0] timer;
    reg settle;
    function [23:0] gray_decode;
        input [23:0] g;
        integer i;
        begin
            gray_decode[23]=g[23];
            for(i=22;i>=0;i=i-1) gray_decode[i]=gray_decode[i+1]^g[i];
        end
    endfunction
    wire [23:0] sampled_edges=gray_decode(gray_sync);
    always @(posedge sysclk) begin
        if(!rst_n) begin
            gray_meta<=0;gray_sync<=0;request_sync<=0;previous_edges<=0;timer<=0;
            edges_per_window<=0;frames<=0;last_pixels<=0;last_lines<=0;last_odd<=0;last_checksum<=0;
            acknowledge<=0;settle<=0;
        end else begin
            gray_meta<=edge_gray;gray_sync<=gray_meta;request_sync<={request_sync[0],request};
            if(timer==WINDOW_CYCLES-1) begin
                timer<=0;edges_per_window<=sampled_edges-previous_edges;previous_edges<=sampled_edges;
            end else timer<=timer+1;
            if(settle) begin
                frames<=held_frames;last_pixels<=held_pixels;last_lines<=held_lines;last_odd<=held_odd;last_checksum<=held_checksum;
                acknowledge<=request_sync[1];settle<=0;
            end else if(request_sync[1]!=acknowledge) settle<=1;
        end
    end
endmodule
