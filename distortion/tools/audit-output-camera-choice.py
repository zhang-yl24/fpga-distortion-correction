"""Separate fixed-view ray uncertainty from a same-K distortion-only remap.

The existing fixed-output-K test remains unchanged. This alternative is valid
only when output intrinsics are explicitly matched to the source calibration;
it cannot approve rotations or an independently specified virtual camera.
"""
from pathlib import Path
import argparse
import json
import numpy as np
import cv2


def maps(k,d,size,model):
    if model.startswith('fisheye'):
        return cv2.fisheye.initUndistortRectifyMap(k,d,np.eye(3),k,size,cv2.CV_32FC1)
    return cv2.initUndistortRectifyMap(k,d,None,k,size,cv2.CV_32FC1)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('stability',type=Path)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    report=json.loads(args.stability.read_text());size=tuple(report['image_size'])
    for name,candidate in report['candidates'].items():
        if 'error' in candidate:continue
        choices=[]
        for fold in candidate['cross_validation']:
            k=np.array(fold['K']);d=np.array(fold['D'])
            x,y=maps(k,d,size,name);choices.append(np.stack((x,y),axis=-1))
        sd=np.sqrt(np.sum(np.std(np.stack(choices),axis=0,ddof=1)**2,axis=-1))
        k=np.array(candidate['K']);d=np.array(candidate['D']);mx,my=maps(k,d,size,name)
        candidate['matched_output_K_map_sd_95th_percentile_px']=float(np.percentile(sd,95))
        candidate['matched_output_K_map_sd_max_px']=float(sd.max())
        candidate['matched_output_K_trial_eligible']=bool(
            (np.array(report['corner_counts_by_3x3_region'])>=15).all() and
            candidate['finite_map'] and candidate['folded_pixels']==0 and
            candidate['view_wise_cross_validation_mean_px']<=.5 and
            candidate['view_wise_cross_validation_max_px']<=1 and np.percentile(sd,95)<=.5)
        candidate['matched_output_K_bilinear_in_bounds_fraction']=float(((mx>=0)&(my>=0)&(mx<size[0]-1)&(my<size[1]-1)).mean())
    report['source_stability']=str(args.stability.resolve())
    report['output_camera_choice_note']='Added test uses output_K=source_K for each independently fitted model, as a distortion-only field-of-view-preserving trial. Original fixed-output-K sensitivity and eligibility remain unchanged. Rotation/independent virtual view is not approved.'
    args.output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({name:{key:value for key,value in candidate.items() if key.startswith('matched_output_K')}
                      for name,candidate in report['candidates'].items()},indent=2))


if __name__=='__main__':main()
