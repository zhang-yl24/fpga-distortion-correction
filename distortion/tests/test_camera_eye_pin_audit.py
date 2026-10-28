"""Pure legacy camera-eye comparisons; never authorizes new hardware."""
from pathlib import Path
import copy
import json
import sys
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.camera_eye_pin_audit import (
    CAMERA_PORTS, audit_pin_map, load_reference_maps, main,
    read_pin_json, write_new_report,
)


def reference(eye):
    maps, _ = load_reference_maps()
    return copy.deepcopy(maps[eye])


@pytest.mark.parametrize('eye,d5', [('CAM1', 'Y21'), ('CAM2', 'AA23')])
def test_matching_legacy_eye_does_not_verify_new_module(eye, d5):
    report = audit_pin_map(reference(eye), eye)
    assert report['passed'] and report['old_reference_match']
    assert report['camera_route_count'] == 14
    assert report['camera_pins']['cam_data[5]'] == d5
    assert not report['new_module_verified']
    assert not report['hardware_ready']
    assert not report['download_authorized_by_tool']
    assert not report['hardware_accessed']
    assert not report['eye_chosen_from_photograph']


def test_legacy_references_are_distinct_and_disjoint():
    maps, sources = load_reference_maps()
    assert set(maps['CAM1']) == set(maps['CAM2']) == set(CAMERA_PORTS)
    assert len(set(maps['CAM1'].values()) | set(maps['CAM2'].values())) == 28
    assert all(Path(value['path']).is_file() and len(value['sha256']) == 64 for value in sources.values())


@pytest.mark.parametrize('actual,requested', [('CAM1', 'CAM2'), ('CAM2', 'CAM1')])
def test_swapping_electrical_eyes_is_rejected(actual, requested):
    report = audit_pin_map(reference(actual), requested)
    assert not report['old_reference_match'] and not report['passed']
    assert len(report['mismatches']) == 14


@pytest.mark.parametrize('eye', ['CAM1', 'CAM2'])
def test_historical_AA22_is_never_accepted(eye):
    pins = reference(eye)
    pins['cam_data[5]'] = 'AA22'
    report = audit_pin_map(pins, eye)
    assert not report['passed'] and report['historical_AA22_D5_rejected']


def test_camera_pin_conflict_is_rejected():
    pins = reference('CAM2')
    pins['cam_data[0]'] = pins['cam_data[1]']
    report = audit_pin_map(pins, 'CAM2')
    assert not report['passed']
    assert report['pin_conflicts'][0]['ports'] == ['cam_data[0]', 'cam_data[1]']


def test_full_candidate_collision_with_non_camera_port_is_rejected():
    pins = reference('CAM1')
    pins['uart_txd'] = pins['cam_sda']
    report = audit_pin_map(pins, 'CAM1')
    assert not report['passed'] and not report['mismatches']
    assert report['pin_conflicts']


@pytest.mark.parametrize('eye', ['left', 'right', 'cam1', '', None, 1, [], {}])
def test_eye_must_be_explicit_electrical_identity(eye):
    with pytest.raises(ValueError, match='CAM1 or CAM2'):
        audit_pin_map(reference('CAM1'), eye)


def test_missing_route_is_invalid():
    pins = reference('CAM1')
    del pins['cam_pclk']
    with pytest.raises(ValueError, match='missing camera ports'):
        audit_pin_map(pins, 'CAM1')


@pytest.mark.parametrize('value', ['aa23', ' AA23', None, 23, 'AA0', True])
def test_invalid_package_pin_values_are_rejected(value):
    pins = reference('CAM2')
    pins['cam_data[5]'] = value
    with pytest.raises(ValueError, match='uppercase package pin'):
        audit_pin_map(pins, 'CAM2')


def test_extra_camera_route_is_not_silently_promoted():
    pins = reference('CAM1')
    pins['cam_xclk'] = 'A1'
    with pytest.raises(ValueError, match='outside the legacy'):
        audit_pin_map(pins, 'CAM1')


def test_duplicate_json_keys_are_rejected_without_opening_hardware():
    with patch.object(Path, 'read_text', return_value='{"cam_sda":"A1","cam_sda":"A2"}'):
        with pytest.raises(ValueError, match='duplicate JSON key'):
            read_pin_json(Path('synthetic-only.json'))


def test_cli_read_only_match_has_no_hardware_permission(capsys):
    code = main(['--candidate', str(ROOT/'board/corrected_gamma_d5-pins.json'), '--eye', 'CAM2'])
    report = json.loads(capsys.readouterr().out)
    assert code == 0 and report['old_reference_match']
    assert not report['new_module_verified'] and not report['download_authorized_by_tool']
    assert len(report['candidate_file']['sha256']) == 64


def test_cli_wrong_eye_is_nonzero(capsys):
    code = main(['--candidate', str(ROOT/'board/corrected_gamma_d5-pins.json'), '--eye', 'CAM1'])
    assert code == 1 and not json.loads(capsys.readouterr().out)['passed']


def test_new_report_cannot_overwrite_historical_files_or_create_directories():
    with pytest.raises(ValueError, match='existing distortion/output/project'):
        write_new_report(ROOT/'results/historical.json', {})
    with pytest.raises(FileExistsError):
        write_new_report(ROOT/'output/project/new-camera-profile.template.json', {})
