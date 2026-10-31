"""Finite safety overapproximation of the current top's readiness cone.

Countdown completions and RX completion/fault are arbitrary cutpoints, not
borrowed hardware successes. Both clocks may stop; simultaneous edges use NBA
old state. This is not a Verilog elaboration or physical metastability proof.
"""
from pathlib import Path
from typing import NamedTuple
from collections import deque
from itertools import product
import json,time,argparse

class S(NamedTuple):
 rst:int=0;rr:int=0;power:int=0;config:int=0;cfgpipe:int=0
 driverfail:int=0;latched:int=0;seqpipe:int=0;rxdone:int=0;rxsync:int=0;seen:int=0;guard_commit:int=0;guard_block:int=0

def cfg_n(s):return int(bool(s.rst and s.power and s.config))
def cfg_rst(s):return (s.cfgpipe>>2)&1
def failed(s):return s.driverfail or s.latched
def seq_async(s):return cfg_n(s) and not failed(s)
def seq_rst(s):return ((s.seqpipe>>2)&1) and cfg_rst(s) and not failed(s)
def rx_completion(s):return int(bool(seq_rst(s) and s.rxdone))
def ready(s):return int(bool(s.rst and s.power and s.rxsync&2))

def settle(s):
 # Asynchronous assertion closure. RX sequencer's init register is synchronous
 # and may retain its old value while cfg clock is stopped; do NOT clear it.
 d={}
 if not s.rst:d.update(rr=0,power=0,config=0,rxsync=0,seen=0,guard_commit=0,guard_block=0)
 t=s._replace(**d)
 if not cfg_n(t):t=t._replace(cfgpipe=0,latched=0)
 if not cfg_rst(t):t=t._replace(driverfail=0)
 if not seq_async(t):t=t._replace(seqpipe=0)
 if not t.rst:return t
 phase=t.seen
 if ready(t):phase=3 if phase in (2,3) else 1
 elif phase==1:phase=2
 return t._replace(seen=phase)

def step(s,r,c,pdone,cdone,rdone,error,mode,rxmeta):
 d={}
 if r:
  if not s.rst:d.update(rr=0,power=0,config=0,rxsync=0)
  else:
   d['rr']=((s.rr&1)<<1)|1
   d['power']=0 if not s.rr&2 else int(bool(s.power or pdone))
   d['config']=0 if not(s.rst and s.power) else int(bool(s.config or cdone))
   d['rxsync']=0 if not s.rr&2 else ((s.rxsync&1)<<1)|rxmeta
   if not s.rr&2:d.update(guard_commit=0,guard_block=0)
   elif s.guard_commit and not ready(s):d['guard_block']=1
   elif not s.guard_block and ready(s):d['guard_commit']=1
 if c:
  d['cfgpipe']=((s.cfgpipe&3)<<1)|1 if cfg_n(s) else 0
  d['latched']=int(bool(s.latched or s.driverfail)) if cfg_n(s) else 0
  if mode in ('no_latch','both_nonsticky'):d['latched']=0
  d['driverfail']=int(bool(s.driverfail or error)) if cfg_rst(s) else 0
  if mode in ('driver_nonsticky','both_nonsticky'):d['driverfail']=int(bool(error)) if cfg_rst(s) else 0
  d['seqpipe']=((s.seqpipe&3)<<1)|cfg_rst(s) if seq_async(s) else 0
  d['rxdone']=int(bool(s.rxdone or rdone)) if seq_rst(s) else 0
 return settle(s._replace(**d))

def edges(s,mode):
 if s.rst:yield 'COMMON_ASSERT',settle(s._replace(rst=0))
 else:yield 'COMMON_RELEASE',settle(s._replace(rst=1))
 for r,c,label in ((1,0,'REF'),(0,1,'CFG'),(1,1,'BOTH_OLD_STATE')):
  rxchoices=tuple(sorted({s.rxsync&1,rx_completion(s)})) if r else (0,)
  for pd,cd,rd,err,rxmeta in product((0,1) if r and not s.power else (0,),
   (0,1) if r and not s.config else (0,),
   (0,1) if c and not s.rxdone else (0,),
   (0,1) if c else (0,),rxchoices):
   yield f'{label}:power_done={pd},cfg_delay_done={cd},rx_finish={rd},fault={err},rxmeta={rxmeta}',step(s,r,c,pd,cd,rd,err,mode,rxmeta)

def explore(mode,seconds=20,limit=300000):
 starts=[settle(S(rxdone=i)) for i in (0,1)]
 parents={s:None for s in starts};q=deque(starts);start=time.monotonic();n=0;witness=None;status='EXHAUSTIVE_ABSTRACT_REACHABILITY_CLOSED'
 while q:
  if time.monotonic()-start>seconds or len(parents)>limit:status='INCOMPLETE_BOUND';break
  s=q.popleft()
  for action,t in edges(s,mode):
   n+=1
   if t.seen==3:
    status='READY_ONE_ZERO_ONE_COUNTEREXAMPLE';chain=[{'action':action,'state':t._asdict()}];a=s
    while parents[a] is not None:
     prev,act=parents[a];chain.append({'action':act,'state':a._asdict()});a=prev
    chain.append({'action':'INITIAL_COMMON_RESET_WITH_RX_REGISTER_MAY_RETAIN','state':a._asdict()});chain.reverse();witness=chain;q.clear();break
   if t not in parents:parents[t]=(s,action);q.append(t)
  if witness:break
 coverage={'ready_high_states':sum(ready(s) for s in parents),'after_high_then_low_states':sum(s.seen==2 for s in parents),'guard_blocked_states':sum(s.guard_block for s in parents),'guard_blocked_while_ready_states':sum(s.guard_block and ready(s) for s in parents)}
 if status=='EXHAUSTIVE_ABSTRACT_REACHABILITY_CLOSED':
  assert coverage['ready_high_states'] and coverage['after_high_then_low_states'] and coverage['guard_blocked_states'],'vacuous property'
  assert not coverage['guard_blocked_while_ready_states'],'sticky guard rejects a reachable ready-high state'
 return {'mode':mode,'status':status,'states':len(parents),'transitions':n,'seconds':time.monotonic()-start,'coverage':coverage,'counterexample':witness,'proof_boundary':'Finite digital source-cone abstraction, requires source writer/guard ledger; includes arbitrary first-stage hold/capture latency; not full RTL equivalence or analog CDC.'}

def main():
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,default=Path('evidence'));p.add_argument('--seconds',type=float,default=20);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
 results=[]
 for mode in ('baseline','driver_nonsticky','no_latch','both_nonsticky'):
  x=explore(mode,a.seconds);(a.out/f'{mode}.json').write_text(json.dumps(x,indent=2)+'\n',encoding='utf-8');results.append(x)
  print(json.dumps({k:v for k,v in x.items() if k!='counterexample'}),flush=True)
 assert all(x['status']=='EXHAUSTIVE_ABSTRACT_REACHABILITY_CLOSED' for x in results[:3])
 assert results[3]['status']=='READY_ONE_ZERO_ONE_COUNTEREXAMPLE'
 (a.out/'MODEL_RESULT.json').write_text(json.dumps({'status':'CONDITIONAL_DIGITAL_SINGLE_HIGH_INTERVAL_PROVED_IN_ABSTRACTION','results':[{k:v for k,v in x.items() if k!='counterexample'} for x in results],'strict_full_top_equivalence':False,'HDL_run':False,'physical_RDC':False},indent=2)+'\n',encoding='utf-8')
if __name__=='__main__':main()
