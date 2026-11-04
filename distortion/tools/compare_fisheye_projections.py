"""Offline output-projection comparison with the deployed KB4 lens held fixed.

No recalibration, deployment, RTL, or hardware operations. Panini d=1 has
inverse ray [xn, yn, 1-xn*xn/4]. All variants resample the same source image.
"""
import argparse
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np


def source_map(rays, k, d):
    radius = np.hypot(rays[..., 0], rays[..., 1])
    theta = np.arctan2(radius, rays[..., 2])
    z = theta*theta
    td = theta*(1+z*(d[0]+z*(d[1]+z*(d[2]+z*d[3]))))
    scale = np.divide(td, radius, out=np.ones_like(td), where=radius != 0)
    return np.stack((k[0, 0]*rays[..., 0]*scale+k[0, 2],
                     k[1, 1]*rays[..., 1]*scale+k[1, 2]), axis=-1).astype(np.float32)


def make_map(model, k, d, w=960, h=540):
    kout = np.asarray(model['Kout_snapshot'])
    yy, xx = np.indices((h, w), dtype=np.float64)
    xn = (xx-kout[0, 2])/kout[0, 0]
    yn = (yy-kout[1, 2])/kout[1, 1]
    zz = 1-xn*xn/4 if model['projection'] == 'panini_d1' else np.ones_like(xn)
    rays = np.stack((xn, yn, zz), axis=-1)
    assert np.all(zz > 0)
    mapping = source_map(rays, k, d)
    assert np.isfinite(mapping).all()
    valid = (mapping[..., 0] >= 0)&(mapping[..., 0] <= w-1)&(mapping[..., 1] >= 0)&(mapping[..., 1] <= h-1)
    # HFOV and horizontal angular magnification are evaluated at the horizon.
    xedge = np.array([-kout[0, 2], w-1-kout[0, 2]])/kout[0, 0]
    angles = 2*np.arctan(xedge/2) if model['projection'] == 'panini_d1' else np.arctan(xedge)
    magnification = 1/np.cos(angles/2 if model['projection'] == 'panini_d1' else angles)**2
    model['left_right_angles_deg'] = np.rad2deg(angles).tolist()
    model['horizontal_fov_deg'] = float(np.rad2deg(angles[1]-angles[0]))
    model['horizontal_angular_magnification_edge_over_center'] = magnification.tolist()
    model['valid_source_fraction'] = float(valid.mean())
    model['all_coordinates_finite'] = True
    return mapping


def titled(frame, title, details):
    image = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
    image = cv2.copyMakeBorder(image, 66, 0, 0, 0, cv2.BORDER_CONSTANT, value=(255, 255, 255))
    cv2.putText(image, title, (16, 27), cv2.FONT_HERSHEY_SIMPLEX, .75, (0, 0, 0), 2)
    cv2.putText(image, details, (16, 52), cv2.FONT_HERSHEY_SIMPLEX, .53, (0, 0, 0), 1)
    return image


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    root = Path(__file__).resolve().parents[2]
    manifest_path = root/'distortion/work/hdmi-camera-snapshot-20261102-a/new-lens-calibration-c.json'
    profile_path = manifest_path.with_name('new-lens-fisheye-1080-c.json')
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    profile = json.loads(profile_path.read_text(encoding='utf-8'))
    camera = manifest['candidates']['fisheye']
    k = np.asarray(camera['K_snapshot'])
    d = np.asarray(camera['D_normalized'])
    old = np.asarray(profile['preview']['new_K_snapshot'])
    models = [{'name': 'Current perspective', 'id': 'current', 'projection': 'rectilinear',
               'Kout_snapshot': old.tolist()}]
    for angle in (110., 105.):
        focal = 959/(2*np.tan(np.deg2rad(angle/2)))
        kout = np.array([[focal, 0, 479.5], [0, focal, 269.5], [0, 0, 1.]])
        models.append({'name': f'Perspective {angle:g} deg', 'id': f'perspective-{angle:g}',
                       'projection': 'rectilinear', 'Kout_snapshot': kout.tolist()})
    edges = np.arctan(np.array([-old[0, 2], 959-old[0, 2]])/old[0, 0])
    pan_edges = 2*np.tan(edges/2)
    focal = 959/(pan_edges[1]-pan_edges[0])
    pan_k = np.array([[focal, 0, -focal*pan_edges[0]], [0, focal, old[1, 2]], [0, 0, 1.]])
    models.append({'name': 'Panini d=1, same horizontal FOV', 'id': 'panini-d1',
                   'projection': 'panini_d1', 'Kout_snapshot': pan_k.tolist()})
    maps = [make_map(model, k, d) for model in models]
    cvx, cvy = cv2.fisheye.initUndistortRectifyMap(k, d, np.eye(3), old, (960, 540), cv2.CV_32FC1)
    check = float(np.max(np.abs(maps[0]-np.stack((cvx, cvy), axis=-1))))
    assert check < 1e-4, check
    assert abs(models[0]['horizontal_fov_deg']-models[3]['horizontal_fov_deg']) < 1e-9
    indices = [0, 5, 20, 30]
    for index in indices:
        source = manifest['views'][index]['image']
        path = Path(source['path'])
        assert hashlib.sha256(path.read_bytes()).hexdigest() == source['sha256']
        gray = cv2.imdecode(np.fromfile(path, np.uint8), cv2.IMREAD_GRAYSCALE)
        panels = [titled(gray, 'Original fisheye image', 'Same source pixels; fixed KB4 calibration')]
        for model, mapping in zip(models, maps):
            corrected = cv2.remap(gray, mapping[..., 0], mapping[..., 1], cv2.INTER_LINEAR,
                                   borderMode=cv2.BORDER_CONSTANT)
            cv2.imencode('.png', corrected)[1].tofile(args.output/f'view-{index:02d}-{model["id"]}.png')
            panels.append(titled(corrected, model['name'],
                                 f'Horizontal FOV {model["horizontal_fov_deg"]:.1f} deg; '+
                                 ('straight lines, cropped FOV' if model['projection'] == 'rectilinear' else
                                  'less edge stretch; some horizontal lines curve')))
        # Main comparison is raw / current / 110-degree perspective / same-FOV Panini.
        collage = np.vstack((np.hstack((panels[0], panels[1])), np.hstack((panels[2], panels[4]))))
        cv2.imencode('.png', collage)[1].tofile(args.output/f'view-{index:02d}-comparison.png')
    transform = np.array([[2., 0., .5], [0., 2., .5], [0., 0., 1.]])
    for model in models:
        model['Kout_native'] = (transform @ np.asarray(model['Kout_snapshot'])).tolist()
    result = {'schema': 'fisheye-output-projection-comparison-v1', 'source_profile': profile['source_fit'],
              'calibration_profile_sha256': hashlib.sha256(profile_path.read_bytes()).hexdigest(),
              'lens_model_held_fixed': 'existing deployed KB4; no added tangential terms in this comparison',
              'input_size': [960, 540], 'view_indices': indices, 'models': models,
              'current_map_vs_opencv_max_snapshot_px': check,
              'panini_horizontal_angular_endpoints_match_current': True,
              'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'hardware_modified': False, 'RTL_modified': False,
              'metric_definition': 'horizontal angular magnification dx/d(longitude) at latitude=0, normalized by its optical-axis value; not image quality or frame rate'}
    (args.output/'result.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps({'output': str(args.output), 'map_check_px': check, 'models': models}, indent=2))


if __name__ == '__main__':
    main()
