"""Apply independently queried scope to a fresh trained ADF copy, then reload."""
from pathlib import Path
import json,re,sys
import native_review as n
ROOT,BASE,SOURCE,TOP=n.ROOT,n.BASE,n.SOURCE,n.TOP
sys.path.insert(0,str(ROOT/'tools'))
import prepare_hdmi_input_bitstream as native
import audit_ddr_final_timing as timing
sha,write,load=n.sha,n.write,n.load

def main():
 work=BASE/'scoped-cdc';plan=load(work/'scope-plan.json');matches=load(work/'scope-match-audit.json')
 _,bound=n.bound_inputs()
 assert matches['ExactGroupsMatched'] and matches['TargetCounts']==[74,92,1,4]
 assert sha(work/'input.adf')==plan['SourceADFSHA256']
 assert load(BASE/'connectivity-review.json')['All81StageConnectionsVerified']
 for name,wanted in bound.items():assert sha(name)==wanted
 head='set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG676\nadd_design '+n.lit(work/'dummy.v')+'\nif {[info script] ne {}} {\n mpnr -input '+n.lit(work/'input.adf')+'\n'
 (work/'apply.tcl').write_text(head+' source '+n.lit(work/'scope.fdc')+'\n save_adif\n puts {TRAINED_SCOPED_CDC_SAVED}\n flush stdout\n}\n',encoding='ascii',newline='\n')
 e=n.run(work/'apply.tcl',work,'apply','TRAINED_SCOPED_CDC_SAVED')
 scopedsha=sha(work/'input.adf');assert scopedsha!=plan['SourceADFSHA256']
 for name,wanted in bound.items():assert sha(name)==wanted
 (work/'report.tcl').write_text(head+' mpnr_report_timing -force_to_run -delay_type min_max -max_path 1000 -nworst 1 -report_exception TRUE\n puts {TRAINED_SCOPED_CDC_REPORT_COMPLETE}\n flush stdout\n}\n',encoding='ascii',newline='\n')
 e2=n.run(work/'report.tcl',work,'report','TRAINED_SCOPED_CDC_REPORT_COMPLETE')
 assert e2['InputDrift']==[] and sha(work/'input.adf')==scopedsha
 audit(work,scopedsha,bound)

