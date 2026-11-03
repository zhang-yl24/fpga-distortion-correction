"""Read-only fresh STA/export of a proved measured-route 720p descendant.

Only a completed independent 720p transport diagnostic is accepted. New plans bind
its own source closure, native receipt, actual ADF and tools. Native execution
is explicit and bounded; no inherited physical names, repairs or exceptions.
"""
import argparse
import hashlib
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time

import prepare_camera720_output as prep
import camera720_inspect as original_inspect
import camera720_hold_route as route
import audit_camera_vga_route_order as route_order
import run_camera720_output_diagnostic as diagnostic

SELF = Path(__file__).resolve()
SCHEMA = 'camera720-derived-readonly-inspection-v1'
MARKER = 'CAMERA720_DERIVED_INSPECTION_COMPLETE'
INIT = 'mpnr_report_timing -force_to_run -delay_type min_max -max_path 1000 -nworst 4 -report_exception TRUE'
require, sha = prep.require, prep.sha


def utc():
    return datetime.now(timezone.utc).isoformat()


def canonical(path, parent=prep.PROJECT):
    p = Path(path).absolute()
    require(p == p.resolve() and p.is_relative_to(parent) and p.is_file(), 'canonical existing input required: '+str(p))
    return p


def drift(watched):
    result = []
    for p, h in watched.items():
        try:
            if p != p.resolve() or not p.is_file() or sha(p) != h:
                result.append(str(p))
        except OSError:
            result.append(str(p))
    return result


