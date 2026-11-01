"""Known synthetic geometry and native capture-contract negative cases."""
from pathlib import Path
import copy
import hashlib
import json
import sys
import zlib

import cv2
import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.calibrate_fisheye_profile import calibrate_observations, load_dataset, validate_manifest, _domain
from tools.stereo_fisheye_calibrate import board_points, validate_intrinsics
from tools.wideangle_mapping_audit import audit_profile


def synthetic_dataset():
    manifest = {'camera_id': 'SYNTHETIC-L', 'lens_id': 'SYNTHETIC-LENS-L',
        'profile_id': 'synthetic-intrinsic-profile', 'capture_mode_id': 'synthetic-vga-rgb565',
        'provenance': 'synthetic', 'image_size': [640, 480],
        'board': {'cols': 9, 'rows': 6, 'square_mm': 20},
        'model_scope': {'projection': 'forward_rectilinear', 'maximum_ray_angle_deg': 75}, 'views': []}
    world = board_points(manifest['board'])
    k = np.array([[360., 0, 319.5], [0, 365., 239.5], [0, 0, 1.]])
    d = np.array([-.04, .008, -.001, .0002])
    observations = []
    for i in range(30):
        r = np.array([.14*(i % 4-1.5), .18*(i % 5-2), .04*(i % 3-1)])
        t = np.array([-80.+45*(i % 5-2), -50.+30*(i % 4-1.5), 390.+23*(i % 6)])
        corners, _ = cv2.fisheye.projectPoints(world, r, t, k, d)
        digest = hashlib.sha256(corners.tobytes()).hexdigest()
        name = f'synthetic-view-{i}'
        split = 'train' if i < 24 else ('model_selection' if i < 26 else 'held_out')
        manifest['views'].append({'view_id': name, 'pose_id': f'pose-{i}', 'session_id': 'synthetic-session',
                                  'split': split, 'path': name+'.png', 'sha256': digest})
        observations.append({'view_id': name, 'image_sha256': digest, 'corners': corners})
    return manifest, observations, k, d


def test_known_four_coefficient_recovery_and_consumable_profile():
    manifest, observations, k, d = synthetic_dataset()
    result = calibrate_observations(manifest, observations)
    assert result['passed'] and result['provenance'] == 'synthetic'
    np.testing.assert_allclose(result['K'], k, atol=1e-4)
    np.testing.assert_allclose(result['D'], d, atol=1e-5)
    assert result['held_out_max_rms_px'] < 1e-5
    assert len(result['calibration_image_sha256']) == 26
    assert len(result['training_image_sha256']) == 24
    assert not set(result['calibration_image_sha256']).intersection(result['held_out_image_sha256'])
    validate_intrinsics(result, 'generated_profile')
    mapping = audit_profile(result, output_size=[64, 48], output_k=[[120., 0, 31.5], [0, 120., 23.5], [0, 0, 1]])
    assert mapping['passed']
    assert not result['hardware_release_allowed'] and not result['candidate_ready_for_profile_review']


def test_heldout_corruption_fails_without_changing_training_fit():
    manifest, observations, _, _ = synthetic_dataset()
    clean = calibrate_observations(manifest, observations)
    observations[-1]['corners'] = observations[-1]['corners'].copy()
    observations[-1]['corners'][0, 13] += [30., -25.]
    changed = calibrate_observations(manifest, observations)
    np.testing.assert_array_equal(changed['K'], clean['K'])
    np.testing.assert_array_equal(changed['D'], clean['D'])
    assert not changed['passed'] and changed['held_out_max_rms_px'] > 1


@pytest.mark.parametrize('case', ['pose_id', 'near_pose', 'sha_leak', 'identity', 'corner_hash'])
def test_explicit_split_identity_and_pose_independence(case):
    manifest, observations, _, _ = synthetic_dataset()
    if case == 'pose_id':
        manifest['views'][-1]['pose_id'] = manifest['views'][0]['pose_id']
    elif case == 'near_pose':
        observations[-1]['corners'] = observations[0]['corners'].copy()
    elif case == 'sha_leak':
        manifest['views'][-1]['sha256'] = manifest['views'][0]['sha256']
    elif case == 'identity':
        manifest['views'][-1]['lens_id'] = 'OTHER-LENS'
    else:
        observations[-1]['image_sha256'] = '0'*64
    with pytest.raises(ValueError):
        calibrate_observations(manifest, observations)


@pytest.mark.parametrize('scope', [
    {'projection': 'full_spherical_200deg', 'maximum_ray_angle_deg': 100},
    {'projection': 'forward_rectilinear', 'maximum_ray_angle_deg': 90},
])
def test_unsupported_200_degree_or_horizon_scope_is_rejected(scope):
    manifest, observations, _, _ = synthetic_dataset()
    manifest['model_scope'] = scope
    with pytest.raises(ValueError, match='unsupported'):
        calibrate_observations(manifest, observations)


