from pathlib import Path
import csv,json,sys
from decimal import Decimal as D
def check(outer,phases):
 assert outer and outer[-1]['event']=='PASS' and outer[-1]['epoch']=='2','Incomplete outer run'
 assert phases and phases[-1]['event']=='PASS','Incomplete phase evidence'
 hits=[x for x in phases if x['event']!='PASS'];assert len(hits)==2
 bycase={int(x['case']):x for x in hits};assert set(bycase)=={1,2}
 v=bycase[1];assert v['event']=='VS_BEFORE'
 assert (int(v['ready_x']),int(v['ready_y']))==(15,5)
 assert (int(v['edge_x']),int(v['edge_y']))==(0,6)
 dt=D(v['edge_ns'])-D(v['ready_ns']);assert dt==D(v['delta_ns'])==D('13.316'),'VS must follow ready by one actual PCLK'
 d=bycase[2];assert d['event']=='DE_SAME_EDGE'
 assert (int(d['ready_x']),int(d['ready_y']))==(1,0)
 assert (int(d['edge_x']),int(d['edge_y']))==(1,0)
 assert D(d['edge_ns'])==D(d['ready_ns']) and D(d['delta_ns'])==0,'DE rise must coincide with ready rise'
 required={1:{'ACTUAL_READY_BEFORE_VS','ALL_QUALIFIED','TERMINAL_INVALID'},2:{'ACTUAL_READY_AT_DE_RISE','ALL_QUALIFIED','TERMINAL_INVALID'}}
 marks={1:set(),2:set()};q=set();applies=[0,0,0];summ=[]
 for z in outer:
  c=int(z['case'])
  if z['event'] in ('MARK','QUALIFIED','APPLY','CURRENT_PUBLIC_DIFF'):assert int(z['epoch'])==c
  if z['event']=='MARK':marks[c].add(z['a'])
  elif z['event']=='QUALIFIED':assert c not in q and all(int(z[f])>=2 for f in ('a','b','c'));q.add(c)
  elif z['event']=='APPLY':applies[int(z['kind'])]+=1
  elif z['event']=='SUMMARY':summ.append(z)
 for c,s in required.items():assert s<=marks[c]
 assert q=={1,2} and all(x>=2 for x in applies)
 assert len(summ)==1 and int(summ[0]['a'])>100 and int(summ[0]['b'])>0 and int(summ[0]['c'])>0
 return {'status':'MISSING_ACTUAL_READY_PHASES_CONFIRMED','cases':2,'ready_before_VS_ns':'13.316','ready_DE_same_edge':True,'strict_baseline_small_public_checks':int(summ[0]['a']),'production_equivalence':False}
if __name__=='__main__':
 outer=list(csv.DictReader(Path(sys.argv[1] if len(sys.argv)>1 else 'outer.csv').open()));phases=list(csv.DictReader(Path(sys.argv[2] if len(sys.argv)>2 else 'phases.csv').open()));print(json.dumps(check(outer,phases),indent=2))
