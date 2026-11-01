"""Apply only a proved upright reset scope to a fresh diagnostic ADF copy.

One native STA initialization precedes exact reset constraints and save_adif.
There is deliberately no second STA, route edit, arbitrary Tcl or hardware.
Saved bytes are checked; constraint effects require a later separate audit.
"""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time

import run_raw_camera_reset_inspect as inspect
import audit_raw_camera_reset as audit

prep, diagnostic = inspect.prep, inspect.diagnostic
require, sha = prep.require, prep.sha
SELF = Path(__file__).resolve()
SCHEMA = 'raw-camera-diagnostic-reset-application-v1'
MARKER = 'RAW_CAMERA_RESET_SAVED'
INIT = 'mpnr_report_timing -force_to_run -delay_type min_max -max_path 20 -nworst 4 -report_exception TRUE'
DUMMY = 'module physical_dummy(input a, output y); assign y=a; endmodule\n'
PROOF_TRUE = ('Complete', 'ScopeAuditPassed', 'NativeQueriesVerified', 'EntryConnectivityVerified',
              'InternalConnectivityVerified', 'VendorSameConfigurationVerified', 'ReportNativeADFBindingVerified')
PROOF_FALSE = ('ConstraintsApplied', 'TimingExceptionApproved', 'TimingAccepted', 'CDCPhysicalAccepted',
               'HardwareAccessed', 'HardwareReleaseAllowed', 'EDAExecuted', 'HistoricalEndpointInventoryUsed')


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def digest(value):
    return isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value) is not None


def add(watched, path, expected=None, pds=None):
    path = Path(path).absolute()
    require(path == path.resolve() and path.is_file() and
            (path.is_relative_to(prep.PROJECT.parent) or path == pds), 'input escapes repository/PDS scope')
    actual = sha(path)
    require(expected is None or digest(expected) and expected == actual, 'input hash differs: '+str(path))
    require(path not in watched or watched[path] == actual, 'conflicting input identity')
    watched[path] = actual
    return path


def binding(value, watched, pds=None):
    require(isinstance(value, dict) and set(value) == {'Path', 'SHA256'} and digest(value['SHA256']),
            'exact Path/SHA256 binding required')
    return add(watched, value['Path'], value['SHA256'], pds)


def proof_flags(proof):
    require(proof.get('Schema') == audit.PROOF_SCHEMA and proof.get('Target') == prep.TARGET
            and proof.get('Status') == 'pass', 'wrong upright reset proof identity')
    for key in PROOF_TRUE:
        require(proof.get(key) is True, 'unproved reset scope: '+key)
    for key in PROOF_FALSE:
        require(proof.get(key) is False, 'proof exceeds unapplied diagnostic scope: '+key)


def graph_semantics(actual, claimed):
    # JSON evidence serializes integer LUT input keys as strings. Compare the
    # exact serialized structure, without discarding any graph/property field.
    require(json.loads(json.dumps(actual)) == claimed, 'actual raw reset graph differs from proof')


def exact_commands(queries):
    require(isinstance(queries, list) and queries, 'empty reset query inventory')
    seen, commands = set(), []
    for row in queries:
        source, targets = row['Source'], row['Targets']
        require(isinstance(source, str) and isinstance(targets, list) and targets
                and all(isinstance(n, str) for n in targets), 'invalid native reset names')
        require(source not in seen and targets == sorted(set(targets)), 'duplicate/unsorted reset inventory')
        seen.add(source)
        for name in [source, *targets]:
            require(audit.scope.SAFE.fullmatch(name) and all(p not in ('', '.', '..') for p in name.split('/')),
                    'unsafe native reset pin name')
        patterns = ['^('+'|'.join(re.escape(n) for n in names)+')$' for names in ([source], targets)]
        require(row['FromRegex'] == patterns[0] and row['ToRegex'] == patterns[1]
                and row['ExpectedFromCount'] == 1 and type(row['ExpectedFromCount']) is int
                and row['ExpectedTargetCount'] == len(targets) and type(row['ExpectedTargetCount']) is int
                and row['ExpectedNativeFromNames'] == ['t:'+source]
                and row['ExpectedNativeToNames'] == ['t:'+n for n in targets], 'reset regex/names/counts are not exact')
        commands.append('set_false_path -from [get_pins -hierarchical -regexp {'+patterns[0]
                        +'}] -to [get_pins -hierarchical -regexp {'+patterns[1]+'}]')
    return commands


