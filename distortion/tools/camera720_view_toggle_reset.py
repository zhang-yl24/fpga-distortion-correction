"""Derive unapplied reset scope from the view-switch candidate's own evidence.

No native process or hardware is accessed. Only one report Design token and
one netlist module token are adapted for existing strict pure parsers. Native
names, paths, counts and connectivity are never taken from a previous build.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import tempfile

import prepare_camera_vga_reset_scope as scope
import audit_camera_vga_reset_netlist as graph

SELF = Path(__file__).resolve()
TARGET = 'camera720_view_toggle_top'
PARSER_TARGET = 'camera_vga_output_top'
SCHEMA = 'camera720-view-toggle-unapplied-reset-scope-v1'
FAMILIES = {'entry_rdc', 'cpd_reset', 'dqs_reset', 'iol_reset', 'training_reset'}
require, sha = scope.require, scope.sha


def ref(path):
    path = Path(path).resolve()
    return {'Path': str(path), 'SHA256': sha(path)}


def report_inventory(report):
    """Keep report line numbers and every native path unchanged."""
    count = 0
    digest = hashlib.sha256()
    header = re.compile(r'\| Design\s*:\s*(\S+)\s*')
    with tempfile.TemporaryDirectory(prefix='view-reset-') as temporary:
        view = Path(temporary) / 'report.rtr'
        with Path(report).open(encoding='utf-8-sig') as source, \
                view.open('w', encoding='utf-8', newline='\n') as target:
            for line in source:
                match = header.fullmatch(line)
                if match:
                    require(match[1] == TARGET, 'report has another Design target')
                    count += 1
                    line = line[:match.start(1)] + PARSER_TARGET + line[match.end(1):]
                target.write(line)
                digest.update(line.encode('utf-8'))
        require(count == 1, 'exactly one view-switch Design header required')
        paths, summaries = scope.parse_report(view)
        # Strict equality includes both corner summaries, WNS/TNS, all logical
        # checks and the capture-edge variants of DDR primitives.
        inventory = scope.audit_inventory(paths, summaries, require_complete=True)
    return inventory, {'OriginalTop': TARGET, 'ParserTop': PARSER_TARGET,
        'HeaderReplacements': count, 'TemporaryViewSHA256': digest.hexdigest(),
        'NativeNamesAndLineNumbersUnchanged': True}


def adapt_netlist(text):
    require(re.findall(r'(?m)^module\s+(\w+)\b', text) == [TARGET],
            'exactly one view-switch netlist module required')
    adapted, count = re.subn(r'(?m)^(module\s+)' + re.escape(TARGET) + r'\b',
                            r'\g<1>' + PARSER_TARGET, text)
    require(count == 1, 'ambiguous netlist module adapter')
    return adapted


def exact_scope(inventory):
    require(inventory.get('Complete') is True, 'complete current recovery inventory required')
    checks = inventory['Corners']['slow']['Checks']
    for check in checks:
        require(scope.classify(check) == check['Family'], 'reset family classification differs')
    queries, body, fdc = scope.query_scope(inventory)
    require(len(queries) == len(FAMILIES) and {q['Family'] for q in queries} == FAMILIES,
            'unexpected reset source families')
    pairs = {(check['Source'], check['Endpoint']) for check in checks}
    require(pairs == {(q['Source'], t) for q in queries for t in q['Targets']}
            and len(pairs) == sum(q['ExpectedTargetCount'] for q in queries),
            'reset selector pairs differ from current report')
    commands = [line for line in fdc.splitlines() if line and not line.startswith('#')]
    require(len(commands) == len(queries) and all(command.startswith(
        'set_false_path -from [get_pins -hierarchical -regexp {') for command in commands),
        'unexpected reset proposal syntax')
    body = body.replace('CAMERA_VGA_RESET_QUERY_', 'CAMERA720_VIEW_RESET_QUERY_')
    fdc = ('# UNAPPLIED view-switch candidate scope; native exact-name query and '
           'ADF provenance remain unverified.\n' + '\n'.join(commands) + '\n')
    return queries, body, fdc, commands


def derive(report, netlist, adf):
    paths = [Path(p).resolve() for p in (report, netlist, adf)]
    require(all(p.is_file() for p in paths), 'existing report, netlist and candidate ADF required')
    report, netlist, adf = paths
    require(adf.suffix.lower() == '.adf', 'candidate ADF file required')
    bound = {str(p): sha(p) for p in paths}
    for p in (SELF, Path(scope.__file__).resolve(), Path(graph.__file__).resolve(),
              Path(graph.syntax.__file__).resolve()):
        bound[str(p)] = sha(p)
    inventory, adapter = report_inventory(report)
    queries, query, fdc, commands = exact_scope(inventory)
    structure = graph.audit_text(adapt_netlist(netlist.read_text(encoding='utf-8-sig')), queries)
    require(structure['Status'] == 'pass' and structure['InternalFunctionalTargetsVerified'] ==
            sum(q['ExpectedTargetCount'] for q in queries if not q['EntryRDC']),
            'actual reset graph does not cover every proposed internal endpoint')
    require(all(sha(name) == digest for name, digest in bound.items()),
            'reset input changed during derivation')
    result = {'Schema': SCHEMA, 'Target': TARGET,
        'CreatedUTC': datetime.now(timezone.utc).isoformat(),
        'Status': 'prepared_unapplied_pending_native_name_and_provenance_checks',
        'Report': ref(report), 'Netlist': ref(netlist), 'SourceADF': ref(adf),
        'InputSHA256': bound, 'Inventory': inventory, 'ReportAdapter': adapter,
        'NativeQueries': queries, 'ExactResetCommands': commands, 'ResetGraph': structure,
        'UniqueSourceEndpointPairs': sum(q['ExpectedTargetCount'] for q in queries),
        'ResetConnectivityVerified': True, 'ReportNativeADFBindingVerified': False,
        'NativeQueriesVerified': False, 'TimingExceptionApproved': False,
        'ConstraintsApplied': False, 'HistoricalEndpointInventoryUsed': False,
        'EDAExecuted': False, 'HardwareAccessed': False, 'HardwareReleaseAllowed': False,
        'Limits': 'Pure report/netlist checks only. The supplied ADF hash is recorded, '
                  'not proof that the native export used it. Exact native names, same-candidate '
                  'export/query receipts, vendor reset relationship basis, any data timing repair, '
                  'and fresh post-application STA remain separate requirements.'}
    return result, query, fdc


def prepare(report, netlist, adf, output):
    output = Path(output).resolve()
    require(not output.exists(), 'fresh reset output directory required')
    result, query, fdc = derive(report, netlist, adf)
    payloads = {'query.tcl': query, 'scope.fdc': fdc}
    result['FilesSHA256'] = {name: hashlib.sha256(data.encode('ascii')).hexdigest()
                           for name, data in payloads.items()}
    output.mkdir(parents=True)
    for name, data in payloads.items():
        with (output / name).open('x', encoding='ascii', newline='\n') as stream:
            stream.write(data)
    with (output / 'proof.json').open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--netlist', type=Path, required=True)
    parser.add_argument('--adf', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    value = prepare(args.report, args.netlist, args.adf, args.output_dir)
    print(json.dumps({'Status': value['Status'], 'Pairs': value['UniqueSourceEndpointPairs'],
                      'Families': {q['Family']: q['ExpectedTargetCount'] for q in value['NativeQueries']},
                      'NativeQueriesVerified': False, 'ConstraintsApplied': False}))


if __name__ == '__main__':
    main()
