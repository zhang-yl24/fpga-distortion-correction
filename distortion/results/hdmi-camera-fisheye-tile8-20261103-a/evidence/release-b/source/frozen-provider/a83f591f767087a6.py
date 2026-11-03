"""Current calibrated candidate digital IO/CDC evidence; never executes EDA.

Queries can combine independent endpoints. Shared endpoints retain a distinct
source CLK/Q query, and actual per-identity coverage is required in every case.
"""
import argparse
from collections import defaultdict
import hashlib
import importlib
import json
from pathlib import Path
import re

import camera720_calibrated_cdc as cdc

require,sha=cdc.require,cdc.sha
SELF=Path(__file__).resolve()
TARGET=cdc.TARGET
SCHEMA='camera720-calibrated-cdc-proof-v1'
PROJECT=cdc.inspect.prep.PROJECT


def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def bind_native(path,mode,watched,candidate=None):
    path=cdc.add(watched,Path(path).resolve())
    schema=read(path).get('Schema')
    modules={'camera720-calibrated-readonly-inspection-v1':'camera720_calibrated_inspect',
             'camera720-calibrated-derived-inspection-v1':'camera720_calibrated_derived_inspect',
             'camera720-calibrated-reassessed-inspection-v1':'camera720_calibrated_reassessed_inspect',
             'camera720-calibrated-final-inspection-v1':'camera720_calibrated_final_inspect'}
    require(schema in modules,'unsupported calibrated native receipt')
    module=importlib.import_module(modules[schema]);value,bound=module.bind_receipt(path)
    require(value['Mode']==mode and value['Target']==TARGET,'native receipt mode/target differs')
    for p,h in bound.items():cdc.add(watched,p,h)
    if candidate is not None:
        require(value['SourceADF']==candidate['Path'] and value['SourceADFSHA256']==candidate['SHA256'],
                'native receipt belongs to another actual candidate')
    require(not cdc.inspect.scan_diagnostics(path.parent),'native C/E/F diagnostic blocks acceptance')
    for p in cdc.io.structure.local_helpers((module,)):cdc.add(watched,p)
    return value


def watch_tools(watched):
    for p in cdc.io.structure.local_helpers((cdc,)):cdc.add(watched,p)
    cdc.add(watched,SELF)


def bind_route(path,watched,candidate):
    # Final inspector emits its native route dump in report mode; exploratory
    # inspectors emit it in query mode. Both receipts undergo their full binder.
    mode=read(path).get('Mode')
    require(mode in ('query','report'),'route evidence must be a native report or query')
    return bind_native(path,mode,watched,candidate)


