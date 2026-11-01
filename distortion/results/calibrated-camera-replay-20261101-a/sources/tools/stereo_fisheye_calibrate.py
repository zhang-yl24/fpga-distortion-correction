"""Offline paired fisheye calibration with explicit pairing/evidence contracts.

The manifest names every left/right exposure; filename order never establishes
synchronization. Fixed real intrinsics and training pairs determine R/T. Separate
held-out pairs measure rectified vertical disparity. No dual-camera FPGA path,
physical synchronization, optical acceptance, or depth accuracy is established
by a numerical fit or a software timestamp alone.
"""
from pathlib import Path
import argparse
import hashlib
import json
import math
import math
import sys

import cv2
import numpy as np

# The native chessboard detector otherwise creates a machine-sized worker pool.
# Match the existing capture tools and keep offline calibration deterministic.
cv2.setNumThreads(1)
cv2.ocl.setUseOpenCL(False)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.wideangle_mapping_audit import _intrinsics, _size, _declared_scope_maximum


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _canonical_sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode('utf-8')).hexdigest()


def _identity(value, name):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(name+' must be an explicit nonempty string')
    return value


def validate_intrinsics(profile, label):
    if profile.get('model') != 'fisheye':
        raise ValueError(label+' model must be fisheye')
    for field in ('camera_id', 'lens_id', 'profile_id'):
        _identity(profile.get(field), label+'.'+field)
    _declared_scope_maximum(profile)
    k = _intrinsics(profile['K'], label+'.K')
    d = np.asarray(profile['D'], dtype=np.float64).reshape(-1)
    if d.shape != (4,) or not np.isfinite(d).all():
        raise ValueError(label+'.D needs all four finite coefficients')
    return k, d.reshape(4, 1), _size(profile['image_size'], label+'.image_size')


def board_points(board):
    cols, rows = board.get('cols'), board.get('rows')
    square = board.get('square_mm')
    if any(isinstance(v, bool) or not isinstance(v, int) or v < 3 for v in (cols, rows)):
        raise ValueError('board requires integer cols/rows >=3 (inner corners)')
    if cols*rows > 10000:
        raise ValueError('board corner count exceeds the supported 10000-corner budget')
    if isinstance(square, bool) or not isinstance(square, (float, int)) or not math.isfinite(square) or square <= 0:
        raise ValueError('square_mm must be a finite positive measured length')
    obj = np.zeros((1, cols*rows, 3), dtype=np.float64)
    obj[0, :, :2] = np.mgrid[0:cols, 0:rows].T.reshape(-1, 2)*square
    return obj


def _file(base, name, label):
    if not isinstance(name, str) or not name.strip():
        raise ValueError(label+' path is missing')
    path = Path(name)
    path = path if path.is_absolute() else Path(base)/path
    path = path.resolve()
    if not path.is_file():
        raise ValueError(label+' does not exist: '+str(path))
    return path


