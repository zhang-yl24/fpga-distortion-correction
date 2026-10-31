"""CPU audit of exact upright reset effects and any explicitly requested route.

Rebind native source/derivative evidence, compare all routes and functional
cells, preserve timed data checks, and require precisely the proved reset
false-path inventory. No previous candidate authority/count/hash is inherited.
"""
import argparse
from collections import Counter
from decimal import Decimal
import hashlib
import json
from pathlib import Path

import run_camera_vga_upright_derived_inspect as derived
import audit_camera_vga_upright_io_cdc as syntax
import audit_camera_vga_routes as routes
import audit_camera_vga_route_reset_scope as route_scope
import audit_camera_vga_physical as pure_physical
import audit_camera_vga_exception_union as exception_syntax

physical, audit, inspect = derived.physical, derived.audit, derived.inspect
prep, require, sha = derived.prep, derived.require, derived.sha
native = pure_physical.native
SELF = Path(__file__).resolve()
SCHEMA = 'camera-vga-upright-reset-effect-audit-v1'


def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def file_binding(path):
    return {'Path':str(Path(path).absolute()), 'SHA256':sha(path)}


def artifact(receipt_path, receipt, name, watched):
    paths = [Path(receipt_path).parent/n for n in receipt['Artifacts']
             if Path(n).name == name and 'report_path_timing' not in Path(n).parts]
    require(len(paths) == 1, 'one bound native artifact required: '+name)
    return physical.add(watched, paths[0], receipt['Artifacts'][paths[0].relative_to(Path(receipt_path).parent).as_posix()])


def compare_timing(before, after, inventory, route_pairs):
    require(set(before) == set(after) == {(c,k) for c in ('slow','fast') for k in native.KINDS}, 'ten timing tables required')
    removed = {}
    for group in inventory['Groups']:
        key = (group['Corner'], group['LaunchClock'], group['CaptureClock'])
        require(group['Complete'] and key not in removed, 'incomplete or repeated current reset group')
        removed[key] = group['ObservedLogicalChecks']
    summaries, changes = {}, []
    for (corner, kind), old in before.items():
        now = after[(corner,kind)]
        cuts = {k[1:]:count for k,count in removed.items() if k[0] == corner} if kind in ('recovery','removal') else {}
        require(set(cuts) <= set(old) and set(now) == set(old)-set(cuts), 'timing clock-pair inventory changed outside exact reset scope')
        for pair,count in cuts.items():require(old[pair]['TotalChecks'] == count, 'removed timing check count differs from actual reset inventory')
        for pair,row in now.items():
            require(row['TotalChecks'] == old[pair]['TotalChecks'], 'timed data/remaining reset checks removed')
            allowed = kind in ('setup','hold') and pair in route_pairs
            require(allowed or row == old[pair], 'unrelated timing summary changed: '+str((corner,kind,pair)))
            if row != old[pair]:changes.append({'Corner':corner,'Kind':kind,'Clocks':list(pair),'Before':old[pair],'After':row})
            require(row['FailingChecks'] == 0 and row['WorstSlackNS'] >= 0 and row['TotalNegativeSlackNS'] == 0, 'remaining native timing failure')
        require(now, 'empty surviving timing table')
        summaries[corner+'_'+kind] = {'WorstSlackNS':min(r['WorstSlackNS'] for r in now.values()),
            'FailingChecks':sum(r['FailingChecks'] for r in now.values()),
            'TotalChecks':sum(r['TotalChecks'] for r in now.values()), 'RemovedResetChecks':sum(cuts.values())}
    return summaries, changes