def derive(export_receipt,route_receipt):
    watched={};export_receipt=Path(export_receipt).resolve();route_receipt=Path(route_receipt).resolve()
    ex=bind_native(export_receipt,'export',watched)
    candidate={'Path':ex['SourceADF'],'SHA256':ex['SourceADFSHA256']}
    native=bind_route(route_receipt,watched,candidate)
    require(native['BuildPlanSHA256']==ex['BuildPlanSHA256'],'route/build identity differs')
    require(ex['NativeNetlistWithFFloc'] is True,'current placed export required')
    text=cdc.add(watched,ex['Netlist']['Path'],ex['Netlist']['SHA256']).read_text(encoding='ascii')
    graph=cdc.io.graph(text);logical,internal,_=cdc.endpoints.logical_relationships(graph)
    placements=cdc.clm.placed_luts(text,graph)
    parents={cdc.endpoints.base.native_parent(r[k]) for r in logical+internal for k in ('SourceFF','DestinationFF')}
    parents.update(n.rsplit('/',2)[0] for n in placements)
    require('route-dump.txt' in native['Artifacts'],'current native route dump absent')
    dump=cdc.add(watched,route_receipt.parent/'route-dump.txt',native['Artifacts']['route-dump.txt'])
    route,normalization=cdc.route_objects(dump,parents)
    mapper=cdc.clm.Mapper(graph,route,placements);mapped=[mapper.map(r) for r in logical]
    supplement=cdc.sameble.derive(graph,route,{'Schema':'camera720-native-endpoints-v1','SameBLEInterstageInventory':internal,
        'LogicalRelationships':mapped,'Queries':[],'CandidateADF':candidate,'BuildPlanSHA256':ex['BuildPlanSHA256']})
    mapped.extend(mapper.map(r) for r in supplement['LogicalRelationships'])
    build=Path(ex['BuildPlan']).resolve().parent
    paths={'top':build/'source/board/camera720_calibrated_top.v',
        'compiled_top':build/'compiled/board/camera720_calibrated_top.v',
        'fdc':build/'compiled/board/camera720-output-diagnostic.fdc',
        'pcf':build/'device_map/camera720_calibrated_top.pcf',
        'prt':build/'place_route/camera720_calibrated_top_prr_route_optimize.prt',
        'official':PROJECT/'platform/video_base/HDMI_IN_DDR3_HDMI_OUT_top.fdc',
        'camref':PROJECT/'board/raw_camera_capture_cam2_ref.fdc','campins':PROJECT/'board/raw_camera_capture_cam2_ref-pins.json'}
    for p in paths.values():cdc.add(watched,p)
    txt={k:p.read_text(encoding='utf-8-sig') for k,p in paths.items()}
    pins=cdc.io.structure.io.pin_audit(cdc.io.module_as(txt['top'],'camera_vga_output_top'),txt['fdc'],txt['pcf'],txt['prt'],
        cdc.io.module_as(text,'camera_vga_output_top'),txt['official'],txt['camref'],json.loads(txt['campins']))
    cdc.io.source_inventory(txt['top'],txt['fdc'])
    constraints,_=cdc.endpoints.base.constraint_inventory(paths['fdc']);queries=cdc.make_queries(mapped,constraints)
    gray=cdc.endpoints.base.gray_structures(graph)+cdc.endpoints.monitor.monitor_gray(graph)
    held=cdc.endpoints.monitor.held_snapshot(graph);held['AllFirstConsumers']=cdc.endpoints.monitor.held_first_sinks(graph,held)
    plan={'Target':TARGET,'CandidateADF':candidate,'CandidateADFSHA256':candidate['SHA256'],
        'ExportReceipt':cdc.ref(export_receipt),'RouteReceipt':cdc.ref(route_receipt),'BuildPlan':cdc.ref(ex['BuildPlan']),
        'Netlist':ex['Netlist'],'RouteDump':cdc.ref(dump),'TimingReport':ex['TimingReport'],
        'GeneratedTop':cdc.ref(paths['top']),'CompiledTop':cdc.ref(paths['compiled_top']),
        'ActualCells':len(graph.cells),'ActualFFs':len(graph.ff),'LogicalRelationships':mapped,
        'SameBLESupplement':supplement,'NativeLUTBindings':cdc.endpoints.native_lut_bindings(graph,route,mapped),
        'InternalCarryLinks':mapper.carry_links,'RouteNormalization':normalization,'Constraints':constraints,'Queries':queries,
        'Pins':pins,'InputDelays':cdc.io.structure.delay.audit(graph),
        'SyncPadSinks':cdc.io.structure.sync_pad_sinks(graph),'Structure':{'Gray':gray,'MonitorHeld':held}}
    watch_tools(watched)
    require(not cdc.inspect.drift(watched),'derive input drift')
    return plan,watched,graph


