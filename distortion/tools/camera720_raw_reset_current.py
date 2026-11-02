"""CPU reset scope for the actual current720 route-b native export.

The original raw scope parser is reused without changing its target globals.
The current report and current graph are independently re-derived; an older
proof never authorizes this ADF. Native query/application remain separate.
"""
import argparse
import json
from pathlib import Path
from types import ModuleType

import camera720_raw_derived_inspect as derived
import camera720_raw_reset as reset
import camera720_reset_apply as commands

inspect, prep = derived.inspect, derived.prep
require, sha = derived.require, derived.sha
SELF = Path(__file__).resolve()
SCHEMA = 'camera720-current-raw-derived-reset-scope-v1'
SOURCE_SHA = 'e43f5707209271cd35a534978315302092b2ad18ca4ecd41b6f0aed06b4847a3'
EXPORT_SHA = 'c0b07011f78f71c7bc5559c31cb4b844b174d19504259675d6c8ad67629a4997'
APPLICATION_SHA = 'f201ed6abaccb90c80b65fbf197e7ef8507b118944fd4496191701d285f2c957'

def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))

def add(watched, path, expected=None):
    path = Path(path).resolve()
    require(path.is_file(), 'input does not exist')
    actual = sha(path)
    require(expected is None or actual == expected, 'bound digest differs: '+str(path))
    require(path not in watched or watched[path] == actual, 'conflicting digest')
    # External executable/library paths only enter through the frozen binder.
    require(path.is_relative_to(prep.PROJECT.parent) or path in watched, 'unadmitted external input')
    watched[path] = actual
    return path

def merge(watched, incoming):
    for path, digest in incoming.items():
        require(path not in watched or watched[path] == digest, 'conflicting native input')
        watched[path] = digest

def bind_tools(watched):
    pending, seen = [derived, reset, commands], set()
    while pending:
        module = pending.pop()
        if id(module) in seen:
            continue
        seen.add(id(module))
        filename = getattr(module, '__file__', None)
        if filename:
            path = Path(filename).resolve()
            if path.suffix == '.py' and path.is_relative_to(prep.PROJECT/'tools'):
                add(watched, path)
                pending.extend(v for v in vars(module).values() if isinstance(v, ModuleType))
    add(watched, SELF)

def exact_export(value):
    require(value.get('Target') == prep.TARGET and value.get('Mode') == 'export'
            and value.get('SourceADFSHA256') == SOURCE_SHA
            and value.get('SourceReceipt', {}).get('SHA256') == APPLICATION_SHA,
            'exact route-b export and ADF required')
    require(value.get('BuildDiagnosticsCleared') is False
            and value.get('HardwareReleaseAllowed') is False, 'diagnostic authority differs')