def bind_proof(build_plan, proof_path, proof_sha):
    proof_path = inspect.canonical(proof_path, prep.WORK)
    require(proof_path.name == 'proof.json' and proof_path.parent.parent == prep.WORK, 'exact fresh proof location required')
    require(digest(proof_sha) and sha(proof_path) == proof_sha, 'explicit proof SHA differs')
    proof = read(proof_path); proof_flags(proof)
    source = Path(proof['SourceADF']).absolute(); source_sha = proof['SourceADFSHA256']
    plan, watched = inspect.bind(build_plan, source, source_sha)
    pds = Path(plan['PDS']['Executable'])
    add(watched, proof_path, proof_sha)
    for key in ('InputSHA256', 'ToolSHA256'):
        require(isinstance(proof.get(key), dict) and proof[key], 'proof hash inventory missing: '+key)
        for name, expected in proof[key].items():
            if key == 'ToolSHA256':
                require(proof['InputSHA256'].get(name) == expected and Path(name).suffix == '.py', 'unbound proof tool')
            add(watched, name, expected, pds)
    require(proof['ToolSHA256'].get(str(audit.SELF)) == sha(audit.SELF), 'current reset auditor is not proof-bound')
    require(set(proof.get('FilesSHA256', {})) == {'current-recovery-inventory.json', 'proposed-scope.fdc'},
            'proof payload inventory differs')
    for name, expected in proof['FilesSHA256'].items():
        add(watched, proof_path.parent/name, expected)
    scope_path = binding(proof['ScopePlan'], watched, pds); scope_plan = read(scope_path)
    require(scope_plan.get('Schema') == audit.PLAN_SCHEMA and scope_plan.get('Target') == prep.TARGET
            and Path(scope_plan['BuildPlan']).absolute() == Path(build_plan).absolute()
            and scope_plan['SourceADF'] == str(source) and scope_plan['SourceADFSHA256'] == source_sha,
            'proof scope belongs to a different build/ADF')
    report = proof['CurrentReport']; net = proof['CurrentNetlist']
    report_path = add(watched, report['Path'], report['SHA256'], pds)
    net_path = add(watched, net['Path'], net['SHA256'], pds)
    require(net_path.stat().st_size == net['Bytes'], 'native netlist size differs')
    # Re-derive current inventory and FDC from raw evidence, not pass booleans.
    inventory, adapter = audit.inventory(report_path)
    queries, body, fdc_text = audit.scope.query_scope(inventory)
    require(read(proof_path.parent/'current-recovery-inventory.json') == inventory
            and proof['NativeQueries'] == queries and scope_plan['NativeQueries'] == queries
            and proof['ReportAdapter'] == adapter, 'actual report inventory differs from proof')
    require(all(proof.get(k) == v for k, v in audit.summary(inventory).items()), 'proof summary differs from current report')
    require(proof['UniqueSourceEndpointPairs'] == sum(len(q['Targets']) for q in queries), 'proof pair count differs')
    fdc = proof_path.parent/'proposed-scope.fdc'
    require(fdc.read_bytes() == fdc_text.encode('utf-8'), 'proof FDC bytes differ from current report derivation')
    commands = exact_commands(queries)
    require([s for s in fdc_text.splitlines() if s and not s.startswith('#')] == commands, 'FDC has unexpected commands')
    # Both query and export must be clean native inspections of this exact ADF.
    query_paths = []
    for name in proof['InputSHA256']:
        path = Path(name)
        if path.name == 'result.json' and path.parent.parent == prep.WORK:
            value = read(path)
            if value.get('Schema') == inspect.SCHEMA and value.get('Mode') == 'query':
                query_paths.append(path)
    require(len(query_paths) == 1, 'exactly one bound native reset query required')
    query_path = query_paths[0]
    query = audit.inspection_receipt(query_path, 'query', build_plan, source, source_sha, watched)
    export_path = net_path.parent.parent/'result.json'
    export = audit.inspection_receipt(export_path, 'export', build_plan, source, source_sha, watched)
    require(export['Netlist'] == net and export.get('NativeNetlistWithFFloc') is True, 'native export binding differs')
    actual_commands = inspect.query_commands(Path(query['QueryBody']).read_text(encoding='ascii'))
    scope_commands = inspect.query_commands(body)
    require(actual_commands[:len(scope_commands)] == scope_commands and
            all(c.startswith(('show -design_net ', '.switch_db ', 'dump_net ', 'puts '))
                for c in actual_commands[len(scope_commands):]), 'executed reset queries differ')
    names = audit.exact_queries(queries, query_path.parent/'stdout.log')
    require(names == proof['NativeNameProof'], 'native reset names differ from proof')
    bound_reports = [str(p) for p, v in ((query_path, query), (export_path, export))
                     if report_path.is_relative_to(p.parent)
                     and v['Artifacts'].get(report_path.relative_to(p.parent).as_posix()) == report['SHA256']]
    require(bound_reports == [report['Receipt']], 'current report is not uniquely receipt-bound')
    actual_graph = audit.graph.audit_text(audit.adapt_netlist(net_path.read_text(encoding='utf-8-sig')), queries)
    graph_semantics(actual_graph, proof['ResetGraph'])
    vendor = audit.vendor_provenance(proof['VendorProvenance']['SourceReference']['Path'], watched)
    require(vendor == proof['VendorProvenance'], 'same-config vendor provenance differs')
    audit.watch_tools(watched)
    for module in (inspect, diagnostic, diagnostic.cleanup):
        add(watched, module.__file__)
    add(watched, SELF)
    require(not inspect.drift(watched), 'raw proof/build input drift')
    return plan, source, proof, fdc, commands, watched


