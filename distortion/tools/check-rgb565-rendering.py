"""Exhaustively compare host image encoding with HDMI RGB565 bit expansion."""
from pathlib import Path
import hashlib,json
import cv2
import numpy as np
from PIL import Image
from frozen_gamma_analysis import metrics
ROOT=Path(__file__).resolve().parents[1]

def main():
    # Independent scalar-bit concatenation equivalent to camera_preview.v.
    pixels=np.arange(65536,dtype=np.uint16).reshape(256,256)
    expected=np.empty((256,256,3),dtype=np.uint8)
    for n in range(65536):
        expected[n//256,n%256]=( ((n>>11)&31)*8+((n>>13)&7),
            ((n>>5)&63)*4+((n>>9)&3), (n&31)*8+((n>>2)&7) )
    rgb=metrics.expand(pixels).astype(np.uint8)
    if not np.array_equal(rgb,expected):raise ValueError('Host RGB differs from HDMI concatenation')
    directory=ROOT/'build/rgb565_rendering_check';directory.mkdir(exist_ok=True)
    encoded_ok,png=cv2.imencode('.png',rgb[...,::-1])
    if not encoded_ok:raise ValueError('PNG encoding failed')
    path=directory/'all-rgb565.png';png.tofile(path)
    # A different decoder reads actual PNG RGB bytes, independent of OpenCV BGR.
    decoded=np.asarray(Image.open(path).convert('RGB'))
    if not np.array_equal(decoded,expected):raise ValueError('PNG color channels or values changed')
    verified=[]
    for label in ('physical-bright-20261008','physical-bright-warmed-20261008','physical-dark-warmed-20261008'):
        folder=ROOT/'captures/gamma-triplets'/label/'group-00000001'
        metadata=json.loads((folder/'comparison.json').read_text())
        for name in ('raw','before','after'):
            npy,png_path=folder/(name+'.npy'),folder/(name+'.png')
            for file in (npy,png_path):
                if hashlib.sha256(file.read_bytes()).hexdigest()!=metadata['files_sha256'][file.name]:
                    raise ValueError('Physical image file differs from capture proof')
            rgb=metrics.expand(np.load(npy,allow_pickle=False)).astype(np.uint8)
            if not np.array_equal(np.asarray(Image.open(png_path).convert('RGB')),rgb):
                raise ValueError('Physical PNG differs from captured RGB565')
            verified.append(str(png_path.relative_to(ROOT)))
    result={'passed':True,'hardware_accessed':False,'rgb565_values_tested':65536,
        'png_decoder':'Pillow RGB; encoder OpenCV BGR','physical_png_files_verified':verified,
        'source_sha256':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest().upper() for p in (
            'tools/check-rgb565-rendering.py','tools/evaluate-tone-pair.py','rtl/camera_preview.v')},
        'limits':'Proves host integer expansion and PNG roundtrip match the HDL concatenation, not physical HDMI transmitter/monitor colorimetry. Frozen export and live preview are different times and sample grids.'}
    (ROOT/'results/lab-20261008/rgb565-rendering-check.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'passed':True,'all_rgb565':65536,'physical_png_files':len(verified)}))

if __name__=='__main__':main()
