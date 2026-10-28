`timescale 1ns/1ps
// Commands -> actual lease -> DVP/CDC/DDR -> packet arbiter. UART TX is an
// independently delayed byte sink; RX commands traverse the real 8N1 receiver.
module tb_guarded_cam1_sccb25_pipeline;
    localparam WIDTH=32,HEIGHT=16,BYTES=1024,TOTAL=1068,BEATS=32;
    reg core_clk=0,cam_clk=0,source_clk=0,source_running=1,rst_n=0;
    always #4 core_clk=~core_clk;always #11 cam_clk=~cam_clk;
    always #18 if(source_running)source_clk=~source_clk;
    reg source_valid=0,source_failed=0,source_over=0;reg [4:0] source_alarm=0;
    reg [7:0] source_fault=0;reg [31:0] source_age=3,source_samples=2,source_conversions=100;
    reg [15:0] source_raw=16'h9d60;reg [11:0] source_code=2518;
    // extra = {padding14,camready,camfailed,hdready,hderror4,pll,expected8,
    // observed8,noacks9,writes9,failedaddr16,camerror8,sensorid16}.
    wire [95:0] source_extra={14'b0,1'b1,1'b0,1'b0,4'b0,1'b1,8'h6f,8'h6f,9'd0,9'd250,16'b0,8'b0,16'h5640};
    wire safety_ok,safety_snapshot_valid,temp_valid,temp_failed,temp_over;
    wire [31:0] safety_snapshot_age,temp_age,temp_samples,temp_conversions;
    wire [7:0] temp_fault;wire [4:0] temp_alarm;wire [15:0] temp_raw;wire [11:0] temp_code;wire [95:0] camera_info;
    guarded_temperature_cdc #(.SNAPSHOT_CYCLES(5),.CORE_MAX_AGE(5000),.SOURCE_MAX_AGE(1000)) temperature(
        .source_clk(source_clk),.core_clk(core_clk),.arst_n(rst_n),.sample_valid(source_valid),
        .failed(source_failed),.fault(source_fault),.raw_word(source_raw),.code12(source_code),
        .sample_age(source_age),.samples(source_samples),.conversions(source_conversions),
        .over_temp(source_over),.alarm(source_alarm),.source_extra(source_extra),.healthy(safety_ok),
        .snapshot_valid(safety_snapshot_valid),.snapshot_event(),.snapshot_age(safety_snapshot_age),
        .held_valid(temp_valid),.held_failed(temp_failed),.held_fault(temp_fault),.held_raw(temp_raw),
        .held_code(temp_code),.held_age(temp_age),.held_samples(temp_samples),.held_conversions(temp_conversions),
        .held_over_temp(temp_over),.held_alarm(temp_alarm),.held_extra(camera_info));
    reg camera_ready=1,ddr_ready=1,warmup_ready=0,rx_pin=1;
    wire rx_valid,rx_framing_error;wire [7:0] rx_data;
    uart_rx_control #(.CLOCK_HZ(1000000),.BAUD(100000)) receiver(.clk(core_clk),.rst_n(rst_n),.rx(rx_pin),
        .valid(rx_valid),.data(rx_data),.framing_error(rx_framing_error));
    reg vsync=0,href=0;reg [7:0] data=0;
    wire [27:0] awaddr,araddr;wire [3:0] awlen,arlen;wire awvalid,arvalid;wire [255:0] wdata;wire [31:0] wstrb;
    reg awready=0,arready=0,wready=0,wlast=0,rvalid=0,rlast=0;reg [255:0] rdata=0;reg [3:0] rid=0;
    wire byte_valid;wire [7:0] byte_data;reg byte_ready=0,byte_done=0;
    wire armed,in_flight,bank_locked,raw_done,raw_failed,requires_reset,capture_active,core_idle,ready_for_grant;
    wire status_active,status_pending,raw_uart_locked,command_busy,reply_event,grant_accepted,grant_rejected;
    wire [7:0] raw_fault;wire [3:0] raw_state,stop_reason;
    wire [31:0] admitted_frames,completed_frames,remaining_frames,remaining_cycles,frame_sequence;
    guarded_capture_controller #(.BUILD_TAG(32'h52473125),.CAMERA_ID(32'h43414d31),.CAMERA_SLOT(2'b01),
        .WIDTH(WIDTH),.HEIGHT(HEIGHT),.TIMEOUT_BITS(17),.CORE_CLOCK_HZ(1000000),
        .STATUS_PERIOD_CYCLES(10000),.SAFETY_MAX_AGE(5000),.TEMP_MAX_AGE(1000)) dut(.*);
    reg [255:0] memory[0:63];reg writing=0,reading=0;
    integer cycle=0,windex=0,rindex=0,write_base=0,read_base=0,writes=0,read_count=0;
    integer tx_delay=0,packet_index=0,packet_length=0,packet_kind=0,status_count=0,raw_count=0,stream_file;
    integer packet_start=0,wire_count=0,previous_sequence=0,last_status_grant_seq=0,current_grant_seq=0;
    reg [7:0] packet[0:TOTAL+31];reg [15:0] last_status_seq=0;reg [7:0] last_status_result=0,last_status_opcode=0;
    reg hold_raw_tail=0,permit_raw_tail=0,delay_is_raw_tail=0;
    reg [3:0] previous_state=0;
    function [31:0] crc_byte;
        input [31:0] previous;input [7:0] value;integer b;reg [31:0] c;
        begin c=previous^{24'b0,value};for(b=0;b<8;b=b+1)c=(c>>1)^(c[0]?32'hEDB88320:0);crc_byte=c;end
    endfunction
    function [15:0] crc16_byte;
        input [15:0] previous;input [7:0] value;integer b;reg [15:0] c;
        begin c=previous^{value,8'b0};for(b=0;b<8;b=b+1)c=(c<<1)^(c[15]?16'h1021:0);crc16_byte=c;end
    endfunction
    function [31:0] u32;
        input integer offset;begin u32={packet[offset+3],packet[offset+2],packet[offset+1],packet[offset]};end
    endfunction
    function [15:0] pixel;
        input integer index,version;begin pixel=16'h4321^(index*53)^(version*16'h1111);end
    endfunction
    task check_packet;
        integer n;reg [31:0] c;reg [15:0] p;
        begin
            if(packet_kind==1)begin
                c=32'hFFFFFFFF;for(n=0;n<120;n=n+1)c=crc_byte(c,packet[n]);
                if(u32(120)!==~c || {packet[124],packet[125],packet[126],packet[127]}!=="ST02")$fatal(1,"Status CRC/tail");
                if({packet[9],packet[8]}!=128 || u32(12)!=32'h52473125)$fatal(1,"Status identity");
                last_status_seq={packet[27],packet[26]};last_status_opcode=packet[28];last_status_result=packet[29];
                if(last_status_opcode==16 && last_status_result==1)last_status_grant_seq=last_status_seq;
                status_count=status_count+1;
            end else begin
                c=32'hFFFFFFFF;for(n=0;n<28;n=n+1)c=crc_byte(c,packet[n]);
                if(u32(28)!==~c || u32(12)!=raw_count+1 || u32(16)!=BYTES || u32(24)!=32'h5651)$fatal(1,"Raw header CRC/identity");
                c=32'hFFFFFFFF;for(n=0;n<BYTES;n=n+1)c=crc_byte(c,packet[32+n]);
                if(u32(20)!==~c || u32(32+BYTES+8)!==~c ||
                   {packet[32+BYTES],packet[33+BYTES],packet[34+BYTES],packet[35+BYTES],packet[36+BYTES],packet[37+BYTES],packet[38+BYTES],packet[39+BYTES]}!=="PGEND001")$fatal(1,"Raw payload/trailer CRC");
                for(n=0;n<WIDTH*HEIGHT;n=n+1)begin p=pixel(n,raw_count);
                    if({packet[33+2*n],packet[32+2*n]}!==p)$fatal(1,"Native pixel mismatch");end
                if(dut.held_camera_id!==32'h43414d31 || dut.held_eye!==2'b01)$fatal(1,"CAM1 held identity/slot");
                raw_count=raw_count+1;
            end
        end
    endtask
    always @(posedge core_clk)begin
        if(rst_n)begin
            if(raw_failed)$fatal(1,"Unexpected raw fault %h state %d writes %d reads %d",raw_fault,raw_state,writes,read_count);
            if(raw_state==1 && previous_state!=1)begin
                if(writing || reading)$fatal(1,"DDR owner did not drain");writes=0;read_count=0;
            end
            previous_state=raw_state;
            if(frame_sequence!=previous_sequence)begin
                if(last_status_grant_seq!=current_grant_seq)$fatal(1,"Raw admission preceded actual GRANT ACK status");
                previous_sequence=frame_sequence;
            end
            if(awvalid && awready)begin
                if(writing || awlen!=15 || !bank_locked)$fatal(1,"Bad write owner");writing=1;windex=0;write_base=awaddr/8;
            end
            if(wready)begin
                if(!writing || !bank_locked || wstrb!==32'hFFFFFFFF)$fatal(1,"Bad write data");
                memory[write_base+windex]=wdata;writes=writes+1;if(windex==15)writing=0;windex=windex+1;
            end
            if(arvalid && arready)begin
                if(writing || arlen!=15 || !bank_locked)$fatal(1,"Bad read owner");reading=1;rindex=0;read_base=araddr/8;
            end
            if(rvalid)begin read_count=read_count+1;if(rindex==15)reading=0;rindex=rindex+1;end
            if(byte_valid && byte_ready)begin
                if(packet_index==0)packet_start=wire_count;
                packet[packet_index]=byte_data;packet_index=packet_index+1;wire_count=wire_count+1;
                $fwrite(stream_file,"%c",byte_data);tx_delay=5;delay_is_raw_tail=0;
                if(packet_index==8)begin
                    if({packet[0],packet[1],packet[2],packet[3],packet[4],packet[5],packet[6],packet[7]}==="PGSTAT02")begin packet_kind=1;packet_length=128;end
                    else if({packet[0],packet[1],packet[2],packet[3],packet[4],packet[5],packet[6],packet[7]}==="PGFRAME1")begin packet_kind=2;packet_length=TOTAL;end
                    else $fatal(1,"Packet magic lost boundary at %d",packet_start);
                end
                if(packet_length!=0 && packet_index==packet_length)begin
                    if(packet_kind==2)delay_is_raw_tail=1;
                    check_packet();packet_index=0;packet_length=0;
                end
            end
        end
    end
    always @(negedge core_clk)begin
        cycle=cycle+1;
        awready=rst_n && !writing && cycle%5!=0;arready=rst_n && !reading && cycle%7!=0;
        wready=rst_n && writing && cycle%3!=0;wlast=wready && windex==15;
        rvalid=rst_n && reading && cycle%4!=0;rlast=rvalid && rindex==15;rdata=reading ? memory[read_base+rindex]:0;
        byte_done=0;byte_ready=0;
        if(tx_delay>0)begin
            if(tx_delay!=1 || !delay_is_raw_tail || !hold_raw_tail || permit_raw_tail)begin
                tx_delay=tx_delay-1;if(tx_delay==0)byte_done=1;
            end
        end else byte_ready=rst_n && cycle%4!=0;
    end
    task send_rx_byte;
        input [7:0] value;integer bitno;
        begin
            @(negedge core_clk);rx_pin=0;repeat(10)@(negedge core_clk);
            for(bitno=0;bitno<8;bitno=bitno+1)begin rx_pin=value[bitno];repeat(10)@(negedge core_clk);end
            rx_pin=1;repeat(12)@(negedge core_clk);
        end
    endtask
    task command;
        input [7:0] op;input [15:0] seq,frames,ms;integer n;reg [7:0] cmdbytes[0:15];reg [15:0] crc;
        begin
            cmdbytes[0]=8'ha5;cmdbytes[1]=8'h5a;cmdbytes[2]=2;cmdbytes[3]=op;
            cmdbytes[4]=seq;cmdbytes[5]=seq>>8;
            cmdbytes[6]=8'h78;cmdbytes[7]=8'h56;cmdbytes[8]=8'h34;cmdbytes[9]=8'h12;
            cmdbytes[10]=frames;cmdbytes[11]=ms;cmdbytes[12]=ms>>8;cmdbytes[13]=0;
            crc=16'hFFFF;for(n=2;n<14;n=n+1)crc=crc16_byte(crc,cmdbytes[n]);cmdbytes[14]=crc;cmdbytes[15]=crc>>8;
            for(n=0;n<16;n=n+1)send_rx_byte(cmdbytes[n]);
        end
    endtask
    task await_result;
        input [15:0] seq;input [7:0] result;integer wait_cycles;
        begin wait_cycles=0;
            while((last_status_seq!=seq || last_status_result!=result) && wait_cycles<20000)begin @(negedge core_clk);wait_cycles=wait_cycles+1;end
            if(wait_cycles==20000)$fatal(1,"Status reply timeout seq %d actual %d result %h",seq,last_status_seq,last_status_result);
        end
    endtask
    task sync_frame;
        begin @(negedge cam_clk);href=0;vsync=1;repeat(4)@(negedge cam_clk);vsync=0;repeat(4)@(negedge cam_clk);end
    endtask
    task send_frame;
        input integer version;integer row,col;reg [15:0] p;
        begin sync_frame();for(row=0;row<HEIGHT;row=row+1)begin
            for(col=0;col<WIDTH;col=col+1)begin p=pixel(row*WIDTH+col,version);href=1;data=p[7:0];@(negedge cam_clk);data=p[15:8];@(negedge cam_clk);end
            href=0;repeat(4)@(negedge cam_clk);
        end sync_frame();end
    endtask
    initial begin
        stream_file=$fopen("guarded-cam1-sccb25-mixed-stream.bin","wb");
        repeat(12)@(negedge core_clk);rst_n=1;wait(status_count>0);send_frame(0);
        if(frame_sequence || armed || writes)$fatal(1,"Boot captured without explicit authorization");
        command(15,1,0,0);await_result(1,1);
        if(armed || warmup_ready || safety_ok)$fatal(1,"OPEN implicitly armed or required warmup");
        command(16,2,1,24000);repeat(3000)@(negedge core_clk);
        if(armed || frame_sequence || last_status_result!=8'h34)$fatal(1,"Unready GRANT not rejected");
        source_valid=1;warmup_ready=1;wait(ready_for_grant);
        current_grant_seq=3;command(16,3,2,24000);wait(capture_active);repeat(12)@(negedge cam_clk);hold_raw_tail=1;
        source_over=1;send_frame(0);wait(raw_count==1);repeat(20)@(negedge core_clk);
        if(armed || !bank_locked || !raw_uart_locked || raw_done || stop_reason!=4)$fatal(1,"Overtemp did not stop admission and preserve final-stop ownership");
        permit_raw_tail=1;wait(raw_done);repeat(1200)@(negedge core_clk);
        if(raw_failed || bank_locked || armed || completed_frames!=1)$fatal(1,"Overtemp drain failed");
        $display("PASS guarded board: boot zero raw, OPEN before warmup, invalid/unready grant rejected, GRANT ACK precedes raw, overtemp admission stop with full native frame/CRC drain.");
        source_over=0;wait(ready_for_grant);permit_raw_tail=0;hold_raw_tail=0;
        current_grant_seq=4;command(16,4,2,24000);wait(capture_active);repeat(12)@(negedge cam_clk);
        @(negedge source_clk);source_running=0;send_frame(1);
        wait(!safety_ok);wait(raw_count==2);wait(raw_done);repeat(1200)@(negedge core_clk);
        if(armed || bank_locked || raw_failed || stop_reason!=4 || safety_snapshot_age<5000 || completed_frames!=2)$fatal(1,"Halted 27MHz source did not stop/drain");
        source_running=1;wait(ready_for_grant);
        current_grant_seq=5;command(16,5,2,1);wait(capture_active);repeat(12)@(negedge cam_clk);
        repeat(2000)@(negedge core_clk);
        if(armed || !bank_locked || stop_reason!=2)$fatal(1,"Lease did not expire on frozen camera source: armed %d lock %d reason %d cycles %d safety %d",armed,bank_locked,stop_reason,remaining_cycles,safety_ok);
        send_frame(2);wait(raw_count==3);wait(raw_done);repeat(1500)@(negedge core_clk);
        if(armed || bank_locked || raw_failed || frame_sequence!=3 || completed_frames!=3)$fatal(1,"Lease drain/finite captures failed");
        source_failed=1;source_fault=8'h71;wait(!safety_ok);
        command(16,6,1,24000);repeat(2000)@(negedge core_clk);
        if(armed || frame_sequence!=3 || !temp_failed)$fatal(1,"ADC failure did not block next grant");
        command(17,7,0,0);await_result(7,1);
        if(packet_index!=0 || raw_count!=3 || status_count<8)$fatal(1,"Mixed stream incomplete");
        $fclose(stream_file);
        $display("PASS guarded board pipeline: 8N1 command RX -> engine -> real lease -> DVP/DDR/UART mixed CRC packets, status boundaries/final byte_done, stopped-source watchdog, frozen-source lease expiry, ADC failure and STOP.");$finish;
    end
    initial begin #20000000;$fatal(1,"Guarded board regression timeout state %d seq %d status %d raw %d",raw_state,frame_sequence,status_count,raw_count);end
endmodule
