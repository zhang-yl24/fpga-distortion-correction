// Independent MS7210 initialization, with ACK / signature verification.
// Uses vendor register settings; HDMI input/MS7200 is not involved.
module hdmi_tx_init(input clk, input rst_n, inout hd_scl, inout hd_sda,
    output reg ready, output reg [3:0] error);
    `include "D:/English/FPGA/distortion/board/ms7210_commands.vh"
    reg [3:0] state;
    reg [5:0] index;
    reg [31:0] delay_count;
    reg trigger, rd;
    reg [15:0] address;
    reg [7:0] write_data;
    wire busy,done; wire [3:0] bus_error; wire [7:0] read_data;
    wire [23:0] command=hdmi_command(index);
    reg16_i2c #(.ADDR_LSB_FIRST(1)) bus(.clk(clk),.rst_n(rst_n),.start(trigger),.read(rd),
        .device(7'h59),.address(address),.write_data(write_data),.busy(busy),.done(done),
        .error(bus_error),.read_data(read_data),.scl(hd_scl),.sda(hd_sda));
    always @(posedge clk) begin
        if(!rst_n) begin
            state<=0; index<=0; delay_count<=0; trigger<=0; rd<=0;
            address<=0; write_data<=0; ready<=0; error<=0;
        end else begin
            trigger<=0;
            case(state)
                0: if(delay_count==270000-1) begin
                    delay_count<=0; address<=16'h0003; write_data<=8'h5a; rd<=0; state<=1;
                end else delay_count<=delay_count+1;
                1: begin trigger<=1; state<=2; end
                2: if(done) begin
                    if(bus_error) begin error<=bus_error; state<=10; end
                    else begin rd<=1; state<=3; end
                end
                3: begin trigger<=1; state<=4; end
                4: if(done) begin
                    if(bus_error || read_data!=8'h5a) begin error<=bus_error ? bus_error:4'he; state<=10; end
                    else begin index<=0; rd<=0; state<=5; end
                end
                5: begin address<=command[23:8]; write_data<=command[7:0]; state<=6; end
                6: begin trigger<=1; state<=7; end
                7: if(done) begin
                    if(bus_error) begin error<=bus_error; state<=10; end
                    else if(index==48) begin ready<=1; state<=9; end
                    else begin index<=index+1; delay_count<=0; state<=8; end
                end
                // The vendor table pauses after command 18 (~300ms).
                8: if(delay_count==(index==19 ? 8100000:27000)-1) begin delay_count<=0; state<=5; end
                   else delay_count<=delay_count+1;
                9: state<=9;
                10: if(delay_count==27000000-1) begin delay_count<=0; state<=0; error<=0; end
                    else delay_count<=delay_count+1;
                default: state<=0;
            endcase
        end
    end
endmodule
