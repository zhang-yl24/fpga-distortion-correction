"""CPU audit of the input-delay candidate reset effects and requested data branches.

Rebind native source/derivative evidence, compare all routes and functional
cells, preserve timed data checks, and require precisely the proved reset
false-path inventory. No previous candidate authority/count/hash is inherited.
"""
import argparse
from collections import Counter
from decimal import Decimal
import hashlib
import json
from pathlib import Path

import run_raw_camera_delay_derived_inspect as derived
import re
import audit_raw_camera_delay_hold as hold
import audit_raw_camera_routes as routes
import audit_camera_vga_physical as pure_physical
import audit_camera_vga_exception_union as exception_syntax

physical, audit, inspect = derived.physical, derived.audit, derived.inspect
prep, require, sha = derived.prep, derived.require, derived.sha
native = pure_physical.native
SELF = Path(__file__).resolve()
SCHEMA = 'raw-camera-delay-reset-effect-audit-v1'


def functional(text):
    require('2023.2-SP3<build 154097>' in text[:300], 'native raw export version differs')
    clean = re.sub(r'/\*.*?\*/|//[^\n]*|\(\*.*?\*\)', lambda m: '\n' * m[0].count('\n'), text, flags=re.S)
    require(re.findall(r'(?m)^module\s+(\w+)', clean) == [prep.TARGET]
            and len(re.findall(r'(?m)^endmodule\b', clean)) == 1, 'one flat raw top required')
    cells, placements = {}, {}
    for m in pure_physical.dialect.CELL.finditer(clean):
        name = m['name'].lstrip('\\')
        require(name not in cells, 'duplicate raw primitive')
        cells[name] = {'Primitive':m['primitive'], 'Parameters':pure_physical.dialect.bindings(m['parameters']),
                       'Ports':pure_physical.dialect.bindings(m['ports'])}
    require(cells and len(cells) == len(re.findall(r'(?m)^[ \t]*V_\w+\b', clean)), 'incomplete primitive parse')
    for m in pure_physical.FF.finditer(text):
        name = m['name'].lstrip('\\')
        require(name in cells and name not in placements, 'duplicate/unmatched raw FF placement')
        placements[name] = {'Site':m['site'], 'Attributes':' '.join((m['attrs'] or '').split())}
    require(placements and set(placements) == {n for n,c in cells.items() if c['Primitive'] in ('V_FFASYN','V_FFSYN')},
            'every raw FF requires native placement')
    return {'Cells':cells, 'FFPlacement':placements,
            'ModuleDeclarations':' '.join(pure_physical.dialect.CELL.sub('', clean).split())}


def constraint_state(path):
    """Keep every constraint reference with its unchanged enclosing context.

    CDBENTRY sibling ordering is immaterial, but moving a reference to another
    instance or changing any field is detected. The remaining token digest
    excludes exactly CDB, CDBENTRY, route annotations and native file metadata.
    """
    parser = routes.common
    path = Path(path).resolve(); original = sha(path)
    semantic = hashlib.sha256(); depth = 0; active = None; start = None
    held, entries, cdb, filetable = [], [], None, None
    owner = None; owner_depth = None; metadata = Counter(); counts = Counter()
    for line_number, line in enumerate(path.open(encoding='utf-8-sig'), 1):
        tokens = parser.TOKEN.findall(line)
        require(not parser.TOKEN.sub('', line).strip(), 'unparsed constraint tokens')
        previous = depth; depth += tokens.count('(') - tokens.count(')')
        require(depth >= 0, 'unbalanced native constraints')
        if active is None:
            if tokens[:2] == ['(', 'INSTANCE'] and depth > previous:
                require(isinstance(tokens[2], str), 'ambiguous instance owner')
                owner, owner_depth = tokens[2].lstrip('\\'), previous
            if previous == 1 and tokens[:2] in (['(', 'CDB'], ['(', 'FILETABLE']):
                active, start, held = tokens[1], previous, []
                counts[active] += 1
            elif tokens[:2] in (['(', 'NETANNOTATE'], ['(', 'CDBENTRY']):
                active, start, held = tokens[1], previous, []
                counts[active] += 1
                context = semantic.copy().hexdigest()
            elif line_number == 1:
                require(tokens[:2] == ['(', 'ADIF'] and len(tokens) == 3, 'missing ADIF header')
                tokens[2] = '"<OUTPUT_PATH>"'; metadata['OutputPath'] += 1
            elif tokens[:2] == ['(', 'TIMESTAMP']:
                require(len(tokens) == 4, 'timestamp dialect differs')
                tokens[2] = '"<TIMESTAMP>"'; metadata['Timestamp'] += 1
            elif tokens[:2] == ['(', 'ATTR_FN']:
                require(len(tokens) == 4, 'source path dialect differs')
                tokens[2] = '<SOURCE_PATH>'; metadata['SourceAttribute'] += 1
            elif tokens[:2] in (['(', 'FILEID'], ['(', 'LINENUM']):
                require(len(tokens) == 4 and tokens[2].isdigit(), 'source metadata differs')
                continue
        if active:
            if active in ('CDB', 'CDBENTRY', 'FILETABLE'):held.extend(tokens)
            if depth == start:
                if active == 'CDB':
                    require(cdb is None, 'multiple native CDB blocks')
                    cdb = parser.expression(held)
                elif active == 'FILETABLE':
                    require(filetable is None, 'multiple source file tables')
                    filetable = parser.expression(held)
                elif active == 'CDBENTRY':
                    entries.append({'ContextSHA256':context, 'Instance':owner,
                                    'Tree':parser.expression(held)})
                active = None
        else:parser.feed(semantic, tokens)
        if owner_depth is not None and depth <= owner_depth:
            owner = owner_depth = None
    require(depth == 0 and active is None and counts['CDB'] == counts['FILETABLE'] == 1
            and counts['NETANNOTATE'] > 1000, 'incomplete native constraint dump')
    require(metadata == {'OutputPath':1, 'Timestamp':1, 'SourceAttribute':1}, 'native metadata inventory differs')
    require(sha(path) == original, 'native constraint dump drift')
    return {'NonConstraintNonRouteSHA256':semantic.hexdigest(), 'CDB':cdb,
            'Entries':entries, 'FileTable':filetable, 'SHA256':original}


