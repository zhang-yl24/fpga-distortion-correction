"""Audit the independent output candidate's isolated DDR physical repair.

This consumes native artifacts only. It does not apply constraints, execute EDA,
approve reset safety, or establish external IO/CDC/hardware acceptance.
"""
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import argparse
import hashlib
import json
import re

import audit_ddr_entry_reset_netlist as dialect
import audit_ddr_final_timing as native
import audit_fresh_ddr_timing as fresh

require = native.require
sha = native.sha
READ_PAIR = ('phy_dq_sysclk_1', 'ddrphy_sysclk')
SLICE = 'u_ddr3_test_h/u_ddrphy_top/ddrphy_slice_top/i_dqs_group[1].ddrphy_data_slice/'
HOLD_SOURCE = SLICE + 'dq_loop[0].u_iobuf_dq/opit_1/ICLKDIV'
HOLD_TARGET = SLICE + 'ddrphy_dqs_rddata_align/rddata_r1[5]/opit_0_inv_srl/D'
FF = re.compile(
    r'(?P<attrs>\(\*[^*]*\*\)\s*)?'
    r'(?P<primitive>V_FFASYN|V_FFSYN)\s*/\*\s*(?P<site>\w+)\s*\*/\s*'
    r'(?:#\s*\((?P<parameters>.*?)\)\s*)?'
    r'(?P<name>\\\S+|[A-Za-z_$][\w$]*)\s*\((?P<ports>.*?)\)\s*;', re.S)


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def functional_export(path):
    return functional_text(Path(path).read_text(encoding='utf-8-sig'))


def functional_text(text):
    """Parse the checked flat native export dialect, including FF positions."""
    require('2023.2-SP3<build 154097>' in text[:300], 'native export version differs')
    clean = re.sub(r'/\*.*?\*/|//[^\n]*|\(\*.*?\*\)',
                   lambda m: '\n' * m[0].count('\n'), text, flags=re.S)
    require(re.findall(r'(?m)^module\s+(\w+)', clean) == ['processed_output_top']
            and len(re.findall(r'(?m)^endmodule\b', clean)) == 1,
            'one flat processed_output_top module required')
    cells = {}
    for match in dialect.CELL.finditer(clean):
        name = match['name'].lstrip('\\')
        require(name not in cells, 'duplicate primitive instance')
        cells[name] = {'Primitive': match['primitive'],
                       'Parameters': dialect.bindings(match['parameters']),
                       'Ports': dialect.bindings(match['ports'])}
    require(len(cells) == len(re.findall(r'(?m)^[ \t]*V_\w+\b', clean)),
            'native primitive parse is incomplete')
    require(cells, 'empty native netlist')
    remainder = ' '.join(dialect.CELL.sub('', clean).split())
    placements = {}
    for match in FF.finditer(text):
        name = match['name'].lstrip('\\')
        require(name in cells and name not in placements, 'unmatched/duplicate FF placement')
        placements[name] = {'Site': match['site'], 'Attributes': ' '.join((match['attrs'] or '').split())}
    ffs = {name for name, cell in cells.items() if cell['Primitive'] in ('V_FFASYN', 'V_FFSYN')}
    require(ffs and set(placements) == ffs, 'not every native FF has a placement comment')
    return {'Cells': cells, 'ModuleDeclarations': remainder, 'FFPlacement': placements}


def compare_exports(baseline, candidate):
    before, after = functional_export(baseline), functional_export(candidate)
    for part in ('Cells', 'ModuleDeclarations', 'FFPlacement'):
        require(before[part] == after[part], 'native functional/placement difference: ' + part)
    return {'FunctionalGraphIdentical': True, 'PrimitiveCellCount': len(before['Cells']),
            'PrimitiveCounts': dict(Counter(c['Primitive'] for c in before['Cells'].values())),
            'FunctionalGraphSHA256': fingerprint({k:before[k] for k in ('Cells', 'ModuleDeclarations')}),
            'AllFFPlacementsIdentical': True, 'FFCount': len(before['FFPlacement']),
            'FFPlacementSHA256': fingerprint(before['FFPlacement']),
            'Scope': 'Exact native primitive parameters/ports/module declarations and FF site/BLE attributes'}


def summaries(path):
    with Path(path).open(encoding='utf-8-sig', errors='strict') as stream:
        return native.parse_summaries(stream)


