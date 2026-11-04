`timescale 1ns/1ps
// Prepared only. Real legacy wrapper/TX/IIC + isolated EDID RX, no forced state.
// Wire receive/send tasks adapted from ddf3540:tests/tb_ms72xx_checked_e2e.sv.
// All slave ACK/scratch/status replies are SYNTHETIC, not silicon/PHY evidence.
module tb_ms72xx_legacy_wire;
    reg clk=0,rst_n=0;always #50 clk=~clk;
    wire scl;tri1 sda;reg slave_sda=0;assign sda=slave_sda?1'b0:1'bz;
    wire rx_done,done;
    ms72xx_ctl dut(.clk(clk),.rst_n(rst_n),.init_over_rx(rx_done),
        .init_over(done),.iic_scl(scl),.iic_sda(sda));
    reg [23:0] rx_expected[0:310],tx_expected[0:48],tx_legacy[0:49];
    reg [7:0] edid_expected[0:255],edid_memory[0:255];
    integer epoch,cycles,after_done,rx_requests,tx_requests,rx_initial,rx_settings;
    integer rx_status,post_reads,tx_writes,edid_writes,row19_count,request,fd,sf;
    integer starts,stops,wire_bytes;
    reg edid_ok,rx_seq_ok,tx_legacy_ok,tx_canonical_ok,tx_after_rx,tx_preamble_ok;
    reg completed,poll_resumed,active,overall_pass;
    reg [7:0] dev,lo,hi,payload,response;
    reg [15:0] register_addr;reg read_request;
    tx49_wire_edge_guard edge_guard(.scl(scl),.sda(sda),.rst_n(rst_n),
        .rx_done(rx_done),.tx_done(done),.epoch(epoch));
    // LOG_ONLY_BEGIN completion_monitors
    always @(posedge rx_done)begin
        $display("WIRE_PROGRESS_RX_DONE epoch=%0d cycles=%0d request=%0d rx_initial=%0d rx_settings=%0d edid_writes=%0d",
            epoch,cycles,request,rx_initial,rx_settings,edid_writes);
        $fflush();
    end
    always @(posedge done)begin
        $display("WIRE_PROGRESS_TX_DONE epoch=%0d cycles=%0d request=%0d tx_writes=%0d row19=%0d post_reads=%0d",
            epoch,cycles,request,tx_writes,row19_count,post_reads);
        $fflush();
    end
    // LOG_ONLY_END completion_monitors

    task wait_start;begin
        do @(negedge sda);while(scl!==1);
        starts=starts+1;
    end endtask
    task receive(output reg [7:0] value);
        begin
            value=0;
            for(integer bitno=0;bitno<8;bitno=bitno+1)begin
                @(posedge scl);
                if(sda!==0 && sda!==1)$fatal(1,"unknown wire SDA while receiving");
                value={value[6:0],sda};
            end
            wire_bytes=wire_bytes+1;
            @(negedge scl);slave_sda=1;
            @(posedge scl);if(sda!==0)$fatal(1,"synthetic ACK not resolved low");
            @(negedge scl);slave_sda=0;
        end
    endtask
    task send(input [7:0] value);
        begin
            for(integer bitno=7;bitno>=0;bitno=bitno-1)begin
                slave_sda=!value[bitno];@(posedge scl);@(negedge scl);
            end
            wire_bytes=wire_bytes+1;
            slave_sda=0;@(posedge scl);
            if(sda!==1)$fatal(1,"master final read NACK missing");
            @(negedge scl);
        end
    endtask
    task wait_stop;begin
        do @(posedge sda);while(scl!==1);
        stops=stops+1;
    end endtask

    task transaction;
        reg [7:0] read_id;
        begin
            wait_start();active=1;
            receive(dev);receive(lo);receive(hi);register_addr={hi,lo};
            payload=0;response=0;read_request=0;
            if(dev==8'h56)begin
                read_request=(rx_requests==1) || (register_addr>=16'h209c && register_addr<=16'h209f);
                if(read_request)begin
                    if(rx_requests==1)begin
                        if(register_addr!==16'h0003)rx_seq_ok=0;
                        response=8'h5a;
                    end else begin
                        if(register_addr!==16'h209c+(rx_status%4))rx_seq_ok=0;
                        response=(register_addr==16'h209e && rx_status>=4)?8'h02:8'h00;
                        if(done)post_reads=post_reads+1;
                        rx_status=rx_status+1;
                    end
                end
            end else if(dev==8'hb2)begin
                if(!rx_done || rx_initial!=300 || rx_settings!=7)tx_after_rx=0;
                read_request=(tx_requests==1) || (register_addr==16'h0502);
                if(tx_requests==1)begin
                    if(register_addr!==16'h0003)begin tx_legacy_ok=0;tx_preamble_ok=0;end
                    response=8'h5a;
                end
            end else $fatal(1,"unexpected shared wire device %h",dev);
            if(read_request)begin
                wait_start();receive(read_id);
                if(read_id!==(dev|8'h01))$fatal(1,"repeated START read ID differs");
                send(response);
            end else begin
                receive(payload);
                if(dev==8'h56)begin
                    if(rx_requests==0)begin
                        if({register_addr,payload}!==24'h00035a)rx_seq_ok=0;
                    end else if(rx_initial<300)begin
                        if({register_addr,payload}!==rx_expected[rx_initial])rx_seq_ok=0;
                        rx_initial=rx_initial+1;
                    end else begin
                        if(rx_settings>=7)rx_seq_ok=0;
                        else if({register_addr,payload}!==rx_expected[304+rx_settings])rx_seq_ok=0;
                        rx_settings=rx_settings+1;
                    end
                    if(register_addr>=16'h0d00 && register_addr<=16'h0dff)begin
                        if(payload!==edid_expected[register_addr-16'h0d00])edid_ok=0;
                        edid_memory[register_addr-16'h0d00]=payload;edid_writes=edid_writes+1;
                    end
                end else begin
                    if(tx_requests==0)begin
                        if({register_addr,payload}!==24'h00035a)begin tx_legacy_ok=0;tx_preamble_ok=0;end
                    end else begin
                        if(tx_writes>=50)tx_legacy_ok=0;
                        else if({register_addr,payload}!==tx_legacy[tx_writes])tx_legacy_ok=0;
                        if(tx_writes>=49)tx_canonical_ok=0;
                        else if({register_addr,payload}!==tx_expected[tx_writes])tx_canonical_ok=0;
                        if({register_addr,payload}===tx_expected[19])row19_count=row19_count+1;
                        tx_writes=tx_writes+1;
                    end
                end
            end
            wait_stop();active=0;request=request+1;
            $fdisplay(fd,"%0d,%0d,%02h,%0d,%04h,%02h,%02h,%0d,%0d",
                epoch,request,dev,read_request,register_addr,payload,response,rx_done,done);
    // LOG_ONLY_BEGIN transaction_csv_flush
            $fflush(fd);
    // LOG_ONLY_END transaction_csv_flush
            if(dev==8'h56)rx_requests=rx_requests+1;else tx_requests=tx_requests+1;
        end
    endtask

    initial begin
        $readmemh("rx_expected.hex",rx_expected);$readmemh("tx_expected.hex",tx_expected);
        $readmemh("tx_legacy_expected.hex",tx_legacy);$readmemh("edid_expected.hex",edid_expected);
        fd=$fopen("wire-transactions.csv","w");sf=$fopen("epoch-summary.csv","w");
        if(!fd || !sf)$fatal(1,"cannot open wire evidence");
        $fdisplay(fd,"epoch,request,device,read,addr,data,response,rx_done,tx_done");
    // LOG_ONLY_BEGIN transaction_header_flush
        $fflush(fd);
    // LOG_ONLY_END transaction_header_flush
        $fdisplay(sf,"epoch,rx_initial,rx_settings,edid_writes,edid_ok,rx_seq_ok,tx_writes,tx_legacy_ok,tx_canonical_ok,row19_count,tx_after_rx,tx_done,post_reads,poll_resumed,completed,cycles,starts,stops,wire_bytes,tx_preamble_ok,edge_done_count,edge_tx_stops");
    // LOG_ONLY_BEGIN summary_header_flush
        $fflush(sf);
    // LOG_ONLY_END summary_header_flush
        overall_pass=1;
        for(epoch=1;epoch<=2;epoch=epoch+1)begin
            @(negedge clk);rst_n=0;slave_sda=0;
            repeat(12)@(negedge clk);
            if(rx_done!==0 || done!==0)$fatal(1,"common reset did not clear wrapper flags");
            cycles=0;after_done=0;rx_requests=0;tx_requests=0;rx_initial=0;rx_settings=0;
            rx_status=0;post_reads=0;tx_writes=0;edid_writes=0;row19_count=0;request=0;
            starts=0;stops=0;wire_bytes=0;active=0;completed=0;poll_resumed=0;
            edid_ok=1;rx_seq_ok=1;tx_legacy_ok=1;tx_canonical_ok=1;tx_after_rx=1;tx_preamble_ok=1;
            for(integer n=0;n<256;n=n+1)edid_memory[n]=8'hxx;
            fork : epoch_threads
                begin forever transaction();end
                begin
                    @(negedge clk);rst_n=1;
                    while(!completed && cycles<4500000)begin
                        @(negedge clk);cycles=cycles+1;
    // LOG_ONLY_BEGIN cycle_heartbeat
                        if((cycles%250000)==0)begin
                            $display("WIRE_PROGRESS_HEARTBEAT epoch=%0d cycles=%0d request=%0d rx_done=%0d tx_done=%0d rx_initial=%0d tx_writes=%0d post_reads=%0d",
                                epoch,cycles,request,rx_done,done,rx_initial,tx_writes,post_reads);
                            $fflush();
                        end
    // LOG_ONLY_END cycle_heartbeat
                        if(done)begin
                            after_done=after_done+1;
                            if(post_reads>=4 && !active)begin completed=1;poll_resumed=1;end
                            else if(after_done>=25000)completed=1;
                        end
                    end
                end
            join_any
            disable epoch_threads;
            for(integer n=0;n<256;n=n+1)if(edid_memory[n]!==edid_expected[n])edid_ok=0;
            if(!done || !poll_resumed || !edid_ok || !rx_seq_ok ||
                !tx_canonical_ok || !tx_preamble_ok || !tx_after_rx || row19_count!=1 || rx_initial!=300 || rx_settings!=7 ||
                edid_writes!=264 || tx_writes!=49 || edge_guard.done_count!=1 || edge_guard.tx_stops!=51)overall_pass=0;
            $fdisplay(sf,"%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d",
                epoch,rx_initial,rx_settings,edid_writes,edid_ok,rx_seq_ok,tx_writes,
                tx_legacy_ok,tx_canonical_ok,row19_count,tx_after_rx,done,post_reads,
                poll_resumed,completed,cycles,starts,stops,wire_bytes,tx_preamble_ok,edge_guard.done_count,edge_guard.tx_stops);
    // LOG_ONLY_BEGIN epoch_summary_flush
            $fflush(sf);
    // LOG_ONLY_END epoch_summary_flush
            $display("LEGACY_WIRE_EPOCH_OBSERVED epoch=%0d rx_init=%0d edid_ok=%0d tx_writes=%0d legacy=%0d canonical=%0d row19=%0d done=%0d post=%0d poll=%0d",
                epoch,rx_initial,edid_ok,tx_writes,tx_legacy_ok,tx_canonical_ok,row19_count,done,post_reads,poll_resumed);
    // LOG_ONLY_BEGIN epoch_display_flush
            $fflush();
    // LOG_ONLY_END epoch_display_flush
        end
        $fclose(fd);$fclose(sf);
        $display("MS72XX_TX49_WIRE_OBSERVATIONS_COMPLETE overall_pass=%0d",overall_pass);
    // LOG_ONLY_BEGIN final_display_flush
        $fflush();
    // LOG_ONLY_END final_display_flush
        if(!overall_pass)$fatal(1,"strict TX49/preamble/wire contract failed");
        $finish;
    end
endmodule
