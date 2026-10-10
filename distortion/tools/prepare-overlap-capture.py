"""Prepare isolated four-bank capture/remap overlap and independent video test."""
from pathlib import Path
import json, re, shutil
root=Path(__file__).resolve().parents[1]
def save(rel,text):
    p=root/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text,encoding='utf-8')
def replace(text,old,new):
    assert text.count(old)==1,(old,text.count(old))
    return text.replace(old,new)

video=(root/'rtl/experimental/ddr_early_video.v').read_text()
video=video.replace('ddr_early_video','ddr_overlap_video')
video=replace(video,'parameter WIDTH=640,HEIGHT=480,BANK_STRIDE=262144,MAX_RADIUS_Q22=0,',
    'parameter WIDTH=640,HEIGHT=480,BANK_STRIDE=262144,MAX_RADIUS_Q22=0,CAPTURE_OVERLAP=1,')
video=replace(video,'output reg [31:0] captured_frames,ownership_errors,',
    'output reg [31:0] capture_overlap_cycles,last_capture_cycles,source_bank_wait_cycles,\n    output reg [31:0] captured_frames,ownership_errors,')
video=replace(video,'reg source_pending,processing,engine_start;',
    'reg source_pending,processing,engine_start;\n    reg capture_bank,pending_source_bank,processing_source_bank;\n    reg [31:0] processing_id,capture_cycles;')
video=replace(video,'wire [27:0] write_base=0;','wire [27:0] write_base=capture_bank ? BANK_STRIDE:0;')
video=replace(video,'wire [27:0] result_base=write_bank ? 2*BANK_STRIDE:BANK_STRIDE;',
    'wire [27:0] result_base=write_bank ? 3*BANK_STRIDE:2*BANK_STRIDE;\n    wire [27:0] processing_source_base=processing_source_bank ? BANK_STRIDE:0;')
video=replace(video,'.source_base(28\'b0),.output_base(result_base),.frame_id(source_id),',
    '.source_base(processing_source_base),.output_base(result_base),.frame_id(processing_id),')
video=replace(video,'restart_wait<=0;captured_frames<=0;ownership_errors<=0;ownership_failed<=0;latest_source_checksum<=0;',
    'restart_wait<=0;captured_frames<=0;ownership_errors<=0;ownership_failed<=0;latest_source_checksum<=0;\n            capture_bank<=0;pending_source_bank<=0;processing_source_bank<=0;processing_id<=0;capture_cycles<=0;\n            capture_overlap_cycles<=0;last_capture_cycles<=0;source_bank_wait_cycles<=0;')
video=replace(video,'if(ready && !capture_active && !source_pending && !processing && !failed) begin',
    '''if(capture_active) capture_cycles<=capture_cycles+1'b1;
            if(capture_active && processing) capture_overlap_cycles<=capture_overlap_cycles+1'b1;
            if(!capture_active && (source_pending || (processing && capture_bank==processing_source_bank)))
                source_bank_wait_cycles<=source_bank_wait_cycles+1'b1;
            if(ready && !capture_active && !source_pending &&
               (!processing || (CAPTURE_OVERLAP && capture_bank!=processing_source_bank)) && !failed) begin''')
video=replace(video,'if(restart_wait==64) begin capture_active<=1;restart_wait<=0;end',
    'if(restart_wait==64) begin capture_active<=1;restart_wait<=0;capture_cycles<=0;end')
video=replace(video,'source_pending<=1;capture_active<=0;captured_frames<=captured_frames+1\'b1;',
    'source_pending<=1;capture_active<=0;captured_frames<=captured_frames+1\'b1;\n                pending_source_bank<=capture_bank;capture_bank<=!capture_bank;last_capture_cycles<=capture_cycles;')
video=replace(video,'source_pending<=0;processing<=1;engine_start<=1;process_cycles<=0;',
    'source_pending<=0;processing<=1;engine_start<=1;process_cycles<=0;\n                processing_source_bank<=pending_source_bank;processing_id<=source_id;')
video=replace(video,'engine_id!=source_id','engine_id!=processing_id')
video=replace(video,'reader_base<=front_bank ? 2*BANK_STRIDE:BANK_STRIDE;',
    'reader_base<=front_bank ? 3*BANK_STRIDE:2*BANK_STRIDE;')
video=replace(video,'(capture_active && (source_pending || processing))',
    '(capture_active && (source_pending || (processing && capture_bank==processing_source_bank))) ||\n               (source_pending && processing && pending_source_bank==processing_source_bank)')
video=video.replace('// Source bank 0 is frozen until the remap engine finishes. Result banks 1/2',
    '// Source banks 0/1 alternate: capture may write only the bank not being read. Result banks 2/3')
save('rtl/experimental/ddr_overlap_video.v',video)

