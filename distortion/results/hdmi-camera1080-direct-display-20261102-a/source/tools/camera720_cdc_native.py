"""CPU-only launch-qualified CDC evidence and bounded missing-path query plans.

A packed CLK may launch multiple FF outputs. Only an actual tco row covers
Source/LaunchOutput/Endpoint. Qualified datapath-only crossings require both
corner maxima; ordinary interstage paths retain both setup and hold.
No PDS execution, constraint changes, or hardware release is performed.
"""
import argparse
from collections import Counter, defaultdict
import copy
import hashlib
import json
from pathlib import Path
import re

import camera720_cdc_grouped as grouped
import camera720_native_endpoints as mapping_tool
import camera720_cdc_sameble as sameble

base, native = grouped.base, grouped.base.native
prep, inspect = grouped.prep, grouped.inspect
require, sha, read = grouped.require, grouped.sha, grouped.read
SELF = Path(__file__).resolve()
SCHEMA = 'camera720-cdc-launch-qualified-plan-v1'
COVERAGE_SCHEMA = 'camera720-cdc-launch-qualified-coverage-v1'
POLICY = 'pds-datapath-only-crossing-max-ordinary-interstage-min-max-v1'
MANUAL = Path('D:/pango/PDS_2023.2/doc/Pango_Design_Suite_User_Guide.pdf')
MANUAL_SHA = '4b49b329809fa5dd4998213e715c2996c92cba26fbed74a8b9f43cb711943bb1'
NUM = native.NUM
IDENTITY = ('Source', 'LaunchOutput', 'Endpoint')
CASE = IDENTITY + ('Corner', 'Kind')
MAX_GROUP, MAX_TIMING = 64, 4


def ref(path):
    return grouped.ref(path)


def identity(value):
    return tuple(value[k] for k in IDENTITY)


def case(value):
    return tuple(value[k] for k in CASE)


def field(pattern, text, label):
    return native.field(pattern, text, label)


def policy_reference():
    return {'Identity': POLICY, 'Document': str(MANUAL), 'SHA256': MANUAL_SHA,
            'PDFPage1Based': 218, 'PrintedPage': 217, 'Section': '6.5.1 set_max_delay',
            'Meaning': 'Effective datapath_only suppresses hold; no minimum acceptance is inferred.'}


def constraint_pairs(constraints):
    maxima, minima = {}, {}
    pattern = r'-from \[get_clocks \{(\w+)\}\] -to \[get_clocks \{(\w+)\}\] ('+NUM+r')'
    for row in constraints['RelevantStatements']:
        for target, prefix in ((maxima, 'set_max_delay -datapath_only '), (minima, 'set_min_delay ')):
            found = re.fullmatch(re.escape(prefix)+pattern, row['Text'])
            if found:
                key = found[1], found[2]
                require(key not in target, 'ambiguous effective clock-pair constraint')
                target[key] = {'Line': row['Line'], 'Text': row['Text'], 'BoundNS': float(found[3])}
    return maxima, minima


