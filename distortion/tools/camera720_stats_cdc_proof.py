"""Actual statistics-candidate scoped IO/CDC proof; CPU only, no hardware release.

New telemetry mux support is bounded to the vendor V_MUX2 Boolean primitive.
Every physical relation and delay is derived from this candidate's own export.
"""
import argparse
import importlib
import hashlib
import json
from pathlib import Path
import re
import tempfile

import camera720_stats_inspect as inspect
import camera720_stats_io_cdc as adapter
import camera720_stats_native_mux as mux
import camera720_stats_cdc_inventory as recipe

SELF=Path(__file__).resolve()
TARGET=adapter.TARGET
SCHEMA='camera720-calibrated-stats-cdc-proof-v1'
PLAN_SCHEMA='camera720-calibrated-stats-final-query-plan-v1'
PROJECT,WORK=inspect.prep.PROJECT,inspect.prep.WORK
cdc=adapter.cdc
require,sha,add,ref=inspect.require,inspect.sha,cdc.add,cdc.ref
read=adapter.grouped.read


def bind_native(path,modes,watched,candidate=None):
    path=add(watched,Path(path).resolve());header=read(path)
    modules={inspect.SCHEMA:'camera720_stats_inspect',
        'camera720-calibrated-stats-derived-inspection-v1':'camera720_stats_derived_inspect',
        'camera720-calibrated-stats-final-inspection-v1':'camera720_stats_final_inspect'}
    require(header.get('Schema') in modules and header.get('Target')==TARGET,'unsupported statistics receipt target/schema')
    module=importlib.import_module(modules[header['Schema']]);value,bound=module.bind_receipt(path)
    require(value['Mode'] in modes and value['ExecutionPassed'] is True,'wrong statistics receipt mode/failure')
    for p,h in bound.items():add(watched,p,h)
    if candidate is not None:
        require(value['SourceADF']==candidate['Path'] and value['SourceADFSHA256']==candidate['SHA256'],
                'statistics query candidate differs')
    require(inspect.scan_diagnostics(path.parent)==[],'native critical/error/fatal diagnostics')
    for p in adapter.structure.local_helpers((module,)):add(watched,p)
    return value


def bind_pair(export_path,route_path):
    watched={};export=bind_native(export_path,{'export'},watched)
    route=bind_native(route_path,{'report','query'},watched)
    require(export.get('NativeNetlistWithFFloc') is True,'placed statistics netlist required')
    require(all(export[k]==route[k] for k in ('SourceADF','SourceADFSHA256','BuildPlan','BuildPlanSHA256')),
            'statistics export/route candidate/build differs')
    require('route-dump.txt' in route['Artifacts'],'actual route dump missing')
    return export,route,watched


def mapped_inventory(graph,route,logical,internal,placements,constraints,candidate,build_sha,telemetry):
    mapper=cdc.clm.Mapper(graph,route,placements);mapped=[mapper.map(row) for row in logical]
    supplement=cdc.sameble.derive(graph,route,{'Schema':'camera720-native-endpoints-v1',
        'SameBLEInterstageInventory':internal,'LogicalRelationships':mapped,'Queries':[],
        'CandidateADF':candidate,'BuildPlanSHA256':build_sha}) if internal else {'LogicalRelationships':[],'DirectInternalRows':[],'Queries':[]}
    mapped.extend(mapper.map(row) for row in supplement['LogicalRelationships'])
    uart=[]
    buffers=[c for c in graph.cells.values() if c['Primitive'] in ('V_OBUF','V_OBUFT')
             and cdc.endpoints.canon(c['Ports']['O'])==adapter.UART]
    require(len(buffers)==1,'one current UART output buffer required')
    launch_support=adapter.structure.monitor.support(graph,buffers[0]['Ports']['I'])
    for source in adapter.uart_launches(graph):
        parent=source.rsplit('/',1)[0]
        leaves=sorted(name for kind,name in launch_support if kind=='ff'
                      and cdc.endpoints.base.native_parent(name)==parent)
        require(leaves,'UART buffer cone must be driven by actual registered Q')
        for name in leaves:
            q=cdc.endpoints.canon(graph.ff[name]['Ports']['Q']);outputs=mapper.outputs[parent].get(q,[])
            require(len(outputs)==1 and (parent,'CLK') in route['Pins'],'unique actual UART CLK/Q required')
            uart.append({'Source':source,'LaunchOutput':parent+'/'+outputs[0],'LogicalFF':name,'LogicalQ':q})
    require(len(uart)==len({(r['Source'],r['LaunchOutput']) for r in uart}),'duplicate UART launch')
    return {'Target':TARGET,'CandidateADF':candidate,'BuildPlanSHA256':build_sha,
        'ActualCells':len(graph.cells),'ActualFFs':len(graph.ff),'LogicalRelationships':mapped,
        'SameBLESupplement':supplement,'Queries':cdc.make_queries(mapped,constraints),'StatisticsDomain':telemetry,
        'NativeLUTBindings':cdc.endpoints.native_lut_bindings(graph,route,mapped),
        'InternalCarryLinks':mapper.carry_links,'UARTSourceOutputs':uart}


