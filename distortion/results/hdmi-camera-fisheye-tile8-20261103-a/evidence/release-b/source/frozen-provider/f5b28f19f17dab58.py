"""Execute only the isolated calibrated720 statistics statistics compile/map/route/STA diagnostic.

Default is read-only validation. --execute explicitly starts a bounded native
process. Source closure, compiled bytes, exact Tcl and both new tools are
rechecked. Exit zero never implies timing acceptance or permission to program.
"""
import argparse
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import re
import subprocess
import time

import prepare_camera720_stats_delay_shared_build as prep
import run_camera_vga_output_diagnostic as cleanup

require,sha=prep.require,prep.sha
SELF=Path(__file__).resolve()


def write(path,value):
    with path.open('x',encoding='utf-8',newline='\n') as f:json.dump(value,f,indent=2);f.write('\n')


def validate_plan(path,maximum_seconds=None):
    path=Path(path).absolute();work=prep.work_path(path.parent)
    require(path==path.resolve() and path.name=='plan.json' and path.is_file(),'exact canonical plan.json required')
    require({p.name for p in work.iterdir()}=={'plan.json','source-plan.json','timing.tcl','compiled','source'},'fresh prepared statistics build directory required')
    raw=path.read_bytes();plan=json.loads(raw)
    require(plan.get('Schema')==prep.SCHEMA and plan.get('Target')==prep.TARGET,'calibrated720 statistics plan identity differs')
    expected,payloads=prep.recipe(plan['SourcePreparation']['Path'],plan['SourcePreparation']['SHA256'],work,plan['MaximumSecondsForExternalExecutor'])
    tcl=payloads[work/'timing.tcl']
    require(set(plan)==set(expected)|{'PreparedUTC'} and isinstance(plan['PreparedUTC'],str) and plan['PreparedUTC'],
            'calibrated720 statistics plan fields/timestamp differ')
    require({k:v for k,v in plan.items() if k!='PreparedUTC'}==expected,'calibrated720 statistics plan differs from current deterministic recipe')
    require((work/'timing.tcl').read_bytes()==tcl,'calibrated720 statistics Tcl recipe drift')
    actual={p for area in ('source','compiled') for p in (work/area).rglob('*') if p.is_file()}
    actual.update((work/'source-plan.json',work/'timing.tcl'))
    require(actual==set(payloads),'compiled tree inventory differs')
    for p,data in payloads.items():
        require(p==p.resolve() and p.read_bytes()==data,'compiled bytes differ outside exact include rewrite')
    maximum=plan['MaximumSecondsForExternalExecutor'] if maximum_seconds is None else maximum_seconds
    require(type(maximum) is int and 30<=maximum<=plan['MaximumSecondsForExternalExecutor'],'deadline exceeds prepared limit')
    watched={Path(n):h for n,h in plan['InputSHA256'].items()}
    watched.update({p:prep.source.digest(data) for p,data in payloads.items()})
    watched[path]=prep.source.digest(raw);watched[work/'timing.tcl']=plan['Tcl']['SHA256']
    watched[Path(plan['PDS']['Executable'])]=plan['PDS']['ExecutableSHA256'];watched[SELF]=sha(SELF)
    require(all(sha(p)==h for p,h in watched.items()),'input drift during calibrated720 statistics validation')
    return {'Plan':plan,'PlanPath':path,'PlanSHA256':watched[path],'Work':work,'MaximumSeconds':maximum,'Watched':watched}


def stage_events(text):
    return [m.groups() for m in re.finditer(r'^Process "([^"]+)" (started|done)\.',text,re.M)]


def snapshot(work):
    before=work/'pre-sta-final.adf';after=work/'place_route'/(prep.TARGET+'_pnr.adf')
    result={'Snapshot':str(before),'FinalRoutedDatabase':str(after),'SnapshotExists':before.is_file(),
            'FinalRoutedDatabaseExists':after.is_file(),'UnchangedAcrossSTA':False,'TimingAccepted':False}
    if before.is_file() and after.is_file():
        require(before==before.resolve() and after==after.resolve(),'database path escaped canonical stage')
        result.update(SnapshotSHA256=sha(before),FinalRoutedDatabaseSHA256=sha(after))
        result['UnchangedAcrossSTA']=result['SnapshotSHA256']==result['FinalRoutedDatabaseSHA256']
    return result