def bind(plan_path, source, expected_sha):
    """Bind a measured-route descendant, then rederive its complete route diff."""
    source = canonical(source, prep.WORK)
    require(source.name == 'saved-route.adf', 'only a saved measured-route descendant is supported')
    receipt = canonical(source.parent/'result.json', prep.WORK)
    stage = canonical(source.parent/'stage-plan.json', prep.WORK)
    result = json.loads(receipt.read_text(encoding='utf-8'))
    application, route_watched, before = route.validate(stage, fresh=False)
    require(application['BuildPlan'] == str(Path(plan_path).absolute()), 'route belongs to another build')
    plan, watched = original_inspect.bind(plan_path, application['SourceADF'], application['SourceADFSHA256'])
    watched.update(route_watched)
    require(all(result.get(k) == v for k, v in application.items()) and
            result.get('StagePlanSHA256') == sha(stage), 'route receipt differs from its exact plan')
    order_only_failure = (result.get('ExecutionPassed') is False and
                          result.get('Error') == 'ValueError: functional/placement semantics changed')
    require(result.get('Schema') == route.SCHEMA and (result.get('ExecutionPassed') is True or order_only_failure) and
            result.get('EDAExecuted') is True and result.get('ExitCode') == 0 and
            result.get('TimedOut') is False and result.get('StoppedForUnexpectedStage') is False and
            (not result.get('Error') or order_only_failure) and result.get('InputDrift') == [] and result.get('Diagnostics') == [] and
            result.get('CompletionMarker') is True and result.get('ActualEvents') == [] and
            result.get('Cleanup', {}).get('Complete') is True, 'route application did not complete cleanly')
    for flag in ('HardwareAccessed', 'BitstreamRequested', 'TimingAccepted', 'HardwareReleaseAllowed',
                 'DataTimingWaiverAllowed', 'ConstraintsChanged', 'FinalSTAExecuted'):
        require(result.get(flag) is False, 'route receipt exceeds its scope: '+flag)
    require(re.fullmatch('[0-9a-f]{64}', expected_sha) and sha(source) == expected_sha and
            sha(source.parent/'input.adf') == expected_sha and
            result.get('ResultADFSHA256') == expected_sha and expected_sha != application['SourceADFSHA256'],
            'route descendant SHA/readback differs')
    artifacts = result.get('Artifacts')
    require(isinstance(artifacts, dict) and
            {'stage-plan.json', 'input.adf', 'saved-route.adf', 'route-dump.txt', 'stdout.log', 'stderr.log'} <= set(artifacts),
            'route artifact inventory incomplete')
    for name, digest in artifacts.items():
        path = canonical(source.parent/name, source.parent)
        require(sha(path) == digest, 'route artifact changed: '+name)
        watched[path] = digest
    log = (source.parent/'stdout.log').read_text(encoding='gb18030', errors='replace')
    require(route.MARKER in log and not diagnostic.stage_events(log), 'route native completion differs')
    after = route.routes.inspect(source.parent/'route-dump.txt', application['Targets'])
    if order_only_failure:
        # Preserve the failed raw-token receipt. Prove independently that the
        # ONLY semantic difference is consecutive CDBENTRY sibling ordering.
        # All entries and their enclosing contexts, raw CDB bytes, placement,
        # logic and every unrequested route remain exact.
        original_dump = Path(application['QueryReceipt']).parent/'route-dump.txt'
        b_order = route_order.ordered_semantics(original_dump)
        a_order = route_order.ordered_semantics(source.parent/'route-dump.txt')
        key = 'OrderedNonRouteSemanticSHA256'
        require(b_order[key] == a_order[key] and
                b_order['CDBRawTextSHA256'] == a_order['CDBRawTextSHA256'] and
                b_order['CDBENTRYCount'] == a_order['CDBENTRYCount'],
                'route differences exceed native CDBENTRY sibling reordering')
        before = {**before, 'NonRouteSemanticSHA256': b_order[key]}
        after = {**after, 'NonRouteSemanticSHA256': a_order[key]}
        # Native query context retained FILEMAP 2 with an EMPTY filename;
        # saving the route removes that unused source-location placeholder.
        # Accept exactly these two token sequences, never a named source map.
        def token_sha(tokens):
            return hashlib.sha256(('\0'.join(tokens)+'\0').encode()).hexdigest()
        placeholder = token_sha(['(', 'FILETABLE', '(', 'FILEMAP', '2', '""', ')', ')'])
        empty = token_sha(['(', 'FILETABLE', ')'])
        b_files = before['ExcludedBlockSHA256']['FILETABLE']
        a_files = after['ExcludedBlockSHA256']['FILETABLE']
        if b_files != a_files:
            require(b_files == placeholder and a_files == empty,
                    'source table changed beyond removal of empty FILEMAP 2 placeholder')
            before = {**before, 'ExcludedBlockSHA256': {**before['ExcludedBlockSHA256'], 'FILETABLE': empty}}
        comparison = route.routes.compare(before, after, application['Targets'])
        require(comparison['ChangedNetCount'] > 0, 'no requested route changed')
        watched[Path(route_order.__file__).resolve()] = sha(route_order.__file__)
    else:
        comparison = route.routes.compare(before, after, application['Targets'])
        require(comparison == result.get('RouteComparison'), 'rederived full route diff differs')
    # The first diagnostic's report was not artifact-bound by its executor.
    # Close that gap using the independent SAME-ADF native query receipt:
    # re-extract measured hold branches AND both setup margins from its bound
    # report, then compare with the original executor's measurements.
    query_path = Path(application['QueryReceipt'])
    query, query_watched = original_inspect.bind_receipt(query_path)
    watched.update(query_watched)
    reports = [query_path.parent/n for n in query['Artifacts']
               if Path(n).name == prep.TARGET+'.rtr' and 'report_path_timing' not in Path(n).parts]
    require(len(reports) == 1, 'one receipt-bound same-ADF timing report required')
    bound_inventory, _ = route.hold.build(reports, prep.TARGET)
    original_report = Path(plan_path).parent/'report_timing'/(prep.TARGET+'.rtr')
    original_inventory, _ = route.hold.build([original_report], prep.TARGET)
    def measurements(inventory):
        return [{k: row[k] for k in ('Source', 'Endpoint', 'LaunchClock', 'CaptureClock',
                                     'Margins', 'PhysicalRepairCandidate')} for row in inventory['Paths']]
    require(not bound_inventory['MissingExactSetup'] and
            measurements(bound_inventory) == measurements(original_inventory),
            'hold branches or setup margins differ from receipt-bound actual report')
    for item in application['Waypoints']:
        target = item['Target']
        chain = after['BranchInventory'][target['Net']]['Leaves'][target['ToRoutePin']]
        pins = item['Selected']['Pins']
        require(any(chain[i:i+2] == pins for i in range(len(chain)-1)), 'saved waypoint no longer present')
    for path in (receipt, stage, source, SELF, Path(route.__file__).resolve(), Path(original_inspect.__file__).resolve()):
        watched[path] = sha(path)
    require(not drift(watched), 'derived route/build evidence drift')
    return plan, watched


