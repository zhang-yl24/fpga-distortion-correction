"""Derive this raw diagnostic's own pins, CDC cones and exact native scopes.

This is CPU preparation, not a timing waiver or hardware release. Crossing
sources include every relevant FF in each data/enable cone; the raw ACK guard
therefore retains both source reset and acknowledgement launch paths.
"""
import argparse
from collections import Counter,defaultdict
import json
from pathlib import Path
import re
import sys
import tempfile

import hdmi_camera_raw_build as build
import hdmi_camera_raw_native as native
import camera720_stats_io_cdc as algorithms
import camera720_stats_native_mux as mux
import audit_ddr_final_timing as timing
import camera720_calibrated_inspect as grammar

SELF=Path(__file__).resolve();TARGET=build.TARGET
require,sha,read,write=build.require,build.sha,build.read,build.write
cdc=algorithms.cdc
canon=cdc.endpoints.canon
parent=cdc.endpoints.base.native_parent
PERIODS={'board27':37.037037,'input_pixel':6.6667,'pixel_clk':13.468013,'cfg_clk':100.0}


class Graph(mux.Graph):
    def clock(self,net,visited=()):
        if net=='pixclk_in':return {'Domain':'input_pixel','Root':net,'Trace':[]}
        if net not in self.clock_cache and net not in ('clk_27m',):
            ds=self.outputs.get(net,[])
            if len(ds)==1:
                name,pin=ds[0]
                if self.cells[name]['Primitive']=='V_GPLL' and pin=='CLKOUT0' and name.startswith('configuration_pll/'):
                    result={'Domain':'cfg_clk','Root':name+'/'+pin,'Trace':[{'Cell':name,'Pin':pin,'Primitive':'V_GPLL','Net':net}]}
                    self.clock_cache[net]=result;return result
        return super().clock(net,visited)


def graph(text):
    require(re.findall(r'(?m)^module\s+(\w+)',text)==[TARGET],'one current raw functional module required')
    adapted=re.sub(r'(?m)^(module\s+)'+TARGET+r'\b',r'\g<1>'+algorithms.structure.prep.TARGET,text,count=1)
    return Graph(algorithms.structure.functional(adapted))


def support(g,net,cache,active=()):
    if net in cache:return cache[net]
    require(net not in active,'Boolean cone cycle')
    if net in ("1'b0","1'b1"):return set()
    ds=g.outputs.get(net,[])
    if not ds:return {('primary',canon(net))}
    require(len(ds)==1,'ambiguous raw diagnostic Boolean driver')
    name,pin=ds[0];cell=g.cells[name];kind=cell['Primitive']
    if name in g.ff:result={('ff',name)}
    elif kind=='V_GPLL' and pin=='LOCK':result={('pll_lock',name)}
    elif kind in ('V_IBUF','V_INBUFG') and pin=='O':result=support(g,cell['Ports']['I'],cache,active+(net,))
    else:
        require(kind in ('V_MUX2','V_LUT6CARRY','V_BUF','V_INV'),'unreviewed raw Boolean cone primitive '+kind)
        result=set()
        for source in mux.inputs(cell,pin):result|=support(g,source,cache,active+(net,))
    cache[net]=result;return result


def source_sync_families(build_dir):
    result=[]
    for source,hierarchy in ((build.TOP,''),(build.UART,'telemetry/'),(build.RAW,'raw_activity/')):
        text=(build_dir/'frozen-inputs'/source).read_text(encoding='utf-8')
        for attrs,hi,lo,names in re.findall(r'\(\*(.*?)\*\)\s*reg\s*\[(\d+):(\d+)\]\s*([^;]+);',text,re.S):
            if not ('async_reg' in attrs or 'syn_preserve' in attrs) or (hi,lo)!=('1','0'):continue
            for item in names.split(','):
                name=item.split('=',1)[0].strip()
                require(re.fullmatch(r'[A-Za-z_]\w*',name),'ambiguous source synchronizer family')
                result.append(hierarchy+name)
    require(result and len(result)==len(set(result)),'empty or duplicate current synchronizer family')
    return result


