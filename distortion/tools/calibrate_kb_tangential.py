"""Compare KB4 and KB4-T2 on a frozen real-image train/holdout split.

KB4-T2 applies two decentering terms AFTER the KB angular radial projection.
It is not the Brown perspective model and is not OpenCV's native fisheye model.
Parameter order: fx, fy, cx, cy, k1, k2, k3, k4, [p1, p2]. Skew is zero.
Reference convention: Project Aria FisheyeRadTanThinPrism, numK=4, no prism,
independent focal lengths; our p1=Aria p1 and our p2=Aria p0.
No camera, UART, FPGA, or deployment operations are performed.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
from pathlib import Path
import sys
import time
import zlib

import cv2
import numpy as np
import scipy
from scipy.optimize import least_squares


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2,
                                   allow_nan=False), encoding='utf-8')


def camera_matrix(parameters):
    fx, fy, cx, cy = parameters[:4]
    return np.array([[fx, 0., cx], [0., fy, cy], [0., 0., 1.]])


def native_matrix(parameters):
    return np.array([[2., 0., .5], [0., 2., .5], [0., 0., 1.]]) @ camera_matrix(parameters)


def tangential(q, p):
    x, y = q[:, 0], q[:, 1]
    p1, p2 = p
    s = x*x + y*y
    return q + np.column_stack((2*p1*x*y+p2*(s+2*x*x),
                                p1*(s+2*y*y)+2*p2*x*y))


def project(world, intrinsic, pose, with_jacobian=False):
    """Independent fx/fy, zero skew, KB4 radial then optional tangential."""
    q, j = cv2.fisheye.projectPoints(world.reshape(1, -1, 3), pose[:3], pose[3:],
                                    np.eye(3), intrinsic[4:8])
    q = q.reshape(-1, 2)
    p1, p2 = intrinsic[8:10] if len(intrinsic) == 10 else (0., 0.)
    distorted = tangential(q, (p1, p2))
    pixels = distorted * intrinsic[:2] + intrinsic[2:4]
    if not with_jacobian:
        return pixels
    n = len(q)
    x, y = q[:, 0], q[:, 1]
    chain = np.empty((n, 2, 2))
    chain[:, 0, 0] = 1 + 2*p1*y + 6*p2*x
    chain[:, 0, 1] = 2*p1*x + 2*p2*y
    chain[:, 1, 0] = chain[:, 0, 1]
    chain[:, 1, 1] = 1 + 6*p1*y + 2*p2*x
    chain *= intrinsic[None, :2, None]
    # OpenCV columns: fx,fy,cx,cy,k1..k4,rvec(3),tvec(3),alpha.
    normalized_j = j.reshape(n, 2, 15)
    camera_j = np.zeros((n, 2, len(intrinsic)))
    camera_j[:, 0, 0] = distorted[:, 0]
    camera_j[:, 1, 1] = distorted[:, 1]
    camera_j[:, 0, 2] = 1
    camera_j[:, 1, 3] = 1
    camera_j[:, :, 4:8] = np.einsum('nij,njk->nik', chain, normalized_j[:, :, 4:8])
    if len(intrinsic) == 10:
        camera_j[:, 0, 8] = intrinsic[0] * 2*x*y
        camera_j[:, 0, 9] = intrinsic[0] * (3*x*x+y*y)
        camera_j[:, 1, 8] = intrinsic[1] * (x*x+3*y*y)
        camera_j[:, 1, 9] = intrinsic[1] * 2*x*y
    pose_j = np.einsum('nij,njk->nik', chain, normalized_j[:, :, 8:14])
    return pixels, camera_j.reshape(-1, len(intrinsic)), pose_j.reshape(-1, 6)


def projection_checks(world, intrinsic, pose):
    zero = np.r_[intrinsic[:8], 0., 0.]
    expected = cv2.fisheye.projectPoints(world.reshape(1, -1, 3), pose[:3], pose[3:],
                                        camera_matrix(zero), zero[4:8])[0].reshape(-1, 2)
    zero_error = float(np.max(np.abs(project(world, zero, pose)-expected)))
    assert zero_error < 1e-9, zero_error
    test = zero.copy()
    test[8:] = [0.0013, -0.0021]
    projected, camera_j, pose_j = project(world, test, pose, True)
    full = np.r_[test, pose]
    numerical = np.empty((len(world)*2, len(full)))
    for i in range(len(full)):
        step = 1e-5*max(abs(full[i]), 1.) if i < 4 else 1e-6*max(abs(full[i]), 1.)
        plus, minus = full.copy(), full.copy()
        plus[i] += step
        minus[i] -= step
        numerical[:, i] = ((project(world, plus[:10], plus[10:])-
                             project(world, minus[:10], minus[10:]))/(2*step)).ravel()
    analytic = np.column_stack((camera_j, pose_j))
    scaled_error = float(np.max(np.abs(analytic-numerical)/(1+np.abs(numerical))))
    assert scaled_error < 2e-5, scaled_error
    # Explicit formula provides a second forward implementation independent of OpenCV.
    xyz = world @ cv2.Rodrigues(pose[:3])[0].T + pose[3:]
    xy = xyz[:, :2]/xyz[:, 2, None]
    radius = np.linalg.norm(xy, axis=1)
    theta = np.arctan(radius)
    powers = np.column_stack([theta**i for i in (2, 4, 6, 8)])
    theta_d = theta*(1+powers @ test[4:8])
    q = xy*np.divide(theta_d, radius, out=np.ones_like(radius), where=radius != 0)[:, None]
    formula = tangential(q, test[8:])*test[:2]+test[2:4]
    formula_error = float(np.max(np.abs(projected-formula)))
    assert formula_error < 1e-9, formula_error
    return {'zero_tangential_vs_opencv_max_px': zero_error,
            'analytic_jacobian_scaled_max_error': scaled_error,
            'explicit_kb_t2_formula_max_px': formula_error}


def initial_pose(world, pixels, intrinsic):
    normalized = cv2.fisheye.undistortPoints(pixels.reshape(1, -1, 2),
                                            camera_matrix(intrinsic), intrinsic[4:8])
    ok, r, t = cv2.solvePnP(world, normalized.reshape(-1, 1, 2), np.eye(3), None)
    if not ok:
        raise RuntimeError('Initial board pose failed')
    return np.r_[r.ravel(), t.ravel()]


class Bundle:
    def __init__(self, world, views, dimension):
        self.world, self.views, self.dimension = world, views, dimension
        self.last_x = None

    def evaluate(self, x):
        if self.last_x is not None and np.array_equal(x, self.last_x):
            return self.last_r, self.last_j
        d, count = self.dimension, len(self.world)*2
        residual = np.empty(len(self.views)*count)
        jacobian = np.zeros((len(residual), len(x)))
        for i, pixels in enumerate(self.views):
            pose_slice = slice(d+6*i, d+6*(i+1))
            row = slice(i*count, (i+1)*count)
            estimate, intrinsic_j, pose_j = project(self.world, x[:d], x[pose_slice], True)
            residual[row] = (estimate-pixels).ravel()
            jacobian[row, :d], jacobian[row, pose_slice] = intrinsic_j, pose_j
        self.last_x, self.last_r, self.last_j = x.copy(), residual, jacobian
        return residual, jacobian

    def fit(self, intrinsic, poses):
        x0 = np.r_[intrinsic, np.asarray(poses).ravel()]
        return least_squares(lambda x: self.evaluate(x)[0], x0,
                             jac=lambda x: self.evaluate(x)[1], method='lm', x_scale='jac',
                             ftol=1e-12, xtol=1e-12, gtol=1e-10, max_nfev=150)


def fit_pose(world, pixels, intrinsic, pose):
    return least_squares(lambda p: (project(world, intrinsic, p)-pixels).ravel(), pose,
                         jac=lambda p: project(world, intrinsic, p, True)[2],
                         method='lm', x_scale='jac', ftol=1e-12, xtol=1e-12,
                         gtol=1e-10, max_nfev=100)


def metrics(deltas):
    per_view = [float(np.sqrt(np.mean(np.sum(d*d, axis=1))))*2 for d in deltas]
    point_errors = np.concatenate([np.linalg.norm(d, axis=1)*2 for d in deltas])
    return {'per_view_rms_native_px': per_view,
            'mean_view_rms_native_px': float(np.mean(per_view)),
            'pooled_rms_native_px': float(np.sqrt(np.mean(point_errors**2))),
            'max_view_rms_native_px': float(max(per_view)),
            'point_error_p95_native_px': float(np.quantile(point_errors, .95))}


def geometry_check(intrinsic, kout):
    theta = np.linspace(0, np.pi/2, 2001)
    derivative = 1+sum((2*i+3)*intrinsic[4+i]*theta**(2*i+2) for i in range(4))
    xx, yy = np.meshgrid(np.linspace(0, 959, 161), np.linspace(0, 539, 91))
    rays = np.column_stack(((xx.ravel()-kout[0, 2])/kout[0, 0],
                            (yy.ravel()-kout[1, 2])/kout[1, 1], np.ones(xx.size)))
    mapped = project(rays, intrinsic, np.zeros(6))
    q = cv2.fisheye.projectPoints(rays.reshape(1, -1, 3), np.zeros(3), np.zeros(3),
                                  np.eye(3), intrinsic[4:8])[0].reshape(-1, 2)
    x, y = q[:, 0], q[:, 1]
    p1, p2 = intrinsic[8:10] if len(intrinsic) == 10 else (0., 0.)
    determinant = (1+2*p1*y+6*p2*x)*(1+6*p1*y+2*p2*x)-(2*p1*x+2*p2*y)**2
    inside = (mapped[:, 0] >= 0)&(mapped[:, 0] <= 959)&(mapped[:, 1] >= 0)&(mapped[:, 1] <= 539)
    return {'positive_focals': bool(np.all(intrinsic[:2] > 0)),
            'principal_point_inside_image': bool(0 < intrinsic[2] < 960 and 0 < intrinsic[3] < 540),
            'radial_min_derivative_0_to_90deg': float(derivative.min()),
            'tangential_min_determinant_on_preview_grid': float(determinant.min()),
            'preview_all_map_finite': bool(np.isfinite(mapped).all()),
            'preview_valid_fraction_grid': float(inside.mean())}


def load_dataset(manifest, output):
    source = json.loads(manifest.read_text(encoding='utf-8'))
    points, images = [], []
    for i, view in enumerate(source['views']):
        path, meta = Path(view['image']['path']), Path(view['metadata']['path'])
        assert digest(path) == view['image']['sha256'], path
        assert digest(meta) == view['metadata']['sha256'], meta
        metadata = json.loads(meta.read_text(encoding='utf-8'))
        payload = Path(metadata['payload']['path'])
        raw = payload.read_bytes()
        assert digest(payload) == metadata['payload']['sha256']
        assert f'{zlib.crc32(raw):08x}' == metadata['source_crc32']
        gray = cv2.imdecode(np.fromfile(path, np.uint8), cv2.IMREAD_GRAYSCALE)
        assert gray.shape == (540, 960)
        assert np.array_equal(gray, np.frombuffer(raw, np.uint8).reshape(540, 960))
        ok, corners = cv2.findChessboardCornersSB(gray, tuple(source['inner_corners']))
        if not ok:
            raise RuntimeError(f'Frozen view lost its corners: {path}')
        points.append(corners.reshape(-1, 2).astype(np.float64))
        images.append(gray)
        print(f'corners {i+1}/{len(source["views"])}', flush=True)
    points = np.asarray(points)
    np.savez_compressed(output/'corners.npz', corners=points,
                        train_indices=source['train_indices'], held_out_indices=source['held_out_indices'])
    return source, points, images


def make_previews(output, images, held, models, kout):
    xx, yy = np.meshgrid(np.arange(960), np.arange(540))
    rays = np.column_stack(((xx.ravel()-kout[0, 2])/kout[0, 0],
                            (yy.ravel()-kout[1, 2])/kout[1, 1], np.ones(xx.size)))
    maps = [project(rays, np.asarray(m['parameters_snapshot']), np.zeros(6)).reshape(540, 960, 2)
            .astype(np.float32) for m in models]
    for index in held:
        panels = []
        for label, frame in [('Original snapshot', images[index])] + [
                (m['name'], cv2.remap(images[index], mapping[:, :, 0], mapping[:, :, 1],
                                      cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT))
                for m, mapping in zip(models, maps)]:
            panel = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
            panel = cv2.copyMakeBorder(panel, 40, 0, 0, 0, cv2.BORDER_CONSTANT, value=(255, 255, 255))
            cv2.putText(panel, label, (15, 27), cv2.FONT_HERSHEY_SIMPLEX, .75, (0, 0, 0), 2)
            panels.append(panel)
        joined = np.concatenate(panels, axis=1)
        cv2.imencode('.png', joined)[1].tofile(output/f'held-{index:02d}-comparison.png')
    difference = np.linalg.norm(maps[1]-maps[0], axis=2)*2
    return {'same_output_K_snapshot': kout.tolist(),
            'model_source_coordinate_difference_native_px': {
                'median': float(np.median(difference)), 'p95': float(np.quantile(difference, .95)),
                'max': float(difference.max())}}


def run(args):
    start = time.perf_counter()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    source, points, images = load_dataset(args.manifest, output)
    cols, rows = source['inner_corners']
    world = np.zeros((cols*rows, 3), np.float64)
    world[:, :2] = np.mgrid[0:cols, 0:rows].T.reshape(-1, 2)*source['square_mm']
    old = source['candidates']['fisheye']
    k = np.asarray(old['K_snapshot'])
    base0 = np.r_[k[0, 0], k[1, 1], k[0, 2], k[1, 2], old['D_normalized']]
    train, held = source['train_indices'], source['held_out_indices']
    poses = [initial_pose(world, p, base0) for p in points]
    checks = projection_checks(world, base0, poses[train[0]])
    write_json(output/'projection-checks.json', checks)
    print('projection and analytic Jacobian checks passed', checks, flush=True)
    baseline_fit = Bundle(world, points[train], 8).fit(base0, np.asarray(poses)[train])
    assert baseline_fit.success, baseline_fit.message
    base = baseline_fit.x[:8]
    base_poses = baseline_fit.x[8:].reshape(-1, 6)
    trials = []
    fits = []
    for initial_p in ([0., 0.], [0.002, -0.002], [-0.002, 0.002]):
        fit = Bundle(world, points[train], 10).fit(np.r_[base, initial_p], base_poses)
        trials.append({'initial_p1_p2': initial_p, 'success': bool(fit.success),
                       'cost': float(fit.cost), 'nfev': fit.nfev, 'message': fit.message})
        if fit.success:
            fits.append(fit)
        print('KB4-T2 training fit', trials[-1], flush=True)
    assert fits, 'No extended model fit converged'
    extension_fit = min(fits, key=lambda f: f.cost)  # Training-only selection.
    profile_path = args.manifest.with_name('new-lens-fisheye-1080-c.json')
    kout = np.asarray(json.loads(profile_path.read_text(encoding='utf-8'))['preview']['new_K_snapshot'])
    models = []
    per_view_rows = []
    for name, dim, fit in [('KB4', 8, baseline_fit), ('KB4-T2', 10, extension_fit)]:
        intrinsic = fit.x[:dim]
        train_poses = fit.x[dim:].reshape(-1, 6)
        train_deltas = [project(world, intrinsic, pose)-points[index]
                        for index, pose in zip(train, train_poses)]
        held_deltas, held_poses, held_opt = [], [], []
        for index in held:
            refined = fit_pose(world, points[index], intrinsic, poses[index])
            assert refined.success, refined.message
            held_poses.append(refined.x.tolist())
            held_opt.append({'success': bool(refined.success), 'nfev': refined.nfev,
                             'optimality': float(refined.optimality)})
            held_deltas.append(project(world, intrinsic, refined.x)-points[index])
        all_poses = list(train_poses)+[np.asarray(p) for p in held_poses]
        depths = [(world @ cv2.Rodrigues(p[:3])[0].T+p[3:])[:, 2].min() for p in all_poses]
        checks_geometry = geometry_check(intrinsic, kout)
        checks_geometry['min_board_depth_mm'] = float(min(depths))
        assert min(depths) > 0 and checks_geometry['positive_focals']
        model = {'name': name, 'parameter_order': ['fx', 'fy', 'cx', 'cy', 'k1', 'k2', 'k3', 'k4']+
                 (['p1', 'p2'] if dim == 10 else []),
                 'parameters_snapshot': intrinsic.tolist(), 'K_native': native_matrix(intrinsic).tolist(),
                 'D_order': ['k1', 'k2', 'k3', 'k4']+(['p1', 'p2'] if dim == 10 else []),
                 'D': intrinsic[4:].tolist(), 'training': metrics(train_deltas), 'held_out': metrics(held_deltas),
                 'train_poses_rvec_tvec_mm': train_poses.tolist(),
                 'held_poses_rvec_tvec_mm': held_poses, 'held_optimizers': held_opt,
                 'geometry_checks': checks_geometry,
                 'fit': {'success': bool(fit.success), 'cost': float(fit.cost),
                         'nfev': fit.nfev, 'optimality': float(fit.optimality)}}
        models.append(model)
        for index, delta, pose in zip(held, held_deltas, held_poses):
            per_view_rows.append({'model': name, 'view_index': index,
                                 'image': Path(source['views'][index]['image']['path']).name,
                                 'rms_native_px': float(np.sqrt(np.mean(np.sum(delta**2, axis=1))))*2,
                                 'max_point_error_native_px': float(np.max(np.linalg.norm(delta, axis=1)))*2})
        np.savez_compressed(output/f'{name}-held-residuals.npz', view_indices=held,
                            residuals_snapshot_px=np.asarray(held_deltas))
        print(name, model['D'], model['training'], model['held_out'], flush=True)
    preview = make_previews(output, images, held, models, kout)
    baseline_error = models[0]['held_out']['mean_view_rms_native_px']
    extended_error = models[1]['held_out']['mean_view_rms_native_px']
    comparison = {'held_mean_reduction_percent': 100*(1-extended_error/baseline_error),
                  'held_views_improved': int(sum(b < a for a, b in zip(
                      models[0]['held_out']['per_view_rms_native_px'], models[1]['held_out']['per_view_rms_native_px']))),
                  'held_views': len(held)}
    result = {'schema': 'kb4-tangential-experiment-v1',
              'model_definition': 'KB4 angular radial projection followed by two decentering terms; no thin prism; zero skew',
              'formula': {'qx_qy': '(theta*(1+k1*theta^2+k2*theta^4+k3*theta^6+k4*theta^8)/r)*[x,y]',
                          'dx': '2*p1*qx*qy+p2*(3*qx^2+qy^2)', 'dy': 'p1*(qx^2+3*qy^2)+2*p2*qx*qy'},
              'reference_url': 'https://github.com/facebookresearch/Aria_data_tools/blob/main/src/sensors/camera/projection/FisheyeRadTanThinPrism.h',
              'capture_date_Asia_Shanghai': '2026-11-03 02:31-02:46',
              'manifest': str(args.manifest.resolve()), 'manifest_sha256': digest(args.manifest),
              'script_sha256': digest(__file__),
              'versions': {'python': platform.python_version(), 'numpy': np.__version__,
                           'opencv': cv2.__version__, 'scipy': scipy.__version__},
              'image_size': [960, 540], 'native_equivalent_size': [1920, 1080],
              'native_coordinate_transform': 'u_native=2*u_snapshot+0.5; v_native=2*v_snapshot+0.5',
              'inner_corners': [cols, rows], 'square_mm': source['square_mm'],
              'train_indices': train, 'held_out_indices': held, 'views': source['views'],
              'evaluation': 'Both models: ordinary pixel-space least squares; holdout intrinsics fixed, pose-only refinement; no holdout parameter tuning',
              'previous_fisheye_validation': {'mean_native_px': old['held_out_mean_native_px'],
                                             'method': 'undistortPoints plus normalized-plane solvePnP; not the same pose metric as this experiment'},
              'projection_checks': checks, 'extended_training_multistart': trials,
              'models': models, 'comparison': comparison, 'preview': preview,
              'hardware_modified': False, 'deployment_parameters_modified': False,
              'elapsed_seconds': time.perf_counter()-start}
    write_json(output/'result.json', result)
    with (output/'held-out-errors.csv').open('w', newline='', encoding='utf-8-sig') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(per_view_rows[0]))
        writer.writeheader()
        writer.writerows(per_view_rows)
    print('RESULT', json.dumps(comparison), 'OUTPUT', output, flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    run(parser.parse_args())
