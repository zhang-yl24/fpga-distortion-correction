"""Prepare/recheck exact 720p CDC native queries; CPU only, no EDA execution.

Re-derive every endpoint from the supplied placed export. Native query receipts
must bind that same ADF and build. Grouping never substitutes for pair/corner
coverage. Missing details produce exact supplementary queries, not a pass.
"""
import argparse
from collections import defaultdict
import copy
from datetime import datetime, timezone
import hashlib
import importlib
import json
from pathlib import Path
import re

import audit_camera720_io_cdc as structure
import audit_camera_vga_cdc_native as native

inspect, prep = structure.inspect, structure.prep
require, sha = inspect.require, inspect.sha
SELF = Path(__file__).resolve()
SCHEMA = 'camera720-cdc-native-batch-v1'
SAFE_PIN = re.compile(r'[A-Za-z0-9_./\[\]-]+')
NUM = native.NUM


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def add(watched, path, expected=None, pds=None):
    path = Path(path).absolute()
    external = pds is not None and path == Path(pds).absolute()
    require(not external or (path.name.lower() == 'pds_shell.exe' and expected is not None), 'external tool binding differs')
    path = inspect.canonical(path, path.parent if external else prep.PROJECT)
    digest = sha(path)
    require(expected is None or digest == expected, 'input digest differs: '+str(path))
    require(path not in watched or watched[path] == digest, 'input changed while binding')
    watched[path] = digest
    return path


def bind_native(path, mode, watched, candidate=None, build_sha=None):
    """Local schema adapter; existing inspectors and their policy stay intact."""
    path = add(watched, path)
    schema = read(path).get('Schema')
    modules = {'camera720-output-readonly-inspection-v1': 'camera720_inspect',
               'camera720-derived-readonly-inspection-v1': 'camera720_derived_inspect',
               'camera720-reset-derived-inspection-v1': 'camera720_reset_inspect'}
    require(schema in modules, 'unsupported actual 720p inspection receipt')
    module = importlib.import_module(modules[schema])
    if schema == 'camera720-reset-derived-inspection-v1':
        value = module.bind_receipt(path, watched)
    else:
        value, bound = module.bind_receipt(path)
        for p, digest in bound.items():
            add(watched, p, digest, value['Command'][0])
    require(value['Mode'] == mode and value['Target'] == prep.TARGET, 'inspection mode/target differs')
    if candidate is not None:
        require(value['SourceADFSHA256'] == candidate['SHA256']
                and Path(value['SourceADF']).resolve() == Path(candidate['Path']).resolve(),
                'inspection belongs to a different actual ADF')
    if build_sha is not None:
        require(value['BuildPlanSHA256'] == build_sha, 'inspection belongs to a different build')
    for helper in structure.local_helpers((module, structure, native)):
        add(watched, helper)
    add(watched, SELF)
    return value


