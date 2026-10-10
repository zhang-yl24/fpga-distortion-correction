"""Independent full-size RGB565 source frames and fixed-point sampling oracle."""
from pathlib import Path
import json
import sys
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from model.reference import bilinear_u8

root = Path(__file__).resolve().parents[1]
work = root/'build/remap_sim'
work.mkdir(parents=True, exist_ok=True)
w,h = 640,480
yy,xx = np.indices((h,w), dtype=np.uint32)
images = []
words = []
for seed in (3,11,29):
    packed = (((xx*7+yy*3+seed)&31)<<11) | (((xx*5+yy*11+seed)&63)<<5) | ((xx*13+yy*7+seed)&31)
    rr=(packed>>11)&31; gg=(packed>>5)&63; bb=packed&31
    images.append(np.stack([(rr<<3)|(rr>>2),(gg<<2)|(gg>>4),(bb<<3)|(bb>>2)],axis=-1).astype(np.uint8))
    flat=packed.ravel()
    words.append([''.join(f'{int(p):04x}' for p in flat[i:i+16][::-1]) for i in range(0,len(flat),16)])
for i,frame in enumerate(words):
    (work/f'frame{i}.mem').write_text('\n'.join(frame)+'\n')

rng=np.random.default_rng(0x5640)
queries=[]
# Sequential real source rows: repeated pixels, burst boundaries and cache hits.
for y in (0,1,17,239,478,479):
    for x in range(640):
        queries.append((x*256+(x%256),y*256+((x*17)%256)))
# Four neighbours cross line boundaries and borders independently.
for x in (-32768,-2,-1,0,15,16,255,256,639,640,32766,32767):
    for y in (-32768,-1,0,479,480,32767):
        for frac in (0,1,128,255):
            queries.append((x*256+frac,y*256+255-frac))
# Same direct-mapped slot, different tags; revisit evicted blocks.
for offset in (0,2048,4096,0,8192,2048,0):
    for i in range(32):
        linear=offset+i*7
        queries.append(((linear%w)*256+31,(linear//w)*256+157))
# Synthetic nonlinear inverse map coordinates (test coefficients, not calibration).
for y in range(0,h,17):
    for x in range(0,w,19):
        u=(x-319.5)/320;v=(y-239.5)/320;r2=u*u+v*v
        queries.append((int(np.floor((319.5+320*u*(1-0.23*r2+0.055*r2*r2))*256+0.5)),
                        int(np.floor((239.5+320*v*(1-0.23*r2+0.055*r2*r2))*256+0.5))))
for _ in range(1024):
    queries.append((int(rng.integers(-512,(w+2)*256)),int(rng.integers(-512,(h+2)*256))))

def rgbint(rgb):
    return (int(rgb[0])<<16)|(int(rgb[1])<<8)|int(rgb[2])
vectors=[]
for image in images:
    for qx,qy in queries:
        ix,iy=qx>>8,qy>>8;fx,fy=qx&255,qy&255
        neighbours=[]
        for dx,dy in ((0,0),(1,0),(0,1),(1,1)):
            neighbours.append(image[iy+dy,ix+dx] if 0<=ix+dx<w and 0<=iy+dy<h else np.zeros(3,dtype=np.uint8))
        expected=bilinear_u8(*neighbours,fx,fy)
        fields=[qx&0xffffff,qy&0xffffff,*map(rgbint,neighbours),rgbint(expected)]
        vectors.append(''.join(f'{v:06x}' for v in fields))
(work/'vectors.mem').write_text('\n'.join(vectors)+'\n')
(work/'counts.vh').write_text(f'`define REMAP_QUERIES {len(queries)}\n`define REMAP_TOTAL {len(vectors)}\n')
meta={'size':[w,h],'queries_per_frame':len(queries),'total_queries':len(vectors),
      'frames':3,'bank_sequence':[0,1,0],'third_frame_replaces_same_bank_data':True,
      'reference':'RGB565 bit replication to RGB888, model.reference.bilinear_u8, signed arithmetic floor, per-neighbour border zero',
      'coverage':['sequential rows','fractional and extreme negative coordinates','all four borders','burst/beat crossing','cache collision/eviction','synthetic nonlinear map','random coordinates','bank switch and same-bank rewrite']}
(work/'vectors.json').write_text(json.dumps(meta,indent=2)+'\n')
print(f'Prepared {len(vectors)} independent remap queries across three complete 640x480 source frames.')
