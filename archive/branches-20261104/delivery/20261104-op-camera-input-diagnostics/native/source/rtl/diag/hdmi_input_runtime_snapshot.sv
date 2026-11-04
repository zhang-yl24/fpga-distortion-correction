`timescale 1ns/1ps
// Passive first runtime failure plus delayed reference-domain evidence only.
// No signal from this module controls resets, admission, DDR or scan ownership.
module hdmi_input_runtime_snapshot #(parameter integer FOLLOWUP_REF_CYCLES=54000)(
 input wire ref_clk,rst_n,pipeline_released,qualified,input_failed,ready_all,
 input wire [255:0] live_tuple,
 output reg first_valid=0,follow_valid=0,output reg [255:0] first_tuple=0,follow_tuple=0,
 output reg [31:0] ref_uptime=0,output reg uptime_wrapped=0
);
 reg [31:0] follow_count=0;
 initial if(FOLLOWUP_REF_CYCLES<1) $error("invalid followup delay");
 always @(posedge ref_clk or negedge rst_n)begin
  if(!rst_n)begin first_valid<=0;follow_valid<=0;first_tuple<=0;follow_tuple<=0;
   ref_uptime<=0;uptime_wrapped<=0;follow_count<=0;end
  else begin
   ref_uptime<=ref_uptime+1'b1;if(&ref_uptime)uptime_wrapped<=1;
   if(!first_valid && pipeline_released && (!qualified || input_failed || !ready_all))begin
    first_valid<=1;first_tuple<=live_tuple;follow_count<=0;
   end else if(first_valid && !follow_valid)begin
    if(follow_count==FOLLOWUP_REF_CYCLES-1)begin follow_valid<=1;follow_tuple<=live_tuple;end
    else follow_count<=follow_count+1'b1;
   end
  end
 end
endmodule
