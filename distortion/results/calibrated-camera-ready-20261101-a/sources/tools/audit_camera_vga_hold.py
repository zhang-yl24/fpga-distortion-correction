"""Extract actual camera candidate hold failures and exact setup counterparts.

Read-only with respect to all input/EDA artifacts. It discovers failing nets
from the supplied native reports rather than inheriting another build's net
names or constraints. A passing extraction is not timing closure or permission
to waive a path. Missing exact setup paths remain explicitly unverified.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

NUM = r'[-+]?\d+(?:\.\d+)?'
SUMMARY = re.compile(r'^(Setup|Hold) Summary\((Slow|Fast) Corner\):\s*$')
SUMMARY_ROW = re.compile(r'^\s*(\S+)\s+(\S+)\s+(' + NUM + r')\s+(' + NUM + r')\s+(\d+)\s+(\d+)\s*$')
NET = re.compile(r'^\s+net \(fanout=(\d+)\)\s+(' + NUM + r')\s+(' + NUM + r')\s+(.+?)\s*$')
PIN = re.compile(r'^\s+(\w+_\d+_\d+/\S+)\s+(?:(tco|td)\s+)?(?:(' + NUM + r')\s+(' + NUM + r')\s+)?([rf])\s+(.+?)\s*$')

def require(ok, message):
    if not ok:
        raise ValueError(message)

def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for data in iter(lambda: stream.read(1 << 20), b''):
            digest.update(data)
    return digest.hexdigest()

def one(pattern, text, label):
    values = re.findall(pattern, text, re.MULTILINE)
    require(len(values) == 1, 'missing or ambiguous ' + label)
    return values[0]

def physical_pin(location):
    site, pin = location.split('/', 1)
    match = re.fullmatch(r'(.+)_(\d+)_(\d+)', site)
    require(match is not None, 'unparsed physical pin ' + location)
    return {'Location':location, 'Site':site, 'SiteKind':match[1],
            'X':int(match[2]), 'Y':int(match[3]), 'Pin':pin,
            'RoutePin':pin + ':' + site}

def parse_path(lines, report, first_line, detailed=True):
    text = ''.join(lines)
    kinds = re.findall(r'^ (Setup|Hold) time\s+', text, re.MULTILINE)
    if not kinds:
        return None
    require(len(kinds) == 1, 'multiple path check kinds')
    typ, corner = one(r'^Path Type\s*:\s*(max|min) \((slow|fast) corner\)\s*$', text, 'path type')
    kind = kinds[0].lower()
    require(typ == ('max' if kind == 'setup' else 'min'), 'kind disagrees with path type')
    clocks = re.findall(r'^ Clock (\S+) \((rising|falling) edge\)', text, re.MULTILINE)
    if len(clocks) != 2 and 'MaxDelay Path' in text and '-datapath_only' in text:
        return None
    if len(clocks) != 2 and not (kind == 'hold' and 'Slack (VIOLATED)' in text):
        return None
    require(len(clocks) == 2, 'path must contain both clock edges: ' + str(first_line))
    source = one(r'^Startpoint\s*:\s*(.+?)\s*$', text, 'source')
    target = one(r'^Endpoint\s*:\s*(.+?)\s*$', text, 'endpoint')
    slack_state, slack = one(r'^ Slack \((MET|VIOLATED)\)\s+(' + NUM + r')\s*$', text, 'slack')
    require((float(slack) < 0) == (slack_state == 'VIOLATED'), 'slack sign disagrees with state')
    if not detailed:
        return {'Source':source,'Endpoint':target,'LaunchClock':clocks[0][0],
                'CaptureClock':clocks[1][0],'LaunchEdge':clocks[0][1],'CaptureEdge':clocks[1][1],
                'Corner':corner,'Kind':kind,'SlackNS':float(slack),
                'Report':str(report),'ReportLine':first_line,'_Lines':lines}
    rows, active = [], False
    for offset, line in enumerate(lines):
        if re.search(r'\s+tco\s+', line):
            active = True
        if active and line.startswith(' Data arrival time'):
            break
        if not active or not line.strip():
            continue
        net, pin = NET.fullmatch(line), PIN.fullmatch(line)
        if net:
            rows.append({'Type':'net', 'Name':net[4].strip(), 'Fanout':int(net[1]),
                         'DelayNS':float(net[2]), 'CumulativeNS':float(net[3]),
                         'ReportLine':first_line + offset})
        elif pin:
            value = physical_pin(pin[1])
            value.update(Type='pin', LogicalResource=pin[6].strip(), DelayType=pin[2],
                         DelayNS=float(pin[3]) if pin[3] is not None else None,
                         CumulativeNS=float(pin[4]) if pin[4] is not None else None,
                         Transition=pin[5], ReportLine=first_line + offset)
            rows.append(value)
        else:
            raise ValueError('unparsed data-path row: ' + line.strip())
    require(rows and rows[0]['Type'] == rows[-1]['Type'] == 'pin', 'missing launch or endpoint pin')
    require(rows[0]['DelayType'] == 'tco' and rows[-1]['LogicalResource'] == target, 'data path endpoints differ')
    require(all(row['Type'] == ('pin' if i % 2 == 0 else 'net') for i,row in enumerate(rows)),
            'data path does not alternate primitive pins and routed nets')
    for i,row in enumerate(rows):
        if row['Type'] == 'net':
            row['FromRoutePin'] = rows[i-1]['RoutePin']
            row['ToRoutePin'] = rows[i+1]['RoutePin']
    return {'Source':source, 'Endpoint':target, 'LaunchClock':clocks[0][0],
            'CaptureClock':clocks[1][0], 'LaunchEdge':clocks[0][1], 'CaptureEdge':clocks[1][1],
            'Corner':corner, 'Kind':kind, 'PathClass':one(r'^Path Class\s*:\s*(.+?)\s*$', text, 'class'),
            'SlackNS':float(slack), 'SlackState':slack_state,
            'ClockSkewNS':float(one(r'^Clock Skew\s*:\s*(' + NUM + r')', text, 'skew')),
            'CaptureClockDelayNS':float(one(r'^  Capture Clock Delay\s*:\s*(' + NUM + r')', text, 'capture delay')),
            'LaunchClockDelayNS':float(one(r'^  Launch Clock Delay\s*:\s*(' + NUM + r')', text, 'launch delay')),
            'TimingExceptions':re.findall(r'^Timing Exception\s*:\s*(.+?)\s*$', text, re.MULTILINE),
            'ExceptionConstraintLines':[int(v) for v in re.findall(r'^Exception constraint line number:\s*(\d+)', text, re.MULTILINE)],
            'DataTrace':rows, 'Report':str(report), 'ReportLine':first_line,
            'PathSHA256':hashlib.sha256(text.encode('utf-8')).hexdigest(), '_Text':text}

def identity(path):
    return tuple(path[key] for key in ('Source','Endpoint','LaunchClock','CaptureClock','LaunchEdge','CaptureEdge'))

def read_report(path, identities=None):
    path = Path(path).resolve()
    before = sha(path)
    paths, summaries, block, first_line, table = [], [], [], 0, None
    with path.open(encoding='utf-8-sig', errors='strict') as stream:
        for number,line in enumerate(stream, 1):
            header = SUMMARY.fullmatch(line)
            if header:
                table = (header[2].lower(), header[1].lower())
            elif ' Summary(' in line or line.startswith('Startpoint'):
                table = None
            if table:
                match = SUMMARY_ROW.fullmatch(line)
                if match:
                    summaries.append({'Corner':table[0], 'Kind':table[1],
                                      'LaunchClock':match[1], 'CaptureClock':match[2],
                                      'WorstSlackNS':float(match[3]), 'TotalNegativeSlackNS':float(match[4]),
                                      'FailingChecks':int(match[5]), 'TotalChecks':int(match[6]),
                                      'Report':str(path), 'ReportLine':number})
            if line.startswith('Startpoint'):
                require(not block or not re.search(r'^ (Setup|Hold) time', ''.join(block), re.MULTILINE),
                        'truncated preceding setup/hold timing path')
                block, first_line = [line], number
            elif block:
                block.append(line)
                if line.startswith(' Slack'):
                    value = parse_path(block, path, first_line, detailed=False)
                    if value is not None and ((identities is None and value['Kind']=='hold' and value['SlackNS']<0)
                                               or (identities is not None and identity(value) in identities)):
                        paths.append(value)
                    block = []
    require(not block or not re.search(r'^ (Setup|Hold) time', ''.join(block), re.MULTILINE),
            'truncated setup/hold timing path at EOF')
    require(paths, 'no selected setup/hold paths')
    require(before == sha(path), 'report changed during audit')
    return paths, summaries, {'Path':str(path), 'SHA256':before, 'SelectedPaths':len(paths)}

def build(reports, expect_failures=3):
    paths, summaries, provenance = [], [], []
    for report in reports:
        parsed, tables, evidence = read_report(report)
        paths.extend(parsed); summaries.extend(tables); provenance.append(evidence)
    failures = sorted({identity(p) for p in paths if p['Kind'] == 'hold' and p['SlackNS'] < 0})
    require(len(failures) == expect_failures, 'unexpected distinct hold-failing path count')
    for summary in summaries:
        if summary['Kind'] != 'hold' or summary['FailingChecks'] == 0:
            continue
        reported={identity(p) for p in paths if p['Kind']=='hold' and p['SlackNS']<0
                  and (p['Corner'],p['LaunchClock'],p['CaptureClock']) ==
                  (summary['Corner'],summary['LaunchClock'],summary['CaptureClock'])}
        require(len(reported)==summary['FailingChecks'], 'hold path detail count differs from summary')
    paths=[]
    for report in reports:
        selected, _, _ = read_report(report, set(failures))
        paths.extend(selected)
    results, excerpts = [], {}
    for number,key in enumerate(failures, 1):
        matched = [parse_path(p['_Lines'], p['Report'], p['ReportLine'])
                   for p in paths if identity(p) == key]
        seen = set(); cases=[]
        for p in matched:
            if p['PathSHA256'] in seen:
                continue
            seen.add(p['PathSHA256'])
            filename = f'path-{number:02d}-{p["Corner"]}-{p["Kind"]}-{len(cases)+1}.txt'
            excerpts[filename]=p['_Text']
            cases.append({**{k:v for k,v in p.items() if k != '_Text'}, 'Excerpt':filename})
        holds = [p for p in cases if p['Kind']=='hold']
        require({p['Corner'] for p in holds} == {'slow','fast'}, 'both corner hold records are required')
        candidate_nets = [p['DataTrace'][-2] for p in holds]
        require(all(v['Type']=='net' and v['Fanout']==1 for v in candidate_nets), 'terminal branch is not fanout one')
        net_keys={(v['Name'],v['FromRoutePin'],v['ToRoutePin']) for v in candidate_nets}
        require(len(net_keys)==1, 'corner terminal net identities differ')
        name, source_pin, target_pin=next(iter(net_keys))
        margins={}
        for corner in ('slow','fast'):
            setup=[p['SlackNS'] for p in cases if p['Corner']==corner and p['Kind']=='setup']
            hold=[p['SlackNS'] for p in holds if p['Corner']==corner]
            margins[corner]={'HoldSlackNS':min(hold), 'ExactSetupSlackNS':min(setup) if setup else None,
                             'ExactSetupFound':bool(setup)}
        results.append({'PathNumber':number, **{k:cases[0][k] for k in ('Source','Endpoint','LaunchClock','CaptureClock')},
                        'Cases':cases, 'Margins':margins,
                        'ClockPairSummaryContext':[s for s in summaries if (s['LaunchClock'],s['CaptureClock'])==key[2:4]],
                        'PhysicalRepairCandidate':{'Type':'terminal data-net route detour', 'Net':name,
                            'FromRoutePin':source_pin, 'ToRoutePin':target_pin, 'Fanout':1,
                            'HoldDeficitLowerBoundNS':max(0,-min(p['SlackNS'] for p in holds)),
                            'MinimumChangeScope':'Only this terminal data branch; preserve logical cells, FF placement and clocks.',
                            'Validated':False, 'Needs':'Actual native route/connectivity and occupancy checks; exact endpoint setup in both corners; post-change full STA.',
                            'TimingWaiverAllowed':False}})
    missing=[{'PathNumber':p['PathNumber'],'Source':p['Source'],'Endpoint':p['Endpoint'],
              'Corner':c,'Kind':'setup','Reason':'Exact source/endpoint setup absent from supplied report; clock-pair WNS is not a substitute.'}
             for p in results for c,v in p['Margins'].items() if not v['ExactSetupFound']]
    return {'Schema':'camera-vga-hold-analysis-v1','ExtractionComplete':True,
            'GeneratedUTC':datetime.now(timezone.utc).isoformat(),'InputReports':provenance,'ToolSHA256':sha(__file__),
            'HoldFailingPathCount':len(results),'Paths':results,'MissingExactSetup':missing,
            'HoldFailureSummary':[s for s in summaries if s['Kind']=='hold' and s['FailingChecks']>0],
            'SynthesisOrRouteExecuted':False,'HardwareAccessed':False,'TimingClosed':False,
            'Limitations':'STA extraction only. Data checks, including rst_clk to ddrphy_sysclk D, remain timed. No reset/CDC exception is inferred.'},excerpts

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, action='append', required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--expect-failures', type=int, default=3)
    args=parser.parse_args()
    require(not args.out.exists(), 'fresh output directory required')
    report, excerpts=build(args.report,args.expect_failures)
    args.out.mkdir(parents=True)
    for filename,text in excerpts.items():
        (args.out/filename).write_text(text,encoding='utf-8')
    (args.out/'camera-vga-hold-analysis.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'Report':str((args.out/'camera-vga-hold-analysis.json').resolve()),
                      'HoldFailures':report['HoldFailingPathCount'],
                      'MissingExactSetup':len(report['MissingExactSetup'])}))

if __name__=='__main__':
    main()