def audit_manifest(manifest, left_profile, right_profile, *, base_dir):
    """Read/hash explicit paired images and sync evidence; create no files."""
    _, _, size = validate_intrinsics(left_profile, 'left_profile')
    _, _, right_size = validate_intrinsics(right_profile, 'right_profile')
    if size != right_size:
        raise ValueError('left/right calibration image_size must match')
    board_points(manifest['board'])
    _identity(manifest.get('rig_id'), 'rig_id')
    if left_profile['camera_id'] == right_profile['camera_id']:
        raise ValueError('left and right camera_id must be distinct')
    for side, profile in (('left', left_profile), ('right', right_profile)):
        for field in ('camera_id', 'lens_id', 'profile_id'):
            if manifest.get(side, {}).get(field) != profile[field]:
                raise ValueError(side+' '+field+' does not match the bound intrinsic profile')
    pairs = manifest.get('pairs')
    if not isinstance(pairs, list) or not pairs:
        raise ValueError('explicit training and held_out pairs are required')
    sync = manifest.get('synchronization', {})
    max_skew = sync.get('maximum_pair_skew_ns')
    if isinstance(max_skew, bool) or not isinstance(max_skew, int) or max_skew < 0:
        raise ValueError('maximum_pair_skew_ns must be an explicit nonnegative integer')
    pair_ids, frames, hashes, paths = set(), set(), set(), set()
    audited, sync_missing = [], []
    held_hashes = set()
    for pair in pairs:
        pair_id = _identity(pair.get('pair_id'), 'pair_id')
        if pair_id in pair_ids:
            raise ValueError('duplicate pair_id: '+pair_id)
        pair_ids.add(pair_id)
        split = pair.get('split')
        if split not in ('train', 'held_out'):
            raise ValueError('every pair requires split=train or held_out')
        row = {'pair_id': pair_id, 'split': split}
        for side, profile in (('left', left_profile), ('right', right_profile)):
            exposure = pair.get(side)
            if not isinstance(exposure, dict):
                raise ValueError(pair_id+' missing '+side+' exposure')
            frame_id = exposure.get('frame_id')
            if isinstance(frame_id, bool) or not isinstance(frame_id, (int, str)) or str(frame_id).strip() == '':
                raise ValueError(pair_id+' requires explicit '+side+' frame_id')
            key = (profile['camera_id'], str(frame_id))
            if key in frames:
                raise ValueError('duplicate frame_id or train/held_out frame leakage: '+str(key))
            frames.add(key)
            path = _file(base_dir, exposure.get('path'), pair_id+'.'+side)
            digest = _sha(path)
            if str(path) in paths or digest in hashes:
                raise ValueError('duplicate image/path or train/held_out content leakage: '+str(path))
            paths.add(str(path))
            hashes.add(digest)
            expected_hash = exposure.get('sha256')
            if expected_hash and (not isinstance(expected_hash, str) or expected_hash.lower() != digest):
                raise ValueError('declared image SHA256 mismatch: '+str(path))
            image = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
            if image is None or (image.shape[1], image.shape[0]) != size:
                raise ValueError('unreadable image or image_size differs from calibration: '+str(path))
            timestamp = exposure.get('exposure_timestamp_ns')
            clock = exposure.get('clock_id')
            if isinstance(timestamp, bool) or not isinstance(timestamp, int) or timestamp < 0 or not isinstance(clock, str) or not clock.strip():
                sync_missing.append(pair_id+'.'+side+': exposure timestamp/clock identity missing')
            row[side] = {'path': str(path), 'sha256': digest, 'frame_id': frame_id,
                         'exposure_timestamp_ns': timestamp, 'clock_id': clock}
            if split == 'held_out':
                held_hashes.add(digest)
        lt, rt = row['left']['exposure_timestamp_ns'], row['right']['exposure_timestamp_ns']
        comparable = (type(lt) is int and type(rt) is int and lt >= 0 and rt >= 0 and
                      bool(row['left']['clock_id']) and row['left']['clock_id'] == row['right']['clock_id'])
        skew = abs(lt-rt) if comparable else None
        row['declared_pair_skew_ns'] = skew
        if not comparable or skew > max_skew:
            sync_missing.append(pair_id+': clocks differ or declared exposure skew exceeds limit')
        audited.append(row)
    if not any(p['split'] == 'train' for p in audited) or not any(p['split'] == 'held_out' for p in audited):
        raise ValueError('both train and held_out pairs are mandatory')
    independence = True
    for label, profile in (('left', left_profile), ('right', right_profile)):
        intrinsic_hashes = profile.get('calibration_image_sha256')
        if not isinstance(intrinsic_hashes, list) or not intrinsic_hashes:
            independence = False
            continue
        if any(not isinstance(h, str) or len(h) != 64 or any(c not in '0123456789abcdefABCDEF' for c in h) for h in intrinsic_hashes):
            raise ValueError(label+' calibration_image_sha256 must list valid image hashes')
        if held_hashes.intersection(h.lower() for h in intrinsic_hashes):
            raise ValueError('held_out images were used in '+label+' intrinsic calibration')
    evidence_record = None
    evidence = sync.get('evidence')
    if isinstance(evidence, dict) and evidence.get('path'):
        evidence_path = _file(base_dir, evidence['path'], 'synchronization evidence')
        digest = _sha(evidence_path)
        if not isinstance(evidence.get('sha256'), str) or evidence['sha256'].lower() != digest:
            raise ValueError('synchronization evidence requires a matching explicit SHA256')
        evidence_record = {'path': str(evidence_path), 'sha256': digest, 'kind': evidence.get('kind')}
    acceptable_method = sync.get('method') in ('hardware_trigger', 'shared_sensor_exposure_clock', 'externally_measured_alignment')
    accepted_hardware_evidence = bool(evidence_record and evidence_record['kind'] in ('trigger_trace', 'exposure_timing_trace', 'external_alignment_measurement') and
        sync.get('evidence_review_status') == 'user_verified_hardware_evidence')
    synchronized = bool(acceptable_method and accepted_hardware_evidence and not sync_missing)
    real_capture_provenance = manifest.get('provenance') == 'real_paired_camera_captures'
    return {'schema': 1, 'hardware_accessed': False, 'pairs': audited, 'rig_id': manifest['rig_id'],
        'capture_provenance': manifest.get('provenance', 'unspecified'),
        'board_sha256': _canonical_sha(manifest['board']),
        'intrinsic_profile_sha256': {side: _canonical_sha(profile) for side, profile in
                                    (('left', left_profile), ('right', right_profile))},
        'image_size': list(size), 'board': manifest['board'], 'pairing_inferred_from_filename_order': False,
        'synchronization_method_declared': sync.get('method', 'unknown'),
        'synchronization_evidence_file': evidence_record, 'synchronization_issues': sync_missing,
        'synchronization_contract_satisfied': synchronized,
        'intrinsics_heldout_independence_verified': independence,
        'acceptance_requirements_passed': bool(synchronized and independence and real_capture_provenance),
        'limits': 'Exposure timestamps are manifest declarations, not independently measured synchronization. Evidence bytes are hashed; software does not interpret timing traces or verify a human review assertion. Physical sync requires reviewed hardware exposure evidence. Intrinsic held-out independence is checked only against the supplied calibration-image hash lists.'}


