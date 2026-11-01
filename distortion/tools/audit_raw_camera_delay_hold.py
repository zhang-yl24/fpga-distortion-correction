"""Extract actual raw-camera input/DDR hold failures and exact setup margins.

External input paths can share a net. The proposed change is one physical
branch, never an inferred clock exception or a changed external delay budget.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

import audit_camera_vga_hold as common

require, sha = common.require, common.sha


def detailed(path):
    if not path['Source'].endswith(' (port)'):
        return common.parse_path(path['_Lines'], path['Report'], path['ReportLine'])
    text = ''.join(path['_Lines'])
    require(path['Source'].startswith('cam_data['), 'unexpected external hold source')
    rows, active = [], False
    for offset, line in enumerate(path['_Lines']):
        if line.startswith(' Input external delay'):
            active = True
            continue
        if active and line.startswith(' Data arrival time'):
            break
        if not active:
            continue
        net, pin = common.NET.fullmatch(line), common.PIN.fullmatch(line)
        if net:
            rows.append({'Type': 'net', 'Name': net[4].strip(), 'Fanout': int(net[1]),
                         'DelayNS': float(net[2]), 'CumulativeNS': float(net[3]),
                         'ReportLine': path['ReportLine'] + offset})
        elif pin:
            rows.append({**common.physical_pin(pin[1]), 'Type': 'pin', 'LogicalResource': pin[6].strip(),
                         'ReportLine': path['ReportLine'] + offset})
    require(len(rows) >= 3 and [r['Type'] for r in rows[-3:]] == ['pin', 'net', 'pin'],
            'external endpoint lacks an exact terminal net')
    require(rows[-1]['LogicalResource'] == path['Endpoint'], 'external terminal endpoint differs')
    rows[-2].update(FromRoutePin=rows[-3]['RoutePin'], ToRoutePin=rows[-1]['RoutePin'])
    return {**{k: v for k, v in path.items() if k != '_Lines'}, 'DataTrace': rows,
            'PathSHA256': hashlib.sha256(text.encode()).hexdigest(), '_Text': text}


def build(reports, expected_target):
    require(expected_target in ('raw_camera_capture_cam2_delay',),
            'unsupported raw target')
    provenance, initial, summaries = [], [], []
    for report in reports:
        report = Path(report).resolve()
        with report.open(encoding='utf-8-sig') as stream:
            head = ''.join(next(stream) for _ in range(12))
        require(re.search(r'\| Design\s*:\s*' + re.escape(expected_target) + r'\s*\n', head), 'wrong native report target')
        paths, tables, record = common.read_report(report)
        initial.extend(paths)
        summaries.extend(tables)
        provenance.append(record)
    failures = {common.identity(p) for p in initial if p['Kind'] == 'hold' and p['SlackNS'] < 0}
    for row in summaries:
        if row['Kind'] == 'hold' and row['FailingChecks']:
            exact = {common.identity(p) for p in initial if p['Kind'] == 'hold' and p['SlackNS'] < 0
                     and (p['Corner'], p['LaunchClock'], p['CaptureClock']) ==
                     (row['Corner'], row['LaunchClock'], row['CaptureClock'])}
            require(len(exact) == row['FailingChecks'], 'negative detail coverage differs from summary')
    selected = []
    for report in reports:
        paths, _, _ = common.read_report(report, failures)
        selected.extend(paths)
    rows, excerpts = [], {}
    for number, key in enumerate(sorted(failures), 1):
        cases, seen = [], set()
        for path in selected:
            if common.identity(path) != key:
                continue
            value = detailed(path)
            if value['PathSHA256'] in seen:
                continue
            seen.add(value['PathSHA256'])
            name = f'path-{number:02d}-{value["Corner"]}-{value["Kind"]}-{len(cases)+1}.txt'
            excerpts[name] = value.pop('_Text')
            cases.append({**value, 'Excerpt': name})
        holds = [v for v in cases if v['Kind'] == 'hold']
        require({v['Corner'] for v in holds} == {'slow', 'fast'}, 'exact hold records in both corners required')
        terminals = [v['DataTrace'][-2] for v in holds]
        identities = {(v['Name'], v['FromRoutePin'], v['ToRoutePin'], v['Fanout']) for v in terminals}
        require(len(identities) == 1, 'terminal branch changes between corners')
        net, source_pin, target_pin, fanout = identities.pop()
        margins = {}
        for corner in ('slow', 'fast'):
            setup = [v['SlackNS'] for v in cases if v['Corner'] == corner and v['Kind'] == 'setup']
            margins[corner] = {'HoldSlackNS': min(v['SlackNS'] for v in holds if v['Corner'] == corner),
                               'ExactSetupFound': bool(setup), 'ExactSetupSlackNS': min(setup) if setup else None}
        rows.append({'PathNumber': number, 'Source': key[0], 'Endpoint': key[1],
                     'LaunchClock': key[2], 'CaptureClock': key[3], 'Cases': cases, 'Margins': margins,
                     'PhysicalRepairCandidate': {'Net': net, 'FromRoutePin': source_pin, 'ToRoutePin': target_pin,
                         'Fanout': fanout, 'BranchOnly': True, 'TimingWaiverAllowed': False,
                         'PreserveOtherBranches': True, 'ExternalInputBudgetChanged': False}})
    missing = [{'PathNumber': row['PathNumber'], 'Corner': corner} for row in rows
               for corner, margin in row['Margins'].items() if not margin['ExactSetupFound']]
    return {'Schema': 'raw-camera-delay-hold-analysis-v1', 'Target': expected_target,
            'GeneratedUTC': datetime.now(timezone.utc).isoformat(), 'ExtractionComplete': True,
            'InputReports': provenance, 'ToolSHA256': sha(__file__), 'CommonParserSHA256': sha(common.__file__),
            'HoldFailingPathCount': len(rows), 'Paths': rows, 'MissingExactSetup': missing,
            'HoldFailureSummary': [s for s in summaries if s['Kind'] == 'hold' and s['FailingChecks']],
            'HardwareAccessed': False, 'TimingClosed': False,
            'Limits': 'Exact endpoints only. Shared-net branch connectivity/occupancy and post-change full STA remain required. External AC budgets remain provisional.'}, excerpts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, action='append', required=True)
    parser.add_argument('--target', required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    require(not args.out.exists(), 'fresh audit directory required')
    record, excerpts = build(args.report, args.target)
    args.out.mkdir(parents=True)
    for name, data in excerpts.items():
        (args.out / name).write_text(data, encoding='utf-8', newline='\n')
    (args.out / 'hold-analysis.json').write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'HoldFailures': record['HoldFailingPathCount'], 'MissingExactSetup': record['MissingExactSetup']}))


if __name__ == '__main__':
    main()
