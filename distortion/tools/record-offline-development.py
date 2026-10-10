"""Save verified offline progress and the exact handoff to the next lab session."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib
import json
import re
import shutil

root = Path(__file__).resolve().parents[1]
now = datetime.now(ZoneInfo('Asia/Shanghai')).isoformat()
def read(path): return json.loads(path.read_text(encoding='utf-8-sig'))
manifest_path = root / 'build/corrected_video/validated-build.json'
manifest = read(manifest_path)
bit = Path(manifest['Bitstream'])
assert hashlib.sha256(bit.read_bytes()).hexdigest().upper() == manifest['SHA256']
report = Path(manifest['TimingReport'])
text = report.read_text()
assert hashlib.sha256(report.read_bytes()).hexdigest().upper() == manifest['TimingSHA256']
assert 'Design Summary : All Constraints Met.' in text
cache = read(root / 'results/cache-native-regression-20261006.json')
rotation = read(root / 'build/rotation_sim/reference.json')
assert 'PASS inverse rotation:' in (root / 'build/rotation_sim/simulation.log').read_text()
assert 'PASS corrected DDR video:' in (root / 'build/corrected_video_fast_sim/simulation.log').read_text()
kit = root / 'results/ready-for-lab/20261006-corrected-video'
kit.mkdir(parents=True, exist_ok=True)
copied = {}
for src in (bit, report, manifest_path, root / 'board/corrected_video-pins.json'):
    dst = kit / src.name
    shutil.copyfile(src, dst)
    digest = hashlib.sha256(src.read_bytes()).hexdigest().upper()
    assert digest == hashlib.sha256(dst.read_bytes()).hexdigest().upper()
    copied[dst.name] = digest
handoff = {
    'recorded_at': now, 'hardware_accessed': False,
    'target': 'corrected_video', 'device': 'PG2L100H-6IFBG676', 'ddr_mhz': 125, 'jtag_mhz': 5,
    'bitstream_sha256': manifest['SHA256'], 'files': copied,
    'timing': {'all_constraints_met': True, 'core_slow_setup_wns_ns': .766, 'core_fast_hold_whs_ns': .103,
               'phy1_to_core_fast_hold_whs_ns': .175, 'lowest_fast_hold_whs_ns': .102, 'pins_verified': 128},
    'preflight_without_board': 'powershell -NoProfile -ExecutionPolicy Bypass -File tools/program-heartbeat.ps1 -Target corrected_video -ValidateOnly',
    'next_lab': ['先安装适配散热片、改善通风并取得温度读数，再进行短时运行。',
                 '在 D:/English/FPGA/distortion 重新执行离线下载前校验，再连接开发板，以 5MHz 下载 corrected_video。',
                 '核对实时矫正画面与错误计数，测量有效新增矫正帧率和延迟；当前包未实板验证。'],
    'included_features': 'Continuous native correction display with the original cache, calibrated bounded radial approximation and no rotation.',
    'not_included_yet': 'Adjacent-beat cache optimization and inverse-rotation prototype are separately simulation-verified; physical timing and board integration remain future work.',
}
(kit / 'handoff.json').write_text(json.dumps(handoff, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
adc_doc = next((root.parent / 'vendor/board').rglob('UG040009*V1.3.pdf'))
thermal = {
    'source': str(adc_doc.resolve()), 'source_sha256': hashlib.sha256(adc_doc.read_bytes()).hexdigest(),
    'document': 'Logos2 ADC User Guide V1.3, printed pp.8,17,24',
    'actual_temperature_measured': False,
    'readback_plan': '先配置温度通道采样。APB DEN 至少提前 SECEN 两个 DCLK 周期；等待 DRDY 后读取地址 0x40 的温度转换结果，并降低 SECEN。JTAG 与 APB 不同时操作 ADC。加入超时和样本时间戳；零初始化寄存器不能当作已完成的测温。',
    'code12_conversion': 'temperature_celsius = extracted_code12 * 0.1219 - 273.15',
    'host_decoder': str(root / 'tools/decode-logos2-temperature.py'),
    'limits': 'ADC primitive/controller and telemetry are not integrated or tested yet. The 12-bit extraction layout must be checked against the native register figure before integration. over_temp alone gives no numeric temperature.',
}
(root / 'results/temperature-monitor-plan-20261006.json').write_text(json.dumps(thermal, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
progress = {
    'recorded_at': now, 'hardware_accessed': False,
    'continuous_display_build': handoff,
    'real_frame_rtl_regression': {'pixels_per_variant': 614400, 'baseline_passed': True, 'candidate_passed': True},
    'cache_candidate': {'cycle_reduction_percent': cache['mean_cycle_reduction_percent'], 'fault_and_border_queries': 19086,
                        'complete_video_pipeline_simulation_passed': True, 'video_simulation_dimensions': [32,16],
                        'integrated_in_board_bitstream': False, 'report': str(root / 'results/cache-native-regression-20261006.json')},
    'rotation_prototype': {**rotation, 'simulation_passed': True, 'integrated_in_board_bitstream': False},
    'thermal_monitor_plan': str(root / 'results/temperature-monitor-plan-20261006.json'),
    'remaining': ['快缓存候选已通过完整视频仿真，下一步验证整板综合/布局布线资源与时序，再接板对比真实帧率。',
                  '组合旋转与相机投影，加入超出当前有效标定半径的处理；验证单次插值与帧参数切换。',
                  '开发 ADC 原语/控制器读回及 UART 温度状态；下次接板做实际测温、连续画面、帧率和延迟验证。'],
}
out = root / 'results/offline-development-20261006.json'
out.write_text(json.dumps(progress, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
status_path = root / 'status.json'
status = read(status_path)
status['offline_development'] = progress
status['current_sram_target'] = None
status['current_connection']['available_for_testing'] = False
status['current_connection']['session_state'] = 'offline_no_board_user_confirmed'
status['corrected_video_timing_repair'] = {**handoff['timing'], 'downloaded': False, 'bitstream_sha256': manifest['SHA256'], 'report': str(report)}
status_path.write_text(json.dumps(status, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
plan_path = root / 'results/offline-plan-20261006.json'
plan = read(plan_path)
plan['latest_progress'] = str(out)
plan['offline_priorities'][0]['current_state'] = '最终路由数据库的慢角/快角全部约束通过，128 引脚及位流校验通过；无降频、未访问开发板。已修复工程上下文和误读中间时序摘要的问题。'
plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
note = f'''\n## 今晚离线开发检查点（{now}）\n\n连续 HDMI 矫正版已生成位流，最终路由数据库全部时序通过：DDR 125MHz，核心慢角建立余量 0.766ns，核心快角保持余量 0.103ns，128 引脚核对通过。板上验证待下次实验室进行。PDS 增量脚本现显式恢复器件和约束，验收/下载前检查最终数据库报告与 SHA256；中间的 after_hold_fix 摘要不代表最后一次修复后的结果。\n\n两组真实图像的完整 RTL 回归通过，共 614400 像素。独立快缓存候选每帧周期由约 551 万降至 381 万，下降 {cache['mean_cycle_reduction_percent']:.2f}%；两组输出逐像素和 CRC 不变，19086 条边界/故障向量通过。这是合成 DDR 暂停模型下的仿真周期，未测实板帧率，也未编入连续显示版。\n\n旋转坐标原型通过 12 个角度及溢出测试，共 13312 条独立整数向量；支持每周期一条坐标、背压、参数排空和复位。尚未组合到整板相机投影，最终旋转光学效果待验证。温度监测的官方资料与读回方案已保存，目前无实际温度值。\n\n详细结果见 results/offline-development-20261006.json；下次接板包见 results/ready-for-lab/20261006-corrected-video/handoff.json。\n'''
note += '\n快缓存候选还通过了完整采集/矫正/HDMI 链路仿真（链路仿真为32x16；原生640x480在帧引擎回归中验证）。覆盖检查现等待实际显示像素数达标，再判断完整帧覆盖，原版与候选均重新通过。\n'
for name in ('README.md', 'results/progress-2026-10-06.txt'):
    path = root / name
    path.write_text(path.read_text(encoding='utf-8') + note, encoding='utf-8')
print(json.dumps({'report': str(out), 'ready_for_lab': str(kit), 'hardware_accessed': False}))
