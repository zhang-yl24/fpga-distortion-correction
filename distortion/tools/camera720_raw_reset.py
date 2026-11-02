"""Derive current720 raw reset scope and inspect its new functional export.

CPU-only. Explicit header adapters reuse frozen parsing/graph algorithms while
preserving native names, source rows and original artifact hashes. No constraint
is applied and failed-build diagnostics are never cleared by this audit.
"""
import argparse
import json
from pathlib import Path
import re
import tempfile
from types import ModuleType

import camera720_raw_inspect as inspect
import prepare_raw_camera_delay_reset_scope as scope
import audit_raw_camera_delay_reset_netlist as graph
import audit_raw_camera_delay_reset as query_parser

prep = inspect.prep
SELF = Path(__file__).resolve()
PLAN_SCHEMA = 'camera720-current-raw-reset-scope-v1'
PROOF_SCHEMA = 'camera720-current-raw-reset-graph-v1'
require, sha = inspect.require, inspect.sha


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def watch(watched, path, digest=None):
    path = inspect.canonical(path)
    actual = sha(path)
    require(digest is None or actual == digest, 'artifact SHA differs: '+str(path))
    require(path not in watched or watched[path] == actual, 'conflicting artifact digest')
    watched[path] = actual
    return path


def watch_tools(watched):
    pending, seen = [inspect, scope, graph, query_parser], set()
    watch(watched, SELF)
    while pending:
        module = pending.pop()
        if id(module) in seen:
            continue
        seen.add(id(module))
        filename = getattr(module, '__file__', None)
        if filename:
            path = Path(filename).resolve()
            if path.suffix == '.py' and path.is_relative_to(prep.PROJECT/'tools'):
                watch(watched, path)
                pending.extend(value for value in vars(module).values() if isinstance(value, ModuleType))


def parse_report(report):
    text = Path(report).read_text(encoding='utf-8-sig')
    pattern = r'(?m)^(\| Design\s*:\s*)(\S+)(\s*)$'
    found = re.findall(pattern, text)
    require(len(found) == 1 and found[0][1] == prep.TARGET, 'one exact current720 raw native report required')
    normalized = re.sub(pattern, lambda m: m[1]+graph.TARGET+m[3], text, count=1)
    # The old parser accepts a path. Only this ephemeral header-normalized copy
    # enters it; original report bytes and all endpoint names remain untouched.
    with tempfile.TemporaryDirectory(prefix='raw720-reset-parser-') as folder:
        path = Path(folder)/'native.rtr'
        path.write_text(normalized, encoding='utf-8', newline='\n')
        paths, summaries = scope.parse_report(path)
    return paths, summaries


def inventory(report, allow_incomplete=False):
    paths, summaries = parse_report(report)
    return scope.audit_inventory(paths, summaries, require_complete=not allow_incomplete)


def native_scope(inv):
    queries, body, fdc = scope.query_scope(inv)
    return queries, body.replace('RAW_CAMERA_DELAY_RESET_QUERY_', 'CAMERA720_RAW_RESET_QUERY_'), fdc


def audit_netlist_text(text, queries):
    require(re.findall(r'(?m)^module\s+(\w+)\b', text) == [prep.TARGET],
            'one exact current720 raw functional top required')
    normalized = re.sub(r'(?m)^(module\s+)'+prep.TARGET+r'\b',
                        lambda m: m[1]+graph.TARGET, text, count=1)
    result = graph.audit_text(normalized, queries)
    require(result['Target'] == graph.TARGET, 'frozen reset parser identity changed')
    return {**result, 'Target':prep.TARGET,
            'HeaderOnlyAdapter':prep.TARGET+' -> '+graph.TARGET+' -> board1080_top for strict V_* parsing',
            'OriginalFunctionalNamesPreserved':True}


def summary(inv):
    return {'Complete':inv['Complete'],
            'LogicalChecksByCorner':{k:v['LogicalChecks'] for k,v in inv['Corners'].items()},
            'NativeVariantsByCorner':{k:v['NativeVariants'] for k,v in inv['Corners'].items()},
            'FailingChecksByCorner':{k:v['FailingChecks'] for k,v in inv['Corners'].items()},
            'HistoricalEndpointInventoryUsed':False}


def save(output, value, payloads, watched, filename):
    output = prep.work_path(output)
    require(not output.exists(), 'fresh raw720 reset evidence directory required')
    require(not inspect.drift(watched), 'reset evidence changed during CPU audit')
    value['InputSHA256'] = {str(p):h for p,h in sorted(watched.items(),key=lambda item:str(item[0]))}
    value['Producer'] = {'Path':str(SELF),'SHA256':sha(SELF)}
    value['FilesSHA256'] = {name:prep.baseline.paths.sha_bytes(data.encode('utf-8')) for name,data in payloads.items()}
    output.mkdir()
    for name, data in payloads.items():
        with (output/name).open('x',encoding='utf-8',newline='\n') as stream:
            stream.write(data)
    inspect.diagnostic.write(output/filename,value)
    return value


