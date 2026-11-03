// Test-only two-session UART peer. Actual baud and physical pin decoder.
localparam [31:0] TICKET_A=1,NONCE_A=32'h87654321,TAG_A=32'ha1000101;
localparam [31:0] TICKET_B=2,NONCE_B=32'h76543210,TAG_B=32'ha1000201;
localparam real TELEMETRY_BIT_PS=1000000000000.0/115200.0;
localparam real TX_BIT_PS=234.0*(1000000000000.0/27000000.0);
reg telemetry_clk=0,telemetry_rx=1;
wire telemetry_tx;
reg [31:0] telemetry_param_id=TAG_A;
reg video_window=0,inject_display_stall=0,fault_ar_selected=0;
reg [27:0] fault_ar_address;
reg [3:0] fault_ar_length;
integer fault_ar_hold_count=0;
always #18518.5185185 telemetry_clk=~telemetry_clk;
integer telemetry_log,telemetry_byte_count=0;
reg [7:0] arm_bytes[0:23],host_packet[0:127];
integer host_index=0,host_length=0,host_acks=0,host_signatures=0;
reg [7:0] telemetry_decoded;
integer telemetry_bit;
initial begin
 telemetry_log=$fopen("telemetry_trace.txt","w");
 if(!telemetry_log)$fatal(1,"TELEMETRY_LOG_OPEN");
end
task automatic send_arm(input [31:0] ticket,input [31:0] nonce);
 integer a,b;reg [159:0] body;reg [31:0] crc;
 begin
  body={32'd0,nonce,ticket,16'd24,8'd1,8'd1,32'h31414753};crc=32'hffffffff;
  for(a=0;a<20;a=a+1)begin arm_bytes[a]=body[a*8+:8];crc=crc_byte(crc,arm_bytes[a]);end
  crc=~crc;for(a=0;a<4;a=a+1)arm_bytes[20+a]=crc[a*8+:8];
  repeat(16)@(negedge telemetry_clk);
  for(a=0;a<24;a=a+1)begin
   telemetry_rx=0;#(TELEMETRY_BIT_PS);
   for(b=0;b<8;b=b+1)begin telemetry_rx=arm_bytes[a][b];#(TELEMETRY_BIT_PS);end
   telemetry_rx=1;#(TELEMETRY_BIT_PS);
  end
  repeat(20)@(negedge telemetry_clk);
  if(dut.telemetry.rx_queued!==1 || dut.telemetry.rx_rejected!==0 || dut.telemetry.rx_busy_drops!==0)
   $fatal(1,"ARM_NOT_ACCEPTED_BY_ACTUAL_UART");
 end
endtask
task automatic accept_wire_byte(input [7:0] value);
 integer n;reg [31:0] crc,actual;reg [31:0] ticket,nonce,epoch;
 begin
  if(host_index==0)begin
   if(value==8'h53)host_length=24;
   else if(value==8'h50)host_length=128;
   else $fatal(1,"WIRE_PACKET_PREFIX");
  end
  host_packet[host_index]=value;host_index=host_index+1;
  if(host_index==host_length)begin
   crc=32'hffffffff;
   for(n=0;n<(host_length==24?20:120);n=n+1)crc=crc_byte(crc,host_packet[n]);
   n=host_length==24?20:120;actual={host_packet[n+3],host_packet[n+2],host_packet[n+1],host_packet[n]};
   if(actual!==~crc)$fatal(1,"WIRE_PACKET_CRC");
   if(host_length==24)begin
    ticket={host_packet[11],host_packet[10],host_packet[9],host_packet[8]};
    nonce={host_packet[15],host_packet[14],host_packet[13],host_packet[12]};
    epoch={host_packet[19],host_packet[18],host_packet[17],host_packet[16]};
    if({host_packet[0],host_packet[1],host_packet[2],host_packet[3]}!=="SGK1" ||
       host_packet[4]!==1 || {host_packet[7],host_packet[6]}!==16'd24)$fatal(1,"WIRE_ACK_SCHEMA");
    if(host_acks==0)begin
     if(phase_id!=1 || ticket!==TICKET_A || nonce!==NONCE_A || epoch!==0 || host_packet[5]!==8'h14)
      $fatal(1,"EXPECTED_PENDING_ABORT_ACK");
    end else if(host_acks==1)begin
     if(phase_id!=2 || ticket!==TICKET_B || nonce!==NONCE_B || epoch==0 || host_packet[5]!==1)
      $fatal(1,"EXPECTED_NEW_ARMED_ACK");
    end else $fatal(1,"EXTRA_ACK");
    host_acks=host_acks+1;
   end else begin
    if(phase_id!=2 || host_acks!=2 || host_signatures!=0)$fatal(1,"FAULT_OR_DUPLICATE_SIGNATURE");
    host_signatures=host_signatures+1;
   end
   host_index=0;host_length=0;
   $display("FAULT_WIRE_PACKET t=%0t ack=%0d sig=%0d bytes=%0d",$time,host_acks,host_signatures,telemetry_byte_count);$fflush();
  end
 end
endtask
initial forever begin
 @(negedge telemetry_tx);
 if(rst_n)begin
  #(TX_BIT_PS/2.0);if(telemetry_tx!==0)$fatal(1,"UART_START");
  for(telemetry_bit=0;telemetry_bit<8;telemetry_bit=telemetry_bit+1)begin
   #(TX_BIT_PS);telemetry_decoded[telemetry_bit]=telemetry_tx;
  end
  #(TX_BIT_PS);if(telemetry_tx!==1)$fatal(1,"UART_STOP");
  $fdisplay(telemetry_log,"B %0d %02x",phase_id,telemetry_decoded);$fflush(telemetry_log);
  telemetry_byte_count=telemetry_byte_count+1;accept_wire_byte(telemetry_decoded);
 end
end
always @(posedge pix_out_clk)begin
 #2;
 if(rst_n && pix_pixel_valid)begin
  $fdisplay(telemetry_log,"P %0d %0d %0d %0d %0d %06x %0d %0d %08x %02x %0d",phase_id,
   pix_frame_id,dut.scan_active_epoch,dut.scan_pixel_x,dut.scan_pixel_y,pix_rgb,
   pix_frame_start,pix_frame_last,dut.scan_active_param_id,dut.scan_active_mode,pix_frame_bank);
  if(pix_frame_last)$fflush(telemetry_log);
 end
end

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
