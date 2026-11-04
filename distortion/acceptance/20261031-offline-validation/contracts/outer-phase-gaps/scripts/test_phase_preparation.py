from pathlib import Path
import json,hashlib,copy,sys
sys.dont_write_bytecode=True
from check_phase_gaps import check
R=Path(__file__).resolve().parents[1]
scope=json.loads((R/'evidence/BASE_AND_PHASE_SCOPE.json').read_text())
for z in scope['frozen_RTL_unchanged']:assert hashlib.sha256((R/z['path']).read_bytes()).hexdigest()==z['sha256']
assert len(scope['frozen_RTL_unchanged'])==7
o=[]
for c,phase in [(1,'ACTUAL_READY_BEFORE_VS'),(2,'ACTUAL_READY_AT_DE_RISE')]:
 for label in (phase,'ALL_QUALIFIED','TERMINAL_INVALID'):o.append(dict(event='MARK',case=str(c),kind='-1',epoch=str(c),time='1',a=label,b='0',c='0'))
 o.append(dict(event='QUALIFIED',case=str(c),kind='-1',epoch=str(c),time='2',a='2',b='2',c='2'))
 for k in range(3):o.append(dict(event='APPLY',case=str(c),kind=str(k),epoch=str(c),time='2',a='0',b='0',c='0'))
o.extend([dict(event='SUMMARY',case='0',kind='-1',epoch='2',time='3',a='1000',b='5',c='2'),dict(event='PASS',case='0',kind='-1',epoch='2',time='3',a='fixture',b='0',c='0')])
p=[dict(event='VS_BEFORE',case='1',ready_ns='100.000',ready_x='15',ready_y='5',edge_ns='113.316',edge_x='0',edge_y='6',delta_ns='13.316'),dict(event='DE_SAME_EDGE',case='2',ready_ns='200.000',ready_x='1',ready_y='0',edge_ns='200.000',edge_x='1',edge_y='0',delta_ns='0.000'),dict(event='PASS',case='0')]
check(o,p);mutants=[]
q=copy.deepcopy(p);q[0]['ready_x']='1';mutants.append((o,q))
q=copy.deepcopy(p);q[1]['edge_ns']='200.001';mutants.append((o,q))
q=copy.deepcopy(p);q[0]['delta_ns']='0.000';mutants.append((o,q))
mutants.append((o,p[:-1]));mutants.append((o[:-1],p))
for a,b in mutants:
 try:check(a,b)
 except AssertionError:pass
 else:raise AssertionError('phase oracle accepted false hit')
print(json.dumps({'status':'PHASE_PATCH_CPU_PREPARATION_PASS_HDL_PENDING','unchanged_RTL_hashes':7,'oracle_negative_fixtures':len(mutants),'new_HDL_cases_only':2}))
