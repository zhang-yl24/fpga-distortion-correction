"""Synthetic geometry and manifest rejection tests; no physical stereo claims."""
from pathlib import Path
import copy
import hashlib
import sys

import cv2
import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.stereo_fisheye_calibrate import audit_manifest, board_points, calibrate_points, detect_manifest_points


def profiles():
    left = {'model': 'fisheye', 'camera_id': 'SYNTHETIC-L', 'lens_id': 'SYNTHETIC-LENS-L',
            'profile_id': 'synthetic-left-v1', 'provenance': 'synthetic', 'image_size': [640, 480],
            'K': [[360., 0, 319.5], [0, 365., 239.5], [0, 0, 1]],
            'D': [-.06, .008, -.001, .0002], 'calibration_image_sha256': ['a'*64]}
    right = copy.deepcopy(left)
    right.update(camera_id='SYNTHETIC-R', lens_id='SYNTHETIC-LENS-R', profile_id='synthetic-right-v1',
                 K=[[357., 0, 317.3], [0, 363., 238.1], [0, 0, 1]], D=[-.05, .006, -.0005, .0001])
    return left, right


def geometry():
    left, right = profiles()
    board = {'cols': 9, 'rows': 6, 'square_mm': 20.}
    world = board_points(board)
    rig_r, _ = cv2.Rodrigues(np.array([.003, .015, -.004]))
    rig_t = np.array([[-65.], [.8], [.4]])
    pairs = []
    for i in range(16):
        r = np.array([.12*(i % 4-1.5), .14*(i % 5-2), .04*(i % 3-1)])
        t = np.array([[-80.+12*(i % 5-2)], [-50.+9*(i % 4-1.5)], [440.+22*(i % 6)]])
        rotation, _ = cv2.Rodrigues(r)
        right_rotation, _ = cv2.Rodrigues(rig_r@rotation)
        right_t = rig_r@t+rig_t
        lp, _ = cv2.fisheye.projectPoints(world, r, t, np.array(left['K']), np.array(left['D']))
        rp, _ = cv2.fisheye.projectPoints(world, right_rotation, right_t, np.array(right['K']), np.array(right['D']))
        pairs.append({'pair_id': f'synthetic-pair-{i}', 'split': 'train' if i < 12 else 'held_out',
                      'left_points': lp, 'right_points': rp})
    return pairs, left, right, board, rig_r, rig_t


def test_known_extrinsic_recovery_and_independent_holdout():
    pairs, left, right, board, rotation, translation = geometry()
    result = calibrate_points(pairs, left, right, board)
    assert result['passed'] and result['numerical_gates_passed']
    np.testing.assert_allclose(result['R_left_to_right'], rotation, atol=1e-6)
    np.testing.assert_allclose(result['T_left_to_right_mm'], translation.ravel(), atol=1e-4)
    assert abs(result['baseline_mm']-np.linalg.norm(translation)) < 1e-4
    assert result['held_out_absolute_y_max_px'] < 1e-4
    assert len(result['training_pair_ids']) == 12 and len(result['held_out_pair_ids']) == 4
    assert not result['stereo_acceptance_ready'] and not result['hardware_release_allowed']
    assert not result['physical_synchronization_measured_by_this_tool']


def test_wrong_heldout_pairing_fails_epipolar_gate():
    pairs, left, right, board, _, _ = geometry()
    pairs[12]['right_points'], pairs[14]['right_points'] = pairs[14]['right_points'], pairs[12]['right_points']
    result = calibrate_points(pairs, left, right, board)
    assert not result['passed']
    assert result['training_rms_px'] < .001
    assert result['held_out_absolute_y_p95_px'] > 1


def test_duplicate_point_observation_is_rejected():
    pairs, left, right, board, _, _ = geometry()
    pairs[-1]['left_points'] = pairs[0]['left_points'].copy()
    with pytest.raises(ValueError, match='duplicate corner'):
        calibrate_points(pairs, left, right, board)


def test_degenerate_collinear_board_pose_is_rejected():
    pairs, left, right, board, _, _ = geometry()
    pairs[0]['left_points'][..., 1] = 200.
    with pytest.raises(ValueError, match='degenerate board pose'):
        calibrate_points(pairs, left, right, board)


