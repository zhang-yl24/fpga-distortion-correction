"""Synthetic numerical checks, never evidence of a real new lens or board."""
from pathlib import Path
import sys

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.wideangle_mapping_audit import audit_profile, _fixed_project, _brown


def profile():
    return {'model': 'fisheye', 'K': [[80., 0, 31.5], [0, 79., 23.5], [0, 0, 1]],
            'D': [-.03, .004, -.0008, .0001], 'image_size': [64, 48],
            'camera_id': 'SYNTHETIC-LEFT', 'profile_id': 'synthetic-unit-test', 'provenance': 'synthetic'}


def test_four_coefficient_profile_full_frames_and_angles():
    result = audit_profile(profile(), angles=[0, 13.7, 90, 180])
    assert result['passed']
    assert result['coordinates_checked'] == 64*48*4
    assert result['fisheye_coefficients_used'] == profile()['D']
    assert result['synthetic_input'] and not result['hardware_release_allowed']
    assert not result['candidate_ready_for_profile_review']
    assert all(row['maximum_coordinate_error_px'] < .05 for row in result['frames'])


def test_independent_output_intrinsics_and_size():
    result = audit_profile(profile(), output_size=[48, 32],
        output_k=[[100., 0, 23.5], [0, 98., 15.5], [0, 0, 1]], angles=[0, 30])
    assert result['passed'] and result['output_size'] == [48, 32]
    assert result['coordinates_checked'] == 48*32*2


def test_sampling_is_only_diagnostic_even_when_sampled_gates_pass():
    result = audit_profile(profile(), stride=5)
    assert result['frames'][0]['numerical_gates_passed']
    assert not result['passed'] and not result['full_requested_frames_checked']
    assert result['coordinates_checked'] < result['requested_full_frame_coordinates']


def test_unbound_profile_cannot_be_ready_for_review_or_released():
    data = profile()
    data.pop('camera_id')
    data['provenance'] = 'real_chessboard_captures'
    result = audit_profile(data)
    assert result['passed'] and not result['profile_identity_bound']
    assert not result['candidate_ready_for_profile_review'] and not result['hardware_release_allowed']


def test_development_source_cannot_be_promoted_by_numerical_success():
    data = profile()
    data.update(provenance='real_chessboard_captures', development_only=True, passed=True,
                candidate_ready_for_profile_review=True, independent_spatial_coverage_passed=True)
    result = audit_profile(data)
    assert result['passed'] and result['source_profile_development_only']
    assert result['source_profile_calibration_passed']
    assert not result['candidate_ready_for_profile_review'] and not result['hardware_release_allowed']


def test_strict_ready_source_retains_review_readiness_and_source_flags():
    data = profile()
    data.update(provenance='real_chessboard_captures', passed=True,
                candidate_ready_for_profile_review=True, independent_spatial_coverage_passed=True)
    result = audit_profile(data)
    assert result['passed'] and result['candidate_ready_for_profile_review']
    assert result['source_profile_flags'] == {'passed': True, 'candidate_ready_for_profile_review': True,
        'independent_spatial_coverage_passed': True, 'development_only': None}
    assert not result['source_profile_development_only'] and not result['hardware_release_allowed']


def test_too_wide_virtual_camera_rejects_fixed_point_domain():
    data = profile()
    data['output_K'] = [[7., 0, 31.5], [0, 7., 23.5], [0, 0, 1]]
    result = audit_profile(data, minimum_in_bounds_fraction=0)
    assert not result['passed']
    assert result['frames'][0]['fixed_point_invalid_coordinates'] > 0


def test_strict_error_gate_rejects_candidate():
    result = audit_profile(profile(), maximum_error_px=1e-9)
    assert not result['passed']


def test_source_domain_coverage_is_a_rejection_gate():
    result = audit_profile(profile(), output_k=[[80., 0, -100.], [0, 79., -100.], [0, 0, 1]],
                           minimum_in_bounds_fraction=.9)
    assert not result['passed']
    assert result['frames'][0]['bilinear_all_neighbours_in_bounds_fraction'] < .9


