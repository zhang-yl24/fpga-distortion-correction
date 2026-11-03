from pathlib import Path
import json,hashlib,re
R=Path(__file__).resolve().parents[1]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
for f in json.loads((R/'MANIFEST.json').read_text())['files']:
 p=R/f['path'];assert p.stat().st_size==f['bytes'] and sha(p)==f['sha256'],f['path']
ledger=json.loads((R/'evidence/SOURCE_LEDGER.json').read_text())
count=0
for z in ledger['writer_inventory']:
 p=R/'actual_self'/Path(z['source']).name
 if not p.exists():
  assert z['register']=='init_over' and not ledger['RX_vendor_derived_body_included'];continue
 assert sha(p)==z['sha256']
 rhs=[re.sub(r'\s+','',x) for x in re.findall(r'\b'+z['register']+r'\s*<=\s*([^;]+);',p.read_text())]
 assert rhs==z['writer_roles'];count+=1
for n in ('baseline','driver_nonsticky','no_latch'):
 d=json.loads((R/'evidence'/f'{n}.json').read_text());assert d['status']=='EXHAUSTIVE_ABSTRACT_REACHABILITY_CLOSED'
 assert d['coverage']['ready_high_states'] and d['coverage']['after_high_then_low_states']
 assert not d['coverage']['guard_blocked_while_ready_states']
assert json.loads((R/'evidence/both_nonsticky.json').read_text())['status']=='READY_ONE_ZERO_ONE_COUNTEREXAMPLE'
print(json.dumps({'status':'PAYLOAD_AND_SELF_SOURCE_BINDING_PASS','self_writer_inventories_checked':count,'restricted_RX_body_not_included':True,'RX_premise_static_checked_locally_not_cloud_elaborated':True,'HDL_status':'PENDING','full_top_equivalence':False}))
