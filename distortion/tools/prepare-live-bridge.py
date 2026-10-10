from pathlib import Path
root=Path(__file__).resolve().parents[1]
s=(root/'rtl/camera_ddr_bridge.v').read_text()
s=s.replace('module camera_ddr_bridge #','module camera_live_bridge #')
s=s.replace('reg frozen=0,valid_held=0,done_held=0;', 'reg frozen=0,valid_held=0,done_held=0,started=0;')
s=s.replace('arm_sync<=0;frozen<=0;', 'arm_sync<=0;started<=0;frozen<=0;')
s=s.replace('            arm_sync<={arm_sync[0],arm};', '            arm_sync<={arm_sync[0],arm};\n            if(cap_rst_n && frame_start) started<=1;')
s=s.replace('if(!frozen && cap_rst_n && (frame_invalid', 'if(!frozen && cap_rst_n && started && (frame_invalid')
(root/'rtl/camera_live_bridge.v').write_text(s)
print('Prepared live bridge: ignore partial rows before first sensor frame boundary; single-frame baseline unchanged.')
