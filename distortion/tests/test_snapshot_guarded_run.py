"""Local reset-reference archival gates; no device or evidence modification."""
from pathlib import Path
import copy
import sys
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
import snapshot_guarded_run as archive


@pytest.fixture
def isolated_manifest():
    source = archive.ROOT/'board/raw_camera_capture_cam1_guarded_isolated-sources.json'
    if not source.is_file():
        pytest.skip('optional local isolated preparation is absent')
    prepared = archive.load(source)
    contract = prepared['OtherSensorResetTrialContract']
    if not all((archive.ROOT/name).is_file() for name in contract['reference_source_sha256']):
        pytest.skip('optional reset electrical reference artifacts are absent')
    return {'Target':'raw_camera_capture_cam1_guarded_isolated',
            'OtherSensorResetTrialContract':copy.deepcopy(contract)}


def test_exact_four_reset_references_are_preserved_including_actual_pin_report(isolated_manifest):
    refs = archive.other_reset_references(isolated_manifest)
    assert len(refs) == 4
    assert any(name.endswith('_prr.prt') for name in refs)
    assert 'board/corrected_gamma_d5-pins.json' in refs


def test_missing_reference_prevents_a_partial_snapshot(isolated_manifest):
    isolated_manifest['OtherSensorResetTrialContract']['reference_source_sha256'].pop('board/corrected_gamma_d5-pins.json')
    with pytest.raises(ValueError):
        archive.other_reset_references(isolated_manifest)


def test_changed_reference_hash_does_not_become_an_archive_input(isolated_manifest):
    refs = isolated_manifest['OtherSensorResetTrialContract']['reference_source_sha256']
    refs['board/corrected_gamma_d5-pins.json'] = '0'*64
    with pytest.raises(ValueError):
        archive.other_reset_references(isolated_manifest)


def test_reference_cannot_escape_project_root(isolated_manifest):
    refs = isolated_manifest['OtherSensorResetTrialContract']['reference_source_sha256']
    digest = refs.pop('board/corrected_gamma_d5-pins.json')
    refs['../outside-reference.json'] = digest
    with pytest.raises(ValueError):
        archive.other_reset_references(isolated_manifest)


def test_other_target_cannot_inherit_an_isolation_contract(isolated_manifest):
    isolated_manifest['Target'] = 'raw_camera_capture_cam2_guarded'
    with pytest.raises(ValueError):
        archive.other_reset_references(isolated_manifest)


def test_old_targets_require_no_new_references_but_isolated_cannot_omit_them():
    assert archive.other_reset_references({'Target':'raw_camera_capture_cam2_guarded'}) == {}
    with pytest.raises(ValueError):
        archive.other_reset_references({'Target':'raw_camera_capture_cam1_guarded_isolated'})
