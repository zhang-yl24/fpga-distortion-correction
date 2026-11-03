// Additive observation only. No telemetry ready/fault feeds the video path.
// Enclosing TB timescale is 1ps/1ps; use actual 27 MHz / 115200 baud.
localparam real TELEMETRY_BIT_PS=1000000000000.0/115200.0;
localparam real TX_BIT_PS=234.0*(1000000000000.0/27000000.0);
reg telemetry_clk=0,telemetry_rx=1;
wire telemetry_tx;
reg [31:0] telemetry_param_id=0;
reg video_window=0;
always #18518.5185185 telemetry_clk=~telemetry_clk;
reg [7:0] arm_bytes[0:23];
integer telemetry_log,telemetry_byte_count=0;
initial begin
 telemetry_log=$fopen("telemetry_trace.txt","w");
 if(!telemetry_log)$fatal(1,"TELEMETRY_LOG_OPEN");
 $readmemh("arm.mem",arm_bytes);
 $fdisplay(telemetry_log,"EVENT OPEN %0t",$time);$fflush(telemetry_log);
end
task automatic arm_before_video;
 integer a,b;
 begin
  $fdisplay(telemetry_log,"EVENT ARM_BEGIN %0t",$time);$fflush(telemetry_log);
  repeat(10)@(negedge telemetry_clk);
  for(a=0;a<24;a=a+1)begin
   telemetry_rx=0;#(TELEMETRY_BIT_PS);
   for(b=0;b<8;b=b+1)begin telemetry_rx=arm_bytes[a][b];#(TELEMETRY_BIT_PS);end
   telemetry_rx=1;#(TELEMETRY_BIT_PS);
  end
  repeat(20)@(negedge telemetry_clk);
  if(dut.telemetry.rx_queued!==1 || dut.telemetry.rx_rejected!==0)
   $fatal(1,"SYSTEM_UART_ARM_NOT_ACCEPTED");
  $fdisplay(telemetry_log,"EVENT ARM_ACCEPTED %0t",$time);$fflush(telemetry_log);
 end
endtask
reg [7:0] telemetry_decoded;integer telemetry_bit;
// Host-side parser consumes ONLY independently decoded UART pin bytes.
reg [7:0] host_packet[0:127];
integer host_index=0,host_length=0,host_acks=0,host_signatures=0;
reg [3:0] host_frame_mask=0;
reg host_signature=0;
function automatic [31:0] host_crc_byte(input [31:0] prior,input [7:0] value);
 reg [31:0] c;integer bitno;
 begin c=prior^value;for(bitno=0;bitno<8;bitno=bitno+1)c=c[0]?(c>>1)^32'hedb88320:c>>1;host_crc_byte=c;end
