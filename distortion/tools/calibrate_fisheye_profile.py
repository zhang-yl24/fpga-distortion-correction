"""Build an identity-bound four-coefficient fisheye profile from explicit views.

The fixed model is fitted on train views only. Model-selection and held-out
views remain explicit and disjoint by image content and physical pose ID.
The supported scope is a forward rectilinear window below 180 degrees; a seller
claim of 200 degrees is not a measured field or support for rear-hemisphere rays.
"""
from pathlib import Path
import argparse
import hashlib
import json
import math
import sys
import zlib

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.calibrate import fit, validate
from tools.stereo_fisheye_calibrate import board_points, _canonical_sha, _identity, _file
from tools.wideangle_mapping_audit import _size

cv2.setNumThreads(1)
cv2.ocl.setUseOpenCL(False)
IDENTITY = ('camera_id', 'lens_id', 'profile_id', 'capture_mode_id')


def _digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _valid_digest(value):
    return isinstance(value, str) and len(value) == 64 and all(c in '0123456789abcdefABCDEF' for c in value)


def validate_manifest(manifest):
    for key in IDENTITY:
        _identity(manifest.get(key), key)
    size = _size(manifest['image_size'], 'image_size')
    if size[0]*size[1] > 2500000:
        raise ValueError('image_size exceeds the 2500000-pixel offline budget')
    board_points(manifest['board'])
    scope = manifest.get('model_scope', {})
    theta = scope.get('maximum_ray_angle_deg')
    if scope.get('projection') != 'forward_rectilinear' or isinstance(theta, bool) or not isinstance(theta, (int, float)) or not math.isfinite(theta) or not 0 < theta < 90:
        raise ValueError('supported model_scope requires forward_rectilinear and 0 < maximum_ray_angle_deg < 90; full 200-degree/rear-hemisphere calibration is unsupported')
    rows = manifest.get('views')
    if not isinstance(rows, list) or not rows:
        raise ValueError('explicit train/model_selection/held_out views are required')
    names, hashes, poses = set(), set(), {}
    for view in rows:
        name = _identity(view.get('view_id'), 'view_id')
        if name in names:
            raise ValueError('duplicate view_id')
        names.add(name)
        for key in ('pose_id', 'session_id'):
            _identity(view.get(key), key)
        split = view.get('split')
        if split not in ('train', 'model_selection', 'held_out'):
            raise ValueError('every view needs an explicit train/model_selection/held_out split')
        for key in IDENTITY:
            if view.get(key, manifest[key]) != manifest[key]:
                raise ValueError('view '+name+' '+key+' differs from the dataset identity')
        if not _valid_digest(view.get('sha256')):
            raise ValueError('every view requires an explicit image sha256')
        digest = view['sha256'].lower()
        if digest in hashes:
            raise ValueError('duplicate image content or train/held-out hash leakage')
        hashes.add(digest)
        poses.setdefault(view['pose_id'], set()).add(split)
    if any(len(splits) > 1 for splits in poses.values()):
        raise ValueError('pose reused across train/model_selection/held_out; pose IDs are global physical-pose identities')
    if sum(view['split'] == 'train' for view in rows) < 12 or sum(view['split'] == 'held_out' for view in rows) < 3:
        raise ValueError('need at least 12 train and 3 held_out views')
    if len({view['pose_id'] for view in rows if view['split'] == 'train'}) < 12:
        raise ValueError('need at least 12 distinct training poses')
    cells = manifest.get('required_coverage_cells', [[r, c] for r in range(3) for c in range(3)])
    if not isinstance(cells, list) or not cells or any(not isinstance(cell, list) or len(cell) != 2 or any(type(v) is not int or v not in (0, 1, 2) for v in cell) for cell in cells):
        raise ValueError('required_coverage_cells must explicitly list source-image 3x3 cells')
    return size


