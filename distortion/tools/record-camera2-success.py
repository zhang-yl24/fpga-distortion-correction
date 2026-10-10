import json
from pathlib import Path
from datetime import datetime

root = Path(__file__).resolve().parents[1]
manifest = json.loads((root/'build/preview/validated-build.json').read_text(encoding='utf-8-sig'))
s = json.loads((root/'status.json').read_text(encoding='utf-8-sig'))
s['date'] = '2026-10-06'
b = s['bringup']
b.update(camera_capture_verified=True, camera_register_initialization_verified=True,
         camera_sustained_pixel_clock_detected=True,
         camera_initialization_blocker='First camera channel still fails after 3018 bit5 enables module D1 (sensor D3), even after replacing BOTH camera PCB and FMC adapter. Physical cause not isolated. Second camera channel works with all eight data bits enabled.',
         camera_initialization_evidence='distortion/results/camera-pad-sweep-20261006.json; distortion/build/camera2/telemetry.txt',
         camera_capture_evidence='Second channel: 307200 RGB565 pixels / 480 lines per frame; user confirmed live HDMI image responds to waving and colors basically normal on 2026-10-06.',
         camera_preview_verified=True, camera_preview_effective_resolution=[160,120],
         camera_input_resolution=[640,480], camera_raw_sync_active_low=True,
         camera_frame_rate_approx_fps=11.4, camera_frame_rate_note='Estimate from UART frame count progression; not a precision timing measurement.',
         camera_pclk_edge_counter_approx_mhz=24)
s['camera_pad_sweep'].update(hardware_results_collected=True,reason='All 14 masks collected after user replaced camera PCB AND FMC adapter; 7020 and 7FF0 fail. Replacing two components together does not identify their individual responsibility.',evidence='distortion/results/camera-pad-sweep-20261006.json')
s['rgb565_burst_pack'].update(pds_device_map_verified=True)
s['current_connection'].update(last_programmed_target='preview',last_programmed_sha256=manifest['SHA256'])
s['verification'].update(camera2_full_bus_initialization_and_frame_structure_verified=True,
                         camera_preview_async_double_buffer_simulation_passed=True,
                         camera_preview_routed_pins_checked=55,
                         camera_preview_setup_wns_ns={'SYS':30.424,'PIX':4.396,'CAM':6.779},
                         camera_preview_user_confirmed=True)
s['next_hardware_requirement']='Develop DDR write/read integrity test and then complete-frame storage using the functioning second camera. Keep current preview as a rollback target.'
s['measurement_limits']='Live color/movement visually confirmed, but preview is only 160x120 scaled to 640x480. No DDR video, distortion correction, real calibration coefficients, measured image quality or end-to-end latency verified.'
(root/'status.json').write_text(json.dumps(s,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
import shutil
shutil.copyfile(root/'build/preview/telemetry.txt',root/'results/camera2-preview-20261006.txt')
p=root/'results/progress-2026-10-06.txt'
previous=p.read_text(encoding='utf-8-sig')
latest='''2026-10-06 当前进展（第二路摄像头实时预览已由用户确认）

- 同时更换摄像头小板和 FMC 转接板后，第一路仍在 3018 bit5（模块 D1）输出使能时失去应答；完整 14 组硬件结果已保存，物理原因尚未隔离。
- 四组同步极性测试确认当前 4740=23 配置须在接收端同时反相原始 VSYNC/HREF。
- 第二路使用完整 8 位 DVP：INIT=1、E=00、264 条配置命令成功；每帧 307200 像素、480 行，无半像素错误。
- PCLK 边沿计数约 24 MHz，帧率约 11.4 fps；这些是板内统计估计，尚未用示波器精测。
- 双缓冲 BRAM 预览已完成仿真、PDS 全流程和 5 MHz 实板下载。用户确认实时画面随挥手变化、颜色基本正常。
- 摄像头输入为 640×480；当前 HDMI 中央预览有效采样仅 160×120，经 4 倍放大显示。完整分辨率 DDR 视频及畸变矫正尚未接入。
- 预览消耗 32 个 DRM；55 个路由引脚核对通过，所有约束通过。SYS/PIX/CAM setup WNS 分别 30.424/4.396/6.779 ns。
- RGB565→256 位打包核心已完成仿真和 PDS 器件映射；异步 FIFO 与 DDR 集成仍需完成。
- 现在进入 DDR 写入/读回及完整帧缓存开发，当前 preview 位流保留为可恢复基线。

当前位流：distortion/build/preview/generate_bitstream/preview.sbit
校验清单：distortion/build/preview/validated-build.json
硬件遥测：distortion/results/camera2-preview-20261006.txt
分组诊断：distortion/results/camera-pad-sweep-20261006.json

以下为当天早期记录，状态以以上最新进展为准：
----------------------------------------
'''
p.write_text(latest+previous,encoding='utf-8')
print('Saved camera2 full-frame structure and user-confirmed BRAM preview evidence; DDR remains unverified.')
