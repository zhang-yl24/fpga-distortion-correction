"""Fit real chessboard captures; reserve every fifth view for validation."""
import argparse
import json
from pathlib import Path
import cv2
import numpy as np


def fit(obj, img, size, model):
    if model == 'fisheye':
        flags = cv2.fisheye.CALIB_RECOMPUTE_EXTRINSIC | cv2.fisheye.CALIB_FIX_SKEW | cv2.fisheye.CALIB_CHECK_COND
        return cv2.fisheye.calibrate(obj, img, size, np.eye(3), np.zeros((4,1)), flags=flags)
    return cv2.calibrateCamera([p.reshape(-1,3).astype(np.float32) for p in obj],
                               [p.reshape(-1,1,2).astype(np.float32) for p in img], size, None, None)


def validate(obj, img, k, d, model):
    errors = []
    for world, measured in zip(obj, img):
        if model == 'fisheye':
            # Fix intrinsics; only estimate each held-out board pose.
            undistorted = cv2.fisheye.undistortPoints(measured, k, d)
            ok, r, t = cv2.solvePnP(world.reshape(-1,3), undistorted.reshape(-1,1,2), np.eye(3), None)
            if not ok: raise ValueError('held-out pose solve failed')
            projected, _ = cv2.fisheye.projectPoints(world, r, t, k, d)
        else:
            ok, r, t = cv2.solvePnP(world.reshape(-1,3), measured.reshape(-1,1,2), k, d)
            if not ok: raise ValueError('held-out pose solve failed')
            projected, _ = cv2.projectPoints(world, r, t, k, d)
        delta = projected.reshape(-1,2) - measured.reshape(-1,2)
        errors.append(float(np.sqrt(np.mean(np.sum(delta**2, axis=1)))))
    return errors


def main():
    a = argparse.ArgumentParser()
    a.add_argument('images', type=Path)
    a.add_argument('--cols', type=int, default=9, help='inner corners, not squares')
    a.add_argument('--rows', type=int, default=6)
    a.add_argument('--square-mm', type=float, required=True)
    a.add_argument('--output', type=Path, default=Path('calibration-comparison.json'))
    args = a.parse_args()
    if min(args.cols,args.rows)<3 or args.square_mm<=0:
        a.error('positive square size and at least 3x3 inner corners required')
    obj = np.zeros((1,args.cols*args.rows,3), dtype=np.float64)
    obj[0,:,:2] = np.mgrid[0:args.cols,0:args.rows].T.reshape(-1,2)*args.square_mm
    names, points, rejected, size = [], [], [], None
    for p in sorted(args.images.iterdir()):
        if p.suffix.lower() not in ('.png','.jpg','.jpeg','.bmp'): continue
        frame = cv2.imdecode(np.fromfile(p,dtype=np.uint8),cv2.IMREAD_GRAYSCALE)
        if frame is None: raise ValueError(f'unreadable image: {p}')
        current_size = (frame.shape[1],frame.shape[0])
        if size and current_size != size: raise ValueError(f'mixed capture sizes: {p}')
        size = current_size
        ok, corners = cv2.findChessboardCornersSB(frame,(args.cols,args.rows))
        if not ok: rejected.append(str(p)); continue
        names.append(str(p)); points.append(corners.reshape(1,-1,2).astype(np.float64))
    if len(points)<15:
        raise ValueError(f'only {len(points)} usable views; capture >=15 distinct poses covering edges and centre')
    hold = [i for i in range(len(points)) if i%5==0]
    train = [i for i in range(len(points)) if i not in hold]
    result = {'schema':1, 'provenance':'real_chessboard_captures', 'image_size':size,
              'train_images':[names[i] for i in train], 'held_out_images':[names[i] for i in hold],
              'rejected_images':rejected, 'square_mm':args.square_mm, 'candidates':{}}
    for model in ('brown','fisheye'):
        try:
            rms,k,d,_,_ = fit([obj]*len(train),[points[i] for i in train],size,model)
            held = validate([obj]*len(hold),[points[i] for i in hold],k,d,model)
            result['candidates'][model] = {'model':model, 'image_size':size,
                'K':k.tolist(),'D':d.ravel().tolist(),'training_rms_px':float(rms),
                'held_out_rms_px':held, 'held_out_mean_px':float(np.mean(held))}
        except (cv2.error,ValueError) as e:
            result['candidates'][model] = {'error':str(e)}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps(result['candidates'],indent=2))
    if all('error' in c for c in result['candidates'].values()): raise SystemExit(1)


if __name__ == '__main__': main()
