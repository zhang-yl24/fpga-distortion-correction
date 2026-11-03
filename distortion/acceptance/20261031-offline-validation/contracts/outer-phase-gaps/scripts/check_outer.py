from pathlib import Path
import csv,json,sys
REQUIRED={c:{'ALL_QUALIFIED','TERMINAL_INVALID'} for c in range(1,10)}
REQUIRED[5]|={'RATE25','TIMING24_OVER_RATE25','GEOMETRY_OVER_TIMING_RATE'}
REQUIRED[6]|={'PENDING_APPLY_TERMINAL_BOUNDARY'}
REQUIRED[7]|={'REF_STOP_INVALID'}
REQUIRED[8]|={'PIXEL_STOP_INVALID'}
REQUIRED[9]|={'TIMING_TERMINAL_SAME_REF'}
def check(rows):
 assert rows and rows[-1]['event']=='PASS','No complete terminal'
 assert sum(x['event']=='PASS' for x in rows)==1
 marks={c:set() for c in REQUIRED};qualified={};ready_cases=set();summaries=[];diffs=[];applies=[0,0,0]
 for z in rows:
  c,k,e=int(z['case']),int(z['kind']),int(z['epoch'])
  if z['event'] in ('MARK','QUALIFIED','READY','APPLY','CURRENT_PUBLIC_DIFF'):
   assert e==c,('old epoch',z)
  if z['event']=='MARK':marks[c].add(z['a'])
  elif z['event']=='QUALIFIED':
   assert c not in qualified and all(int(z[f])>=2 for f in ('a','b','c'));qualified[c]=z
  elif z['event']=='READY':
   assert c in range(1,7) or c==9
   assert 0<=int(z['a'])<16 and 0<=int(z['b'])<8
   ready_cases.add(c)
  elif z['event']=='SUMMARY':summaries.append(z)
  elif z['event']=='CURRENT_DIFF_COUNT':diffs.append(z)
  elif z['event']=='APPLY':assert k in (0,1,2);applies[k]+=1
 for c,s in REQUIRED.items():assert s<=marks[c],('missing coverage',c,s-marks[c])
 assert set(qualified)==set(range(1,10)) and {1,2,3,4}<=ready_cases
 assert len(summaries)==len(diffs)==1
 s=summaries[0];assert int(s['a'])>100 and int(s['b'])>0 and int(s['c'])>0
 assert all(n>=9 for n in applies),('vacuous fresh snapshots',applies)
 assert rows[-1]['epoch']=='9'
 return {'status':'THREEWAY_DIRECTED_CONTRACT_COMPLETE','cases':9,'baseline_vs_small_public_checks':int(s['a']),'current_guard_public_differences':int(diffs[0]['a']),'current_gate_phase_differences_observed':True,'current_guard_production_equivalence':False,'small_candidate_full_top_equivalence':False,'physical_RDC_accepted':False}
if __name__=='__main__':
 rows=list(csv.DictReader(Path(sys.argv[1] if len(sys.argv)>1 else 'outer.csv').open()));print(json.dumps(check(rows),indent=2))
