`timescale 1ns/1ps
// Transaction-level slave model: executes real sequencer, not physical I2C.
module tb_board1080_hdmi30_edid;
    reg clk=0,rstn=0,busy=0,byte_over=0;
    reg [7:0] data_out=0;
    wire init_over,iic_trig,w_r;
    wire [7:0] device_id,data_in;
    wire [15:0] addr;
    ms7200_ctl dut(.clk(clk),.rstn(rstn),.init_over(init_over),.device_id(device_id),
        .iic_trig(iic_trig),.w_r(w_r),.addr(addr),.data_in(data_in),
        .busy(busy),.data_out(data_out),.byte_over(byte_over));
    always #50 clk=~clk; // Actual configuration domain is nominal10MHz.
    reg [23:0] expected[0:310];
    reg [7:0] edid[0:255];
    integer csv,summary,epoch,transaction,initial_writes,edid_writes,status_reads,setting_writes;
    integer active_cycles,delay_cycles,watchdog,done_cycles,trace_index;
    reg active;
    reg [7:0] response;

    task check_request;
    begin
        response=0;trace_index=-1;
        if(device_id!==8'h56)$fatal(1,"RX device ID changed");
        if(transaction==0)begin
            if(w_r!==1 || addr!==16'h0003 || data_in!==8'h5a)$fatal(1,"initial scratch write changed");
        end else if(transaction==1)begin
            if(w_r!==0 || addr!==16'h0003)$fatal(1,"scratch read changed");
            response=8'h5a;
        end else if(initial_writes<300)begin
            trace_index=initial_writes;
            if(w_r!==1 || {addr,data_in}!==expected[initial_writes])
                $fatal(1,"initial command mismatch epoch=%0d row=%0d addr=%h data=%h expected=%h",epoch,initial_writes,addr,data_in,expected[initial_writes]);
            if(addr>=16'h0d00 && addr<=16'h0dff)begin
                if(data_in!==edid[addr-16'h0d00])$fatal(1,"EDID wire request differs");
                edid_writes=edid_writes+1;
            end
            initial_writes=initial_writes+1;
        end else if(!w_r)begin
            if(addr!==16'h209c+(status_reads%4))
                $fatal(1,"receiver status read order changed actual=%h expected=%h reads=%0d state=%h count=%0d",addr,16'h209c+(status_reads%4),status_reads,dut.state,dut.dri_cnt);
            response=(addr==16'h209e && status_reads>=4) ? 8'h02:8'h00;
            status_reads=status_reads+1;
        end else begin
            trace_index=304+setting_writes;
            if(setting_writes>=7 || {addr,data_in}!==expected[304+setting_writes])
                $fatal(1,"post-lock setting command changed");
            setting_writes=setting_writes+1;
        end
        delay_cycles=12+(transaction%5)*7;
        $fdisplay(csv,"%0d,%0d,%0d,%04h,%02h,%02h,%0d",epoch,trace_index,w_r,addr,data_in,response,delay_cycles);
        transaction=transaction+1;
    end
    endtask

    initial begin
        $readmemh("commands_expected.hex",expected);
        $readmemh("edid_expected.hex",edid);
        csv=$fopen("hdmi30-commands.csv","w");
        if(!csv)$fatal(1,"cannot open command trace");
        $fdisplay(csv,"epoch,index,write,addr,data,response,busy_cycles");
        for(epoch=1;epoch<=2;epoch=epoch+1)begin
            @(negedge clk);rstn=0;busy=0;byte_over=0;data_out=0;
            repeat(8)@(negedge clk);
            if(init_over!==0)$fatal(1,"reset did not clear completion");
            transaction=0;initial_writes=0;edid_writes=0;status_reads=0;setting_writes=0;
            active=0;active_cycles=0;done_cycles=0;watchdog=0;
            rstn=1;
            while(done_cycles<6)begin
                @(negedge clk);
                watchdog=watchdog+1;
                if(watchdog>30000)$fatal(1,"sequencer timeout");
                byte_over=0;
                if(init_over)begin
                    if(active || initial_writes!=300 || setting_writes!=7 || edid_writes!=264)
                        $fatal(1,"completion before all committed transactions");
                    done_cycles=done_cycles+1;
                end else if(!active && iic_trig)begin
                    // Actual iic_dri samples pluse through three registers;
                    // registered controller addr settles before bus acceptance.
                    active=1;active_cycles=-4;
                end else if(active)begin
                    active_cycles=active_cycles+1;
                    if(active_cycles==0)begin check_request();busy=1;data_out=response;end
                    if(active_cycles==delay_cycles-3)byte_over=1;
                    if(active_cycles==delay_cycles)begin busy=0;active=0;end
                end
            end
            if(status_reads<8)$fatal(1,"missing low-to-high status polls");
            $display("HDMI30_EPOCH_PASS epoch=%0d writes=%0d edid=%0d status_reads=%0d settings=%0d transactions=%0d",epoch,initial_writes,edid_writes,status_reads,setting_writes,transaction);
        end
        $fclose(csv);
        summary=$fopen("summary.json","w");
        $fdisplay(summary,"{\"Passed\":true,\"Epochs\":2,\"InitialWritesPerEpoch\":300,\"EDIDWritesPerEpoch\":264,\"SettingWritesPerEpoch\":7,\"ResetReplayPassed\":true,\"VariableBusyDelaysExercised\":true,\"ActualControllerExecuted\":true,\"PhysicalI2CVerified\":false,\"HardwareAccessed\":false}");
        $fclose(summary);
        $display("BOARD1080_HDMI30_EDID_SIM_PASS");
        $finish;
    end
endmodule