def bind_export(receipt, expected_sha, build_plan, adf, watched):
    path = watch(watched,receipt,expected_sha)
    value, bound = inspect.bind_receipt(path)
    watched.update(bound)
    require(value['Mode'] == 'export' and value['BuildPlan'] == str(build_plan)
            and value['SourceADF'] == str(adf) and value['SourceADFSHA256'] == sha(adf),
            'reset export must bind this exact raw build and candidate')
    report = path.parent/'report_timing'/(prep.TARGET+'.rtr')
    require(value['Artifacts'].get(report.relative_to(path.parent).as_posix()) == sha(report),
            'raw report is absent from export receipt')
    return value, report


def prepare(build_plan, adf, adf_sha, report, output, review=None, review_sha=None,
            export_receipt=None, export_sha=None, allow_incomplete=False):
    build_plan,adf = Path(build_plan).absolute(),Path(adf).absolute()
    _,watched = inspect.bind(build_plan,adf,adf_sha,review,review_sha)
    watch_tools(watched)
    report = watch(watched,report)
    native_bound = False
    if export_receipt is not None:
        require(export_sha is not None,'explicit export receipt SHA required')
        _,expected_report = bind_export(export_receipt,export_sha,build_plan,adf,watched)
        require(report == expected_report,'scope report differs from exact native export')
        native_bound = True
    else:
        require(export_sha is None and report == build_plan.parent/'report_timing'/(prep.TARGET+'.rtr'),
                'initial report must be this build exact report_timing path')
    inv = inventory(report,allow_incomplete)
    queries,body,fdc = native_scope(inv) if inv['Complete'] else ([], '', '')
    build_result = read(build_plan.parent/'execution-result.json')
    value = {'Schema':PLAN_SCHEMA,'Target':prep.TARGET,'Status':'prepared_unapplied' if inv['Complete'] else 'incomplete_no_proposal',
        'BuildPlan':str(build_plan),'BuildPlanSHA256':sha(build_plan),'SourceADF':str(adf),'SourceADFSHA256':adf_sha,
        'BuildDiagnosticsReview':{'Path':str(Path(review).absolute()),'SHA256':review_sha} if review else None,
        'BuildExecutionCompletedWithoutError':build_result['ExecutionCompletedWithoutError'],
        'BuildDiagnosticsCleared':build_result['Diagnostics'] == [],
        'Report':{'Path':str(report),'SHA256':sha(report)},
        'ExportReceipt':{'Path':str(Path(export_receipt).absolute()),'SHA256':export_sha} if export_receipt else None,
        'ReportNativeADFBindingVerified':native_bound,
        'ReportAdapter':{'OriginalTop':prep.TARGET,'ParserTop':graph.TARGET,'OriginalNativePathsAndLinesPreserved':True},
        **summary(inv),'NativeQueries':queries,'UniqueSourceEndpointPairs':sum(len(q['Targets']) for q in queries),
        'ConstraintsApplied':False,'NativeQueriesVerified':False,'ResetConnectivityVerified':False,
        'TimingExceptionApproved':False,'TimingAccepted':False,'HardwareAccessed':False,
        'HardwareReleaseAllowed':False,'EDAExecuted':False,
        'Limits':'A current report-derived unapplied proposal only. Build diagnostics remain unresolved. Exact native pin, functional reset graph and vendor reset review are separate obligations.'}
    payloads={'recovery-inventory.json':json.dumps(inv,indent=2)+'\n'}
    if inv['Complete']:
        payloads.update({'query-body.tcl':body,'proposed-scope.fdc':fdc})
    return save(output,value,payloads,watched,'plan.json')


