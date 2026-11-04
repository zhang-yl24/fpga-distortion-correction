from pathlib import Path
import hashlib,json
R=Path(__file__).resolve().parents[1]
m=json.loads((R/'PACKAGE_FILES.json').read_text(encoding='utf-8'))
assert {p.relative_to(R).as_posix() for p in R.rglob('*') if p.is_file()}=={x['path'] for x in m['files']}|{'PACKAGE_FILES.json'}
for x in m['files']:
 b=(R/x['path']).read_bytes()
 assert len(b)==x['bytes'] and hashlib.sha256(b).hexdigest()==x['sha256'],x['path']
r=json.loads((R/'RELEASE_BINDING.json').read_text(encoding='utf-8'))
assert r['status']=='DIAGNOSTIC_TIMING_UNCLOSED_NOT_BOARD_TESTED'
assert r['diagnostic_only'] and not r['timing_closed'] and not r['fresh_60fps_proven']
assert not r['strict_bitgen_admitted'] and not r['electrical_e2e_measured']
b=(R/r['bit_file']).read_bytes()
assert len(b)==r['bit_bytes'] and hashlib.sha256(b).hexdigest()==r['bit_sha256']
assert hashlib.sha256((R/'STA_SUMMARY.json').read_bytes()).hexdigest()==r['sta_summary_sha256']
s=json.loads((R/'STA_SUMMARY.json').read_text(encoding='utf-8'))
assert not s['timing_closed'] and len(s['checks'])==12
assert sum(x['failing_endpoints'] for x in s['checks'])==1
print('PASS_DIAGNOSTIC_PACKAGE',len(m['files'])+1,'files; timing remains unclosed -0.007ns')
