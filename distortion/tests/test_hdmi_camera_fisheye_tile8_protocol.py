"""Narrow source contract and native cofactor regression; no EDA/hardware."""
import copy
from pathlib import Path
import sys
from types import SimpleNamespace
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import hdmi_camera_fisheye_tile8_protocol as p


@pytest.mark.parametrize('role',list(p.CONTRACTS))
def test_current_compiled_contract_binds_all_critical_uses_and_assignments(role):
    spec=p.CONTRACTS[role]
    text=(p.build.WORK/'build-a/compiled'/spec['Source']).read_text(encoding='utf-8-sig')
    value=p.contract(role,text)
    assert set(value['CompleteCriticalSignalUsesAndAssignments'])==set(spec['Signals'])
    with pytest.raises(ValueError,match='unreviewed complete source'):
        p.contract(role,text+'\nwire unreviewed_business_change=1;\n')


def test_scan_ack_cannot_be_changed_to_release_the_lease():
    spec=p.CONTRACTS['System'];text=(p.build.WORK/'build-a/compiled'/spec['Source']).read_text()
    changed=text.replace('response_busy<=0;','response_busy<=0;lease_active<=0;',1)
    with pytest.raises(ValueError):p.contract('System',changed)


def test_all_twelve_tail_predicates_are_required_without_native_fsm_claim():
    proof=p.release_gate_proof()
    assert len(proof['Predicates'])==12 and proof['AssignmentsChecked']==4096
    assert proof['GrantACKDoesNotReleaseScanLease']is True
    assert proof['NativeFSMInductionClaimed']is False


def test_boolean_overapproximation_never_uses_lost_correlation_as_proof():
    x=('variable','x');xor=('lut',6,(x,x))
    assert p.possible(xor,{})=={0,1}
    assert p.possible(xor,{'x':1})=={0}
    assert p.possible(('mux',('constant',0),x,('constant',0)),{})=={0}


def fault_graph():
    v=lambda n:('variable','ff:'+n)
    c=lambda n:('constant',n)
    expressions={'board_failed':v('sticky'),'ref_reset[1]':v('release'),'power_ready':v('power')}
    expressions.update({f'system/system_fault[{i}]':v('fault'+str(i))for i in (5,7)})
    # SR = !(reset_n && power), local release synchronously drives sticky D.
    sr=('lut',7,(('variable','primary:reset_n'),v('power')))
    expressions.update({'sticky_d':v('release'),'sticky_ce':('variable','event'),'sticky_sr':sr,
                        'fault_d':v('sticky'),'one':c(1),'zero':c(0)})
    parameters={'INIT':"1'b0",'GRS_EN':'"TRUE"','LRS_EN':'"TRUE"','SET_RESET':'"RESET"'}
    ff={'sticky':{'Primitive':'V_FFASYN','Parameters':parameters,
                  'Ports':{'D':'sticky_d','CE':'sticky_ce','SR':'sticky_sr','CK':'ref'}}}
    for i in (5,7):
        ff['fault'+str(i)]={'Primitive':'V_FFSYN','Parameters':dict(parameters),
                           'Ports':{'D':'fault_d','CE':'one','SR':'zero','CK':'core'}}
    return SimpleNamespace(expression=lambda n:expressions[n],ff=ff,expressions=expressions)


def test_sticky_board_failure_proves_same_common_reset_and_both_actual_consumers():
    value=p.native_fault_review(fault_graph())
    assert value['Passed']is True and len(value['CommonResetTruth'])==4
    assert value['ReleasedDConstant']==1
    assert [x['LogicalFaultBit']for x in value['NativeConsumerEvidence']]==[5,7]
    assert value['AbsentOptimizedBoardFaultBitFFInvented']is False


@pytest.mark.parametrize('change',['initial','grs','reset_priority','nonsticky','foreign_reset','missing_consumer'])
def test_changed_native_fault_semantics_are_rejected(change):
    g=fault_graph()
    if change=='initial':g.ff['sticky']['Parameters']['INIT']="1'b1"
    elif change=='grs':g.ff['sticky']['Parameters']['GRS_EN']='"FALSE"'
    elif change=='reset_priority':g.ff['sticky']['Parameters']['SET_RESET']='"SET"'
    elif change=='nonsticky':g.expressions['sticky_d']=('constant',0)
    elif change=='foreign_reset':g.expressions['sticky_sr']=('variable','primary:other_reset')
    else:g.expressions['fault_d']=('constant',1)
    with pytest.raises(ValueError):p.native_fault_review(g)


def test_missing_or_changed_saved_review_cannot_verify(monkeypatch,tmp_path):
    path=tmp_path/'review.json';saved={'Schema':p.SCHEMA,'Target':p.build.TARGET,
        'BuildPlan':{'Path':'plan'},'ExportReceipt':{'Path':'export'},'Passed':True}
    p.build.write(path,saved)
    monkeypatch.setattr(p,'review',lambda *args:({**saved,'Passed':False},{}))
    with pytest.raises(ValueError,match='complete recomputation'):p.verify(path)


def test_native_expression_json_roundtrip_remains_exactly_verifiable(monkeypatch,tmp_path):
    path=tmp_path/'review.json';raw={'Schema':p.SCHEMA,'Target':p.build.TARGET,
        'BuildPlan':{'Path':'plan'},'ExportReceipt':{'Path':'export'},'Passed':True,
        'NativeExpression':('lut',6,(('variable','x'),('variable','y')))}
    p.build.write(path,raw)
    monkeypatch.setattr(p,'review',lambda *args:(p.canonical_value(raw),{}))
    value,watched=p.verify(path)
    assert value==p.build.read(path) and watched[path]==p.build.sha(path)
    with pytest.raises(ValueError):p.canonical_value({'NonFinite':float('nan')})


@pytest.fixture(scope='module')
def actual_mode_graph():
    net=p.build.WORK/'export-a/generate_netlist/hdmi_camera_fisheye_top_sim.v'
    receipt=p.build.WORK/'export-a/result.json'
    if not receipt.is_file():pytest.skip('completed actual tile8 export required; active files are not read')
    result=p.build.read(receipt)
    assert result['ExecutionPassed'] is True
    assert p.build.sha(net)==result['Artifacts']['generate_netlist/hdmi_camera_fisheye_top_sim.v']
    top=p.build.WORK/'build-a/compiled'/p.build.TOP
    return p.mode_graph(net.read_text(encoding='gb18030',errors='strict'),
                        p.build.top_ports(top.read_text(encoding='utf-8-sig')))


def test_actual_mode_data_and_all_twenty_three_native_valid_ce_vetoes(actual_mode_graph):
    value=p.native_mode_review(actual_mode_graph)
    assert value['Passed']is True and len(value['Actual23ValidStageVetoes'])==23
    assert value['AbsentProcessingLogicalNetPolarityInvented']is False
    assert value['Actual23ValidStageVetoes'][-1]['ActualNet'].endswith('/mapped_valid')


@pytest.mark.parametrize('pin,value',[('D',"1'b0"),('CE',"1'b1"),('CK','unrelated_clock')])
def test_actual_mode_source_enable_or_clock_mutation_is_rejected(actual_mode_graph,pin,value):
    ff,_=p.logical(actual_mode_graph,'system/bank_core/engine/core/mapper/corrected')
    ports=actual_mode_graph.ff[ff]['Ports'];old=ports[pin]
    try:
        ports[pin]=value
        with pytest.raises(ValueError):p.native_mode_review(actual_mode_graph)
    finally:ports[pin]=old
