`timescale 1ns/1ps
// PGGUARD02 command receiver. Independent lease feedback, no UART TX here.
// Sequence counters wrap naturally. CRC/integrity is not authentication.
module guarded_command_engine #(
    parameter CLOCK_HZ=125000000,
    parameter RX_TIMEOUT_CYCLES=1250000,
    parameter GRANT_TIMEOUT_CYCLES=1024
)(
    input clk,rst_n,
    input byte_valid,input [7:0] byte_data,input framing_error,
    input core_idle,fault_active,can_grant,grant_ready,grant_accepted,grant_rejected,
    output reg grant_valid,output reg [31:0] grant_frames,grant_cycles,
    output reg stop_pulse,reply_event,output wire command_busy,
    output reg [31:0] session_id,
    output reg [15:0] last_received_seq,last_accepted_seq,
    output reg [7:0] last_opcode,last_result,
    output reg [31:0] accepted_count,rejected_count,duplicate_count,rx_error_count,
    output reg [15:0] requested_frames,lease_ms
);
    localparam OP_OPEN=8'h0f,OP_GRANT=8'h10,OP_STOP=8'h11,OP_QUERY=8'h12;
    localparam [31:0] CYCLES_PER_MS=CLOCK_HZ/1000;
    localparam R_NONE=8'h00,R_ACCEPTED=8'h01,R_DUP=8'h02,
        R_VERSION=8'h10,R_CRC=8'h11,R_FRAMING=8'h12,R_RX_TIMEOUT=8'h13,
        R_NO_SESSION=8'h20,R_SESSION=8'h21,R_OLD=8'h22,R_CONFLICT=8'h23,
        R_OPCODE=8'h30,R_ARG=8'h31,R_IDLE=8'h32,R_FAULT=8'h33,
        R_READY=8'h34,R_GRANT_REJECTED=8'h35,R_GRANT_TIMEOUT=8'h36,R_BUSY=8'h37;
    reg [7:0] rx[0:15];
    reg [4:0] rx_count;
    reg [15:0] rx_crc;
    reg [31:0] rx_age,grant_age;
    reg pending;
    reg [15:0] pending_seq;
    reg tuple_valid;
    reg [7:0] tuple_opcode;
    reg [15:0] tuple_seq;
    reg [31:0] tuple_session,tuple_arg;
    integer accept_add,reject_add,dup_add,error_add;
    reg pending_active;
    reg [15:0] delta;
    wire [7:0] opcode=rx[3];
    wire [15:0] seq={rx[5],rx[4]};
    wire [31:0] command_session={rx[9],rx[8],rx[7],rx[6]};
    wire [31:0] arg={rx[13],rx[12],rx[11],rx[10]};
    wire [23:0] requested_ms=arg[31:8];
    assign command_busy=(rx_count!=0)||pending||grant_valid;

    function [15:0] crc_byte;
        input [15:0] crc;input [7:0] data;
        reg [15:0] value;integer i;
        begin
            value=crc^{data,8'b0};
            for(i=0;i<8;i=i+1)
                value=value[15] ? (value<<1)^16'h1021 : value<<1;
            crc_byte=value;
        end
    endfunction

    task reject_command;
        input [7:0] code;input [7:0] op;
        begin
            reject_add=reject_add+1;
            last_opcode<=op;last_result<=code;reply_event<=1;
        end
    endtask
    task accept_command;
        input [15:0] accepted_seq;input [7:0] op;
        begin
            accept_add=accept_add+1;
            last_accepted_seq<=accepted_seq;last_opcode<=op;
            last_result<=R_ACCEPTED;reply_event<=1;
        end
    endtask
    task consume_sequence;
        begin
            last_received_seq<=seq;tuple_valid<=1;tuple_opcode<=opcode;
            tuple_seq<=seq;tuple_session<=command_session;tuple_arg<=arg;
        end
    endtask
    task forward_command;
        begin
            consume_sequence;
            case(opcode)
                OP_OPEN:begin
                    if(arg!=0 || command_session==0) reject_command(R_ARG,opcode);
                    else if(pending_active) reject_command(R_BUSY,opcode);
                    else if(fault_active) reject_command(R_FAULT,opcode);
                    else if(!core_idle) reject_command(R_IDLE,opcode);
                    else accept_command(seq,opcode);
                end
                OP_GRANT:begin
                    requested_frames<={8'b0,arg[7:0]};lease_ms<=arg[23:8];
                    if(arg[7:0]<1 || arg[7:0]>3 || requested_ms<1 || requested_ms>24000)
                        reject_command(R_ARG,opcode);
                    else if(pending_active) reject_command(R_BUSY,opcode);
                    else if(fault_active) reject_command(R_FAULT,opcode);
                    else if(!can_grant || !grant_ready) reject_command(R_READY,opcode);
                    else begin
                        grant_frames<={24'b0,arg[7:0]};
                        grant_cycles<=requested_ms*CYCLES_PER_MS;
                        grant_valid<=1;pending<=1;pending_seq<=seq;grant_age<=0;
                        last_opcode<=opcode;last_result<=R_NONE;
                    end
                end
                OP_STOP:begin
                    if(arg!=0) reject_command(R_ARG,opcode);
                    else begin
                        if(pending_active) reject_add=reject_add+1;
                        pending<=0;pending_active=0;
                        stop_pulse<=1;accept_command(seq,opcode);
                    end
                end
                OP_QUERY:begin
                    if(arg!=0) reject_command(R_ARG,opcode);
                    else if(pending_active) reject_command(R_BUSY,opcode);
                    else accept_command(seq,opcode);
                end
                default:reject_command(R_OPCODE,opcode);
            endcase
        end
    endtask
    task complete_command;
        begin
            if(opcode==OP_OPEN && (session_id==0 || command_session!=session_id)) begin
                if(command_session==0 || arg!=0) reject_command(R_ARG,opcode);
                else if(pending_active) reject_command(R_BUSY,opcode);
                else if(fault_active) reject_command(R_FAULT,opcode);
                else if(!core_idle) reject_command(R_IDLE,opcode);
                else begin
                    session_id<=command_session;
                    consume_sequence;accept_command(seq,opcode);
                end
            end else if(session_id==0) reject_command(R_NO_SESSION,opcode);
            else if(command_session!=session_id) reject_command(R_SESSION,opcode);
            else begin
                delta=seq-last_received_seq;
                if(delta==0) begin
                    if(tuple_valid && tuple_seq==seq && tuple_opcode==opcode &&
                        tuple_session==command_session && tuple_arg==arg) begin
                        dup_add=dup_add+1;last_opcode<=opcode;last_result<=R_DUP;reply_event<=1;
                    end else reject_command(R_CONFLICT,opcode);
                end else if(delta[15]) reject_command(R_OLD,opcode);
                else forward_command;
            end
        end
    endtask

    always @(posedge clk) begin
        if(!rst_n) begin
            rx_count<=0;rx_crc<=16'hffff;rx_age<=0;grant_age<=0;
            pending<=0;pending_seq<=0;tuple_valid<=0;tuple_opcode<=0;
            tuple_seq<=0;tuple_session<=0;tuple_arg<=0;
            grant_valid<=0;grant_frames<=0;grant_cycles<=0;stop_pulse<=0;reply_event<=0;
            session_id<=0;last_received_seq<=0;last_accepted_seq<=0;last_opcode<=0;last_result<=R_NONE;
            accepted_count<=0;rejected_count<=0;duplicate_count<=0;rx_error_count<=0;
            requested_frames<=0;lease_ms<=0;
        end else begin
            grant_valid<=0;stop_pulse<=0;reply_event<=0;
            accept_add=0;reject_add=0;dup_add=0;error_add=0;pending_active=pending;
            if(pending) begin
                if(grant_rejected) begin
                    pending<=0;pending_active=0;
                    reject_command(R_GRANT_REJECTED,OP_GRANT);
                end else if(grant_accepted) begin
                    pending<=0;pending_active=0;
                    accept_command(pending_seq,OP_GRANT);
                end else if(grant_age>=GRANT_TIMEOUT_CYCLES-1) begin
                    pending<=0;pending_active=0;stop_pulse<=1;
                    reject_command(R_GRANT_TIMEOUT,OP_GRANT);
                end else grant_age<=grant_age+1'b1;
            end
            if(framing_error) begin
                rx_count<=0;rx_age<=0;rx_crc<=16'hffff;
                error_add=error_add+1;last_result<=R_FRAMING;reply_event<=1;
            end else if(byte_valid) begin
                rx_age<=0;
                if(rx_count==0) begin
                    if(byte_data==8'ha5) begin rx[0]<=byte_data;rx_count<=1;end
                end else if(rx_count==1) begin
                    if(byte_data==8'h5a) begin rx[1]<=byte_data;rx_count<=2;rx_crc<=16'hffff;end
                    else if(byte_data!=8'ha5) rx_count<=0;
                end else begin
                    rx[rx_count]<=byte_data;
                    if(rx_count<=13) rx_crc<=crc_byte(rx_crc,byte_data);
                    if(rx_count==15) begin
                        rx_count<=0;
                        if({byte_data,rx[14]}!=rx_crc) begin
                            error_add=error_add+1;last_result<=R_CRC;reply_event<=1;
                        end else if(rx[2]!=8'h02) begin
                            error_add=error_add+1;last_result<=R_VERSION;reply_event<=1;
                        end else complete_command;
                    end else rx_count<=rx_count+1'b1;
                end
            end else if(rx_count!=0) begin
                if(rx_age>=RX_TIMEOUT_CYCLES-1) begin
                    rx_count<=0;rx_age<=0;rx_crc<=16'hffff;
                    error_add=error_add+1;last_result<=R_RX_TIMEOUT;reply_event<=1;
                end else rx_age<=rx_age+1'b1;
            end
            accepted_count<=accepted_count+accept_add;
            rejected_count<=rejected_count+reject_add;
            duplicate_count<=duplicate_count+dup_add;
            rx_error_count<=rx_error_count+error_add;
        end
    end
endmodule
