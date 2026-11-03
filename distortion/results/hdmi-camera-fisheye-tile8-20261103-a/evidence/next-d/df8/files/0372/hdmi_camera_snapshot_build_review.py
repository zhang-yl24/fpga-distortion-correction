"""Read-only continuation of a completed snapshot build with two exact C rows.

Original receipts/diagnostics stay unchanged. Exact source interval proofs cover
the additional native_pixels/row_pixels reductions only. Same-domain timing
failures remain failures; this report grants no application/bit/hardware release.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import re

import hdmi_camera_snapshot_build as build

SELF=Path(__file__).resolve()
SCHEMA='hdmi-camera-snapshot-readonly-build-review-v1'
require,sha,read,ref=build.require,build.sha,build.read,build.ref


def counter_ranges(source):
    text=re.sub(r'/\*.*?\*/|//[^\r\n]*','',source,flags=re.S);flat=re.sub(r'\s+','',text)
    guard=("if(row_pixels>=NATIVE_WIDTH||line_count>=NATIVE_HEIGHT||native_pixels>=PIXELS)"
        "finish_frame(8'h24);elsebeginrow_pixels<=row_pixels+1'b1;native_pixels<=native_pixels+1'b1;end")
    require(flat.count(guard)==1,'snapshot guarded pixel increment changed')
    expected={'native_pixels':['0','0',"native_pixels+1'b1"],
        'row_pixels':['0','0','0',"row_pixels+1'b1",'0']}
    require('localparamintegerPIXELS=NATIVE_WIDTH*NATIVE_HEIGHT,BYTES=WIDTH*HEIGHT;' in flat,
        'native pixel terminal definition changed')
    rows=[]
    for name,old,new,maximum in (('native_pixels',32,21,1920*1080),('row_pixels',12,11,1920)):
        assignments=re.findall(name+r'<=([^;]+);',flat)
        require(assignments==expected[name],'additional/different counter assignment: '+name)
        require(0<=maximum<(1<<new),'snapshot terminal does not fit reduced width')
        rows.append({'Accumulator':name,'OriginalBits':old,'ReducedBits':new,'MaximumAfterReset':maximum,
            'Assignments':assignments,'ResetBaseZeroVerified':True,'HoldPreservesBound':True,
            'GuardedIncrementPreservesBound':True,'TerminalFitsReducedUnsignedWidth':True,
            'SourceIntervalProofPassed':True,'UnknownUnresetPowerUpStateAccepted':False})
    return rows


def derive(receipt_path):
    receipt_path=Path(receipt_path).absolute();work=build.work_path(receipt_path.parent)
    require(receipt_path==work/'execution-result.json','exact snapshot source receipt required')
    value=read(receipt_path);plan_path=work/'plan.json';plan=build.validate(plan_path)
    require(value.get('Schema')=='hdmi-camera-snapshot-build-execution-v1' and value.get('Target')==build.TARGET
        and value.get('BuildCompleted') is False,'original failed snapshot receipt required')
    require(value['PlanSHA256']==sha(plan_path) and value['Command']==plan['Command'] and value['ExitCode']==0
        and value['EDAExecuted'] is True and value['TimedOut'] is False and value['StoppedForUnexpectedStage'] is False
        and not value.get('Error') and value['InputDrift']==[] and value['Cleanup']['Complete'] is True
        and value['Cleanup']['ParentExited'] is True,'snapshot native work did not finish cleanly')
    logs={p.relative_to(work).as_posix():sha(p) for p in work.rglob('*.log')}
    log=(work/'stdout.log').read_text(encoding='gb18030',errors='strict')
    require(value['NativeLogSHA256']==logs and value['Diagnostics']==build.diagnostics(work)
        and value['ActualEvents']==build.events(log)==[[s,e] for s in build.STAGES for e in ('started','done')],
        'snapshot source logs/events differ')
    errors=build.diagnostic_errors(value['Diagnostics'],plan)
    native=build.paths.alias_path(build.ROOT,plan['RepoAlias'],work)
    expected=[]
    for logname in ('compile/run.log','flow.log','run.log','stdout.log'):
        for name,old,new in (('native_pixels',32,21),('row_pixels',12,11)):
            body='C: Sdm-3003: ['+native+'/compiled/'+build.CAPTURE+'(line number: 90)] Reduce accumulator '+name+' size from '+str(old)+' to '+str(new)+'. If this is not intended behavior, please drive '+name+' with valid values.'
            expected.append(logname+': '+body)
    require(errors==value['NativeErrors'] and Counter(errors)==Counter(expected),
        'unknown/missing/duplicate critical snapshot diagnostics')
    source=work/'compiled'/build.CAPTURE
    ranges=counter_ranges(source.read_text(encoding='utf-8-sig'))
    compile_text=(work/'compile/run.log').read_text(encoding='gb18030',errors='strict')
    instance=re.search(r'I: Module instance \{'+re.escape(build.TARGET)+r'/capture\} parameter value:\n((?:    .+\n)+)',compile_text)
    require(instance is not None and all(re.search(r'\b'+key+r' = .*\(\d+\x27d'+str(number)+r'\)',instance[1])
        for key,number in (('NATIVE_WIDTH',1920),('NATIVE_HEIGHT',1080),('TIMEOUT_BITS',26))),
        'actual capture width/height/timeout parameters differ')
    adf=work/'place_route'/(build.TARGET+'_pnr.adf');report=work/'report_timing'/(build.TARGET+'.rtr')
    require(value['ADF']==str(adf) and value['ADFSHA256']==sha(adf) and value['TimingReport']==ref(report),
        'snapshot source ADF/report binding differs')
    require(value['MemoryResourceReview']==build.memory_resource_review(work),'native memory resource binding differs')
    require(all(value.get(k) is False for k in ('HardwareAccessed','BitstreamRequested','HardwareReleaseAllowed',
        'TimingAccepted','ExternalACAccepted','DiagnosticsReviewed','DiagnosticsCleared')),'source receipt overclaims release')
    watched={}
    for group in ('InputSHA256','PreparedSHA256'):
        for path,h in plan[group].items():build.add(watched,path,h)
    for name,h in logs.items():build.add(watched,work/name,h)
    for path in (SELF,plan_path,receipt_path,adf,report):build.add(watched,path)
    return {'Schema':SCHEMA,'Target':build.TARGET,'BuildPlan':ref(plan_path),'SourceBuildReceipt':ref(receipt_path),
        'SourceADF':ref(adf),'SourceTimingReport':ref(report),'ReadOnlyInspectionAllowed':True,
        'OriginalBuildCompleted':False,'SourceDiagnostics':value['Diagnostics'],'AdditionalCounterRangeProofs':ranges,
        'AllowedReadonlyDiagnosticBodies':sorted({r.split(': ',1)[-1] for r in value['Diagnostics']}),
        'SourceDiagnosticsPreserved':True,'DiagnosticsCleared':False,'SameDomainTimingFailuresWaived':False,
        'ConstraintsApplicable':False,'BitstreamAllowed':False,'HardwareReleaseAllowed':False,
        'MemoryResourceReview':value['MemoryResourceReview'],'InputSHA256':watched}, {Path(p):h for p,h in watched.items()}


def verify(path):
    path=Path(path).absolute();saved=read(path)
    require(saved.get('Schema')==SCHEMA,'snapshot read-only review required')
    current,watched=derive(saved['SourceBuildReceipt']['Path']);require(current==saved,'snapshot read-only review changed')
    watched[path]=sha(path);return saved,watched


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source-receipt',type=Path)
    p.add_argument('--output',type=Path);p.add_argument('--verify',type=Path);a=p.parse_args()
    if a.verify:verify(a.verify);print('{"Verified":true}');return 0
    require(a.source_receipt and a.output,'source receipt and output required');v,_=derive(a.source_receipt);build.write(a.output,v)
    print(json.dumps({'ReadOnlyInspectionAllowed':True,'Review':str(a.output),'SameDomainTimingFailuresWaived':False}));return 0


if __name__=='__main__':raise SystemExit(main())
