"""Save one current hold-branch route and optional proved reset scope on a copy.

The route identity is re-derived from this upright build's raw timing report;
waypoints must be unused in its receipt-bound complete route dump. No full PnR,
post-save STA, bitstream or hardware. A clean save is not timing acceptance.
"""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time

import run_camera_vga_upright_inspect as inspect
import run_camera_vga_upright_physical as physical
import audit_camera_vga_upright_io_cdc as evidence
import audit_camera_vga_hold as hold
import audit_camera_vga_routes as routes

prep=inspect.prep
require,sha=prep.require,prep.sha
SELF=Path(__file__).resolve()
REQUEST_SCHEMA='camera-vga-upright-route-reset-request-v1'
SCHEMA='camera-vga-upright-route-reset-application-v1'
MARKER='CAMERA_VGA_UPRIGHT_ROUTE_RESET_SAVED'
WAYPOINT=r'[A-Z][A-Z0-9_]*(?:\[\d+\])?:(?:CLMA|CLMS|IOLHR|SRB)_\d+_\d+'
CHAIN=WAYPOINT+'>'+WAYPOINT+';'


def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def route_commands(row,target,occupied):
    require(isinstance(row,dict) and set(row)=={'Net','Branch','Pins'},'exact route fields required')
    require(row['Net']==target['Net'] and re.fullmatch(r'_N\d+',row['Net'])
            and row['Branch']==target['ToRoutePin'],'only measured terminal net/branch allowed')
    require(re.fullmatch(WAYPOINT,row['Branch']) and re.fullmatch(CHAIN,row['Pins']),
            'one native waypoint pair with one final semicolon required')
    pins=row['Pins'][:-1].split('>')
    require(len(pins)==len(set(pins)),'repeated waypoint pin')
    require(all(not occupied.get(p) for p in pins),'waypoint pin already occupied in baseline route database')
    return ['show -design_net {'+row['Net']+'}',
        'unroute -branch {'+row['Net']+':'+row['Branch']+';}',
        'manual_route -net {'+row['Net']+'} -branch {'+row['Branch']+'} -pins {'+row['Pins']+'}',
        'show -design_net {'+row['Net']+'}']


def bind_request(request_path):
    watched={};request_path=physical.add(watched,inspect.canonical(request_path,prep.WORK));r=read(request_path)
    fields={'Schema','Target','BuildPlan','SourceADF','HoldAudit','QueryReceipt','RouteDump','Route','ResetProof'}
    require(set(r)==fields and r['Schema']==REQUEST_SCHEMA and r['Target']==prep.TARGET,'exact upright route/reset request required')
    plan_path=physical.binding(r['BuildPlan'],watched);source=physical.binding(r['SourceADF'],watched)
    plan,base=inspect.bind(plan_path,source,r['SourceADF']['SHA256']);watched.update(base)
    pds=Path(plan['PDS']['Executable']);audit_path=physical.binding(r['HoldAudit'],watched)
    report=plan_path.parent/'report_timing'/(prep.TARGET+'.rtr')
    require(report.is_file(),'current native timing report missing')
    actual,_=hold.build([report],expect_failures=1);record=read(audit_path)
    require({k:v for k,v in record.items() if k!='GeneratedUTC'}=={k:v for k,v in actual.items() if k!='GeneratedUTC'},
            'hold audit differs from actual current native report')
    require(actual['MissingExactSetup']==[],'exact setup evidence missing for route candidate')
    measured=actual['Paths'][0];target={**measured['PhysicalRepairCandidate'],'Endpoint':measured['Endpoint']}
    require(target['TimingWaiverAllowed'] is False and all(v['ExactSetupSlackNS']>0 for v in measured['Margins'].values()),
            'data route cannot use timing exceptions')
    query_path=physical.binding(r['QueryReceipt'],watched)
    _,query=evidence.receipt(query_path,'query',sha(source),sha(plan_path),watched)
    dump=physical.binding(r['RouteDump'],watched)
    require(dump.is_relative_to(query_path.parent) and query['Artifacts'].get(dump.relative_to(query_path.parent).as_posix())==sha(dump),
            'route dump not bound to original read-only native query')
    parsed=routes.inspect(dump,{target['Net']:target})
    commands=route_commands(r['Route'],target,parsed['_Occupied'])
    proof=None;fdc=None;reset_commands=[]
    if r['ResetProof'] is not None:
        proof_path=physical.binding(r['ResetProof'],watched)
        _,proof_source,proof,fdc,reset_commands,proof_inputs=physical.bind_proof(plan_path,proof_path,r['ResetProof']['SHA256'])
        require(proof_source==source and proof['SourceADFSHA256']==sha(source),'reset proof belongs to different route source')
        watched.update(proof_inputs)
    for mod in (inspect,inspect.diagnostic,inspect.diagnostic.cleanup,physical,physical.audit,evidence,hold,routes):
        physical.add(watched,Path(mod.__file__).resolve())
    physical.add(watched,SELF);physical.add(watched,report)
    require(not inspect.drift(watched),'route/reset source/evidence drift')
    return r,plan,source,target,commands,reset_commands,proof,fdc,watched