def compare_routes(before, after, before_scope, after_scope, requested):
    require(before['NetAnnotations'].keys() == after['NetAnnotations'].keys(), 'native net inventory changed')
    changed = sorted(n for n,h in before['NetAnnotations'].items() if after['NetAnnotations'][n] != h)
    require(set(changed) == set(requested), 'route changed beyond exact request or requested route did not change')
    require(before['TargetConnectivity'] == after['TargetConnectivity'], 'route logical connectivity changed')
    require(before_scope['NonConstraintNonRouteSHA256'] == after_scope['NonConstraintNonRouteSHA256'],
            'nonconstraint functional/placement semantics changed')
    return {'RoutingUnchanged':not changed, 'OnlyRequestedRoutingChanges':True, 'ChangedNets':changed,
            'AllOtherNETANNOTATEIdentical':True, 'LogicalConnectivityIdentical':True, 'NonconstraintSemanticsUnchanged':True,
            'RouteCount':before['RouteCount'], 'BaselineAnnotationsSHA256':digest(before['NetAnnotations']),
            'CandidateAnnotationsSHA256':digest(after['NetAnnotations'])}


def compare_false_paths(baseline, candidate, inventory):
    require(all(not v for v in baseline.values()), 'baseline contains unapproved false paths')
    expected = {corner:{native.path_identity(p) for check in inventory['Corners'][corner]['Checks']
                        for p in check['NativeVariants']} for corner in ('slow','fast')}
    return native.validate_exception_sets(candidate, expected)


def nonfalse_equal(before, after):
    require(set(before) == set(after) and len(before) == 16, 'non-false exception section inventory differs')
    result = {}
    for key, rows in before.items():
        a,b = Counter(r['SHA256'] for r in rows),Counter(r['SHA256'] for r in after[key])
        require(a == b, 'non-reset exception paths differ; additional two-sided evidence required: '+str(key))
        result[str(key)] = {'Paths':len(rows), 'NormalizedPathMultisetSHA256':digest(sorted(a.items()))}
    return result


def route_paths(before_report, after_report, measured):
    target = {(measured['Source'], measured['Endpoint'])}
    old = pure_physical.target_paths(before_report,target)
    new = pure_physical.target_paths(after_report,target)
    by_key = lambda row:tuple(row[k] for k in ('Corner','Kind','LaunchEdge','CaptureEdge'))
    require({by_key(r) for r in old} == {by_key(r) for r in new}, 'route path edge/check inventory differs')
    # Timing summaries plus exact pin/site/clock identity guard the sole edited data net.
    for row in new:
        matches = [p for p in old if by_key(p) == by_key(row)]
        require(matches and row['SlackNS'] >= 0, 'exact routed setup/hold path missing or failing')
        accepted = False
        for previous in matches:
            fields = ('Source','Endpoint','LaunchClock','CaptureClock','LaunchEdge','CaptureEdge','Corner','Kind','PathClass',
                      'TimingExceptions','ClockSkewNS','CaptureClockDelayNS','LaunchClockDelayNS')
            if any(previous[k] != row[k] for k in fields) or len(previous['DataTrace']) != len(row['DataTrace']):continue
            same = True; delta = Decimal(0)
            for a,b in zip(previous['DataTrace'],row['DataTrace']):
                keys = set(a)-{'DelayNS','CumulativeNS','ReportLine'}
                if keys != set(b)-{'DelayNS','CumulativeNS','ReportLine'} or any(a[k] != b[k] for k in keys):same=False;break
                if a.get('Type') == 'pin' and a['DelayNS'] != b['DelayNS']:same=False;break
                if a.get('Type') == 'net' and a['Name'] != measured['PhysicalRepairCandidate']['Net'] and a['DelayNS'] != b['DelayNS']:same=False;break
                if a.get('Type') == 'net':delta += Decimal(str(b['DelayNS']))-Decimal(str(a['DelayNS']))
                if (a['CumulativeNS'] is None) != (b['CumulativeNS'] is None):same=False;break
                if a['CumulativeNS'] is not None and abs(Decimal(str(b['CumulativeNS']))-Decimal(str(a['CumulativeNS']))-delta)>Decimal('0.001'):same=False;break
            if same and abs(Decimal(str(row['SlackNS']))-Decimal(str(previous['SlackNS']))-delta*(-1 if row['Kind']=='setup' else 1))>Decimal('0.001'):same=False
            if same:accepted=True;break
        require(accepted, 'route target changed outside exact terminal data-net delay')
    return {'ExactFourCornerKindCoverage':True, 'AllTargetChecksMet':True,
            'Baseline':[ {k:v for k,v in p.items() if k not in ('_Text','_Lines')} for p in old],
            'Candidate':[ {k:v for k,v in p.items() if k not in ('_Text','_Lines')} for p in new]}


