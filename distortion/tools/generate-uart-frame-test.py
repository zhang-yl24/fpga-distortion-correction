from pathlib import Path
import zlib
import numpy as np
from frame_protocol import encode
root=Path(__file__).resolve().parents[1];work=root/'build/uart_frame_sim';work.mkdir(parents=True,exist_ok=True)
packets=[];beats=[];crcs=[]
for ident in (1,2,3):
    rng=np.random.default_rng(0xF000+ident)
    payload=rng.integers(0,256,size=2048,dtype=np.uint8).tobytes()
    packets.extend(encode(32,32,ident,payload));crcs.append(zlib.crc32(payload))
    beats.extend(int.from_bytes(payload[i:i+32],'little') for i in range(0,len(payload),32))
(work/'packets.mem').write_text('\n'.join(f'{v:02x}' for v in packets)+'\n')
(work/'beats.mem').write_text('\n'.join(f'{v:064x}' for v in beats)+'\n')
(work/'crcs.mem').write_text('\n'.join(f'{v:08x}' for v in crcs)+'\n')
print('Generated three native source frames and independent zlib packet/header/payload CRC32 goldens.')
