"""Apply and prove only the current raw HDMI candidate's exact CDC/reset scope.

Native names must first be checked by a separate, source-bound read-only
inspection. Application edits one independent ADF copy; original routing and
placement must survive. A successful application is not a physical release:
fresh-process STA, export, route and IO/interstage checks remain mandatory.
"""
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time

import hdmi_camera_raw_build as build
import hdmi_camera_raw_native as native
import hdmi_camera_raw_audit as audit
import hdmi_camera_raw_reset_audit as reset
import camera720_stats_delay_reset_apply as route_semantics
import audit_camera720_reset as query_parser

SELF = Path(__file__).resolve()
TARGET = build.TARGET
SCHEMA = 'hdmi-camera-raw-physical-application-v1'
PROOF_SCHEMA = 'hdmi-camera-raw-final-physical-proof-v1'
MARKER = 'HDMI_CAMERA_RAW_EXACT_PHYSICAL_SCOPE_SAVED'
SUFFIXES = {'.tcl', '.log', '.rtr', '.txt', '.v', '.fdc', '.adf'}
require, sha, read, write = build.require, build.sha, build.read, build.write
add, merge, ref = native.add, native.merge, native.ref


def drift(watched):
    return [str(p) for p, h in watched.items() if not p.is_file() or sha(p) != h]


def semantic(value):
    return json.loads(json.dumps(value))


def bind_scope(path):
    """Recompute the proposal; imported caller modules are not scope facts."""
    path = Path(path).resolve(); saved = read(path); watched = {}
    require(saved.get('Schema') == 'hdmi-camera-raw-unapplied-physical-scope-v1'
            and saved.get('Target') == TARGET, 'current raw data scope required')
    current, _, _ = audit.derive(saved['BuildPlan']['Path'], saved['ExportReceipt']['Path'],
                                 saved['RouteReceipt']['Path'])
    # audit.local_helpers enumerates loaded modules. A verifier necessarily
    # imports additional tools; compare every actual scope fact and rebind both
    # closures instead of pretending the process-dependent inventory is fixed.
    require({k:v for k,v in semantic(current).items() if k != 'InputSHA256'} ==
            {k:v for k,v in saved.items() if k != 'InputSHA256'}, 'raw data scope recomputation differs')
    require(set(saved['InputSHA256']) <= set(current['InputSHA256']) and
            all(current['InputSHA256'][p] == h for p,h in saved['InputSHA256'].items()),
            'original scope helper closure missing or changed')
    merge(watched, saved['InputSHA256']); merge(watched, current['InputSHA256'])
    add(watched, path)
    return saved, watched


def inputs(data_path, reset_path):
    data_path, reset_path = Path(data_path).resolve(), Path(reset_path).resolve()
    scope, watched = bind_scope(data_path)
    review, bound = reset.verify(reset_path); merge(watched, bound)
    require(all(scope[k] == review[k] for k in ('BuildPlan', 'ExportReceipt', 'RouteReceipt', 'SourceADF')),
            'data and reset scopes identify different candidates')
    require(review['AuditPassed'] and review['ResetScopeVerified'] and review['RawResetEpochGuardVerified']
            and scope['ForeignDataEnableViolations'] == [] and scope['ConstraintsApplied'] is False
            and review['ConstraintsApplied'] is False, 'current raw scope is incomplete or already applied')
    source = Path(scope['SourceADF']['Path'])
    require(sha(source) == scope['SourceADF']['SHA256'], 'raw source ADF changed')
    for module in (native, audit, reset, build, route_semantics, route_semantics.routes,
                   route_semantics.separated, query_parser):
        add(watched, module.__file__)
    add(watched, SELF)
    return scope, review, watched