def uart_query_body(pins,pairs,video_launches,uart):
    body=adapter.video.query_body(pins,pairs,video_launches)
    for row in uart:
        source,output=row['Source'],row['LaunchOutput']
        require(all(cdc.SAFE.fullmatch(p) for p in (source,output)),'unsafe UART launch')
        pattern='^('+'|'.join(re.escape(p) for p in sorted({source,output}))+')$'
        body+='get_pins -hierarchical -regexp {'+pattern+'}\n'
        body+='report_path_timing -delay_type min_max -max_path 1000 -nworst 8 -report_exception TRUE -from {'+source+'} -through {'+output+'} -to {uart_txd}\n'
    return body


dvp_query_pairs=recipe.dvp_query_pairs

def derive(export_path, route_path):
    export_path,route_path = Path(export_path).resolve(),Path(route_path).resolve()
    export,native,watched = bind_pair(export_path,route_path)
    build = Path(export['BuildPlan']).resolve().parent
    # Descendant inspectors bind the same build closure without duplicating
    # these reference fields. Resolve only the exact bound build roles.
    export=dict(export)
    for key,path in (('GeneratedTop',build/'source'/inspect.TOP),
                     ('CompiledTop',build/'compiled'/inspect.TOP),
                     ('CompiledHeader',build/'compiled'/inspect.HEADER)):
        require(path in watched and watched[path]==sha(path),'generated/compiled role absent from native closure')
        item=ref(path)
        require(key not in export or export[key]==item,'native source role reference differs')
        export[key]=item
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
    telemetry = mux.audit(graph.g)
    logical,internal,placements,parents = adapter.cdc_inputs(graph,text['netlist'])
    uart_sources = adapter.uart_launches(graph)
    parents.update(s.rsplit('/',1)[0] for s in uart_sources)
    dump = add(watched,route_path.parent/'route-dump.txt',native['Artifacts']['route-dump.txt'])
    with tempfile.TemporaryDirectory(prefix='stats-route-') as tmp:
        normalized = Path(tmp)/'native.adif'
        normalization = cdc.normalize_source_locations(dump,normalized)
        route = cdc.endpoints.route_objects(normalized,parents)
    constraints,_ = cdc.endpoints.base.constraint_inventory(paths['fdc'])
    candidate = {'Path':export['SourceADF'],'SHA256':export['SourceADFSHA256']}
    inventory = mapped_inventory(graph,route,logical,internal,placements,constraints,candidate,export['BuildPlanSHA256'],telemetry)
    report = add(watched,export['TimingReport']['Path'],export['TimingReport']['SHA256'])
    records,violations,other = adapter.collect(inventory['Queries'],[report])
    coverage = cdc.timing.coverage(inventory['Queries'],records,violations)
    pairs,pair_sources = dvp_query_pairs(report)
    uart = adapter.uart_launches(graph)
    io_body = uart_query_body(pins,pairs,adapter.video.tx_launches(graph),inventory['UARTSourceOutputs'])
    inspect.query_commands(io_body)
    # Original Gray/held protocol scope remains visible for the later final audit.
    gray = cdc.endpoints.base.gray_structures(graph)+cdc.endpoints.monitor.monitor_gray(graph)
    held = cdc.endpoints.monitor.held_snapshot(graph)
    held['AllFirstConsumers'] = cdc.endpoints.monitor.held_first_sinks(graph,held)
    for p in adapter.structure.local_helpers((inspect,adapter,mux,recipe)):
        add(watched,p)
    add(watched,SELF)
    add(watched,mux.MODEL,mux.MODEL_SHA)
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

