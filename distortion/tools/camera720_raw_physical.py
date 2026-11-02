"""Prepare/apply exactly two measured raw720 terminal-branch detours on a copy.

Route-only: no reset exception, full PnR, bitstream or hardware operation.
One pre-edit STA initialization must preserve the original ADF. A successful
save remains diagnostic and needs fresh-process STA, netlist and route audit.
"""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time

import camera720_raw_inspect as inspect
import camera720_raw_reset as reset
import run_raw_camera_delay_route_reset as route_helpers
import audit_raw_camera_routes as routes
import audit_camera720_hold as hold

prep=inspect.prep
require,sha=inspect.require,inspect.sha
SELF=Path(__file__).resolve()
REQUEST_SCHEMA='camera720-current-raw-route-request-v1'
SCHEMA='camera720-current-raw-route-application-v1'
MARKER='CAMERA720_CURRENT_RAW_ROUTE_SAVED'
INIT=inspect.INIT
DUMMY='module physical_dummy(input a, output y); assign y=a; endmodule\n'
ORIGINAL_ADF='799296ded7e2fd66969d4cfdf25a9a30e316c2d8ac9c520b659cb83576f8fed7'
ARTIFACT_SUFFIXES={'.tcl','.log','.rtr','.txt','.v','.fdc','.adf','.py','.json'}


def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def add(watched,path,expected=None):
    path=Path(path).absolute()
    wire=Path(routes.common.WIRE_DEFAULT).resolve()
    require(path == path.resolve() and path.is_file() and
            (path.is_relative_to(prep.PROJECT) or path == wire or path in watched),
            'canonical project input or already bound exact external file required')
    digest=sha(path)
    require(expected is None or (isinstance(expected,str) and re.fullmatch('[0-9a-f]{64}',expected) and digest == expected),
            'input SHA differs: '+str(path))
    require(path not in watched or watched[path] == digest,'conflicting input identity')
    watched[path]=digest
    return path


def binding(ref,watched):
    require(isinstance(ref,dict) and set(ref) == {'Path','SHA256'},'exact Path/SHA256 reference required')
    return add(watched,ref['Path'],ref['SHA256'])


def bind_inspection(ref,mode,build,source,watched):
    path=binding(ref,watched)
    value,inputs=inspect.bind_receipt(path);watched.update(inputs)
    require(value['Mode'] == mode and value['BuildPlan'] == str(build)
            and value['SourceADF'] == str(source) and value['SourceADFSHA256'] == ORIGINAL_ADF,
            'inspection belongs to another raw candidate')
    return value,path


def report_identity(path):
    with Path(path).open(encoding='utf-8-sig') as stream:
        header=''.join(next(stream) for _ in range(12))
    require(re.findall(r'(?m)^\| Design\s*:\s*(\S+)\s*$',header) == [prep.TARGET],
            'exact current raw native report required')


def exact_report_fields(text,source,launch,endpoint):
    headers=re.findall(r'(?m)^\| Tcl Command\s*:\s*(.+)$',text)
    require(len(headers)==1 and headers[0].startswith('report_path_timing '),'one native targeted header required')
    for option,expected in (('from',source),('through',launch),('to',endpoint)):
        found=re.findall(r'-'+option+r'\s+\{([^{}]*)\}',headers[0])
        require(len(found)==1 and found[0].split()==['t:'+expected],'native target selector differs: '+option)


def validate_existing_exception(value,fdc_lines):
    exceptions=value.get('TimingExceptions',[])
    indexes=value.get('ExceptionConstraintLines',[])
    if not exceptions:
        require(indexes==[],'unexpected exception line without exception')
        return
    require(exceptions==['MultiCycle Path Setup -end 2'] and len(indexes)==1
            and type(indexes[0]) is int and 1<=indexes[0]<=len(fdc_lines),
            'only the original exact vendor multicycle data relationship is permitted')
    expected='set_multicycle_path 2 -from [get_clocks '+value['LaunchClock']+'] -to [get_clocks '+value['CaptureClock']+']'
    require(value['LaunchClock']=='ddrphy_sysclk' and value['CaptureClock'] in ('phy_dq_sysclk_0','phy_dq_sysclk_1')
            and fdc_lines[indexes[0]-1].strip()==expected,'native exception differs from original bound FDC line')


