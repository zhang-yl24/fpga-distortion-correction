`timescale 1ns/1ps
// Atomic 27MHz temperature snapshots. ASCII THERMAL_IDLE V1, nominal 921600
// baud; CRC16/CCITT-FALSE covers the body before " Z=" (not CR/LF).
// One snapshot is frozen through the final UART byte_done. No hardware ADC
// accuracy, temperature acceptance or thermal-safe operation is implied.
module thermal_idle_telemetry #(parameter REPORT_CYCLES=13500000)(
    input clk,rst_n,input sample_valid,failed,input [7:0] fault,
    input [15:0] raw_word,input [11:0] code12,input [31:0] sample_age,samples,conversions,
    input over_temp,input [4:0] alarm,
    output wire byte_valid,input byte_ready,byte_done,output wire [7:0] byte_data,
    output reg record_started,record_done,output reg [31:0] record_sequence
);
    localparam IDLE=0,SEND=1,WAIT_DONE=2;
    localparam BODY_BYTES=116,LINE_BYTES=125;
    reg [1:0] state;reg [31:0] period_count;reg [7:0] index;
    reg held_valid,held_failed,held_over;reg [4:0] held_alarm;reg [7:0] held_fault;
    reg [15:0] held_raw,crc;reg [11:0] held_code;
    reg [31:0] held_sequence,held_age,held_samples,held_conversions;
    wire [3:0] valid_fmt={3'b0,held_valid},failed_fmt={3'b0,held_failed},over_fmt={3'b0,held_over};
    wire [7:0] alarm_fmt={3'b0,held_alarm};
    function [7:0] hexchar(input [3:0] value);
        begin hexchar=value<10 ? 8'h30+value:8'h41+value-10;end
    endfunction
    function [15:0] crc_byte(input [15:0] previous,input [7:0] value);
        reg [15:0] c;integer bit_index;
        begin c=previous^{value,8'h00};for(bit_index=0;bit_index<8;bit_index=bit_index+1)
            c=c[15] ? (c<<1)^16'h1021:c<<1;crc_byte=c;end
    endfunction
    function [7:0] message(input [7:0] at);
        begin case(at)
            0:message=8'h54;
            1:message=8'h48;
            2:message=8'h45;
            3:message=8'h52;
            4:message=8'h4d;
            5:message=8'h41;
            6:message=8'h4c;
            7:message=8'h5f;
            8:message=8'h49;
            9:message=8'h44;
            10:message=8'h4c;
            11:message=8'h45;
            12:message=8'h20;
            13:message=8'h56;
            14:message=8'h3d;
            15:message=8'h30;
            16:message=8'h31;
            17:message=8'h20;
            18:message=8'h42;
            19:message=8'h3d;
            20:message=8'h30;
            21:message=8'h30;
            22:message=8'h30;
            23:message=8'h45;
            24:message=8'h31;
            25:message=8'h30;
            26:message=8'h30;
            27:message=8'h30;
            28:message=8'h20;
            29:message=8'h51;
            30:message=8'h3d;
            31:message=hexchar(held_sequence[31:28]);
            32:message=hexchar(held_sequence[27:24]);
            33:message=hexchar(held_sequence[23:20]);
            34:message=hexchar(held_sequence[19:16]);
            35:message=hexchar(held_sequence[15:12]);
            36:message=hexchar(held_sequence[11:8]);
            37:message=hexchar(held_sequence[7:4]);
            38:message=hexchar(held_sequence[3:0]);
            39:message=8'h20;
            40:message=8'h54;
            41:message=8'h56;
            42:message=8'h3d;
            43:message=hexchar(valid_fmt[3:0]);
            44:message=8'h20;
            45:message=8'h54;
            46:message=8'h46;
            47:message=8'h3d;
            48:message=hexchar(failed_fmt[3:0]);
            49:message=8'h20;
            50:message=8'h45;
            51:message=8'h3d;
            52:message=hexchar(held_fault[7:4]);
            53:message=hexchar(held_fault[3:0]);
            54:message=8'h20;
            55:message=8'h54;
            56:message=8'h52;
            57:message=8'h3d;
            58:message=hexchar(held_raw[15:12]);
            59:message=hexchar(held_raw[11:8]);
            60:message=hexchar(held_raw[7:4]);
            61:message=hexchar(held_raw[3:0]);
            62:message=8'h20;
            63:message=8'h54;
            64:message=8'h43;
            65:message=8'h3d;
            66:message=hexchar(held_code[11:8]);
            67:message=hexchar(held_code[7:4]);
            68:message=hexchar(held_code[3:0]);
            69:message=8'h20;
            70:message=8'h54;
            71:message=8'h41;
            72:message=8'h3d;
            73:message=hexchar(held_age[31:28]);
            74:message=hexchar(held_age[27:24]);
            75:message=hexchar(held_age[23:20]);
            76:message=hexchar(held_age[19:16]);
            77:message=hexchar(held_age[15:12]);
            78:message=hexchar(held_age[11:8]);
            79:message=hexchar(held_age[7:4]);
            80:message=hexchar(held_age[3:0]);
            81:message=8'h20;
            82:message=8'h54;
            83:message=8'h53;
            84:message=8'h3d;
            85:message=hexchar(held_samples[31:28]);
            86:message=hexchar(held_samples[27:24]);
            87:message=hexchar(held_samples[23:20]);
            88:message=hexchar(held_samples[19:16]);
            89:message=hexchar(held_samples[15:12]);
            90:message=hexchar(held_samples[11:8]);
            91:message=hexchar(held_samples[7:4]);
            92:message=hexchar(held_samples[3:0]);
            93:message=8'h20;
            94:message=8'h43;
            95:message=8'h56;
            96:message=8'h3d;
            97:message=hexchar(held_conversions[31:28]);
            98:message=hexchar(held_conversions[27:24]);
            99:message=hexchar(held_conversions[23:20]);
            100:message=hexchar(held_conversions[19:16]);
            101:message=hexchar(held_conversions[15:12]);
            102:message=hexchar(held_conversions[11:8]);
            103:message=hexchar(held_conversions[7:4]);
            104:message=hexchar(held_conversions[3:0]);
            105:message=8'h20;
            106:message=8'h4f;
            107:message=8'h54;
            108:message=8'h3d;
            109:message=hexchar(over_fmt[3:0]);
            110:message=8'h20;
            111:message=8'h41;
            112:message=8'h4c;
            113:message=8'h3d;
            114:message=hexchar(alarm_fmt[7:4]);
            115:message=hexchar(alarm_fmt[3:0]);
            116:message=8'h20;
            117:message=8'h5a;
            118:message=8'h3d;
            119:message=hexchar(crc[15:12]);
            120:message=hexchar(crc[11:8]);
            121:message=hexchar(crc[7:4]);
            122:message=hexchar(crc[3:0]);
            123:message=8'h0d;
            124:message=8'h0a;
            default:message=0;
        endcase end
    endfunction
    assign byte_valid=state==SEND;
    assign byte_data=message(index);
    always @(posedge clk) begin
        if(!rst_n) begin
            state<=IDLE;period_count<=0;index<=0;crc<=16'hffff;record_sequence<=0;
            held_sequence<=0;held_valid<=0;held_failed<=0;held_over<=0;held_alarm<=0;held_fault<=0;
            held_raw<=0;held_code<=0;held_age<=0;held_samples<=0;held_conversions<=0;
            record_started<=0;record_done<=0;
        end else begin
            record_started<=0;record_done<=0;
            case(state)
                IDLE:if(period_count>=REPORT_CYCLES-1)begin
                    period_count<=0;record_sequence<=record_sequence+1'b1;held_sequence<=record_sequence+1'b1;
                    held_valid<=sample_valid;held_failed<=failed;held_over<=over_temp;
                    held_alarm<=alarm;held_fault<=fault;held_raw<=raw_word;held_code<=code12;
                    held_age<=sample_age;held_samples<=samples;held_conversions<=conversions;
                    crc<=16'hffff;index<=0;state<=SEND;record_started<=1;
                end else period_count<=period_count+1'b1;
                SEND:if(byte_ready)begin
                    if(index<BODY_BYTES)crc<=crc_byte(crc,byte_data);
                    state<=WAIT_DONE;
                end
                WAIT_DONE:if(byte_done)begin
                    if(index==LINE_BYTES-1)begin state<=IDLE;record_done<=1;end
                    else begin index<=index+1'b1;state<=SEND;end
                end
                default:state<=IDLE;
            endcase
        end
    end
endmodule