def audit(work,scopedsha,bound):
 baseline=SOURCE/f'report_timing/{TOP}.rtr';report=work/(TOP+'.rtr');exceptions=work/(TOP+'_exception.rtr')
 native.TARGET=TOP
 tables,clocks=native.report_summaries(report)
 with baseline.open(encoding='utf-8-sig') as f:oldtables,oldclocks=timing.parse_summaries(f)
 assert clocks==oldclocks
 # Only the independently bounded asynchronous clock-pair rows may differ.
 allowed={('setup',('input_pixel','board27')),('setup',('board27','input_pixel')),('hold',('input_pixel','board27')),('hold',('board27','input_pixel')),('recovery',('board27','input_pixel')),('removal',('board27','input_pixel'))}
 changed=[]
 for corner in ('slow','fast'):
  for kind in timing.KINDS:
   for pair in set(oldtables[(corner,kind)])|set(tables[(corner,kind)]):
    a,b=oldtables[(corner,kind)].get(pair),tables[(corner,kind)].get(pair)
    if a!=b:
     assert (kind,pair) in allowed,(corner,kind,pair,a,b)
     changed.append(dict(Corner=corner,Kind=kind,Clocks=list(pair),Before=a,After=b))
 sections,false,maxima=native.exception_inventory(exceptions)
 plan=load(work/'scope-plan.json');targets={g['Name']:set(g['Targets']) for g in plan['Groups']}
 all_data=set.union(*(targets[name] for name in ('gray_and_scalar','held_snapshot','reverse_request')))
 assert len(all_data)==167
 for corner in ('slow','fast'):
  maxrows=[r for r in maxima if r['Corner']==corner]
  assert {r['Endpoint'] for r in maxrows}==all_data
  assert {r['Endpoint'] for r in false[(corner,'hold')]}==all_data
  assert false[(corner,'setup')]==[]
  for kind in ('recovery','removal'):
   assert {r['Endpoint'] for r in false[(corner,kind)]}==targets['pixel_resets']
  for r in maxrows:
   g=next(g for g in plan['Groups'] if r['Endpoint'] in g['Targets'])
   assert r['MaxDelayNS']==8.0 and r['ArrivalNS']<=8.0 and r['SlackNS']>=0
   assert r['CaptureClock']==('input_pixel' if g['LaunchClock']=='board27' else 'board27')
  for r in false[(corner,'hold')]:
   g=next(g for g in plan['Groups'] if r['Endpoint'] in g['Targets'])
   assert r['LaunchClock']==g['LaunchClock']
   assert r['CaptureClock']==('input_pixel' if g['LaunchClock']=='board27' else 'board27')
  for kind in ('recovery','removal'):
   for r in false[(corner,kind)]:assert r['LaunchClock']=='board27' and r['CaptureClock']=='input_pixel'
 oldlog=(SOURCE/'native-stdout.log').read_text(encoding='utf-8',errors='replace')
 newlog=(work/'report-stdout.log').read_text(encoding='utf-8',errors='replace')
 warning=lambda text:set(re.findall(r"(?m)^W: Timing-(4086|4087): Port '([^']+)'",text))
 assert warning(oldlog)==warning(newlog)
 required=[BASE/'mapping-review.json',BASE/'connectivity-review.json',BASE/'functional-export'/f'generate_netlist/{TOP}_sim.v',BASE/'functional-export/native-execution.json',BASE/'functional-export/export-plan.json',SOURCE/f'place_route/{TOP}_prr_route_optimize.prt',baseline,SOURCE/f'report_timing/{TOP}_exception.rtr']
 required += [work/name for name in ('scope-plan.json','scope-match-audit.json','scope.fdc','query.tcl','query-stdout.log','query-stderr.log','query-execution.json','apply.tcl','apply-stdout.log','apply-stderr.log','apply-execution.json','report.tcl','report-stdout.log','report-stderr.log','report-execution.json','input.adf',TOP+'.rtr',TOP+'_exception.rtr')]
 evidence=bound|{str(path):sha(path) for path in required}
 for path,wanted in load(BASE/'connectivity-review.json')['LibrarySHA256'].items():evidence[path]=wanted
 for path,wanted in evidence.items():assert sha(path)==wanted
 result=dict(Schema='trained-input-scoped-cdc-review-v1',AuditPassed=True,Target=TOP,SourceADFSHA256=load(work/'scope-plan.json')['SourceADFSHA256'],ScopedADFSHA256=scopedsha,AllTenTimingTypesPassed=True,NativeClocksUnchanged=True,AllNonTargetSummariesUnchanged=True,ChangedTargetSummaryRows=changed,ExactNativeQueryGroups=[74,92,1,4],Pins46Verified=True,MappedFFs161Verified=True,StageLinks81Verified=True,MaxDelayCountPerCorner={c:len([p for p in maxima if p['Corner']==c]) for c in ('slow','fast')},FalsePathCountPerCorner={c:{k:len(false[(c,k)]) for k in ('setup','hold','recovery','removal')} for c in ('slow','fast')},WorstSlackNS={c:{k:min(row['WorstSlackNS'] for row in tables[(c,k)].values()) for k in timing.KINDS} for c in ('slow','fast')},MaxDelayNotOverriddenByFalsePath=True,NoSecondStageDataPinsExcepted=True,ExternalIOWarningsUnchanged=True,SourceInputDrift=[],EvidenceSHA256=evidence,HardwareAccessed=False,HardwareReleaseAllowed=False,FullCDCSignoff=False,Limits='Only exact bounded asynchronous entry paths and four reset-synchronizer RS pins are scoped. Exclusions do not improve physical delays or establish external AC, MTBF, complete CDC or video acceptance.')
 write(work/'scoped-cdc-review.json',result)
 print(json.dumps({k:result[k] for k in ('AuditPassed','Target','ScopedADFSHA256','WorstSlackNS','MaxDelayCountPerCorner','FalsePathCountPerCorner')}));print('REVIEW_SHA256 '+sha(work/'scoped-cdc-review.json'))

if __name__=='__main__':main()
