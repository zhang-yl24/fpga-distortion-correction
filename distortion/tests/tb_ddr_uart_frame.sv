`timescale 1ns/1ps
module tb_ddr_uart_frame;
    reg clk=0;always #4 clk=~clk;
    reg rst_n=0,start=0;reg [31:0] frame_id=1,source_crc;
    wire [27:0] araddr;wire [3:0] arlen;
    wire arvalid,byte_valid,idle,done,failed;wire [7:0] byte_data,fault;
    reg arready=0,rvalid=0,rlast=0;reg [255:0] rdata=0;reg [3:0] rid=0;
    wire tx,busy,byte_done;wire byte_ready=!busy;
    ddr_uart_frame #(.WIDTH(32),.HEIGHT(32),.TIMEOUT_BITS(12)) dut(.clk(clk),.rst_n(rst_n),.start(start),
        .base_address(28'd128),.frame_id(frame_id),.source_crc(source_crc),
        .araddr(araddr),.arlen(arlen),.arvalid(arvalid),.arready(arready),
        .rdata(rdata),.rvalid(rvalid),.rlast(rlast),.rid(rid),
        .byte_valid(byte_valid),.byte_ready(byte_ready),.byte_done(byte_done),.byte_data(byte_data),
        .idle(idle),.done(done),.failed(failed),.fault(fault));
    uart_tx #(.CLOCK_HZ(125000000),.BAUD(31250000)) uart(.clk(clk),.rst_n(rst_n),
        .start(byte_valid && byte_ready),.data(byte_data),.tx(tx),.busy(busy),.done(byte_done));
    reg [7:0] packets[0:6275];reg [255:0] beats[0:191];reg [31:0] crcs[0:2];
    integer received=0,ticks=0,burst_left=0,beat_addr=0,phase=0,mode=0;
    reg held=0;reg [7:0] held_data;reg arheld=0;reg [27:0] held_addr;
    always @(negedge clk) begin
        ticks=ticks+1;arready=rst_n && mode!=3 && burst_left==0 && ticks%7>=3;
        rvalid=rst_n && mode!=3 && burst_left!=0 && ticks%5!=0;
        rlast=burst_left==1;rid=mode==2 ? 1:0;
        if(mode==1 && burst_left==12) rlast=1;
        if(rvalid) rdata=beats[phase*64+beat_addr];
    end
    always @(posedge clk) begin
        if(!rst_n) begin burst_left<=0;held<=0;arheld<=0;end
        else begin
            if(held && (!byte_valid || byte_data!==held_data)) $fatal(1,"Byte changed under UART backpressure");
            held<=byte_valid && !byte_ready;held_data<=byte_data;
            if(arheld && (!arvalid || araddr!==held_addr)) $fatal(1,"AR withdrew or changed before acceptance");
            arheld<=arvalid && !arready;held_addr<=araddr;
            if(arvalid && arready) begin
                if(arlen!=15 || araddr<128 || araddr>=640 || araddr[6:0]!=0) $fatal(1,"Invalid reserved burst");
                burst_left<=16;beat_addr<=(araddr-128)>>3;
            end
            if(rvalid) begin burst_left<=burst_left-1;beat_addr<=beat_addr+1;end
        end
    end
    // Decode the physical 8N1 wire, not the exporter's internal byte bus.
    reg [7:0] decoded;integer bitno,reset_epoch=0,decode_epoch;
    initial forever begin
        @(negedge tx);decode_epoch=reset_epoch;
        #16;if(decode_epoch==reset_epoch && tx!==0) $fatal(1,"Bad UART start bit");
        for(bitno=0;bitno<8;bitno=bitno+1) begin #32;decoded[bitno]=tx;end
        #32;if(decode_epoch==reset_epoch && tx!==1) $fatal(1,"Bad UART stop bit");
        if(mode==0 && decode_epoch==reset_epoch && rst_n) begin
            if(decoded!==packets[received]) $fatal(1,"UART packet mismatch at %0d got %h expected %h",received,decoded,packets[received]);
            received=received+1;
        end
    end
    task reset;
        begin @(negedge clk);rst_n=0;start=0;reset_epoch=reset_epoch+1;repeat(50) @(posedge clk);@(negedge clk);rst_n=1;end
    endtask
    task launch;
        begin @(negedge clk);source_crc=crcs[phase];frame_id=phase+1;start=1;@(negedge clk);start=0;end
    endtask
    initial begin
        $readmemh("packets.mem",packets);$readmemh("beats.mem",beats);$readmemh("crcs.mem",crcs);
        for(phase=0;phase<3;phase=phase+1) begin
            reset();launch();wait(done);#1;
            if(failed || received!=(phase+1)*2092 || busy) $fatal(1,"Frame completion before final stop bit");
        end
        phase=0;
        for(mode=1;mode<=3;mode=mode+1) begin reset();launch();wait(failed);#1;
            if(fault!==(mode==3 ? 8'h01:8'h03)) $fatal(1,"Wrong quarantine fault");
        end
        // No final trailer can be emitted when DDR data does not match capture.
        mode=4;reset();launch();source_crc=0; // Latched correct CRC remains stable.
        wait(dut.state==5);@(negedge clk);force dut.expected_crc=0;
        wait(failed);#1;if(fault!==8'h14) $fatal(1,"Source CRC disagreement missed");release dut.expected_crc;
        mode=4;reset();launch();wait(dut.state==5);reset();
        mode=0;received=0;launch();wait(done);#1;
        if(received!=2092 || failed) $fatal(1,"Mid-stream reset recovery failed");
        $display("PASS DDR-to-UART native frames: three complete packets decoded on 8N1 wire against Python/zlib goldens; AR/R stalls, byte hold, header/source/read CRC32, malformed RLAST/RID, timeout, source mismatch, final stop-bit completion and mid-stream reset recovery.");$finish;
    end
    initial begin #10000000;$fatal(1,"UART exporter timeout received=%0d",received);end
endmodule
