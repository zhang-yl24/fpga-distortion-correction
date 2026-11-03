integer bad_done_count=0,pending_abort_edges=0,fault_preconditions=0;
reg bad_seen=0;
reg [31:0] fault_lease_id,fault_lease_epoch;
reg fault_lease_bank;
integer fault_hold_output_cycles=0,recovery_count=0;
reg fault_observed=0;
// Sample the gate's actual PRE-edge state when video_abort will be consumed.
always @(posedge pix_out_clk)begin
 if(rst_n && phase_id==1)begin
  if(dut.telemetry.link.observer.gate.video_abort && !fault_observed)begin
   if(dut.telemetry.link.observer.gate.pending!==1 ||
      dut.telemetry.link.observer.gate.ack_valid!==0 ||
      dut.telemetry.link.observer.gate.armed!==0 ||
      dut.telemetry.link.observer.capture.active!==0 ||
      dut.telemetry.link.mailbox_request!==dut.telemetry.link.mailbox_ack)
    $fatal(1,"ABORTED_ACK_PENDING_PRECONDITION");
   pending_abort_edges=pending_abort_edges+1;fault_observed=1;
  end
  if(dut.output_video.frame_active && !dut.output_video.failed)begin
   if(!fault_ar_selected || dut.output_video.request_open!==0 ||
      dut.telemetry.link.observer.gate.pending!==1 ||
      dut.telemetry.link.observer.gate.ack_valid!==0 ||
      dut.telemetry.link.observer.gate.armed!==0 ||
      dut.telemetry.link.observer.capture.active!==0 ||
      dut.telemetry.link.mailbox_request!==dut.telemetry.link.mailbox_ack || scan_count!=0)
    $fatal(1,"PRE_FIRST_PIXEL_ACTIVE_GRANT_CONTRACT");
   fault_lease_id=dut.output_video.active_id;
   fault_lease_epoch=dut.output_video.lease_epoch;
   fault_lease_bank=dut.output_video.active_bank;fault_preconditions=fault_preconditions+1;
  end
 end
 #2;
 if(!rst_n)bad_seen=pix_done_toggle;
 else if(phase_id==1)begin
  if(pix_pixel_valid || pix_frame_start || pix_frame_last || pix_rgb!==0)
   $fatal(1,"FAULT_FRAME_EXPOSED_PIXEL");
  if(pix_done_toggle!=bad_seen)begin
   bad_seen=pix_done_toggle;bad_done_count=bad_done_count+1;
   if(bad_done_count!=1 || pix_done_good!==0 || dut.scan_fault!==8'h02 || underflows!==1 ||
      dut.output_video.consumed_pixels!==0 || dut.output_video.done_id!==fault_lease_id ||
      dut.output_video.done_epoch!==fault_lease_epoch || dut.output_video.done_bank!==fault_lease_bank ||
      fault_preconditions==0 || unique_total!=0)
    $fatal(1,"BAD_DONE_IDENTITY_COUNT_OR_CAUSE");
   $display("FAULT_UNDERFLOW t=%0t id=%0d epoch=%0d",$time,fault_lease_id,fault_lease_epoch);$fflush();
  end
  if(dut.output_video.failed)begin
   fault_hold_output_cycles=fault_hold_output_cycles+1;
   if(dut.scan_fault!==8'h02 || underflows!==1 || display_valid!==0 ||
      dut.output_video.metadata_valid!==0 || dut.output_video.request_open!==0)
    $fatal(1,"FAULT_NOT_FAIL_CLOSED");
  end
 end
end
// Session B consumes one full corrected image, then stops requesting refreshes
// after the actual registered final pixel. The current good done is not bypassed.
always @(negedge pix_out_clk)begin
 if(rst_n && phase_id==2 && pix_frame_last)scan_enable=0;
end
task automatic telemetry_barrier(input integer target);
 integer quiet_byte;
 begin
  drain_observe=1;
  wait(telemetry_byte_count==target && host_index==0 &&
       idle_pix_stable>=16 && idle_ctrl_stable>=16 && telemetry_paths_idle());
  for(quiet_byte=0;quiet_byte<234*10;quiet_byte=quiet_byte+1)begin
   @(negedge telemetry_clk);
   if(telemetry_byte_count!=target || host_index!=0 || !telemetry_paths_idle() || telemetry_tx!==1)
    $fatal(1,"EXTRA_PACKET_OR_UNSTABLE_UART_DRAIN");
  end
  drain_observe=0;
 end
endtask
initial begin
 #35000000000;$fatal(1,"FAULT_RECOVERY_GLOBAL_35MS_WATCHDOG");
end
always @(negedge telemetry_clk)begin
 if($time%1000000000 < 37038)begin
  $display("FAULT_PROGRESS t=%0t phase=%0d bad=%0d good=%0d bytes=%0d",$time,phase_id,bad_done_count,unique_total,telemetry_byte_count);$fflush();
 end
