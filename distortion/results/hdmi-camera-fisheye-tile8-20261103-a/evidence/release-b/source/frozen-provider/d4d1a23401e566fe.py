"""Inventory all ten current 720p native timing tables without applying scope.

Only a rebound read-only camera720_inspect receipt is accepted. Every failing
clock pair remains visible, including newly added monitor/reset paths. This
does not derive or approve exceptions, prove path coverage, or access PDS.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re

import camera720_inspect as inspect
import audit_ddr_final_timing as syntax

prep, require, sha = inspect.prep, inspect.require, inspect.sha
SELF = Path(__file__).resolve()
SCHEMA = 'camera720-native-timing-inventory-v1'
DESIGN = re.compile(r'^\| Design\s*:\s*(\S+)\s*$', re.M)


def recovery_record(lines):
    """Preserve normal and datapath-only recovery records without inventing clocks.

    PDS suppresses both clock edge rows for a max-delay -datapath_only
    recovery check. Its path group identifies the destination domain, but
    does not prove a source clock or either clock edge. Such records cannot
    become ordinary DDR reset exception candidates.
    """
    text = ''.join(lines)
    clocks = re.findall(r'^ Clock (\S+) \((rising|falling) edge\)', text, re.M)
    exceptions = re.findall(r'^Timing Exception\s*:\s*(.*?)\s*$', text, re.M)
    if len(clocks) == 2 and not exceptions:
        record = syntax.path_record(lines)
        require(record['PathClass'] == 'async timing path', 'recovery is not an ordinary async path')
        record.update(ClockEdgesPresent=True, DatapathOnly=False, TimingException=None)
        return record
    require(not clocks and len(exceptions) == 1,
            'recovery clock rows absent/ambiguous without an exact datapath-only exception')
    delay = re.fullmatch(r'MaxDelay Path ('+syntax.NUM+r')ns -datapath_only', exceptions[0])
    require(delay is not None, 'unsupported clockless recovery exception')

    def one(pattern, label):
        values = re.findall(pattern, text, re.M)
        require(len(values) == 1, 'missing/ambiguous datapath recovery '+label)
        return values[0]

    source = one(r'^Startpoint\s*:\s*(\S+)\s*$', 'source')
    endpoint = one(r'^Endpoint\s*:\s*(\S+)\s*$', 'endpoint')
    group = one(r'^Path Group\s*:\s*(\S+)\s*$', 'group')
    corner = one(r'^Path Type\s*:\s*max \((slow|fast) corner\)\s*$', 'type')
    cls = one(r'^Path Class\s*:\s*(.*?)\s*$', 'class')
    require(cls == 'async timing path', 'datapath recovery is not an async path')
    constraint = int(one(r'^Exception constraint line number:\s*(\d+)\s*$', 'constraint line'))
    return {'Source': source, 'Endpoint': endpoint, 'LaunchClock': None,
            'CaptureClock': None, 'LaunchEdge': None, 'CaptureEdge': None,
            'PathGroup': group, 'Corner': corner, 'PathClass': cls,
            'ClockEdgesPresent': False, 'DatapathOnly': True,
            'TimingException': exceptions[0], 'MaximumDatapathNS': delay[1],
            'ConstraintLine': constraint}


def parse_report(report):
    text = Path(report).read_text(encoding='utf-8-sig')
    require(DESIGN.findall(text) == [prep.TARGET], 'exactly one current 720p native report identity required')
    require('2023.2-SP3 <build 154097>' in text[:1000]
            and re.search(r'^\| Device\s*:\s*PG2L100H\s*$', text, re.M)
            and re.search(r'^\| Speed Grade\s*:\s*-6\s*$', text, re.M)
            and re.search(r'^\| Package\s*:\s*FBG676\s*$', text, re.M), 'native tool/device identity differs')
    lines = text.splitlines(keepends=True)
    # These generic parsing functions use no historical target totals or reset
    # PAIRS/SOURCES. In particular expected_paths/build are never called.
    tables, clocks = syntax.parse_summaries(iter(lines))
    summaries, failures = {}, []
    for (corner, kind), rows in sorted(tables.items()):
        output = []
        for pair, value in sorted(rows.items()):
            require(0 <= value['FailingChecks'] <= value['TotalChecks'], 'invalid native check count')
            item = {'Clocks': list(pair), **value}
            output.append(item)
            if value['FailingChecks'] or value['WorstSlackNS'] < 0 or value['TotalNegativeSlackNS'] < 0:
                failures.append({'Corner': corner, 'Kind': kind, **item})
        summaries[corner+'_'+kind] = {
            'WorstSlackNS': min(row['WorstSlackNS'] for row in rows.values()),
            'FailingChecks': sum(row['FailingChecks'] for row in rows.values()),
            'TotalChecks': sum(row['TotalChecks'] for row in rows.values()), 'Rows': output}
    details, block, first_line = [], [], 0

    def finish():
        if not block or not any(re.match(r'^ Recovery time\s', line) for line in block):
            return
        record = recovery_record(block)
        slacks = re.findall(r'^ Slack \((MET|VIOLATED)\)\s+('+syntax.NUM+r')\s*$', ''.join(block), re.M)
        require(len(slacks) == 1, 'recovery detail has no unique native slack')
        record.update(NativeReportLine=first_line, SlackState=slacks[0][0], SlackNS=slacks[0][1])
        # A discovery hint, never an electrical or logical reset classification.
        names = (record['Source'], record['Endpoint'])
        record['HierarchyHint'] = ('camera_monitor' if any(n.startswith('camera_configuration/monitor/') for n in names)
                                   else 'ddr' if any(n.startswith('u_ddr3_test_h/') for n in names) else 'other')
        details.append(record)

    for line_number, line in enumerate(lines, 1):
        if line.startswith('Startpoint'):
            finish()
            block, first_line = [line], line_number
        elif block:
            block.append(line)
    finish()
    return summaries, clocks, failures, details


def run(receipt):
    value, watched = inspect.bind_receipt(receipt)
    receipt = Path(receipt).absolute()
    names = [n for n in value['Artifacts'] if Path(n).name == prep.TARGET+'.rtr'
             and 'report_path_timing' not in Path(n).parts]
    require(len(names) == 1, 'one bound complete native timing report required')
    report = inspect.canonical(receipt.parent/names[0], receipt.parent)
    for module in (inspect, prep, inspect.diagnostic, syntax, syntax.recovery):
        path = Path(module.__file__).resolve()
        watched[path] = sha(path)
    watched[SELF] = sha(SELF)
    summaries, clocks, failures, details = parse_report(report)
    require(not inspect.drift(watched), 'native evidence or parser changed during inventory')
    return {'Schema': SCHEMA, 'Target': prep.TARGET, 'CreatedUTC': datetime.now(timezone.utc).isoformat(),
            'InspectionReceipt': {'Path': str(receipt), 'SHA256': sha(receipt)},
            'SourceADFSHA256': value['SourceADFSHA256'],
            'NativeReport': {'Path': str(report), 'SHA256': sha(report)},
            'SourceSHA256': {str(p): h for p, h in watched.items()},
            'NativeParserFunctions': ['audit_ddr_final_timing.parse_summaries',
                                      'audit_camera720_timing_inventory.recovery_record'],
            'TenTimingTablesPresent': True, 'SummaryChecksAllMet': not failures,
            'ClockSummary': clocks, 'Summaries': summaries, 'FailingClockGroups': failures,
            'DetailedRecoveryRecords': details, 'DetailedRecoveryCompletenessProved': False,
            'HistoricalEndpointInventoryUsed': False, 'MonitorCDCPhysicalCoverageProved': False,
            'TimingExceptionApproved': False, 'ConstraintsApplied': False,
            'TimingAccepted': False, 'OpticalCorrectionAccepted': False,
            'HardwareAccessed': False, 'EDAExecuted': False, 'HardwareReleaseAllowed': False,
            'Limits': 'Inventory of native reported checks only. Detailed path limits may truncate coverage. '
                      'Hierarchy hints are not reset-graph proof. New monitor Gray/held-bus/synchronizer/reset '
                      'paths, input delays/pads and any proposed DDR reset scope need independent audits.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--receipt', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.absolute()
    require(output == output.resolve() and output.is_relative_to(prep.WORK)
            and output.parent.is_dir() and not output.exists(), 'fresh canonical output under 720 workspace required')
    result = run(args.receipt)
    with output.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    print(json.dumps({'InventoryCreated': str(output), 'TenTimingTablesPresent': True,
                      'SummaryChecksAllMet': result['SummaryChecksAllMet'],
                      'FailingClockGroups': len(result['FailingClockGroups']),
                      'TimingAccepted': False, 'HardwareAccessed': False}))


if __name__ == '__main__':
    main()
