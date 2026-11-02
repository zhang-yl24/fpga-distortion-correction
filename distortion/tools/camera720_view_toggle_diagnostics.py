"""Explain this build's exact width diagnostics without changing native receipts.

Only identical bounded public counters and protected DDR source/configuration
provenance from the reviewed stats-delay build are accepted. No EDA is run.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import copy
import hashlib
import json
from pathlib import Path
import re

import camera720_view_toggle_build as build

SELF = Path(__file__).resolve()
SCHEMA = 'camera720-view-toggle-build-diagnostics-disposition-v1'
BASELINE = build.ROOT / 'work/camera720-stats-delay/build-c-diagnostic-disposition-a.json'
BASELINE_SHA = 'c4f96be5747a9bda5948720b0f6f720c6e5432625a4a314e6db5c3a27d5e1406'
DEFAULT_BUILD = build.WORK / 'build-a/plan.json'
DEFAULT_OUTPUT = build.WORK / 'build-diagnostics-disposition.json'
require, sha, read = build.require, build.sha, build.read
CRITICAL = re.compile(r'^\s*(?:C:|E:|F:|CRITICAL:|ERROR:|FATAL:|Traceback).*$', re.M)
EVENT = re.compile(r'^C: Sdm-3003: \[(.+)\(line number: (\d+)\)\] Reduce accumulator (\w+) '
                   r'size from (\d+) to (\d+)\. If this is not intended behavior, please drive \3 with valid values\.$')


def normalize(text):
    """Normalize only the source-root prefix inside a diagnostic's brackets."""
    return re.sub(r'\[[^\r\n]*?/compiled/', '[compiled/', text.replace('\\', '/'))


def parameters(text):
    result = {}
    for match in re.finditer(r'^I: Module instance \{([^}]+)\} parameter value:\n((?:[ \t]+[^\n]+\n)+)', text, re.M):
        require(match[1] not in result, 'duplicate elaborated instance')
        result[match[1]] = {'StartLine': text[:match.start()].count('\n') + 1,
                            'Parameters': [line.strip() for line in match[2].splitlines()]}
    return result


