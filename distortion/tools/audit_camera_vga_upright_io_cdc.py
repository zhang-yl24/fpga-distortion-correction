"""CPU-only upright IO/CDC structure and one-context native query preparation.

Candidate identity is always the new top and caller-bound ADF. The sole parser
adaptation is an explicitly recorded, in-memory module declaration token rename
for the old IO syntax helper. Original files/hashes and module globals stay intact.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import re

import run_camera_vga_upright_inspect as inspect
import audit_camera_vga_cdc as cdc
import audit_camera_vga_io as io

prep=inspect.prep
require,sha=prep.require,prep.sha
SELF=Path(__file__).resolve()


def functional(text):
    require('2023.2-SP3<build 154097>' in text[:300], 'native upright export version differs')
    clean=re.sub(r'/\*.*?\*/|//[^\n]*|\(\*.*?\*\)',lambda m:'\n'*m[0].count('\n'),text,flags=re.S)
    require(re.findall(r'(?m)^module\s+(\w+)',clean)==[prep.TARGET]
            and len(re.findall(r'(?m)^endmodule\b',clean))==1, 'one flat upright top module required')
    cells={}
    for m in cdc.physical.dialect.CELL.finditer(clean):
        name=m['name'].lstrip('\\')
        require(name not in cells,'duplicate upright primitive')
        cells[name]={'Primitive':m['primitive'],'Parameters':cdc.physical.dialect.bindings(m['parameters']),
                     'Ports':cdc.physical.dialect.bindings(m['ports'])}
    require(cells and len(cells)==len(re.findall(r'(?m)^[ \t]*V_\w+\b',clean)),'incomplete upright primitive parse')
    placements={}
    for m in cdc.physical.FF.finditer(text):
        name=m['name'].lstrip('\\')
        require(name in cells and name not in placements,'unmatched/duplicate upright FF placement')
        placements[name]={'Site':m['site'],'Attributes':' '.join((m['attrs'] or '').split())}
    require(placements and set(placements)=={n for n,c in cells.items() if c['Primitive'] in cdc.FF_TYPES},
            'every actual upright FF needs placement evidence')
    return {'Cells':cells,'FFPlacement':placements,'ModuleDeclarations':' '.join(cdc.physical.dialect.CELL.sub('',clean).split())}


def io_syntax(text):
    clean=io.pin_parser.clean_verilog(text)
    require(re.findall(r'\bmodule\s+(\w+)',clean)==[prep.TARGET], 'IO syntax adapter requires unique actual upright top')
    changed,count=re.subn(r'(\bmodule\s+)'+prep.TARGET+r'\b',r'\1camera_vga_output_top',text)
    require(count==1,'IO module declaration token adaptation ambiguous')
    return changed,{'OriginalTextSHA256':prep.baseline.paths.sha_bytes(text.encode()),
        'ParserTextSHA256':prep.baseline.paths.sha_bytes(changed.encode()),
        'Rewrite':'module declaration identifier only; camera_vga_upright_top -> camera_vga_output_top',
        'InMemoryOnly':True,'OriginalFileUnmodified':True}


def bind_file(watched,path,digest=None,parent=prep.PROJECT):
    p=inspect.canonical(path,parent);h=sha(p)
    require(digest is None or digest==h,'evidence hash mismatch: '+str(p))
    require(p not in watched or watched[p]==h,'conflicting evidence hash')
    watched[p]=h
    return p


def receipt(path,mode,source_sha,build_sha,watched):
    p=bind_file(watched,path,parent=prep.WORK);r=json.loads(p.read_text())
    require(r.get('Schema')==inspect.SCHEMA and r.get('Target')==prep.TARGET and r.get('Mode')==mode,
            'upright receipt identity/mode differs')
    stages=[] if mode=='query' else ['Report Timing','Generate Netlist']
    require(r.get('ExpectedActualStages')==stages and r.get('ActualEvents')==[[s,e] for s in stages for e in ('started','done')],
            'native upright inspection stage set differs')
    require(r.get('ExecutionPassed') is True and r.get('ExitCode')==0 and r.get('InputDrift')==[]
            and r.get('Diagnostics')==[] and r.get('InputADFUnchanged') is True and r.get('CompletionMarker') is True
            and r.get('TimedOut') is False and r.get('StoppedForUnexpectedStage') is False
            and r.get('HardwareAccessed') is False and r.get('BitstreamRequested') is False
            and r.get('SourceADFSHA256')==source_sha and r.get('BuildPlanSHA256')==build_sha,
            'clean same-candidate upright inspection required')
    bind_file(watched,r['SourceADF'],source_sha,prep.WORK)
    bind_file(watched,p.parent/'input.adf',source_sha,prep.WORK)
    for name,h in r['InputSHA256'].items():
        path0=Path(name)
        parent=prep.PROJECT if path0.is_relative_to(prep.PROJECT) else Path(r['Command'][0]).parent
        require(parent==prep.PROJECT or path0==Path(r['Command'][0]),'unexpected external evidence file')
        bind_file(watched,path0,h,parent)
    for name,h in r['Artifacts'].items():bind_file(watched,p.parent/name,h,p.parent)
    bind_file(watched,p.parent/'stage-plan.json',r['StagePlanSHA256'],p.parent)
    require(not inspect.drift(watched),'receipt inputs changed')
    return p,r


def artifact(stage,r,name):
    matches=[stage.parent/p for p in r['Artifacts'] if Path(p).name==name and 'report_path_timing' not in Path(p).parts]
    return cdc.one(matches,'bound artifact '+name)


def gray_coverage(gray,report,fdc):
    constraints,pairs=cdc.constraint_inventory(fdc)
    paths,stats=cdc.max_delay_paths(report,{r['NativeEndpoint'] for r in gray})
    groups=[];missing=[]
    for group in sorted({r['Group'] for r in gray}):
        bits=[r for r in gray if r['Group']==group]
        domains={(r['SourceClock'],r['DestinationClock']) for r in bits}
        require(len(domains)==1,'inconsistent Gray clock pair')
        source,dest=next(iter(domains));require((source,dest) in pairs,'Gray max-delay constraint missing')
        required={r['NativeEndpoint'] for r in bits}
        for corner in ('slow','fast'):
            records=[p for p in paths if p['Corner']==corner and p['Endpoint'] in required]
            seen=Counter(p['Endpoint'] for p in records)
            require(all(n==1 for n in seen.values()),'ambiguous Gray endpoint path')
            missing += [{'Group':group,'Corner':corner,'Endpoint':e} for e in sorted(required-set(seen))]
            for row in records:
                bit=cdc.one([b for b in bits if b['NativeEndpoint']==row['Endpoint']],'current Gray target')
                require(row['Source']==cdc.native_parent(bit['Source'])+'/CLK' and row['BoundNS']==pairs[(source,dest)]['BoundNS']
                        and 0<=row['ArrivalNS']<constraints['PeriodsNS'][source], 'Gray actual source/budget differs')
            groups.append({'Group':group,'Corner':corner,'SourceClock':source,'DestinationClock':dest,
                'CoverageComplete':set(seen)==required,'Constraint':pairs[(source,dest)],'SourcePeriodNS':constraints['PeriodsNS'][source],'Paths':records})
    return constraints,groups,missing,stats


def audit(build_plan,source,source_sha,export_receipt,report_receipt,output_dir,io_receipt=None):
    build_plan=inspect.canonical(build_plan,prep.WORK);build=build_plan.parent
    original=build/'place_route'/(prep.TARGET+'_pnr.adf')
    plan,watched=inspect.bind(build_plan,original,sha(original))
    source=bind_file(watched,source,source_sha,prep.WORK)
    er,export=receipt(export_receipt,'export',source_sha,sha(build_plan),watched)
    rr,reported=receipt(report_receipt or export_receipt,'query' if report_receipt else 'export',source_sha,sha(build_plan),watched)
    netlist=artifact(er,export,prep.TARGET+'_sim.v')
    require(export['Netlist']['SHA256']==sha(netlist) and export.get('NativeNetlistWithFFloc') is True,'actual upright export binding differs')
    text=netlist.read_text(encoding='utf-8-sig');g=cdc.Graph(functional(text))
    gray=cdc.gray_structures(g);scalar=cdc.scalar_structures(g);resets,replicas=cdc.reset_structures(g)
    fdc=bind_file(watched,build/'compiled'/plan['Constraints']['FDC'])
    require(sha(fdc)==plan['InputSHA256'][plan['Constraints']['FDC']],'compiled FDC source mismatch')
    constraints,groups,missing,stats=gray_coverage(gray,artifact(rr,reported,prep.TARGET+'_exception.rtr'),fdc)
    queries={(q['Source'],q['Endpoint']):q for row in scalar+resets+[c for r in replicas for c in r['Chains']] for q in row['NativeQueries']}
    queries=[queries[k] for k in sorted(queries)]
    gray_queries=[]
    for endpoint in sorted({r['Endpoint'] for r in missing}):
        bit=cdc.one([b for b in gray if b['NativeEndpoint']==endpoint],'missing current Gray endpoint')
        gray_queries.append({'Label':bit['Label'],'Source':cdc.native_parent(bit['Source'])+'/CLK','Endpoint':endpoint,
            'SourceClock':bit['SourceClock'],'DestinationClock':bit['DestinationClock'],'Purpose':'missing current Gray max-delay path; both corners'})
    paths={'top':prep.PROJECT/prep.TOP,'pcf':build/'device_map'/(prep.TARGET+'.pcf'),
        'prt':build/'place_route'/(prep.TARGET+'_prr_route_optimize.prt'),
        'official':prep.PROJECT/'platform/video_base/HDMI_IN_DDR3_HDMI_OUT_top.fdc',
        'cam_reference':prep.PROJECT/'board/raw_camera_capture_cam2_ref.fdc',
        'cam_pins':prep.PROJECT/'board/raw_camera_capture_cam2_ref-pins.json'}
    texts={k:bind_file(watched,p).read_text(encoding='utf-8-sig') for k,p in paths.items()}
    top_text,top_adapt=io_syntax(texts['top']);net_text,net_adapt=io_syntax(text)
    pins=io.pin_audit(top_text,fdc.read_text(),texts['pcf'],texts['prt'],net_text,texts['official'],texts['cam_reference'],json.loads(texts['cam_pins']))
    if io_receipt:
        ir,irvalue=receipt(io_receipt,'query',source_sha,sha(build_plan),watched)
        io.apply_native_sites(pins,artifact(ir,irvalue,'stdout.log').read_text(encoding='gb18030'))
    for mod in (inspect,inspect.diagnostic,prep,cdc,cdc.physical,cdc.physical.dialect,cdc.physical.hold,
                cdc.physical.native,io,io.pin_parser,io.net_parser,io.tx_parser,io.candidate):
        bind_file(watched,Path(mod.__file__).resolve())
    bind_file(watched,SELF)
    tools={str(p):h for p,h in watched.items() if p.parent==prep.PROJECT/'tools'}
    provenance={'Target':prep.TARGET,'CandidateADF':{'Path':str(source),'SHA256':source_sha},'BuildPlanSHA256':sha(build_plan),
        'ActualNetlist':{'Path':str(netlist),'SHA256':sha(netlist)},'InputSHA256':{str(p):h for p,h in watched.items()},'ToolSHA256':tools}
    result={'Schema':'camera-vga-upright-io-cdc-structure-v1',**provenance,'AuditedUTC':prep.utc(),'StructuralAuditPassed':True,
        'ActualCellCount':len(g.cells),'ActualFFCount':len(g.ff),'GrayBitSynchronizers':gray,'ScalarSynchronizers':scalar,
        'ResetReleaseStructure':{'PackedOrSingleSecondStageChains':resets,'ReplicatedSecondStageTrees':replicas},
        'ClockTopology':g.clock_cache,'ConstraintInventory':constraints,'GrayPhysicalGroups':groups,'Pins':pins,
        'SourceContract':{'FrozenSharedSourcesUnchanged':True,'TopEquivalentOutsideModuleAndInitNames':True,'FDCUnchanged':True,
            'ParserOnlyModuleTokenAdaptations':{'Top':top_adapt,'Export':net_adapt}},
        'Summary':{'GrayBits':len(gray),'ScalarChains':len(scalar),'ResetChains':len(resets),
            'ReplicatedResetSecondStages':sum(r['SecondStageCount'] for r in replicas),'InterstageQueryPairs':len(queries),
            'MissingGrayQueryPairs':len(gray_queries),'PinCount':pins['TopPortCount'],**stats},
        'Scope':{'NativeInterstageTimingComplete':False,'GrayDatapathBoundComplete':not missing,'AnalogMTBFProven':False,
            'AllCDCUniversallyProven':False,'ExternalACTimingAccepted':False,'NativeElectricalSettingsVerified':False,
            'DDRResetExceptionProof':'Separate candidate-specific review; no old endpoint names inherited.',
            'PhysicalDerivationProvenance':'Separate review if candidate differs from original routed build.'},
        'HardwareAccessed':False,'EDAExecuted':False,'TimingAccepted':False,'HardwareReleaseAllowed':False}
    query={'Schema':'camera-vga-upright-io-cdc-query-plan-v1',**provenance,'Queries':queries,'GrayCoverageQueries':gray_queries,
        'MissingGrayCases':missing,'IOSites':sorted({r['Site'] for r in pins['PinInventory']}),'OneNativeContext':True,'HardwareAccessed':False}
    body=['# One native process; inspector initializes STA once. All objects derive from this ADF export.']
    for q in queries+gray_queries:
        body.append('report_path_timing -delay_type min_max -max_path 100 -nworst 8 -report_exception TRUE -from {'+q['Source']+'} -to {'+q['Endpoint']+'}')
    body += ['show -dev_instance {'+site+'}' for site in query['IOSites']]
    body='\n'.join(body)+'\n';inspect.query_commands(body)
    require(not inspect.drift(watched),'upright IO/CDC evidence drift')
    output_dir=prep.work_path(output_dir);require(not output_dir.exists(),'fresh upright audit output directory required')
    output_dir.mkdir()
    for name,value in (('io-cdc-structure.json',result),('query-plan.json',query)):inspect.diagnostic.write(output_dir/name,value)
    (output_dir/'query-body.tcl').write_text(body,encoding='ascii',newline='\n')
    print(json.dumps({'StructuralAuditPassed':True,'OutputDirectory':str(output_dir),'ActualCellCount':len(g.cells),
                      'ActualFFCount':len(g.ff),**result['Summary']}))
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('plan','source-adf','export-receipt','output-dir'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--source-adf-sha256',required=True);p.add_argument('--report-receipt',type=Path);p.add_argument('--io-receipt',type=Path)
    a=p.parse_args();audit(a.plan,a.source_adf,a.source_adf_sha256,a.export_receipt,a.report_receipt,a.output_dir,a.io_receipt)


if __name__=='__main__':main()
