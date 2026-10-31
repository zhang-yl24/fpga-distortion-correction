`timescale 1ns/1ps
// Isolated startup guard for the trained observer. Inactive sync is first
// inferred from two complete DE lines, then one complete fixed raster must
// pass before the sticky production observer is released. This is digital
// raster qualification, not HDMI PHY lock, electrical timing, or pixel proof.
module hdmi1080_input_status_frame_trained #(
    parameter WIDTH=1920,HEIGHT=1080,HTOTAL=2200,VTOTAL=1125,
    parameter ACTIVITY_REF_CYCLES=27000,PCLK_WINDOW_MIN=73500,PCLK_WINDOW_MAX=75000
)(
    input ref_clk,pix_clk,rst_n,pix_vs,pix_hs,pix_de,
    output normalized_vs,output qualified,failed,output [7:0] fault,
    output polarity_known_ref,vs_inactive_ref,hs_inactive_ref,
    output [31:0] good_frames,bad_frames,pclk_edges_per_window,
    output [15:0] last_pixels_per_line,last_lines
);
    reg [1:0] p_reset;
    always @(posedge pix_clk or negedge rst_n)
        if(!rst_n)p_reset<=0;else p_reset<={p_reset[0],1'b1};

    reg candidate_valid,candidate_vs,candidate_hs;
    reg first_line_valid,first_line_vs,first_line_hs;
    reg [16:0] train_pixels;
    reg train_line_active,train_line_bad,train_vs,train_hs;
    reg previous_candidate_valid;
    reg provisional_vs_previous,provisional_hs_previous,provisional_de_previous;
    reg provisional_saw_hs,provisional_frame_active,provisional_frame_bad;
    reg [31:0] provisional_hs_ticks,provisional_frame_ticks;
    reg [15:0] provisional_hs_count,provisional_de_lines;
    reg [16:0] provisional_de_pixels;
    reg raster_ready;

    wire provisional_vs=candidate_valid && (pix_vs ^ candidate_vs);
    wire provisional_hs=candidate_valid && (pix_hs ^ candidate_hs);
    wire provisional_vs_rise=provisional_vs && !provisional_vs_previous;
    wire provisional_hs_rise=provisional_hs && !provisional_hs_previous;
    wire provisional_de_fall=!pix_de && provisional_de_previous;

    always @(posedge pix_clk) begin
        if(!p_reset[1])begin
            candidate_valid<=0;candidate_vs<=0;candidate_hs<=0;
            first_line_valid<=0;first_line_vs<=0;first_line_hs<=0;
            train_pixels<=0;train_line_active<=0;train_line_bad<=0;train_vs<=0;train_hs<=0;
            previous_candidate_valid<=0;
            provisional_vs_previous<=0;provisional_hs_previous<=0;provisional_de_previous<=0;
            provisional_saw_hs<=0;provisional_frame_active<=0;provisional_frame_bad<=0;
            provisional_hs_ticks<=0;provisional_frame_ticks<=0;
            provisional_hs_count<=0;provisional_de_lines<=0;provisional_de_pixels<=0;
            raster_ready<=0;
        end else begin
            previous_candidate_valid<=candidate_valid;
            provisional_vs_previous<=provisional_vs;
            provisional_hs_previous<=provisional_hs;
            provisional_de_previous<=pix_de;

            // Learn a candidate from two full, matching active lines.
            if(!candidate_valid)begin
                if(pix_de)begin
                    if(!train_line_active)begin
                        train_line_active<=1;train_line_bad<=0;train_pixels<=1;
                        train_vs<=pix_vs;train_hs<=pix_hs;
                    end else begin
                        if(train_pixels<WIDTH+1)train_pixels<=train_pixels+1'b1;
                        if(pix_vs!=train_vs || pix_hs!=train_hs)train_line_bad<=1;
                    end
                end else if(train_line_active)begin
                    train_line_active<=0;train_pixels<=0;
                    if(!train_line_bad && train_pixels==WIDTH)begin
                        if(first_line_valid && first_line_vs==train_vs && first_line_hs==train_hs)begin
                            candidate_valid<=1;candidate_vs<=train_vs;candidate_hs<=train_hs;
                            first_line_valid<=0;
                        end else begin
                            first_line_valid<=1;
                            first_line_vs<=train_vs;
                            first_line_hs<=train_hs;
                        end
                    end else first_line_valid<=0;
                end
            end

            // Start a provisional frame at a normalized VS edge. Discard
            // partial startup history before this boundary without reporting a
            // sticky fault. Only a complete exact raster can release the strict
            // downstream observer.
            if(candidate_valid && provisional_vs_rise)begin
                if(provisional_frame_active &&
                   !provisional_frame_bad && !pix_de &&
                   provisional_frame_ticks+1==HTOTAL*VTOTAL &&
                   provisional_hs_count==VTOTAL && provisional_de_lines==HEIGHT)
                    raster_ready<=1;
                provisional_frame_active<=1;
                provisional_frame_bad<=0;
                provisional_frame_ticks<=0;
                provisional_hs_count<=provisional_hs_rise ? 1:0;
                provisional_de_lines<=0;
                provisional_de_pixels<=0;
                provisional_hs_ticks<=0;
                provisional_saw_hs<=provisional_hs_rise;
            end else if(candidate_valid && provisional_frame_active)begin
                if(provisional_frame_ticks<HTOTAL*VTOTAL+1)
                    provisional_frame_ticks<=provisional_frame_ticks+1'b1;
                if(provisional_hs_ticks<HTOTAL+1)
                    provisional_hs_ticks<=provisional_hs_ticks+1'b1;
                if(provisional_hs_rise)begin
                    if(provisional_saw_hs && provisional_hs_ticks+1!=HTOTAL)
                        provisional_frame_bad<=1;
                    provisional_saw_hs<=1;
                    provisional_hs_ticks<=0;
                    if(provisional_hs_count<VTOTAL+1)
                        provisional_hs_count<=provisional_hs_count+1'b1;
                end
                if(pix_de)begin
                    if(pix_vs!=candidate_vs || pix_hs!=candidate_hs)
                        provisional_frame_bad<=1;
                    if(provisional_de_pixels<WIDTH+1)
                        provisional_de_pixels<=provisional_de_pixels+1'b1;
                    if(provisional_de_pixels>=WIDTH)
                        provisional_frame_bad<=1;
                end else if(provisional_de_fall)begin
                    if(provisional_de_pixels!=WIDTH)
                        provisional_frame_bad<=1;
                    if(provisional_de_lines<HEIGHT+1)
                        provisional_de_lines<=provisional_de_lines+1'b1;
                    provisional_de_pixels<=0;
                end
            end
        end
    end

    wire inner_normalized_vs,inner_qualified,inner_failed,inner_known,inner_vs_idle,inner_hs_idle;
    wire [7:0] inner_fault;
    wire [31:0] inner_good,inner_bad,inner_edges;
    wire [15:0] inner_width,inner_height;
    hdmi1080_input_status_trained #(.WIDTH(WIDTH),.HEIGHT(HEIGHT),.HTOTAL(HTOTAL),.VTOTAL(VTOTAL),
        .ACTIVITY_REF_CYCLES(ACTIVITY_REF_CYCLES),.PCLK_WINDOW_MIN(PCLK_WINDOW_MIN),
        .PCLK_WINDOW_MAX(PCLK_WINDOW_MAX)) strict_observer(
        .ref_clk(ref_clk),.pix_clk(pix_clk),.rst_n(rst_n && raster_ready),
        .pix_vs(pix_vs),.pix_hs(pix_hs),.pix_de(pix_de),
        .normalized_vs(inner_normalized_vs),.qualified(inner_qualified),.failed(inner_failed),.fault(inner_fault),
        .polarity_known_ref(inner_known),.vs_inactive_ref(inner_vs_idle),.hs_inactive_ref(inner_hs_idle),
        .good_frames(inner_good),.bad_frames(inner_bad),.pclk_edges_per_window(inner_edges),
        .last_pixels_per_line(inner_width),.last_lines(inner_height));
    assign normalized_vs=inner_normalized_vs;
    assign qualified=inner_qualified;
    assign failed=inner_failed;
    assign fault=inner_fault;
    assign polarity_known_ref=inner_known;
    assign vs_inactive_ref=inner_vs_idle;
    assign hs_inactive_ref=inner_hs_idle;
    assign good_frames=inner_good;
    assign bad_frames=inner_bad;
    assign pclk_edges_per_window=inner_edges;
    assign last_pixels_per_line=inner_width;
    assign last_lines=inner_height;
endmodule