def derive(export_path, watched):
    """Repeat structural checks against this export, including reset descendants."""
    receipt = bind_native(export_path, 'export', watched)
    require(receipt.get('NativeNetlistWithFFloc') is True, 'placed native export required')
    netlist = add(watched, receipt['Netlist']['Path'], receipt['Netlist']['SHA256'])
    text = netlist.read_text(encoding='utf-8-sig')
    graph = structure.monitor.Graph(structure.functional(text))
    build = Path(receipt['BuildPlan']).parent
    paths = {'top': prep.PROJECT/prep.TOP, 'fdc': build/'compiled'/prep.FDC,
             'pcf': build/'device_map'/(prep.TARGET+'.pcf'),
             'prt': build/'place_route'/(prep.TARGET+'_prr_route_optimize.prt'),
             'official': prep.PROJECT/'platform/video_base/HDMI_IN_DDR3_HDMI_OUT_top.fdc',
             'cam_reference': prep.PROJECT/'board/raw_camera_capture_cam2_ref.fdc',
             'cam_pins': prep.PROJECT/'board/raw_camera_capture_cam2_ref-pins.json'}
    texts = {key: add(watched, p).read_text(encoding='utf-8-sig') for key, p in paths.items()}
    pins = structure.io.pin_audit(structure.io_syntax(texts['top']), texts['fdc'], texts['pcf'], texts['prt'],
        structure.io_syntax(text), texts['official'], texts['cam_reference'], json.loads(texts['cam_pins']))
    values = {'Pins': pins, 'SyncPadSinks': structure.sync_pad_sinks(graph),
              'InputDelay': structure.delay.audit(graph), 'FIFOGray': structure.cdc.gray_structures(graph),
              'MonitorGray': structure.monitor.monitor_gray(graph),
              'ApplicationScalar': structure.monitor.application_scalars(graph),
              'MonitorScalar': structure.monitor.monitor_scalar(graph),
              'ApplicationReset': structure.monitor.reset_chains(graph)}
    held = structure.monitor.held_snapshot(graph)
    held['AllFirstConsumers'] = structure.monitor.held_first_sinks(graph, held)
    held['HeldBusEndpointTraversalComplete'] = True
    values['MonitorHeldSnapshot'] = held
    queries = structure.monitor.query_pairs(values['FIFOGray']+values['MonitorGray'],
        values['ApplicationScalar']+values['MonitorScalar'], values['ApplicationReset'], held)
    constraints, maxima = structure.cdc.constraint_inventory(paths['fdc'])
    minima = {}
    for row in constraints['RelevantStatements']:
        match = re.fullmatch(r'set_min_delay -from \[get_clocks \{(\w+)\}\] -to \[get_clocks \{(\w+)\}\] ('+NUM+r')', row['Text'])
        if match:
            key = match[1], match[2]
            require(key not in minima, 'ambiguous crossing minimum constraint')
            minima[key] = float(match[3])
    queries = requirements(queries, maxima, minima, constraints['PeriodsNS'])
    return {'CandidateADF': {'Path': receipt['SourceADF'], 'SHA256': receipt['SourceADFSHA256']},
            'BuildPlanSHA256': receipt['BuildPlanSHA256'], 'Netlist': receipt['Netlist'],
            'ExportReceipt': {'Path': str(Path(export_path).absolute()), 'SHA256': sha(export_path)},
            'Queries': queries, 'IOSites': sorted({r['Site'] for r in pins['PinInventory']}),
            'ComponentChecks': values, 'Constraints': constraints,
            'ActualCells': len(graph.cells), 'ActualFFs': len(graph.ff),
            'FinalExportReevaluated': True}


def requirements(queries, maxima, minima, periods):
    result, seen = [], set()
    for original in queries:
        q = copy.deepcopy(original)
        pair = q['Source'], q['Endpoint']
        require(pair not in seen, 'duplicate physical query pair')
        seen.add(pair)
        require(all(SAFE_PIN.fullmatch(p) for p in pair), 'unsafe actual endpoint')
        if 'Clock' in q:
            q.update(CheckKinds=['setup', 'hold'], Corners=['slow', 'fast'])
        else:
            clock_pair = q['SourceClock'], q['DestinationClock']
            require(clock_pair in maxima and clock_pair in minima, 'crossing lacks exact max/min constraints')
            require(clock_pair[0] in periods, 'crossing source period missing')
            q.update(CheckKinds=['max-delay', 'min-delay'], Corners=['slow', 'fast'],
                     MaximumNS=maxima[clock_pair]['BoundNS'], MinimumNS=minima[clock_pair],
                     SourcePeriodNS=periods[clock_pair[0]])
        result.append(q)
    require(result, 'empty actual CDC inventory')
    return result


def group_commands(queries, exact=False):
    groups = defaultdict(list)
    for q in queries:
        for p in (q['Source'], q['Endpoint']):
            require(SAFE_PIN.fullmatch(p), 'unsafe actual endpoint')
        domain = ('normal', q['Clock']) if 'Clock' in q else ('cross', q['SourceClock'], q['DestinationClock'])
        groups[domain+(q['Source'], q['Endpoint'] if exact else '')].append(q)
    result = []
    for key, values in sorted(groups.items()):
        for first in range(0, len(values), 28):
            subset = values[first:first+28]
            source = subset[0]['Source']
            endpoints = sorted({q['Endpoint'] for q in subset})
            command = ('report_path_timing -delay_type min_max -max_path 1000 -nworst 8 -report_exception TRUE -from {'
                       +source+'} -to {'+' '.join(endpoints)+'}')
            result.append({'Source': source, 'Endpoints': endpoints,
                           'ExpectedPairs': [{'Source': q['Source'], 'Endpoint': q['Endpoint']} for q in subset],
                           'Command': command})
    require(sum(len(r['ExpectedPairs']) for r in result) == len(queries), 'grouping dropped an expected pair')
    return result


