"""Record actual guarded host command, frame telemetry and fresh idle proof."""
from pathlib import Path
from datetime import datetime
import argparse,hashlib,json,statistics
root=Path(__file__).resolve().parents[1];lab=root/'results/lab-20261007'
read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
parser=argparse.ArgumentParser();parser.add_argument('--tag',default='13_7');parser.add_argument('--target',choices=('corrected_host','corrected_host_cadence','corrected_gamma'),default='corrected_host');args=parser.parse_args()
assert all(c.isalnum() or c=='_' for c in args.tag)
transaction=read(lab/('host-angle-'+args.tag+'-transaction.json'))
assert transaction['hardware_accessed'] and transaction['acknowledged']
log_failure=transaction['idle_return_code']==-1 and transaction.get('error')=='heartbeat idle failed'
if log_failure:assert "unsupported operand type(s) for +: 'NoneType' and 'str'" in Path(transaction['idle_log']).read_text()
else:assert transaction['idle_return_code']==0 and 'error' not in transaction
assert transaction['writes']==1 and transaction['opcode']==1
observations=transaction['observations'];assert len(observations)>=2
transfers=list((root/'build'/args.target).glob('program-evidence-*/transfer.json'))
transfer=max((read(p) for p in transfers),key=lambda d:d['CheckedOn'])
manifest=read(root/'build'/args.target/'validated-build.json')
assert transfer['Done'] and transfer['SHA256']==manifest['SHA256']==hashlib.sha256(Path(manifest['Bitstream']).read_bytes()).hexdigest().upper()
assert datetime.fromisoformat(transaction['acknowledged_at_utc'])>datetime.fromisoformat(transfer['CheckedOn'])
status=read(root/'status.json');assert status['current_sram_target']=='heartbeat'
idle_proofs=[read(p) for p in (root/'build/heartbeat').glob('program-evidence-*/transfer.json')]
latest=max(idle_proofs,key=lambda d:d['CheckedOn'])
assert latest['Done'] and latest['CheckedOn']==status['current_connection']['checked_on']
idle=min((d for d in idle_proofs if datetime.fromisoformat(d['CheckedOn'])>datetime.fromisoformat(observations[-1]['received_utc'])),key=lambda d:d['CheckedOn'])
assert idle['Done'] and idle['Target']=='heartbeat'
assert datetime.fromisoformat(idle['CheckedOn'])>datetime.fromisoformat(observations[-1]['received_utc'])
first,last=observations[0],observations[-1]
span=(datetime.fromisoformat(last['received_utc'])-datetime.fromisoformat(first['received_utc'])).total_seconds()
delta=(last['fields']['CF']-first['fields']['CF'])&0xffffffff;assert span>1 and delta>0
phase=int(transaction['argument'],16)
rows=[r['fields'] for r in observations]
assert all(r['HR']==phase and r['RA']==phase and r['HQ']==transaction['sequence'] for r in rows)
temps=[(r['TR']>>4)*.1219-273.15 for r in rows]
check={'passed':True,'hardware_accessed_by_recorder':False,'target':args.target,'angle_deg':phase*360/(1<<32),
    'bitstream_sha256':transfer['SHA256'],'one_write_controller_and_new_processed_frame_ack':True,
    'observed_new_frames':delta,'observation_span_seconds':span,'approx_new_frame_rate_fps':delta/span,
    'max_process_ms_at_125mhz':max(r['CY'] for r in rows)/125000,
    'temperature_celsius_range':[min(temps),max(temps)],'idle_transfer':idle,
    'wrapper_finished_cleanly':not log_failure,
    'wrapper_failure':'Heartbeat transfer succeeded; post-transfer captured-output string concatenation failed. Raw failure retained, actual fresh DONE/heartbeat proof independently checked.' if log_failure else None,
    'limits':'Actual CP2102 UART command and new completed-frame phase acknowledgement plus finite error-free telemetry. User screen confirmation is separate. RA is processed result phase, not a directly measured on-screen phase or input-to-display latency. Internal ADC temperature is approximate.'}
(lab/('host-angle-'+args.tag+'-check.json')).write_text(json.dumps(check,indent=2)+'\n')
print(json.dumps(check))