def calibrate_points(pairs, left_profile, right_profile, board, *, manifest_audit=None,
                     maximum_training_rms_px=.5, maximum_heldout_p95_y_px=.5,
                     maximum_heldout_y_px=1., minimum_training_pairs=8, minimum_heldout_pairs=3):
    """Fit fixed-intrinsic R/T from explicit point pairs, evaluate held-out pairs."""
    k1, d1, size = validate_intrinsics(left_profile, 'left_profile')
    k2, d2, size2 = validate_intrinsics(right_profile, 'right_profile')
    if size != size2 or left_profile['camera_id'] == right_profile['camera_id']:
        raise ValueError('distinct camera identities and matching image sizes are required')
    if manifest_audit is not None:
        if manifest_audit.get('board_sha256') != _canonical_sha(board):
            raise ValueError('board changed after manifest audit; square size and geometry must remain bound')
        for side, profile in (('left', left_profile), ('right', right_profile)):
            if manifest_audit.get('intrinsic_profile_sha256', {}).get(side) != _canonical_sha(profile):
                raise ValueError(side+' intrinsic profile changed after manifest audit')
    obj = board_points(board)
    if any(isinstance(value, bool) or not isinstance(value, int) or value < limit for value, limit in
           ((minimum_training_pairs, 3), (minimum_heldout_pairs, 1))):
        raise ValueError('minimum pair counts must be integer, training >=3 and held_out >=1')
    for value in (maximum_training_rms_px, maximum_heldout_p95_y_px, maximum_heldout_y_px):
        if not math.isfinite(value) or value <= 0:
            raise ValueError('all error gates must be finite and positive')
    normalized, names, hashes = [], set(), set()
    for pair in pairs:
        name = _identity(pair.get('pair_id'), 'pair_id')
        if name in names or pair.get('split') not in ('train', 'held_out'):
            raise ValueError('unique pair IDs and explicit train/held_out split required')
        names.add(name)
        row = {'pair_id': name, 'split': pair['split']}
        for side in ('left', 'right'):
            points = np.asarray(pair[side+'_points'], dtype=np.float64)
            if points.size != obj.shape[1]*2:
                raise ValueError('corner count differs from the declared board')
            points = points.reshape(1, -1, 2)
            if not np.isfinite(points).all() or np.any(points[..., 0] < 0) or np.any(points[..., 0] >= size[0]) or np.any(points[..., 1] < 0) or np.any(points[..., 1] >= size[1]):
                raise ValueError('corners must be finite and inside the bound image size')
            if np.linalg.matrix_rank(points.reshape(-1, 2)-points.reshape(-1, 2).mean(axis=0)) < 2:
                raise ValueError('degenerate board pose: detected corners must span two image dimensions')
            profile = left_profile if side == 'left' else right_profile
            scope_angle = _declared_scope_maximum(profile)
            if scope_angle is not None:
                pk, pd = (k1, d1) if side == 'left' else (k2, d2)
                radius = np.hypot((points[..., 0]-pk[0, 2])/pk[0, 0], (points[..., 1]-pk[1, 2])/pk[1, 1])
                if radius.max() >= math.pi/2:
                    raise ValueError(side+' corners exceed the profile forward inverse-model domain')
                rays = cv2.fisheye.undistortPoints(points, pk, pd)
                angles = np.degrees(np.arctan(np.linalg.norm(rays, axis=-1)))
                if not np.isfinite(angles).all() or angles.max() > scope_angle+1e-7:
                    raise ValueError(side+' corners exceed the profile model_scope')
            digest = hashlib.sha256(points.tobytes()).hexdigest()
            if digest in hashes:
                raise ValueError('duplicate corner set or train/held_out data leakage')
            hashes.add(digest)
            row[side+'_points'] = points
        normalized.append(row)
    train = [p for p in normalized if p['split'] == 'train']
    held = [p for p in normalized if p['split'] == 'held_out']
    if len(train) < minimum_training_pairs or len(held) < minimum_heldout_pairs:
        raise ValueError(f'need >={minimum_training_pairs} training and >={minimum_heldout_pairs} held_out pairs')
    if manifest_audit is not None:
        declared = {(p['pair_id'], p['split']) for p in manifest_audit['pairs']}
        if declared != {(p['pair_id'], p['split']) for p in normalized}:
            raise ValueError('point observations do not match the audited manifest pair IDs/splits')
        declared_pairs = {p['pair_id']: p for p in manifest_audit['pairs']}
        for pair in pairs:
            for side in ('left', 'right'):
                if pair.get(side+'_image_sha256') != declared_pairs[pair['pair_id']][side]['sha256']:
                    raise ValueError('detected point observations are not bound to the audited image hashes')
    result = cv2.fisheye.stereoCalibrate([obj]*len(train), [p['left_points'] for p in train],
        [p['right_points'] for p in train], k1.copy(), d1.copy(), k2.copy(), d2.copy(), size,
        flags=cv2.fisheye.CALIB_FIX_INTRINSIC,
        criteria=(cv2.TERM_CRITERIA_EPS+cv2.TERM_CRITERIA_MAX_ITER, 100, 1e-8))
    rms, _, _, _, _, rotation, translation = result[:7]
    if not np.isfinite(rotation).all() or not np.isfinite(translation).all() or not np.isfinite(rms):
        raise ValueError('stereo calibration produced nonfinite values')
    baseline = float(np.linalg.norm(translation))
    if baseline <= 1e-6 or not np.allclose(rotation.T@rotation, np.eye(3), atol=1e-6) or not np.isclose(np.linalg.det(rotation), 1., atol=1e-6):
        raise ValueError('degenerate stereo baseline or invalid rotation')
    r1, r2, p1, p2, q = cv2.fisheye.stereoRectify(k1, d1, k2, d2, size, rotation, translation,
        flags=cv2.CALIB_ZERO_DISPARITY, balance=0., fov_scale=1.)
    rows, held_errors = [], []
    for pair in normalized:
        left = cv2.fisheye.undistortPoints(pair['left_points'], k1, d1, R=r1, P=p1).reshape(-1, 2)
        right = cv2.fisheye.undistortPoints(pair['right_points'], k2, d2, R=r2, P=p2).reshape(-1, 2)
        errors = np.abs(left[:, 1]-right[:, 1])
        if not np.isfinite(left).all() or not np.isfinite(right).all():
            raise ValueError('rectified corners are nonfinite')
        rows.append({'pair_id': pair['pair_id'], 'split': pair['split'], 'corner_count': int(len(errors)),
            'rectified_absolute_y_mean_px': float(errors.mean()),
            'rectified_absolute_y_p95_px': float(np.percentile(errors, 95)),
            'rectified_absolute_y_max_px': float(errors.max())})
        if pair['split'] == 'held_out':
            held_errors.extend(errors.tolist())
    held_errors = np.asarray(held_errors)
    p95, maximum = float(np.percentile(held_errors, 95)), float(held_errors.max())
    passed = bool(rms <= maximum_training_rms_px and p95 <= maximum_heldout_p95_y_px and maximum <= maximum_heldout_y_px)
    real = all(profile.get('provenance') == 'real_chessboard_captures' for profile in (left_profile, right_profile))
    evidence = bool(manifest_audit and manifest_audit['acceptance_requirements_passed'])
    return {'schema': 1, 'hardware_accessed': False, 'hardware_release_allowed': False,
        'passed': passed, 'numerical_gates_passed': passed,
        'stereo_acceptance_ready': bool(passed and real and evidence),
        'synthetic_or_unverified_intrinsics': not real,
        'intrinsic_scope_maximum_ray_angle_deg': {side: _declared_scope_maximum(profile) for side, profile in
                                                (('left', left_profile), ('right', right_profile))},
        'intrinsic_scope_known': all(_declared_scope_maximum(profile) is not None for profile in (left_profile, right_profile)),
        'capture_provenance': manifest_audit.get('capture_provenance', 'unverified_in_memory_point_pairs') if manifest_audit else 'unverified_in_memory_point_pairs',
        'synchronization_contract_satisfied': bool(manifest_audit and manifest_audit['synchronization_contract_satisfied']),
        'physical_synchronization_measured_by_this_tool': False, 'depth_accuracy_verified': False,
        'model': 'opencv_fisheye_fixed_intrinsics', 'translation_unit': 'mm',
        'transform_convention': 'X_right = R_left_to_right @ X_left + T_left_to_right_mm',
        'R_left_to_right': rotation.tolist(), 'T_left_to_right_mm': translation.ravel().tolist(),
        'baseline_mm': baseline, 'training_pair_ids': [p['pair_id'] for p in train],
        'held_out_pair_ids': [p['pair_id'] for p in held], 'training_rms_px': float(rms),
        'held_out_absolute_y_p95_px': p95, 'held_out_absolute_y_max_px': maximum,
        'rectification': {'R_left': r1.tolist(), 'R_right': r2.tolist(), 'P_left': p1.tolist(), 'P_right': p2.tolist(), 'Q': q.tolist()},
        'pairs': rows, 'board': board,
        'criteria': {'maximum_training_rms_px': maximum_training_rms_px,
                     'maximum_heldout_p95_y_px': maximum_heldout_p95_y_px,
                     'maximum_heldout_y_px': maximum_heldout_y_px,
                     'minimum_training_pairs': minimum_training_pairs, 'minimum_heldout_pairs': minimum_heldout_pairs,
                     'note': 'Internal engineering gates, not competition scoring rules or optical acceptance standards.'},
        'intrinsic_profile_sha256': {side: _canonical_sha(profile)
            for side, profile in (('left', left_profile), ('right', right_profile))},
        'source_sha256': {str(path.relative_to(ROOT)): _sha(path) for path in (Path(__file__), ROOT/'tools/wideangle_mapping_audit.py')},
        'limits': 'Purely offline calibration. R/T use only training pairs; held-out vertical residuals assess epipolar consistency, not depth accuracy or full-field optical performance. Point-pair IDs and software timestamps do not establish simultaneous physical exposures. A ready numerical/evidence record still cannot release hardware: dual-camera RTL, sync behavior, timing and real optical validation remain unverified.'}


