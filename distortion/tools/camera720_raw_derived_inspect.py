"""Fresh-process export/query of an exact current720 raw route-only derivative.

No old physical receipt or arbitrary ADF is accepted. Full route comparison is
an independent CPU check after the saved candidate is reopened by native PDS.
"""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time

import camera720_raw_physical as physical

inspect=physical.inspect
prep,diagnostic=inspect.prep,inspect.diagnostic
require,sha=inspect.require,inspect.sha
canonical,drift=inspect.canonical,inspect.drift
scan_diagnostics,native_netlist_valid=inspect.scan_diagnostics,inspect.native_netlist_valid
SELF=Path(__file__).resolve()
SCHEMA='camera720-current-raw-derived-inspection-v1'
MARKER='CAMERA720_CURRENT_RAW_DERIVED_INSPECTION_COMPLETE'
INIT=inspect.INIT
utc=prep.utc


def render(mode,original,base,work,body=None):
    require(mode in ('query','report','export'),'unsupported derived inspection mode')
    require(body is None or MARKER not in body,'reserved derived completion marker')
    if mode in ('query','export'):
        return inspect.render(mode,original,base,work,body).replace(inspect.MARKER,MARKER)
    require(body is None,'report mode accepts no body')
    w=work.as_posix()
    return ('set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG676\n'
            'add_design {'+w+'/dummy.v}\nif {[info script] ne {}} {\n'
            '    mpnr -input {'+w+'/input.adf}\n    '+INIT+'\n'
            '    .switch_db -route -input {'+w+'/input.adf} -output {'+w+'/route-dump.txt}\n'
            '    puts {'+MARKER+'}\n    flush stdout\n}\n')


def recipe(source_receipt,source_sha,work,mode,body_path=None,maximum=300):
    work=prep.work_path(work)
    require(type(maximum) is int and 120<=maximum<=300,'inspection bound must be120..300 seconds')
    watched={};source_receipt=physical.add(watched,source_receipt,source_sha)
    result=physical.bind_completed(source_receipt,watched)
    source=Path(result['ResultADF']['Path']);build_path=Path(result['BuildPlan'])
    build=physical.read(build_path)
    body=None
    if mode=='query':
        body_path=canonical(body_path,prep.WORK);physical.add(watched,body_path)
        body=body_path.read_text(encoding='ascii')
    else:require(body_path is None,'non-query mode accepts no body')
    tcl=render(mode,(build_path.parent/'timing.tcl').read_text(encoding='ascii'),build_path.parent,work,body)
    physical.add(watched,SELF)
    require(not drift(watched),'physical derivative input drift')
    value={'Schema':SCHEMA,'Target':prep.TARGET,'Mode':mode,'WorkDirectory':str(work),
        'BuildPlan':str(build_path),'BuildPlanSHA256':sha(build_path),
        'SourceReceipt':{'Path':str(source_receipt),'SHA256':source_sha},
        'SourceADF':str(source),'SourceADFSHA256':result['ResultADFSHA256'],
        'OriginalSourceADF':result['SourceADF'],'OriginalSourceADFSHA256':result['SourceADFSHA256'],
        'BuildDiagnosticsReview':result['BuildDiagnosticsReview'],
        'BuildExecutionCompletedWithoutError':False,'BuildDiagnosticsCleared':False,
        'QueryBody':str(body_path) if body_path else None,'MaximumSeconds':maximum,
        'ExpectedActualStages':['Report Timing','Generate Netlist'] if mode=='export' else [],
        'InputSHA256':{str(p):h for p,h in watched.items()},
        'TclSHA256':prep.baseline.paths.sha_bytes(tcl.encode('ascii')),
        'Command':[build['PDS']['Executable'],'-file',(work/'stage.tcl').as_posix(),'-work_dir',work.as_posix(),'-project_name',prep.TARGET],
        'HardwareAccessed':False,'BitstreamRequested':False,'TimingAccepted':False,'HardwareReleaseAllowed':False,
        'OpticalCorrectionAccepted':False,
        'Limits':'Fresh native read-only inspection of exact route derivative. Build diagnostics remain unresolved. Full timing, functional netlist and route comparisons require separate audits.'}
    return value,tcl,watched