def validate_measured_cases(record,reports,exact_root,fdc_lines):
    require(record.get('Schema') == 'camera720-current-raw-hold-analysis-v1' and record.get('Target') == prep.TARGET
            and record.get('ExtractionComplete') is True and record.get('HoldFailingPathCount') == 2
            and record.get('MissingExactSetup') == [] and record.get('MissingExactHold') == []
            and record.get('AllExactDualCornerSetupAndHoldFound') is True,'complete current two-branch hold evidence required')
    for flag in ('HardwareAccessed','RawCandidateProgrammed','TimingClosed','HardwareReleaseAllowed'):
        require(record.get(flag) is False,'hold evidence exceeds diagnostic scope')
    measured=record.get('Paths')
    require(isinstance(measured,list) and len(measured)==2,'exact two measured paths required')
    identities={hold.common.identity(row) for row in measured}
    require(len(identities)==2,'duplicate measured path')
    actual={}
    for report in reports:
        report_identity(report)
        selected,tables,_=hold.common.read_report(report,identities)
        if report == reports[0]:
            require({hold.common.identity(p) for p in selected if p['Kind']=='hold' and p['SlackNS']<0}==identities,
                    'measured paths are not exactly the current hold failures')
            for table in tables:
                if table['Kind']=='hold' and table['FailingChecks']:
                    seen_failures={hold.common.identity(p) for p in selected if p['Kind']=='hold' and p['SlackNS']<0
                        and (p['Corner'],p['LaunchClock'],p['CaptureClock'])==(table['Corner'],table['LaunchClock'],table['CaptureClock'])}
                    require(len(seen_failures)==table['FailingChecks'],'current hold detail coverage differs from native summary')
        for path in selected:
            detailed=hold.detailed(path);detailed.pop('_Text')
            actual[(str(report),detailed['ReportLine'],detailed['PathSHA256'])]=detailed
    targets=[]
    for row in measured:
        cases=row['Cases'];seen=set();launches=set();kinds=set()
        require(cases,'measured path has no cases')
        for case in cases:
            key=(case['Report'],case['ReportLine'],case['PathSHA256'])
            require(key in actual and key not in seen,'case missing from actual report or repeated')
            seen.add(key);value=actual[key]
            require(all(case.get(k)==v for k,v in value.items()),'claimed timing path differs from native bytes')
            require(hold.common.identity(value)==hold.common.identity(row),'measured path identity differs')
            if not row['Source'].endswith(' (port)'):
                launch=value['DataTrace'][0]['LogicalResource']
                require(value['DataTrace'][0].get('DelayType') == 'tco','actual launch tco missing')
                launches.add(launch)
                if Path(value['Report']).is_relative_to(exact_root/'report_path_timing'):
                    exact_report_fields(Path(value['Report']).read_text(encoding='utf-8-sig'),row['Source'],launch,row['Endpoint'])
                    kinds.add((launch,value['Corner'],value['Kind']))
                validate_existing_exception(value,fdc_lines)
        for corner in ('slow','fast'):
            for kind in ('setup','hold'):
                values=[c['SlackNS'] for c in cases if c['Corner']==corner and c['Kind']==kind]
                require(values,'missing exact corner/kind')
                margin=row['Margins'][corner]
                require(margin['Exact'+kind.title()+'Found'] is True
                        and margin['Exact'+kind.title()+'SlackNS']==min(values),'exact margin differs')
                if kind=='setup':require(min(values)>0,'route detour lacks positive exact setup')
        if not row['Source'].endswith(' (port)'):
            expected={row['Source'].rsplit('/',1)[0]+'/'+q for q in ('L5Q','L6Q')}
            require(launches==expected and kinds=={(q,c,k) for q in expected for c in ('slow','fast') for k in ('setup','hold')},
                    'both actual packed launch outputs need targeted dual-corner setup and hold')
        target={**row['PhysicalRepairCandidate'],'Endpoint':row['Endpoint']}
        terminal={(c['DataTrace'][-2]['Name'],c['DataTrace'][-2]['FromRoutePin'],c['DataTrace'][-2]['ToRoutePin'],c['DataTrace'][-2]['Fanout']) for c in cases}
        require(terminal=={(target['Net'],target['FromRoutePin'],target['ToRoutePin'],target['Fanout'])},'terminal branch differs')
        require(target['BranchOnly'] is True and target['PreserveOtherBranches'] is True
                and target['TimingWaiverAllowed'] is False and target['ExternalInputBudgetChanged'] is False,
                'measured repair exceeds terminal branch scope')
        targets.append(target)
    return targets


def validate_request_shape(value):
    fields={'Schema','Target','BuildPlan','SourceADF','BuildDiagnosticsReview','HoldAudit','ExactTimingReceipt',
            'DiscoveryReceipt','RouteDump','WaypointEvidence','Routes','ResetProof'}
    require(set(value)==fields and value['Schema']==REQUEST_SCHEMA and value['Target']==prep.TARGET,
            'exact current raw route-only request required')
    require(value['ResetProof'] is None,'route-only producer does not authorize reset exceptions')
    require(value['SourceADF']['SHA256']==ORIGINAL_ADF,'only the original reviewed raw ADF can be copied')


