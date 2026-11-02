"""Fresh raw-diagnostic native pad and synchronizer evidence; CPU only.

Only the current raw graph and routes generate queries. Packed same-BLE
connections rely on the bound vendor sequential model and complete same-ADF
STA; this module never invents separate FF timing arcs or analog MTBF.
"""
import argparse
import copy
import json
from pathlib import Path
import re
import tempfile

import hdmi_camera_raw_audit as audit
import hdmi_camera_raw_native as native
import camera720_io_evidence as electrical

SELF = Path(__file__).resolve()
TARGET = audit.TARGET
require, sha, read, write = audit.require, audit.sha, audit.read, audit.write
cdc = audit.cdc
DOCUMENTS = {
    cdc.timing.MANUAL: cdc.timing.MANUAL_SHA,
    Path('D:/pango/PDS_2023.2/doc/Tcl_Command_User_Guide.pdf'):
        '7be74cf2d0fba752cc7016a47b994d9bfb05805f4c7b19fb4d15266033de9ba4',
    Path('D:/pango/PDS_2023.2/doc/Timing_Analyzer_User_Guide.pdf'):
        '9d04d214d74f95348ce292b3c244e6ee880dd7095014209db243f8b8c1b2b420',
}


def _binding(value, watched):
    require(isinstance(value, dict) and set(value) == {'Path', 'SHA256'},
            'exact current native reference required')
    return native.add(watched, value['Path'], value['SHA256'])


def inventory(scope):
    """Resolve first-stage Q and actual interstage boundary from this ADF."""
    require(scope.get('Target') == TARGET and scope.get('Schema') ==
            'hdmi-camera-raw-unapplied-physical-scope-v1', 'current raw scope required')
    text = Path(scope['NativeNetlist']['Path']).read_text(encoding='utf-8-sig')
    require(sha(scope['NativeNetlist']['Path']) == scope['NativeNetlist']['SHA256'],
            'raw synchronization netlist changed')
    g = audit.graph(text)
    families = audit.source_sync_families(Path(scope['BuildPlan']['Path']).parent)
    chains = scope['Synchronizers']
    require(len(chains) == len(families) and {c['Family'] for c in chains} == set(families),
            'raw synchronization families changed')
    for chain in chains:
        release = (chain['InterstageLogic'] or {}).get('ReleaseNet')
        actual = g.chain(chain['First'], chain['Second'], chain['Label'], release)
        require(chain == {'Family': chain['Family'], **actual},
                'raw synchronization graph or physical packing changed')
    mapped_rows = []
    packed = []
    for chain in chains:
        require(chain['ClockRootsIdentical'] and chain['ClearFunctionsEquivalent']
                and chain['FirstStageOnlyFeedsSecondStage'], 'invalid raw synchronization structure')
        if chain['SameBLE']:
            require(not chain['NativeQueries'] and chain['SameSite']
                    and chain['FirstPlacement'] == chain['SecondPlacement'],
                    'unqueried interstage relationship is not one current BLE')
            packed.append({k: chain[k] for k in ('Family', 'First', 'Second',
                'FirstPlacement', 'SecondPlacement', 'DestinationClock', 'InterstageLogic')})
            continue
        require(chain['NativeQueries'], 'ordinary interstage path lacks a query')
        mapped_rows.append({'SourceFF': chain['First'], 'DestinationFF': chain['Second'],
            'DestinationPin': 'D', 'SourceClock': chain['DestinationClock'],
            'DestinationClock': chain['DestinationClock'], 'Labels': [chain['Family']],
            'Purposes': ['ordinary synchronizer interstage'],
            'OriginalEndpoints': [q['Endpoint'] for q in chain['NativeQueries']]})
    placements = cdc.clm.placed_luts(text, g)
    parents = {audit.parent(n) for r in mapped_rows for n in (r['SourceFF'], r['DestinationFF'])}
    parents.update(n.rsplit('/', 2)[0] for n in placements)
    require(sha(scope['RouteDump']['Path']) == scope['RouteDump']['SHA256'], 'raw route dump changed')
    with tempfile.TemporaryDirectory(prefix='raw-interstage-') as temporary:
        normalized = Path(temporary) / 'route.adif'
        cdc.normalize_source_locations(scope['RouteDump']['Path'], normalized)
        route = cdc.endpoints.route_objects(normalized, parents)
    mapper = cdc.clm.Mapper(g, route, placements)
    mapped = [mapper.map(row) for row in mapped_rows]
    queries = cdc.make_queries(mapped, {'RelevantStatements': []}) if mapped else []
    require(sum(len(q['LogicalRelationships']) for q in queries) >= len(mapped_rows),
            'native interstage mapping omits a synchronization chain')
    return {'Synchronizers': chains, 'PackedInterstage': packed,
            'OrdinaryInterstage': mapped, 'Queries': queries}