def query_reports(path,value,queries,uart):
    path=Path(path).resolve()
    commands=inspect.query_commands(Path(value['QueryBody']).read_text(encoding='ascii'))
    timed=[c for c in commands if c.startswith('report_path_timing ')];known={q[k] for q in queries for k in cdc.timing.IDENTITY}
    preceding=None;pin_groups=[]
    for command in commands:
        if command.startswith('get_pins -hierarchical -regexp '):preceding=command;continue
        if not command.startswith('report_path_timing '):continue
        sources,ends=cdc.timing.query_filter(command)
        if sources<=cdc.io.native_io.PORTS or ends<=cdc.io.native_io.tx.PORTS:continue
        through=re.findall(r'-through \{([^}]+)\}',command)
        require(len(through)==1,'CDC query needs one explicit through collection')
        outputs=set(through[0].split())
        is_uart=ends=={adapter.UART}
        if is_uart:
            require(len(sources)==len(outputs)==1 and (next(iter(sources)),next(iter(outputs))) in
                    {(r['Source'],r['LaunchOutput']) for r in uart}, 'unknown actual UART launch selector')
        else:
            require(sources|ends|outputs<=known,'native query has unknown current CDC selector')
        require(all(sum(o.rsplit('/',1)[0]==s.rsplit('/',1)[0] for o in outputs)==1 for s in sources),
                'one selected launch output per source CLK required')
        require(all(any(o.rsplit('/',1)[0]==s.rsplit('/',1)[0] for s in sources) for o in outputs),
                'through collection contains unpaired launch output')
        require(preceding is not None,'CDC query lacks exact pin enumeration')
        pattern=preceding.split(' -regexp {',1)[1][:-1]
        require(pattern.startswith('^(') and pattern.endswith(')$'),'exact pin alternatives required')
        pins=[re.sub(r'\\(.)',r'\1',s) for s in pattern[2:-2].split('|')]
        require(len(pins)==len(set(pins)) and set(pins)==sources|outputs|(set() if is_uart else ends),'pin enumeration scope differs')
        pin_groups.append({'PinPattern':pattern,'Pins':pins});preceding=None
    log=(path.parent/'stdout.log').read_text(encoding='gb18030')
    issues=cdc.timing.validate_pin_log(log,pin_groups);reports=[]
    for name in value['Artifacts']:
        if not name.endswith('.rtr') or name.endswith('_exception.rtr') or 'report_path_timing/' not in name:continue
        report=(path.parent/name).resolve()
        with report.open(encoding='gb18030') as stream:header=''.join(next(stream,'') for _ in range(18))
        require(re.search(r'^\| Design\s*:\s*'+TARGET+r'\s*$',header,re.M),'query report target differs')
        cdc.timing.validate_report_filter(name,header,timed)
        index=int(re.search(r'report_path_timing_(\d+)/',name.replace('\\','/'))[1])-1
        actual=cdc.timing.field(r'^\| Tcl Command\s*:\s*(.*?)\s*$',header,'command')
        normalize=lambda text:[{p[2:] if p.startswith(('p:','t:')) else p for p in v.split()}
                               for v in re.findall(r'-through \{([^}]+)\}',text)]
        require(normalize(actual)==normalize(timed[index]),'native through filter changed or dropped')
        reports.append(report)
    require(len(reports)==len(timed),'targeted report count differs from requested commands')
    return reports,issues,log


def uart_records(reports, launches):
    expected={(r['Source'],r['LaunchOutput']) for r in launches};rows=[]
    for path in sorted({Path(p).resolve() for p in reports}):
        for text in re.split(r'(?=^Startpoint\s*:)',path.read_text(encoding='ascii'),flags=re.M)[1:]:
            match=re.search(r'^Endpoint\s*:\s*uart_txd \(port\)\s*$',text,re.M)
            if not match:continue
            field=lambda p:cdc.timing.field(p,text,'UART propagation')
            kind,corner=field(r'^Path Type\s*:\s*(min|max) \((slow|fast) corner\)\s*$')
            if kind!='max':continue
            require(field(r'^Path Class\s*:\s*(.+?)\s*$')=='combinational timing path',
                    'UART output is not a native combinational pad path')
            source=field(r'^Startpoint\s*:\s*(.+?)\s*$');launch=cdc.timing.launch_row(text)['LaunchOutput']
            require((source,launch) in expected,'UART path launches from unexpected actual Q')
            require(re.findall(r'^ Clock (\S+) \((rising|falling) edge\)',text,re.M)==[(adapter.CORE,'rising')]
                    and not re.search(r'^Timing Exception\s*:',text,re.M),'UART clock/exception differs')
            arrival=float(field(r'^ Data arrival time\s+('+adapter.native_io.NUMBER+r')\s+Logic Levels:'))
            require(arrival>=0,'negative UART physical pad arrival')
            rows.append({'Port':adapter.UART,'Source':source,'LaunchOutput':launch,'Corner':corner,'DelayType':'max',
                'ReportedPadArrivalNS':arrival,'Report':str(path),'PathSHA256':hashlib.sha256(text.encode('ascii')).hexdigest()})
    return rows


