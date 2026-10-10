"""Bind isolated SCCB simulation to its actual sources; no hardware access."""
from pathlib import Path
import hashlib
import json
import re
import shutil

root = Path(__file__).resolve().parents[1]
work = root / 'build/camera_cadence_sim'
log = work / 'simulation.log'
text = log.read_text()
assert 'PASS camera cadence trial:' in text and not re.search(r'(?im)fatal:|error:', text)
files = ['rtl/reg16_i2c.v', 'rtl/experimental/ov5640_cadence_trial_init.v',
         'board/ov5640_cadence_trial_commands.vh', 'tests/tb_ov5640_cadence_trial.sv']
snapshot = work / 'source-snapshot'
hashes = {}
for rel in files:
    src = root / rel
    assert src.stat().st_mtime <= log.stat().st_birthtime
    dest = snapshot / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    hashes[rel] = hashlib.sha256(src.read_bytes()).hexdigest()
(snapshot / 'files-sha256.json').write_text(json.dumps(hashes, indent=2) + '\n')
result = {'passed': True, 'hardware_accessed': False, 'source_sha256': hashes,
          'simulation_sha256': hashlib.sha256(log.read_bytes()).hexdigest(),
          'scope': 'SCCB table writes/readback, preserved VGA RGB565 geometry and banding steps; wrong ID, unverified NACK, acknowledged pad and PLL-divider readback mismatches rejected. Does not prove physical PCLK, exposure quality, frame rate, DDR stability or temperature.'}
(root / 'results/lab-20261007/camera-cadence-simulation-check.json').write_text(json.dumps(result, indent=2) + '\n')
print('PASS: isolated cadence SCCB simulation source binding; no hardware accessed.')
