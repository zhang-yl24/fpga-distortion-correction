// OV5640 DVP/VGA/RGB565 setup + critical register readback + HDMI pattern.
module camera_init(input clk_27m, output [7:0] led, output uart_txd,
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
    ov5640_init camera(.clk(clk_27m),.rst_n(rst_n),.cam_rst_n(cam_rst_n),
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
    video_pattern #(.MODE_720P(1)) pattern(.clk(pix_clk),.rst_n(pixel_reset_sync[1]),
        .hs(hs_out),.vs(vs_out),.de(de_out),.r(r_out),.g(g_out),.b(b_out));
    assign led={2'b00,|hd_error,|cam_errors,pll_lock,hd_ready,cam_match,heart};
    function [7:0] hexchar;
        input [3:0] nibble;
        begin hexchar=nibble<10 ? 8'd48+nibble:8'd65+nibble-10; end
    endfunction
    reg [15:0] report_id;
    reg [7:0] report_errors;
    reg [3:0] report_hd_error;
    reg report_hd_ready;
    reg report_camera_ready;
    reg [8:0] report_writes;
    reg [8:0] report_noacks;
    reg [7:0] report_observed,report_expected;
    reg [15:0] report_failed_address;
    function [7:0] message;
        input [5:0] idx;
        begin
            case(idx)
                0:message="C"; 1:message="A"; 2:message="M"; 3:message="=";
                4:message=hexchar(report_id[15:12]); 5:message=hexchar(report_id[11:8]);
                6:message=hexchar(report_id[7:4]); 7:message=hexchar(report_id[3:0]);
                8:message=" "; 9:message="E"; 10:message="=";
                11:message=hexchar(report_errors[7:4]); 12:message=hexchar(report_errors[3:0]);
                13:message=" "; 14:message="H"; 15:message="D"; 16:message="M"; 17:message="I";
                18:message="="; 19:message=report_hd_ready ? "1":"0";
                20:message=" "; 21:message="E"; 22:message="="; 23:message=hexchar(report_hd_error);
                24:message=" ";25:message="I";26:message="N";27:message="I";28:message="T";
                29:message="=";30:message=report_camera_ready ? "1":"0";
                31:message=" ";32:message="W";33:message="=";
                34:message=hexchar({3'b0,report_writes[8]});
                35:message=hexchar(report_writes[7:4]);36:message=hexchar(report_writes[3:0]);
                37:message=" ";38:message="A";39:message="=";
                40:message=hexchar(report_failed_address[15:12]);41:message=hexchar(report_failed_address[11:8]);
                42:message=hexchar(report_failed_address[7:4]);43:message=hexchar(report_failed_address[3:0]);
                44:message=" ";45:message="N";46:message="=";
                47:message=hexchar({3'b0,report_noacks[8]});48:message=hexchar(report_noacks[7:4]);49:message=hexchar(report_noacks[3:0]);
                50:message=" ";51:message="R";52:message="=";53:message=hexchar(report_observed[7:4]);54:message=hexchar(report_observed[3:0]);
                55:message=" ";56:message="T";57:message="=";58:message=hexchar(report_expected[7:4]);59:message=hexchar(report_expected[3:0]);
                60:message=13;61:message=10;
                default:message="?";
            endcase
        end
    endfunction
    reg [1:0] report_state;
    reg [5:0] report_index;
    reg [24:0] report_timer;
    reg tx_start; reg [7:0] tx_data;
    wire tx_busy,tx_done;
    uart_tx uart(.clk(clk_27m),.rst_n(rst_n),.start(tx_start),.data(tx_data),
        .tx(uart_txd),.busy(tx_busy),.done(tx_done));
    always @(posedge clk_27m) begin
        if(!rst_n) begin
            report_state<=0; report_index<=0; report_timer<=0; tx_start<=0; tx_data<=0;
            report_observed<=0;report_expected<=0;report_noacks<=0;report_camera_ready<=0;report_writes<=0;report_failed_address<=0;
            report_id<=0; report_errors<=0; report_hd_error<=0; report_hd_ready<=0;
        end else begin
            tx_start<=0;
            case(report_state)
                0: if(report_timer==27000000-1 && cam_complete) begin
                    report_observed<=camera_observed;report_expected<=camera_expected;report_noacks<=camera_noacks;report_camera_ready<=camera_ready;report_writes<=camera_writes;report_failed_address<=camera_failed_address;
                    report_id<=sensor_id; report_errors<=cam_errors;
                    report_hd_error<=hd_error; report_hd_ready<=hd_ready;
                    report_timer<=0; report_index<=0; report_state<=1;
                end else if(report_timer<27000000-1) report_timer<=report_timer+1;
                1: begin tx_data<=message(report_index); tx_start<=1; report_state<=2; end
                2: if(tx_done) begin
                    if(report_index==61) report_state<=0;
                    else begin report_index<=report_index+1; report_state<=1; end
                end
                default: report_state<=0;
            endcase
        end
    end
endmodule
