"""Stage a separate same-source Gamma capture board candidate, never download."""
from pathlib import Path
import hashlib,json,re,shutil
from datetime import datetime
from pds_source_manifest import expand_sources
root=Path(__file__).resolve().parents[1];old='corrected_capture';new='gamma_capture'
text=(root/'board'/f'{old}.v').read_text().replace(f'module {old}(',f'module {new}(')
text=text.replace('ddr_corrected_capture pipeline(', 'gamma_frozen_capture #(.MAX_RADIUS_Q22(ROT_MAX_R2_Q22)) pipeline(')
text=text.replace('    `include "D:/English/FPGA/distortion/board/calibration-trial.vh"','    `include "D:/English/FPGA/distortion/board/calibration-trial.vh"\n    `include "D:/English/FPGA/distortion/board/rotation-domain.vh"')
text=text.replace('ov5640_init #','ov5640_cadence_trial_init #')
text=text.replace('wire store_arm=test_reset_sync[1] && camera_ready_ddr[1];',
    'wire store_arm;\n    capture_warmup sensor_warmup(.clk(core_clk),.rst_n(ddr_reset_sync[1]),.ready(test_reset_sync[1] && camera_ready_ddr[1]),.armed(store_arm));')
(root/'board'/f'{new}.v').write_text(text)
for suffix in ('.fdc','-pins.json'):shutil.copy2(root/'board'/f'{old}{suffix}',root/'board'/f'{new}{suffix}')
fdc=root/'board'/f'{new}.fdc';constraints=fdc.read_text()
# Use the accepted faster-camera PCLK constraint and source-only pin map.
live=(root/'board/corrected_gamma.fdc').read_text()
clock=re.search(r'(?m)^create_clock[^\n]*cam_pclk[^\n]*',live)
assert clock
old_clock=re.search(r'(?m)^create_clock[^\n]*cam_pclk[^\n]*',constraints);assert old_clock
constraints=constraints[:old_clock.start()]+clock[0]+constraints[old_clock.end():];fdc.write_text(constraints)
common=['ddr_uart_frame','rgb565_burst_pack','video_async_fifo','camera_live_bridge','ddr_video_writer','camera_preview','dvp_rgb565_capture','dvp_monitor','reg16_i2c','uart_tx','video_pattern','mul32_pipe','ddr_remap_sample','bilinear_rgb','pixel_inverse_rotation','bounded_brown_inverse_mapper']
experimental=['capture_warmup','gamma_frozen_capture','adaptive_gamma_frame_engine','rotated_remap_core_gamma','ddr_adaptive_result_writer','ddr_adaptive_cache','adaptive_gamma_stream','adaptive_gamma_tagged','ov5640_cadence_trial_init']
paths=[f'rtl/{name}.v' for name in common]+[f'rtl/experimental/{name}.v' for name in experimental]+['platform/video_base/ipcore/ddr3_test/ddr3_test.idf','board/hdmi_tx_init.v',f'board/{new}.v','board/bringup_pll.v']
tail=(root/'board'/f'build-{old}.tcl').read_text();tail=tail[tail.index('add_constraint '):].replace(old,new)
tail=tail.replace('pnr\n','pnr -optimize_multi_corner_timing -fix_hold_violation -fix_hold_violation_iterations 50 -fix_hold_violation_threshold 100 -fix_hold_violation_in_route TRUE\n')
(root/'board'/f'build-{new}.tcl').write_text(''.join(f'add_design {{D:/English/FPGA/distortion/{path}}}\n' for path in paths)+tail)
(root/'board'/f'program-{new}.tcl').write_text((root/'board'/f'program-{old}.tcl').read_text().replace(old,new))
paths += [f'board/{new}.fdc',f'board/build-{new}.tcl',f'board/{new}-pins.json','board/calibration-trial.vh','board/rotation-domain.vh','board/ov5640_cadence_trial_commands.vh','board/ms7210_commands.vh','rtl/experimental/gamma_curves.vh','rtl/video_crc32.vh']
assert all((root/path).is_file() for path in paths)
paths=expand_sources(root,paths)+[f'board/{new}-sources.json']
(root/'board'/f'{new}-sources.json').write_text(json.dumps(paths,indent=2)+'\n')
proof={'target':new,'hardware_accessed':False,'build_started':False,'source_sha256':{path:hashlib.sha256((root/path).read_bytes()).hexdigest().upper() for path in paths},
    'source_protocol':'One immutable raw input, two bypass warmup passes, raw/bypass UART export, third enabled Gamma pass and tone-mode-labelled UART result',
    'native_size':[640,480],'bound':1976439,'limits':'Newly staged, unbuilt board candidate. Requires completed bounded native regression plus final timing, pin and complete synthesis source hash gates before physical capture. The generic hardware helper enforces these gates.'}
lab=root/'results'/('lab-'+datetime.now().strftime('%Y%m%d'));lab.mkdir(exist_ok=True)
(lab/'gamma-capture-board-candidate.json').write_text(json.dumps(proof,indent=2)+'\n')
print('Prepared isolated gamma_capture board candidate; no build or hardware access.')