def bodies(queries, sites=(), exact=False):
    groups = group_commands(queries, exact)
    commands = [g['Command'] for g in groups]
    for site in sites:
        require(re.fullmatch(r'[A-Za-z0-9_]+', site), 'unsafe native site')
        commands.append('show -dev_instance {'+site+'}')
    if sites:
        commands.append('.switch_db -route -input {@WORK@/input.adf} -output {@WORK@/route-dump.txt}')
    result = []
    for first in range(0, len(commands), 300):
        body = '# Explicit pair/corner coverage remains mandatory.\n'+'\n'.join(commands[first:first+300])+'\n'
        inspect.query_commands(body)
        result.append(body)
    return result, groups


def write_output(output, name, value, watched, payloads):
    output = prep.work_path(output)
    require(not output.exists() and not inspect.drift(watched), 'fresh output and stable bound inputs required')
    value['InputSHA256'] = {str(p): h for p, h in watched.items()}
    output.mkdir()
    for filename, body in payloads.items():
        (output/filename).write_text(body, encoding='ascii', newline='\n')
    inspect.diagnostic.write(output/name, value)
    return value


def prepare(export_path, output):
    watched = {}
    value = derive(export_path, watched)
    texts, groups = bodies(value['Queries'], value['IOSites'])
    payloads = {f'query-{i:02}.tcl': text for i, text in enumerate(texts)}
    value.update(Schema=SCHEMA, Target=prep.TARGET, CreatedUTC=datetime.now(timezone.utc).isoformat(),
                 Groups=groups, QueryBodies={n: hashlib.sha256(t.encode('ascii')).hexdigest() for n,t in payloads.items()},
                 ExpectedCases=len(value['Queries'])*4, NativeCommands=sum(len(inspect.query_commands(t)) for t in texts),
                 OneNativeContext=len(texts) == 1, CoverageAssumedFromGrouping=False,
                 HardwareAccessed=False, EDAExecuted=False, TimingAccepted=False, HardwareReleaseAllowed=False)
    return write_output(output, 'batch-plan.json', value, watched, payloads)


def parse_record(lines, report, line, query):
    text = ''.join(lines)
    field = lambda pattern, label: native.field(pattern, text, label)
    source = field(r'^Startpoint\s*:\s*(\S+)\s*$', 'source')
    endpoint = field(r'^Endpoint\s*:\s*(\S+)\s*$', 'endpoint')
    require((source,endpoint) == (query['Source'],query['Endpoint']), 'native pair differs')
    typ, corner = field(r'^Path Type\s*:\s*(max|min) \((slow|fast) corner\)\s*$', 'type/corner')
    require(field(r'^Path Class\s*:\s*(.+?)\s*$', 'class') == 'sequential timing path', 'not a sequential path')
    state, slack = field(r'^ Slack \((MET|VIOLATED)\)\s+('+NUM+r')\s*$', 'slack')
    require(state == 'MET' and float(slack) >= 0, 'native timing violation')
    exceptions = re.findall(r'^Timing Exception\s*:\s*(.+?)\s*$', text, re.M)
    arrival = float(field(r'^ Data arrival time\s+('+NUM+r')\s+Logic Levels:.*$', 'arrival'))
    result = {'Source': source, 'Endpoint': endpoint, 'Corner': corner, 'SlackNS': float(slack),
              'ArrivalNS': arrival, 'Report': str(report), 'ReportLine': line,
              'PathSHA256': hashlib.sha256(text.encode()).hexdigest()}
    if 'Clock' in query:
        ordinary = native.path_syntax.parse_path(lines, report, line, detailed=False)
        require(ordinary is not None and not exceptions, 'ordinary interstage check absent or excepted')
        require(ordinary['LaunchClock'] == ordinary['CaptureClock'] == query['Clock']
                and ordinary['LaunchEdge'] == ordinary['CaptureEdge'] == 'rising', 'ordinary clock/edge differs')
        result['Kind'] = ordinary['Kind']
    else:
        kind = 'max-delay' if typ == 'max' else 'min-delay'
        prefix = 'Max' if typ == 'max' else 'Min'
        pattern = prefix+r'Delay Path ('+NUM+r')ns'+(r' -datapath_only' if typ == 'max' else '')
        require(len(exceptions) == 1 and re.fullmatch(pattern, exceptions[0]), 'explicit crossing max/min exception missing or differs')
        bound = float(re.fullmatch(pattern, exceptions[0])[1])
        require(bound == query['MaximumNS' if typ == 'max' else 'MinimumNS'], 'crossing bound differs from actual FDC')
        if typ == 'max':
            require(0 <= arrival < query['SourcePeriodNS'], 'crossing arrival exceeds source period')
        else:
            clocks = re.findall(r'^ Clock (\S+) \((rising|falling) edge\)', text, re.M)
            require(clocks == [(query['SourceClock'],'rising'),(query['DestinationClock'],'rising')], 'minimum-delay crossing clocks differ')
        result.update(Kind=kind, BoundNS=bound)
    require(result['Kind'] in query['CheckKinds'] and corner in query['Corners'], 'unexpected check case')
    return result