def render(commands,resets,work):
    w=work.as_posix()
    return ('set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG676\n'
        'add_design {'+w+'/dummy.v}\nif {[info script] ne {}} {\n    mpnr -input {'+w+'/input.adf}\n'
        +('    '+physical.INIT+'\n' if resets else '')
        +'    file copy {'+w+'/input.adf} {'+w+'/post-init.adf}\n'
        +'\n'.join(commands+resets)+'\n    save_adif\n'
        +'    file copy {'+w+'/input.adf} {'+w+'/saved-reset.adf}\n'
        +'    .switch_db -route -input {'+w+'/input.adf} -output {'+w+'/route-dump.txt}\n'
        +'    puts {'+MARKER+'}\n    flush stdout\n}\n')


def recipe(request_path,work,maximum=300):
    work=prep.work_path(work);require(type(maximum) is int and 120<=maximum<=300,'bound must be120..300 seconds')
    r,plan,source,target,commands,resets,proof,fdc,watched=bind_request(request_path)
    tcl=render(commands,resets,work)
    value={'Schema':SCHEMA,'Target':prep.TARGET,'Mode':'save-route-reset','WorkDirectory':str(work),
        'Request':{'Path':str(Path(request_path).absolute()),'SHA256':sha(request_path)},
        'BuildPlan':r['BuildPlan']['Path'],'BuildPlanSHA256':r['BuildPlan']['SHA256'],
        'SourceADF':str(source),'SourceADFSHA256':sha(source),'Route':r['Route'],'MeasuredTarget':target,
        'ResetProof':r['ResetProof'],'ResetFDC':{'Path':str(fdc),'SHA256':sha(fdc)} if fdc else None,
        'NativeQueries':proof['NativeQueries'] if proof else [],'ExactRouteCommands':commands,'ExactResetCommands':resets,
        'InputSHA256':{str(p):h for p,h in watched.items()},'MaximumSeconds':maximum,'ExpectedActualStages':[],
        'TclSHA256':prep.baseline.paths.sha_bytes(tcl.encode('ascii')),
        'Command':[plan['PDS']['Executable'],'-file',(work/'stage.tcl').as_posix(),'-work_dir',work.as_posix(),'-project_name',prep.TARGET],
        'HardwareAccessed':False,'BitstreamRequested':False,'TimingAccepted':False,'HardwareReleaseAllowed':False,
        'FinalSTAExecuted':False,'DataTimingWaiverAllowed':False,'DiagnosticCopyOnly':True}
    return value,tcl,watched


def prepare(request,work,maximum=300):
    value,tcl,watched=recipe(request,work,maximum);work=Path(value['WorkDirectory'])
    require(not work.exists(),'fresh route/reset stage required');work.mkdir()
    shutil.copyfile(value['SourceADF'],work/'input.adf');shutil.copyfile(SELF,work/'executor-snapshot.py')
    if value['ResetFDC']:shutil.copyfile(value['ResetFDC']['Path'],work/'applied-scope.fdc')
    (work/'stage.tcl').write_text(tcl,encoding='ascii',newline='\n')
    (work/'dummy.v').write_text(physical.DUMMY,encoding='ascii',newline='\n')
    value['PreparedUTC']=prep.utc();inspect.diagnostic.write(work/'stage-plan.json',value)
    validate_prepared(work/'stage-plan.json');return work/'stage-plan.json'


