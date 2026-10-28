`timescale 1ns/1ps
// A raw bank owns UART from its admission through the final packet stop bit.
// Failed partial raw packets retain ownership until host timeout/reset; status
// is never inserted into a payload. A pre-export fault can release safely.
module guarded_uart_arbiter(
    input clk,rst_n,raw_admitted,raw_done,raw_failed,
    input raw_valid,input [7:0] raw_data,output wire raw_ready,raw_byte_done,
    input status_valid,input [7:0] status_data,output wire status_ready,status_byte_done,
    input status_pending,status_active,command_busy,reply_event,
    output reg raw_locked,output wire admission_allowed,
    output wire tx_valid,output wire [7:0] tx_data,input tx_ready,tx_done
);
    reg raw_started;
    assign admission_allowed=rst_n && !raw_locked && !status_pending && !status_active &&
        !command_busy && !reply_event && tx_ready;
    assign tx_valid=raw_locked ? raw_valid:status_valid;
    assign tx_data=raw_locked ? raw_data:status_data;
    assign raw_ready=raw_locked && tx_ready;
    assign raw_byte_done=raw_locked && tx_done;
    assign status_ready=!raw_locked && tx_ready;
    assign status_byte_done=!raw_locked && tx_done;
    always @(posedge clk)begin
        if(!rst_n)begin raw_locked<=0;raw_started<=0;end
        else begin
            if(raw_admitted)begin raw_locked<=1;raw_started<=0;end
            if(raw_valid && raw_ready)raw_started<=1;
            if(raw_done)begin raw_locked<=0;raw_started<=0;end
            if(raw_failed && !raw_started && tx_ready)raw_locked<=0;
        end
    end
endmodule