def normalize_queries(inventory, constraints):
    """Preserve mapped FF identity and derive applicable native check kinds."""
    require(inventory.get('MappingPassed') is True and inventory.get('NativeTimingAccepted') is False,
            'completed mapping without timing acceptance required')
    relations = inventory['LogicalRelationships']
    maxima, minima = constraint_pairs(constraints)
    result, seen, represented = [], set(), set()
    require(isinstance(relations, list) and relations and inventory['Queries'], 'empty mapping inventory')
    for original in inventory['Queries']:
        key = identity(original)
        require(key not in seen and all(isinstance(p, str) and base.SAFE_PIN.fullmatch(p) for p in key),
                'duplicate or unsafe launch-qualified identity')
        seen.add(key)
        require(key[0].endswith('/CLK') and key[0].rsplit('/', 1)[0] == key[1].rsplit('/', 1)[0],
                'launch output does not belong to source CLK')
        requirement, indexes = original['Requirements'], original['LogicalRelationships']
        require(isinstance(indexes, list) and indexes and len(indexes) == len(set(indexes)),
                'logical relationship binding missing or duplicated')
        for index in indexes:
            require(type(index) is int and 0 <= index < len(relations), 'invalid logical relationship index')
            row = relations[index]
            require((row['SourceNativeClockPin'], row['SourceNativeOutputPin']) == key[:2]
                    and key[2] in {b['Endpoint'] for b in row['NativeBoundaries']},
                    'query differs from logical FF and native boundary')
            clocks = (requirement.get('Clock', requirement.get('SourceClock')),
                      requirement.get('Clock', requirement.get('DestinationClock')))
            require((row['SourceClock'], row['DestinationClock']) == clocks, 'logical clock binding differs')
            represented.add(index)
        require(requirement.get('Corners') == ['slow', 'fast'], 'both corners required')
        q = {k: copy.deepcopy(original[k]) for k in IDENTITY}
        q.update(LogicalRelationships=list(indexes), Corners=['slow', 'fast'])
        if 'Clock' in requirement:
            require(requirement['CheckKinds'] == ['setup', 'hold'] and not any(
                k in requirement for k in ('SourceClock', 'DestinationClock')), 'ordinary contract differs')
            q.update(Clock=requirement['Clock'], CheckKinds=['setup', 'hold'],
                     HoldAnalysisSuppressed=False, MinDelayNotAccepted=False)
        else:
            pair = requirement['SourceClock'], requirement['DestinationClock']
            require(pair[0] != pair[1] and pair in maxima and pair in minima,
                    'crossing lacks exact datapath-only and declared minimum constraints')
            maximum, minimum = maxima[pair], minima[pair]
            require(requirement['CheckKinds'] == ['max-delay', 'min-delay']
                    and requirement['MaximumNS'] == maximum['BoundNS']
                    and requirement['MinimumNS'] == minimum['BoundNS']
                    and requirement['SourcePeriodNS'] == constraints['PeriodsNS'][pair[0]],
                    'mapped legacy constraint provenance differs')
            q.update(SourceClock=pair[0], DestinationClock=pair[1], CheckKinds=['max-delay'],
                     MaximumNS=maximum['BoundNS'], SourcePeriodNS=requirement['SourcePeriodNS'],
                     EffectiveMaximum=copy.deepcopy(maximum), DeclaredMinimum=copy.deepcopy(minimum),
                     HoldAnalysisSuppressed=True, MinDelayNotAccepted=True, SuppressionReason=POLICY)
        result.append(q)
    require(represented == set(range(len(relations))), 'logical relationship lost from query inventory')
    return sorted(result, key=identity)


def bind_inputs(mapping_ref, original_ref, seed_ref):
    watched = {}
    old = grouped.bind_original(original_ref['Path'], original_ref['SHA256'], watched)
    context = grouped.bind_seed(seed_ref, old['CandidateADF'], old['BuildPlanSHA256'], watched)
    path = inspect.canonical(mapping_ref['Path'], prep.WORK)
    require(grouped.native.physical.digest(mapping_ref['SHA256']), 'explicit mapping SHA required')
    grouped.watch(watched, path, mapping_ref['SHA256'])
    inventory = read(path)
    require(inventory.get('Schema') == 'camera720-native-endpoints-v1'
            and inventory['CandidateADF'] == old['CandidateADF']
            and inventory['BuildPlanSHA256'] == old['BuildPlanSHA256']
            and inventory['ExportReceipt'] == old['ExportReceipt'], 'mapping candidate/export/build differs')
    require(all(inventory.get(k) is False for k in ('HardwareAccessed', 'EDAExecuted', 'HardwareReleaseAllowed')),
            'mapping exceeds CPU scope')
    grouped.merge(watched, inventory['InputSHA256'], context[1]['Command'][0])
    require(inventory['InputSHA256'].get(str(mapping_tool.SELF)) == sha(mapping_tool.SELF),
            'mapping producer absent or drifted')
    require(inventory['InputSHA256'].get(original_ref['Path']) == original_ref['SHA256'],
            'mapping not derived from exact original plan')
    route = inventory['RouteProvenance']
    require(route['Verified'] is True and route['InputADFSHA256'] == old['CandidateADF']['SHA256']
            and route['ExecutionPassed'] is True and route['InputDrift'] == [], 'route provenance differs')
    pairs = {(q['Source'], q['Endpoint']) for q in old['Queries']}
    represented = {(r['SourceNativeClockPin'], e) for r in inventory['LogicalRelationships'] for e in r['OriginalEndpoints']}
    require(represented == pairs and inventory['OriginalPhysicalPairs'] == len(pairs), 'original inventory lost')
    netlist = Path(old['Netlist']['Path'])
    dump_paths = [Path(p) for p,h in inventory['InputSHA256'].items() if h == route['ArtifactSHA256']]
    require(len(dump_paths) == 1, 'exact native route dump absent from mapping closure')
    graph = mapping_tool.monitor.Graph(mapping_tool.structure.functional(netlist.read_text(encoding='utf-8-sig')))
    parents = {mapping_tool.base.native_parent(r[k]) for r in inventory['SameBLEInterstageInventory']
               for k in ('SourceFF', 'DestinationFF')}
    native_route = mapping_tool.route_objects(dump_paths[0], parents)
    supplement = sameble.derive(graph, native_route, inventory)
    augmented = copy.deepcopy(inventory)
    offset = len(augmented['LogicalRelationships'])
    augmented['LogicalRelationships'].extend(copy.deepcopy(supplement['LogicalRelationships']))
    for q in supplement['Queries']:
        q = copy.deepcopy(q)
        q['LogicalRelationships'] = [i+offset for i in q['LogicalRelationships']]
        augmented['Queries'].append(q)
    queries = normalize_queries(augmented, old['Constraints'])
    inventory['SameBLESupplement'] = supplement
    require(MANUAL.is_file() and MANUAL.resolve() == MANUAL and sha(MANUAL) == MANUAL_SHA,
            'local vendor datapath-only authority differs')
    watched[MANUAL] = MANUAL_SHA
    grouped.watch(watched, SELF)
    grouped.watch(watched, mapping_tool.SELF)
    grouped.watch(watched, sameble.SELF)
    require(not inspect.drift(watched), 'bound inputs changed')
    return old, inventory, queries, context, watched


