import importlib.util
from pathlib import Path
import sys
import zlib

spec=importlib.util.spec_from_file_location('frame_protocol',Path(__file__).resolve().parents[1]/'tools/frame_protocol.py')
protocol=importlib.util.module_from_spec(spec);sys.modules[spec.name]=protocol;spec.loader.exec_module(protocol)

def test_fragmented_stream_recovers_after_metadata_and_payload_corruption():
    data=bytes(range(256))*8
    good=protocol.encode(32,32,17,data)
    bad_header=bytearray(good);bad_header[12]^=0x40
    bad_data=bytearray(good);bad_data[700]^=1
    stream=b'started-mid-packet'+bad_header+bad_data+good+protocol.encode(32,32,18,data[::-1])
    p=protocol.FrameParser();frames=[]
    for offset in range(0,len(stream),37):frames.extend(p.feed(stream[offset:offset+37]))
    assert [f.frame_id for f in frames]==[17,18]
    assert [f.payload for f in frames]==[data,data[::-1]]
    assert p.rejected==2 and len(p.buffer)<=7
    assert frames[0].source_crc==zlib.crc32(data)

def test_invalid_size_does_not_reserve_unbounded_buffer():
    header=bytearray(protocol.encode(1,1,1,b'\0\0')[:32])
    header[16:20]=b'\xff'*4
    header[28:32]=zlib.crc32(header[:28]).to_bytes(4,'little')
    p=protocol.FrameParser();assert p.feed(header+b'x'*20000)==[]
    assert len(p.buffer)<=7 and p.rejected==1

def test_truncated_packet_and_bad_trailer_are_never_saved():
    packet=protocol.encode(32,32,1,bytes(range(256))*8)
    p=protocol.FrameParser();assert p.feed(packet[:-1])==[]
    assert len(p.feed(packet[-1:]))==1
    bad=bytearray(packet);bad[-12]^=1
    assert p.feed(bad)==[] and p.rejected==1
