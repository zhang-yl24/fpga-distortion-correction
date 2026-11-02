"""Save exactly the current raw720 five-group reset scope on a copied ADF.

One native timing initialization, exact pin-resolved false paths, one save.
No route edits, arbitrary Tcl, bitstream or hardware entry point exists.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

import camera720_raw_reset_current as current
import camera720_raw_physical as original_physical

derived, inspect, prep = current.derived, current.inspect, current.prep
require, sha, read = current.require, current.sha, current.read
SELF = Path(__file__).resolve()
REQUEST_SCHEMA = 'camera720-current-raw-reset-application-request-v1'
SCHEMA = 'camera720-current-raw-reset-application-v1'
MARKER = 'CAMERA720_CURRENT_RAW_EXACT_RESET_SAVED'
INIT, DUMMY = inspect.INIT, original_physical.DUMMY
ARTIFACT_SUFFIXES = original_physical.ARTIFACT_SUFFIXES
SOURCE_SHA = current.SOURCE_SHA

def add(watched,path,expected=None):
    return current.add(watched,path,expected)

def binding(value,watched):
    require(isinstance(value,dict) and set(value)=={'Path','SHA256'}, 'exact Path/SHA256 binding required')
    return add(watched,value['Path'],value['SHA256'])

def bind_request(path):
    # Loaded lazily so the independently developed vendor auditor never
    # becomes a circular dependency of the frozen current-scope producer.
    import camera720_raw_vendor_basis as vendor
    watched={}
    path=binding({'Path':str(Path(path).resolve()),'SHA256':sha(path)},watched)
    request=read(path)
    require(set(request)=={'Schema','Target','ScopePlan','QueryReceipt','VendorBasis',
                          'BaselineRouteReport','BaselineFunctionalComparison','BaselineSerialization'},
            'exact reset-only request required')
    require(request['Schema']==REQUEST_SCHEMA and request['Target']==prep.TARGET, 'wrong reset request identity')
    scope_path=binding(request['ScopePlan'],watched)
    query_path=binding(request['QueryReceipt'],watched)
    scope,names,bound=current.bind_scope(scope_path,request['ScopePlan']['SHA256'],
                                        query_path,request['QueryReceipt']['SHA256'])
    current.merge(watched,bound)
    require(names, 'actual current candidate native pin verification required')
    basis_path=binding(request['VendorBasis'],watched)
    basis,basis_inputs=vendor.audit_value(scope_path)
    require(read(basis_path)==basis, 'vendor reset basis differs from current recomputation')
    current.merge(watched,basis_inputs)
    for flag in ('VendorSameConfigurationVerified','RegisteredEntryContractVerified','InternalResetContractVerified'):
        require(basis.get(flag) is True, 'missing vendor/entry reset contract: '+flag)
    require(basis.get('SourceADFSHA256')==SOURCE_SHA, 'vendor basis candidate differs')
    report_path=binding(request['BaselineRouteReport'],watched)
    report,report_inputs=derived.bind_receipt(report_path);current.merge(watched,report_inputs)
    require(report['Mode']=='report' and report['SourceADFSHA256']==SOURCE_SHA
            and report['SourceReceipt']==scope['RouteApplicationReceipt'], 'baseline fresh route receipt differs')
    dump=report_path.parent/'route-dump.txt'
    require(report['Artifacts'].get('route-dump.txt')==sha(dump), 'fresh baseline route dump unbound')
    add(watched,dump)
    # These exact independently reviewed results preserve the original strict
    # ordering diagnostic instead of rewriting it as a pass. Full reset effect
    # still rechecks all functional cells and all routes after the new save.
    for key,digest in (('BaselineFunctionalComparison','3a7c84923194e28bb25833395deec83db690144d5aedd9888b081f2578c838ee'),
                       ('BaselineSerialization','114bfe0498abb4885d2fbf8c5abd805254f85f4401eb966248b7a79041aebd06')):
        proof_path=binding(request[key],watched)
        require(request[key]['SHA256']==digest, 'exact reviewed route-b proof required')
        proof=read(proof_path)
        hashes=proof.get('BoundFiles') if key=='BaselineSerialization' else proof.get('InputSHA256')
        require(isinstance(hashes,dict) and hashes,'baseline proof input closure missing')
        for name,h in hashes.items():
            p=Path(name).resolve()
            if p not in watched:
                require(p.is_relative_to(prep.PROJECT.parent), 'unbound external route proof input')
            add(watched,p,h)
    current.bind_tools(watched);add(watched,vendor.__file__);add(watched,SELF)
    commands=current.commands.exact_commands(scope['NativeQueries'])
    build=read(scope['BuildPlan'])
    require(not inspect.drift(watched),'reset application evidence drift')
    return request,scope,names,basis,build,dump,commands,watched

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

def recipe(request_path,work,maximum=300):
    work=prep.work_path(work)
    require(type(maximum)is int and 120<=maximum<=300,'bound must be120..300 seconds')
    request,scope,names,basis,build,dump,commands,watched=bind_request(request_path)
    tcl=render(commands,work)
    value={'Schema':SCHEMA,'Target':prep.TARGET,'Mode':'save-reset-only','WorkDirectory':str(work),
        'Request':{'Path':str(Path(request_path).resolve()),'SHA256':sha(request_path)},
        'BuildPlan':scope['BuildPlan'],'BuildPlanSHA256':scope['BuildPlanSHA256'],
        'SourceADF':scope['SourceADF'],'SourceADFSHA256':SOURCE_SHA,
        'SourceReceipt':scope['ExportReceipt'],'RouteApplicationReceipt':scope['RouteApplicationReceipt'],
        'BuildDiagnosticsReview':scope['BuildDiagnosticsReview'],
        'BuildExecutionCompletedWithoutError':False,'BuildDiagnosticsCleared':False,
        'ResetScopePlan':request['ScopePlan'],'NativeQueryReceipt':request['QueryReceipt'],
        'VendorBasis':request['VendorBasis'],'BaselineRouteReport':request['BaselineRouteReport'],
        'BaselineFunctionalComparison':request['BaselineFunctionalComparison'],
        'BaselineSerialization':request['BaselineSerialization'],
        'BaselineRouteDump':{'Path':str(dump),'SHA256':sha(dump)},
        'NativeQueries':scope['NativeQueries'],'ExpectedNativeNameProof':names,
        'ExactResetCommands':commands,'ExactRouteCommands':[],
        'MaximumSeconds':maximum,'ExpectedActualStages':[],
        'InputSHA256':{str(p):h for p,h in watched.items()},
        'TclSHA256':prep.baseline.paths.sha_bytes(tcl.encode('ascii')),
        'Command':[build['PDS']['Executable'],'-file',(work/'stage.tcl').as_posix(),
                   '-work_dir',work.as_posix(),'-project_name',prep.TARGET],
        'HardwareAccessed':False,'BitstreamRequested':False,'TimingAccepted':False,
        'HardwareReleaseAllowed':False,'OpticalCorrectionAccepted':False,
        'FinalSTAExecuted':False,'AppliedScopeReadbackVerified':False,'DiagnosticCopyOnly':True,
        'DataTimingWaiverAllowed':False,'TimingExceptionApproved':False,
        'VendorSameConfigurationVerified':True,'RegisteredEntryContractVerified':True,
        'InternalResetContractVerified':True}
    return value,tcl,watched


def prepare(request,work,maximum=300):
    value,tcl,watched=recipe(request,work,maximum);work=Path(value['WorkDirectory'])
    require(not work.exists() and not inspect.drift(watched),'fresh stage and stable inputs required');work.mkdir()
    shutil.copyfile(value['SourceADF'],work/'input.adf');shutil.copyfile(SELF,work/'executor-snapshot.py')
    (work/'stage.tcl').write_text(tcl,encoding='ascii',newline='\n')
    (work/'dummy.v').write_text(DUMMY,encoding='ascii',newline='\n')
    value['PreparedUTC']=prep.utc();inspect.diagnostic.write(work/'stage-plan.json',value)
    return work/'stage-plan.json'


def bound_plan(path,fresh):
    path=inspect.canonical(path,prep.WORK);work=prep.work_path(path.parent);value=read(path)
    require(path.name=='stage-plan.json' and value.get('Schema')==SCHEMA,'exact raw physical stage-plan required')
    expected,tcl,watched=recipe(value['Request']['Path'],work,value['MaximumSeconds'])
    require(set(value)==set(expected)|{'PreparedUTC'} and isinstance(value['PreparedUTC'],str) and value['PreparedUTC']
            and {k:v for k,v in value.items() if k!='PreparedUTC'}==expected,'physical plan differs from exact recipe')
    files={'stage-plan.json','stage.tcl','dummy.v','input.adf','executor-snapshot.py'}
    if fresh:require({p.name for p in work.iterdir()}==files,'physical stage contaminated or reused')
    require((work/'stage.tcl').read_bytes()==tcl.encode('ascii') and (work/'dummy.v').read_bytes()==DUMMY.encode('ascii')
            and sha(work/'executor-snapshot.py')==sha(SELF),'physical stage instruction drift')
    if fresh:require(sha(work/'input.adf')==SOURCE_SHA,'physical input copy differs')
    for name in files-{'input.adf'}:add(watched,work/name)
    require(not inspect.drift(watched),'physical stage input drift')
    return value,watched


def validate_prepared(path):return bound_plan(path,True)


def artifact_hashes(work):
    return {p.relative_to(work).as_posix():sha(p) for p in work.rglob('*') if p.is_file()
            and p.suffix in ARTIFACT_SUFFIXES and p.name!='result.json'}


def execution_ok(value):
    return (value.get('Schema')==SCHEMA and value.get('Target')==prep.TARGET and value.get('ExitCode')==0
        and value.get('EDAExecuted') is True and not value.get('Error') and value.get('TimedOut') is False
        and value.get('StoppedForUnexpectedStage') is False and value.get('InputDrift')==[]
        and value.get('Diagnostics')==[] and value.get('ActualEvents')==[] and value.get('CompletionMarker') is True
        and value.get('InitializationPreservedADF') is True and value.get('SavedADFReadbackMatches') is True
        and value.get('ResultADFChanged') is True and value.get('NativeApplicationNamesVerified') is True
        and value.get('Cleanup',{}).get('Complete') is True)


def bind_completed(path,watched):
    path=inspect.canonical(path,prep.WORK);work=path.parent;value=read(path)
    require(path.name=='result.json' and value.get('ExecutionPassed') is True and execution_ok(value),'clean current raw reset save required')
    plan,bound=bound_plan(work/'stage-plan.json',False);watched.update(bound)
    require(all(value.get(k)==v for k,v in plan.items()) and value['StagePlanSHA256']==sha(work/'stage-plan.json'),
            'physical receipt differs from exact plan')
    require(value['Artifacts']==artifact_hashes(work),'physical artifact inventory/bytes differ')
    for name,digest in value['Artifacts'].items():add(watched,inspect.canonical(work/name,work),digest)
    require(inspect.scan_diagnostics(work)==[],'physical critical/error diagnostics present')
    log=(work/'stdout.log').read_text(encoding='gb18030',errors='replace')
    require(inspect.diagnostic.stage_events(log)==[] and MARKER in log,'physical stage events/marker differ')
    actual_names=current.reset.query_parser.exact_queries(value['NativeQueries'],work/'stdout.log')
    require(actual_names==value.get('ApplicationNativeNameProof')
            and actual_names==value['ExpectedNativeNameProof'], 'applied reset selectors differ from exact native queries')
    require(sha(work/'post-init.adf')==SOURCE_SHA and sha(work/'input.adf')==sha(work/'saved-reset.adf')==value['ResultADFSHA256']
            and value['ResultADFSHA256']!=SOURCE_SHA,
            'physical ADF initialization/save chain differs')
    for name in ('input.adf','post-init.adf','saved-reset.adf'):
        p=work/name
        require(value['ADFReadback'][name]=={'Path':str(p),'SHA256':sha(p),'Bytes':p.stat().st_size},'ADF readback record differs')
    require(value['ResultADF']==value['ADFReadback']['input.adf'],'result ADF record differs')
    add(watched,path);require(not inspect.drift(watched),'physical completed evidence drift')
    return value


def execute(path):
    value,watched=validate_prepared(path);work=Path(value['WorkDirectory'])
    require(os.name=='nt','native PDS requires Windows')
    result={**value,'StagePlanSHA256':sha(path),'StartedUTC':prep.utc(),'EDAExecuted':False,'ExecutionPassed':False,
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
            result['Cleanup']=(inspect.diagnostic.cleanup.stop_owned_tree(process,work,'bounded raw reset-only') if process.poll() is None
                               else {'Complete':True,'OwnedPID':process.pid,'ParentExited':True,'DescendantLivenessIndependentlyVerified':False})
            result['ExitCode']=process.poll()
        else:result['Cleanup']={'Complete':True,'Required':False}
    try:
        log=(work/'stdout.log').read_text(encoding='gb18030',errors='replace') if (work/'stdout.log').exists() else ''
        adfs={n:{'Path':str(work/n),'SHA256':sha(work/n),'Bytes':(work/n).stat().st_size}
              for n in ('input.adf','post-init.adf','saved-reset.adf') if (work/n).is_file()}
        final=adfs.get('input.adf',{}).get('SHA256')
        actual_names=current.reset.query_parser.exact_queries(value['NativeQueries'],work/'stdout.log')
        result.update(ActualEvents=inspect.diagnostic.stage_events(log),InputDrift=inspect.drift(watched),
            Diagnostics=inspect.scan_diagnostics(work),CompletionMarker=MARKER in log,ADFReadback=adfs,
            ResultADF=adfs.get('input.adf'),ResultADFSHA256=final,
            InitializationPreservedADF=adfs.get('post-init.adf',{}).get('SHA256')==SOURCE_SHA,
            SavedADFReadbackMatches=bool(final) and adfs.get('saved-reset.adf',{}).get('SHA256')==final,
            ResultADFChanged=bool(final) and final!=SOURCE_SHA,Artifacts=artifact_hashes(work),
            ApplicationNativeNameProof=actual_names,NativeApplicationNamesVerified=actual_names==value['ExpectedNativeNameProof'])
    except Exception as error:result['Error']=type(error).__name__+': '+str(error)
    result.update(FinishedUTC=prep.utc(),ElapsedSeconds=round(time.monotonic()-started,3))
    result['ExecutionPassed']=execution_ok(result)
    inspect.diagnostic.write(work/'result.json',result)
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--request',type=Path);p.add_argument('--name')
    p.add_argument('--stage-plan',type=Path);p.add_argument('--maximum-seconds',type=int,default=300)
    mode=p.add_mutually_exclusive_group();mode.add_argument('--prepare-only',action='store_true');mode.add_argument('--execute',action='store_true');mode.add_argument('--validate-only',action='store_true')
    a=p.parse_args()
    if a.stage_plan:
        require(not a.request and not a.name and not a.prepare_only,'stage plan only accepts validation or execution')
        if a.execute:value=execute(a.stage_plan)
        else:validate_prepared(a.stage_plan);value={'Validated':True,'EDAExecuted':False}
    else:
        require(a.request and a.name and not a.execute,'prepare exact request first; execute only stage-plan')
        if a.prepare_only:value={'Prepared':True,'StagePlan':str(prepare(a.request,prep.WORK/a.name,a.maximum_seconds)),'EDAExecuted':False}
        else:recipe(a.request,prep.WORK/a.name,a.maximum_seconds);value={'Validated':True,'EDAExecuted':False}
    print(json.dumps({k:value[k] for k in ('Prepared','Validated','StagePlan','ExecutionPassed','ExitCode','ResultADFSHA256','EDAExecuted') if k in value}))
    return 0 if value.get('ExecutionPassed',True) else 1


if __name__=='__main__':raise SystemExit(main())
