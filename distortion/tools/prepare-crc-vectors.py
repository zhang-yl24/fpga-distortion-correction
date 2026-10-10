from pathlib import Path
import random,binascii
root=Path(__file__).resolve().parents[1]
dest=root/'build/live_crc_sim';dest.mkdir(parents=True,exist_ok=True)
rng=random.Random(20261006);lines=[];stream=b''
for i in range(256):
    if i%4==0:stream=b''
    block=bytes(rng.randrange(256) for _ in range(32));stream+=block
    expected=binascii.crc32(stream)&0xffffffff
    lines.append(f'{expected:08x}{int.from_bytes(block,"little"):064x}')
(dest/'vectors.hex').write_text('\n'.join(lines)+'\n')
print('Generated 256 independent Python CRC32 prefix vectors (64 four-beat streams).')