def coverage(queries, records, violations):
    expected = {(q['Source'],q['Endpoint'],c,k) for q in queries for c in q['Corners'] for k in q['CheckKinds']}
    counts = defaultdict(list)
    for row in records:
        key = tuple(row[k] for k in ('Source','Endpoint','Corner','Kind'))
        require(key in expected, 'unexpected native check identity')
        counts[key].append(row['SlackNS'])
    missing = [{'Source':s,'Endpoint':e,'Corner':c,'Kind':k} for s,e,c,k in sorted(expected-set(counts))]
    return {'ExpectedCases': len(expected), 'CoveredCases': len(counts), 'MissingCases': missing,
            'CaseCoverage': [{'Source':s,'Endpoint':e,'Corner':c,'Kind':k,'MinimumSlackNS':min(v),'Variants':len(v)}
                             for (s,e,c,k),v in sorted(counts.items())],
            'Complete': not missing, 'EnumeratedPathsTimingPassed': not missing and not violations}


def collect(queries, reports):
    lookup = {(q['Source'],q['Endpoint']):q for q in queries}
    records, violations, seen = [], [], set()
    for report in reports:
        for lines, line in native.blocks(report):
            text = ''.join(lines)
            pair = tuple(native.field(pattern,text,label) for pattern,label in (
                (r'^Startpoint\s*:\s*(.+?)\s*$','source'),(r'^Endpoint\s*:\s*(.+?)\s*$','endpoint')))
            if pair not in lookup:
                continue
            try:
                row = parse_record(lines,report,line,lookup[pair])
            except ValueError as error:
                violations.append({'Source':pair[0],'Endpoint':pair[1],'Report':str(report),'ReportLine':line,'Error':str(error)})
                continue
            if row['PathSHA256'] not in seen:
                seen.add(row['PathSHA256']); records.append(row)
    return records, violations


def approved_body(body, plan, initial_bodies):
    """Accept exact initial batches or exact one-pair supplements only."""
    commands = inspect.query_commands(body)
    if body in initial_bodies:
        return
    allowed = {g['Command'] for g in group_commands(plan['Queries'], exact=True)}
    require(all(c in allowed for c in commands), 'query is neither planned batch nor exact pair supplement')


