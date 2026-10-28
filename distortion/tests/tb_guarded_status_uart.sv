`timescale 1ns/1ps
module tb_guarded_status_uart;
    reg clk=0;always #4 clk=~clk;
    reg rst_n=0,request=0,defer_snapshot=0,raw_admitted=0,raw_done=0,raw_failed=0;
    reg command_busy=0,reply_event=0,raw_valid=0;reg [7:0] raw_data=0;
    reg [991:0] payload=0;
    wire pending,active,record_started,record_done;wire [31:0] record_sequence;
    wire status_valid,status_ready,status_byte_done;wire [7:0] status_data;
    wire raw_locked,admission_allowed,raw_ready,raw_byte_done,tx_valid;wire [7:0] tx_data;
    reg tx_ready=0,tx_done=0,permit_tail=0;integer delay_count=0,bytes=0,cycle=0,i;
    reg [7:0] received[0:1023];
    guarded_status_uart #(.PERIOD_CYCLES(100000)) status(.clk(clk),.rst_n(rst_n),.request(request),
        .raw_locked(raw_locked),.defer_snapshot(defer_snapshot),.payload(payload),
        .pending(pending),.active(active),.record_started(record_started),.record_done(record_done),
        .record_sequence(record_sequence),.byte_valid(status_valid),.byte_ready(status_ready),
        .byte_done(status_byte_done),.byte_data(status_data));
    guarded_uart_arbiter arbiter(.clk(clk),.rst_n(rst_n),.raw_admitted(raw_admitted),.raw_done(raw_done),.raw_failed(raw_failed),
        .raw_valid(raw_valid),.raw_data(raw_data),.raw_ready(raw_ready),.raw_byte_done(raw_byte_done),
        .status_valid(status_valid),.status_data(status_data),.status_ready(status_ready),.status_byte_done(status_byte_done),
        .status_pending(pending),.status_active(active),.command_busy(command_busy),.reply_event(reply_event),
        .raw_locked(raw_locked),.admission_allowed(admission_allowed),.tx_valid(tx_valid),.tx_data(tx_data),
        .tx_ready(tx_ready),.tx_done(tx_done));
    always @(posedge clk)if(rst_n && tx_valid && tx_ready)begin received[bytes]=tx_data;bytes=bytes+1;delay_count=5;end
    always @(negedge clk)begin
        cycle=cycle+1;tx_done=0;tx_ready=0;
        if(delay_count>0)begin
            if(delay_count!=1 || bytes%128!=0 || permit_tail)begin
                delay_count=delay_count-1;if(delay_count==0)tx_done=1;
            end
        end else tx_ready=rst_n && cycle%3!=0;
    end
    function [31:0] crc_byte;
        input [31:0] previous;input [7:0] value;integer bitno;reg [31:0] c;
        begin c=previous^{24'b0,value};for(bitno=0;bitno<8;bitno=bitno+1)c=(c>>1)^(c[0]?32'hEDB88320:0);crc_byte=c;end
    endfunction
    reg [31:0] c;
    initial begin
        for(i=0;i<120;i=i+1)payload[i*8+:8]=i;
        repeat(5)@(negedge clk);rst_n=1;
        wait(active);@(negedge clk);payload=~payload;
        wait(bytes==128);repeat(12)@(negedge clk);
        if(!active || admission_allowed || record_done)$fatal(1,"Status released before final byte_done");
        c=32'hFFFFFFFF;
        for(i=0;i<120;i=i+1)begin
            if(received[i]!==i[7:0])$fatal(1,"Atomic snapshot changed at %d",i);c=crc_byte(c,received[i]);
        end
        if({received[123],received[122],received[121],received[120]}!==~c ||
           {received[124],received[125],received[126],received[127]}!=="ST02")$fatal(1,"Status CRC/trailer");
        permit_tail=1;wait(record_done);wait(admission_allowed);
        @(negedge clk);raw_admitted=1;@(negedge clk);raw_admitted=0;
        request=1;@(negedge clk);request=0;
        for(i=0;i<17;i=i+1)begin
            @(negedge clk);raw_valid=1;raw_data=8'hb0+i;wait(raw_ready);@(negedge clk);raw_valid=0;
        end
        while(delay_count!=0)@(negedge clk);
        repeat(6)@(negedge clk);
        if(bytes!=145 || !raw_locked || active)$fatal(1,"Status inserted in raw owner");
        raw_done=1;@(negedge clk);raw_done=0;wait(bytes==273);
        for(i=0;i<17;i=i+1)if(received[128+i]!==8'hb0+i)$fatal(1,"Raw/status interleave");
        wait(record_done);repeat(3)@(negedge clk);
        raw_admitted=1;@(negedge clk);raw_admitted=0;raw_failed=1;
        repeat(3)@(negedge clk);if(raw_locked)$fatal(1,"Pre-export fault failed to release status owner");
        raw_failed=0;raw_admitted=1;@(negedge clk);raw_admitted=0;
        raw_valid=1;raw_data=8'hce;wait(raw_ready);@(negedge clk);raw_valid=0;raw_failed=1;request=1;
        @(negedge clk);request=0;repeat(20)@(negedge clk);
        if(!raw_locked || active || admission_allowed)$fatal(1,"Partial failed raw was not quarantined");
        $display("PASS guarded UART packets: atomic 120-byte body/CRC/ST02, final byte_done ownership, raw boundary arbitration, partial raw quarantine.");$finish;
    end
    initial begin #200000;$fatal(1,"Status UART regression timeout bytes=%d",bytes);end
endmodule
