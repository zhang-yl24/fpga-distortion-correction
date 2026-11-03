"""Independent fisheye IO/interstage checks from the applied native ADF.

Only current direct graph objects generate queries. Packed BLE arcs use exact
vendor-model structural proof plus all-ten-table STA. Ordinary interstage arcs
retain both setup/hold corners. No analog/external AC acceptance is inferred.
"""
import argparse
from collections import Counter
import copy
import hashlib
import json
from pathlib import Path
import re

import hdmi_camera_fisheye_fill8r3s3_build as build
import hdmi_camera_fisheye_fill8r3s3_scoped_native as baseline
import hdmi_camera_fisheye_fill8r3s3_physical as physical
import hdmi_camera_fisheye_fill8r3s3_scoped_native as native
import hdmi_camera_fisheye_fill8r3s3_audit as audit
import camera720_io_evidence as electrical
import audit_camera_vga_io as sites
import camera720_cdc_native as timing

SELF=Path(__file__).resolve()
require,sha,read,write=build.require,build.sha,build.read,build.write
add,merge,ref=baseline.add,baseline.merge,baseline.ref
_INVENTORY_CACHE={}
MAX_INTERSTAGE_REPORTS_PER_STAGE=8


def inventory(scope):
    """Reuse same-process CPU inventory only after hashing its entire closure.

    Query/fresh-STA receipts and their timing records are never cached here.
    The full candidate dictionary is part of the key, including every exact
    pin/chain and matrix field; returned dictionaries cannot mutate authority.
    """
    key=hashlib.sha256(json.dumps(scope,sort_keys=True,separators=(',',':')).encode('utf-8')).hexdigest()
    cached=_INVENTORY_CACHE.get(key)
    if cached is not None:
        require(not baseline.drift(cached[1]),'cached fisheye native inventory input drift')
        return copy.deepcopy(cached)
    value,watched=_inventory(scope);watched=dict(watched);add(watched,SELF)
    require(not baseline.drift(watched),'fisheye native inventory inputs changed while deriving')
    _INVENTORY_CACHE[key]=copy.deepcopy((value,watched));return copy.deepcopy((value,watched))