def query_commands(body):
    require(body and body.isascii(), 'nonempty ASCII body required')
    brace = r'\{[^{}\r\n]*\}'
    patterns = [r'puts '+brace,
        r'get_(?:pins|ports|clocks) -hierarchical -regexp '+brace,
        r'get_(?:ports|clocks) -regexp '+brace,
        r'show -(?:design_net|dev_instance) '+brace,
        r'\.switch_db -route -input \{@WORK@/input\.adf\} -output \{@WORK@/[A-Za-z0-9_-]+\.txt\}',
        r'dump_net -grid_unit '+brace+r' -print_site -out_file \{@WORK@/[A-Za-z0-9_-]+\.txt\}',
        r'report_path_timing -delay_type min_max -max_path (?:[1-9][0-9]{0,2}|1000) -nworst [1-8] -report_exception TRUE -from '+brace+r' -to '+brace,
        r'(?:mpnr_report_timing|report_path_timing|show|show_device|get_pins|get_ports|get_clocks) -help']
    commands = []
    for line in body.splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        require(not re.search(r'\\[{}\r\n]',line) and all(ord(c) >= 32 for c in line),
                'escaped braces/continuations/control characters forbidden')
        require(any(re.fullmatch(p,line) for p in patterns), 'unsupported read-only query: '+line[:100])
        require(MARKER not in line, 'reserved completion marker')
        commands.append(line)
    require(commands and len(commands) <= 300, 'query command count out of bounds')
    return commands


def monitor_query_template():
    """Initial object discovery only; no assumed post-synthesis bit counts."""
    return '\n'.join((
        '# Read-only discovery. Optimized-away diagnostics are not invented.',
        'puts {CAMERA720_NATIVE_CLOCKS}', 'get_clocks -regexp {.*}',
        'puts {CAMERA720_NATIVE_PORTS}', 'get_ports -regexp {.*}',
        'puts {CAMERA720_NATIVE_MONITOR_PINS}',
        'get_pins -hierarchical -regexp {^camera_configuration/monitor/.*}',
        'puts {CAMERA720_NATIVE_BOARD_RESET_PINS}',
        'get_pins -hierarchical -regexp {^(power_ready|key_reset_sync|ref_reset|core_reset|board_failed_core).*}',
        '.switch_db -route -input {@WORK@/input.adf} -output {@WORK@/route-dump.txt}',
    ))+'\n'


def render(mode, original, base, work, body=None):
    aw = work.as_posix()
    if mode == 'query':
        commands = query_commands(body)
        # Native get_pins needs STA context; only one initialization per process.
        return ('set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG676\n'
                'add_design {'+aw+'/dummy.v}\nif {[info script] ne {}} {\n'
                '    mpnr -input {'+aw+'/input.adf}\n    '+INIT+'\n'
                +'\n'.join(commands).replace('@WORK@',aw)+'\n    puts {'+MARKER+'}\n    flush stdout\n}\n')
    require(mode == 'export' and body is None, 'export accepts no query body')
    suffix = ('if {[file exists '+prep.literal(base/'place_route'/(prep.TARGET+'_pnr.adf'))+']} {\n'
              '    file copy '+prep.literal(base/'place_route'/(prep.TARGET+'_pnr.adf'))+' '+prep.literal(base/'pre-sta-final.adf')+'\n}\n'
              'report_timing -force_to_run -delay_type min_max -max_path 1000 -nworst 4 -report_exception TRUE\n')
    require(original.endswith(suffix) and original.count(suffix)==1, '720p transport build suffix differs')
    prefix = original[:-len(suffix)]
    require(prefix.endswith('pnr -optimize_multi_corner_timing -fix_hold_violation\n'), '720p transport placement context differs')
    # PDS flow context retains real source/IP/FDC roles. Explicit input_db_file
    # selects only fresh Report Timing and Generate Netlist actual stages.
    return (prefix+'report_timing -force_to_run -input_db_file {'+aw+'/input.adf} -delay_type min_max -max_path 1000 -nworst 4 -report_exception TRUE\n'
            'if {[info script] ne {}} {\n    gen_netlist -force_to_run -input_db_file {'+aw+'/input.adf} -func_sim_only\n'
            '    puts {'+MARKER+'}\n    flush stdout\n}\n')


