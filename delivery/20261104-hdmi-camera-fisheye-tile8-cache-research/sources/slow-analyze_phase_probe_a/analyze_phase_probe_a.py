"""Reparse all actual cycle events; separate timing-stub conclusions from board FPS."""
from pathlib import Path
from collections import defaultdict
from datetime import datetime,timezone
import csv,hashlib,json,statistics

HERE=Path(__file__).resolve().parent
WORK=HERE/'phase-sweep-b'
REPO=HERE.parents[2]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def require(ok,message):
 if not ok:raise ValueError(message)

def main():
 receipt=json.loads((WORK/'simulation.json').read_text())
 require(receipt['Passed'] is True and receipt['InputDrift']==[] and len(receipt['Cases'])==40,'complete actual40case run required')
 for name,h in receipt['InputSHA256'].items():require(sha(Path(name))==h,'source drift')
 original=REPO/'distortion/work/hdmi-camera-fisheye-tile8df8-20261103-a/physical-release-provider-source-manifest-v3-a.json'
 require(sha(original)=='7b2c444b1e6e7d482c1875307fbc7b717689d0f5da9eaf8fac49ef249540a8fb','original source authority drift')
 pins=json.loads(original.read_text())['InputSHA256']
 for name,h in receipt['InputSHA256'].items():
  if '/rtl/' in name.replace('\\','/'):require(pins.get(name)==h,'probe compiled different production RTL')
 groups=defaultdict(list);cases=[];timeline=[]
 watch={str(WORK/'simulation.json'):sha(WORK/'simulation.json'),str(Path(__file__).resolve()):sha(Path(__file__)),str(original):sha(original)}
 for index,summary in enumerate(receipt['Cases']):
  path=WORK/(str(index).zfill(2)+'-events.csv');watch[str(path)]=sha(path)
  rows=[]
  for row in csv.DictReader(path.open()):
   rows.append({k:(v if k=='event' else int(v)) for k,v in row.items()})
  require(all(a['cycle']<=b['cycle'] for a,b in zip(rows,rows[1:])),'nonmonotonic event order')
  byid=defaultdict(dict);leases=[];lease=None;lastid=0;uniques=0;repeats=0
  for row in rows:
   event=row['event'];fid=row['id']
   if fid>0 and event not in ('display_grant','display_done'):
    require(event not in byid[fid],'duplicate source/processing identity event');byid[fid][event]=row['cycle']
   if event=='display_grant':
    require(lease is None,'overlapping lease in actual events');lease=row
   if event=='display_done':
    require(lease is not None and lease['id']==fid and lease['bank']==row['bank'],'lease ID/bank mismatch')
    require(row['cycle']-lease['cycle']==4000,'lease duration differs')
    leases.append({'ID':fid,'Bank':row['bank'],'GrantCycle':lease['cycle'],'DoneCycle':row['cycle']})
    if 4*4167<=row['cycle']<20*4167:
     if fid>lastid:uniques+=1
     elif fid==lastid:repeats+=1
     else:raise ValueError('backwards presented ID')
    lastid=fid;lease=None
  require(lease is None and uniques==summary['unique'] and repeats==summary['repeats'],'independent display event count differs')
  valid=[]
  for fid,row in sorted(byid.items()):
   needed=('capture_grant','source_offer','source_accept','engine_start','engine_done','pending_set','pending_clear')
   require(all(k in row for k in needed),'incomplete source/processing timeline')
   require(row['engine_done']-row['engine_start']==summary['process_stub_cycles']+1,'actual perID stub elapsed mismatch')
   first=next(l for l in leases if l['ID']==fid)
   require(first['GrantCycle']==row['pending_clear'],'published pending not consumed by first matching lease')
   values={'Case':index,'RequestedStubCycles':summary['process_stub_cycles'],'Phase':summary['phase'],'ID':fid,**row,
    'GrantToOffer':row['source_offer']-row['capture_grant'],'OfferToAccept':row['source_accept']-row['source_offer'],
    'AcceptToEngineStart':row['engine_start']-row['source_accept'],'StartToDone':row['engine_done']-row['engine_start'],
    'PendingWait':row['pending_clear']-row['pending_set'],'FirstDisplayDone':first['DoneCycle']}
   timeline.append(values)
   if 4*4167<=row['source_accept']<20*4167:valid.append(values)
  acceptcycles=[v['source_accept'] for v in valid]
  intervals=[b-a for a,b in zip(acceptcycles,acceptcycles[1:])]
  body={'Case':index,'RequestedStubCycles':summary['process_stub_cycles'],'ActualMeasuredBankProcessCycles':summary['last_measured_process_cycles'],
   'Phase':summary['phase'],'RefreshBoundaryCount':summary['refreshes'],'UniqueDoneInWindow':uniques,'RepeatDoneInWindow':repeats,
   'MatchedCompleteLeases':leases,'AcceptedIntervals':intervals,'MeanPendingWaitCycles':statistics.mean(v['PendingWait'] for v in valid),
   'MeanOfferToAcceptCycles':statistics.mean(v['OfferToAccept'] for v in valid),
   'WindowBoundaryCountingBasis':'unique/repeat by display_done in[4OP,20OP);refresh by boundary in same interval;first/last lease may straddle',
   'NormalizedRateIsFiniteTimingModelNotBoardMeasurement':True}
  cases.append(body);groups[summary['process_stub_cycles']].append(body)
 result={'Schema':'tile8-phase-probe-independent-cycle-analysis-v1','Passed':True,'CreatedUTC':datetime.now(timezone.utc).isoformat(),
  'ActualCaseCount':len(cases),'OriginalProductionSourcePinsMatchFrozen1038Map':True,
  'ActualPerFrameStubDurationValidatedEveryCase':True,'EveryDisplayGrantDoneIDBankPairReparsed':True,
  'TimeScaleVsBoard':1000,'InputPixelGeometry':[16,16],'InputPixelClockMHz':1000000/6734,
  'OutputModelPeriodCoreCycles':4167,'DisplayLeaseCoreCycles':4000,'EngineDurationStub':True,'DisplayLeaseModel':True,
  'FullDDRAndImagePipelineSimulated':False,'RealInputDMACaptureFIFOAndBankRTL':True,
  'Groups':[{'RequestedStubCycles':proc,'ActualBankProcessCycles':proc+1,'NormalizedMS':(proc+1)*1000/125000,
   'Phases':len(items),'UniqueDoneCountRange':[min(v['UniqueDoneInWindow'] for v in items),max(v['UniqueDoneInWindow'] for v in items)],
   'RepeatDoneCountRange':[min(v['RepeatDoneInWindow'] for v in items),max(v['RepeatDoneInWindow'] for v in items)],
   'AcceptedIntervalCycles':sorted({n for v in items for n in v['AcceptedIntervals']})} for proc,items in groups.items()],
  'Cases':cases,'RepresentativeID4Phase0':[t for t in timeline if t['ID']==4 and t['Phase']==0],
  'Recommendation':'Prioritize real DDR/miss service profiling and a bounded frame-processing reduction; do not require a scheduler rewrite merely to explain the current 15FPS. Scheduling robustness must still be validated in full system and board phases.',
  'Limits':['Fixed-time engine and lease stubs are not actual fisheye/DDR throughput.',
   'Periods scaled1000;unscaled CDC/DMA bookkeeping is relatively amplified.',
   'Finite16-period statistics can have a one-lease boundary difference;actual paired events retained.',
   'Frozen original sources are used;no scheduling RTL was optimized or board FPS changed.',
   'Only eight phases/five durations/specific frame geometry tested;not proof of all frequency/phase conditions.'],
  'EDAExecuted':False,'HardwareAccessed':False,'InputSHA256':watch,'InputDrift':[]}
 require(not (HERE/'phase-analysis-a.json').exists(),'fresh analysis required')
 with (HERE/'phase-timeline-a.csv').open('x',newline='') as f:
  writer=csv.DictWriter(f,fieldnames=list(timeline[0]));writer.writeheader();writer.writerows(timeline)
 with (HERE/'phase-analysis-a.json').open('x') as f:json.dump(result,f,indent=2);f.write('\n')
 print(json.dumps({'Passed':True,'Groups':result['Groups'],'OutputSHA256':sha(HERE/'phase-analysis-a.json')}))

if __name__=='__main__':main()
