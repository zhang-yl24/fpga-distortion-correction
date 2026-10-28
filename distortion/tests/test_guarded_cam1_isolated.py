"""Local artifact-backed isolated clone gates; no PDS, UART or JTAG calls."""
from pathlib import Path
import re
import sys

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import prepare_guarded_cam1_isolated as prep
import build_guarded_cam1_isolated as builder


def test_actual_top_only_identity_port_and_constant_sink_change():
    manifest=prep.verify_clone()
    assert len(manifest['source_files'])==107
    assert len(manifest['OtherSensorResetTrialVerification']['SharedSourceSHA256'])==103
    assert manifest['GuardedControlContract']['build_tag']==0x52473149
    old=(prep.ROOT/f'board/{prep.ORIGINAL}.v').read_bytes()
    new=(prep.ROOT/f'board/{prep.TARGET}.v').read_bytes()
    restored=new.replace(prep.TARGET.encode(),prep.ORIGINAL.encode()).replace(b'52473149',b'52473101')
    restored=restored.replace(b'cam_sda,cam2_hold_rst_n,',b'cam_sda,').replace(prep.HOLD_ASSIGNMENT,b'')
    assert restored==old
    assert new.count(b'cam2_hold_rst_n')==2 and new.count(prep.HOLD_ASSIGNMENT)==1
    assert b'I2C_QUARTER_CYCLES' not in new
    assert b".trial_pad_mask(16'h7ff0)" in new


def test_original129_unchanged_and_new_y20_is_unique():
    old=prep.load(prep.ROOT/f'board/{prep.ORIGINAL}-pins.json')
    new=prep.load(prep.ROOT/f'board/{prep.TARGET}-pins.json')
    assert len(new)==len(set(new.values()))==130
    assert {k:v for k,v in new.items() if k!='cam2_hold_rst_n'}==old
    assert new['cam2_hold_rst_n']=='Y20' and new['cam_rst_n']=='T20'
    old_fdc=(prep.ROOT/f'board/{prep.ORIGINAL}.fdc').read_bytes()
    new_fdc=(prep.ROOT/f'board/{prep.TARGET}.fdc').read_bytes()
    assert new_fdc==old_fdc+b'\r\n'+prep.reset_attributes()
    locs=re.findall(rb'define_attribute \{p:([^}]+)\} \{PAP_IO_LOC\} \{([^}]+)\}',new_fdc)
    assert len(locs)==130 and len({x[0] for x in locs})==len({x[1] for x in locs})==130


@pytest.mark.parametrize('old,new',[(b'52473101',b'52473102'),
    (b'.DYNAMIC_PAD_MASK(1)',b'.DYNAMIC_PAD_MASK(0)'),
    (b"16'h7ff0",b"16'h00f0"),(b'cam_rst_n,cam_scl,cam_sda,',b'cam_rst_n,cam_scl,cam_sda,cam2_hold_rst_n,'),
    (b'ov5640_cadence_trial_init #',b'ov5640_colorbars_init #')])
def test_parent_anchor_or_unchanged_init_policy_cannot_drift(old,new):
    data=(prep.ROOT/f'board/{prep.ORIGINAL}.v').read_bytes().replace(old,new)
    with pytest.raises(ValueError):prep.clone_top(data)


def test_duplicate_sink_anchor_rejected():
    data=(prep.ROOT/f'board/{prep.ORIGINAL}.v').read_bytes()+b'\n    // Connector slot only; no physical left/right or stereo-sync claim.\r\n'
    with pytest.raises(ValueError):prep.clone_top(data)


def test_reference_hash_change_rejected(monkeypatch):
    original=prep.sha
    monkeypatch.setattr(prep,'sha',lambda p:'0'*64 if str(p).endswith('cam2_guarded-pins.json') else original(p))
    with pytest.raises(ValueError,match='reference changed'):prep.reset_attributes()