def test_reference_coverage_must_also_pass_when_quantization_moves_border():
    data = profile()
    data['K'] = [[80., 0, 31.5], [0, 80., 23.5], [0, 0, 1]]
    data['D'] = [0., 0., 0., 0.]
    result = audit_profile(data, output_k=[[80., 0, 33.24], [0, 80., 23.5], [0, 0, 1]],
                           minimum_in_bounds_fraction=1.)
    assert result['frames'][0]['bilinear_all_neighbours_in_bounds_fraction'] == 1.
    assert result['frames'][0]['opencv_all_neighbours_in_bounds_fraction'] < 1.
    assert not result['passed']


def test_folded_fisheye_reference_cannot_pass():
    data = profile()
    data['D'] = [-8., 0., 0., 0.]
    result = audit_profile(data, maximum_error_px=1000, minimum_in_bounds_fraction=0)
    assert not result['passed']
    assert result['frames'][0]['reference_folded_samples'] > 0


def test_large_finite_angles_wrap_consistently():
    result = audit_profile(profile(), angles=[0, 3600000000000])
    assert result['passed']
    assert result['frames'][0]['maximum_coordinate_error_px'] == result['frames'][1]['maximum_coordinate_error_px']


def test_full_four_coefficient_terms_affect_reference_and_fit():
    a, b = profile(), profile()
    b['D'][2:] = [10., -4.]
    first, second = audit_profile(a), audit_profile(b)
    assert not np.allclose(first['fitted_brown_radial_coefficients'], second['fitted_brown_radial_coefficients'])
    assert first['profile_sha256'] != second['profile_sha256']


@pytest.mark.parametrize('change', [
    {'D': [0, 0]}, {'D': [0, 0, 0, float('nan')]}, {'model': 'brown'},
    {'K': [[80, 1, 31.5], [0, 79, 23.5], [0, 0, 1]]}, {'image_size': [1, 48]},
])
def test_invalid_camera_profiles_are_rejected(change):
    data = profile()
    data.update(change)
    with pytest.raises(ValueError):
        audit_profile(data)


@pytest.mark.parametrize('options', [{'angles': []}, {'angles': [float('inf')]}, {'stride': 0},
                                   {'maximum_error_px': -1}, {'minimum_in_bounds_fraction': 1.1},
                                   {'maximum_points_per_frame': True}, {'maximum_points_per_frame': -1}])
def test_invalid_audit_requests_are_rejected(options):
    with pytest.raises(ValueError):
        audit_profile(profile(), **options)


def test_large_frame_rejects_budget_before_mesh_allocation(monkeypatch):
    def no_mesh(*args, **kwargs):
        raise AssertionError('meshgrid must not run before the points budget check')
    monkeypatch.setattr(np, 'meshgrid', no_mesh)
    with pytest.raises(ValueError, match='exceeds maximum_points_per_frame'):
        audit_profile(profile(), output_size=[32767, 32767])


def test_narrow_profile_scope_cannot_be_used_for_wider_requested_rays():
    data = profile()
    data['model_scope'] = {'projection': 'forward_rectilinear', 'maximum_ray_angle_deg': 10}
    with pytest.raises(ValueError, match='exceed the profile model_scope'):
        audit_profile(data)


def test_vectorized_oracle_matches_scalar_for_extreme_inputs():
    rng = np.random.default_rng(20261024)
    u = rng.integers(-(1 << 23), (1 << 23), size=(11, 13), dtype=np.int64)
    v = rng.integers(-(1 << 23), (1 << 23), size=(11, 13), dtype=np.int64)
    for radial in ((-.4, .12, -.008), (500., 0., 0.)):
        config = _brown.parameters((*radial, 0, 0))
        sx, sy, invalid, _ = _fixed_project(u, v, config)
        for index in np.ndindex(u.shape):
            expected = _brown.project(int(u[index]), int(v[index]), config)
            assert expected == (int(sx[index]), int(sy[index]), int(invalid[index]))
