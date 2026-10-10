"""Independent CRC packets and arbitrary-phase CORDIC golden pairs."""
from pathlib import Path
import binascii
import json
import sys
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
from model.rotation import phase_from_degrees,cordic
angles=[0,7.5,13.7,-23.45,89.99,90.01,137.25,179.999,-178.125,225.125,271.875,359.99,0.125,45.625,112.345,333.375]
phases=[phase_from_degrees(a) for a in angles]
work=root/'build/host_control_sim';work.mkdir(exist_ok=True)
def packet(phase,seq):
    body=bytes((1,1))+seq.to_bytes(2,'little')+phase.to_bytes(4,'little')
    return b'\xa5\x5a'+body+binascii.crc_hqx(body,0xffff).to_bytes(2,'little')
(work/'packets.mem').write_text('\n'.join(packet(p,i+1).hex() for i,p in enumerate(phases))+'\n')
all_phases=list(dict.fromkeys(phases+[(phases[-1]+i*0x15555555)&0xffffffff for i in range(1,14)]))
(work/'golden.mem').write_text('\n'.join(f'{p:08x}{co&0xffffffff:08x}{si&0xffffffff:08x}' for p in all_phases for co,si in [cordic(p)])+'\n')
(work/'counts.vh').write_text(f'`define HOST_GOLDEN {len(all_phases)}\n')
(work/'reference.json').write_text(json.dumps({'angles':angles,'phases':phases,'crc':'CRC16/CCITT-FALSE init=FFFF poly=1021, version through argument, little-endian wire CRC'},indent=2)+'\n')
print('Prepared 16 arbitrary-angle commands and independent CRC/CORDIC oracles.')
