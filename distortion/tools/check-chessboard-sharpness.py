"""Measure black/white edge transitions, independently of calibration error.

Use inner grid segments, not whole-image Laplacian energy (sensor noise and
the laboratory background would contaminate that score). Preserve every raw
capture. Rejection requires BOTH a wide transition and a large cell fraction.
"""
from pathlib import Path
import argparse
import json
import cv2
import numpy as np

cv2.setNumThreads(1)


def crossing(x,values,level):
    indices=np.where((values[:-1]<level)&(values[1:]>=level))[0]
    if not len(indices):return None
    roots=[float(x[i]+(level-values[i])*(x[i+1]-x[i])/(values[i+1]-values[i])) for i in indices]
    return min(roots,key=abs)


def sharpness(gray,corners):
    grid=corners.reshape(6,9,2);widths=[];fractions=[]
    for axis in (0,1):
        for row in range(6-int(axis==0)):
            for col in range(9-int(axis==1)):
                point=grid[row,col];other=grid[row+int(axis==0),col+int(axis==1)]
                tangent=other-point;length=float(np.linalg.norm(tangent));tangent/=length
                perpendicular=np.array([-tangent[1],tangent[0]])
                adjacent=grid[row,min(8,col+1)] if axis==0 and col<8 else (
                    grid[row,max(0,col-1)] if axis==0 else grid[min(5,row+1),col] if row<5 else grid[row-1,col])
                cell=float(np.linalg.norm(adjacent-point))
                x=np.linspace(-.35*cell,.35*cell,max(31,int(cell*2.8)+1)).astype(np.float32)
                locations=(point+other)/2+x[:,None]*perpendicular
                profiles=[]
                for shift in np.linspace(-.1,.1,5):
                    q=locations+shift*length*tangent
                    profiles.append(cv2.remap(gray,q[:,0].astype(np.float32).reshape(1,-1),
                        q[:,1].astype(np.float32).reshape(1,-1),cv2.INTER_LINEAR).ravel())
                profile=np.mean(profiles,axis=0)
                n=max(3,len(profile)//6);left=float(np.median(profile[:n]));right=float(np.median(profile[-n:]))
                if abs(right-left)<25:continue
                normalized=(profile-left)/(right-left)
                # Three-sample smoothing suppresses noise, applied identically
                # to every capture; distances remain in original sensor pixels.
                normalized=np.convolve(np.pad(normalized,(1,1),mode='edge'),np.ones(3)/3,mode='valid')
                lo,hi=crossing(x,normalized,.2),crossing(x,normalized,.8)
                if lo is not None and hi is not None and hi>=lo:
                    widths.append(hi-lo);fractions.append((hi-lo)/cell)
    if len(widths)<30:return {'measured_edges':len(widths),'quality_rejected':True,'reason':'too few high-contrast measured grid segments'}
    width=float(np.median(widths));fraction=float(np.median(fractions))
    rejected=width>3.0 and fraction>.10
    return {'measured_edges':len(widths),'median_20_80_edge_width_px':width,
        'median_transition_to_cell_fraction':fraction,'quality_rejected':rejected,
        'reason':'wide black/white transitions, consistent with blur' if rejected else 'edge-transition gate passed'}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('selection',type=Path);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();selection=json.loads(args.selection.read_text());results=[]
    for name in selection['selected']:
        gray=cv2.imdecode(np.fromfile(name,dtype=np.uint8),cv2.IMREAD_GRAYSCALE)
        ok,corners=cv2.findChessboardCornersSB(gray,(9,6));assert ok
        results.append({'image':name,**sharpness(gray.astype(np.float32),corners)})
    report={'thresholds':{'median_20_80_edge_width_px':3.0,'median_transition_to_cell_fraction':.10,
        'both_width_thresholds_required_for_blur_rejection':True,'minimum_measured_edges':30},
        'limits':'Image-quality criterion independent of model residuals; does not detect board nonplanarity, all rolling-shutter distortion, or lens errors.',
        'images':results}
    args.output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'rejected':[r for r in results if r['quality_rejected']],
        'widest_five':sorted(results,key=lambda r:r.get('median_20_80_edge_width_px',999),reverse=True)[:5]},indent=2))


if __name__=='__main__':main()
