"""Bind six arbitrary-angle full-frame RTL checks to sources and references."""
from pathlib import Path
import csv,hashlib,json,re
root=Path(__file__).resolve().parents[1];work=root/'build/host_angle_native_sim'
log_path=work/'simulation.log';log=log_path.read_text()
assert 'PASS adaptive native regression: 1843200 real-camera pixels' in log
assert not re.search(r'(?im)fatal:|error:',log)
reference=json.loads((work/'reference.json').read_text());rows=list(csv.DictReader((work/'cycles.csv').open()))
assert len(rows)==len(reference['frames'])==6 and reference['pixels']==1843200
frames=[]
for i,(row,expected) in enumerate(zip(rows,reference['frames'])):
    assert int(row['phase'])==i and int(row['pixels'])==expected['pixels']==307200
    assert row['crc32'].upper()==expected['crc32'].upper()
    frames.append({**expected,'rtl_cycles':int(row['cycles']),'rtl_read_bursts':int(row['read_bursts'])})
snapshot=work/'source-snapshot';hashes=json.loads((snapshot/'files-sha256.json').read_text())
for rel,digest in hashes.items():
    assert hashlib.sha256((root/rel).read_bytes()).hexdigest()==digest
    assert hashlib.sha256((snapshot/rel).read_bytes()).hexdigest()==digest
    assert (root/rel).stat().st_mtime<=log_path.stat().st_birthtime
result={'passed':True,'hardware_accessed':False,'pixels_checked':1843200,'angles':[f['angle_deg'] for f in frames],
    'frames':frames,'source_sha256':hashes,'simulation_sha256':hashlib.sha256(log_path.read_bytes()).hexdigest(),
    'limits':'Six non-step full-size frames with real-camera sources, independent scalar/vector coordinate checks, all RGB565 pixels and CRCs, frame-locked parameters, immutable source and synthetic DDR stalls. UART/CORDIC controller is tested separately; this is not full-board host-control or optical quality validation.'}
(root/'results/lab-20261007/host-angle-native-check.json').write_text(json.dumps(result,indent=2)+'\n')
print('PASS six arbitrary-angle source-bound full-frame regressions: 1843200 pixels.')