def render(commands, work):
    # Commands come only from bind_proof; callers cannot supply a native body.
    aw = work.as_posix()
    return ('set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG676\n'
            'add_design {'+aw+'/dummy.v}\nif {[info script] ne {}} {\n'
            '    mpnr -input {'+aw+'/input.adf}\n    '+INIT+'\n'
            '    file copy {'+aw+'/input.adf} {'+aw+'/post-init.adf}\n'
            +'\n'.join(commands)+'\n    save_adif\n'
            '    file copy {'+aw+'/input.adf} {'+aw+'/saved-reset.adf}\n'
            '    puts {'+MARKER+'}\n    flush stdout\n}\n')


def recipe(build_plan, proof_path, proof_sha, work, maximum=300):
    work = prep.work_path(work)
    require(type(maximum) is int and 120 <= maximum <= 300, 'native bound must be 120..300 seconds')
    plan, source, proof, fdc, commands, watched = bind_proof(build_plan, proof_path, proof_sha)
    require(work not in [p.parent for p in watched], 'output would overlap a bound evidence directory')
    tcl = render(commands, work)
    value = {'Schema':SCHEMA, 'Target':prep.TARGET, 'Mode':'save-reset', 'WorkDirectory':str(work),
        'BuildPlan':str(Path(build_plan).absolute()), 'BuildPlanSHA256':sha(build_plan),
        'ResetProof':{'Path':str(Path(proof_path).absolute()), 'SHA256':proof_sha},
        'ResetFDC':{'Path':str(fdc), 'SHA256':sha(fdc)},
        'NativeQueries':proof['NativeQueries'],
        'SourceADF':str(source), 'SourceADFSHA256':proof['SourceADFSHA256'],
        'MaximumSeconds':maximum, 'ExpectedActualStages':[], 'ExactResetCommands':commands,
        'InputSHA256':{str(p):h for p,h in watched.items()},
        'TclSHA256':prep.baseline.paths.sha_bytes(tcl.encode('ascii')),
        'Command':[plan['PDS']['Executable'], '-file', (work/'stage.tcl').as_posix(),
                   '-work_dir', work.as_posix(), '-project_name', prep.TARGET],
        'HardwareAccessed':False, 'BitstreamRequested':False, 'TimingExceptionApproved':False,
        'TimingAccepted':False, 'HardwareReleaseAllowed':False, 'AppliedScopeReadbackVerified':False,
        'FinalSTAExecuted':False, 'DiagnosticCopyOnly':True,
        'Limits':'Only an explicitly requested diagnostic-copy application. Saved bytes are not proof of exception effects or timing closure; separate fresh-process STA/export and audits remain required.'}
    return value, tcl, watched


def prepare(*args, **kwargs):
    value, tcl, watched = recipe(*args, **kwargs)
    work = Path(value['WorkDirectory'])
    require(not work.exists() and not inspect.drift(watched), 'fresh directory and stable inputs required')
    work.mkdir()
    shutil.copyfile(value['SourceADF'], work/'input.adf')
    require(sha(work/'input.adf') == value['SourceADFSHA256'], 'diagnostic ADF copy differs')
    shutil.copyfile(value['ResetFDC']['Path'], work/'applied-scope.fdc')
    shutil.copyfile(SELF, work/'executor-snapshot.py')
    (work/'stage.tcl').write_text(tcl, encoding='ascii', newline='\n')
    (work/'dummy.v').write_text(DUMMY, encoding='ascii', newline='\n')
    value['PreparedUTC'] = prep.utc()
    diagnostic.write(work/'stage-plan.json', value)
    return work/'stage-plan.json'


