"""Pure CPU action-model tests; no artifact fixtures, directories or hardware."""
from pathlib import Path
from fractions import Fraction
import sys

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import ov5640_clock_sequence_audit as audit


def codes(result):
    return {item['code'] for item in result['errors']}


def write_index(actions,address,value):
    return next(i for i,item in enumerate(actions) if item['op'] in ('write','rmw') and
                item['address']==address and item['value']==value)


def test_reviewed_static_states_match_independent_arithmetic():
    actions=audit.proposed_actions();result=audit.audit_sequence(actions)
    assert result['static_model_passed'] is True
    changed=[item for item in result['trace'] if item.get('upper_VCO_model_hz') is not None]
    assert [item['upper_VCO_model_hz'] for item in changed]==[472500000,378000000,756000000]
    independently=[Fraction(27_000_000*105,6),Fraction(27_000_000*84,6),Fraction(27_000_000*84,3)]
    assert [Fraction(item['upper_VCO_model_hz']) for item in changed]==independently
    final=result['final_clock_model_if_all_declared_read_checks_succeed']
    assert final['VCO_nominal_hz']==672000000 and final['VCO_upper_hz']==756000000
    assert final['PCLK_nominal_hz']==42000000 and final['PCLK_upper_hz']==47250000
    assert actions==audit.proposed_actions()  # Auditor does not mutate its input.


def test_legacy_mult96_tail_is_rejected_even_though_final_map_matches():
    bad=audit.audit_sequence(audit.legacy_tail_counterexample())
    assert bad['static_model_passed'] is False
    assert 'VCO_EXCEEDS_LOCAL_LIMIT' in codes(bad)
    assert any(item.get('upper_VCO_model_hz')==864000000 for item in bad['trace'])
    assert bad['final_clock_model_if_all_declared_read_checks_succeed']==audit.audit_sequence(
        audit.proposed_actions())['final_clock_model_if_all_declared_read_checks_succeed']


def test_final_pre3_before_mult84_does_not_hide945mhz_with_root2():
    actions=audit.proposed_actions()
    i=write_index(actions,0x3037,0x16)
    actions[i]['value']=0x13;actions[i+1]['expected']=0x13
    bad=audit.audit_sequence(actions)
    assert {'FINAL_PREDIV_ORDER','VCO_EXCEEDS_LOCAL_LIMIT'}.issubset(codes(bad))
    assert any(item.get('upper_VCO_model_hz')==945000000 for item in bad['trace'])


def test_nominal24_alone_does_not_pass_a27mhz_upper_bound_claim():
    actions=audit.legacy_tail_counterexample()
    nominal_only=audit.audit_sequence(actions,upper_xvclk_hz=24_000_000)
    assert 'VCO_EXCEEDS_LOCAL_LIMIT' not in codes(nominal_only)
    assert 'VCO_EXCEEDS_LOCAL_LIMIT' in codes(audit.audit_sequence(actions))
    assert nominal_only['static_model_passed'] is False  # Ordering remains independently invalid.


def test_later_reset_and_good_final_tree_cannot_erase_prior_excess():
    earlier=audit.legacy_tail_counterexample()[:11]
    r=audit.audit_sequence(earlier+audit.proposed_actions())
    assert r['static_model_passed'] is False and 'VCO_EXCEEDS_LOCAL_LIMIT' in codes(r)
    assert len(r['unknown_intervals'])==2
    assert r['final_clock_model_if_all_declared_read_checks_succeed'] is not None


def test_low_vco_usability_and_all_analog_actions_remain_unverified():
    r=audit.audit_sequence(audit.proposed_actions());low=r['low_VCO_model_caveat']
    assert [x['upper_VCO_model_hz'] for x in low['static_changed_states_below_inferred_lower_at_upper_input']]==[472500000,378000000]
    assert low['local_minimum_usable_VCO_guaranteed_hz'] is None
    assert low['Linux_inference_is_guaranteed_local_spec'] is False
    assert low['low_VCO_usability_or_lock_verified'] is False
    assert r['all_actions_analog_validated'] is False and r['hardware_release_allowed'] is False


@pytest.mark.parametrize('mutation',['no-reset','no-initial-mult-read','no-pre6-read',
    'no-final-read','PLL-selected-early','bypass-released-early','wrong-read-address','wrong-read-expected'])
def test_missing_or_reordered_actions_fail_closed(mutation):
    a=audit.proposed_actions()
    if mutation=='no-reset':a.pop(0)
    elif mutation=='no-initial-mult-read':a.pop(1)
    elif mutation=='no-pre6-read':a.pop(write_index(a,0x3037,0x16)+1)
    elif mutation=='no-final-read':a.pop()
    elif mutation=='PLL-selected-early':a[3]['value']=2;a[4]['expected']=2
    elif mutation=='bypass-released-early':a[7]['value']=0;a[8]['expected']=0
    elif mutation=='wrong-read-address':a[10]['address']=0x3036
    else:a[10]['expected']=0x13
    assert audit.audit_sequence(a)['static_model_passed'] is False