end
initial begin
 if(W!=32 || H!=32)$fatal(1,"FAULT_CASE_SMALL_SCALE_ONLY");
 $readmemh("source0.mem",sources,0,N-1);$readmemh("source1.mem",sources,N,2*N-1);
 $readmemh("expected0.mem",goldens,0,N-1);$readmemh("expected1.mem",goldens,N,2*N-1);
 $readmemh("masks0.mem",masks,0,N-1);$readmemh("masks1.mem",masks,N,2*N-1);
 $readmemh("sourcecrc0.mem",source_crcs,0,0);$readmemh("sourcecrc1.mem",source_crcs,1,1);
 $readmemh("crc0.mem",result_crcs,0,0);$readmemh("crc1.mem",result_crcs,1,1);
 for(i=0;i<2*N;i=i+1)begin source_words[i/16][(i%16)*16+:16]=sources[i];result_words[i/16][(i%16)*16+:16]=goldens[i];end
 events=$fopen("events.csv","w");frames_csv=$fopen("frames.csv","w");scans_csv=$fopen("scans.csv","w");
 $fdisplay(events,"event,phase,frame_id,physical_bank,time_ps");
 clear_scoreboard();reset_domains(1);inject_display_stall=1;telemetry_param_id=TAG_A;
 send_arm(TICKET_A,NONCE_A);
 @(negedge core_clk);ticks=0;video_window=1;capture_admit=1;scan_enable=1;
 send_frames(1);
 wait(bad_done_count==1 && pending_abort_edges==1);
 if(publications[0]!=1 || commits[0]!=1 || releases[0]!=1 || fault_ar_hold_count==0)
  $fatal(1,"FAULT_NOT_AFTER_REAL_RESULT_PUBLICATION");
 video_window=0;
 wait(host_acks==1);telemetry_barrier(24);
 // No normal wait_drain here: bad lease, held AR and reader ownership are
 // intentionally quarantined until common reset, not released as success.
 repeat(SIM_HT*SIM_VT)@(negedge pix_out_clk);
 if(host_signatures!=0 || bad_done_count!=1 || pending_abort_edges!=1 ||
    unique_total!=0 || scan_good_frames!=0 || presented_frames!=0 || !failed ||
    fault_hold_output_cycles<SIM_HT*SIM_VT || dut.telemetry.link.observer.capture.active ||
    dut.telemetry.link.mailbox_request!=dut.telemetry.link.mailbox_ack)
  $fatal(1,"FAULT_OBSERVATION_INCOMPLETE");
 $fdisplay(telemetry_log,"FAULT_CLOSED %0d %0d %0d %0d",bad_done_count,pending_abort_edges,fault_preconditions,fault_ar_hold_count);$fflush(telemetry_log);
 // The wire is fully drained before this common-reset protocol barrier.
 reset_domains(2);inject_display_stall=0;telemetry_param_id=TAG_B;
 if(dut.output_video.failed || underflows || failed || dut.telemetry.transmitter.busy ||
    dut.telemetry.link.mailbox_request!=dut.telemetry.link.mailbox_ack || rleft || wleft)
  $fatal(1,"COMMON_RESET_DID_NOT_CLEAR_DOMAINS");
 $fdisplay(telemetry_log,"RESET_BARRIER");$fflush(telemetry_log);
 send_arm(TICKET_B,NONCE_B);
 @(negedge core_clk);ticks=0;video_window=1;capture_admit=1;scan_enable=1;
 send_frames(1);wait(unique_total==1);wait_drain();video_window=0;
 if(commit_total!=1 || release_total!=1 || publish_total!=1 || scan_count!=N ||
    input_pixels[0]!=N || source_written[0]!=FB || result_written[0]!=FB ||
    scan_pixels[0]!=N || scan_good_frames!=1 || scan_repeat_frames!=0 || presented_frames!=1 ||
    underflows || mismatches || failed || dut.input_link.dropped_frames ||
    dut.input_link.overflow_frames || dut.input_link.no_free_frames ||
    dut.telemetry.signature_dropped!=0)
  $fatal(1,"RECOVERY_FULL_CORRECTED_FRAME_OR_OWNERSHIP");
 telemetry_barrier(176);
 if(host_acks!=2 || host_signatures!=1)$fatal(1,"FINAL_WIRE_ACCOUNTING");
 $fdisplay(telemetry_log,"COMPLETE_FAULT_RECOVERY");$fflush(telemetry_log);$fclose(telemetry_log);
 summary=$fopen("summary.json","w");
 $fdisplay(summary,"{\"passed\":true,\"expected_underflows\":1,\"bad_done\":%0d,\"pending_abort_edges\":%0d,\"fault_preconditions\":%0d,\"fault_hold_cycles\":%0d,\"recovery_pixels\":%0d,\"recovery_good\":%0d,\"recovery_crc565\":\"%08x\",\"wire_bytes\":%0d,\"acks\":%0d,\"signatures\":%0d,\"recovery_underflows\":%0d,\"physical_DDR\":false}",bad_done_count,pending_abort_edges,fault_preconditions,fault_ar_hold_count,scan_count,scan_good_frames,pix_done_crc,telemetry_byte_count,host_acks,host_signatures,underflows);
 $fclose(summary);$display("PASS FAULT_RECOVERY_REAL_SYSTEM");$fflush();$finish;
end
