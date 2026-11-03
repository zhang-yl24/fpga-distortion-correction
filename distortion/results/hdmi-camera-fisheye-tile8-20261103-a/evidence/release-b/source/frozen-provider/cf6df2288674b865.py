"""R3S3 own graph startup witness, functional negative cases and strict routed margin."""
from pathlib import Path
import sys
import pytest
sys.path.insert(0,str(Path('D:\\GravityLRT\\thu\\semester_4.5\\FPGAchina\\fpga-distortion-correction\\distortion')/'tools'))
import hdmi_camera_fisheye_fill8r3s3_vendor_startup_bounded_b as p


@pytest.fixture(scope='module')
def g():
    fw=p.build.ROOT/'work/hdmi-camera-fisheye-fill8r3s3-20261103-a'
    return p.Graph((fw/'export-a/generate_netlist/hdmi_camera_fisheye_top_sim.v').read_text(encoding='gb18030'),
                   p.build.top_ports((fw/'build-a/compiled'/p.build.TOP).read_text(encoding='utf-8-sig')))


def test_actual_four_ff_sequence_holds_core_pll_reset_for_three_intervals(g):
    value=p.finite_sequence(g)
    assert value['NominalMinimumStartupWindowNS']==24.0
    assert all(row['After']['CorePLLRST']==[1]for row in value['Rows'][:3])
    assert value['Rows'][3]['After']['CorePLLRST']==[0,1]
    assert value['OtherLockCounterOrFSMStatesFixed']is False


@pytest.mark.parametrize('name,pin,mutated',[
    ('Second','D',"1'b1"),('State0','SR',"1'b0"),('CorePLLRST','D',"1'b0")])
def test_shortened_native_startup_pipeline_is_rejected(g,name,pin,mutated):
    ports=g.ff[p.sequence(g)[name]]['Ports'];old=ports[pin]
    try:
        ports[pin]=mutated
        with pytest.raises(ValueError):p.finite_sequence(g)
    finally:ports[pin]=old


def test_warm_async_establishment_does_not_borrow_init_or_clock(g):
    n=p.sequence(g)['Second'];cell=g.ff[n];old=cell['Primitive']
    try:
        cell['Primitive']='V_FFSYN'
        with pytest.raises(ValueError,match='warm common reset'):p.finite_sequence(g)
    finally:cell['Primitive']=old


def test_official_model_and_actual_pll_rst_have_bound_functional_contract(g):
    value=p.primitive_contract(g,{})
    assert value['Passed']is True and value['ResetAssertedForcesCLKOUT0Low']is True
    assert value['SimulationInternalThreeGateCyclesUsedAsSiliconDelay']is False
    ports=g.cells[p.CORE_PLL]['Ports'];old=ports['RST']
    try:
        ports['RST']="1'b0"
        with pytest.raises(ValueError,match='proved active-high|logical role lacks one native FF'):p.primitive_contract(g,{})
    finally:ports['RST']=old


def good_timing():
    return {'Schema':'hdmi-camera-fisheye-fill8r3s3-vendor-startup-paths-v1','MaximumRequiredNS':2.789,
            'CompleteActualResetPathCoverage':True,'Missing':[],'Violations':[]}


def test_all_reported_delay_terms_must_fit_the_finite_window():
    accepted,maximum,margin=p.timing_acceptance(good_timing())
    assert accepted is True and maximum==2.789 and margin==pytest.approx(21.211)


@pytest.mark.parametrize('maximum',[24.0,24.001,-1,float('nan'),float('inf'),True,None])
def test_nonpositive_margin_or_invalid_delay_is_blocking(maximum):
    value=good_timing();value['MaximumRequiredNS']=maximum
    assert p.timing_acceptance(value)[0]is False


@pytest.mark.parametrize('field,value',[('CompleteActualResetPathCoverage',False),('Missing',['fast/removal']),
    ('Violations',['wrong_source']),('Schema','old_vendor_range_v1')])
