"""Apply only the measured calibrated720 hold branch on an isolated ADF copy.

No reset exception or new placement. Exact dual-corner setup/hold and current
route occupancy are independently reconstructed before any command is emitted.
Saved route execution is not full timing or hardware/optical acceptance.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time

import camera720_calibrated_inspect as inspect
import run_raw_camera_delay_route_reset as route_helpers
import audit_raw_camera_routes as routes
import audit_camera720_hold as hold

prep=inspect.prep
require,sha=inspect.require,inspect.sha
SELF=Path(__file__).resolve()
REQUEST_SCHEMA='camera720-calibrated-hold-route-request-v1'
SCHEMA='camera720-calibrated-hold-route-application-v1'
MARKER='CAMERA720_CALIBRATED_HOLD_ROUTE_SAVED'
INIT=inspect.INIT
DUMMY='module physical_dummy(input a, output y); assign y=a; endmodule\n'
ORIGINAL_ADF='71bea98abdbc80cdf2a9af86f60e76e9b49dd4c52d1c62b08f10cf5ce8b9d66a'
ARTIFACT_SUFFIXES={'.tcl','.log','.rtr','.txt','.v','.fdc','.adf','.py','.json'}
SERIALIZER=prep.PROJECT/'work/camera720-raw/compare-route-serialization-diagnostic.py'

def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))

def add(watched,path,expected=None):
    path=Path(path).absolute()
    wire=Path(routes.common.WIRE_DEFAULT).resolve()
    require(path==path.resolve() and path.is_file() and
            (path.is_relative_to(prep.PROJECT) or path==wire or path in watched),
            'canonical project or bound exact external file required')
    digest=sha(path)
    require(expected is None or isinstance(expected,str) and re.fullmatch('[0-9a-f]{64}',expected) and digest==expected,
            'input SHA differs: '+str(path))
    require(path not in watched or watched[path]==digest,'conflicting input identity')
    watched[path]=digest
    return path

def binding(ref,watched):
    require(isinstance(ref,dict) and set(ref)=={'Path','SHA256'},'exact Path/SHA256 reference required')
    return add(watched,ref['Path'],ref['SHA256'])

def report_identity(path):
    with Path(path).open(encoding='utf-8-sig') as stream:head=''.join(stream.readline() for _ in range(16))
    require(re.findall(r'(?m)^\| Design\s*:\s*(\S+)\s*$',head)==[prep.TARGET],
            'current calibrated native report required')

def ref(path):
    return {'Path':str(Path(path).resolve()),'SHA256':sha(path)}


def measured_target(record, full_report, reports):
    require(record.get('Schema')=='camera720-calibrated-exact-hold-analysis-v1'
            and record.get('Target')==prep.TARGET and record.get('ExtractionComplete') is True
            and record.get('HoldFailingPathCount')==1 and record.get('MissingExactSetup')==[],
            'one complete current calibrated hold relationship required')
    require(record.get('TimingClosed') is False and record.get('HardwareAccessed') is False,
            'hold analysis cannot claim timing or hardware')
    report_identity(full_report)
    negative,tables,_=hold.common.read_report(full_report)
    failures={hold.common.identity(p) for p in negative if p['Kind']=='hold' and p['SlackNS']<0}
    require(len(failures)==1 and len(record.get('Paths',[]))==1,'only one measured native hold relationship allowed')
    for table in tables:
        if table['Kind']=='hold' and table['FailingChecks']:
            keys={hold.common.identity(p) for p in negative if p['Kind']=='hold' and p['SlackNS']<0
                  and (p['Corner'],p['LaunchClock'],p['CaptureClock'])==
                      (table['Corner'],table['LaunchClock'],table['CaptureClock'])}
            require(len(keys)==table['FailingChecks'],'full native hold detail/summary coverage differs')
    row=record['Paths'][0]
    require(tuple(row[k] for k in ('Source','Endpoint','LaunchClock','CaptureClock'))==next(iter(failures))[:4]
            and {hold.common.identity(case) for case in row['Cases']}==failures,
            'hold record is not the current native failure')
    actual=[]
    for report in reports:
        report_identity(report)
        paths,_,_=hold.common.read_report(report,failures)
        actual.extend(hold.detailed(p) for p in paths)
    actual_clean=[{k:v for k,v in p.items() if k!='_Text'} for p in actual]
    saved=[{k:v for k,v in p.items() if k!='Excerpt'} for p in row['Cases']]
    require(saved==actual_clean,'hold/setup path records differ from native report bytes')
    require(len(actual)==4 and {(p['Corner'],p['Kind']) for p in actual}==
            {(c,k) for c in ('slow','fast') for k in ('setup','hold')},
            'exact single launch dual-corner setup and hold required')
    terminals={(p['DataTrace'][-2]['Name'],p['DataTrace'][-2]['FromRoutePin'],
                p['DataTrace'][-2]['ToRoutePin'],p['DataTrace'][-2]['Fanout']) for p in actual}
    require(len(terminals)==1,'terminal branch differs between measured checks')
    for p in actual:
        require(p['TimingExceptions']==[] and p['ExceptionConstraintLines']==[],
                'this measured DDR return relationship carries no timing exception')
        require(p['DataTrace'][0]['DelayType']=='tco' and p['DataTrace'][0]['LogicalResource'].rsplit('/',1)[0]
                ==p['Source'].rsplit('/',1)[0], 'actual launch tco does not belong to selected clock instance')
    require(all(p['SlackNS']>0 for p in actual if p['Kind']=='setup'),'actual setup margin must be positive')
    net,source_pin,target_pin,fanout=next(iter(terminals))
    target={**row['PhysicalRepairCandidate'],'Endpoint':row['Endpoint']}
    require((target['Net'],target['FromRoutePin'],target['ToRoutePin'],target['Fanout'])==
            (net,source_pin,target_pin,fanout) and fanout==1 and target['TimingWaiverAllowed'] is False,
            'only measured single-load terminal branch may change')
    for corner in ('slow','fast'):
        margins=row['Margins'][corner]
        require(margins['ExactSetupFound'] is True and margins['ExactSetupSlackNS']==
                next(p['SlackNS'] for p in actual if p['Corner']==corner and p['Kind']=='setup')
                and margins['HoldSlackNS']==next(p['SlackNS'] for p in actual if p['Corner']==corner and p['Kind']=='hold'),
                'reported setup/hold margin differs')
    for report in reports:
        with report.open(encoding='utf-8-sig') as stream:head=''.join(stream.readline() for _ in range(16))
        command=re.findall(r'(?m)^\| Tcl Command\s*:\s*(.+)$',head)
        require(len(command)==1 and command[0].startswith('report_path_timing '),'exact targeted native command required')
        for option,name in (('from',row['Source']),('through',actual[0]['DataTrace'][0]['LogicalResource']),('to',row['Endpoint'])):
            found=re.findall('-'+option+r'\s+\{([^{}]*)\}',command[0])
            require(len(found)==1 and found[0].split()==['t:'+name],'native selector differs: '+option)
    return [target]


def validate_request_shape(r):
    fields={'Schema','Target','DiscoveryReceipt','ExportReceipt','HoldAudit','WaypointEvidence','Routes'}
    require(set(r)==fields and r['Schema']==REQUEST_SCHEMA and r['Target']==prep.TARGET,
            'exact calibrated hold-only request required')


def bind_request(request_path):
    watched={};request_path=add(watched,request_path);r=read(request_path);validate_request_shape(r)
    discovery_path=binding(r['DiscoveryReceipt'],watched)
    discovery,bound=inspect.bind_receipt(discovery_path);watched.update(bound)
    export_path=binding(r['ExportReceipt'],watched)
    export,bound=inspect.bind_receipt(export_path);watched.update(bound)
    require(discovery['Mode']=='query' and export['Mode']=='export' and export['NativeNetlistWithFFloc'] is True,
            'actual native query and placed export required')
    for field in ('Target','BuildPlan','BuildPlanSHA256','SourceADF','SourceADFSHA256','BuildDiagnosticsReview'):
        require(discovery[field]==export[field],'query/export belong to different candidates')
    require(discovery['SourceADFSHA256']==ORIGINAL_ADF,'only the current original routed candidate is eligible')
    build_path=Path(discovery['BuildPlan']);build=read(build_path);source=Path(discovery['SourceADF'])
    hp=binding(r['HoldAudit'],watched);record=read(hp)
    require(record['SourceADF']==ref(source) and record['NativeDiscoveryReceipt']==r['DiscoveryReceipt'],
            'measured timing audit belongs to another candidate')
    reports=[]
    for item in record['InputReports']:
        path=add(watched,item['Path'],item['SHA256'])
        require(path.is_relative_to(discovery_path.parent) and
                discovery['Artifacts'].get(path.relative_to(discovery_path.parent).as_posix())==sha(path),
                'targeted report not bound to actual query receipt')
        reports.append(path)
    full_report=Path(discovery['TimingReport']['Path'])
    add(watched,full_report,discovery['TimingReport']['SHA256'])
    targets=measured_target(record,full_report,reports)
    dump=add(watched,discovery_path.parent/'route-dump.txt')
    require(discovery['Artifacts'].get('route-dump.txt')==sha(dump),'current full route dump is unbound')
    parsed=routes.inspect(dump,targets)
    commands=route_helpers.route_commands(r['Routes'],targets,parsed['_Occupied'])
    ep=binding(r['WaypointEvidence'],watched);e=read(ep)
    require(e.get('Schema')=='camera720-calibrated-waypoint-selection-v1' and e.get('Target')==prep.TARGET
            and e['DiscoveryReceipt']==r['DiscoveryReceipt'] and e['ExportReceipt']==r['ExportReceipt']
            and e['HoldAudit']==r['HoldAudit'] and e['SourceADF']==ref(source) and e['RouteDump']==ref(dump),
            'waypoint provenance differs')
    route_helpers.validate_waypoint_evidence({'Schema':'raw-camera-waypoint-selection-v1',
        'WirePattern':e['WirePattern'],'Selections':e['Selections']},r['Routes'],targets,parsed)
    require(e['BranchInventory']==parsed['BranchInventory'] and e['NonRouteSemanticSHA256']==parsed['NonRouteSemanticSHA256']
            and e['ExcludedBlockSHA256']==parsed['ExcludedBlockSHA256'],'waypoint inventory differs from full native route')
    binding(e['WirePattern'],watched)
    for mod in (route_helpers,route_helpers.physical,route_helpers.hold,hold,hold.common,routes,routes.common):
        add(watched,mod.__file__)
    add(watched,SELF);add(watched,SERIALIZER)
    require(not inspect.drift(watched),'current hold-route evidence drift')
    expanded={**r,'BuildPlan':ref(build_path),'BuildDiagnosticsReview':discovery['BuildDiagnosticsReview'],
              'RouteDump':ref(dump),'SourceADF':ref(source)}
    return expanded,build,source,targets,commands,watched


def serialization_module():
    spec=importlib.util.spec_from_file_location('calibrated_route_serialization',SERIALIZER)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def compare_route_dumps(original,derived,targets,requested):
    """Full tokens plus exact parent-bound CDB entry multisets, never token deletion."""
    before=routes.inspect(Path(original),targets);after=routes.inspect(Path(derived),targets)
    require(set(before['NetAnnotations'])==set(after['NetAnnotations']),'native route inventory changed')
    changed={n for n,h in before['NetAnnotations'].items() if after['NetAnnotations'][n]!=h}
    require({routes.annotation_name(n) for n in changed}=={t['Net'] for t in targets},
            'unrequested route changed or measured route did not change')
    checks=[]
    for t,row in zip(targets,requested):
        old,new=before['BranchInventory'][t['Net']],after['BranchInventory'][t['Net']]
        require(old['LogicalConnections']==new['LogicalConnections'] and set(old['Leaves'])==set(new['Leaves']),
                'logical connectivity or physical leaves changed')
        for leaf,chain in old['Leaves'].items():
            if leaf!=t['ToRoutePin']:
                require(chain==new['Leaves'][leaf],'unrequested sibling branch changed')
        chain=new['Leaves'][t['ToRoutePin']];pins=row['Pins'].rstrip(';').split('>')
        require(chain!=old['Leaves'][t['ToRoutePin']] and any(chain[i:i+len(pins)]==pins for i in range(len(chain)-len(pins)+1)),
                'requested contiguous detour absent')
        checks.append({'Net':t['Net'],'UnrequestedSiblingsPreserved':len(old['Leaves'])-1})
    serializer=serialization_module()
    aa,bb=serializer.extract(Path(original)),serializer.extract(Path(derived))
    refs=serializer.reference_comparison(aa,bb)
    require(refs['DefinitionsEqual'] and refs['ParentObjectsEqual'] and refs['AllFullEntriesEqualWithinParent']
            and refs['AllResolvedEntriesEqualWithinParent'] and refs['OtherNonRouteTokensEqual'],
            'non-route functional/placement or parent-bound constraint semantics changed')
    require(aa['ExcludedBlocks']['CDB']['TokenSHA256']==bb['ExcludedBlocks']['CDB']['TokenSHA256'],
            'constraint database definitions changed')
    require(aa['ExcludedBlocks']['FILETABLE']['TokenSHA256']==bb['ExcludedBlocks']['FILETABLE']['TokenSHA256'],
            'source file table changed beyond supported serialization')
    return {'Passed':True,'ChangedNets':sorted(changed),'ChangedNetCount':len(changed),
            'AllOtherRoutesUnchanged':True,'FunctionalAndPlacementSemanticsUnchanged':True,
            'CDBDefinitionsIdentical':True,'FullCDBEntriesEqualWithinExactParent':True,
            'DefinitionsCompared':refs['DefinitionCountBefore'],'EntriesCompared':refs['EntryCountBefore'],
            'ParentObjectsCompared':len(refs['ParentChecks']),'OtherBranchChecks':checks,
            'StrictNonRouteTokensIdentical':before['NonRouteSemanticSHA256']==after['NonRouteSemanticSHA256'],
            'SourceLocationMetadata':[before['SourceLocationMetadata'],after['SourceLocationMetadata']],
            'SourceAnnotationRecords':[aa['SourceAnnotationsOutsideCDBEntries'],bb['SourceAnnotationsOutsideCDBEntries']],
            'TimingAcceptanceImplied':False}

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
        'OriginalExportReceipt':r['ExportReceipt'],
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
    value['PreparedUTC']=inspect.utc();inspect.diagnostic.write(work/'stage-plan.json',value)
    return work/'stage-plan.json'


def bound_plan(path,fresh):
    path=inspect.canonical(path,prep.WORK);work=prep.work_path(path.parent);value=read(path)
    require(path.name=='stage-plan.json' and value.get('Schema')==SCHEMA,'exact calibrated hold-route stage-plan required')
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
        and value.get('ResultADFChanged') is True and value.get('Cleanup',{}).get('Complete') is True
        and value.get('RouteComparison',{}).get('Passed') is True)


def bind_completed(path,watched):
    path=inspect.canonical(path,prep.WORK);work=path.parent;value=read(path)
    require(path.name=='result.json' and value.get('ExecutionPassed') is True and execution_ok(value),'clean current calibrated hold-route save required')
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
    comparison=compare_route_dumps(value['OriginalRouteDump']['Path'],work/'route-dump.txt',
                                   value['MeasuredTargets'],value['Routes'])
    require(value['RouteComparison']==comparison,'saved route preservation proof differs from actual full dumps')
    add(watched,path);require(not inspect.drift(watched),'physical completed evidence drift')
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
            result['Cleanup']=(inspect.diagnostic.cleanup.stop_owned_tree(process,work,'bounded calibrated hold-route only') if process.poll() is None
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
        require(result['ExitCode']==0 and not result.get('Error') and not result['TimedOut']
                and not result['StoppedForUnexpectedStage'] and result['Diagnostics']==[]
                and result['ActualEvents']==[] and result['CompletionMarker'] and result['InputDrift']==[]
                and result['InitializationPreservedADF'] and result['SavedADFReadbackMatches'] and result['ResultADFChanged'],
                'native route initialization/save failed; preservation cannot be claimed')
        result['RouteComparison']=compare_route_dumps(value['OriginalRouteDump']['Path'],work/'route-dump.txt',
                                                       value['MeasuredTargets'],value['Routes'])
    except Exception as error:result['Error']=type(error).__name__+': '+str(error)
    result.update(FinishedUTC=inspect.utc(),ElapsedSeconds=round(time.monotonic()-started,3))
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
