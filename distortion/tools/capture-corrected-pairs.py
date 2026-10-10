"""CRC-checked physical raw/result pairs and independent host integer comparison."""
from pathlib import Path
from datetime import datetime,timezone
import argparse
import hashlib
import json
import re
import os
import subprocess
import sys
import time
import zlib
import cv2
import numpy as np
import serial
from frame_protocol import FrameParser

root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root))
from model.reference import remap_fixed
cv2.setNumThreads(1)

def expand(raw,width,height):
    pixels=np.frombuffer(raw,dtype='<u2').reshape(height,width)
    r=(pixels>>11)&31;g=(pixels>>5)&63;b=pixels&31
    return np.stack(((r<<3)|(r>>2),(g<<2)|(g>>4),(b<<3)|(b>>2)),axis=-1).astype(np.uint8)

def png(path,rgb):
    ok,buf=cv2.imencode('.png',rgb[...,::-1]);assert ok;buf.tofile(path)

def reference(payload,q):
    image=expand(payload,640,480)
    rgb=remap_fixed(image,q[...,0]/256,q[...,1]/256)
    raw=(((rgb[...,0].astype(np.uint16)>>3)<<11)|((rgb[...,1].astype(np.uint16)>>2)<<5)|(rgb[...,2].astype(np.uint16)>>3)).astype('<u2')
    return raw

