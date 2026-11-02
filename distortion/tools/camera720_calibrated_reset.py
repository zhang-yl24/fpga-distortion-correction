"""CPU proof of this calibrated candidate's exact native DDR reset scope.

Only one report Design token and one netlist module token are adapted for
existing strict pure parsers. Native names, graph edges and counts come from
the actual new export. No EDA, constraints, release or hardware action occurs.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import tempfile

import camera720_calibrated_inspect as inspect
import prepare_camera_vga_reset_scope as scope
import audit_camera_vga_reset_netlist as graph
import audit_camera720_reset as queries_parser

prep, require, sha = inspect.prep, inspect.require, inspect.sha
SELF = Path(__file__).resolve()
SCHEMA = 'camera720-calibrated-reset-proof-v1'
REFERENCE = prep.PROJECT/'results/camera-vga-reset-analysis-20261031-a/vendor-reference.json'
REFERENCE_SHA = 'ff4a7dd5b7fda35b73a80d293fe0ec837ce13c22f00cde7737b66dbb179a8af0'
VENDOR = prep.PROJECT.parent/'vendor/reference/ddr/2_9_ddr3_test/2_9_ddr3_test/ddr3_test/ipcore/ddr3_test'
MANUAL = prep.PROJECT.parent/'vendor/board/盘古100Pro+开发板（MES2L676-100HP）配套资料/6_IP_setup_packet/PG2L/DDR3/UG042003_HMIC_S_IP.pdf'
MANUAL_SHA = 'c158c326ccf0146d5f6c1eca1efde61a70669667a7eeae78bce016bfcdaffc02'
FAMILIES = {'entry_rdc','cpd_reset','dqs_reset','iol_reset','training_reset'}


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def ref(path):
    path=Path(path).resolve()
    return {'Path':str(path),'SHA256':sha(path)}


def add(watched,path,expected=None):
    path=Path(path).absolute()
    require(path==path.resolve() and path.is_file(), 'canonical existing input required')
    actual=sha(path)
    require(expected is None or expected==actual, 'input digest differs: '+str(path))
    require(path not in watched or watched[path]==actual, 'conflicting input identity')
    watched[path]=actual
    return path


def binding(value,watched):
    require(isinstance(value,dict) and set(value)=={'Path','SHA256'} and
            isinstance(value['SHA256'],str) and re.fullmatch('[0-9a-f]{64}',value['SHA256']),
            'exact Path/SHA256 input required')
    return add(watched,value['Path'],value['SHA256'])


def merge(watched,other):
    for path,digest in other.items():
        path=Path(path)
        require(path not in watched or watched[path]==digest,'conflicting closure input')
        watched[path]=digest


def inventory(report):
    count=0; digest=hashlib.sha256()
    design=re.compile(r'\| Design\s*:\s*(\S+)\s*')
    with tempfile.TemporaryDirectory(prefix='calibrated-reset-') as tmp:
        view=Path(tmp)/'report.rtr'
        with Path(report).open(encoding='utf-8-sig') as source, view.open('w',encoding='utf-8',newline='\n') as target:
            for line in source:
                match=design.fullmatch(line)
                if match:
                    require(match[1]==prep.TARGET,'report has another target')
                    count+=1
                    line=line[:match.start(1)]+'camera_vga_output_top'+line[match.end(1):]
                target.write(line);digest.update(line.encode())
        require(count==1,'exactly one current Design header required')
        paths,summaries=scope.parse_report(view)
    value=scope.audit_inventory(paths,summaries,require_complete=True)
    return value,{'OriginalTop':prep.TARGET,'ParserTop':'camera_vga_output_top',
        'HeaderReplacements':count,'TemporaryViewSHA256':digest.hexdigest(),
        'NativeNamesAndLineNumbersUnchanged':True}


def adapt_netlist(text):
    require(re.findall(r'(?m)^module\s+(\w+)\b',text)==[prep.TARGET],'exact calibrated top declaration required')
    result,count=re.subn(r'(?m)^(module\s+)'+re.escape(prep.TARGET)+r'\b',r'\1camera_vga_output_top',text)
    require(count==1,'ambiguous netlist adapter')
    return result


def exact_scope(inv):
    queries,body,fdc=scope.query_scope(inv)
    require(len(queries)==len(FAMILIES) and {q['Family'] for q in queries}==FAMILIES,
            'unexpected reset source families')
    for query in queries:
        require(query['Targets']==sorted(set(query['Targets'])),'duplicate reset targets')
        for target in query['Targets']:
            checks=[p for p in inv['Corners']['slow']['Checks'] if p['Source']==query['Source'] and p['Endpoint']==target]
            require(checks and all(scope.classify(p)==query['Family'] for p in checks),
                    'reset target is not classified by actual recovery evidence')
    commands=[line for line in fdc.splitlines() if line and not line.startswith('#')]
    require(len(commands)==len(queries) and all(c.startswith('set_false_path -from [get_pins -hierarchical -regexp {') for c in commands),
            'unexpected reset constraint syntax')
    body=body.replace('CAMERA_VGA_RESET_QUERY_','CAMERA720_CALIBRATED_RESET_QUERY_')
    inspect.query_commands(body)
    return queries,body,commands


def vendor_basis(export,watched):
    build=Path(export['BuildPlan']).parent
    manifest_path=add(watched,build/'source/manifest.json')
    manifest=read(manifest_path)
    require(manifest.get('Target')==prep.TARGET,'generated manifest target differs')
    reference=read(add(watched,REFERENCE,REFERENCE_SHA))
    prefix='platform/video_base/ipcore/ddr3_test/'
    expected={p[len(prefix):] for p in manifest['source_files'] if p.startswith(prefix)}
    rows=reference['Files']
    require(len(rows)==len(expected) and {r['RelativePath'] for r in rows}==expected,
            'generated candidate DDR ownership differs from vendor inventory')
    actual=[]
    for row in rows:
        rel=Path(row['RelativePath'])
        require(not rel.is_absolute() and '..' not in rel.parts,'vendor relative path escapes')
        original=(prep.PROJECT/prefix/rel).resolve();vendor=(VENDOR/rel).resolve();compiled=(build/'compiled'/prefix/rel).resolve()
        require(Path(row['CandidatePath']).resolve()==original and Path(row['VendorPath']).resolve()==vendor,
                'vendor reference paths differ')
        for path in (original,vendor,compiled):add(watched,path,row['SHA256'])
        actual.append({'RelativePath':rel.as_posix(),'Original':str(original),'Vendor':str(vendor),
                       'Compiled':str(compiled),'SHA256':row['SHA256']})
    fdc=reference['VendorFDC'];fdcpath=add(watched,fdc['Path'],fdc['SHA256'])
    require(fdcpath==(VENDOR/'pnr/ddr_test.fdc').resolve(),'vendor FDC path differs')
    lines=fdcpath.read_text(encoding='utf-8-sig').splitlines();relationships=[]
    for clock in ('rst_clk','phy_dq_clk_0','phy_dq_clk_1'):
        command='set_clock_groups -name '+clock+' -asynchronous -group [get_clocks {'+clock+'}]'
        matches=[i+1 for i,line in enumerate(lines) if line.strip()==command]
        require(len(matches)==1,'documented vendor relationship differs')
        relationships.append({'Line':matches[0],'Text':command})
    add(watched,MANUAL,MANUAL_SHA)
    return {'GeneratedManifest':ref(manifest_path),'ReferenceInventory':ref(REFERENCE),
        'IDFAndExpandedBodyCount':len(actual),'Files':actual,'VendorFDC':fdc,'VendorClockRelationships':relationships,
        'Manual':{'Path':str(MANUAL),'SHA256':MANUAL_SHA,'Pages':[32,47,66,69]},
        'SameConfigurationBytesVerified':True,'GlobalClockGroupsImported':False,
        'Contract':'Use the supplied HMIC_S reset/training architecture under its documented clocks/reset and init_done contract; exact current placed reset graph is checked independently.',
        'VendorEncryptedInternalsProved':False,'AnalogMTBFProven':False,
        'ExternalResetContract':'Board reset assertion is asynchronous; entry chain releases on rst_clk after PLL LOCK. External reset electrical behavior and arbitrary short stopped-clock reset epochs are not proved.'}


def audit_value(export_receipt,query_receipt):
    export_path,query_path=Path(export_receipt).resolve(),Path(query_receipt).resolve()
    export,watched=inspect.bind_receipt(export_path)
    query,inputs=inspect.bind_receipt(query_path);merge(watched,inputs)
    require(export['Mode']=='export' and query['Mode']=='query' and
            all(export[k]==query[k] for k in ('Target','BuildPlan','BuildPlanSHA256','SourceADF','SourceADFSHA256')),
            'reset evidence belongs to different candidates or modes')
    inv,adapter=inventory(export['TimingReport']['Path'])
    queries,body,commands=exact_scope(inv)
    require(Path(query['QueryBody']).read_text(encoding='ascii')==body,'executed native selector body differs')
    names=queries_parser.exact_queries(queries,query_path.parent/'stdout.log')
    structure=graph.audit_text(adapt_netlist(Path(export['Netlist']['Path']).read_text(encoding='utf-8-sig')),queries)
    require(structure['FirstStageFunctionalFanout']==1 and structure['RawClearFunction']=='~(reset_n & power_ready)',
            'current entry reset graph differs')
    require(structure['InternalFunctionalTargetsVerified']==sum(len(q['Targets']) for q in queries if not q['EntryRDC']),
            'internal graph coverage differs')
    vendor=vendor_basis(export,watched)
    for module in (scope,graph,graph.syntax,queries_parser):add(watched,module.__file__)
    add(watched,SELF)
    result={'Schema':SCHEMA,'Target':prep.TARGET,'Producer':ref(SELF),
        'BuildPlan':export['BuildPlan'],'BuildPlanSHA256':export['BuildPlanSHA256'],
        'BuildDiagnosticsReview':export['BuildDiagnosticsReview'],
        'SourceADF':{'Path':export['SourceADF'],'SHA256':export['SourceADFSHA256']},
        'ExportReceipt':ref(export_path),'QueryReceipt':ref(query_path),
        'Report':export['TimingReport'],'Netlist':export['Netlist'],'ReportAdapter':adapter,
        'Inventory':inv,'NativeQueries':queries,'NativeNameProof':names,'ResetGraph':structure,
        'ExactResetCommands':commands,'VendorBasis':vendor,
        'UniqueSourceEndpointPairs':sum(len(q['Targets']) for q in queries),
        'NativeQueriesVerified':True,'ResetConnectivityVerified':True,'VendorSameConfigurationVerified':True,
        'LogicalChecksByCorner':{c:r['LogicalChecks'] for c,r in inv['Corners'].items()},
        'NativeVariantsByCorner':{c:r['NativeVariants'] for c,r in inv['Corners'].items()},
        'Complete':True,'OriginalBuildDiagnosticsCleared':False,
        'TimingExceptionApproved':False,'ConstraintsApplied':False,'HardwareReleaseAllowed':False,
        'HardwareAccessed':False,'EDAExecuted':False,'HistoricalEndpointInventoryUsed':False,
        'Limits':'Exact reset scope and supplied-IP operating contract only. A separate descendant-copy application, fresh full STA/export and exact exception-effect audit are required; data paths remain timed.'}
    require(not inspect.drift(watched),'reset proof input drift')
    result['InputSHA256']={str(p):h for p,h in sorted(watched.items(),key=lambda x:str(x[0]))}
    return result,watched


def verify(path):
    saved=read(path)
    require(saved.get('Schema')==SCHEMA and saved.get('Target')==prep.TARGET,'wrong reset proof identity')
    watched={};export=binding(saved['ExportReceipt'],watched);query=binding(saved['QueryReceipt'],watched)
    actual,inputs=audit_value(export,query);merge(watched,inputs)
    require(actual==saved,'reset proof differs from actual recomputation')
    add(watched,path)
    return actual,watched


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--export',type=Path,required=True);p.add_argument('--query',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    out=a.output.resolve();require(out.parent.is_dir() and out.is_relative_to(prep.WORK) and not out.exists(),'fresh work JSON required')
    value,_=audit_value(a.export,a.query)
    data=json.dumps(value,indent=2,allow_nan=False)+'\n'
    with out.open('x',encoding='utf-8',newline='\n') as stream:stream.write(data)
    print(json.dumps({'Output':ref(out),'Pairs':value['UniqueSourceEndpointPairs'],
        'LogicalChecksByCorner':value['LogicalChecksByCorner'],'NativeVariantsByCorner':value['NativeVariantsByCorner']}))


if __name__=='__main__':main()
