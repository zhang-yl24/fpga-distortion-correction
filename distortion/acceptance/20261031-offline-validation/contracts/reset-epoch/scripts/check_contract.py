"""Independent event/epoch acceptance for the HDL CSV, never RTL output self-PASS."""
import csv,json,sys
from pathlib import Path
REQUIRED={1:{'MATURE_REAL_27000_TIMER','OUTSTANDING_REQ_ONE'},
2:{'REF_STOP_PROTECTED','RAW_GUARD_REMOVAL_REJECTED'},3:{'FRESH_EPOCH_PUBLISHED'},
4:{'PCLK_STOP_PROTECTED','FRESH_EPOCH_PUBLISHED'},5:{'REF_RESUME_NO_RESET','FRESH_EPOCH_PUBLISHED'},
6:{'READY_BOUNCE_FAIL_CLOSED'},7:{'FRESH_EPOCH_PUBLISHED'},
8:{'FRESH_EPOCH_PUBLISHED','ASYNC_PHASE_ORDERS_CHECKED'}}
def check(rows):
 assert rows and rows[-1]['event']=='PASS','Missing terminal PASS; partial CSV is incomplete'
 assert sum(r['event']=='PASS' for r in rows)==1
 marks={c:set() for c in REQUIRED};negative=set();applies={0:[],1:[]}
 for r in rows:
  ev,c,k,e=r['event'],int(r['case']),int(r['kind']),int(r['epoch'])
  if ev=='MARK':marks[c].add(r['value'])
  elif ev=='ERROR':
   assert k==2,('protected DUT error',r)
   assert r['value'] in {'SOURCE_BEFORE_REF_CLEAN','BUNDLE_CHANGED_AFTER_ACK_DETECTION'},r
   negative.add(r['value'])
  elif ev=='APPLY' and k in applies:
   assert int(r['value'])>0,'Publication has no real fresh valid frames'
   applies[k].append((c,e))
 for c,v in REQUIRED.items():assert v<=marks[c],('missing coverage',c,v-marks[c])
 assert negative=={'SOURCE_BEFORE_REF_CLEAN','BUNDLE_CHANGED_AFTER_ACK_DETECTION'}
 for k,v in applies.items():
  assert len(v)>=5 and {3,4,5,7,8}<={c for c,e in v}
  assert all(e==3 for c,e in v if c==3)
  assert all(e==4 for c,e in v if c in (4,5))
  assert all(e==5 for c,e in v if c==7)
  assert all(e==8 for c,e in v if c==8)
 assert not any(r['event']=='APPLY' and int(r['kind'])==1 and int(r['case'])==6 for r in rows)
 return {'status':'RESET_EPOCH_EVENT_ORACLE_PASS','coverage_cases':8,'protected_applies':{str(k):len(v) for k,v in applies.items()},'unsafe_raw_negative_rejected':True,'Analog_RDC_accepted':False}
if __name__=='__main__':
 rows=list(csv.DictReader(Path(sys.argv[1] if len(sys.argv)>1 else 'contract.csv').open()))
 result=check(rows);print(json.dumps(result,indent=2))