def selector_queries(scope, review):
    rows = []
    for s in scope['DataScopes']:
        require(s['SourceClock'] != s['DestinationClock'] and s['Targets'] == sorted(set(s['Targets']))
                and s['MaximumNS'] == audit.PERIODS[s['DestinationClock']], 'invalid raw data bound')
        pattern = '^(' + '|'.join(re.escape(p) for p in s['Targets']) + ')$'
        require(s['Query'] == 'get_pins -hierarchical -regexp {' + pattern + '}', 'raw data selector differs')
        rows.append({'Pattern':pattern, 'Targets':s['Targets']})
    for s in review['NativeQueries']:
        for pattern, names in ((s['FromRegex'], [s['Source']]), (s['ToRegex'], s['Targets'])):
            rows.append({'Pattern':pattern, 'Targets':names})
    require(rows and len({r['Pattern'] for r in rows}) == len(rows), 'duplicate or empty exact selector')
    return rows


def query_body(scope, review):
    return '\n'.join('get_pins -hierarchical -regexp {' + r['Pattern'] + '}'
                     for r in selector_queries(scope, review)) + '\n'


def exact_names(queries, log_path, repetitions=None):
    records = []
    for line in Path(log_path).read_text(encoding='utf-8-sig', errors='replace').splitlines():
        m = query_parser.MATCH.fullmatch(line)
        if not m or not m[2].startswith('get_pins '):
            continue
        pattern, command, count, names = m[1], m[2], int(m[3]), m[4].split()
        require(count == len(names) == len(set(names)), 'native selector count/list mismatch')
        prefix = 'get_pins -hierarchical -regexp '
        require(command in (prefix + pattern, prefix + '{' + pattern + '}'), 'unexpected native selector syntax')
        records.append({'Pattern':pattern, 'Count':count, 'NativeNames':names})
    proof = []
    for query in queries:
        found = [r for r in records if r['Pattern'] == query['Pattern']]
        count = 1 if repetitions is None else repetitions[query['Pattern']]
        require(len(found) == count and all(r['Count'] == len(query['Targets']) and
                set(r['NativeNames']) == {'t:' + p for p in query['Targets']} for r in found),
                'native exact selector names differ')
        proof.append(found[0])
    expected_count = len(queries) if repetitions is None else sum(repetitions.values())
    require(len(records) == expected_count, 'unexpected native pin selectors')
    return proof


def derive_application(data_path, reset_path, query_receipt):
    scope, review, watched = inputs(data_path, reset_path)
    query_receipt = Path(query_receipt).resolve()
    query, bound = native.bind_receipt(query_receipt); merge(watched, bound)
    require(query['Mode'] == 'query' and query['SourceProof'] is None
            and query['BuildPlanSHA256'] == scope['BuildPlan']['SHA256']
            and query['SourceADF'] == scope['SourceADF']['Path']
            and query['SourceADFSHA256'] == scope['SourceADF']['SHA256'], 'preflight selector inspection belongs to another source')
    body = query_body(scope, review)
    require(Path(query['QueryBody']).read_text(encoding='ascii') == body, 'preflight query body differs')
    names = exact_names(selector_queries(scope, review), query_receipt.parent/'stdout.log')
    commands = scope['UnappliedDataCommands'] + review['UnappliedResetCommands']
    require(commands and not any('set_clock_groups' in c or 'multicycle' in c for c in commands),
            'only exact current raw data/reset constraints permitted')
    facts = {'BuildPlan':scope['BuildPlan'], 'DataScope':ref(data_path), 'ResetReview':ref(reset_path),
             'PreflightQuery':ref(query_receipt), 'SourceADF':scope['SourceADF'],
             'BaselineExport':scope['ExportReceipt'], 'BaselineRoute':scope['RouteReceipt'],
             'BaselineNetlist':scope['NativeNetlist'], 'BaselineRouteDump':scope['RouteDump'],
             'NativeQueries':selector_queries(scope, review), 'ExpectedNativeNames':names,
             'ExactCommands':commands, 'QueryBody':body}
    return facts, watched


