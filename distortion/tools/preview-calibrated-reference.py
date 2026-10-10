"""Render an explicitly labelled CPU reference; never call it FPGA output."""
from pathlib import Path
import argparse
import json
import sys
import cv2
import numpy as np

root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
from model.reference import remap_fixed

parser=argparse.ArgumentParser();parser.add_argument('image',type=Path)
parser.add_argument('--candidate',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args();metadata=json.loads((args.candidate/'candidate.json').read_text());assert metadata['passed']
w,h=metadata['image_size'];image=cv2.imdecode(np.fromfile(args.image,dtype=np.uint8),cv2.IMREAD_COLOR)
assert image.shape==(h,w,3)
q=np.fromfile(args.candidate/'coordinates-q8.bin',dtype='<i4').reshape(h,w,2)
corrected=remap_fixed(image,q[...,0]/256,q[...,1]/256)
# The result frame writer reduces interpolated RGB888 to RGB565. Expand it
# again by the same bit replication used by the HDMI output for the preview.
b=corrected[...,0]>>3;g=corrected[...,1]>>2;r=corrected[...,2]>>3
corrected=np.stack(((b<<3)|(b>>2),(g<<2)|(g>>4),(r<<3)|(r>>2)),axis=-1)
canvas=np.full((h+46,w*2,3),255,dtype=np.uint8)
canvas[46:,:w]=image;canvas[46:,w:]=corrected
cv2.putText(canvas,'Original native camera frame',(12,27),cv2.FONT_HERSHEY_SIMPLEX,.6,(0,0,0),1,cv2.LINE_AA)
cv2.putText(canvas,'CPU integer reference - NOT FPGA output',(w+12,27),cv2.FONT_HERSHEY_SIMPLEX,.6,(0,0,0),1,cv2.LINE_AA)
args.output.parent.mkdir(parents=True,exist_ok=True);cv2.imencode('.png',canvas)[1].tofile(args.output)
args.output.with_suffix('.json').write_text(json.dumps({'source_image':str(args.image.resolve()),
    'candidate':str(args.candidate.resolve()),'rendered_by':'CPU integer bilinear reference + RGB565 quantization',
    'hardware_output':False,'image_was_used_for_calibration':True},indent=2)+'\n')
print(str(args.output.resolve()))
