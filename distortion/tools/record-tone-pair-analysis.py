"""Bind analysis tests and synthetic native demonstration to current sources."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
lab = root / 'results/lab-20261007'
read = lambda path: json.loads(path.read_text(encoding='utf-8-sig'))
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest().upper()
run = subprocess.run([sys.executable, str(root/'tests/test_tone_pair_analysis.py')], capture_output=True, text=True)
(lab/'gamma-pair-analysis-tests.log').write_text(run.stdout+run.stderr, encoding='utf-8')
assert run.returncode == 0 and 'Ran 6 tests' in run.stderr and 'OK' in run.stderr
report = read(lab/'gamma-synthetic-pair-analysis.json')
native = read(lab/'gamma-tone-simulation-check.json')
assert native['passed'] and report['exact_tone_pixels_passed']
assert report['provenance']['source_kind'] == 'synthetic_same_source'
assert report['shape'] == [480, 640]
for path, digest in report['input_sha256'].items():assert sha(Path(path)).lower() == digest.lower()
for relative, digest in native['source_sha256'].items():assert sha(root/relative) == digest.upper()
names = ['tools/evaluate-tone-pair.py','tools/plot-gamma-native-proof.py','tools/record-tone-pair-analysis.py','tests/test_tone_pair_analysis.py']
check = {'passed': True, 'tests_passed': 6, 'source_sha256': {name: sha(root/name) for name in names},
    'native_tone_check_sha256': sha(lab/'gamma-tone-simulation-check.json'),
    'analysis_sha256': sha(lab/'gamma-synthetic-pair-analysis.json'),
    'hardware_accessed': False, 'physical_low_light_comparison': False,
    'scope': 'Same-source metadata validation, masked geometry exclusion, exact tone output and intensity distribution analysis. Native demonstration uses a sealed synthetic dark-frame regression; it is not a physical optical measurement.'}
(lab/'gamma-pair-analysis-check.json').write_text(json.dumps(check, indent=2)+'\n', encoding='utf-8')
print(json.dumps({'passed': True, 'tests_passed': 6, 'physical_low_light_comparison': False}))
