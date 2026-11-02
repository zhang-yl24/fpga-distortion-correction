"""Independent direct IO/interstage/check coverage from the applied native ADF.

Only current direct graph objects generate queries. Packed BLE arcs use exact
vendor-model structural proof plus all-ten-table STA. Ordinary interstage arcs
retain both setup/hold corners. No analog/external AC acceptance is inferred.
"""
import argparse
from collections import Counter
import copy
import json
from pathlib import Path
import re

import hdmi_camera_direct_build as build
import hdmi_camera_direct_native as baseline
import hdmi_camera_direct_physical as physical
import hdmi_camera_direct_native as native
import hdmi_camera_direct_audit as audit
import camera720_io_evidence as electrical
import audit_camera_vga_io as sites
import camera720_cdc_native as timing

SELF=Path(__file__).resolve()
require,sha,read,write=build.require,build.sha,build.read,build.write
add,merge,ref=baseline.add,baseline.merge,baseline.ref


def inventory(scope):
    graph,route,mapper,watched=audit.native_graph(scope)
    pins=[]
    for row in scope['Pins']['Inventory']:
        require(row['Route'] is not None and row['FunctionalConnections'],'retained direct pin lacks native site/connections')
        require(row['Attributes'].get('UNUSED')!='TRUE','direct consumer pin is marked UNUSED')
        connections=[]
        for c in row['FunctionalConnections']:
            require(c['Primitive'] in ('V_IBUF','V_OBUFT'),
                    'primary pad connection is not a reviewed IO primitive')
            connections.append({**c,'NativeInstance':c['Cell'].rsplit('/',1)[0]})
        pins.append({'Port':row['Port'],'Site':row['Route']['Site'],**row['Attributes'],
            'FinalPrimitiveConnections':connections,'SourceDisposition':'routed_with_actual_native_consumer'})
    require(scope['Pins']['Declared']==scope['Pins']['Routed']==len(pins),
            'direct declared/routed pins must all have native consumers')
    mapped=[];packed=[];chains=[]
    chain_rows=list(scope['Synchronizers'])+list(scope['ReleaseChains'])+[scope['LocalResetGuards']['KeyReleaseChain']]
    seen_chains=set()
    for chain in chain_rows:
        # Discover permitted local gating by exact support, then verify the
        # inherited exhaustive LUT truth-table/fanout chain algorithm.
        first,second=chain['First'],chain['Second'];release=None
        if (first,second) in seen_chains:continue
        seen_chains.add((first,second))
        if graph.ff[second]['Ports']['D']!=graph.ff[first]['Ports']['Q']:
            others={token[3:] for token in graph.support(graph.ff[second]['Ports']['D'])
                if token.startswith('ff:') and token!='ff:'+first}
            require(len(others)==1,'interstage gating has no unique local release FF')
            release=graph.ff[next(iter(others))]['Ports']['Q']
        label=chain.get('Family',chain.get('FirstLogical',first))
        actual=graph.chain(first,second,label,release)
        chains.append(actual)
        if actual['SameBLE']:
            require(actual['SameSite'] and not actual['NativeQueries'],'unqueryable interstage is not exact same BLE')
            packed.append(actual);continue
        row={'SourceFF':first,'DestinationFF':second,'DestinationPin':'D',
            'SourceClock':actual['DestinationClock'],'DestinationClock':actual['DestinationClock'],
            'Labels':[label],'Purposes':['ordinary synchronizer interstage'],
            'OriginalEndpoints':[q['Endpoint'] for q in actual['NativeQueries']]}
        mapped.append(mapper.map(row))
    queries=[]
    for row in mapped:
        source=row['SourceFF'];m=re.search(r'/(FFAPP|FF)([0-3])/FF$',source)
        require(m is not None,'unknown direct synchronizer physical FF slot')
        physical_q=row['SourcePlacement']['Site']+('/CR' if m[1]=='FFAPP' else '/Q')+m[2]
        parent=row['SourceNativeClockPin'].rsplit('/',1)[0]
        for boundary in row['NativeBoundaries']:
            queries.append({'FromCLK':row['SourceNativeClockPin'],'LaunchQ':row['SourceNativeOutputPin'],
                'Endpoint':boundary['Endpoint'],'Clock':row['DestinationClock'],
                'NativeObjects':{'SourcePhysicalQ':[physical_q],'SourceCLKNet':[route['Pins'][parent,'CLK']]}})
    physical.static_helpers(watched,SELF)
    return {'Pins':{'PinInventory':pins},'InterstageQueries':queries,'PackedInterstage':packed,'Chains':chains},watched


