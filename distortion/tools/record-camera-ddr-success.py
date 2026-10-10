from pathlib import Path
import json,re,shutil
root=Path(__file__).resolve().parents[1]
raw=(root/'build/camera_ddr/telemetry.txt').read_text(encoding='utf-8-sig')
lines=[line for line in raw.splitlines() if 'CAM=' in line]
assert len(lines)>=6
checksums=[]
for line in lines:
    assert 'D=1 K=1 Q=9 OK=1 FAIL=0 X=00 WB=00004B00 RB=00004B00' in line,line
    assert 'P=0004B000 L=01E0 O=0' in line,line
    m=re.search(r'CS=([0-9A-F]{8}) RS=([0-9A-F]{8})',line)
    assert m and m[1]==m[2],line
    checksums.append(m[1])
assert len(set(checksums))==1,'This target captures exactly one frame, not a continuous stream.'
shutil.copyfile(root/'build/camera_ddr/telemetry.txt',root/'results/camera-ddr-frame-20261006.txt')
m=json.loads((root/'build/camera_ddr/validated-build.json').read_text(encoding='utf-8-sig'))
s=json.loads((root/'status.json').read_text(encoding='utf-8-sig'))
s['current_connection'].update(last_programmed_target='camera_ddr',last_programmed_sha256=m['SHA256'])
s['camera_ddr_frame_store'].update(hardware_verified=True,frame_bytes=614400,
    written_beats=19200,read_beats=19200,source_checksum=checksums[0],read_checksum=checksums[0],
    routed_pins_checked=128,setup_wns_ns={'DDR':2.440,'CAM':9.827,'PIX':4.080,'CAM_to_DDR':6.738,'DDR_to_CAM':6.839},
    cdc_path_bound_ns=8.0,resources={'FF':7894,'LUT':6889,'DRM':40,'APM':1},
    evidence='distortion/results/camera-ddr-frame-20261006.txt',
    note='Exactly ONE complete frame after each SRAM configuration/reset. Source, write and read rolling checksums match. No continuous DDR video display or remapping implemented. HDMI remains the independent live 160x120 BRAM preview.')
s['video_async_fifo'].update(routed_board_verified=True,routed_data_bits=258,
    cdc_note='Both CAM->DDR and DDR->CAM constrained with 8ns datapath-only maximum delay and 0ns minimum; routed reports explicitly time 44 and 12 endpoints. No clock-group false path hides these crossings.')
s['rgb565_burst_pack'].update(integrated_with_ddr=True,hardware_verified=True,
    note='Verified through a single full-frame source/write/read checksum test. Continuous frame publication/arbitration and DDR display remain required.')
s['bringup']['camera_full_resolution_ddr_frame_verified']=True
s['next_hardware_requirement']='Implement continuous frame buffering and full-resolution DDR-to-HDMI read scheduling; then connect calibration inverse mapping and bilinear interpolation.'
s['measurement_limits']='Current live HDMI preview samples 160x120 and scales it to 640x480. A separate single complete 640x480 frame is stored/read back in DDR with matching rolling checksums. No continuous full-resolution DDR display, FPGA distortion correction, real calibration, measured image quality or end-to-end latency yet.'
s['not_yet_implemented']+=['continuous DDR frame publication and HDMI read arbitration']
(root/'status.json').write_text(json.dumps(s,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
report=f'''2026-10-06 11:55 当前已验证状态

实拍与显示：第二路摄像头完整 8 位 DVP 正常；每帧 307200 像素、480 行；用户确认 HDMI 实时画面随挥手变化且颜色基本正常。
显示边界：当前实时预览为 BRAM 双缓冲的 160×120 有效采样，4 倍放大显示；尚非完整分辨率 DDR 视频。
DDR 基础校验：128 KiB 区域，先全部写再全部读，四轮不同数据，各方向 16384 个 256 位块，无数据差异。
DDR 完整帧：实际摄像头一帧 640×480 RGB565，614400 字节；写入/读回各 19200 个 256 位块。源校验值与读回校验值同为 {checksums[0]}；OK=1、FAIL=0。
完整帧验证边界：此版本上电/重配置后只存储和校验一帧；连续八条遥测是同一帧的保持结果，不能宣称八帧或连续帧测试。
实现：像素打包、258 位异步 FIFO、完整 16 拍突发预取、帧尺寸/首末标记检查、存储完成后元数据核对、整帧读回。
仿真：逐像素 DDR 地址、字节顺序、两端不同时钟、队列满/回绕、读写暂停、单比特错误、地址重叠、短行及复位恢复均已按相关模块验证。
时序：128 个路由引脚核对通过。DDR/摄像头/HDMI setup WNS=2.440/9.827/4.080 ns；CAM→DDR、DDR→CAM 的 8 ns 数据路径约束也通过，WNS=6.738/6.839 ns。
频率：JTAG 保持 5 MHz（完整下载 7 秒），DDR 核心保持配套 125 MHz，PCLK 板内边沿统计约 24 MHz；未靠持续降频通过。
第一路：更换摄像头小板和 FMC 转接板后，模块 D1 输出使能仍使 SCCB 失去应答；原因未电气隔离。当前使用第二路推进，不声称所有摄像头通道故障已解决。
资源（含实时 BRAM 预览及 DDR IP）：7894 FF，6889 LUT，40 DRM，1 APM。
当前 FPGA SRAM 程序：camera_ddr；断电后须重下载；Flash 未编程。
下一步：连续帧发布/双缓冲、DDR→HDMI 全分辨率读取，再接入畸变坐标映射和双线性插值，并采集真实标定图像。

位流校验清单：distortion/build/camera_ddr/validated-build.json
完整帧原始遥测：distortion/results/camera-ddr-frame-20261006.txt
DDR 四轮原始遥测：distortion/results/ddr-integrity-20261006.txt
项目当前状态：distortion/status.json

以下保留今日过程记录，最新状态以上文为准：
----------------------------------------
'''
p=root/'results/progress-2026-10-06.txt'
p.write_text(report+p.read_text(encoding='utf-8-sig'),encoding='utf-8')
# These are descriptive JSON fields only; do not regenerate the verified ROM.
p=root/'board/ov5640-vga-rgb565-candidate.json'
c=json.loads(p.read_text())
c['status']='camera2_initialized_preview_and_single_frame_ddr_verified_on_20261006'
c['board_adaptations']=c['board_adaptations'].replace('sync active high','4740=23 retained; receiver must invert raw VSYNC and HREF per real four-polarity test on 2026-10-06')
c['hardware_observations_20261006']={'channel':2,'initialization_verified':True,'low_byte_first_color_preview_user_confirmed':True,'raw_vsync_and_href_active_low_receiver_verified':True,'one_640x480_ddr_frame_checksum_verified':True,'actual_frequency_and_image_quality_limits':'24MHz edge-counter estimate, approximately 11.4fps; no precision timing or image-quality measurement.'}
p.write_text(json.dumps(c,indent=2)+'\n')
print(f'Saved one real 640x480 DDR frame proof: {len(lines)} status samples, checksum {checksums[0]}, 19200 beats each direction.')