def compare_file_tables(before, after):
    """PDS may discard empty source filenames on save; preserve real mappings."""
    def inventory(tree):
        require(isinstance(tree, list) and tree and tree[0] == 'FILETABLE', 'missing file table')
        result = {}
        for row in tree[1:]:
            require(isinstance(row, list) and len(row) == 3 and row[0] == 'FILEMAP'
                    and row[1].isdigit() and row[1] not in result
                    and isinstance(row[2], str) and row[2].startswith('"') and row[2].endswith('"'),
                    'unsupported or duplicate source file mapping')
            result[row[1]] = row[2]
        return result
    old, new = inventory(before), inventory(after)
    require(all(k in old and old[k] == v for k,v in new.items()), 'source file mapping added or changed')
    removed = {k:v for k,v in old.items() if k not in new}
    require(all(v == '""' for v in removed.values()), 'nonempty source filename removed')
    return {'Passed':True, 'OnlyEmptySourceNamesRemoved':True, 'RemovedEmptyIDs':sorted(removed),
            'BeforeSHA256':digest(before), 'AfterSHA256':digest(after)}


def fields(tree, label):
    require(isinstance(tree, list) and tree and tree[0] == label, 'wrong constraint node')
    result = {}
    for child in tree[1:]:
        require(isinstance(child, list) and len(child) == 2 and isinstance(child[1], str)
                and child[0] not in result, 'ambiguous constraint fields')
        result[child[0]] = child[1]
    return result


def compare_constraints(before, after, queries):
    require(before['NonConstraintNonRouteSHA256'] == after['NonConstraintNonRouteSHA256'],
            'nonconstraint functional/placement semantics changed')
    require(before['CDB'][0] == after['CDB'][0] == 'CDB', 'missing native CDB')
    old, new = Counter(digest(v) for v in before['CDB'][1:]), Counter(digest(v) for v in after['CDB'][1:])
    require(not old - new, 'existing native constraint changed or removed')
    added_nodes = []
    remaining = new - old
    for child in after['CDB'][1:]:
        key = digest(child)
        if remaining[key]:added_nodes.append(child); remaining[key] -= 1
    require(len(added_nodes) == len(queries) and added_nodes, 'exact reset query count required in CDB')
    added_ids = {}
    for child in added_nodes:
        value = fields(child, 'FP')
        require(set(value) == {'FID','LN','CDBID','SU','HD','EXCPTFEA'}
                and value['FID'] == value['LN'] == value['SU'] == value['HD'] == '1'
                and value['EXCPTFEA'] == '264437760' and value['CDBID'].isdigit(),
                'new native constraint is not the exact scoped false-path dialect')
        require(value['CDBID'] not in added_ids, 'duplicate added CDB identity')
        added_ids[value['CDBID']] = {'From':[], 'To':[]}
    prior_ids = []
    def visit(value):
        if isinstance(value, list):
            if len(value) == 2 and value[0] == 'CDBID':prior_ids.append(value[1])
            for child in value:visit(child)
    visit(before['CDB'])
    require(not set(prior_ids).intersection(added_ids), 'new constraint reuses a prior CDB identity')
    old_refs = Counter(digest(v) for v in before['Entries'])
    new_refs = Counter(digest(v) for v in after['Entries'])
    require(not old_refs - new_refs, 'existing constraint pin reference moved, changed or removed')
    added_refs = new_refs - old_refs
    for entry in after['Entries']:
        key = digest(entry)
        if not added_refs[key]:continue
        added_refs[key] -= 1
        value = fields(entry['Tree'], 'CDBENTRY')
        require(set(value) == {'CDBID','FILEID','LINENUM','TYPE','PINNAME'}
                and value['FILEID'] == value['LINENUM'] == '1'
                and value['CDBID'] in added_ids and value['TYPE'] in ('1','3')
                and entry['Instance'], 'unexpected added constraint pin reference')
        added_ids[value['CDBID']]['From' if value['TYPE'] == '1' else 'To'].append(
            entry['Instance'] + '/' + value['PINNAME'].strip('"'))
    wanted = Counter((q['Source'], tuple(sorted(q['Targets']))) for q in queries)
    actual = Counter()
    for value in added_ids.values():
        require(len(value['From']) == 1 and value['To'] and len(set(value['To'])) == len(value['To']),
                'native false path has broad, repeated or missing endpoints')
        actual[(value['From'][0], tuple(sorted(value['To'])))] += 1
    require(actual == wanted and all(n == 1 for n in actual.values()), 'CDB reset scope differs from proved exact pins')
    return {'ExactNativeConstraintDeltaVerified':True, 'OriginalConstraintsAndReferencesPreserved':True,
            'AddedFalsePathConstraints':len(added_ids), 'AddedSourceEndpointPairs':sum(len(v['To']) for v in added_ids.values()),
            'AddedCDBIDs':sorted(added_ids), 'NonconstraintSemanticsSHA256':before['NonConstraintNonRouteSHA256']}


