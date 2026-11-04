`timescale 1ns/1ps
// Isolated test-only pin stimulus for assertion rejection, not a DUT/PHY test.
module tb_edge_guard_negative;
    reg scl=0,sda=1,rst_n=0,rx_done=0,tx_done=0;
    integer epoch=1,scenario;
    tx49_wire_edge_guard guard(.scl(scl),.sda(sda),.rst_n(rst_n),.rx_done(rx_done),.tx_done(tx_done),.epoch(epoch));
    task start;begin scl=0;sda=1;#10;scl=1;#10;sda=0;#10;scl=0;end endtask
    task address(input[7:0] d);begin
        for(integer i=7;i>=0;i=i-1)begin scl=0;sda=d[i];#10;scl=1;#10;scl=0;end
    end endtask
    task stop;begin scl=0;sda=0;#10;scl=1;#10;sda=1;#10;scl=0;end endtask
    task good_epoch;begin
        #10;rst_n=1;#10;rx_done=1;#10;
        for(integer n=0;n<51;n=n+1)begin
            start();address(8'hb2);
            if(n==1)begin start();address(8'hb3);end
            stop();
        end
        #10;tx_done=1;#10;
        if(guard.done_count!=1 || guard.tx_stops!=51)$fatal(1,"test positive incomplete");
    end endtask
    initial begin
        if(!$value$plusargs("CASE=%d",scenario))$fatal(1,"missing CASE");
        #10;
        case(scenario)
        0: begin
            good_epoch();#10;rst_n=0;rx_done=0;tx_done=0;epoch=2;#10;
            good_epoch();$display("EDGE_GUARD_POSITIVE_TWO_EPOCHS_PASS");$finish;
        end
        1: begin rst_n=1;start();rx_done=1;#10;address(8'hb2);end
        2: begin
            rst_n=1;rx_done=1;#10;
            for(integer n=0;n<50;n=n+1)begin start();address(8'hb2);stop();end
            start();address(8'hb2);#10;tx_done=1;
        end
        3: begin good_epoch();tx_done=0;#10;tx_done=1;end
        4: begin rst_n=1;rx_done=1;#10;start();address(8'hb2);start();address(8'hb3);start();end
        5: begin rst_n=1;start(); // restart in a new reset epoch for precise simultaneous edge
            rst_n=0;#10;scl=1;sda=1;#10;rst_n=1;#10;
            rx_done=1;sda=0;#10;scl=0;address(8'hb2);
        end
        6: begin rst_n=1;rx_done=1;#10;start();address(8'hb2);start();address(8'hb2);end
        default:$fatal(1,"unknown test");
        endcase
        #100;$fatal(1,"NEGATIVE_NOT_REJECTED");
    end
endmodule
