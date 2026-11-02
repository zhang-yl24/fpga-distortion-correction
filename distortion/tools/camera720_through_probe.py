"""Bounded two-path diagnostic of packed launches through one valid CIN.

This independent wrapper never changes frozen query policy and never accepts
CDC timing or hardware release. Only root explicitly executes a prepared plan.
"""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
from types import ModuleType

import camera720_stage_fast as fast
import camera720_cdc_native as cdc

native, inspect, prep, diagnostic = fast.native, fast.inspect, fast.prep, fast.diagnostic
require, sha, read = fast.require, fast.sha, fast.read
SELF = Path(__file__).resolve()
SCHEMA = 'camera720-through-probe-plan-v1'
RESULT_SCHEMA = 'camera720-through-probe-result-v1'
MARKER = 'CAMERA720_THROUGH_PROBE_COMPLETE'
SOURCE_PARENT = 'camera_configuration/monitor/held_snapshot[101]/opit_0_L6Q_LUT6DQL5Q_perm'
SOURCE = SOURCE_PARENT + '/CLK'
ENDPOINT = 'camera_configuration/monitor/frame_age[12]/opit_0_AQ/CIN'
CANDIDATE_SHA = '777bed47bf6489457f42cda54a3cadc4e74f7a4ae2c8caacc51eb49f14e48904'
CDC_PLAN_SHA = '8284cb237803073b48e831c8d5c6999a1e6833a2b0160f903020caf5f98ac415'
FILES = {'stage-plan.json', 'stage.tcl', 'input.adf', 'dummy.v', 'executor-snapshot.py'}


def commands():
    return [('report_path_timing -delay_type min_max -max_path 1000 -nworst 8 -report_exception TRUE'
             ' -from {'+SOURCE+'} -through {'+SOURCE_PARENT+'/'+q+'} -to {'+ENDPOINT+'}')
            for q in ('L6Q', 'L5Q')]


def render(work):
    aw = work.as_posix()
    return ('set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG676\n'
            'add_design {'+aw+'/dummy.v}\nif {[info script] ne {}} {\n'
            '    mpnr -input {'+aw+'/input.adf}\n    '+inspect.INIT+'\n'
            +'\n'.join(commands())+'\n    puts {'+MARKER+'}\n    flush stdout\n}\n')


def tool_closure():
    pending, seen, paths = [fast, cdc], set(), {SELF, fast.PYTHON}
    while pending:
        module = pending.pop()
        if id(module) in seen:
            continue
        seen.add(id(module))
        name = getattr(module, '__file__', None)
        if not name:
            continue
        path = Path(name).resolve()
        if not path.is_relative_to(prep.PROJECT/'tools') or path.suffix != '.py':
            continue
        paths.add(path)
        pending.extend(v for v in vars(module).values() if isinstance(v, ModuleType))
    return {str(p): sha(p) for p in sorted(paths)}


def recipe(seed_path, seed_sha, work):
    seed, original, watched = fast.bind_seed(seed_path, seed_sha)
    work = prep.work_path(work)
    require(original['SourceADFSHA256'] == CANDIDATE_SHA, 'fixed diagnostic candidate differs')
    plan_path = inspect.canonical(prep.WORK/'cdc-qualified-b/native-plan.json', prep.WORK)
    native.add(watched, plan_path, CDC_PLAN_SHA)
    plan = read(plan_path)
    require(plan['Producer'] == fast.binding(cdc.SELF) and plan['CandidateADF']['SHA256'] == CANDIDATE_SHA,
            'frozen launch query authority differs')
    queries = []
    for q in ('L6Q', 'L5Q'):
        matches = [r for r in plan['Queries'] if cdc.identity(r) == (SOURCE, SOURCE_PARENT+'/'+q, ENDPOINT)]
        require(len(matches) == 1, 'exact probe identity missing or ambiguous')
        queries.append(matches[0])
    tools = tool_closure()
    fast.rehash(tools, watched, Path(original['Command'][0]))
    script = render(work)
    value = {'Schema': SCHEMA, 'Target': prep.TARGET, 'Producer': fast.binding(SELF),
             'InspectionSeed': fast.binding(seed_path), 'FrozenCDCPlan': fast.binding(plan_path),
             'SourceADF': original['SourceADF'], 'SourceADFSHA256': CANDIDATE_SHA,
             'BuildPlan': original['BuildPlan'], 'BuildPlanSHA256': original['BuildPlanSHA256'],
             'WorkDirectory': str(work), 'MaximumSeconds': 300, 'ExpectedActualStages': [],
             'TimingCommands': commands(), 'Queries': queries, 'TclSHA256': prep.baseline.paths.sha_bytes(script.encode('ascii')),
             'Command': [original['Command'][0], '-file', (work/'stage.tcl').as_posix(),
                         '-work_dir', work.as_posix(), '-project_name', prep.TARGET],
             'InputSHA256': {str(p): h for p,h in watched.items()}, 'ToolSHA256': tools,
             'EDAExecuted': False, **{k: False for k in fast.FALSE_FLAGS},
             'Limits': 'Diagnostic launch selection only; no CDC coverage, timing acceptance, ADF/FDC mutation, or hardware release.'}
    require(not inspect.drift(watched), 'probe recipe input drift')
    return value, script, watched


