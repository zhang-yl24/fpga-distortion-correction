"""Precise final native warning/site/interstage query boundaries."""
from pathlib import Path
import sys

import pytest

sys.path.insert(0,str(Path('D:\\GravityLRT\\thu\\semester_4.5\\FPGAchina\\fpga-distortion-correction\\distortion')/'tools'))
import hdmi_camera_fisheye_tile8df8v3_physical_checks as checks


@pytest.mark.parametrize('change',['file_drift','missing_file','caller_mutation','different_scope'])
def test_cpu_inventory_cache_rehashes_every_dependency_and_does_not_cache_receipt_checks(tmp_path,monkeypatch,change):
    dependency=tmp_path/'native.v';dependency.write_text('bound graph');calls=[]
    def derive(scope):
        calls.append(scope.copy());return {'Pins':{'PinInventory':[{'Site':'actual'}]}},{dependency:checks.sha(dependency)}
    monkeypatch.setattr(checks,'_inventory',derive)
    scope={'UniqueCase':str(tmp_path),'ExactChain':'first'}
    value,watched=checks.inventory(scope);value['Pins']['PinInventory'].clear();watched.clear()
    if change=='file_drift':dependency.write_text('changed')
    elif change=='missing_file':dependency.unlink()
    elif change=='different_scope':scope['ExactChain']='second'
    if change in('file_drift','missing_file'):
        with pytest.raises(ValueError,match='inventory input drift'):checks.inventory(scope)
    else:
        value,watched=checks.inventory(scope)
        assert value['Pins']['PinInventory']==[{'Site':'actual'}]and dependency in watched
        assert len(calls)==(2 if change=='different_scope'else 1)


def test_current_sites_and_exact_ordinary_interstage_queries_fit_bounded_native_body():
    current={'Pins':{'PinInventory':[{'Site':'IOB_'+str(n)} for n in range(69)]},
        'InterstageQueries':[{'FromCLK':'actual'+str(n)+'/CLK','LaunchQ':'actual'+str(n)+'/Q',
            'Endpoint':'target'+str(n)+'/D'} for n in range(10)]}
    bodies=checks.query_bodies(current)
    assert len(bodies)==2 and sum(len(checks.baseline.query_commands(body))for body in bodies)==89
    assert all(sum(line.startswith('report_path_timing ')for line in body.splitlines())<=8 for body in bodies)
    assert sum(line.startswith('show ')for body in bodies for line in body.splitlines())==69
    assert '-through {t:actual0/Q}' in bodies[0] and 'set_false_path' not in bodies[0]


@pytest.fixture
def warning_context(tmp_path,monkeypatch):
    build=tmp_path/'build';(build/'place_route').mkdir(parents=True)
    for n in ('run_route_optimize.log','run_route.log','run_place.log'):(build/'place_route'/n).write_text('original bound route')
    stage=tmp_path/'export';stage.mkdir();receipt=stage/'result.json';receipt.write_text('bound receipt')
    scope={'BuildPlan':{'Path':str(build/'plan.json')},'Pins':{'Inventory':[{'Port':'bidirectional[0]','Direction':'INOUT'},
        {'Port':'input_only','Direction':'INPUT'},{'Port':'output_only','Direction':'OUTPUT'}]}}
    value={'Mode':'export','RepoAlias':'P:/','Artifacts':{}}
    monkeypatch.setattr(checks.build.paths,'alias_path',lambda project,alias,path:alias+Path(path).relative_to(tmp_path).as_posix())
    log=stage/'stdout.log'
    return scope,[(receipt,value)],log


def test_only_actual_declared_port_directions_accept_external_ac_warning(warning_context):
    scope,receipts,log=warning_context
    log.write_text("W: Timing-4086: Port 'bidirectional[0]' is not constrained, it is treated as combinational input.\n"
        "W: Timing-4087: Port 'bidirectional[0]' is not constrained, it is treated as combinational output.\n")
    value=checks.warning_review(scope,receipts,{})
    assert value['Passed'] and len(value['Warnings'])==2 and not value['ExternalACAccepted']


