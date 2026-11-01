"""Read-only fresh-process inspection of a proved input-delay diagnostic derivative.

The source must be the byte-checked output of the exact reset-save executor.
Every source/proof/native receipt is rebound; arbitrary mutation is forbidden.
"""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time

import run_raw_camera_delay_reset_physical as physical

inspect, audit = physical.inspect, physical.audit
prep, diagnostic = physical.prep, physical.diagnostic
require, sha = prep.require, prep.sha
SELF = Path(__file__).resolve()
SCHEMA = 'raw-camera-delay-derived-inspection-v1'
MARKER = 'RAW_CAMERA_DELAY_DERIVED_INSPECTION_COMPLETE'


def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def add(watched, path, expected=None, pds=None):
    return physical.add(watched, path, expected, pds)


def artifacts(path, value, watched):
    require(isinstance(value.get('Artifacts'), dict) and value['Artifacts'], 'missing native artifact inventory')
    for name, h in value['Artifacts'].items():
        p = inspect.canonical(path.parent/name, path.parent)
        add(watched, p, h)
    for name in ('stage.tcl', 'stdout.log', 'stderr.log'):
        require(name in value['Artifacts'], 'unbound core native artifact')


def bind_application(path, watched):
    path = inspect.canonical(path, prep.WORK)
    require(path.name == 'result.json' and path.parent.parent == prep.WORK, 'exact reset-save result path required')
    result = read(path)
    require(result.get('Schema') == physical.SCHEMA and result.get('Target') == prep.TARGET
            and result.get('Mode') == 'save-reset' and result.get('ExecutionPassed') is True
            and result.get('ConstraintsAppliedToDiagnosticCopy') is True and physical.execution_ok(result),
            'reset-save receipt is not clean')
    for flag in ('HardwareAccessed', 'BitstreamRequested', 'TimingExceptionApproved', 'TimingAccepted',
                 'HardwareReleaseAllowed', 'AppliedScopeReadbackVerified', 'FinalSTAExecuted'):
        require(result.get(flag) is False, 'reset-save authority differs: '+flag)
    proof = result['ResetProof']
    expected, tcl, bound = physical.recipe(result['BuildPlan'], proof['Path'], proof['SHA256'],
                                         path.parent, result['MaximumSeconds'])
    stage_path = inspect.canonical(path.parent/'stage-plan.json', prep.WORK)
    require(physical.digest(result.get('StagePlanSHA256')), 'reset stage-plan hash missing')
    add(watched, stage_path, result['StagePlanSHA256'])
    stage = read(stage_path)
    require(set(stage) == set(expected)|{'PreparedUTC'} and isinstance(stage['PreparedUTC'], str) and stage['PreparedUTC']
            and {k:v for k,v in stage.items() if k != 'PreparedUTC'} == expected
            and all(result.get(k) == v for k,v in stage.items()), 'reset receipt/plan differs from exact recipe')
    for p,h in bound.items():add(watched, p, h, Path(result['Command'][0]))
    add(watched, path)
    require((path.parent/'stage.tcl').read_bytes() == tcl.encode('ascii'), 'reset executed Tcl differs')
    require((path.parent/'dummy.v').read_bytes() == physical.DUMMY.encode('ascii'), 'reset dummy source differs')
    add(watched, path.parent/'executor-snapshot.py', sha(physical.SELF))
    add(watched, path.parent/'applied-scope.fdc', result['ResetFDC']['SHA256'])
    for name,h in result['InputSHA256'].items():add(watched, name, h, Path(result['Command'][0]))
    artifacts(path, result, watched)
    log = (path.parent/'stdout.log').read_text(encoding='gb18030', errors='replace')
    require(physical.MARKER in log and diagnostic.stage_events(log) == [], 'reset native completion/events differ')
    names = audit.exact_queries(read(proof['Path'])['NativeQueries'], path.parent/'stdout.log')
    require(names == result['ApplicationNativeNameProof'], 'reset applied native names differ')
    source = inspect.canonical(path.parent/'input.adf', prep.WORK)
    require(result['ResultADF'] == {'Path':str(source), 'SHA256':sha(source), 'Bytes':source.stat().st_size}
            and result['ResultADFSHA256'] == sha(source) != result['SourceADFSHA256'], 'reset result ADF differs')
    for name in ('input.adf', 'post-init.adf', 'saved-reset.adf'):
        p = add(watched, path.parent/name)
        require(result['ADFReadback'].get(name) == {'Path':str(p), 'SHA256':sha(p), 'Bytes':p.stat().st_size}
                and result['Artifacts'].get(name) == sha(p), 'reset ADF readback differs')
    require(sha(path.parent/'post-init.adf') == result['SourceADFSHA256']
            and sha(path.parent/'saved-reset.adf') == sha(source), 'reset snapshots differ')
    require(not inspect.drift(watched), 'reset application chain drift')
    return result