def groups(queries,missing,maximum=128):
    require(type(maximum) is int and 1<=maximum<=128,'group bound must be 1..128')
    known={cdc.timing.identity(q):q for q in queries}
    require(len(known)==len(queries),'duplicate native identity')
    needed={cdc.timing.identity(q) for q in missing}
    require(needed<=set(known),'unknown missing identity')
    reaches=defaultdict(set)
    for q in queries:reaches[q['Endpoint']].add((q['Source'],q['LaunchOutput']))
    result=[]
    for q in sorted((known[k] for k in needed),key=lambda q:(cdc.timing.domain(q),cdc.timing.identity(q))):
        for group in result:
            if group['Domain']!=list(cdc.timing.domain(q)):continue
            launches=dict(group['SourceLaunches']);ends=set(group['Endpoints'])|{q['Endpoint']}
            if q['Source'] in launches and launches[q['Source']]!=q['LaunchOutput']:continue
            launches[q['Source']]=q['LaunchOutput']
            if len(ends)>maximum or len(group['ExpectedIdentities'])>=maximum:continue
            # Include ALL known identities, even cases already covered by the
            # initial report, when detecting competing launches at an endpoint.
            if any(len(reaches[e]&set(launches.items()))>1 for e in ends):continue
            group.update(SourceLaunches=launches,Endpoints=sorted(ends))
            group['ExpectedIdentities'].append({k:q[k] for k in cdc.timing.IDENTITY})
            break
        else:
            result.append({'Domain':list(cdc.timing.domain(q)),'SourceLaunches':{q['Source']:q['LaunchOutput']},
                'Endpoints':[q['Endpoint']],'ExpectedIdentities':[{k:q[k] for k in cdc.timing.IDENTITY}]})
    for group in result:
        ss=sorted(group['SourceLaunches']);qs=sorted(group['SourceLaunches'].values());es=group['Endpoints'];pins=sorted(set(ss+qs+es))
        require(all(cdc.SAFE.fullmatch(p) for p in pins),'unsafe query pin')
        pattern='^('+'|'.join(re.escape(p) for p in pins)+')$'
        group.update(Pins=pins,PinPattern=pattern,PinCommand='get_pins -hierarchical -regexp {'+pattern+'}',
            Command='report_path_timing -delay_type min_max -max_path 1000 -nworst 8 -report_exception TRUE -from {'+
                ' '.join(ss)+'} -through {'+' '.join(qs)+'} -to {'+' '.join(es)+'}')
    actual=[cdc.timing.identity(q) for g in result for q in g['ExpectedIdentities']]
    require(len(actual)==len(set(actual)) and set(actual)==needed,'group coverage differs')
    return result


def query_reports(path,value,queries):
    path=Path(path).resolve()
    commands=cdc.inspect.query_commands(Path(value['QueryBody']).read_text(encoding='ascii'))
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
        require(sources|ends|outputs<=known,'native query has unknown current CDC selector')
        require(all(sum(o.rsplit('/',1)[0]==s.rsplit('/',1)[0] for o in outputs)==1 for s in sources),
                'one selected launch output per source CLK required')
        require(all(any(o.rsplit('/',1)[0]==s.rsplit('/',1)[0] for s in sources) for o in outputs),
                'through collection contains unpaired launch output')
        require(preceding is not None,'CDC query lacks exact pin enumeration')
        pattern=preceding.split(' -regexp {',1)[1][:-1]
        require(pattern.startswith('^(') and pattern.endswith(')$'),'exact pin alternatives required')
        pins=[re.sub(r'\\(.)',r'\1',s) for s in pattern[2:-2].split('|')]
        require(len(pins)==len(set(pins)) and set(pins)==sources|ends|outputs,'pin enumeration scope differs')
        pin_groups.append({'PinPattern':pattern,'Pins':pins});preceding=None
    log=(path.parent/'stdout.log').read_text(encoding='gb18030')
    issues=cdc.timing.validate_pin_log(log,pin_groups);reports=[]
    for name in value['Artifacts']:
        if not name.endswith('.rtr') or name.endswith('_exception.rtr') or 'report_path_timing/' not in name:continue
        report=(path.parent/name).resolve()
        with report.open(encoding='gb18030') as stream:header=''.join(next(stream,'') for _ in range(18))
        cdc.timing.validate_report_filter(name,header,timed)
        index=int(re.search(r'report_path_timing_(\d+)/',name.replace('\\','/'))[1])-1
        actual=cdc.timing.field(r'^\| Tcl Command\s*:\s*(.*?)\s*$',header,'command')
        normalize=lambda text:[{p[2:] if p.startswith(('p:','t:')) else p for p in v.split()}
                               for v in re.findall(r'-through \{([^}]+)\}',text)]
        require(normalize(actual)==normalize(timed[index]),'native through filter changed or dropped')
        reports.append(report)
    require(len(reports)==len(timed),'targeted report count differs from requested commands')
    return reports,issues,log