def render(work, facts):
    w = Path(work).as_posix()
    return ('set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG676\n'
            'add_design {' + w + '/dummy.v}\nif {[info script] ne {}} {\n'
            '    mpnr -input {' + w + '/input.adf}\n    ' + native.INIT + '\n'
            '    file copy {' + w + '/input.adf} {' + w + '/post-init.adf}\n'
            + facts['QueryBody'] + '\n'.join(facts['ExactCommands']) + '\n    save_adif\n'
            '    file copy {' + w + '/input.adf} {' + w + '/saved-scope.adf}\n'
            '    .switch_db -route -input {' + w + '/input.adf} -output {' + w + '/route-dump.txt}\n'
            '    puts {' + MARKER + '}\n    flush stdout\n}\n')


def prepare(data_path, reset_path, query_receipt, work):
    work = build.work_path(work); require(not work.exists(), 'fresh raw physical directory required')
    facts, watched = derive_application(data_path, reset_path, query_receipt)
    plan = build.validate(facts['BuildPlan']['Path'])
    require(not any(p.is_relative_to(work) for p in watched), 'physical output overlaps source evidence')
    work.mkdir(); shutil.copyfile(facts['SourceADF']['Path'], work/'input.adf')
    (work/'dummy.v').write_text(native.DUMMY, encoding='ascii', newline='\n')
    (work/'stage.tcl').write_text(render(work, facts), encoding='ascii', newline='\n')
    for name in ('dummy.v', 'stage.tcl'): add(watched, work/name)
    value = {'Schema':SCHEMA, 'Target':TARGET, **facts, 'WorkDirectory':str(work),
             'CreatedUTC':build.utc(), 'MaximumSeconds':300,
             'InputSHA256':{str(p):h for p,h in watched.items()},
             'Command':[plan['Command'][0], '-file', (work/'stage.tcl').as_posix(),
                        '-work_dir', work.as_posix(), '-project_name', TARGET],
             'HardwareAccessed':False, 'BitstreamRequested':False, 'TimingAccepted':False,
             'HardwareReleaseAllowed':False}
    write(work/'stage-plan.json', value)
    return work/'stage-plan.json'


def check_plan(path, fresh=False):
    path = Path(path).resolve(); work = build.work_path(path.parent); saved = read(path)
    require(path.name == 'stage-plan.json' and saved.get('Schema') == SCHEMA
            and saved.get('Target') == TARGET and saved['WorkDirectory'] == str(work), 'exact raw physical plan required')
    current, watched = derive_application(saved['DataScope']['Path'], saved['ResetReview']['Path'], saved['PreflightQuery']['Path'])
    require(all(saved.get(k) == v for k,v in current.items()), 'physical recipe changed')
    merge(watched, saved['InputSHA256'])
    plan = build.validate(saved['BuildPlan']['Path'])
    require(saved['MaximumSeconds'] == 300 and saved['Command'] ==
            [plan['Command'][0], '-file', (work/'stage.tcl').as_posix(), '-work_dir', work.as_posix(), '-project_name', TARGET],
            'raw physical command or deadline differs')
    require((work/'stage.tcl').read_text(encoding='ascii') == render(work, current)
            and (work/'dummy.v').read_text(encoding='ascii') == native.DUMMY, 'physical Tcl differs')
    for key in ('HardwareAccessed', 'BitstreamRequested', 'TimingAccepted', 'HardwareReleaseAllowed'):
        require(saved.get(key) is False, 'raw physical stage overclaims ' + key)
    if fresh:
        require(not (work/'execution-start.json').exists() and sha(work/'input.adf') == saved['SourceADF']['SHA256'],
                'fresh original ADF copy required')
    add(watched, path)
    return saved, watched


def artifacts(work):
    return {p.relative_to(work).as_posix():sha(p) for p in work.rglob('*')
            if p.is_file() and p.suffix in SUFFIXES}