def detect_manifest_points(audit):
    board = audit['board']
    observations = []
    for pair in audit['pairs']:
        row = {'pair_id': pair['pair_id'], 'split': pair['split']}
        for side in ('left', 'right'):
            path = Path(pair[side]['path'])
            if _sha(path) != pair[side]['sha256']:
                raise ValueError('input image changed after manifest audit')
            image = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
            ok, corners = cv2.findChessboardCornersSB(image, (board['cols'], board['rows']))
            if not ok:
                raise ValueError(pair['pair_id']+'.'+side+' has no complete declared chessboard; no pair silently dropped')
            row[side+'_points'] = corners.astype(np.float64).reshape(1, -1, 2)
            row[side+'_image_sha256'] = pair[side]['sha256']
        observations.append(row)
    return observations


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    parser.add_argument('--left-intrinsics', type=Path, required=True)
    parser.add_argument('--right-intrinsics', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if not args.output.parent.is_dir() or args.output.exists():
        parser.error('choose a new output filename inside an existing directory; no directories or evidence are overwritten')
    load = lambda path: json.loads(path.read_text(encoding='utf-8-sig'))
    manifest, left, right = load(args.manifest), load(args.left_intrinsics), load(args.right_intrinsics)
    audit = audit_manifest(manifest, left, right, base_dir=args.manifest.parent)
    observations = detect_manifest_points(audit)
    result = calibrate_points(observations, left, right, manifest['board'], manifest_audit=audit)
    result['manifest_audit'] = audit
    result['input_file_sha256'] = {str(path.resolve()): _sha(path) for path in (args.manifest, args.left_intrinsics, args.right_intrinsics)}
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8')
    print(json.dumps({key: result[key] for key in ('passed', 'stereo_acceptance_ready', 'baseline_mm', 'held_out_absolute_y_p95_px', 'hardware_release_allowed')}))
    if not result['stereo_acceptance_ready']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
