"""C reset separation rejects raw arbiter release without a vendor assumption."""
import copy
from pathlib import Path
import sys
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import hdmi_camera_fisheye_tile8_startup as s


def compiled(role):
    return (s.build.WORK/'build-a/compiled'/s.protocol.CONTRACTS[role]['Source']).read_text(encoding='utf-8-sig')


def test_actual_c_source_contract_uses_local_core_reset_only_for_arbiter_and_contract():
    plan=s.build.read(s.build.WORK/'build-a/plan.json');value=s.source_contracts(plan,s.build.WORK/'build-c',{})
    assert value['Passed']is True and value['SourceOnly']is True
    assert value['SharedWritesReset']=='system/core_reset_sync[1]'
    assert value['ContractCheckerReset']=='system/core_reset_sync[1]'
    assert value['WREADYNotAssumedConstant']is True
    assert value['BResetValueIdleInvariantNotUsed']is True
    assert value['ActualNativeTwoStageReleaseAndEveryConsumerCofactorRequired']is True


@pytest.mark.parametrize('role,old,new',[
    ('Link','.rst_n(core_rst_n)','.rst_n(rst_n)'),
    ('Link','if(!core_rst_n)contract_failed<=0;','if(!rst_n)contract_failed<=0;'),
    ('Link','.rst_n(rst_n),.enable(enable && !failed)','.rst_n(core_rst_n),.enable(enable && !failed)'),
    ('System','.core_rst_n(cr)','.core_rst_n(rst_n)')])
def test_changing_arbiter_contract_dma_or_parent_reset_breaks_frozen_contract(role,old,new):
    text=compiled(role)
    assert old in text
    with pytest.raises(ValueError):s.protocol.contract(role,text.replace(old,new,1))


def test_b_raw_link_cannot_be_substituted_for_c_source():
    old=(s.build.ROOT/'rtl/experimental/hdmi1080_input_write_link.v').read_text()
    with pytest.raises(ValueError):s.protocol.contract('Link',old)


@pytest.mark.parametrize('change',['clock','polarity','extra_assignment'])
def test_two_stage_release_clock_reset_and_all_assignments_are_bound(change):
    text=compiled('System')
    if change=='clock':text=text.replace('posedge core_clk','posedge pix_out_clk')
    elif change=='polarity':text=text.replace('negedge rst_n','posedge rst_n')
    else:text+='\nalways @(posedge core_clk)core_reset_sync<=2\'b11;'
    with pytest.raises(ValueError):s.release_source(text,'core_reset_sync','core_clk','rst_n')


def test_source_contract_does_not_claim_native_guard_or_timing():
    value,watched=s.review_sources(s.build.WORK/'build-a/plan.json')
    assert value['SourceOnly']is True and value['NativeGuardEvidenceProduced']is False
    assert value['TimingOrHardwareReleaseAuthorized']is False
    assert str(s.SELF)in value['InputSHA256']