def prepare(*args, **kwargs):
    value,tcl,watched = recipe(*args, **kwargs)
    work = Path(value['WorkDirectory'])
    require(not work.exists(), 'fresh inspection directory required')
    require(not drift(watched), 'input drift before preparation')
    work.mkdir()
    shutil.copyfile(value['SourceADF'], work/'input.adf')
    require(sha(work/'input.adf') == value['SourceADFSHA256'], 'ADF copy differs')
    (work/'stage.tcl').write_text(tcl,encoding='ascii',newline='\n')
    shutil.copyfile(SELF,work/'executor-snapshot.py')
    if value['Mode']!='export':
        (work/'dummy.v').write_text('module physical_dummy(input a, output y); assign y=a; endmodule\n',encoding='ascii',newline='\n')
    value['PreparedUTC'] = utc()
    diagnostic.write(work/'stage-plan.json',value)
    return work/'stage-plan.json'


def validate_prepared(path):
    path = canonical(path,prep.WORK)
    work = prep.work_path(path.parent)
    require(path.name=='stage-plan.json','exact stage-plan.json required')
    value = json.loads(path.read_text())
    require(value.get('Schema')==SCHEMA and value.get('Target')==prep.TARGET,'current720 raw inspection identity differs')
    expected,tcl,watched = recipe(value['SourceReceipt']['Path'],value['SourceReceipt']['SHA256'],work,
                                value['Mode'],value['QueryBody'],value['MaximumSeconds'])
    require(set(value)==set(expected)|{'PreparedUTC'} and {k:v for k,v in value.items() if k!='PreparedUTC'}==expected,
            'inspection plan differs from bound recipe')
    files={'input.adf','stage.tcl','executor-snapshot.py','stage-plan.json'}
    if value['Mode']!='export':files.add('dummy.v')
    require({p.name for p in work.iterdir()}==files,'inspection stage reused or contaminated')
    require((work/'stage.tcl').read_bytes()==tcl.encode('ascii') and sha(work/'input.adf')==value['SourceADFSHA256']
            and sha(work/'executor-snapshot.py')==sha(SELF),'inspection prepared artifact drift')
    if value['Mode']!='export':
        require((work/'dummy.v').read_bytes()==b'module physical_dummy(input a, output y); assign y=a; endmodule\n','dummy context changed')
    for name in files:watched[canonical(work/name,work)]=sha(work/name)
    require(not drift(watched),'inspection input drift')
    return value,watched