def run(application_path, candidate_export_path, baseline_route_receipt=None, candidate_route_receipt=None):
    watched = {}; application_path = inspect.canonical(application_path, prep.WORK)
    application = derived.bind_source_receipt(application_path, watched)
    require(application.get('ResetProof') is not None, 'reset effect audit requires an applied proved reset scope')
    proof_path = Path(application['ResetProof']['Path']); proof = read(proof_path)
    build = Path(application['BuildPlan']); source = Path(application['SourceADF']); source_sha = application['SourceADFSHA256']
    _,_,_,_,_,proof_inputs = physical.bind_proof(build,proof_path,application['ResetProof']['SHA256'])
    watched.update(proof_inputs)
    baseline_export_path = Path(proof['CurrentNetlist']['Path']).parent.parent/'result.json'
    baseline = audit.inspection_receipt(baseline_export_path,'export',build,source,source_sha,watched)
    candidate_export_path = inspect.canonical(candidate_export_path,prep.WORK)
    final = derived.bind_receipt(candidate_export_path,watched)
    require(final['Mode'] == 'export' and final['SourceReceipt'] == file_binding(application_path)
            and final['SourceADFSHA256'] == application['ResultADFSHA256'], 'final export belongs to another derivative')
    br = artifact(baseline_export_path,baseline,prep.TARGET+'.rtr',watched)
    cr = artifact(candidate_export_path,final,prep.TARGET+'.rtr',watched)
    be = artifact(baseline_export_path,baseline,prep.TARGET+'_exception.rtr',watched)
    ce = artifact(candidate_export_path,final,prep.TARGET+'_exception.rtr',watched)
    inventory, _ = audit.inventory(proof['CurrentReport']['Path'])
    targets, route_pairs, measured = {},set(),None
    if application.get('Route'):
        request = read(application['Request']['Path'])
        dump_before = physical.binding(request['RouteDump'],watched)
        hold_value = read(request['HoldAudit']['Path']); measured = hold_value['Paths'][0]
        target = {**measured['PhysicalRepairCandidate'],'Endpoint':measured['Endpoint']}
        targets[target['Net']] = target; route_pairs.add((measured['LaunchClock'],measured['CaptureClock']))
        dump_after = artifact(application_path,application,'route-dump.txt',watched)
        route_origin = {'BaselineReceipt':request['QueryReceipt'], 'CandidateReceipt':file_binding(application_path),
                        'Request':application['Request'], 'RequestedRoute':application['Route']}
    else:
        require(baseline_route_receipt and candidate_route_receipt, 'reset-only route comparison needs both clean route dumps')
        old_route = audit.inspection_receipt(baseline_route_receipt,'query',build,source,source_sha,watched)
        new_route = derived.bind_receipt(candidate_route_receipt,watched)
        require(new_route['SourceReceipt'] == file_binding(application_path) and new_route['Mode'] in ('report','query'), 'wrong derivative route receipt')
        dump_before = artifact(baseline_route_receipt,old_route,'route-dump.txt',watched)
        dump_after = artifact(candidate_route_receipt,new_route,'route-dump.txt',watched)
        route_origin = {'BaselineReceipt':file_binding(baseline_route_receipt), 'CandidateReceipt':file_binding(candidate_route_receipt)}
    a,b = routes.inspect(dump_before,targets),routes.inspect(dump_after,targets)
    sa,sb = route_scope.constraint_separated(dump_before),route_scope.constraint_separated(dump_after)
    route_result = compare_routes(a,b,sa,sb,targets)
    if targets:
        name = next(iter(targets)); requested = application['Route']['Pins'][:-1].split('>'); actual = b['TargetRoutes'][name]
        require(any(actual[i:i+len(requested)] == requested for i in range(len(actual))), 'requested continuous detour absent from saved route')
    before_graph = syntax.functional(Path(baseline['Netlist']['Path']).read_text(encoding='utf-8-sig'))
    after_graph = syntax.functional(Path(final['Netlist']['Path']).read_text(encoding='utf-8-sig'))
    require(before_graph == after_graph, 'functional graph, declarations or FF placement changed')
    bt,bc = pure_physical.summaries(br); ct,cc = pure_physical.summaries(cr)
    require(bc == cc, 'clock definitions/loads changed')
    summaries,changes = compare_timing(bt,ct,inventory,route_pairs)
    with be.open(encoding='gb18030') as f:old_false = native.parse_false_paths(f)
    with ce.open(encoding='gb18030') as f:new_false = native.parse_false_paths(f)
    false_counts = compare_false_paths(old_false,new_false,inventory)
    other = nonfalse_equal(exception_syntax.read_exceptions(be),exception_syntax.read_exceptions(ce))
    paths = route_paths(br,cr,measured) if measured else None
    for module in (physical,derived,audit,inspect,syntax,routes,route_scope,pure_physical,
                   pure_physical.hold,pure_physical.dialect,native,exception_syntax):
        physical.add(watched, module.__file__)
    physical.add(watched,SELF)
    require(not inspect.drift(watched), 'effect audit input/tool drift')
    result = {'Schema':SCHEMA,'Target':prep.TARGET,'CreatedUTC':prep.utc(),'AuditPassed':True,'ResetEffectVerified':True,
        'SourceADF':file_binding(source),'ResultADF':file_binding(application['ResultADF']['Path']),
        'ApplicationReceipt':file_binding(application_path),'ResetProof':application['ResetProof'],
        'BaselineExportReceipt':file_binding(baseline_export_path),'CandidateExportReceipt':file_binding(candidate_export_path),
        'FunctionalGraphIdentical':True,'AllFFPlacementsIdentical':True,
        'ActualCellCount':len(before_graph['Cells']),'ActualFFCount':len(before_graph['FFPlacement']),
        'FunctionalPartSHA256':{k:digest(v) for k,v in before_graph.items()},
        **route_result,'RouteScopeEvidence':{**route_origin,'BaselineDump':file_binding(dump_before),
            'CandidateDump':file_binding(dump_after),'Comparison':route_result,
            'BaselineNonconstraintSHA256':sa['NonConstraintNonRouteSHA256'],'CandidateNonconstraintSHA256':sb['NonConstraintNonRouteSHA256']},
        'ExactResetExceptionUnionVerified':True,'NoDataFalsePaths':True,'ClockDefinitionsAndLoadsUnchanged':True,
        'AllInternalChecksMet':True,'CornerSummaries':summaries,'TimingSummaryChanges':changes,
        'FalsePathCounts':false_counts,'OtherExceptionsIdentical':True,'NonFalseExceptionComparison':other,'TargetRouteTiming':paths,
        'InputSHA256':{str(p):h for p,h in watched.items()},'ToolSHA256':{str(p):h for p,h in watched.items() if p.suffix=='.py'},
        'EDAExecuted':False,'HardwareAccessed':False,'TimingAccepted':False,'HardwareReleaseAllowed':False,'ExternalIOAccepted':False,
        'Limits':'Current internal native STA, exact reset effects and requested route only. External AC/CDC/hardware validation and bitstream release remain separate.'}
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--application',type=Path,required=True);p.add_argument('--candidate-export',type=Path,required=True)
    p.add_argument('--baseline-route-receipt',type=Path);p.add_argument('--candidate-route-receipt',type=Path)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    output=a.output.absolute();require(output==output.resolve() and output.is_relative_to(prep.WORK) and not output.exists(),'fresh in-workspace output required')
    result=run(a.application,a.candidate_export,a.baseline_route_receipt,a.candidate_route_receipt)
    with output.open('x',encoding='utf-8',newline='\n') as f:json.dump(result,f,indent=2);f.write('\n')
    require(read(output)==result,'effect output readback mismatch')
    print(json.dumps({k:result[k] for k in ('AuditPassed','ResetEffectVerified','RoutingUnchanged','ChangedNets','AllInternalChecksMet')}))


if __name__=='__main__':main()
