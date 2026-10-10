"""Compare isolated eight-beat native RTL with the accepted tiled experiment."""
from pathlib import Path
import csv,hashlib,json,shutil
root=Path(__file__).resolve().parents[1]
work=root/'build/short_burst_native_sim'
log=work/'simulation.log';text=log.read_text()
assert 'PASS short burst native regression: 1843200' in text and 'Fatal:' not in text
query=root/'build/short_burst_query_sim/simulation.log'
assert 'PASS short burst composed rotation' in query.read_text() and 'Fatal:' not in query.read_text()
rows=list(csv.DictReader((work/'cycles.csv').open()))
current=json.loads((root/'results/lab-20261007/adaptive-native-check.json').read_text())
assert len(rows)==6
snapshot=work/'source-snapshot';snapshot.mkdir(exist_ok=True)
files=[root/'rtl/experimental'/n for n in ('ddr_short_burst_cache.v','short_burst_frame_engine.v','ddr_adaptive_result_writer.v')]
for p in files:
    assert p.stat().st_mtime<=log.stat().st_birthtime,'Source modified after this simulation began: '+str(p)
    shutil.copy2(p,snapshot/p.name)
hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
(snapshot/'files-sha256.json').write_text(json.dumps(hashes,indent=2)+'\n')
frames=[]
for row,base in zip(rows,current['frames']):
    assert int(row['pixels'])==307200 and row['crc32'].lower()==base['crc32'].lower()
    cycles=int(row['cycles']);bursts=int(row['read_bursts'])
    frames.append({'angle_deg':base['angle_deg'],'crc32':row['crc32'],'pixels':307200,
        'tiled_16_beat_cycles':base['adaptive_cycles'],'short_8_beat_cycles':cycles,
        'process_cycle_reduction_from_tiled_percent':100*(1-cycles/base['adaptive_cycles']),
        'read_bursts':bursts,'read_payload_bytes':bursts*256,
        'read_payload_reduction_from_tiled_percent':100*(1-bursts*256/(base['adaptive_read_bursts']*512))})
result={'passed':True,'hardware_accessed':False,'pixels_checked':1843200,'source_sha256':hashes,
        'cache_bytes':8192,'cache_lines':32,'burst_beats':8,'frames':frames,
        'query_fault_regression_passed':True,'limits':'Isolated six-angle full-frame RTL with sealed real camera sources and synthetic DDR stalls. Byte/CRC output is unchanged. Eight-beat controller compatibility, complete camera/HDMI arbitration, timing, physical bandwidth and FPS remain unverified. This is not an active board target.'}
dest=root/'results/lab-20261007/short-burst-native-check.json'
dest.write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({'passed':True,'frames':frames},indent=2))
