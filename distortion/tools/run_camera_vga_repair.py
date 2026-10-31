"""Apply explicit camera DDR route/reset requests to an independent ADF copy."""
import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
import time

import run_camera_vga_physical as core

SCHEMA = 'camera-vga-physical-repair-request-v1'
RESULT_SCHEMA = 'camera-vga-physical-repair-v1'
MARKER = 'CAMERA_EXACT_PHYSICAL_REPAIR_COMPLETE'
NETS = frozenset(('_N101', '_N188', '_N78'))
SITE = r'(?:CLMA|CLMS|IOLHR|SRB)_\d+_\d+'
PIN = r'[A-Z][A-Z0-9_]*(?:\[\d+\])?'
BRANCH = PIN + ':' + SITE
WAYPOINT = PIN + ':' + SITE
PINS = r'(?:' + WAYPOINT + r'>' + WAYPOINT + r';){1,32}'


def bound_file(item, watched):
    core.require(isinstance(item, dict) and set(item) == {'Path', 'SHA256'}, 'exact Path/SHA256 binding required')
    path = core.canonical_file(item['Path'], core.ROOT)
    core.require(re.fullmatch(r'[0-9a-f]{64}', item['SHA256']) and core.sha(path) == item['SHA256'],
                 'bound evidence hash differs: ' + str(path))
    watched[path] = item['SHA256']
    return path


def completed_receipt(path, source_sha, watched):
    receipt = json.loads(path.read_text(encoding='utf-8'))
    core.require(receipt.get('Schema') in (core.SCHEMA, RESULT_SCHEMA)
                 and receipt.get('ExecutionPassed') is True and receipt.get('ExitCode') == 0
                 and receipt.get('TimedOut') is False and receipt.get('InputDrift') == []
                 and receipt.get('Diagnostics') == [] and receipt.get('CompletionMarker') is True
                 and receipt.get('BaselineADFSHA256') == core.BASE_SHA
                 and receipt.get('ResultADFSHA256') == source_sha, 'source/query receipt did not complete cleanly')
    core.require(receipt.get('HardwareAccessed') is False and receipt.get('BitstreamRequested') is False,
                 'receipt includes unsupported hardware scope')
    for name, digest in receipt['InputSHA256'].items():
        p = Path(name)
        core.require(p.is_file() and core.sha(p) == digest, 'receipt input drift: ' + str(p))
        core.require(p not in watched or watched[p] == digest, 'conflicting evidence hash')
        watched[p] = digest
    for name, digest in receipt['Artifacts'].items():
        p = core.canonical_file(path.parent / name, path.parent)
        core.require(core.sha(p) == digest, 'receipt artifact drift: ' + str(p))
        watched[p] = digest
    return receipt


def route_commands(changes):
    core.require(isinstance(changes, list) and len(changes) <= 3, 'route change count exceeds exact camera scope')
    seen, commands = set(), []
    for row in changes:
        core.require(isinstance(row, dict) and set(row) == {'Net', 'Branch', 'Pins'}, 'route request fields differ')
        core.require(row['Net'] in NETS and row['Net'] not in seen, 'unexpected or repeated route net')
        core.require(re.fullmatch(BRANCH, row['Branch']) is not None, 'invalid native branch pin/site')
        core.require(re.fullmatch(PINS, row['Pins']) is not None, 'invalid native detour pin/site chain')
        seen.add(row['Net'])
        commands += ['show -design_net {' + row['Net'] + '}',
                     'unroute -branch {' + row['Net'] + ':' + row['Branch'] + ';}',
                     'manual_route -net {' + row['Net'] + '} -branch {' + row['Branch'] + '} -pins {' + row['Pins'] + '}',
                     'show -design_net {' + row['Net'] + '}']
    return commands


