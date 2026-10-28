`timescale 1ns/1ps
// CAM1 register-only diagnostic. No DDR, HDMI, DVP input, RAW or host grant.
// Pad samples are synchronized digital levels, not voltage or waveform measurements.
module cam1_transaction_probe #(parameter STATUS_PERIOD_CYCLES=13500000)(
    input clk_27m,output uart_txd,output led0,
    inout cam_rst_n,cam_scl,cam_sda
);
    reg [19:0] power_count=0;
    wire rst_n=&power_count;
    always @(posedge clk_27m)if(!rst_n)power_count<=power_count+1'b1;
    wire [15:0] sensor_id,failed_address;
    wire camera_ready,camera_failed;wire [7:0] camera_error,observed_value,expected_value;
    wire [8:0] commands_written,verified_write_noacks;
    wire diag3018_write_issued,diag3018_write_completed,diag3018_final_data_noack,diag3018_noack_pending;
    wire [3:0] diag3018_write_bus_error,diag3018_read_bus_error;
    wire diag3018_read_issued,diag3018_read_completed,diag3018_read_value_valid,diag3018_read_equal;
    wire [7:0] diag3018_read_value;
    wire [2:0] diagnostic_probe_attempted,diagnostic_probe_completed,diagnostic_probe_value_valid;
    wire [11:0] diagnostic_probe_bus_errors;wire [23:0] diagnostic_probe_values;
    wire [1:0] diagnostic_probe_count;wire diagnostic_probe_done;
    ov5640_cadence_diagnostic_init #(.DYNAMIC_PAD_MASK(1),.I2C_QUARTER_CYCLES(68),.DIAGNOSTIC_PROBES(1)) camera(
        .clk(clk_27m),.rst_n(rst_n),.cam_rst_n(cam_rst_n),.cam_scl(cam_scl),.cam_sda(cam_sda),
        .trial_pad_mask(16'h7ff0),.sensor_id(sensor_id),.ready(camera_ready),.failed(camera_failed),
        .error_code(camera_error),.failed_address(failed_address),.commands_written(commands_written),
        .verified_write_noacks(verified_write_noacks),.observed_value(observed_value),.expected_value(expected_value),
        .diag3018_write_issued(diag3018_write_issued),.diag3018_write_completed(diag3018_write_completed),
        .diag3018_write_bus_error(diag3018_write_bus_error),.diag3018_final_data_noack(diag3018_final_data_noack),
        .diag3018_noack_pending(diag3018_noack_pending),.diag3018_read_issued(diag3018_read_issued),
        .diag3018_read_completed(diag3018_read_completed),.diag3018_read_bus_error(diag3018_read_bus_error),
        .diag3018_read_value(diag3018_read_value),.diag3018_read_value_valid(diag3018_read_value_valid),
        .diag3018_read_equal(diag3018_read_equal),.diagnostic_probe_attempted(diagnostic_probe_attempted),
        .diagnostic_probe_completed(diagnostic_probe_completed),.diagnostic_probe_value_valid(diagnostic_probe_value_valid),
        .diagnostic_probe_bus_errors(diagnostic_probe_bus_errors),.diagnostic_probe_values(diagnostic_probe_values),
        .diagnostic_probe_count(diagnostic_probe_count),.diagnostic_probe_done(diagnostic_probe_done));

    reg [31:0] uptime_ms=0,sequence_number=0,period_count=0;
    reg [14:0] ms_count=0;reg pending=0,heart=0;
    (* async_reg="true" *) reg [2:0] pads_meta=0,pads_sync=0;
    wire [7:0] transaction_flags={diag3018_read_equal,diag3018_read_value_valid,
        diag3018_read_completed,diag3018_read_issued,diag3018_noack_pending,
        diag3018_final_data_noack,diag3018_write_completed,diag3018_write_issued};
    reg [447:0] payload;
    always @*begin
        payload=0;
        payload[0*8+:64]=64'h3130444d41434750; // PGCAMD01 in wire order.
        payload[8*8+:8]=1;payload[9*8+:8]=64;payload[10*8+:8]=1;
        payload[12*8+:16]=sensor_id;payload[14*8+:8]=camera_error;
        payload[15*8+:8]=transaction_flags;payload[16*8+:16]=failed_address;
        payload[18*8+:16]={7'b0,commands_written};payload[20*8+:16]={7'b0,verified_write_noacks};
        payload[22*8+:8]=observed_value;payload[23*8+:8]=expected_value;
        payload[24*8+:8]={4'b0,diag3018_write_bus_error};payload[25*8+:8]={4'b0,diag3018_read_bus_error};
        payload[26*8+:8]=diag3018_read_value;
        payload[27*8+:8]={4'b0,1'b1,diagnostic_probe_done,camera_failed,camera_ready};
        payload[28*8+:8]={5'b0,diagnostic_probe_attempted};
        payload[29*8+:8]={5'b0,diagnostic_probe_completed};
        payload[30*8+:8]={5'b0,diagnostic_probe_value_valid};
        payload[31*8+:8]={6'b0,diagnostic_probe_count};
        payload[32*8+:16]={4'b0,diagnostic_probe_bus_errors};payload[34*8+:24]=diagnostic_probe_values;
        payload[37*8+:16]=16'h7ff0;payload[39*8+:16]=16'd68;
        payload[41*8+:32]=uptime_ms;payload[45*8+:32]=sequence_number+1'b1;
        payload[49*8+:8]={5'b0,pads_sync}; // bytes50..55 and byte11 remain zero.
    end
    reg [447:0] snapshot;
    reg packet_active=0,waiting_done=0;
    reg [6:0] byte_index=0;
    reg [31:0] crc_state=32'hffffffff,crc_final=0;
    wire serial_busy,serial_done;
    wire serial_start=packet_active && !waiting_done && !serial_busy;
    reg [7:0] serial_data;
    always @*begin
        if(byte_index<56)serial_data=snapshot[byte_index*8+:8];
        else if(byte_index<60)serial_data=crc_final[(byte_index-56)*8+:8];
        else case(byte_index)
            60:serial_data=8'h43;61:serial_data=8'h44;62:serial_data=8'h30;default:serial_data=8'h31;
        endcase
    end
    function [31:0] crc_byte;
        input [31:0] previous;input [7:0] value;integer i;reg [31:0] c;
        begin c=previous^{24'b0,value};for(i=0;i<8;i=i+1)c=(c>>1)^(c[0]?32'hedb88320:0);crc_byte=c;end
    endfunction
    uart_tx #(.CLOCK_HZ(27000000),.BAUD(921600)) serial(.clk(clk_27m),.rst_n(rst_n),
        .start(serial_start),.data(serial_data),.tx(uart_txd),.busy(serial_busy),.done(serial_done));
    always @(posedge clk_27m)begin
        if(!rst_n)begin
            uptime_ms<=0;sequence_number<=0;period_count<=0;ms_count<=0;pending<=0;heart<=0;
            pads_meta<=0;pads_sync<=0;snapshot<=0;packet_active<=0;waiting_done<=0;
            byte_index<=0;crc_state<=32'hffffffff;crc_final<=0;
        end else begin
            pads_meta<={cam_rst_n,cam_sda,cam_scl};pads_sync<=pads_meta;
            if(ms_count==26999)begin ms_count<=0;uptime_ms<=uptime_ms+1'b1;end
            else ms_count<=ms_count+1'b1;
            if(period_count==STATUS_PERIOD_CYCLES-1)begin period_count<=0;pending<=1;heart<=!heart;end
            else period_count<=period_count+1'b1;
            if(!packet_active && pending && !serial_busy)begin
                pending<=0;snapshot<=payload;sequence_number<=sequence_number+1'b1;
                packet_active<=1;waiting_done<=0;byte_index<=0;crc_state<=32'hffffffff;
            end
            if(serial_start)begin
                waiting_done<=1;
                if(byte_index<56)begin
                    crc_state<=crc_byte(crc_state,serial_data);
                    if(byte_index==55)crc_final<=~crc_byte(crc_state,serial_data);
                end
            end
            if(waiting_done && serial_done)begin
                waiting_done<=0;
                if(byte_index==63)packet_active<=0;
                else byte_index<=byte_index+1'b1;
            end
        end
    end
    assign led0=heart;
endmodule
