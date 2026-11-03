"""Audit a new four-coefficient fisheye profile without changing board parameters.

This fits the existing three-term radial Brown arithmetic to requested output
rays. OpenCV supplies the independent four-coefficient fisheye reference. A
passing audit establishes a numerical model approximation only, never optical
accuracy, stereo synchronization, routed timing, or permission to program a board.
"""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import math
import sys

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from model.rotation import cordic, phase_from_degrees, inverse_rotate

_spec = importlib.util.spec_from_file_location('wideangle_brown_oracle', ROOT/'tools/generate-brown-vectors.py')
_brown = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_brown)
Q = 1 << 22


def _size(value, name):
    if len(value) != 2 or any(isinstance(v, bool) or int(v) != v or not 2 <= v <= 32767 for v in value):
        raise ValueError(name + ' must contain two integer dimensions in [2,32767]')
    return tuple(map(int, value))


def _intrinsics(value, name):
    k = np.asarray(value, dtype=np.float64)
    if k.shape != (3, 3) or not np.isfinite(k).all() or k[0, 0] <= 0 or k[1, 1] <= 0:
        raise ValueError(name + ' must be finite 3x3 intrinsics with positive focal lengths')
    if not np.allclose(k[[0, 1, 2, 2, 2], [1, 0, 0, 1, 2]], [0, 0, 0, 0, 1], rtol=0, atol=1e-12):
        raise ValueError(name + ' requires zero skew and conventional last row')
    return k


def _sample_axis(length, stride):
    return np.unique(np.r_[np.arange(0, length, stride), length-1]).astype(np.int64)


def _rays(xx, yy, angle, output_k, size):
    a = math.radians(angle % 360)
    cx, cy = (size[0]-1)/2, (size[1]-1)/2
    u = math.cos(a)*(xx-cx) + math.sin(a)*(yy-cy) + cx
    v = -math.sin(a)*(xx-cx) + math.cos(a)*(yy-cy) + cy
    return (u-output_k[0, 2])/output_k[0, 0], (v-output_k[1, 2])/output_k[1, 1]


def _radial(r2, d):
    r = np.sqrt(r2)
    theta = np.arctan(r)
    t2 = theta*theta
    distorted = theta*(1+t2*(d[0]+t2*(d[1]+t2*(d[2]+t2*d[3]))))
    return np.divide(distorted, r, out=np.ones_like(r), where=r != 0)


def _declared_scope_maximum(profile):
    scope = profile.get('model_scope')
    if scope is None:
        return None
    angle = scope.get('maximum_ray_angle_deg') if isinstance(scope, dict) else None
    if not isinstance(scope, dict) or scope.get('projection') != 'forward_rectilinear' or isinstance(angle, bool) or not isinstance(angle, (int, float)) or not math.isfinite(angle) or not 0 < angle < 90:
        raise ValueError('profile model_scope requires a supported forward_rectilinear ray angle below 90 degrees')
    return float(angle)


def _fixed_project(u, v, c):
    """Vectorized radial-only form of generate-brown-vectors.project.

    Every intermediate is saturated at the same point as the scalar oracle;
    scalar spot checks in audit_profile protect this vectorization contract.
    """
    def rs(x, n):
        return (x + (1 << (n-1))) >> n
    bad = np.zeros(np.broadcast_shapes(u.shape, v.shape), dtype=bool)
    def s32(x):
        nonlocal bad
        bad |= (x < -(1 << 31)) | (x >= (1 << 31))
        return np.clip(x, -(1 << 31), (1 << 31)-1)
    nx = rs((u-c[0])*c[6], 16)
    ny = rs((v-c[1])*c[7], 16)
    bad |= (np.abs(nx) > 2*Q) | (np.abs(ny) > 2*Q)
    nx, ny = s32(nx), s32(ny)
    xx, yy, xy = rs(nx*nx, 22), rs(ny*ny, 22), rs(nx*ny, 22)
    r2 = xx+yy
    xx, yy, xy, r2 = s32(xx), s32(yy), s32(xy), s32(r2)
    # Tangential coefficients are zero; the RTL still checks these factors.
    s32(r2+2*xx)
    s32(r2+2*yy)
    h5 = s32(c[9]+rs(c[10]*r2, 22))
    h7 = s32(c[8]+rs(h5*r2, 22))
    radial = s32(Q+rs(h7*r2, 22))
    xd, yd = s32(rs(nx*radial, 22)), s32(rs(ny*radial, 22))
    sx, sy = rs(xd*c[4], 22)+c[2], rs(yd*c[5], 22)+c[3]
    bad |= (sx < -(1 << 23)) | (sx >= (1 << 23)) | (sy < -(1 << 23)) | (sy >= (1 << 23))
    return np.where(bad, -(1 << 23), sx), np.where(bad, -(1 << 23), sy), bad, r2