def test_stereo_corners_must_stay_inside_each_declared_profile_scope():
    pairs, left, right, board, _, _ = geometry()
    left['model_scope'] = {'projection': 'forward_rectilinear', 'maximum_ray_angle_deg': 3}
    with pytest.raises(ValueError, match='exceed the profile model_scope'):
        calibrate_points(pairs, left, right, board)


def test_board_size_budget_rejects_before_allocating_points():
    with pytest.raises(ValueError, match='corner budget'):
        board_points({'cols': 1000000, 'rows': 1000000, 'square_mm': 20.})


@pytest.mark.parametrize('case', ['size', 'identity', 'missing_intrinsic_identity', 'few_train', 'few_held', 'outside'])
def test_invalid_point_inputs(case):
    pairs, left, right, board, _, _ = geometry()
    if case == 'size':
        right['image_size'] = [1280, 720]
    elif case == 'identity':
        right['camera_id'] = left['camera_id']
    elif case == 'missing_intrinsic_identity':
        del right['lens_id']
    elif case == 'few_train':
        pairs = pairs[6:]
    elif case == 'few_held':
        pairs = pairs[:-2]
    else:
        pairs[0]['left_points'][0, 0, 0] = -1
    with pytest.raises(ValueError):
        calibrate_points(pairs, left, right, board)