def _decode_bound_capture(view, manifest, base_dir, image, image_path):
    """Bind native PNG to metadata and original RGB565 bytes; infer no eye ID."""
    if not view.get('metadata_path'):
        raise ValueError('physical/replay dataset requires metadata_path and metadata_sha256 per view')
    meta_path = _file(base_dir, view['metadata_path'], 'capture metadata')
    if not _valid_digest(view.get('metadata_sha256')) or _digest(meta_path) != view['metadata_sha256'].lower():
        raise ValueError('capture metadata sha256 mismatch')
    metadata = json.loads(meta_path.read_text(encoding='utf-8-sig'))
    if metadata.get('geometry_applied') is not False:
        raise ValueError('calibration requires untouched source pixels, geometry_applied=false')
    if [metadata.get('width'), metadata.get('height')] != list(manifest['image_size']):
        raise ValueError('capture metadata dimensions differ from the dataset mode')
    binding = metadata.get('identity_binding')
    if not isinstance(binding, dict) or any(binding.get(key) != manifest[key] for key in IDENTITY):
        raise ValueError('capture metadata identity_binding differs from camera/lens/profile/mode')
    if metadata.get('pixel_format') != 'RGB565_LE':
        raise ValueError('bound capture metadata must specify pixel_format=RGB565_LE')
    raw_path = _file(meta_path.parent, metadata.get('raw_path'), 'raw RGB565 source')
    payload = raw_path.read_bytes()
    if len(payload) != image.shape[0]*image.shape[1]*2:
        raise ValueError('raw RGB565 payload size differs from image_size')
    raw_sha = hashlib.sha256(payload).hexdigest()
    if not _valid_digest(metadata.get('raw_sha256')) or metadata['raw_sha256'].lower() != raw_sha:
        raise ValueError('raw RGB565 sha256 mismatch')
    expected_crc = f'{zlib.crc32(payload):08X}'
    if not isinstance(metadata.get('source_crc32'), str) or metadata['source_crc32'].upper() != expected_crc:
        raise ValueError('raw RGB565 source CRC32 mismatch')
    if metadata.get('received_crc32') is not None and str(metadata['received_crc32']).upper() != expected_crc:
        raise ValueError('raw RGB565 received CRC32 mismatch')
    if metadata.get('image_sha256', '').lower() != view['sha256'].lower():
        raise ValueError('metadata PNG hash differs from the manifest image')
    source_image = _file(meta_path.parent, metadata.get('image_path'), 'metadata PNG source')
    if source_image != image_path:
        raise ValueError('metadata image_path differs from the manifest path')
    words = np.frombuffer(payload, dtype='<u2').reshape(image.shape[:2])
    r, g, b = (words >> 11) & 31, (words >> 5) & 63, words & 31
    expected = np.stack(((b << 3) | (b >> 2), (g << 2) | (g >> 4), (r << 3) | (r >> 2)), axis=-1).astype(np.uint8)
    if not np.array_equal(image, expected):
        raise ValueError('PNG pixels differ from the untouched raw RGB565 payload')
    expected_contract = {'protocol': 'PGFRAME1', 'payload_role': 'native_raw',
                         'geometry_applied': False, 'image_size': list(manifest['image_size'])}
    build_record = metadata.get('build_binding')
    bound_raw_contract = bool(metadata.get('upstream_raw_contract_hash_bound') is True and
        metadata.get('upstream_payload_role') == 'native_raw' and isinstance(build_record, dict) and
        build_record.get('raw_capture_contract') == expected_contract)
    physical = bool(metadata.get('source_kind') == 'physical_native_camera' and
                    metadata.get('hardware_accessed') is True and bound_raw_contract)
    return {'metadata_path': str(meta_path), 'metadata_sha256': _digest(meta_path),
        'raw_path': str(raw_path), 'raw_sha256': raw_sha, 'raw_crc32': expected_crc,
        'source_kind': metadata.get('source_kind', 'unspecified'), 'physical_capture_record': physical,
        'upstream_raw_contract_hash_bound': bound_raw_contract,
        'identity_binding_kind': metadata.get('identity_binding_kind', 'unspecified'),
        'identity_verified_on_wire': metadata.get('identity_verified_on_wire') is True}


