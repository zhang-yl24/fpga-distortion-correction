`timescale 1ns/1ps
// Synthetic complete720 frame through frozen CDC/packer/writer/exporter.
// No sensor initializer or board wrapper is instantiated; UART ready is abstract.
// Real DVP bytes through the shipped CDC/packer/writer/exporter, with a
// deterministic DDR bus model and independent byte/CRC reference.
module tb_camera720_raw_capture;
    localparam WIDTH=1280,HEIGHT=720;
    localparam BYTES=WIDTH*HEIGHT*2,TOTAL=BYTES+44,FRAME_BEATS=WIDTH*HEIGHT/16;
    reg clk=0,cam_clk=0;always #4 clk=~clk;always #11 cam_clk=~cam_clk;
    reg rst_n=0,request_enable=0,vsync=0,href=0;
    reg camera_authorize=0; wire store_arm;
    wire request_valid=request_enable && store_arm;
    capture_warmup #(.CLOCK_HZ(1000),.DELAY_MS(5)) warmup(
        .clk(clk),.rst_n(rst_n),.ready(camera_authorize),.armed(store_arm));reg [7:0] data=0;
    reg [27:0] request_base_address=0;
    reg [31:0] request_frame_id=0,request_camera_id=0;reg [1:0] request_eye=0;
    wire request_ready,bank_locked,capture_active,done,failed;
    wire [7:0] fault;wire [3:0] state;
    wire [31:0] held_frame_id,held_camera_id,source_crc,written_beats;
    wire [1:0] held_eye;wire [15:0] frame_width,frame_height;
    wire [27:0] awaddr,araddr;wire [3:0] awlen,arlen;wire awvalid,arvalid;
    wire [255:0] wdata;wire [31:0] wstrb;
    reg awready=0,arready=0,wready=0,wlast=0,rvalid=0,rlast=0;
    reg [255:0] rdata=0;reg [3:0] rid=0;
    wire byte_valid;wire [7:0] byte_data;reg byte_ready=0,byte_done=0;
    raw_camera_capture #(.WIDTH(WIDTH),.HEIGHT(HEIGHT),.TIMEOUT_BITS(16)) dut(
        .core_clk(clk),.cam_clk(cam_clk),.rst_n(rst_n),.*);
    reg [255:0] memory[0:FRAME_BEATS+31];reg [7:0] packet[0:TOTAL+31];
    integer cycle=0,write_base=0,read_base=0,windex=0,rindex=0;
    integer writes=0,reads=0,accepted_bytes=0,tail_delay=0;
    reg writing=0,reading=0,corrupt=0,bad_wlast=0,hold_uart=0,permit_final_done=0;
    reg stalled_ar=0,stalled_aw=0,stalled_byte=0;
    reg [27:0] saved_ar,saved_aw;reg [7:0] saved_byte;
    reg [3:0] previous_state=0;
    integer stream_file;
    function [15:0] pixel_value;
        input integer index,version;
        begin pixel_value=16'h4321 ^ (index*53) ^ (version*16'h1111);end
    endfunction
    function [31:0] crc_byte;
        input [31:0] previous;input [7:0] value;integer b;reg [31:0] c;
        begin c=previous^{24'b0,value};for(b=0;b<8;b=b+1)c=(c>>1)^(c[0]?32'hEDB88320:0);crc_byte=c;end
    endfunction
    function [31:0] expected_crc;
        input integer version;integer p;reg [31:0] c;reg [15:0] value;
        begin c=32'hFFFFFFFF;for(p=0;p<WIDTH*HEIGHT;p=p+1)begin
            value=pixel_value(p,version);c=crc_byte(c,value[7:0]);c=crc_byte(c,value[15:8]);
        end expected_crc=~c;end
    endfunction
    function [31:0] packet_u32;
        input integer offset;
        begin packet_u32={packet[offset+3],packet[offset+2],packet[offset+1],packet[offset]};end
    endfunction
    always @(posedge clk) begin
        if(!rst_n) begin
            writing=0;reading=0;windex=0;rindex=0;writes=0;reads=0;
            accepted_bytes=0;tail_delay=0;stalled_ar=0;stalled_aw=0;stalled_byte=0;previous_state=0;
        end else begin
            if(state==1 && previous_state!=1)begin
                if(writing || reading)$fatal(1,"Rearm before previous DDR owner drained");
                writes=0;reads=0;accepted_bytes=0;tail_delay=0;
            end
            previous_state=state;
            if(stalled_ar && (!arvalid || araddr!==saved_ar))$fatal(1,"Stalled AR changed");
            if(stalled_aw && (!awvalid || awaddr!==saved_aw))$fatal(1,"Stalled AW changed");
            if(stalled_byte && (!byte_valid || byte_data!==saved_byte))$fatal(1,"Stalled UART byte changed");
            stalled_ar=arvalid && !arready;saved_ar=araddr;
            stalled_aw=awvalid && !awready;saved_aw=awaddr;
            stalled_byte=byte_valid && !byte_ready;saved_byte=byte_data;
            if(awvalid && awready)begin
                if(writing || awlen!==15 || !bank_locked || awaddr[6:0]!=0 || awaddr>460672)$fatal(1,"Bad write ownership");
                writing=1;windex=0;write_base=awaddr/8;
            end
            if(wready)begin
                if(!writing || reading || wstrb!==32'hFFFFFFFF || !bank_locked)$fatal(1,"Unexpected source-bank write");
                memory[write_base+windex]=wdata;writes=writes+1;
                if(windex==15)writing=0;windex=windex+1;
            end
            if(arvalid && arready)begin
                if(writing || reads>=FRAME_BEATS || arlen!==15 || !bank_locked || araddr[6:0]!=0 || araddr>460672)$fatal(1,"Bad read ownership");
                reading=1;rindex=0;read_base=araddr/8;
            end
            if(rvalid)begin reads=reads+1;if(rindex==15)reading=0;rindex=rindex+1;end
            if(byte_valid && byte_ready)begin
                if(!bank_locked || accepted_bytes>=TOTAL)$fatal(1,"UART/ownership overflow");
                packet[accepted_bytes]=byte_data;accepted_bytes=accepted_bytes+1;
                tail_delay=5;
            end
            if(done && (accepted_bytes!=TOTAL || !permit_final_done))$fatal(1,"Published before final UART stop bit");
        end
    end
    always @(negedge clk)begin
        cycle=cycle+1;
        awready=rst_n && !writing && cycle%5!=0;
        arready=rst_n && !reading && cycle%7!=0;
        wready=rst_n && writing && cycle%3!=0;
        wlast=wready && (bad_wlast ? windex==14:windex==15);
        rvalid=rst_n && reading && cycle%4!=0;rlast=rvalid && rindex==15;
        rdata=reading ? memory[read_base+rindex]:0;
        if(corrupt && reading && read_base==16 && rindex==3)rdata[147]=!rdata[147];
        byte_ready=rst_n && !hold_uart && cycle%6==0;
        byte_done=0;
        if(tail_delay>0)begin
            tail_delay=tail_delay-1;
            if(tail_delay==0 && (accepted_bytes<TOTAL || permit_final_done))byte_done=1;
        end else if(accepted_bytes==TOTAL && permit_final_done && state==4)byte_done=1;
    end
    task reset_all;
        begin
            @(negedge clk);rst_n=0;request_enable=0;href=0;vsync=0;permit_final_done=0;
            corrupt=0;bad_wlast=0;hold_uart=0;
            repeat(10)@(negedge cam_clk);rst_n=1;repeat(10)@(negedge cam_clk);
        end
    endtask
    task request_frame;
        input [31:0] ident;
        begin
            wait(request_ready);@(negedge clk);
            request_frame_id=ident;request_camera_id=32'h43414d32;request_eye=2;
            request_base_address=0;request_enable=1;@(negedge clk);request_enable=0;
            wait(capture_active);repeat(12)@(negedge cam_clk);
        end
    endtask
    task sync_frame;
        begin
            @(negedge cam_clk);href=0;vsync=1;
            repeat(4)@(negedge cam_clk);vsync=0;repeat(4)@(negedge cam_clk);
        end
    endtask
    task send_frame;
        input integer mode,version;integer row,col;reg [15:0] value;
        begin
            sync_frame();
            for(row=0;row<HEIGHT;row=row+1)begin
                for(col=0;col<WIDTH-((mode==1 && row==HEIGHT-1)?1:0);col=col+1)begin
                    value=pixel_value(row*WIDTH+col,version);
                    href=1;data=value[7:0];@(negedge cam_clk);
                    data=value[15:8];@(negedge cam_clk);
                end
                if(mode==2 && row==HEIGHT-1)begin href=1;data=8'hc7;@(negedge cam_clk);end
                href=0;repeat(4)@(negedge cam_clk);
            end
            sync_frame();
        end
    endtask
    task await_fault;
        integer timeout;
        begin
            timeout=0;
            while(!failed && timeout<100000)begin @(negedge clk);timeout=timeout+1;end
            if(!failed || done || request_ready)$fatal(1,"Fault not quarantined state=%d",state);
            if(accepted_bytes==TOTAL)$fatal(1,"Invalid frame exported complete packet");
        end
    endtask
    task validate_packet;
        input integer ident,version;integer p;reg [15:0] value;reg [31:0] hc;
        begin
            if(accepted_bytes!=TOTAL || written_beats!=FRAME_BEATS || source_crc!==expected_crc(version))$fatal(1,"Frame metadata/CRC mismatch");
            if({packet[0],packet[1],packet[2],packet[3],packet[4],packet[5],packet[6],packet[7]}!=="PGFRAME1")$fatal(1,"Header magic");
            if({packet[9],packet[8]}!==WIDTH || {packet[11],packet[10]}!==HEIGHT || packet_u32(12)!==ident ||
               packet_u32(16)!==BYTES || packet_u32(20)!==expected_crc(version) || packet_u32(24)!==32'h5651)$fatal(1,"Header metadata");
            hc=32'hFFFFFFFF;for(p=0;p<28;p=p+1)hc=crc_byte(hc,packet[p]);
            if(packet_u32(28)!==~hc)$fatal(1,"Header CRC");
            for(p=0;p<WIDTH*HEIGHT;p=p+1)begin
                value=pixel_value(p,version);
                if({packet[33+p*2],packet[32+p*2]}!==value)$fatal(1,"Native pixel mismatch %d",p);
            end
            if({packet[32+BYTES],packet[33+BYTES],packet[34+BYTES],packet[35+BYTES],
                packet[36+BYTES],packet[37+BYTES],packet[38+BYTES],packet[39+BYTES]}!=="PGEND001")$fatal(1,"Trailer magic");
            if(packet_u32(40+BYTES)!==expected_crc(version))$fatal(1,"Trailer CRC");
            for(p=0;p<TOTAL;p=p+1)$fwrite(stream_file,"%c",packet[p]);
        end
    endtask
    integer before_writes;
    initial begin
        stream_file=$fopen("current720-raw-stream.bin","wb");
        reset_all();
        request_enable=1;
        repeat(12)@(negedge clk);
        if(capture_active || bank_locked || store_arm)$fatal(1,"Request admitted before live authorization");
        request_enable=0;camera_authorize=1;wait(store_arm);
        request_frame(41);
        fork
            send_frame(0,0);
            begin
                repeat(2000)@(negedge cam_clk);camera_authorize=0;
                @(negedge clk);
                if(store_arm)$fatal(1,"Authorization loss did not revoke admission");
            end
        join
        wait(accepted_bytes==TOTAL);
        if(request_ready || done || !bank_locked)$fatal(1,"Released before stop bit");
        // Change all upstream metadata and send a different sensor frame while
        // the bank is frozen. Neither the exported frame nor the bank may change.
        before_writes=writes;request_frame_id=99;request_camera_id=32'h43414d31;request_eye=1;
        request_base_address=128;send_frame(0,1);
        if(writes!=before_writes || held_frame_id!=41 || held_camera_id!=32'h43414d32 || held_eye!=2)$fatal(1,"Frozen ownership/metadata changed");
        validate_packet(41,0);
        permit_final_done=1;wait(done);@(negedge clk);
        if(!request_ready || bank_locked)$fatal(1,"No ownership release/rearm after stop bit");
        $display("PASS raw capture: complete native DVP, CRC/header/pixels, DDR stalls, UART backpressure, frozen bank and identity, delayed final stop bit.");
        if(writes!=57600 || reads!=57600 || frame_width!=1280 || frame_height!=720)$fatal(1,"720 shape/beat totals");
        request_enable=1;
        repeat(100)@(negedge clk);
        if(bank_locked || capture_active || writes!=57600 || store_arm)$fatal(1,"New frame admitted after authorization loss");
        $display("PASS current720 raw admission: preauthorization blocked, mode loss drains in-flight frame, new requests blocked");
        $fclose(stream_file);
        $display("PASS current720 raw digital: 921600 exact RGB565 pixels, 1843200 payload bytes, 57600 DDR write/read beats, native PGFRAME1 CRC, stalls/frozen bank/final stop-bit ownership; no sensor mode, PCLK timing or fps acceptance.");
        $finish;
    end
    initial begin #250000000;$fatal(1,"720 digital regression timeout state=%d fault=%h bytes=%d",state,fault,accepted_bytes);end
endmodule