def test_all_destinations_prechecked_before_write(tmp_path,monkeypatch):
    (tmp_path/'second').write_bytes(b'old')
    monkeypatch.setattr(prep,'ROOT',tmp_path)
    monkeypatch.setattr(prep,'expected_files',lambda:({'first':b'new','second':b'expected'},{}))
    with pytest.raises(ValueError,match='overwrite'):prep.prepare()
    assert not (tmp_path/'first').exists() and (tmp_path/'second').read_bytes()==b'old'


def test_default_builder_plan_cannot_execute_pds(tmp_path,monkeypatch):
    monkeypatch.setattr(builder,'APPROVED',tmp_path)
    monkeypatch.setattr(builder.subprocess,'Popen',lambda *a,**k:pytest.fail('default plan executed PDS'))
    plan=builder.run_build(tmp_path/'plan')
    assert plan['ExecuteBuild'] is False and plan['NoFlashOrProgrammingOperation'] is True
    assert plan['OtherSensorResetTrialContract']==prep.OTHER_SENSOR_RESET_TRIAL_CONTRACT
    assert not (tmp_path/'plan/validated-build.json').exists()


def test_execute_requires_actual_top_lifecycle_and_pipeline(tmp_path,monkeypatch):
    monkeypatch.setattr(builder,'APPROVED',tmp_path)
    with pytest.raises(ValueError,match='constant-sink actual-board lifecycle'):
        builder.run_build(tmp_path/'missing',execute=True)
    assert not (tmp_path/'missing').exists()


@pytest.mark.parametrize('value',[True,0,59,1801,float('nan'),float('inf')])
def test_finite_strict_builder_bound(value,tmp_path):
    with pytest.raises(ValueError,match='bound'):builder.run_build(tmp_path/'bad',timeout_seconds=value)


def test_parent_pipeline_is_not_new_top_lifecycle_evidence():
    parent=prep.load(prep.BASE_BUILD)
    with pytest.raises(ValueError,match='constant-sink lifecycle'):
        prep.validate_simulation(parent['SimulationEvidence'])


def test_testbench_instantiates_actual_board_not_sink_projection():
    tb=(prep.ROOT/'tests/tb_cam1_isolated_init.sv').read_text()
    assert prep.TARGET+' dut(' in tb
    assert 'assign cam2_hold_rst_n' not in tb
    assert 'clock_enabled=0' in tb and 'force dut.power_count' in tb
    stubs=(prep.ROOT/'tests/cam1_isolated_board_stubs.v').read_text()
    assert prep.TARGET not in stubs and 'ov5640_cadence_trial_init' not in stubs


def test_contract_retains_unmeasured_boundaries():
    c=prep.OTHER_SENSOR_RESET_TRIAL_CONTRACT
    assert c['drives_high'] is False and c['released_during_configured_run'] is False
    assert c['physical_reset_independence_verified'] is False
    assert c['other_sensor_inactivity_verified'] is False and c['hardware_fix_or_cause_established'] is False
    assert c['before_configuration_and_after_heartbeat_hold_guaranteed'] is False
    assert type(c['active_camera_quarter_cycles']) is int and c['active_camera_quarter_cycles']==68


@pytest.mark.parametrize('mode',['missing','wrong-pad','wrong-direction','duplicate'])
def test_routed_pin_failures_rejected(mode,tmp_path):
    parent=prep.load(prep.BASE_BUILD)
    lines=Path(parent['PinReport']).read_text().splitlines()
    for i,line in enumerate(lines):
        fields=line.split('|')
        if len(fields)>=7 and fields[0]=='Y20':
            fields[4:7]=['cam2_hold_rst_n','inout','YES']
            if mode=='missing':fields[4:7]=['','','']
            elif mode=='wrong-pad':fields[0]='Y21'
            elif mode=='wrong-direction':fields[5]='output'
            lines[i]='|'.join(fields)
            if mode=='duplicate':lines.append(lines[i])
            break
    path=tmp_path/'route.prt';path.write_text('\n'.join(lines))
    with pytest.raises(ValueError):builder.validate_pins(path)
