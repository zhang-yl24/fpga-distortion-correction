"""Stage a bounded polynomial approximation for the existing FPGA mapper.

No LUT replaces coordinate arithmetic. This is explicitly a radial Brown
polynomial approximation to the calibrated two-coefficient fisheye model,
for this native image size and output_K=source_K, with no output rotation.
"""
from pathlib import Path
import argparse
import importlib.util
import json
import math
import cv2
import numpy as np

root=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('oracle',root/'tools/generate-brown-vectors.py')
oracle=importlib.util.module_from_spec(spec);spec.loader.exec_module(oracle)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('calibration',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--maximum-error-px',type=float,default=.25)
    args=parser.parse_args();data=json.loads(args.calibration.read_text());candidate=data['candidates']['fisheye2']
    assert candidate['matched_output_K_trial_eligible'],'same-K fisheye trial checks have not passed'
    k=np.array(candidate['K']);d=np.array(candidate['D']);w,h=candidate['image_size']
    yy,xx=np.indices((h,w),dtype=np.float64);x=(xx-k[0,2])/k[0,0];y=(yy-k[1,2])/k[1,1]
    r2=x*x+y*y;r=np.sqrt(r2);theta=np.arctan(r)
    theta_d=theta*(1+d[0]*theta**2+d[1]*theta**4)
    radial=np.divide(theta_d,r,out=np.ones_like(r),where=r!=0)
    weight=np.hypot(k[0,0]*x,k[1,1]*y)
    basis=np.stack((r2,r2*r2,r2*r2*r2),axis=-1)
    coefficients=np.linalg.lstsq((basis*weight[...,None]).reshape(-1,3),((radial-1)*weight).ravel(),rcond=None)[0]
    approx=1+np.sum(basis*coefficients,axis=-1)
    expected_x=k[0,0]*x*radial+k[0,2];expected_y=k[1,1]*y*radial+k[1,2]
    cvx,cvy=cv2.fisheye.initUndistortRectifyMap(k,d,np.eye(3),k,(w,h),cv2.CV_32FC1)
    assert np.max(np.hypot(expected_x-cvx,expected_y-cvy))<.0001,'analytic reference disagrees with OpenCV map'
    float_error=np.hypot(k[0,0]*x*(approx-radial),k[1,1]*y*(approx-radial))
    c=[oracle.quant(v,256) for v in (k[0,2],k[1,2],k[0,2],k[1,2],k[0,0],k[1,1])]
    c+=[oracle.quant(1/k[0,0],1<<30),oracle.quant(1/k[1,1],1<<30)]
    c+=[oracle.quant(v,1<<22) for v in (*coefficients,0,0)]
    coordinates=np.empty((h,w,2),dtype='<i4');invalid=0
    for v in range(h):
        for u in range(w):
            sx,sy,bad=oracle.project(u*256,v*256,c);coordinates[v,u]=(sx,sy);invalid+=bad
    error=np.hypot(coordinates[...,0]/256-expected_x,coordinates[...,1]/256-expected_y)
    assert invalid==0,'integer mapper exceeds its normalized or arithmetic domain'
    metrics={'floating_polynomial_max_coordinate_error_px':float(float_error.max()),
        'integer_mapper_max_coordinate_error_px':float(error.max()),
        'integer_mapper_rms_coordinate_error_px':float(np.sqrt(np.mean(error**2))),
        'integer_mapper_95th_percentile_coordinate_error_px':float(np.percentile(error,95)),
        'full_image_coordinates_checked':w*h,'arithmetic_invalid_coordinates':invalid}
    args.output.mkdir(parents=True,exist_ok=True)
    result={'source_calibration':str(args.calibration.resolve()),'image_size':[w,h],
        'calibrated_model':'fisheye2','K':k.tolist(),'D':d.tolist(),'output_K':k.tolist(),
        'hardware_coordinate_model':'three-term Brown radial polynomial surrogate, tangential terms zero',
        'radial_coefficients':coefficients.tolist(),'integer_config':c,'coordinate_error_metrics':metrics,
        'maximum_coordinate_error_gate_px':args.maximum_error_px,
        'passed':bool(error.max()<=args.maximum_error_px),'hardware_programmed':False,
        'calibration_cross_validation_mean_px':candidate['view_wise_cross_validation_mean_px'],
        'calibration_cross_validation_max_px':candidate['view_wise_cross_validation_max_px'],
        'matched_output_K_between_fold_map_sd_p95_px':candidate['matched_output_K_map_sd_95th_percentile_px'],
        'valid_normalized_radius_max':float(r.max()),'rotation_degrees':0,
        'limits':'Coordinate approximation error against the fitted model, not measured corrected-image accuracy. Bounded to this 640x480 field and matched output K; no exact fisheye or rotation FPGA path.'}
    (args.output/'candidate.json').write_text(json.dumps(result,indent=2)+'\n')
    if not result['passed']:raise SystemExit(f'Coordinate approximation failed quarter-pixel gate: {error.max():.6f}px')
    coordinates.tofile(args.output/'coordinates-q8.bin')
    names=('OUT_CX','OUT_CY','SRC_CX','SRC_CY','SRC_FX','SRC_FY','INV_FX','INV_FY','K1','K2','K3','P1','P2')
    declarations=['// Real fisheye2 calibration approximated over native 640x480; no rotation.']
    for name,value,bits in zip(names,c,[24]*6+[32]*7):
        declarations.append(f"localparam signed [{bits-1}:0] CAL_{name}={bits}'sh{value&((1<<bits)-1):0{bits//4}x};")
    (args.output/'calibration-candidate.vh').write_text('\n'.join(declarations)+'\n')
    print(json.dumps(metrics,indent=2))


if __name__=='__main__':main()
