"""Access-trace evaluation only: does not predict hardware FPS or certify RTL."""
import sys, re, json, hashlib
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
import generate_hdmi_fisheye_profile as fish

ROOT=Path(__file__).resolve().parents[1]/'source'
header=ROOT/'board/hdmi-camera-fisheye-profile.vh'
table=ROOT/'board/hdmi-camera-fisheye-radial-table.vh'
constants={k:int(v,16) for k,v in re.findall(r"FISHEYE_(\w+)=32'sh([0-9a-f]+)",header.read_text())}
pairs=[int(v,16) for v in re.findall(r"fisheye_radial_pair=64'h([0-9a-f]+)",table.read_text())]
assert len(pairs)==1024
last_delta=pairs[-1]>>32
if last_delta>=2**31:last_delta-=2**32
lut=np.array([p&0xffffffff for p in pairs]+[(pairs[-1]&0xffffffff)+last_delta],dtype=np.int64)
y,x=np.indices((1080,1920),dtype=np.int64)
sx,sy,black=fish.fixed_map(x*256,y*256,config={'Constants':constants,'LUTQ30':lut})
# RTL corrected-mode sequence: stripe, tile, row within tile, column within tile.
order=np.arange(1080*1920).reshape(135,8,240,8).transpose(0,2,1,3).reshape(-1)
xs=(sx.reshape(-1)[order]>>8).tolist();ys=(sy.reshape(-1)[order]>>8).tolist()
def simulate(bits):
    tags=[-1]*(1<<bits);mask=len(tags)-1;miss=slow=0
    for xx,yy in zip(xs,ys):
        blocks=[((yy+dy)*1920+xx+dx)>>7 for dy,dx in ((0,0),(0,1),(1,0),(1,1)) if 0<=xx+dx<1920 and 0<=yy+dy<1080]
        if all(tags[b&mask]==b for b in blocks):continue
        slow+=1
        for b in blocks:
            if tags[b&mask]!=b:miss+=1;tags[b&mask]=b
    return {'index_bits':bits,'cache_bytes':(1<<bits)*256,'block_reads':miss,'slow_queries':slow,'queries':len(xs)}
results=[simulate(b) for b in (7,8,9)]
report={'kind':'access-trace model, not HDL or board measurement','profile_sha256':hashlib.sha256(header.read_bytes()).hexdigest(),'table_sha256':hashlib.sha256(table.read_bytes()).hexdigest(),'results':results,'hardware_fps_verified':False}
Path(__file__).with_suffix('.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