TCO = re.compile(r'^\s+\S+\s+tco\s+('+NUM+r')\s+('+NUM+r')\s+([rf])\s+(\S+)\s*$', re.M)


def launch_row(text):
    rows = TCO.findall(text)
    require(len(rows) == 1, 'selected path lacks one exact native tco launch row')
    return {'IncrementNS': float(rows[0][0]), 'ArrivalNS': float(rows[0][1]),
            'Transition': rows[0][2], 'LaunchOutput': rows[0][3]}


def parse_record(lines, report, line, query):
    text = ''.join(lines)
    source = field(r'^Startpoint\s*:\s*(\S+)\s*$', text, 'source')
    endpoint = field(r'^Endpoint\s*:\s*(\S+)\s*$', text, 'endpoint')
    launch = launch_row(text)
    require((source, launch['LaunchOutput'], endpoint) == identity(query), 'native launch-qualified identity differs')
    typ, corner = field(r'^Path Type\s*:\s*(max|min) \((slow|fast) corner\)\s*$', text, 'type/corner')
    require(field(r'^Path Class\s*:\s*(.*?)\s*$', text, 'class') == 'sequential timing path', 'not a sequential path')
    state, slack = field(r'^ Slack \((MET|VIOLATED)\)\s+('+NUM+r')\s*$', text, 'slack')
    require(state == 'MET' and float(slack) >= 0, 'native timing violation')
    arrival = float(field(r'^ Data arrival time\s+('+NUM+r')\s+Logic Levels:.*$', text, 'arrival'))
    exceptions = re.findall(r'^Timing Exception\s*:\s*(.*?)\s*$', text, re.M)
    result = {k: query[k] for k in IDENTITY}
    result.update(Corner=corner, SlackNS=float(slack), ArrivalNS=arrival, Launch=launch,
                  Report=str(report), ReportLine=line,
                  PathSHA256=hashlib.sha256('\n'.join(l.rstrip() for l in text.splitlines() if l.strip()).encode('ascii')).hexdigest())
    if 'Clock' in query:
        ordinary = native.path_syntax.parse_path(lines, report, line, detailed=False)
        require(ordinary is not None and not exceptions, 'ordinary interstage check absent or excepted')
        require(ordinary['LaunchClock'] == ordinary['CaptureClock'] == query['Clock']
                and ordinary['LaunchEdge'] == ordinary['CaptureEdge'] == 'rising', 'ordinary clock/edge differs')
        require(ordinary['Kind'] == ('setup' if typ == 'max' else 'hold'), 'ordinary check kind differs')
        result.update(Kind=ordinary['Kind'], Clock=query['Clock'], HoldAnalysisSuppressed=False)
    else:
        require(typ == 'max' and query['HoldAnalysisSuppressed'] and query['MinDelayNotAccepted'],
                'minimum result cannot establish suppressed datapath-only acceptance')
        require(len(exceptions) == 1, 'one effective datapath-only exception required')
        match = re.fullmatch(r'MaxDelay Path ('+NUM+r')ns -datapath_only', exceptions[0])
        require(match and float(match[1]) == query['MaximumNS'], 'effective datapath-only bound differs')
        require(int(field(r'^Exception constraint line number:\s*(\d+)\s*$', text, 'constraint line'))
                == query['EffectiveMaximum']['Line'], 'effective constraint line differs')
        require(field(r'^Path Group\s*:\s*(\S+)\s*$', text, 'path group') == query['DestinationClock'],
                'datapath-only destination domain differs')
        require(not re.findall(r'^ Clock (\S+) \((rising|falling) edge\)', text, re.M),
                'datapath-only path unexpectedly includes clock-edge timing')
        require(0 <= arrival < query['SourcePeriodNS'], 'crossing arrival exceeds source period')
        check = float(field(r'^ Setup time\s+('+NUM+r')\s+'+NUM+r'\s*$', text, 'setup library check'))
        require(abs((query['MaximumNS']+check-arrival)-float(slack)) <= 0.003,
                'datapath-only slack arithmetic differs')
        result.update(Kind='max-delay', BoundNS=query['MaximumNS'],
                      HoldAnalysisSuppressed=True, MinDelayNotAccepted=True)
    require(result['Kind'] in query['CheckKinds'] and corner in query['Corners'], 'unexpected native corner/kind')
    return result


