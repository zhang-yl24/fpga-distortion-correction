"""Record finite measured UART/download evidence without accessing hardware."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib,json,re,shutil,statistics
root=Path(__file__).resolve().parents[1]
lab=root/'results/lab-20261007'
read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest().upper()
now=datetime.now(ZoneInfo('Asia/Shanghai'))
targets=('corrected_video','corrected_fast','corrected_rotate')
transfers={}
for target in targets:
    paths=sorted((root/'build'/target).glob('program-evidence-*/transfer.json'),key=lambda p:p.stat().st_mtime)
    matching=[p for p in paths if read(p)['CheckedOn'].startswith('2026-10-07') and read(p)['Done']]
    assert matching,f'No current transfer: {target}'
    p=matching[-1];transfer=read(p);manifest=read(p.parent/'validated-build.json')
    assert transfer['SHA256']==manifest['SHA256']==sha(Path(manifest['Bitstream']))
    dst=lab/'downloads'/target;dst.mkdir(parents=True,exist_ok=True)
    for src in p.parent.iterdir():
        if src.is_file():shutil.copy2(src,dst/src.name)
    transfers[target]=transfer
baseline=read(lab/'corrected-baseline-check.json');fast=read(lab/'corrected-fast-check.json')
zero=read(lab/'rotation-zero-check.json');auto=read(lab/'rotation-auto-check.json')
assert all(d['passed'] for d in (baseline,fast,zero,auto))
per_angle={}
capture=read(lab/'rotation-auto-telemetry-timed.json')
for sample in capture['Samples']:
    f={k:int(v,16) for k,v in re.findall(r'\b(\w+)=([0-9A-F]+)\b',sample['Line'])}
    angle=round(f['RA']*360/(1<<32))%360
    per_angle.setdefault(angle,[]).append(f['CY'])
per_angle={str(a):{'samples':len(v),'process_ms_min':min(v)/125000,'process_ms_median':statistics.median(v)/125000,'process_ms_max':max(v)/125000} for a,v in sorted(per_angle.items())}
reduction=(1-fast['mean_process_cycles']/baseline['mean_process_cycles'])*100
result={'recorded_at':now.isoformat(),'hardware_accessed_by_recorder':False,'physical_transfers':transfers,
    'baseline':baseline,'cache_optimized':fast,'rotation_zero':zero,'rotation_auto':auto,
    'physical_cycle_reduction_percent':reduction,'rotation_per_angle':per_angle,
    'user_observation':{'corrected_fast_live_image':'User confirmed normal picture and response to hand motion.','KEY0':'User confirmed short-press rotation and long-press automatic demo.'},
    'limits':['Current native input 640x480; optical accuracy and higher resolutions not established.','Temperature is a working internal-reference ADC estimate, not externally calibrated.','Host UART timestamps approximate rates; processing-cycle reduction is not an equal increase in new-frame rate.','Current finite test does not establish long-run reliability or repeated cold-boot stability.'],
    'next_optimization':'Test isolated corrected_early last-line completion; current packer waits for the next VSYNC and capture reset misses that frame boundary. Larger-angle DDR locality remains a separate bottleneck.'}
for label,file in (('rotation_stability','rotation-stability-check.json'),('rotation_extended_interrupted_for_cooling','rotation-extended-partial-check.json'),('cooling_policy','cooling-policy.json'),('cooling_restart','cooling-restart-check.json'),('automatic_idle_transfer','cooling-restart-idle.json')):
    if (lab/file).exists():result[label]=read(lab/file)
if (lab/'adaptive-native-check.json').exists():
    result['adaptive_native_simulation']=read(lab/'adaptive-native-check.json')
if (lab/'adaptive-twelve-native-check.json').exists():
    check=read(lab/'adaptive-twelve-native-check.json');assert check['passed']
    result['adaptive_twelve_angle_native_simulation']=check
if (lab/'camera-cadence-simulation-check.json').exists():
    check=read(lab/'camera-cadence-simulation-check.json');assert check['passed']
    result['camera_cadence_simulation']=check
    result['camera_cadence_candidate']=read(lab/'camera-cadence-candidate.json')
if (lab/'physical-rotation-comparison.json').exists():
    result['physical_rotation_comparison']=read(lab/'physical-rotation-comparison.json')
if (lab/'rotated-coordinate-error.json').exists():
    audit=read(lab/'rotated-coordinate-error.json');assert audit['passed']
    result['twelve_angle_numerical_audit']=audit
if (lab/'short-burst-native-check.json').exists():
    experiment=read(lab/'short-burst-native-check.json');assert experiment['passed']
    result['short_burst_native_simulation']=experiment
if (lab/'paired-cache-native-check.json').exists():
    experiment=read(lab/'paired-cache-native-check.json');assert experiment['passed']
    result['paired_cache_native_simulation']=experiment
if (lab/'pipeline-hit-native-check.json').exists():
    experiment=read(lab/'pipeline-hit-native-check.json');assert experiment['passed']
    result['pipeline_hit_native_simulation']=experiment
if (lab/'pipeline-twelve-native-check.json').exists():
    experiment=read(lab/'pipeline-twelve-native-check.json');assert experiment['passed']
    result['pipeline_twelve_native_simulation']=experiment
if (lab/'brown-bounded-minimax-candidate.json').exists():
    result['bounded_model_candidate']=read(lab/'brown-bounded-minimax-candidate.json')
if (lab/'throughput-budget.json').exists():
    result['higher_resolution_requirements']=read(lab/'throughput-budget.json')
if (lab/'host-control-simulation-check.json').exists():
    check=read(lab/'host-control-simulation-check.json');assert check['passed']
    result['host_control_simulation']=check
for key,name in [('host_client','host-client-check.json'),('host_angle_native_simulation','host-angle-native-check.json'),('adaptive_gamma_simulation','adaptive-gamma-simulation-check.json'),('gamma_tagged_simulation','gamma-tagged-simulation-check.json'),('gamma_frame_simulation','gamma-frame-simulation-check.json'),('gamma_native_simulation','gamma-native-simulation-check.json'),('gamma_tone_simulation','gamma-tone-simulation-check.json'),('gamma_video_bypass_simulation','gamma-video-simulation-check.json')]:
    if (lab/name).exists():
        check=read(lab/name);assert check['passed'];result[key]=check
result['competition_requirements']=read(lab/'competition-requirements.json')
if (lab/'host-cadence-auto-check.json').exists():
    check=read(lab/'host-cadence-auto-check.json');assert check['passed']
    result['physical_host_cadence_auto']=check
if (lab/'gamma-mapping-check.json').exists():result['gamma_device_mapping']=read(lab/'gamma-mapping-check.json')
for key,name in (('gamma_frozen_capture_simulation','gamma-frozen-capture-simulation-check.json'),('gamma_frozen_native_simulation','gamma-frozen-native-simulation-check.json')):
    if (lab/name).exists():
        check=read(lab/name);assert check['passed'];result[key]=check
if (lab/'gamma-frozen-native-partial-check.json').exists() and 'gamma_frozen_native_simulation' not in result:
    result['gamma_frozen_native_partial']=read(lab/'gamma-frozen-native-partial-check.json')
for key,name in (('gamma_bright_attempts','gamma-bright-attempts-check.json'),('gamma_bright_source_diagnostic','gamma-bright-source-histogram.json'),('gamma_power_cycle_recovery','gamma-power-cycle-recovery-check.json')):
    if (lab/name).exists():result[key]=read(lab/name)
if (lab/'gamma-power-cycle-observation.json').exists():result['user_observation']['gamma_power_cycle_recovery']=read(lab/'gamma-power-cycle-observation.json')
if (lab/'gamma-physical-check.json').exists():
    check=read(lab/'gamma-physical-check.json');assert check['passed'] and check['wrapper_finished_cleanly']
    result['physical_gamma_angle']=check
    paths=sorted((root/'build/corrected_gamma').glob('program-evidence-*/transfer.json'),key=lambda p:p.stat().st_mtime)
    transfer=read(paths[-1]);manifest=read(paths[-1].parent/'validated-build.json')
    assert transfer['Done'] and transfer['SHA256']==check['bitstream_sha256']==manifest['SHA256']==sha(Path(manifest['Bitstream']))
    dst=lab/'downloads/corrected_gamma';dst.mkdir(parents=True,exist_ok=True)
    for src in paths[-1].parent.iterdir():
        if src.is_file():shutil.copy2(src,dst/src.name)
    result['physical_transfers']['corrected_gamma']=transfer
    if (lab/'gamma-observation.json').exists():result['user_observation']['corrected_gamma_angle']=read(lab/'gamma-observation.json')
    if (lab/'gamma-auto-check.json').exists():
        auto_check=read(lab/'gamma-auto-check.json');assert auto_check['passed'] and auto_check['bitstream_sha256']==check['bitstream_sha256']
        result['physical_gamma_auto']=auto_check
    if (lab/'gamma-auto-observation.json').exists():result['user_observation']['corrected_gamma_auto']=read(lab/'gamma-auto-observation.json')
if (lab/'host-angle-cadence_13_7-check.json').exists():
    check=read(lab/'host-angle-cadence_13_7-check.json');assert check['passed'] and check['wrapper_finished_cleanly']
    result['physical_host_cadence_angle']=check
    paths=sorted((root/'build/corrected_host_cadence').glob('program-evidence-*/transfer.json'),key=lambda p:p.stat().st_mtime)
    transfer=read(paths[-1]);manifest=read(paths[-1].parent/'validated-build.json')
    assert transfer['Done'] and transfer['SHA256']==check['bitstream_sha256']==manifest['SHA256']==sha(Path(manifest['Bitstream']))
    dst=lab/'downloads/corrected_host_cadence';dst.mkdir(parents=True,exist_ok=True)
    for src in paths[-1].parent.iterdir():
        if src.is_file():shutil.copy2(src,dst/src.name)
    result['physical_transfers']['corrected_host_cadence']=transfer
    if (lab/'host-cadence-observation.json').exists():result['user_observation']['corrected_host_cadence']=read(lab/'host-cadence-observation.json')
if (lab/'host-angle-13_7-check.json').exists():
    check=read(lab/'host-angle-13_7-check.json');assert check['passed']
    result['physical_host_angle']=check
    result['physical_host_angles']=[check]
    if (lab/'host-angle-7_5-check.json').exists():
        additional=read(lab/'host-angle-7_5-check.json');assert additional['passed'] and additional['wrapper_finished_cleanly']
        result['physical_host_angles'].append(additional)
    paths=sorted((root/'build/corrected_host').glob('program-evidence-*/transfer.json'),key=lambda p:p.stat().st_mtime)
    transfer=read(paths[-1]);manifest=read(paths[-1].parent/'validated-build.json')
    assert transfer['Done'] and transfer['SHA256']==check['bitstream_sha256']==manifest['SHA256']==sha(Path(manifest['Bitstream']))
    dst=lab/'downloads/corrected_host';dst.mkdir(parents=True,exist_ok=True)
    for src in paths[-1].parent.iterdir():
        if src.is_file():shutil.copy2(src,dst/src.name)
    result['physical_transfers']['corrected_host']=transfer
    if (lab/'host-observation.json').exists():result['user_observation']['corrected_host']=read(lab/'host-observation.json')
if (lab/'optical-pair-check.json').exists():
    check=read(lab/'optical-pair-check.json');assert check['passed']
    result['fresh_physical_pair']=check
    paths=sorted((root/'build/corrected_capture').glob('program-evidence-*/transfer.json'),key=lambda p:p.stat().st_mtime)
    transfer=read(paths[-1]);manifest=read(paths[-1].parent/'validated-build.json')
    assert transfer['Done'] and transfer['SHA256']==check['bitstream_sha256']==manifest['SHA256']==sha(Path(manifest['Bitstream']))
    dst=lab/'downloads/corrected_capture';dst.mkdir(parents=True,exist_ok=True)
    for src in paths[-1].parent.iterdir():
        if src.is_file():shutil.copy2(src,dst/src.name)
    result['physical_transfers']['corrected_capture']=transfer
if (lab/'physical-checkerboard-straightness.json').exists():
    result['limited_physical_straightness']=read(lab/'physical-checkerboard-straightness.json')
extra_pairs=[]
for name in ('optical-left-pair-check.json','optical-left-adjusted-pair-check.json','gamma-bright-source-pair-check.json'):
    if (lab/name).exists():
        check=read(lab/name);assert check['passed']
        extra_pairs.append(check)
if extra_pairs:result['additional_optical_pairs']=extra_pairs
if (lab/'physical-straightness-diagnostic.json').exists():
    result['physical_straightness_diagnostic']=read(lab/'physical-straightness-diagnostic.json')
if (root/'build/cooling_capture_validation/idle-after-capture.json').exists():
    proof=read(root/'build/cooling_capture_validation/idle-after-capture.json');assert proof['Done']
    result['binary_capture_idle_helper_verified']=proof
early=None
if (lab/'early-zero-check.json').exists():
    early=read(lab/'early-zero-check.json');assert early['passed']
    early_transfers=sorted((root/'build/corrected_early').glob('program-evidence-*/transfer.json'),key=lambda p:p.stat().st_mtime)
    assert early_transfers
    transfer=read(early_transfers[-1]);assert transfer['Done'] and transfer['CheckedOn'].startswith('2026-10-07')
    dst=lab/'downloads/corrected_early';dst.mkdir(parents=True,exist_ok=True)
    for src in early_transfers[-1].parent.iterdir():
        if src.is_file():shutil.copy2(src,dst/src.name)
    result['early_zero']=early;result['physical_transfers']['corrected_early']=transfer
    result['new_frame_rate_ratio_early_to_fast']=early['approx_rates_per_second']['CF']/fast['approx_rates_per_second']['CF']
    result['user_observation']['corrected_early_live_image']='User confirmed normal picture and response to hand motion.'
    result['next_optimization']='Early completion did not materially increase measured new-frame rate. Instrument real capture/rearm/processing timings and investigate sensor blanking and source-bank overlap before claiming a throughput improvement.'
    if (lab/'early-auto-check.json').exists():result['early_auto']=read(lab/'early-auto-check.json')
new_checks={}
for target,prefix in (('corrected_overlap','overlap'),('corrected_overlap_route','overlap_route'),('corrected_adaptive','adaptive'),('corrected_adaptive_seed2','adaptive_seed2'),('corrected_pipeline_hit','pipeline_hit'),('corrected_adaptive_cadence','cadence')):
    check_file=lab/(prefix+'-zero-check.json')
    if not check_file.exists():continue
    check=read(check_file);assert check['passed']
    paths=sorted((root/'build'/target).glob('program-evidence-*/transfer.json'),key=lambda p:p.stat().st_mtime)
    assert paths
    transfer=read(paths[-1]);manifest=read(paths[-1].parent/'validated-build.json')
    assert transfer['Done'] and transfer['CheckedOn'].startswith('2026-10-07')
    assert transfer['SHA256']==manifest['SHA256']==sha(Path(manifest['Bitstream']))
    dst=lab/'downloads'/target;dst.mkdir(parents=True,exist_ok=True)
    for src in paths[-1].parent.iterdir():
        if src.is_file():shutil.copy2(src,dst/src.name)
    result['physical_transfers'][target]=transfer;result[prefix+'_zero']=check;new_checks[prefix]=check
    result[prefix+'_new_frame_rate_ratio_to_fast']=check['approx_rates_per_second']['CF']/fast['approx_rates_per_second']['CF']
    auto_path=lab/(prefix+'-auto-check.json')
    if auto_path.exists():result[prefix+'_auto']=read(auto_path)
    observation_path=lab/(prefix+'-observation.json')
    if observation_path.exists():result['user_observation'][target]=read(observation_path)
if new_checks:
    prefix=next(p for p in ('cadence','pipeline_hit','adaptive_seed2','adaptive','overlap_route','overlap') if p in new_checks)
    result['next_optimization']='Compare latest physical remap rate with the measured sensor VSYNC cadence; verify large-angle gain, cold-boot recovery and independent optical test images before raising resolution or adding features.'
if 'physical_gamma_auto' in result:
    result['next_optimization']='Measure matched real strong/low-light tone comparisons, physical camera rotation and hardware end-to-end latency; preserve latest Gamma all-angle release and actual heartbeat idle.'
if (lab/'gamma-pair-analysis-check.json').exists():
    result['tone_pair_analysis_tool']=read(lab/'gamma-pair-analysis-check.json')
(lab/'session.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
status=read(root/'status.json')
all_transfers=[p for p in (root/'build').glob('*/program-evidence-*/transfer.json') if read(p).get('Done') and read(p)['CheckedOn'].startswith('2026-10-07')]
latest_path=max(all_transfers,key=lambda p:read(p)['CheckedOn']);latest=read(latest_path)
if latest['Target']=='heartbeat':
    result['automatic_idle_transfer']=latest
    shutil.copy2(latest_path,lab/'latest-idle.json')
    (lab/'session.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
status['current_sram_target']=latest['Target']
status['current_connection'].update({'checked_on':latest['CheckedOn'],'available_for_testing':True,'session_state':'idle_between_tests' if latest['Target']=='heartbeat' else 'board_connected_user_confirmed_and_programmed','last_programmed_target':latest['Target'],'last_programmed_sha256':latest['SHA256'],'actual_temperature_measured':True,'temperature_measurement_method':'Internal reference ADC only; approximate, no external calibration.','temperature_currently_available':False})
status['latest_lab_session']=str(lab/'session.json')
status['lab_20261007']=result
if 'historical_preintegration_status' not in status:
    status['historical_preintegration_status']={key:status.get(key) for key in
        ('date','not_yet_implemented','next_hardware_requirement','measurement_limits')}
status['date']=now.date().isoformat()
status['not_yet_implemented']=['runtime host parameter control','higher-resolution end-to-end video modes']
status['not_yet_implemented'].append('adaptive tone enhancement integrated with live video')
status['remaining_acceptance']=['independent optical accuracy at edges and multiple poses, MTF50/SFR and end-to-end latency',
    'pipeline final board timing and finite physical performance',
    'higher-camera-cadence exposure checks and integration with host control',
    'host arbitrary-angle physical board integration and optical demonstration',
    'adaptive Gamma full-video integration and independent light-level comparisons',
    'long-run thermal and repeated cold-boot acceptance']
status['next_hardware_requirement']='Adaptive seed2 passed finite zero and all-twelve-angle physical tests. Finish pipeline and cadence final multi-corner timing/source/pin gates, then compare finite physical rates and errors with automatic heartbeat idle. Host control remains an isolated prototype.'
status['measurement_limits']='Continuous 640x480 corrected HDMI and twelve-step rotation physically observed. Adaptive seed2 achieves about 11.41fps across the twelve-angle short test, with maximum processing time about 43.89ms; about 60Hz HDMI includes repeated frames. Isolated pipeline and host-control regressions prove simulation behavior only. Limited center/left optical captures do not establish final optical accuracy. No physical higher-resolution or 30/60fps claim.'
if 'cadence' in new_checks:
    c=new_checks['cadence'];a=result.get('cadence_auto')
    status['next_hardware_requirement']='Cadence candidate passed a finite zero-angle telemetry test. Validate all twelve angles and visual response; host control, pipeline and optical acceptance remain separate.'
    status['measurement_limits']=f"Latest 640x480 cadence zero-angle finite physical telemetry shows about {c['approx_rates_per_second']['CF']:.2f} newly processed fps, sensor period estimates {c['scheduling']['approx_sensor_frame_rate_at_125mhz']:.2f}fps. Twelve-angle rate belongs to its separate test. HDMI about 60Hz contains repeated frames. No physical higher-resolution, 30/60fps, final optical quality or end-to-end latency claim."
    if a:status['measurement_limits']+=f" Separate twelve-angle finite test averages {a['approx_rates_per_second']['CF']:.2f} new fps with zero video errors."
    status['next_hardware_requirement']='Cadence zero and all twelve angles passed finite physical tests. Complete arbitrary host control, pipeline and independent optical acceptance with automatic idle between tests.'
if 'physical_host_angle' in result:
    status['not_yet_implemented'].remove('runtime host parameter control')
    status['measurement_limits']+=f" {len(result['physical_host_angles'])} arbitrary host angles have live controller/new processed-frame acknowledgements on the separate baseline-camera host build; combination with faster camera cadence, physical camera rotation and final optical accuracy require separate acceptance."
if 'physical_host_cadence_angle' in result:
    h=result['physical_host_cadence_angle']
    status['measurement_limits']+=f" The combined host/cadence board also passed a finite {h['angle_deg']:.1f}-degree host-command/new-frame test at about {h['approx_new_frame_rate_fps']:.2f}fps; independent screen observation and twelve-angle combination acceptance remain separate."
    status['next_hardware_requirement']='Confirm combined host/cadence screen response, then accept all angles, physical camera rotation, optical quality and hardware end-to-end latency. Pipeline candidate still requires final routed gates before finite physical testing.'
if 'physical_host_cadence_auto' in result:
    h=result['physical_host_cadence_auto']
    status['next_hardware_requirement']='Combined host/cadence all twelve angles passed finite physical and visual acceptance. Finish Gamma native-tone simulation and complete board routed gates before finite testing; optical quality, camera physical rotation and hardware latency remain separate.'
    status['measurement_limits']+=f" Combined host-started twelve-angle short test about {h['approx_rates_per_second']['CF']:.2f} new fps, zero errors and user-confirmed normal motion/color with no obvious corruption or tearing."
if 'physical_gamma_angle' in result:
    status['not_yet_implemented'].remove('adaptive tone enhancement integrated with live video')
    status['remaining_acceptance']=['independent multi-pose optical accuracy, MTF50/SFR and hardware end-to-end latency',
        'pipeline final routed timing and finite physical performance',
        'real strong/low-light comparisons and physical camera rotation',
        'higher-resolution end-to-end video modes', 'long-run thermal and repeated cold-boot acceptance']
    h=result['physical_gamma_angle']
    status['measurement_limits']+=f" Gamma integrated board passed final 125MHz timing and a finite 13.7-degree physical test at {h['approx_new_frame_rate_fps']:.2f} new fps, live modes 0/1 and zero video errors; user confirmed normal motion/color. This does not establish real low-light optical benefit."
    status['next_hardware_requirement']='Capture matched real light-level comparisons and measure hardware latency; physical camera rotation and final optical/high-resolution acceptance remain. Keep automatic heartbeat idle after finite tests.'
    if 'physical_gamma_auto' in result:
        h=result['physical_gamma_auto']
        status['measurement_limits']+=f" Separate Gamma all-twelve-angle finite telemetry passed at {h['approx_rates_per_second']['CF']:.2f} new fps with zero video errors; screen observation is recorded separately."
status['current_connection']['last_successful_heartbeat_date']=latest['CheckedOn'].split('T')[0] if latest['Target']=='heartbeat' else status['current_connection'].get('last_successful_heartbeat_date')
if (lab/'evening-close-check.json').exists():
    closing=read(lab/'evening-close-check.json')
    if latest['Target']=='heartbeat' and closing['idle_transfer']['CheckedOn']==latest['CheckedOn']:
        assert closing['passed']
        result['evening_close']=closing
        status['current_connection']['available_for_testing']=False
        status['current_connection']['session_state']='idle_ready_for_user_power_off'
        status['lab_20261007']=result
        (lab/'session.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
(root/'status.json').write_text(json.dumps(status,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
note=f'''## 实板进展（{now.isoformat()}）

已在5MHz JTAG实际下载原版、缓存优化版和旋转/测温版，DONE=1，CRC/ID/timeout错误为0。用户确认优化版实时画面、短按旋转和长按自动演示正常。

原版每帧最大处理时间{baseline['max_process_ms']:.3f}ms，缓存优化版{fast['max_process_ms']:.3f}ms；处理周期实测减少约{reduction:.2f}%。新增矫正帧率仍约{fast['approx_rates_per_second']['CF']:.2f}fps，HDMI刷新约{fast['approx_rates_per_second']['PF']:.2f}Hz，二者分别统计。

自动旋转短测记录全部12个30°步进角度，后热身有效区间{auto['span_seconds']:.2f}秒，UF/MF/OW/X全0。内部ADC估计温度{auto['temperature_celsius_range'][0]:.2f}～{auto['temperature_celsius_range'][1]:.2f}℃，读回有效且报警为0；尚未外部校准。90°附近每帧处理约114ms，DDR访问局部性仍需优化。

提前提交采集帧的独立版本 corrected_early 已通过打包和三时钟视频仿真，整板编译进行中，尚未下载或验证新增帧率收益。

证据：results/lab-20261007/session.json，保留原始串口时间戳、下载日志、位流SHA与每角度周期；当前范围640×480，未证明1080p、60fps或最终光学精度。
'''
if new_checks:
    latest_check=new_checks[prefix]
    headline=f"当前已实板验证的最新版本为 {prefix}：640×480、零旋转新增矫正帧约{latest_check['approx_rates_per_second']['CF']:.2f}fps，相机实际帧周期估计约{latest_check['scheduling']['approx_sensor_frame_rate_at_125mhz']:.2f}fps，视频错误计数为0。"
    if prefix+'_auto' in result:
        rotation=result[prefix+'_auto']
        headline+=f"自动旋转短测覆盖{len(rotation['observed_result_angles_deg'])}个角度，平均新增矫正帧约{rotation['approx_rates_per_second']['CF']:.2f}fps。"
    headline+='核心时钟125MHz；HDMI约60Hz包含重复刷新，另行统计。下面原版和早期缓存数据保留作前后对照。\n\n'
    note=note.replace('\n\n已在5MHz', '\n\n'+headline+'已在5MHz',1)
    note=note.replace('新增矫正帧率仍约','早期缓存版本新增矫正帧率约',1)
    note=note.replace('自动旋转短测记录全部12个','早期旋转版本的自动短测记录全部12个',1)
if early:
    note=note.replace('提前提交采集帧的独立版本 corrected_early 已通过打包和三时钟视频仿真，整板编译进行中，尚未下载或验证新增帧率收益。',
        f"提前提交采集帧的独立版本 corrected_early 已完成整板构建并实板下载。用户确认实时画面正常。零角度新增帧率约{early['approx_rates_per_second']['CF']:.2f}fps，相对缓存优化版约{result['new_frame_rate_ratio_early_to_fast']:.2f}倍；视频错误计数为0，未观察到明显帧率提升，继续定位真实采集与重启等待。")
note+='\n用户已加装临时树莓派散热块，实际安装效果尚未外部测温。测试结束默认下载低负载 heartbeat，DDR/矫正/视频输出停止；下一轮重载前至少待机60秒。仅关闭电脑软件不会停止FPGA。当前载入状态以status.json为准。\n'
if 'cooling_restart' in result:
    temperatures=result['cooling_restart']['temperature_celsius_range']
    note+=f"\n自动待机流程已实板验证，结束后 heartbeat 下载 DONE=1。待机后重启短测内部 ADC 估计 {temperatures[0]:.2f}～{temperatures[1]:.2f}℃；此数据不能单独量化散热块效果。\n"
if 'adaptive_native_simulation' in result:
    note+='\n新增自适应分块已通过六角度1,843,200像素及CRC的真实原图仿真：±30°处理周期减少约28.5%，±90°约46.2%，对应DDR源图读取突发减少约86.5%～86.8%；0°/180°沿用逐行路径，周期基本不变。此处为合成DDR暂停条件下的仿真，不替代实板新增帧率。\n'
if 'twelve_angle_numerical_audit' in result:
    audit=result['twelve_angle_numerical_audit'];maximum=max(f['max_coordinate_error_px'] for f in audit['frames'])
    note+=f"\n12个30°步进角度共3,686,400个输出坐标已完成离线核查：在既定径向有效域内，相对拟合鱼眼模型最大数值误差{maximum:.6f}像素；0°整数坐标与已封存参数逐项一致。这是模型数值误差，不能称为实拍光学矫正精度。完整RTL逐像素覆盖另由独立12角度回归证明。\n"
if 'limited_physical_straightness' in result:
    check=result['limited_physical_straightness']
    if check['all_complete_boards_detected']:
        row=check['records'][0]
        note+=f"\n新采集完整棋盘的一组同帧原图与实板矫正图，307,200像素与整数软件参考逐项一致；54个内交点全部检测到。中心姿态直线残差RMS为原图{row['raw']['line_residual_rms_px']:.3f}像素、矫正图{row['corrected']['line_residual_rms_px']:.3f}像素。它只是一组有限画质核查，使用此前的corrected_capture位流，不替代新视频版、边缘/多姿态/跨镜头的最终验收。原采集脚本自动待机曾失败；像素文件经重新核验，随后实际恢复heartbeat，并单独实测修复后的待机辅助程序成功。\n"
for prefix,check in new_checks.items():
    note+=f"\n{prefix} 实板零旋转短测：新增矫正帧约{check['approx_rates_per_second']['CF']:.2f}fps，相机帧周期估计约{check['scheduling']['approx_sensor_frame_rate_at_125mhz']:.2f}fps，视频错误计数0；原始串口与待机下载证据已保存。\n"
    if prefix+'_auto' in result:
        rotation=result[prefix+'_auto']
        note+=f"\n{prefix} 自动旋转实板短测覆盖{len(rotation['observed_result_angles_deg'])}个角度，新增矫正帧约{rotation['approx_rates_per_second']['CF']:.2f}fps，视频错误计数0；内部ADC估计温度{rotation['temperature_celsius_range'][0]:.2f}～{rotation['temperature_celsius_range'][1]:.2f}℃。\n"
if 'adaptive_twelve_angle_native_simulation' in result:
    note+='\n自适应分块的完整RTL逐像素回归已扩展到12个30°步进角度，共3,686,400像素全部匹配整数软件参考及CRC；包含合成DDR暂停、帧参数锁定和源图不变性检查。这是RTL数值正确性证据，不能替代光学精度或新整板版本的实际画面验证。\n'
if 'camera_cadence_simulation' in result:
    candidate=result['camera_cadence_candidate']
    note+=f"\n相机时序独立候选理论约{candidate['candidate_predicted_fps']:.2f}fps，抗频闪参数同步调整，并已通过SCCB写入/读回及错误PLL分频拒绝仿真；原基线相机表保持不变。该理论值与新增矫正帧率分别统计，实际数据以对应物理测试结果为准。\n"
if 'physical_straightness_diagnostic' in result:
    note+='\n边缘画质补测：两次左侧采集均有307,200像素与软件参考完全匹配，且自动待机成功。第一次棋盘被裁切，不计直线残差；调整后完整54个角点可见，原图直线残差RMS约0.147px、实板重采样图约0.159px，尚无改善。增加了直接变换原图角点的独立诊断以区分模型与重采样/定位影响，最终光学精度仍未验收，不以中心姿态结果代替边缘结论。\n'
if 'paired_cache_native_simulation' in result:
    note+='\n独立成对邻点缓存实验：六角度1,843,200像素与CRC一致；相对前一个8拍短突发实验，处理周期减少约20%～32%。2,322个四邻点/RGB查询及异常协议检查通过，相机/DDR/HDMI三时钟混合8/16拍仲裁、源/result bank所有权、CRC发布和复位恢复仿真通过。未启动此版本的整板构建，时序、真实控制器兼容性及实测收益仍待验证。\n'
if 'pipeline_hit_native_simulation' in result:
    experiment=result['pipeline_hit_native_simulation']
    savings=[f['cycle_reduction_from_paired_percent'] for f in experiment['frames']]
    note+=f"\n缓存命中流水原型：六角度1,843,200像素与CRC一致，相对成对邻点版本的整帧处理周期减少约{min(savings):.1f}%～{max(savings):.1f}%。热缓存测试连续64周期每周期接收1个四邻点查询；2,322个查询/故障和三时钟视频回归通过。四个同步读副本逻辑数据容量32KiB，串行回退缓存另8KiB。整板映射资源见pipeline-mapping-check.json，完整布线仍在运行；尚未证明最终时序、实际帧率或温度。\n"
if 'pipeline_twelve_native_simulation' in result:
    note+='\n命中流水原型已进一步通过12个30°步进角度完整RTL回归，共3,686,400像素、全部DDR写拍和CRC一致，源帧不变性、参数锁定及同bank重新采集检查通过。尚未进行该版本的实板性能验证。\n'
if 'bounded_model_candidate' in result:
    candidate=result['bounded_model_candidate']
    note+=f"\n保留现有标定、径向边界和三级多项式结构，另拟合了一组独立系数候选。12角度密集数值检查相对拟合鱼眼模型最大坐标误差由约0.146px降至{candidate['max_coordinate_error_px']:.5f}px；现用板卡参数未修改，候选尚需RTL新向量及实拍验证，不能称为光学精度提升。\n"
if 'higher_resolution_requirements' in result:
    note+='\n高分辨率预算已单独计算：125MHz核心实现1080p30需要平均不超过约2.01周期/像素；8位DVP传输RGB565最低需124.416MHz字节时钟，尚不含消隐。当前VGA实验、48MHz相机输入约束及1MiB帧间隔均不能直接证明1080p30，需要并行采样流水线、新相机模式、帧存储布局与完整时序验收。详细要求保存在throughput-budget.json，均为目标预算。\n'
if 'host_angle_native_simulation' in result:
    note+=f"\n任意角度开发：UART协议与原子CORDIC参数更新仿真通过；上位机工具的{result['host_client']['tests_passed']}项测试覆盖固件能力检查、坏包/重复处理、发送一次、完成帧回报和异常后待机调用（硬件/待机调用在测试中为模拟）。6个非步进角度整帧回归共1,843,200像素和全部CRC匹配。电脑控制的实板结果另列。\n"
if 'adaptive_gamma_simulation' in result:
    note+='\n光照增强独立模块回归：RGB565恒等/提亮/压暗曲线196,608种像素输出校验通过；帧统计、两帧一致决策、帧锁定、掩码、暂停与异常帧/复位测试通过。完整视频集成与实板结果单列，真实光照画质收益仍需对照测量。\n'
if 'gamma_device_mapping' in result:
    resources=result['gamma_device_mapping']['mapped_resources']
    note+=f"\n光照增强模块独立PDS器件映射通过：LUT {resources['LUT']['used']}，寄存器{resources['FF']['used']}，DSP/DRM均为0。尚未证明集成后的125MHz时序与资源。\n"
if 'physical_host_angle' in result:
    h=result['physical_host_angle']
    note+=f"\n上位机任意角度首次实板验证：电脑经CP2102只发送一次角度命令，控制器序号及新增完成帧角度均读回一致，角度约{h['angle_deg']:.3f}°。有限观察中的视频错误为0，测试后实际返回heartbeat。屏幕效果按独立用户观察记录；一个角度不代表全角度或物理相机旋转验收。\n"
    note+='首次13.7°测试在已经成功回待机后发生日志包装异常，原始记录与异常日志保留；修复后另做7.5°实板测试，命令、新完成帧、有限观察及待机收尾全部成功，包装程序退出码0。两次测试均使用原相机时序的host位流。\n' if len(result['physical_host_angles'])>1 else ''
if 'physical_host_cadence_angle' in result:
    h=result['physical_host_cadence_angle']
    note+=f"\n提速相机与任意角度控制组合版已完成125MHz多角时序、130管脚与源码/位流检查；13.7°有限实板控制验证约{h['approx_new_frame_rate_fps']:.2f}fps，视频错误0，自动待机成功。此为新增完成帧读回，屏幕观察及组合版全部角度仍需单独验收。\n"
if 'gamma_tagged_simulation' in result:
    note+='\n光照增强标签接口的独立回归通过12完整小帧、3,072像素的光栅/8×8分块遍历，像素、位置标签及显式黑边掩码在暂停和复位后对应；完整DDR/CRC集成结果单列。\n'
if 'physical_host_cadence_auto' in result:
    h=result['physical_host_cadence_auto']
    note+=f"\n组合版电脑启动12角度自动短测通过：平均新增矫正帧{h['approx_rates_per_second']['CF']:.2f}fps，最大处理{h['max_process_ms_at_125mhz']:.2f}ms，视频错误0且自动待机成功。用户确认画面正常、实时变化、颜色正常，无明显花屏或撕裂。\n"
if 'gamma_frame_simulation' in result:
    note+='\nGamma已在隔离副本中接入矫正→增强→DDR写回及增强后CRC：10帧32×32合成图、非零径向/切向参数、多角度、掩码/标签、暂停、全部DDR写拍和CRC一致。完整640×480及三时钟旁路结果单列；尚未实板证明增强效果。\n'
if 'gamma_native_simulation' in result:
    note+='\nGamma整合链路的6任意角度、1,843,200原生像素回归通过，每个像素/显式掩码/DDR写拍/CRC匹配；这组真实相机输入触发恒等模式，不能独自证明原生提亮分支。\n'
if 'gamma_tone_simulation' in result:
    note+='\n另对真实相机像素作合成降亮，3个原生640×480完整帧共921,600像素通过，模式依次0、0、1，最后一帧提亮后DDR像素和CRC一致。它是合成暗场回归，不是物理低光画质测量。\n'
if 'gamma_video_bypass_simulation' in result:
    note+='\nGamma视频副本通过三独立时钟旁路回归：全部显示像素、帧CRC发布、四bank所有权、错误响应隔离和处理中复位恢复。启用增强时的画质与整板时序仍需另外验收。\n'
if 'physical_gamma_angle' in result:
    h=result['physical_gamma_angle'];r=h['mapped_global_resources']
    note+=f"\nGamma增强整板 corrected_gamma 已通过最终125MHz多角时序、130管脚及源码/位流绑定。13.7°实板短测新增帧约{h['approx_new_frame_rate_fps']:.2f}fps，GM读到恒等和提亮，视频错误0，用户确认实时画面/颜色正常。整板LUT {r['LUT']['used']}、FF {r['FF']['used']}、APM {r['APM']['used']}、DRM {r['DRM']['used']}；与组合版相比增加572 LUT、319 FF，APM/DRM不变。\n"
    if 'physical_gamma_auto' in result:
        a=result['physical_gamma_auto']
        note+=f"\nGamma全部12角度有限实板遥测通过：新增矫正帧约{a['approx_rates_per_second']['CF']:.2f}fps，最大处理{a['max_process_ms_at_125mhz']:.2f}ms，视频错误0，增强帧计数持续增加，随后实际回heartbeat。"
        note+='用户确认全部角度正常、实时变化、颜色正常，无明显花屏或撕裂。\n' if 'corrected_gamma_auto' in result['user_observation'] else '本轮独立屏幕观察尚未记录。\n'
    note+='真实强光/暗光画质提升、物理相机旋转、MTF50/SFR及硬件端到端延迟仍需独立验收。\n'
if 'gamma_bright_attempts' in result:
    b=result['gamma_bright_attempts']
    note+='\n今晚两次照亮白纸测试的视频/角度通信正常，用户确认第二轮显示无异常；两轮均仅读到恒等模式，未触发压暗。零角度有限窗口约18.39新增帧/s。保留未触发结果，不作为压暗或强光画质通过证据。后续基线配置采集307,200像素与软件参考匹配，但画面为衣服/背景，不能用其直方图代表白纸场景。\n'
if 'gamma_power_cycle_recovery' in result:
    c=result['gamma_power_cycle_recovery']
    note+=f"\n用户执行一次P-ON重启后，Gamma重新下载恢复成功，33.375°新增帧回报约{c['approx_new_frame_rate_fps']:.2f}fps、视频错误0；用户确认实时画面恢复且无明显异常，随后实际回待机。这是一轮主机重新下载恢复，未证明Flash自主启动或重复冷启动可靠性。\n"
if 'gamma_frozen_capture_simulation' in result:
    c=result['gamma_frozen_capture_simulation']
    note+=f"\n同帧Gamma采集原型通过暗/亮/普通三场景、9个完整UART数据包、{c['pixels_compared']:,}个像素及CRC：原图冻结，两个旁路统计预热，导出增强前图后复用同源帧输出增强图；DDR与UART暂停、源图/导出bank不变性通过。上位机组装器{c['host_parser_tests_passed']}项错误/截断/乱序检查通过。该原型还未部署实板；预热重复的是同一冻结帧，不代表动态场景响应时间。\n"
if 'gamma_frozen_native_simulation' in result:
    c=result['gamma_frozen_native_simulation']
    note+=f"\n同帧采集另完成原生640×480三场景、9数据包、{c['pixels_compared']:,}像素回归；完整原图/旁路/增强输出及CRC匹配。此回归半径guard=0，待构建板级候选使用当前标定有效域边界，需要另行完成对应参数与时序验收。\n"
elif 'gamma_frozen_native_partial' in result:
    c=result['gamma_frozen_native_partial']
    note+=f"\n同帧采集的640×480完整回归尚未结束；仅封存并核对了{c['complete_packets_validated']}个完整前缀数据包、{c['complete_packet_pixels_validated']:,}像素及CRC，其中完整增强前后组为{c['complete_triplets_validated']}组。不将部分进展写作整体验收通过。\n"
path=root/'README.md';text=path.read_text(encoding='utf-8')
start='<!-- CURRENT_LAB_20261007_BEGIN -->';end='<!-- CURRENT_LAB_20261007_END -->'
block=start+'\n'+note+'\n'+end
if start in text:text=re.sub(re.escape(start)+'.*?'+re.escape(end),lambda _:block,text,flags=re.S)
else:text=text.replace('<!-- CURRENT_CORRECTED_PIPELINE_BEGIN -->',block+'\n\n<!-- CURRENT_CORRECTED_PIPELINE_BEGIN -->',1)
path.write_text(text,encoding='utf-8')
(lab/'progress.txt').write_text(note,encoding='utf-8')
files={str(p.relative_to(lab)):sha(p) for p in lab.rglob('*') if p.is_file() and p.name!='files-sha256.json'}
(lab/'files-sha256.json').write_text(json.dumps(files,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'cycle_reduction_percent':reduction,'lab_evidence':str(lab/'session.json'),'rotation_angles':list(per_angle),'current_target':latest['Target']}))
