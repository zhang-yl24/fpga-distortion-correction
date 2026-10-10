`timescale 1ns/1ps
// Read-only SCCB observer; shares open-drain wires only after init is finished.
// Each row is individually timed. Multi-byte gains are NOT an atomic snapshot.
module ov5640_state_scan #(parameter CLOCK_HZ=27000000, QUARTER_CYCLES=68,
    TIMEOUT_CYCLES=1350000, SCAN_GAP_MS=1000)(
    input clk,rst_n,enabled,inout scl,sda,
    output byte_valid,output [7:0] byte_data,input byte_ready,
    output reg failed,output reg [3:0] fault);
    localparam WAIT_SCAN=0,START_READ=1,WAIT_READ=2,SEND_ROW=3,HALT=4;
    localparam TICK_CYCLES=CLOCK_HZ/1000;
    reg [2:0] state;reg [4:0] index;reg [5:0] char_index;
    reg [31:0] tick_count,elapsed_ms,gap_ms,sample_ms;
    reg [15:0] sample_address;reg [7:0] sample_value;
    reg [3:0] sample_error;reg trigger;
    wire busy,done;wire [3:0] bus_error;wire [7:0] value;
    function [15:0] scan_address;
        input [4:0] i;
        begin case(i)
            0:scan_address=16'h5001;1:scan_address=16'h3406;2:scan_address=16'h3503;
            3:scan_address=16'h4300;4:scan_address=16'h501f;5:scan_address=16'h503d;
            6:scan_address=16'h3400;7:scan_address=16'h3401;8:scan_address=16'h3402;
            9:scan_address=16'h3403;10:scan_address=16'h3404;11:scan_address=16'h3405;
            12:scan_address=16'h3500;13:scan_address=16'h3501;14:scan_address=16'h3502;
            15:scan_address=16'h350a;16:scan_address=16'h350b;17:scan_address=16'h3a00;
            18:scan_address=16'h3a19;19:scan_address=16'h5000;20:scan_address=16'h3017;
            21:scan_address=16'h3018;22:scan_address=16'h3035;23:scan_address=16'h3036;
            default:scan_address=0;
        endcase end
    endfunction
    reg16_i2c #(.QUARTER_CYCLES(QUARTER_CYCLES),.TIMEOUT_CYCLES(TIMEOUT_CYCLES))
        observer(.clk(clk),.rst_n(rst_n && enabled),.start(trigger),.read(1'b1),
            .device(7'h3c),.address(scan_address(index)),.write_data(8'b0),
            .busy(busy),.done(done),.error(bus_error),.read_data(value),.scl(scl),.sda(sda));
    function [7:0] hexchar;
        input [3:0] n;begin hexchar=n<10 ? 8'd48+n:8'd65+n-10;end
    endfunction
    function [7:0] message;
        input [5:0] i;
        begin case(i)
            0:message="I";1:message="S";2:message="P";3:message=" ";4:message="T";5:message="=";
            6:message=hexchar(sample_ms[31:28]);7:message=hexchar(sample_ms[27:24]);
            8:message=hexchar(sample_ms[23:20]);9:message=hexchar(sample_ms[19:16]);
            10:message=hexchar(sample_ms[15:12]);11:message=hexchar(sample_ms[11:8]);
            12:message=hexchar(sample_ms[7:4]);13:message=hexchar(sample_ms[3:0]);
            14:message=" ";15:message="A";16:message="=";
            17:message=hexchar(sample_address[15:12]);18:message=hexchar(sample_address[11:8]);
            19:message=hexchar(sample_address[7:4]);20:message=hexchar(sample_address[3:0]);
            21:message=" ";22:message="V";23:message="=";
            24:message=hexchar(sample_value[7:4]);25:message=hexchar(sample_value[3:0]);
            26:message=" ";27:message="E";28:message="=";29:message=hexchar(sample_error);
            30:message=13;31:message=10;default:message=0;
        endcase end
    endfunction
    assign byte_valid=state==SEND_ROW && rst_n && enabled;
    assign byte_data=message(char_index);
    always @(posedge clk) begin
        if(!rst_n || !enabled) begin
            state<=WAIT_SCAN;index<=0;char_index<=0;trigger<=0;failed<=0;fault<=0;
            tick_count<=0;elapsed_ms<=0;gap_ms<=SCAN_GAP_MS;
            sample_ms<=0;sample_address<=0;sample_value<=0;sample_error<=0;
        end else begin
            trigger<=0;
            if(tick_count==TICK_CYCLES-1) begin
                tick_count<=0;elapsed_ms<=elapsed_ms+1'b1;
                if(state==WAIT_SCAN && gap_ms<SCAN_GAP_MS) gap_ms<=gap_ms+1'b1;
            end else tick_count<=tick_count+1'b1;
            case(state)
                WAIT_SCAN:if(gap_ms>=SCAN_GAP_MS) begin index<=0;state<=START_READ;end
                START_READ:if(!busy) begin trigger<=1;state<=WAIT_READ;end
                WAIT_READ:if(done) begin
                    sample_ms<=elapsed_ms;sample_address<=scan_address(index);
                    sample_value<=bus_error==0 ? value:8'h00;sample_error<=bus_error;
                    char_index<=0;state<=SEND_ROW;
                    if(bus_error!=0) begin failed<=1;fault<=bus_error;end
                end
                SEND_ROW:if(byte_ready) begin
                    if(char_index==31) begin
                        if(sample_error!=0) state<=HALT;
                        else if(index==23) begin gap_ms<=0;state<=WAIT_SCAN;end
                        else begin index<=index+1'b1;state<=START_READ;end
                    end else char_index<=char_index+1'b1;
                end
                HALT:begin end
                default:begin failed<=1;fault<=4'hf;state<=HALT;end
            endcase
        end
    end
endmodule
