"""View-wise cross-validation and full-image map sensitivity for real captures.

The thresholds are engineering checks for a first hardware comparison, not
competition quality criteria. All-view parameters are saved as candidates.
"""
from pathlib import Path
import argparse
import json
import cv2
import numpy as np
from calibrate import fit, validate

cv2.setNumThreads(1)


def maps(k, d, output_k, size, model):
    if model.startswith('fisheye'):
        return cv2.fisheye.initUndistortRectifyMap(k, d, np.eye(3), output_k, size, cv2.CV_32FC1)
    return cv2.initUndistortRectifyMap(k, d, None, output_k, size, cv2.CV_32FC1)


def fit_model(obj,img,size,model):
    if model=='brown4':
        return cv2.calibrateCamera([p.reshape(-1,3).astype(np.float32) for p in obj],
            [p.reshape(-1,1,2).astype(np.float32) for p in img],size,None,None,flags=cv2.CALIB_FIX_K3)
    if model=='fisheye2':
        flags=(cv2.fisheye.CALIB_RECOMPUTE_EXTRINSIC | cv2.fisheye.CALIB_FIX_SKEW |
               cv2.fisheye.CALIB_CHECK_COND | cv2.fisheye.CALIB_FIX_K3 | cv2.fisheye.CALIB_FIX_K4)
        return cv2.fisheye.calibrate(obj,img,size,np.eye(3),np.zeros((4,1)),flags=flags)
    return fit(obj,img,size,model)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('selection',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--reduced-models',action='store_true',help='also compare Brown k3=0 and fisheye k3=k4=0')
    args=parser.parse_args()
    selected=json.loads(args.selection.read_text(encoding='utf-8'))
    names=selected['selected'];size=tuple(selected['image_size']);points=[]
    coverage=np.zeros((3,3),dtype=int)
    for name in names:
        gray=cv2.imdecode(np.fromfile(name,dtype=np.uint8),cv2.IMREAD_GRAYSCALE)
        assert gray is not None and (gray.shape[1],gray.shape[0])==size
        ok,corners=cv2.findChessboardCornersSB(gray,(9,6));assert ok
        xy=corners.reshape(-1,2)
        for x,y in xy:coverage[min(2,int(y*3/size[1])),min(2,int(x*3/size[0]))]+=1
        points.append(xy.reshape(1,-1,2).astype(np.float64))
    assert len(points)>=15
    obj=np.zeros((1,54,3),dtype=np.float64)
    obj[0,:,:2]=np.mgrid[0:9,0:6].T.reshape(-1,2)*20
    report={'provenance':'real OV5640 native captures','images':names,'image_size':size,
        'square_mm':20,'folds':5,'corner_counts_by_3x3_region':coverage.tolist(),
        'criteria':{'all_regions_minimum_detected_corners':15,'held_out_mean_max_px':0.5,
            'held_out_per_view_max_px':1.0,'full_map_folded_pixels_max':0,
            'between_fold_map_sd_95th_percentile_max_px':0.5},
        'criteria_note':'Engineering gates for initial hardware comparison; not contest standards or measured corrected-image quality.',
        'candidates':{}}
    for model in (('brown','fisheye','brown4','fisheye2') if args.reduced_models else ('brown','fisheye')):
        try:
            rms,k,d,_,_=fit_model([obj]*len(points),points,size,model)
            mx,my=maps(k,d,k,size,model)
            du_dy,du_dx=np.gradient(mx.astype(np.float64));dv_dy,dv_dx=np.gradient(my.astype(np.float64))
            det=du_dx*dv_dy-du_dy*dv_dx
            finite=bool(np.isfinite(mx).all() and np.isfinite(my).all() and np.isfinite(det).all())
            fold_maps=[];all_errors=[];folds=[]
            for n in range(5):
                hold=[i for i in range(len(points)) if i%5==n]
                train=[i for i in range(len(points)) if i not in hold]
                frms,fk,fd,_,_=fit_model([obj]*len(train),[points[i] for i in train],size,model)
                errors=validate([obj]*len(hold),[points[i] for i in hold],fk,fd,'fisheye' if model.startswith('fisheye') else 'brown')
                fx,fy=maps(fk,fd,k,size,model)
                fold_maps.append(np.stack((fx,fy),axis=-1));all_errors.extend(errors)
                folds.append({'fold':n,'training_views':len(train),'held_out_images':[names[i] for i in hold],
                    'held_out_rms_px':errors,'training_rms_px':float(frms),'K':fk.tolist(),'D':fd.ravel().tolist()})
            # Same output camera for every fold, so a focal/principal point
            # change does not silently change the output rays being compared.
            spread=np.sqrt(np.sum(np.std(np.stack(fold_maps),axis=0,ddof=1)**2,axis=-1))
            p95=float(np.percentile(spread,95));folded=int((det<=0).sum())
            eligible=bool((coverage>=15).all() and finite and folded==0 and
                          np.mean(all_errors)<=.5 and max(all_errors)<=1 and p95<=.5)
            report['candidates'][model]={'model':model,'image_size':size,'K':k.tolist(),'D':d.ravel().tolist(),
                'parameter_constraints':{'brown4':'k3 fixed at 0','fisheye2':'k3 and k4 fixed at 0'}.get(model,'standard unconstrained distortion coefficients'),
                'output_K':k.tolist(),'full_data_training_rms_px':float(rms),
                'view_wise_cross_validation_mean_px':float(np.mean(all_errors)),
                'view_wise_cross_validation_max_px':max(all_errors),'folded_pixels':folded,
                'finite_map':finite,'map_sd_95th_percentile_px':p95,'map_sd_max_px':float(spread.max()),
                'eligible_for_first_hardware_comparison':eligible,'cross_validation':folds,
                'limits':'Map spread measures sensitivity to this view split; it is not a calibrated confidence interval or independent edge accuracy measurement.'}
        except (cv2.error,ValueError) as error:
            report['candidates'][model]={'error':str(error),'eligible_for_first_hardware_comparison':False}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'selected_views':len(points),'coverage':coverage.tolist(),
        'models':{name:{key:value for key,value in candidate.items() if key in (
            'error','view_wise_cross_validation_mean_px','view_wise_cross_validation_max_px',
            'folded_pixels','map_sd_95th_percentile_px','map_sd_max_px','eligible_for_first_hardware_comparison')}
            for name,candidate in report['candidates'].items()}},indent=2))


if __name__=='__main__':main()
