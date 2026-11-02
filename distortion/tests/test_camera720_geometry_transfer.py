"""Known geometry, independent held-out residuals and untouched capture binding."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import zlib

import cv2
import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools import camera720_geometry_transfer as transfer


def profile():
    return {'model': 'fisheye', 'image_size': [640, 480], 'camera_id': 'synthetic-camera',
        'lens_id': 'synthetic-lens', 'profile_id': 'synthetic-vga-profile', 'capture_mode_id': 'synthetic-vga',
        'K': [[159.561921, 0, 321.225838], [0, 159.846725, 250.242558], [0, 0, 1]],
        'D': [.176020788, -.010104993, -.013110537, .002201229],
        'model_scope': {'projection': 'forward_rectilinear', 'maximum_ray_angle_deg': 88,
            'inverse_method': transfer.inverse.METHOD}}


def manifest():
    target = {k: profile()[k] for k in transfer.calibration.IDENTITY}
    target.update(profile_id='synthetic720-profile', capture_mode_id='synthetic720')
    return {'schema': transfer.MANIFEST_SCHEMA, 'target_identity': target,
        'camera_focus_and_mount_unchanged_declared': True,
        'board': {'cols': 6, 'rows': 9, 'square_mm': 25}, 'method': 'fit_axis_aligned',
        'thresholds': {'rms_px': .5, 'maximum_px': 1.5},
        'pairs': [{'pair_id': 'a', 'pose_id': 'pose-a', 'same_stationary_pose_declared': True,
                   'split': 'fit', 'corner_order': 'auto'},
                  {'pair_id': 'b', 'pose_id': 'pose-b', 'same_stationary_pose_declared': True,
                   'split': 'held_out', 'corner_order': 'auto'}]}


def observations():
    board = manifest()['board']
    world = transfer.board_points(board)
    k = np.asarray(profile()['K']); d = np.asarray(profile()['D'])
    a = np.array([[2.01, 0, -3.5], [0, 1.99, -118.25], [0, 0, 1]])
    result = []
    for i, name in enumerate(('a', 'b')):
        r = np.array([.1+i*.03, -.2, .05])
        t = np.array([-60.+i*20, -100., 400.])
        xy = cv2.fisheye.projectPoints(world, r, t, k, d)[0].reshape(-1, 2)
        target = xy @ a[:2, :2].T + a[:2, 2]
        # A real SB detector can reverse the raster index order across modes.
        target = transfer.order_points(target, board, 'reverse_both' if i == 0 else 'reverse_cols')
        result.append({'pair_id': name, 'source': xy, 'target': target})
    return result, a


def test_recovers_mode_transform_with_detector_symmetry_and_keeps_distortion():
    obs, expected = observations()
    report = transfer.evaluate_observations(profile(), manifest(), obs)
    np.testing.assert_allclose(report['A_source_to_target'], expected, atol=1e-10)
    np.testing.assert_allclose(report['candidate_parameters']['K'], expected @ np.asarray(profile()['K']), atol=1e-10)
    assert report['candidate_parameters']['D'] == profile()['D']
    assert report['candidate_parameters']['inverse_method'] == transfer.inverse.METHOD
    assert report['numeric_pair_checks_passed']
    assert [x['corner_order']['selected'] for x in report['pairs']] == ['reverse_both', 'reverse_cols']
    assert not report['optical_calibration_accepted'] and not report['hardware_release_allowed']
    assert not report['drop_in_calibration_profile'] and not report['source_visibility_scope_inherited']


def test_heldout_pose_motion_fails_without_refitting_transform():
    obs, _ = observations()
    baseline = transfer.evaluate_observations(profile(), manifest(), obs)
    obs[1]['target'] = obs[1]['target'] + [4., -3.]
    changed = transfer.evaluate_observations(profile(), manifest(), obs)
    np.testing.assert_array_equal(changed['A_source_to_target'], baseline['A_source_to_target'])
    assert not changed['numeric_pair_checks_passed']
    assert changed['pairs'][1]['rms_px'] == pytest.approx(5.)


@pytest.mark.parametrize('case', ['pose_leak', 'not_stationary', 'lens_changed', 'no_holdout', 'nan', 'missing_corner', 'unknown_order'])
def test_bad_pair_identity_and_geometry_are_rejected(case):
    m = manifest(); obs, _ = observations()
    if case == 'pose_leak': m['pairs'][1]['pose_id'] = 'pose-a'
    elif case == 'not_stationary': m['pairs'][0]['same_stationary_pose_declared'] = False
    elif case == 'lens_changed': m['target_identity']['lens_id'] = 'different-lens'
    elif case == 'no_holdout': m['pairs'][1]['split'] = 'fit'
    elif case == 'nan': obs[1]['target'][0, 0] = float('nan')
    elif case == 'missing_corner': obs[1]['source'] = obs[1]['source'][:-1]
    else: m['pairs'][0]['corner_order'] = 'unchecked'
    with pytest.raises(ValueError): transfer.evaluate_observations(profile(), m, obs)


@pytest.mark.parametrize('a', [
    [[2, .01, 0], [0, 2, -120], [0, 0, 1]],
    [[-2, 0, 1280], [0, 2, -120], [0, 0, 1]],
    [[2, 0, 0], [0, 2, -120], [0, 0, 2]],
    [[2, 0, float('inf')], [0, 2, -120], [0, 0, 1]],
])
def test_general_affine_or_nonfinite_matrix_not_silently_treated_as_crop(a):
    with pytest.raises(ValueError): transfer.candidate(profile(), a, manifest()['target_identity'])


def test_supplied_matrix_never_refits_to_explain_heldout_error():
    obs, expected = observations(); m = manifest()
    m['method'] = 'supplied_axis_aligned'; m['pairs'] = m['pairs'][1:]
    m['A_source_to_target'] = [[2, 0, 0], [0, 1.5, 0], [0, 0, 1]]
    report = transfer.evaluate_observations(profile(), m, obs[1:])
    np.testing.assert_array_equal(report['A_source_to_target'], m['A_source_to_target'])
    assert not report['numeric_pair_checks_passed']


def test_q8_grid_error_matches_direct_reprojection_and_detects_overflow():
    k = np.array([[319.12345, 0, 641.23456], [0, 318.98765, 382.34567], [0, 0, 1.]])
    report = transfer.q8_intrinsics_audit(k, [1280, 720])
    yy, xx = np.indices((720, 1280)); points = np.column_stack((xx.ravel(), yy.ravel()))
    values = np.array([k[0, 0], k[1, 1], k[0, 2], k[1, 2]])
    rounded = np.rint(values*256)/256
    distorted_rays = (points-values[2:])/values[:2]
    projected = distorted_rays*rounded[:2]+rounded[2:]
    assert report['source_grid_pixels_checked'] == 921600
    assert report['maximum_source_pixel_error_px'] == pytest.approx(np.linalg.norm(projected-points, axis=1).max(), abs=1e-10)
    assert report['representable'] and not report['fpga_mapping_verified']
    k[0, 0] = 40000
    assert not transfer.q8_intrinsics_audit(k, [1280, 720])['representable']


def test_rank_deficient_correspondences_rejected():
    p = np.column_stack((np.full(12, 10.), np.arange(12)))
    with pytest.raises(ValueError, match='span'): transfer.fit_axis(p, p)


def write_capture(tmp_path, pair, side, words, identity):
    stem = pair+'-'+side
    raw, png, meta = [tmp_path/(stem+ext) for ext in ('.rgb565', '.png', '.json')]
    payload = words.astype('<u2').tobytes(); raw.write_bytes(payload)
    r, g, b = (words >> 11) & 31, (words >> 5) & 63, words & 31
    image = np.stack(((b << 3) | (b >> 2), (g << 2) | (g >> 4), (r << 3) | (r >> 2)), axis=-1).astype(np.uint8)
    png.write_bytes(cv2.imencode('.png', image)[1].tobytes())
    digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    metadata = {'source_kind': 'offline_uart_replay', 'hardware_accessed': False,
        'geometry_applied': False, 'identity_binding': identity,
        'width': words.shape[1], 'height': words.shape[0], 'pixel_format': 'RGB565_LE',
        'raw_path': raw.name, 'raw_sha256': digest(raw), 'image_path': png.name,
        'image_sha256': digest(png), 'source_crc32': f'{zlib.crc32(payload):08X}'}
    meta.write_text(json.dumps(metadata), encoding='utf-8')
    return {'path': png.name, 'sha256': digest(png), 'metadata_path': meta.name,
            'metadata_sha256': digest(meta)}


def capture_fixture(tmp_path):
    m = manifest()
    source_identity = {k: profile()[k] for k in transfer.calibration.IDENTITY}
    for i, pair in enumerate(m['pairs']):
        source = np.full((480, 640), 65535, dtype=np.uint16)
        x0, y0 = 140+i*20, 90+i*12
        for row in range(10):
            for col in range(7):
                if (row+col) % 2:
                    source[y0+row*24:y0+(row+1)*24, x0+col*24:x0+(col+1)*24] = 0
        target = np.repeat(np.repeat(source, 2, axis=0), 2, axis=1)[120:840]
        pair['source'] = write_capture(tmp_path, pair['pair_id'], 'source', source, source_identity)
        pair['target'] = write_capture(tmp_path, pair['pair_id'], 'target', target, m['target_identity'])
    return m


def test_bound_replay_decodes_full_720_and_detects_corners_without_physical_claim(tmp_path):
    m = capture_fixture(tmp_path)
    observations, evidence = transfer.load_observations(profile(), m, tmp_path)
    report = transfer.evaluate_observations(profile(), m, observations)
    assert report['numeric_pair_checks_passed']
    actual = np.asarray(report['A_source_to_target'])
    np.testing.assert_allclose(np.diag(actual)[:2], [2, 2], atol=.005)
    expected = np.array([[2, 0, .5], [0, 2, -119.5], [0, 0, 1]])
    # SB localization at two raster scales is not analytically exact. Check
    # the measured region, rather than the extrapolated intercept at (0,0).
    for observation in observations:
        xy = observation['source']
        assert np.linalg.norm(xy @ (actual-expected)[:2, :2].T + (actual-expected)[:2, 2], axis=1).max() < .3
    assert len(evidence) == 4 and not any(x['physical_capture_record'] for x in evidence)
    assert not report['optical_calibration_accepted']


@pytest.mark.parametrize('fault', ['raw_corruption', 'geometry_applied', 'metadata_identity', 'duplicate_frame'])
def test_capture_provenance_faults_rejected(tmp_path, fault):
    m = capture_fixture(tmp_path)
    view = m['pairs'][0]['target']
    meta_path = tmp_path/view['metadata_path']; meta = json.loads(meta_path.read_text())
    if fault == 'raw_corruption':
        raw = tmp_path/meta['raw_path']; data = bytearray(raw.read_bytes()); data[-1] ^= 1; raw.write_bytes(data)
    elif fault == 'duplicate_frame':
        m['pairs'][1]['source'] = copy.deepcopy(m['pairs'][0]['source'])
    else:
        if fault == 'geometry_applied': meta['geometry_applied'] = True
        else: meta['identity_binding']['capture_mode_id'] = 'wrong-mode'
        meta_path.write_text(json.dumps(meta), encoding='utf-8')
        view['metadata_sha256'] = hashlib.sha256(meta_path.read_bytes()).hexdigest()
    with pytest.raises(ValueError): transfer.load_observations(profile(), m, tmp_path)


def test_hypothesis_cli_outputs_unaccepted_envelope_and_refuses_overwrite(tmp_path):
    source = tmp_path/'source.json'; source.write_text(json.dumps(profile()), encoding='utf-8')
    out = tmp_path/'hypothesis.json'
    args = [sys.executable, '-B', str(Path(transfer.__file__)), str(source), '--hypothesis', '2', '2', '0', '-120',
        '--target-mode', 'synthetic720', '--target-profile', 'synthetic720-profile', '--output', str(out)]
    first = subprocess.run(args, capture_output=True, text=True)
    assert first.returncode == 0, first.stderr
    report = json.loads(out.read_text())
    assert report['method'] == 'unmeasured_user_matrix_hypothesis' and report['measured_target_images'] == 0
    assert not report['numeric_pair_checks_passed'] and not report['optical_calibration_accepted']
    second = subprocess.run(args, capture_output=True, text=True)
    assert second.returncode != 0 and 'fresh output' in second.stderr


def test_reencoded_duplicate_frame_cannot_enter_independent_pose(tmp_path):
    m = capture_fixture(tmp_path)
    first = m['pairs'][0]['source']
    source_meta = json.loads((tmp_path/first['metadata_path']).read_text())
    words = np.fromfile(tmp_path/source_meta['raw_path'], dtype='<u2').reshape(480, 640)
    replacement = write_capture(tmp_path, 'reencoded-copy', 'source', words,
        {k: profile()[k] for k in transfer.calibration.IDENTITY})
    png = tmp_path/replacement['path']
    image = cv2.imdecode(np.fromfile(png, dtype=np.uint8), cv2.IMREAD_COLOR)
    png.write_bytes(cv2.imencode('.png', image, [cv2.IMWRITE_PNG_COMPRESSION, 9])[1].tobytes())
    replacement['sha256'] = hashlib.sha256(png.read_bytes()).hexdigest()
    assert replacement['sha256'] != first['sha256']
    meta_path = tmp_path/replacement['metadata_path']; meta = json.loads(meta_path.read_text())
    meta['image_sha256'] = replacement['sha256']; meta_path.write_text(json.dumps(meta), encoding='utf-8')
    replacement['metadata_sha256'] = hashlib.sha256(meta_path.read_bytes()).hexdigest()
    m['pairs'][1]['source'] = replacement
    with pytest.raises(ValueError, match='duplicate raw frame'):
        transfer.load_observations(profile(), m, tmp_path)


@pytest.mark.parametrize('flipped_axes', [(0,), (1,), (0, 1)])
def test_symmetric_chessboard_can_conceal_pixel_flip_without_orientation_claim(flipped_axes):
    m = manifest(); board = m['board']; observations = []
    cols, rows = np.meshgrid(np.arange(board['cols']), np.arange(board['rows']))
    centered = np.column_stack((cols.ravel()-(board['cols']-1)/2, rows.ravel()-(board['rows']-1)/2))
    for pair, spacing in zip(m['pairs'], (18., 24.)):
        source = centered*spacing + [319.5, 239.5]
        target = source*2 + [0, -120]
        for axis in flipped_axes:
            target[:, axis] = (1279 if axis == 0 else 719)-target[:, axis]
        observations.append({'pair_id': pair['pair_id'], 'source': source, 'target': target})
    report = transfer.evaluate_observations(profile(), m, observations)
    # Different apparent board scales are independent numeric geometries,
    # yet board symmetry hides a real mirrored image. The flag must stay false.
    assert report['numeric_pair_checks_passed']
    assert not report['image_pixel_orientation_verified']
    assert 'reflection' in report['orientation_limits']


@pytest.mark.parametrize('side', ['source', 'target', 'both'])
def test_fit_heldout_same_corner_geometry_rejected_despite_distinct_pose_labels(side):
    m = manifest(); obs, _ = observations()
    for name in (('source', 'target') if side == 'both' else (side,)):
        obs[1][name] = transfer.order_points(obs[0][name], m['board'], 'reverse_both')
    assert m['pairs'][0]['pose_id'] != m['pairs'][1]['pose_id']
    with pytest.raises(ValueError, match='repeated fit/held-out corner geometry'):
        transfer.evaluate_observations(profile(), m, obs)


@pytest.mark.parametrize('cx', [6e305, 1e200])
def test_finite_extreme_intrinsics_reject_intermediate_quantization_overflow(cx):
    k = [[.002, 0, cx], [0, 318, 382], [0, 0, 1]]
    with pytest.raises(ValueError, match='arithmetic overflow'):
        transfer.q8_intrinsics_audit(k, [1280, 720])


def test_overflowing_hypothesis_cli_does_not_create_partial_json(tmp_path):
    p = profile(); p['K'] = [[.002, 0, 6e305], [0, 318, 382], [0, 0, 1]]
    source = tmp_path/'source.json'; source.write_text(json.dumps(p), encoding='utf-8')
    out = tmp_path/'failed.json'
    args = [sys.executable, '-B', str(Path(transfer.__file__)), str(source), '--hypothesis', '1', '1', '0', '0',
        '--target-mode', 'synthetic720', '--target-profile', 'synthetic720-profile', '--output', str(out)]
    result = subprocess.run(args, capture_output=True, text=True)
    assert result.returncode != 0 and 'arithmetic overflow' in result.stderr
    assert not out.exists()


def test_report_serialization_is_completed_before_output_file_creation(tmp_path, monkeypatch):
    source = tmp_path/'source.json'; source.write_text(json.dumps(profile()), encoding='utf-8')
    out = tmp_path/'failed-serialization.json'; original = transfer.candidate
    def nonserializable_report(*args):
        result = original(*args); result['deliberate_bad_metric'] = float('inf')
        return result
    monkeypatch.setattr(transfer, 'candidate', nonserializable_report)
    monkeypatch.setattr(sys, 'argv', [str(Path(transfer.__file__)), str(source), '--hypothesis', '2', '2', '0', '-120',
        '--target-mode', 'synthetic720', '--target-profile', 'synthetic720-profile', '--output', str(out)])
    with pytest.raises(ValueError, match='JSON compliant'):
        transfer.main()
    assert not out.exists()
