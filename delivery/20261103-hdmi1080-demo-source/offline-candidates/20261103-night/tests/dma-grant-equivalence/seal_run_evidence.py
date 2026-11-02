"""Copy only review evidence; omit generated binaries, no native-tree writes."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
RUN = ROOT / 'results/xsim_approved_pair_a'
OUT = ROOT / 'evidence/xsim_approved_pair_a'
result = json.loads((RUN / 'result.json').read_text())
assert result['status'] == 'PASS_PAIRED_HDL_AND_ORIGINAL_ORACLES'
OUT.mkdir(parents=True, exist_ok=False)
shutil.copyfile(RUN / 'result.json', OUT / 'result.json')
shutil.copyfile(ROOT / 'MANIFEST.json', OUT / 'EXECUTED_PACKAGE_MANIFEST.json')
files = ['compile.ps1', 'elaborate.ps1', 'simulate.ps1', 'compile.log', 'elaborate.log',
         'simulate.log', 'simulation.log', 'public_trace.csv', 'queue_events.csv',
         'queue_writes.csv', 'queue_descriptors.csv', 'queue_aw.csv']
for name in ('baseline', 'candidate'):
    (OUT / name).mkdir()
    for filename in files:
        source, target = RUN / name / filename, OUT / name / filename
        shutil.copyfile(source, target)
        assert hashlib.sha256(source.read_bytes()).digest() == hashlib.sha256(target.read_bytes()).digest()
subprocess.run([sys.executable, '-B', str(ROOT / 'build_package.py')], check=True, cwd=ROOT)