def collect(queries, reports):
    lookup = {identity(q): q for q in queries}
    pairs = {(q['Source'], q['Endpoint']) for q in queries}
    rows, violations, other_launches, seen = [], [], Counter(), set()
    for report in sorted(set(Path(p) for p in reports)):
        with report.open(encoding='gb18030', errors='strict') as stream:
            head = ''.join(next(stream, '') for _ in range(18))
        require('2023.2-SP3 <build 154097>' in head and
                re.search(r'^\| Design\s*:\s*'+re.escape(prep.TARGET)+r'\s*$', head, re.M),
                'normal native timing report identity missing')
        for lines, line in native.blocks(report):
            text = ''.join(lines)
            source = field(r'^Startpoint\s*:\s*(.+?)\s*$', text, 'source')
            endpoint = field(r'^Endpoint\s*:\s*(.+?)\s*$', text, 'endpoint')
            if (source, endpoint) not in pairs:
                continue
            try:
                launch = launch_row(text)['LaunchOutput']
                key = source, launch, endpoint
                if key not in lookup:
                    other_launches[key] += 1
                    continue
                value = parse_record(lines, report, line, lookup[key])
            except ValueError as error:
                violations.append({'Source': source, 'Endpoint': endpoint, 'Report': str(report),
                                   'ReportLine': line, 'Stage': 'native-path-validation', 'Error': str(error)})
                continue
            if value['PathSHA256'] not in seen:
                seen.add(value['PathSHA256']); rows.append(value)
    return rows, violations, [{'Source': s, 'LaunchOutput': l, 'Endpoint': e, 'ObservedVariants': n}
                             for (s, l, e), n in sorted(other_launches.items())]


def coverage(queries, rows, violations):
    expected = {identity(q)+(c, k) for q in queries for c in q['Corners'] for k in q['CheckKinds']}
    counts = defaultdict(list)
    for row in rows:
        require(case(row) in expected, 'unexpected native coverage identity')
        counts[case(row)].append(row['SlackNS'])
    missing = [dict(zip(CASE, key)) for key in sorted(expected-set(counts))]
    return {'ExpectedCases': len(expected), 'CoveredCases': len(counts), 'MissingCases': missing,
            'CaseCoverage': [dict(zip(CASE, key), MinimumSlackNS=min(slacks), Variants=len(slacks))
                             for key, slacks in sorted(counts.items())],
            'Complete': not missing, 'EnumeratedPathsTimingPassed': not missing and not violations}


def domain(q):
    return ('ordinary', q['Clock']) if 'Clock' in q else ('datapath-only', q['SourceClock'], q['DestinationClock'], q['MaximumNS'])


