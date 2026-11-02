"""Apply only current native DDR reset pairs on an isolated view-toggle ADF.

Fresh same-ADF report/export, exact current graph and unchanged vendor DDR
configuration are required. No routing, data waiver, bitstream or board access.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time

import camera720_view_toggle_build as build
import camera720_view_toggle_reset as proof
import camera720_view_toggle_final_inspect as inspect
import audit_camera720_reset as query_parser
import audit_camera_vga_physical as timing
import camera720_stats_delay_reset_apply as route_semantics
import camera720_stats_delay_reset as vendor

SELF = Path(__file__).resolve()
SCHEMA = 'camera720-view-toggle-reset-application-v1'
MARKER = 'CAMERA720_VIEW_TOGGLE_EXACT_RESET_SAVED'
TARGET, require, sha, read = build.TARGET, build.require, build.sha, build.read
add, merge, ref, drift = inspect.add, inspect.merge, inspect.ref, inspect.drift
SUFFIXES = {'.tcl','.log','.rtr','.txt','.v','.fdc','.adf'}
compare_routes = route_semantics.compare_routes


def artifact(receipt_path, value, name, watched):
    matches = [Path(receipt_path).parent/n for n in value['Artifacts']
               if Path(n).name == name and 'report_path_timing' not in Path(n).parts]
    require(len(matches) == 1, 'one bound native artifact required: '+name)
    p = matches[0]
    return add(watched,p,value['Artifacts'][p.relative_to(Path(receipt_path).parent).as_posix()])


def functional(path):
    text = proof.adapt_netlist(Path(path).read_text(encoding='utf-8-sig'))
    # Existing parser accepts one top token; every cell, connection and FF site
    # stays in the actual current candidate namespace.
    import tempfile
    with tempfile.TemporaryDirectory(prefix='view-functional-') as d:
        p = Path(d)/'functional.v'; p.write_text(text,encoding='utf-8',newline='\n')
        return timing.functional(p)


def vendor_basis(build_plan, watched):
    build_plan = Path(build_plan).resolve()
    plan = build.validate(build_plan); work = build_plan.parent
    reference = read(add(watched,vendor.REFERENCE,vendor.REFERENCE_SHA))
    require(reference.get('Status') == 'pass' and reference.get('AllBytesIdentical') is True
            and reference.get('GlobalClockGroupsImported') is False and
            reference.get('ConstraintsApplied') is False, 'vendor same-configuration reference differs')
    prefix = 'platform/video_base/ipcore/ddr3_test/'
    compiled = work/'compiled'
    expected = {Path(n).relative_to(compiled).as_posix()[len(prefix):]
                for n in plan['PreparedSHA256'] if Path(n).is_relative_to(compiled)
                and Path(n).relative_to(compiled).as_posix().startswith(prefix)}
    rows = reference['Files']
    require(len(rows) == len(expected) and {r['RelativePath'] for r in rows} == expected,
            'current compiled DDR closure differs from documented vendor configuration')
    files=[]
    for row in rows:
        rel=Path(row['RelativePath'])
        require(not rel.is_absolute() and '..' not in rel.parts, 'vendor path escapes')
        original=(build.ROOT/prefix/rel).resolve(); supplied=(vendor.VENDOR/rel).resolve()
        actual=(compiled/prefix/rel).resolve()
        require(Path(row['CandidatePath']).resolve()==original and Path(row['VendorPath']).resolve()==supplied,
                'vendor reference ownership differs')
        for p in (original,supplied,actual): add(watched,p,row['SHA256'])
        files.append({'RelativePath':rel.as_posix(),'SHA256':row['SHA256'],'Compiled':str(actual)})
    fdc=reference['VendorFDC']; p=add(watched,fdc['Path'],fdc['SHA256'])
    require(p==(vendor.VENDOR/'pnr/ddr_test.fdc').resolve(), 'vendor constraint ownership differs')
    lines=p.read_text(encoding='utf-8-sig').splitlines(); relationships=[]
    for clock in ('rst_clk','phy_dq_clk_0','phy_dq_clk_1'):
        command='set_clock_groups -name '+clock+' -asynchronous -group [get_clocks {'+clock+'}]'
        matches=[i+1 for i,line in enumerate(lines) if line.strip()==command]
        require(len(matches)==1,'vendor reset/training relationship differs')
        relationships.append({'Line':matches[0],'Text':command})
    add(watched,vendor.MANUAL,vendor.MANUAL_SHA)
    return {'ReferenceInventory':ref(vendor.REFERENCE),'IDFAndExpandedBodyCount':len(files),
        'Files':files,'VendorFDC':fdc,'VendorClockRelationships':relationships,
        'Manual':ref(vendor.MANUAL),'SameConfigurationBytesVerified':True,
        'GlobalClockGroupsImported':False,'VendorEncryptedInternalsProved':False,
        'Contract':'Supplied HMIC_S reset/training operating contract; exact placed reset graph independently checked.',
        'ExternalResetContract':'Asynchronous assertion and rst_clk synchronized release after PLL lock; arbitrary short stopped-clock epochs unproved.'}


def nonreset_checks(tables, inventory):
    require(set(tables)=={(c,k) for c in ('slow','fast') for k in timing.native.KINDS},
            'ten complete native timing tables required')
    excluded={(g['Corner'],g['LaunchClock'],g['CaptureClock']) for g in inventory['Groups']}
    for (corner,kind),rows in tables.items():
        require(rows,'empty native timing table')
        for pair,row in rows.items():
            if kind in ('recovery','removal') and isinstance(pair,tuple) and (corner,*pair) in excluded:
                continue
            require(row['FailingChecks']==0 and row['WorstSlackNS']>=0 and row['TotalNegativeSlackNS']==0,
                    'unresolved non-proposed timing failure: '+str((corner,kind,pair)))


def derive(export_path, route_path, route_application=None):
    export_path,route_path = Path(export_path).resolve(),Path(route_path).resolve()
    export,watched=inspect.bind_receipt(export_path)
    route,inputs=inspect.bind_receipt(route_path);merge(watched,inputs)
    require(export['Mode']=='export' and route['Mode']=='report' and
            export['SourceADF']==route['SourceADF'] and export['SourceADFSHA256']==route['SourceADFSHA256']
            and export['BuildPlan']==route['BuildPlan'] and export['BuildPlanSHA256']==route['BuildPlanSHA256'],
            'fresh reset evidence belongs to different ADF or build')
    source=add(watched,export['SourceADF'],export['SourceADFSHA256'])
    original=Path(export['BuildPlan']).parent/'place_route'/(TARGET+'_pnr.adf')
    route_ref=None
    if source!=original:
        require(route_application is not None,'derived ADF requires exact route application receipt')
        import camera720_view_toggle_route as routing
        applied,bound=routing.bind_completed(route_application);merge(watched,bound)
        require(applied['ResultADF']['Path']==str(source) and applied['ResultADFSHA256']==sha(source)
                and applied['BuildPlan']==export['BuildPlan'], 'route application identifies another ADF')
        route_ref=ref(route_application)
    report=artifact(export_path,export,TARGET+'.rtr',watched)
    netlist=artifact(export_path,export,TARGET+'_sim.v',watched)
    # Route-mode initialization is checked independently against same-ADF export.
    route_report=artifact(route_path,route,TARGET+'.rtr',watched)
    bt,bc=timing.summaries(report);rt,rc=timing.summaries(route_report)
    require(bt==rt and bc==rc,'fresh route/report timing or clocks differ')
    inventory,adapter=proof.report_inventory(report)
    queries,query,fdc,commands=proof.exact_scope(inventory)
    graph=proof.graph.audit_text(proof.adapt_netlist(netlist.read_text(encoding='utf-8-sig')),queries)
    require(graph['Status']=='pass' and graph['FirstStageFunctionalFanout']==1
            and graph['RawClearFunction']=='~(reset_n & power_ready)' and
            graph['InternalFunctionalTargetsVerified']==sum(q['ExpectedTargetCount'] for q in queries if not q['EntryRDC']),
            'current reset graph coverage/entry contract differs')
    nonreset_checks(bt,inventory)
    graph_value=functional(netlist)
    dump=artifact(route_path,route,'route-dump.txt',watched)
    vendor_value=vendor_basis(export['BuildPlan'],watched)
    for module in (proof,proof.scope,proof.graph,proof.graph.syntax,query_parser,timing,timing.native,
                   route_semantics,route_semantics.routes,route_semantics.separated,vendor): add(watched,module.__file__)
    add(watched,SELF)
    facts={'BuildPlan':export['BuildPlan'],'BuildPlanSHA256':export['BuildPlanSHA256'],
        'SourceADF':str(source),'SourceADFSHA256':sha(source),'BaselineExport':ref(export_path),
        'BaselineReport':ref(route_path),'BaselineRouteDump':ref(dump),'BaselineNetlist':ref(netlist),
        'RouteApplication':route_ref,'Inventory':inventory,'ReportAdapter':adapter,
        'NativeQueries':queries,'ExactResetCommands':commands,'ResetGraph':graph,'VendorBasis':vendor_value,
        'UniqueSourceEndpointPairs':sum(q['ExpectedTargetCount'] for q in queries),
        'ActualCellCount':len(graph_value['Cells']),'ActualFFCount':len(graph_value['FFPlacement']),
        'NativeQueriesVerified':False,'ConstraintsApplied':False,'HistoricalEndpointInventoryUsed':False}
    require(not drift(watched),'reset preparation input drift')
    return facts,watched


def render(work,commands):
    w=Path(work).as_posix()
    return ('set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG676\n'
        'add_design {'+w+'/dummy.v}\nif {[info script] ne {}} {\n    mpnr -input {'+w+
        '/input.adf}\n    '+inspect.INIT+'\n    file copy {'+w+'/input.adf} {'+w+'/post-init.adf}\n'
        +'\n'.join(commands)+'\n    save_adif\n    file copy {'+w+'/input.adf} {'+w+
        '/saved-reset.adf}\n    .switch_db -route -input {'+w+'/input.adf} -output {'+w+
        '/route-dump.txt}\n    puts {'+MARKER+'}\n    flush stdout\n}\n')


def prepare(export_path,route_path,work,route_application=None):
    work=build.work_path(work);require(not work.exists(),'fresh reset application directory required')
    facts,watched=derive(export_path,route_path,route_application)
    text=render(work,facts['ExactResetCommands']);plan=read(facts['BuildPlan'])
    work.mkdir();shutil.copyfile(facts['SourceADF'],work/'input.adf')
    (work/'stage.tcl').write_text(text,encoding='ascii',newline='\n')
    (work/'dummy.v').write_text(inspect.DUMMY,encoding='ascii',newline='\n')
    for name in ('stage.tcl','dummy.v'):add(watched,work/name)
    value={'Schema':SCHEMA,'Target':TARGET,'Mode':'save-reset','CreatedUTC':inspect.utc(),**facts,
        'WorkDirectory':str(work),'MaximumSeconds':300,'InputSHA256':{str(p):h for p,h in watched.items()},
        'Command':[plan['PDS']['Executable'],'-file',(work/'stage.tcl').as_posix(),
                   '-work_dir',work.as_posix(),'-project_name',TARGET],
        'HardwareAccessed':False,'BitstreamRequested':False,'HardwareReleaseAllowed':False,
        'TimingAccepted':False,'DataTimingWaiverAllowed':False}
    build.write(work/'stage-plan.json',value);return work/'stage-plan.json'


def check_stage(path):
    path=Path(path).resolve();work=build.work_path(path.parent);value=read(path)
    require(path.name=='stage-plan.json' and value.get('Schema')==SCHEMA and value.get('Target')==TARGET
            and value['Mode']=='save-reset' and value['WorkDirectory']==str(work),'wrong reset application stage')
    watched={}
    for name,h in value['InputSHA256'].items():add(watched,name,h)
    require(value['InputSHA256'].get(str(SELF))==sha(SELF),'reset producer unbound')
    expected,_=derive(value['BaselineExport']['Path'],value['BaselineReport']['Path'],
                      value['RouteApplication']['Path'] if value['RouteApplication'] else None)
    require(all(value.get(k)==v for k,v in expected.items()),'reset application scope/evidence changed')
    plan=build.validate(value['BuildPlan'])
    require(value['MaximumSeconds']==300 and value['Command']==[plan['PDS']['Executable'],'-file',
            (work/'stage.tcl').as_posix(),'-work_dir',work.as_posix(),'-project_name',TARGET], 'reset command differs')
    require((work/'stage.tcl').read_text(encoding='ascii')==render(work,value['ExactResetCommands'])
            and (work/'dummy.v').read_text(encoding='ascii')==inspect.DUMMY,'reset Tcl instructions differ')
    for key in ('HardwareAccessed','BitstreamRequested','HardwareReleaseAllowed','TimingAccepted','DataTimingWaiverAllowed'):
        require(value.get(key) is False,'reset plan overclaims '+key)
    add(watched,path);return value,watched


def artifacts(work):
    return {p.relative_to(work).as_posix():sha(p) for p in Path(work).rglob('*') if p.is_file() and p.suffix in SUFFIXES}


def execute(path):
    value,watched=check_stage(path);work=Path(value['WorkDirectory'])
    require(os.name=='nt' and not (work/'execution-start.json').exists()
            and sha(work/'input.adf')==value['SourceADFSHA256'],'fresh native reset copy required')
    result={**value,'StagePlanSHA256':sha(path),'StartedUTC':inspect.utc(),'EDAExecuted':False,
        'ExecutionPassed':False,'TimedOut':False,'ExitCode':None};process=None;start=time.monotonic()
    build.write(work/'execution-start.json',result)
    try:
        with (work/'stdout.log').open('xb') as out,(work/'stderr.log').open('xb') as err:
            process=subprocess.Popen(value['Command'],cwd=work,stdout=out,stderr=err,shell=False,
                creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0));result.update(EDAExecuted=True,OwnedPID=process.pid)
            try:result['ExitCode']=process.wait(timeout=value['MaximumSeconds'])
            except subprocess.TimeoutExpired:result['TimedOut']=True
    except BaseException as e:result['Error']=type(e).__name__+': '+str(e)
    finally:
        if process is not None and process.poll() is None:
            result['Cleanup']=build.cleanup.stop_owned_tree(process,work,'bounded exact reset save')
        else:result['Cleanup']={'Complete':True,'ParentExited':True}
        result['ElapsedSeconds']=round(time.monotonic()-start,3)
    try:
        log=(work/'stdout.log').read_text(encoding='gb18030',errors='replace')
        names=query_parser.exact_queries(value['NativeQueries'],work/'stdout.log')
        comparison=compare_routes(value['BaselineRouteDump']['Path'],work/'route-dump.txt')
        final=sha(work/'input.adf')
        result.update(ActualEvents=inspect.events(log),CompletionMarker=MARKER in log,
            InputDrift=drift(watched),Diagnostics=inspect.diagnostics(work),NativeNameProof=names,
            NativeQueriesVerified=True,ConstraintsApplied=True,
            InitializationPreservedADF=sha(work/'post-init.adf')==value['SourceADFSHA256'],
            SavedADFReadbackMatches=sha(work/'saved-reset.adf')==final,ResultADFChanged=final!=value['SourceADFSHA256'],
            ResultADF=ref(work/'input.adf'),ResultADFSHA256=final,RouteComparison=comparison,
            RoutesAndPlacementUnchanged=True,Artifacts=artifacts(work))
        result['ExecutionPassed']=(result['ExitCode']==0 and not result['TimedOut'] and not result.get('Error')
            and result['ActualEvents']==[] and result['CompletionMarker'] and result['InputDrift']==result['Diagnostics']==[]
            and result['InitializationPreservedADF'] and result['SavedADFReadbackMatches'] and result['ResultADFChanged']
            and result['Cleanup']['Complete'])
    except Exception as e:result['Error']=type(e).__name__+': '+str(e)
    build.write(work/'result.json',result);return result


def bind_completed(path):
    path=Path(path).resolve();work=build.work_path(path.parent);saved=read(path)
    stage,watched=check_stage(work/'stage-plan.json')
    # Native execution legitimately advances these two preparation status fields.
    require(path.name=='result.json' and all(saved.get(k)==v for k,v in stage.items()
            if k not in ('NativeQueriesVerified','ConstraintsApplied')) and
            saved['StagePlanSHA256']==sha(work/'stage-plan.json') and saved.get('ExecutionPassed') is True
            and saved.get('ExitCode')==0 and saved.get('EDAExecuted') is True and not saved.get('Error')
            and saved.get('TimedOut') is False and saved.get('InputDrift')==saved.get('Diagnostics')==[]
            and saved.get('Cleanup',{}).get('Complete') is True,'unclean reset application receipt')
    log=(work/'stdout.log').read_text(encoding='gb18030',errors='replace')
    require(saved['ActualEvents']==inspect.events(log)==[] and MARKER in log and inspect.diagnostics(work)==[],
            'reset execution stages/logs differ')
    require(saved.get('NativeQueriesVerified') is True and saved.get('ConstraintsApplied') is True
            and saved['NativeNameProof']==query_parser.exact_queries(saved['NativeQueries'],work/'stdout.log'),
            'reset application exact native names differ')
    require(sha(work/'post-init.adf')==saved['SourceADFSHA256'] and
            sha(work/'input.adf')==sha(work/'saved-reset.adf')==saved['ResultADFSHA256']!=saved['SourceADFSHA256']
            and saved['ResultADF']==ref(work/'input.adf'),'reset save readback chain differs')
    require(saved['Artifacts']==artifacts(work) and
            saved['RouteComparison']==compare_routes(saved['BaselineRouteDump']['Path'],work/'route-dump.txt'),
            'reset application artifacts or routes changed')
    for n,h in saved['Artifacts'].items():add(watched,work/n,h)
    add(watched,path);return saved,watched


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--export',type=Path)
    p.add_argument('--route',type=Path);p.add_argument('--route-application',type=Path)
    p.add_argument('--work-dir',type=Path);p.add_argument('--execute-plan',type=Path);a=p.parse_args()
    if a.execute_plan:
        r=execute(a.execute_plan);print(json.dumps({k:r.get(k) for k in ('ExecutionPassed','ExitCode','ElapsedSeconds','Error')}))
        return 0 if r['ExecutionPassed'] else 1
    path=prepare(a.export,a.route,a.work_dir,a.route_application);print(json.dumps({'Prepared':True,'Plan':str(path)}));return 0


if __name__=='__main__':raise SystemExit(main())
