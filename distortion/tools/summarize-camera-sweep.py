from pathlib import Path
import json,re
root=Path(__file__).resolve().parents[1]
raw=(root/'build/camera_sweep/telemetry.txt').read_text(encoding='utf-8-sig')
(root/'results/camera-after-swap-sweep-20261006.txt').write_text(raw,encoding='utf-8')
groups={}
for line in raw.splitlines():
    if not line.startswith('CAM=5640 ') or not re.search(r' Q=[0-9A-F]{2} M=[0-9A-F]{4}$',line):continue
    fields=dict(re.findall(r'\b([A-Z]+)=([0-9A-F]+)',line))
    # E occurs twice (camera, HDMI); parse camera error explicitly.
    fields['CAM_E']=re.search(r'CAM=5640 E=([0-9A-F]{2})',line)[1]
    groups.setdefault(fields['Q'],[]).append(fields)
summary={}
for trial,rows in sorted(groups.items()):
    summary[trial]={'mask':rows[-1]['M'],'samples':len(rows),
        'camera_errors':sorted({r['CAM_E'] for r in rows}),
        'init_ready_seen':any(r['INIT']=='1' for r in rows),
        'last_sample':rows[-1]}
assert len(summary)==14, f'Incomplete sweep: {sorted(summary)}'
assert all(rows['mask']==mask for rows,mask in zip(summary.values(),
    ['0000','1000','2000','4000','7000','7100','7200','7400','7800','7010','7020','7040','7080','7FF0']))
result={'date':'2026-10-06','hardware_change_user_confirmed':'Both camera module and FMC adapter replaced',
    'all_14_trials_observed':True,'summary':summary,
    'finding':'Only 7020 (module D1 alone with sync/clock) and 7FF0 (full bus) fail with camera read-address NACK E61 at 3018. Other masks complete initialization. Full image not verified; first sample after clock pauses may contain transitional statistics.'}
(root/'results/camera-pad-sweep-20261006.json').write_text(json.dumps(result,indent=2)+'\n')
for q,r in summary.items():print(q,r['mask'],r['camera_errors'],'ready',r['init_ready_seen'])
