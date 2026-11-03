from pathlib import Path
import hashlib,json

PHYSICAL=Path('D:/f60-run/physical-i')
SYSTEM=Path('D:/f60-work/system-final-i-rowpad640-fanout16')

def digest(data):return hashlib.sha256(data).hexdigest()
plans=[json.loads((p/'candidate-plan.json').read_text()) for p in (PHYSICAL,SYSTEM)]
overlay_maps=[{r['source']:r['source_sha256'] for r in p['overlays']} for p in plans]
overlay_differences=[{'source':s,'physical':overlay_maps[0].get(s),'system':overlay_maps[1].get(s)}
    for s in sorted(set(overlay_maps[0])|set(overlay_maps[1])) if overlay_maps[0].get(s)!=overlay_maps[1].get(s)]
source_keys=[set(p['source_files']) for p in plans]
assert source_keys[0]==source_keys[1]
rows=[]
for relative in sorted(source_keys[0]):
    raw=[(p/'compiled'/relative).read_bytes() for p in (PHYSICAL,SYSTEM)]
    hashes=[digest(data) for data in raw]
    for i in (0,1):assert hashes[i]==plans[i]['source_files'][relative],relative
    normalized=[]
    for folder,data in zip((PHYSICAL,SYSTEM),raw):
        root=(folder/'compiled').as_posix()
        normalized.append(data.replace(root.encode(),b'@COMPILED@').replace(root.replace('/','\\').encode(),b'@COMPILED@'))
    rows.append({'path':relative,'physical_sha256':hashes[0],'system_sha256':hashes[1],
                 'exact_match':raw[0]==raw[1],'normalized_match':normalized[0]==normalized[1]})
configuration_fields=['baseline_commit','baseline_bitstream','build_id','profile_id','tile_width','tile_height','cache_configuration','clock_hz']
configuration={key:plans[0][key]==plans[1][key] for key in configuration_fields}
report={'physical_run':str(PHYSICAL),'system_snapshot':str(SYSTEM),
        'physical_source_identity':plans[0]['source_identity'],'system_source_identity':plans[1]['source_identity'],
        'same_overlay_sources':not overlay_differences,'source_differences':overlay_differences,
        'closure_files':len(rows),'closure_exact_matches':sum(r['exact_match'] for r in rows),
        'closure_normalized_matches':sum(r['normalized_match'] for r in rows),
        'closure':rows,'configuration_matches':configuration,
        'passed':not overlay_differences and all(r['normalized_match'] for r in rows) and all(configuration.values()),
        'note':'Every prepared file is checked against its manifest SHA; only its own absolute compiled-root prefix is normalized for comparison. No other content normalization is performed.'}
(SYSTEM/'physical-i-source-binding.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k!='closure'},indent=2))
assert report['passed']