def tx_records(report):
    """Current output-video pad maxima; not external AC setup/hold acceptance."""
    records=[]
    text=Path(report).read_text(encoding='ascii')
    for block in re.split(r'(?=^Startpoint\s*:)',text,flags=re.M)[1:]:
        match=re.search(r'^Endpoint\s*:\s*(\S+) \(port\)\s*$',block,re.M)
        if not match or match[1] not in cdc.io.native_io.tx.PORTS:continue
        field=lambda p:cdc.timing.field(p,block,'TX')
        kind,corner=field(r'^Path Type\s*:\s*(min|max) \((slow|fast) corner\)\s*$')
        if kind!='max':continue
        require(field(r'^Path Class\s*:\s*(.+?)\s*$')=='combinational timing path','unexpected TX path class')
        source=field(r'^Startpoint\s*:\s*(.+?)\s*$');port=match[1]
        clocks=re.findall(r'^ Clock (\S+) \((rising|falling) edge\)',block,re.M)
        require((source.startswith('system/output_video/') and clocks==[('pixel_clk','rising')]) if port!='pix_clk'
                else source=='clk_27m (port)' and not clocks,'TX source/edge differs')
        require('video_pll/u_gpll/gpll_inst/CLKOUT0' in block,'TX clock bypasses expected PLL')
        records.append({'Port':port,'Corner':corner,'DelayType':kind,'Source':source,
            'ReportedPadArrivalNS':float(field(r'^ Data arrival time\s+('+cdc.io.native_io.NUMBER+r')\s+Logic Levels:')),
            'Report':str(Path(report).resolve()),'PathSHA256':hashlib.sha256(block.encode('ascii')).hexdigest()})
    return records


def physical_basis(plan,graph,watched):
    documents={cdc.timing.MANUAL:cdc.timing.MANUAL_SHA,
        Path('D:/pango/PDS_2023.2/doc/Tcl_Command_User_Guide.pdf'):'7be74cf2d0fba752cc7016a47b994d9bfb05805f4c7b19fb4d15266033de9ba4',
        Path('D:/pango/PDS_2023.2/doc/Timing_Analyzer_User_Guide.pdf'):'9d04d214d74f95348ce292b3c244e6ee880dd7095014209db243f8b8c1b2b420'}
    for p,h in documents.items():cdc.add(watched,p,h)
    extract=cdc.add(watched,PROJECT/'work/camera720-clm-timing-manual-evidence.json','1d86f0682e8df259efd30000daf3660c7ccc544b382a3cba4e4fb6d4b1096524')
    require({Path(r['Document']):r['SHA256'] for r in read(extract)}==documents,'vendor manual identity differs')
    represented=set();merged=[]
    for q in plan['Queries']:
        indices=q['LogicalRelationships'];represented.update(indices)
        rows=[plan['LogicalRelationships'][i] for i in indices]
        if len(rows)==1:continue
        cells=[graph.ff[r['DestinationFF']] for r in rows]
        require(len({r['DestinationPlacement']['Site'] for r in rows})==1,'merged physical boundary spans sites')
        require(len({c['Ports']['CK'] for c in cells})==1 and len({c['Primitive'] for c in cells})==1
                and all(c['Parameters']==cells[0]['Parameters'] for c in cells),'merged target FF clock/configuration differs')
        merged.append({**{k:q[k] for k in cdc.timing.IDENTITY},'LogicalRelationships':indices,
            'DestinationFFs':[r['DestinationFF'] for r in rows],'PhysicalSite':rows[0]['DestinationPlacement']['Site'],
            'ActualClockNet':cells[0]['Ports']['CK'],'Primitive':cells[0]['Primitive'],'Parameters':cells[0]['Parameters']})
    require(represented==set(range(len(plan['LogicalRelationships']))),'physical queries omit logical relationships')
    return {'Documents':[cdc.ref(p) for p in documents],'Extract':cdc.ref(extract),'MergedQueries':merged,
        'MergedQueryCount':len(merged),'AllMergedGroupsHomogeneous':True,'LogicalRelationshipsRetained':len(represented),
        'VendorPhysicalSequentialTimingModelReliedUpon':True,'CompletePhysicalCaseCoverageRequiredSeparately':True,
        'FinalCandidateFullSTARequiredSeparately':True,'PhysicalTimingAggregationProved':False,
        'IndividualFFArcsEnumerated':False,'IndependentWorstOverInternalFFFormulaClaimed':False,
        'DirectInternalChainsScope':'Exact same-BLE Q-to-D chains rely on the vendor packed sequential model and independent full STA, without invented individual arc delays.'}


