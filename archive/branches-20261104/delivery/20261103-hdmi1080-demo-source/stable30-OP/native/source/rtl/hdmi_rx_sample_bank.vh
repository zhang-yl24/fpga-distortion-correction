// One coherent input stage, existing PCLK rising edge. No enable/reset gating.
// Clocked consumers see the preceding PCLK sample: exactly1cycle latency.
reg [26:0] hdmi_rx_sample=27'b0;
always @(posedge pixclk_in)hdmi_rx_sample<={vs_in,hs_in,de_in,r_in,g_in,b_in};
wire sampled_vs=hdmi_rx_sample[26];
wire sampled_hs=hdmi_rx_sample[25];
wire sampled_de=hdmi_rx_sample[24];
wire [23:0] sampled_rgb=hdmi_rx_sample[23:0];
