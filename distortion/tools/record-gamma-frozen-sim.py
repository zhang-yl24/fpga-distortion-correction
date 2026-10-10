"""Independently validate complete serialized same-source triplets and CRCs."""
from pathlib import Path
import argparse,hashlib,json,subprocess,sys
from frame_protocol import FrameParser
from gamma_triplets import GammaTripletAssembler
parser=argparse.ArgumentParser();parser.add_argument('--native',action='store_true');parser.add_argument('--work-name');parser.add_argument('--lab-date',default='20261007');args=parser.parse_args()
assert args.lab_date.isdigit() and len(args.lab_date)==8
root=Path(__file__).resolve().parents[1];work=root/'build'/(args.work_name or ('gamma_frozen_native_sim' if args.native else 'gamma_frozen_capture_sim'));lab=root/'results'/('lab-'+args.lab_date);lab.mkdir(exist_ok=True)
assert work.resolve().parent==(root/'build').resolve()
read=lambda path:json.loads(path.read_text(encoding='utf-8-sig'))
proof=read(work/'start-proof.json')
for path,digest in proof['source_sha256'].items():assert hashlib.sha256((root/path).read_bytes()).hexdigest().upper()==digest
def payload(name):return b''.join(int(row,16).to_bytes(32,'little') for row in (work/name).read_text().splitlines())
source,before,after=[payload(name) for name in ('source.mem','result.mem','tone.mem')]
ref=read(work/'reference.json');parser=FrameParser();frames=parser.feed((work/'export.bin').read_bytes());size=ref['shape'][0]*ref['shape'][1]*2
assert len(frames)==9 and parser.rejected==0 and parser.discarded==0
assembler=GammaTripletAssembler();triplets=[]
for frame in frames:
    triplet=assembler.feed(frame)
    if triplet:triplets.append(triplet)
assembler.finish();assert len(triplets)==3 and assembler.incomplete_groups==0 and assembler.orphan_packets==0
for phase,scene in enumerate(ref['frames']):
    triple=frames[phase*3:(phase+1)*3];group=phase+1
    assert [f.frame_id for f in triple]==[group<<4,(group<<4)|1,(group<<4)|(scene['mode']<<2)|2]
    for frame,expected,crc in zip(triple,(source,before,after),scene['crcs']):
        assert (frame.height,frame.width)==tuple(ref['shape'])
        assert frame.payload==expected[phase*size:(phase+1)*size] and frame.source_crc==crc
log=(work/'simulation.log').read_text();assert ('PASS native frozen Gamma capture:' if args.native else 'PASS frozen Gamma capture:') in log and 'Fatal:' not in log
test=subprocess.run([sys.executable,str(root/'tests/test_gamma_triplets.py')],capture_output=True,text=True)
(work/'host-tests.log').write_text(test.stdout+test.stderr,encoding='utf-8');assert test.returncode==0 and 'Ran 9 tests' in test.stderr
hashes={**proof['source_sha256'],**{name:hashlib.sha256((root/name).read_bytes()).hexdigest().upper() for name in ('tools/gamma_triplets.py','tools/frame_protocol.py','tools/record-gamma-frozen-sim.py','tests/test_gamma_triplets.py')}}
result={'passed':True,'hardware_accessed':False,'work_directory':str(work),'radius_guard':ref.get('radius_guard',0),'groups':3,'uart_packets':9,'pixels_compared':size//2*9,'shape':ref['shape'],'modes':[1,2,0],'host_parser_tests_passed':9,
    'artifacts_sha256':{name:hashlib.sha256((work/name).read_bytes()).hexdigest().upper() for name in ('export.bin','simulation.log','start-proof.json')},
    'same_source_and_export_bank_immutability':True,'two_bypass_statistic_warmup_passes':True,
    'source_sha256':hashes,'limits':'Synthetic frozen-source prototype only. Two warmup passes repeat one frozen source to establish controlled before/after statistics; they do not represent live scene adaptation time. No board target, final timing or physical optical benefit claim.'}
(lab/('gamma-frozen-native-simulation-check.json' if args.native else 'gamma-frozen-capture-simulation-check.json')).write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps({key:result[key] for key in ('passed','groups','uart_packets','pixels_compared','modes','host_parser_tests_passed')}))