def bind_source_receipt(path, watched):
    path = inspect.canonical(path, prep.WORK)
    value = read(path)
    if value.get('Schema') == physical.SCHEMA:
        return bind_application(path, watched)
    if value.get('Schema') == 'raw-camera-delay-route-reset-application-v1':
        import run_raw_camera_delay_route_reset as route_reset
        require(route_reset.SCHEMA == value['Schema'], 'route/reset schema differs')
        result = route_reset.bind_completed(path, watched)
        add(watched, route_reset.__file__)
        require(result.get('Target') == prep.TARGET and result.get('ExecutionPassed') is True,
                'route/reset source is not a proved input-delay derivative')
        source = inspect.canonical(path.parent/'input.adf', prep.WORK)
        require(result.get('Mode') == 'save-route-reset'
                and result['ResultADF'] == {'Path':str(source),'SHA256':sha(source),'Bytes':source.stat().st_size}
                and result['ResultADFSHA256'] == sha(source)
                and result['Artifacts'].get('input.adf') == sha(source), 'route/reset result identity differs')
        log = (path.parent/'stdout.log').read_text(encoding='gb18030', errors='replace')
        require(route_reset.MARKER in log and diagnostic.stage_events(log) == [], 'route/reset native events differ')
        return result
    raise ValueError('unsupported input-delay mutation receipt schema')


def expected_stages(mode):
    require(mode in ('query', 'report', 'export'), 'unsupported derived inspection mode')
    return ['Report Timing', 'Generate Netlist'] if mode == 'export' else []


def render(mode, original, base, work, body=None):
    expected_stages(mode)
    require(body is None or MARKER not in body, 'reserved derived completion marker')
    if mode in ('query', 'export'):
        return inspect.render(mode, original, base, work, body).replace(inspect.MARKER, MARKER)
    require(body is None, 'report mode accepts no body')
    aw = work.as_posix()
    return ('set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG676\n'
            'add_design {'+aw+'/dummy.v}\nif {[info script] ne {}} {\n'
            '    mpnr -input {'+aw+'/input.adf}\n    '+inspect.INIT+'\n'
            '    .switch_db -route -input {'+aw+'/input.adf} -output {'+aw+'/route-dump.txt}\n'
            '    puts {'+MARKER+'}\n    flush stdout\n}\n')