tb=(root/'tests/tb_ddr_early_video.sv').read_text().replace('tb_ddr_early_video','tb_ddr_overlap_video').replace('ddr_early_video','ddr_overlap_video')
tb=replace(tb,'module tb_ddr_overlap_video;','module tb_ddr_overlap_video #(parameter OVERLAP=1);')
tb=replace(tb,'.WIDTH(32),.HEIGHT(16),.BANK_STRIDE(512),','.WIDTH(32),.HEIGHT(16),.BANK_STRIDE(512),.CAPTURE_OVERLAP(OVERLAP),')
tb=replace(tb,'memory[0:191]','memory[0:255]')
tb=replace(tb,'integer active_phase=0,phase_mask=0,verified_pixels=0,committed_frames=0,i;',
    'integer active_phase=0,phase_mask=0,verified_pixels=0,committed_frames=0,i;\n    integer src_index=0,locked_base=0,start_captured,start_processed,bank_mask=0;')
tb=replace(tb,'if(memory[0]===source[0]) active_phase=0;',
    'src_index=(dut.engine_start ? dut.processing_source_bank:dut.pending_source_bank) ? 64:0;\n            if(memory[src_index]===source[0]) active_phase=0;')
tb=tb.replace('memory[0]===source[32]','memory[src_index]===source[32]').replace('memory[0]===source[64]','memory[src_index]===source[64]')
tb=replace(tb,'mode==1 && reading && rbase<32','mode==1 && reading && rbase<128')
tb=replace(tb,'for(i=0;i<32;i=i+1) source_locked[i]=memory[i];',
    'locked_base=dut.processing_source_bank ? 64:0;\n                for(i=0;i<32;i=i+1) source_locked[i]=memory[locked_base+i];')
layout='(awaddr<256 || (awaddr>=512 && awaddr<768) || (awaddr>=1024 && awaddr<1280) || (awaddr>=1536 && awaddr<1792))'
tb=replace(tb,'(awaddr<256 || (awaddr>=512 && awaddr<768) || (awaddr>=1024 && awaddr<1280))',layout)
tb=replace(tb,'(araddr<256 || (araddr>=512 && araddr<768) || (araddr>=1024 && araddr<1280))',layout.replace('awaddr','araddr'))
tb=tb.replace('three banks','four banks')
tb=replace(tb,'if((wbase<32 && dut.processing) || (wbase>=64 && !dut.processing))',
    'if((wbase<128 && (!dut.capture_active || (dut.processing && wbase/64==locked_base/64))) || (wbase>=128 && !dut.processing))')
tb=replace(tb,'if(wbase>=64) begin','if(wbase<128) bank_mask=bank_mask|(1<<(wbase/64));\n                if(wbase>=128) begin')
tb=replace(tb,'if(memory[i]!==source_locked[i])','if(memory[locked_base+i]!==source_locked[i])')
tb=replace(tb,'word_index=(dut.front_bank ? 128:64)', 'word_index=(dut.front_bank ? 192:128)')
tb=replace(tb,'$display("INFO: identity/nonlinear changing source frames, three-bank ownership and HDMI passed");',
    '''if(bank_mask!=3) $fatal(1,"Both camera source banks were not exercised");
        if(OVERLAP && !dut.capture_overlap_cycles) $fatal(1,"No actual capture/remap overlap");
        if(!OVERLAP && dut.capture_overlap_cycles) $fatal(1,"Serial control unexpectedly overlapped");
        start_captured=captured_frames;start_processed=processed_frames;
        repeat(500000) @(negedge core_clk);
        $display("PERF overlap=%0d cycles=500000 captured=%0d processed=%0d overlap_cycles=%0d",OVERLAP,captured_frames-start_captured,processed_frames-start_processed,dut.capture_overlap_cycles);
        $display("INFO: four-bank ownership, actual overlap, independent result/CRC/HDMI passed");''')
tb=tb.replace('PASS early DDR video:', 'PASS overlap DDR video:').replace('changing repeated source bank','alternating source banks with capture/remap overlap')
tb+='\nmodule tb_ddr_overlap_serial; tb_ddr_overlap_video #(.OVERLAP(0)) serial_control(); endmodule\n'
save('tests/tb_ddr_overlap_video.sv',tb)
work=root/'build/overlap_video_sim';work.mkdir(parents=True,exist_ok=True)
for p in (root/'build/early_video_sim').glob('*.mem'):shutil.copy2(p,work/p.name)
runner=(root/'tools/run-early-video-sim.ps1').read_text().replace('early_video_sim','overlap_video_sim').replace('tb_ddr_early_video','tb_ddr_overlap_video').replace("'ddr_early_video'","'ddr_overlap_video'").replace('PASS early DDR video:','PASS overlap DDR video:')
save('tools/run-overlap-video-sim.ps1',runner)
serial=runner.replace('tb_ddr_overlap_video -s tb_ddr_overlap_video','tb_ddr_overlap_serial -s tb_ddr_overlap_serial').replace('tb_ddr_overlap_video -runall -log simulation.log','tb_ddr_overlap_serial -runall -log serial-simulation.log').replace('simulation.log','serial-simulation.log')
serial=serial.replace('serial-serial-simulation.log','serial-simulation.log')
save('tools/run-overlap-serial-sim.ps1',serial)

