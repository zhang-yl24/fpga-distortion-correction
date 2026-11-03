"""Evaluate an axis-aligned sensor-mode transfer without accepting calibration.

Only paired, untouched PGFRAME1 images can supply measured correspondences.
An explicit matrix hypothesis requires no images and is always unvalidated.
The output is a diagnostic envelope, never a drop-in accepted lens profile.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools import calibrate_fisheye_profile as calibration
from tools import fisheye_forward_inverse as inverse
from tools.stereo_fisheye_calibrate import board_points

SCHEMA = 'camera720-axis-mode-transfer-diagnostic-v1'
MANIFEST_SCHEMA = 'camera720-paired-mode-geometry-v1'
ORDERS = ('identity', 'reverse_rows', 'reverse_cols', 'reverse_both')
REPEATED_GEOMETRY_TOLERANCE_PX = 1e-6
cv2.setNumThreads(1)
cv2.ocl.setUseOpenCL(False)


def require(ok, message):
    if not ok:
        raise ValueError(message)


def binding(path):
    path = Path(path).resolve()
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def size(value):
    require(isinstance(value, (list, tuple)) and len(value) == 2 and
            all(type(n) is int and n > 1 for n in value) and value[0]*value[1] <= 2500000,
            'bounded integer image width/height required')
    return tuple(value)


def positive(value, label):
    require(type(value) in (int, float) and np.isfinite(value) and value > 0,
            label+' must be a finite positive number')
    return float(value)


def axis_matrix(value):
    a = np.asarray(value, dtype=np.float64)
    require(a.shape == (3, 3) and np.isfinite(a).all() and
            np.array_equal(a[[0, 1, 2, 2, 2], [1, 0, 0, 1, 2]], [0, 0, 0, 0, 1]) and
            min(a[0, 0], a[1, 1]) > 0, 'positive axis scales and translation only; no rotation, shear or reflection')
    return a


def source_profile(profile):
    require(profile.get('model') == 'fisheye' and size(profile['image_size']) == (640, 480),
            'source must be the explicit 640x480 fisheye mode')
    require(all(isinstance(profile.get(k), str) and profile[k].strip() for k in calibration.IDENTITY),
            'source camera/lens/profile/mode identity required')
    k = axis_matrix(profile['K'])
    d = np.asarray(profile['D'], dtype=np.float64)
    require(d.shape == (4,) and np.isfinite(d).all(), 'four finite fisheye coefficients required')
    scope = profile['model_scope']
    require(scope.get('projection') == 'forward_rectilinear' and scope.get('inverse_method') == inverse.METHOD,
            'source must retain the bounded forward inverse method')
    inverse.domain(d, scope['maximum_ray_angle_deg'])
    return k, d


def q8_intrinsics_audit(k, image_size):
    """Only source-intrinsic representation; not Brown/FPGA remap verification."""
    k = axis_matrix(k)
    width, height = size(image_size)
    values = np.array([k[0, 0], k[1, 1], k[0, 2], k[1, 2]])
    try:
        with np.errstate(over='raise', invalid='raise', divide='raise'):
            encoded = np.rint(values*256)
            require(np.isfinite(encoded).all(), 'intrinsic fixed-point conversion overflow')
            representable = bool(np.all((encoded >= -(1 << 23)) & (encoded < (1 << 23))))
            decoded = encoded/256
            require(min(decoded[:2]) > 0, 'source focal length rounds to zero in signed24 Q8')
            # Isolate K quantization only, with no distortion fit. Reject
            # intermediate overflow even when the input K itself is finite.
            dx = (np.arange(width)-values[2])/values[0]*(decoded[0]-values[0]) + decoded[2]-values[2]
            dy = (np.arange(height)-values[3])/values[1]*(decoded[1]-values[1]) + decoded[3]-values[3]
            error_squared = dy[:, None]**2 + dx[None, :]**2
            maximum_error = float(np.sqrt(error_squared.max()))
            rms_error = float(np.sqrt(error_squared.mean()))
    except FloatingPointError as error:
        raise ValueError('intrinsic fixed-point arithmetic overflow') from error
    require(np.isfinite([maximum_error, rms_error]).all(), 'nonfinite intrinsic quantization metrics')
    return {'format': 'signed24_fraction8', 'rounding': 'nearest_ties_to_even',
        'encoded_fx_fy_cx_cy': [int(v) for v in encoded],
        'decoded_fx_fy_cx_cy': decoded.tolist(), 'representable': representable,
        'source_grid_pixels_checked': width*height,
        'maximum_source_pixel_error_px': maximum_error,
        'rms_source_pixel_error_px': rms_error,
        'fpga_mapping_verified': False, 'brown_surrogate_verified': False,
        'limits': 'Only error caused by representing source K in signed24 Q8; no output K, distortion coefficients, inverse, address or FPGA arithmetic audit.'}


def candidate(profile, a, target_identity):
    k, d = source_profile(profile)
    a = axis_matrix(a)
    require(isinstance(target_identity, dict) and set(target_identity) == set(calibration.IDENTITY),
            'explicit target camera/lens/profile/mode identities required')
    require(all(isinstance(v, str) and v.strip() for v in target_identity.values()), 'nonempty target identities required')
    require(all(target_identity[x] == profile[x] for x in ('camera_id', 'lens_id')) and
            all(target_identity[x] != profile[x] for x in ('capture_mode_id', 'profile_id')),
            'same camera/lens and distinct target mode/profile required')
    try:
        with np.errstate(over='raise', invalid='raise'):
            kt = axis_matrix(a @ k)
    except FloatingPointError as error:
        raise ValueError('candidate intrinsic matrix overflow') from error
    return {'schema': SCHEMA, 'source_identity': {x: profile[x] for x in calibration.IDENTITY},
        'target_identity': copy.deepcopy(target_identity), 'source_image_size': [640, 480],
        'target_image_size': [1280, 720], 'A_source_to_target': a.tolist(),
        'candidate_parameters': {'model': 'fisheye', 'K': kt.tolist(), 'D': d.tolist(),
            'projection': 'forward_rectilinear', 'maximum_ray_angle_deg': profile['model_scope']['maximum_ray_angle_deg'],
            'inverse_method': inverse.METHOD},
        'intrinsics_quantization': q8_intrinsics_audit(kt, [1280, 720]),
        'source_visibility_scope_inherited': False, 'source_heldout_acceptance_inherited': False,
        'optical_calibration_accepted': False, 'hardware_release_allowed': False,
        'hardware_accessed': False, 'drop_in_calibration_profile': False,
        'image_pixel_orientation_verified': False,
        'orientation_limits': 'Unlabeled checkerboard index symmetries can conceal an actual pixel reflection. Positive fitted A and small residuals do not verify image direction; an independent asymmetric target/text and sensor-mode orientation review are required.',
        'limits': 'A*K and unchanged D are conditional on a fixed image-coordinate crop/scale model. Paired residuals are a diagnostic; independent target-mode pose validation, visible-region coverage and complete fixed-point mapping verification remain required.'}


def fit_axis(source, target):
    source, target = np.asarray(source, dtype=np.float64), np.asarray(target, dtype=np.float64)
    require(source.shape == target.shape and source.ndim == 2 and source.shape[1] == 2 and
            len(source) >= 4 and np.isfinite(source).all() and np.isfinite(target).all(),
            'matching finite point arrays with at least four points required')
    a = np.eye(3)
    for col in (0, 1):
        centered = source[:, col]-source[:, col].mean()
        require(np.ptp(centered) >= 1 and np.dot(centered, centered) > 1e-9,
                'source correspondences do not span both axes')
        a[col, col] = np.dot(centered, target[:, col]-target[:, col].mean())/np.dot(centered, centered)
        a[col, 2] = target[:, col].mean()-a[col, col]*source[:, col].mean()
    return axis_matrix(a)


def residuals(source, target, a):
    delta = np.asarray(source) @ a[:2, :2].T + a[:2, 2]-np.asarray(target)
    lengths = np.linalg.norm(delta, axis=1)
    return {'rms_px': float(np.sqrt(np.mean(lengths**2))), 'maximum_px': float(lengths.max()),
            'mean_delta_xy_px': delta.mean(axis=0).tolist(), 'points': len(lengths)}


def order_points(points, board, order):
    require(order in ORDERS, 'unknown checkerboard index symmetry')
    grid = np.asarray(points).reshape(board['rows'], board['cols'], 2)
    if order in ('reverse_rows', 'reverse_both'):
        grid = grid[::-1]
    if order in ('reverse_cols', 'reverse_both'):
        grid = grid[:, ::-1]
    return grid.reshape(-1, 2)


def select_order(source, target, board, *, requested='auto', fixed_a=None):
    """Fit-view ordering may fit A; held-out ordering uses only frozen A."""
    require(requested in ORDERS+('auto',), 'explicit checkerboard order or auto required')
    scores = []
    for order in ORDERS:
        aligned = order_points(target, board, order)
        try:
            a = fit_axis(source, aligned) if fixed_a is None else axis_matrix(fixed_a)
            score = residuals(source, aligned, a)['rms_px']
            scores.append((score, order, aligned))
        except ValueError:
            pass
    require(scores, 'no positive crop/scale correspondence orientation is possible')
    scores.sort(key=lambda x: x[:2])
    if requested == 'auto':
        require(len(scores) == 1 or scores[1][0]-scores[0][0] > 1e-6,
                'checkerboard order is ambiguous; specify physical corner correspondence')
        selected = scores[0]
    else:
        matches = [x for x in scores if x[1] == requested]
        require(matches, 'specified corner order implies unsupported orientation')
        selected = matches[0]
    return selected[2], {'selected': selected[1], 'selection': requested,
        'rms_by_valid_symmetry_px': {order: score for score, order, _ in scores},
        'held_out_matrix_refitted_for_order': False}


def reject_repeated_split_geometry(pairs, lookup, board):
    """Reject matching fit/held-out image geometry despite different labels.

    This detects only coincident corners, not independent physical poses.
    Symmetry matching accounts for changed SB corner enumeration.
    """
    for fit in (p for p in pairs if p['split'] == 'fit'):
        for held in (p for p in pairs if p['split'] == 'held_out'):
            for side in ('source', 'target'):
                first = np.asarray(lookup[fit['pair_id']][side])
                second = lookup[held['pair_id']][side]
                distance = min(float(np.linalg.norm(first-order_points(second, board, order), axis=1).max())
                               for order in ORDERS)
                require(distance > REPEATED_GEOMETRY_TOLERANCE_PX,
                        'repeated fit/held-out corner geometry in '+side+': '+fit['pair_id']+' / '+held['pair_id'])


def validate_manifest(profile, manifest):
    require(manifest.get('schema') == MANIFEST_SCHEMA, 'wrong paired-mode manifest schema')
    require(manifest.get('camera_focus_and_mount_unchanged_declared') is True,
            'operator declaration of unchanged camera, lens focus and mount required')
    board_points(manifest['board'])
    require(max(manifest['board']['cols'], manifest['board']['rows']) <= 32, 'checkerboard dimensions exceed detector budget')
    rms_limit = positive(manifest['thresholds']['rms_px'], 'rms_px')
    max_limit = positive(manifest['thresholds']['maximum_px'], 'maximum_px')
    require(max_limit >= rms_limit, 'maximum residual limit must be at least RMS limit')
    pairs = manifest['pairs']
    require(isinstance(pairs, list) and pairs, 'explicit paired poses required')
    names, poses, splits = set(), set(), set()
    for pair in pairs:
        require(isinstance(pair.get('pair_id'), str) and pair['pair_id'] and pair['pair_id'] not in names,
                'unique pair_id required')
        require(isinstance(pair.get('pose_id'), str) and pair['pose_id'] and pair['pose_id'] not in poses,
                'unique physical pose IDs; no fit/held-out pose reuse')
        require(pair.get('same_stationary_pose_declared') is True, 'each cross-mode pair needs a stationary-pose declaration')
        require(pair.get('split') in ('fit', 'held_out'), 'pair split must be fit or held_out')
        names.add(pair['pair_id']); poses.add(pair['pose_id']); splits.add(pair['split'])
    mode = manifest['method']
    require(mode in ('fit_axis_aligned', 'supplied_axis_aligned'), 'explicit fit or supplied transform method required')
    require('held_out' in splits, 'at least one independent held-out pair needed for diagnostic evaluation')
    candidate(profile, np.eye(3), manifest['target_identity'])
    return pairs, names, splits, mode, rms_limit, max_limit


def evaluate_observations(profile, manifest, observations):
    pairs, names, splits, mode, rms_limit, max_limit = validate_manifest(profile, manifest)
    lookup = {o['pair_id']: o for o in observations}
    require(len(lookup) == len(observations) and set(lookup) == names, 'exact measured pair identities required')
    count = manifest['board']['rows']*manifest['board']['cols']
    for observation in observations:
        for side, shape in (('source', (640, 480)), ('target', (1280, 720))):
            points = np.asarray(observation[side])
            require(points.shape == (count, 2) and np.isfinite(points).all() and
                    np.all(points >= 0) and np.all(points < shape), 'complete finite native corner arrays required')
    reject_repeated_split_geometry(pairs, lookup, manifest['board'])
    aligned, choices = {}, {}
    if mode == 'fit_axis_aligned':
        require('fit' in splits, 'fit method needs a fit pair')
        for pair in pairs:
            if pair['split'] != 'fit':
                continue
            o = lookup[pair['pair_id']]
            aligned[pair['pair_id']], choices[pair['pair_id']] = select_order(o['source'], o['target'], manifest['board'], requested=pair.get('corner_order', 'auto'))
        a = fit_axis(np.concatenate([lookup[k]['source'] for k in aligned]), np.concatenate(list(aligned.values())))
    else:
        require(splits == {'held_out'}, 'supplied transform must evaluate held-out pairs only')
        a = axis_matrix(manifest['A_source_to_target'])
    result = candidate(profile, a, manifest['target_identity'])
    rows, counts = [], {split: np.zeros((3, 3), dtype=int) for split in ('fit', 'held_out')}
    for pair in pairs:
        key, o = pair['pair_id'], lookup[pair['pair_id']]
        if key not in aligned:
            aligned[key], choices[key] = select_order(o['source'], o['target'], manifest['board'], requested=pair.get('corner_order', 'auto'), fixed_a=a)
        metrics = residuals(o['source'], aligned[key], a)
        for x, y in aligned[key]:
            require(0 <= x < 1280 and 0 <= y < 720, 'target corner outside native720 image')
            counts[pair['split']][min(2, int(y*3/720)), min(2, int(x*3/1280))] += 1
        rows.append({'pair_id': key, 'pose_id': pair['pose_id'], 'split': pair['split'],
            'corner_order': choices[key], **metrics,
            'within_declared_thresholds': metrics['rms_px'] <= rms_limit and metrics['maximum_px'] <= max_limit})
    result.update(method=mode, thresholds=copy.deepcopy(manifest['thresholds']), pairs=rows,
        target_corner_coverage_3x3={k: v.tolist() for k, v in counts.items()},
        numeric_pair_checks_passed=all(x['within_declared_thresholds'] for x in rows),
        independent_target_lens_validation_completed=False,
        repeated_fit_heldout_corner_geometry_detected=False,
        repeated_geometry_tolerance_px=REPEATED_GEOMETRY_TOLERANCE_PX,
        geometry_independence_limits='Only coincident fit/held-out corner sets in either mode are rejected, under permitted index symmetries. Distinct coordinates, bytes or pose IDs do not independently establish distinct physical poses.',
        physical_pose_identity_verified=False, operator_declarations_verified_independently=False)
    return result


def load_observations(profile, manifest, base):
    """Decode PNG/raw/metadata exactly as the existing calibration pipeline."""
    validate_manifest(profile, manifest)
    identities = {'source': {k: profile[k] for k in calibration.IDENTITY}, 'target': manifest['target_identity']}
    sizes = {'source': [640, 480], 'target': [1280, 720]}
    hashes, raw_hashes, observed, evidence = set(), set(), [], []
    for pair in manifest['pairs']:
        row = {'pair_id': pair['pair_id']}
        for side in ('source', 'target'):
            view = pair[side]
            path = calibration._file(base, view['path'], side+' image')
            digest = calibration._digest(path)
            require(calibration._valid_digest(view.get('sha256')) and digest == view['sha256'].lower() and digest not in hashes,
                    'image hash mismatch or duplicate physical image content')
            hashes.add(digest)
            image = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)
            require(image is not None and [image.shape[1], image.shape[0]] == sizes[side], 'native mode image dimensions differ')
            capture = calibration._decode_bound_capture(view, {**identities[side], 'image_size': sizes[side]}, base, image, path)
            require(capture['raw_sha256'] not in raw_hashes, 'duplicate raw frame content, including re-encoded PNG')
            raw_hashes.add(capture['raw_sha256'])
            found, corners = cv2.findChessboardCornersSB(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY), (manifest['board']['cols'], manifest['board']['rows']))
            require(found and corners is not None, 'complete declared chessboard missing; no pairs silently dropped')
            row[side] = corners.reshape(-1, 2).astype(np.float64)
            evidence.append({'pair_id': pair['pair_id'], 'side': side, 'image': binding(path), **capture})
        observed.append(row)
    return observed, evidence


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source_profile', type=Path)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--pairs', type=Path, help='manifest containing real paired untouched captures')
    mode.add_argument('--hypothesis', type=float, nargs=4, metavar=('SX', 'SY', 'TX', 'TY'))
    parser.add_argument('--target-mode')
    parser.add_argument('--target-profile')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    require(args.output.parent.is_dir() and not args.output.exists(), 'fresh output file in existing directory required')
    profile_binding = binding(args.source_profile)
    profile = json.loads(args.source_profile.read_text(encoding='utf-8-sig'))
    source_profile(profile)
    if args.pairs:
        pair_binding = binding(args.pairs)
        manifest = json.loads(args.pairs.read_text(encoding='utf-8-sig'))
        observations, evidence = load_observations(profile, manifest, args.pairs.parent)
        report = evaluate_observations(profile, manifest, observations)
        report.update(pair_manifest=pair_binding, capture_evidence=evidence,
            all_captures_recorded_physical=all(x['physical_capture_record'] for x in evidence))
        require(binding(args.pairs) == pair_binding, 'pair manifest changed during evaluation')
        for capture in evidence:
            require(binding(capture['image']['path']) == capture['image'] and
                    calibration._digest(capture['metadata_path']) == capture['metadata_sha256'] and
                    calibration._digest(capture['raw_path']) == capture['raw_sha256'],
                    'paired capture input changed during evaluation')
    else:
        require(args.target_mode and args.target_profile, 'hypothesis requires explicit new mode and profile IDs')
        sx, sy, tx, ty = args.hypothesis
        target = {k: profile[k] for k in calibration.IDENTITY}
        target.update(capture_mode_id=args.target_mode, profile_id=args.target_profile)
        report = candidate(profile, [[sx, 0, tx], [0, sy, ty], [0, 0, 1]], target)
        report.update(method='unmeasured_user_matrix_hypothesis', numeric_pair_checks_passed=False,
            measured_target_images=0, all_captures_recorded_physical=False,
            independent_target_lens_validation_completed=False)
    require(binding(args.source_profile) == profile_binding, 'source profile changed during evaluation')
    report.update(source_profile=profile_binding, tool=binding(__file__))
    # Validate the entire JSON before creating a file: nonfinite or otherwise
    # unserializable output must not leave a truncated diagnostic report.
    serialized = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False)+'\n'
    with args.output.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(serialized)
    print(json.dumps({'report': binding(args.output), 'method': report['method'],
        'numeric_pair_checks_passed': report['numeric_pair_checks_passed'],
        'optical_calibration_accepted': False}))
    return 0 if args.hypothesis or report['numeric_pair_checks_passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
