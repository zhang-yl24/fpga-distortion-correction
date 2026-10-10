"""Compare completed native simulations against the sealed independent oracle."""
from pathlib import Path
import csv,json,hashlib,re
root=Path(__file__).resolve().parents[1]
work=root/'build/adaptive_native_sim'
log=(work/'simulation.log').read_text()
assert 'PASS adaptive native regression: 1843200 real-camera pixels' in log and 'Fatal:' not in log
rows=lambda p:list(csv.DictReader(p.open()))
baseline=rows(root/'build/rotated_native_sim/cycles.csv');adaptive=rows(work/'cycles.csv')
assert len(baseline)==len(adaptive)==6
frames=[]
for a,b,angle in zip(baseline,adaptive,[0,30,-30,90,-90,180]):
    assert a['phase']==b['phase'] and a['crc32']==b['crc32'] and int(b['pixels'])==307200
    frames.append({'angle_deg':angle,'crc32':b['crc32'],'pixels':307200,
        'baseline_cycles':int(a['cycles']),'adaptive_cycles':int(b['cycles']),
        'baseline_read_bursts':int(a['read_bursts']),'adaptive_read_bursts':int(b['read_bursts']),
        'process_cycle_reduction_percent':100*(1-int(b['cycles'])/int(a['cycles'])),
        'read_burst_reduction_percent':100*(1-int(b['read_bursts'])/int(a['read_bursts']))})
snapshot=work/'source-snapshot';hashes=json.loads((snapshot/'files-sha256.json').read_text())
for name,digest in hashes.items():
    assert hashlib.sha256((snapshot/name).read_bytes()).hexdigest()==digest
    assert hashlib.sha256((root/'rtl/experimental'/name).read_bytes()).hexdigest()==digest
result={'passed':True,'hardware_accessed':False,'pixels_checked':1843200,'source_sha256':hashes,'frames':frames,
    'scope':'640x480, six real-camera input frames, independent integer-model output and raster CRC. Synthetic DDR stalls; process cycles are not physical frame rate or a higher-resolution claim.',
    'strategy':'Frame-locked raster near 0/180 degrees; 8x8 tiles otherwise. Sixteen direct-mapped cache lines; eight-row raster reorder buffer.'}
out=root/'results/lab-20261007/adaptive-native-check.json';out.write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({'output':str(out),'frames':frames},indent=2))
