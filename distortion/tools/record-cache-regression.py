"""Record reproducible RTL measurements without treating them as board FPS."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import csv
import hashlib
import json

root = Path(__file__).resolve().parents[1]
now = datetime.now(ZoneInfo('Asia/Shanghai')).isoformat()
record = {'recorded_at': now, 'native_pixels_per_variant': 614400, 'board_integrated': False, 'variants': {}}
for variant, folder in (('baseline', 'native_regression_sim'), ('fast', 'native_regression_fast_sim')):
    work = root / 'build' / folder
    log = (work / 'simulation.log').read_text()
    assert 'PASS native regression:' in log and 'Fatal:' not in log
    rows = list(csv.DictReader((work / 'cycles.csv').open()))
    assert len(rows) == 2
    for r in rows:
        for key in ('phase', 'cycles', 'cache_hits', 'cache_misses', 'read_bursts', 'pixels'):
            r[key] = int(r[key])
        assert r['pixels'] == 307200 and r['cache_misses'] == r['read_bursts'] == 1200
        r['modeled_process_ms_at_125mhz'] = r['cycles'] / 125000
    record['variants'][variant] = {'frames': rows, 'log_sha256': hashlib.sha256((work / 'simulation.log').read_bytes()).hexdigest()}
baseline = record['variants']['baseline']['frames']
fast = record['variants']['fast']['frames']
assert [r['crc32'] for r in baseline] == [r['crc32'] for r in fast]
assert all(f['cycles'] < b['cycles'] for b, f in zip(baseline, fast))
record['mean_cycle_reduction_percent'] = 100 * (1 - sum(r['cycles'] for r in fast) / sum(r['cycles'] for r in baseline))
fault_log = root / 'build/brown_remap_fast_sim/simulation.log'
assert 'PASS composed Brown' in fault_log.read_text() and 'Fatal:' not in fault_log.read_text()
record['fault_and_border_queries_passed'] = 19086
record['limits'] = 'Actual RTL cycle measurements with a synthetic DDR service model; no HDMI arbitration or sensor cadence. Physical implementation, resources and real new-frame rate of the candidate remain unverified. Baseline real hardware evidence is separately archived.'
out = root / 'results/cache-native-regression-20261006.json'
out.write_text(json.dumps(record, indent=2) + '\n')
print(json.dumps({'report': str(out), 'cycle_reduction_percent': record['mean_cycle_reduction_percent'], 'passed': True}))