def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def file_binding(path):
    return {'Path':str(Path(path).absolute()), 'SHA256':sha(path)}


def artifact(receipt_path, receipt, name, watched):
    paths = [Path(receipt_path).parent/n for n in receipt['Artifacts']
             if Path(n).name == name and 'report_path_timing' not in Path(n).parts]
    require(len(paths) == 1, 'one bound native artifact required: '+name)
    return physical.add(watched, paths[0], receipt['Artifacts'][paths[0].relative_to(Path(receipt_path).parent).as_posix()])


def compare_timing(before, after, inventory, route_pairs):
    require(set(before) == set(after) == {(c,k) for c in ('slow','fast') for k in native.KINDS}, 'ten timing tables required')
    removed = {}
    for group in inventory['Groups']:
        key = (group['Corner'], group['LaunchClock'], group['CaptureClock'])
        require(group['Complete'] and key not in removed, 'incomplete or repeated current reset group')
        removed[key] = group['ObservedLogicalChecks']
    summaries, changes = {}, []
    for (corner, kind), old in before.items():
        now = after[(corner,kind)]
        cuts = {k[1:]:count for k,count in removed.items() if k[0] == corner} if kind in ('recovery','removal') else {}
        require(set(cuts) <= set(old) and set(now) == set(old)-set(cuts), 'timing clock-pair inventory changed outside exact reset scope')
        for pair,count in cuts.items():require(old[pair]['TotalChecks'] == count, 'removed timing check count differs from actual reset inventory')
        for pair,row in now.items():
            require(row['TotalChecks'] == old[pair]['TotalChecks'], 'timed data/remaining reset checks removed')
            allowed = kind in ('setup','hold') and pair in route_pairs
            require(allowed or row == old[pair], 'unrelated timing summary changed: '+str((corner,kind,pair)))
            if row != old[pair]:changes.append({'Corner':corner,'Kind':kind,'Clocks':list(pair),'Before':old[pair],'After':row})
            require(row['FailingChecks'] == 0 and row['WorstSlackNS'] >= 0 and row['TotalNegativeSlackNS'] == 0, 'remaining native timing failure')
        require(now, 'empty surviving timing table')
        summaries[corner+'_'+kind] = {'WorstSlackNS':min(r['WorstSlackNS'] for r in now.values()),
            'FailingChecks':sum(r['FailingChecks'] for r in now.values()),
            'TotalChecks':sum(r['TotalChecks'] for r in now.values()), 'RemovedResetChecks':sum(cuts.values())}
    return summaries, changes


def compare_false_paths(baseline, candidate, inventory):
    require(all(not v for v in baseline.values()), 'baseline contains unapproved false paths')
    expected = {corner:{native.path_identity(p) for check in inventory['Corners'][corner]['Checks']
                        for p in check['NativeVariants']} for corner in ('slow','fast')}
    return native.validate_exception_sets(candidate, expected)


def nonfalse_equal(before, after):
    require(set(before) == set(after) and len(before) == 16, 'non-false exception section inventory differs')
    result = {}
    for key, rows in before.items():
        a,b = Counter(r['SHA256'] for r in rows),Counter(r['SHA256'] for r in after[key])
        require(a == b, 'non-reset exception paths differ; additional two-sided evidence required: '+str(key))
        result[str(key)] = {'Paths':len(rows), 'NormalizedPathMultisetSHA256':digest(sorted(a.items()))}
    return result


