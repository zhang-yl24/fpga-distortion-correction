"""Reuse a completed full reset-inspection proof with exact byte revalidation.

Creating a seed calls the frozen full validator, never a claimed pass flag.
An explicit seed SHA anchors that validation. Later plans for the identical
source may change only the fresh directory, read-only mode/body and deadline.
All original inputs, loaded local helpers, Python/PDS and prepared bytes are
rehashed. Native stages, fresh STA, deadline and output checks are unchanged.
No original module or global is patched. This is not release authority.
"""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
from types import ModuleType

import camera720_reset_inspect as native

prep, inspect, diagnostic = native.prep, native.inspect, native.diagnostic
require, sha, read = native.require, native.sha, native.read
SELF = Path(__file__).resolve()
PYTHON = Path(sys.executable).resolve()
SCHEMA = 'camera720-inspection-authority-seed-v1'
FALSE_FLAGS = ('HardwareAccessed', 'BitstreamRequested', 'TimingAccepted',
               'HardwareReleaseAllowed', 'OpticalCorrectionAccepted', 'ExceptionEffectsAccepted')


def binding(path):
    path = Path(path).absolute()
    return {'Path': str(path), 'SHA256': sha(path)}


def tool_closure():
    """Follow the modules actually referenced by this frozen native adapter."""
    pending = [native]; seen = set(); paths = {SELF, PYTHON}
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
    return {str(path): sha(path) for path in sorted(paths)}


def rehash(mapping, watched, pds):
    require(isinstance(mapping, dict) and mapping, 'nonempty exact input closure required')
    for name, digest in mapping.items():
        path = Path(name)
        require(path.is_absolute() and native.physical.digest(digest), 'canonical input/hash required')
        if path == PYTHON:
            require(path == path.resolve() and sha(path) == digest, 'Python executable changed')
            require(path not in watched or watched[path] == digest, 'conflicting Python identity')
            watched[path] = digest
        else:
            native.add(watched, path, digest, pds)


def prepared_files(mode):
    return {'input.adf', 'stage.tcl', 'executor-snapshot.py', 'stage-plan.json'} | (
        {'dummy.v'} if mode != 'export' else set())


def envelope(original, work, mode, body_path=None, maximum=300):
    """Only deterministic rendering; the seed proves the source authority."""
    require(original.get('Schema') == native.SCHEMA and original.get('Target') == prep.TARGET,
            'wrong anchored native plan')
    require(original.get('Mode') == 'export' and original.get('QueryBody') is None,
            'full export plan must anchor the source proof')
    for flag in FALSE_FLAGS:
        require(original.get(flag) is False, 'anchored plan exceeds diagnostic scope')
    require(type(maximum) is int and 120 <= maximum <= 300, 'deadline must be 120..300 seconds')
    work = prep.work_path(work)
    build_path = Path(original['BuildPlan']); build = read(build_path)
    inputs = dict(original['InputSHA256'])
    body = None
    if mode == 'query':
        body_path = inspect.canonical(body_path, prep.WORK)
        body = body_path.read_text(encoding='ascii')
        inputs[str(body_path)] = sha(body_path)
    else:
        require(body_path is None, 'non-query mode accepts no body')
    script = native.render(mode, (build_path.parent/'timing.tcl').read_text(encoding='ascii'),
                           build_path.parent, work, body)
    value = {k: v for k, v in original.items() if k != 'PreparedUTC'}
    value.update(Mode=mode, WorkDirectory=str(work), QueryBody=str(body_path) if body_path else None,
                 MaximumSeconds=maximum, ExpectedActualStages=native.expected_stages(mode), InputSHA256=inputs,
                 TclSHA256=prep.baseline.paths.sha_bytes(script.encode('ascii')),
                 Command=[build['PDS']['Executable'], '-file', (work/'stage.tcl').as_posix(),
                          '-work_dir', work.as_posix(), '-project_name', prep.TARGET])
    return value, script