def _query_parts(scope, current):
    pins = scope['Pins']
    require(pins['TopPortCount'] == len(pins['PinInventory']) == 46,
            'all46 raw pins required')
    sites = sorted({row['Site'] for row in pins['PinInventory']})
    require(all(cdc.SAFE.fullmatch(s) for s in sites), 'unsafe raw IO site')
    commands = ['show -dev_instance {' + site + '}' for site in sites]
    groups = []
    timed = []
    for q in current['Queries']:
        selected = sorted({q[k] for k in cdc.timing.IDENTITY})
        require(all(cdc.SAFE.fullmatch(p) for p in selected), 'unsafe raw interstage native pin')
        pattern = '^(' + '|'.join(re.escape(p) for p in selected) + ')$'
        commands.append('get_pins -hierarchical -regexp {' + pattern + '}')
        command = ('report_path_timing -delay_type min_max -max_path 1000 -nworst 8 '
            '-report_exception TRUE -from {' + q['Source'] + '} -through {' +
            q['LaunchOutput'] + '} -to {' + q['Endpoint'] + '}')
        commands.append(command)
        timed.append(command)
        groups.append({'PinPattern': pattern, 'Pins': selected})
    body = '\n'.join(commands) + '\n'
    native.query_commands(body)
    return body, groups, timed


def prepare_queries(scope):
    """Return one bounded native query body; never execute PDS."""
    return _query_parts(scope, inventory(scope))[0]


def _all_ten(report):
    with Path(report).open(encoding='utf-8-sig') as stream:
        tables, clocks = audit.timing.parse_summaries(stream)
    require(set(tables) == {(c, k) for c in ('slow', 'fast') for k in audit.timing.KINDS},
            'ten raw timing tables required')
    for table in tables.values():
        require(table and all(row['FailingChecks'] == 0 and row['WorstSlackNS'] >= 0
                and row['TotalNegativeSlackNS'] == 0 for row in table.values()),
                'full current raw STA has an unresolved failure')
    return tables, clocks


def _query_reports(path, receipt, commands):
    reports = []
    for name in receipt['Artifacts']:
        if not name.endswith('.rtr') or name.endswith('_exception.rtr') or 'report_path_timing/' not in name:
            continue
        report = path.parent / name
        with report.open(encoding='gb18030') as stream:
            header = ''.join(next(stream, '') for _ in range(18))
        require(re.search(r'^\| Design\s*:\s*' + TARGET + r'\s*$', header, re.M),
                'raw interstage report target differs')
        cdc.timing.validate_report_filter(name, header, commands)
        number = re.search(r'report_path_timing_(\d+)/', name.replace('\\', '/'))
        require(number is not None and 1 <= int(number[1]) <= len(commands), 'unknown raw query report')
        actual = cdc.timing.field(r'^\| Tcl Command\s*:\s*(.*?)\s*$', header, 'command')
        through = lambda s: [{p[2:] if p.startswith(('p:', 't:')) else p for p in v.split()}
                            for v in re.findall(r'-through \{([^}]+)\}', s)]
        require(through(actual) == through(commands[int(number[1]) - 1]),
                'raw interstage launch-output selector changed')
        reports.append(report)
    require(len(reports) == len(commands), 'raw interstage report count differs')
    return reports


def _records(queries, reports):
    lookup = {cdc.timing.identity(q): q for q in queries}
    require(len(lookup) == len(queries), 'duplicate raw interstage identity')
    rows, violations, seen = [], [], set()
    for report in reports:
        for lines, line in cdc.timing.native.blocks(report):
            text = ''.join(lines)
            source = cdc.timing.field(r'^Startpoint\s*:\s*(.+?)\s*$', text, 'source')
            endpoint = cdc.timing.field(r'^Endpoint\s*:\s*(.+?)\s*$', text, 'endpoint')
            launch = cdc.timing.launch_row(text)['LaunchOutput']
            key = source, launch, endpoint
            require(key in lookup, 'unrequested launch/endpoint in exact interstage query')
            try:
                row = cdc.timing.parse_record(lines, report, line, lookup[key])
            except ValueError as error:
                violations.append({'Source': source, 'LaunchOutput': launch, 'Endpoint': endpoint,
                    'Report': str(report), 'ReportLine': line, 'Error': str(error)})
                continue
            if row['PathSHA256'] not in seen:
                rows.append(row)
                seen.add(row['PathSHA256'])
    return rows, violations