def synchronizers(g,families):
    rows=[];missing=[]
    for family in families:
        candidates=[n for n,c in g.ff.items() if canon(c['Ports']['Q'])==family+'[0]']
        second=[n for n,c in g.ff.items() if canon(c['Ports']['Q'])==family+'[1]']
        if not candidates:
            if len(second)==1:
                upstream=[n for kind,n in support(g,g.ff[second[0]]['Ports']['D'],{}) if kind=='ff'
                    and n.startswith((family+'[0]/',family+'[1]/')) and n!=second[0]]
                candidates=upstream
            else:candidates=[n for n in g.ff if n.startswith(family+'[0]/') and '/FFAPP' not in n]
        if len(candidates)!=1:missing.append({'Family':family,'FirstCandidates':candidates});continue
        first=candidates[0]
        if not second:
            second=[n for n,c in g.ff.items() if n!=first and ('ff',first) in support(g,c['Ports']['D'],{})]
        if len(second)!=1:missing.append({'Family':family,'SecondCandidates':second});continue
        release=None
        prefix=family.rsplit('/',1)[0]+'/' if '/' in family else ''
        reset_family='p_reset' if g.clock(g.ff[first]['Ports']['CK'])['Domain']=='input_pixel' else (
            'cfg_reset' if prefix=='telemetry/' and g.clock(g.ff[first]['Ports']['CK'])['Domain']=='cfg_clk' else
            'r_reset' if prefix=='raw_activity/' else 'ref_reset')
        releases=[c['Ports']['Q'] for c in g.ff.values() if canon(c['Ports']['Q'])==prefix+reset_family+'[1]']
        if len(releases)==1:release=releases[0]
        rows.append({'Family':family,**g.chain(first,second[0],family+' first-to-second',release)})
    require(not missing,'current synchronizer source/native mapping incomplete: '+str(missing))
    return rows


def crossing_role(source,destination,pin):
    if pin!='D':return None
    for hierarchy,held,captured in (('raw_activity/','held_snapshot','snapshot'),('telemetry/','cfg_held','cfg_snapshot')):
        for family in ('request_sync','ack_sync'):
            if destination.startswith(hierarchy+family+'[0]/'):
                allowed=('snapshot_request',) if family=='request_sync' else ('snapshot_ack',)
                if hierarchy=='raw_activity/' and family=='ack_sync':allowed+=('p_reset[1]',)
                if any(source.startswith(hierarchy+n+'/') for n in allowed):return hierarchy+family+' first stage'
        source_bit=re.match(r'^'+re.escape(hierarchy+held)+r'\[(\d+)\]/',source)
        destination_bit=re.match(r'^'+re.escape(hierarchy+captured)+r'\[(\d+)\]/',destination)
        if source_bit and destination_bit and source_bit.group(1)==destination_bit.group(1):
            return hierarchy+'held snapshot to first consumer; same bit and native graph support checked'
    if source.startswith('hdmi_configuration/') and any(destination.startswith(name+'[0]/') for name in
           ('rx_done_ref','tx_done_ref','cfg_failed_ref')):
        return 'top configuration status first stage'
    return None


def crossing_inventory(g,chains=()):
    cache={};rows=[];violations=[]
    identities={row[key]:row['Family']+'['+str(index)+']/' for row in chains
                for index,key in enumerate(('First','Second'))}
    def identity(name):
        if name in identities:return identities[name]
        logical=canon(g.ff[name]['Ports']['Q'])
        # raw_activity.snapshot is connected directly to the top-level
        # raw_snapshot wire, whose name survives the functional flattening.
        raw_output=re.fullmatch(r'raw_snapshot\[(\d+)\]',logical)
        if raw_output and re.match(r'^raw_activity/snapshot\[\d+\]/',name):
            logical='raw_activity/snapshot['+raw_output[1]+']'
        return logical+'/'
    for destination,cell in sorted(g.ff.items()):
        dc=g.clock(cell['Ports']['CK'])['Domain']
        for pin in ('D','CE'):
            if pin not in cell['Ports']:continue
            for kind,source in sorted(support(g,cell['Ports'][pin],cache)):
                if kind!='ff':continue
                sc=g.clock(g.ff[source]['Ports']['CK'])['Domain']
                if sc==dc:continue
                # Packed FFAPP registers can borrow another bit's physical
                # instance name. Classify their actual functional Q nets;
                # synchronizer stages additionally need the proved chain
                # identities because packing may replace their logical Q.
                source_role=identity(source)
                destination_role=identity(destination)
                role=crossing_role(source_role,destination_role,pin)
                item={'SourceFF':source,'DestinationFF':destination,'DestinationPin':pin,
                    'SourceClock':sc,'DestinationClock':dc,'Labels':[role] if role else [],
                    'Purposes':['intentional current diagnostic protocol'] if role else [],'OriginalEndpoints':[],
                    'SourceRole':source_role,'DestinationRole':destination_role}
                (rows if role else violations).append(item)
    require(rows,'no current raw CDC relationships derived')
    return rows,violations


