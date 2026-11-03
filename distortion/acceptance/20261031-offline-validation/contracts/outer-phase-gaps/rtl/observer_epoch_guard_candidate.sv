`timescale 1ns/1ps
// Pure self-developed PROTOTYPE. Common reset remains asynchronous.
// readiness_ref must be a reference-clock register, asynchronously cleared
// by the same common reset, as power_ready/rx_done_ref are in the real top.
// No ready signal is connected to an asynchronous reset pin here.
// Ready loss after commitment is fail-closed until COMMON reset. This
// intentionally stronger retry policy is not claimed production-equivalent.
module observer_epoch_guard_candidate(
 input wire ref_clk,pclk,reset_n,readiness_ref,
 output wire ref_permit,pixel_permit,
 output reg blocked=0
);
 (* async_reg="true" *) reg [1:0] ref_release=0;
 (* async_reg="true" *) reg [1:0] permit_sync=0;
 reg committed=0;
 always @(posedge ref_clk or negedge reset_n)
  if(!reset_n)begin ref_release<=0;committed<=0;blocked<=0;end
  else begin
   ref_release<={ref_release[0],1'b1};
   if(!ref_release[1])begin committed<=0;blocked<=0;end
   else if(committed && !readiness_ref)blocked<=1;
   else if(!blocked && readiness_ref)committed<=1;
  end
 assign ref_permit=reset_n && ref_release[1] && committed && !blocked && readiness_ref;
 always @(posedge pclk or negedge reset_n)
  if(!reset_n)permit_sync<=0;
  else permit_sync<={permit_sync[0],ref_permit};
 assign pixel_permit=reset_n && permit_sync[1];
endmodule