def prepare(seed_path, seed_sha, work):
    value, script, watched = recipe(seed_path, seed_sha, work)
    work = Path(value['WorkDirectory'])
    require(not work.exists(), 'fresh through probe directory required')
    work.mkdir()
    shutil.copyfile(value['SourceADF'], work/'input.adf')
    shutil.copyfile(SELF, work/'executor-snapshot.py')
    (work/'stage.tcl').write_bytes(script.encode('ascii'))
    (work/'dummy.v').write_bytes(native.physical.DUMMY.encode('ascii'))
    require(sha(work/'input.adf') == CANDIDATE_SHA and not inspect.drift(watched), 'probe copy/input drift')
    value['PreparedUTC'] = inspect.utc()
    diagnostic.write(work/'stage-plan.json', value)
    return work/'stage-plan.json'


def validate(path, expected_sha):
    path = inspect.canonical(path, prep.WORK)
    require(path.name == 'stage-plan.json' and native.physical.digest(expected_sha) and sha(path) == expected_sha,
            'explicit through stage plan SHA differs')
    value = read(path)
    expected, script, watched = recipe(value['InspectionSeed']['Path'], value['InspectionSeed']['SHA256'], path.parent)
    require(set(value) == set(expected)|{'PreparedUTC'} and isinstance(value['PreparedUTC'], str) and value['PreparedUTC']
            and {k:v for k,v in value.items() if k != 'PreparedUTC'} == expected, 'through stage differs from exact recipe')
    require({p.name for p in path.parent.iterdir()} == FILES, 'probe stage reused or contaminated')
    require((path.parent/'stage.tcl').read_bytes() == script.encode('ascii')
            and (path.parent/'dummy.v').read_bytes() == native.physical.DUMMY.encode('ascii')
            and sha(path.parent/'input.adf') == CANDIDATE_SHA
            and sha(path.parent/'executor-snapshot.py') == sha(SELF), 'prepared probe bytes drifted')
    for name in FILES:
        native.add(watched, path.parent/name)
    require(not inspect.drift(watched), 'probe validation drift')
    return value, watched


def selector(command, option):
    matches = re.findall(r'-'+option+r'\s+\{([^}]*)\}', command)
    require(len(matches) == 1, 'one exact '+option+' selector required')
    pins = [p[2:] if p.startswith(('t:', 'p:')) else p for p in matches[0].split()]
    require(len(pins) == 1, 'one exact '+option+' pin required')
    return pins[0]


def parse_report(report, query, command):
    text = report.read_text(encoding='gb18030')
    head = '\n'.join(text.splitlines()[:18])
    require('2023.2-SP3 <build 154097>' in head and
            re.search(r'^\| Design\s*:\s*'+re.escape(prep.TARGET)+r'\s*$', head, re.M), 'native report identity differs')
    headers = re.findall(r'^\| Tcl Command\s*:\s*(.*?)\s*$', head, re.M)
    require(len(headers) == 1 and headers[0].startswith('report_path_timing '), 'one native timing command required')
    require(all(selector(headers[0], o) == selector(command, o) for o in ('from', 'through', 'to')),
            'native from/through/to selector dropped or changed')
    records = []
    for lines, line in cdc.native.blocks(report):
        records.append(cdc.parse_record(lines, report, line, query))
    require(records and {r['Corner'] for r in records} == {'slow', 'fast'}, 'both actual launch corners required')
    require(all(r['Kind'] == 'max-delay' for r in records), 'only effective datapath-only maximum observations expected')
    return {'Report': fast.binding(report), 'SelectorsRetained': True, 'Records': records,
            'LaunchObservedBothCorners': True, 'TimingAccepted': False}


def scan_diagnostics(work):
    result = []
    for p in sorted(work.rglob('*.log')):
        for line, text in enumerate(p.read_text(encoding='gb18030', errors='replace').splitlines(), 1):
            if re.match(r'^\s*(?:C:|E:|F:|ERROR:|FATAL:|Traceback)', text):
                result.append({'Log': p.relative_to(work).as_posix(), 'Line': line, 'Text': text.strip()})
    return result


def observations(work, value):
    observed, issues = [], []
    root = work/'report_path_timing'
    expected = {f'report_path_timing_{i}' for i in (1,2)}
    if not root.is_dir() or {p.name for p in root.iterdir() if p.is_dir()} != expected:
        issues.append({'Stage': 'native-query-count', 'Error': 'exact two isolated report directories required'})
    for i, (query, command) in enumerate(zip(value['Queries'], value['TimingCommands']), 1):
        report = root/f'report_path_timing_{i}'/'report_timing'/(prep.TARGET+'.rtr')
        try:
            item = parse_report(report, query, command)
            item['TimingCommandIndex1Based'] = i
            observed.append(item)
        except (OSError, ValueError) as error:
            issues.append({'Stage': 'native-through-observation', 'TimingCommandIndex1Based': i, 'Error': str(error)})
    return observed, issues


