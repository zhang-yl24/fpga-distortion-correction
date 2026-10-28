"""Audit synthetic full720 raw wire independently, then use frozen host parser."""
from pathlib import Path
import argparse
import hashlib
import json
import struct
import sys
import zlib
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from frame_protocol import FrameParser


def audit(work):
    work = Path(work).resolve()
    approved = (ROOT/'build/offline-20261024').resolve()
    if not work.is_relative_to(approved) or not work.is_dir():
        raise ValueError('audit output must remain in existing approved scratch')
    path = work/'raw-camera-capture-720-synthetic-stream.bin'
    wire = path.read_bytes()
    if len(wire) != 1843244:
        raise ValueError('complete720 packet length differs')
    magic, width, height, frame_id, count, source_crc, fmt, header_crc = struct.unpack('<8sHHIIIII', wire[:32])
    if ((magic,width,height,frame_id,count,fmt) != (b'PGFRAME1',1280,720,41,1843200,0x5651)
            or zlib.crc32(wire[:28]) != header_crc):
        raise ValueError('manual720 raw header/CRC differs')
    payload = wire[32:32+count]
    if (wire[32+count:40+count] != b'PGEND001' or
            zlib.crc32(payload) != source_crc or struct.unpack_from('<I',wire,40+count)[0] != source_crc):
        raise ValueError('manual720 payload/trailer CRC differs')
    # Independent vector arithmetic, without importing an HDL test generator.
    pixels = np.frombuffer(payload, dtype='<u2')
    expected = ((np.arange(921600,dtype=np.uint32)*53)^0x4321).astype(np.uint16)
    if not np.array_equal(pixels,expected):
        raise ValueError('one or more of921600 pixels differ from the known source')
    parser = FrameParser()
    frames = []
    for start in range(0,len(wire),4093):
        frames.extend(parser.feed(wire[start:start+4093]))
    if (len(frames) != 1 or parser.rejected or parser.discarded or parser.buffer or
            frames[0].payload != payload or
            (frames[0].width,frames[0].height,frames[0].frame_id,frames[0].source_crc) != (width,height,frame_id,source_crc)):
        raise ValueError('unmodified host FrameParser does not recover the exact complete720 frame')
    sha = lambda file: hashlib.sha256(Path(file).read_bytes()).hexdigest()
    prepared_path = ROOT/'board/raw_camera_capture_cam2_guarded-sources.json'
    prepared = json.loads(prepared_path.read_text(encoding='utf-8-sig'))
    if len(prepared['SourceSHA256']) != 107:
        raise ValueError('main source107 closure differs')
    for name,digest in prepared['SourceSHA256'].items():
        if sha(ROOT/name) != digest.lower():
            raise ValueError('frozen main source changed: '+name)
    result = dict(schema=1,passed=True,synthetic_only=True,hardware_accessed=False,PDS_accessed=False,
                  width=width,height=height,pixels=921600,payload_bytes=count,wire_bytes=len(wire),
                  DDR_write_beats=57600,DDR_read_beats=57600,
                  all_pixels_exact_known_pattern=True,manual_header_payload_trailer_CRC32_passed=True,
                  source_crc32=f'{source_crc:08X}',wire_sha256=sha(path),payload_sha256=hashlib.sha256(payload).hexdigest(),
                  unmodified_host_parser_exact_recovery=True,host_parser_rejected=parser.rejected,
                  host_parser_discarded=parser.discarded,host_parser_remaining=len(parser.buffer),
                  host_parser_source_sha256=sha(ROOT/'tools/frame_protocol.py'),main_source107_unchanged=True,
                  prepared_source_manifest_sha256=sha(prepared_path),audit_source_sha256=sha(__file__),
                  limits='Full digital1280x720 data capacity only. Synthetic DVP and deterministic DDR model, abstract byte-ready sink. No720 sensor configuration, real PCLK/input timing, camera cadence/fps, physical pin or board acceptance, optics, stereo, corrected-image throughput, or UART real-time video claim. Actual921600baud8N1 full-frame export is nominally at least20seconds.')
    output = work/'independent-720-digital-wire-audit.json'
    with output.open('x',encoding='utf-8') as stream:
        json.dump(result,stream,indent=2,allow_nan=False)
        stream.write('\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('workdir')
    args = parser.parse_args()
    result = audit(args.workdir)
    print(json.dumps({key:result[key] for key in ('passed','pixels','payload_bytes','wire_bytes','source_crc32','wire_sha256')}))
