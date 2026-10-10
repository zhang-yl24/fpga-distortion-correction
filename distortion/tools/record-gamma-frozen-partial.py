"""Seal only complete packets/groups of an unfinished native simulation.

Never upgrades an incomplete overall regression to PASS. The source snapshot
and immutable prefix are saved so the exact validated scope remains reviewable.
"""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json
from frame_protocol import FrameParser
from gamma_triplets import GammaTripletAssembler
root=Path(__file__).resolve().parents[1];work=root/'build/gamma_frozen_native_sim';lab=root/'results/lab-20261007'
read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
proof=read(work/'start-proof.json');reference=read(work/'reference.json')
for name,digest in proof['source_sha256'].items():assert hashlib.sha256((root/name).read_bytes()).hexdigest().upper()==digest
data=(work/'export.bin').read_bytes();log=(work/'simulation.log').read_text();assert 'Fatal:' not in log
parser=FrameParser();frames=parser.feed(data);assembler=GammaTripletAssembler();groups=[]
assert parser.rejected==0 and parser.discarded==0
size=reference['shape'][0]*reference['shape'][1]*2
payloads=[b''.join(int(row,16).to_bytes(32,'little') for row in (work/name).read_text().splitlines()) for name in ('source.mem','result.mem','tone.mem')]
for frame in frames:
    group,kind,mode=frame.frame_id>>4,frame.frame_id&3,(frame.frame_id>>2)&3;phase=group-1
    assert 0<=phase<3 and kind in (0,1,2)
    assert (frame.height,frame.width)==tuple(reference['shape'])
    assert frame.payload==payloads[kind][phase*size:(phase+1)*size]
    assert frame.source_crc==reference['frames'][phase]['crcs'][kind]
    assert mode==(reference['frames'][phase]['mode'] if kind==2 else 0)
    complete=assembler.feed(frame)
    if complete:groups.append({'group_id':complete.group_id,'mode':complete.mode})
folder=lab/'gamma-frozen-native-partial';folder.mkdir(exist_ok=True)
# Keep only complete packet prefix, excluding a UART packet still being written.
prefix=b''.join(data[offset:offset+size+44] for offset in range(0,len(frames)*(size+44),size+44))
(folder/'complete-packets.bin').write_bytes(prefix);(folder/'simulation-partial.log').write_text(log)
(folder/'start-proof.json').write_text(json.dumps(proof,indent=2)+'\n')
result={'recorded_utc':datetime.now(timezone.utc).isoformat(),'hardware_accessed':False,
    'overall_regression_complete':False,'complete_packets_validated':len(frames),
    'complete_triplets_validated':len(groups),'complete_triplets':groups,
    'complete_packet_pixels_validated':len(frames)*size//2,'source_sha256':proof['source_sha256'],
    'prefix_sha256':hashlib.sha256(prefix).hexdigest().upper(),
    'limits':'Only complete serialized prefix packets were checked against independent pixel references and CRC. Remaining packets/scene modes and full RTL termination have not passed. An incomplete overall regression must not be reported as PASS.'}
(lab/'gamma-frozen-native-partial-check.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({key:result[key] for key in ('overall_regression_complete','complete_packets_validated','complete_triplets_validated','complete_packet_pixels_validated')}))