def recipe(source_receipt, work, mode, body_path=None, maximum=300):
    work = prep.work_path(work)
    require(type(maximum) is int and 120 <= maximum <= 300, 'inspection bound must be 120..300 seconds')
    watched = {}; result = bind_source_receipt(source_receipt, watched)
    source_receipt = Path(source_receipt).absolute()
    source = Path(result['ResultADF']['Path']); build_path = Path(result['BuildPlan']); build = read(build_path)
    body = None
    if mode == 'query':
        body_path = inspect.canonical(body_path, prep.WORK); add(watched, body_path)
        body = body_path.read_text(encoding='ascii')
    else:require(body_path is None, 'non-query mode accepts no body')
    add(watched, SELF); add(watched, physical.SELF)
    tcl = render(mode, (build_path.parent/'timing.tcl').read_text(encoding='ascii'), build_path.parent, work, body)
    require(not inspect.drift(watched), 'source chain drift during preparation')
    value = {'Schema':SCHEMA, 'Target':prep.TARGET, 'Mode':mode, 'WorkDirectory':str(work),
        'BuildPlan':str(build_path), 'BuildPlanSHA256':sha(build_path),
        'SourceReceipt':{'Path':str(source_receipt), 'SHA256':sha(source_receipt)},
        'SourceADF':str(source), 'SourceADFSHA256':result['ResultADFSHA256'],
        'OriginalSourceADF':result['SourceADF'], 'OriginalSourceADFSHA256':result['SourceADFSHA256'],
        'QueryBody':str(body_path) if body_path else None, 'MaximumSeconds':maximum,
        'ExpectedActualStages':expected_stages(mode), 'InputSHA256':{str(p):h for p,h in watched.items()},
        'TclSHA256':prep.baseline.paths.sha_bytes(tcl.encode('ascii')),
        'Command':[build['PDS']['Executable'], '-file', (work/'stage.tcl').as_posix(),
                   '-work_dir', work.as_posix(), '-project_name', prep.TARGET],
        'HardwareAccessed':False, 'BitstreamRequested':False, 'TimingAccepted':False, 'HardwareReleaseAllowed':False,
        'Limits':'Read-only derived diagnostics. Reset effect, internal timing and external hardware acceptance require independent audits.'}
    return value, tcl, watched


def prepare(*args, **kwargs):
    value, tcl, watched = recipe(*args, **kwargs); work = Path(value['WorkDirectory'])
    require(not work.exists() and not inspect.drift(watched), 'fresh directory and stable source chain required')
    work.mkdir(); shutil.copyfile(value['SourceADF'], work/'input.adf')
    require(sha(work/'input.adf') == value['SourceADFSHA256'], 'inspection ADF copy differs')
    (work/'stage.tcl').write_text(tcl, encoding='ascii', newline='\n')
    shutil.copyfile(SELF, work/'executor-snapshot.py')
    if value['Mode'] != 'export':(work/'dummy.v').write_text(physical.DUMMY, encoding='ascii', newline='\n')
    value['PreparedUTC'] = prep.utc(); diagnostic.write(work/'stage-plan.json', value)
    return work/'stage-plan.json'


def validate_prepared(path):
    path = inspect.canonical(path, prep.WORK); work = prep.work_path(path.parent)
    require(path.name == 'stage-plan.json', 'exact stage-plan.json required')
    value = read(path)
    require(value.get('Schema') == SCHEMA and value.get('Target') == prep.TARGET, 'wrong derived inspection identity')
    expected, tcl, watched = recipe(value['SourceReceipt']['Path'], work, value['Mode'], value['QueryBody'], value['MaximumSeconds'])
    require(set(value) == set(expected)|{'PreparedUTC'} and isinstance(value['PreparedUTC'], str) and value['PreparedUTC']
            and {k:v for k,v in value.items() if k != 'PreparedUTC'} == expected, 'derived plan differs from recipe')
    files = {'input.adf', 'stage.tcl', 'executor-snapshot.py', 'stage-plan.json'}
    if value['Mode'] != 'export':files.add('dummy.v')
    require({p.name for p in work.iterdir()} == files, 'inspection stage reused or contaminated')
    require((work/'stage.tcl').read_bytes() == tcl.encode('ascii')
            and sha(work/'input.adf') == value['SourceADFSHA256']
            and sha(work/'executor-snapshot.py') == sha(SELF), 'derived prepared artifact drift')
    if value['Mode'] != 'export':require((work/'dummy.v').read_bytes() == physical.DUMMY.encode('ascii'), 'dummy drift')
    for name in files:add(watched, work/name)
    require(not inspect.drift(watched), 'derived inspection input drift')
    return value, watched


def receipt_flags(value):
    stages = expected_stages(value.get('Mode'))
    require(value.get('Schema') == SCHEMA and value.get('Target') == prep.TARGET
            and value.get('ExecutionPassed') is True and value.get('ExitCode') == 0
            and value.get('TimedOut') is False and value.get('StoppedForUnexpectedStage') is False
            and not value.get('Error') and value.get('InputDrift') == [] and value.get('Diagnostics') == []
            and value.get('CompletionMarker') is True and value.get('InputADFUnchanged') is True
            and value.get('Cleanup', {}).get('Complete') is True and value.get('EDAExecuted') is True
            and value.get('ExpectedActualStages') == stages
            and value.get('ActualEvents') == [[s,e] for s in stages for e in ('started','done')], 'derived receipt is not clean')
    for flag in ('HardwareAccessed', 'BitstreamRequested', 'TimingAccepted', 'HardwareReleaseAllowed'):
        require(value.get(flag) is False, 'derived inspection exceeds diagnostic scope')
    if value['Mode'] == 'export':require(value.get('NativeNetlistWithFFloc') is True, 'placed native export missing')