def query_bodies(current):
    commands=['show -dev_instance {'+site+'}' for site in sorted({r['Site'] for r in current['Pins']['PinInventory']})]
    for q in current['InterstageQueries']:
        commands.extend([physical.exact_selector(sorted({q['FromCLK'],q['LaunchQ'],q['Endpoint']}))['Command'],
            'report_path_timing -delay_type min_max -max_path 10000 -nworst 8 -report_exception TRUE -from {t:'+q['FromCLK']+
            '} -through {t:'+q['LaunchQ']+'} -to {t:'+q['Endpoint']+'}'])
    # Keep site enumeration in one query to preserve apply_native_sites' exact
    # inventory check. Split later timing queries only at whole command pairs.
    bodies=[];body=[]
    for command in commands:
        if len(body)>=220 and command.startswith('get_pins'):
            bodies.append('\n'.join(body)+'\n');body=[]
        body.append(command)
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
                require(accepted,'unknown direct native warning: '+line)
                rows.append({'Code':'MissingStandaloneRouteCompanion','Log':str(log),'Line':number,'Text':line})
    return {'Passed':True,'Warnings':rows,'Counts':dict(Counter(r['Code'] for r in rows)),'ExternalACAccepted':False}


def derive(scope,application_path,export_path,route_path,query_paths):
    # Import here to avoid an import cycle with the final provider.
    import hdmi_camera_direct_final as final
    acceptance=final.native_acceptance(scope);current,watched=inventory(scope)
    expected_bodies=query_bodies(current);require(len(query_paths)==len(expected_bodies),'complete direct IO/interstage query receipts required')
    exported,inputs=native.bind_receipt(export_path);merge(watched,inputs)
    receipts=[(Path(export_path),exported)];logs=[];records=[];found=set()
    lookup={(q['FromCLK'],q['LaunchQ'],q['Endpoint']):q for q in current['InterstageQueries']}
    require(len(lookup)==len(current['InterstageQueries']),'duplicate direct interstage query identity')
    for path,body in zip(query_paths,expected_bodies):
        value,inputs=native.bind_receipt(path);merge(watched,inputs);receipts.append((Path(path),value))
        require(value['Mode']=='query' and value['SourceProof']==ref(application_path)
            and value['SourceADF']==exported['SourceADF'] and Path(value['QueryBody']).read_text(encoding='ascii')==body,
            'direct final native query body/source differs')
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
    require(found==required,'direct native interstage corner/setup/hold coverage missing')
    pins=copy.deepcopy(current['Pins']);sites.apply_native_sites(pins,'\n'.join(logs))
    params=electrical.io_parameters(scope['RouteDump']['Path'],pins)
    require(params['Passed'] and params['Ports']==scope['Pins']['Declared'],'native direct electrical parameter coverage incomplete')
    routed,inputs=native.bind_receipt(route_path);merge(watched,inputs);receipts.append((Path(route_path),routed))
    app,inputs=physical.bind_application(application_path);merge(watched,inputs)
    receipts.append((Path(application_path),app))
    for key in ('ExportReceipt','RouteReceipt','PreflightQuery'):
        path=Path(app[key]['Path']);value,inputs=baseline.bind_receipt(path);merge(watched,inputs)
        receipts.append((path,value))
    warnings=warning_review(scope,receipts,watched)
    return {'Passed':True,'NativeWarningsReviewed':warnings['Passed'],'NativeWarningReview':warnings,
        'ResetAccepted':acceptance['ResetAccepted'],'InterstageTimingAccepted':True,
        'Pins':{'DeclaredTopPorts':scope['Pins']['Declared'],'NativeActivePorts':scope['Pins']['Routed'],'UnusedPads':[],
            'NativeElectricalParametersVerified':True,'NativeElectricalParameters':params,
            'ExplicitNativeUNUSEDPorts':[r['Port'] for r in pins['PinInventory'] if r.get('UNUSED')=='TRUE'],
            'PinInventory':pins['PinInventory']},
        'CDC':{'DataScopes':scope['DataScopes'],'Missing':[],'Violations':[],'InterstageTimingAccepted':True,
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