def load_dataset(manifest, *, base_dir):
    """Read native captures, verify hashes/metadata/raw pixels and detect corners."""
    size = validate_manifest(manifest)
    rows, observations, paths = [], [], set()
    board = manifest['board']
    for view in manifest['views']:
        path = _file(base_dir, view.get('path'), view['view_id'])
        if str(path) in paths or _digest(path) != view['sha256'].lower():
            raise ValueError('duplicate image path or image SHA256 mismatch')
        paths.add(str(path))
        image = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)
        if image is None or (image.shape[1], image.shape[0]) != size:
            raise ValueError('unreadable image or capture mode/image_size mismatch')
        capture = _decode_bound_capture(view, manifest, base_dir, image, path)
        ok, corners = cv2.findChessboardCornersSB(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY), (board['cols'], board['rows']))
        if not ok:
            raise ValueError('complete declared chessboard missing from '+view['view_id']+'; no views silently dropped')
        observations.append({'view_id': view['view_id'], 'image_sha256': view['sha256'].lower(),
                             'corners': corners.astype(np.float64).reshape(1, -1, 2)})
        rows.append({'view_id': view['view_id'], 'path': str(path), 'image_sha256': view['sha256'].lower(), **capture})
    return {'manifest_sha256': _canonical_sha(manifest), 'views': rows,
            'all_physical_capture_records': all(row['physical_capture_record'] for row in rows),
            'identity_verified_on_wire': all(row['identity_verified_on_wire'] for row in rows),
            'identity_note': 'Camera/eye connection is operator declared unless wire identity is explicitly present; hashed metadata is not independent physical identity verification.'}, observations


def _domain(k, d, size, maximum_angle):
    theta = math.radians(maximum_angle)
    # The derivative of theta_d(theta) is a quartic in theta^2. Its
    # minimum is evaluated at interval endpoints and real stationary roots.
    polynomial = np.array([1., 3*d[0], 5*d[1], 7*d[2], 9*d[3]])
    derivative = np.polynomial.polynomial.polyder(polynomial)
    roots = np.polynomial.polynomial.polyroots(derivative)
    candidates = [0., theta*theta] + [float(root.real) for root in roots if abs(root.imag) < 1e-9 and 0 < root.real < theta*theta]
    minimum = float(np.min(np.polynomial.polynomial.polyval(candidates, polynomial)))
    t2 = theta*theta
    maximum_distorted_radius = float(theta*(1+t2*(d[0]+t2*(d[1]+t2*(d[2]+t2*d[3])))))
    mx, my = cv2.fisheye.initUndistortRectifyMap(k, d, np.eye(3), k, size, cv2.CV_32FC1)
    yy, xx = np.indices(mx.shape)
    ray_angle = np.arctan(np.hypot((xx-k[0, 2])/k[0, 0], (yy-k[1, 2])/k[1, 1]))
    requested = ray_angle <= theta
    dxdy, dxdx = np.gradient(mx.astype(np.float64))
    dydy, dydx = np.gradient(my.astype(np.float64))
    det = dxdx*dydy-dxdy*dydx
    finite = bool(np.isfinite(mx).all() and np.isfinite(my).all() and np.isfinite(det).all())
    folds = int(np.count_nonzero(requested & (det <= 0)))
    compatible = bool(finite and minimum > 0 and 0 < maximum_distorted_radius < math.pi/2 and folds == 0)
    return {'maximum_ray_angle_deg': maximum_angle, 'claimed_total_rectilinear_field_deg': None,
        'radial_derivative_minimum': minimum, 'distorted_radius_at_maximum_ray_angle': maximum_distorted_radius,
        'opencv_inverse_clip_radius': math.pi/2, 'finite_same_K_map': finite,
        'same_K_map_pixels_in_requested_angle': int(requested.sum()), 'same_K_map_folded_pixels_in_requested_angle': folds,
        'supported_forward_domain_passed': compatible,
        'merchant_200_degree_claim_verified': False, 'full_200_degree_domain_supported': False,
        'limits': 'Forward-hemisphere model only. OpenCV 4.11 undistortPoints clips distorted radius to pi/2; no rear-hemisphere or measured 200-degree coverage is established. Same-K map folds are finite-difference diagnostics; monotonic radial derivative is audited analytically over the declared angular interval.'}


