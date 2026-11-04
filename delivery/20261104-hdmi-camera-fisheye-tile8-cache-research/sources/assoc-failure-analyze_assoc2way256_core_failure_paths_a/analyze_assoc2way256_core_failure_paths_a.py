"""Read every actual assoc2way256 ordinary-core slow setup path; no EDA."""
from pathlib import Path
from collections import Counter
import hashlib
import json
import mmap
import re

OUT = Path(__file__).resolve().parent
WORK = OUT.parents[1] / 'distortion/work/hdmi-camera-fisheye-assoc2way256-20261104-a'
REPORT = WORK / 'build-a/report_timing/hdmi_camera_fisheye_top.rtr'
OUTPUT = OUT / 'assoc2way256-ordinary-core-failure-paths-a.json'
EXCERPT = OUT / 'assoc2way256-ordinary-core-failure-paths-a.txt'

def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()

def family(name):
    leaf = name.rsplit('/', 1)[-1]
    return re.sub(r'(?:\[\d+\]|_\d+)+$', '', leaf)

def main():
    assert not OUTPUT.exists() and not EXCERPT.exists()
    before = REPORT.stat()
    failures, excerpts = [], []
    total = 0
    with REPORT.open('rb') as stream, mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ) as source:
        head = source[:30000].decode('gb18030')
        setup = head.split('Setup Summary(Slow Corner):', 1)[1].split('Hold Summary', 1)[0]
        fields = re.search(r'(?m)^\s*ddrphy_sysclk\s+ddrphy_sysclk\s+(-?[0-9.]+)\s+(-?[0-9.]+)\s+(\d+)\s+(\d+)\s*$', setup)
        assert fields
        summary = dict(Corner='slow', Kind='setup', WorstSlackNS=float(fields[1]), TotalNegativeSlackNS=float(fields[2]), FailingChecks=int(fields[3]), TotalChecks=int(fields[4]))
        start = source.find(b'Startpoint  :')
        while start >= 0:
            total += 1
            end = source.find(b'\nStartpoint  :', start + 1)
            end = len(source) if end < 0 else end + 1
            header = source[start:min(start + 1200, end)]
            if b'Path Group  : ddrphy_sysclk' in header and b'Path Type   : max (slow corner)' in header and source.find(b'Slack (VIOLATED)', start, end) >= 0:
                text = source[start:end].decode('gb18030')
                clocks = re.findall(r'(?m)^ Clock\s+(\S+)\s+\(', text)
                if clocks == ['ddrphy_sysclk', 'ddrphy_sysclk']:
                    get = lambda label: re.search(r'(?m)^' + re.escape(label) + r'\s*:\s*(.*)', text)[1].strip()
                    slack = float(re.search(r'Slack \(VIOLATED\)\s+(-?[0-9.]+)', text)[1])
                    metrics = re.search(r'Logic:\s*([0-9.]+)ns\(([0-9.]+)%\), Route:\s*([0-9.]+)ns\(([0-9.]+)%\)', text)
                    data = text[text.rfind('\n', 0, text.index(' tco ')) + 1:text.index('Data arrival time')]
                    nets = []
                    for line in data.splitlines():
                        net = re.search(r'net \(fanout=(\d+)\)\s+([0-9.]+)\s+([0-9.]+)\s+(.*)', line)
                        if net:
                            nets.append(dict(Fanout=int(net[1]), RouteNS=float(net[2]), CumulativeNS=float(net[3]), Net=net[4].strip()))
                    row = dict(FirstByteOffset=start, Startpoint=get('Startpoint'), Endpoint=get('Endpoint'), Clocks=clocks, SlackNS=slack,
                               LogicLevels=int(re.search(r'Logic Levels:\s*(\d+)', text)[1]), LogicNS=float(metrics[1]), LogicPercent=float(metrics[2]),
                               RouteNS=float(metrics[3]), RoutePercent=float(metrics[4]), DataPathLines=[s for s in data.splitlines() if s.strip()],
                               Nets=nets, MaximumDataFanout=max((n['Fanout'] for n in nets), default=0))
                    failures.append(row)
                    excerpts.append((slack, text))
            start = source.find(b'Startpoint  :', end)
    failures.sort(key=lambda row: row['SlackNS'])
    worst = {}
    for row in failures:
        worst.setdefault(row['Endpoint'], row)
    assert len(worst) == summary['FailingChecks']
    assert failures[0]['SlackNS'] == summary['WorstSlackNS']
    assert abs(sum(row['SlackNS'] for row in worst.values()) - summary['TotalNegativeSlackNS']) < 1e-8
    actual_sha = sha(REPORT)
    after = REPORT.stat()
    assert (before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns)
    receipt_path = WORK / 'raw-core-timing-a.json'
    receipt_ref = None
    if receipt_path.exists():
        receipt = json.loads(receipt_path.read_text())
        assert actual_sha == receipt['Report']['SHA256']
        saved = next(row for row in receipt['Rows'] if row['Corner'] == 'slow' and row['Kind'] == 'setup')
        assert all(saved[k] == v for k, v in summary.items() if k != 'TotalChecks')
        receipt_ref = dict(Path=str(receipt_path), SHA256=sha(receipt_path))
    value = dict(Schema='assoc2way256-actual-core-endpoint-failure-review-v1', Report=dict(Path=str(REPORT), SHA256=actual_sha, Bytes=before.st_size),
                 RawCoreReceipt=receipt_ref, ActualOrdinaryCorePassed=False, FullNativeReportSHARechecked=True, DetailedPathsScanned=total,
                 NegativePaths=len(failures), UniqueFailingEndpoints=len(worst), ActualSummary=summary,
                 WorstPathPerFailingEndpoint=list(worst.values()), AllNegativePaths=failures,
                 EndpointFamilyCounts=dict(Counter(family(row['Endpoint']) for row in worst.values())),
                 StartpointFamilyCounts=dict(Counter(family(row['Startpoint']) for row in worst.values())),
                 StartpointOccurrences=dict(Counter(row['Startpoint'] for row in failures)),
                 EDAExecuted=False, HDLSimulationExecuted=False, PDriveAccessed=False, HardwareAccessed=False, RTLModified=False,
                 NewSeedStarted=False, TimingExceptionProposed=False)
    with OUTPUT.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')
    with EXCERPT.open('x', encoding='utf-8') as stream:
        for _, text in sorted(excerpts):
            stream.write(text + '\n' + '=' * 100 + '\n')
    brief = [dict(Startpoint=r['Startpoint'], Endpoint=r['Endpoint'], SlackNS=r['SlackNS'], LogicLevels=r['LogicLevels'], LogicNS=r['LogicNS'], RouteNS=r['RouteNS'], RoutePercent=r['RoutePercent'], MaximumDataFanout=r['MaximumDataFanout']) for r in failures[:10]]
    print(json.dumps(dict(Report=str(OUTPUT), SHA256=sha(OUTPUT), NegativePaths=len(failures), UniqueEndpoints=len(worst),
                         EndpointFamilyCounts=value['EndpointFamilyCounts'], StartpointFamilyCounts=value['StartpointFamilyCounts'], WorstTen=brief)))

if __name__ == '__main__':
    main()