def application_evidence(value, work):
    log = (work/'stdout.log').read_text(encoding='gb18030', errors='replace')
    # PDS logs get_pins inside constraint substitutions too. Every occurrence
    # is required and checked, rather than silently dropping duplicate records.
    text = value['QueryBody'] + '\n'.join(value['ExactCommands'])
    repetitions = {q['Pattern']:text.count('get_pins -hierarchical -regexp {' + q['Pattern'] + '}')
                   for q in value['NativeQueries']}
    names = exact_names(value['NativeQueries'], work/'stdout.log', repetitions)
    require(names == value['ExpectedNativeNames'], 'application selector names differ from verified preflight')
    require(sha(work/'post-init.adf') == value['SourceADF']['SHA256'], 'STA initialization changed original ADF')
    final = ref(work/'input.adf')
    require(sha(work/'saved-scope.adf') == final['SHA256'] != value['SourceADF']['SHA256'], 'scoped ADF save/readback differs')
    routes = route_semantics.compare_routes(value['BaselineRouteDump']['Path'], work/'route-dump.txt')
    require(build.events(log) == [] and MARKER in log and build.diagnostics(work) == [], 'physical native stages/logs differ')
    return {'NativeNameProof':names, 'InitializationPreservedADF':True, 'SavedADFReadbackMatches':True,
            'ResultADFChanged':True, 'ResultADF':final, 'RouteComparison':routes,
            'RoutesAndPlacementUnchanged':True, 'ConstraintsApplied':True,
            'NativeQueriesVerified':True, 'Artifacts':artifacts(work)}