def validate_waypoints(evidence,rows,targets,parsed):
    require(evidence.get('Schema')=='camera720-current-raw-route-candidates-v1'
            and evidence.get('Target')==prep.TARGET,'exact raw waypoint evidence required')
    # Explicit data adapter; no modification of frozen helper module globals.
    projected={'Schema':'raw-camera-waypoint-selection-v1','WirePattern':evidence['WirePattern'],
               'Selections':evidence['Selections']}
    route_helpers.validate_waypoint_evidence(projected,rows,targets,parsed)
    require(evidence['BranchInventory']==parsed['BranchInventory']
            and evidence['NonRouteSemanticSHA256']==parsed['NonRouteSemanticSHA256']
            and evidence['ExcludedBlockSHA256']==parsed['ExcludedBlockSHA256'],
            'candidate route/placement/constraint snapshot differs')


def bind_request(request_path):
    watched={};request_path=add(watched,request_path);r=read(request_path);validate_request_shape(r)
    build=binding(r['BuildPlan'],watched);source=binding(r['SourceADF'],watched)
    review=binding(r['BuildDiagnosticsReview'],watched)
    plan,base=inspect.bind(build,source,ORIGINAL_ADF,review,r['BuildDiagnosticsReview']['SHA256']);watched.update(base)
    hp=binding(r['HoldAudit'],watched);record=read(hp)
    for name,digest in record.get('InputSHA256',{}).items():add(watched,name,digest)
    exact,exact_path=bind_inspection(r['ExactTimingReceipt'],'query',build,source,watched)
    require(record.get('ExactSetupReceipt')==r['ExactTimingReceipt'] and record.get('SourceADF')==r['SourceADF'],
            'hold exact native receipt/source binding differs')
    discovery,dp=bind_inspection(r['DiscoveryReceipt'],'query',build,source,watched)
    report_refs=record.get('InputReports',[])
    require(isinstance(report_refs,list) and report_refs,'hold input reports missing')
    reports=[]
    for ref in report_refs:
        report=add(watched,ref['Path'],ref['SHA256']);reports.append(report)
        if report!=build.parent/'report_timing'/(prep.TARGET+'.rtr'):
            require(report.is_relative_to(exact_path.parent) and exact['Artifacts'].get(report.relative_to(exact_path.parent).as_posix())==sha(report),
                    'extra timing report not bound to exact native receipt')
    require(reports[0]==build.parent/'report_timing'/(prep.TARGET+'.rtr'),'first hold report must be the unchanged source build report')
    targets=validate_measured_cases(record,reports,exact_path.parent,Path(plan['Constraints']['FDC']).read_text().splitlines())
    dump=binding(r['RouteDump'],watched)
    require(dump.is_relative_to(dp.parent) and discovery['Artifacts'].get(dump.relative_to(dp.parent).as_posix())==sha(dump),
            'source route is not bound to discovery receipt')
    parsed=routes.inspect(dump,targets)
    commands=route_helpers.route_commands(r['Routes'],targets,parsed['_Occupied'])
    ep=binding(r['WaypointEvidence'],watched);evidence=read(ep)
    require(evidence['HoldAudit']==r['HoldAudit'] and evidence['RouteDump']==r['RouteDump']
            and evidence['DiscoveryReceipt']==r['DiscoveryReceipt'] and evidence['SourceADF']==r['SourceADF'],
            'waypoint evidence belongs to another candidate')
    for name,digest in evidence.get('InputSHA256',{}).items():add(watched,name,digest)
    add(watched,evidence['WirePattern']['Path'],evidence['WirePattern']['SHA256'])
    validate_waypoints(evidence,r['Routes'],targets,parsed)
    for module in (route_helpers,route_helpers.physical,route_helpers.hold,hold,hold.common,routes,routes.common):
        add(watched,module.__file__)
    reset.watch_tools(watched);add(watched,SELF)
    require(not inspect.drift(watched),'raw physical evidence drift')
    return r,plan,source,targets,commands,watched


def render(commands,work):
    w=work.as_posix()
    return ('set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG676\n'
            'add_design {'+w+'/dummy.v}\nif {[info script] ne {}} {\n    mpnr -input {'+w+'/input.adf}\n'
            '    '+INIT+'\n    file copy {'+w+'/input.adf} {'+w+'/post-init.adf}\n'
            +'\n'.join(commands)+'\n    save_adif\n'
            '    file copy {'+w+'/input.adf} {'+w+'/saved-route.adf}\n'
            '    .switch_db -route -input {'+w+'/input.adf} -output {'+w+'/route-dump.txt}\n'
            '    puts {'+MARKER+'}\n    flush stdout\n}\n')


