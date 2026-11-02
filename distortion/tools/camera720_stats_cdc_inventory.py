"""Bind real statistics export/route receipts and prepare missing queries.

CPU only. Optional native stage preparation creates inputs for the owner's
separate executor; this entry point never executes PDS or accesses hardware.
"""
import argparse
import json
from pathlib import Path
import re
import tempfile

import camera720_stats_inspect as inspect
import camera720_stats_io_cdc as adapter

SELF = Path(__file__).resolve()
TARGET = adapter.TARGET
SCHEMA = 'camera720-calibrated-stats-digital-query-plan-v1'
PROJECT, WORK = inspect.prep.PROJECT, inspect.prep.WORK
cdc = adapter.cdc
require, sha, add, ref = inspect.require, inspect.sha, cdc.add, cdc.ref


def bind_native(path, modes, watched):
    path = add(watched,Path(path).resolve())
    header = json.loads(path.read_text(encoding='utf-8'))
    require(header.get('Schema') == inspect.SCHEMA and header.get('Target') == TARGET,
            'actual statistics inspector receipt required')
    value, bound = inspect.bind_receipt(path)
    require(value['Mode'] in modes and value['ExecutionPassed'] is True,
            'wrong statistics receipt mode or failed execution')
    for p,h in bound.items():
        add(watched,p,h)
    return value


def bind_pair(export_path, route_path):
    watched = {}
    export = bind_native(export_path,{'export'},watched)
    route = bind_native(route_path,{'report','query'},watched)
    require(export.get('NativeNetlistWithFFloc') is True, 'fresh placed statistics netlist required')
    require(all(export[key] == route[key] for key in ('SourceADF','SourceADFSHA256','BuildPlan','BuildPlanSHA256')),
            'statistics export/route refer to different candidates or builds')
    require('route-dump.txt' in route['Artifacts'], 'statistics route dump absent')
    return export,route,watched


def dvp_query_pairs(report):
    """Extract current setup endpoints even for a violated diagnostic build.

    Negative slack is preserved here, never accepted as passing timing.
    Complete DVP acceptance remains a later measured-query audit.
    """
    choices = {p:[] for p in adapter.native_io.PORTS}
    for lines,number in cdc.timing.native.blocks(report):
        text = ''.join(lines)
        src = re.search(r'^Startpoint\s*:\s*(\S+) \(port\)\s*$',text,re.M)
        if not src or src[1] not in choices:
            continue
        field = lambda pattern:cdc.timing.field(pattern,text,'DVP query preparation')
        kind,corner = field(r'^Path Type\s*:\s*(min|max) \((slow|fast) corner\)\s*$')
        if kind != 'max':
            continue
        end = field(r'^Endpoint\s*:\s*(\S+)\s*$')
        require(end.startswith(adapter.native_io.SINK_PREFIXES) and cdc.SAFE.fullmatch(end),
                'DVP setup endpoint escaped actual capture hierarchy')
        require(field(r'^Path Class\s*:\s*(.+?)\s*$') == 'sequential timing path'
                and re.findall(r'^ Clock (\S+) \((rising|falling) edge\)',text,re.M) ==
                    [('camera_pclk','rising'),('camera_pclk','rising')]
                and not re.search(r'^Timing Exception\s*:',text,re.M), 'unreviewed DVP query path')
        state,slack = field(r'^ Slack \((MET|VIOLATED)\)\s+('+adapter.native_io.NUMBER+r')\s*$')
        require((float(slack)>=0) == (state=='MET'), 'DVP slack state inconsistent')
        choices[src[1]].append({'Port':src[1],'Endpoint':end,'Corner':corner,'SlackNS':float(slack),
                               'State':state,'Report':str(Path(report).resolve()),'ReportLine':number})
    selected = []
    for port,rows in sorted(choices.items()):
        require(rows, 'current full report has no DVP setup endpoint: '+port)
        selected.append(min(rows,key=lambda r:(r['SlackNS'],r['Endpoint'],r['Corner'],r['ReportLine'])))
    return [(r['Port'],r['Endpoint']) for r in selected], selected


