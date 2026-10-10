"""Seal completed twelve-angle native RTL evidence; no hardware access."""
from pathlib import Path
import csv
import hashlib
import json
import re

root = Path(__file__).resolve().parents[1]
work = root / 'build/pipeline_twelve_native_sim'
log_path = work / 'simulation.log'
log = log_path.read_text()
assert 'PASS pipeline twelve native regression: 3686400 real-camera pixels' in log
assert not re.search(r'(?im)fatal:|error:', log)
reference = json.loads((work / 'reference.json').read_text())
rows = list(csv.DictReader((work / 'cycles.csv').open()))
assert len(rows) == len(reference['frames']) == 12
frames = []
for i, (actual, expected) in enumerate(zip(rows, reference['frames'])):
    assert int(actual['phase']) == i and int(actual['pixels']) == expected['pixels'] == 307200
    assert actual['crc32'].upper() == expected['crc32'].upper()
    assert int(actual['cycles']) > 0 and int(actual['read_bursts']) > 0
    frames.append({**expected, 'rtl_cycles': int(actual['cycles']), 'rtl_read_bursts': int(actual['read_bursts']),
                   'rtl_process_ms_at_125mhz': int(actual['cycles']) / 125000})
snapshot = work / 'source-snapshot'
hashes = json.loads((snapshot / 'files-sha256.json').read_text())
for rel, digest in hashes.items():
    assert hashlib.sha256((snapshot / rel).read_bytes()).hexdigest() == digest
    assert hashlib.sha256((root / rel).read_bytes()).hexdigest() == digest
    assert (root / rel).stat().st_mtime <= log_path.stat().st_birthtime
result = {
    'passed': True, 'hardware_accessed': False, 'pixels_checked': 3686400,
    'angles': list(range(0, 360, 30)), 'source_sha256': hashes, 'frames': frames,
    'simulation_sha256': hashlib.sha256(log_path.read_bytes()).hexdigest(),
    'limits': 'Twelve full-size RTL frames using two sealed real-camera inputs, frame-locked settings, independent integer interpolation, all DDR beats and CRCs, synthetic stalls and immutable source checks. Six prior angle oracles retain matching CRCs. Numerical and RTL correctness only; optical accuracy, higher resolution, actual DDR throughput and finite physical stability remain separate evidence.',
}
out = root / 'results/lab-20261007/pipeline-twelve-native-check.json'
out.write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps({'passed': True, 'pixels_checked': result['pixels_checked'], 'angles': result['angles']}))