def recipe(build_plan, source, source_sha, work, mode, body_path=None, maximum=300):
    work = prep.work_path(work)
    require(type(maximum) is int and 120 <= maximum <= 300, 'inspection bound must be120..300 seconds')
    plan, watched = bind(build_plan, source, source_sha)
    body = None
    if mode == 'query':
        body_path = canonical(body_path, prep.WORK)
        watched[body_path] = sha(body_path)
        body = body_path.read_text(encoding='ascii')
    else:
        require(body_path is None, 'export accepts no body path')
    tcl = render(mode, (Path(build_plan).parent/'timing.tcl').read_text(encoding='ascii'), Path(build_plan).absolute().parent, work, body)
    value = {'Schema':SCHEMA,'Target':prep.TARGET,'Mode':mode,'WorkDirectory':str(work),
        'BuildPlan':str(Path(build_plan).absolute()),'BuildPlanSHA256':sha(build_plan),
        'SourceADF':str(Path(source).absolute()),'SourceADFSHA256':source_sha,
        'QueryBody':str(body_path) if body_path else None,'MaximumSeconds':maximum,
        'ExpectedActualStages':[] if mode=='query' else ['Report Timing','Generate Netlist'],
        'InputSHA256':{str(p):h for p,h in watched.items()},'TclSHA256':prep.baseline.paths.sha_bytes(tcl.encode('ascii')),
        'Command':[plan['PDS']['Executable'],'-file',(work/'stage.tcl').as_posix(),'-work_dir',work.as_posix(),'-project_name',prep.TARGET],
        'HardwareAccessed':False,'BitstreamRequested':False,'TimingAccepted':False,'HardwareReleaseAllowed':False,
        'OpticalCorrectionAccepted':False,
        'Limits':'Read-only independent 720p transport inspection. New monitor CDC/reset paths, native timing, optical calibration and hardware acceptance require separate review.'}
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
    if value['Mode']=='query':
        (work/'dummy.v').write_text('module physical_dummy(input a, output y); assign y=a; endmodule\n',encoding='ascii',newline='\n')
    value['PreparedUTC'] = utc()
    diagnostic.write(work/'stage-plan.json',value)
    return work/'stage-plan.json'