def bound_plan(path,fresh):
    path=inspect.canonical(path,prep.WORK);work=prep.work_path(path.parent);value=read(path)
    require(path.name=='stage-plan.json' and value.get('Schema')==SCHEMA,'exact upright route/reset stage plan required')
    expected,tcl,watched=recipe(value['Request']['Path'],work,value['MaximumSeconds'])
    require(set(value)==set(expected)|{'PreparedUTC'} and {k:v for k,v in value.items() if k!='PreparedUTC'}==expected,
            'route/reset plan differs from derived exact recipe')
    files={'stage-plan.json','stage.tcl','dummy.v','input.adf','executor-snapshot.py'}
    if value['ResetFDC']:files.add('applied-scope.fdc')
    if fresh:require({p.name for p in work.iterdir()}==files,'prepared route stage contaminated/reused')
    require((work/'stage.tcl').read_bytes()==tcl.encode('ascii') and (work/'dummy.v').read_bytes()==physical.DUMMY.encode('ascii')
            and sha(work/'executor-snapshot.py')==sha(SELF),'prepared stage instructions differ')
    if fresh:require(sha(work/'input.adf')==value['SourceADFSHA256'],'input clone differs')
    if value['ResetFDC']:require(sha(work/'applied-scope.fdc')==value['ResetFDC']['SHA256'],'applied reset FDC differs')
    for name in files-{'input.adf'}:physical.add(watched,work/name)
    require(not inspect.drift(watched),'route/reset stage input drift')
    return value,watched


def validate_prepared(path):return bound_plan(path,True)


def execution_ok(value):
    return physical.execution_ok(value) and value.get('Schema')==SCHEMA


def bind_completed(path,watched):
    path=inspect.canonical(path,prep.WORK);value=read(path);work=path.parent
    require(path.name=='result.json' and value.get('ExecutionPassed') is True and execution_ok(value),'clean route/reset receipt required')
    plan,inputs=bound_plan(work/'stage-plan.json',False);watched.update(inputs)
    require(all(value.get(k)==v for k,v in plan.items()) and value['StagePlanSHA256']==sha(work/'stage-plan.json'),
            'route/reset receipt plan identity differs')
    physical.add(watched,path)
    for name,h in value['Artifacts'].items():physical.add(watched,inspect.canonical(work/name,work),h)
    require(sha(work/'input.adf')==sha(work/'saved-reset.adf')==value['ResultADFSHA256']
            and sha(work/'post-init.adf')==value['SourceADFSHA256'],'route/reset saved copy chain differs')
    if value['NativeQueries']:
        require(physical.audit.exact_queries(value['NativeQueries'],work/'stdout.log')==value['ApplicationNativeNameProof'],
                'actual reset application pin identities differ')
    require(not inspect.drift(watched),'completed route/reset input drift')
    return value