target='corrected_overlap'
top=(root/'board/corrected_early.v').read_text().replace('corrected_early','corrected_overlap').replace('ddr_early_video','ddr_overlap_video')
top=replace(top,'wire [31:0] corrected_frames,process_cycles,cache_hits,cache_misses,completed_queries,result_crc;',
    '''wire [31:0] corrected_frames,process_cycles,cache_hits,cache_misses,completed_queries,result_crc;
    wire [31:0] capture_overlap_cycles,last_capture_cycles,source_bank_wait_cycles,sensor_period;
    camera_frame_period period_monitor(.clk(core_clk),.rst_n(test_reset_sync[1]),.vsync(!cam_vsync),.last_period(sensor_period));
    reg [127:0] held_capture=0,capture_status=0,report_capture=0;''')
top=replace(top,'.processed_frames(corrected_frames),.last_process_cycles(process_cycles),',
    '.capture_overlap_cycles(capture_overlap_cycles),.last_capture_cycles(last_capture_cycles),.source_bank_wait_cycles(source_bank_wait_cycles),\n        .processed_frames(corrected_frames),.last_process_cycles(process_cycles),')
top=replace(top,'pixel_ack_sync<=0;pixel_snapshot_request<=0;held_engine<=0;held_rotation<=0;',
    'pixel_ack_sync<=0;pixel_snapshot_request<=0;held_engine<=0;held_rotation<=0;held_capture<=0;')
top=replace(top,'held_engine<={corrected_frames,process_cycles,cache_hits,cache_misses,result_crc};held_rotation<={rotation_automatic,result_phase};',
    'held_capture<={capture_overlap_cycles,last_capture_cycles,source_bank_wait_cycles,sensor_period};\n                held_engine<={corrected_frames,process_cycles,cache_hits,cache_misses,result_crc};held_rotation<={rotation_automatic,result_phase};')
top=replace(top,'rotation_status<=held_rotation;', 'rotation_status<=held_rotation;capture_status<=held_capture;')
top=replace(top,'rotation_status<=0;', 'rotation_status<=0;capture_status<=0;')
top=replace(top,'snapshot_request<=0;report_rotation<=0;', 'snapshot_request<=0;report_capture<=0;report_rotation<=0;')
top=replace(top,'report_engine<=engine_status;', 'report_capture<=capture_status;report_engine<=engine_status;')
top=replace(top,'reg [7:0] report_index;', 'reg [8:0] report_index;')
top=replace(top,'input [7:0] idx;', 'input [8:0] idx;')
chars=[];idx=244
for field,hi in (('OC',127),('CC',95),('BW',63),('SP',31)):
    for char in ' '+field+'=':
        chars.append(f'                {idx}:message="{char}";');idx+=1
    for nibble in range(8):
        n=hi-nibble*4;chars.append(f'                {idx}:message=hexchar(report_capture[{n}:{n-3}]);');idx+=1
chars.append(f'                {idx}:message=13;{idx+1}:message=10;')
top=replace(top,'                244:message=13;245:message=10;', '\n'.join(chars))
top=replace(top,'report_index==245',f'report_index=={idx+1}')
save(f'board/{target}.v',top)
tcl=(root/'board/build-corrected_early.tcl').read_text().replace('corrected_early',target).replace('/ddr_early_video.v}','/ddr_overlap_video.v}')
tcl=tcl.replace('add_design {D:/English/FPGA/distortion/rtl/dvp_monitor.v}', 'add_design {D:/English/FPGA/distortion/rtl/dvp_monitor.v}\nadd_design {D:/English/FPGA/distortion/rtl/camera_frame_period.v}')
save(f'board/build-{target}.tcl',tcl)
for suffix in ('.fdc','-pins.json'):shutil.copy2(root/'board'/('corrected_early'+suffix),root/'board'/(target+suffix))
save(f'board/program-{target}.tcl',(root/'board/program-corrected_early.tcl').read_text().replace('corrected_early',target))
sources=re.findall(r'^add_design \{([^}]+)\}',tcl,re.M)
sources += [str(root/'board'/f'{target}.fdc'),str(root/'board'/f'build-{target}.tcl')]
sources += [str(root/p) for p in ('board/calibration-trial.vh','board/ov5640_commands.vh','board/ms7210_commands.vh','rtl/video_crc32.vh','board/rotation-domain.vh','rtl/cordic-constants.vh')]
save(f'board/{target}-sources.json',json.dumps([str(Path(s).relative_to(root)) for s in sources],indent=2)+'\n')
for name in ('build-pds.ps1','program-heartbeat.ps1','read-telemetry.ps1'):
    p=root/'tools'/name;text=p.read_text(encoding='utf-8-sig')
    text=re.sub(r"(?:@|ValidateSet)\(([^)\n]*'corrected_early'[^)\n]*)\)",lambda m:m[0] if "'corrected_overlap'" in m[0] else m[0][:-1]+",'corrected_overlap')",text)
    p.write_text(text,encoding='utf-8-sig')
print('Prepared isolated four-bank capture/remap overlap and serial control simulation.')
