from pathlib import Path
import struct,zlib
ROOT=Path(__file__).resolve().parent
def packet(magic,ticket,nonce,version=1,length=24):
    body=magic+struct.pack('<BBHIII',version,1,length,ticket,nonce,0)
    return body+struct.pack('<I',zlib.crc32(body))
packets={'ARM_A':packet(b'SGA1',0x01020304,0x31544753),
         'ARM_B':packet(b'SGA1',0x11223344,0x55667788),
         'STAT_A':packet(b'SGT1',0x31414753,1),
         'STAT_B':packet(b'SGT1',0x88776655,0x44332211),
         'BAD_ARM_SCHEMA':packet(b'SGA1',0x01020304,0x31544753,version=2),
         'BAD_STAT_SCHEMA':packet(b'SGT1',0x31414753,1,length=20)}
for kind in ['ARM','STAT']:
    b=bytearray(packets[kind+'_A']);b[-1]^=1;packets['BAD_'+kind+'_CRC']=bytes(b)
out=['// Python zlib CRC32, exact original24B SGA1/SGT1 schema.']
for name,data in packets.items():
    assert len(data)==24
    out.append(f"localparam [191:0] {name}=192'h{int.from_bytes(data,'little'):048x};")
(ROOT/'tests').mkdir(exist_ok=True)
(ROOT/'tests/packets.vh').write_text('\n'.join(out)+'\n',encoding='utf-8')
