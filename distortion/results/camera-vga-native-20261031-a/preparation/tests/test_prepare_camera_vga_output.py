"""Camera candidate pins/timing and isolation must survive targeted corruption."""
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import prepare_camera_vga_output as prep
import run_camera_vga_output_diagnostic as runner


@pytest.fixture(scope='module')
def base():
    return prep.base_manifest(prep.PROJECT)


def test_real_camera_pin_inventory_and_ddr_body(base):
    result = prep.audit_constraint(prep.PROJECT, prep.constraint_bytes(prep.PROJECT, base), base)
    assert (result['PackagePins'], result['CameraPins'], result['DDRPins']) == (128, 14, 71)
    assert result['ExternalIOAccepted'] is False
    assert prep.ddr_body_comparison(prep.PROJECT)['RawBytesIdentical'] is True


@pytest.mark.parametrize('old,new', [
    (b'{AA23}', b'{AA22}'),
    (b'camera_pclk -period 20.833', b'camera_pclk -period 40.0'),
    (b'-clock camera_pclk -max 5.0', b'-clock camera_pclk -max 0.0'),
    (b'{PAP_IO_LOC} {Y20}', b'{PAP_IO_LOC} {B24}'),
])
def test_reject_changed_physical_input_contract(base, old, new):
    data = prep.constraint_bytes(prep.PROJECT, base)
    assert old in data
    with pytest.raises(ValueError):
        prep.audit_constraint(prep.PROJECT, data.replace(old, new), base)


def test_reject_added_camera_clock_waiver(base):
    data = prep.constraint_bytes(prep.PROJECT, base)
    with pytest.raises(ValueError):
        prep.audit_constraint(prep.PROJECT, data + b'set_false_path -from [get_clocks camera_pclk]\n', base)


def test_new_closure_excludes_synthetic_and_hdmi_ingress(base):
    names = prep.derived_names(base)
    assert not prep.REMOVED & set(names)
    assert set(prep.ADDED) <= set(names)
    assert len(names) == len(set(names))
    assert 'rtl/experimental/dvp_rgb565_capture_cdc.v' in names
    assert 'platform/video_base/ipcore/ddr3_test/ddr3_test.idf' in names


def test_reject_changed_top_pin_direction(base, monkeypatch):
    source = (prep.PROJECT/prep.TOP).read_text()
    broken = source.replace('inout cam_rst_n,cam_scl,cam_sda,', 'output cam_rst_n,cam_scl,cam_sda,')
    assert broken != source
    ports = prep.top_ports(broken)
    monkeypatch.setattr(prep, 'top_ports', lambda _: ports)
    with pytest.raises(ValueError, match='direction differs'):
        prep.audit_constraint(prep.PROJECT, prep.constraint_bytes(prep.PROJECT, base), base)


def test_only_exact_scratch_roots_are_allowed():
    assert prep.work_parent_allowed(prep.PROJECT, prep.PROJECT/'build/camera-vga-output/pds-a')
    assert prep.work_parent_allowed(prep.PROJECT, prep.PROJECT/'work/camera-vga-output/pds-a')
    assert prep.work_parent_allowed(prep.PROJECT, prep.TEMP_BUILD/'pds-a')
    assert not prep.work_parent_allowed(prep.PROJECT, prep.TEMP_BUILD.parent/'unrelated/pds-a')
    assert not prep.work_parent_allowed(prep.PROJECT, prep.TEMP_BUILD/'nested/pds-a')
    assert not prep.work_parent_allowed(prep.PROJECT, prep.PROJECT/'build/processed-output/pds-a')
    assert not prep.work_parent_allowed(prep.PROJECT, prep.PROJECT/'work/camera-vga-output/nested/pds-a')
    assert not prep.work_parent_allowed(prep.PROJECT, prep.PROJECT/'work/unrelated/pds-a')
    assert not prep.work_parent_allowed(prep.PROJECT, prep.PROJECT/'work/camera-vga-output')


def test_direct_workspace_scratch_path_is_preserved():
    expected = prep.PROJECT/'work/camera-vga-output/pds-a/compiled/a.v'
    assert prep.recipe_path(prep.PROJECT, 'direct', expected) == expected.resolve().as_posix()


@pytest.mark.parametrize('relative', [
    'work/unrelated/pds-a/plan.json',
    'work/camera-vga-output/nested/pds-a/plan.json',
    'build/processed-output/pds-a/plan.json',
])
def test_runner_rejects_plans_outside_exact_workspace_scratch(relative):
    with pytest.raises(ValueError, match='outside exact camera'):
        runner.validate_plan(prep.PROJECT/relative)


def test_direct_path_does_not_allow_other_temporary_locations():
    accepted = prep.recipe_path(prep.PROJECT, 'direct', prep.TEMP_BUILD/'pds-a/compiled/a.v')
    assert 'codex-camera-vga-output' in accepted
    with pytest.raises(ValueError, match='escaped'):
        prep.recipe_path(prep.PROJECT, 'direct', prep.TEMP_BUILD.parent/'unrelated/a.v')
