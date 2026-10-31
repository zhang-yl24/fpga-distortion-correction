"""Finite CPU abstraction of the exact frozen reset/enable/req/ack/settle control.

No RTL tool or analog metastability model is invoked. First synchronizer stages
may hold or capture; second stages always read the OLD first stage (NBA).
The request timer permission is nondeterministic, admitting both arbitrarily
delayed and faster-than-RTL traffic. Actual 27000-cycle timing is a subset.
"""
from pathlib import Path
from typing import NamedTuple
from collections import deque
from itertools import product
from time import monotonic
import json,argparse,hashlib
ROOT=Path(__file__).resolve().parents[1]
class S(NamedTuple):
    rst:int=0;pr:int=0;rr:int=0;known:int=0;pen:int=0;ren:int=0;running:int=0;run_sync:int=0
    disabled:int=1;ready:int=0;reqsync:int=0;req:int=0;ack:int=0;acksync:int=0;seen:int=0
    settle:int=0;apply:int=0;held_seq:int=0;held_tag:int=0;arm_seq:int=0;arm_tag:int=0
    ref_seq:int=0;ref_tag:int=0;pclean:int=0;rclean:int=0;gap:int=0
PKEYS=('pr','known','pen','running','reqsync','ack','held_seq','held_tag','pclean')
RKEYS=('rr','ren','run_sync','disabled','ready','req','acksync','seen','settle','apply','arm_seq','arm_tag','ref_seq','ref_tag','rclean')
def enable(s):return int(bool(s.pr&2) and s.known)
def prun(s):return bool(s.pr&2 and s.pen&2)
def rrun(s):return bool(s.rr&2 and s.ren&2 and s.ready)
def choices(old,value):return (old,) if old==value else (old,value)
def shift(old,value):return ((old&1)<<1)|value
def pnext(s):
    resets=(0,) if not s.rst else choices(s.pr&1,1)
    metas=choices(s.reqsync&1,s.req) if prun(s) else (0,)
    knowns=(0,) if not s.pr&2 else ((1,) if s.known else (0,1))
    for reset,meta,known in product(resets,metas,knowns):
        d={'pr':0 if not s.rst else shift(s.pr,reset),'known':known}
        if not s.pr&2:d.update(pen=0,running=0)
        else:d.update(pen=shift(s.pen,enable(s)),running=int(bool(s.pen&2)))
        if not prun(s):d.update(reqsync=0,ack=0,held_seq=0,held_tag=0,pclean=1)
        else:
            d['reqsync']=shift(s.reqsync,meta)
            if (s.reqsync>>1)!=s.ack:d.update(ack=s.reqsync>>1,held_seq=(s.held_seq+1)%3,held_tag=s.reqsync>>1)
        yield d
def rnext(s):
    resets=(0,) if not s.rst else choices(s.rr&1,1)
    enables=choices(s.ren&1,enable(s)) if s.rr&2 else (0,)
    runs=choices(s.run_sync&1,int(bool(s.running and s.pr&2))) if s.rr&2 else (0,)
    acks=choices(s.acksync&1,s.ack) if rrun(s) else (0,)
    issues=(0,1) if rrun(s) and s.req==s.seen and not s.settle and not s.apply else (0,)
    for reset,en,run,ack,issue in product(resets,enables,runs,acks,issues):
        d={'rr':0 if not s.rst else shift(s.rr,reset)};error=None
        if not s.rr&2:d.update(ren=0,run_sync=0,disabled=1,ready=0)
        else:
            d.update(ren=shift(s.ren,en),run_sync=shift(s.run_sync,run))
            if not s.ren&2:d.update(ready=0,disabled=int(not bool(s.run_sync&2)))
            else:
                if not s.run_sync&2:d['disabled']=1
                if s.disabled and s.run_sync&2:d['ready']=1
        if not rrun(s):d.update(req=0,acksync=0,seen=0,settle=0,apply=0,arm_seq=0,arm_tag=0,ref_seq=0,ref_tag=0,rclean=1)
        else:
            d['acksync']=shift(s.acksync,ack)
            if issue:d['req']=s.req^1
            if s.apply:
                d['apply']=0
                if s.ref_tag!=s.seen:error='APPLY_DATA_TAG_NOT_ACK_SEEN'
            if s.settle:
                if not (s.pclean and s.rclean):error='CAPTURE_WITHOUT_BOTH_BUSINESS_RESET_DOMAINS_CLEARED'
                elif s.held_tag!=s.arm_tag:error='CAPTURE_DATA_TAG_DIFFERS_FROM_DETECTED_ACK'
                elif s.held_seq!=s.arm_seq:error='SOURCE_BUNDLE_CHANGED_DURING_SETTLE'
                d.update(ref_seq=s.held_seq,ref_tag=s.held_tag,apply=1,seen=s.acksync>>1,settle=0)
            elif (s.acksync>>1)!=s.seen:d.update(settle=1,arm_seq=s.held_seq,arm_tag=s.acksync>>1)
        yield d,error
