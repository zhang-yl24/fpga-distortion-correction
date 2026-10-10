"""Same adaptive design and constraints, alternate placement seed; no hardware."""
from pathlib import Path
import hashlib
import json
import re
import shutil

root = Path(__file__).resolve().parents[1]
old, new = 'corrected_adaptive', 'corrected_adaptive_seed2'
old_top = (root / 'board' / (old + '.v')).read_text()
top = old_top.replace('module ' + old + '(', 'module ' + new + '(')
assert top != old_top and top.replace('module ' + new + '(', 'module ' + old + '(') == old_top
(root / 'board' / (new + '.v')).write_text(top)
tcl = (root / 'board' / ('build-' + old + '.tcl')).read_text().replace(old, new)
assert tcl.count('pnr -force_to_run') == 1
tcl = tcl.replace('pnr -force_to_run', 'pnr -force_to_run -gplace_seed 2')
(root / 'board' / ('build-' + new + '.tcl')).write_text(tcl)
for suffix in ('.fdc', '-pins.json'):
    shutil.copy2(root / 'board' / (old + suffix), root / 'board' / (new + suffix))
(root / 'board' / ('program-' + new + '.tcl')).write_text((root / 'board' / ('program-' + old + '.tcl')).read_text().replace(old, new))
sources = json.loads((root / 'board' / (old + '-sources.json')).read_text())
sources = [p.replace(old, new) for p in sources]
(root / 'board' / (new + '-sources.json')).write_text(json.dumps(sources, indent=2) + '\n')
for name in ('build-pds.ps1', 'program-heartbeat.ps1', 'read-telemetry.ps1'):
    path = root / 'tools' / name
    text = path.read_text(encoding='utf-8-sig')
    text = re.sub(r"(?:@|ValidateSet)\(([^)\n]*'corrected_adaptive'[^)\n]*)\)",
                  lambda m: m[0] if "'" + new + "'" in m[0] else m[0][:-1] + ",'" + new + "')", text)
    path.write_text(text, encoding='utf-8-sig')
hashes = {p: hashlib.sha256((root / p).read_bytes()).hexdigest() for p in sources}
result = {'hardware_accessed': False, 'target': new, 'placement_seed': 2,
          'router_thread_option': 'device default; no unsupported thread option',
          'top_equal_except_module_name': True,
          'pin_map_and_constraints_identical': all((root / 'board' / (old + s)).read_bytes() == (root / 'board' / (new + s)).read_bytes() for s in ('.fdc', '-pins.json')),
          'source_sha256': hashes,
          'limits': 'Alternative placement only; core/DDR/camera/HDMI clocks, hold fixes and pin constraints preserved. Build, final multi-corner timing and source hashes must pass before any physical configuration. Original adaptive board RTL/Tcl/constraints remain unchanged.'}
assert result['pin_map_and_constraints_identical']
(root / 'results/lab-20261007/adaptive-seed2-candidate.json').write_text(json.dumps(result, indent=2) + '\n')
print('Prepared seed-2 physical implementation; original adaptive sources unchanged.')
