"""Check finite host-started rotation and fresh automatic idle from saved evidence."""
from pathlib import Path
from datetime import datetime
import argparse,hashlib,importlib.util,json
root=Path(__file__).resolve().parents[1];lab=root/'results/lab-20261007'
read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
parser=argparse.ArgumentParser();parser.add_argument('--target',choices=('corrected_host_cadence','corrected_gamma'),default='corrected_host_cadence');args=parser.parse_args()
prefix='gamma' if args.target=='corrected_gamma' else 'host-cadence'
t=read(lab/(prefix+'-auto-transaction.json'))
assert t['hardware_accessed'] and t['acknowledged'] and t['writes']==1 and t['opcode']==2 and t['argument']=='00000001'
assert t['idle_return_code']==0 and 'error' not in t
rows=t['observations'];assert len(rows)>=30
assert all(r['fields']['AU']==1 and r['fields']['HQ']==t['sequence'] and r['fields']['HC']==t['after']['HC'] for r in rows)
assert all(all(r['fields'][k]==t['after'][k] for k in ('HX','HD','HE')) for r in rows)
capture={'StartedUtc':t['acknowledged_at_utc'],'Samples':[{'ReceivedUtc':r['received_utc'],'Line':r['line']} for r in rows]}
spec=importlib.util.spec_from_file_location('overlap',root/'tools/analyze-overlap-telemetry.py')
a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)
check=a.analyze(capture)
raw_angles=check['observed_result_angles_deg']
assert all(abs(v-round(v/30)*30)<.001 for v in raw_angles)
assert sorted({round(v)%360 for v in raw_angles})==list(range(0,360,30))
check['raw_result_angles_deg']=raw_angles
check['observed_result_angles_deg']=list(range(0,360,30))
target=args.target;manifest=read(root/'build'/target/'validated-build.json')
transfer=max((read(p) for p in (root/'build'/target).glob('program-evidence-*/transfer.json')),key=lambda d:d['CheckedOn'])
assert transfer['Done'] and transfer['SHA256']==manifest['SHA256']==hashlib.sha256(Path(manifest['Bitstream']).read_bytes()).hexdigest().upper()
assert datetime.fromisoformat(t['acknowledged_at_utc'])>datetime.fromisoformat(transfer['CheckedOn'])
idle=min((read(p) for p in (root/'build/heartbeat').glob('program-evidence-*/transfer.json') if datetime.fromisoformat(read(p)['CheckedOn'])>datetime.fromisoformat(rows[-1]['received_utc'])),key=lambda d:d['CheckedOn'])
assert idle['Done'] and idle['Target']=='heartbeat'
status=read(root/'status.json');assert status['current_sram_target']=='heartbeat' and status['current_connection']['checked_on']==idle['CheckedOn']
check.update(target=target,bitstream_sha256=transfer['SHA256'],one_write_host_auto_command=True,idle_transfer=idle,
    wrapper_finished_cleanly=True,screen_observation_separate=True)
if args.target=='corrected_gamma':
    assert all(r['fields']['GM'] in (0,1,2) and 0<=((r['fields']['GF']-r['fields']['CF'])&0xffffffff)<=2 for r in rows)
    check['gamma_modes_observed']=sorted({r['fields']['GM'] for r in rows})
    check['gamma_completed_frames_delta']=rows[-1]['fields']['GF']-rows[0]['fields']['GF'];assert check['gamma_completed_frames_delta']>0
(lab/(prefix+'-auto-check.json')).write_text(json.dumps(check,indent=2)+'\n')
(lab/(prefix+'-auto-telemetry-timed.json')).write_text(json.dumps(capture,indent=2)+'\n')
print(json.dumps({'passed':True,'angles':check['observed_result_angles_deg'],'new_fps':check['approx_rates_per_second']['CF'],'max_processing_ms':check['max_process_ms_at_125mhz'],'idle':idle['CheckedOn']}))