def derive(export_path, export_sha):
    require(export_sha == EXPORT_SHA, 'explicit frozen route-b export digest required')
    path = inspect.canonical(export_path, prep.WORK)
    require(sha(path) == export_sha, 'export digest differs')
    value, watched = derived.bind_receipt(path)
    exact_export(value)
    report = path.parent/'report_timing'/(prep.TARGET+'.rtr')
    require(value['Artifacts'].get(report.relative_to(path.parent).as_posix()) == sha(report),
            'current report is not export-bound')
    add(watched, report)
    netlist = add(watched, value['Netlist']['Path'], value['Netlist']['SHA256'])
    inv = reset.inventory(report)
    queries, body, fdc = reset.native_scope(inv)
    exact = commands.exact_commands(queries)
    require([s for s in fdc.splitlines() if s and not s.startswith('#')] == exact,
            'FDC differs from exact derived reset commands')
    structural = reset.audit_netlist_text(netlist.read_text(encoding='utf-8-sig'), queries)
    require(inv['Complete'] and structural['RegisteredStickyPropertyVerified'] is True,
            'incomplete current reset scope/graph')
    bind_tools(watched)
    result = {'Schema':SCHEMA, 'Target':prep.TARGET, 'Status':'current_graph_verified_unapplied',
        'ExportReceipt':{'Path':str(path),'SHA256':export_sha},
        'RouteApplicationReceipt':value['SourceReceipt'],
        'BuildPlan':value['BuildPlan'], 'BuildPlanSHA256':value['BuildPlanSHA256'],
        'SourceADF':value['SourceADF'], 'SourceADFSHA256':value['SourceADFSHA256'],
        'BuildDiagnosticsReview':value['BuildDiagnosticsReview'],
        'CurrentReport':{'Path':str(report),'SHA256':sha(report)}, 'CurrentNetlist':value['Netlist'],
        **reset.summary(inv), 'NativeQueries':queries, 'ExactResetCommands':exact,
        'UniqueSourceEndpointPairs':sum(len(q['Targets']) for q in queries),
        'StructuralProof':structural, 'ResetConnectivityVerified':True,
        'ReportNativeADFBindingVerified':True, 'NativeQueriesVerified':False,
        'VendorResetContractProven':False, 'ConstraintsApplied':False,
        'TimingExceptionApproved':False, 'TimingAccepted':False, 'HardwareReleaseAllowed':False,
        'BuildExecutionCompletedWithoutError':False, 'BuildDiagnosticsCleared':False,
        'HardwareAccessed':False, 'EDAExecuted':False, 'OpticalCorrectionAccepted':False,
        'Producer':{'Path':str(SELF),'SHA256':sha(SELF)}}
    payloads = {'recovery-inventory.json':json.dumps(inv,indent=2)+'\n',
                'query-body.tcl':body, 'proposed-scope.fdc':fdc}
    result['FilesSHA256'] = {n:prep.baseline.paths.sha_bytes(t.encode('utf-8')) for n,t in payloads.items()}
    result['InputSHA256'] = {str(p):h for p,h in watched.items()}
    require(not inspect.drift(watched), 'reset scope input drift')
    # Frozen graph helpers use tuples internally; normalize once to the exact
    # JSON representation before later plan equality checks.
    return json.loads(json.dumps(result)), payloads, watched

def prepare(export_path, export_sha, output):
    output = prep.work_path(output)
    require(not output.exists(), 'fresh current reset scope directory required')
    value, payloads, watched = derive(export_path, export_sha)
    output.mkdir()
    for name, text in payloads.items():
        (output/name).write_text(text,encoding='utf-8',newline='\n')
    inspect.diagnostic.write(output/'plan.json',value)
    require(read(output/'plan.json') == value, 'scope output readback differs')
    return output/'plan.json'

def bind_scope(path, expected_sha, query_receipt=None, query_sha=None):
    path = inspect.canonical(path, prep.WORK)
    require(path.name == 'plan.json' and sha(path) == expected_sha, 'exact current scope plan required')
    value = read(path)
    expected, payloads, watched = derive(value['ExportReceipt']['Path'],value['ExportReceipt']['SHA256'])
    require(value == expected, 'current scope differs from actual report/graph derivation')
    add(watched,path,expected_sha)
    for name,text in payloads.items():
        require((path.parent/name).read_bytes() == text.encode('utf-8'), 'scope payload bytes differ')
        add(watched,path.parent/name,value['FilesSHA256'][name])
    evidence = []
    if query_receipt is not None:
        require(query_sha is not None, 'query receipt requires explicit digest')
        query_path = add(watched,query_receipt,query_sha)
        query, bound = derived.bind_receipt(query_path)
        merge(watched,bound)
        require(query['Mode'] == 'query' and query['SourceADFSHA256'] == SOURCE_SHA
                and query['SourceReceipt'] == value['RouteApplicationReceipt']
                and query['BuildPlan'] == value['BuildPlan'], 'query candidate differs')
        require(Path(query['QueryBody']).read_bytes() == payloads['query-body.tcl'].encode('ascii'),
                'native query body differs from exact current inventory')
        evidence = reset.query_parser.exact_queries(value['NativeQueries'],query_path.parent/'stdout.log')
    else:
        require(query_sha is None, 'query digest without receipt')
    require(not inspect.drift(watched), 'current reset scope changed while binding')
    return value, evidence, watched

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--export-receipt',type=Path,required=True)
    parser.add_argument('--export-sha256',required=True)
    parser.add_argument('--name',required=True)
    args=parser.parse_args()
    path=prepare(args.export_receipt,args.export_sha256,prep.WORK/args.name)
    value=read(path)
    print(json.dumps({'Prepared':True,'Path':str(path),'SHA256':sha(path),
        'Groups':len(value['NativeQueries']),'Pairs':value['UniqueSourceEndpointPairs'],
        'NativeQueriesVerified':False,'TimingAccepted':False,'EDAExecuted':False}))

if __name__ == '__main__':
    main()