def groups_for(queries, missing, maximum=MAX_GROUP):
    require(type(maximum) is int and 1 <= maximum <= MAX_GROUP, 'group limit must be 1..64')
    needed = {tuple(row[k] for k in IDENTITY) for row in missing}
    domains = defaultdict(list)
    for q in queries:
        if identity(q) in needed:
            domains[domain(q)].append(q)
    result = []
    for dom, values in sorted(domains.items()):
        pending = sorted(values, key=identity)
        while pending:
            selected, deferred, per_endpoint = [], [], defaultdict(set)
            group_sources, group_endpoints = set(), set()
            for q in pending:
                # At most four launches reach a selected endpoint; nworst 8
                # may still select edge variants, so coverage is never inferred.
                launches = per_endpoint[q['Endpoint']] | {(q['Source'], q['LaunchOutput'])}
                ss, es = group_sources | {q['Source']}, group_endpoints | {q['Endpoint']}
                if len(selected) >= maximum or len(launches) > 4 or len(ss) > 4 or len(ss)*len(es) > maximum:
                    deferred.append(q)
                else:
                    selected.append(q); per_endpoint[q['Endpoint']] = launches
                    group_sources, group_endpoints = ss, es
            pending = deferred
            require(selected, 'cannot construct bounded missing-query group')
            sources = sorted({q['Source'] for q in selected})
            endpoints = sorted({q['Endpoint'] for q in selected})
            pins = sorted(set(sources+endpoints+[q['LaunchOutput'] for q in selected]))
            pattern = '^('+'|'.join(re.escape(pin) for pin in pins)+')$'
            command = ('report_path_timing -delay_type min_max -max_path 1000 -nworst 8 -report_exception TRUE -from {'+
                       ' '.join(sources)+'} -to {'+' '.join(endpoints)+'}')
            result.append({'Domain': list(dom), 'ExpectedIdentities': [{k: q[k] for k in IDENTITY} for q in selected],
                           'Pins': pins, 'PinPattern': pattern,
                           'PinCommand': 'get_pins -hierarchical -regexp {'+pattern+'}', 'Command': command})
    require({tuple(r[k] for k in IDENTITY) for g in result for r in g['ExpectedIdentities']} == needed,
            'grouping lost or invented missing identities')
    return result


def query_bodies(groups, per_body=3):
    require(type(per_body) is int and 1 <= per_body <= MAX_TIMING, 'at most four timing commands per body')
    payloads = {}
    for first in range(0, len(groups), per_body):
        commands = [s for g in groups[first:first+per_body] for s in (g['PinCommand'], g['Command'])]
        body = '# Launch-qualified missing queries; every output/corner/kind requires actual detail.\n'+'\n'.join(commands)+'\n'
        inspect.query_commands(body)
        payloads[f'query-{first//per_body:02}.tcl'] = body
    return payloads


def validate_pin_log(log, groups):
    issues = []
    for group in groups:
        matches = [line for line in log.splitlines() if 'Timing-5001:' in line
                   and "The pattern '"+group['PinPattern']+"'" in line]
        if len(matches) != 1:
            issues.append({'Stage': 'native-pin-enumeration', 'Pattern': group['PinPattern'],
                           'Error': 'exact pin enumeration absent or repeated'})
            continue
        line = matches[0]
        count = re.search(r' match (\d+) objects below:', line)
        pins = re.findall(r'\bt:([^\s]+)', line.split('objects below:', 1)[-1])
        if count is None or int(count[1]) != len(group['Pins']) or len(pins) != len(set(pins)) or set(pins) != set(group['Pins']):
            issues.append({'Stage': 'native-pin-enumeration', 'Pattern': group['PinPattern'],
                           'Expected': group['Pins'], 'Observed': pins,
                           'Error': 'missing, invalid, or truncated native pins'})
    return issues


def timing_command(source, endpoint):
    return ('report_path_timing -delay_type min_max -max_path 1000 -nworst 8 -report_exception TRUE -from {'+
            source+'} -to {'+endpoint+'}')


def query_filter(command):
    """Extract exact object collections; no truncated/subset filter acceptance."""
    require(command.startswith('report_path_timing ') and len(re.findall(r'-from\s', command)) == 1
            and len(re.findall(r'-to\s', command)) == 1, 'ambiguous targeted command filters')
    pairs = []
    for option in ('from', 'to'):
        match = re.search('-'+option+r' \{([^}]*)\}', command)
        require(match is not None, 'targeted command lacks collection')
        values = [s[2:] if s.startswith(('t:', 'p:')) else s for s in match[1].split()]
        require(values and len(values) == len(set(values)), 'empty or repeated targeted collection')
        pairs.append(set(values))
    return tuple(pairs)


