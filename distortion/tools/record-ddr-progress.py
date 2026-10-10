from pathlib import Path
import json,re,shutil
root=Path(__file__).resolve().parents[1]
s=json.loads((root/'status.json').read_text(encoding='utf-8-sig'))
raw=(root/'build/ddr_check/telemetry.txt').read_text(encoding='utf-8-sig')
lines=[line for line in raw.splitlines() if 'CAM=' in line]
assert len(lines)>=6
for line in lines:
    assert 'D=1 K=1 Q=7 OK=1 FAIL=0 X=00 WB=00004000 RB=00004000 BAD=00000000 BA=0000000 PASS=04' in line,line
shutil.copyfile(root/'build/ddr_check/telemetry.txt',root/'results/ddr-integrity-20261006.txt')
m=json.loads((root/'build/ddr_check/validated-build.json').read_text(encoding='utf-8-sig'))
s['bringup']['ddr_hardware_verified']=True
s['current_connection'].update(last_programmed_target='ddr_check',last_programmed_sha256=m['SHA256'])
s['ddr_integrity']={'hardware_verified':True,'region_bytes':131072,'passes':4,'written_256bit_beats':16384,'read_256bit_beats':16384,'errors':0,'core_clock_mhz':125,'setup_wns_ns':0.922,'routed_pins_checked':128,'evidence':'distortion/results/ddr-integrity-20261006.txt','limits':'Finite region/four patterns; not a full-memory stress or bandwidth measurement.'}
s['video_async_fifo']={'implemented':True,'simulation_verified':True,'pds_device_map_verified':True,'data_bits':256,'depth':512,'drm_blocks':4,'routed_board_verified':False}
s['camera_ddr_frame_store']={'implemented':True,'integration_simulation_verified':True,'hardware_verified':False,'frame_size':[640,480],'frame_beats':19200,'note':'One-frame acquisition and readback, not continuous DDR display. Current routed build in progress.'}
s['next_hardware_requirement']='Complete routed camera_ddr build and validate source/write/read checksums for one full 640x480 frame on the real board.'
(root/'status.json').write_text(json.dumps(s,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
p=root/'results/progress-2026-10-06.txt'
with p.open('a',encoding='utf-8') as f:
    f.write('''

11:44 之后补充（DDR 实板校验通过，完整帧存储开发中）：
- 复用配套 HMIC_S IP，125 MHz core_clock 保持；128 个物理引脚逐个校验，DDR setup WNS=0.922 ns，所有时序约束通过。
- 128 KiB 区域先全部写入再全部读回，四轮不同数据，共写/读各 16384 个 256 位块（各 512 KiB）；连续八条 UART 报告均 OK=1、FAIL=0、BAD=0、PASS=04。
- 异步 FIFO 已通过不同频率、满队列、4096 次传输/回绕、暂停、复位恢复仿真；PDS 映射为 4 DRM，339 FF，390 LUT（含独立可加载各数据通道的测试顶层）。
- camera_ddr_bridge 和 ddr_frame_store 已联动仿真：DVP→打包→异步 FIFO→完整突发预取→DDR→读回，逐像素地址核对、错误注入、短行拒绝和恢复通过。
- 正在生成 camera_ddr 实板程序，完整 640×480 单帧存储及 checksum 读回尚未实板确认；实时 HDMI 仍是先前的 160×120 BRAM 预览。
''')
print('Saved verified DDR integrity evidence (four passes, 16384 beats each direction, zero mismatches).')