def seed_from_full(path, expected_sha256, output, receipt=False):
    path = inspect.canonical(path, prep.WORK)
    require(native.physical.digest(expected_sha256) and sha(path) == expected_sha256,
            'explicit original plan/receipt SHA differs')
    output = Path(output).absolute()
    require(output == output.resolve() and output.parent == prep.WORK and not output.exists()
            and re.fullmatch(r'[a-z0-9][a-z0-9_-]*\.json', output.name), 'fresh direct work seed required')
    before_tools = tool_closure()
    if receipt:
        watched = {}; completed = native.bind_receipt(path, watched)
        require(completed['Mode'] == 'export', 'completed placed export required')
        stage_path = path.parent/'stage-plan.json'; original = read(stage_path)
        method = 'camera720_reset_inspect.bind_receipt'
    else:
        original, watched = native.validate_prepared(path)
        stage_path = path
        method = 'camera720_reset_inspect.validate_prepared'
    return seal_seed(original, watched, stage_path, path, expected_sha256, method, before_tools, output)


def seal_seed(original, watched, stage_path, path, expected_sha256, method, before_tools, output):
    """Called only with the actual successful full-validator result."""
    require(original['Mode'] == 'export' and original['QueryBody'] is None, 'export authority anchor required')
    pds = Path(original['Command'][0])
    rehash(before_tools, watched, pds)
    rehash(original['InputSHA256'], watched, pds)
    for name in prepared_files(original['Mode']):
        native.add(watched, stage_path.parent/name)
    native.add(watched, path, expected_sha256)
    expected, script = envelope(original, stage_path.parent, original['Mode'], None, original['MaximumSeconds'])
    require({k:v for k,v in original.items() if k != 'PreparedUTC'} == expected
            and (stage_path.parent/'stage.tcl').read_bytes() == script.encode('ascii'),
            'validated native envelope differs')
    require(before_tools == tool_closure() and not inspect.drift(watched), 'validation inputs/tools drifted')
    inputs = {str(p): h for p, h in watched.items()}
    seed = {'Schema': SCHEMA, 'Target': prep.TARGET, 'CreatedUTC': inspect.utc(),
            'FullValidationCompleted': True, 'ValidationMethod': {'Function': method, **binding(path)},
            'OriginalStagePlan': binding(stage_path), 'AuthorityInputSHA256': original['InputSHA256'],
            'ValidatedInputSHA256': inputs,
            'ToolSHA256': {p:h for p,h in inputs.items() if Path(p).suffix.lower() in ('.py', '.exe')},
            'SeedCreator': binding(SELF), 'Python': binding(PYTHON),
            'SourceADF': {'Path': original['SourceADF'], 'SHA256': original['SourceADFSHA256']},
            'EDAExecuted': False, **{flag: False for flag in FALSE_FLAGS}}
    with output.open('x', encoding='utf-8', newline='\n') as f:
        json.dump(seed, f, indent=2); f.write('\n')
    return {'Seed': binding(output), 'BoundInputs': len(inputs), 'FullValidationCompleted': True,
            'EDAExecuted': False, 'HardwareAccessed': False}