def validate_report_filter(report_name, header, timing_commands):
    match = re.search(r'(?:^|/)report_path_timing_(\d+)/', report_name.replace('\\', '/'))
    require(match is not None and 1 <= int(match[1]) <= len(timing_commands), 'targeted report index differs')
    commands = re.findall(r'^\| Tcl Command\s*:\s*(.*?)\s*$', header, re.M)
    require(len(commands) == 1 and query_filter(commands[0]) == query_filter(timing_commands[int(match[1])-1]),
            'targeted report source/endpoint filters were dropped or changed')


def bind_reports(receipt_refs, old, seed_ref, context, watched, allowed_bodies=None, groups=(), initial_commands=()):
    reports, bound_refs, issues, excluded = [], [], [], []
    for supplied in receipt_refs:
        path = inspect.canonical(supplied['Path'], prep.WORK)
        grouped.watch(watched, path, supplied['SHA256'])
        mode = read(path)['Mode']
        receipt = grouped.bind_native_fast(path, mode, watched, old['CandidateADF'], old['BuildPlanSHA256'], seed_ref, context)
        if mode == 'query':
            body = Path(receipt['QueryBody']).read_text(encoding='ascii')
            commands = inspect.query_commands(body)
            timing_commands = [c for c in commands if c.startswith('report_path_timing ')]
            if allowed_bodies is not None:
                require(body in allowed_bodies, 'native query is not an exact prepared missing-query body')
                selected = [g for g in groups if g['Command'] in commands]
                require(len(selected) <= MAX_TIMING, 'native timing context too large')
                issues.extend(validate_pin_log((path.parent/'stdout.log').read_text(encoding='gb18030'), selected))
            else:
                require(len(commands) == len(initial_commands) and set(commands) == set(initial_commands),
                        'initial query must be exactly the independently derived same-BLE supplement')
        else:
            require(ref(path) == old['ExportReceipt'], 'only bound final export may supply full STA')
        for name, digest in receipt['Artifacts'].items():
            if Path(name).name != prep.TARGET+'.rtr':
                continue
            report = grouped.watch(watched, path.parent/name, digest)
            if 'report_path_timing' in Path(name).parts:
                with report.open(encoding='gb18030') as stream:
                    head = ''.join(next(stream, '') for _ in range(18))
                validate_report_filter(name, head, timing_commands)
            reports.append(report)
        bound_refs.append(ref(path))
    require(reports, 'no actual receipt-bound native timing reports')
    return sorted(set(reports)), bound_refs, issues, excluded


def output_value(old, inventory, queries, rows, violations, excluded):
    result = coverage(queries, rows, violations)
    result.update(Schema=COVERAGE_SCHEMA, Target=prep.TARGET, Producer=ref(SELF), Policy=policy_reference(),
                  CandidateADF=old['CandidateADF'], Records=rows, Violations=violations, ExcludedOtherLaunches=excluded,
                  MissingIdentityCount=len({tuple(r[k] for k in IDENTITY) for r in result['MissingCases']}),
                  SameBLEInterstageInventory=copy.deepcopy(inventory['SameBLEInterstageInventory']),
                  SameBLESupplement=copy.deepcopy(inventory['SameBLESupplement']),
                  SupplementalLogicalRelationshipOffset=len(inventory['LogicalRelationships']),
                  SupplementalProducer=ref(sameble.SELF), BuildPlanSHA256=old['BuildPlanSHA256'],
                  SameBLEInternalTimingAccepted=False, HoldAnalysisSuppressedForDatapathOnly=True,
                  SuppressedCrossingCount=sum('Clock' not in q for q in queries), MinDelayNotAccepted=True,
                  NativeSiteMappingVerified=False, NativeElectricalSettingsVerified=False, AnalogMTBFProven=False,
                  TimingAccepted=False, HardwareReleaseAllowed=False, HardwareAccessed=False, EDAExecuted=False,
                  Limits='Enumerated launch-qualified CDC paths only. Same-BLE internal timing, IO/electrical, overall STA, analog MTBF, optics, and hardware release remain separate.')
    return result