def bind_receipt(path):
    """Rebind a finished read-only inspection for downstream CPU audits.

    Unlike validate_prepared this permits generated artifacts, but every
    original input, stage command and artifact is checked against the receipt.
    Neither this function nor the receipt approves a timing exception.
    """
    path = canonical(path, prep.WORK)
    work = prep.work_path(path.parent)
    require(path.name == 'result.json', 'exact finished inspection result required')
    value = json.loads(path.read_text(encoding='utf-8'))
    require(value.get('Schema') == SCHEMA and value.get('Target') == prep.TARGET, 'wrong finished inspection identity')
    expected,tcl,watched = recipe(value['SourceReceipt']['Path'],value['SourceReceipt']['SHA256'],work,
                                value['Mode'],value['QueryBody'],value['MaximumSeconds'])
    stage_path = canonical(work/'stage-plan.json', work)
    stage = json.loads(stage_path.read_text(encoding='utf-8'))
    require(set(stage) == set(expected)|{'PreparedUTC'} and isinstance(stage['PreparedUTC'], str)
            and stage['PreparedUTC'] and {k:v for k,v in stage.items() if k!='PreparedUTC'} == expected,
            'finished inspection stage differs from exact recipe')
    require(all(value.get(k) == v for k,v in stage.items()) and value.get('StagePlanSHA256') == sha(stage_path),
            'finished inspection receipt differs from its stage plan')
    require(value.get('EDAExecuted') is True and value.get('ExecutionPassed') is True
            and value.get('ExitCode') == 0 and value.get('TimedOut') is False
            and value.get('StoppedForUnexpectedStage') is False and not value.get('Error')
            and value.get('InputDrift') == [] and value.get('Diagnostics') == []
            and value.get('CompletionMarker') is True and value.get('InputADFUnchanged') is True
            and value.get('Cleanup', {}).get('Complete') is True, 'finished inspection was not clean')
    for flag in ('HardwareAccessed', 'BitstreamRequested', 'TimingAccepted',
                 'HardwareReleaseAllowed', 'OpticalCorrectionAccepted'):
        require(value.get(flag) is False, 'finished inspection exceeds read-only scope: '+flag)
    require((work/'stage.tcl').read_bytes() == tcl.encode('ascii')
            and sha(work/'executor-snapshot.py') == sha(SELF)
            and sha(work/'input.adf') == value['SourceADFSHA256'], 'finished inspection input copy drift')
    if value['Mode'] != 'export':
        require((work/'dummy.v').read_bytes() == b'module physical_dummy(input a, output y); assign y=a; endmodule\n',
                'finished query dummy context drift')
    stages = ['Report Timing', 'Generate Netlist'] if value['Mode']=='export' else []
    events = [[s,e] for s in stages for e in ('started','done')]
    log = (work/'stdout.log').read_text(encoding='gb18030', errors='replace')
    require(value['ExpectedActualStages'] == stages and value.get('ActualEvents') == events
            and [list(item) for item in diagnostic.stage_events(log)] == events and MARKER in log,
            'finished native stages or completion marker differ')
    artifacts = value.get('Artifacts')
    require(isinstance(artifacts, dict) and {'stage.tcl', 'stdout.log', 'stderr.log'} <= set(artifacts),
            'finished native artifact bindings missing')
    actual = {p.relative_to(work).as_posix() for p in work.rglob('*') if p.is_file()
              and p.suffix in ('.tcl', '.log', '.rtr', '.v', '.gnr', '.txt', '.fdc')}
    require(actual == set(artifacts), 'finished native artifact inventory differs')
    require(scan_diagnostics(work) == [], 'finished native critical/error diagnostics present')
    for name, digest in artifacts.items():
        artifact = canonical(work/name, work)
        require(sha(artifact) == digest, 'finished native artifact drift: '+name)
        watched[artifact] = digest
    if value['Mode'] == 'export':
        netlist = canonical(work/'generate_netlist'/(prep.TARGET+'_sim.v'), work)
        require(native_netlist_valid(netlist) and value.get('NativeNetlistWithFFloc') is True and value.get('Netlist') == {
            'Path': str(netlist), 'SHA256': sha(netlist), 'Bytes': netlist.stat().st_size}, 'native placed export binding differs')
    for item in (path, stage_path, work/'executor-snapshot.py', work/'input.adf'):
        watched[item] = sha(item)
    require(not drift(watched), 'finished inspection input or artifact drift')
    return value, watched


def execute(path):
    value,watched = validate_prepared(path)
    require(os.name=='nt','native inspection requires Windows')
    work=Path(value['WorkDirectory']);result={**value,'StagePlanSHA256':sha(path),'StartedUTC':utc(),
        'EDAExecuted':False,'ExecutionPassed':False,'TimedOut':False,'StoppedForUnexpectedStage':False,'ExitCode':None}
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
        Netlist={'Path':str(netlist),'SHA256':sha(netlist),'Bytes':netlist.stat().st_size} if netlist.is_file() else None,
        Artifacts={p.relative_to(work).as_posix():sha(p) for p in work.rglob('*') if p.is_file()
                   and p.suffix in ('.tcl','.log','.rtr','.v','.gnr','.txt','.fdc')})
    result['ExecutionPassed']=(result['ExitCode']==0 and not result.get('Error') and not result['TimedOut']
        and not result['StoppedForUnexpectedStage'] and not result['InputDrift'] and not diagnostics
        and events==expected and result['CompletionMarker'] and result['InputADFUnchanged']
        and result['Cleanup'].get('Complete',False) and (value['Mode']!='export' or netvalid))
    diagnostic.write(work/'result.json',result)
    return result