def main():
    a=argparse.ArgumentParser();a.add_argument('--port',default='COM5');a.add_argument('--pairs',type=int,default=2)
    a.add_argument('--seconds',type=float,default=24)
    a.add_argument('--report',type=Path);args=a.parse_args()
    if not 1<=args.seconds<=24:raise ValueError('Laboratory capture must finish within 24 seconds before idle')
    candidate=root/'results/calibration-fpga-candidate-20261006'
    config=json.loads((candidate/'candidate.json').read_text())
    header=(root/'board/calibration-trial.vh').read_text()
    vals=[]
    for bits,value in re.findall(r"=(24|32)'sh([0-9a-fA-F]+);",header):
        n=int(value,16);n=n-(1<<int(bits)) if n>>(int(bits)-1) else n;vals.append(n)
    assert vals==config['integer_config'],'Staged source coefficients differ from host candidate'
    q=np.fromfile(candidate/'coordinates-q8.bin',dtype='<i4').reshape(480,640,2)
    manifest=json.loads((root/'build/corrected_capture/validated-build.json').read_text(encoding='utf-8-sig'))
    bit=Path(manifest['Bitstream']);assert hashlib.sha256(bit.read_bytes()).hexdigest().upper()==manifest['SHA256']
    status=json.loads((root/'status.json').read_text(encoding='utf-8-sig'))
    assert status['current_sram_target']=='corrected_capture','Program the guarded capture target before receiving binary frames'
    assert status['current_connection']['last_programmed_sha256']==manifest['SHA256'],'Active bitstream differs from capture manifest'
    out=root/'captures/corrected-pairs'/datetime.now().strftime('%Y%m%d-%H%M%S');out.mkdir(parents=True)
    parser=FrameParser();sources={};pairs=[];packet_ids=[];deadline=time.monotonic()+args.seconds
    with CoolingBoundary(out), serial.Serial(args.port,921600,timeout=.25,dsrdtr=False,rtscts=False,xonxoff=False) as port:
        if hasattr(port,'set_buffer_size'):port.set_buffer_size(rx_size=1048576,tx_size=4096)
        port.reset_input_buffer()
        while len(pairs)<args.pairs and time.monotonic()<deadline:
            for frame in parser.feed(port.read(min(max(port.in_waiting,1),65536))):
                assert (frame.width,frame.height)==(640,480)
                packet_ids.append(frame.frame_id)
                if frame.frame_id%2==0:
                    sources[frame.frame_id//2]=frame
                    print(json.dumps({'received':'raw','pair_id':frame.frame_id//2,'crc32':f'{frame.source_crc:08X}'}),flush=True)
                    continue
                pair_id=frame.frame_id//2
                if pair_id not in sources:continue # opened during earlier raw packet
                raw=sources.pop(pair_id)
                expected=reference(raw.payload,q)
                actual=np.frombuffer(frame.payload,dtype='<u2').reshape(480,640)
                mismatch=actual!=expected
                folder=out/f'pair{pair_id:08d}';folder.mkdir()
                (folder/'raw-source.rgb565').write_bytes(raw.payload)
                (folder/'fpga-corrected.rgb565').write_bytes(frame.payload)
                (folder/'software-reference.rgb565').write_bytes(expected.tobytes())
                raw_rgb=expand(raw.payload,640,480);actual_rgb=expand(frame.payload,640,480)
                expected_rgb=expand(expected.tobytes(),640,480)
                png(folder/'raw-source.png',raw_rgb);png(folder/'fpga-corrected.png',actual_rgb);png(folder/'software-reference.png',expected_rgb)
                difference=np.abs(actual_rgb.astype(np.int16)-expected_rgb.astype(np.int16))
                record={'pair_id':pair_id,'source_packet_id':raw.frame_id,'result_packet_id':frame.frame_id,
                        'raw_crc32':f'{raw.source_crc:08X}','fpga_crc32':f'{frame.source_crc:08X}',
                        'software_crc32':f'{zlib.crc32(expected.tobytes()):08X}',
                        'pixels_compared':307200,'mismatched_pixels':int(mismatch.sum()),
                        'max_rgb_channel_difference':int(difference.max()),
                        'different_from_passthrough_pixels':int(np.count_nonzero(actual!=np.frombuffer(raw.payload,dtype='<u2').reshape(480,640))),
                        'directory':str(folder.resolve())}
                (folder/'comparison.json').write_text(json.dumps(record,indent=2)+'\n')
                pairs.append(record);print(json.dumps(record),flush=True)
                if len(pairs)>=args.pairs:break
    result={'recorded_utc':datetime.now(timezone.utc).isoformat(),'target':'corrected_capture','bitstream_sha256':manifest['SHA256'],
            'pairs':pairs,'packet_ids':packet_ids,'rejected_packets':parser.rejected,'discarded_stream_bytes':parser.discarded,
            'passed':len(pairs)==args.pairs and parser.rejected==0 and all(p['mismatched_pixels']==0 and p['different_from_passthrough_pixels']>100 for p in pairs),
            'coordinates_sha256':hashlib.sha256((candidate/'coordinates-q8.bin').read_bytes()).hexdigest(),
            'limits':'Actual FPGA pixels versus same-frame integer reference of bounded radial approximation, matched K, no rotation. Does not establish optical calibration accuracy or realtime frame rate; UART exports are validation only.'}
    (out/'summary.json').write_text(json.dumps(result,indent=2)+'\n')
    report=args.report or root/'results'/('corrected-pair-check-'+datetime.now().strftime('%Y%m%d')+'.json')
    report.parent.mkdir(parents=True,exist_ok=True)
    report.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'passed':result['passed'],'pairs':len(pairs),'directory':str(out.resolve())}),flush=True)
    if not result['passed']:raise SystemExit('Same-frame FPGA pixel validation did not pass; inspect preserved report')

class CoolingBoundary:
    """Close serial first, then replace SRAM even on a packet/read failure."""
    def __init__(self,output):self.output=output
    def __enter__(self):return self
    def __exit__(self,*exception):
        # Python launched from PowerShell 7 inherits its module lookup path.
        # Let Windows PowerShell 5 initialize its own built-in module paths.
        task_env={k:v for k,v in os.environ.items() if k.upper()!='PSMODULEPATH'}
        with (self.output/'idle-after-capture.log').open('w',encoding='utf-8') as log:
            process=subprocess.run(['powershell','-NoProfile','-ExecutionPolicy','Bypass','-File',str(root/'tools/program-heartbeat.ps1'),'-Target','heartbeat','-Frequency','5MHz'],stdout=log,stderr=subprocess.STDOUT,timeout=90,env=task_env)
        if process.returncode:raise RuntimeError('Capture ended but idle transfer failed; inspect idle-after-capture.log')
        status=json.loads((root/'status.json').read_text(encoding='utf-8-sig'))
        proofs=sorted((root/'build/heartbeat').glob('program-evidence-*/transfer.json'),key=lambda p:p.stat().st_mtime)
        proof=json.loads(proofs[-1].read_text(encoding='utf-8-sig'))
        assert proof['Done'] and proof['Target']=='heartbeat' and status['current_sram_target']=='heartbeat'
        assert proof['CheckedOn']==status['current_connection']['checked_on']
        (self.output/'idle-after-capture.json').write_text(json.dumps(proof,indent=2)+'\n')
        print('Capture finished: verified low-load heartbeat, DDR/remap/video stopped.',flush=True)

if __name__=='__main__':main()