def calibrate_observations(manifest, observations, *, capture_audit=None):
    """Fit the fixed four-coefficient model; direct point calls stay synthetic."""
    size = validate_manifest(manifest)
    obj = board_points(manifest['board'])
    by_id = {view['view_id']: view for view in manifest['views']}
    if len(observations) != len(by_id) or {row['view_id'] for row in observations} != set(by_id):
        raise ValueError('corner observations must cover exactly the explicit manifest views')
    if capture_audit is not None and capture_audit.get('manifest_sha256') != _canonical_sha(manifest):
        raise ValueError('manifest changed after native capture audit')
    corner_sets, rows = [], []
    for item in observations:
        view = by_id[item['view_id']]
        if item.get('image_sha256') != view['sha256'].lower():
            raise ValueError('detected corners are not bound to the manifest image SHA256')
        xy = np.asarray(item['corners'], dtype=np.float64)
        if xy.size != obj.shape[1]*2:
            raise ValueError('corner count differs from the declared board')
        xy = xy.reshape(1, -1, 2)
        if not np.isfinite(xy).all() or np.any(xy[..., 0] < 0) or np.any(xy[..., 0] >= size[0]) or np.any(xy[..., 1] < 0) or np.any(xy[..., 1] >= size[1]):
            raise ValueError('corners must be finite and in the declared image')
        if np.linalg.matrix_rank(xy.reshape(-1, 2)-xy.reshape(-1, 2).mean(axis=0)) < 2:
            raise ValueError('degenerate chessboard pose')
        for previous, previous_view in corner_sets:
            if view['split'] != previous_view['split']:
                delta = min(float(np.sqrt(np.mean(np.sum((xy-previous)**2, axis=-1)))),
                            float(np.sqrt(np.mean(np.sum((xy-previous[:, ::-1])**2, axis=-1)))))
                if delta < 2.:
                    raise ValueError('corners repeat a pose across dataset splits despite differing IDs')
        corner_sets.append((xy, view))
        rows.append((view, xy))
    train = [(view, xy) for view, xy in rows if view['split'] == 'train']
    rms, k, d, rvecs, tvecs = fit([obj]*len(train), [xy for _, xy in train], size, 'fisheye')
    d = d.reshape(-1)
    if not np.isfinite(k).all() or not np.isfinite(d).all() or not math.isfinite(rms):
        raise ValueError('fisheye fit produced nonfinite parameters')
    domain = _domain(k, d, size, manifest['model_scope']['maximum_ray_angle_deg'])
    errors, coverage, radial, observed_distorted_max = [], {}, {}, 0.
    observed_forward_max = 0.
    for view, xy in rows:
        distorted_radius = np.hypot((xy[..., 0]-k[0, 2])/k[0, 0], (xy[..., 1]-k[1, 2])/k[1, 1])
        observed_distorted_max = max(observed_distorted_max, float(distorted_radius.max()))
        if distorted_radius.max() >= math.pi/2:
            raise ValueError('observed corners exceed the supported OpenCV inverse distorted-radius domain; do not claim full 200-degree calibration')
        error = validate([obj], [xy], k, d, 'fisheye')[0]
        undistorted = cv2.fisheye.undistortPoints(xy, k, d)
        angle = np.degrees(np.arctan(np.linalg.norm(undistorted, axis=-1)))
        observed_forward_max = max(observed_forward_max, float(angle.max()))
        errors.append({'view_id': view['view_id'], 'pose_id': view['pose_id'], 'session_id': view['session_id'],
                       'split': view['split'], 'held_pose_reprojection_rms_px': error,
                       'model_inferred_maximum_ray_angle_deg': float(angle.max())})
        split = view['split']
        counts = coverage.setdefault(split, np.zeros((3, 3), dtype=int))
        for x, y in xy.reshape(-1, 2):
            counts[min(2, int(y*3/size[1])), min(2, int(x*3/size[0]))] += 1
        # Sensor-position radius is not a measured angular field of view.
        rho = np.hypot((xy[..., 0]-k[0, 2])/(size[0]/2), (xy[..., 1]-k[1, 2])/(size[1]/2))
        hist, _ = np.histogram(rho, [0, .25, .5, .75, 1., np.inf])
        radial.setdefault(split, np.zeros(5, dtype=int))[:] += hist
    train_errors = [row['held_pose_reprojection_rms_px'] for row in errors if row['split'] == 'train']
    held = [row['held_pose_reprojection_rms_px'] for row in errors if row['split'] == 'held_out']
    selection = [row['held_pose_reprojection_rms_px'] for row in errors if row['split'] == 'model_selection']
    cells = manifest.get('required_coverage_cells', [[r, c] for r in range(3) for c in range(3)])
    coverage_passed = all(coverage['train'][r, c] >= 15 and coverage['held_out'][r, c] >= 3 for r, c in cells)
    observations_inside_scope = observed_forward_max <= manifest['model_scope']['maximum_ray_angle_deg']
    numeric = bool(rms <= .5 and np.mean(held) <= .5 and max(held) <= 1. and observations_inside_scope and
                   (not selection or max(selection) <= 1.) and domain['supported_forward_domain_passed'])
    physical = bool(capture_audit and capture_audit['all_physical_capture_records'] and manifest.get('provenance') == 'real_sensor_captures')
    provenance = 'real_chessboard_captures' if physical else ('synthetic' if capture_audit is None else 'offline_or_unverified_capture_origin')
    used = [view['sha256'].lower() for view in manifest['views'] if view['split'] in ('train', 'model_selection')]
    result = {key: manifest[key] for key in IDENTITY}
    result.update({'schema': 1, 'model': 'fisheye', 'image_size': list(size), 'K': k.tolist(), 'D': d.tolist(),
        'provenance': provenance, 'calibration_image_sha256': used,
        'training_image_sha256': [view['sha256'].lower() for view, _ in train],
        'held_out_image_sha256': [view['sha256'].lower() for view in manifest['views'] if view['split'] == 'held_out'],
        'model_scope': manifest['model_scope'], 'source_dataset_manifest_sha256': _canonical_sha(manifest),
        'hardware_accessed_by_calibrator': False, 'hardware_release_allowed': False,
        'passed': numeric, 'independent_spatial_coverage_passed': bool(coverage_passed),
        'candidate_ready_for_profile_review': bool(numeric and coverage_passed and physical),
        'identity_verified_on_wire': bool(capture_audit and capture_audit['identity_verified_on_wire']),
        'identity_binding_note': 'Manifest/native metadata bind the operator-declared physical connection; hashes do not independently verify sensor/eye identity.',
        'training_rms_px': float(rms), 'held_out_mean_rms_px': float(np.mean(held)), 'held_out_max_rms_px': float(max(held)),
        'per_view_validation': errors, 'source_image_3x3_corner_counts': {split: value.tolist() for split, value in coverage.items()},
        'source_image_radius_histogram': {split: value.tolist() for split, value in radial.items()},
        'radius_histogram_bin_edges': [0, .25, .5, .75, 1., 'infinity'],
        'coverage_criteria': {'required_source_image_cells': cells, 'minimum_training_corners_per_cell': 15,
                              'minimum_held_out_corners_per_cell': 3, 'note': 'Engineering coverage checks; image radius/cell coverage is not measured angular or all-field optical acceptance.'},
        'maximum_observed_distorted_radius': observed_distorted_max,
        'maximum_observed_model_inferred_ray_angle_deg': observed_forward_max,
        'observations_inside_declared_forward_scope': bool(observations_inside_scope),
        'domain_audit': domain, 'capture_audit': capture_audit,
        'fixed_model': 'fisheye four distortion coefficients; no refit using held_out or model_selection views',
        'source_sha256': {str(path.relative_to(ROOT)): _digest(path) for path in
                          (Path(__file__), ROOT/'tools/calibrate.py', ROOT/'tools/stereo_fisheye_calibrate.py',
                           ROOT/'tools/wideangle_mapping_audit.py')},
        'limits': 'Training images alone estimate K/D. All training and model-selection image hashes are exported for downstream stereo leakage rejection; held-out views are used only for declared validation. Synthetic/API-only or replay inputs never become real-lens ready. A small reprojection residual and 3x3 coverage do not prove measured 200-degree support, independent optical straightness, stereo sync, depth accuracy or routed hardware readiness.'})
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    parser.add_argument('--output', type=Path, required=True, help='new flat profile JSON; directly consumable by wideangle/stereo tools')
    args = parser.parse_args()
    if not args.output.parent.is_dir() or args.output.exists():
        parser.error('output must be a new filename in an existing directory')
    manifest = json.loads(args.manifest.read_text(encoding='utf-8-sig'))
    audit, observations = load_dataset(manifest, base_dir=args.manifest.parent)
    profile = calibrate_observations(manifest, observations, capture_audit=audit)
    profile['source_dataset_manifest_file'] = str(args.manifest.resolve())
    profile['source_dataset_manifest_file_sha256'] = _digest(args.manifest)
    args.output.write_text(json.dumps(profile, indent=2, ensure_ascii=False, allow_nan=False)+'\n', encoding='utf-8')
    print(json.dumps({key: profile[key] for key in ('passed', 'candidate_ready_for_profile_review', 'provenance', 'held_out_mean_rms_px', 'hardware_release_allowed')}))
    if not profile['candidate_ready_for_profile_review']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