def derive(export_path, route_path):
    export_path,route_path = Path(export_path).resolve(),Path(route_path).resolve()
    export,native,watched = bind_pair(export_path,route_path)
    build = Path(export['BuildPlan']).resolve().parent
    paths = {'top':add(watched,export['GeneratedTop']['Path'],export['GeneratedTop']['SHA256']),
        'compiled_top':add(watched,export['CompiledTop']['Path'],export['CompiledTop']['SHA256']),
        'netlist':add(watched,export['Netlist']['Path'],export['Netlist']['SHA256']),
        'fdc':build/'compiled/board/camera720-calibrated-stats.fdc',
        'pcf':build/'device_map'/f'{TARGET}.pcf',
        'prt':build/'place_route'/f'{TARGET}_prr_route_optimize.prt',
        'official':PROJECT/'platform/video_base/HDMI_IN_DDR3_HDMI_OUT_top.fdc',
        'camref':PROJECT/'board/raw_camera_capture_cam2_ref.fdc',
        'campins':PROJECT/'board/raw_camera_capture_cam2_ref-pins.json'}
    for p in paths.values():
        add(watched,p)
    text = {k:p.read_text(encoding='utf-8-sig') for k,p in paths.items()}
    source = adapter.source_inventory(text['top'],text['fdc'])
    require(source == adapter.source_inventory(text['compiled_top'],text['fdc']),
            'generated and compiled statistics interfaces differ')
    pins = adapter.pin_audit(text['top'],text['fdc'],text['pcf'],text['prt'],text['netlist'],
                            text['official'],text['camref'],json.loads(text['campins']))
    graph = adapter.graph(text['netlist'])
    # Validate new telemetry before applying the original scoped CDC mappers.
    telemetry = adapter.stats_domain(graph)
    logical,internal,placements,parents = adapter.cdc_inputs(graph,text['netlist'])
    dump = add(watched,route_path.parent/'route-dump.txt',native['Artifacts']['route-dump.txt'])
    with tempfile.TemporaryDirectory(prefix='stats-route-') as tmp:
        normalized = Path(tmp)/'native.adif'
        normalization = cdc.normalize_source_locations(dump,normalized)
        route = cdc.endpoints.route_objects(normalized,parents)
    constraints,_ = cdc.endpoints.base.constraint_inventory(paths['fdc'])
    candidate = {'Path':export['SourceADF'],'SHA256':export['SourceADFSHA256']}
    inventory = adapter.map_cdc(graph,route,logical,internal,placements,constraints,candidate,export['BuildPlanSHA256'])
    require(inventory['StatisticsDomain'] == telemetry, 'statistics domain changed during derivation')
    report = add(watched,export['TimingReport']['Path'],export['TimingReport']['SHA256'])
    records,violations,other = adapter.collect(inventory['Queries'],[report])
    coverage = cdc.timing.coverage(inventory['Queries'],records,violations)
    pairs,pair_sources = dvp_query_pairs(report)
    uart = adapter.uart_launches(graph)
    io_body = adapter.io_query_body(pins,pairs,adapter.video.tx_launches(graph),uart)
    inspect.query_commands(io_body)
    # Original Gray/held protocol scope remains visible for the later final audit.
    gray = cdc.endpoints.base.gray_structures(graph)+cdc.endpoints.monitor.monitor_gray(graph)
    held = cdc.endpoints.monitor.held_snapshot(graph)
    held['AllFirstConsumers'] = cdc.endpoints.monitor.held_first_sinks(graph,held)
    for p in adapter.structure.local_helpers((inspect,adapter)):
        add(watched,p)
    add(watched,SELF)
    add(watched,cdc.timing.MANUAL,cdc.timing.MANUAL_SHA)
    require(not inspect.drift(watched), 'statistics derivation input drift')
    result = {**inventory,'ExportReceipt':ref(export_path),'RouteReceipt':ref(route_path),
        'BuildPlan':ref(export['BuildPlan']),'CandidateADFSHA256':candidate['SHA256'],
        'Netlist':export['Netlist'],'RouteDump':ref(dump),'TimingReport':export['TimingReport'],
        'GeneratedTop':export['GeneratedTop'],'CompiledTop':export['CompiledTop'],
        'CompiledHeader':export['CompiledHeader'],'SourceInterface':source,'Pins':pins,
        'NativeInterfaceSourceLocationNormalization':normalization,'Constraints':constraints,
        'InputDelays':adapter.structure.delay.audit(graph),'SyncPadSinks':adapter.structure.sync_pad_sinks(graph),
        'Structure':{'Gray':gray,'MonitorHeld':held},'InitialRecords':records,'Violations':violations,
        'OtherLaunches':other,'InitialCoverage':coverage,'DVPQuerySources':pair_sources,'UARTLaunches':uart,
        'BuildDiagnosticsReview':export.get('BuildDiagnosticsReview'),
        'BuildDiagnosticsCleared':False,'NativeElectricalParametersVerified':False,
        'UARTExternalACAccepted':False,'ScopedDigitalChecksPassed':False,
        'InheritedTimingOrCounts':False,'HardwareReleaseAllowed':False,'OpticalCorrectionAccepted':False}
    return result,watched,io_body


