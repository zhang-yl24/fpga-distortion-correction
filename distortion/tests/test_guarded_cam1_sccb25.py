"""Offline SCCB270 clone/build gates; no hardware or real PDS is invoked."""
from pathlib import Path
import copy
import sys

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import prepare_guarded_cam1_sccb25 as prep
import build_guarded_cam1_sccb25 as builder


def test_exact_single_parameter_top_and_shared103():
    manifest=prep.verify_clone()
    assert len(manifest['source_files'])==107
    assert len(manifest['SCCBSpeedTrialVerification']['SharedSourceSHA256'])==103
    assert manifest['SCCBTrialContract']==prep.SCCB_TRIAL_CONTRACT
    assert manifest['GuardedControlContract']['build_tag']==0x52473125
    old=(prep.ROOT/f'board/{prep.ORIGINAL}.v').read_bytes()
    new=(prep.ROOT/f'board/{prep.TARGET}.v').read_bytes()
    restored=new.replace(prep.TARGET.encode(),prep.ORIGINAL.encode()).replace(b'52473125',b'52473101').replace(b',.I2C_QUARTER_CYCLES(270)',b'')
    assert restored==old
    for suffix in ('.fdc','-pins.json'):
        assert (prep.ROOT/f'board/{prep.TARGET}{suffix}').read_bytes()==(prep.ROOT/f'board/{prep.ORIGINAL}{suffix}').read_bytes()
    assert b".trial_pad_mask(16'h7ff0)" in new


@pytest.mark.parametrize('old,new',[(b'52473101',b'52473102'),
    (b'.DYNAMIC_PAD_MASK(1)',b'.DYNAMIC_PAD_MASK(0)'),
    (b"16'h7ff0",b"16'h00f0"),
    (b'ov5640_cadence_trial_init #',b'ov5640_colorbars_init #')])
def test_missing_reviewed_anchor_or_mask_cannot_be_silently_changed(old,new):
    data=(prep.ROOT/f'board/{prep.ORIGINAL}.v').read_bytes().replace(old,new)
    with pytest.raises(ValueError):prep.clone_top(data)


def test_duplicate_parameter_site_rejected():
    data=(prep.ROOT/f'board/{prep.ORIGINAL}.v').read_bytes()+b'\nov5640_cadence_trial_init #(.DYNAMIC_PAD_MASK(1))\n'
    with pytest.raises(ValueError):prep.clone_top(data)


def test_all_destinations_prechecked_before_any_write(tmp_path,monkeypatch):
    (tmp_path/'second').write_bytes(b'previous evidence')
    monkeypatch.setattr(prep,'ROOT',tmp_path)
    monkeypatch.setattr(prep,'expected_files',lambda:({'first':b'new','second':b'expected'},{}))
    with pytest.raises(ValueError,match='overwrite'):prep.prepare()
    assert not (tmp_path/'first').exists() and (tmp_path/'second').read_bytes()==b'previous evidence'


def test_default_builder_is_plan_only(tmp_path,monkeypatch):
    monkeypatch.setattr(builder,'APPROVED',tmp_path)
    monkeypatch.setattr(builder.subprocess,'Popen',lambda *a,**k:pytest.fail('default plan executed PDS'))
    plan=builder.run_build(tmp_path/'plan')
    assert plan['ExecuteBuild'] is False and plan['HardwareAccessed'] is False
    assert plan['SCCBTrialContract']==prep.SCCB_TRIAL_CONTRACT
    assert not (tmp_path/'plan/validated-build.json').exists()


def test_execute_requires_bus_and_pipeline_simulation_before_output(tmp_path,monkeypatch):
    monkeypatch.setattr(builder,'APPROVED',tmp_path)
    with pytest.raises(ValueError,match='SCCB270'):
        builder.run_build(tmp_path/'missing',execute=True)
    assert not (tmp_path/'missing').exists()


@pytest.mark.parametrize('value',[True,0,59,1801,float('nan'),float('inf')])
def test_timeout_strict_and_finite(tmp_path,value):
    with pytest.raises(ValueError,match='bound'):builder.run_build(tmp_path/'bound',timeout_seconds=value)


def test_parent_cam1_pipeline_alone_is_not_sccb_waveform_evidence():
    base=prep.load(prep.BASE_BUILD)
    with pytest.raises(ValueError,match='SCCB270'):
        prep.validate_simulation(base['SimulationEvidence'])


def test_contract_does_not_claim_frequency_measurement_or_fix():
    c=prep.SCCB_TRIAL_CONTRACT
    assert type(c['quarter_cycles']) is int and c['quarter_cycles']==270
    assert c['nominal_scl_hz']==c['input_clock_hz']//(4*c['quarter_cycles'])==25000
    assert c['nominal_frequency_only'] is True
    assert c['hardware_acceptance_inferred_from_parameter'] is False
    assert c['timeout_cycles']==1350000 and c['pad_mask']=='0x7FF0'