def target_records(report, measured):
    identities = {hold.common.identity(c) for p in measured for c in p['Cases']}
    rows, _, _ = hold.common.read_report(report, identities)
    rows = [r for r in rows if hold.common.identity(r) in identities]
    require({hold.common.identity(r) for r in rows} == identities, 'exact routed path identity disappeared')
    return rows


def target_skeleton(row, net):
    """Only the terminal net and resulting totals may change, including port paths."""
    body, route, arrivals, totals, slack = [], [], [], [], []
    data_done = False
    num = hold.common.NUM
    for line in row['_Lines']:
        if not line.strip() or set(line.strip()) <= set('=-*'):continue
        match = hold.common.NET.fullmatch(line)
        if not data_done and match and match[4].strip() == net:
            route.append((Decimal(match[2]), Decimal(match[3])))
            body.append('net (fanout=' + match[1] + ') <DELAY> <CUMULATIVE> ' + net)
            continue
        match = re.fullmatch(r' Data arrival time\s+(' + num + r')(.*)\s*', line.rstrip('\r\n'))
        if match:
            data_done = True; arrivals.append(Decimal(match[1]))
            body.append('Data arrival time <ARRIVAL> ' + native.normalize(match[2])); continue
        match = exception_syntax.LOGIC.fullmatch(line.rstrip('\r\n'))
        if match:
            totals.append(tuple(Decimal(v) for v in match.groups()))
            body.append('Logic: <VERIFIED_LOGIC> Route: <VERIFIED_ROUTE>'); continue
        match = re.fullmatch(r' Slack \((MET|VIOLATED)\)\s+(' + num + r')\s*', line.rstrip('\r\n'))
        if match:
            slack.append(Decimal(match[2])); body.append('Slack <VERIFIED_STATE_AND_VALUE>'); continue
        body.append(native.normalize(line))
    require(len(route) == len(totals) == len(slack) == 1 and len(arrivals) == 2,
            'exact terminal route/totals missing from target path')
    return {'Body':body, 'NetDelay':route[0][0], 'NetCumulative':route[0][1],
            'Arrivals':arrivals, 'LogicRoute':totals[0], 'Slack':slack[0]}


READ_SLICE = 'u_ddr3_test_h/u_ddrphy_top/ddrphy_slice_top/i_dqs_group[2].ddrphy_data_slice/'
READ_SOURCE = READ_SLICE + 'dq_loop[7].u_iobuf_dq/opit_1/ICLKDIV'
READ_ENDPOINT = READ_SLICE + 'ddrphy_dqs_rddata_align/rddata_r1[63]/opit_0_inv_srl/D'


