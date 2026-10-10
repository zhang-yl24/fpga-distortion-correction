"""Integer-model entire-frame references, including final RGB565 quantization."""
from pathlib import Path
import importlib.util
import json
import sys
import zlib
import numpy as np

root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root))
from model.reference import bilinear_u8
spec=importlib.util.spec_from_file_location('brown',root/'tools/generate-brown-vectors.py')
brown=importlib.util.module_from_spec(spec);spec.loader.exec_module(brown)
out=root/'build/frame_engine_sim';out.mkdir(parents=True,exist_ok=True)
w,h=32,16;yy,xx=np.indices((h,w),dtype=np.uint32)
source=[];result=[];crcs=[];parameters=[]
for phase,seed in enumerate((17,99,201)):
    c=[15*256+128,7*256+128,15*256+128+(128 if phase else 0),7*256+128,
       32*256,32*256,1<<25,1<<25,-(1<<19) if phase else 0,0,0,0,0]
    parameters.append(c)
    raw=((((xx*7+yy*3+seed)&31)<<11)|(((xx*5+yy*11+seed)&63)<<5)|((xx*13+yy*7+seed)&31)).astype('<u2')
    r=(raw>>11)&31;g=(raw>>5)&63;b=raw&31
    image=np.stack(((r<<3)|(r>>2),(g<<2)|(g>>4),(b<<3)|(b>>2)),axis=-1).astype(np.uint8)
    corrected=[]
    for y in range(h):
        for x in range(w):
            sx,sy,bad=brown.project(x*256,y*256,c)
            ix,iy=sx>>8,sy>>8;fx,fy=sx&255,sy&255
            neighbours=[image[iy+dy,ix+dx] if 0<=ix+dx<w and 0<=iy+dy<h else np.zeros(3,dtype=np.uint8)
                        for dx,dy in ((0,0),(1,0),(0,1),(1,1))]
            rgb=bilinear_u8(*neighbours,fx,fy)
            corrected.append(((int(rgb[0])>>3)<<11)|((int(rgb[1])>>2)<<5)|(int(rgb[2])>>3))
    src=raw.tobytes();dst=np.array(corrected,dtype='<u2').tobytes()
    assert phase!=0 or dst==src,'identity reference must preserve every pixel'
    source.extend(int.from_bytes(src[i:i+32],'little') for i in range(0,len(src),32))
    result.extend(int.from_bytes(dst[i:i+32],'little') for i in range(0,len(dst),32))
    crcs.append(zlib.crc32(dst))
(out/'source.mem').write_text(''.join(f'{v:064x}\n' for v in source))
(out/'result.mem').write_text(''.join(f'{v:064x}\n' for v in result))
(out/'crcs.mem').write_text(''.join(f'{v:08x}\n' for v in crcs))
(out/'reference.json').write_text(json.dumps({'image_size':[w,h],'synthetic_parameters':parameters,
    'purpose':'complete frame integration simulation; not actual camera calibration','crcs':crcs},indent=2)+'\n')
print('Generated three complete integer-Brown/bilinear/RGB565 frame references (identity, nonlinear, same-bank new frame).')