def compare_summaries(before, after, reset_scoped):
    require(set(before) == set(after), 'timing table inventory differs')
    reset_pairs = set(native.recovery.PAIRS) | {native.ENTRY_PAIR}
    changed, totals = [], {}
    for key, old in before.items():
        corner, kind = key
        now = after[key]
        cuts = reset_pairs if reset_scoped and kind in ('recovery', 'removal') else set()
        require(cuts <= set(old) and set(now) == set(old) - cuts,
                'unexpected timed clock pair added/removed: ' + str(key))
        for pair in cuts:
            expected = 1 if pair == native.ENTRY_PAIR else native.recovery.PAIRS[pair]
            require(old[pair]['TotalChecks'] == expected, 'removed reset check count differs')
        for pair, row in now.items():
            require(row['TotalChecks'] == old[pair]['TotalChecks'], 'timed check count changed')
            if kind in ('setup', 'hold') and pair == READ_PAIR:
                require(row['FailingChecks'] == 0 and row['WorstSlackNS'] >= 0
                        and row['TotalNegativeSlackNS'] == 0, 'repaired read pair still fails')
                if kind == 'hold':
                    require(old[pair]['FailingChecks'] == 1 and old[pair]['WorstSlackNS'] < 0,
                            'baseline must have the single known PHY read hold failure')
                if row != old[pair]:
                    changed.append({'Corner':corner, 'Kind':kind, 'Clocks':list(pair),
                                    'Before':old[pair], 'After':row})
            else:
                require(row == old[pair], 'unrelated timing row changed: ' + str((key, pair)))
            if reset_scoped or kind != 'recovery':
                require(row['FailingChecks'] == 0 and row['WorstSlackNS'] >= 0
                        and row['TotalNegativeSlackNS'] == 0, 'remaining native timing failure')
        totals[corner + '_' + kind] = {
            'WorstSlackNS': min(row['WorstSlackNS'] for row in now.values()),
            'FailingChecks': sum(row['FailingChecks'] for row in now.values()),
            'TimedChecks': sum(row['TotalChecks'] for row in now.values()),
            'RemovedResetChecks': sum(old[pair]['TotalChecks'] for pair in cuts)}
    require(sum(row['Kind'] == 'hold' for row in changed) == 2, 'both corner hold improvements required')
    return changed, totals


def target_paths(path):
    """Stream the potentially very large native report; retain this data bit."""
    result, block, line_number = [], [], 0
    def finish():
        if not block:
            return
        text = ''.join(block)
        if not re.search(r'(?m)^Endpoint\s*:\s*' + re.escape(HOLD_TARGET) + r'\s*$', text):
            return
        kind = re.findall(r'(?m)^ (Setup|Hold) time\s', text)
        if not kind:
            return
        require(len(kind) == 1, 'ambiguous target check kind')
        value = native.path_record(block)
        require(value['Source'] == HOLD_SOURCE and value['Endpoint'] == HOLD_TARGET
                and (value['LaunchClock'], value['CaptureClock']) == READ_PAIR,
                'target launch/capture identity changed')
        slacks = re.findall(r'(?m)^ Slack \((MET|VIOLATED)\)\s+(' + native.NUM + r')\s*$', text)
        require(len(slacks) == 1, 'target slack is missing/ambiguous')
        require('_N107' in text, 'target no longer traverses the reviewed data branch')
        value.update(Kind=kind[0].lower(), SlackNS=float(slacks[0][1]), SlackState=slacks[0][0],
                     NativeReportLine=line_number,
                     NativePathSHA256=hashlib.sha256(text.encode()).hexdigest())
        result.append(value)
    with Path(path).open(encoding='utf-8-sig', errors='strict') as stream:
        for lineno, line in enumerate(stream, 1):
            if line.startswith('Startpoint'):
                finish()
                block, line_number = [line], lineno
            elif block:
                block.append(line)
    finish()
    require({(r['Corner'], r['Kind']) for r in result} ==
            {(c,k) for c in ('slow','fast') for k in ('setup','hold')},
            'exact read bit needs both corner setup and hold native paths')
    return result


def other_exceptions(path):
    """Retain every non-false exception's complete normalized native path."""
    sections, pending, section, block = {}, None, None, []
    def finish():
        if block and section is not None and not section[1].startswith('set_false_path('):
            # Sort fingerprints later: reporter ordering is not a path change.
            body = []
            for line in block:
                if line.strip() and not set(line.strip()) <= set('=-*'):
                    body.append(native.normalize(line))
                if line.startswith(' Slack'):
                    break
            sections[section].append(hashlib.sha256('\n'.join(body).encode()).hexdigest())
    with Path(path).open(encoding='gb18030', errors='strict') as stream:
        for line in stream:
            header = native.EX_HEADER.fullmatch(line.rstrip('\r\n'))
            if header:
                finish()
                block, section, pending = [], None, header[1]
                continue
            corner = re.fullmatch(r'\| (Slow|Fast) Corner\s*', line)
            if pending is not None and corner:
                section = (corner[1].lower(), pending)
                require(section not in sections, 'duplicate native exception section')
                sections[section] = []
                pending = None
                continue
            if line.startswith('Startpoint'):
                finish()
                block = [line]
            elif block:
                block.append(line)
    finish()
    require(len(sections) == 24, 'all native exception categories/corners required')
    return {str(key):{'Paths':len(value), 'SortedFullPathSHA256':fingerprint(sorted(value))}
            for key,value in sorted(sections.items()) if not key[1].startswith('set_false_path(')}


