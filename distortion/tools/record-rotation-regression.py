"""Archive cycle evidence and render actual-capture integer-model previews."""
from pathlib import Path
import csv,hashlib,json
import numpy as np
from PIL import Image,ImageDraw,ImageFont
root=Path(__file__).resolve().parents[1]
work=root/'build/rotated_native_sim'
reference=json.loads((work/'reference.json').read_text())
log=(work/'simulation.log').read_text()
assert 'PASS rotated native regression: 1843200' in log and 'Fatal:' not in log
rows=list(csv.DictReader((work/'cycles.csv').open()))
assert len(rows)==6
for row,frame in zip(rows,reference['frames']):
    assert row['crc32'].upper()==frame['crc32'] and int(row['pixels'])==307200
    frame.update({k:int(row[k]) for k in ('cycles','cache_hits','cache_misses','read_bursts','pixels')})
    frame['modeled_engine_ms_at_125mhz']=int(row['cycles'])/125000
reference.update({'rtl_passed':True,'board_rotation_verified':False,'coordinate_lookup_table':False,
    'clock_hz':125000000,'log_sha256':hashlib.sha256((work/'simulation.log').read_bytes()).hexdigest(),
    'performance_limits':'Standalone full-frame RTL with synthetic DDR stalls. No camera cadence, HDMI arbitration, physical DDR service time or optical-quality proof. 90-degree cache misses show a bandwidth locality bottleneck.'})
out=root/'results/rotated-native-regression-20261006.json'
out.write_text(json.dumps(reference,indent=2)+'\n')
payload=b''.join(int(line,16).to_bytes(32,'little') for line in (work/'result.mem').read_text().splitlines())
assert len(payload)==6*640*480*2
image=Image.new('RGB',(1056,652),'white');draw=ImageDraw.Draw(image)
font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',20);small=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',16)
draw.text((16,10),'真实采集图像 → 整数模型旋转与矫正预览（非本轮实板输出）',font=font,fill='black')
for i,frame in enumerate(reference['frames']):
    p=np.frombuffer(payload[i*614400:(i+1)*614400],dtype='<u2').reshape(480,640)
    r,g,b=(p>>11)&31,(p>>5)&63,p&31
    rgb=np.stack(((r<<3)|(r>>2),(g<<2)|(g>>4),(b<<3)|(b>>2)),axis=-1).astype(np.uint8)
    panel=Image.fromarray(rgb).resize((336,252))
    x=16+(i%3)*344;y=56+(i//3)*288
    image.paste(panel,(x,y));draw.text((x,y+254),f'{frame["angle_deg"]:+d}°  原帧{"A" if i%2==0 else "B"}  {frame["modeled_engine_ms_at_125mhz"]:.2f} ms（仿真）',font=small,fill='black')
draw.text((16,630),'6 个角度共 1,843,200 像素逐项一致；不同角度交替使用两组已采集原帧。',font=small,fill='black')
image.save(root/'results/rotation-preview-20261006.png')
print('Recorded six-angle cycle evidence and labeled software preview; not a physical FPS result.')
