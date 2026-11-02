"""Single-CLK/single-Q recovery of missing physical CLM observations.

The frozen grouped plan and its valid partial receipt remain evidence. This
separate diagnostic uses four exact single-source timing commands per context.
"""
import argparse
from collections import defaultdict
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

import camera720_cdc_clm_native as parent

fast, native, prep, inspect, diagnostic = parent.fast, parent.native, parent.prep, parent.inspect, parent.diagnostic
require,sha,read = parent.require,parent.sha,parent.read
SELF=Path(__file__).resolve()
PLAN_SCHEMA='camera720-single-clm-recovery-plan-v1'
STAGE_SCHEMA='camera720-single-clm-recovery-stage-v1'
RECEIPT_SCHEMA='camera720-single-clm-recovery-result-v1'
COVERAGE_SCHEMA='camera720-single-clm-recovery-coverage-v1'
MARKER='CAMERA720_SINGLE_CLM_RECOVERY_COMPLETE'
PARENT_PLAN='cdc-clm-through-b/plan.json'
PARENT_SHA='3e5b7fe56b2ced36b29aa5b1a1e8b6e80c494f9a23da3ebd76e94868cab5ee38'
PARTIAL='cdc-clm-native-00/result.json'
PARTIAL_SHA='22c78becfb02f9a668a02ad444781d7ee5b96c65cd516d37d452a8cca2a0c229'
PER_CONTEXT=4


def groups_for(queries,missing):
    need={parent.old.identity(q) for q in missing}
    buckets=defaultdict(list)
    for q in queries:
        if parent.old.identity(q) not in need:continue
        require('Clock' not in q,'ordinary cases must remain complete')
        buckets[(parent.old.domain(q),q['Source'],q['LaunchOutput'])].append(q)
    result=[]
    for (domain,source,launch),rows in sorted(buckets.items()):
        require(source.rsplit('/',1)[0]==launch.rsplit('/',1)[0],'source/launch parent differs')
        rows=sorted(rows,key=parent.old.identity)
        for start in range(0,len(rows),64):
            selected=rows[start:start+64];ends=sorted({q['Endpoint'] for q in selected})
            require(len(ends)==len(selected),'duplicate single-source endpoint')
            result.append({'Domain':list(domain),'SourceLaunches':{source:launch},'Endpoints':ends,
                'ExpectedIdentities':[{k:q[k] for k in parent.old.IDENTITY} for q in selected],
                'Command':parent.command([source],[launch],ends)})
    require({parent.old.identity(q) for g in result for q in g['ExpectedIdentities']}==need,'recovery grouping loses missing identities')
    return result


def render(work,groups):
    require(1<=len(groups)<=PER_CONTEXT,'one to four single-source commands required')
    for g in groups:
        require(len(g['SourceLaunches'])==1 and 1<=len(g['Endpoints'])<=64,'one source/output and bounded endpoints required')
        require(g['Command']==parent.command(g['SourceLaunches'],g['SourceLaunches'].values(),g['Endpoints']),'exact single-source command required')
    aw=work.as_posix()
    return ('set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG676\n'
        'add_design {'+aw+'/dummy.v}\nif {[info script] ne {}} {\n'
        '    mpnr -input {'+aw+'/input.adf}\n    '+inspect.INIT+'\n'+
        '\n'.join(g['Command'] for g in groups)+'\n    puts {'+MARKER+'}\n    flush stdout\n}\n')


def parent_context():
    path=prep.WORK/PARENT_PLAN
    plan,original,watched=parent.bind_plan(path,PARENT_SHA)
    native.add(watched,SELF)
    return plan,original,watched