def uart_summary(plan,records,electrical):
    expected={(r['Source'],r['LaunchOutput'],c) for r in plan['UARTSourceOutputs'] for c in ('slow','fast')}
    worst={}
    for row in records:
        key=(row['Source'],row['LaunchOutput'],row['Corner'])
        if key not in worst or row.get('ReportedPadArrivalNS',0)>worst[key].get('ReportedPadArrivalNS',0):worst[key]=row
    records=[worst[k] for k in sorted(worst)]
    actual=set(worst)
    require(actual<=expected,'unexpected UART case')
    missing=[dict(zip(('Source','LaunchOutput','Corner'),key)) for key in sorted(expected-actual)]
    native=[r for r in electrical['Rows'] if r['Port']==adapter.UART]
    require(electrical['Passed'] and len(native)==1,'actual UART native electrical instance missing')
    return {'Port':adapter.UART,'Attributes':dict(adapter.UART_ATTRIBUTES),
        'ActualNativeLaunches':sorted({r['Source'] for r in plan['UARTSourceOutputs']}),
        'NativeSourceOutputs':plan['UARTSourceOutputs'],'NativeMaximumPaths':records,
        'ExpectedMaximumCases':len(expected),'ObservedMaximumCases':len(expected&actual),'Missing':missing,
        'LaunchCoverageComplete':not missing,'NativeElectricalParametersVerified':True,
        'NativeElectricalEvidence':native,'ExternalACAccepted':False,'ReceiverSamplingBudgetSpecified':False}


def audit_value(export_receipt,route_receipt,query_receipts):
    plan,watched,_=derive(export_receipt,route_receipt)
    paths=sorted(Path(p).resolve() for p in query_receipts)
    require(len(paths)==len(set(paths)),'duplicate statistics query receipt')
    reports=[Path(plan['TimingReport']['Path']).resolve()];refs=[];issues=[];site_logs=[]
    for path in paths:
        value=bind_native(path,{'query'},watched,plan['CandidateADF'])
        require(value['BuildPlanSHA256']==plan['BuildPlan']['SHA256'],'statistics query build differs')
        found,bad,log=query_reports(path,value,plan['Queries'],plan['UARTSourceOutputs'])
        reports.extend(found);issues.extend(bad);refs.append(ref(path))
        if re.search(r'^Site \S+ \(\d+\) :',log,re.M):site_logs.append(log)
    reports=sorted(set(reports))
    records,bad,other=adapter.collect(plan['Queries'],reports);issues.extend(bad)
    coverage=cdc.timing.coverage(plan['Queries'],records,issues);missing=list(coverage['MissingCases'])
    bounds,incomplete=adapter.grouped.protocol_bounds(plan,records);missing.extend(incomplete)
    held_complete=not any(r['Group']=='held_snapshot' for r in incomplete)
    plan['Structure']['MonitorHeld']['HeldBusPhysicalBoundComplete']=held_complete
    plan['Structure']['MonitorHeld']['AllFirstConsumers']['PhysicalBoundComplete']=held_complete
    pins=plan['Pins']
    if len(site_logs)==1:adapter.io.apply_native_sites(pins,site_logs[0])
    else:missing.append({'Stage':'native-site-inventory','ObservedCompleteSiteLogs':len(site_logs),'Expected':1})
    electrical=adapter.native_io.io_parameters(plan['RouteDump']['Path'],pins)
    pins['FinalNativeElectricalAttributesVerified']=electrical['Passed']
    dvp=adapter.native_io.dvp_summary(adapter.native_io.dvp_records(reports))
    missing.extend(dict(Stage='conditional-dvp',**r) for r in dvp['MissingCases'])
    tx=[r for p in reports for r in adapter.grouped.tx_records(p)]
    actual={(r['Port'],r['Corner'],r['DelayType']) for r in tx}
    expected={(p,c,'max') for p in adapter.native_io.tx.PORTS for c in ('slow','fast')}
    missing.extend(dict(zip(('Port','Corner','DelayType'),k),Stage='native-tx-maxima') for k in sorted(expected-actual))
    commands=adapter.native_io.tx.commands(add(watched,PROJECT/'board/ms7210_commands.vh').read_text(),
        add(watched,PROJECT/'platform/video_base/source/hdmi/ms7210_ctl.v').read_text())
    uart=uart_summary(plan,uart_records(reports,plan['UARTSourceOutputs']),electrical)
    missing.extend(dict(Stage='UART-pad-propagation',**r) for r in uart['Missing'])
    # The physical sequential model is checked on this graph, never a prior count.
    graph=adapter.graph(Path(plan['Netlist']['Path']).read_text(encoding='ascii'))
    basis=adapter.grouped.physical_basis(plan,graph,watched)
    require(not inspect.drift(watched),'statistics proof input drift')
    result={**plan,'Schema':SCHEMA,'Producer':ref(SELF),'QueryReceipts':refs,'Records':records,
        'CaseCoverage':coverage['CaseCoverage'],'ExpectedCases':coverage['ExpectedCases'],'ObservedCases':coverage['CoveredCases'],
        'Missing':missing,'Violations':issues,'ProtocolTimingBounds':bounds,'ExcludedOtherLaunches':other,
        'PhysicalSTABasis':basis,'ScopedDigitalChecksPassed':not missing and not issues,
        'NativeElectricalParameters':electrical,'DVP':dvp,'UART':uart,
        'TX':{'Vendor49CommandsIdentical':True,'Commands':commands,'NativeMaximumPaths':tx,
              'NativeMinimumDelaysObtained':False,'RegisterSamplingInterpretationVerified':False},
        'InputSHA256':{str(p):h for p,h in watched.items()},'InputDrift':[],
        'HardwareAccessed':False,'EDAExecuted':False,'HardwareReleaseAllowed':False,
        'Limits':'Current statistics candidate scoped digital evidence only. Independent final full STA/reset effect remains required. No external UART/DVP/TX AC, measured board voltage, analog MTBF or optical/FPS acceptance.'}
    return result,watched


