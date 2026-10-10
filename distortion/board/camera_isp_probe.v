// OV5640 DVP/VGA/RGB565 setup + critical register readback + HDMI pattern.
module camera_isp_probe(input clk_27m,cam_pclk,cam_vsync,cam_href,input [7:0] cam_data, output [7:0] led, output uart_txd,
    inout cam_rst_n,cam_scl,cam_sda, inout hd_scl,hd_sda,
    output rstn_out,pix_clk,hs_out,vs_out,de_out,
    output [7:0] r_out,g_out,b_out);
    reg [19:0] power_count=0;
    wire rst_n=&power_count;
    always @(posedge clk_27m) if(!rst_n) power_count<=power_count+1;
    reg [23:0] heart_count;
    reg heart;
    always @(posedge clk_27m) begin
        if(!rst_n) begin heart_count<=0; heart<=0; end
        else if(heart_count==13499999) begin heart_count<=0; heart<=!heart; end
        else heart_count<=heart_count+1;
    end
    wire [15:0] sensor_id; wire [7:0] cam_errors;
    wire cam_complete,cam_match,hd_ready,pll_lock;
    wire [3:0] hd_error;
    wire camera_ready,camera_failed;
    wire [15:0] camera_failed_address;
    wire [8:0] camera_writes;
    wire [8:0] camera_noacks;
    wire [7:0] camera_observed,camera_expected;
    ov5640_cadence_trial_init #(.DYNAMIC_PAD_MASK(1)) camera(.trial_pad_mask(16'h7ff0),.clk(clk_27m),.rst_n(rst_n),.cam_rst_n(cam_rst_n),
        .cam_scl(cam_scl),.cam_sda(cam_sda),.sensor_id(sensor_id),
        .ready(camera_ready),.failed(camera_failed),.error_code(cam_errors),
        .failed_address(camera_failed_address),.commands_written(camera_writes),.verified_write_noacks(camera_noacks),
        .observed_value(camera_observed),.expected_value(camera_expected));
    assign cam_complete=camera_ready || camera_failed;
    assign cam_match=camera_ready;
    assign rstn_out=rst_n;
    hdmi_tx_init hdmi(.clk(clk_27m),.rst_n(rst_n),.hd_scl(hd_scl),.hd_sda(hd_sda),
        .ready(hd_ready),.error(hd_error));
    bringup_pll video_pll(.clkin1(clk_27m),.clkout0(pix_clk),.lock(pll_lock));
    (* async_reg="true" *) reg [1:0] pixel_reset_sync=0;
    always @(posedge pix_clk or negedge pll_lock)
        if(!pll_lock) pixel_reset_sync<=0;
        else pixel_reset_sync<={pixel_reset_sync[0],1'b1};
    wire preview_ready;
    camera_preview picture(.cam_clk(cam_pclk),.rst_n(rst_n && pll_lock),.cam_ready(camera_ready),
        .vsync(!cam_vsync),.href(!cam_href),.data(cam_data),.pix_clk(pix_clk),
        .hs(hs_out),.vs(vs_out),.de(de_out),.r(r_out),.g(g_out),.b(b_out),.display_valid(preview_ready));
    assign led={probe_failed,preview_ready,|hd_error,|cam_errors,pll_lock,hd_ready,cam_match,heart};
    wire byte_valid,byte_ready,serial_busy,serial_done,probe_failed;
    wire [7:0] byte_data;wire [3:0] probe_fault;
    ov5640_state_scan scan(.clk(clk_27m),.rst_n(rst_n),.enabled(camera_ready && !camera_failed),
        .scl(cam_scl),.sda(cam_sda),.byte_valid(byte_valid),.byte_data(byte_data),
        .byte_ready(byte_ready),.failed(probe_failed),.fault(probe_fault));
    uart_tx #(.CLOCK_HZ(27000000),.BAUD(921600)) serial(.clk(clk_27m),.rst_n(rst_n),
        .start(byte_valid && byte_ready),.data(byte_data),.tx(uart_txd),.busy(serial_busy),.done(serial_done));
    assign byte_ready=!serial_busy;
endmodule