def test_nonmonotonic_radial_model_fails_forward_domain_gate():
    k = np.array([[80., 0, 31.5], [0, 80., 23.5], [0, 0, 1.]])
    result = _domain(k, np.array([-1., 0., 0., 0.]), (64, 48), 75)
    assert result['radial_derivative_minimum'] < 0
    assert not result['supported_forward_domain_passed']
    assert not result['merchant_200_degree_claim_verified']


def native_fixture(tmp_path):
    manifest, observations, _, _ = synthetic_dataset()
    words = np.full((480, 640), 0xffff, dtype='<u2')
    for row in range(7):
        for col in range(10):
            if (row+col) % 2:
                words[80+row*32:80+(row+1)*32, 100+col*32:100+(col+1)*32] = 0
    image = np.repeat(np.where(words == 0, 0, 255).astype(np.uint8)[..., None], 3, axis=-1)
    image_path, raw_path, meta_path = tmp_path/'frame.png', tmp_path/'frame.rgb565', tmp_path/'frame.json'
    raw_path.write_bytes(words.tobytes())
    image_path.write_bytes(cv2.imencode('.png', image)[1].tobytes())
    metadata = {'schema': 1, 'source_kind': 'offline_uart_replay', 'hardware_accessed': False,
        'identity_binding': {key: manifest[key] for key in ('camera_id', 'lens_id', 'profile_id', 'capture_mode_id')},
        'width': 640, 'height': 480, 'frame_id': 1, 'source_crc32': f'{zlib.crc32(words.tobytes()):08X}',
        'raw_path': raw_path.name, 'raw_sha256': hashlib.sha256(raw_path.read_bytes()).hexdigest(),
        'image_path': image_path.name, 'image_sha256': hashlib.sha256(image_path.read_bytes()).hexdigest(),
        'geometry_applied': False, 'pixel_format': 'RGB565_LE',
        'identity_binding_kind': 'operator_declared_single_eye_connection', 'identity_verified_on_wire': False}
    meta_path.write_text(json.dumps(metadata), encoding='utf-8')
    manifest['views'][0].update(path=image_path.name, sha256=metadata['image_sha256'],
        metadata_path=meta_path.name, metadata_sha256=hashlib.sha256(meta_path.read_bytes()).hexdigest())
    return manifest, metadata, image_path, raw_path, meta_path


@pytest.mark.parametrize('case', ['png_sha', 'metadata_identity', 'raw_sha', 'source_crc', 'geometry'])
def test_native_image_metadata_and_raw_integrity_are_bound(tmp_path, case):
    manifest, metadata, image_path, raw_path, meta_path = native_fixture(tmp_path)
    if case == 'png_sha':
        image_path.write_bytes(image_path.read_bytes()+b'tampered')
    elif case == 'metadata_identity':
        metadata['identity_binding']['camera_id'] = 'OTHER-CAMERA'
    elif case == 'raw_sha':
        raw_path.write_bytes(raw_path.read_bytes()+b'tampered')
    elif case == 'source_crc':
        metadata['source_crc32'] = '00000000'
    else:
        metadata['geometry_applied'] = True
    if case not in ('png_sha', 'raw_sha'):
        meta_path.write_text(json.dumps(metadata), encoding='utf-8')
        manifest['views'][0]['metadata_sha256'] = hashlib.sha256(meta_path.read_bytes()).hexdigest()
    with pytest.raises(ValueError):
        load_dataset(manifest, base_dir=tmp_path)


def test_native_fixture_detection_is_bound_and_replay_stays_nonphysical(tmp_path):
    from tools.calibrate_fisheye_profile import _decode_bound_capture
    manifest, metadata, image_path, raw_path, meta_path = native_fixture(tmp_path)
    image = cv2.imdecode(np.fromfile(image_path, dtype=np.uint8), cv2.IMREAD_COLOR)
    capture = _decode_bound_capture(manifest['views'][0], manifest, tmp_path, image, image_path.resolve())
    assert not capture['physical_capture_record'] and not capture['identity_verified_on_wire']
    assert capture['raw_sha256'] == metadata['raw_sha256']


def test_self_declared_physical_capture_without_raw_build_contract_is_unverified(tmp_path):
    from tools.calibrate_fisheye_profile import _decode_bound_capture
    manifest, metadata, image_path, raw_path, meta_path = native_fixture(tmp_path)
    metadata.update(source_kind='physical_native_camera', hardware_accessed=True)
    meta_path.write_text(json.dumps(metadata), encoding='utf-8')
    manifest['views'][0]['metadata_sha256'] = hashlib.sha256(meta_path.read_bytes()).hexdigest()
    image = cv2.imdecode(np.fromfile(image_path, dtype=np.uint8), cv2.IMREAD_COLOR)
    record = _decode_bound_capture(manifest['views'][0], manifest, tmp_path, image, image_path.resolve())
    assert not record['physical_capture_record'] and not record['upstream_raw_contract_hash_bound']
