"""Explicit development estimate from real views; never accepts a calibration.

The strict calibrator is unchanged. A failed free-four-coefficient fit is kept.
The selected constrained model is declared before any held-out evaluation.
"""
from pathlib import Path
import argparse
import hashlib
import json
import math
import sys

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.calibrate import fit, validate
from tools.calibrate_fisheye_profile import validate_manifest, _decode_bound_capture, _domain
from tools.stereo_fisheye_calibrate import board_points

cv2.setNumThreads(1)
cv2.ocl.setUseOpenCL(False)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write('\n')


def constrained_fit(obj, points, size):
    flags = (cv2.fisheye.CALIB_RECOMPUTE_EXTRINSIC | cv2.fisheye.CALIB_FIX_SKEW |
             cv2.fisheye.CALIB_CHECK_COND | cv2.fisheye.CALIB_FIX_K3 | cv2.fisheye.CALIB_FIX_K4)
    return cv2.fisheye.calibrate([obj]*len(points), points, size, np.eye(3), np.zeros((4, 1)), flags=flags)


def line_metrics(points, cols, rows):
    grid = np.asarray(points).reshape(rows, cols, 2)
    distances, normalized = [], []
    for group in ([grid[i] for i in range(rows)], [grid[:, i] for i in range(cols)]):
        for line in group:
            centered = line-line.mean(axis=0)
            _, _, vectors = np.linalg.svd(centered, full_matrices=False)
            delta = centered @ vectors[-1]
            span = np.ptp(centered @ vectors[0])
            distances.extend(delta.tolist())
            normalized.extend((delta/max(span, 1e-12)).tolist())
    return {'point_to_line_rms_px': float(np.sqrt(np.mean(np.square(distances)))),
            'line_span_normalized_rms': float(np.sqrt(np.mean(np.square(normalized))))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    parser.add_argument('--development-only', action='store_true', required=True)
    parser.add_argument('--profile', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--preview-prefix', type=Path, required=True)
    parser.add_argument('--sensitivity-exclude-pose')
    args = parser.parse_args()
    preview = {name: Path(str(args.preview_prefix)+suffix) for name, suffix in
               [('rectified', '-rectified.png'), ('valid_mask', '-valid-mask.png'), ('comparison', '-comparison.png')]}
    outputs = [args.profile, args.report, *preview.values()]
    if len({p.resolve() for p in outputs}) != len(outputs) or any(p.exists() or not p.parent.is_dir() for p in outputs):
        parser.error('all outputs must be fresh files in existing directories')
    manifest = json.loads(args.manifest.read_text(encoding='utf-8-sig'))
    strict_error = None
    try:
        validate_manifest(manifest)
    except ValueError as error:
        strict_error = str(error)
        if strict_error not in ('need at least 12 train and 3 held_out views', 'need at least 12 distinct training poses'):
            raise
    size = tuple(manifest['image_size'])
    if len(manifest['views']) > 30:
        raise ValueError('development analysis supports at most30 source views')
    obj = board_points(manifest['board'])
    data = []
    for view in manifest['views']:
        path = Path(view['path'])
        path = path if path.is_absolute() else args.manifest.parent/path
        path = path.resolve()
        if sha(path) != view['sha256'].lower():
            raise ValueError('source image changed: '+view['view_id'])
        image = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)
        if image is None or (image.shape[1], image.shape[0]) != size:
            raise ValueError('source image size differs')
        capture = _decode_bound_capture(view, manifest, args.manifest.parent, image, path)
        ok, corners = cv2.findChessboardCornersSB(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY),
                                                 (manifest['board']['cols'], manifest['board']['rows']))
        if not ok:
            raise ValueError('complete board missing; do not silently drop '+view['view_id'])
        data.append((view, corners.astype(np.float64).reshape(1, -1, 2), image, capture))
    train = [row for row in data if row[0]['split'] == 'train']
    held = [row for row in data if row[0]['split'] == 'held_out']
    if not train or not held:
        raise ValueError('explicit training and independent held-out views required')
    attempts = []
    for name, subset, constrained in [('free4_all_train', train, False), ('constrained2_all_train', train, True)]:
        try:
            answer = constrained_fit(obj, [row[1] for row in subset], size) if constrained else fit([obj]*len(subset), [row[1] for row in subset], size, 'fisheye')
            rms, k, d, rvecs, tvecs = answer
            attempts.append({'name': name, 'completed': True, 'training_rms_px': float(rms), 'K': k.tolist(), 'D': d.ravel().tolist()})
            if constrained:
                selected = answer
        except (cv2.error, ValueError) as error:
            attempts.append({'name': name, 'completed': False, 'error': str(error)})
    if not attempts[-1]['completed']:
        write_json(args.report, {'development_only': True, 'fit_completed': False, 'attempts': attempts,
                                'hardware_release_allowed': False, 'candidate_ready_for_profile_review': False})
        return 1
    rms, k, d, rvecs, tvecs = selected
    if not np.isfinite(k).all() or not np.isfinite(d).all() or not math.isfinite(rms):
        raise ValueError('nonfinite constrained estimate')
    # The all-train constrained2 model is selected above, BEFORE held-out scores.
    per_view = []
    output_k = np.array([[240., 0., (size[0]-1)/2], [0., 240., (size[1]-1)/2], [0., 0., 1.]])
    for view, corners, image, capture in data:
        error = validate([obj], [corners], k, d, 'fisheye')[0]
        transformed = cv2.fisheye.undistortPoints(corners, k, d, P=output_k)
        per_view.append({'view_id': view['view_id'], 'pose_id': view['pose_id'], 'split': view['split'],
            'fixed_intrinsic_pose_reprojection_rms_px': error,
            'source_line_metrics': line_metrics(corners, manifest['board']['cols'], manifest['board']['rows']),
            'development_rectified_line_metrics': line_metrics(transformed, manifest['board']['cols'], manifest['board']['rows'])})
    sensitivity = []
    for removed in train:
        subset = [row for row in train if row is not removed]
        try:
            value, sk, sd, _, _ = constrained_fit(obj, [row[1] for row in subset], size)
            sensitivity.append({'removed_training_pose': removed[0]['pose_id'], 'completed': True,
                                'training_rms_px': float(value), 'K': sk.tolist(), 'D': sd.ravel().tolist()})
        except (cv2.error, ValueError) as error:
            sensitivity.append({'removed_training_pose': removed[0]['pose_id'], 'completed': False, 'error': str(error)})
    if args.sensitivity_exclude_pose:
        subset = [row for row in train if row[0]['pose_id'] != args.sensitivity_exclude_pose]
        if len(subset) != len(train)-1:
            raise ValueError('sensitivity exclusion must name one actual training pose')
        try:
            value, sk, sd, _, _ = fit([obj]*len(subset), [row[1] for row in subset], size, 'fisheye')
            attempts.append({'name': 'free4_sensitivity_exclusion', 'excluded_training_pose': args.sensitivity_exclude_pose,
                             'completed': True, 'training_rms_px': float(value), 'K': sk.tolist(), 'D': sd.ravel().tolist()})
        except (cv2.error, ValueError) as error:
            attempts.append({'name': 'free4_sensitivity_exclusion', 'excluded_training_pose': args.sensitivity_exclude_pose,
                             'completed': False, 'error': str(error)})
    domain = _domain(k, d.ravel(), size, manifest['model_scope']['maximum_ray_angle_deg'])
    preview_domain = _domain(k, d.ravel(), size, 60.)
    mx, my = cv2.fisheye.initUndistortRectifyMap(k, d, np.eye(3), output_k, size, cv2.CV_32FC1)
    valid = np.isfinite(mx) & np.isfinite(my) & (mx >= 0) & (my >= 0) & (mx < size[0]-1) & (my < size[1]-1)
    source = train[0]
    rectified = cv2.remap(source[2], mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)
    rectified[~valid] = 0
    comparison = np.full((size[1]+32, size[0]*2, 3), 255, dtype=np.uint8)
    comparison[32:, :size[0]] = source[2]
    comparison[32:, size[0]:] = rectified
    cv2.putText(comparison, 'Native source', (8, 23), cv2.FONT_HERSHEY_SIMPLEX, .55, (0, 0, 0), 1, cv2.LINE_AA)
    cv2.putText(comparison, 'DEVELOPMENT ONLY: cropped/scaled output grid', (size[0]+8, 23), cv2.FONT_HERSHEY_SIMPLEX, .50, (0, 0, 0), 1, cv2.LINE_AA)
    for name, pixels in [('rectified', rectified), ('valid_mask', valid.astype(np.uint8)*255), ('comparison', comparison)]:
        ok, encoded = cv2.imencode('.png', pixels)
        if not ok:
            raise ValueError('preview encoding failed')
        with preview[name].open('xb') as stream:
            stream.write(encoded.tobytes())
    held_errors = [row['fixed_intrinsic_pose_reprojection_rms_px'] for row in per_view if row['split'] == 'held_out']
    profile = {key: manifest[key] for key in ('camera_id', 'lens_id', 'profile_id', 'capture_mode_id')}
    profile.update(schema=1, model='fisheye', K=k.tolist(), D=d.ravel().tolist(), image_size=list(size),
        provenance='real_chessboard_captures' if all(row[3]['physical_capture_record'] for row in data) else 'offline_or_unverified_capture_origin',
        development_only=True, calibration_status='constrained_development_estimate_not_accepted',
        fit_constraints='k3=k4 fixed0; only k1/k2 free. Full four-free-coefficient conditioning failure is preserved.',
        selected_model_basis='Constrained2 declared from training data only before held-out evaluation; held-out images did not fit K/D.',
        numeric_fit_completed=True, passed=False, candidate_ready_for_profile_review=False,
        independent_spatial_coverage_passed=False, minimum_training_pose_count_passed=len(train) >= 12,
        hardware_release_allowed=False, hardware_accessed_by_calibrator=False,
        model_scope=manifest['model_scope'], domain_audit=domain,
        training_rms_px=float(rms), held_out_mean_rms_px=float(np.mean(held_errors)), held_out_max_rms_px=float(max(held_errors)),
        training_pose_count=len(train), held_out_pose_count=len(held),
        object_coordinate_unit=manifest['board'].get('coordinate_unit', 'square'), metric_scale_verified=False,
        training_image_sha256=[row[0]['sha256'] for row in train], calibration_image_sha256=[row[0]['sha256'] for row in train],
        held_out_image_sha256=[row[0]['sha256'] for row in held],
        source_dataset_manifest_file=str(args.manifest.resolve()), source_dataset_manifest_file_sha256=sha(args.manifest),
        source_sha256={str(path.relative_to(ROOT)): sha(path) for path in [Path(__file__), ROOT/'tools/calibrate.py', ROOT/'tools/calibrate_fisheye_profile.py']},
        limits='Actual constrained development estimate only. Incomplete11-train/source coverage and failed80-degree domain are not waived. '
               'No calibrated full-field lens, four-free-coefficient stability, metric translation, stereo, hardware or optical acceptance.')
    write_json(args.profile, profile)
    report = {'development_only': True, 'profile': str(args.profile.resolve()), 'profile_sha256': sha(args.profile),
        'strict_manifest_validation_error': strict_error, 'strict_calibrator_modified': False,
        'attempts': attempts, 'per_view_validation': per_view, 'leave_one_training_pose_out': sensitivity,
        'requested_80deg_domain': domain, 'preview_60deg_domain': preview_domain,
        'preview': {'source_view_id': source[0]['view_id'], 'source_path': source[0]['path'], 'source_sha256': source[0]['sha256'],
            'output_K': output_k.tolist(), 'maximum_output_corner_ray_angle_deg': math.degrees(math.atan(math.hypot((size[0]-1)/2, (size[1]-1)/2)/240)),
            'valid_pixels': int(valid.sum()), 'total_pixels': int(valid.size),
            'files': {name: {'path': str(path.resolve()), 'sha256': sha(path)} for name, path in preview.items()},
            'scope': 'Software bilinear preview with engineering fx=fy240 output grid, crop/scale and masks. It is not measured lens FOV or FPGA output.'},
        'limits': profile['limits']}
    write_json(args.report, report)
    print(json.dumps({'development_only': True, 'profile': str(args.profile), 'training_rms_px': float(rms),
        'held_out_mean_rms_px': profile['held_out_mean_rms_px'], 'held_out_max_rms_px': profile['held_out_max_rms_px'],
        'requested80_domain_passed': domain['supported_forward_domain_passed'],
        'leave_one_out_completed': sum(row['completed'] for row in sensitivity),
        'preview_valid_pixels': int(valid.sum()), 'candidate_ready_for_profile_review': False}, allow_nan=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
