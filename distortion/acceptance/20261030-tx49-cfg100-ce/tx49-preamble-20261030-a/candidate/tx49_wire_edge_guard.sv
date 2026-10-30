`timescale 1ns/1ps
// Test-only raw wire observer. No DUT hierarchy writes, no shortened waits.
module tx49_wire_edge_guard(input scl,sda,rst_n,rx_done,tx_done,input integer epoch);
    integer fd,transaction_id,bit_count,tx_stops,done_count,starts,stops,repeat_count;
    reg active,reading_device,start_rx_ready,rx_seen,repeated;
    reg [7:0] shift,first_device;
    time last_tx_stop,rx_done_time,start_time;
    task clear_epoch;begin
        transaction_id=0;bit_count=0;tx_stops=0;done_count=0;starts=0;stops=0;
        active=0;reading_device=0;start_rx_ready=0;rx_seen=0;repeated=0;
        shift=0;first_device=0;last_tx_stop=0;rx_done_time=0;start_time=0;repeat_count=0;
    end endtask
    initial begin
        fd=$fopen("wire-events.csv","w");
        if(!fd)$fatal(1,"edge evidence open failed");
        $fdisplay(fd,"epoch,time_ns,event,transaction,device,rx_ready,repeated,tx_stops,done_count");
        $fflush(fd);clear_epoch();
    end
    always @(negedge rst_n)begin
        clear_epoch();
        $fdisplay(fd,"%0d,%0d,RESET,0,00,0,0,0,0",epoch,$time);$fflush(fd);
    end
    always @(posedge rx_done)if(rst_n)begin
        rx_seen=1;rx_done_time=$time;
        $fdisplay(fd,"%0d,%0d,RX_DONE,%0d,00,1,0,%0d,%0d",epoch,$time,transaction_id,tx_stops,done_count);$fflush(fd);
    end
    always @(negedge sda)if(rst_n && scl===1'b1)begin
        repeated=active;
        if(!active)begin transaction_id=transaction_id+1;repeat_count=0;end
        else begin
            repeat_count=repeat_count+1;
            if(repeat_count>1)$fatal(1,"TX49_EXTRA_RESTART duplicate repeated START");
        end
        active=1;reading_device=1;bit_count=0;shift=0;
        start_rx_ready=(rx_done===1'b1 && rx_seen);start_time=$time;
        starts=starts+1;
        $fdisplay(fd,"%0d,%0d,START,%0d,00,%0d,%0d,%0d,%0d",epoch,$time,transaction_id,start_rx_ready,repeated,tx_stops,done_count);$fflush(fd);
    end
    always @(posedge scl)if(rst_n && active && reading_device)begin
        if(sda!==0 && sda!==1)$fatal(1,"edge guard unknown device SDA");
        shift={shift[6:0],sda};bit_count=bit_count+1;
        if(bit_count==8)begin
            reading_device=0;
            if(!repeated)first_device=shift;
            else if(shift!==(first_device|8'h01))
                $fatal(1,"TX49_BAD_RESTART repeated START address mismatch or missing STOP");
            $fdisplay(fd,"%0d,%0d,DEVICE,%0d,%02h,%0d,%0d,%0d,%0d",epoch,$time,transaction_id,shift,start_rx_ready,repeated,tx_stops,done_count);$fflush(fd);
            if((shift==8'hb2 || shift==8'hb3) && (!start_rx_ready || start_time<=rx_done_time))
                $fatal(1,"TX49_EARLY_START actual START preceded RX completion");
        end
    end
    always @(posedge sda)if(rst_n && scl===1'b1 && active)begin
        if(reading_device)$fatal(1,"STOP before complete device address");
        active=0;stops=stops+1;
        if(first_device==8'hb2)begin tx_stops=tx_stops+1;last_tx_stop=$time;end
        $fdisplay(fd,"%0d,%0d,STOP,%0d,%02h,%0d,0,%0d,%0d",epoch,$time,transaction_id,first_device,rx_done,tx_stops,done_count);$fflush(fd);
    end
    always @(posedge tx_done)if(rst_n)begin
        done_count=done_count+1;
        $fdisplay(fd,"%0d,%0d,TX_DONE,%0d,00,%0d,0,%0d,%0d",epoch,$time,transaction_id,rx_done,tx_stops,done_count);$fflush(fd);
        if(done_count!=1 || tx_stops!=51 || active || last_tx_stop==0 || $time<=last_tx_stop)
            $fatal(1,"TX49_EARLY_DONE done is not after final actual TX STOP");
    end
endmodule