def verify(path):
    path=Path(path).resolve();saved=read(path);bound={};add(bound,path)
    require(saved.get('Schema')==SCHEMA and saved.get('Target')==TARGET,'wrong statistics digital proof')
    for p,h in saved['InputSHA256'].items():add(bound,p,h)
    for item in [saved['ExportReceipt'],saved['RouteReceipt']]+saved['QueryReceipts']:add(bound,item['Path'],item['SHA256'])
    actual,watched=audit_value(saved['ExportReceipt']['Path'],saved['RouteReceipt']['Path'],[r['Path'] for r in saved['QueryReceipts']])
    clean=lambda v:json.loads(json.dumps({k:x for k,x in v.items() if k not in ('CreatedUTC','InputSHA256')}))
    require(clean(actual)==clean(saved),'saved statistics proof differs from recomputation')
    for p,h in watched.items():add(bound,p,h)
    return actual,bound


def prepare(export_receipt,route_receipt,output,per_body=8):
    output=Path(output).absolute()
    require(output==output.resolve() and output.is_relative_to(WORK.resolve()) and not output.exists(),'fresh statistics query directory required')
    initial,watched,io_body=derive(export_receipt,route_receipt)
    groups,bodies=adapter.cdc_query_bodies(initial['Queries'],initial['InitialCoverage']['MissingCases'],per_body)
    bodies['query-io.tcl']=io_body
    for body in bodies.values():inspect.query_commands(body)
    output.mkdir()
    for name,body in bodies.items():(output/name).write_text(body,encoding='ascii',newline='\n')
    value={'Schema':PLAN_SCHEMA,'Target':TARGET,'Producer':ref(SELF),'InitialEvidence':initial,'Groups':groups,
        'CommandsPerBody':per_body,'QueryBodies':{n:ref(output/n) for n in bodies},
        'InputSHA256':{str(p):h for p,h in watched.items()},'HardwareReleaseAllowed':False,'NativeQueriesExecuted':False}
    inspect.diagnostic.write(output/'plan.json',value)
    return value


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('mode',choices=('prepare','audit','verify'))
    parser.add_argument('--export-receipt',type=Path);parser.add_argument('--route-receipt',type=Path)
    parser.add_argument('--query-receipt',type=Path,action='append',default=[])
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--commands-per-body',type=int,default=8)
    args=parser.parse_args()
    if args.mode=='verify':value,_=verify(args.output)
    else:
        require(args.export_receipt and args.route_receipt,'actual statistics receipts required')
        if args.mode=='prepare':value=prepare(args.export_receipt,args.route_receipt,args.output,args.commands_per_body)
        else:
            value,_=audit_value(args.export_receipt,args.route_receipt,args.query_receipt)
            require(not args.output.exists(),'fresh statistics audit output required');inspect.diagnostic.write(args.output,value)
    print(json.dumps({k:value[k] for k in ('Schema','CandidateADFSHA256','ExpectedCases','ObservedCases','ScopedDigitalChecksPassed') if k in value}))


if __name__=='__main__':main()