def execute(path, expected_sha):
    value, watched = validate(path, expected_sha)
    require(os.name == 'nt', 'native through probe requires Windows')
    work, started, process = Path(value['WorkDirectory']), time.monotonic(), None
    result = {**value, 'Schema': RESULT_SCHEMA, 'PlanSchema': SCHEMA, 'StagePlanSHA256': expected_sha,
              'StartedUTC': inspect.utc(), 'ExecutionPassed': False, 'ProbeObserved': False,
              'TimedOut': False, 'StoppedForUnexpectedStage': False, 'ExitCode': None}
    diagnostic.write(work/'execution-start.json', result)
    try:
        with (work/'stdout.log').open('xb') as out, (work/'stderr.log').open('xb') as err:
            process = subprocess.Popen(value['Command'], cwd=work, stdout=out, stderr=err, shell=False,
                                       creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            result.update(EDAExecuted=True, OwnedPID=process.pid)
            while process.poll() is None:
                remaining = 300 - (time.monotonic()-started)
                if remaining <= 0:
                    result['TimedOut'] = True; break
                try:
                    process.wait(timeout=min(2, remaining))
                except subprocess.TimeoutExpired:
                    pass
                log = (work/'stdout.log').read_text(encoding='gb18030', errors='replace')
                if diagnostic.stage_events(log):
                    result['StoppedForUnexpectedStage'] = True; break
    except BaseException as error:
        result['Error'] = type(error).__name__+': '+str(error)
    finally:
        if process is not None:
            result['Cleanup'] = (diagnostic.cleanup.stop_owned_tree(process, work, 'bounded through diagnostic')
                if process.poll() is None else {'Complete': True, 'OwnedPID': process.pid, 'ParentExited': True,
                                               'DescendantLivenessIndependentlyVerified': False})
            result['ExitCode'] = process.poll()
        else:
            result['Cleanup'] = {'Complete': True, 'Required': False}
    try:
        log = (work/'stdout.log').read_text(encoding='gb18030', errors='replace') if (work/'stdout.log').exists() else ''
        observed, issues = observations(work, value)
        result.update(ActualEvents=[list(x) for x in diagnostic.stage_events(log)],
            CompletionMarker=MARKER in log, InputDrift=inspect.drift(watched), Diagnostics=scan_diagnostics(work),
            InputADFUnchanged=sha(work/'input.adf') == CANDIDATE_SHA, Observations=observed, ObservationFailures=issues)
        result['ExecutionPassed'] = (result['ExitCode'] == 0 and not result.get('Error') and not result['TimedOut']
            and not result['StoppedForUnexpectedStage'] and result['Cleanup'].get('Complete') is True
            and result['ActualEvents'] == [] and result['CompletionMarker'] and not result['InputDrift']
            and not result['Diagnostics'] and result['InputADFUnchanged'])
        result['ProbeObserved'] = result['ExecutionPassed'] and not issues and len(observed) == 2
    except Exception as error:
        result['ReadbackError'] = type(error).__name__+': '+str(error)
        result['ExecutionPassed'] = False
    result.update(FinishedUTC=inspect.utc(), ElapsedSeconds=round(time.monotonic()-started, 3),
        Artifacts={p.relative_to(work).as_posix(): sha(p) for p in work.rglob('*') if p.is_file()
                   and p.name not in ('result.json', 'execution-start.json')})
    diagnostic.write(work/'result.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    p = sub.add_parser('prepare')
    p.add_argument('--seed', type=Path, required=True); p.add_argument('--seed-sha256', required=True)
    p.add_argument('--name', required=True)
    for action in ('validate', 'execute'):
        p = sub.add_parser(action)
        p.add_argument('--stage-plan', type=Path, required=True); p.add_argument('--stage-plan-sha256', required=True)
    args = parser.parse_args()
    if args.action == 'prepare':
        path = prepare(args.seed, args.seed_sha256, prep.WORK/args.name)
        result = {'Prepared': True, 'StagePlan': fast.binding(path), 'EDAExecuted': False}
    elif args.action == 'validate':
        validate(args.stage_plan, args.stage_plan_sha256)
        result = {'Validated': True, 'EDAExecuted': False}
    else:
        value = execute(args.stage_plan, args.stage_plan_sha256)
        result = {k: value[k] for k in ('ExecutionPassed', 'ProbeObserved', 'ExitCode', 'ElapsedSeconds',
                                       'Diagnostics', 'ObservationFailures', 'TimingAccepted', 'HardwareReleaseAllowed')}
    print(json.dumps(result, indent=2))
    return 0 if result.get('ProbeObserved', True) else 1


if __name__ == '__main__':
    raise SystemExit(main())
