"""Reject unreadable/cornerless or near-identical views before model fitting."""
from pathlib import Path
import argparse
import json
import shutil
import cv2
import numpy as np

def main():
    a=argparse.ArgumentParser();a.add_argument('images',type=Path);a.add_argument('--output',type=Path,required=True)
    a.add_argument('--minimum-motion-px',type=float,default=8);args=a.parse_args()
    assert args.minimum_motion_px>0 and args.images.resolve()!=args.output.resolve()
    args.output.mkdir(parents=True,exist_ok=True)
    accepted=[];points=[];rejected=[];size=None
    for path in sorted(args.images.glob('*.png')):
        frame=cv2.imdecode(np.fromfile(path,dtype=np.uint8),cv2.IMREAD_GRAYSCALE)
        if frame is None:rejected.append({'image':str(path),'reason':'unreadable'});continue
        current=(frame.shape[1],frame.shape[0])
        if current!=(640,480):raise ValueError(f'Unexpected sensor mode: {path} {current}')
        size=current
        ok,corners=cv2.findChessboardCornersSB(frame,(9,6))
        if not ok:rejected.append({'image':str(path),'reason':'54 corners not detected'});continue
        xy=corners.reshape(-1,2)
        distances=[min(float(np.sqrt(np.mean(np.sum((xy-old)**2,axis=1)))),
                       float(np.sqrt(np.mean(np.sum((xy[::-1]-old)**2,axis=1))))) for old in points]
        if distances and min(distances)<args.minimum_motion_px:
            rejected.append({'image':str(path),'reason':'near-duplicate corner pose','nearest_rms_motion_px':min(distances)});continue
        destination=args.output/path.name
        if destination.exists() and destination.read_bytes()!=path.read_bytes():raise FileExistsError(destination)
        shutil.copy2(path,destination);points.append(xy);accepted.append(str(destination.resolve()))
    union=np.concatenate(points) if points else np.empty((0,2))
    report={'source':str(args.images.resolve()),'selected':accepted,'rejected':rejected,'selected_count':len(accepted),
        'image_size':size,'inner_corners':[9,6],'minimum_corner_rms_motion_px':args.minimum_motion_px,
        'corner_bounds_pixels':[union.min(axis=0).tolist(),union.max(axis=0).tolist()] if len(union) else None,
        'limits':'Corner-motion heuristic removes repeated poses, not a proof of full geometric coverage or calibration accuracy.'}
    (args.output/'selection.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'selected_count':len(accepted),'rejected_count':len(rejected),'corner_bounds_pixels':report['corner_bounds_pixels']},indent=2))
    if len(accepted)<15:raise SystemExit('Need at least 15 distinct complete checkerboard poses before fitting')

if __name__=='__main__':main()
