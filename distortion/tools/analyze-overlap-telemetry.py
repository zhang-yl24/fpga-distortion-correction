"""Check saved live-video telemetry and frame-scheduling diagnostics."""
from pathlib import Path
from datetime import datetime
import argparse,importlib.util,json,re,statistics,shutil
root=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('rotation_check',root/'tools/analyze-rotation-telemetry.py')
rotation=importlib.util.module_from_spec(spec);spec.loader.exec_module(rotation)

def analyze(capture):
    result=rotation.analyze(capture)
    started=datetime.fromisoformat(capture['StartedUtc']);rows=[]
    for sample in capture['Samples']:
        if (datetime.fromisoformat(sample['ReceivedUtc'])-started).total_seconds()<4:continue
        f={k:int(v,16) for k,v in re.findall(r'\b(\w+)=([0-9A-Fa-f]+)\b',sample['Line'])}
        if not {'OC','CC','BW','SP'}<=f.keys():raise ValueError('Missing capture scheduling diagnostics')
        if not 0<f['SP']<0xFFFFFFFF or not 0<f['CC']<0xFFFFFFFF:raise ValueError('Invalid frame period/capture interval')
        rows.append((datetime.fromisoformat(sample['ReceivedUtc']),f))
    deltas={k:0 for k in ('OC','BW')}
    for (old_stamp,old),(stamp,new) in zip(rows,rows[1:]):
        # These cumulative counters can wrap far from 0xFFFF0000 between
        # one-second UART samples. A physical clock-rate bound distinguishes
        # a legal wrap from a reset or corrupt jump for finite captures.
        span=(stamp-old_stamp).total_seconds()
        if not 0<span<20:raise ValueError('Scheduling counters require increasing timestamps with gaps under 20 seconds')
        maximum_delta=int(span*125000000*1.1)+1250000
        for key in deltas:
            value=(new[key]-old[key])&0xFFFFFFFF
            if value>maximum_delta:raise ValueError(f'{key} reset or implausible counter jump')
            deltas[key]+=value
    if deltas['OC']==0:raise ValueError('No capture-armed/remap overlap observed')
    fields=[f for _,f in rows]
    result['scheduling']={
        'sensor_period_cycles_range':[min(r['SP'] for r in fields),max(r['SP'] for r in fields)],
        'approx_sensor_frame_rate_at_125mhz':125000000/statistics.median(r['SP'] for r in fields),
        'last_armed_capture_ms_range':[min(r['CC'] for r in fields)/125000,max(r['CC'] for r in fields)/125000],
        'capture_armed_and_processing_overlap_cycles_delta':deltas['OC'],
        'source_bank_wait_cycles_delta':deltas['BW'],
        'counter_limit':'OC means capture is armed while remap is processing; includes waiting for VSYNC and is not a count of simultaneous DDR data beats.'}
    result['process_cycles_by_angle']={}
    for r in fields:
        angle=str(round(r['RA']*360/(1<<32)))
        result['process_cycles_by_angle'].setdefault(angle,[]).append(r['CY'])
    result['process_cycles_by_angle']={a:{'samples':len(v),'median_cycles':statistics.median(v),'max_cycles':max(v)} for a,v in result['process_cycles_by_angle'].items()}
    return result

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('capture',type=Path);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();capture=json.loads(args.capture.read_text(encoding='utf-8-sig'))
    result=analyze(capture);args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    stem=args.output.stem.removesuffix('-check')
    shutil.copy2(args.capture,args.output.parent/(stem+'-telemetry-timed.json'))
    raw=args.capture.parent/'telemetry.txt'
    if raw.exists():shutil.copy2(raw,args.output.parent/(stem+'-telemetry.txt'))
    idle=args.capture.parent/'idle-after-test.json'
    if idle.exists():
        proof=json.loads(idle.read_text(encoding='utf-8-sig'))
        if not proof['Done'] or proof['Target']!='heartbeat':raise ValueError('Idle transfer not verified')
        shutil.copy2(idle,args.output.parent/(stem+'-idle.json'))
    print(json.dumps(result,ensure_ascii=False,indent=2))