def execute(path,maximum_seconds=None):
    context=validate_plan(path,maximum_seconds);plan=context['Plan'];work=context['Work']
    require(os.name=='nt','native PDS diagnostic requires Windows')
    started=time.monotonic();process=None
    result={'Schema':'camera720-calibrated-stats-delay-shared-build-execution-v1','Target':prep.TARGET,
            'StartedUTC':datetime.now(timezone.utc).isoformat(),'Plan':str(context['PlanPath']),
            'PlanSHA256':context['PlanSHA256'],'ExecutorSHA256':sha(SELF),'Command':plan['CommandToRunSeparately'],
            'MaximumSeconds':context['MaximumSeconds'],'HardwareAccessed':False,'BitstreamRequested':False,
            'TimingAccepted':False,'HardwareReleaseAllowed':False,'EDAExecuted':False,'TimedOut':False,
            'StoppedForUnexpectedStage':False,'NativeExitCode':None,'ExecutionCompletedWithoutError':False}
    write(work/'execution-start.json',result)
    expected=[(stage,event) for stage in plan['ExpectedActualStages'] for event in ('started','done')]
    try:
        with (work/'execution-stdout.log').open('xb') as out,(work/'execution-stderr.log').open('xb') as err:
            process=subprocess.Popen(plan['CommandToRunSeparately'],cwd=work,stdout=out,stderr=err,shell=False,
                                     creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            result['EDAExecuted']=True;result['OwnedPID']=process.pid
            while process.poll() is None:
                remaining=context['MaximumSeconds']-(time.monotonic()-started)
                if remaining<=0:result['TimedOut']=True;break
                try:process.wait(timeout=min(5,remaining))
                except subprocess.TimeoutExpired:pass
                events=stage_events((work/'execution-stdout.log').read_text(encoding='gb18030',errors='replace'))
                if events!=expected[:len(events)]:result['StoppedForUnexpectedStage']=True;break
    except BaseException as error:
        result['Error']=type(error).__name__+': '+str(error)
    finally:
        if process is not None:
            if process.poll() is None:
                result['Cleanup']=cleanup.stop_owned_tree(process,work,'timeout' if result['TimedOut'] else 'unexpected/interrupted')
            else:result['Cleanup']={'Required':False,'OwnedPID':process.pid,'ParentExited':True,'Complete':True,'DescendantLivenessIndependentlyVerified':False}
            result['NativeExitCode']=process.poll()
        else:result['Cleanup']={'Required':False,'Complete':True}
        result['InputDrift']=[str(p) for p,h in context['Watched'].items() if not p.is_file() or sha(p)!=h]
        result['SourcesStable']=not result['InputDrift'];result['DatabaseSnapshotAudit']=snapshot(work)
        stdout=work/'execution-stdout.log'
        events=stage_events(stdout.read_text(encoding='gb18030',errors='replace')) if stdout.exists() else []
        result['ActualEvents']=events;result['ActualStagesComplete']=events==expected
        logs=sorted(work.rglob('*.log'));diagnostics=[]
        for p in logs:
            diagnostics.extend(p.relative_to(work).as_posix()+': '+line.strip() for line in re.findall(
                r'(?m)^\s*(?:C:|E:|F:|ERROR:|FATAL:|Traceback).*$',p.read_text(encoding='gb18030',errors='replace')))
        result['Diagnostics']=diagnostics
        result['ExecutionCompletedWithoutError']=(result['NativeExitCode']==0 and result['SourcesStable'] and not result.get('Error')
            and not result['TimedOut'] and not result['StoppedForUnexpectedStage'] and result['ActualStagesComplete']
            and not diagnostics and result['Cleanup'].get('Complete',False) and result['DatabaseSnapshotAudit']['UnchangedAcrossSTA'])
        result['FinishedUTC']=datetime.now(timezone.utc).isoformat();result['ElapsedSeconds']=round(time.monotonic()-started,3)
        result['LogSHA256']={p.relative_to(work).as_posix():sha(p) for p in logs}
        result['Limits']='Diagnostic execution only. New statistics top,129pins, counter fanout and all existing datapaths require fresh IO/timing/CDC review. Original native diagnostics are retained; no old routed repair, bitstream or hardware release.'
        write(work/'execution-result.json',result)
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',type=Path,required=True)
    modes=p.add_mutually_exclusive_group();modes.add_argument('--execute',action='store_true');modes.add_argument('--validate-only',action='store_true')
    p.add_argument('--maximum-seconds',type=int);args=p.parse_args()
    if args.execute:
        value=execute(args.plan,args.maximum_seconds)
        print(json.dumps({k:value[k] for k in ('ExecutionCompletedWithoutError','NativeExitCode','TimedOut','SourcesStable','TimingAccepted','ElapsedSeconds')}))
        return 0 if value['ExecutionCompletedWithoutError'] else 1
    value=validate_plan(args.plan,args.maximum_seconds)
    print(json.dumps({'Validated':True,'PlanSHA256':value['PlanSHA256'],'Command':value['Plan']['CommandToRunSeparately'],
                      'MaximumSeconds':value['MaximumSeconds'],'EDAExecuted':False,'HardwareAccessed':False}));return 0


if __name__=='__main__':raise SystemExit(main())
