"""Minimax polynomial inside the existing lens domain; no board parameter edits."""
from pathlib import Path
import hashlib
import importlib.util
import json
import math
import sys
import numpy as np
from scipy.optimize import linprog
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
from model.rotation import cordic,phase_from_degrees,inverse_rotate
spec=importlib.util.spec_from_file_location('brown_reference',root/'tools/generate-brown-vectors.py')
brown=importlib.util.module_from_spec(spec);spec.loader.exec_module(brown)
old_path=root/'results/calibration-fpga-candidate-20261006/candidate.json'
old=json.loads(old_path.read_text());k=np.array(old['K']);d=np.array(old['D'])
bound_path=root/'results/rotation-domain-20261006.json'
bound=json.loads(bound_path.read_text())['guard_radius_squared_q22'];Q=1<<22
radius2=np.linspace(0,bound/Q,4097);radius=np.sqrt(radius2);theta=np.arctan(radius)
scale=np.divide(theta*(1+d[0]*theta**2+d[1]*theta**4),radius,out=np.ones_like(radius),where=radius!=0)
weight=max(k[0,0],k[1,1])*radius
matrix=weight[:,None]*np.stack((radius2,radius2**2,radius2**3),axis=1)
target=weight*(scale-1)
constraints=np.vstack((np.column_stack((matrix,-np.ones(len(radius2)))),
                        np.column_stack((-matrix,-np.ones(len(radius2))))))
solution=linprog([0,0,0,1],A_ub=constraints,b_ub=np.concatenate((target,-target)),
    bounds=[(None,None)]*3+[(0,None)],method='highs')
assert solution.success,solution.message
config=list(old['integer_config']);config[8:11]=[int(round(a*Q)) for a in solution.x[:3]]
y,x=np.indices((480,640),dtype=np.int64);u=x*256;v=y*256;cx,cy=81792,61312
def rs(a,b):return (a+(1<<(b-1)))>>b
def project(ru,rv,c):
    nx=rs((ru-c[0])*c[6],16);ny=rs((rv-c[1])*c[7],16)
    r2=rs(nx*nx,22)+rs(ny*ny,22)
    radial=Q+rs((c[8]+rs((c[9]+rs(c[10]*r2,22))*r2,22))*r2,22)
    sx=rs(rs(nx*radial,22)*c[4],22)+c[2];sy=rs(rs(ny*radial,22)*c[5],22)+c[3]
    return sx,sy,r2<=bound
rows=[];rng=np.random.default_rng(2026100701)
previous=json.loads((root/'results/lab-20261007/rotated-coordinate-error.json').read_text())
for angle in range(0,360,30):
    co,si=cordic(phase_from_degrees(angle))
    ru=rs(co*(u-cx)+si*(v-cy),30)+cx;rv=rs(-si*(u-cx)+co*(v-cy),30)+cy
    oldx,oldy,valid=project(ru,rv,old['integer_config']);newx,newy,newvalid=project(ru,rv,config)
    assert np.array_equal(valid,newvalid),'Domain changed'
    for index in rng.choice(307200,1024,replace=False):
        yy,xx=divmod(int(index),640);pu,pv,bad=inverse_rotate(xx*256,yy*256,cx,cy,co,si)
        px,py,bad2=brown.project(pu,pv,config)
        assert not bad and not bad2 and (px,py)==(newx[yy,xx],newy[yy,xx])
    a=math.radians(angle)
    fu=math.cos(a)*(x-cx/256)+math.sin(a)*(y-cy/256)+cx/256
    fv=-math.sin(a)*(x-cx/256)+math.cos(a)*(y-cy/256)+cy/256
    nx=(fu-k[0,2])/k[0,0];ny=(fv-k[1,2])/k[1,1]
    rr=np.hypot(nx,ny);tt=np.arctan(rr)
    ss=np.divide(tt*(1+d[0]*tt**2+d[1]*tt**4),rr,out=np.ones_like(rr),where=rr!=0)
    ex=k[0,0]*nx*ss+k[0,2];ey=k[1,1]*ny*ss+k[1,2]
    old_error=np.hypot(oldx/256-ex,oldy/256-ey)[valid]
    error=np.hypot(newx/256-ex,newy/256-ey)[valid]
    assert abs(float(old_error.max())-previous['frames'][angle//30]['max_coordinate_error_px'])<1e-12
    rows.append({'angle_deg':angle,'pixels_examined':307200,'valid_domain_pixels':int(valid.sum()),
        'old_max_coordinate_error_px':float(old_error.max()),'candidate_max_coordinate_error_px':float(error.max()),
        'candidate_rms_coordinate_error_px':float(np.sqrt(np.mean(error**2))),
        'candidate_p95_coordinate_error_px':float(np.percentile(error,95))})
    print(json.dumps(rows[-1]),flush=True)
result={'passed_dense_audit':True,'hardware_accessed':False,'board_parameters_changed':False,
    'dense_pixels_examined':3686400,'scalar_oracle_spotchecks':12288,
    'guard_radius_squared_q22':bound,'previous_integer_config':old['integer_config'],
    'candidate_integer_config':config,'candidate_polynomial_coefficients':solution.x[:3].tolist(),
    'sampled_minimax_objective_px':float(solution.x[3]),'fit_radius_squared_samples':len(radius2),
    'frames':rows,'max_coordinate_error_px':max(r['candidate_max_coordinate_error_px'] for r in rows),
    'source_sha256':{str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in
        (old_path,bound_path,root/'model/rotation.py',root/'tools/generate-brown-vectors.py',Path(__file__))},
    'limits':'Isolated coefficient candidate for the existing fitted fisheye2 lens, K, radial guard and third-order Brown datapath. Linear programming minimizes sampled continuous radial coordinate error; dense tests include current fixed-point rotation/quantization. It does not prove a continuous-domain supremum, optical accuracy, new RTL outputs, timing or physical image improvement. No calibration data, active include, board sources or archived golden outputs were changed. Separate candidate vectors/RTL and held-out physical poses are required before adoption.'}
(root/'results/lab-20261007/brown-bounded-minimax-candidate.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({'max_coordinate_error_px':result['max_coordinate_error_px'],'active_parameters_changed':False}))