def read_hold_skeleton(row, parsed):
    """Keep clock/constraint text exact; check every removed data/hold value."""
    dec, within = exception_syntax.dec, exception_syntax.within
    body, arrivals, required, totals, hold_arc, slack = [], [], [], [], [], []
    active, index = False, 0
    num = hold.common.NUM
    uncertainty = []
    for line in row['_Lines']:
        line = line.rstrip('\r\n')
        if not line.strip() or set(line.strip()) <= set('=-*'):continue
        if re.search(r'\s+tco\s+', line):active = True
        match = re.fullmatch(r' Data arrival time\s+(' + num + r')(.*)', line)
        if match:
            active = False; arrivals.append(dec(match[1]))
            body.append('Data arrival time <CHECKED> ' + native.normalize(match[2])); continue
        if active:
            require(hold.common.NET.fullmatch(line) or hold.common.PIN.fullmatch(line),
                    'unparsed representative data row')
            body.append('<CHECKED_DATA_ROW_' + str(index) + '>'); index += 1; continue
        match = exception_syntax.LOGIC.fullmatch(line)
        if match:
            totals.append(tuple(dec(v) for v in match.groups())); body.append('<CHECKED_TOTALS>'); continue
        match = re.fullmatch(r' Hold time\s+(' + num + r')\s+(' + num + r')\s*', line)
        if match:
            hold_arc.append(tuple(dec(v) for v in match.groups())); body.append('<CHECKED_HOLD_ARC>'); continue
        match = re.fullmatch(r' Data required time\s+(' + num + r')\s*', line)
        if match:
            required.append(dec(match[1])); body.append('Data required time <CHECKED>'); continue
        match = re.fullmatch(r' Slack \((MET|VIOLATED)\)\s+(' + num + r')\s*', line)
        if match:
            slack.append(dec(match[2])); body.append('Slack <CHECKED>'); continue
        match = re.fullmatch(r' clock uncertainty\s+(' + num + r')\s+(' + num + r')\s*', line)
        if match:uncertainty.append(tuple(dec(v) for v in match.groups()))
        body.append(native.normalize(line))
    trace = parsed['DataTrace']
    require(index == len(trace) == 5 and len(arrivals) == len(required) == 2
            and arrivals[0] == arrivals[1] and required[0] == required[1]
            and len(totals) == len(hold_arc) == len(slack) == len(uncertainty) == 1,
            'incomplete representative values')
    require(trace[-1]['DelayNS'] is trace[-1]['CumulativeNS'] is None,
            'representative endpoint acquired an extra data delay')
    start = dec(trace[0]['CumulativeNS']) - dec(trace[0]['DelayNS'])
    cumulative = start; logic = Decimal(0); routed = Decimal(0)
    for value in trace[:-1]:
        delay = dec(value['DelayNS']); require(delay >= 0, 'negative representative data delay')
        cumulative += delay
        within(dec(value['CumulativeNS']), cumulative, 'representative cumulative delay')
        if value['Type'] == 'pin':logic += delay
        else:routed += delay
    within(arrivals[0], cumulative, 'representative arrival')
    tl, lp, tr, rp = totals[0]
    within(tl, logic, 'representative logic total'); within(tr, routed, 'representative route total')
    require(tl + tr > 0, 'zero representative total delay')
    within(lp, tl / (tl + tr) * 100, 'representative logic percentage')
    within(rp, tr / (tl + tr) * 100, 'representative route percentage')
    arc, arc_cumulative = hold_arc[0]
    within(arc_cumulative, uncertainty[0][1] + arc, 'representative hold arc cumulative')
    within(required[0], arc_cumulative, 'representative required time')
    within(slack[0], arrivals[0] - required[0], 'representative hold slack')
    require(slack[0] == dec(parsed['SlackNS']) == dec(row['SlackNS']), 'representative slack metadata differs')
    return {'Body':body, 'Arrival':arrivals[0], 'Required':required[0], 'HoldArc':arc,
            'Slack':slack[0], 'LogicRoute':totals[0], 'Start':start}


def compare_read_hold_representative(old, new, net, context):
    """Observed r-to-f worst-path switch, explicitly not same-transition proof.

    The complete native setup/hold tables remain the timing authority. This
    branch accounts for their changed representative only after independent
    functional, physical-route, clock and exact-constraint comparisons pass.
    """
    required_evidence = ('FunctionalGraphIdentical', 'AllFFPlacementsIdentical',
        'AllInternalChecksMet', 'OnlyRequestedRoutingChanges', 'ExactNativeConstraintDeltaVerified',
        'ClockDefinitionsAndLoadsUnchanged', 'ExactResetExceptionUnionVerified', 'OtherExceptionsIdentical')
    require(context and all(context.get(k) is True for k in required_evidence)
            and context.get('ChangedNets') == ['_N199'],
            'representative switch needs complete independent physical/constraint/STA evidence')
    a, b = hold.detailed(old), hold.detailed(new)
    identity_fields = ('Source', 'Endpoint', 'Corner', 'Kind', 'LaunchClock', 'CaptureClock',
                       'LaunchEdge', 'CaptureEdge', 'PathClass', 'TimingExceptions')
    expected = (READ_SOURCE, READ_ENDPOINT, 'fast', 'hold', 'phy_dq_sysclk_1', 'ddrphy_sysclk',
                'rising', 'rising', 'sequential timing path', [])
    require(net == '_N199' and tuple(a[k] for k in identity_fields) ==
            tuple(b[k] for k in identity_fields) == expected,
            'not the observed read fast-hold representative')
    sa, sb = read_hold_skeleton(old, a), read_hold_skeleton(new, b)
    require(sa['Body'] == sb['Body'], 'representative clock/constraint/non-data text changed')
    at, bt = a['DataTrace'], b['DataTrace']
    for x, y in zip(at, bt):
        exclude = {'DelayNS', 'CumulativeNS', 'Transition', 'ReportLine'}
        require({k:v for k,v in x.items() if k not in exclude} ==
                {k:v for k,v in y.items() if k not in exclude},
                'representative logical/physical connectivity changed')
    require([v['Location'] for v in at if v['Type'] == 'pin'] ==
            ['IOLHR_364_708/RX_DATA[7]', 'CLMA_351_702/CR1', 'CLMS_351_709/M2']
            and [v['Name'] for v in at if v['Type'] == 'net'] == [READ_SLICE + 'ddrphy_rdata [63]', '_N199']
            and all(v['Fanout'] == 1 for v in at if v['Type'] == 'net')
            and [v['DelayType'] for v in at if v['Type'] == 'pin'] == ['tco', 'td', None],
            'unexpected representative physical chain')
    require([v['Transition'] for v in at if v['Type'] == 'pin'] == ['r'] * 3
            and [v['Transition'] for v in bt if v['Type'] == 'pin'] == ['f'] * 3,
            'native representative transition pattern differs')
    require(sa['Start'] == sb['Start'] and at[0]['DelayNS'] == bt[0]['DelayNS'],
            'representative launch or tco changed')
    require(sb['Slack'] >= 0, 'new worst representative still fails')
    within = exception_syntax.within
    within(sb['Required'] - sa['Required'], sb['HoldArc'] - sa['HoldArc'], 'required-time delta')
    within(sb['Slack'] - sa['Slack'], sb['Arrival'] - sa['Arrival'] -
           (sb['Required'] - sa['Required']), 'representative slack delta')
    clean = lambda trace: [{k:v for k,v in r.items() if k != 'ReportLine'} for r in trace]
    return {'NativeWorstTransitionRepresentativeChanged':True, 'SameTransitionVariantProved':False,
            'OnlyRepairedNetDelayChanged':False, 'BaselineDataTrace':clean(at), 'CandidateDataTrace':clean(bt),
            'BaselineLogicRouteTotals':[float(v) for v in sa['LogicRoute']],
            'CandidateLogicRouteTotals':[float(v) for v in sb['LogicRoute']],
            'HoldArcNS':{'Before':float(sa['HoldArc']), 'After':float(sb['HoldArc'])},
            'RequiredTimeDeltaNS':float(sb['Required'] - sa['Required']),
            'ArrivalDeltaNS':float(sb['Arrival'] - sa['Arrival']), 'SlackDeltaNS':float(sb['Slack'] - sa['Slack']),
            'Baseline':{k:a[k] for k in ('Report', 'ReportLine', 'PathSHA256')},
            'Candidate':{k:b[k] for k in ('Report', 'ReportLine', 'PathSHA256')},
            'Evidence':'Native worst data transition changed rrr to fff for this exact read path. '
                       'Only _N199 routing changed; function, FF sites, clocks and non-reset constraints are unchanged; '
                       'complete native timing tables pass. This is not a comparison of equal data-transition variants.'}


