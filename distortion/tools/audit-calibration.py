"""Check whole-image maps and show spatial evidence independently of fit RMS."""
from pathlib import Path
import argparse
import json
import cv2
import numpy as np


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('comparison', type=Path)
    parser.add_argument('selection', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    fit = json.loads(args.comparison.read_text(encoding='utf-8'))
    selection = json.loads(args.selection.read_text(encoding='utf-8'))
    args.output.mkdir(parents=True, exist_ok=True)
    w, h = fit['image_size']
    canvas = np.full((h, w, 3), 255, dtype=np.uint8)
    counts = np.zeros((3, 3), dtype=int)
    observations = []
    for name in selection['selected']:
        frame = cv2.imdecode(np.fromfile(name, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
        ok, corners = cv2.findChessboardCornersSB(frame, (9, 6))
        assert ok
        xy = corners.reshape(-1, 2)
        observations.append(xy)
        for x, y in xy:
            counts[min(2, int(y*3/h)), min(2, int(x*3/w))] += 1
            cv2.circle(canvas, (round(float(x)), round(float(y))), 2, (190, 110, 0), -1)
    for i in (1, 2):
        cv2.line(canvas, (w*i//3, 0), (w*i//3, h-1), (100, 100, 100), 1)
        cv2.line(canvas, (0, h*i//3), (w-1, h*i//3), (100, 100, 100), 1)
    for row in range(3):
        for col in range(3):
            cv2.putText(canvas, f'{counts[row,col]} corners', (col*w//3+8, row*h//3+22),
                        cv2.FONT_HERSHEY_SIMPLEX, .48, (0, 0, 0), 1, cv2.LINE_AA)
    cv2.imencode('.png', canvas)[1].tofile(args.output/'corner-coverage.png')
    report = {'source_comparison': str(args.comparison.resolve()),
              'selected_views': len(observations), 'corner_counts_by_3x3_region': counts.tolist(),
              'all_nine_regions_observed': bool((counts > 0).all()),
              'measured_square_mm': 20, 'five_squares_measured_mm_user_confirmed': 100,
              'status': 'provisional; inspect coverage and full-image mapping before using hardware parameters',
              'candidates': {}}
    sample = cv2.imdecode(np.fromfile(fit['held_out_images'][-1], dtype=np.uint8), cv2.IMREAD_COLOR)
    for model, candidate in fit['candidates'].items():
        if 'error' in candidate:
            report['candidates'][model] = candidate
            continue
        k, d = np.array(candidate['K']), np.array(candidate['D'])
        if model == 'fisheye':
            mx, my = cv2.fisheye.initUndistortRectifyMap(k, d, np.eye(3), k, (w,h), cv2.CV_32FC1)
        else:
            mx, my = cv2.initUndistortRectifyMap(k, d, None, k, (w,h), cv2.CV_32FC1)
        # For output->source coordinates, a nonpositive Jacobian indicates a
        # fold/orientation reversal. A small fit error cannot rule this out.
        du_dy, du_dx = np.gradient(mx.astype(np.float64))
        dv_dy, dv_dx = np.gradient(my.astype(np.float64))
        det = du_dx*dv_dy-du_dy*dv_dx
        finite = np.isfinite(mx) & np.isfinite(my) & np.isfinite(det)
        folds = finite & (det <= 0)
        inbounds = finite & (mx>=0) & (mx<w-1) & (my>=0) & (my<h-1)
        report['candidates'][model] = {
            'training_rms_px': candidate['training_rms_px'],
            'held_out_mean_px': candidate['held_out_mean_px'],
            'mapping_uses_output_K_equal_to_input_K': True,
            'finite_map': bool(finite.all()), 'folded_pixels': int(folds.sum()),
            'jacobian_determinant_min': float(det[finite].min()),
            'bilinear_all_neighbours_in_bounds_fraction': float(inbounds.mean()),
            'limits': 'Finite-difference fold check, not an independent edge accuracy measurement.'}
        preview = cv2.remap(sample, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)
        pair = np.concatenate((sample, preview), axis=1)
        cv2.imencode('.png', pair)[1].tofile(args.output/f'{model}-provisional-comparison.png')
    (args.output/'audit.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
