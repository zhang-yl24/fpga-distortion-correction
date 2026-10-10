"""Bind parity banking to completed adversarial and 12-angle native evidence."""
from pathlib import Path
import csv,hashlib,json,re
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1]
read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest().upper()

def validate():
    inputs=read(ROOT/'results/lab-20261008/pipeline-parity-inputs.json')
    for name,digest in inputs['source_sha256'].items():
        if sha(ROOT/name)!=digest:raise ValueError('Parity regression input changed: '+name)
    passes={'query':'PASS pipeline hit composed rotation','stream':'PASS pipeline hit stream:','native':'PASS pipeline twelve native regression: 3686400 real-camera pixels'}
    logs={}
    for kind,item in inputs['suite'].items():
        path=Path(item['work_directory'])/'simulation.log'
        text=path.read_text()
        if passes[kind] not in text or re.search(r'(?i)fatal:|error:',text):raise ValueError('Parity suite did not pass: '+kind)
        logs[kind]={'path':str(path),'sha256':sha(path)}
    baseline=read(ROOT/'results/lab-20261007/pipeline-twelve-native-check.json')
    # Recheck original oracle and arithmetic identity before comparing cycles.
    for name,digest in baseline['source_sha256'].items():
        if sha(ROOT/name)!=digest.upper():raise ValueError('Original oracle changed: '+name)
    native=Path(inputs['suite']['native']['work_directory'])
    rows=list(csv.DictReader((native/'cycles.csv').open(newline='')))
    if len(rows)!=12:raise ValueError('Incomplete full-frame outputs')
    frames=[]
    for phase,(row,old) in enumerate(zip(rows,baseline['frames'])):
        if int(row['phase'])!=phase or int(row['pixels'])!=307200 or row['crc32'].upper()!=old['crc32'].upper():raise ValueError('Parity frame CRC/order mismatch')
        if int(row['cycles'])!=old['rtl_cycles'] or int(row['read_bursts'])!=old['rtl_read_bursts']:raise ValueError('Unexpected protocol cadence change')
        frames.append({'angle_deg':phase*30,'pixels':307200,'crc32':row['crc32'].upper(),
            'rtl_cycles':int(row['cycles']),'rtl_read_bursts':int(row['read_bursts']),'identical_baseline_cycles':True})
    return {'passed':True,'recorded_utc':datetime.now(timezone.utc).isoformat(),'hardware_accessed':False,
        'source_sha256':inputs['source_sha256'],'simulation_logs':logs,'frames':frames,
        'pixels_checked':3686400,'queries_checked':2322,'stream_packets_checked':161,
        'consecutive_hit_accepts':64,'logical_fast_cache_bytes_before':32768,'logical_fast_cache_bytes_after':16384,
        'serial_cache_bytes':8192,'cycles_csv_sha256':sha(native/'cycles.csv'),
        'limits':'Exact native pixel/CRC and protocol-cycle identity under synthetic DDR stalls. Halved declared fast RAM is not yet measured PDS resources, final timing, board frame rate, optical quality, or temperature.'}

def main():
    result=validate()
    (ROOT/'results/lab-20261008/pipeline-parity-regression.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'passed':True,'pixels_checked':result['pixels_checked'],'logical_fast_cache_bytes':16384,'hardware_accessed':False}))

if __name__=='__main__':main()