def audit(baseline_report, baseline_exceptions, candidate_report, candidate_exceptions,
          baseline_netlist, candidate_netlist, candidate_adf, candidate_snapshot, *, reset_scoped=False):
    files = [Path(p).resolve() for p in (baseline_report, baseline_exceptions, candidate_report,
             candidate_exceptions, baseline_netlist, candidate_netlist, candidate_adf, candidate_snapshot)]
    watched = {str(p):sha(p) for p in files}
    require(sha(candidate_adf) == sha(candidate_snapshot), 'candidate ADF changed across STA')
    tools = {str(Path(p).resolve()):sha(p) for p in
             (__file__, native.__file__, fresh.__file__, fresh.variants.__file__,
              native.recovery.__file__, dialect.__file__)}
    before, before_clocks = summaries(baseline_report)
    after, after_clocks = summaries(candidate_report)
    require(before_clocks == after_clocks, 'native clock definitions or loads changed')
    changed, totals = compare_summaries(before, after, reset_scoped)
    with Path(baseline_exceptions).open(encoding='gb18030', errors='strict') as stream:
        old_false = native.parse_false_paths(stream)
    require(all(not v for v in old_false.values()), 'baseline already contains false-path cuts')
    with Path(candidate_exceptions).open(encoding='gb18030', errors='strict') as stream:
        new_false = native.parse_false_paths(stream)
    recovery_inventory = None
    if reset_scoped:
        expected, recovery_inventory, entries = fresh.expected_paths(baseline_report)
        false_counts = native.validate_exception_sets(new_false, expected)
    else:
        require(all(not v for v in new_false.values()), 'hold-only candidate introduced false paths')
        false_counts = {str(k):len(v) for k,v in new_false.items()}
    prior_other = other_exceptions(baseline_exceptions)
    require(prior_other == other_exceptions(candidate_exceptions),
            'non-false timing exception paths or their delays changed')
    old_target, new_target = target_paths(baseline_report), target_paths(candidate_report)
    require(all(r['SlackState'] == 'MET' and r['SlackNS'] >= 0 for r in new_target),
            'repaired bit setup/hold native path failed')
    exports = compare_exports(baseline_netlist, candidate_netlist)
    require(all(sha(p) == h for p,h in watched.items()), 'audit input changed')
    require(all(sha(p) == h for p,h in tools.items()), 'audit implementation changed')
    return {'Schema':'processed-output-physical-comparison-v1',
            'AuditedUTC':datetime.now(timezone.utc).isoformat(), 'AuditPassed':True,
            'ResetExceptionsApplied':reset_scoped,
            'AllReportedInternalTimingChecksMet':all(r['FailingChecks'] == 0 for r in totals.values()),
            'AllTenNativeTimingTablesChecked':True, 'NativeClockDefinitionsAndLoadsUnchanged':True,
            'NativeExceptionReportEncoding':'gb18030-strict (PDS infinity A1 DE retained)',
            'OnlyTargetReadPairSummarySlacksChanged':True, 'Changes':changed,
            'CornerSummaries':totals, 'FalsePathCounts':false_counts,
            'NoDataSetupOrHoldFalsePaths':True, 'AllOtherExceptionPathsUnchanged':prior_other,
            'TargetBitBaselinePaths':old_target,
            'TargetBitCandidatePaths':new_target, 'FunctionalAndFFPlacementComparison':exports,
            'BaselineRecoveryInventory':recovery_inventory,
            'CandidateADF':{'Path':str(Path(candidate_adf).resolve()),'SHA256':sha(candidate_adf)},
            'CandidateSnapshotMatchesADF':True, 'InputSHA256':watched, 'ToolsSHA256':tools,
            'HardwareAccessed':False, 'BitstreamRequested':False, 'HardwareReleaseAllowed':False,
            'ExternalIOAccepted':False, 'CDCPhysicalAccepted':False, 'ResetSafetyAccepted':False,
            'Limitations':['Scope is native internal timing, exact exception effects, functional graph and FF placement.',
                          'This does not prove every unrelated wire route unchanged; route query evidence is separate.',
                          'Reset correctness, external IO AC, CDC skew/MTBF, DDR training and visible board output require separate evidence.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    names = ('baseline-report','baseline-exceptions','candidate-report','candidate-exceptions',
             'baseline-netlist','candidate-netlist','candidate-adf','candidate-snapshot')
    for name in names:
        parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--reset-scoped', action='store_true')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = audit(*(getattr(args, n.replace('-','_')) for n in names), reset_scoped=args.reset_scoped)
    with args.output.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps({k:result[k] for k in ('AuditPassed','AllReportedInternalTimingChecksMet','HardwareReleaseAllowed')}))


if __name__ == '__main__':
    main()
