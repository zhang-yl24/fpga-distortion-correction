`timescale 1ns/1ps
// One PCLK sampling stage for all 27 input bits. This establishes a common
// digital sequence; it does not establish RGB packing or external setup/hold.
// Reset asserts locally without PCLK. Data clears synchronously; the valid
// output masks retained data immediately, including a stopped-source reset.
module hdmi_camera_pixel_sampler_old #(
    parameter integer VS_ACTIVE_LEVEL=1,
    parameter integer DE_ACTIVE_LEVEL=1
)(
    input pclk,rst_n,raw_vs,raw_hs,raw_de,
    input [23:0] raw_rgb,
    (* syn_preserve=1, syn_srlstyle="registers" *) output reg sampled_vs,sampled_hs,sampled_de,
    (* syn_preserve=1, syn_srlstyle="registers" *) output reg [23:0] sampled_rgb,
    output wire sampled_valid,vs_active,de_active
);
    (* PAP_ASYNC_REG=1, syn_preserve=1, syn_srlstyle="registers" *) reg [1:0] p_reset=0;
    always @(posedge pclk or negedge rst_n)
        if(!rst_n)p_reset<=0;else p_reset<={p_reset[0],1'b1};
    (* syn_preserve=1, syn_srlstyle="registers" *) reg sample_valid_hold;
    always @(posedge pclk)begin
        if(!p_reset[1])begin
            sampled_vs<=0;sampled_hs<=0;sampled_de<=0;sampled_rgb<=0;sample_valid_hold<=0;
        end else begin
            {sampled_vs,sampled_hs,sampled_de,sampled_rgb}<={raw_vs,raw_hs,raw_de,raw_rgb};
            sample_valid_hold<=1;
        end
    end
    localparam POLARITY_OK=(VS_ACTIVE_LEVEL==0 || VS_ACTIVE_LEVEL==1) &&
        (DE_ACTIVE_LEVEL==0 || DE_ACTIVE_LEVEL==1);
    assign sampled_valid=p_reset[1] && sample_valid_hold;
    assign vs_active=POLARITY_OK && sampled_valid && (sampled_vs==VS_ACTIVE_LEVEL[0]);
    assign de_active=POLARITY_OK && sampled_valid && (sampled_de==DE_ACTIVE_LEVEL[0]);
    // A valid first sample establishes a consumer's history/baseline. A
    // consumer must not compare it to the reset value to invent an edge.
endmodule