def _inventory(scope):
    graph,route,mapper,watched=audit.native_graph(scope)
    consumers=audit.consumer_index(graph)
    pins=[]
    for row in scope['Pins']['Inventory']:
        require(row['Route'] is not None and row['FunctionalConnections'],'retained direct pin lacks native site/connections')
        connections=[]
        for c in row['FunctionalConnections']:
            if c['Primitive']=='V_BUF':
                cell=graph.cells[c['Cell']];ports=cell['Ports']
                loads=[(name,pin)for name,other in graph.cells.items()for pin,value in other['Ports'].items()
                    if value==ports['Z']and(name,pin)!=(c['Cell'],'Z')]
                require(c['Pin']=='I'and ports['I']==row['Port']and len(loads)==1
                    and graph.cells[loads[0][0]]['Primitive']=='V_IBUFDS'and loads[0][1]=='IB',
                    'unreviewed primary-pad differential negative-input shim')
            require(c['Primitive'] in ('V_IBUF','V_IBUFDS','V_OBUF','V_OBUFT','V_OBUFDS','V_OBUFTDS','V_IOBUF','V_BUF'),
                    'primary pad connection is not a reviewed IO primitive')
            connections.append({**c,'NativeInstance':c['Cell'].rsplit('/',1)[0]})
        pins.append({'Port':row['Port'],'Site':row['Route']['Site'],**row['Attributes'],
            'FinalPrimitiveConnections':connections,'SourceDisposition':row.get('Disposition','routed_with_actual_native_consumer')})
    require(scope['Pins']['Declared']==scope['Pins']['Routed']==scope['Pins'].get('Active')==len(pins)==144
        and scope['Pins'].get('UnusedPads')==[],
            'direct declared/routed pins must all have native consumers')
    mapped=[];packed=[];chains=[]
    chain_rows=list(scope['Synchronizers'])+list(scope['ReleaseChains'])
    key_chain=scope['LocalResetGuards'].get('KeyReleaseChain')
    if key_chain is not None:chain_rows.append(key_chain)
    seen_chains=set()
    for chain in chain_rows:
        first,second=chain['First'],chain['Second']
        if (first,second)in seen_chains:continue
        seen_chains.add((first,second))
        label=chain.get('Family',chain.get('FirstLogical',first))
        if chain.get('LocalReleaseFF')is not None:
            actual=audit.scalar_chain(graph,first,second,
                (chain['LocalReleaseFF'],chain['LocalReleaseInactivePhysicalQ']),label,consumers)
        elif 'InactivePhysicalQ'in chain:
            actual=audit.boolean.release_chain(graph,second,chain['InactivePhysicalQ'][1])
            require(actual['First']==first,'ordinary release predecessor differs')
            pa,pb=graph.g['FFPlacement'][first],graph.g['FFPlacement'][second]
            actual.update(FirstPlacement=pa,SecondPlacement=pb,SameSite=pa['Site']==pb['Site'],
                SameBLE=pa==pb,DestinationClock=graph.clock(graph.ff[first]['Ports']['CK'])['Domain'],NativeQueries=[])
        else:
            release=None
            if graph.ff[second]['Ports']['D']!=graph.ff[first]['Ports']['Q']:
                others={token[3:]for token in graph.support(graph.ff[second]['Ports']['D'])
                    if token.startswith('ff:')and token!='ff:'+first}
                require(len(others)==1,'interstage gating has no unique local release FF')
                release=graph.ff[next(iter(others))]['Ports']['Q']
            actual=graph.chain(first,second,label,release)
        chains.append(actual)
        if actual['SameBLE']:
            require(actual['SameSite']and not actual['NativeQueries'],'unqueryable interstage is not exact same BLE')
            packed.append(actual);continue
        row={'SourceFF':first,'DestinationFF':second,'DestinationPin':'D',
            'SourceClock':actual['DestinationClock'],'DestinationClock':actual['DestinationClock'],
            'Labels':[label],'Purposes':['ordinary synchronizer interstage'],
            'OriginalEndpoints':[q['Endpoint'] for q in actual['NativeQueries']]}
        mapped.append(mapper.map(row))
    queries=[];boundary_support={};launch_sources={}
    for row in mapped:
        source=row['SourceFF'];m=re.search(r'/(FFAPP|FF)([0-3])/FF$',source)
        require(m is not None,'unknown direct synchronizer physical FF slot')
        physical_q=row['SourcePlacement']['Site']+('/CR' if m[1]=='FFAPP' else '/Q')+m[2]
        parent=row['SourceNativeClockPin'].rsplit('/',1)[0]
        launch=row['SourceNativeOutputPin']
        require(launch not in launch_sources or launch_sources[launch]==source,'ordinary interstage native Q source is ambiguous')
        launch_sources[launch]=source
        for boundary in row['NativeBoundaries']:
            support=sorted(mapper.support(boundary['FunctionalBoundaryNet']))
            end=boundary['Endpoint']
            entry={'FunctionalBoundaryNet':boundary['FunctionalBoundaryNet'],
                'NativeBoundaryNet':boundary.get('NativeBoundaryNet',boundary.get('BoundaryNet')),'SupportFFs':support,
                'CompleteNativeBoundarySupportVerified':True}
            require(end not in boundary_support or boundary_support[end]==entry,
                'ordinary interstage timing endpoint has conflicting actual FF support')
            boundary_support[end]=entry
            queries.append({'FromCLK':row['SourceNativeClockPin'],'LaunchQ':row['SourceNativeOutputPin'],
                'Endpoint':boundary['Endpoint'],'Clock':row['DestinationClock'],
                'NativeObjects':{'SourcePhysicalQ':[physical_q],'SourceCLKNet':[route['Pins'][parent,'CLK']]}})
    physical.static_helpers(watched,SELF)
    matrix=interstage_matrix(queries,boundary_support,launch_sources)
    return {'Pins':{'PinInventory':pins},'InterstageQueries':queries,'PackedInterstage':packed,'Chains':chains,
        'InterstageReadOnlyMatrix':matrix},watched


def interstage_matrix(queries,boundary_support,launch_sources):
    expected={(q['LaunchQ'],q['Endpoint'])for q in queries}
    require(len(expected)==len(queries),'ambiguous ordinary interstage native Q/endpoint inventory')
    require(set(launch_sources)=={q['LaunchQ']for q in queries},'ordinary interstage launch axis omits a qualified source FF')
    actual=set()
    for end in sorted({q['Endpoint']for q in queries}):
        entry=boundary_support.get(end,{})
        require(entry.get('CompleteNativeBoundarySupportVerified')is True
            and entry.get('FunctionalBoundaryNet')and entry.get('NativeBoundaryNet')
            and isinstance(entry.get('SupportFFs'),list)and entry['SupportFFs']==sorted(set(entry['SupportFFs'])),
            'complete ordinary interstage actual native endpoint support required')
        actual.update((q,end)for q,source in launch_sources.items()if source in entry['SupportFFs'])
    require(actual==expected,'batched ordinary interstage query contains an unexpected/missing actual source-Q/endpoint path')
    return {'CompleteNativeSupportMatrixVerified':True,'AllowedPairs':[{'LaunchQ':q,'Endpoint':end}for q,end in sorted(expected)],
        'LaunchSourceFFs':launch_sources,'NativeEndpointSupport':boundary_support,
        'NoTimingExceptionApplied':True,'RequiredDualCornerSetupHoldEnumerationComplete':False}