endfunction
task automatic host_accept_byte(input [7:0] value);
 integer n,frame;reg [31:0] crc,received_crc;
 begin
  if(host_index==0)begin
   if(value==8'h53)begin host_signature=0;host_length=24;end
   else if(value==8'h50)begin host_signature=1;host_length=128;end
   else $fatal(1,"HOST_UNKNOWN_PACKET_START");
  end
  host_packet[host_index]=value;host_index=host_index+1;
  if(host_index==host_length)begin
   crc=32'hffffffff;
   for(n=0;n<(host_signature?120:20);n=n+1)crc=host_crc_byte(crc,host_packet[n]);
   if(host_signature)begin
    received_crc={host_packet[123],host_packet[122],host_packet[121],host_packet[120]};
    if({host_packet[0],host_packet[1],host_packet[2],host_packet[3],host_packet[4],host_packet[5],host_packet[6],host_packet[7]}!=="PGSIG001" ||
       {host_packet[124],host_packet[125],host_packet[126],host_packet[127]}!=="SG01" ||
       {host_packet[13],host_packet[12]}!==16'd128) $fatal(1,"HOST_SIGNATURE_FRAMING");
    frame={host_packet[27],host_packet[26],host_packet[25],host_packet[24]};
    if(frame<1 || frame>3 || host_frame_mask[frame])$fatal(1,"HOST_SIGNATURE_ID_DUPLICATE");
    host_frame_mask[frame]=1;host_signatures=host_signatures+1;
   end else begin
    received_crc={host_packet[23],host_packet[22],host_packet[21],host_packet[20]};
    if({host_packet[0],host_packet[1],host_packet[2],host_packet[3]}!=="SGK1" ||
       {host_packet[7],host_packet[6]}!==16'd24 || host_packet[5]!==8'd1 ||
       {host_packet[11],host_packet[10],host_packet[9],host_packet[8]}!==32'd1 ||
       {host_packet[15],host_packet[14],host_packet[13],host_packet[12]}!==32'h87654321)
      $fatal(1,"HOST_ACK_FRAMING_OR_ID");
    host_acks=host_acks+1;if(host_acks!=1)$fatal(1,"HOST_DUPLICATE_ACK");
   end
   if(received_crc!==~crc)$fatal(1,"HOST_PACKET_CRC");
   host_index=0;
   $fdisplay(telemetry_log,"EVENT HOST_PACKET %0t ack=%0d sig=%0d bytes=%0d",$time,host_acks,host_signatures,telemetry_byte_count);
   $fflush(telemetry_log);$display("TELEMETRY_HOST_PACKET t=%0t ack=%0d sig=%0d bytes=%0d",$time,host_acks,host_signatures,telemetry_byte_count);$fflush();
  end
 end
endtask
initial forever begin
 @(negedge telemetry_tx);
 if(rst_n)begin
  #(TX_BIT_PS/2.0);
  if(telemetry_tx!==0)$fatal(1,"SYSTEM_UART_BAD_START");
  for(telemetry_bit=0;telemetry_bit<8;telemetry_bit=telemetry_bit+1)begin
   #(TX_BIT_PS);telemetry_decoded[telemetry_bit]=telemetry_tx;
  end
  #(TX_BIT_PS);
  if(telemetry_tx!==1)$fatal(1,"SYSTEM_UART_BAD_STOP");
  $fdisplay(telemetry_log,"B %02x",telemetry_decoded);telemetry_byte_count=telemetry_byte_count+1;$fflush(telemetry_log);
  host_accept_byte(telemetry_decoded);
 end
end
always @(negedge pix_out_clk)if(rst_n && pix_pixel_valid)begin
 if(!dut.scan_metadata_valid || dut.scan_active_param_id!==32'ha1000000+pix_frame_id ||
    dut.scan_active_mode!==(pix_frame_id==2 ? 8'd1:8'd0))
  $fatal(1,"REAL_SYSTEM_WRONG_LEASE_METADATA");
 $fdisplay(telemetry_log,"P %0d %0d %0d %0d %06x %0d %0d %08x %02x %0d",
  pix_frame_id,dut.scan_active_epoch,dut.scan_pixel_x,dut.scan_pixel_y,pix_rgb,
  pix_frame_start,pix_frame_last,dut.scan_active_param_id,dut.scan_active_mode,pix_frame_bank);
 $fflush(telemetry_log);
end
// A momentary idle UART is insufficient: account for every producer/CDC/slot.
function automatic telemetry_paths_idle;
 begin telemetry_paths_idle=
  (dut.telemetry.transmitter.busy===1'b0) && (dut.telemetry.link.tx_valid===1'b0) &&
  (dut.telemetry.link.tx_owner===2'd0) && (dut.telemetry.link.ack_active===1'b0) &&
  (dut.telemetry.link.signature_active===1'b0) && (dut.telemetry.link.reply_valid===1'b0) &&
  (dut.telemetry.link.gate_ack_valid===1'b0) && (dut.telemetry.link.cmd_valid===1'b0) &&
  (dut.telemetry.link.load_valid===1'b0) && (dut.telemetry.link.parser.index===5'd0) &&
  (dut.telemetry.link.observer.gate.pending===1'b0) && (dut.telemetry.link.observer.capture.active===1'b0) &&
  (dut.telemetry.link.mailbox_request===dut.telemetry.link.mailbox_ack) &&
  (dut.telemetry.link.signature_tx.request_sync==={2{dut.telemetry.link.mailbox_request}}) &&
  (dut.telemetry.link.observer.capture.ack_sync==={2{dut.telemetry.link.mailbox_ack}}) &&
  (dut.telemetry.link.request_cdc.request_toggle===dut.telemetry.link.request_cdc.ack_toggle) &&
  (dut.telemetry.link.request_cdc.request_sync==={2{dut.telemetry.link.request_cdc.request_toggle}}) &&
  (dut.telemetry.link.request_cdc.ack_sync==={2{dut.telemetry.link.request_cdc.ack_toggle}}) &&
  (dut.telemetry.link.request_cdc.d_valid===1'b0) &&
  (dut.telemetry.link.ack_cdc.request_toggle===dut.telemetry.link.ack_cdc.ack_toggle) &&
  (dut.telemetry.link.ack_cdc.request_sync==={2{dut.telemetry.link.ack_cdc.request_toggle}}) &&
  (dut.telemetry.link.ack_cdc.ack_sync==={2{dut.telemetry.link.ack_cdc.ack_toggle}}) &&
  (dut.telemetry.link.ack_cdc.d_valid===1'b0);
 end
endfunction
reg drain_observe=0;reg [31:0] drop_pix_previous=0,drop_ctrl_previous=0;
integer drop_pix_stable=0,drop_ctrl_stable=0,idle_pix_stable=0,idle_ctrl_stable=0;
always @(negedge pix_out_clk)begin
 if(!rst_n || !drain_observe)begin drop_pix_stable<=0;idle_pix_stable<=0;end
 else begin
  if(dut.telemetry.signature_dropped===drop_pix_previous)begin if(drop_pix_stable<32)drop_pix_stable<=drop_pix_stable+1;end
  else drop_pix_stable<=0;
  if(telemetry_paths_idle())begin if(idle_pix_stable<32)idle_pix_stable<=idle_pix_stable+1;end
  else idle_pix_stable<=0;
 end
 drop_pix_previous<=dut.telemetry.signature_dropped;
end
always @(negedge telemetry_clk)begin
 if(!rst_n || !drain_observe)begin drop_ctrl_stable<=0;idle_ctrl_stable<=0;end
 else begin
  if(dut.telemetry.signature_dropped===drop_ctrl_previous)begin if(drop_ctrl_stable<32)drop_ctrl_stable<=drop_ctrl_stable+1;end
  else drop_ctrl_stable<=0;
  if(telemetry_paths_idle())begin if(idle_ctrl_stable<32)idle_ctrl_stable<=idle_ctrl_stable+1;end
  else idle_ctrl_stable<=0;
 end
 drop_ctrl_previous<=dut.telemetry.signature_dropped;
end
task automatic finish_telemetry;
 integer locked_drop,target_bytes,progress_cycles,quiet_cycle;
 begin
  // Called only after all original video assertions and real drain pass.
  $fdisplay(telemetry_log,"EVENT DRAIN_BEGIN %0t bytes=%0d drops=%0d",$time,telemetry_byte_count,dut.telemetry.signature_dropped);
  $fflush(telemetry_log);$display("TELEMETRY_DRAIN_BEGIN t=%0t bytes=%0d",$time,telemetry_byte_count);$fflush();
  drain_observe=1;progress_cycles=0;
  wait(drop_pix_stable>=16 && drop_ctrl_stable>=16);
  locked_drop=dut.telemetry.signature_dropped;
  if(locked_drop!==0 && locked_drop!==1)$fatal(1,"UNEXPECTED_SIGNATURE_DROP_COUNT");
  target_bytes=24+128*(3-locked_drop);
  while(!(telemetry_byte_count==target_bytes && host_acks==1 && host_signatures==3-locked_drop && host_index==0 &&
          idle_pix_stable>=16 && idle_ctrl_stable>=16 && telemetry_paths_idle()))begin
   @(negedge telemetry_clk);
   if(dut.telemetry.signature_dropped!==locked_drop)$fatal(1,"DROP_CHANGED_AFTER_VIDEO_BARRIER");
   if(telemetry_byte_count>target_bytes)$fatal(1,"EXTRA_UART_BYTES");
   progress_cycles=progress_cycles+1;
   if(progress_cycles%27000==0)begin
    $fdisplay(telemetry_log,"EVENT DRAIN_PROGRESS %0t bytes=%0d target=%0d ack=%0d sig=%0d busy=%0d valid=%0d idle=%0d",$time,telemetry_byte_count,target_bytes,host_acks,host_signatures,dut.telemetry.transmitter.busy,dut.telemetry.link.tx_valid,telemetry_paths_idle());
    $fflush(telemetry_log);$display("TELEMETRY_DRAIN_PROGRESS t=%0t bytes=%0d target=%0d",$time,telemetry_byte_count,target_bytes);$fflush();
   end
  end
  if(!host_frame_mask[1] || !host_frame_mask[2])$fatal(1,"REQUIRED_RAW_OR_CORRECTED_SIGNATURE_MISSING");
  // One complete UART byte beyond fully settled queues catches delayed starts.
  for(quiet_cycle=0;quiet_cycle<234*10;quiet_cycle=quiet_cycle+1)begin
   @(negedge telemetry_clk);
   if(!telemetry_paths_idle() || telemetry_tx!==1'b1 || telemetry_byte_count!=target_bytes ||
      host_index!=0 || dut.telemetry.signature_dropped!==locked_drop)
    $fatal(1,"LATE_PACKET_AFTER_DRAIN");
  end
  if(dut.telemetry.rx_rejected || dut.telemetry.rx_busy_drops || dut.telemetry.rx_timeouts)
   $fatal(1,"SYSTEM_UART_UNEXPECTED_RX_ERROR");
  $fdisplay(telemetry_log,"T %0d %0d",telemetry_byte_count,dut.telemetry.signature_dropped);
  $fdisplay(telemetry_log,"COMPLETE_REAL_SYSTEM_TELEMETRY");
  $fclose(telemetry_log);$display("COMPLETE_REAL_SYSTEM_TELEMETRY");
 end
endtask
initial begin #60000000000;$fatal(1,"SYSTEM_TELEMETRY_60MS_LIMIT");end
