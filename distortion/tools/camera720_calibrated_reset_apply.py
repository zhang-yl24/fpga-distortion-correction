"""Apply only proved calibrated720 DDR reset pairs to a checked route copy.

The source must have fresh native timing/export and unchanged functional graph.
One STA initialization precedes five exact pin selectors and save_adif. No data
exception, arbitrary Tcl, route command, bitstream or hardware entry exists.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

import camera720_calibrated_reset as proof
import camera720_calibrated_io_adapter as io
import audit_camera_vga_physical as timing
import audit_camera_vga_routes as routes
import audit_camera_vga_route_reset_scope as separated

inspect,prep,require,sha=proof.inspect,proof.prep,proof.require,proof.sha
read,add,binding,merge,ref=proof.read,proof.add,proof.binding,proof.merge,proof.ref
SELF=Path(__file__).resolve()
REQUEST_SCHEMA='camera720-calibrated-reset-application-request-v1'
SCHEMA='camera720-calibrated-reset-application-v1'
MARKER='CAMERA720_CALIBRATED_EXACT_RESET_SAVED'
INIT=inspect.INIT
DUMMY='module physical_dummy(input a, output y); assign y=a; endmodule\n'
ARTIFACT_SUFFIXES={'.tcl','.log','.rtr','.txt','.v','.fdc','.adf','.py','.json'}


def functional(path):
    text=Path(path).read_text(encoding='utf-8-sig')
    return io.structure.functional(io.module_as(text,io.structure.prep.TARGET))


def artifact(receipt_path,value,name,watched):
    matches=[Path(receipt_path).parent/n for n in value['Artifacts']
             if Path(n).name==name and 'report_path_timing' not in Path(n).parts]
    require(len(matches)==1,'one bound native artifact required: '+name)
    path=matches[0]
    return add(watched,path,value['Artifacts'][path.relative_to(Path(receipt_path).parent).as_posix()])


def nonreset_checks(tables,inventory):
    require(set(tables)=={(c,k) for c in ('slow','fast') for k in timing.native.KINDS},'ten native timing tables required')
    excluded={(g['Corner'],g['LaunchClock'],g['CaptureClock']) for g in inventory['Groups']}
    for (corner,kind),rows in tables.items():
        require(rows,'empty native timing table')
        for pair,row in rows.items():
            if kind=='recovery' and isinstance(pair,tuple) and len(pair)==2 and (corner,*pair) in excluded:
                continue
            require(row['FailingChecks']==0 and row['WorstSlackNS']>=0 and row['TotalNegativeSlackNS']==0,
                    'unresolved non-proposed timing failure: '+str((corner,kind,pair)))


def bind_request(path):
    import camera720_calibrated_route_reassessment as physical
    import camera720_calibrated_reassessed_inspect as derived
    watched={};path=add(watched,inspect.canonical(path,prep.WORK));request=read(path)
    require(set(request)=={'Schema','Target','ResetProof','RouteApplication','BaselineExport','BaselineReport'}
            and request['Schema']==REQUEST_SCHEMA and request['Target']==prep.TARGET,'exact reset-only request required')
    proof_path=binding(request['ResetProof'],watched)
    original,inputs=proof.verify(proof_path);merge(watched,inputs)
    route_path=binding(request['RouteApplication'],watched)
    route=physical.bind_completed(route_path,watched)
    require(route['SourceADFSHA256']==original['SourceADF']['SHA256'] and route['BuildPlan']==original['BuildPlan']
            and route['ExactResetCommands']==[] and route['ResetProof'] is None,
            'route candidate is not an unscoped descendant of the proved source')
    export_path=binding(request['BaselineExport'],watched);report_path=binding(request['BaselineReport'],watched)
    export,inputs=derived.bind_receipt(export_path);merge(watched,inputs)
    report,inputs=derived.bind_receipt(report_path);merge(watched,inputs)
    for value,mode in ((export,'export'),(report,'report')):
        require(value['Mode']==mode and value['SourceReceipt']==request['RouteApplication']
                and value['SourceADFSHA256']==route['ResultADFSHA256'] and value['BuildPlan']==original['BuildPlan'],
                'fresh evidence belongs to another route candidate')
    source=add(watched,route['ResultADF']['Path'],route['ResultADFSHA256'])
    old_net=binding({k:original['Netlist'][k] for k in ('Path','SHA256')},watched)
    new_net=add(watched,export['Netlist']['Path'],export['Netlist']['SHA256'])
    before,after=functional(old_net),functional(new_net)
    require(before==after,'hold repair changed functional graph/declarations/FF placement')
    rtr=artifact(report_path,report,prep.TARGET+'.rtr',watched)
    inv,adapter=proof.inventory(rtr)
    queries,_,commands=proof.exact_scope(inv)
    require(queries==original['NativeQueries'] and commands==original['ExactResetCommands'],
            'route candidate reset source/target inventory differs')
    structure=proof.graph.audit_text(proof.adapt_netlist(new_net.read_text(encoding='utf-8-sig')),queries)
    require(structure['InternalFunctionalTargetsVerified']==sum(len(q['Targets']) for q in queries if not q['EntryRDC']),
            'route candidate reset connectivity incomplete')
    tables,_=timing.summaries(rtr);nonreset_checks(tables,inv)
    dump=artifact(report_path,report,'route-dump.txt',watched)
    saved_dump=binding(route['NativeRouteDump'],watched)
    old_routes,new_routes=routes.inspect(saved_dump,{}),routes.inspect(dump,{})
    require(all(old_routes[k]==new_routes[k] for k in
            ('NetAnnotations','NonRouteSemanticSHA256','ExcludedBlockSHA256')),
            'fresh route report changed routing, constraints or functional/placement semantics')
    for module in (physical,derived,io,io.structure,timing,timing.native,timing.dialect,routes,separated):add(watched,module.__file__)
    add(watched,SELF)
    require(not inspect.drift(watched),'reset source evidence drift')
    facts={'SourceADF':str(source),'SourceADFSHA256':sha(source),'BuildPlan':original['BuildPlan'],
        'BuildPlanSHA256':original['BuildPlanSHA256'],'BuildDiagnosticsReview':original['BuildDiagnosticsReview'],
        'ResetProof':request['ResetProof'],'RouteApplication':request['RouteApplication'],
        'BaselineExport':request['BaselineExport'],'BaselineReport':request['BaselineReport'],
        'BaselineRouteDump':ref(dump),'CurrentResetInventory':inv,'CurrentResetReportAdapter':adapter,
        'CurrentResetGraph':structure,'NativeQueries':queries,'ExpectedNativeNameProof':original['NativeNameProof'],
        'ExactResetCommands':commands,'FunctionalGraphAndFFPlacementUnchanged':True,
        'ActualCellCount':len(before['Cells']),'ActualFFCount':len(before['FFPlacement'])}
    return facts,watched


def render(commands,work):
    w=work.as_posix()
    return ('set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG676\n'
        'add_design {'+w+'/dummy.v}\nif {[info script] ne {}} {\n'
        '    mpnr -input {'+w+'/input.adf}\n    '+INIT+'\n'
        '    file copy {'+w+'/input.adf} {'+w+'/post-init.adf}\n'
        +'\n'.join(commands)+'\n    save_adif\n'
        '    file copy {'+w+'/input.adf} {'+w+'/saved-reset.adf}\n'
        '    .switch_db -route -input {'+w+'/input.adf} -output {'+w+'/route-dump.txt}\n'
        '    puts {'+MARKER+'}\n    flush stdout\n}\n')


def recipe(request,work,maximum=300):
    work=prep.work_path(work)
    require(type(maximum)is int and 120<=maximum<=300,'native deadline must be120..300 seconds')
    facts,watched=bind_request(request)
    require(not any(p.is_relative_to(work) for p in watched),'output overlaps source evidence')
    build=read(facts['BuildPlan']);tcl=render(facts['ExactResetCommands'],work)
    result={'Schema':SCHEMA,'Target':prep.TARGET,'Mode':'save-reset','WorkDirectory':str(work),
        'Request':ref(request),**facts,'MaximumSeconds':maximum,'ExpectedActualStages':[],
        'InputSHA256':{str(p):h for p,h in sorted(watched.items(),key=lambda x:str(x[0]))},
        'TclSHA256':prep.baseline.paths.sha_bytes(tcl.encode('ascii')),
        'Command':[build['PDS']['Executable'],'-file',(work/'stage.tcl').as_posix(),'-work_dir',work.as_posix(),'-project_name',prep.TARGET],
        'HardwareAccessed':False,'BitstreamRequested':False,'HardwareReleaseAllowed':False,
        'BuildExecutionCompletedWithoutError':False,'BuildDiagnosticsCleared':False,
        'DiagnosticCopyOnly':True,'DataTimingWaiverAllowed':False,'TimingAccepted':False,'FinalSTAExecuted':False}
    return result,tcl,watched


def prepare(request,work,maximum=300):
    value,tcl,watched=recipe(request,work,maximum);work=Path(value['WorkDirectory'])
    require(not work.exists() and not inspect.drift(watched),'fresh stage and stable source evidence required')
    work.mkdir();shutil.copyfile(value['SourceADF'],work/'input.adf');shutil.copyfile(SELF,work/'executor-snapshot.py')
    require(sha(work/'input.adf')==value['SourceADFSHA256'],'input clone differs')
    (work/'stage.tcl').write_text(tcl,encoding='ascii',newline='\n')
    (work/'dummy.v').write_text(DUMMY,encoding='ascii',newline='\n')
    value['PreparedUTC']=inspect.utc();inspect.diagnostic.write(work/'stage-plan.json',value)
    return work/'stage-plan.json'


def bound_plan(path,fresh):
    path=inspect.canonical(path,prep.WORK);work=prep.work_path(path.parent);value=read(path)
    require(path.name=='stage-plan.json' and value.get('Schema')==SCHEMA,'exact calibrated reset stage required')
    expected,tcl,watched=recipe(value['Request']['Path'],work,value['MaximumSeconds'])
    require(set(value)==set(expected)|{'PreparedUTC'} and isinstance(value['PreparedUTC'],str) and value['PreparedUTC']
            and {k:v for k,v in value.items() if k!='PreparedUTC'}==expected,'reset stage differs from exact recipe')
    files={'stage-plan.json','stage.tcl','dummy.v','input.adf','executor-snapshot.py'}
    if fresh:require({p.name for p in work.iterdir()}==files,'prepared stage reused or contaminated')
    require((work/'stage.tcl').read_bytes()==tcl.encode('ascii') and (work/'dummy.v').read_bytes()==DUMMY.encode('ascii')
            and sha(work/'executor-snapshot.py')==sha(SELF),'stage instructions changed')
    if fresh:require(sha(work/'input.adf')==value['SourceADFSHA256'],'prepared mutable copy differs')
    for name in files-{'input.adf'}:add(watched,work/name)
    require(not inspect.drift(watched),'reset stage input drift')
    return value,watched


def validate_prepared(path):return bound_plan(path,True)


def artifact_hashes(work):
    return {p.relative_to(work).as_posix():sha(p) for p in work.rglob('*') if p.is_file()
            and p.suffix in ARTIFACT_SUFFIXES and p.name!='result.json'}


def compare_routes(before_path,after_path):
    before,after=routes.inspect(before_path,{}),routes.inspect(after_path,{})
    a,b=separated.constraint_separated(before_path),separated.constraint_separated(after_path)
    require(before['ExcludedBlockSHA256']['FILETABLE']==after['ExcludedBlockSHA256']['FILETABLE'],
            'reset save changed source file table')
    value=separated.verify(before,after,a,b)
    return {**value,'RouteCount':before['RouteCount'],'FileTableUnchanged':True,
        'NonConstraintNonRouteSHA256':a['NonConstraintNonRouteSHA256'],
        'BeforeSourceLocations':a['SourceLocations'],'AfterSourceLocations':b['SourceLocations'],
        'ConstraintEffectStillRequiresFreshSTA':True}


def execution_ok(value):
    return (value.get('Schema')==SCHEMA and value.get('Target')==prep.TARGET and value.get('ExitCode')==0
        and value.get('EDAExecuted') is True and not value.get('Error') and value.get('TimedOut') is False
        and value.get('StoppedForUnexpectedStage') is False and value.get('InputDrift')==[]
        and value.get('Diagnostics')==[] and value.get('ActualEvents')==[] and value.get('CompletionMarker') is True
        and value.get('InitializationPreservedADF') is True and value.get('SavedADFReadbackMatches') is True
        and value.get('ResultADFChanged') is True and value.get('NativeApplicationNamesVerified') is True
        and value.get('RoutesAndPlacementUnchanged') is True and value.get('Cleanup',{}).get('Complete') is True)


def bind_completed(path,watched):
    path=inspect.canonical(path,prep.WORK);work=path.parent;value=read(path)
    require(path.name=='result.json' and value.get('ExecutionPassed') is True and execution_ok(value),'clean calibrated reset save required')
    plan,inputs=bound_plan(work/'stage-plan.json',False);merge(watched,inputs)
    require(all(value.get(k)==v for k,v in plan.items()) and value['StagePlanSHA256']==sha(work/'stage-plan.json'),
            'reset receipt differs from plan')
    require(value['Artifacts']==artifact_hashes(work),'native reset artifact inventory changed')
    for name,digest in value['Artifacts'].items():add(watched,inspect.canonical(work/name,work),digest)
    require(inspect.scan_diagnostics(work)==[],'native reset diagnostics present')
    log=(work/'stdout.log').read_text(encoding='gb18030',errors='replace')
    require(inspect.diagnostic.stage_events(log)==[] and MARKER in log,'native reset stage events differ')
    names=proof.queries_parser.exact_queries(value['NativeQueries'],work/'stdout.log')
    require(names==value['ExpectedNativeNameProof']==value['ApplicationNativeNameProof'],'actual application selectors differ')
    require(sha(work/'post-init.adf')==value['SourceADFSHA256'] and
            sha(work/'input.adf')==sha(work/'saved-reset.adf')==value['ResultADFSHA256']!=value['SourceADFSHA256'],
            'native reset initialization/save chain differs')
    for name in ('input.adf','post-init.adf','saved-reset.adf'):
        p=work/name
        require(value['ADFReadback'][name]=={'Path':str(p),'SHA256':sha(p),'Bytes':p.stat().st_size},'ADF readback record differs')
    require(value['ResultADF']==value['ADFReadback']['input.adf'],'result ADF record differs')
    comparison=compare_routes(value['BaselineRouteDump']['Path'],work/'route-dump.txt')
    require(comparison==value['RouteComparison'],'reset route comparison differs')
    add(watched,path);require(not inspect.drift(watched),'completed reset evidence drift')
    return value


def execute(path):
    value,watched=validate_prepared(path);work=Path(value['WorkDirectory'])
    require(os.name=='nt','native PDS requires Windows')
    result={**value,'StagePlanSHA256':sha(path),'StartedUTC':inspect.utc(),'EDAExecuted':False,'ExecutionPassed':False,
            'TimedOut':False,'StoppedForUnexpectedStage':False,'ExitCode':None}
    inspect.diagnostic.write(work/'execution-start.json',result);process=None;started=time.monotonic()
    try:
        with (work/'stdout.log').open('xb') as out,(work/'stderr.log').open('xb') as err:
            process=subprocess.Popen(value['Command'],cwd=work,stdout=out,stderr=err,shell=False,
                creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0));result.update(EDAExecuted=True,OwnedPID=process.pid)
            while process.poll() is None:
                remaining=value['MaximumSeconds']-(time.monotonic()-started)
                if remaining<=0:result['TimedOut']=True;break
                try:process.wait(timeout=min(2,remaining))
                except subprocess.TimeoutExpired:pass
                if inspect.diagnostic.stage_events((work/'stdout.log').read_text(encoding='gb18030',errors='replace')):
                    result['StoppedForUnexpectedStage']=True;break
    except BaseException as error:result['Error']=type(error).__name__+': '+str(error)
    finally:
        if process is not None:
            result['Cleanup']=(inspect.diagnostic.cleanup.stop_owned_tree(process,work,'bounded calibrated reset save') if process.poll() is None
                else {'Complete':True,'OwnedPID':process.pid,'ParentExited':True,'DescendantLivenessIndependentlyVerified':False})
            result['ExitCode']=process.poll()
        else:result['Cleanup']={'Complete':True,'Required':False}
    try:
        log=(work/'stdout.log').read_text(encoding='gb18030',errors='replace') if (work/'stdout.log').exists() else ''
        adfs={n:{'Path':str(work/n),'SHA256':sha(work/n),'Bytes':(work/n).stat().st_size}
              for n in ('input.adf','post-init.adf','saved-reset.adf') if (work/n).is_file()}
        final=adfs.get('input.adf',{}).get('SHA256')
        names=proof.queries_parser.exact_queries(value['NativeQueries'],work/'stdout.log')
        comparison=compare_routes(value['BaselineRouteDump']['Path'],work/'route-dump.txt')
        result.update(ActualEvents=inspect.diagnostic.stage_events(log),InputDrift=inspect.drift(watched),
            Diagnostics=inspect.scan_diagnostics(work),CompletionMarker=MARKER in log,ADFReadback=adfs,
            ResultADF=adfs.get('input.adf'),ResultADFSHA256=final,
            InitializationPreservedADF=adfs.get('post-init.adf',{}).get('SHA256')==value['SourceADFSHA256'],
            SavedADFReadbackMatches=bool(final) and adfs.get('saved-reset.adf',{}).get('SHA256')==final,
            ResultADFChanged=bool(final) and final!=value['SourceADFSHA256'],
            ApplicationNativeNameProof=names,NativeApplicationNamesVerified=names==value['ExpectedNativeNameProof'],
            RouteComparison=comparison,RoutesAndPlacementUnchanged=True,Artifacts=artifact_hashes(work))
    except Exception as error:result['Error']=type(error).__name__+': '+str(error)
    result.update(FinishedUTC=inspect.utc(),ElapsedSeconds=round(time.monotonic()-started,3))
    result['ExecutionPassed']=execution_ok(result)
    inspect.diagnostic.write(work/'result.json',result)
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--request',type=Path);p.add_argument('--name')
    p.add_argument('--stage-plan',type=Path);p.add_argument('--maximum-seconds',type=int,default=300)
    actions=p.add_mutually_exclusive_group();actions.add_argument('--prepare-only',action='store_true');actions.add_argument('--execute',action='store_true')
    a=p.parse_args()
    if a.stage_plan:
        require(not (a.request or a.name or a.prepare_only),'stage plan cannot mix preparation inputs')
        if a.execute:result=execute(a.stage_plan)
        else:validate_prepared(a.stage_plan);result={'Validated':True}
    else:
        require(a.request and a.name,'request and fresh stage name required')
        if a.prepare_only or a.execute:
            stage=prepare(a.request,prep.WORK/a.name,a.maximum_seconds)
            result=execute(stage) if a.execute else {'Prepared':True,'StagePlan':str(stage),'EDAExecuted':False}
        else:recipe(a.request,prep.WORK/a.name,a.maximum_seconds);result={'Validated':True,'EDAExecuted':False}
    print(json.dumps({k:result[k] for k in ('Prepared','Validated','StagePlan','ExecutionPassed','ExitCode','ElapsedSeconds','ResultADFSHA256','EDAExecuted') if k in result}))
    return 0 if result.get('ExecutionPassed',True) else 1


if __name__=='__main__':raise SystemExit(main())
