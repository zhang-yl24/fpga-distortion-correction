"""Current calibrated720 CDC inventory and missing queries; CPU only.

This diagnostic adapter binds a current placed export and native route receipt.
It reuses pure logical/physical mappers, never historical paths or timing results.
It neither executes EDA nor grants timing, optical, or hardware acceptance.
"""
import argparse
from collections import Counter,defaultdict
import hashlib
import json
from pathlib import Path
import re
import tempfile

import camera720_calibrated_inspect as inspect
import camera720_calibrated_io_adapter as io
import camera720_native_endpoints as endpoints
import camera720_cdc_clm as clm
import camera720_cdc_sameble as sameble
import camera720_cdc_native as timing

TARGET=io.TARGET
SCHEMA='camera720-calibrated-cdc-diagnostic-inventory-v1'
SELF=Path(__file__).resolve()
require,sha=inspect.require,inspect.sha
SAFE=re.compile(r'[A-Za-z0-9_./\[\]-]+')


def ref(path):return {'Path':str(Path(path).resolve()),'SHA256':sha(path)}


def add(watched,path,expected=None):
    path=Path(path).absolute()
    require(path==path.resolve() and path.is_file(),'canonical existing CDC input required')
    actual=sha(path)
    require(expected is None or expected==actual,'CDC input digest differs: '+str(path))
    require(path not in watched or watched[path]==actual,'CDC input changed while binding')
    watched[path]=actual
    return path


def normalize_source_locations(source,destination):
    """Remove only whole-line numeric source coordinates, not connectivity.

    The frozen native interface reader predates FILEID/LINENUM inside NET.
    Existing full-route auditors classify these as source metadata. Preserve
    their ordered byte digest/count; every other source byte is copied exactly.
    """
    counts=Counter();digest=hashlib.sha256()
    with Path(source).open('rb') as inp,Path(destination).open('xb') as out:
        for line in inp:
            match=re.fullmatch(rb'\s*\((FILEID|LINENUM)\s+([0-9]+)\s*\)\s*',line)
            if match:
                counts[match[1].decode('ascii')]+=1;digest.update(line)
            else:
                require(not re.match(rb'\s*\((FILEID|LINENUM)\b',line),'malformed source-location annotation')
                out.write(line)
    return {'SourceSHA256':sha(source),'NormalizedSHA256':sha(destination),
            'RemovedSourceMetadataCounts':dict(counts),'OrderedRemovedBytesSHA256':digest.hexdigest(),
            'AllOtherBytesCopiedExactly':True,'RemovedCategories':['FILEID numeric source-table index','LINENUM numeric source-line index']}


def route_objects(path,wanted):
    with tempfile.TemporaryDirectory(prefix='calibrated-cdc-route-',dir=inspect.prep.WORK) as tmp:
        normalized=Path(tmp)/'source-location-normalized.adif'
        provenance=normalize_source_locations(path,normalized)
        value=endpoints.route_objects(normalized,wanted)
    return value,provenance


def make_queries(mappings,constraints):
    maxima,minima=timing.constraint_pairs(constraints);queries={}
    for i,row in enumerate(mappings):
        sc,dc=row['SourceClock'],row['DestinationClock']
        for boundary in row['NativeBoundaries']:
            key=row['SourceNativeClockPin'],row['SourceNativeOutputPin'],boundary['Endpoint']
            require(all(SAFE.fullmatch(p) for p in key),'unsafe native CDC pin')
            q=queries.setdefault(key,{'Source':key[0],'LaunchOutput':key[1],'Endpoint':key[2],
                                     'LogicalRelationships':[],'Corners':['slow','fast']})
            q['LogicalRelationships'].append(i)
            if sc==dc:
                fields=dict(Clock=sc,CheckKinds=['setup','hold'],HoldAnalysisSuppressed=False,MinDelayNotAccepted=False)
            else:
                require((sc,dc) in maxima and (sc,dc) in minima,'current crossing lacks max/min constraints')
                fields=dict(SourceClock=sc,DestinationClock=dc,CheckKinds=['max-delay'],MaximumNS=maxima[sc,dc]['BoundNS'],
                    SourcePeriodNS=constraints['PeriodsNS'][sc],EffectiveMaximum=maxima[sc,dc],DeclaredMinimum=minima[sc,dc],
                    HoldAnalysisSuppressed=True,MinDelayNotAccepted=True,SuppressionReason=timing.POLICY)
            require(all(k not in q or q[k]==v for k,v in fields.items()),'merged native boundary has incompatible timing requirements')
            q.update(fields)
    require(queries,'empty current CDC query inventory')
    return [queries[k] for k in sorted(queries)]


