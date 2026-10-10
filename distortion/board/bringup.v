// Short hardware acceptance image: HDMI pattern + camera ID + UART telemetry.
module bringup(input clk_27m, output [7:0] led, output uart_txd,
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
    camera_id_probe camera(.clk(clk_27m),.rst_n(rst_n),.cam_rst_n(cam_rst_n),
        .cam_scl(cam_scl),.cam_sda(cam_sda),.sensor_id(sensor_id),.errors(cam_errors),
        .complete(cam_complete),.match_5640(cam_match));
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
                24:message=13; 25:message=10;
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
            report_id<=0; report_errors<=0; report_hd_error<=0; report_hd_ready<=0;
        end else begin
            tx_start<=0;
            case(report_state)
                0: if(report_timer==27000000-1 && cam_complete) begin
                    report_id<=sensor_id; report_errors<=cam_errors;
                    report_hd_error<=hd_error; report_hd_ready<=hd_ready;
                    report_timer<=0; report_index<=0; report_state<=1;
                end else if(report_timer<27000000-1) report_timer<=report_timer+1;
                1: begin tx_data<=message(report_index); tx_start<=1; report_state<=2; end
                2: if(tx_done) begin
                    if(report_index==25) report_state<=0;
                    else begin report_index<=report_index+1; report_state<=1; end
                end
                default: report_state<=0;
            endcase
        end
    end
endmodule