def audit(plan_path,plan_sha,export_receipt,export_sha,output,query_receipt=None,query_sha=None):
    watched={}
    path=watch(watched,plan_path,plan_sha)
    plan=read(path)
    require(plan.get('Schema') == PLAN_SCHEMA and plan.get('Target') == prep.TARGET
            and plan.get('Complete') is True and plan.get('ConstraintsApplied') is False
            and plan.get('TimingExceptionApproved') is False,'complete current720 unapplied reset plan required')
    for name,digest in plan['InputSHA256'].items():
        original=Path(name).absolute()
        require(original == original.resolve() and original.is_file() and sha(original) == digest,'scope input changed')
        watched[original]=digest
    for name,digest in plan['FilesSHA256'].items():
        require(Path(name).name == name,'invalid reset artifact path')
        watch(watched,path.parent/name,digest)
    review=plan.get('BuildDiagnosticsReview') or {}
    _,bound=inspect.bind(plan['BuildPlan'],plan['SourceADF'],plan['SourceADFSHA256'],review.get('Path'),review.get('SHA256'))
    watched.update(bound);watch_tools(watched)
    inv=inventory(plan['Report']['Path'])
    queries,body,fdc=native_scope(inv)
    require(queries == plan['NativeQueries'] and summary(inv) == {k:plan[k] for k in summary(inv)}
            and (path.parent/'query-body.tcl').read_text() == body
            and (path.parent/'proposed-scope.fdc').read_text() == fdc,'scope is not rederived from its exact native report')
    export,report=bind_export(export_receipt,export_sha,Path(plan['BuildPlan']),Path(plan['SourceADF']),watched)
    actual=inventory(report)
    actual_queries,_,_=native_scope(actual)
    require(actual_queries == queries,'export native reset inventory differs from proposal')
    netlist=watch(watched,export['Netlist']['Path'],export['Netlist']['SHA256'])
    structural=audit_netlist_text(netlist.read_text(encoding='utf-8-sig'),queries)
    pin_evidence=[]
    if query_receipt is not None:
        require(query_sha is not None,'explicit query receipt SHA required')
        qpath=watch(watched,query_receipt,query_sha)
        qvalue,qbound=inspect.bind_receipt(qpath);watched.update(qbound)
        require(qvalue['Mode'] == 'query' and qvalue['BuildPlan'] == plan['BuildPlan']
                and qvalue['SourceADFSHA256'] == plan['SourceADFSHA256']
                and inspect.query_commands(Path(qvalue['QueryBody']).read_text()) == inspect.query_commands(body),
                'native reset query must be exact proposed body for this candidate')
        pin_evidence=query_parser.exact_queries(queries,qpath.parent/'stdout.log')
    else:
        require(query_sha is None,'query SHA requires a query receipt')
    value={'Schema':PROOF_SCHEMA,'Target':prep.TARGET,'Status':'graph_verified_no_timing_approval',
        'ScopePlan':{'Path':str(path),'SHA256':plan_sha},
        'BuildPlan':plan['BuildPlan'],'SourceADF':plan['SourceADF'],'SourceADFSHA256':plan['SourceADFSHA256'],
        'ExportReceipt':{'Path':str(Path(export_receipt).absolute()),'SHA256':export_sha},
        'QueryReceipt':{'Path':str(Path(query_receipt).absolute()),'SHA256':query_sha} if query_receipt else None,
        'BuildDiagnosticsReview':plan['BuildDiagnosticsReview'],
        'BuildExecutionCompletedWithoutError':export['BuildExecutionCompletedWithoutError'],
        'BuildDiagnosticsCleared':export['BuildDiagnosticsCleared'],
        **summary(actual),'NativeQueries':queries,'ReportNativeADFBindingVerified':True,
        'ResetConnectivityVerified':True,'NativeQueriesVerified':bool(pin_evidence),'NativePinEvidence':pin_evidence,
        'RegisteredStickyPropertyVerified':structural['RegisteredStickyPropertyVerified'],
        'StructuralProof':structural,'VendorResetContractProven':False,'ConstraintsApplied':False,
        'TimingExceptionApproved':False,'TimingAccepted':False,'HardwareAccessed':False,
        'HardwareReleaseAllowed':False,'EDAExecuted':False,
        'Limits':'Only current registered startup/DDR reset structure and optional exact pins. Other reset consumers, complete physical timing and diagnostic disposition remain separate. No constraint or release is approved.'}
    return save(output,value,{'recovery-inventory.json':json.dumps(actual,indent=2)+'\n'},watched,'result.json')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    commands=p.add_subparsers(dest='command',required=True)
    a=commands.add_parser('prepare')
    a.add_argument('--build-plan',type=Path,required=True);a.add_argument('--adf',type=Path,required=True)
    a.add_argument('--adf-sha256',required=True);a.add_argument('--report',type=Path,required=True)
    a.add_argument('--output',type=Path,required=True);a.add_argument('--review',type=Path);a.add_argument('--review-sha256')
    a.add_argument('--export-receipt',type=Path);a.add_argument('--export-sha256');a.add_argument('--allow-incomplete',action='store_true')
    a=commands.add_parser('audit')
    a.add_argument('--plan',type=Path,required=True);a.add_argument('--plan-sha256',required=True)
    a.add_argument('--export-receipt',type=Path,required=True);a.add_argument('--export-sha256',required=True)
    a.add_argument('--query-receipt',type=Path);a.add_argument('--query-sha256');a.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    if a.command == 'prepare':
        value=prepare(a.build_plan,a.adf,a.adf_sha256,a.report,a.output,a.review,a.review_sha256,
                      a.export_receipt,a.export_sha256,a.allow_incomplete)
    else:
        value=audit(a.plan,a.plan_sha256,a.export_receipt,a.export_sha256,a.output,a.query_receipt,a.query_sha256)
    print(json.dumps({k:value[k] for k in ('Schema','Status','Complete','LogicalChecksByCorner',
        'FailingChecksByCorner','TimingExceptionApproved','HardwareReleaseAllowed')}))


if __name__ == '__main__':
    main()
