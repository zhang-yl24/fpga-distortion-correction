"""Record a validated continuous hardware run without changing old targets."""
from pathlib import Path
from datetime import datetime
import json
import re
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
subprocess.run([sys.executable, str(root/'tools/check-live-telemetry.py')], check=True)
evidence = json.loads((root/'results/live-video-check-20261006.json').read_text())
assert evidence['observed_span_seconds'] >= 30, 'Need the longer finite run before declaring this milestone.'
work = root/'build/live_video'
manifest = json.loads((work/'validated-build.json').read_text(encoding='utf-8-sig'))
timing = (work/'place_route/live_video_timing_summary_after_hold_fix.txt').read_text()
assert 'All Constraints Met' in timing
slow = timing.split('Setup Summary(Slow Corner):', 1)[1].split('Hold Summary', 1)[0]
wns = {f'{a}->{b}': float(v) for a, b, v in
       re.findall(r'^\s*(\w+)\s+(\w+)\s+(-?\d+\.\d+)\s+0\.000', slow, re.M)}
assert wns and min(wns.values()) > 0
program = (work/'program.out.txt').read_text(errors='replace')
assert 'The done bit is 1' in program and 'cfg_program -device_index 0 successfully' in program
state = json.loads((root/'status.json').read_text(encoding='utf-8-sig'))
state['current_connection'].update(last_programmed_target='live_video', last_programmed_sha256=manifest['SHA256'])
state['bringup'].update(camera_continuous_full_resolution_ddr_video_verified=True,
                       camera_full_resolution_monitor_user_confirmed=state['bringup'].get('camera_full_resolution_monitor_user_confirmed',False))
state['verification'].update(live_video_crc32_python_reference_passed=True,
                            live_video_small_and_fifo_exceeding_frame_simulations_passed=True,
                            live_video_routed_pins_checked=128,
                            live_video_all_constraints_met=True)
state['live_video'] = dict(evidence, implemented=True, hardware_verified=True,
    target='live_video', two_frame_banks=True, bank_stride_bytes=1048576,
    frame_bytes=614400, ddr_core_mhz=125, pixel_clock_mhz=74.25,
    hdmi_mode='1280x720@60, native 640x480 image centered',
    crc32_stages=['accepted camera packet stream', 'DDR writer', 'DDR reader', 'display pixel stream'],
    setup_wns_ns=wns, cdc_datapath_max_ns=8,
    resources={'FF': 8673, 'LUT': 9649, 'DRM': 12, 'APM': 0},
    evidence='distortion/results/live-video-check-20261006.json',
    throughput_limit='Current ownership controller waits for frame-boundary hand-off and rearms on the next sensor VSYNC, dropping about every other camera frame. New committed frames are about 5.7fps, not 60fps. Continuous capture/ownership optimization and sensor frame-rate tuning remain required.')
state['rgb565_burst_pack']['note'] = 'Continuous full-resolution two-bank video path verified with per-frame IEEE CRC32.'
state['video_async_fifo']['cdc_note'] = 'CAM<->DDR and PIX<->DDR crossings explicitly timed with 8ns datapath maxima; slow/fast setup/hold pass. Full-frame simulation exceeds FIFO depth.'
state['not_yet_implemented'] = [x for x in state['not_yet_implemented'] if x != 'continuous DDR frame publication and HDMI read arbitration']
state['not_yet_implemented'].append('continuous camera frame acquisition without current hand-off gaps')
state['next_hardware_requirement'] = 'Connect inverse-coordinate mapping, arbitrary-neighbour DDR reader/cache and bilinear interpolation. Optimize frame acquisition cadence and obtain real calibration images.'
monitor_note = 'User confirmed normal monitor picture on 2026-10-06.' if state['bringup']['camera_full_resolution_monitor_user_confirmed'] else 'New monitor appearance not yet user confirmed.'
state['measurement_limits'] = 'Full 640x480 RGB565 continuous DDR-to-HDMI pixel stream checked on hardware using source/read/pixel CRC32 and advancing frame counters. '+monitor_note+' Finite run only; no distortion correction, actual calibration, measured image quality or end-to-end latency yet. Camera input approximately 11.4fps, new committed frames approximately 5.7fps, display refresh approximately 60Hz.'
(root/'status.json').write_text(json.dumps(state, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
rates = evidence['approx_rates_per_second']
stamp = datetime.now().strftime('%Y-%m-%d %H:%M')
report = f'''{stamp} 连续全分辨率 DDR 视频里程碑

实板路径：第二路 OV5640 → 640×480 RGB565 → 双帧 DDR 缓存 → 原分辨率像素输出 → HDMI 720p60 中央区域。
连续证据：{evidence['samples']} 条完整 UART 遥测，首末采样间隔 {evidence['observed_span_seconds']:.3f} 秒；新增提交帧 {evidence['counter_delta']['WF']}，完整显示帧 {evidence['counter_delta']['PF']}。
错误计数：欠载 UF=0、输出像素 CRC 不一致 MF=0、读写缓存冲突 OW=0、故障 X=00；源帧 CRC32 在变化，未停留于同一帧。
校验：IEEE CRC32，摄像头源、DDR 写/读和 HDMI 输出像素逐帧核对。各阶段保持自己的帧元数据，最新源 CRC 与上一显示帧 CRC 可以不同，不据此误报。
速率：相机输入约 {rates['F']:.2f} 帧/秒，新提交帧约 {rates['WF']:.2f} 帧/秒，完整显示约 {rates['PF']:.2f} 次/秒。串口接收时间估计，约 100ms 轮询误差；显示会重复已有帧，不能宣称 60fps 相机采集。
性能边界：当前双缓存控制等待显示帧边界交接，随后重新等待摄像头 VSYNC，约丢弃隔帧；需要改为连续采集并优化缓存交接，不能将本版作为最终性能指标。
时钟：DDR 125 MHz、HDMI 74.25 MHz、JTAG 5 MHz；未持续降频。
实现核对：128 个物理引脚一致，布局布线快慢角建立/保持及恢复约束全部通过；DDR/PIX/CAM setup WNS=2.251/3.420/8.543 ns，CAM↔DDR、PIX↔DDR 的 8ns 数据路径约束也通过。
资源：8673 FF、9649 LUT、12 DRM、0 APM；已移除用于早期预览的低分辨率 BRAM 双帧。
仿真：两种尺寸、不同时钟、逐像素独立比较、帧大于 FIFO 容量、同时读写、突发暂停、欠载、周期性多位破坏和复位恢复；CRC32 与 Python binascii 独立交叉验证。
显示边界：新版本 HDMI 输出像素链路的硬件校验已通过；用户尚未确认显示器上本版的物理画面。此前仅确认低分辨率预览正常。
当前程序：live_video，仅 SRAM，断电需重下载；旧 preview 和 camera_ddr 位流保留，Flash 未写。
下一步：逆坐标计算、DDR 邻域读取/缓存与双线性插值接入；同步优化新帧速率并获取真实棋盘标定图像。
位流 SHA256：{manifest['SHA256']}
原始遥测：distortion/results/live-video-20261006.txt
时间戳与检查：distortion/results/live-video-timed-20261006.json；distortion/results/live-video-check-20261006.json

以下保留此前过程记录，以最新状态为准：
----------------------------------------
'''
p = root/'results/progress-2026-10-06.txt'
previous = p.read_text(encoding='utf-8-sig')
if '连续全分辨率 DDR 视频里程碑' not in previous.split('\n', 1)[0]:
    p.write_text(report+previous, encoding='utf-8')
print('Saved continuous full-resolution hardware milestone and its finite verification limits.')
