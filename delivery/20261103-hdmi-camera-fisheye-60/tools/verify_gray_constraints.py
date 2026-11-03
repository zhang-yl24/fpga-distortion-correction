#!/usr/bin/env python3
"""Verify PDS Gray-only delay/skew bounds against every expected endpoint.

Run after a fresh build with report_timing -report_exception TRUE
-report_max_skew. The full design expects capture pointer 7 + display pointer 10
bits, in both directions. This checks constraint binding, not CDC signoff.
"""
from pathlib import Path
import argparse
import hashlib
import json
import re
import xml.etree.ElementTree as ET


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(project, layout):
    db = project / 'prj_tasks/pnr_1/report_timing/report_db'
    instances = [('capture_size', 7), ('display_size', 10)] if layout == 'probe' else [
        ('system/input_link/input_dma/capture/pixels', 7), ('system/display_fifo', 10)]
    expected = {}
    groups = []
    for inst, bits in instances:
        for direction, stage in [('rd', 'w'), ('wr', 'r')]:
            group = set()
            for bit in range(bits):
                target = f'{inst}/{direction}_gray_{stage}1[{bit}]'
                source = f'{inst}/{direction}_gray[{bit}]'
                allowed = {source}
                if bit == bits - 1:
                    allowed.add(f'{inst}/{direction}_binary[{bit}]')
                expected[target] = allowed
                group.add(target)
            groups.append(group)
    reports = {}
    hashes = {}
    errors = []
    for corner in ['slow', 'fast']:
        path = db / f'exception_report_{corner}_set_max_delay_setup.db'
        hashes[str(path)] = sha(path)
        table = ET.parse(path).getroot().find('table')
        heads = [x.text for x in table.find('column_headers')]
        rows = []
        for row in table.findall('row'):
            value = {key: (x.text or '') for key, x in zip(heads, row.findall('data'))}
            target = value['End Point'].split('/opit_')[0]
            arrival = row.find('.//table[@id="arrival"]')
            nets = []
            for ar in arrival.findall('row'):
                data = [x.text or '' for x in ar.findall('data')]
                if 'net' in data[1]:
                    nets.append(re.sub(r'\s+', '', data[5]))
            if target not in expected or not expected[target].intersection(nets):
                errors.append(f'Unexpected physical source/endpoint: {target}: {nets}')
            if value['Exception'] != 'MaxDelay Path 6.000ns -datapath_only':
                errors.append(f'Unexpected timing exception for {target}: {value["Exception"]}')
            if float(value['Requirement']) != 6 or float(value['Slack']) < 0:
                errors.append(f'{corner}: 6 ns max-delay failed: {target}: {value["Slack"]}')
            value.update(target=target, source_nets=nets)
            rows.append(value)
        if len(rows) != 34 or {row['target'] for row in rows} != set(expected):
            errors.append(f'{corner}: require exactly 34 unique Gray first-stage paths; observed {len(rows)}')
        path = db / f'report_timing_{corner}_path_max_skew.db'
        hashes[str(path)] = sha(path)
        table = ET.parse(path).getroot().find('table')
        heads = [x.text for x in table.find('column_headers')]
        skew = []
        for row in table.findall('row'):
            value = {key: (x.text or '') for key, x in zip(heads, row.findall('data'))}
            if float(value['Required Skew']) != 6 or float(value['Slack']) < 0:
                errors.append(f'{corner}: 6 ns skew failed: {value}')
            endpoints = set()
            for rr in row.findall('.//row'):
                data = rr.findall('data')
                if len(data) == 14 and data[5].text:
                    endpoints.add(data[5].text.split('/opit_')[0])
            if endpoints not in groups:
                errors.append(f'{corner}: unexpected skew group: {sorted(endpoints)}')
            value['endpoints'] = sorted(endpoints)
            skew.append(value)
        if len(skew) != 4 or set().union(*(set(x['endpoints']) for x in skew)) != set(expected):
            errors.append(f'{corner}: require all four independent skew groups; observed {len(skew)}')
        reports[corner] = dict(maxdelay_paths=len(rows),
            worst_slack_ns=min((float(row['Slack']) for row in rows), default=None),
            max_data_delay_ns=max((float(row['Data delay']) for row in rows), default=None),
            paths=rows, skew_groups=skew)
    return dict(status='FAIL' if errors else 'PASS', errors=errors, project=str(project), layout=layout, reports=reports,
                sha256=hashes, scope='Exact Gray first-stage bounds only; CDC/reset/MTBF, held bundles and external IO require separate review.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, required=True)
    parser.add_argument('--layout', choices=['probe', 'full'], default='full')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        result = verify(args.project.resolve(), args.layout)
    except (OSError, ValueError, KeyError, TypeError, AttributeError, ET.ParseError) as error:
        db = args.project / 'prj_tasks/pnr_1/report_timing/report_db'
        present = sorted(set(db.glob('exception_report_*_set_max_delay_setup.db')) |
                         set(db.glob('report_timing_*_path_max_skew.db')))
        result = dict(status='FAIL', project=str(args.project.resolve()), layout=args.layout,
                      errors=[f'{type(error).__name__}: {error}'], reports={},
                      sha256={str(path): sha(path) for path in present})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'status': result['status'], 'errors': result.get('errors', [])}))
    print(json.dumps({corner: {key: value for key, value in row.items()
                      if key not in ('paths', 'skew_groups')}
                      for corner, row in result['reports'].items()}, indent=2))
    if result['status'] != 'PASS':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
