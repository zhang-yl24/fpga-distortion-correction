from pathlib import Path
from frame_protocol import FrameParser
root=Path(__file__).resolve().parents[1];work=root/'build/corrected_capture_sim'
def load(name):
    return b''.join(int(line,16).to_bytes(32,'little') for line in (work/name).read_text().splitlines())
source=load('source.mem');golden=load('result.mem')
parser=FrameParser();frames=parser.feed((work/'export.bin').read_bytes())
assert len(frames)==6 and parser.rejected==0 and parser.discarded==0
assert [f.frame_id for f in frames]==list(range(2,8))
for raw,result in zip(frames[::2],frames[1::2]):
    assert (raw.width,raw.height,result.width,result.height)==(32,16,32,16)
    phases=[phase for phase in (1,2) if raw.payload==source[phase*1024:(phase+1)*1024]]
    assert len(phases)==1
    phase=phases[0];assert result.payload==golden[phase*1024:(phase+1)*1024]
print('PASS host independently parsed six UART packets: header/source/payload/trailer CRCs, paired IDs, all 1536 raw and 1536 corrected pixels matched.')