def prepare(export_path, route_path, output, per_body=8, stage_prefix=None):
    require(type(per_body) is int and 1<=per_body<=8, 'one to eight timing commands per batch required')
    if stage_prefix is not None:
        require(isinstance(stage_prefix,str) and re.fullmatch('[A-Za-z0-9_-]+',stage_prefix), 'safe native stage prefix required')
    output = Path(output).absolute()
    require(output == output.resolve() and output.is_relative_to(WORK.resolve()) and not output.exists(),
            'fresh statistics query output directory required')
    initial,watched,io_body = derive(export_path,route_path)
    groups,bodies = adapter.cdc_query_bodies(initial['Queries'],initial['InitialCoverage']['MissingCases'],per_body)
    bodies['query-io.tcl'] = io_body
    for body in bodies.values():
        inspect.query_commands(body)
    stage_dirs = {name:WORK/(stage_prefix+'-'+('io' if name=='query-io.tcl' else name[6:-4])) for name in bodies} if stage_prefix else {}
    require(all(not p.exists() for p in stage_dirs.values()), 'native stage preparation would reuse an existing directory')
    require(not inspect.drift(watched), 'statistics inputs changed before query preparation')
    output.mkdir()
    for name,body in bodies.items():
        (output/name).write_text(body,encoding='ascii',newline='\n')
    value = {'Schema':SCHEMA,'Target':TARGET,'Producer':ref(SELF),'InitialEvidence':initial,'Groups':groups,
        'CommandsPerBody':per_body,'QueryBodies':{n:ref(output/n) for n in bodies},
        'InputSHA256':{str(p):h for p,h in watched.items()},'InputDrift':[],
        'HardwareAccessed':False,'EDAExecuted':False,'NativeQueriesExecuted':False,'HardwareReleaseAllowed':False}
    inspect.diagnostic.write(output/'plan.json',value)
    if stage_dirs:
        candidate = initial['CandidateADF'];review = initial.get('BuildDiagnosticsReview') or {}
        prepared = {}
        for name,work in stage_dirs.items():
            path = inspect.prepare(initial['BuildPlan']['Path'],candidate['Path'],candidate['SHA256'],work,
                'query',output/name,300,review.get('Path'),review.get('SHA256'))
            prepared[name] = ref(path)
        inspect.diagnostic.write(output/'prepared-stages.json',{'QueryPlan':ref(output/'plan.json'),
            'Stages':prepared,'EDAExecuted':False,'HardwareReleaseAllowed':False})
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--export-receipt',type=Path,required=True)
    parser.add_argument('--route-receipt',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--commands-per-body',type=int,default=8)
    parser.add_argument('--stage-prefix')
    args = parser.parse_args()
    value = prepare(args.export_receipt,args.route_receipt,args.output,args.commands_per_body,args.stage_prefix)
    initial = value['InitialEvidence'];coverage=initial['InitialCoverage']
    print(json.dumps({'Output':ref(args.output/'plan.json'),'Ports':initial['Pins']['TopPortCount'],
        'ActualFFs':initial['ActualFFs'],'ExpectedCases':coverage['ExpectedCases'],
        'InitiallyCoveredCases':coverage['CoveredCases'],'Violations':len(initial['Violations']),
        'CDCCommands':len(value['Groups']),'QueryBodies':len(value['QueryBodies']),
        'HardwareReleaseAllowed':False}))


if __name__ == '__main__':main()