def compare_routes(receipt,receipt_sha,output):
    watched={};path=physical.add(watched,receipt,receipt_sha)
    value,bound=bind_receipt(path);watched.update(bound)
    require(value['Mode']=='report','fresh native report/route receipt required')
    saved=physical.bind_completed(value['SourceReceipt']['Path'],watched)
    targets=saved['MeasuredTargets']
    original=physical.binding(saved['OriginalRouteDump'],watched)
    after=physical.add(watched,path.parent/'route-dump.txt')
    require(value['Artifacts'].get('route-dump.txt')==sha(after),'derived native route dump unbound')
    before_data=physical.routes.inspect(original,targets)
    after_data=physical.routes.inspect(after,targets)
    comparison=physical.routes.compare(before_data,after_data,targets,allow_constraint_change=False)
    require(comparison['ChangedNetCount']==len({t['Net'] for t in targets}),'not every measured route changed')
    for target,row in zip(targets,saved['Routes']):
        old=before_data['BranchInventory'][target['Net']]['Leaves'][target['ToRoutePin']]
        new=after_data['BranchInventory'][target['Net']]['Leaves'][target['ToRoutePin']]
        pins=row['Pins'].replace(';','>').strip('>').split('>')
        require(new!=old and all(pin in new for pin in pins),'requested detour absent from actual saved route')
    result={'Schema':'camera720-current-raw-route-comparison-v1','Target':prep.TARGET,
        'SourceReceipt':value['SourceReceipt'],'DerivedReceipt':{'Path':str(path),'SHA256':receipt_sha},
        'OriginalRouteDump':saved['OriginalRouteDump'],
        'DerivedRouteDump':{'Path':str(after),'SHA256':sha(after)},'RouteComparison':comparison,
        'InputSHA256':{str(p):h for p,h in watched.items()},'BuildDiagnosticsCleared':False,
        'TimingAccepted':False,'HardwareReleaseAllowed':False}
    require(not drift(watched),'route evidence changed during comparison')
    diagnostic.write(Path(output),result)
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source-receipt',type=Path);p.add_argument('--source-sha256');p.add_argument('--name')
    p.add_argument('--mode',choices=('query','report','export'));p.add_argument('--body',type=Path)
    p.add_argument('--maximum-seconds',type=int,default=300);p.add_argument('--stage-plan',type=Path)
    modes=p.add_mutually_exclusive_group();modes.add_argument('--prepare-only',action='store_true')
    modes.add_argument('--execute',action='store_true');modes.add_argument('--validate-only',action='store_true')
    a=p.parse_args()
    if a.stage_plan:
        require(not any((a.source_receipt,a.source_sha256,a.name,a.mode,a.body,a.prepare_only)),'exact stage-plan validation or execution only')
        if a.execute:value=execute(a.stage_plan)
        else:validate_prepared(a.stage_plan);value={'Validated':True,'EDAExecuted':False}
    else:
        require(a.source_receipt and a.source_sha256 and a.name and a.mode and not a.execute,'prepare exact derived receipt first')
        args=(a.source_receipt,a.source_sha256,prep.WORK/a.name,a.mode,a.body,a.maximum_seconds)
        if a.prepare_only:value={'Prepared':True,'StagePlan':str(prepare(*args)),'EDAExecuted':False}
        else:recipe(*args);value={'Validated':True,'EDAExecuted':False}
    print(json.dumps({k:value[k] for k in ('Prepared','Validated','StagePlan','ExecutionPassed','ExitCode','EDAExecuted') if k in value}))
    return 0 if value.get('ExecutionPassed',True) else 1


if __name__=='__main__':raise SystemExit(main())