def query_bodies(current):
    matrix=current.get('InterstageReadOnlyMatrix')
    if matrix is not None:
        queries=current['InterstageQueries'];require(interstage_matrix(queries,matrix['NativeEndpointSupport'],
            matrix['LaunchSourceFFs'])==matrix,'ordinary interstage batch support proof changed')
        commands=['show -dev_instance {'+site+'}'for site in sorted({r['Site']for r in current['Pins']['PinInventory']})]
        if queries:
            axes=[[r[key]for r in queries]for key in('FromCLK','LaunchQ','Endpoint')]
            axes=[sorted(set(axis))for axis in axes]
            for part in physical.bounded_name_chunks({n for axis in axes for n in axis}):
                commands.append(physical.exact_selector(part)['Command'])
            commands.append('report_path_timing -delay_type min_max -max_path 10000 -nworst 8 -report_exception TRUE'
                +' -from {'+' '.join('t:'+n for n in axes[0])+'}'
                +' -through {'+' '.join('t:'+n for n in axes[1])+'}'
                +' -to {'+' '.join('t:'+n for n in axes[2])+'}')
        body='\n'.join(commands)+'\n';baseline.query_commands(body);return[body]
    commands=['show -dev_instance {'+site+'}' for site in sorted({r['Site'] for r in current['Pins']['PinInventory']})]
    for q in current['InterstageQueries']:
        commands.extend([physical.exact_selector(sorted({q['FromCLK'],q['LaunchQ'],q['Endpoint']}))['Command'],
            'report_path_timing -delay_type min_max -max_path 10000 -nworst 8 -report_exception TRUE -from {t:'+q['FromCLK']+
            '} -through {t:'+q['LaunchQ']+'} -to {t:'+q['Endpoint']+'}'])
    # Keep site enumeration in one query to preserve the exact inventory.
    # Each native timing command reloads the design: bound their count as well
    # as the grammar length, splitting only at whole selector/report pairs.
    bodies=[];body=[];reports=0
    for command in commands:
        if command.startswith('get_pins')and(len(body)>=220 or reports>=MAX_INTERSTAGE_REPORTS_PER_STAGE):
            bodies.append('\n'.join(body)+'\n');body=[];reports=0
        body.append(command)
        reports+=int(command.startswith('report_path_timing '))
    if body:bodies.append('\n'.join(body)+'\n')
    for body in bodies:baseline.query_commands(body)
    return bodies