def execute(path):
    value,watched=validate_prepared(path);work=Path(value['WorkDirectory']);require(os.name=='nt','Windows native stage required')
    result={**value,'StagePlanSHA256':sha(path),'StartedUTC':prep.utc(),'EDAExecuted':False,'ExecutionPassed':False,
        'TimedOut':False,'StoppedForUnexpectedStage':False,'ExitCode':None}
    inspect.diagnostic.write(work/'execution-start.json',result);process=None;started=time.monotonic()
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
                if inspect.diagnostic.stage_events((work/'stdout.log').read_text(encoding='gb18030',errors='replace')):
                    result['StoppedForUnexpectedStage']=True;break
    except BaseException as error:result['Error']=type(error).__name__+': '+str(error)
    finally:
        if process is not None:
            if process.poll() is None:result['Cleanup']=inspect.diagnostic.cleanup.stop_owned_tree(process,work,'bounded upright route/reset')
            else:result['Cleanup']={'Complete':True,'OwnedPID':process.pid,'ParentExited':True,'DescendantLivenessIndependentlyVerified':False}
            result['ExitCode']=process.poll()
        else:result['Cleanup']={'Complete':True,'Required':False}
    try:
        log=(work/'stdout.log').read_text(encoding='gb18030',errors='replace') if (work/'stdout.log').exists() else ''
        diagnostics=[]
        for p in work.rglob('*.log'):
            diagnostics += [p.relative_to(work).as_posix()+': '+s.strip() for s in re.findall(
                r'(?m)^\s*(?:E:|F:|ERROR:|FATAL:|Traceback).*$',p.read_text(encoding='gb18030',errors='replace'))]
        names=physical.audit.exact_queries(value['NativeQueries'],work/'stdout.log') if value['NativeQueries'] else []
        adfs={n:{'Path':str(work/n),'SHA256':sha(work/n),'Bytes':(work/n).stat().st_size}
              for n in ('input.adf','post-init.adf','saved-reset.adf') if (work/n).is_file()}
        final=adfs.get('input.adf',{}).get('SHA256')
        result.update(ActualEvents=inspect.diagnostic.stage_events(log),InputDrift=inspect.drift(watched),Diagnostics=diagnostics,
            CompletionMarker=MARKER in log,ADFReadback=adfs,ResultADF=adfs.get('input.adf'),ResultADFSHA256=final,
            ApplicationNativeNamesVerified=True,ApplicationNativeNameProof=names,
            InitializationPreservedADF=adfs.get('post-init.adf',{}).get('SHA256')==value['SourceADFSHA256'],
            SavedADFReadbackMatches=bool(final) and adfs.get('saved-reset.adf',{}).get('SHA256')==final,
            ResultADFChanged=bool(final) and final!=value['SourceADFSHA256'],
            Artifacts={p.relative_to(work).as_posix():sha(p) for p in work.rglob('*') if p.is_file()
                       and p.suffix in ('.tcl','.log','.rtr','.txt','.v','.fdc','.adf','.py','.json')})
    except Exception as error:result['Error']=type(error).__name__+': '+str(error)
    # Preserve partial failure evidence even if pin parsing/readback failed.
    result.setdefault('InputDrift',inspect.drift(watched))
    result.setdefault('Artifacts',{p.relative_to(work).as_posix():sha(p) for p in work.rglob('*') if p.is_file()
        and p.suffix in ('.tcl','.log','.rtr','.txt','.v','.fdc','.adf','.py','.json')})
    result.update(FinishedUTC=prep.utc(),ElapsedSeconds=round(time.monotonic()-started,3))
    result['ExecutionPassed']=execution_ok(result);inspect.diagnostic.write(work/'result.json',result);return result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--request',type=Path);p.add_argument('--name')
    p.add_argument('--stage-plan',type=Path);p.add_argument('--maximum-seconds',type=int,default=300)
    modes=p.add_mutually_exclusive_group();modes.add_argument('--prepare-only',action='store_true');modes.add_argument('--execute',action='store_true');modes.add_argument('--validate-only',action='store_true')
    a=p.parse_args()
    if a.stage_plan:
        require(not a.request and not a.name and not a.prepare_only,'stage-plan mode accepts no preparation arguments')
        if a.execute:r=execute(a.stage_plan)
        else:validate_prepared(a.stage_plan);r={'Validated':True,'EDAExecuted':False}
    else:
        require(a.request and a.name and not a.execute,'request/name only prepare or validate; execute exact stage-plan')
        if a.prepare_only:r={'Prepared':True,'StagePlan':str(prepare(a.request,prep.WORK/a.name,a.maximum_seconds)),'EDAExecuted':False}
        else:recipe(a.request,prep.WORK/a.name,a.maximum_seconds);r={'Validated':True,'EDAExecuted':False}
    print(json.dumps({k:r[k] for k in ('Prepared','Validated','StagePlan','ExecutionPassed','ExitCode','ResultADFSHA256','ElapsedSeconds','Diagnostics') if k in r}))
    return 0 if r.get('ExecutionPassed',True) else 1


if __name__=='__main__':raise SystemExit(main())
