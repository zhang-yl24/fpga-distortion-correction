`timescale 1ns/1ps
// Observe VSYNC in the core clock domain; do not depend on blanking PCLK.
// last_period is the interval between synchronized frame-start edges.
module camera_frame_period(input clk,rst_n,vsync,output reg [31:0] last_period);
    (* async_reg="true" *) reg [1:0] sync;
    reg previous,seen;
    reg [31:0] count;
    always @(posedge clk) begin
        if(!rst_n) begin sync<=0;previous<=0;seen<=0;count<=0;last_period<=0;end
        else begin
            sync<={sync[0],vsync};previous<=sync[1];
            if(sync[1] && !previous) begin
                if(seen) last_period<=count+1'b1;
                count<=0;seen<=1;
            end else if(seen) count<=count+1'b1;
        end
    end
endmodule