def warning_review(scope,receipts,watched):
    ports={r['Port']:r['Direction'] for r in scope['Pins']['Inventory']};rows=[]
    source=Path(scope['BuildPlan']['Path']).parent
    originals=[source/'place_route'/name for name in ('run_route_optimize.log','run_route.log','run_place.log')]
    for path in originals:add(watched,path)
    for path,value in receipts:
        stage=Path(path).parent
        for log in sorted(stage.rglob('*.log')):
            add(watched,log)
            for number,line in enumerate(log.read_text(encoding='gb18030',errors='strict').splitlines(),1):
                if not re.match(r'^\s*W:',line):continue
                message=line.strip()
                wrapped=re.fullmatch(r'W: report_path_timing_(\d+): (Timing-408[67]: .+|Failed to open file .+)',message)
                if wrapped:
                    require(value.get('Mode')=='query' and any('report_path_timing_'+wrapped[1]+'/' in n
                        and n.endswith(build.TARGET+'.rtr') for n in value['Artifacts']),
                        'native query warning prefix has no bound report')
                    message='W: '+wrapped[2]
                electrical_warning=re.fullmatch(r"W: Timing-(4086|4087): Port '([^']+)' is not constrained, it is treated as combinational (input|output)\.",message)
                if electrical_warning:
                    # Native text must identify a declared port and its real
                    # direction; external AC remains explicitly unaccepted.
                    code,port,direction=electrical_warning.groups()
                    require(port in ports and direction==('input' if code=='4086' else 'output')
                        and ports[port] in (direction.upper(),'INOUT'),'native AC warning port/direction differs')
                    rows.append({'Code':'Timing-'+electrical_warning[1],'Log':str(log),'Line':number,'Port':port,'Text':line});continue
                missing=re.fullmatch(r'W: Failed to open file (.+)',message)
                accepted=False
                nested=re.search(r'(?:^|/)report_path_timing_(\d+)(?:/|$)',log.relative_to(stage).as_posix())
                query_report_bound=(value.get('Mode')=='query' and (wrapped is not None or
                    nested is not None and any('report_path_timing_'+nested[1]+'/' in n and n.endswith(build.TARGET+'.rtr')
                        for n in value['Artifacts'])))
                if (value.get('Mode')=='export' or query_report_bound) and missing:
                    for name in ('run_route_optimize.log','run_route.log','run_place.log'):
                        expected=build.paths.alias_path(build.ROOT,value['RepoAlias'],stage/'place_route'/name)
                        if missing[1]==expected and not (stage/'place_route'/name).exists():accepted=True
                require(accepted,'unknown fisheye native warning: '+line)
                rows.append({'Code':'MissingStandaloneRouteCompanion','Log':str(log),'Line':number,'Text':line})
    return {'Passed':True,'Warnings':rows,'Counts':dict(Counter(r['Code'] for r in rows)),'ExternalACAccepted':False}


def bind_query_receipt(path):
    """Bind either full native or explicitly query-only read-only evidence."""
    saved=read(path)
    if saved.get('Schema')=='hdmi-camera-fisheye-fill8r3s3-targeted-native-query-v1':
        import hdmi_camera_fisheye_fill8r3s3_target_query as targeted
        require(Path(targeted.__file__).resolve()==SELF.with_name('hdmi_camera_fisheye_fill8r3s3_target_query.py'),
            'targeted native query provider location differs')
        value,watched=targeted.bind_receipt(path)
        require(value.get('Mode')=='query'and value.get('SourceProof')is not None,
            'targeted native receipt must be a current application-bound read-only query')
        physical.static_helpers(watched,targeted.__file__)
        return value,watched
    return native.bind_receipt(path)