def validate_prepared(path):
    path = canonical(path,prep.WORK)
    work = prep.work_path(path.parent)
    require(path.name=='stage-plan.json','exact stage-plan.json required')
    value = json.loads(path.read_text())
    require(value.get('Schema')==SCHEMA and value.get('Target')==prep.TARGET,'720p transport inspection identity differs')
    expected,tcl,watched = recipe(value['BuildPlan'],value['SourceADF'],value['SourceADFSHA256'],work,
                                value['Mode'],value['QueryBody'],value['MaximumSeconds'])
    require(set(value)==set(expected)|{'PreparedUTC'} and {k:v for k,v in value.items() if k!='PreparedUTC'}==expected,
            'inspection plan differs from bound recipe')
    files={'input.adf','stage.tcl','executor-snapshot.py','stage-plan.json'}
    if value['Mode']=='query':files.add('dummy.v')
    require({p.name for p in work.iterdir()}==files,'inspection stage reused or contaminated')
    require((work/'stage.tcl').read_bytes()==tcl.encode('ascii') and sha(work/'input.adf')==value['SourceADFSHA256']
            and sha(work/'executor-snapshot.py')==sha(SELF),'inspection prepared artifact drift')
    if value['Mode']=='query':
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
    expected, tcl, watched = recipe(value['BuildPlan'], value['SourceADF'], value['SourceADFSHA256'],
                                   work, value['Mode'], value['QueryBody'], value['MaximumSeconds'])
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
    if value['Mode'] == 'query':
        require((work/'dummy.v').read_bytes() == b'module physical_dummy(input a, output y); assign y=a; endmodule\n',
                'finished query dummy context drift')
    stages = [] if value['Mode'] == 'query' else ['Report Timing', 'Generate Netlist']
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
    for name, digest in artifacts.items():
        artifact = canonical(work/name, work)
        require(sha(artifact) == digest, 'finished native artifact drift: '+name)
        watched[artifact] = digest
    if value['Mode'] == 'export':
        netlist = canonical(work/'generate_netlist'/(prep.TARGET+'_sim.v'), work)
        require(value.get('NativeNetlistWithFFloc') is True and value.get('Netlist') == {
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
    diagnostics=[]
    for p in work.rglob('*.log'):
        diagnostics += [p.relative_to(work).as_posix()+': '+line.strip() for line in re.findall(
            r'(?m)^\s*(?:E:|F:|ERROR:|FATAL:|Traceback).*$',p.read_text(encoding='gb18030',errors='replace'))]
    netlist=work/'generate_netlist'/(prep.TARGET+'_sim.v')
    nettext=netlist.read_text(encoding='ascii',errors='replace') if netlist.is_file() else ''
    netvalid=bool(re.search(r'(?m)^module '+prep.TARGET+r'\s*$',nettext)) and bool(re.search(r'V_\w+\s*/\*\s*(?:CLMA|CLMS|IOLHR)_\d+_\d+\s*\*/',nettext))
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


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--plan',type=Path);p.add_argument('--source-adf',type=Path);p.add_argument('--source-adf-sha256')
    p.add_argument('--name');p.add_argument('--mode',choices=('query','export'));p.add_argument('--body',type=Path)
    p.add_argument('--maximum-seconds',type=int,default=300);p.add_argument('--stage-plan',type=Path)
    modes=p.add_mutually_exclusive_group();modes.add_argument('--prepare-only',action='store_true')
    modes.add_argument('--validate-only',action='store_true');modes.add_argument('--execute',action='store_true')
    a=p.parse_args()
    if a.stage_plan:
        require(not any((a.plan,a.source_adf,a.source_adf_sha256,a.name,a.mode,a.body,a.prepare_only)), 'stage-plan accepts only validation or execution')
        if a.execute:result=execute(a.stage_plan)
        else:
            value,_=validate_prepared(a.stage_plan);result={'Validated':True,'StagePlan':str(a.stage_plan),'ExpectedActualStages':value['ExpectedActualStages']}
    else:
        require(a.plan and a.source_adf and a.source_adf_sha256 and a.name and a.mode,'build plan, exact ADF/hash, name and mode required')
        args=(a.plan,a.source_adf,a.source_adf_sha256,prep.WORK/a.name,a.mode,a.body,a.maximum_seconds)
        if a.prepare_only or a.execute:
            stage=prepare(*args)
            result=execute(stage) if a.execute else {'Prepared':True,'StagePlan':str(stage),'EDAExecuted':False,'HardwareAccessed':False}
        else:
            value,_,_=recipe(*args);result={'Validated':True,'ExpectedActualStages':value['ExpectedActualStages'],'EDAExecuted':False,'HardwareAccessed':False}
    print(json.dumps({k:result[k] for k in ('Prepared','Validated','StagePlan','ExecutionPassed','ExitCode','ElapsedSeconds','InputDrift','Diagnostics','ExpectedActualStages','EDAExecuted','HardwareAccessed') if k in result}))
    return 0 if result.get('ExecutionPassed',True) else 1


if __name__=='__main__':raise SystemExit(main())