def local_helpers():
    """All actually loaded project tool implementations, including from-imports."""
    paths=set()
    for module in list(sys.modules.values()):
        file=getattr(module,'__file__',None)
        if file:
            path=Path(file).resolve()
            if path.is_file() and path.is_relative_to(build.ROOT/'tools'):paths.add(path)
    return sorted(paths)


def pin_inventory(build_dir,export_text,g,plan):
    parser=algorithms.io.pin_parser
    source=(build_dir/'frozen-inputs'/build.TOP).read_text(encoding='utf-8')
    source=re.sub(r'module\s+'+TARGET+r'\s*#\(.*?\)\s*\(','module board1080_top(',source,count=1,flags=re.S)
    declared=parser.top_ports(source)
    fdc=parser.fdc_pins((build_dir/build.FDC).read_text())
    pcf=parser.pcf_pins((build_dir/'device_map'/(TARGET+'.pcf')).read_text())
    _,routed=parser.routed_pads((build_dir/'place_route'/(TARGET+'_prr_route_optimize.prt')).read_text())
    require(set(declared)==set(fdc)==set(pcf)==set(routed)==set(plan['Pins']),'complete actual current pad inventories differ')
    connections=defaultdict(list)
    for name,c in g.cells.items():
        for pin,value in c['Ports'].items():
            if value in declared:
                connections[value].append({'Cell':name,'Primitive':c['Primitive'],'Pin':pin,
                    'NativeInstance':name.rsplit('/',1)[0],'FunctionalParameters':c['Parameters']})
    require(set(connections)==set(declared),'functional raw export disconnects a declared pad')
    rows=[]
    for port,direction in sorted(declared.items()):
        require(fdc[port]['DIRECTION']==direction==routed[port]['Direction']
            and fdc[port]['LOC']==plan['Pins'][port]==routed[port]['Pad']
            and pcf[port]=={k:v for k,v in fdc[port].items() if k!='DIRECTION'},'current pad direction/location/electrical mismatch: '+port)
        rows.append({'Port':port,**fdc[port],'Site':routed[port]['Site'],'Bank':routed[port]['Bank'],
            'FinalPrimitiveConnections':connections[port]})
    return {'TopPortCount':len(declared),'PinInventory':rows,'DeclarationPCFAndRouteMatched':True,
        'FunctionalAllPadsConnected':True,'NativeElectricalParametersVerified':False}


