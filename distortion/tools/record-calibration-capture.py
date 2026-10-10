"""Preserve native frame-export evidence without claiming corrected hardware."""
from pathlib import Path
from datetime import datetime
import hashlib
import json
import re
import shutil
import zlib

root = Path(__file__).resolve().parents[1]
work = root/'build/calibration_capture'
manifest = json.loads((work/'validated-build.json').read_text(encoding='utf-8-sig'))
bitstream = Path(manifest['Bitstream'])
assert hashlib.sha256(bitstream.read_bytes()).hexdigest().upper() == manifest['SHA256']
timing_path = work/'place_route/calibration_capture_timing_summary_after_hold_fix.txt'
timing = timing_path.read_text(errors='replace')
assert 'All Constraints Met' in timing
slow = timing.split('Setup Summary(Slow Corner):',1)[1].split('Hold Summary',1)[0]
wns = {f'{a}->{b}':float(v) for a,b,v in re.findall(
    r'^\s*(\w+)\s+(\w+)\s+(-?\d+\.\d+)\s+0\.000', slow, re.M)}
assert wns and min(wns.values()) > 0
program = (work/'program.out.txt').read_text(errors='replace')
assert 'The done bit is 1' in program and 'cfg_program -device_index 0 successfully' in program
transfer = json.loads((work/'program-evidence-20261006-143855-5MHz/transfer.json').read_text(encoding='utf-8-sig'))
assert transfer['Done'] and transfer['Frequency']=='5MHz' and transfer['SHA256']==manifest['SHA256']
sim = (root/'build/uart_frame_sim/simulation.log').read_text(errors='replace')
assert 'PASS DDR-to-UART native frames' in sim
capture = json.loads((root/'results/calibration-capture-latest.json').read_text())
assert capture['saved_frames']==len(capture['frames']) and capture['saved_frames']>0
for frame in capture['frames']:
    raw = Path(frame['raw']).read_bytes()
    assert len(raw)==614400 and (frame['width'],frame['height'])==(640,480)
    assert f'{zlib.crc32(raw):08X}'==frame['received_crc32']==frame['source_crc32']
    assert frame['geometry_applied'] is False
result = {'recorded_at':datetime.now().isoformat(timespec='seconds'),
    'target':'calibration_capture', 'hardware_verified':True,
    'bitstream_sha256':manifest['SHA256'],'program_frequency':'5MHz',
    'resolution':[640,480],'frame_bytes':614400,'ddr_core_mhz':125,
    'uart_requested_baud':921600,'uart_actual_baud':125000000/136,
    'hdmi_preview_resolution':[160,120], 'routed_pins_checked':128,
    'all_constraints_met':True,'setup_wns_ns':wns,
    'saved_frames':capture['saved_frames'],'complete_chessboards':sum(f['chessboard_detected'] for f in capture['frames']),
    'rejected_packets':capture['rejected_packets'],
    'discarded_stream_bytes':capture['discarded_stream_bytes'],
    'discard_note':'Opening COM5 during a packet requires discarding its tail until the next header; not rejected complete packets.',
    'five_printed_squares_measured_mm_user_confirmed':100,'square_mm':20,'inner_corners':[9,6],
    'capture_summary':'distortion/results/calibration-capture-latest.json',
    'limits':'Dedicated frozen-frame export (~6.8s per transfer), not continuous video FPS. HDMI is a 160x120 preview. End-to-end FPGA correction remains unverified.'}
(root/'results/calibration-capture-20261006.json').write_text(json.dumps(result,indent=2)+'\n')
archive = root/'results/verified/calibration-capture-20261006'
sources = ['rtl/ddr_uart_frame.v','board/calibration_capture.v','board/calibration_capture.fdc',
    'tools/frame_protocol.py','tools/capture-calibration.py','tools/select-calibration-views.py',
    'tools/calibrate.py','tools/audit-calibration.py','tools/prepare-calibration-capture.py',
    'tools/generate-uart-frame-test.py','tests/tb_ddr_uart_frame.sv','tests/test_frame_protocol.py',
    'tools/build-pds.ps1','tools/program-heartbeat.ps1']
for source in sources:
    destination=archive/source;destination.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(root/source,destination)
archive.mkdir(parents=True,exist_ok=True)
for source in (bitstream,timing_path,work/'validated-build.json',work/'program.out.txt',
               root/'build/uart_frame_sim/simulation.log',root/'results/calibration-capture-20261006.json'):
    shutil.copy2(source,archive/source.name)
shutil.copy2(root/'results/calibration-capture-latest.json',archive/'capture-first-batch.json')
state=json.loads((root/'status.json').read_text(encoding='utf-8-sig'))
state['current_connection'].update(last_programmed_target='calibration_capture',last_programmed_sha256=manifest['SHA256'])
state['calibration_capture']=result
state['verification'].update(uart_native_frame_export_wire_simulation_passed=True,
    calibration_capture_all_constraints_met=True,calibration_capture_routed_pins_checked=128)
state['not_yet_implemented']=[s for s in state['not_yet_implemented'] if s!='calibration-frame export from the actual OV5640 source']
state['next_hardware_requirement']='Complete edge calibration coverage; integrate corrected output frame store and burst-owner arbiters.'
state['measurement_limits']+=' Native raw calibration frames now exported from frozen DDR with matching source/host CRC32. Current SRAM target is calibration_capture with a 160x120 HDMI preview; final corrected video remains unverified.'
(root/'status.json').write_text(json.dumps(state,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
report=f'''{result['recorded_at']} 真实摄像头标定帧导出与首轮多姿态采集

实板：第二路 OV5640 → 原生 640×480 RGB565 → 冻结 DDR 帧 → UART 二进制导出。每帧 614400 字节，原始像素完整保存；PNG 仅按位展开颜色，不缩放、不做几何矫正。
首轮连续导出 {result['saved_frames']} 帧，完整角点 {result['complete_chessboards']} 帧，完整包校验拒绝 {result['rejected_packets']}；逐帧源 CRC32、DDR 读出 CRC32、电脑接收 CRC32 一致。
串口 921600 baud 请求值，实际约 {result['uart_actual_baud']:.1f}；约 6.8 秒/帧用于标定传输，不能视作相机采集帧率。打开串口时丢弃正在发送包的尾部属于正常同步。
HDMI 当前是 160×120 预览；已验证 live_video 的 640×480 连续显示位流保留。当前配置 calibration_capture 仅 SRAM。
时序：DDR 保持 125MHz、JTAG 5MHz，128 引脚校验通过；快慢角全部约束满足，DDR 建立 WNS={wns['ddrphy_sysclk->ddrphy_sysclk']:.3f} ns。
仿真：三帧完整 8N1 波形与 Python/zlib 独立参考逐字节核对；DDR/串口暂停、CRC、RLAST/RID、超时、复位恢复通过。
打印板：9×6 内角点、20mm 方格；用户确认五格实测 100mm。
首轮拟合有真实数据，但覆盖不足，参数仍为候选；不能用局部低误差宣称边缘矫正有效。下一步补齐边缘视角、审核全图映射，再接入 FPGA 矫正输出。
证据：distortion/results/calibration-capture-20261006.json；captures/calibration；results/verified/calibration-capture-20261006。

以下保留此前过程记录，以最新状态为准：
----------------------------------------
'''
p=root/'results/progress-2026-10-06.txt';previous=p.read_text(encoding='utf-8-sig')
if '真实摄像头标定帧导出与首轮多姿态采集' not in previous.split('\n',1)[0]:p.write_text(report+previous,encoding='utf-8')
print(json.dumps(result,indent=2))