def bootstrap(source_receipt, source_sha256, work, output, maximum=300):
    """Full recipe once, materialize/read back its exact result, seal it."""
    source_receipt = inspect.canonical(source_receipt, prep.WORK)
    require(native.physical.digest(source_sha256) and sha(source_receipt) == source_sha256,
            'explicit source receipt SHA differs')
    work = prep.work_path(work)
    output = Path(output).absolute()
    require(output == output.resolve() and output.parent == prep.WORK and not output.exists()
            and re.fullmatch(r'[a-z0-9][a-z0-9_-]*\.json', output.name), 'fresh direct work seed required')
    require(not work.exists(), 'fresh export directory required')
    before_tools = tool_closure()
    # This is the unchanged full source binder and exact recipe called by
    # native.prepare. Its return, not a cached file or claimed flag, is used.
    value, script, watched = native.recipe(source_receipt, work, 'export', None, maximum)
    require(value['WorkDirectory'] == str(work) and value['SourceReceipt'] == {
        'Path':str(source_receipt), 'SHA256':source_sha256}, 'full recipe source identity differs')
    require(not work.exists() and not inspect.drift(watched), 'full recipe drifted before materialization')
    work.mkdir(); shutil.copyfile(value['SourceADF'], work/'input.adf')
    (work/'stage.tcl').write_bytes(script.encode('ascii'))
    shutil.copyfile(native.SELF, work/'executor-snapshot.py')
    value['PreparedUTC'] = inspect.utc(); diagnostic.write(work/'stage-plan.json', value)
    require({p.name for p in work.iterdir()} == prepared_files('export')
            and read(work/'stage-plan.json') == value
            and sha(work/'input.adf') == value['SourceADFSHA256']
            and (work/'stage.tcl').read_bytes() == script.encode('ascii')
            and sha(work/'executor-snapshot.py') == sha(native.SELF), 'full prepared output readback differs')
    sealed = seal_seed(value, watched, work/'stage-plan.json', source_receipt, source_sha256,
                       'camera720_reset_inspect.recipe', before_tools, output)
    return {'Prepared':True, 'StagePlan':binding(work/'stage-plan.json'), **sealed}


def bind_seed(path, expected_sha256):
    path = inspect.canonical(path, prep.WORK)
    require(native.physical.digest(expected_sha256) and sha(path) == expected_sha256,
            'explicit seed SHA differs')
    seed = read(path)
    require(seed.get('Schema') == SCHEMA and seed.get('Target') == prep.TARGET
            and seed.get('FullValidationCompleted') is True and seed.get('EDAExecuted') is False,
            'completed full validation seed required')
    for flag in FALSE_FLAGS:
        require(seed.get(flag) is False, 'seed exceeds read-only diagnostic authority')
    stage_ref = seed['OriginalStagePlan']; stage = inspect.canonical(stage_ref['Path'], prep.WORK)
    require(stage.name == 'stage-plan.json' and sha(stage) == stage_ref['SHA256'], 'original plan changed')
    original = read(stage); pds = Path(original['Command'][0])
    watched = {}; rehash(seed['ValidatedInputSHA256'], watched, pds)
    require(seed['AuthorityInputSHA256'] == original['InputSHA256']
            and all(seed['ValidatedInputSHA256'].get(p) == h for p,h in original['InputSHA256'].items()),
            'full authority closure was dropped or changed')
    tools = {p:h for p,h in seed['ValidatedInputSHA256'].items() if Path(p).suffix.lower() in ('.py','.exe')}
    require(seed['ToolSHA256'] == tools and all(tools.get(p) == h for p,h in tool_closure().items()),
            'full helper/executable closure changed')
    require(seed['SeedCreator'] == binding(SELF) and seed['Python'] == binding(PYTHON), 'seed creator/Python differs')
    method = seed['ValidationMethod']; source = inspect.canonical(method['Path'], prep.WORK)
    require(seed['ValidatedInputSHA256'].get(str(source)) == method['SHA256'] == sha(source),
            'completed validation identity differs')
    if method['Function'] == 'camera720_reset_inspect.validate_prepared':
        require(source == stage and method['SHA256'] == stage_ref['SHA256'], 'validated plan anchor differs')
    elif method['Function'] == 'camera720_reset_inspect.recipe':
        require(method['Path'] == original['SourceReceipt']['Path'] and
                method['SHA256'] == original['SourceReceipt']['SHA256'], 'full recipe source anchor differs')
        application = read(source)
        require(application.get('Schema') == native.physical.SCHEMA and
                application.get('Target') == prep.TARGET and application.get('Mode') == 'save-reset' and
                application.get('ExecutionPassed') is True and native.physical.execution_ok(application),
                'full recipe no longer binds a clean reset application')
    else:
        require(method['Function'] == 'camera720_reset_inspect.bind_receipt' and source == stage.parent/'result.json',
                'unsupported full validation method')
        completed = read(source); native.receipt_flags(completed)
        require(completed['StagePlanSHA256'] == sha(stage) and all(completed.get(k) == v for k,v in original.items()),
                'completed export differs from original plan')
    require(seed['SourceADF'] == {'Path': original['SourceADF'], 'SHA256': original['SourceADFSHA256']},
            'source differs from completed full proof')
    for p in (stage, Path(original['SourceADF']), Path(original['BuildPlan']),
              Path(original['BuildPlan']).parent/'timing.tcl', native.SELF, pds):
        require(watched.get(p) == sha(p), 'mandatory proof input missing: '+str(p))
    expected, script = envelope(original, stage.parent, 'export', None, original['MaximumSeconds'])
    require({k:v for k,v in original.items() if k != 'PreparedUTC'} == expected,
            'original deterministic envelope differs')
    for name in prepared_files('export'):
        p = stage.parent/name
        require(watched.get(p) == sha(p), 'original prepared byte closure missing')
    require((stage.parent/'stage.tcl').read_bytes() == script.encode('ascii')
            and sha(stage.parent/'executor-snapshot.py') == sha(native.SELF)
            and sha(stage.parent/'input.adf') == original['SourceADFSHA256'], 'original prepared bytes differ')
    native.add(watched, path, expected_sha256)
    require(not inspect.drift(watched), 'seed inputs drifted')
    return seed, original, watched


