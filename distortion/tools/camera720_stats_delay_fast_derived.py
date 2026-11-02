"""Explicit source seal for compatible current hold-derived native inspections.

Seal performs the frozen full recipe once. Later boundaries rehash every bound
byte. Native reports are still fresh; the frozen ordinary inspector can fully
recompute and validate the resulting compatible stage/receipt independently.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

import camera720_stats_delay_derived_inspect as original
import camera720_stats_delay_hold_route as hold

physical,inspect,prep=original.physical,original.inspect,original.prep
require,sha,read,add=physical.require,physical.sha,physical.read,physical.add
SELF=Path(__file__).resolve()
SCHEMA='camera720-stats-delay-hold-derived-source-seal-v1'


def ref(path):
    path=Path(path).resolve()
    return {'Path':str(path),'SHA256':sha(path)}


def explicit(digest):
    require(isinstance(digest,str) and re.fullmatch('[0-9a-f]{64}',digest),
            'explicit lowercase SHA256 required')


def seal_source(receipt,receipt_sha,output):
    explicit(receipt_sha)
    output=Path(output).absolute()
    require(output==output.resolve() and output.parent==prep.WORK and output.suffix=='.json'
            and not output.exists(),'fresh direct source authority required')
    # Frozen recipe binds the actual completed hold application and all graph,
    # complete route/CDB/source-metadata comparisons, exactly once here.
    example,_,watched=original.recipe(receipt,receipt_sha,prep.WORK/'sealed-source-recipe-only','report')
    value={'Schema':SCHEMA,'Target':prep.TARGET,'CreatedUTC':inspect.utc(),
        'Producer':ref(SELF),'Validator':ref(original.SELF),'HoldProvider':ref(hold.SELF),
        'ValidationFunction':'camera720_stats_delay_derived_inspect.recipe',
        'SourceReceipt':example['SourceReceipt'],
        'CandidateADF':ref(example['SourceADF']),
        'BuildPlan':ref(example['BuildPlan']),
        'BaseInputSHA256':{str(p):h for p,h in watched.items()},
        'FullVerificationCompleted':True,'EDAExecuted':False,'HardwareAccessed':False,
        'TimingAccepted':False,'HardwareReleaseAllowed':False}
    for p in (SELF,Path(sys.executable).resolve()):add(watched,p)
    value['InputSHA256']={str(p):h for p,h in watched.items()}
    value['ToolSHA256']={p:h for p,h in value['InputSHA256'].items() if Path(p).suffix.lower() in ('.py','.exe')}
    require(not inspect.drift(watched),'source seal input drift')
    inspect.diagnostic.write(output,value)
    require(read(output)==value,'source seal readback differs')
    return output


def bind_authority(path,expected_sha):
    explicit(expected_sha);watched={};path=add(watched,path,expected_sha);v=read(path)
    require(v.get('Schema')==SCHEMA and v.get('Target')==prep.TARGET
        and v.get('FullVerificationCompleted') is True
        and v.get('ValidationFunction')=='camera720_stats_delay_derived_inspect.recipe'
        and v.get('Producer')==ref(SELF) and v.get('Validator')==ref(original.SELF)
        and v.get('HoldProvider')==ref(hold.SELF),'source seal producer/validator identity differs')
    for k in ('EDAExecuted','HardwareAccessed','TimingAccepted','HardwareReleaseAllowed'):
        require(v.get(k) is False,'source authority overclaims '+k)
    hashes=v.get('InputSHA256');base=v.get('BaseInputSHA256')
    require(isinstance(hashes,dict) and hashes and isinstance(base,dict) and base,
            'source seal closure missing')
    for name,digest in hashes.items():
        p=Path(name).absolute()
        require(p==p.resolve(),'noncanonical sealed path')
        add(watched,p,digest)
    require(v.get('ToolSHA256')=={p:h for p,h in hashes.items() if Path(p).suffix.lower() in ('.py','.exe')},
            'source seal tool closure differs')
    require(all(hashes.get(p)==h for p,h in base.items()),'base closure absent from seal')
    def bound(r):
        require(set(r)=={'Path','SHA256'} and base.get(r['Path'])==r['SHA256'],
                'required original source reference unbound')
        return Path(r['Path'])
    receipt=bound(v['SourceReceipt']);candidate=bound(v['CandidateADF']);build=bound(v['BuildPlan'])
    result=read(receipt);stage_path=receipt.parent/'stage-plan.json';stage=read(stage_path)
    require(result.get('ExecutionPassed') is True and hold.execution_ok(result),'sealed actual hold result not clean')
    require(all(result.get(k)==x for k,x in stage.items()) and result['StagePlanSHA256']==sha(stage_path),
            'sealed actual hold result/stage mismatch')
    require(result['ResultADF']['Path']==str(candidate) and result['ResultADFSHA256']==sha(candidate)
        and result['BuildPlan']==str(build) and result['BuildPlanSHA256']==sha(build),
            'sealed candidate or build mismatch')
    for p,h in result['InputSHA256'].items():require(base.get(p)==h,'original input omitted from seal')
    artifacts=hold.artifact_hashes(receipt.parent)
    require(result['Artifacts']==artifacts,'sealed hold artifact inventory differs')
    for n,h in artifacts.items():require(base.get(str(receipt.parent/n))==h,'actual artifact omitted from seal')
    require(sha(receipt.parent/'post-init.adf')==result['SourceADFSHA256']
        and sha(receipt.parent/'saved-route.adf')==sha(candidate)!=result['SourceADFSHA256'],
            'sealed initialization/save chain differs')
    for tool in (original.SELF,hold.SELF):require(base.get(str(tool))==sha(tool),'validator missing from base closure')
    require(not inspect.drift(watched),'sealed input drift')
    return result,{Path(p):h for p,h in base.items()},watched


def recipe(authority,authority_sha,work,mode,body_path=None,maximum=300):
    work=prep.work_path(work)
    require(type(maximum)is int and 120<=maximum<=300,'inspection bound must be120..300 seconds')
    result,base,watched=bind_authority(authority,authority_sha)
    source=Path(result['ResultADF']['Path']);build_path=Path(result['BuildPlan']);build=read(build_path)
    body=None
    if mode=='query':
        body_path=inspect.canonical(body_path,prep.WORK);add(base,body_path);add(watched,body_path)
        body=body_path.read_text(encoding='ascii')
    else:require(body_path is None,'non-query mode accepts no body')
    tcl=original.render(mode,(build_path.parent/'timing.tcl').read_text(encoding='ascii'),build_path.parent,work,body)
    # Exact compatible frozen recipe fields; the execution seal is separately
    # included in the native result and runtime drift checks, never hidden.
    value={'Schema':original.SCHEMA,'Target':prep.TARGET,'Mode':mode,'WorkDirectory':str(work),
        'BuildPlan':str(build_path),'BuildPlanSHA256':sha(build_path),
        'SourceReceipt':read(authority)['SourceReceipt'],
        'SourceADF':str(source),'SourceADFSHA256':result['ResultADFSHA256'],
        'OriginalSourceADF':result['SourceADF'],'OriginalSourceADFSHA256':result['SourceADFSHA256'],
        'BuildDiagnosticsReview':result['BuildDiagnosticsReview'],
        'BuildExecutionCompletedWithoutError':False,'BuildDiagnosticsCleared':False,
        'QueryBody':str(body_path) if body_path else None,'MaximumSeconds':maximum,
        'ExpectedActualStages':['Report Timing','Generate Netlist'] if mode=='export' else [],
        'InputSHA256':{str(p):h for p,h in base.items()},
        'TclSHA256':hashlib.sha256(tcl.encode('ascii')).hexdigest(),
        'Command':[build['PDS']['Executable'],'-file',(work/'stage.tcl').as_posix(),'-work_dir',work.as_posix(),'-project_name',prep.TARGET],
        'HardwareAccessed':False,'BitstreamRequested':False,'TimingAccepted':False,'HardwareReleaseAllowed':False,
        'OpticalCorrectionAccepted':False,
        'Limits':'Fresh native read-only inspection of exact route derivative. Build diagnostics remain unresolved. Full timing, functional netlist and route comparisons require separate audits.'}
    require(not inspect.drift(watched),'sealed recipe input drift')
    return value,tcl,watched


def prepare(*args,**kwargs):
    value,tcl,watched=recipe(*args,**kwargs);work=Path(value['WorkDirectory'])
    require(not work.exists() and not inspect.drift(watched),'fresh stage and stable sealed inputs required')
    work.mkdir();shutil.copyfile(value['SourceADF'],work/'input.adf')
    require(sha(work/'input.adf')==value['SourceADFSHA256'],'copied candidate differs')
    (work/'stage.tcl').write_text(tcl,encoding='ascii',newline='\n')
    shutil.copyfile(original.SELF,work/'executor-snapshot.py')
    if value['Mode']!='export':(work/'dummy.v').write_text('module physical_dummy(input a, output y); assign y=a; endmodule\n',encoding='ascii',newline='\n')
    value['PreparedUTC']=inspect.utc();inspect.diagnostic.write(work/'stage-plan.json',value)
    return work/'stage-plan.json'


def validate_prepared(path,authority,authority_sha):
    path=inspect.canonical(path,prep.WORK);value=read(path);work=prep.work_path(path.parent)
    require(path.name=='stage-plan.json','exact prepared stage filename required')
    expected,tcl,watched=recipe(authority,authority_sha,work,value['Mode'],value['QueryBody'],value['MaximumSeconds'])
    require(set(value)==set(expected)|{'PreparedUTC'} and isinstance(value['PreparedUTC'],str) and value['PreparedUTC']
        and {k:v for k,v in value.items() if k!='PreparedUTC'}==expected,'prepared stage differs from sealed exact recipe')
    files={'input.adf','stage.tcl','executor-snapshot.py','stage-plan.json'}
    if value['Mode']!='export':files.add('dummy.v')
    require({p.name for p in work.iterdir()}==files,'prepared native stage reused or contaminated')
    require((work/'stage.tcl').read_bytes()==tcl.encode('ascii') and sha(work/'input.adf')==value['SourceADFSHA256']
        and sha(work/'executor-snapshot.py')==sha(original.SELF),'prepared native stage bytes differ')
    if value['Mode']!='export':require((work/'dummy.v').read_bytes()==b'module physical_dummy(input a, output y); assign y=a; endmodule\n','dummy context changed')
    for n in files:add(watched,work/n)
    require(not inspect.drift(watched),'prepared sealed inputs drift')
    return value,watched


diagnostic=inspect.diagnostic
drift,scan_diagnostics=inspect.drift,inspect.scan_diagnostics
native_netlist_valid=inspect.native_netlist_valid
utc=inspect.utc
MARKER=original.MARKER


def execute(path,authority,authority_sha):
    value,watched = validate_prepared(path,authority,authority_sha)
    require(os.name=='nt','native inspection requires Windows')
    work=Path(value['WorkDirectory']);result={**value,'StagePlanSHA256':sha(path),'StartedUTC':utc(),
        'EDAExecuted':False,'ExecutionPassed':False,'TimedOut':False,'StoppedForUnexpectedStage':False,'ExitCode':None}
    result.update(ExecutionProvider=ref(SELF),SourceAuthority=ref(authority),SealedValidationClosure={str(p):h for p,h in watched.items()})
    diagnostic.write(work/'execution-start.json',result)
    process=None;started=time.monotonic()
    expected=[(s,e) for s in value['ExpectedActualStages'] for e in ('started','done')]
    try:
        with (work/'stdout.log').open('xb') as out,(work/'stderr.log').open('xb') as err:
            process=subprocess.Popen(value['Command'],cwd=work,stdout=out,stderr=err,shell=False,
                                     creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            result.update(EDAExecuted=True,OwnedPID=process.pid)
            while process.poll() is None:
                remaining=value['MaximumSeconds']-(time.monotonic()-started)
                if remaining<=0:result['TimedOut']=True;break
                try:process.wait(timeout=min(2,remaining))
                except subprocess.TimeoutExpired:pass
                events=diagnostic.stage_events((work/'stdout.log').read_text(encoding='gb18030',errors='replace'))
                if events!=expected[:len(events)]:result['StoppedForUnexpectedStage']=True;break
    except BaseException as error:
        result['Error']=type(error).__name__+': '+str(error)
    finally:
        if process is not None:
            if process.poll() is None:result['Cleanup']=diagnostic.cleanup.stop_owned_tree(process,work,'bounded inspection')
            else:result['Cleanup']={'Complete':True,'OwnedPID':process.pid,'ParentExited':True,'DescendantLivenessIndependentlyVerified':False}
            result['ExitCode']=process.poll()
        else:result['Cleanup']={'Complete':True,'Required':False}
    log=(work/'stdout.log').read_text(encoding='gb18030',errors='replace') if (work/'stdout.log').exists() else ''
    events=diagnostic.stage_events(log)
    diagnostics=scan_diagnostics(work)
    netlist=work/'generate_netlist'/(prep.TARGET+'_sim.v')
    netvalid=native_netlist_valid(netlist)
    result.update(FinishedUTC=utc(),ElapsedSeconds=round(time.monotonic()-started,3),ActualEvents=events,
        InputDrift=drift(watched),Diagnostics=diagnostics,CompletionMarker=MARKER in log,
        InputADFUnchanged=sha(work/'input.adf')==value['SourceADFSHA256'],NativeNetlistWithFFloc=netvalid if value['Mode']=='export' else None,
        TimingReport=inspect.timing_report(work,value['Mode']),
        Netlist={'Path':str(netlist),'SHA256':sha(netlist),'Bytes':netlist.stat().st_size} if netlist.is_file() else None,
        Artifacts={p.relative_to(work).as_posix():sha(p) for p in work.rglob('*') if p.is_file()
                   and p.suffix in ('.tcl','.log','.rtr','.v','.gnr','.txt','.fdc')})
    result['ExecutionPassed']=(result['ExitCode']==0 and not result.get('Error') and not result['TimedOut']
        and not result['StoppedForUnexpectedStage'] and not result['InputDrift'] and not diagnostics
        and events==expected and result['CompletionMarker'] and result['InputADFUnchanged']
        and result['Cleanup'].get('Complete',False) and result['TimingReport'] is not None and (value['Mode']!='export' or netvalid))
    diagnostic.write(work/'result.json',result)
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source-receipt',type=Path);p.add_argument('--source-sha256');p.add_argument('--seal-source',type=Path)
    p.add_argument('--authority',type=Path);p.add_argument('--authority-sha256');p.add_argument('--name')
    p.add_argument('--mode',choices=('query','report','export'));p.add_argument('--body',type=Path)
    p.add_argument('--maximum-seconds',type=int,default=300);p.add_argument('--stage-plan',type=Path)
    p.add_argument('--execute',action='store_true');p.add_argument('--prepare-only',action='store_true')
    a=p.parse_args()
    if a.seal_source:
        require(a.source_receipt and a.source_sha256 and not any((a.authority,a.authority_sha256,a.stage_plan,a.name,a.mode,a.body,a.execute,a.prepare_only)),'seal accepts only actual source receipt/SHA/output')
        out=seal_source(a.source_receipt,a.source_sha256,a.seal_source)
        print(json.dumps({'Sealed':True,'Authority':ref(out),'EDAExecuted':False}));return 0
    require(a.authority and a.authority_sha256 and not any((a.source_receipt,a.source_sha256)),'explicit source authority required')
    if a.stage_plan:
        require(not any((a.name,a.mode,a.body,a.prepare_only)),'stage action cannot mix preparation inputs')
        if a.execute:v=execute(a.stage_plan,a.authority,a.authority_sha256)
        else:validate_prepared(a.stage_plan,a.authority,a.authority_sha256);v={'Validated':True}
    else:
        require(a.name and a.mode and a.prepare_only and not a.execute,'prepare fresh exact stage first')
        out=prepare(a.authority,a.authority_sha256,prep.WORK/a.name,a.mode,a.body,a.maximum_seconds)
        v={'Prepared':True,'StagePlan':str(out),'EDAExecuted':False}
    print(json.dumps({k:v[k] for k in ('Prepared','StagePlan','Validated','ExecutionPassed','ExitCode','ElapsedSeconds') if k in v}))
    return 0 if v.get('ExecutionPassed',True) else 1


if __name__=='__main__':raise SystemExit(main())
