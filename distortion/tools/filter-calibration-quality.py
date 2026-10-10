"""Copy quality-approved poses, retaining rejection evidence and raw images."""
from pathlib import Path
import argparse
import json
import shutil
import cv2
import numpy as np


def main():
    parser=argparse.ArgumentParser();parser.add_argument('selection',type=Path)
    parser.add_argument('quality',type=Path);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();original=json.loads(args.selection.read_text());quality=json.loads(args.quality.read_text())
    observations={item['image']:item for item in quality['images']}
    assert set(original['selected'])==set(observations),'quality report must cover exactly this pose set'
    approved=[name for name in original['selected'] if not observations[name]['quality_rejected']]
    args.output.mkdir(parents=True,exist_ok=True)
    assert not (set(p.name for p in args.output.glob('*.png'))-set(Path(n).name for n in approved)), 'output contains stale, unselected PNGs'
    points=[];selected=[];rejected=list(original['rejected'])
    for name in original['selected']:
        if observations[name]['quality_rejected']:
            rejected.append(observations[name]);continue
        path=Path(name);destination=args.output/path.name
        if destination.exists():assert destination.read_bytes()==path.read_bytes()
        else:shutil.copy2(path,destination)
        gray=cv2.imdecode(np.fromfile(path,dtype=np.uint8),cv2.IMREAD_GRAYSCALE)
        ok,corners=cv2.findChessboardCornersSB(gray,(9,6));assert ok
        points.append(corners.reshape(-1,2));selected.append(str(destination.resolve()))
    union=np.concatenate(points)
    result=dict(original,selected=selected,selected_count=len(selected),rejected=rejected,
        corner_bounds_pixels=[union.min(axis=0).tolist(),union.max(axis=0).tolist()],
        parent_selection=str(args.selection.resolve()),quality_report=str(args.quality.resolve()),
        limits='Pose and independent edge-sharpness selection; no image removed using a calibration residual.')
    (args.output/'selection.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'approved_views':len(selected),'quality_rejected':len(original['selected'])-len(selected)}))
    if len(selected)<15:raise SystemExit('Need >=15 quality-approved poses')


if __name__=='__main__':main()