def check(plan_path, receipt_paths, output):
    watched = {}
    plan_path = add(watched, plan_path)
    plan = read(plan_path)
    require(plan.get('Schema') == SCHEMA and plan.get('Target') == prep.TARGET, 'unexpected CDC batch plan')
    actual = derive(plan['ExportReceipt']['Path'], watched)
    require({str(p):h for p,h in watched.items() if p != plan_path} == plan['InputSHA256'],
            'prepared source/tool closure differs from rederived final export')
    pds = read(plan['ExportReceipt']['Path'])['Command'][0]
    for path,digest in plan['InputSHA256'].items():
        add(watched,path,digest,pds)
    for key,value in actual.items():
        require(plan.get(key) == value, 'plan differs from rederived final export: '+key)
    initial, groups = bodies(plan['Queries'], plan['IOSites'])
    require(plan['Groups'] == groups and plan['QueryBodies'] == {
        f'query-{i:02}.tcl':hashlib.sha256(t.encode('ascii')).hexdigest() for i,t in enumerate(initial)}, 'query recipe differs')
    for name,digest in plan['QueryBodies'].items():
        add(watched,plan_path.parent/name,digest)
    reports, logs, native_receipts = [], [], []
    for path in receipt_paths:
        receipt = bind_native(path,'query',watched,plan['CandidateADF'],plan['BuildPlanSHA256'])
        body_path = add(watched,receipt['QueryBody'])
        require(receipt['InputSHA256'].get(str(body_path)) == sha(body_path), 'query body absent from receipt closure')
        approved_body(body_path.read_text(encoding='ascii'),plan,initial)
        root = Path(path).absolute().parent
        for name,digest in receipt['Artifacts'].items():
            if name.endswith('.rtr'):
                reports.append(add(watched,root/name,digest))
        logs.append(add(watched,root/'stdout.log',receipt['Artifacts']['stdout.log']).read_text(encoding='gb18030'))
        native_receipts.append({'Path':str(Path(path).absolute()),'SHA256':sha(path)})
    require(reports, 'no receipt-bound native timing reports')
    records, violations = collect(plan['Queries'],sorted(set(reports)))
    result = coverage(plan['Queries'],records,violations)
    # Supplements can repeat site evidence; accept identical blocks only.
    site_blocks = {}
    for log in logs:
        for block in re.findall(r'(?ms)^Site \S+ \(\d+\) :\r?\n.*?(?=^Site |^Executing :|\Z)',log):
            site = re.match(r'Site (\S+)',block)[1]
            require(site not in site_blocks or site_blocks[site] == block,'native site evidence conflicts')
            site_blocks[site] = block
    pins = copy.deepcopy(plan['ComponentChecks']['Pins'])
    site_error = None
    try:
        structure.io.apply_native_sites(pins,''.join(site_blocks.values()))
    except ValueError as error:
        site_error = str(error)
    missing_pairs = {(r['Source'],r['Endpoint']) for r in result['MissingCases']}
    missing_queries = [q for q in plan['Queries'] if (q['Source'],q['Endpoint']) in missing_pairs]
    supplemental, _ = bodies(missing_queries,exact=True)
    result.update(Schema='camera720-cdc-native-coverage-v1', Target=prep.TARGET,
                  BatchPlan={'Path':str(plan_path),'SHA256':sha(plan_path)}, CandidateADF=plan['CandidateADF'],
                  NativeReceipts=native_receipts, Records=records, Violations=violations,
                  MissingPairCount=len(missing_pairs), Pins=pins, NativeSiteError=site_error,
                  NativeSiteMappingVerified=site_error is None,
                  EnumeratedPathsAndSitesPassed=result['EnumeratedPathsTimingPassed'] and site_error is None,
                  NativeElectricalSettingsVerified=False, AnalogMTBFProven=False,
                  TimingAccepted=False, HardwareAccessed=False, EDAExecuted=False, HardwareReleaseAllowed=False,
                  Limits='Enumerated digital CDC path coverage only. Electrical settings, analog MTBF, complete reset scope and overall timing acceptance remain separate checks.')
    return write_output(output,'coverage.json',result,watched,
        {f'supplement-{i:02}.tcl':text for i,text in enumerate(supplemental)})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='mode',required=True)
    p = sub.add_parser('prepare'); p.add_argument('--export-receipt',type=Path,required=True)
    c = sub.add_parser('check'); c.add_argument('--batch-plan',type=Path,required=True)
    c.add_argument('--query-receipt',type=Path,action='append',required=True)
    for command in (p,c): command.add_argument('--output-dir',type=Path,required=True)
    args = parser.parse_args()
    value = prepare(args.export_receipt,args.output_dir) if args.mode == 'prepare' else check(args.batch_plan,args.query_receipt,args.output_dir)
    keys = ('Schema','NativeCommands','ExpectedCases','CoveredCases','MissingPairCount','EnumeratedPathsTimingPassed',
            'NativeSiteMappingVerified','EnumeratedPathsAndSitesPassed','TimingAccepted','HardwareReleaseAllowed')
    print(json.dumps({k:value[k] for k in keys if k in value}))
    return 0 if args.mode == 'prepare' or value['EnumeratedPathsAndSitesPassed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
