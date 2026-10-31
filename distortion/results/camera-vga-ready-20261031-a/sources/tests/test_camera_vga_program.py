import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import prepare_camera_vga_program as program
import execute_camera_vga_program as executor


@pytest.fixture
def isolated(tmp_path,monkeypatch):
    monkeypatch.setattr(program.bit,'PROJECT',tmp_path)
    helper=tmp_path/'tool.py';helper.write_text('audit evidence')
    source=tmp_path/'input.adf';source.write_text('candidate')
    common={'HardwareReleaseAllowed':False,'HardwareAccessed':False,
            'InputSHA256':{str(source):program.bit.sha(source)},
            'ToolSHA256':{str(helper):program.bit.sha(helper)}}
    return tmp_path,common


def cdc(common):
    return {**common,'Schema':'camera-vga-cdc-structural-v1','AuditPassed':True,
            'CandidateADFSHA256':program.bit.ADF_SHA,'Summary':{'GrayBits':10,'ScalarChains':3,'ResetChains':2},
            'Scope':{'NativeInterstageTimingComplete':True,'GrayDatapathBoundComplete':True,
                     'AnalogMTBFProven':False,'AllCDCUniversallyProven':False}}


def pins(common):
    return {**common,'Schema':'camera-vga-io-evidence-v1','AuditCompleted':True,
            'CandidateADF':{'SHA256':program.bit.ADF_SHA},
            'Pins':{'DeclarationAndSourceBuildMappingPassed':True,'FinalFunctionalPadSiteMappingPassed':True,
                    'FinalNativeElectricalAttributesVerified':False},
            'TX':{'ExternalTimingAccepted':False},'DVP':{'ExternalTimingAccepted':False}}


def save(root,value):
    path=root/'proof.json';path.write_text(json.dumps(value));return path


def test_complete_native_cdc_is_bound_without_promoting_analog_claims(isolated):
    root,common=isolated;entry,bound=program.evidence(save(root,cdc(common)),'cdc')
    assert entry['Scope']['StructuralAuditPassed']
    assert entry['Scope']['NativeInterstageTimingComplete']
    assert entry['Scope']['GrayDatapathBoundComplete']
    assert not entry['Scope']['AllCDCUniversallyProven']
    assert len(bound)==3


@pytest.mark.parametrize('field',['NativeInterstageTimingComplete','GrayDatapathBoundComplete'])
def test_incomplete_native_cdc_cannot_prepare_final_sram_plan(isolated,field):
    root,common=isolated;value=cdc(common);value['Scope'][field]=False
    with pytest.raises(ValueError,match='complete native interstage'):
        program.evidence(save(root,value),'cdc')


def test_pin_mapping_is_bound_without_external_ac_claim(isolated):
    root,common=isolated;entry,_=program.evidence(save(root,pins(common)),'pin')
    assert entry['Scope']['PinMappingsPassed']
    assert not entry['Scope']['FinalNativeElectricalAttributesVerified']
    assert not entry['Scope']['TXExternalTimingAccepted']
    assert not entry['Scope']['DVPExternalTimingAccepted']


def test_evidence_drift_rejected(isolated):
    root,common=isolated;proof=save(root,cdc(common));(root/'tool.py').write_text('changed tool')
    with pytest.raises(ValueError,match='drift'):program.evidence(proof,'cdc')


def test_wrong_candidate_is_rejected(isolated):
    root,common=isolated;value=cdc(common);value['CandidateADFSHA256']='0'*64
    with pytest.raises(ValueError,match='CDC proof differs'):program.evidence(save(root,value),'cdc')


def test_missing_actual_pin_mapping_is_rejected(isolated):
    root,common=isolated;value=pins(common);value['Pins']['FinalFunctionalPadSiteMappingPassed']=False
    with pytest.raises(ValueError,match='pin mapping'):program.evidence(save(root,value),'pin')


@pytest.mark.parametrize('confirmation',[False,None,1,'yes'])
def test_new_power_confirmation_is_checked_before_any_validation_or_hardware(monkeypatch,confirmation):
    def touched(*args,**kwargs):raise AssertionError('must not reach hardware or offline plan validation')
    monkeypatch.setattr(executor,'validate',touched);monkeypatch.setattr(executor.hw,'listening_pids',touched)
    with pytest.raises(ValueError,match='new user-confirmed board power'):
        executor.execute(Path('missing-plan.json'),board_powered=confirmation)


@pytest.mark.parametrize('seconds',[float('nan'),float('inf'),0,301,True])
def test_invalid_timeout_rejected_before_plan_or_hardware(monkeypatch,seconds):
    monkeypatch.setattr(executor,'validate',lambda *args:pytest.fail('validation must not run'))
    with pytest.raises(ValueError,match='timeout'):
        executor.execute(Path('missing-plan.json'),board_powered=True,timeout_seconds=seconds)


def test_camera_recipe_is_only_sram_and_exact_bit_path():
    scripts=program.native._scripts({'bitstream_path':'D:/camera-final.sbit'},'1MHz')
    assert set(scripts)=={'scan','program'}
    assert 'D:/camera-final.sbit' in scripts['program']
    assert 'cfg_program -device_index 0' in scripts['program']
    assert 'cfg_read_device_property -mode 3' in scripts['program']
    assert all('flash' not in value.lower() for value in scripts.values())