def reset_commands(scope, source_sha, watched):
    if scope is None:
        return []
    core.require(isinstance(scope, dict) and set(scope) == {'FDC', 'Proof'}, 'reset scope fields differ')
    fdc = bound_file(scope['FDC'], watched)
    proofpath = bound_file(scope['Proof'], watched)
    proof = json.loads(proofpath.read_text(encoding='utf-8'))
    core.require(proof.get('Schema') == 'camera-vga-reset-proof-v1'
                 and proof.get('SourceADFSHA256') == source_sha, 'reset proof belongs to a different ADF')
    for flag in ('NativeQueriesVerified', 'EntryConnectivityVerified', 'InternalConnectivityVerified', 'TimingExceptionApproved'):
        core.require(proof.get(flag) is True, 'reset proof is incomplete: ' + flag)
    core.require(proof.get('ProposedFDC') == scope['FDC'], 'reset FDC differs from proof')
    bound_file(proof['ScopePlan'], watched)
    inputs = proof.get('InputSHA256')
    core.require(isinstance(inputs, dict) and inputs, 'reset proof input hashes missing')
    for name, digest in inputs.items():
        path = Path(name).absolute()
        core.require(path == path.resolve() and path.is_file()
                     and (path.is_relative_to(core.PROJECT.parent) or path == core.PDS),
                     'reset proof source escaped read-only repository/PDS scope')
        core.require(re.fullmatch(r'[0-9a-f]{64}', digest) and core.sha(path) == digest,
                     'reset proof input drift: ' + str(path))
        core.require(path not in watched or watched[path] == digest, 'conflicting reset input hash')
        watched[path] = digest
    queries = proof.get('NativeQueries')
    core.require(isinstance(queries, list) and 1 <= len(queries) <= 16, 'reset query group count invalid')
    commands = []
    for row in queries:
        source, targets = row['Source'], row['Targets']
        core.require(isinstance(source, str) and isinstance(targets, list) and targets
                     and len(targets) == len(set(targets)) == row['ExpectedTargetCount']
                     and row['ExpectedFromCount'] == 1, 'reset native object counts differ')
        patterns = ['^(' + '|'.join(re.escape(n) for n in names) + ')$' for names in ([source], sorted(targets))]
        core.require(patterns == [row['FromRegex'], row['ToRegex']], 'reset regex is not exact enumerated pins')
        core.require(all(not any(c in p for c in '\n\r{}') for p in patterns), 'invalid reset pin name')
        commands.append('set_false_path -from [get_pins -hierarchical -regexp {' + patterns[0]
                        + '}] -to [get_pins -hierarchical -regexp {' + patterns[1] + '}]')
    actual = [line.strip() for line in fdc.read_text(encoding='ascii').splitlines()
              if line.strip() and not line.lstrip().startswith('#')]
    core.require(actual == commands, 'reset FDC differs from exact proof commands')
    return commands


def prepare_request(request_path):
    request_path = core.canonical_file(request_path, core.ROOT)
    request = json.loads(request_path.read_text(encoding='utf-8'))
    fields = {'Schema', 'SourceADF', 'SourceADFSHA256', 'SourceReceipt', 'RouteChanges', 'QueryReceipt', 'Occupancy', 'ResetScope'}
    core.require(set(request) == fields and request['Schema'] == SCHEMA, 'unsupported repair request schema/fields')
    _, watched = core.bind_inputs(extra=(Path(__file__).resolve(), request_path))
    source = core.canonical_file(request['SourceADF'], core.ROOT)
    source_sha = core.sha(source)
    core.require(source_sha == request['SourceADFSHA256'], 'source ADF hash differs')
    if source == core.ORIGINAL:
        core.require(request['SourceReceipt'] is None and source_sha == core.BASE_SHA, 'original source binding differs')
    else:
        core.require(source.name == 'input.adf' and source.parent.parent == core.ROOT, 'derived source must be exact stage copy')
        path = bound_file(request['SourceReceipt'], watched)
        core.require(path == source.parent / 'result.json', 'source receipt path differs')
        completed_receipt(path, source_sha, watched)
    watched[source] = source_sha
    routes = route_commands(request['RouteChanges'])
    if routes:
        querypath = bound_file(request['QueryReceipt'], watched)
        query = completed_receipt(querypath, source_sha, watched)
        core.require(query.get('InputADFUnchanged') is True, 'route query must be read-only')
        occupancy = json.loads(bound_file(request['Occupancy'], watched).read_text(encoding='utf-8'))
        core.require(occupancy.get('SourceADFSHA256') == source_sha, 'occupancy belongs to a different ADF')
        core.require(occupancy.get('QueryReceipt') == request['QueryReceipt'], 'occupancy query binding differs')
    else:
        core.require(request['QueryReceipt'] is None and request['Occupancy'] is None, 'unused route evidence must be null')
    resets = reset_commands(request['ResetScope'], source_sha, watched)
    core.require(routes or resets, 'empty repair request')
    core.require(not core.check_inputs(watched), 'repair evidence changed during validation')
    return request, source, watched, routes + resets