def recipe(seed_path, seed_sha256, work, mode, body_path=None, maximum=300):
    seed, original, watched = bind_seed(seed_path, seed_sha256)
    value, script = envelope(original, work, mode, body_path, maximum)
    rehash(value['InputSHA256'], watched, Path(value['Command'][0]))
    require(not inspect.drift(watched), 'new stage input drift')
    return value, script, watched


def prepare(seed_path, seed_sha256, work, mode, body_path=None, maximum=300):
    value, script, watched = recipe(seed_path, seed_sha256, work, mode, body_path, maximum)
    work = Path(value['WorkDirectory'])
    require(not work.exists(), 'fresh inspection directory required')
    work.mkdir(); shutil.copyfile(value['SourceADF'], work/'input.adf')
    (work/'stage.tcl').write_bytes(script.encode('ascii'))
    shutil.copyfile(native.SELF, work/'executor-snapshot.py')
    if mode != 'export':
        (work/'dummy.v').write_bytes(native.physical.DUMMY.encode('ascii'))
    value['PreparedUTC'] = inspect.utc(); diagnostic.write(work/'stage-plan.json', value)
    require(sha(work/'input.adf') == value['SourceADFSHA256'] and not inspect.drift(watched), 'new prepared input drift')
    return work/'stage-plan.json'


def validate(seed_path, seed_sha256, path):
    path = inspect.canonical(path, prep.WORK)
    require(path.name == 'stage-plan.json', 'exact stage-plan.json required')
    value = read(path); work = prep.work_path(path.parent)
    expected, script, watched = recipe(seed_path, seed_sha256, work, value['Mode'], value['QueryBody'], value['MaximumSeconds'])
    require(set(value) == set(expected)|{'PreparedUTC'} and isinstance(value['PreparedUTC'], str) and value['PreparedUTC']
            and {k:v for k,v in value.items() if k != 'PreparedUTC'} == expected, 'prepared plan differs')
    files = prepared_files(value['Mode'])
    require({p.name for p in work.iterdir()} == files, 'stage reused or contaminated')
    require((work/'stage.tcl').read_bytes() == script.encode('ascii')
            and sha(work/'input.adf') == value['SourceADFSHA256']
            and sha(work/'executor-snapshot.py') == sha(native.SELF), 'prepared byte drift')
    if value['Mode'] != 'export':
        require((work/'dummy.v').read_bytes() == native.physical.DUMMY.encode('ascii'), 'dummy drift')
    for name in files:
        native.add(watched, work/name)
    require(not inspect.drift(watched), 'stage validation drift')
    return value, watched


