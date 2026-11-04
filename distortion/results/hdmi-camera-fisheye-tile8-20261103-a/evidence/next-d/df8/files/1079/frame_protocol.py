"""Bounded, resynchronizing parser for CRC-protected native RGB565 frames."""
from dataclasses import dataclass
import struct
import zlib

MAGIC=b'PGFRAME1';END=b'PGEND001';FORMAT=0x5651
HEADER=struct.Struct('<8sHHIIIII')
@dataclass
class Frame:
    width:int
    height:int
    frame_id:int
    source_crc:int
    payload:bytes

class FrameParser:
    def __init__(self):self.buffer=bytearray();self.rejected=0;self.discarded=0
    def feed(self,data):
        self.buffer.extend(data);frames=[]
        while True:
            where=self.buffer.find(MAGIC)
            if where<0:
                discard=max(0,len(self.buffer)-7);self.discarded+=discard;del self.buffer[:discard];break
            if where:self.discarded+=where;del self.buffer[:where]
            if len(self.buffer)<32:break
            magic,w,h,ident,count,source,fmt,header_crc=HEADER.unpack(self.buffer[:32])
            if not(0<w<=1920 and 0<h<=1080 and count==w*h*2 and fmt==FORMAT and
                   zlib.crc32(self.buffer[:28])==header_crc):
                self.rejected+=1;del self.buffer[0];continue
            total=32+count+12
            if len(self.buffer)<total:break
            payload=bytes(self.buffer[32:32+count]);trailer=self.buffer[32+count:total]
            computed=zlib.crc32(payload)
            if trailer[:8]!=END or struct.unpack('<I',trailer[8:])[0]!=computed or source!=computed:
                self.rejected+=1;del self.buffer[0];continue
            frames.append(Frame(w,h,ident,source,payload));del self.buffer[:total]
        return frames

def encode(width,height,ident,payload):
    assert len(payload)==width*height*2
    crc=zlib.crc32(payload)
    head=struct.pack('<8sHHIIII',MAGIC,width,height,ident,len(payload),crc,FORMAT)
    return head+struct.pack('<I',zlib.crc32(head))+payload+END+struct.pack('<I',crc)