def recipe(request,work,maximum=300):
    work=prep.work_path(work);require(type(maximum)is int and 120<=maximum<=300,'bound must be120..300 seconds')
    r,build,source,targets,commands,watched=bind_request(request)
    tcl=render(commands,work)
    value={'Schema':SCHEMA,'Target':prep.TARGET,'Mode':'save-route-only','WorkDirectory':str(work),
        'Request':{'Path':str(Path(request).absolute()),'SHA256':sha(request)},
        'BuildPlan':r['BuildPlan']['Path'],'BuildPlanSHA256':r['BuildPlan']['SHA256'],
        'SourceADF':str(source),'SourceADFSHA256':ORIGINAL_ADF,'BuildDiagnosticsReview':r['BuildDiagnosticsReview'],
        'BuildExecutionCompletedWithoutError':False,'BuildDiagnosticsCleared':False,
        'OriginalRouteDump':r['RouteDump'],'Routes':r['Routes'],'MeasuredTargets':targets,
        'ExactRouteCommands':commands,'ExactResetCommands':[],'ResetProof':None,
        'MaximumSeconds':maximum,'ExpectedActualStages':[],
        'InputSHA256':{str(p):h for p,h in watched.items()},'TclSHA256':prep.baseline.paths.sha_bytes(tcl.encode('ascii')),
        'Command':[build['PDS']['Executable'],'-file',(work/'stage.tcl').as_posix(),'-work_dir',work.as_posix(),'-project_name',prep.TARGET],
        'HardwareAccessed':False,'BitstreamRequested':False,'TimingAccepted':False,'HardwareReleaseAllowed':False,
        'FinalSTAExecuted':False,'DataTimingWaiverAllowed':False,'ConstraintsApplied':False,'DiagnosticCopyOnly':True}
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
    if fresh:require(sha(work/'input.adf')==ORIGINAL_ADF,'physical input copy differs')
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
        and value.get('ResultADFChanged') is True and value.get('Cleanup',{}).get('Complete') is True)


def bind_completed(path,watched):
    path=inspect.canonical(path,prep.WORK);work=path.parent;value=read(path)
    require(path.name=='result.json' and value.get('ExecutionPassed') is True and execution_ok(value),'clean current raw route save required')
    plan,bound=bound_plan(work/'stage-plan.json',False);watched.update(bound)
    require(all(value.get(k)==v for k,v in plan.items()) and value['StagePlanSHA256']==sha(work/'stage-plan.json'),
            'physical receipt differs from exact plan')
    require(value['Artifacts']==artifact_hashes(work),'physical artifact inventory/bytes differ')
    for name,digest in value['Artifacts'].items():add(watched,inspect.canonical(work/name,work),digest)
    require(inspect.scan_diagnostics(work)==[],'physical critical/error diagnostics present')
    log=(work/'stdout.log').read_text(encoding='gb18030',errors='replace')
    require(inspect.diagnostic.stage_events(log)==[] and MARKER in log,'physical stage events/marker differ')
    require(sha(work/'post-init.adf')==ORIGINAL_ADF and sha(work/'input.adf')==sha(work/'saved-route.adf')==value['ResultADFSHA256']
            and value['ResultADFSHA256']!=ORIGINAL_ADF,
            'physical ADF initialization/save chain differs')
    for name in ('input.adf','post-init.adf','saved-route.adf'):
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
            result['Cleanup']=(inspect.diagnostic.cleanup.stop_owned_tree(process,work,'bounded raw route-only') if process.poll() is None
                               else {'Complete':True,'OwnedPID':process.pid,'ParentExited':True,'DescendantLivenessIndependentlyVerified':False})
            result['ExitCode']=process.poll()
        else:result['Cleanup']={'Complete':True,'Required':False}
    try:
        log=(work/'stdout.log').read_text(encoding='gb18030',errors='replace') if (work/'stdout.log').exists() else ''
        adfs={n:{'Path':str(work/n),'SHA256':sha(work/n),'Bytes':(work/n).stat().st_size}
              for n in ('input.adf','post-init.adf','saved-route.adf') if (work/n).is_file()}
        final=adfs.get('input.adf',{}).get('SHA256')
        result.update(ActualEvents=inspect.diagnostic.stage_events(log),InputDrift=inspect.drift(watched),
            Diagnostics=inspect.scan_diagnostics(work),CompletionMarker=MARKER in log,ADFReadback=adfs,
            ResultADF=adfs.get('input.adf'),ResultADFSHA256=final,
            InitializationPreservedADF=adfs.get('post-init.adf',{}).get('SHA256')==ORIGINAL_ADF,
            SavedADFReadbackMatches=bool(final) and adfs.get('saved-route.adf',{}).get('SHA256')==final,
            ResultADFChanged=bool(final) and final!=ORIGINAL_ADF,Artifacts=artifact_hashes(work))
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