def validate_prepared(path):
    path = inspect.canonical(path, prep.WORK); work = prep.work_path(path.parent)
    require(path.name == 'stage-plan.json', 'exact stage-plan.json required')
    value = read(path)
    require(value.get('Schema') == SCHEMA and value.get('Mode') == 'save-reset', 'unsupported physical stage')
    proof = value['ResetProof']
    expected, tcl, watched = recipe(value['BuildPlan'], proof['Path'], proof['SHA256'], work, value['MaximumSeconds'])
    require(set(value) == set(expected)|{'PreparedUTC'} and isinstance(value['PreparedUTC'], str) and value['PreparedUTC']
            and {k:v for k,v in value.items() if k != 'PreparedUTC'} == expected, 'physical plan differs from bound recipe')
    files = {'stage-plan.json', 'stage.tcl', 'dummy.v', 'input.adf', 'applied-scope.fdc', 'executor-snapshot.py'}
    require({p.name for p in work.iterdir()} == files, 'prepared stage reused or contaminated')
    require((work/'stage.tcl').read_bytes() == tcl.encode('ascii') and (work/'dummy.v').read_bytes() == DUMMY.encode('ascii')
            and sha(work/'input.adf') == value['SourceADFSHA256']
            and sha(work/'applied-scope.fdc') == value['ResetFDC']['SHA256']
            and sha(work/'executor-snapshot.py') == sha(SELF), 'prepared stage artifact drift')
    # The clone is intentionally mutable; all source evidence and stage instructions remain watched.
    for name in files-{'input.adf'}:
        add(watched, work/name)
    require(not inspect.drift(watched), 'physical stage input drift')
    return value, watched


def execution_ok(result):
    return (result.get('ExitCode') == 0 and not result.get('Error') and result.get('EDAExecuted') is True
            and result.get('TimedOut') is False and result.get('StoppedForUnexpectedStage') is False
            and result.get('InputDrift') == [] and result.get('Diagnostics') == [] and result.get('ActualEvents') == []
            and result.get('CompletionMarker') is True and result.get('InitializationPreservedADF') is True
            and result.get('ApplicationNativeNamesVerified') is True
            and result.get('SavedADFReadbackMatches') is True and result.get('ResultADFChanged') is True
            and result.get('Cleanup', {}).get('Complete') is True)


