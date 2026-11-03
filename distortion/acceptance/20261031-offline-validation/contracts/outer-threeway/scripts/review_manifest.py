from pathlib import Path
import json,hashlib
R=Path(__file__).resolve().parents[1]
for z in json.loads((R/'MANIFEST.json').read_text())['files']:
 p=R/z['path'];assert p.stat().st_size==z['bytes'] and hashlib.sha256(p.read_bytes()).hexdigest()==z['sha256'],z['path']
b=json.loads((R/'evidence/SOURCE_BINDING.json').read_text())
for n,k in [('hdmi1080_input_status_cdc.v','original_outer_sha256'),('dvp_mode_admission_monitor_cdc.v','original_inner_sha256'),('observer_epoch_guard_candidate.sv','current_guard_sha256'),('dvp_mode_admission_monitor_epoch_candidate.v','current_guard_inner_sha256')]:
 assert hashlib.sha256((R/'rtl'/n).read_bytes()).hexdigest()==b[k],n
for z in b['new_candidates']:assert hashlib.sha256((R/'rtl'/z['file']).read_bytes()).hexdigest()==z['sha256']
assert not b['RX_vendor_body_included'] and not b['production_RTL_changed']
print('PASS: payload hashes,2frozen originals,existing guard/helper,isolated candidates. HDL PENDING.')
