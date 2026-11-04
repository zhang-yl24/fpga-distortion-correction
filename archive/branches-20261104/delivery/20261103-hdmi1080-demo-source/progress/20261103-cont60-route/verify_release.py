from pathlib import Path
import argparse,json,hashlib
R=Path(__file__).resolve().parent
ap=argparse.ArgumentParser();ap.add_argument('--previous-source',type=Path,default=R.parent/'20261103-morning/index6/source');a=ap.parse_args()
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
pro=read(R/'PROVENANCE.json')
for row in pro['exact_copied']:assert sha(R/row['path'])==row['sha256']
for row in pro['portable_native_modules']:assert sha(R/row['path'])==row['delivered_sha256']
old=read(R/'REUSED_SOURCE_50.json')
assert len(old['files'])==50
for row in old['files']:assert sha(a.previous_source/row['path'])==row['sha256']
c=read(R/'continuous/SUMMARY.json')
assert c['pixels_checked']==6220800 and c['metrics']['presented']==3 and c['metrics']['repeats']==0
assert not c['input_ready_gating'] and not c['stop_wait_between_inputs'] and not c['DDR_source_preloaded']
assert [x['engine_edges'] for x in c['frames']]==[2073970,2073971,2073961]
for x in c['frames']:
 gap=x['scan_first_observed_ps']-x['input_SOF_drive_ps']
 assert abs(gap/1e9-x['SOF_drive_to_scanfirst_observed_ms'])<1e-12
d=read(R/'continuous/DIGITAL_LATENCY_BREAKDOWN.json')
assert not d['capture_ready_to_accept_queue_measured']
assert all(x['capture_ready_to_processing_accept_queue_ms'] is None for x in d['frames'])
t=read(R/'route/TIMING_PATH_SUMMARY.json')
assert sum(x['count'] for x in t['derived_path_groups'].values())==10213
assert t['timing']['slow']['setup']['WNS_ns']==-2.105 and not t['hardware_accepted'] and not t['bitstream_generated']
m=read(R/'route/CONSTRAINT_MODEL_SUMMARY.json')
assert not m['actual_vendor_groups_applied'] and m['RCF_priority_nets_applied']==2
print(json.dumps({'reused_source_files':50,'three_frame_finite_RTL':True,'setup_failure_endpoints':10213,'vendor_groups_registered_not_applied':True,'hardware_60_or_E2E_claimed':False}))