@pytest.mark.parametrize('message',[
    "W: Timing-4086: Port 'unknown' is not constrained, it is treated as combinational input.",
    "W: Timing-4087: Port 'input_only' is not constrained, it is treated as combinational output.",
    "W: Timing-4086: Port 'input_only' is not constrained, it is treated as combinational output.",
    'W: Sdm-3003: source diagnostic repeated at wrong stage',
    'W: Other-001: unexpected warning',
    'W: Failed to open file P:/another-stage/place_route/run_route.log',
    'W: Failed to open file P:/export/place_route/another.log'])
def test_unknown_codes_ports_directions_or_missing_files_are_rejected(warning_context,message):
    scope,receipts,log=warning_context;log.write_text(message+'\n')
    with pytest.raises(ValueError):checks.warning_review(scope,receipts,{})


def test_only_three_absent_own_export_companions_are_recorded_as_unneeded(warning_context):
    scope,receipts,log=warning_context
    log.write_text(''.join('W: Failed to open file P:/export/place_route/'+name+'\n'
        for name in ('run_route_optimize.log','run_route.log','run_place.log')))
    value=checks.warning_review(scope,receipts,{})
    assert value['Counts']=={'MissingStandaloneRouteCompanion':3}
    (log.parent/'place_route').mkdir();(log.parent/'place_route/run_route.log').write_text('unexpected actual file')
    with pytest.raises(ValueError):checks.warning_review(scope,receipts,{})



def matrix_fixture():
    queries=[{'FromCLK':'first%d/CLK'%i,'LaunchQ':'first%d/Q'%i,'Endpoint':'second%d/D'%i}for i in range(13)]
    launches={'first%d/Q'%i:'functional%d/FF'%i for i in range(13)}
    support={'second%d/D'%i:{'FunctionalBoundaryNet':'functional%d/D'%i,'NativeBoundaryNet':'actual%d/D'%i,
        'SupportFFs':['functional%d/FF'%i,'localrelease/FF'],'CompleteNativeBoundarySupportVerified':True}for i in range(13)}
    return queries,support,launches


def test_one_read_only_interstage_batch_preserves_complete_native_support_and_all13_case_obligations():
    queries,support,launches=matrix_fixture();matrix=checks.interstage_matrix(queries,support,launches)
    body=checks.query_bodies({'Pins':{'PinInventory':[{'Site':'IOB_%d'%i}for i in range(144)]},
        'InterstageQueries':queries,'InterstageReadOnlyMatrix':matrix})
    assert len(body)==1 and body[0].count('report_path_timing ')==1
    assert '-max_path 10000 -nworst 8 -report_exception TRUE'in body[0]
    assert all('t:'+row[key]in body[0]for row in queries for key in('FromCLK','LaunchQ','Endpoint'))
    assert len(matrix['AllowedPairs'])==13 and matrix['NoTimingExceptionApplied']is True
    assert matrix['RequiredDualCornerSetupHoldEnumerationComplete']is False


@pytest.mark.parametrize('change',['missing_support','opaque_support','unlisted_crosspair','omitted_source','conflicting_source','duplicate_pair'])
def test_batched_interstage_rejects_incomplete_or_extra_native_source_endpoint_pairs(change):
    queries,support,launches=matrix_fixture()
    if change=='missing_support':support.pop('second0/D')
    elif change=='opaque_support':support['second0/D']['CompleteNativeBoundarySupportVerified']=False
    elif change=='unlisted_crosspair':support['second0/D']['SupportFFs'].insert(0,'functional1/FF')
    elif change=='omitted_source':launches.pop('first0/Q')
    elif change=='conflicting_source':launches['first0/Q']='functional1/FF'
    else:queries.append(dict(queries[0]))
    with pytest.raises(ValueError):checks.interstage_matrix(queries,support,launches)