def protocol_bounds(plan,records):
    by_identity=defaultdict(list)
    for r in records:by_identity[cdc.timing.identity(r)].append(r)
    gray=defaultdict(list)
    for row in plan['Structure']['Gray']:gray[row['Group']].append(row)
    scopes=[]
    for name,bits in sorted(gray.items()):
        indices={i for i,r in enumerate(plan['LogicalRelationships']) if any(r['SourceFF']==b['Source'] and r['DestinationFF']==b['First'] for b in bits)}
        require(indices,'Gray group lacks represented source/first-stage relationships')
        scopes.append(('gray:'+name,indices,plan['Constraints']['PeriodsNS'][bits[0]['SourceClock']]))
    held={i for i,r in enumerate(plan['LogicalRelationships']) if 'held snapshot to every first sequential consumer' in r['Purposes']}
    require(held,'monitor held-data scope absent')
    scopes.append(('held_snapshot',held,2*plan['Constraints']['PeriodsNS']['board27']))
    bounds=[];missing=[]
    for name,indices,budget in scopes:
        keys={cdc.timing.identity(q) for q in plan['Queries'] if indices.intersection(q['LogicalRelationships'])}
        require(keys,'protocol scope has no mapped query')
        for corner in ('slow','fast'):
            rows=[r for k in keys for r in by_identity[k] if r['Corner']==corner and r['Kind']=='max-delay']
            if {cdc.timing.identity(r) for r in rows}!=keys:
                missing.append({'Stage':'protocol-propagation','Group':name,'Corner':corner});continue
            worst=max(r['ArrivalNS'] for r in rows)
            require(all(r['ArrivalNS']>=0 for r in rows) and worst<budget,'protocol propagation exceeds source/consumption budget')
            bounds.append({'Group':name,'Corner':corner,'MaximumReportedArrivalNS':worst,'BudgetNS':budget,
                'PhysicalQueries':len(keys),'ReleasedOperationOnly':True,'ArbitraryStoppedClockResetEpochProven':False,
                'BoundBasis':'Complete launch-qualified maxima with nonnegative arrival; Gray spread bounded by maximum arrival, held data bounded by two destination periods.'})
    return bounds,missing