def bind_receipt(path, watched):
    """Return a fully rebound receipt dict; used by final IO/bit/effect consumers."""
    path = inspect.canonical(path, prep.WORK)
    require(path.name == 'result.json' and path.parent.parent == prep.WORK, 'exact derived result path required')
    value = read(path); receipt_flags(value)
    expected, tcl, bound = recipe(value['SourceReceipt']['Path'], path.parent, value['Mode'], value['QueryBody'], value['MaximumSeconds'])
    require(physical.digest(value.get('StagePlanSHA256')), 'derived stage-plan hash missing')
    stage_path = add(watched, path.parent/'stage-plan.json', value['StagePlanSHA256']); stage = read(stage_path)
    require(set(stage) == set(expected)|{'PreparedUTC'} and isinstance(stage['PreparedUTC'], str) and stage['PreparedUTC']
            and {k:v for k,v in stage.items() if k != 'PreparedUTC'} == expected
            and all(value.get(k) == v for k,v in stage.items()), 'derived receipt/plan differs from exact recipe')
    for p,h in bound.items():add(watched, p, h, Path(value['Command'][0]))
    add(watched, path); add(watched, path.parent/'input.adf', value['SourceADFSHA256'])
    add(watched, path.parent/'executor-snapshot.py', sha(SELF))
    require((path.parent/'stage.tcl').read_bytes() == tcl.encode('ascii'), 'derived executed Tcl differs')
    artifacts(path, value, watched)
    log = (path.parent/'stdout.log').read_text(encoding='gb18030', errors='replace')
    require(MARKER in log and [list(x) for x in diagnostic.stage_events(log)] == value['ActualEvents'], 'derived actual events differ')
    if value['Mode'] == 'export':
        p = path.parent/'generate_netlist'/(prep.TARGET+'_sim.v')
        require(value['Netlist'] == {'Path':str(p), 'SHA256':sha(p), 'Bytes':p.stat().st_size}
                and value['Artifacts'].get(p.relative_to(path.parent).as_posix()) == sha(p), 'derived netlist binding differs')
    require(not inspect.drift(watched), 'derived source/artifact drift')
    return value