def manifest_fixture(tmp_path):
    left, right = profiles()
    manifest = {'schema': 1, 'rig_id': 'SYNTHETIC-TEST-RIG', 'provenance': 'synthetic',
        'left': {k: left[k] for k in ('camera_id', 'lens_id', 'profile_id')},
        'right': {k: right[k] for k in ('camera_id', 'lens_id', 'profile_id')},
        'board': {'cols': 9, 'rows': 6, 'square_mm': 20},
        'synchronization': {'method': 'software_timestamps_only', 'maximum_pair_skew_ns': 1000,
                            'evidence_review_status': 'unverified'}, 'pairs': []}
    for i in range(2):
        pair = {'pair_id': f'pair-{i}', 'split': 'train' if i == 0 else 'held_out'}
        for eye, side in enumerate(('left', 'right')):
            image = np.full((480, 640), i*2+eye, dtype=np.uint8)
            image[0, 0] = 10+i*2+eye
            path = tmp_path/f'{side}-{i}.png'
            path.write_bytes(cv2.imencode('.png', image)[1].tobytes())
            pair[side] = {'path': path.name, 'frame_id': i, 'exposure_timestamp_ns': i*10000000+eye*10,
                          'clock_id': 'declared-shared-clock', 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
        manifest['pairs'].append(pair)
    return manifest, left, right


def test_matching_software_timestamps_do_not_establish_sync(tmp_path):
    manifest, left, right = manifest_fixture(tmp_path)
    result = audit_manifest(manifest, left, right, base_dir=tmp_path)
    assert not result['synchronization_contract_satisfied']
    assert not result['acceptance_requirements_passed']
    assert result['intrinsics_heldout_independence_verified']
    assert result['pairs'][0]['declared_pair_skew_ns'] == 10
    assert not result['pairing_inferred_from_filename_order']


@pytest.mark.parametrize('case', ['duplicate_frame', 'duplicate_image', 'missing_eye', 'wrong_size', 'lens_identity',
                                   'hash_mismatch', 'heldout_intrinsic_leak', 'duplicate_pair_id', 'no_holdout'])
def test_manifest_rejects_identity_pairing_size_and_leakage_errors(tmp_path, case):
    manifest, left, right = manifest_fixture(tmp_path)
    if case == 'duplicate_frame':
        manifest['pairs'][1]['left']['frame_id'] = manifest['pairs'][0]['left']['frame_id']
    elif case == 'duplicate_image':
        manifest['pairs'][1]['right']['path'] = manifest['pairs'][0]['left']['path']
    elif case == 'missing_eye':
        del manifest['pairs'][0]['right']
    elif case == 'wrong_size':
        path = tmp_path/manifest['pairs'][0]['left']['path']
        path.write_bytes(cv2.imencode('.png', np.zeros((4, 4), dtype=np.uint8))[1].tobytes())
        manifest['pairs'][0]['left'].pop('sha256')
    elif case == 'lens_identity':
        manifest['right']['lens_id'] = 'wrong-lens'
    elif case == 'hash_mismatch':
        manifest['pairs'][0]['left']['sha256'] = '0'*64
    elif case == 'heldout_intrinsic_leak':
        left['calibration_image_sha256'] = [manifest['pairs'][1]['left']['sha256']]
    elif case == 'duplicate_pair_id':
        manifest['pairs'][1]['pair_id'] = manifest['pairs'][0]['pair_id']
    else:
        manifest['pairs'][1]['split'] = 'train'
    with pytest.raises(ValueError):
        audit_manifest(manifest, left, right, base_dir=tmp_path)


def test_hardware_sync_requires_hashed_trace_and_human_review_declaration(tmp_path):
    manifest, left, right = manifest_fixture(tmp_path)
    path = tmp_path/'synthetic-evidence.txt'
    path.write_text('SYNTHETIC UNIT TEST FIXTURE; NOT A PHYSICAL TIMING TRACE', encoding='utf-8')
    manifest['synchronization'].update(method='hardware_trigger',
        evidence={'kind': 'trigger_trace', 'path': path.name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    result = audit_manifest(manifest, left, right, base_dir=tmp_path)
    assert not result['synchronization_contract_satisfied']
    manifest['synchronization']['evidence_review_status'] = 'user_verified_hardware_evidence'
    result = audit_manifest(manifest, left, right, base_dir=tmp_path)
    # The software only enforces the evidence contract and hashes. This synthetic
    # declaration does not constitute actual hardware evidence or release.
    assert result['synchronization_contract_satisfied']
    assert 'does not interpret timing traces' in result['limits']


def test_clock_identity_and_skew_cannot_be_inferred(tmp_path):
    manifest, left, right = manifest_fixture(tmp_path)
    manifest['pairs'][0]['right']['clock_id'] = 'different-clock'
    manifest['pairs'][1]['right']['exposure_timestamp_ns'] += 100000
    result = audit_manifest(manifest, left, right, base_dir=tmp_path)
    assert not result['acceptance_requirements_passed']
    assert len(result['synchronization_issues']) == 2


def test_missing_intrinsic_hash_list_leaves_independence_unverified(tmp_path):
    manifest, left, right = manifest_fixture(tmp_path)
    left.pop('calibration_image_sha256')
    result = audit_manifest(manifest, left, right, base_dir=tmp_path)
    assert not result['intrinsics_heldout_independence_verified']
    assert not result['acceptance_requirements_passed']


@pytest.mark.parametrize('changed', ['board', 'intrinsics'])
def test_point_api_rejects_geometry_or_profile_changes_after_manifest_audit(tmp_path, changed):
    manifest, left, right = manifest_fixture(tmp_path)
    audit = audit_manifest(manifest, left, right, base_dir=tmp_path)
    pairs, left, right, board, _, _ = geometry()
    board = copy.deepcopy(manifest['board'])
    if changed == 'board':
        board['square_mm'] = 21.
        message = 'board changed after manifest audit'
    else:
        left['K'][0][0] += .1
        message = 'left intrinsic profile changed after manifest audit'
    with pytest.raises(ValueError, match=message):
        calibrate_points(pairs, left, right, board, manifest_audit=audit)


def test_declared_chessboard_detection_and_source_hash_binding(tmp_path):
    manifest, left, right = manifest_fixture(tmp_path)
    for i, pair in enumerate(manifest['pairs']):
        for eye, side in enumerate(('left', 'right')):
            image = np.full((480, 640), 250-eye, dtype=np.uint8)
            for row in range(7):
                for col in range(10):
                    y, x = 80+i*5+row*32, 100+eye*6+col*32
                    image[y:y+32, x:x+32] = (10+eye) if (row+col) % 2 else (240-eye)
            path = tmp_path/pair[side]['path']
            path.write_bytes(cv2.imencode('.png', image)[1].tobytes())
            pair[side]['sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
    audit = audit_manifest(manifest, left, right, base_dir=tmp_path)
    points = detect_manifest_points(audit)
    assert len(points) == 2
    assert all(pair['left_points'].shape == pair['right_points'].shape == (1, 54, 2) for pair in points)
    assert points[0]['left_image_sha256'] == audit['pairs'][0]['left']['sha256']
    path = tmp_path/manifest['pairs'][0]['left']['path']
    path.write_bytes(path.read_bytes()+b'changed fixture')
    with pytest.raises(ValueError, match='changed after manifest audit'):
        detect_manifest_points(audit)
