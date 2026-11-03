"""The provider revision must preserve original S3 inputs and close every new edge."""
from pathlib import Path
import importlib
import sys
import pytest
ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT.parent/'.venv/Lib/site-packages')]

def module(role):return importlib.import_module('hdmi_camera_fisheye_tile8df8v2_'+role)

def test_closed_revision_edges_and_original_shared_authorities():
    physical,scoped,target,checks,final,bit,program=[module(role)for role in(
        'physical','scoped_native','target_query','physical_checks','final','bitstream','program')]
    build=importlib.import_module('hdmi_camera_fisheye_tile8df8_build')
    raw=importlib.import_module('hdmi_camera_fisheye_tile8df8_native')
    audit=importlib.import_module('hdmi_camera_fisheye_tile8df8_audit')
    assert all(m.build is build for m in (physical,scoped,target,checks,final,bit))
    assert scoped.raw_native is raw
    assert physical.native is checks.native is checks.baseline is final.native is final.baseline is bit.native is scoped
    assert checks.physical is final.application is physical
    assert checks.audit is audit and program.bit is bit
    assert physical.AUDIT_SCHEMA=='hdmi-camera-fisheye-tile8df8-native-audit-v1'
    assert build.WORK.name=='hdmi-camera-fisheye-tile8df8-20261103-a'
    assert bit.SIMULATIONS['SystemSimulation']=='run_hdmi_camera_fisheye_tile8df8_system_sim'

def test_new_dispatch_rejects_frozen_old_scoped_schema(monkeypatch,tmp_path):
    scoped=module('scoped_native')
    monkeypatch.setattr(scoped,'read',lambda p:{'Schema':'hdmi-camera-fisheye-tile8df8-scoped-native-inspection-v1'})
    with pytest.raises(ValueError,match='exact own scoped-native schema'):
        scoped.bind_receipt(tmp_path/'result.json')

def test_raw_dispatch_uses_only_original_s3_raw_schema(monkeypatch,tmp_path):
    scoped=module('scoped_native');sentinel=object()
    monkeypatch.setattr(scoped,'read',lambda p:{'Schema':scoped.raw_native.SCHEMA})
    monkeypatch.setattr(scoped.raw_native,'bind_receipt',lambda p:sentinel)
    assert scoped.bind_receipt(tmp_path/'result.json')is sentinel

def test_new_bit_requires_new_final_proof_schema():
    bit=module('bitstream')
    with pytest.raises(ValueError,match='physical proof required'):
        bit.physical_flags({'Schema':'hdmi-camera-fisheye-tile8df8-final-physical-proof-v1','Target':bit.TARGET})