def _folds(mx, my, xaxis, yaxis, invalid=None):
    dxdy, dxdx = np.gradient(mx, yaxis, xaxis)
    dydy, dydx = np.gradient(my, yaxis, xaxis)
    det = dxdx*dydy-dxdy*dydx
    usable = np.isfinite(det)
    if invalid is not None:
        # A finite-difference stencil touching an invalid point is not evidence
        # of a fold. Arithmetic invalidity has its own mandatory rejection gate.
        usable &= ~invalid
        usable[1:] &= ~invalid[:-1]
        usable[:-1] &= ~invalid[1:]
        usable[:, 1:] &= ~invalid[:, :-1]
        usable[:, :-1] &= ~invalid[:, 1:]
    return int(np.count_nonzero(usable & (det <= 0))), float(det[usable].min()) if usable.any() else None


def audit_profile(profile, *, output_size=None, output_k=None, angles=(0,), stride=1,
                  maximum_error_px=.25, minimum_in_bounds_fraction=.5,
                  maximum_points_per_frame=2500000):
    """Return a JSON-compatible numerical audit; do not write files or use hardware."""
    if profile.get('model') != 'fisheye':
        raise ValueError('model must be fisheye; no implicit Brown conversion')
    source_size = _size(profile['image_size'], 'image_size')
    size = _size(output_size or profile.get('output_size', source_size), 'output_size')
    k = _intrinsics(profile['K'], 'K')
    new_k = _intrinsics(output_k if output_k is not None else profile.get('output_K', k), 'output_K')
    d = np.asarray(profile['D'], dtype=np.float64).reshape(-1)
    if d.shape != (4,) or not np.isfinite(d).all():
        raise ValueError('D must contain all four finite fisheye coefficients')
    scope_maximum = _declared_scope_maximum(profile)
    if isinstance(stride, bool) or int(stride) != stride or stride < 1:
        raise ValueError('stride must be a positive integer')
    stride = int(stride)
    if isinstance(maximum_points_per_frame, bool) or not isinstance(maximum_points_per_frame, int) or maximum_points_per_frame <= 0:
        raise ValueError('maximum_points_per_frame must be a positive integer')
    angles = [float(a) for a in angles]
    if not angles or not all(math.isfinite(a) for a in angles):
        raise ValueError('angles must be a nonempty finite list')
    if not math.isfinite(maximum_error_px) or maximum_error_px <= 0:
        raise ValueError('maximum_error_px must be finite and positive')
    if not math.isfinite(minimum_in_bounds_fraction) or not 0 <= minimum_in_bounds_fraction <= 1:
        raise ValueError('minimum_in_bounds_fraction must be in [0,1]')
    xaxis, yaxis = _sample_axis(size[0], stride), _sample_axis(size[1], stride)
    sampled_points = len(xaxis)*len(yaxis)
    if sampled_points > maximum_points_per_frame:
        raise ValueError(f'requested {sampled_points} points per frame exceeds maximum_points_per_frame={maximum_points_per_frame}; reduce size or explicitly choose diagnostic sampling/budget')
    xx, yy = np.meshgrid(xaxis, yaxis)
    # Accumulate normal equations in a normalized radial basis. This bounds
    # memory independently of the number of requested rotation angles.
    radius_max = max(float(np.max(np.hypot(*_rays(xx, yy, a, new_k, size)))) for a in angles)
    requested_maximum_angle = math.degrees(math.atan(radius_max))
    if scope_maximum is not None and requested_maximum_angle > scope_maximum+1e-7:
        raise ValueError('requested rays exceed the profile model_scope; a narrow calibration must not approve a wider output')
    scale = max(radius_max*radius_max, 1e-12)
    normal, rhs = np.zeros((3, 3)), np.zeros(3)
    for angle in angles:
        nx, ny = _rays(xx, yy, angle, new_k, size)
        r2 = nx*nx+ny*ny
        weight = np.hypot(k[0, 0]*nx, k[1, 1]*ny)
        z = r2/scale
        basis = np.stack((z, z*z, z*z*z), axis=-1)*weight[..., None]
        target = (_radial(r2, d)-1)*weight
        flat = basis.reshape(-1, 3)
        normal += flat.T@flat
        rhs += flat.T@target.ravel()
    beta = np.linalg.lstsq(normal, rhs, rcond=None)[0]
    coefficients = beta/np.array([scale, scale**2, scale**3])
    c = [_brown.quant(v, 256) for v in (new_k[0, 2], new_k[1, 2], k[0, 2], k[1, 2], k[0, 0], k[1, 1])]
    c += [_brown.quant(1/new_k[0, 0], 1 << 30), _brown.quant(1/new_k[1, 1], 1 << 30)]
    c += [_brown.quant(v, Q) for v in (*coefficients, 0, 0)]
    if any(not -(1 << (bits-1)) <= value < (1 << (bits-1)) for value, bits in zip(c, [24]*6+[32]*7)):
        raise ValueError('candidate configuration is outside existing fixed-point register widths')
    cx, cy = (size[0]-1)*128, (size[1]-1)*128
    rows = []
    for angle in angles:
        nx, ny = _rays(xx, yy, angle, new_k, size)
        rays = np.stack((nx, ny, np.ones_like(nx)), axis=-1).reshape(-1, 1, 3)
        expected, _ = cv2.fisheye.projectPoints(rays, np.zeros(3), np.zeros(3), k, d)
        ex, ey = expected[:, 0, 0].reshape(xx.shape), expected[:, 0, 1].reshape(xx.shape)
        cosine, sine = cordic(phase_from_degrees(angle % 360))
        u = ((cosine*(xx*256-cx)+sine*(yy*256-cy)+(1 << 29)) >> 30)+cx
        v = ((-sine*(xx*256-cx)+cosine*(yy*256-cy)+(1 << 29)) >> 30)+cy
        rotation_bad = (u < -(1 << 23)) | (u >= (1 << 23)) | (v < -(1 << 23)) | (v >= (1 << 23))
        u, v = np.where(rotation_bad, -(1 << 23), u), np.where(rotation_bad, -(1 << 23), v)
        sx, sy, invalid, r2 = _fixed_project(u, v, c)
        invalid |= rotation_bad
        # Check independent scalar integer and rotation oracles at deterministic
        # boundary and interior locations on every requested angle.
        spots = np.unique(np.linspace(0, xx.size-1, min(33, xx.size)).astype(int))
        for index in spots:
            row, col = np.unravel_index(index, xx.shape)
            pu, pv, rb = inverse_rotate(int(xx[row, col])*256, int(yy[row, col])*256, cx, cy, cosine, sine)
            px, py, pb = _brown.project(pu, pv, c)
            if (px, py, bool(pb or rb)) != (int(sx[row, col]), int(sy[row, col]), bool(invalid[row, col])):
                raise AssertionError('vectorized mapper differs from existing scalar oracle')
        finite = bool(np.isfinite(ex).all() and np.isfinite(ey).all())
        valid = ~invalid & np.isfinite(ex) & np.isfinite(ey)
        error = np.hypot(sx[valid]/256-ex[valid], sy[valid]/256-ey[valid])
        inbounds = valid & (sx >= 0) & (sy >= 0) & (sx < (source_size[0]-1)*256) & (sy < (source_size[1]-1)*256)
        reference_inbounds = (ex >= 0) & (ey >= 0) & (ex < source_size[0]-1) & (ey < source_size[1]-1)
        ref_folds, ref_det = _folds(ex, ey, xaxis, yaxis)
        fixed_folds, fixed_det = _folds(sx/256, sy/256, xaxis, yaxis, invalid)
        maximum = float(error.max()) if error.size else None
        passed = bool(finite and not invalid.any() and ref_folds == fixed_folds == 0 and
                      maximum is not None and maximum <= maximum_error_px and
                      inbounds.mean() >= minimum_in_bounds_fraction and
                      reference_inbounds.mean() >= minimum_in_bounds_fraction)
        rows.append({'angle_deg': angle, 'coordinates_checked': int(xx.size),
            'finite_opencv_reference': finite, 'fixed_point_invalid_coordinates': int(invalid.sum()),
            'reference_folded_samples': ref_folds, 'fixed_point_folded_samples': fixed_folds,
            'reference_jacobian_min': ref_det, 'fixed_point_jacobian_min': fixed_det,
            'maximum_coordinate_error_px': maximum,
            'rms_coordinate_error_px': float(np.sqrt(np.mean(error**2))) if error.size else None,
            'p95_coordinate_error_px': float(np.percentile(error, 95)) if error.size else None,
            'bilinear_all_neighbours_in_bounds_fraction': float(inbounds.mean()),
            'opencv_all_neighbours_in_bounds_fraction': float(reference_inbounds.mean()),
            'maximum_normalized_radius_squared_q22': int(r2.max()),
            'scalar_oracle_spotchecks': int(len(spots)), 'numerical_gates_passed': passed})
    identity = all(isinstance(profile.get(key), str) and profile[key].strip() for key in ('camera_id', 'profile_id'))
    synthetic = profile.get('provenance') == 'synthetic'
    real = profile.get('provenance') == 'real_chessboard_captures'
    source_flags = {key: profile.get(key) for key in
                    ('passed', 'candidate_ready_for_profile_review',
                     'independent_spatial_coverage_passed', 'development_only')}
    source_ready = (real and source_flags['passed'] is True and
                    source_flags['candidate_ready_for_profile_review'] is True and
                    source_flags['independent_spatial_coverage_passed'] is True and
                    source_flags['development_only'] is not True)
    full = stride == 1
    passed = full and all(row['numerical_gates_passed'] for row in rows)
    return {'schema': 1, 'hardware_accessed': False, 'optical_acceptance_complete': False,
        'passed': passed, 'profile_identity_bound': bool(identity), 'synthetic_input': synthetic,
        'camera_id': profile.get('camera_id'), 'profile_id': profile.get('profile_id'),
        'provenance': profile.get('provenance', 'unspecified'),
        'candidate_ready_for_profile_review': bool(passed and identity and source_ready),
        'source_profile_flags': source_flags,
        'source_profile_development_only': source_flags['development_only'] is True,
        'source_profile_calibration_passed': source_flags['passed'] is True,
        'source_profile_candidate_ready_for_profile_review': source_flags['candidate_ready_for_profile_review'] is True,
        'source_profile_independent_spatial_coverage_passed': source_flags['independent_spatial_coverage_passed'] is True,
        'hardware_release_allowed': False,
        'hardware_release_reason': 'Requires independent real calibration/optical acceptance, a newly justified radius guard, RTL regression and routed board-build binding.',
        'profile_sha256': hashlib.sha256(json.dumps(profile, sort_keys=True, allow_nan=False).encode('utf-8')).hexdigest(),
        'source_image_size': list(source_size), 'output_size': list(size), 'output_K': new_k.tolist(),
        'fisheye_coefficients_used': d.tolist(), 'fitted_brown_radial_coefficients': coefficients.tolist(),
        'integer_config': c, 'sample_stride': stride, 'full_requested_frames_checked': full,
        'profile_scope_known': scope_maximum is not None,
        'profile_maximum_ray_angle_deg': scope_maximum,
        'maximum_requested_ray_angle_deg': requested_maximum_angle,
        'maximum_points_per_frame': maximum_points_per_frame,
        'points_per_frame_checked': sampled_points,
        'existing_board_radius_guard_applied': False,
        'required_radius_guard_q22_for_checked_rays': max(row['maximum_normalized_radius_squared_q22'] for row in rows)+2,
        'source_sha256': {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in
                          (Path(__file__), ROOT/'model/rotation.py', ROOT/'tools/generate-brown-vectors.py')},
        'coordinates_checked': sum(row['coordinates_checked'] for row in rows),
        'requested_full_frame_coordinates': size[0]*size[1]*len(angles),
        'criteria': {'maximum_coordinate_error_px': maximum_error_px,
                     'minimum_in_bounds_fraction': minimum_in_bounds_fraction,
                     'arithmetic_invalid_max': 0, 'folded_samples_max': 0, 'requires_stride_one': True},
        'frames': rows,
        'limits': 'Model approximation only. Finite-difference folds and rectangular source bounds do not prove lens edge coverage or optical accuracy. Sampled runs cannot pass a full-frame candidate. This fits only the requested image sizes, output camera and angles; parameters and old radius guards must not be reused outside that scope. No board include, old calibration, bitstream or evidence is modified.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('profile', type=Path, help='JSON with model=fisheye, K, D[4], image_size, provenance, camera_id and profile_id')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--angles', type=float, nargs='+', default=[0])
    parser.add_argument('--output-size', type=int, nargs=2)
    parser.add_argument('--output-k', type=Path, help='JSON containing a 3x3 output intrinsic matrix')
    parser.add_argument('--stride', type=int, default=1)
    parser.add_argument('--maximum-error-px', type=float, default=.25)
    parser.add_argument('--minimum-in-bounds-fraction', type=float, default=.5)
    parser.add_argument('--maximum-points-per-frame', type=int, default=2500000)
    args = parser.parse_args()
    if not args.output.parent.is_dir():
        parser.error('output parent directory must already exist; this tool never creates directories')
    if args.output.exists():
        parser.error('output already exists; choose a new report filename to preserve evidence')
    profile = json.loads(args.profile.read_text(encoding='utf-8-sig'))
    output_k = json.loads(args.output_k.read_text(encoding='utf-8-sig')) if args.output_k else None
    report = audit_profile(profile, output_size=args.output_size, output_k=output_k,
        angles=args.angles, stride=args.stride, maximum_error_px=args.maximum_error_px,
        minimum_in_bounds_fraction=args.minimum_in_bounds_fraction,
        maximum_points_per_frame=args.maximum_points_per_frame)
    report['source_profile_file_sha256'] = hashlib.sha256(args.profile.read_bytes()).hexdigest()
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False)+'\n', encoding='utf-8')
    print(json.dumps({key: report[key] for key in ('passed', 'coordinates_checked', 'synthetic_input', 'profile_identity_bound', 'hardware_release_allowed')}))
    if not report['passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