def compare_target_records(old, new, measured, context=None):
    pairs = {(p['Source'], p['Endpoint']):p for p in measured}
    key = lambda row: (hold.common.identity(row), row['Corner'], row['Kind'])
    require(Counter(key(r) for r in old) == Counter(key(r) for r in new), 'exact route check/edge multiplicity differs')
    results = []
    for pair, path in pairs.items():
        selected = [r for r in new if (r['Source'], r['Endpoint']) == pair]
        require({(r['Corner'],r['Kind']) for r in selected} == {(c,k) for c in ('slow','fast') for k in ('setup','hold')},
                'both-corner setup/hold paths required for every requested branch')
        net = path['PhysicalRepairCandidate']['Net']; checks = []
        for row in selected:
            candidate = target_skeleton(row, net)
            require(candidate['Slack'] >= 0, 'exact routed target still fails')
            matches = [previous for previous in old if key(previous) == key(row)]
            accepted = False
            for previous in matches:
                baseline = target_skeleton(previous, net)
                if baseline['Body'] != candidate['Body']:continue
                delta = candidate['NetDelay'] - baseline['NetDelay']
                near = lambda v,e: abs(v-e) <= Decimal('0.001')
                if not near(candidate['NetCumulative']-baseline['NetCumulative'], delta):continue
                if not all(near(b-a,delta) for a,b in zip(baseline['Arrivals'],candidate['Arrivals'])):continue
                al,_,ar,_ = baseline['LogicRoute']; bl,_,br,_ = candidate['LogicRoute']
                if al != bl or not near(br-ar,delta):continue
                if not near(candidate['Slack']-baseline['Slack'], delta * (-1 if row['Kind'] == 'setup' else 1)):continue
                accepted = True;break
            representative = {}
            if not accepted and context and len(matches) == 1 and (
                    row['Source'], row['Endpoint'], row['Corner'], row['Kind'], net) == (
                    READ_SOURCE, READ_ENDPOINT, 'fast', 'hold', '_N199'):
                representative = compare_read_hold_representative(matches[0], row, net, context)
                accepted = True
            require(accepted, 'target path changed beyond the requested terminal-net delay')
            checks.append({'Corner':row['Corner'],'Kind':row['Kind'],'SlackNS':row['SlackNS'],
                           'TerminalNetDelayNS':float(candidate['NetDelay']), **representative})
        results.append({'Source':pair[0],'Endpoint':pair[1],'Net':net,'AllFourChecksMet':True,'Checks':checks})
    return results