def execute(seed_path, seed_sha256, path):
    value, watched = validate(seed_path, seed_sha256, path); require(os.name == 'nt', 'native derived inspection requires Windows')
    work = Path(value['WorkDirectory']); started = time.monotonic(); process = None
    result = {**value, 'StagePlanSHA256':sha(path), 'StartedUTC':inspect.utc(), 'EDAExecuted':False,
              'ExecutionPassed':False, 'TimedOut':False, 'StoppedForUnexpectedStage':False, 'ExitCode':None,
              'FastExecutionSeed':binding(seed_path), 'FastExecutor':binding(SELF),
              'FullSourceProofReused':True, 'AllProofInputsRehashed':True}
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
            Diagnostics=diagnostics, CompletionMarker=native.MARKER in log, InputADFUnchanged=sha(work/'input.adf') == value['SourceADFSHA256'],
            NativeNetlistWithFFloc=valid if value['Mode']=='export' else None,
            Netlist={'Path':str(net), 'SHA256':sha(net), 'Bytes':net.stat().st_size} if net.is_file() else None,
            Artifacts={p.relative_to(work).as_posix():sha(p) for p in work.rglob('*') if p.is_file()
                       and p.suffix in ('.tcl', '.log', '.rtr', '.v', '.gnr', '.txt', '.fdc')})
        result['ExecutionPassed'] = True
        try:native.receipt_flags(result)
        except ValueError:result['ExecutionPassed'] = False
    except Exception as error:
        result['ReadbackError'] = type(error).__name__+': '+str(error); result['ExecutionPassed'] = False
    result.update(FinishedUTC=inspect.utc(), ElapsedSeconds=round(time.monotonic()-started, 3))
    diagnostic.write(work/'result.json', result); return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='action', required=True)
    seed = commands.add_parser('seed')
    source = seed.add_mutually_exclusive_group(required=True)
    source.add_argument('--stage-plan', type=Path)
    source.add_argument('--export-receipt', type=Path)
    seed.add_argument('--source-sha256', required=True)
    seed.add_argument('--output', type=Path, required=True)
    initial = commands.add_parser('bootstrap')
    initial.add_argument('--source-receipt', type=Path, required=True)
    initial.add_argument('--source-sha256', required=True)
    initial.add_argument('--name', required=True)
    initial.add_argument('--output', type=Path, required=True)
    initial.add_argument('--maximum-seconds', type=int, default=300)
    for action in ('prepare', 'validate', 'execute'):
        command = commands.add_parser(action)
        command.add_argument('--seed', type=Path, required=True)
        command.add_argument('--seed-sha256', required=True)
        if action == 'prepare':
            command.add_argument('--name', required=True)
            command.add_argument('--mode', choices=('query', 'report', 'export'), required=True)
            command.add_argument('--body', type=Path)
            command.add_argument('--maximum-seconds', type=int, default=300)
        else:
            command.add_argument('--stage-plan', type=Path, required=True)
    args = parser.parse_args()
    if args.action == 'seed':
        result = seed_from_full(args.stage_plan or args.export_receipt, args.source_sha256,
                                args.output, receipt=bool(args.export_receipt))
    elif args.action == 'bootstrap':
        result = bootstrap(args.source_receipt, args.source_sha256, prep.WORK/args.name,
                           args.output, args.maximum_seconds)
    elif args.action == 'prepare':
        path = prepare(args.seed, args.seed_sha256, prep.WORK/args.name, args.mode, args.body, args.maximum_seconds)
        result = {'Prepared': True, 'StagePlan': binding(path), 'EDAExecuted': False}
    elif args.action == 'validate':
        validate(args.seed, args.seed_sha256, args.stage_plan)
        result = {'Validated': True, 'EDAExecuted': False}
    else:
        result = execute(args.seed, args.seed_sha256, args.stage_plan)
        result = {k: result[k] for k in ('ExecutionPassed','ExitCode','ElapsedSeconds','InputDrift','Diagnostics','EDAExecuted')}
    print(json.dumps(result, indent=2))
    return 0 if result.get('ExecutionPassed', True) else 1


if __name__ == '__main__':
    raise SystemExit(main())