def derive(build_plan,export_receipt,route_receipt):
    build_plan=Path(build_plan).resolve();build_dir=build_plan.parent
    plan=build.validate(build_plan);watched={}
    exported,inputs=native.bind_receipt(export_receipt);native.merge(watched,inputs)
    routed,inputs=native.bind_receipt(route_receipt);native.merge(watched,inputs)
    require(exported['Mode']=='export' and routed['Mode'] in ('report','query')
        and all(exported[k]==routed[k] for k in ('BuildPlanSHA256','SourceADFSHA256','SourceADF'))
        and exported['BuildPlanSHA256']==sha(build_plan),'native raw export/route lineage differs')
    net=Path(export_receipt).parent/'generate_netlist'/(TARGET+'_sim.v')
    dump=Path(route_receipt).parent/'route-dump.txt'
    native.add(watched,net);native.add(watched,dump)
    text=net.read_text(encoding='utf-8-sig');g=graph(text)
    pins=pin_inventory(build_dir,text,g,plan)
    sync=synchronizers(g,source_sync_families(build_dir))
    rows,violations=crossing_inventory(g,sync)
    require(not violations,'unreviewed current foreign-domain data/enable cones: '+str(violations[:8]))
    placements=cdc.clm.placed_luts(text,g)
    parents={parent(n) for row in rows for n in (row['SourceFF'],row['DestinationFF'])}
    parents.update(n.rsplit('/',2)[0] for n in placements)
    with tempfile.TemporaryDirectory(prefix='hdmi-raw-route-') as temporary:
        normalized=Path(temporary)/'route.adif'
        normalization=cdc.normalize_source_locations(dump,normalized)
        route=cdc.endpoints.route_objects(normalized,parents)
    mapper=cdc.clm.Mapper(g,route,placements)
    mapped=[mapper.map(row) for row in rows]
    groups=defaultdict(set)
    for row in mapped:
        for boundary in row['NativeBoundaries']:groups[row['SourceClock'],row['DestinationClock']].add(boundary['Endpoint'])
    scopes=[];commands=[];queries=[]
    for (sc,dc),targets in sorted(groups.items()):
        require(sc in PERIODS and dc in PERIODS and sc!=dc,'unreviewed raw clock-domain pair')
        pattern='^('+'|'.join(re.escape(p) for p in sorted(targets))+')$'
        query='get_pins -hierarchical -regexp {'+pattern+'}'
        budget=PERIODS[dc]
        scopes.append({'SourceClock':sc,'DestinationClock':dc,'Targets':sorted(targets),
            'MaximumNS':budget,'BoundBasis':'At most one destination-clock period; handshake holds data through synchronized ACK plus an extra settling cycle.',
            'Query':query})
        queries+=['puts {RAW_SCOPE_'+sc+'_TO_'+dc+'}',query]
        commands+=['set_max_delay -datapath_only -from [get_clocks {'+sc+'}] -to ['+query+'] '+str(budget),
                   'set_false_path -hold -from [get_clocks {'+sc+'}] -to ['+query+']']
    native.query_commands('\n'.join(queries)+'\n')
    report=Path(export_receipt).parent/'report_timing'/(TARGET+'.rtr')
    with report.open(encoding='utf-8-sig') as stream:tables,clocks=timing.parse_summaries(stream)
    summary={corner+'_'+kind:{'FailingChecks':sum(r['FailingChecks'] for r in data.values()),
        'WorstSlackNS':min(r['WorstSlackNS'] for r in data.values())} for (corner,kind),data in tables.items()}
    for helper in local_helpers():native.add(watched,helper)
    native.add(watched,SELF)
    result={'Schema':'hdmi-camera-raw-unapplied-physical-scope-v1','Target':TARGET,
        'BuildPlan':native.ref(build_plan),'ExportReceipt':native.ref(export_receipt),'RouteReceipt':native.ref(route_receipt),
        'SourceADF':native.ref(exported['SourceADF']),'NativeNetlist':native.ref(net),'RouteDump':native.ref(dump),
        'Pins':pins,'ActualCells':len(g.cells),'ActualFFs':len(g.ff),'Synchronizers':sync,
        'ForeignDataEnableRelationships':mapped,'ForeignDataEnableViolations':violations,
        'NativeRouteNormalization':normalization,'DataScopes':scopes,'UnappliedDataCommands':commands,
        'TimingSummary':summary,'NativeClocks':clocks,'ResetScopeVerified':False,'NativeNamesQueried':False,
        'ConstraintsApplied':False,'HardwareAccessed':False,'BitstreamRequested':False,'HardwareReleaseAllowed':False,
        'InputSHA256':{str(p):h for p,h in watched.items()},
        'Limits':'CPU proposal only. Exact native names, reset selectors, all interstage timing/current full STA and unchanged graph/placement/routing after any exception remain required. No old counts or PHY/video acceptance.'}
    return result,'\n'.join(queries)+'\n','\n'.join(commands)+'\n'


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--build-plan',type=Path,required=True)
    p.add_argument('--export-receipt',type=Path,required=True);p.add_argument('--route-receipt',type=Path,required=True)
    p.add_argument('--output-dir',type=Path,required=True);a=p.parse_args();out=build.work_path(a.output_dir)
    require(not out.exists(),'fresh physical scope output required')
    value,query,fdc=derive(a.build_plan,a.export_receipt,a.route_receipt);out.mkdir()
    (out/'query.tcl').write_text(query,encoding='ascii',newline='\n')
    (out/'UNAPPLIED-data-scope.fdc').write_text(fdc,encoding='ascii',newline='\n');write(out/'scope.json',value)
    print(json.dumps({'PreparedOnly':True,'Pins':value['Pins']['TopPortCount'],'ActualFFs':value['ActualFFs'],
        'SynchronizerPairs':len(value['Synchronizers']),'Crossings':len(value['ForeignDataEnableRelationships']),
        'Scopes':[{k:s[k] for k in ('SourceClock','DestinationClock','MaximumNS')} for s in value['DataScopes']]}))


if __name__=='__main__':main()
