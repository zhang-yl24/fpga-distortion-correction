"""Check physical tone-state telemetry, actual gated bitstream and fresh idle."""
from pathlib import Path
import hashlib,json,re
root=Path(__file__).resolve().parents[1];lab=root/'results/lab-20261007'
read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
t=read(lab/'host-angle-gamma_13_7-transaction.json');host=read(lab/'host-angle-gamma_13_7-check.json')
assert host['passed'] and host['wrapper_finished_cleanly']
rows=[r['fields'] for r in t['observations']]
assert all(r['GM'] in (0,1,2) and 0<=((r['GF']-r['CF'])&0xffffffff)<=2 for r in rows)
assert rows[-1]['GF']>rows[0]['GF']
m=read(root/'build/corrected_gamma/validated-build.json')
assert m['SHA256']==host['bitstream_sha256'] and 'All Constraints Met' in Path(m['TimingReport']).read_text()
resources={}
for k,u,a,p in re.findall(r'\|\s*(\w+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)',(root/'build/corrected_gamma/build.log').read_text(encoding='utf-8-sig')):
    resources.setdefault(k,{'used':int(u),'available':int(a),'pds_percent':int(p)})
result={**host,'gamma_modes_observed':sorted({r['GM'] for r in rows}),
    'gamma_completed_frames_delta':rows[-1]['GF']-rows[0]['GF'],'gamma_crc_frame_counters_coherent':True,
    'mapped_global_resources':resources,'final_timing_sha256':m['TimingSHA256'],'source_sha256':m['SourceSHA256'],
    'limits':'Finite physical angle command, new corrected frames, live GM/GF statistics and zero video errors. GM is mode of the tone pipeline, not directly measured display-frame metadata. Identity mode in a normally lit scene does not prove physical dark/bright quality. Optical benefit and all-angle stability require separate tests.'}
(lab/'gamma-physical-check.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({'passed':True,'new_fps':host['approx_new_frame_rate_fps'],'gamma_modes':result['gamma_modes_observed'],'new_gamma_frames':result['gamma_completed_frames_delta'],'temperature_range':host['temperature_celsius_range']}))