def derive(scope, export_receipt, query_receipts, *, bind_native=None):
    """Verify current-ADF native queries, all46 pads and every interstage case.

    The caller must independently prove baseline/final functional, placement
    and complete-route equivalence before relying on the baseline route cells.
    An injected binder must run the complete native receipt verifier and return
    its full watched closure; this permits a clean validation subprocess whose
    imports match those used when the native stage was prepared.
    """
    binder = native.bind_receipt if bind_native is None else bind_native
    require(callable(binder), 'complete native receipt binder required')
    watched = {}
    for name in ('BuildPlan', 'NativeNetlist', 'RouteDump', 'SourceADF'):
        _binding(scope[name], watched)
    for p, h in scope['InputSHA256'].items():
        native.add(watched, p, h)
    export_path = Path(export_receipt).resolve()
    exported, bound = binder(export_path)
    native.merge(watched, bound)
    require(exported['Mode'] == 'export' and exported['BuildPlanSHA256'] == scope['BuildPlan']['SHA256']
            and Path(exported['BuildPlan']) == Path(scope['BuildPlan']['Path'])
            and exported.get('SourceProof') is not None, 'final raw export lacks scoped-application lineage')
    report = export_path.parent / 'report_timing' / (TARGET + '.rtr')
    native.add(watched, report)
    _all_ten(report)
    current = inventory(scope)
    body, groups, timed = _query_parts(scope, current)
    paths = [Path(p).resolve() for p in query_receipts]
    require(len(paths) == len(set(paths)) == 1, 'one complete raw pad/interstage query receipt required')
    query_path = paths[0]
    queried, bound = binder(query_path)
    native.merge(watched, bound)
    require(queried['Mode'] == 'query' and all(queried[k] == exported[k] for k in
            ('BuildPlan', 'BuildPlanSHA256', 'SourceADF', 'SourceADFSHA256', 'SourceProof')),
            'raw pad/interstage query belongs to another final ADF')
    require(Path(queried['QueryBody']).read_text(encoding='ascii') == body,
            'raw query body differs from complete current pin/interstage recipe')
    log = (query_path.parent / 'stdout.log').read_text(encoding='gb18030')
    violations = cdc.timing.validate_pin_log(log, groups)
    pins = copy.deepcopy(scope['Pins'])
    audit.algorithms.io.apply_native_sites(pins, log)
    native_parameters = electrical.io_parameters(scope['RouteDump']['Path'], pins)
    require(native_parameters['Passed'] and native_parameters['Ports'] == 46,
            'raw pad native electrical coverage incomplete')
    pins.update(NativeElectricalParametersVerified=True, NativeElectricalParameters=native_parameters)
    reports = _query_reports(query_path, queried, timed)
    rows, issues = _records(current['Queries'], reports)
    violations.extend(issues)
    coverage = cdc.timing.coverage(current['Queries'], rows, violations)
    require(coverage['EnumeratedPathsTimingPassed'], 'raw interstage timing coverage incomplete or violated')
    documents = []
    for p, digest in DOCUMENTS.items():
        native.add(watched, p, digest)
        documents.append(native.ref(p))
    for p in audit.local_helpers():
        native.add(watched, p)
    native.add(watched, SELF)
    result = {'Pins': pins, 'CDC': {'DataScopes': scope['DataScopes'],
        'InterstageTimingAccepted': True, 'SynchronizerCount': len(current['Synchronizers']),
        'InterstageQueries': current['Queries'], 'InterstageRecords': rows,
        'InterstageCoverage': coverage, 'PackedSameBLEInterstage': current['PackedInterstage'],
        'PackedSameBLECount': len(current['PackedInterstage']),
        'VendorPackedSequentialModelBasis': {'Documents': documents,
            'SameFinalADFFullSTAAllTenPassed': True, 'IndividualPackedFFArcsClaimed': False,
            'AnalogMTBFAccepted': False, 'RequiresIndependentlyUnchangedGraphPlacementRoutes': True},
        'QueryReceipts': [native.ref(query_path)], 'Missing': coverage['MissingCases'],
        'Violations': violations, 'ExternalACAccepted': False}}
    return result, watched


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scope', type=Path, required=True)
    parser.add_argument('--query-output', type=Path)
    parser.add_argument('--export-receipt', type=Path)
    parser.add_argument('--query-receipt', type=Path, action='append', default=[])
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    scope = read(args.scope)
    if args.query_output:
        require(not args.query_output.exists(), 'fresh raw query output required')
        args.query_output.write_text(prepare_queries(scope), encoding='ascii', newline='\n')
        print(json.dumps({'PreparedOnly': True, 'QueryBody': str(args.query_output.resolve())}))
    else:
        require(args.export_receipt and args.output and not args.output.exists(),
                'current export and fresh output required')
        result, watched = derive(scope, args.export_receipt, args.query_receipt)
        write(args.output, {**result, 'InputSHA256': {str(p): h for p, h in watched.items()}})
        print(json.dumps({'Pins': 46, 'InterstageTimingAccepted': True,
            'CoveredInterstageCases': result['CDC']['InterstageCoverage']['CoveredCases']}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