def prepare(name):
    work=prep.work_path(prep.WORK/name);require(not work.exists(),'fresh recovery plan required')
    plan,original,watched=parent_context()
    reports=[]
    for reference in plan['InitialReports']:
        reports.append(parent.grouped.watch(watched,reference['Path'],reference['SHA256']))
    rows,issues,excluded=parent.old.collect(plan['Queries'],reports)
    initial=parent.summary(plan['Queries'],rows,issues)
    require({k:initial[k] for k in plan['InitialCoverage']}==plan['InitialCoverage'],'initial grouped evidence changed')
    partial_ref=parent.fixed(PARTIAL,PARTIAL_SHA)
    index,more=parent.bind_completed(partial_ref,prep.WORK/PARENT_PLAN,PARENT_SHA,watched)
    require(index==0,'exact completed grouped context0 required')
    rows=list({r['PathSHA256']:r for r in rows+more}.values())
    initial=parent.summary(plan['Queries'],rows,issues)
    require(not issues and not initial['OrdinaryMissingCases'],'valid preserved partial/ordinary evidence required')
    groups=groups_for(plan['Queries'],initial['MissingCases'])
    value={'Schema':PLAN_SCHEMA,'Target':prep.TARGET,'Producer':fast.binding(SELF),'ParentProducer':fast.binding(parent.SELF),
        'ParentPlan':parent.fixed(PARENT_PLAN,PARENT_SHA),'PreservedPartialReceipts':[partial_ref],
        'CandidateADF':plan['CandidateADF'],'BuildPlanSHA256':plan['BuildPlanSHA256'],'InspectionSeed':plan['InspectionSeed'],
        'Queries':plan['Queries'],'InitialCoverage':{k:initial[k] for k in ('ExpectedCases','CoveredCases','MissingCases','Complete','EnumeratedPathsTimingPassed')},
        'Groups':groups,'CommandsPerContext':PER_CONTEXT,'NativeContexts':(len(groups)+PER_CONTEXT-1)//PER_CONTEXT,
        'MaximumSeconds':300,'PhysicalTimingAggregationProved':False,'EDAExecuted':False,'TimingAccepted':False,'HardwareReleaseAllowed':False,
        'InputSHA256':{str(p):h for p,h in watched.items()}}
    require(not inspect.drift(watched),'recovery preparation drift')
    work.mkdir();diagnostic.write(work/'plan.json',value)
    diagnostic.write(work/'initial-coverage.json',{**initial,'Schema':COVERAGE_SCHEMA,'Producer':fast.binding(SELF),
        'Plan':fast.binding(work/'plan.json'),'ExcludedOtherLaunches':excluded})
    return work/'plan.json'