def prepare(mapping_ref, original_ref, seed_ref, receipt_refs, output, maximum=MAX_GROUP, per_body=3):
    old, inventory, queries, context, watched = bind_inputs(mapping_ref, original_ref, seed_ref)
    old['NativeQueries'] = queries
    initial_commands = [timing_command(q['Source'], q['Endpoint']) for q in inventory['SameBLESupplement']['Queries']]
    refs = [old['ExportReceipt']]+receipt_refs
    require(len({r['Path'] for r in refs}) == len(refs), 'duplicate evidence receipt')
    reports, bound, issues, omitted = bind_reports(refs, old, seed_ref, context, watched, initial_commands=initial_commands)
    rows, violations, excluded = collect(queries, reports)
    violations += issues
    result = output_value(old, inventory, queries, rows, violations, excluded)
    groups = groups_for(queries, result['MissingCases'], maximum)
    payloads = query_bodies(groups, per_body)
    plan = {'Schema': SCHEMA, 'Target': prep.TARGET, 'CreatedUTC': inspect.utc(), 'Producer': ref(SELF),
            'Policy': policy_reference(), 'EndpointInventory': mapping_ref, 'OriginalBatchPlan': original_ref,
            'InspectionSeed': seed_ref, 'CandidateADF': old['CandidateADF'], 'BuildPlanSHA256': old['BuildPlanSHA256'],
            'InitialEvidence': bound, 'InitialReports': [ref(p) for p in reports], 'ExcludedInitialReports': omitted,
            'SameBLESupplement': inventory['SameBLESupplement'], 'SupplementalProducer': ref(sameble.SELF),
            'SupplementalLogicalRelationshipOffset': len(inventory['LogicalRelationships']),
            'Queries': queries,
            'InitialCoverage': {k: result[k] for k in ('ExpectedCases', 'CoveredCases', 'MissingCases', 'Complete', 'EnumeratedPathsTimingPassed')},
            'Groups': groups, 'MaximumExpectedIdentitiesPerGroup': maximum, 'MaximumTimingCommandsPerBody': per_body,
            'QueryBodies': {n: hashlib.sha256(t.encode('ascii')).hexdigest() for n,t in payloads.items()},
            'NativeTimingCommands': len(groups), 'NativeContexts': len(payloads), 'CoverageAssumedFromGrouping': False,
            'EDAExecuted': False, 'HardwareAccessed': False, 'TimingAccepted': False, 'HardwareReleaseAllowed': False}
    result.update(EndpointInventory=mapping_ref, OriginalBatchPlan=original_ref, InspectionSeed=seed_ref,
                  NativeReceipts=bound, ExcludedReports=omitted, InputSHA256={str(p):h for p,h in watched.items()})
    payloads['initial-coverage.json'] = json.dumps(result, indent=2)+'\n'
    return base.write_output(output, 'native-plan.json', plan, watched, payloads)


def audit_value(plan_path, expected_sha, receipt_refs):
    path = inspect.canonical(plan_path, prep.WORK)
    require(grouped.native.physical.digest(expected_sha) and sha(path) == expected_sha, 'explicit native plan SHA differs')
    plan = read(path)
    require(plan.get('Schema') == SCHEMA and plan.get('Producer') == ref(SELF) and plan.get('Policy') == policy_reference(),
            'native plan schema/producer/policy differs')
    require(plan.get('Target') == prep.TARGET and plan.get('CoverageAssumedFromGrouping') is False
            and all(plan.get(k) is False for k in ('EDAExecuted','HardwareAccessed','TimingAccepted','HardwareReleaseAllowed')),
            'native plan exceeds CPU-only scope')
    old, inventory, queries, context, watched = bind_inputs(plan['EndpointInventory'], plan['OriginalBatchPlan'], plan['InspectionSeed'])
    old['NativeQueries'] = queries
    initial_commands = [timing_command(q['Source'], q['Endpoint']) for q in inventory['SameBLESupplement']['Queries']]
    reports, initial_refs, issues, omitted = bind_reports(plan['InitialEvidence'], old, plan['InspectionSeed'], context, watched,
                                                       initial_commands=initial_commands)
    require(plan['Queries'] == queries and plan['CandidateADF'] == old['CandidateADF']
            and plan['InitialReports'] == [ref(p) for p in reports] and plan['ExcludedInitialReports'] == omitted,
            'prepared native inventory differs')
    require(plan['SameBLESupplement'] == inventory['SameBLESupplement'] and plan['SupplementalProducer'] == ref(sameble.SELF)
            and plan['BuildPlanSHA256'] == old['BuildPlanSHA256']
            and plan['SupplementalLogicalRelationshipOffset'] == len(inventory['LogicalRelationships']),
            'supplemental mapping/producer differs')
    rows, violations, excluded = collect(queries, reports)
    initial = coverage(queries, rows, violations+issues)
    require(plan['InitialCoverage'] == {k: initial[k] for k in plan['InitialCoverage']}, 'initial coverage cannot be reproduced')
    groups = groups_for(queries, initial['MissingCases'], plan['MaximumExpectedIdentitiesPerGroup'])
    bodies = query_bodies(groups, plan['MaximumTimingCommandsPerBody'])
    require(groups == plan['Groups'] and plan['QueryBodies'] == {n: hashlib.sha256(t.encode('ascii')).hexdigest() for n,t in bodies.items()},
            'prepared missing-query recipe differs')
    require({str(p):h for p,h in watched.items()} == plan['InputSHA256'], 'native plan input closure differs')
    grouped.watch(watched, path, expected_sha)
    for name, digest in plan['QueryBodies'].items(): grouped.watch(watched, path.parent/name, digest)
    if receipt_refs:
        more, bound, pin_issues, extra_omitted = bind_reports(receipt_refs, old, plan['InspectionSeed'], context, watched, set(bodies.values()), groups)
        reports = sorted(set(reports+more)); issues += pin_issues; omitted += extra_omitted
        rows, violations, excluded = collect(queries, reports)
    else:
        bound = []
    result = output_value(old, inventory, queries, rows, violations+issues, excluded)
    result.update(Plan={'Path':str(path), 'SHA256':expected_sha}, EndpointInventory=plan['EndpointInventory'],
                  OriginalBatchPlan=plan['OriginalBatchPlan'], InspectionSeed=plan['InspectionSeed'],
                  NativeReceipts=initial_refs+bound, ExcludedReports=omitted,
                  InvalidPins=[v for v in issues if v['Stage']=='native-pin-enumeration'])
    missing_groups = groups_for(queries, result['MissingCases'], plan['MaximumExpectedIdentitiesPerGroup'])
    payloads = query_bodies(missing_groups, plan['MaximumTimingCommandsPerBody'])
    result.update(RemainingGroups=missing_groups, RemainingBodies={n:hashlib.sha256(t.encode('ascii')).hexdigest() for n,t in payloads.items()})
    require(not inspect.drift(watched), 'native coverage input drift')
    result['InputSHA256'] = {str(p):h for p,h in watched.items()}
    return result, watched, payloads