def compare_routes(before, after, bs, cs, requested, targets, queries):
    # Constraint references participate in the ordinary route parser's semantic
    # digest. Replace that digest only after separately proving every CDB delta.
    constraints = compare_constraints(bs, cs, queries)
    filetables = compare_file_tables(bs['FileTable'], cs['FileTable'])
    normalized_files = digest(cs['FileTable'])
    verified_before = {**before, 'NonRouteSemanticSHA256':bs['NonConstraintNonRouteSHA256'],
                       'ExcludedBlockSHA256':{**before['ExcludedBlockSHA256'], 'FILETABLE':normalized_files}}
    verified_after = {**after, 'NonRouteSemanticSHA256':cs['NonConstraintNonRouteSHA256'],
                      'ExcludedBlockSHA256':{**after['ExcludedBlockSHA256'], 'FILETABLE':normalized_files}}
    comparison = routes.compare(verified_before, verified_after, targets, allow_constraint_change=True)
    changed = {routes.annotation_name(n) for n in comparison['ChangedNets']}
    require(changed == {t['Net'] for t in targets}, 'a requested net did not change')
    for request in requested:
        net, branch = request['Net'], request['Branch']
        previous = before['BranchInventory'][net]['Leaves'][branch]
        current = after['BranchInventory'][net]['Leaves'][branch]
        require(current != previous, 'a requested data branch did not change')
        cursor = 0
        for segment in request['Pins'].rstrip(';').split(';'):
            segment = segment.split('>')
            hits = [i for i in range(cursor, len(current)-len(segment)+1) if current[i:i+len(segment)] == segment]
            require(hits, 'requested continuous waypoint segment absent or out of order')
            cursor = hits[0] + len(segment)
    return {**comparison, 'RoutingUnchanged':not changed, 'OnlyRequestedRoutingChanges':True,
            'RawNonRouteSemanticSHA256':{'Baseline':before['NonRouteSemanticSHA256'], 'Candidate':after['NonRouteSemanticSHA256']},
            'ConstraintDelta':constraints, 'SourceFileTableComparison':filetables,
            'SourceLocationMetadata':{'Before':before['SourceLocationMetadata'], 'After':after['SourceLocationMetadata']}}


