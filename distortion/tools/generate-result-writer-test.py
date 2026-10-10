"""Independent zlib/RGB bit extraction references for corrected frame storage."""
from pathlib import Path
import random
import struct
import zlib

out=Path(__file__).resolve().parents[1]/'build/frame_store_sim'
out.mkdir(parents=True,exist_ok=True)
rng=random.Random(0x20261006)
pixels=[rng.getrandbits(24) for _ in range(1536)]
pixels[:8]=[0,0xffffff,0xff0000,0x00ff00,0x0000ff,0x7f7f7f,0x010101,0x080408]
raws=[b''.join(struct.pack('<H',((p>>19)<<11)|(((p>>10)&63)<<5)|((p>>3)&31))
      for p in pixels[i*512:(i+1)*512]) for i in range(3)]
(out/'pixels.mem').write_text(''.join(f'{p:06x}\n' for p in pixels))
(out/'beats.mem').write_text(''.join(f'{int.from_bytes(raw[i:i+32],"little"):064x}\n'
                                  for raw in raws for i in range(0,len(raw),32)))
(out/'crcs.mem').write_text(''.join(f'{zlib.crc32(raw):08x}\n' for raw in raws))
print('Generated 1536 independent RGB888->RGB565 pixels and three zlib CRC32 values.')
