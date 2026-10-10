"""Dense numerical audit against the fitted lens model; no optical claim."""
from pathlib import Path
import hashlib,importlib.util,json,math,sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
from model.rotation import cordic,phase_from_degrees,inverse_rotate
spec=importlib.util.spec_from_file_location('brown',root/'tools/generate-brown-vectors.py')
brown=importlib.util.module_from_spec(spec);spec.loader.exec_module(brown)
candidate_path=root/'results/calibration-fpga-candidate-20261006/candidate.json'
candidate=json.loads(candidate_path.read_text())
k=np.array(candidate['K']);d=np.array(candidate['D']);c=candidate['integer_config']
bound=json.loads((root/'results/rotation-domain-20261006.json').read_text())['guard_radius_squared_q22']
y,x=np.indices((480,640),dtype=np.int64);u=x*256;v=y*256
cx,cy=81792,61312;Q=1<<22
def rs(value,bits):return (value+(1<<(bits-1)))>>bits
def integer_map(angle):
    co,si=cordic(phase_from_degrees(angle))
    ru=rs(co*(u-cx)+si*(v-cy),30)+cx
    rv=rs(-si*(u-cx)+co*(v-cy),30)+cy
    nx=rs((ru-c[0])*c[6],16);ny=rs((rv-c[1])*c[7],16)
    r2=rs(nx*nx,22)+rs(ny*ny,22)
    valid=r2<=bound
    radial=Q+rs((c[8]+rs((c[9]+rs(c[10]*r2,22))*r2,22))*r2,22)
    sx=rs(rs(nx*radial,22)*c[4],22)+c[2]
    sy=rs(rs(ny*radial,22)*c[5],22)+c[3]
    return ru,rv,sx,sy,valid
rows=[];maps={};rng=np.random.default_rng(20261007)
for angle in range(0,360,30):
    ru,rv,sx,sy,valid=integer_map(angle)
    # Compare the vectorized audit with the existing scalar golden oracle.
    co,si=cordic(phase_from_degrees(angle))
    for index in rng.choice(307200,2048,replace=False):
        yy,xx=divmod(int(index),640)
        pu,pv,bad=inverse_rotate(xx*256,yy*256,cx,cy,co,si)
        assert not bad and (pu,pv)==(ru[yy,xx],rv[yy,xx])
        px,py,bad=brown.project(pu,pv,c)
        assert not bad and (px,py)==(sx[yy,xx],sy[yy,xx])
    if angle==0:
        sealed=np.fromfile(root/'results/calibration-fpga-candidate-20261006/coordinates-q8.bin',dtype='<i4').reshape(480,640,2)
        assert np.array_equal(sealed[...,0],sx) and np.array_equal(sealed[...,1],sy)
    # Exact floating rotation and fitted fisheye projection are independent
    # of fixed-point CORDIC/Brown approximation above.
    a=math.radians(angle)
    fu=(math.cos(a)*(x-cx/256)+math.sin(a)*(y-cy/256))+cx/256
    fv=(-math.sin(a)*(x-cx/256)+math.cos(a)*(y-cy/256))+cy/256
    nx=(fu-k[0,2])/k[0,0];ny=(fv-k[1,2])/k[1,1]
    radius=np.hypot(nx,ny);theta=np.arctan(radius)
    td=theta*(1+d[0]*theta**2+d[1]*theta**4)
    scale=np.divide(td,radius,out=np.ones_like(radius),where=radius!=0)
    ex=k[0,0]*nx*scale+k[0,2];ey=k[1,1]*ny*scale+k[1,2]
    error=np.hypot(sx/256-ex,sy/256-ey)
    inside=(sx>=0)&(sy>=0)&(sx<639*256)&(sy<479*256)&valid
    values=error[valid]
    row={'angle_deg':angle,'pixels_examined':307200,'inside_calibrated_radius_pixels':int(valid.sum()),
         'outside_calibrated_radius_black_pixels':int((~valid).sum()),
         'four_bilinear_neighbors_in_bounds_pixels':int(inside.sum()),
         'max_coordinate_error_px':float(values.max()),'rms_coordinate_error_px':float(np.sqrt(np.mean(values**2))),
         'p95_coordinate_error_px':float(np.percentile(values,95))}
    assert row['max_coordinate_error_px']<=.25,row
    rows.append(row);maps[angle]=np.where(valid,error,np.nan)
    print(f"angle={angle:3d} max={row['max_coordinate_error_px']:.6f}px rms={row['rms_coordinate_error_px']:.6f}px valid={row['inside_calibrated_radius_pixels']}",flush=True)
out=root/'results/lab-20261007'
result={'passed':True,'hardware_accessed':False,'dense_output_pixels_examined':12*307200,
        'scalar_oracle_spotchecks':12*2048,'zero_map_matches_sealed_candidate':True,
        'quarter_pixel_numerical_gate':.25,'frames':rows,
        'source_sha256':{str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in
                         (candidate_path,root/'model/rotation.py',root/'tools/generate-brown-vectors.py',root/'results/rotation-domain-20261006.json')},
        'limits':'Dense software coordinate audit against the fitted fisheye2 model at 640x480, including fixed-point rotation and Brown surrogate. Only rays inside the established radial bound count toward numerical error. Masking and source-edge black pixels are reported separately. This is neither a new optical measurement nor 12-angle full-frame RTL coverage; existing native RTL coverage remains six angles. No new calibration or high-resolution proof.'}
(out/'rotated-coordinate-error.json').write_text(json.dumps(result,indent=2)+'\n')
plt.rcParams.update({'font.family':'Microsoft YaHei','text.color':'black','axes.labelcolor':'black','xtick.color':'black','ytick.color':'black'})
fig,axes=plt.subplots(1,3,figsize=(13.8,4.4),layout='constrained')
for ax,angle in zip(axes,(0,30,90)):
    im=ax.imshow(maps[angle],vmin=0,vmax=.16,cmap='viridis')
    ax.set_title(f'{angle}°：相对拟合镜头模型的坐标误差');ax.set_xlabel('输出像素 x');ax.set_ylabel('输出像素 y')
fig.colorbar(im,ax=axes,label='坐标误差（像素）',shrink=.8)
fig.suptitle('640×480 数值误差核查：覆盖12个30°步进角度',fontsize=16)
fig.supxlabel('白色区域为径向有效域之外；本图不代表实拍光学矫正精度或高分辨率验证。',fontsize=10)
fig.savefig(out/'rotated-coordinate-error.png',dpi=150);plt.close(fig)
print('PASS: twelve dense model audits, scalar cross-checks and sealed zero-degree coordinates; no hardware accessed.')
