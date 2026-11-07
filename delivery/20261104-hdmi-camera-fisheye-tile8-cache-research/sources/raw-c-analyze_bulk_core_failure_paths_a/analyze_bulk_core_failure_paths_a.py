"""Extract every actual bulk research ordinary-core slow setup failure; read-only."""
from pathlib import Path
from collections import Counter
import hashlib
import json
import mmap
import re

OUT = Path(__file__).resolve().parent
WORK = OUT.parents[1] / 'distortion/work/hdmi-camera-fisheye-tile8df8bulk-20261104-a'
REPORT = WORK / 'build-a/report_timing/hdmi_camera_fisheye_top.rtr'
OUTPUT = OUT / 'bulk-ordinary-core-failure-paths-a.json'
EXCERPT = OUT / 'bulk-ordinary-core-failure-paths-a.txt'


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(8 * 1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def main():
    assert not OUTPUT.exists() and not EXCERPT.exists()
    receipt_path = WORK / 'raw-core-timing-a.json'
    receipt = json.loads(receipt_path.read_text())
    failures, excerpts = [], []
    total = 0
    with REPORT.open('rb') as stream, mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ) as source:
        start = source.find(b'Startpoint  :')
        while start >= 0:
            total += 1
            end = source.find(b'\nStartpoint  :', start + 1)
            end = len(source) if end < 0 else end + 1
            header = source[start:min(start + 1200, end)]
            if b'Path Group  : ddrphy_sysclk' in header and b'Path Type   : max (slow corner)' in header:
                failure = source.find(b'Slack (VIOLATED)', start, end)
                if failure >= 0:
                    text = source[start:end].decode('gb18030')
                    clocks = re.findall(r'(?m)^ Clock\s+(\S+)\s+\(', text)
                    if clocks == ['ddrphy_sysclk', 'ddrphy_sysclk']:
                        get = lambda label: re.search(r'(?m)^' + re.escape(label) + r'\s*:\s*(.*)', text)[1].strip()
                        slack = float(re.search(r'Slack \(VIOLATED\)\s+(-?[0-9.]+)', text)[1])
                        levels = int(re.search(r'Logic Levels:\s*(\d+)', text)[1])
                        metrics = re.search(r'Logic:\s*([0-9.]+)ns\(([0-9.]+)%\), Route:\s*([0-9.]+)ns\(([0-9.]+)%\)', text)
                        data = text[text.index(' tco '):text.index('Data arrival time')]
                        # Include the complete launch pin line, not only the
                        # tco token, in the retained exact excerpt.
                        first_tco = text.rfind('\n', 0, text.index(' tco '))
                        data = text[first_tco + 1:text.index('Data arrival time')]
                        nets = []
                        for line in data.splitlines():
                            net = re.search(r'net \(fanout=(\d+)\)\s+([0-9.]+)\s+([0-9.]+)\s+(.*)', line)
                            if net:
                                nets.append({'Fanout': int(net[1]), 'RouteNS': float(net[2]), 'CumulativeNS': float(net[3]), 'Net': net[4].strip()})
                        row = {'FirstByteOffset': start, 'Startpoint': get('Startpoint'), 'Endpoint': get('Endpoint'),
                               'Clocks': clocks, 'SlackNS': slack, 'LogicLevels': levels,
                               'LogicNS': float(metrics[1]), 'LogicPercent': float(metrics[2]),
                               'RouteNS': float(metrics[3]), 'RoutePercent': float(metrics[4]),
                               'DataPathLines': [line for line in data.splitlines() if line.strip()],
                               'Nets': nets, 'MaximumDataFanout': max(n['Fanout'] for n in nets)}
                        failures.append(row)
                        excerpts.append((slack, text))
            start = source.find(b'Startpoint  :', end)
    failures.sort(key=lambda row: row['SlackNS'])
    worst = {}
    for row in failures:
        worst.setdefault(row['Endpoint'], row)
    actual_sha = sha(REPORT)
    assert actual_sha == receipt['Report']['SHA256']
    summary = next(row for row in receipt['Rows'] if row['Corner'] == 'slow' and row['Kind'] == 'setup')
    assert len(worst) == summary['FailingChecks'] == 21
    assert failures[0]['SlackNS'] == summary['WorstSlackNS'] == -0.714
    assert abs(sum(row['SlackNS'] for row in worst.values()) - summary['TotalNegativeSlackNS']) < 1e-9
    value = {'Schema': 'tile8df8bulk-actual-core-endpoint-failure-review-v1',
             'Report': receipt['Report'], 'RawCoreReceipt': {'Path': str(receipt_path), 'SHA256': sha(receipt_path)},
             'ActualOrdinaryCorePassed': False, 'FullNativeReportSHARechecked': True,
             'DetailedPathsScanned': total, 'NegativePaths': len(failures), 'UniqueFailingEndpoints': len(worst),
             'ActualSummary': summary, 'WorstPathPerFailingEndpoint': list(worst.values()), 'AllNegativePaths': failures,
             'StartpointOccurrences': dict(Counter(row['Startpoint'] for row in failures)),
             'EDAExecuted': False, 'HDLSimulationExecuted': False, 'PDriveAccessed': False, 'HardwareAccessed': False,
             'RTLModified': False, 'NewSeedStarted': False, 'TimingExceptionProposed': False}
    with OUTPUT.open('x', encoding='utf-8') as f:
        json.dump(value, f, indent=2)
        f.write('\n')
    with EXCERPT.open('x', encoding='utf-8') as f:
        for _, text in sorted(excerpts):
            f.write(text + '\n' + '=' * 100 + '\n')
    print(json.dumps({'Report': str(OUTPUT), 'SHA256': sha(OUTPUT), 'NegativePaths': len(failures),
                     'UniqueEndpoints': len(worst), 'WorstPerEndpoint': list(worst.values())}))


if __name__ == '__main__':
    main()
