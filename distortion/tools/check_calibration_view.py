"""Offline single-pose chessboard check; does not fit or accept a calibration.

Use explicit inner-corner counts, not the product/model label printed on a board.
The detector is the same default findChessboardCornersSB used by the calibrator.
"""
from pathlib import Path
import argparse
import json
import sys

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.calibrate_fisheye_profile import _decode_bound_capture, _digest
from tools.native_camera_capture import load_json, validate_binding, IDENTITY_FIELDS

cv2.setNumThreads(1)
cv2.ocl.setUseOpenCL(False)


def inspect_image(image, cols, rows):
    if any(type(n) is not int or not 3 <= n <= 32 for n in (cols, rows)):
        raise ValueError('explicit inner-corner cols/rows must be integers3..32')
    if (not isinstance(image, np.ndarray) or image.dtype != np.uint8 or
            image.ndim != 3 or image.shape[2] != 3 or image.size == 0 or
            image.shape[0]*image.shape[1] > 2500000):
        raise ValueError('bounded uint8 BGR image required')
    height, width = image.shape[:2]
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    found, corners = cv2.findChessboardCornersSB(gray, (cols, rows))
    result = {'inner_corners': [cols, rows], 'expected_corner_count': cols*rows,
              'image_size': [width, height], 'complete_board_detected': bool(found),
              'corners': [], 'source_image_3x3_corner_counts': [[0]*3 for _ in range(3)],
              'warnings': [], 'calibration_ready': False}
    if not found:
        result['warnings'].append('Complete declared board not detected; do not use this view in the dataset.')
        return result
    xy = corners.reshape(-1, 2)
    if len(xy) != cols*rows or not np.isfinite(xy).all():
        raise ValueError('detector returned incomplete/nonfinite corners')
    grid = xy.reshape(rows, cols, 2)
    spacing = np.concatenate((np.linalg.norm(np.diff(grid, axis=0), axis=2).ravel(),
                              np.linalg.norm(np.diff(grid, axis=1), axis=2).ravel()))
    counts = np.zeros((3, 3), dtype=int)
    for x, y in xy:
        if not 0 <= x < width or not 0 <= y < height:
            raise ValueError('detected corner is outside the source image')
        counts[min(2, int(y*3/height)), min(2, int(x*3/width))] += 1
    margin = float(np.min(np.column_stack((xy[:, 0], xy[:, 1], width-1-xy[:, 0], height-1-xy[:, 1]))))
    radius = np.hypot((xy[:, 0]-(width-1)/2)/(width/2), (xy[:, 1]-(height-1)/2)/(height/2))
    histogram, _ = np.histogram(radius, [0, .25, .5, .75, 1., np.inf])
    result.update(corners=xy.tolist(), source_image_3x3_corner_counts=counts.tolist(),
        adjacent_corner_spacing_px={'minimum': float(spacing.min()), 'median': float(np.median(spacing))},
        minimum_inner_corner_border_margin_px=margin,
        inner_corner_convex_hull_image_fraction=float(cv2.contourArea(cv2.convexHull(corners))/(width*height)),
        source_image_center_radius_histogram=histogram.tolist(),
        source_image_center_radius_bin_edges=[0, .25, .5, .75, 1., 'infinity'],
        radius_note='Image-center position only, not optical-axis radius, ray angle or measured field of view.')
    sharpness = {}
    for label, vertical in [('horizontal', False), ('vertical', True)]:
        try:
            average, edges = cv2.estimateChessboardSharpness(gray, (cols, rows), corners, vertical=vertical)
            values = [float(v) for v in average[:3]]
            if not np.isfinite(values).all():
                raise ValueError('nonfinite edge estimate')
            sharpness[label] = {'mean_10_90_transition_width_px': values[0],
                'mean_black_level': values[1], 'mean_white_level': values[2],
                'measured_edges': 0 if edges is None else len(edges)}
            if values[0] > 3:
                result['warnings'].append(label+' edge transition exceeds the OpenCV approximate3px sharpness guidance; inspect focus/motion.')
        except (cv2.error, ValueError) as error:
            sharpness[label] = {'available': False, 'reason': str(error)}
            result['warnings'].append(label+' edge sharpness unavailable; manual quality review required.')
    result['board_edge_sharpness'] = sharpness
    if spacing.min() < 8:
        result['warnings'].append('Some adjacent corners are under8px apart; move the board closer or reduce tilt.')
    if margin < 5:
        result['warnings'].append('An inner corner is within5px of the boundary; verify the entire board and outer white margin.')
    result['quality_note'] = ('Warnings guide capture only; a detected board does not prove board flatness, measured square size, '
        'unique pose, independent held-out data or sufficient dataset coverage. The hull and margin describe inner corners, not the full target.')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('metadata', type=Path)
    parser.add_argument('--binding', type=Path, required=True, help='current camera/lens/profile/mode and CAM port binding')
    parser.add_argument('--cols', type=int, required=True)
    parser.add_argument('--rows', type=int, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--overlay', type=Path, required=True, help='fresh diagnostic PNG; never a calibration input')
    parser.add_argument('--view-id')
    parser.add_argument('--pose-id')
    parser.add_argument('--session-id')
    parser.add_argument('--split', choices=('train', 'model_selection', 'held_out'))
    args = parser.parse_args()
    outputs = [args.output.resolve(), args.overlay.resolve()]
    if (len(set(outputs)) != 2 or any(not p.parent.is_dir() or p.exists() for p in outputs)
            or args.overlay.suffix.lower() != '.png'):
        parser.error('use two fresh output files in existing directories; overlay must be PNG')
    labels = (args.view_id, args.pose_id, args.session_id, args.split)
    if any(labels) and not all(labels):
        parser.error('view/pose/session/split must all be explicit together')
    binding = load_json(args.binding)
    identity = validate_binding(binding)
    metadata = load_json(args.metadata)
    if any(metadata.get('identity_binding', {}).get(key) != identity[key] for key in IDENTITY_FIELDS):
        raise ValueError('capture metadata differs from the selected current camera/lens/profile/mode/eye')
    image_path = Path(metadata['image_path'])
    if not image_path.is_absolute():
        image_path = args.metadata.parent/image_path
    image_path = image_path.resolve()
    image = cv2.imdecode(np.fromfile(image_path, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError('unreadable native PNG')
    if [image.shape[1], image.shape[0]] != binding['image_size']:
        raise ValueError('native PNG dimensions differ from the selected capture mode')
    view = {'path': str(image_path), 'sha256': _digest(image_path),
            'metadata_path': str(args.metadata.resolve()), 'metadata_sha256': _digest(args.metadata)}
    manifest = {key: identity[key] for key in ('camera_id', 'lens_id', 'profile_id', 'capture_mode_id')}
    manifest['image_size'] = binding['image_size']
    capture = _decode_bound_capture(view, manifest, args.metadata.parent, image, image_path)
    report = inspect_image(image, args.cols, args.rows)
    report.update(schema=1, image_path=str(image_path), image_sha256=view['sha256'],
        metadata_path=view['metadata_path'], metadata_sha256=view['metadata_sha256'],
        identity_binding=identity, capture_pixel_binding=capture, hardware_accessed_by_checker=False,
        optical_calibration_verified=False, hardware_release_allowed=False,
        square_size_measured_by_checker=False, physical_board_specification_inferred=False,
        limits='One source-bound pose diagnostic only. No K/D fit, physical-eye proof, board-size assumption, '
               'pose-count increment, train/held-out acceptance or calibration release. A PNG overlay is derived inspection material.')
    overlay = image.copy()
    if report['complete_board_detected']:
        corners = np.array(report['corners'], dtype=np.float32).reshape(-1, 1, 2)
        cv2.drawChessboardCorners(overlay, (args.cols, args.rows), corners, True)
        if all(labels):
            report['manifest_view_candidate'] = dict(view_id=args.view_id, pose_id=args.pose_id,
                session_id=args.session_id, split=args.split, **view)
    ok, encoded = cv2.imencode('.png', overlay)
    if not ok:
        raise ValueError('overlay PNG encoding failed')
    with args.overlay.open('xb') as stream:
        stream.write(encoded.tobytes())
    report['overlay_path'] = str(args.overlay.resolve())
    report['overlay_sha256'] = _digest(args.overlay)
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write('\n')
    print(json.dumps({'complete_board_detected': report['complete_board_detected'],
        'corner_count': len(report['corners']), 'warnings': report['warnings'], 'report': str(args.output)}))
    return 0 if report['complete_board_detected'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