def audit_value(export_receipt,route_receipt,query_receipts):
    export_receipt=Path(export_receipt).resolve();route_receipt=Path(route_receipt).resolve()
    paths=sorted(Path(p).resolve() for p in query_receipts)
    require(len(paths)==len(set(paths)),'duplicate query receipt')
    plan,watched,graph=derive(export_receipt,route_receipt)
    reports=[cdc.add(watched,plan['TimingReport']['Path'],plan['TimingReport']['SHA256'])]
    refs=[];issues=[];site_logs=[]
    for path in paths:
        value=bind_native(path,'query',watched,plan['CandidateADF'])
        require(value['BuildPlanSHA256']==plan['BuildPlan']['SHA256'],'query build differs')
        found,bad,log=query_reports(path,value,plan['Queries'])
        reports.extend(found);issues.extend(bad);refs.append(cdc.ref(path))
        if re.search(r'^Site \S+ \(\d+\) :',log,re.M):site_logs.append(log)
    reports=sorted(set(reports))
    records,bad,other=cdc.collect(plan['Queries'],reports);issues.extend(bad)
    coverage=cdc.timing.coverage(plan['Queries'],records,issues);missing=list(coverage['MissingCases'])
    bounds,incomplete=protocol_bounds(plan,records);missing.extend(incomplete)
    held_complete=not any(r['Group']=='held_snapshot' for r in incomplete)
    plan['Structure']['MonitorHeld']['HeldBusPhysicalBoundComplete']=held_complete
    plan['Structure']['MonitorHeld']['AllFirstConsumers']['PhysicalBoundComplete']=held_complete
    plan['Structure']['MonitorHeld']['Limits']='Released-operation Boolean handshake and all first-consumer physical boundaries. Full current STA and reset effect remain separate; no arbitrary stopped-clock reset or analog MTBF claim.'
    pins=plan['Pins']
    if len(site_logs)==1:cdc.io.structure.io.apply_native_sites(pins,site_logs[0])
    else:missing.append({'Stage':'native-site-inventory','ObservedCompleteSiteLogs':len(site_logs),'Expected':1})
    electrical=cdc.io.native_io.io_parameters(plan['RouteDump']['Path'],pins)
    pins['FinalNativeElectricalAttributesVerified']=electrical['Passed']
    dvp=cdc.io.native_io.dvp_summary(cdc.io.native_io.dvp_records(reports))
    missing.extend(dict(Stage='conditional-dvp',**r) for r in dvp['MissingCases'])
    tx=[r for p in reports for r in tx_records(p)]
    actual={(r['Port'],r['Corner'],r['DelayType']) for r in tx}
    expected={(p,c,'max') for p in cdc.io.native_io.tx.PORTS for c in ('slow','fast')}
    missing.extend(dict(zip(('Port','Corner','DelayType'),k),Stage='native-tx-maxima') for k in sorted(expected-actual))
    commands=cdc.io.native_io.tx.commands(cdc.add(watched,PROJECT/'board/ms7210_commands.vh').read_text(),
        cdc.add(watched,PROJECT/'platform/video_base/source/hdmi/ms7210_ctl.v').read_text())
    basis=physical_basis(plan,graph,watched)
    watch_tools(watched)
    require(not cdc.inspect.drift(watched),'current digital audit input drift')
    result={**plan,'Schema':SCHEMA,'Producer':cdc.ref(SELF),'QueryReceipts':refs,'Records':records,
        'CaseCoverage':coverage['CaseCoverage'],'ExpectedCases':coverage['ExpectedCases'],'ObservedCases':coverage['CoveredCases'],
        'Missing':missing,'Violations':issues,'ProtocolTimingBounds':bounds,'ExcludedOtherLaunches':other,'PhysicalSTABasis':basis,
        'ScopedDigitalChecksPassed':not missing and not issues,'NativeElectricalParameters':electrical,'DVP':dvp,
        'TX':{'Vendor49CommandsIdentical':True,'Commands':commands,'NativeMaximumPaths':tx,
              'NativeMinimumDelaysObtained':False,'RegisterSamplingInterpretationVerified':False},
        'InputSHA256':{str(p):h for p,h in watched.items()},'InputDrift':[],
        'HardwareAccessed':False,'EDAExecuted':False,'HardwareReleaseAllowed':False,'OpticalCorrectionAccepted':False,
        'Limits':'Current-candidate scoped IO/CDC and vendor sequential timing model. Independent final full STA/reset effect remain required. External DVP/TX AC, actual board voltages, analog MTBF and individual packed FF arc aggregation are not claimed.'}
    return result,watched