def derive(scope,application_path,export_path,route_path,query_paths):
    # Import here to avoid an import cycle with the final provider.
    import hdmi_camera_fisheye_fill8r3s3_final as final
    acceptance=final.native_acceptance(scope);current,watched=inventory(scope)
    expected_bodies=query_bodies(current);require(len(query_paths)==len(expected_bodies),'complete direct IO/interstage query receipts required')
    exported,inputs=native.bind_receipt(export_path);merge(watched,inputs)
    receipts=[(Path(export_path),exported)];logs=[];records=[];found=set()
    lookup={(q['FromCLK'],q['LaunchQ'],q['Endpoint']):q for q in current['InterstageQueries']}
    require(len(lookup)==len(current['InterstageQueries']),'duplicate direct interstage query identity')
    for path,body in zip(query_paths,expected_bodies):
        value,inputs=bind_query_receipt(path);merge(watched,inputs);receipts.append((Path(path),value))
        require(value['Mode']=='query' and value['SourceProof']==ref(application_path)
            and value['SourceADF']==exported['SourceADF']and value['SourceADFSHA256']==exported['SourceADFSHA256']
            and value['BuildPlanSHA256']==exported['BuildPlanSHA256']
            and Path(value['QueryBody']).read_text(encoding='ascii')==body,
            'fisheye final native query body/source differs')
        log=(Path(path).parent/'stdout.log').read_text(encoding='gb18030',errors='strict');logs.append(log)
        for name in value['Artifacts']:
            if not name.endswith('.rtr') or name.endswith('_exception.rtr') or 'report_path_timing/' not in name:continue
            report=Path(path).parent/name
            with report.open(encoding='gb18030',errors='strict') as stream:header=''.join(next(stream,'') for _ in range(18))
            require(re.search(r'^\| Design\s*:\s*'+build.TARGET+r'\s*$',header,re.M),
                    'direct interstage report identifies another design')
            commands=[line for line in body.splitlines() if line.startswith('report_path_timing ')]
            timing.validate_report_filter(name,header,commands)
            for lines,line_number in timing.native.blocks(report):
                text=''.join(lines)
                one=lambda pattern:timing.field(pattern,text,'direct ordinary interstage identity')
                source=one(r'^Startpoint\s*:\s*(\S+)\s*$');endpoint=one(r'^Endpoint\s*:\s*(\S+)\s*$')
                launch=timing.launch_row(text)['LaunchOutput'];key=source,launch,endpoint
                require(key in lookup,'unexpected actual source Q/interstage endpoint')
                kind,corner=one(r'^Path Type\s*:\s*(max|min) \((slow|fast) corner\)\s*$')
                state,slack=one(r'^ Slack \((MET|VIOLATED)\)\s+('+timing.NUM+r')\s*$')
                clocks=re.findall(r'^ Clock (\S+) \((rising|falling) edge\)',text,re.M)
                require(len(clocks)==2 and all(c[0]==lookup[key]['Clock'] for c in clocks)
                    and state=='MET' and float(slack)>=0 and not re.search(r'^Timing Exception\s*:',text,re.M),
                    'direct synchronizer interstage is waived/violated or uses another clock')
                found.add((*key,corner,kind));records.append({'Source':source,'LaunchQ':launch,'Endpoint':endpoint,
                    'Corner':corner,'Kind':kind,'SlackNS':float(slack),'Report':str(report),'Line':line_number})
    required={(*key,c,k) for key in lookup for c in ('slow','fast') for k in ('max','min')}
    require(found==required,'fisheye native interstage corner/setup/hold coverage missing')
    pins=copy.deepcopy(current['Pins']);sites.apply_native_sites(pins,'\n'.join(logs))
    params=electrical.io_parameters(scope['RouteDump']['Path'],pins)
    require(params['Passed'] and params['Ports']==scope['Pins']['Declared'],'native direct electrical parameter coverage incomplete')
    routed,inputs=native.bind_receipt(route_path);merge(watched,inputs);receipts.append((Path(route_path),routed))
    app,inputs=physical.bind_application(application_path);merge(watched,inputs)
    receipts.append((Path(application_path),app))
    prior=[app[key]for key in('ExportReceipt','RouteReceipt')]+app.get('PreflightQueries',[app['PreflightQuery']])
    for record in prior:
        path=Path(record['Path']);value,inputs=baseline.bind_receipt(path);merge(watched,inputs)
        receipts.append((path,value))
    warnings=warning_review(scope,receipts,watched)
    return {'Passed':True,'NativeWarningsReviewed':warnings['Passed'],'NativeWarningReview':warnings,
        'ResetAccepted':acceptance['ResetAccepted'],'InterstageTimingAccepted':True,
        'Pins':{'DeclaredTopPorts':scope['Pins']['Declared'],'NativeRoutedPorts':scope['Pins']['Routed'],
            'NativeActivePorts':scope['Pins'].get('Active',scope['Pins']['Routed']),'UnusedPads':scope['Pins'].get('UnusedPads',[])
            ,'UnusedPadDispositionsAccepted':scope['Pins'].get('UnusedPadDispositionsAccepted',scope['Pins'].get('UnusedPads',[])==[]),
            'Dispositions':scope['Pins'].get('Dispositions',[]),
            'NativeElectricalParametersVerified':True,'NativeElectricalParameters':params,
            'ExplicitNativeUNUSEDPorts':[r['Port'] for r in pins['PinInventory'] if r.get('UNUSED')=='TRUE'],
            'PinInventory':pins['PinInventory']},
        'DataCDC':{'DataScopes':scope['DataScopes'],'Missing':[],'Violations':[],'InterstageTimingAccepted':True,
            'InterstageQueries':current['InterstageQueries'],'InterstageRecords':records,'PackedSameBLE':current['PackedInterstage'],
            'OrdinaryCaseCount':len(required),'AnalogMTBFAccepted':False},
        'SourceSampling':scope['SourceSampling']},watched


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--audit',type=Path,required=True)
    p.add_argument('--output-dir',type=Path,required=True);a=p.parse_args();scope,_=physical.bind_audit(a.audit)
    current,_=inventory(scope);bodies=query_bodies(current);a.output_dir.mkdir(exist_ok=False)
    for i,body in enumerate(bodies):(a.output_dir/f'checks-{i:02}.tcl').write_text(body,encoding='ascii',newline='\n')
    print(json.dumps({'Bodies':len(bodies),'Sites':len(current['Pins']['PinInventory']),
        'InterstageQueries':len(current['InterstageQueries'])}));return 0


if __name__=='__main__':raise SystemExit(main())