@pytest.mark.parametrize('address,mask',[(0x3103,0xff),(0x3039,0xff),(0x3037,0x0f),(0x3108,0x03)])
def test_wrong_masks_cannot_claim_debug_bits_or_omit_required_fields(address,mask):
    a=audit.proposed_actions();i=next(i for i,item in enumerate(a) if item['op']=='rmw' and item['address']==address)
    a[i]['mask']=mask;a[i+1]['mask']=mask
    assert 'WRONG_MASK' in codes(audit.audit_sequence(a))


def test_expected_reads_are_not_observed_reads_or_pll_lock_evidence():
    r=audit.audit_sequence(audit.proposed_actions())
    assert r['declared_read_check_count']>0 and r['supplied_observation_count']==0
    assert r['unknown_intervals'][0]['physical_VCO_before_control_proven'] is False
    assert r['unknown_intervals'][0]['reset_action']==0
    assert r['unknown_intervals'][0]['first_control_read_check_action']>0
    assert r['bypass_or_standby_proves_VCO_off'] is False
    assert r['PLL_lock_observed'] is None and r['PLL_settling_guarantee_source'] is None
    assert r['hardware_release_allowed'] is False and r['complete_720_initialization'] is False
    assert r['XVCLK_measured_hz'] is None


def test_matching_supplied_readbacks_remain_unverified_input():
    a=audit.proposed_actions()
    for item in a:
        if item['op']=='read_check':item['observed']=item['expected'];item['bus_error']=0
    r=audit.audit_sequence(a)
    assert r['static_model_passed'] and r['supplied_observation_count']==r['declared_read_check_count']
    assert r['observations_are_independently_verified_hardware'] is False
    assert r['hardware_release_allowed'] is False


@pytest.mark.parametrize('field,value,expected_code',[('observed',0,'OBSERVED_MISMATCH'),
    ('bus_error',1,'SCCB_READ_ERROR')])
def test_mismatch_or_nack_cannot_be_promoted_by_expected_values(field,value,expected_code):
    a=audit.proposed_actions();a[1]['observed']=a[1]['expected'];a[1][field]=value
    assert expected_code in codes(audit.audit_sequence(a))


def test_reserved_bit_preservation_uses_explicit_pre_read_not_a_masked_match():
    a=audit.proposed_actions();a[3]['pre_read']=0xb3;a[4]['observed']=0xb1
    good=audit.audit_sequence(a);assert good['static_model_passed']
    row=next(row for row in good['trace'] if row['action_index']==3)
    assert row['RMW_expected_full_written_byte_from_supplied_pre_read']==0xb1
    assert row['RMW_pre_read_evidence']=='supplied_unverified_observation'
    a[4]['observed']=0  # mask02 still matches, but reserved/debug bits were lost.
    bad=audit.audit_sequence(a)
    assert 'PRESERVED_BITS_MISMATCH' in codes(bad) and not bad['static_model_passed']


def test_wait_is_bounded_without_creating_lock_or_delay_guarantees():
    a=audit.proposed_actions();a.insert(10,{'op':'wait','cycles':123})
    r=audit.audit_sequence(a);assert r['static_model_passed']
    assert next(row for row in r['trace'] if row['op']=='wait')['wait_is_lock_evidence'] is False
    assert not any(item['op']=='wait' for item in audit.proposed_actions())
    a[10]['PLL_locked']=True
    with pytest.raises(ValueError):audit.audit_sequence(a)


@pytest.mark.parametrize('kwargs',[{'nominal_xvclk_hz':True},{'nominal_xvclk_hz':28_000_000},
    {'upper_xvclk_hz':23_000_000},{'upper_xvclk_hz':27_000_001}])
def test_input_bound_types_and_units_are_strict(kwargs):
    with pytest.raises(ValueError):audit.audit_sequence(audit.proposed_actions(),**kwargs)


@pytest.mark.parametrize('change',[{'mask':True},{'expected':'0x69'},{'observed':False},{'bus_error':-1}])
def test_register_fields_reject_ambiguous_types(change):
    a=audit.proposed_actions();a[1].update(change)
    with pytest.raises(ValueError):audit.audit_sequence(a)


def test_unknown_pll_reset_semantics_and_final_wake_are_not_generated():
    a=audit.proposed_actions()
    assert all(item.get('address')!=0x3102 for item in a)
    a[5]['value']=0;a[6]['expected']=0
    assert 'FINAL_WAKE_NOT_IMPLEMENTED' in codes(audit.audit_sequence(a))
    with pytest.raises(ValueError):audit.audit_sequence([{'op':'reset'},
        {'op':'rmw','address':0x3102,'mask':1,'value':1}])


def test_cli_cannot_create_an_unapproved_output_or_directory():
    path=audit.ROOT/'clock-audit-test-unapproved'/'report.json'
    with pytest.raises(SystemExit) as error:audit.main(['--output',str(path)])
    assert error.value.code==2 and not path.parent.exists()