def audit(plan_path, expected_sha, receipt_refs, output):
    result, watched, payloads = audit_value(plan_path, expected_sha, receipt_refs)
    return base.write_output(output, 'coverage.json', result, watched, payloads)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='mode', required=True)
    p = sub.add_parser('prepare')
    for name in ('mapping', 'original', 'inspection-seed'):
        p.add_argument('--'+name, type=Path, required=True); p.add_argument('--'+name+'-sha256', required=True)
    p.add_argument('--evidence-receipt', type=Path, action='append', default=[])
    p.add_argument('--maximum-pairs', type=int, default=MAX_GROUP)
    p.add_argument('--timing-per-body', type=int, default=3)
    c = sub.add_parser('check'); c.add_argument('--plan', type=Path, required=True); c.add_argument('--plan-sha256', required=True)
    c.add_argument('--query-receipt', type=Path, action='append', default=[])
    for command in (p,c): command.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.mode == 'prepare':
            value = prepare({'Path':str(args.mapping.absolute()), 'SHA256':args.mapping_sha256},
                {'Path':str(args.original.absolute()), 'SHA256':args.original_sha256},
                {'Path':str(args.inspection_seed.absolute()), 'SHA256':args.inspection_seed_sha256},
                [ref(p) for p in args.evidence_receipt], args.output_dir, args.maximum_pairs, args.timing_per_body)
        else:
            value = audit(args.plan, args.plan_sha256, [ref(p) for p in args.query_receipt], args.output_dir)
    except (ValueError, KeyError, OSError) as error:
        failure = {'Schema':'camera720-cdc-launch-qualified-failure-v1', 'Mode':args.mode,
                   'Stage':'binding-or-evidence-audit', 'Error':str(error), 'TimingAccepted':False, 'HardwareReleaseAllowed':False}
        if not args.output_dir.exists():
            prep.work_path(args.output_dir).mkdir()
            (args.output_dir/'failure.json').write_text(json.dumps(failure,indent=2)+'\n',encoding='utf-8')
        print(json.dumps(failure)); return 2
    summary = value.get('InitialCoverage', value)
    print(json.dumps({k:summary[k] for k in ('ExpectedCases', 'CoveredCases', 'Complete', 'EnumeratedPathsTimingPassed') if k in summary}
                     | {k:value[k] for k in ('NativeTimingCommands', 'NativeContexts') if k in value}))
    return 0 if args.mode == 'prepare' or value['EnumeratedPathsTimingPassed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