def execute(path):
    value, watched = validate_prepared(path); require(os.name == 'nt', 'native derived inspection requires Windows')
    work = Path(value['WorkDirectory']); started = time.monotonic(); process = None
    result = {**value, 'StagePlanSHA256':sha(path), 'StartedUTC':prep.utc(), 'EDAExecuted':False,
              'ExecutionPassed':False, 'TimedOut':False, 'StoppedForUnexpectedStage':False, 'ExitCode':None}
    diagnostic.write(work/'execution-start.json', result)
    expected = [(s,e) for s in value['ExpectedActualStages'] for e in ('started','done')]
    try:
        with (work/'stdout.log').open('xb') as out, (work/'stderr.log').open('xb') as err:
            process = subprocess.Popen(value['Command'], cwd=work, stdout=out, stderr=err, shell=False,
                                       creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            result.update(EDAExecuted=True, OwnedPID=process.pid)
            while process.poll() is None:
                remaining = value['MaximumSeconds']-(time.monotonic()-started)
                if remaining <= 0:result['TimedOut'] = True; break
                try:process.wait(timeout=min(2, remaining))
                except subprocess.TimeoutExpired:pass
                events = diagnostic.stage_events((work/'stdout.log').read_text(encoding='gb18030', errors='replace'))
                if events != expected[:len(events)]:result['StoppedForUnexpectedStage'] = True; break
    except BaseException as error:result['Error'] = type(error).__name__+': '+str(error)
    finally:
        if process is not None:
            result['Cleanup'] = (diagnostic.cleanup.stop_owned_tree(process, work, 'bounded derived inspection')
                if process.poll() is None else {'Complete':True, 'OwnedPID':process.pid, 'ParentExited':True,
                                               'DescendantLivenessIndependentlyVerified':False})
            result['ExitCode'] = process.poll()
        else:result['Cleanup'] = {'Complete':True, 'Required':False}
    try:
        log = (work/'stdout.log').read_text(encoding='gb18030', errors='replace') if (work/'stdout.log').exists() else ''
        diagnostics = []
        for p in work.rglob('*.log'):
            diagnostics += [p.relative_to(work).as_posix()+': '+s.strip() for s in re.findall(
                r'(?m)^\s*(?:E:|F:|ERROR:|FATAL:|Traceback).*$', p.read_text(encoding='gb18030', errors='replace'))]
        net = work/'generate_netlist'/(prep.TARGET+'_sim.v')
        text = net.read_text(encoding='ascii', errors='replace') if net.is_file() else ''
        valid = bool(re.search(r'(?m)^module '+prep.TARGET+r'\s*$', text)) and bool(re.search(r'V_\w+\s*/\*\s*(?:CLMA|CLMS|IOLHR)_\d+_\d+\s*\*/', text))
        result.update(ActualEvents=[list(e) for e in diagnostic.stage_events(log)], InputDrift=inspect.drift(watched),
            Diagnostics=diagnostics, CompletionMarker=MARKER in log, InputADFUnchanged=sha(work/'input.adf') == value['SourceADFSHA256'],
            NativeNetlistWithFFloc=valid if value['Mode']=='export' else None,
            Netlist={'Path':str(net), 'SHA256':sha(net), 'Bytes':net.stat().st_size} if net.is_file() else None,
            Artifacts={p.relative_to(work).as_posix():sha(p) for p in work.rglob('*') if p.is_file()
                       and p.suffix in ('.tcl', '.log', '.rtr', '.v', '.gnr', '.txt', '.fdc')})
        result['ExecutionPassed'] = True
        try:receipt_flags(result)
        except ValueError:result['ExecutionPassed'] = False
    except Exception as error:
        result['ReadbackError'] = type(error).__name__+': '+str(error); result['ExecutionPassed'] = False
    result.update(FinishedUTC=prep.utc(), ElapsedSeconds=round(time.monotonic()-started, 3))
    diagnostic.write(work/'result.json', result); return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source-receipt', type=Path); p.add_argument('--name'); p.add_argument('--mode', choices=('query','report','export'))
    p.add_argument('--body', type=Path); p.add_argument('--maximum-seconds', type=int, default=300); p.add_argument('--stage-plan', type=Path)
    modes = p.add_mutually_exclusive_group(); modes.add_argument('--prepare-only', action='store_true')
    modes.add_argument('--validate-only', action='store_true'); modes.add_argument('--execute', action='store_true')
    a = p.parse_args()
    if a.stage_plan:
        require(not any((a.source_receipt,a.name,a.mode,a.body,a.prepare_only)), 'stage-plan accepts only validation/execution')
        if a.execute:result = execute(a.stage_plan)
        else:validate_prepared(a.stage_plan); result = {'Validated':True, 'EDAExecuted':False}
    else:
        require(a.source_receipt and a.name and a.mode, 'source receipt, fresh name and mode required')
        args = (a.source_receipt, prep.WORK/a.name, a.mode, a.body, a.maximum_seconds)
        if a.prepare_only or a.execute:
            stage = prepare(*args); result = execute(stage) if a.execute else {'Prepared':True, 'StagePlan':str(stage), 'EDAExecuted':False}
        else:recipe(*args); result = {'Validated':True, 'EDAExecuted':False}
    print(json.dumps({k:result[k] for k in ('Prepared','Validated','StagePlan','ExecutionPassed','ExitCode','ElapsedSeconds','InputDrift','Diagnostics','EDAExecuted') if k in result}))
    return 0 if result.get('ExecutionPassed', True) else 1


if __name__ == '__main__':raise SystemExit(main())
