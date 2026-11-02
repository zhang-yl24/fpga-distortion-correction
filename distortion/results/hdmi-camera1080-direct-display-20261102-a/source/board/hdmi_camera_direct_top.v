`timescale 1ns/1ps
// Independent reversible RGB888 direct-display diagnostic. No DDR or frame store.
// RGB/HS/VS/DE share one PCLK sampler; the forwarded clock always runs with input.
// This is a digital experiment, not acceptance of RX/TX external AC or RGB format.
module hdmi_camera_direct_top #(
    parameter integer INPUT_TIMING_CONFIGURED=0,
    parameter integer RX_VS_ACTIVE_LEVEL=1,
    parameter integer RX_DE_ACTIVE_LEVEL=1,
    parameter integer CFG_SETTLE_CYCLES=2700000
)(
    input clk_27m,reset_n,pixclk_in,vs_in,hs_in,de_in,
    input [7:0] r_in,g_in,b_in,
    output pix_clk,hs_out,vs_out,de_out,
    output [7:0] r_out,g_out,b_out,
    inout hd_scl,hd_sda,
    output rstn_out,output [7:0] led
);
    // Only the observed positive-VS/positive-DE digital timing is selected by
    // this builder. Defaults remain blank. HS polarity is passed unchanged.
    localparam TIMING_CONFIG_OK=INPUT_TIMING_CONFIGURED==1 &&
        RX_VS_ACTIVE_LEVEL==1 && RX_DE_ACTIVE_LEVEL==1 && CFG_SETTLE_CYCLES>=1;
    (* async_reg="true" *) reg [1:0] key_reset_sync=0;
    always @(posedge clk_27m or negedge reset_n)
        if(!reset_n)key_reset_sync<=0;else key_reset_sync<={key_reset_sync[0],1'b1};
    reg [19:0] power_count=0;
    reg power_ready=0;
    always @(posedge clk_27m or negedge reset_n)begin
        if(!reset_n)begin power_count<=0;power_ready<=0;end
        else if(!key_reset_sync[1])begin power_count<=0;power_ready<=0;end
        else if(!(&power_count))power_count<=power_count+1'b1;
        else power_ready<=1;
    end
    wire global_reset_n=reset_n && power_ready;
    assign rstn_out=global_reset_n;
    reg [31:0] cfg_wait_count=0;
    reg cfg_ready=0;
    always @(posedge clk_27m or negedge global_reset_n)begin
        if(!global_reset_n)begin cfg_wait_count<=0;cfg_ready<=0;end
        else if(!cfg_ready)begin
            if(cfg_wait_count<CFG_SETTLE_CYCLES-1)cfg_wait_count<=cfg_wait_count+1'b1;
            else cfg_ready<=1;
        end
    end
    wire cfg_reset_n=global_reset_n && cfg_ready;
    wire cfg_clk,cfg_lock;
    cfg_pll configuration_pll(.clkin1(clk_27m),.clkout0(cfg_clk),.lock(cfg_lock));
    wire rx_done,tx_done,cfg_failed;
    wire [3:0] cfg_error;
    wire [31:0] cfg_transactions;
    wire [15:0] cfg_last_address;
    wire [7:0] cfg_last_value;
    wire [1:0] cfg_last_meta;
    ms72xx_rearm_observed_ctl hdmi_configuration(
        .clk(cfg_clk),.rst_n(cfg_reset_n),.init_over_rx(rx_done),.init_over(tx_done),
        .init_failed(cfg_failed),.error_code(cfg_error),.iic_scl(hd_scl),.iic_sda(hd_sda),
        .completed_transactions(cfg_transactions),.last_address(cfg_last_address),
        .last_value(cfg_last_value),.last_meta(cfg_last_meta));

    (* async_reg="true" *) reg [1:0] ref_reset=0;
    (* async_reg="true" *) reg [1:0] cfg_lock_ref,rx_done_ref,tx_done_ref,cfg_failed_ref;
    always @(posedge clk_27m or negedge global_reset_n)begin
        if(!global_reset_n)begin
            ref_reset<=0;cfg_lock_ref<=0;rx_done_ref<=0;tx_done_ref<=0;cfg_failed_ref<=0;
        end else begin
            ref_reset<={ref_reset[0],1'b1};
            if(!ref_reset[1])begin
                cfg_lock_ref<=0;rx_done_ref<=0;tx_done_ref<=0;cfg_failed_ref<=0;
            end else begin
                cfg_lock_ref<={cfg_lock_ref[0],cfg_lock};rx_done_ref<={rx_done_ref[0],rx_done};
                tx_done_ref<={tx_done_ref[0],tx_done};cfg_failed_ref<={cfg_failed_ref[0],cfg_failed};
            end
        end
    end
    reg ref_ready=0,board_failed=0;
    reg [23:0] heart_count=0;
    reg heartbeat=0;
    always @(posedge clk_27m or negedge global_reset_n)begin
        if(!global_reset_n)begin ref_ready<=0;board_failed<=0;heart_count<=0;heartbeat<=0;end
        else if(!ref_reset[1])begin ref_ready<=0;board_failed<=0;heart_count<=0;heartbeat<=0;end
        else begin
            if(heart_count==13499999)begin heart_count<=0;heartbeat<=!heartbeat;end
            else heart_count<=heart_count+1'b1;
            ref_ready<=TIMING_CONFIG_OK && cfg_ready && cfg_lock_ref[1] && rx_done_ref[1] &&
                tx_done_ref[1] && !cfg_failed_ref[1] && !board_failed;
            if(cfg_failed_ref[1] || (ref_ready && (!cfg_lock_ref[1] || !rx_done_ref[1] || !tx_done_ref[1])))
                board_failed<=1;
        end
    end

    (* async_reg="true" *) reg [1:0] input_reset=0,ready_pix=0;
    always @(posedge pixclk_in or negedge global_reset_n)begin
        if(!global_reset_n)begin input_reset<=0;ready_pix<=0;end
        else begin
            input_reset<={input_reset[0],1'b1};
            if(!input_reset[1])ready_pix<=0;
            else ready_pix<={ready_pix[0],ref_ready};
        end
    end
    wire sampled_vs,sampled_hs,sampled_de,sampled_valid;
    wire input_vs_active,input_de_active;
    wire [23:0] sampled_rgb;
    hdmi_camera_pixel_sampler #(.VS_ACTIVE_LEVEL(RX_VS_ACTIVE_LEVEL),.DE_ACTIVE_LEVEL(RX_DE_ACTIVE_LEVEL)) input_sampler(
        .pclk(pixclk_in),.rst_n(global_reset_n),.raw_vs(vs_in),.raw_hs(hs_in),.raw_de(de_in),
        .raw_rgb({r_in,g_in,b_in}),.sampled_vs(sampled_vs),.sampled_hs(sampled_hs),.sampled_de(sampled_de),
        .sampled_rgb(sampled_rgb),.sampled_valid(sampled_valid),.vs_active(input_vs_active),.de_active(input_de_active));
    // No ready/configuration signal gates the forwarded clock. All output
    // data/control values come from the same single registered input bundle.
    assign pix_clk=pixclk_in;
    assign {r_out,g_out,b_out}=sampled_rgb;
    assign hs_out=sampled_hs;
    assign vs_out=sampled_vs;
    // Only DE is blanked. Ready crosses two local FFs before it can enable DE;
    // common reset also masks a retained sampler value when PCLK is stopped.
    assign de_out=TIMING_CONFIG_OK && input_reset[1] && ready_pix[1] && sampled_valid &&
        input_de_active && sampled_de;
    assign led={cfg_failed_ref[1],board_failed,ref_ready,tx_done_ref[1],rx_done_ref[1],
        cfg_lock_ref[1],cfg_ready,heartbeat};
endmodule
