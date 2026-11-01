"""CPU integration checks for 720p reset effects; no EDA or hardware execution."""
from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
import audit_camera720_reset_effect as tool


@pytest.fixture
def effect_case(tmp_path, monkeypatch):
    """Mock expensive native bind/parsers, retain the actual effect comparisons."""
    base_dir = tmp_path/'baseline'; base_dir.mkdir()
    app_dir = tmp_path/'application'; app_dir.mkdir()
    final_dir = tmp_path/'candidate'; final_dir.mkdir()
    paths = [app_dir/'result.json', base_dir/'result.json', final_dir/'result.json']
    for path in paths:
        path.write_text('{}', encoding='utf-8')
    report = tmp_path/'inventory.rtr'; report.write_text('native report')
    proof = tmp_path/'proof.json'
    proof.write_text(json.dumps({'CurrentReport': {'Path':str(report)}}))
    source = base_dir/'source.adf'; source.write_text('route repaired')
    old_dump = base_dir/'route-dump.txt'; old_dump.write_text('old native dump')
    new_dump = app_dir/'route-dump.txt'; new_dump.write_text('new native dump')
    old_net = base_dir/'flat.v'; old_net.write_text('same graph')
    new_net = final_dir/'flat.v'; new_net.write_text('same graph')
    reports, exceptions = [], []
    for parent in (base_dir, final_dir):
        p = parent/(tool.prep.TARGET+'.rtr'); p.write_text('timing'); reports.append(p)
        p = parent/(tool.prep.TARGET+'_exception.rtr'); p.write_text('exceptions'); exceptions.append(p)
    before = {'Mode':'export', 'BuildPlanSHA256':'same-build', 'SourceADFSHA256':'held',
              'Netlist':{'Path':str(old_net)}}
    after = {'Mode':'export', 'BuildPlanSHA256':'same-build', 'SourceADFSHA256':'reset',
             'Netlist':{'Path':str(new_net)},
             'SourceReceipt':{'Path':str(paths[0]), 'SHA256':tool.sha(paths[0])}}
    for receipt, parent in ((before,base_dir),(after,final_dir)):
        receipt['Artifacts'] = {p.name:tool.sha(p) for p in parent.glob('*.rtr')}
    application = {'BuildPlanSHA256':'same-build', 'SourceADFSHA256':'held', 'ResultADFSHA256':'reset',
                   'SourceADF':str(source), 'ResetProof':{'Path':str(proof), 'SHA256':tool.sha(proof)}}
    bound = [*paths, proof, report, old_dump, new_dump, old_net, new_net, *reports, *exceptions]
    hashes = {p:tool.sha(p) for p in bound}
    def bind_app(path, watched):
        assert path == paths[0]
        watched.update(hashes)
        return application
    def bind_before(path):
        assert path == paths[1]
        return before, dict(hashes)
    def bind_after(path, watched):
        assert path == paths[2]
        watched.update(hashes)
        return after
    monkeypatch.setattr(tool.final,'bind_source_receipt',bind_app)
    monkeypatch.setattr(tool.baseline,'bind_receipt',bind_before)
    monkeypatch.setattr(tool.final,'bind_receipt',bind_after)

    data = ('data-clock','destination-clock'); reset = ('reset-clock','ddr-clock')
    old_tables, new_tables = {}, {}
    groups = []
    pin = {'Source':'reset/CLK', 'Endpoint':'sync/RS', 'LaunchClock':reset[0],
           'CaptureClock':reset[1], 'LaunchEdge':'rising', 'CaptureEdge':'rising'}
    inventory = {'Groups':groups, 'Corners':{c:{'Checks':[{'NativeVariants':[dict(pin)]}]} for c in ('slow','fast')}}
    for corner in ('slow','fast'):
        groups.append({'Corner':corner, 'LaunchClock':reset[0], 'CaptureClock':reset[1],
                       'Complete':True, 'ObservedLogicalChecks':3})
        for kind in tool.semantics.native.KINDS:
            key = (corner,kind)
            old_tables[key] = {data:{'TotalChecks':100, 'WorstSlackNS':0.02,
                                    'TotalNegativeSlackNS':0, 'FailingChecks':0}}
            new_tables[key] = deepcopy(old_tables[key])
            if kind in ('recovery','removal'):
                old_tables[key][reset] = {'TotalChecks':3, 'WorstSlackNS':-1,
                                         'TotalNegativeSlackNS':-3, 'FailingChecks':3}
    monkeypatch.setattr(tool.reset,'inventory',lambda _: (inventory,{}))
    clocks = {'board':125.0}
    monkeypatch.setattr(tool.semantics.pure_physical,'summaries',
                        lambda p:(old_tables if p==reports[0] else new_tables,clocks))
    old_false = {(c,k):[] for c in ('slow','fast') for k in ('setup','hold','recovery','removal')}
    new_false = deepcopy(old_false)
    for corner in ('slow','fast'):
        for kind in ('recovery','removal'):
            new_false[corner,kind] = [{**pin,'LaunchDataTransition':'r','NativePathSignature':corner+kind}]
    monkeypatch.setattr(tool.semantics.native,'parse_false_paths',
                        lambda f:old_false if Path(f.name)==exceptions[0] else new_false)
    other = {str(i):[{'SHA256':'same'}] for i in range(16)}
    monkeypatch.setattr(tool.semantics.exception_syntax,'read_exceptions',lambda _:other)
    monkeypatch.setattr(tool.graph,'functional',lambda text:text)
    old_route = {'NetAnnotations':{'signal':'unchanged'}, 'TargetConnectivity':{'signal':['q','d']}, 'RouteCount':1}
    new_route = deepcopy(old_route)
    monkeypatch.setattr(tool.routes,'inspect',lambda p,_:old_route if p==old_dump else new_route)
    monkeypatch.setattr(tool.route_scope,'constraint_separated',lambda _:{'NonConstraintNonRouteSHA256':'same'})
    return locals()


