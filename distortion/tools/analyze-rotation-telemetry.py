"""Read saved UART evidence only; never connect or program hardware."""
from pathlib import Path
from datetime import datetime
import argparse,json,re

def analyze(capture,warmup=4,min_samples=6,max_temperature=85):
    started=datetime.fromisoformat(capture['StartedUtc'])
    samples=[]
    required=set('CAM E I H D V WF CF PF UF MF OW X CS RC RS PS CY HT MS RA AU TV TR TF TA AL'.split())
    for sample in capture['Samples']:
        line=sample['Line']
        matches=re.findall(r'\b(\w+)=([0-9A-Fa-f]+)\b',line)
        fields={k:int(v,16) for k,v in matches}
        if len(matches)!=len(fields):raise ValueError('Duplicate UART fields')
        if not required<=fields.keys():raise ValueError('Incomplete rotation/temperature telemetry line')
        stamp=datetime.fromisoformat(sample['ReceivedUtc'])
        for key in ('UF','MF','OW','X'):
            if fields[key]:raise ValueError(f'{key} indicates a video fault: {fields[key]}')
        if (stamp-started).total_seconds()<warmup:continue
        for key,value in {'CAM':0x5640,'E':0,'I':1,'H':1,'D':1,'V':1,'TV':1,'TF':0}.items():
            if fields[key]!=value:raise ValueError(f'{key} is not ready: {fields[key]}')
        if fields['TA']>=54000000:raise ValueError('Stale temperature sample')
        if fields['AL']&0x20:raise ValueError('Hardware over-temperature indicator asserted')
        if fields['AL']&0x40 or not fields['AL']&0x80:raise ValueError('Temperature flags do not indicate a valid sample')
        if not 0<fields['TR']<=65535:raise ValueError('Invalid temperature status word')
        code=fields['TR']>>4
        temperature=(code*1219-2731500)/10000
        if code==0 or not -40<=temperature<=125:raise ValueError('Temperature code is not physically plausible for this acceptance run')
        if temperature>max_temperature:raise ValueError(f'Temperature {temperature:.2f} C exceeds requested diagnostic limit {max_temperature} C')
        if fields['AU'] not in (0,1) or fields['CY']<=0:raise ValueError('Invalid mode/process count')
        samples.append((stamp,fields,temperature))
    if len(samples)<min_samples:raise ValueError('Need six complete post-warmup samples')
    rates={k:0 for k in ('WF','CF','PF')}
    for (old_stamp,old,_),(stamp,new,_) in zip(samples,samples[1:]):
        if stamp<=old_stamp:raise ValueError('UART timestamps must increase')
        for key in rates:
            delta=new[key]-old[key]
            if delta<0:
                if old[key]<0xFFFF0000 or new[key]>0xFFFF:raise ValueError(f'{key} regressed/reset')
                delta&=0xFFFFFFFF
            rates[key]+=delta
    span=(samples[-1][0]-samples[0][0]).total_seconds()
    if span<=4 or any(v<=0 for v in rates.values()):raise ValueError('No sustained new-frame evidence')
    if len({s[1]['CS'] for s in samples})<2:raise ValueError('Camera source did not change')
    angles=sorted({round(s[1]['RA']*360/(1<<32),4) for s in samples})
    return {'passed':True,'hardware_accessed_by_analyzer':False,'samples':len(samples),'span_seconds':span,
        'delta':rates,'approx_rates_per_second':{k:v/span for k,v in rates.items()},
        'observed_result_angles_deg':angles,'temperature_celsius_range':[min(s[2] for s in samples),max(s[2] for s in samples)],
        'max_process_ms_at_125mhz':max(s[1]['CY'] for s in samples)/125000,
        'limits':'Saved serial evidence only. CF counts new completed remaps; PF includes repeated HDMI refreshes. Host timestamps approximate rates. Internal-reference ADC is an approximate temperature until compared with an external instrument. Optical quality and visible key behavior need direct observation.'}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('capture',type=Path);p.add_argument('--output',type=Path)
    p.add_argument('--warmup',type=float,default=4);p.add_argument('--max-temperature',type=float,default=85)
    a=p.parse_args();result=analyze(json.loads(a.capture.read_text(encoding='utf-8-sig')),a.warmup,max_temperature=a.max_temperature)
    text=json.dumps(result,ensure_ascii=False,indent=2)+'\n'
    if a.output:a.output.write_text(text,encoding='utf-8')
    print(text)
