"""Reproduce the standalone helper reset contract boundary with the REAL timer.

This is a source-control CPU projection, not a full-Verilog or analog run.
The actual top excludes the demonstrated raw-reset-release environment.
"""
from pathlib import Path
import json,sys
sys.dont_write_bytecode=True
from protocol_model import S,pnext,rnext,rrun
ROOT=Path(__file__).resolve().parents[1]
s=S(rst=1,pr=3,rr=3,known=1,pen=3,ren=3,running=1,run_sync=3,ready=1,pclean=1,rclean=1)
timer=0;N=27000;events=[];number=0;failure=None
def step(action,record=True):
    global s,timer,number,failure
    old=s;d={};error=None
    if action=='ASSERT_COMMON_RESET':s=s._replace(rst=0,pr=0,rr=0,pclean=0,rclean=0)
    elif action=='RELEASE_COMMON_RESET':s=s._replace(rst=1)
    else:
        if action in ('PCLK','BOTH'):d.update(list(pnext(old))[-1])
        if action in ('REFCLK','BOTH'):
            rd,error=list(rnext(old))[-1]
            if not rrun(old):timer=0
            else:
                issue=old.req==old.seen and not old.settle and not old.apply and timer==N-1
                rd['req']=old.req^1 if issue else old.req
                timer=0 if issue else min(N-1,timer+1)
            d.update(rd)
        s=s._replace(**d)
    number+=1
    if error:failure=error
    if record:events.append({'Event':number,'Action':action,'Timer':timer,'State':s._asdict(),'Violation':error})
    return error
# A mature active epoch is reachable; source control remains stable while
# the real reference request interval counts all 27000 cycles.
for _ in range(N):step('BOTH',False)
assert s.req==1 and s.ack==0 and timer==0
events.append({'Event':number,'Action':'27000_REAL_TIMER_REFERENCE_TICKS_COMPLETED','Timer':timer,'State':s._asdict()})
step('ASSERT_COMMON_RESET');step('RELEASE_COMMON_RESET')
for _ in range(10):step('PCLK')
assert s.ack==1 and s.held_tag==1 and s.req==1
# Additional PCLK edges are a control fixed point. In the actual data path,
# valid source frames can advance live counters while held_snapshot stays A.
fixed=s
for _ in range(8):step('PCLK',False)
assert s==fixed
events.append({'Event':number,'Action':'PCLK_CONTROL_FIXED_POINT_LIVE_FRAME_COUNTERS_MAY_PROGRESS','State':s._asdict()})
for _ in range(8):step('REFCLK')
assert s.settle==1 and s.arm_tag==1 and s.req==0 and timer<N-1
# Input clock restarts with three edges inside one 37.037037 ns reference
# period: offsets 1, 14.315579, 27.631158 ns are a feasible sequence.
for _ in range(3):step('PCLK')
assert s.held_tag==0 and s.ack==0
error=step('REFCLK')
assert error=='CAPTURE_DATA_TAG_DIFFERS_FROM_DETECTED_ACK'
out={'Status':'HELPER_ONLY_RESET_RELEASE_CONTRACT_COUNTEREXAMPLE_REPLAYED','TimerCycles':N,'FirstStageSampling':'Deterministic current sample, no extra metastability delay',
     'Violation':error,'Events':events,'CPUProjectionNotFullRTL':True,
     'PayloadWitness':'Held bundle A is captured on stale retained request=1 after raw reset; live source frame counters can change while ref clock is stopped; B is captured on request=0 immediately before receiver consumes ACK=1.',
     'IntegrationReachability':'Excluded by actual top: observer_reset_n cannot rise while board reference clock has not performed a clearing edge, because power_ready/rx_done_ref are reference-clocked and asynchronously cleared. This is NOT a demonstrated integrated-top defect.',
     'FixRecommendation':'Make this reset-release guard an explicit helper integration precondition. If reused with truly independent raw-reset release, add a proven epoch/reinitialization handshake in a separate candidate rather than a timing exception.',
     'EDAStarted':False,'SourceChanged':False}
(ROOT/'evidence/helper-boundary-counterexample.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps({k:v for k,v in out.items() if k!='Events'},indent=2))