def test_incomplete_or_wrong_native_report_cannot_be_replaced_by_small_slack(field,value):
    timing=good_timing();timing[field]=value
    assert p.timing_acceptance(timing)[0]is False


def test_all_actual_raw_reset_ff_sites_are_enumerated_not_only_violated_report_names(g):
    rows,pins,source=p.targets(g,(p.build.ROOT/'work/hdmi-camera-fisheye-fill8r3s3-20261103-a/route-a/route-dump.v').read_text(encoding='gb18030'))
    assert len(rows)==34
    expected_native_ffs={n for n in g.ff if n.startswith(p.PHASE)or n.startswith(p.DDRC)}
    assert len(expected_native_ffs)==34
    assert pins==sorted({g.placements[n]["Site"]+"/RS"for n in expected_native_ffs})
    assert len({row['FF']for row in rows})==34
    power,polarity=p.protocol.logical(g,'power_ready');assert polarity==[0,1]
    assert source['SourceFF']==power and source['SourceNativeOutputPin'].rsplit('/',1)[-1]in ('Q','L6Q','L5Q')
    assert source['SourcePhysicalQ'].startswith(g.placements[power]['Site']+'/')
    assert {row['FF']for row in rows}=={n for n in g.ff if n.startswith(p.PHASE)or n.startswith(p.DDRC)}
    assert all(row['ActualClock']['Root']==p.CORE_PLL+'/CLKOUT0'for row in rows)
    assert any(row['ActualEnable']!="1'b1"for row in rows)


def test_sequence_uses_current_graph_roles_instead_of_old_packed_slot(g):
    selected=p.sequence(g)
    assert len(set(selected.values()))==4
    role, truth = p.protocol.logical(g, p.SEQUENCE_SIGNALS['CorePLLRST'])
    assert truth == [0, 1] and selected['CorePLLRST'] == role
    witness=p.finite_sequence(g)
    assert witness['SequenceFFs']==selected and 'no packed FF slot or query alias'in witness['SequenceIdentityBasis']
    assert witness['NominalMinimumStartupWindowNS']==24.0


@pytest.mark.parametrize('role',['Second','State0','CorePLLRST'])
def test_an_inverted_named_signal_cannot_silently_change_the_startup_encoding(g,role,monkeypatch):
    actual=g.expression
    signal=p.SEQUENCE_SIGNALS[role]
    def changed(value,active=()):
        expression=actual(value,active)
        return ('not',expression)if p.base.canon(value)==p.base.canon(signal)else expression
    monkeypatch.setattr(g,'expression',changed)
    with pytest.raises(ValueError,match='active-high'):p.sequence(g)


@pytest.mark.parametrize('mutation',['second_from_fsm','core_from_sync','pll_from_sync','wrong_clock'])
def test_current_graph_functional_roles_and_clock_cannot_be_replaced_by_native_names(g,mutation):
    selected=p.sequence(g)
    target=selected['Second']if mutation=='second_from_fsm'else selected['CorePLLRST']
    ports=g.ff[target]['Ports'];pin='D';replacement=g.ff[selected['Second']]['Ports']['Q']
    if mutation=='second_from_fsm':replacement=g.ff[selected['State0']]['Ports']['Q']
    elif mutation=='pll_from_sync':ports=g.cells[p.CORE_PLL]['Ports'];pin='RST'
    elif mutation=='wrong_clock':pin='CK';replacement='reset_n'
    old=ports[pin]
    try:
        ports[pin]=replacement
        with pytest.raises(ValueError):p.finite_sequence(g)
    finally:ports[pin]=old


def test_missing_unqueryable_logical_role_cannot_borrow_a_ff_slot(g,monkeypatch):
    monkeypatch.setitem(p.SEQUENCE_SIGNALS,'CorePLLRST','not_an_actual_design_signal')
    with pytest.raises(ValueError,match='unknown used startup leaf'):p.sequence(g)
