"""Archive measured evidence; keep simulated and physical claims separate."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib
import json
import re
import shutil
root=Path(__file__).resolve().parents[1]
now=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest().upper()
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
simulation={}
for target in ('corrected_video','corrected_capture'):
    p=root/f'build/{target}_sim/simulation.log'
    log=p.read_text(errors='replace')
    assert re.search(r'^PASS ',log,re.M) and not re.search(r'fatal:|error:',log,re.I)
    simulation[target]={'passed':True,'log':str(p.resolve())}
builds={}
programmed={}
for target in ('corrected_video','corrected_capture'):
    work=root/'build'/target
    manifest=work/'validated-build.json'
    if not manifest.exists():continue
    data=read(manifest);bit=Path(data['Bitstream'])
    timing=Path(data['TimingReport']) if data.get('TimingReport') else work/f'place_route/{target}_timing_summary_after_hold_fix.txt'
    assert digest(bit)==data['SHA256'] and 'All Constraints Met' in timing.read_text()
    summary=timing.read_text()
    builds[target]={'sha256':data['SHA256'],'all_constraints_met':True,'bitstream':str(bit.resolve()),
                    'timing_report':str(timing.resolve())}
    transfers=sorted(work.glob('program-evidence-*/transfer.json'),key=lambda p:p.stat().st_mtime)
    matches=[p for p in transfers if read(p)['SHA256']==data['SHA256'] and read(p)['Done']]
    if matches:programmed[target]={'evidence':str(matches[-1].resolve()),**read(matches[-1])}
pair_file=root/'results/corrected-pair-check-20261006.json'
run_file=root/'results/corrected-video-check-20261006.json'
pairs=read(pair_file) if pair_file.exists() else None
run=read(run_file) if run_file.exists() else None
pair_ok=bool(pairs and pairs['passed'] and 'corrected_capture' in programmed and pairs['bitstream_sha256']==builds['corrected_capture']['sha256'])
run_ok=bool(run and run['passed'] and 'corrected_video' in programmed)
archive=root/'results/verified'/('corrected-pipeline-'+datetime.now(ZoneInfo('Asia/Shanghai')).strftime('%Y%m%d-%H%M%S'))
archive.mkdir(parents=True)
source_files=['rtl/ddr_corrected_video.v','rtl/ddr_corrected_capture.v','board/calibration-trial.vh',
              'tests/tb_ddr_corrected_video.sv','tests/tb_ddr_corrected_capture.sv',
              'tools/prepare-corrected-video.py','tools/prepare-corrected-capture.py','tools/capture-corrected-pairs.py',
              'tools/check-corrected-telemetry.py','tools/check-corrected-capture-sim.py',
              'tools/run-corrected-video-sim.ps1','tools/run-corrected-capture-sim.ps1',
              'tools/build-pds.ps1','tools/program-heartbeat.ps1','tools/read-telemetry.ps1',
              'tools/record-corrected-progress.py']
source_files+=['rtl/'+n+'.v' for n in ('remap_frame_engine','ddr_result_writer','ddr_read_arbiter','ddr_write_arbiter','brown_remap_core','brown_inverse_mapper','mul32_pipe','ddr_remap_sample','ddr_neighbour_cache','bilinear_rgb','ddr_uart_frame','ddr_video_reader','ddr_video_writer','ddr_video_output','camera_live_bridge','video_async_fifo','rgb565_burst_pack','dvp_rgb565_capture')]
source_files+=['rtl/video_crc32.vh','rtl/uart_tx.v','rtl/ov5640_init.v','rtl/reg16_i2c.v','rtl/dvp_monitor.v',
               'board/hdmi_tx_init.v','board/ms7210_commands.vh','board/ov5640_commands.vh','board/bringup_pll.v',
               'platform/video_base/ipcore/ddr3_test/ddr3_test.idf',
               'results/calibration-fpga-candidate-20261006/candidate.json',
               'results/calibration-fpga-candidate-20261006/coordinates-q8.bin']
source_files+=['tools/preview-corrected-hardware.py','board/repair-corrected-video-hold.tcl',
               'board/diagnose-corrected-hold.tcl','board/pds-route-options.tcl',
               'board/finalize-corrected-video.tcl','tools/finalize-corrected-video.py',
               'tools/prepare-corrected-hold-repair.py',
               'rtl/experimental/ddr_neighbour_cache_fast.v','rtl/pixel_inverse_rotation.v',
               'tests/tb_native_remap_regression.sv','tests/tb_pixel_inverse_rotation.sv',
               'tools/prepare-native-regression.py','tools/run-native-regression.ps1',
               'tools/prepare-cache-fast-path.py','tools/record-cache-regression.py',
               'tools/prepare-rotation-test.py','tools/run-rotation-sim.ps1']
for name in ('results/cache-native-regression-20261006.json','results/cache-fast-path-source-20261006.json',
             'build/native_regression_sim/simulation.log','build/native_regression_sim/cycles.csv',
             'build/native_regression_sim/reference.json','build/native_regression_fast_sim/simulation.log',
             'build/native_regression_fast_sim/cycles.csv','build/brown_remap_fast_sim/simulation.log',
             'build/corrected_video_fast_sim/simulation.log',
             'build/rotation_sim/simulation.log','build/rotation_sim/reference.json',
             'build/corrected_video/hold-repair-context.log','build/corrected_video/finalize.log'):
    if (root/name).exists():source_files.append(name)
for name in ('build/corrected_video/failed-first-route/build.log','build/corrected_video/failed-first-route/timing.txt',
             'build/corrected_video/failed-first-route/hold-diagnosis.rtr','build/corrected_video/hold-repair.log',
             'results/corrected-hardware-preview-20261006.png','results/corrected-hardware-preview-20261006.json'):
    if (root/name).exists():source_files.append(name)
for target in ('corrected_video','corrected_capture'):
    source_files+=['board/'+target+'.v','board/'+target+'.fdc','board/'+target+'-pins.json','board/build-'+target+'.tcl','board/program-'+target+'.tcl',f'build/{target}_sim/simulation.log']
    if target in builds:
        source_files+=[f'build/{target}/validated-build.json',f'build/{target}/generate_bitstream/{target}.sbit',f'build/{target}/place_route/{target}_timing_summary_after_hold_fix.txt',f'build/{target}/device_map/{target}.dmr']
        source_files.append(str(Path(builds[target]['timing_report']).relative_to(root)))
    if target in programmed:
        transfer_folder=Path(programmed[target]['evidence']).parent
        source_files+=[str(p.relative_to(root)) for p in transfer_folder.iterdir() if p.is_file()]
for p in (pair_file,run_file,root/'results/corrected-video-telemetry.txt',root/'results/corrected-video-telemetry-timed.json'):
    if p.exists():source_files.append(str(p.relative_to(root)))
hashes={}
for name in dict.fromkeys(source_files):
    p=root/name;dest=archive/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dest)
    assert digest(dest)==digest(p);hashes[name]=digest(p)
record={'recorded_at':now,'simulations':simulation,'builds':builds,'programmed':programmed,
        'same_frame_pixel_hardware_verified':pair_ok,'continuous_corrected_video_hardware_verified':run_ok,
        'pair_check':str(pair_file.resolve()) if pairs else None,'continuous_check':str(run_file.resolve()) if run else None,
        'archive':str(archive.resolve()),'sha256':hashes,
        'scope':'Native 640x480, staged bounded radial approximation, matched source/output K, no rotation. Simulations and finite hardware verification are recorded independently; no claim of final optical accuracy or competition-grade frame rate.'}
(archive/'summary.json').write_text(json.dumps(record,indent=2)+'\n')
(root/'results/corrected-pipeline-progress-20261006.json').write_text(json.dumps(record,indent=2)+'\n')
status=read(root/'status.json')
status['corrected_pipeline']={k:v for k,v in record.items() if k!='sha256'}
if programmed:
    latest=max(programmed.items(),key=lambda kv:kv[1]['CheckedOn'])
    status['current_sram_target']=latest[0]
    status['current_connection']['last_programmed_target']=latest[0]
    status['current_connection']['last_programmed_sha256']=latest[1]['SHA256']
    status['current_connection']['checked_on']=latest[1]['CheckedOn']
    status['current_connection']['over_temp_status_bit']=1
    status['current_connection']['actual_temperature_measured']=False
if pair_ok:
    status['verification']['same_frame_native_corrected_pixels_hardware_verified']=sum(p['pixels_compared'] for p in pairs['pairs'])
    status['real_calibration_hardware_trial_verified']=True
    status['brown_remap_core']['hardware_integrated']=True
    status['brown_remap_core']['hardware_programmed']=True
    status['brown_remap_core']['model']='Bounded native 640x480 fisheye2 radial polynomial surrogate, actual calibration trial, matched K, no rotation'
    status['brown_remap_core']['limits']='Actual same-frame RGB565 pixels matched integer reference in corrected_capture. Exact fisheye/rotation and final optical calibration accuracy remain unverified.'
    status['remap_frame_engine']['hardware_programmed']=True
    status['remap_frame_engine']['physical_evidence']=str(pair_file.resolve())
    for key,value in status.items():
        if isinstance(value,dict) and 'new_correction_hardware_programmed' in value:
            value['new_correction_hardware_programmed']=True
            value['same_frame_native_pixel_evidence']=str(pair_file.resolve())
            value['limits']='Cross-validated captured corners; staged bounded radial approximation matched real FPGA pixels to same-frame integer reference. Matched K, no rotation; no claim of final optical precision, exact fisheye or end-to-end latency.'
    status['measurement_limits']='Actual arithmetic remap, neighbour cache, bilinear and RGB565 result writer verified on 640x480 camera frames against the same-source integer reference. Continuous corrected HDMI remains pending unless corrected_pipeline continuous hardware flag is true. Matched source/output K, bounded radial surrogate, no rotation; no claim of final optical quality or end-to-end latency.'
if run_ok:status['verification']['continuous_corrected_video_hardware_verified']=True
(root/'status.json').write_text(json.dumps(status,indent=2)+'\n')
progress=root/'results/progress-2026-10-06.txt'
lines=[f'{now} 实板矫正链路集成与验证',
       '新增：冻结相机源帧 + 两个交替结果/显示帧；算术坐标核心、双线性插值、DDR 完整突发仲裁、CRC 完成后发布。',
       '端到端仿真通过：独立时钟、恒等/非线性模型、变化源帧、帧区所有权、逐像素 HDMI、DDR 暂停、异常响应隔离、中途复位恢复。',
       '独立导出仿真通过：三组原图/矫正图、UART 暂停、六个完整包；主机核对全部像素、包头/负载/尾部 CRC。',
       f'整板通过全约束与引脚检查：{list(builds)}；已确认 SRAM 下载：{list(programmed)}。',
       f'同帧实板逐像素核对通过：{pair_ok}；连续实板矫正视频验证通过：{run_ok}。',
       '适用范围：640×480、源/输出 K 匹配、无旋转；有界鱼眼模型多项式近似。不是最终光学标定精度证明。',
       'DDR 125MHz、JTAG 5MHz；本轮未降频。',f'证据：{archive.resolve()}。']
if pair_ok:lines.append(f"实板同帧核对：{len(pairs['pairs'])} 组，{sum(p['pixels_compared'] for p in pairs['pairs'])} 像素，差异 0。")
if run_ok:lines.append(f"连续视频：{run['span_seconds']:.2f}s，新增矫正帧 {run['approx_rates_per_second']['CF']}fps，HDMI刷新 {run['approx_rates_per_second']['PF']}fps，处理最大 {run['max_process_ms']:.3f}ms，UF/MF/OW/X 均 0。")
progress.write_text('\n'.join(lines)+'\n\n以下保留此前记录：\n----------------------------------------\n'+progress.read_text(encoding='utf-8'),encoding='utf-8')
readme=root/'README.md'
text=readme.read_text(encoding='utf-8')
start='<!-- CURRENT_CORRECTED_PIPELINE_BEGIN -->';end='<!-- CURRENT_CORRECTED_PIPELINE_END -->'
section=start+'\n## 当前矫正实板状态（'+now+'）\n\n'+('\n'.join(lines[1:]) if pair_ok else '集成仿真已通过；实板验证尚未完成。')+'\n\n'+end+'\n\n'
if start in text:
    lo=text.index(start);hi=text.index(end,lo)+len(end)
    text=text[:lo]+section.rstrip()+text[hi:]
else:text=text.replace('## 已完成与边界',section+'## 已完成与边界（此前阶段记录）',1)
readme.write_text(text,encoding='utf-8')
print(json.dumps({k:v for k,v in record.items() if k!='sha256'},indent=2))