def collect(queries,reports):
    """Current target header; otherwise exact frozen launch/timing parser."""
    lookup={timing.identity(q):q for q in queries};pairs={(q['Source'],q['Endpoint']) for q in queries}
    rows,violations,other,seen=[],[],Counter(),set()
    for report in sorted(set(Path(p).resolve() for p in reports)):
        with report.open(encoding='gb18030') as stream:head=''.join(next(stream,'') for _ in range(18))
        require('2023.2-SP3 <build 154097>' in head and re.search(r'^\| Design\s*:\s*'+TARGET+r'\s*$',head,re.M),
                'current calibrated report target/version differs')
        for lines,line in timing.native.blocks(report):
            text=''.join(lines)
            source=timing.field(r'^Startpoint\s*:\s*(.+?)\s*$',text,'source')
            endpoint=timing.field(r'^Endpoint\s*:\s*(.+?)\s*$',text,'endpoint')
            if (source,endpoint) not in pairs:continue
            try:
                key=(source,timing.launch_row(text)['LaunchOutput'],endpoint)
                if key not in lookup:other[key]+=1;continue
                value=timing.parse_record(lines,report,line,lookup[key])
            except ValueError as error:
                violations.append({'Source':source,'Endpoint':endpoint,'Report':str(report),'ReportLine':line,'Error':str(error)})
                continue
            if value['PathSHA256'] not in seen:seen.add(value['PathSHA256']);rows.append(value)
    return rows,violations,[dict(zip(timing.IDENTITY,k),ObservedVariants=n) for k,n in sorted(other.items())]


def groups(queries,missing,maximum=128):
    """One source CLK and exactly one Q per query, preserving all missing cases."""
    require(type(maximum) is int and 1<=maximum<=128,'endpoint bound must be 1..128')
    known={timing.identity(q):q for q in queries}
    require(len(known)==len(queries),'duplicate native query identity')
    needed={timing.identity(r) for r in missing}
    require(needed<=set(known),'missing case not in current inventory')
    buckets=defaultdict(list)
    for key in sorted(needed):
        q=known[key];buckets[(timing.domain(q),q['Source'],q['LaunchOutput'])].append(q)
    result=[]
    for (domain,source,output),rows in sorted(buckets.items()):
        for offset in range(0,len(rows),maximum):
            subset=rows[offset:offset+maximum];ends=sorted({q['Endpoint'] for q in subset});pins=sorted({source,output,*ends})
            require(all(SAFE.fullmatch(p) for p in pins),'unsafe current query selector')
            pattern='^('+'|'.join(re.escape(p) for p in pins)+')$'
            result.append({'Domain':list(domain),'Source':source,'LaunchOutput':output,'Endpoints':ends,'Pins':pins,
                'ExpectedIdentities':[{k:q[k] for k in timing.IDENTITY} for q in subset],
                'PinCommand':'get_pins -hierarchical -regexp {'+pattern+'}',
                'Command':'report_path_timing -delay_type min_max -max_path 1000 -nworst 8 -report_exception TRUE -from {'+source+'} -through {'+output+'} -to {'+' '.join(ends)+'}'})
    actual=[timing.identity(q) for g in result for q in g['ExpectedIdentities']]
    require(len(actual)==len(set(actual)) and set(actual)==needed,'missing native identities lost or duplicated')
    return result


def bodies(items,per_body=4):
    require(type(per_body) is int and 1<=per_body<=8,'at most eight timing commands per context')
    result={}
    for offset in range(0,len(items),per_body):
        text='# Current calibrated720 diagnostic queries; actual coverage required.\n'+'\n'.join(
            c for g in items[offset:offset+per_body] for c in (g['PinCommand'],g['Command']))+'\n'
        inspect.query_commands(text)
        result[f'query-{offset//per_body:02}.tcl']=text
    return result