def test_bound_chain_and_ten_tables_pass_without_hardware_authority(effect_case):
    result = tool.run(*effect_case['paths'])
    assert result['AuditPassed'] and result['ResetEffectVerified']
    assert len(result['CornerSummaries']) == 10
    assert result['CornerSummaries']['fast_recovery']['RemovedResetChecks'] == 3
    for field in ('EDAExecuted','HardwareAccessed','TimingAccepted','HardwareReleaseAllowed',
                  'CDCPhysicalAccepted','ExternalACAccepted'):
        assert result[field] is False


@pytest.mark.parametrize('change', ['build','ancestor','result','receipt','mode'])
def test_other_candidate_or_incomplete_export_never_passes(effect_case,change):
    c = effect_case
    if change=='build':c['after']['BuildPlanSHA256']='other'
    if change=='ancestor':c['application']['SourceADFSHA256']='other'
    if change=='result':c['after']['SourceADFSHA256']='other'
    if change=='receipt':c['after']['SourceReceipt']['SHA256']='other'
    if change=='mode':c['after']['Mode']='report'
    with pytest.raises(ValueError):tool.run(*c['paths'])


@pytest.mark.parametrize('change', ['missing_table','removed_data','changed_slack','remaining_failure',
                                  'extra_false_path','missing_reset_variant','route_change'])
def test_unapproved_effects_fail_closed(effect_case,change):
    c = effect_case
    if change=='missing_table':del c['new_tables']['fast','mpw']
    if change=='removed_data':c['new_tables']['slow','hold'][c['data']]['TotalChecks']-=1
    if change=='changed_slack':c['new_tables']['slow','setup'][c['data']]['WorstSlackNS']=0.03
    if change=='remaining_failure':
        for tables in (c['old_tables'],c['new_tables']):
            tables['slow','hold'][c['data']]['WorstSlackNS']=-0.01
            tables['slow','hold'][c['data']]['FailingChecks']=1
    if change=='extra_false_path':c['new_false']['slow','setup']=deepcopy(c['new_false']['slow','recovery'])
    if change=='missing_reset_variant':c['new_false']['fast','removal']=[]
    if change=='route_change':c['new_route']['NetAnnotations']['signal']='changed'
    with pytest.raises(ValueError):tool.run(*c['paths'])


def test_drift_during_comparison_is_not_rehashed_into_acceptance(effect_case,monkeypatch):
    real_compare = tool.semantics.compare_routes
    def change_after_read(*args):
        result = real_compare(*args)
        effect_case['new_net'].write_text('changed after graph comparison')
        return result
    monkeypatch.setattr(tool.semantics,'compare_routes',change_after_read)
    with pytest.raises(ValueError,match='changed during verification'):
        tool.run(*effect_case['paths'])


def test_artifact_requires_exact_bound_hash(tmp_path):
    p=tmp_path/'target.rtr'; p.write_text('current')
    with pytest.raises(ValueError,match='identity differs'):
        tool.artifact(tmp_path/'result.json',{'Artifacts':{'target.rtr':'stale'}},p.name,{})


def test_conflicting_watch_never_replaces_previous_evidence(tmp_path):
    p=tmp_path/'proof.json'; p.write_text('before')
    watched={}; tool.watch(watched,p)
    previous=dict(watched); p.write_text('after')
    with pytest.raises(ValueError,match='changed during verification'):tool.watch(watched,p)
    assert watched==previous