def render(commands, work):
    aw = work.as_posix()
    # Native get_pins requires a constructed timing graph after mpnr loads the
    # database. Initialize it only for a request that applies reset scopes.
    initialize = ('mpnr_report_timing -force_to_run -delay_type min_max -max_path 20 -nworst 4 -report_exception TRUE\n'
                  if any(command.startswith('set_false_path ') for command in commands) else '')
    return ('set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG676\n'
            'add_design {' + aw + '/dummy.v}\nif {[info script] ne {}} {\n'
            'mpnr -input {' + aw + '/input.adf}\n' + initialize + '\n'.join(commands) + '\n'
            'save_adif\nfile copy {' + aw + '/input.adf} {' + aw + '/pre-sta.adf}\n'
            'mpnr_report_timing -force_to_run -delay_type min_max -max_path 1000 -nworst 4 -report_exception TRUE\n'
            '.switch_db -route -input {' + aw + '/input.adf} -output {' + aw + '/route-dump.txt}\n'
            'puts {' + MARKER + '}\nflush stdout\n}\n')


def execute(request_path, work, maximum, prepare_only=False):
    work, maximum = core.fresh_work(work), core.deadline(maximum)
    request, source, watched, commands = prepare_request(request_path)
    work.mkdir()
    clone = work / 'input.adf'
    shutil.copyfile(source, clone)
    core.require(core.sha(clone) == watched[source], 'repair input copy differs')
    script, dummy = work / 'stage.tcl', work / 'dummy.v'
    script.write_text(render(commands, work), encoding='ascii', newline='\n')
    dummy.write_text('module physical_dummy(input a,output y); assign y=a; endmodule\n', encoding='ascii')
    for p in (script, dummy):
        watched[p] = core.sha(p)
    command = [str(core.PDS), '-file', script.as_posix(), '-work_dir', work.as_posix(), '-project_name', core.TARGET]
    receipt = {'Schema': RESULT_SCHEMA, 'PreparedUTC': core.utc(), 'SourceADF': str(source),
               'SourceADFSHA256': watched[source], 'BaselineADFSHA256': core.BASE_SHA, 'OriginalPlanSHA256': core.PLAN_SHA,
               'OriginalReportSHA256': core.REPORT_SHA, 'Request': request, 'Command': command, 'MaximumSeconds': maximum,
               'InputSHA256': {str(p): h for p, h in watched.items()}, 'HardwareAccessed': False, 'BitstreamRequested': False,
               'TimingAccepted': False, 'HardwareReleaseAllowed': False, 'ExecutionPassed': False, 'EDAExecuted': False,
               'TimedOut': False, 'StoppedForUnexpectedStage': False, 'OnlyExactRequestedPhysicalChanges': True}
    core.write_json(work / 'stage-plan.json', receipt)
    watched[work / 'stage-plan.json'] = core.sha(work / 'stage-plan.json')
    if prepare_only:
        return {'Prepared': True, 'EDAExecuted': False, 'WorkDirectory': str(work), 'Command': command}
    core.require(not core.check_inputs(watched), 'input drift before repair')
    started, process = time.monotonic(), None
    receipt['StartedUTC'] = core.utc()
    try:
        with (work / 'stdout.log').open('xb') as out, (work / 'stderr.log').open('xb') as err:
            process = subprocess.Popen(command, cwd=str(work), stdout=out, stderr=err, shell=False,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            receipt.update(EDAExecuted=True, OwnedPID=process.pid)
            while process.poll() is None:
                remaining = maximum - (time.monotonic() - started)
                if remaining <= 0:
                    receipt['TimedOut'] = True
                    core.stop_owned(process)
                    break
                try:
                    process.wait(timeout=min(2, remaining))
                except subprocess.TimeoutExpired:
                    pass
                log = (work / 'stdout.log').read_text(encoding='utf-8', errors='replace')
                if re.search(r'^Process "[^"]+" started\.', log, re.M):
                    receipt['StoppedForUnexpectedStage'] = True
                    core.stop_owned(process)
                    break
            receipt['ExitCode'] = process.poll()
    except BaseException as error:
        receipt['Error'] = type(error).__name__ + ': ' + str(error)
    finally:
        core.stop_owned(process)
    log = (work / 'stdout.log').read_text(encoding='utf-8', errors='replace') if (work / 'stdout.log').exists() else ''
    diagnostics = []
    for p in work.rglob('*.log'):
        diagnostics.extend(str(p.relative_to(work)) + ': ' + line.strip() for line in re.findall(
            r'(?m)^\s*(?:E:|F:|ERROR:|FATAL:).*$', p.read_text(encoding='utf-8', errors='replace')))
    receipt.update(FinishedUTC=core.utc(), ElapsedSeconds=round(time.monotonic() - started, 3),
        InputDrift=core.check_inputs(watched), Diagnostics=diagnostics, CompletionMarker=MARKER in log,
        ResultADFSHA256=core.sha(clone), PreSTAEqualsResultADF=(work / 'pre-sta.adf').is_file()
        and core.sha(work / 'pre-sta.adf') == core.sha(clone),
        Artifacts={p.relative_to(work).as_posix(): core.sha(p) for p in work.rglob('*') if p.is_file()
                   and p.suffix in ('.tcl', '.log', '.rtr', '.v', '.txt', '.fdc')})
    receipt['ExecutionPassed'] = (receipt.get('ExitCode') == 0 and not receipt.get('Error') and not receipt['TimedOut']
        and not receipt['StoppedForUnexpectedStage'] and not receipt['InputDrift'] and not diagnostics
        and receipt['CompletionMarker'] and receipt['PreSTAEqualsResultADF'])
    core.write_json(work / 'result.json', receipt)
    return receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--name', required=True)
    parser.add_argument('--request', type=Path, required=True)
    parser.add_argument('--maximum-seconds', type=int, default=300)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('--validate-only', action='store_true')
    modes.add_argument('--prepare-only', action='store_true')
    args = parser.parse_args(argv)
    work, maximum = core.fresh_work(core.ROOT / args.name), core.deadline(args.maximum_seconds)
    if args.validate_only:
        _, source, _, commands = prepare_request(args.request)
        print(json.dumps({'Validated': True, 'EDAExecuted': False, 'SourceADF': str(source), 'Commands': commands}))
        return 0
    result = execute(args.request, work, maximum, args.prepare_only)
    print(json.dumps({k: result[k] for k in ('Prepared', 'ExecutionPassed', 'ExitCode', 'ElapsedSeconds',
                     'Diagnostics', 'ResultADFSHA256') if k in result}), flush=True)
    return 0 if args.prepare_only or result['ExecutionPassed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