def bind_plan(path,digest):
    path=inspect.canonical(path,prep.WORK)
    require(path.name=='plan.json' and native.physical.digest(digest) and sha(path)==digest,'explicit recovery plan SHA differs')
    value=read(path);plan,original,watched=parent_context()
    require(value['Schema']==PLAN_SCHEMA and value['Target']==prep.TARGET and value['Producer']==fast.binding(SELF)
        and value['ParentProducer']==fast.binding(parent.SELF) and value['ParentPlan']==parent.fixed(PARENT_PLAN,PARENT_SHA)
        and value['PreservedPartialReceipts']==[parent.fixed(PARTIAL,PARTIAL_SHA)],'exact recovery source/producer differs')
    require(all(value[k] is False for k in ('PhysicalTimingAggregationProved','EDAExecuted','TimingAccepted','HardwareReleaseAllowed')),
        'recovery plan exceeds observation authority')
    parent.rehash_inputs(value['InputSHA256'],watched,Path(original['Command'][0]))
    require(value['Queries']==plan['Queries'] and value['CandidateADF']==plan['CandidateADF']
        and value['BuildPlanSHA256']==plan['BuildPlanSHA256'] and value['InspectionSeed']==plan['InspectionSeed'],'parent query scope changed')
    groups=groups_for(value['Queries'],value['InitialCoverage']['MissingCases'])
    require(value['Groups']==groups and value['CommandsPerContext']==PER_CONTEXT and value['MaximumSeconds']==300
        and value['NativeContexts']==(len(groups)+PER_CONTEXT-1)//PER_CONTEXT,'single-source recovery grouping changed')
    require(value['InputSHA256'].get(str(SELF))==sha(SELF),'recovery producer closure missing')
    native.add(watched,path,digest);require(not inspect.drift(watched),'recovery plan drift')
    return value,original,watched


def stage_recipe(path,digest,index,work):
    plan,original,watched=bind_plan(path,digest)
    require(type(index)is int and 0<=index<plan['NativeContexts'],'invalid recovery context')
    work=prep.work_path(work);groups=plan['Groups'][index*PER_CONTEXT:(index+1)*PER_CONTEXT];script=render(work,groups)
    value={'Schema':STAGE_SCHEMA,'Target':prep.TARGET,'Producer':fast.binding(SELF),'Plan':fast.binding(path),
        'ContextIndex':index,'Groups':groups,'CandidateADF':plan['CandidateADF'],'BuildPlanSHA256':plan['BuildPlanSHA256'],
        'InspectionSeed':plan['InspectionSeed'],'WorkDirectory':str(work),'MaximumSeconds':300,'ExpectedActualStages':[],
        'Command':[original['Command'][0],'-file',(work/'stage.tcl').as_posix(),'-work_dir',work.as_posix(),'-project_name',prep.TARGET],
        'TclSHA256':prep.baseline.paths.sha_bytes(script.encode('ascii')),'InputSHA256':{str(p):h for p,h in watched.items()},
        'EDAExecuted':False,**{k:False for k in fast.FALSE_FLAGS}}
    return value,script,watched,plan


def prepare_stage(path,digest,index,name):
    work=prep.work_path(prep.WORK/name);require(not work.exists(),'fresh single-source native stage required')
    value,script,watched,_=stage_recipe(path,digest,index,work)
    work.mkdir();shutil.copyfile(value['CandidateADF']['Path'],work/'input.adf');shutil.copyfile(SELF,work/'executor-snapshot.py')
    (work/'stage.tcl').write_bytes(script.encode('ascii'));(work/'dummy.v').write_bytes(native.physical.DUMMY.encode('ascii'))
    require(sha(work/'input.adf')==value['CandidateADF']['SHA256'] and not inspect.drift(watched),'recovery prepared bytes drift')
    value['PreparedUTC']=inspect.utc();diagnostic.write(work/'stage-plan.json',value)
    return work/'stage-plan.json'


def validate_stage(path,digest,finished=False):
    path=inspect.canonical(path,prep.WORK)
    require(path.name=='stage-plan.json' and native.physical.digest(digest) and sha(path)==digest,'explicit recovery stage SHA differs')
    value=read(path);expected,script,watched,plan=stage_recipe(value['Plan']['Path'],value['Plan']['SHA256'],value['ContextIndex'],path.parent)
    require(set(value)==set(expected)|{'PreparedUTC'} and isinstance(value['PreparedUTC'],str) and value['PreparedUTC']
        and {k:v for k,v in value.items() if k!='PreparedUTC'}==expected,'recovery stage differs from recipe')
    if not finished:require({p.name for p in path.parent.iterdir()}==parent.probe.FILES,'recovery stage reused')
    require((path.parent/'stage.tcl').read_bytes()==script.encode('ascii') and sha(path.parent/'input.adf')==value['CandidateADF']['SHA256']
        and sha(path.parent/'executor-snapshot.py')==sha(SELF) and (path.parent/'dummy.v').read_bytes()==native.physical.DUMMY.encode('ascii'),
        'recovery stage input byte drift')
    for name in parent.probe.FILES:native.add(watched,path.parent/name)
    require(not inspect.drift(watched),'recovery stage drift')
    return value,watched,plan


def execute(path,digest):
    value,watched,plan=validate_stage(path,digest);require(os.name=='nt','single-source native queries require Windows')
    work,process,started=Path(value['WorkDirectory']),None,time.monotonic()
    result={**value,'Schema':RECEIPT_SCHEMA,'PlanSchema':STAGE_SCHEMA,'StagePlanSHA256':digest,
        'StartedUTC':inspect.utc(),'ExecutionPassed':False,'ObservationValid':False,'TimedOut':False,
        'StoppedForUnexpectedStage':False,'ExitCode':None}
    diagnostic.write(work/'execution-start.json',result)
    try:
        with (work/'stdout.log').open('xb')as out,(work/'stderr.log').open('xb')as err:
            process=subprocess.Popen(value['Command'],cwd=work,stdout=out,stderr=err,shell=False,
                creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            result.update(EDAExecuted=True,OwnedPID=process.pid)
            while process.poll()is None:
                remaining=300-(time.monotonic()-started)
                if remaining<=0:result['TimedOut']=True;break
                try:process.wait(timeout=min(2,remaining))
                except subprocess.TimeoutExpired:pass
                if diagnostic.stage_events((work/'stdout.log').read_text(encoding='gb18030',errors='replace')):
                    result['StoppedForUnexpectedStage']=True;break
    except BaseException as error:result['Error']=type(error).__name__+': '+str(error)
    finally:
        if process is not None:
            result['Cleanup']=(diagnostic.cleanup.stop_owned_tree(process,work,'bounded single-source recovery')
                if process.poll()is None else {'Complete':True,'OwnedPID':process.pid,'ParentExited':True,
                    'DescendantLivenessIndependentlyVerified':False})
            result['ExitCode']=process.poll()
        else:result['Cleanup']={'Complete':True,'Required':False}
    try:
        log=(work/'stdout.log').read_text(encoding='gb18030',errors='replace') if(work/'stdout.log').exists()else ''
        rows,issues,unmapped,partial=parent.observe(work,value,plan)
        result.update(ActualEvents=[list(x)for x in diagnostic.stage_events(log)],CompletionMarker=MARKER in log,
            InputDrift=inspect.drift(watched),Diagnostics=parent.probe.scan_diagnostics(work),
            InputADFUnchanged=sha(work/'input.adf')==value['CandidateADF']['SHA256'],Records=rows,
            ObservationFailures=issues,UnmappedObservedPaths=unmapped,GroupCoverage=partial)
        result['ExecutionPassed']=(result['ExitCode']==0 and not result.get('Error') and not result['TimedOut']
            and not result['StoppedForUnexpectedStage'] and result['Cleanup'].get('Complete')is True
            and result['ActualEvents']==[] and result['CompletionMarker'] and not result['InputDrift']
            and not result['Diagnostics'] and result['InputADFUnchanged'])
        result['ObservationValid']=result['ExecutionPassed'] and not issues
    except Exception as error:
        result['ReadbackError']=type(error).__name__+': '+str(error);result['ExecutionPassed']=False
    result.update(FinishedUTC=inspect.utc(),ElapsedSeconds=round(time.monotonic()-started,3),
        Artifacts={p.relative_to(work).as_posix():sha(p)for p in work.rglob('*')if p.is_file()
            and p.name not in ('result.json','execution-start.json')})
    diagnostic.write(work/'result.json',result);return result


def bind_completed(reference,path,digest,watched):
    receipt=parent.grouped.watch(watched,reference['Path'],reference['SHA256']);v=read(receipt)
    require(receipt.name=='result.json' and v['Schema']==RECEIPT_SCHEMA and v['PlanSchema']==STAGE_SCHEMA
        and v['Producer']==fast.binding(SELF) and v['Plan']=={'Path':str(Path(path).resolve()),'SHA256':digest},'wrong recovery native receipt')
    stage,inputs,plan=validate_stage(receipt.parent/'stage-plan.json',v['StagePlanSHA256'],finished=True)
    require(all(v.get(k)==x for k,x in stage.items()if k not in ('Schema','EDAExecuted')),'recovery receipt/stage mismatch')
    require(v['EDAExecuted']is True and v['ExecutionPassed']is True and v['ObservationValid']is True
        and v['ExitCode']==0 and v['TimedOut']is False and v['StoppedForUnexpectedStage']is False
        and not v.get('Error') and not v.get('ReadbackError') and v['InputDrift']==[] and v['Diagnostics']==[]
        and v['ObservationFailures']==[] and v['InputADFUnchanged']is True and v['CompletionMarker']is True
        and v['ActualEvents']==[] and v['Cleanup'].get('Complete')is True,'failed recovery native evidence')
    require(all(v[k]is False for k in fast.FALSE_FLAGS),'recovery receipt exceeds diagnostic scope')
    parent.rehash_inputs({str(p):h for p,h in inputs.items()},watched,Path(v['Command'][0]))
    files={p.relative_to(receipt.parent).as_posix()for p in receipt.parent.rglob('*')if p.is_file()
        and p.name not in ('result.json','execution-start.json')}
    require(files==set(v['Artifacts']),'recovery artifact inventory changed');parent.clean_logs([reference],watched)
    log=(receipt.parent/'stdout.log').read_text(encoding='gb18030',errors='replace')
    require(MARKER in log and diagnostic.stage_events(log)==[],'recovery native marker/events differ')
    rows,issues,unmapped,partial=parent.observe(receipt.parent,stage,plan)
    require(not issues and rows==v['Records'] and unmapped==v['UnmappedObservedPaths'] and partial==v['GroupCoverage'],
        'actual recovery report observations differ')
    return v['ContextIndex'],rows


def audit_value(path,digest,receipts):
    recovery,original,watched=bind_plan(path,digest)
    base,inputs=parent.audit_value(prep.WORK/PARENT_PLAN,PARENT_SHA,recovery['PreservedPartialReceipts'])
    parent.rehash_inputs({str(p):h for p,h in inputs.items()},watched,Path(original['Command'][0]))
    require({k:base[k]for k in recovery['InitialCoverage']}==recovery['InitialCoverage'],'preserved partial coverage not reproducible')
    rows=list(base['Records']);seen=set()
    for reference in receipts:
        index,more=bind_completed(reference,path,digest,watched)
        require(index not in seen,'duplicate recovery native context');seen.add(index);rows.extend(more)
    rows=list({r['PathSHA256']:r for r in rows}.values())
    result={**base,**parent.summary(recovery['Queries'],rows,base['Violations'])}
    require(not inspect.drift(watched),'recovery audit input drift')
    result.update(Schema=COVERAGE_SCHEMA,Producer=fast.binding(SELF),ParentProducer=fast.binding(parent.SELF),
        ParentPlan=recovery['ParentPlan'],Plan=fast.binding(path),PreservedPartialReceipts=recovery['PreservedPartialReceipts'],
        NativeReceipts=receipts,CompletedContexts=sorted(seen),InputSHA256={str(p):h for p,h in watched.items()})
    return result,watched


def audit(path,digest,receipts,name):
    value,_=audit_value(path,digest,receipts);work=prep.work_path(prep.WORK/name)
    require(not work.exists(),'fresh recovery audit output required');work.mkdir();diagnostic.write(work/'coverage.json',value)
    return work/'coverage.json',value


def main():
    p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='action',required=True)
    q=s.add_parser('prepare');q.add_argument('--name',required=True)
    for action in ('prepare-stage','audit'):
        q=s.add_parser(action);q.add_argument('--plan',type=Path,required=True);q.add_argument('--plan-sha256',required=True);q.add_argument('--name',required=True)
        if action=='prepare-stage':q.add_argument('--context',type=int,required=True)
        else:q.add_argument('--receipt',type=Path,action='append',default=[])
    for action in ('validate-stage','execute'):
        q=s.add_parser(action);q.add_argument('--stage-plan',type=Path,required=True);q.add_argument('--stage-plan-sha256',required=True)
    a=p.parse_args()
    if a.action=='prepare':out={'Plan':fast.binding(prepare(a.name)),'EDAExecuted':False}
    elif a.action=='prepare-stage':out={'StagePlan':fast.binding(prepare_stage(a.plan,a.plan_sha256,a.context,a.name)),'EDAExecuted':False}
    elif a.action=='validate-stage':validate_stage(a.stage_plan,a.stage_plan_sha256);out={'Validated':True,'EDAExecuted':False}
    elif a.action=='execute':
        v=execute(a.stage_plan,a.stage_plan_sha256);out={k:v[k]for k in ('ExecutionPassed','ObservationValid','ElapsedSeconds','Diagnostics','ObservationFailures')}
        out['GroupCoverageComplete']=v.get('GroupCoverage',{}).get('Complete',False)
    else:
        f,v=audit(a.plan,a.plan_sha256,[fast.binding(r)for r in a.receipt],a.name)
        out={'Coverage':fast.binding(f),'ExpectedCases':v['ExpectedCases'],'CoveredCases':v['CoveredCases'],'PhysicalBoundaryChecksPassed':v['PhysicalBoundaryChecksPassed']}
    print(json.dumps(out,indent=2));return 0 if out.get('ObservationValid',out.get('PhysicalBoundaryChecksPassed',True))else 1


if __name__=='__main__':raise SystemExit(main())
