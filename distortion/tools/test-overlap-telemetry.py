"""Exercise new cumulative diagnostics against an actual saved UART capture."""
from pathlib import Path
import copy,importlib.util,json,re
root=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('overlap',root/'tools/analyze-overlap-telemetry.py')
overlap=importlib.util.module_from_spec(spec);spec.loader.exec_module(overlap)
base=json.loads((root/'results/lab-20261007/early-zero-telemetry-timed.json').read_text(encoding='utf-8-sig'))
for i,sample in enumerate(base['Samples']):
    oc=(0xE0000000+i*100000000)&0xFFFFFFFF
    sample['Line']+=f' OC={oc:08X} CC=00A00000 BW={i*20000000:08X} SP=00A76B68'
assert any('OC=00' in s['Line'] or 'OC=01' in s['Line'] for s in base['Samples']) or any(int(re.search(r'OC=([0-9A-F]+)',s['Line'])[1],16)<0x20000000 for s in base['Samples'])
assert overlap.analyze(base)['passed']
def rejected(change):
    case=copy.deepcopy(base);change(case)
    try:overlap.analyze(case)
    except ValueError:return
    raise AssertionError('Malformed scheduling evidence accepted')
def field(case,key,value):
    case['Samples'][-1]['Line']=re.sub(r'\b'+key+r'=[0-9A-F]+',key+'='+value,case['Samples'][-1]['Line'])
rejected(lambda c:field(c,'OC','00000000'))
rejected(lambda c:field(c,'BW','FFFFFFFF'))
rejected(lambda c:field(c,'SP','00000000'))
rejected(lambda c:field(c,'CC','FFFFFFFF'))
rejected(lambda c:c['Samples'][-1].update(Line=c['Samples'][-1]['Line']+' OC=00000000'))
rejected(lambda c:c['Samples'][-1].update(Line=re.sub(r' OC=[0-9A-F]+','',c['Samples'][-1]['Line'])))
rejected(lambda c:c['Samples'][-1].update(ReceivedUtc=c['Samples'][-2]['ReceivedUtc']))
for sample in (zero:=copy.deepcopy(base))['Samples']:
    sample['Line']=re.sub(r'OC=[0-9A-F]+','OC=00000001',sample['Line'])
try:overlap.analyze(zero)
except ValueError:pass
else:raise AssertionError('Zero overlap accepted')
print('PASS: valid wrap, reset/jump, invalid intervals, duplicate/missing fields, timestamp and zero-overlap rejection. Hardware was not accessed.')