def execute(path):
    value, watched = check_plan(path, True); work = Path(value['WorkDirectory'])
    require(os.name == 'nt', 'native raw physical stage requires Windows')
    result = {**value, 'StagePlanSHA256':sha(path), 'StartedUTC':build.utc(),
              'EDAExecuted':False, 'ExitCode':None, 'TimedOut':False, 'ExecutionPassed':False}
    write(work/'execution-start.json', result); process = None; start = time.monotonic()
    try:
        with (work/'stdout.log').open('xb') as out, (work/'stderr.log').open('xb') as err:
            process = subprocess.Popen(value['Command'], cwd=work, stdout=out, stderr=err, shell=False,
                                       creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            result.update(EDAExecuted=True, OwnedPID=process.pid)
            try: result['ExitCode'] = process.wait(timeout=value['MaximumSeconds'])
            except subprocess.TimeoutExpired: result['TimedOut'] = True
    except BaseException as error: result['Error'] = type(error).__name__ + ': ' + str(error)
    finally:
        result['Cleanup'] = (build.cleanup.stop_owned_tree(process, work, 'bounded exact raw CDC/reset scope')
                             if process is not None and process.poll() is None else {'Complete':True, 'ParentExited':True})
    try:
        result.update(application_evidence(value, work))
        result['InputDrift'] = drift(watched)
        result['ExecutionPassed'] = (result['ExitCode'] == 0 and result['EDAExecuted'] and not result['TimedOut']
                                      and not result.get('Error') and result['InputDrift'] == [] and result['Cleanup']['Complete'])
    except Exception as error: result['Error'] = type(error).__name__ + ': ' + str(error)
    result.update(FinishedUTC=build.utc(), ElapsedSeconds=round(time.monotonic()-start, 3))
    write(work/'result.json', result)
    return result


def bind_application(path):
    path = Path(path).resolve(); work = build.work_path(path.parent); saved = read(path)
    plan, watched = check_plan(work/'stage-plan.json')
    require(path.name == 'result.json' and all(saved.get(k) == v for k,v in plan.items())
            and saved.get('ExecutionPassed') is True and saved.get('EDAExecuted') is True
            and saved.get('ExitCode') == 0 and saved.get('TimedOut') is False and not saved.get('Error')
            and saved.get('InputDrift') == [] and saved.get('Cleanup', {}).get('Complete') is True
            and saved['StagePlanSHA256'] == sha(work/'stage-plan.json'), 'unclean raw physical application')
    evidence = application_evidence(plan, work)
    require(all(saved.get(k) == v for k,v in evidence.items()), 'raw physical receipt evidence changed')
    for name,h in evidence['Artifacts'].items(): add(watched, work/name, h)
    add(watched, path)
    return saved, watched


def summaries(path):
    with Path(path).open(encoding='utf-8-sig') as stream: return audit.timing.parse_summaries(stream)


def artifact(receipt_path, value, name):
    found = [Path(receipt_path).parent/n for n in value['Artifacts']
             if Path(n).name == name and 'report_path_timing' not in Path(n).parts]
    require(len(found) == 1, 'one receipt-bound native artifact required: ' + name)
    return found[0]


def all_ten_pass(tables):
    require(set(tables) == {(c,k) for c in ('slow','fast') for k in audit.timing.KINDS}, 'ten current native tables required')
    require(all(rows for rows in tables.values()), 'empty native timing table')
    for key, rows in tables.items():
        for pair,row in rows.items():
            require(row['FailingChecks'] == 0 and row['WorstSlackNS'] >= 0 and row['TotalNegativeSlackNS'] == 0,
                    'unresolved native timing failure: ' + str((key,pair)))


def exception_paths(path):
    """Keep every exception section and complete native path body, not counts."""
    sections = {}; kind = corner = None; block = None
    def finish():
        nonlocal block
        if block is None: return
        text = ''.join(block)
        require(any(s.startswith(' Slack') for s in block), 'truncated native exception path')
        def one(pattern):
            found = re.findall(pattern, text, re.M); require(len(found) == 1, 'incomplete native exception path')
            return found[0]
        row = {'Source':one(r'^Startpoint\s*:\s*(\S+)\s*$'), 'Endpoint':one(r'^Endpoint\s*:\s*(\S+)\s*$'),
               'Corner':one(r'^Path Type\s*:\s*(?:max|min) \((slow|fast) corner\)\s*$'),
               'Exception':one(r'^Timing Exception\s*:\s*(.+?)\s*$'),
               'Body':'\n'.join(' '.join(s.split()) for s in block if s.strip() and not set(s.strip()) <= set('-='))}
        require(row['Corner'] == corner, 'exception corner differs from section')
        sections[(corner,kind)].append(row); block = None
    for line in Path(path).open(encoding='utf-8-sig'):
        m = re.fullmatch(r'\| Exception type\s*:\s*(\S+)\s*\n?', line)
        if m:
            finish(); kind = m[1]; corner = None; continue
        m = re.fullmatch(r'\| (Slow|Fast) Corner\s*\n?', line)
        if m:
            corner=m[1].lower(); require(kind is not None and (corner,kind) not in sections, 'duplicate exception section')
            sections[(corner,kind)] = []; continue
        if line.startswith('Startpoint'):
            finish(); require(corner is not None, 'exception path outside section'); block=[line]
        elif block is not None:
            block.append(line)
            if line.startswith(' Slack'): finish()
    finish()
    expected = {(c,f'{s}({k})') for c in ('slow','fast') for s,kinds in
                (('set_max_delay',('setup','recovery')),('set_min_delay',('hold','removal')),
                 ('set_multicycle_path',('setup','hold','recovery','removal')),
                 ('set_false_path',('setup','hold','recovery','removal'))) for k in kinds}
    require(set(sections) == expected, 'complete native exception sections required')
    return sections


def validate_exceptions(scope, review, path):
    sections = exception_paths(path)
    allowed = {(r['SourceNativeClockPin'],b['Endpoint']):audit.PERIODS[r['DestinationClock']]
               for r in scope['ForeignDataEnableRelationships'] for b in r['NativeBoundaries']}
    reset_pairs = {(q['Source'],t) for q in review['NativeQueries'] for t in q['Targets']}
    counts = {}
    for (corner,kind),rows in sections.items():
        pairs = set()
        for row in rows:
            pair = row['Source'],row['Endpoint']; pairs.add(pair)
            if kind == 'set_max_delay(setup)':
                require(pair in allowed, 'unexpected maximum-delay path')
                m = re.fullmatch(r'MaxDelay Path ([0-9.]+)ns -datapath_only', row['Exception'])
                require(m is not None and abs(float(m[1])-allowed[pair]) <= 0.00051, 'maximum-delay budget differs')
                require('Slack (MET)' in row['Body'], 'maximum-delay path does not meet bound')
            elif kind == 'set_false_path(hold)':
                require(pair in allowed and row['Exception'] == 'False Path', 'unexpected data hold exception')
            elif kind in ('set_false_path(recovery)', 'set_false_path(removal)'):
                require(pair in reset_pairs and row['Exception'] == 'False Path', 'unexpected async reset exception')
            else: require(False, 'unapproved native exception type: ' + kind)
        expected = (set(allowed) if kind in ('set_max_delay(setup)','set_false_path(hold)') else
                    reset_pairs if kind in ('set_false_path(recovery)','set_false_path(removal)') else set())
        require(pairs == expected, 'missing native exception source/endpoint coverage: ' + str((corner,kind,len(pairs),len(expected))))
        counts[corner+'_'+kind] = {'Paths':len(rows), 'UniquePairs':len(pairs)}
    return counts


def compare_fresh_sta(proof, report, exceptions):
    current, clocks = summaries(report); original, old_clocks = summaries(proof['FreshSTAReport']['Path'])
    all_ten_pass(current)
    require(current == original and clocks == old_clocks, 'fresh STA summaries or clocks changed')
    require(exception_paths(exceptions) == exception_paths(proof['FreshSTAExceptions']['Path']),
            'fresh native exception paths changed')
    return {'STAAllTenPassed':True, 'ClockAndSummaryIdentityPreserved':True, 'AllExceptionPathsPreserved':True}


def native_warning_review(scope, stages, watched):
    """Only the declared diagnostic external-AC limitations survive native STA."""
    directions = {r['Port']:r['DIRECTION'] for r in scope['Pins']['PinInventory']}
    rows = []
    pattern = re.compile(r"W: Timing-(4086|4087): Port '([^']+)' is not constrained, it is treated as combinational (input|output)\.")
    for stage in sorted({Path(p).resolve() for p in stages},key=str):
        for path in sorted(stage.rglob('*.log')):
            add(watched,path)
            for number,line in enumerate(path.read_text(encoding='gb18030',errors='strict').splitlines(),1):
                if not line.lstrip().startswith('W:'): continue
                m = pattern.fullmatch(line.strip())
                require(m is not None, 'unreviewed final native warning: ' + line)
                code,port,direction = m.groups()
                require(port in directions and direction == ('input' if code == '4086' else 'output')
                        and directions[port] in (direction.upper(),'INOUT'), 'external-AC warning port/direction differs')
                rows.append({'Log':str(path),'Line':number,'Code':'Timing-'+code,'Port':port,
                             'Direction':direction,'Text':line})
    return {'Passed':True,'Warnings':rows,'Counts':dict(Counter(r['Code'] for r in rows)),
            'OnlyDeclaredPortExternalACWarnings':True,'ExternalACAccepted':False,
            'Disposition':'Only input/output external AC is unaccepted for this digital activity diagnostic; no internal timing or synthesis warning is waived.'}


def final_facts(application, export_receipt, route_receipt, query_receipts):
    app, watched = bind_application(application)
    scope, review, bound = inputs(app['DataScope']['Path'], app['ResetReview']['Path']); merge(watched,bound)
    receipts = []
    for path, mode in ((export_receipt,'export'), (route_receipt,'report')):
        value,bound = native.bind_receipt(path); merge(watched,bound)
        require(value['Mode'] == mode and value['SourceProof'] == ref(application)
                and value['SourceADF'] == app['ResultADF']['Path']
                and value['SourceADFSHA256'] == app['ResultADF']['SHA256']
                and value['BuildPlanSHA256'] == app['BuildPlan']['SHA256'], 'final native evidence uses another application')
        receipts.append(value)
    exported,routed = receipts
    net = Path(export_receipt).parent/'generate_netlist'/(TARGET+'_sim.v')
    old_graph = audit.graph(Path(app['BaselineNetlist']['Path']).read_text(encoding='utf-8-sig'))
    new_graph = audit.graph(net.read_text(encoding='utf-8-sig'))
    require(old_graph.cells == new_graph.cells, 'final functional primitive graph changed')
    old_text = Path(app['BaselineNetlist']['Path']).read_text(encoding='utf-8-sig')
    new_text = net.read_text(encoding='utf-8-sig')
    placements = audit.cdc.clm.placed_luts
    require(placements(old_text, old_graph) == placements(new_text, new_graph), 'final LUT placement changed')
    # Native functional parser includes every FF site/attributes in its value.
    old_value = audit.algorithms.structure.functional(re.sub(r'(?m)^(module\s+)'+TARGET+r'\b',
                         r'\g<1>'+audit.algorithms.structure.prep.TARGET,old_text,count=1))
    new_value = audit.algorithms.structure.functional(re.sub(r'(?m)^(module\s+)'+TARGET+r'\b',
                         r'\g<1>'+audit.algorithms.structure.prep.TARGET,new_text,count=1))
    require(old_value == new_value, 'final declarations, graph or FF placement changed')
    routes = route_semantics.compare_routes(app['BaselineRouteDump']['Path'], Path(route_receipt).parent/'route-dump.txt')
    report = Path(export_receipt).parent/'report_timing'/(TARGET+'.rtr')
    exceptions = report.with_name(TARGET+'_exception.rtr')
    tables,clocks = summaries(report); all_ten_pass(tables)
    rt,rc = summaries(artifact(route_receipt, routed, TARGET+'.rtr'))
    require(tables == rt and clocks == rc, 'independent final native summaries differ')
    exception_counts = validate_exceptions(scope, review, exceptions)
    import hdmi_camera_raw_physical_checks as checks
    checked,bound = checks.derive(scope, export_receipt, query_receipts); merge(watched,bound)
    require(checked['Pins']['NativeElectricalParametersVerified'] is True
            and checked['CDC']['InterstageTimingAccepted'] is True, 'final pin/interstage checks incomplete')
    # Fresh native stages reject every critical/error diagnostic; reviewed
    # synthesis truncations must additionally bind the explicit diagnostics audit.
    import hdmi_camera_raw_diagnostics as diagnostics
    diagnostics_path = Path(app['BuildPlan']['Path']).parent.parent/'diagnostics-c.json'
    diagnostic_value,bound = diagnostics.verify(diagnostics_path); merge(watched,bound)
    require(diagnostic_value['BuildPlan'] == app['BuildPlan'] and diagnostic_value['Passed'] is True
            and diagnostic_value['NativeWarningsReviewed'] is True, 'current raw diagnostic review not accepted')
    for helper in (checks,diagnostics): add(watched,helper.__file__)
    add(watched,diagnostics_path)
    warning_review = native_warning_review(scope,
        [Path(p).parent for p in (application, app['PreflightQuery']['Path'], app['BaselineExport']['Path'],
          app['BaselineRoute']['Path'], export_receipt, route_receipt, *query_receipts)], watched)
    result = {'Schema':PROOF_SCHEMA, 'Target':TARGET, 'Passed':True,
              'BuildPlan':app['BuildPlan'], 'Application':ref(application), 'FinalADF':app['ResultADF'],
              'FinalExport':ref(export_receipt), 'FinalRoute':ref(route_receipt),
              'FinalQueries':[ref(p) for p in query_receipts], 'FreshSTAReport':ref(report),
              'FreshSTAExceptions':ref(exceptions), 'STAAllTenPassed':True, 'NativeWarningsReviewed':True,
              'NetlistEquivalent':True, 'AllFFPlacementsEquivalent':True, 'RoutesUnchanged':True,
              'ResetAccepted':True, **checked, 'ExceptionCoverage':exception_counts, 'RouteComparison':routes,
              'NativeWarningReview':warning_review,
              'DiagnosticReview':ref(diagnostics_path), 'HardwareAccessed':False, 'ExternalACAccepted':False,
              'PixelsVerified':False, 'HardwareReleaseAllowed':False,
              'Limits':'Own150MHz internal diagnostic only. Synthetic output bars; no HDMI input pixel, external AC or analog MTBF acceptance.'}
    for p in (net, report, exceptions): add(watched,p)
    for p in audit.local_helpers(): add(watched,p)
    result['InputSHA256'] = {str(p):h for p,h in watched.items()}
    return result,watched


def verify(path):
    path = Path(path).resolve(); saved = read(path)
    require(saved.get('Schema') == PROOF_SCHEMA and saved.get('Target') == TARGET, 'current raw final proof required')
    actual,watched = final_facts(saved['Application']['Path'], saved['FinalExport']['Path'],
                                 saved['FinalRoute']['Path'], [p['Path'] for p in saved['FinalQueries']])
    require({k:v for k,v in semantic(actual).items() if k != 'InputSHA256'} ==
            {k:v for k,v in saved.items() if k != 'InputSHA256'}, 'final raw physical proof recomputation differs')
    require(set(saved['InputSHA256']) <= set(actual['InputSHA256']) and
            all(actual['InputSHA256'][p] == h for p,h in saved['InputSHA256'].items()),
            'saved final physical helper closure missing or changed')
    merge(watched,saved['InputSHA256'])
    add(watched,path)
    return saved,watched


def main():
    parser=argparse.ArgumentParser(description=__doc__); modes=parser.add_subparsers(dest='mode',required=True)
    query=modes.add_parser('query'); prepare_p=modes.add_parser('prepare')
    for p in (query,prepare_p):
        p.add_argument('--data-scope',type=Path,required=True); p.add_argument('--reset-review',type=Path,required=True)
    query.add_argument('--output',type=Path,required=True)
    prepare_p.add_argument('--query-receipt',type=Path,required=True); prepare_p.add_argument('--work-dir',type=Path,required=True)
    execute_p=modes.add_parser('execute'); execute_p.add_argument('--plan',type=Path,required=True)
    prove=modes.add_parser('prove')
    for name in ('application','export-receipt','route-receipt','output'):
        prove.add_argument('--'+name,type=Path,required=True)
    prove.add_argument('--query-receipt',type=Path,action='append',required=True)
    check=modes.add_parser('verify'); check.add_argument('--proof',type=Path,required=True)
    args=parser.parse_args()
    if args.mode=='query':
        scope,review,_=inputs(args.data_scope,args.reset_review)
        with args.output.open('x',encoding='ascii',newline='\n') as stream:stream.write(query_body(scope,review))
        print(json.dumps({'Prepared':True,'QueryBody':str(args.output.resolve())}));return 0
    if args.mode=='prepare':
        plan=prepare(args.data_scope,args.reset_review,args.query_receipt,args.work_dir)
        print(json.dumps({'Prepared':True,'Plan':str(plan)}));return 0
    if args.mode=='execute':
        value=execute(args.plan);print(json.dumps({k:value.get(k) for k in ('ExecutionPassed','ElapsedSeconds','Error')}))
        return 0 if value['ExecutionPassed'] else 1
    if args.mode=='prove':
        value,_=final_facts(args.application,args.export_receipt,args.route_receipt,args.query_receipt)
        write(args.output,value);print(json.dumps({'Passed':True,'Proof':str(args.output.resolve())}));return 0
    verify(args.proof);print('{"Verified":true}');return 0


if __name__=='__main__':raise SystemExit(main())