def run(application_path, candidate_export_path):
    watched = {}; application_path = inspect.canonical(application_path, prep.WORK)
    application = derived.bind_source_receipt(application_path, watched)
    require(application.get('ResetProof') is not None, 'reset effect audit requires an applied proved reset scope')
    proof_path = Path(application['ResetProof']['Path']); proof = read(proof_path)
    build = Path(application['BuildPlan']); source = Path(application['SourceADF']); source_sha = application['SourceADFSHA256']
    _,_,_,_,_,proof_inputs = physical.bind_proof(build,proof_path,application['ResetProof']['SHA256'])
    watched.update(proof_inputs)
    baseline_export_path = Path(proof['CurrentNetlist']['Path']).parent.parent/'result.json'
    baseline = audit.inspection_receipt(baseline_export_path,'export',build,source,source_sha,watched)
    candidate_export_path = inspect.canonical(candidate_export_path,prep.WORK)
    final = derived.bind_receipt(candidate_export_path,watched)
    require(final['Mode'] == 'export' and final['SourceReceipt'] == file_binding(application_path)
            and final['SourceADFSHA256'] == application['ResultADFSHA256'], 'final export belongs to another derivative')
    br = artifact(baseline_export_path,baseline,prep.TARGET+'.rtr',watched)
    cr = artifact(candidate_export_path,final,prep.TARGET+'.rtr',watched)
    be = artifact(baseline_export_path,baseline,prep.TARGET+'_exception.rtr',watched)
    ce = artifact(candidate_export_path,final,prep.TARGET+'_exception.rtr',watched)
    inventory, _ = audit.inventory(proof['CurrentReport']['Path'])
    require(application.get('Schema') == 'raw-camera-delay-route-reset-application-v1' and application.get('Routes'),
            'this audit requires the exact multi-branch raw route/reset application')
    request = read(application['Request']['Path'])
    dump_before = physical.binding(request['RouteDump'], watched)
    hold_path = physical.binding(request['HoldAudit'], watched)
    hold_value = read(hold_path)
    measured = hold_value['Paths']
    require(hold_value.get('Schema') == 'raw-camera-delay-hold-analysis-v1' and hold_value.get('Target') == prep.TARGET
            and measured and hold_value['ExtractionComplete'] and not hold_value['MissingExactSetup'],
            'complete current input-delay hold evidence required')
    targets = [{**p['PhysicalRepairCandidate'], 'Endpoint':p['Endpoint']} for p in measured]
    route_pairs = {(p['LaunchClock'],p['CaptureClock']) for p in measured}
    dump_after = artifact(application_path, application, 'route-dump.txt', watched)
    route_origin = {'BaselineReceipt':request['QueryReceipt'], 'CandidateReceipt':file_binding(application_path),
                    'Request':application['Request'], 'RequestedRoutes':application['Routes']}
    a,b = routes.inspect(dump_before,targets),routes.inspect(dump_after,targets)
    sa,sb = constraint_state(dump_before),constraint_state(dump_after)
    route_result = compare_routes(a,b,sa,sb,application['Routes'],targets,proof['NativeQueries'])
    before_graph = functional(Path(baseline['Netlist']['Path']).read_text(encoding='utf-8-sig'))
    after_graph = functional(Path(final['Netlist']['Path']).read_text(encoding='utf-8-sig'))
    require(before_graph == after_graph, 'functional graph, declarations or FF placement changed')
    bt,bc = pure_physical.summaries(br); ct,cc = pure_physical.summaries(cr)
    require(bc == cc, 'clock definitions/loads changed')
    summaries,changes = compare_timing(bt,ct,inventory,route_pairs)
    with be.open(encoding='gb18030') as f:old_false = native.parse_false_paths(f)
    with ce.open(encoding='gb18030') as f:new_false = native.parse_false_paths(f)
    false_counts = compare_false_paths(old_false,new_false,inventory)
    other = nonfalse_equal(exception_syntax.read_exceptions(be),exception_syntax.read_exceptions(ce))
    path_context = {'FunctionalGraphIdentical':True, 'AllFFPlacementsIdentical':True,
        'AllInternalChecksMet':True, 'OnlyRequestedRoutingChanges':route_result['OnlyRequestedRoutingChanges'],
        'ChangedNets':sorted(routes.annotation_name(n) for n in route_result['ChangedNets']),
        'ExactNativeConstraintDeltaVerified':route_result['ConstraintDelta']['ExactNativeConstraintDeltaVerified'],
        'ClockDefinitionsAndLoadsUnchanged':True, 'ExactResetExceptionUnionVerified':True, 'OtherExceptionsIdentical':True}
    paths = compare_target_records(target_records(br,measured),target_records(cr,measured),measured,path_context)
    for module in (physical,derived,audit,inspect,routes,routes.common,hold,hold.common,pure_physical,
                   pure_physical.hold,pure_physical.dialect,native,exception_syntax):
        physical.add(watched, module.__file__)
    physical.add(watched,SELF)
    require(not inspect.drift(watched), 'effect audit input/tool drift')
    result = {'Schema':SCHEMA,'Target':prep.TARGET,'CreatedUTC':prep.utc(),'AuditPassed':True,'ResetEffectVerified':True,
        'SourceADF':file_binding(source),'ResultADF':file_binding(application['ResultADF']['Path']),
        'ApplicationReceipt':file_binding(application_path),'ResetProof':application['ResetProof'],
        'BaselineExportReceipt':file_binding(baseline_export_path),'CandidateExportReceipt':file_binding(candidate_export_path),
        'FunctionalGraphIdentical':True,'AllFFPlacementsIdentical':True,
        'ActualCellCount':len(before_graph['Cells']),'ActualFFCount':len(before_graph['FFPlacement']),
        'FunctionalPartSHA256':{k:digest(v) for k,v in before_graph.items()},
        **route_result,'RouteScopeEvidence':{**route_origin,'BaselineDump':file_binding(dump_before),
            'CandidateDump':file_binding(dump_after),'Comparison':route_result,
            'BaselineNonconstraintSHA256':sa['NonConstraintNonRouteSHA256'],'CandidateNonconstraintSHA256':sb['NonConstraintNonRouteSHA256']},
        'ExactResetExceptionUnionVerified':True,'NoDataFalsePaths':True,'ClockDefinitionsAndLoadsUnchanged':True,
        'AllInternalChecksMet':True,'CornerSummaries':summaries,'TimingSummaryChanges':changes,
        'FalsePathCounts':false_counts,'OtherExceptionsIdentical':True,'NonFalseExceptionComparison':other,'TargetRouteTiming':paths,
        'InputSHA256':{str(p):h for p,h in watched.items()},'ToolSHA256':{str(p):h for p,h in watched.items() if p.suffix=='.py'},
        'EDAExecuted':False,'HardwareAccessed':False,'TimingAccepted':False,'HardwareReleaseAllowed':False,'ExternalIOAccepted':False,
        'Limits':'Current internal native STA, exact reset effects and requested branches only. External AC/CDC/hardware validation and bitstream release remain separate.'}
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--application',type=Path,required=True);p.add_argument('--candidate-export',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    output=a.output.absolute();require(output==output.resolve() and output.is_relative_to(prep.WORK) and not output.exists(),'fresh in-workspace output required')
    result=run(a.application,a.candidate_export)
    with output.open('x',encoding='utf-8',newline='\n') as f:json.dump(result,f,indent=2);f.write('\n')
    require(read(output)==result,'effect output readback mismatch')
    print(json.dumps({k:result[k] for k in ('AuditPassed','ResetEffectVerified','RoutingUnchanged','ChangedNets','AllInternalChecksMet')}))


if __name__=='__main__':main()
