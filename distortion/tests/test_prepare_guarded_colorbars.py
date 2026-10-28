"""Read-only clone tests: no fixtures create directories or alter project sources."""
import copy
import importlib.util
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[1] / 'tools'
spec = importlib.util.spec_from_file_location('prepare_guarded_colorbars_under_test', TOOLS/'prepare_guarded_colorbars.py')
candidate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(candidate)


def replace_json(monkeypatch, suffix, change):
    original = candidate.load
    def patched(path):
        value = original(path)
        if str(path).replace('\\', '/').endswith(suffix):
            value = copy.deepcopy(value)
            change(value)
        return value
    monkeypatch.setattr(candidate, 'load', patched)


def test_exact_staged_clone_and_idempotent_stage_are_read_only():
    manifest = candidate.validate()
    paths = [candidate.ROOT/name for name in manifest['source_files']]
    paths += [candidate.ROOT/f'board/{candidate.TARGET}-sources.json']
    before = {str(path): candidate.sha(path) for path in paths}
    assert candidate.prepare() == manifest
    assert {str(path): candidate.sha(path) for path in paths} == before
    parent = candidate.load(candidate.ROOT/f'board/{candidate.BASE}-sources.json')
    assert set(parent['source_files']) & set(manifest['source_files']) == {
        name for name in parent['source_files'] if name in manifest['source_files']}
    assert len(set(parent['source_files']) & set(manifest['source_files'])) == 101
    assert manifest['GuardedControlContract']['build_tag'] == 0x52473242
    assert manifest['SensorOutputContract']['calibration_scene_eligible'] is False


@pytest.mark.parametrize('name', [f'board/{candidate.BASE}-sources.json', *candidate.COLOR_SOURCES])
def test_pinned_parent_and_color_components_cannot_drift(monkeypatch, name):
    original = candidate.sha
    path = (candidate.ROOT/name).resolve()
    monkeypatch.setattr(candidate, 'sha', lambda value: '0'*64 if Path(value).resolve() == path else original(value))
    with pytest.raises(ValueError):
        candidate.validate()


@pytest.mark.parametrize('change', [
    lambda x: x.update(target='another_target'),
    lambda x: x['GuardedControlContract'].update(build_tag=0x52473201),
    lambda x: x['SensorOutputContract'].update(lens_optical_acceptance_eligible=True),
    lambda x: x['SensorOutputContract'].update(calibration_scene_eligible=True),
    lambda x: x['SensorOutputContract'].update(input_origin='natural_scene'),
    lambda x: x['SensorOutputContract'].update(control_value='0x00'),
    lambda x: x.update(hardware_accessed=True),
    lambda x: x.update(hardware_accessed=0),
    lambda x: x.update(physical_eye='left'),
    lambda x: x.update(connector_slot_tag=1),
    lambda x: x.update(validated_colorbar_component_sha256={}),
    lambda x: x.update(parent_prepared_source_manifest={}),
    lambda x: x.update(SourceSHA256={}),
    lambda x: x.update(SourceSHA256=[]),
    lambda x: x['SourceSHA256'].update({'rtl/uart_tx.v': 123}),
    lambda x: x['source_files'].append(x['source_files'][0]),
])
def test_unreviewed_manifest_claim_or_hash_is_rejected(monkeypatch, change):
    replace_json(monkeypatch, f'{candidate.TARGET}-sources.json', change)
    with pytest.raises(ValueError):
        candidate.validate()


@pytest.mark.parametrize('change', [
    lambda x: x['source_files'].append('rtl/uart_tx.v'),
    lambda x: x['SourceSHA256'].pop('rtl/uart_tx.v'),
    lambda x: x['SourceSHA256'].update({'rtl/uart_tx.v': 2}),
])
def test_parent_source_closure_is_complete(monkeypatch, change):
    replace_json(monkeypatch, f'{candidate.BASE}-sources.json', change)
    with pytest.raises(ValueError):
        candidate.validate()


@pytest.mark.parametrize('suffix', ['.v', '.fdc', '-pins.json'])
def test_generated_top_fdc_and_pin_clone_require_exact_text(monkeypatch, suffix):
    original = Path.read_text
    path = (candidate.ROOT/f'board/{candidate.TARGET}{suffix}').resolve()
    def changed(value, *args, **kwargs):
        text = original(value, *args, **kwargs)
        return text+'\nUNREVIEWED_DELTA\n' if value.resolve() == path else text
    monkeypatch.setattr(Path, 'read_text', changed)
    with pytest.raises(ValueError, match='unreviewed colorbar clone'):
        candidate.validate()


COLOR_SIM = candidate.APPROVED/'guarded-colorbars-sim-20261025-184546-309/guarded-colorbars-simulation.json'


def test_default_build_inputs_are_plan_only_and_extra_color_sim_enables_build():
    assert candidate.validate_build_inputs()['ReadyForBuild'] is False
    ready = candidate.validate_build_inputs(COLOR_SIM)
    assert ready['ReadyForBuild'] is True
    assert ready['HardwareAccessed'] is False
    assert ready['ParentValidatedBuildSHA256'] == candidate.BASE_VALIDATED_SHA256


def test_exact_natural_validated_artifact_is_required(monkeypatch):
    original = candidate.sha
    monkeypatch.setattr(candidate, 'sha', lambda path: '0'*64 if Path(path) == candidate.BASE_BUILD else original(path))
    with pytest.raises(ValueError, match='specific validated natural'):
        candidate.validate_build_inputs(COLOR_SIM)


@pytest.mark.parametrize('change', [
    lambda x: x.update(Passed=False),
    lambda x: x.update(HardwareAccessed=True),
    lambda x: x.update(RegressionTops=['tb_guarded_board_pipeline']),
    lambda x: x.update(RegressionTops=None),
    lambda x: x.update(SourceSHA256={}),
    lambda x: x.update(LogSHA256={}),
    lambda x: x.update(MixedStreamSHA256='0'*64),
])
def test_complete_natural_five_top_source_evidence_is_required(monkeypatch, change):
    replace_json(monkeypatch, '/guarded-board-simulation.json', change)
    with pytest.raises(ValueError):
        candidate.validate_build_inputs(COLOR_SIM)


@pytest.mark.parametrize('change', [
    lambda x: x.update(Passed=False),
    lambda x: x.update(HardwareAccessed=True),
    lambda x: x.update(PDSAccessed=True),
    lambda x: x.update(DynamicPadMask=0),
    lambda x: x.update(DynamicPadMask=True),
    lambda x: x.update(TrialPadMask='ffff'),
    lambda x: x.update(Fixture='unknown'),
    lambda x: x.update(OpticalSceneVerified=True),
    lambda x: x.update(SourceSHA256={}),
    lambda x: x.update(SourceSHA256After={}),
    lambda x: x.update(SimulationLogSHA256='0'*64),
])
def test_specific_colorbar_readback_specialization_is_required(monkeypatch, change):
    replace_json(monkeypatch, '/guarded-colorbars-simulation.json', change)
    with pytest.raises(ValueError):
        candidate.validate_build_inputs(COLOR_SIM)


def test_external_colorbar_evidence_is_rejected():
    with pytest.raises(ValueError, match='approved scratch'):
        candidate.validate_build_inputs(candidate.ROOT/'output/project/guarded-colorbars-simulation.json')