def prepare(export_path,route_path,output,per_body=4):
    watched={};refs=[];values=[]
    for path,mode in ((export_path,'export'),(route_path,'query')):
        path=Path(path).resolve();value,bound=inspect.bind_receipt(path)
        require(value['Mode']==mode and value['Target']==TARGET,'wrong current CDC receipt mode/target')
        for p,h in bound.items():add(watched,p,h)
        add(watched,path);refs.append(ref(path));values.append(value)
    export,route_receipt=values
    require(export['NativeNetlistWithFFloc'] is True,'placed current export required')
    require(export['SourceADF']==route_receipt['SourceADF'] and export['SourceADFSHA256']==route_receipt['SourceADFSHA256']
            and export['BuildPlanSHA256']==route_receipt['BuildPlanSHA256'],'CDC route and graph candidate differ')
    candidate={'Path':export['SourceADF'],'SHA256':export['SourceADFSHA256']}
    text=add(watched,export['Netlist']['Path'],export['Netlist']['SHA256']).read_text(encoding='ascii')
    graph=io.graph(text)
    logical,internal,_=endpoints.logical_relationships(graph)
    placements=clm.placed_luts(text,graph)
    wanted={endpoints.base.native_parent(row[k]) for row in logical+internal for k in ('SourceFF','DestinationFF')}
    wanted.update(n.rsplit('/',2)[0] for n in placements)
    require('route-dump.txt' in route_receipt['Artifacts'],'current route dump missing')
    dump=add(watched,Path(route_path).resolve().parent/'route-dump.txt',route_receipt['Artifacts']['route-dump.txt'])
    route,route_provenance=route_objects(dump,wanted)
    mapper=clm.Mapper(graph,route,placements)
    mappings=[mapper.map(row) for row in logical]
    supplement=sameble.derive(graph,route,{'Schema':'camera720-native-endpoints-v1','SameBLEInterstageInventory':internal,
        'LogicalRelationships':mappings,'Queries':[],'CandidateADF':candidate,'BuildPlanSHA256':export['BuildPlanSHA256']})
    mappings.extend(mapper.map(row) for row in supplement['LogicalRelationships'])
    constraints,_=endpoints.base.constraint_inventory(add(watched,Path(export['BuildPlan']).parent/'compiled/board/camera720-output-diagnostic.fdc'))
    queries=make_queries(mappings,constraints)
    report=add(watched,export['TimingReport']['Path'],export['TimingReport']['SHA256'])
    records,violations,other=collect(queries,[report])
    coverage=timing.coverage(queries,records,violations)
    items=groups(queries,coverage['MissingCases']);payloads=bodies(items,per_body)
    luts=endpoints.native_lut_bindings(graph,route,mappings)
    add(watched,timing.MANUAL,timing.MANUAL_SHA)
    for path in io.structure.local_helpers((inspect,io,endpoints,clm,sameble,timing)):add(watched,path)
    add(watched,SELF)
    require(not inspect.drift(watched),'current CDC preparation input drift')
    output=Path(output).absolute()
    require(output==output.resolve() and output.is_relative_to(inspect.prep.WORK) and not output.exists(),'fresh current CDC work directory required')
    output.mkdir()
    for name,body in payloads.items():(output/name).write_text(body,encoding='ascii',newline='\n')
    result={'Schema':SCHEMA,'Target':TARGET,'Producer':ref(SELF),'ExportReceipt':refs[0],'RouteReceipt':refs[1],
        'CandidateADF':candidate,'BuildPlan':ref(export['BuildPlan']),'Netlist':export['Netlist'],'RouteDump':ref(dump),
        'NativeInterfaceSourceLocationNormalization':route_provenance,
        'GeneratedTop':export['GeneratedTop'],'CompiledTop':export['CompiledTop'],'CompiledHeader':export['CompiledHeader'],
        'ActualCells':len(graph.cells),'ActualFFs':len(graph.ff),'LogicalRelationships':mappings,
        'OriginalLogicalRelationships':len(logical),'SameBLEInventory':internal,'SameBLESupplement':supplement,
        'NativeLUTBindings':luts,'InternalCarryLinks':mapper.carry_links,'Constraints':constraints,'Queries':queries,
        'InitialRecords':records,'Violations':violations,'OtherLaunches':other,'InitialCoverage':coverage,'Groups':items,
        'QueryBodies':{name:ref(output/name) for name in payloads},'CommandsPerBody':per_body,
        'InputSHA256':{str(p):h for p,h in watched.items()},'InputDrift':[],
        'SourceContractScope':['actual FIFO registered Gray sources and synchronizer chains',
            'actual monitor request/ack and held snapshot first-consumer graph',
            'actual application scalar chains and local reset release topology',
            'same-BLE direct links explicitly separated from routed interstages',
            'current compiled FDC domains and vendor datapath_only suppression'],
        'StructureDerivedFromCurrentCandidate':True,'TimingAccepted':False,'HardwareReleaseAllowed':False,
        'PhysicalTimingAggregationProved':False,'IndividualInternalFFArcsEnumerated':False,
        'Limits':'Diagnostic original-candidate inventory. Native details are only initial partial coverage. Repaired candidates need fresh receipts and timing; this inventory grants no whole-design or optical acceptance.'}
    inspect.diagnostic.write(output/'inventory.json',result)
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--export-receipt',type=Path,required=True);p.add_argument('--route-receipt',type=Path,required=True)
    p.add_argument('--output-dir',type=Path,required=True);p.add_argument('--commands-per-body',type=int,default=4)
    a=p.parse_args();result=prepare(a.export_receipt,a.route_receipt,a.output_dir,a.commands_per_body)
    print(json.dumps({'Output':ref(a.output_dir/'inventory.json'),'FFs':result['ActualFFs'],
        'LogicalRelationships':len(result['LogicalRelationships']),'Queries':len(result['Queries']),
        'CoveredCases':result['InitialCoverage']['CoveredCases'],'ExpectedCases':result['InitialCoverage']['ExpectedCases'],
        'Violations':len(result['Violations']),'Commands':len(result['Groups']),'Contexts':len(result['QueryBodies'])}))


if __name__=='__main__':main()
