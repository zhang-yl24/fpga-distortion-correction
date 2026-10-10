"""Finite hardware run; correction count differs from HDMI refresh count."""
from pathlib import Path
from datetime import datetime
import argparse
import json
import re
import shutil
import statistics
root=Path(__file__).resolve().parents[1]
a=argparse.ArgumentParser();a.add_argument('--warmup',type=float,default=4)
a.add_argument('--target',choices=('corrected_video','corrected_fast'),default='corrected_video')
a.add_argument('--output',type=Path)
args=a.parse_args()
work=root/'build'/args.target
capture=json.loads((work/'telemetry-timed.json').read_text(encoding='utf-8-sig'))
samples=[];all_records=[]
for sample in capture['Samples']:
    fields={k:int(v,16) for k,v in re.findall(r'(\w+)=([0-9A-F]+)',sample['Line'])}
    required={'CAM','E','I','H','D','V','WF','CF','PF','UF','MF','OW','X','CS','RC','RS','PS','CY','HT','MS'}
    assert required<=fields.keys(),sample
    stamp=datetime.fromisoformat(sample['ReceivedUtc']);all_records.append((stamp,fields))
    for name in ('UF','MF','OW','X'):assert fields[name]==0,sample
    elapsed=(stamp-datetime.fromisoformat(capture['StartedUtc'])).total_seconds()
    if elapsed>=args.warmup:samples.append((stamp,fields))
assert len(samples)>=6,'Need six complete post-warmup samples'
for stamp,fields in samples:
    for k,v in {'CAM':0x5640,'E':0,'I':1,'H':1,'D':1,'V':1}.items():assert fields[k]==v,(k,fields[k])
    assert fields['CY']>0
for (_,before),(_,after) in zip(samples,samples[1:]):
    for k in ('WF','CF','PF'):assert after[k]>=before[k],f'{k} regressed'
span=(samples[-1][0]-samples[0][0]).total_seconds();assert span>4
delta={k:samples[-1][1][k]-samples[0][1][k] for k in ('WF','CF','PF')}
assert all(v>0 for v in delta.values())
assert len({r['CS'] for _,r in samples})>1,'No changing camera source detected'
result={'passed':True,'target':args.target,'samples':len(samples),'span_seconds':span,'delta':delta,
        'approx_rates_per_second':{k:round(v/span,3) for k,v in delta.items()},
        'process_cycles_range':[min(r['CY'] for _,r in samples),max(r['CY'] for _,r in samples)],
        'mean_process_cycles':statistics.mean(r['CY'] for _,r in samples),
        'median_process_cycles':statistics.median(r['CY'] for _,r in samples),
        'sample_process_cycles':[r['CY'] for _,r in samples],
        'core_clock_hz':125000000,'max_process_ms':max(r['CY'] for _,r in samples)/125000,
        'underflows':0,'pixel_crc_errors':0,'ownership_errors':0,'fault':0,
        'resolution':[640,480],'limits':'Finite serial-timestamped hardware run. CF is new processed frames, PF is HDMI refreshes and includes repeats. Host polling timing is approximate. CRC is checked against each locked processed frame; these snapshots can describe different frame IDs.'}
output=args.output or root/'results/corrected-video-check-20261006.json'
output.parent.mkdir(parents=True,exist_ok=True)
for name in ('telemetry.txt','telemetry-timed.json'):
    shutil.copyfile(work/name,output.parent/(output.stem+'-'+name))
output.write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