def execute(path):
    value, watched = validate_prepared(path)
    require(os.name == 'nt', 'native physical stage requires Windows')
    work = Path(value['WorkDirectory'])
    result = {**value, 'StagePlanSHA256':sha(path), 'StartedUTC':prep.utc(), 'EDAExecuted':False,
              'ExecutionPassed':False, 'TimedOut':False, 'StoppedForUnexpectedStage':False, 'ExitCode':None}
    diagnostic.write(work/'execution-start.json', result)
    process = None; started = time.monotonic()
    try:
        with (work/'stdout.log').open('xb') as out, (work/'stderr.log').open('xb') as err:
            process = subprocess.Popen(value['Command'], cwd=work, stdout=out, stderr=err, shell=False,
                                       creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            result.update(EDAExecuted=True, OwnedPID=process.pid)
            while process.poll() is None:
                remaining = value['MaximumSeconds']-(time.monotonic()-started)
                if remaining <= 0:
                    result['TimedOut'] = True; break
                try:
                    process.wait(timeout=min(2, remaining))
                except subprocess.TimeoutExpired:
                    pass
                if diagnostic.stage_events((work/'stdout.log').read_text(encoding='gb18030', errors='replace')):
                    result['StoppedForUnexpectedStage'] = True; break
    except BaseException as error:
        result['Error'] = type(error).__name__+': '+str(error)
    finally:
        if process is not None:
            if process.poll() is None:
                result['Cleanup'] = diagnostic.cleanup.stop_owned_tree(process, work, 'bounded upright reset save')
            else:
                result['Cleanup'] = {'Complete':True, 'OwnedPID':process.pid, 'ParentExited':True,
                                     'DescendantLivenessIndependentlyVerified':False}
            result['ExitCode'] = process.poll()
        else:
            result['Cleanup'] = {'Complete':True, 'Required':False}
    try:
        log = (work/'stdout.log').read_text(encoding='gb18030', errors='replace') if (work/'stdout.log').exists() else ''
        diagnostics = []
        for p in work.rglob('*.log'):
            diagnostics += [p.relative_to(work).as_posix()+': '+s.strip() for s in re.findall(
                r'(?m)^\s*(?:E:|F:|ERROR:|FATAL:|Traceback).*$', p.read_text(encoding='gb18030', errors='replace'))]
        adfs = {}
        for name in ('input.adf', 'post-init.adf', 'saved-reset.adf'):
            p = work/name
            if p.is_file() and p == p.resolve():
                adfs[name] = {'Path':str(p), 'SHA256':sha(p), 'Bytes':p.stat().st_size}
        final_sha = adfs.get('input.adf', {}).get('SHA256')
        application_names = []
        try:
            application_names = audit.exact_queries(value['NativeQueries'], work/'stdout.log')
            result['ApplicationNativeNamesVerified'] = True
        except (ValueError, OSError) as error:
            result['ApplicationNativeNamesVerified'] = False
            result['ApplicationNativeNameError'] = type(error).__name__+': '+str(error)
        result.update(ActualEvents=diagnostic.stage_events(log), InputDrift=inspect.drift(watched), Diagnostics=diagnostics,
            CompletionMarker=MARKER in log, ADFReadback=adfs, ResultADF=adfs.get('input.adf'), ResultADFSHA256=final_sha,
            ApplicationNativeNameProof=application_names,
            InitializationPreservedADF=adfs.get('post-init.adf', {}).get('SHA256') == value['SourceADFSHA256'],
            SavedADFReadbackMatches=bool(final_sha) and adfs.get('saved-reset.adf', {}).get('SHA256') == final_sha,
            ResultADFChanged=bool(final_sha) and final_sha != value['SourceADFSHA256'],
            Artifacts={p.relative_to(work).as_posix():sha(p) for p in work.rglob('*') if p.is_file()
                       and p.suffix in ('.tcl', '.log', '.rtr', '.v', '.fdc', '.adf', '.py', '.json')})
    except Exception as error:
        result['ReadbackError'] = type(error).__name__+': '+str(error)
        result['Error'] = result.get('Error', result['ReadbackError'])
    result.update(FinishedUTC=prep.utc(), ElapsedSeconds=round(time.monotonic()-started, 3))
    result['ExecutionPassed'] = execution_ok(result)
    result['ConstraintsAppliedToDiagnosticCopy'] = result['ExecutionPassed']
    diagnostic.write(work/'result.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build-plan', type=Path); parser.add_argument('--proof', type=Path)
    parser.add_argument('--proof-sha256'); parser.add_argument('--name')
    parser.add_argument('--maximum-seconds', type=int, default=300); parser.add_argument('--stage-plan', type=Path)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('--validate-only', action='store_true'); modes.add_argument('--prepare-only', action='store_true')
    modes.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    if args.stage_plan:
        require(not any((args.build_plan, args.proof, args.proof_sha256, args.name, args.prepare_only)), 'stage-plan cannot be mixed with preparation inputs')
        if args.execute:
            result = execute(args.stage_plan)
        else:
            validate_prepared(args.stage_plan); result = {'Validated':True, 'StagePlan':str(args.stage_plan), 'EDAExecuted':False}
    else:
        require(args.build_plan and args.proof and args.proof_sha256 and args.name, 'build plan, proof, proof hash and fresh name required')
        inputs = (args.build_plan, args.proof, args.proof_sha256, prep.WORK/args.name, args.maximum_seconds)
        if args.prepare_only or args.execute:
            path = prepare(*inputs)
            result = execute(path) if args.execute else {'Prepared':True, 'StagePlan':str(path), 'EDAExecuted':False}
        else:
            recipe(*inputs); result = {'Validated':True, 'EDAExecuted':False}
    print(json.dumps({k:result[k] for k in ('Prepared', 'Validated', 'StagePlan', 'ExecutionPassed', 'ExitCode',
          'ElapsedSeconds', 'InputDrift', 'Diagnostics', 'ResultADFSHA256', 'EDAExecuted') if k in result}))
    return 0 if result.get('ExecutionPassed', True) else 1


if __name__ == '__main__':
    raise SystemExit(main())