def inspect(build_path=DEFAULT_BUILD):
    watched = {}

    def bind(path, expected=None):
        path = Path(path).resolve()
        digest = sha(path)
        require(expected is None or digest == expected, 'diagnostic input SHA differs: ' + str(path))
        require(str(path) not in watched or watched[str(path)] == digest, 'conflicting diagnostic input')
        watched[str(path)] = digest
        return {'Path': str(path), 'SHA256': digest}

    def merge(bindings):
        for path, digest in bindings.items():
            bind(path, digest)

    def logs_for(plan_path, receipt):
        work = plan_path.parent
        require({p.relative_to(work).as_posix() for p in work.rglob('*.log')} ==
                {p.replace('\\', '/') for p in receipt['LogSHA256']}, 'native log inventory differs')
        logs, recorded = {}, []
        for name, digest in receipt['LogSHA256'].items():
            p = work / name
            bind(p, digest)
            rows = [line.strip() for line in CRITICAL.findall(p.read_text(encoding='gb18030', errors='replace'))]
            if rows:
                logs[name.replace('\\', '/')] = rows
                recorded.extend(name + ': ' + line for line in rows)
        require(Counter(row.replace('\\', '/') for row in recorded) ==
                Counter(row.replace('\\', '/') for row in receipt['Diagnostics']), 'native receipt diagnostic rows differ')
        require(len(recorded) == 52 and len(logs) == 4 and all(len(x) == 13 for x in logs.values()),
                'exact four copies of thirteen width diagnostics required')
        require(all(Counter(rows) == Counter(logs['compile/run.log']) for rows in logs.values()),
                'native diagnostic log copies differ')
        require(all(EVENT.fullmatch(text) for text in logs['compile/run.log']),
                'unreviewed critical or error diagnostic')
        return logs, receipt['Diagnostics']

    build_path = Path(build_path).resolve()
    plan = build.validate(build_path)
    bind(build_path)
    receipt_path = build_path.parent / 'execution-result.json'
    bind(receipt_path)
    receipt = read(receipt_path)
    require(receipt['Schema'] == 'camera720-view-toggle-build-execution-v1'
            and receipt['PlanSHA256'] == sha(build_path) and receipt['BuildCompleted'] is True
            and receipt['ExitCode'] == 0 and receipt['TimedOut'] is False
            and receipt['InputDrift'] == [] and receipt['StagesCompleted'] is True
            and receipt['Stages'] == [[s, e] for s in build.STAGES for e in ('started', 'done')]
            and receipt['UnchangedAcrossSTA'] is True and not receipt.get('Error'),
            'exact completed candidate build required')
    for key in ('InputSHA256', 'PreparedSHA256'):
        merge(plan[key])
    bind(BASELINE, BASELINE_SHA)
    baseline = read(BASELINE)
    require(baseline['PublicCounterBoundsReviewed'] is True
            and baseline['VendorSameConfigurationProvenanceReviewed'] is True
            and baseline['OriginalReceiptModified'] is False
            and baseline['SynthesisEquivalenceProved'] is False, 'reviewed bounded baseline required')
    merge(baseline['InputSHA256'])
    old_build_path = Path(baseline['BuildPlan']['Path']).resolve()
    bind(old_build_path, baseline['BuildPlan']['SHA256'])
    old_plan = read(old_build_path)
    for key in ('InputSHA256', 'PreparedSHA256'):
        merge(old_plan[key])
    old_receipt_path = Path(baseline['ExecutionReceipt']['Path']).resolve()
    bind(old_receipt_path, baseline['ExecutionReceipt']['SHA256'])
    old_receipt = read(old_receipt_path)
    current_logs, diagnostics = logs_for(build_path, receipt)
    old_logs, _ = logs_for(old_build_path, old_receipt)
    require(Counter(map(normalize, current_logs['compile/run.log'])) ==
            Counter(map(normalize, old_logs['compile/run.log'])), 'exact width diagnostic text differs from baseline')
    compile_path = build_path.parent / 'compile/run.log'
    compile_text = compile_path.read_text(encoding='gb18030', errors='replace')
    lines, params = compile_text.splitlines(), parameters(compile_text)
    events = []
    for index, text in enumerate(lines):
        if not text.startswith('C:'):
            continue
        match = EVENT.fullmatch(text)
        require(match is not None, 'unreviewed current compile diagnostic')
        source, number, symbol, before, after = Path(match[1]).resolve(), int(match[2]), match[3], int(match[4]), int(match[5])
        require(source.is_relative_to(build_path.parent / 'compiled'), 'diagnostic source outside bound candidate')
        source_ref = bind(source, plan['PreparedSHA256'][str(source)])
        nodes = []
        for following in range(index + 1, len(lines)):
            if not lines[following].startswith('W: Sdm-2000:'):
                break
            node = re.search(r'Removed register node (.+)\[(\d+)\] that is stuck at constant 0\.', lines[following])
            if node:
                nodes.append({'InstanceSignal': node[1], 'Bit': int(node[2]), 'LogLine': following + 1, 'Text': lines[following]})
        require(nodes, 'native reduction has no removed-bit evidence')
        instances = sorted({row['InstanceSignal'].rsplit('/', 1)[0] for row in nodes})
        candidates = [row for row in baseline['DiagnosticEvents'] if row['Symbol'] == symbol
                      and row['Source']['SHA256'] == source_ref['SHA256'] and row['Instances'] == instances]
        require(len(candidates) == 1, 'new source, symbol or elaborated diagnostic instance')
        old = candidates[0]
        bind(old['Source']['Path'], old['Source']['SHA256'])
        require(old['DeclaredBits'] == before and old['ReducedBits'] == after and old['ReportedSourceLine'] == number,
                'diagnostic width or source line changed')
        require(Counter((r['InstanceSignal'], r['Bit']) for r in nodes) ==
                Counter((r['InstanceSignal'], r['Bit']) for r in old['RemovedConstantZeroNodes']),
                'removed-register identity differs')
        event = {k: copy.deepcopy(v) for k, v in old.items() if k not in
                 ('CompileLogLine', 'Text', 'Source', 'RemovedConstantZeroNodes', 'Elaboration', 'ElaboratedInstance')}
        event.update(CompileLogLine=index + 1, Text=text, Source=source_ref, RemovedConstantZeroNodes=nodes)
        if old['PublicRTLBoundProved']:
            instance = plan['Target'] + '/' + instances[0]
            require(params[instance]['Parameters'] == old['Elaboration']['Parameters'], 'public actual parameter changed')
            maximum = old['ReachableMaximum']
            require(0 <= maximum < (1 << after) and maximum.bit_length() == old['RequiredBits'],
                    'public reduced counter cannot retain full reachable bound')
            source_lines = source.read_text().splitlines()
            for excerpt in old['ProofExcerpts']:
                require(source_lines[excerpt['StartLine'] - 1:excerpt['EndLine']] == excerpt['Text'], 'public proof source differs')
            event.update(ElaboratedInstance=instance, Elaboration=params[instance])
        else:
            require(source.suffix == '.vp' and source.read_text().startswith('`pragma protect begin_protected'),
                    'reviewed protected source identity differs')
            require(old['EncryptedInternalBoundIndependentlyProved'] is False, 'cannot inherit independent protected bound proof')
        events.append(event)
    require(len(events) == 13 and sum(e['PublicRTLBoundProved'] for e in events) == 11,
            'exact public and vendor event scope differs')
    ddr_params = {name.split('/u_ddr3_test_h', 1)[1]: row['Parameters']
                  for name, row in params.items() if '/u_ddr3_test_h' in name}
    require(ddr_params == baseline['CurrentDDRParameterBlocks'], 'actual protected DDR parameters differ')
    vendor_root = build_path.parent / 'compiled/platform/video_base/ipcore/ddr3_test'
    vendor_rows = baseline['ProtectedVendorProvenance']['Files']
    require({p.relative_to(vendor_root).as_posix() for p in vendor_root.rglob('*') if p.is_file()} ==
            {r['RelativePath'] for r in vendor_rows}, 'protected vendor closure inventory differs')
    vendor_comparison = []
    for old in vendor_rows:
        current = vendor_root / old['RelativePath']
        current_ref = bind(current, plan['PreparedSHA256'][str(current)])
        previous = old['CurrentCompiled']
        bind(previous['Path'], previous['SHA256'])
        require(current_ref['SHA256'] == previous['SHA256'], 'protected vendor bytes differ')
        vendor_comparison.append({'RelativePath': old['RelativePath'], 'CurrentCompiled': current_ref, 'BaselineCompiled': previous})
    control = build_path.parent / 'compiled' / build.CONTROL
    bind(control, plan['PreparedSHA256'][str(control)])
    control_text = control.read_text()
    require(control.read_bytes() == (build.ROOT / build.CONTROL).read_bytes(), 'button bound source differs')
    button_param = params[plan['Target'] + '/view_control']
    require(button_param['Parameters'] == ["DEBOUNCE_CYCLES = 32'b00000000001001100010010110100000 (32'd2500000)"],
            'actual debounce period differs')
    for token in ('COUNT_WIDTH=(DEBOUNCE_CYCLES>1) ? $clog2(DEBOUNCE_CYCLES):1',
                  'LAST_COUNT=DEBOUNCE_CYCLES-1', 'stable_count<=0;',
                  'if(stable_count==LAST_COUNT)', "stable_count<=stable_count+1'b1"):
        require(token in control_text, 'button counter proof source differs')
    require(not any('camera720_view_control.v' in line for line in diagnostics), 'new button width diagnostic needs independent disposition')
    button = {'Source': bind(control), 'ElaboratedParameters': button_param, 'Counter': 'stable_count',
              'DebounceCycles': 2500000, 'DeclaredBits': 22, 'ReachableMinimum': 0,
              'ReachableMaximum': 2499999, 'UnsignedMaximum': (1 << 22) - 1,
              'NoWidthDiagnosticObserved': True, 'PublicRTLBoundProved': True,
              'Reason': 'Reset/opposite input clears zero; terminal sample at2499999 clears zero; only values below2499999 increment. Both release and press phases use the same bound.',
              'SynthesisEquivalenceProved': False}
    result = {'Schema': SCHEMA, 'Target': build.TARGET, 'CreatedUTC': datetime.now(timezone.utc).isoformat(),
              'Producer': bind(SELF), 'BuildPlan': bind(build_path), 'BuildReceipt': bind(receipt_path),
              'BaselineDisposition': bind(BASELINE, BASELINE_SHA), 'BaselineBuildPlan': bind(old_build_path),
              'BaselineBuildReceipt': bind(old_receipt_path), 'CandidateADF': bind(receipt['ADF'], receipt['ADFSHA256']),
              'OriginalBuildCompleted': receipt['BuildCompleted'], 'OriginalReceiptModified': False,
              'BuildDiagnosticsCleared': False, 'Diagnostics': diagnostics,
              'DiagnosticsSHA256': hashlib.sha256(json.dumps(diagnostics, separators=(',', ':')).encode()).hexdigest(),
              'ExactDiagnosticsEqualAfterBuildPathNormalization': True,
              'DiagnosticComparisonScope': 'Each native diagnostic text after stripping its log-role prefix; normalize only source root through /compiled/. Full original rows are retained.',
              'LogRoleAliases': {'stdout.log': 'execution-stdout.log'},
              'DiagnosticsSummary': {'RecordedCount': len(diagnostics), 'BaselineRecordedCount': len(old_receipt['Diagnostics']),
                  'LogCopies': {name: len(rows) for name, rows in current_logs.items()}, 'EventsPerLog': len(events),
                  'DistinctDiagnosticTextCount': len(set(current_logs['compile/run.log'])), 'PublicRTLEvents': 11,
                  'ProtectedVendorEvents': 2, 'AllCopiesMatchCompileEventMultiset': True},
              'DiagnosticEvents': events, 'CurrentDDRParameterBlocks': ddr_params,
              'ProtectedVendorProvenance': {'FilesIdentical': True, 'FileCount': len(vendor_rows),
                  'Files': vendor_comparison, 'PrintedDDRParametersIdentical': True,
                  'ParameterBlockCount': len(ddr_params), 'EncryptedInternalBoundIndependentlyProved': False,
                  'PriorHardwareOrTimingAcceptanceInherited': False},
              'NewButtonCounterReview': button, 'PublicCounterBoundsReviewed': True,
              'VendorSameConfigurationProvenanceReviewed': True,
              'ExactDiagnosticsExplainedForReadOnlyInvestigation': True, 'SynthesisEquivalenceProved': False,
              'TimingAccepted': False, 'HardwareReleaseAllowed': False, 'HardwareAccessed': False, 'EDAExecutedByReview': False,
              'InputSHA256': watched,
              'Limits': ['Exact recorded native critical diagnostics remain retained; this disposition does not clear them.',
                         'Public digital counter induction assumes established reset and exact source/actual parameter values.',
                         'Two protected vendor counter internals are not independently proved; only identical bytes and elaborated configuration are established.',
                         'The new candidate requires its own reset, IO, CDC, functional and full dual-corner timing verification.']}
    require(all(Path(p).is_file() and sha(p) == h for p, h in watched.items()), 'diagnostic input drift')
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--build-plan', type=Path, default=DEFAULT_BUILD)
    p.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    a = p.parse_args()
    value = inspect(a.build_plan)
    build.write(a.output, value)
    require(read(a.output) == value, 'diagnostic output readback differs')
    print(json.dumps({'Output': str(a.output.resolve()), 'SHA256': sha(a.output),
                      'Summary': value['DiagnosticsSummary'], 'InputCount': len(value['InputSHA256'])}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
