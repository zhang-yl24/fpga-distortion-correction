"""Compare actual native simulation cycles with sealed previous cache outputs."""
from pathlib import Path
import csv
import hashlib
import json
import re

root = Path(__file__).resolve().parents[1]
work = root / 'build/paired_cache_native_sim'
checks = {'native': 'PASS paired cache native regression: 1843200',
          'query': 'PASS paired cache composed rotation', 'video': 'PASS paired DDR video:'}
source_hashes={}
for kind, marker in checks.items():
    folder = root / ('build/paired_cache_' + kind + '_sim')
    text = (folder / 'simulation.log').read_text()
    assert marker in text and not re.search(r'(?im)fatal:|error:', text), kind
    hashes = json.loads((folder / 'source-snapshot/files-sha256.json').read_text())
    for name, digest in hashes.items():
        src = root / ('tests' if name.startswith('tb_') else 'rtl/experimental') / name
        assert hashlib.sha256(src.read_bytes()).hexdigest() == digest
        assert hashlib.sha256((folder / 'source-snapshot' / name).read_bytes()).hexdigest() == digest
        assert src.stat().st_mtime <= (folder / 'simulation.log').stat().st_birthtime
        source_hashes[str(src.relative_to(root))]=digest
rows = list(csv.DictReader((work / 'cycles.csv').open()))
base = json.loads((root / 'results/lab-20261007/short-burst-native-check.json').read_text())['frames']
adaptive = json.loads((root / 'results/lab-20261007/adaptive-native-check.json').read_text())['frames']
assert len(rows) == len(base) == len(adaptive) == 6
frames = []
for row, old, tile in zip(rows, base, adaptive):
    assert int(row['pixels']) == 307200 and row['crc32'].upper() == old['crc32'].upper() == tile['crc32'].upper()
    cycles = int(row['cycles'])
    assert int(row['read_bursts']) == old['read_bursts'], 'Cycle optimization unexpectedly changed DDR request count'
    frames.append({'angle_deg': old['angle_deg'], 'pixels': 307200, 'crc32': row['crc32'],
        'paired_cycles': cycles, 'previous_short_burst_cycles': old['short_8_beat_cycles'],
        'adaptive_16_beat_cycles': tile['adaptive_cycles'], 'read_bursts': int(row['read_bursts']),
        'process_ms_at_125mhz': cycles / 125000,
        'cycle_reduction_from_short_burst_percent': (1 - cycles / old['short_8_beat_cycles']) * 100,
        'cycle_reduction_from_adaptive_16_beat_percent': (1 - cycles / tile['adaptive_cycles']) * 100})
result = {'passed': True, 'hardware_accessed': False, 'pixels_checked': 1843200, 'frames': frames,
          'source_sha256':source_hashes,
          'query_fault_regression_passed': True, 'mixed_burst_camera_hdmi_simulation_passed': True,
          'strategy': 'Direct computed-line tag check, paired horizontal neighbors from one synchronous RAM beat, 32 cache lines with 8-beat bursts; raster near 0/180 and tiles otherwise.',
          'limits': 'Six native frames and 2322 independent query oracles, plus small three-clock camera/DDR/HDMI test with mixed 8/16-beat reads, ownership, CRC, malformed-response and reset checks. Synthetic DDR model; not a board target. Controller compatibility, routed timing, physical bandwidth, FPS and temperature still require validation.'}
(root / 'results/lab-20261007/paired-cache-native-check.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps({'passed': True, 'frames': frames}, indent=2))
