from pathlib import Path
import hashlib,json,sys,copy
sys.dont_write_bytecode=True
from check_contract import check,REQUIRED
R=Path(__file__).resolve().parents[1]
b=json.loads((R/'evidence/SOURCE_BINDING.json').read_text())
raw=(R/'rtl/dvp_mode_admission_monitor_cdc.v').read_bytes();assert hashlib.sha256(raw).hexdigest()==b['frozen_helper_sha256']
c=(R/'rtl/dvp_mode_admission_monitor_epoch_candidate.v').read_text()
for a,z in reversed(b['changes']):assert c.count(z)==1;c=c.replace(z,a)
assert c.replace('\r\n','\n')==raw.decode().replace('\r\n','\n')
for n in ('dvp_mode_admission_monitor_cdc.v','dvp_mode_admission_monitor_epoch_candidate.v'):
 s=(R/'rtl'/n).read_text();assert s.count('or negedge rst_n')==2
 assert 'if(!rst_n)p_reset<=0;else p_reset<={p_reset[0],1\'b1};' in s
 assert 'if(!rst_n)r_reset<=0;else r_reset<={r_reset[0],1\'b1};' in s
# Independent reference model of the NEW guard only, not full RTL proof.
class Guard:
 def __init__(s):s.reset()
 def reset(s):s.rr=s.ps=s.commit=s.block=s.ready=0
 def ref(s,ready):
  oldrr,oldcommit=s.rr,s.commit
  s.rr=((s.rr&1)<<1)|1
  if not oldrr&2:s.commit=s.block=0
  elif oldcommit and not s.ready:s.block=1
  elif not s.block and s.ready:s.commit=1
  s.ready=ready
 def permit(s):return bool(s.rr&2 and s.commit and not s.block and s.ready)
 def pix(s):s.ps=((s.ps&1)<<1)|int(s.permit())
tests=0
for stopped in ('ref','pclk'):
 for prior in range(4):
  g=Guard();g.ps=g.rr=prior;g.commit=1;g.ready=1;g.reset()
  assert g.ps==g.rr==0 and not g.permit();tests+=1
  if stopped=='ref':
   for _ in range(64):g.pix();assert not g.ps&2 and not g.permit()
  else:
   for _ in range(8):g.ref(1)
   assert g.permit() and not g.ps&2
  tests+=1
g=Guard()
for _ in range(4):g.ref(1)
assert g.permit();g.pix();assert not g.ps&2;g.pix();assert g.ps&2;tests+=1
g.ref(0);assert not g.permit();g.ref(1);assert g.block and not g.permit()
for _ in range(16):g.ref(1);g.pix();assert not g.permit()
tests+=1
g.reset();assert not g.block and not g.permit();tests+=1
# Synthetic positive/negative event fixtures test the host ORACLE itself.
rows=[]
for c,labels in REQUIRED.items():
 e=3 if c==3 else 4 if c in (4,5,6) else 5 if c==7 else 8 if c==8 else c
 for label in labels:rows.append(dict(event='MARK',case=str(c),kind='-1',epoch=str(e),time='1',value=label))
 if c in (3,4,5,7,8):
  for k in (0,1):rows.append(dict(event='APPLY',case=str(c),kind=str(k),epoch=str(e),time='2',value='1'))
for code in ('SOURCE_BEFORE_REF_CLEAN','BUNDLE_CHANGED_AFTER_ACK_DETECTION'):
 rows.append(dict(event='ERROR',case='2',kind='2',epoch='2',time='1',value=code))
rows.append(dict(event='PASS',case='0',kind='-1',epoch='8',time='3',value='fixture'))
assert check(rows)['status']=='RESET_EPOCH_EVENT_ORACLE_PASS';tests+=1
mutants=[]
mutants.append(rows[:-1])
t=copy.deepcopy(rows);next(r for r in t if r['event']=='ERROR')['kind']='0';mutants.append(t)
t=copy.deepcopy(rows);next(r for r in t if r['event']=='APPLY' and r['case']=='7')['epoch']='4';mutants.append(t)
t=copy.deepcopy(rows);next(r for r in t if r['event']=='APPLY')['value']='0';mutants.append(t)
mutants.append([r for r in rows if r['event']!='ERROR'])
mutants.append([r for r in rows if not(r['event']=='MARK' and r['case']=='6')])
t=copy.deepcopy(rows);t.insert(-1,dict(event='APPLY',case='6',kind='1',epoch='4',time='2',value='1'));mutants.append(t)
for t in mutants:
 try:check(t)
 except AssertionError:tests+=1
 else:raise AssertionError('oracle accepted negative fixture')
out={'status':'CPU_PREPARATION_PASS_HDL_NOT_RUN','tests':tests,'negative_oracle_fixtures':len(mutants),'candidate_inverse_diff_matches_frozen_helper':True,'two_raw_reset_synchronizers_retained':True,'candidate_protocol_equivalence_accepted':False}
(R/'evidence/CPU_PREPARATION.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
