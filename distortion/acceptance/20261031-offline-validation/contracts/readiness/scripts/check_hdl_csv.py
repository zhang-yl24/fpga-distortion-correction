from pathlib import Path
import csv,json,sys
p=Path(sys.argv[1] if len(sys.argv)>1 else 'readiness.csv')
lines=p.read_text().splitlines();assert lines and lines[-1]=='PASS','HDL terminal missing'
rows=list(csv.DictReader(lines[:-1]));assert len(rows)>20
for k in range(4):
 r=[z for z in rows if int(z['mode'])==k];assert r
 assert any(z['ready']=='1' for z in r) and any(z['phase']=='2' for z in r),'vacuous witness'
 for z in r:
  if z['reset_n']=='0':assert z['ready']=='0' and z['blocked']=='0' and z['phase']=='0'
  if k<3:assert z['phase']!='3' and not(z['ready']=='1' and z['blocked']=='1')
 assert r[-1]['ready']=='1' and r[-1]['blocked']=='0','fresh common-reset epoch did not recover'
 if k==3:assert any(z['phase']=='3' for z in r),'mutant not rejected'
print(json.dumps({'status':'READINESS_CONE_HDL_ORACLE_PASS','modes':4,'double_nonsticky_counterexample':True,'full_top_equivalence':False}))