def verify(proof_path):
    path=Path(proof_path).resolve();saved=read(path);bound={};cdc.add(bound,path)
    require(saved.get('Schema')==SCHEMA and saved.get('Target')==TARGET,'wrong calibrated digital proof')
    for p,h in saved['InputSHA256'].items():cdc.add(bound,p,h)
    for item in [saved['ExportReceipt'],saved['RouteReceipt']]+saved['QueryReceipts']:cdc.add(bound,item['Path'],item['SHA256'])
    actual,watched=audit_value(saved['ExportReceipt']['Path'],saved['RouteReceipt']['Path'],[r['Path'] for r in saved['QueryReceipts']])
    clean=lambda value:json.loads(json.dumps({k:v for k,v in value.items() if k not in ('CreatedUTC','InputSHA256')}))
    require(clean(actual)==clean(saved),'saved calibrated digital proof differs from recomputation')
    for p,h in watched.items():cdc.add(bound,p,h)
    return actual,bound


def prepare(export_receipt,route_receipt,output,per_body=8):
    # No queries means the audit remains explicitly incomplete. The actual
    # initial records determine the supplementary native requests.
    initial,watched=audit_value(export_receipt,route_receipt,[])
    coverage=cdc.timing.coverage(initial['Queries'],initial['Records'],initial['Violations'])
    grouped=groups(initial['Queries'],coverage['MissingCases']);payloads=cdc.bodies(grouped,per_body)
    graph=cdc.io.graph(Path(initial['Netlist']['Path']).read_text(encoding='ascii'))
    dvp=cdc.io.native_io.dvp_records([Path(initial['TimingReport']['Path']).resolve()]);pairs=[]
    for port in sorted(cdc.io.native_io.PORTS):
        choices=[r for r in dvp if r['Port']==port and r['DelayType']=='max']
        require(choices,'no current DVP setup endpoint for '+port)
        row=min(choices,key=lambda r:(r['SlackNS'],r['Endpoint'],r['Corner'],r['ReportLine']))
        pairs.append((port,row['Endpoint']))
    payloads['query-io.tcl']=cdc.io.query_body(initial['Pins'],pairs,cdc.io.tx_launches(graph))
    output=Path(output).absolute()
    require(output==output.resolve() and output.is_relative_to(cdc.inspect.prep.WORK) and not output.exists(),'fresh query directory required')
    output.mkdir()
    for name,body in payloads.items():(output/name).write_text(body,encoding='ascii',newline='\n')
    value={'Schema':'camera720-calibrated-digital-query-plan-v1','Target':TARGET,'Producer':cdc.ref(SELF),
        'InitialEvidence':initial,'Groups':grouped,'CommandsPerBody':per_body,'QueryBodies':{n:cdc.ref(output/n) for n in payloads},
        'InputSHA256':{str(p):h for p,h in watched.items()},'HardwareReleaseAllowed':False,'NativeQueriesExecuted':False}
    cdc.inspect.diagnostic.write(output/'plan.json',value)
    return value


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('mode',choices=('prepare','audit','verify'))
    p.add_argument('--export-receipt',type=Path);p.add_argument('--route-receipt',type=Path)
    p.add_argument('--query-receipt',type=Path,action='append',default=[]);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--commands-per-body',type=int,default=8);a=p.parse_args()
    if a.mode=='verify':value,_=verify(a.output)
    else:
        require(a.export_receipt and a.route_receipt,'actual current export and route receipts required')
        if a.mode=='prepare':value=prepare(a.export_receipt,a.route_receipt,a.output,a.commands_per_body)
        else:
            value,_=audit_value(a.export_receipt,a.route_receipt,a.query_receipt)
            require(not a.output.exists(),'fresh digital audit output required');cdc.inspect.diagnostic.write(a.output,value)
    print(json.dumps({k:value[k] for k in ('Schema','CandidateADFSHA256','ExpectedCases','ObservedCases','ScopedDigitalChecksPassed','CommandsPerBody') if k in value}))


if __name__=='__main__':main()
