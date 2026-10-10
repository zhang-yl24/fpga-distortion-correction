"""Receive CRC-verified raw OV5640 frames; save untouched pixels and metadata."""
from pathlib import Path
from datetime import datetime,timezone
import argparse
import json
import time
import zlib
from concurrent.futures import ThreadPoolExecutor
import cv2
import numpy as np
import serial
from frame_protocol import FrameParser

# A single worker already decouples detection from UART reception. Avoid
# multiplying native OpenCV worker pools inside the Python save thread.
cv2.setNumThreads(1)

def save(frame,directory):
    assert (frame.width,frame.height)==(640,480),'Unexpected capture mode'
    stamp=datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    stem=f'{stamp}-frame{frame.frame_id:08d}'
    pixels=np.frombuffer(frame.payload,dtype='<u2').reshape(frame.height,frame.width)
    # Match FPGA bit replication, not a colour correction or rescale.
    r=(pixels>>11)&31;g=(pixels>>5)&63;b=pixels&31
    image=np.stack(((b<<3)|(b>>2),(g<<2)|(g>>4),(r<<3)|(r>>2)),axis=-1).astype(np.uint8)
    ok,corners=cv2.findChessboardCornersSB(cv2.cvtColor(image,cv2.COLOR_BGR2GRAY),(9,6))
    directory.mkdir(parents=True,exist_ok=True)
    image_path=directory/f'{stem}.png';raw_path=directory/f'{stem}.rgb565'
    raw_path.write_bytes(frame.payload)
    success,encoded=cv2.imencode('.png',image);assert success;encoded.tofile(image_path)
    metadata={'captured_utc':datetime.now(timezone.utc).isoformat(),'frame_id':frame.frame_id,
        'provenance':'OV5640 camera2 native DVP -> frozen DDR -> binary UART',
        'width':640,'height':480,'format':'RGB565 little endian, bit replication to RGB888 PNG',
        'payload_bytes':len(frame.payload),'source_crc32':f'{frame.source_crc:08X}',
        'received_crc32':f'{zlib.crc32(frame.payload):08X}',
        'chessboard_inner_corners':[9,6],'chessboard_detected':bool(ok),
        'geometry_applied':False,'square_mm_nominal':20}
    if ok:
        xy=corners.reshape(-1,2);metadata.update(corner_count=len(xy),
            corner_bounds_pixels=[xy.min(axis=0).tolist(),xy.max(axis=0).tolist()],
            corners_pixels=xy.tolist())
        marked=image.copy();cv2.drawChessboardCorners(marked,(9,6),corners,ok)
        preview=directory.parent/'previews';preview.mkdir(parents=True,exist_ok=True)
        success,encoded=cv2.imencode('.png',marked);assert success;encoded.tofile(preview/f'{stem}-corners.png')
    (directory/f'{stem}.json').write_text(json.dumps(metadata,indent=2)+'\n')
    return {'image':str(image_path.resolve()),'raw':str(raw_path.resolve()),**metadata}

def main():
    a=argparse.ArgumentParser();a.add_argument('--port',default='COM5');a.add_argument('--baud',type=int,default=921600)
    a.add_argument('--frames',type=int,default=1);a.add_argument('--seconds',type=float,default=35)
    a.add_argument('--directory',type=Path,default=Path(__file__).resolve().parents[1]/'captures/calibration')
    a.add_argument('--summary',type=Path,default=Path(__file__).resolve().parents[1]/'results/calibration-capture-latest.json')
    args=a.parse_args();assert args.frames>0 and args.seconds>0
    parser=FrameParser();saved=[];seen=set();jobs=[];deadline=time.monotonic()+args.seconds
    def process(frame):
        result=save(frame,args.directory)
        print(json.dumps({'saved':result['image'],'frame_id':frame.frame_id,'crc32':result['received_crc32'],
              'corners':54 if result['chessboard_detected'] else 0}),flush=True)
        return result
    # Keep receiving while OpenCV detects corners/encodes PNG. A slow or
    # cornerless image must not starve the Windows UART driver and lose bytes.
    with ThreadPoolExecutor(max_workers=1) as workers:
        with serial.Serial(args.port,args.baud,timeout=.25,write_timeout=1,dsrdtr=False,rtscts=False,xonxoff=False) as port:
            if hasattr(port,'set_buffer_size'):port.set_buffer_size(rx_size=1048576,tx_size=4096)
            port.reset_input_buffer()
            while len(jobs)<args.frames and time.monotonic()<deadline:
                data=port.read(min(max(port.in_waiting,1),65536))
                for frame in parser.feed(data):
                    if frame.frame_id in seen:continue
                    seen.add(frame.frame_id);jobs.append(workers.submit(process,frame))
                    if len(jobs)>=args.frames:break
        saved=[job.result() for job in jobs]
    summary={'saved_frames':len(saved),'rejected_packets':parser.rejected,'discarded_stream_bytes':parser.discarded,
        'port':args.port,'baud':args.baud,'frames':saved}
    results=Path(__file__).resolve().parents[1]/'results';results.mkdir(exist_ok=True)
    args.summary.parent.mkdir(parents=True,exist_ok=True)
    args.summary.write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps({'saved_frames':len(saved),'rejected_packets':parser.rejected,'discarded_stream_bytes':parser.discarded}),flush=True)
    if len(saved)<args.frames:raise SystemExit('Timed out waiting for complete CRC-verified native frames')

if __name__=='__main__':main()
