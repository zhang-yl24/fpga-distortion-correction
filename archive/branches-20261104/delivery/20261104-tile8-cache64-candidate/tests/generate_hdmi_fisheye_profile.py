"""Generate the new HDMI C fisheye's bounded radial ROM and exact CPU oracle.

Output-to-source mapping uses the C preview's balance=.5 rectilinear projection.
No fitting, old Brown surrogate, image capture or hardware action is performed.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re

import cv2
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
SELF=Path(__file__).resolve()
CALIBRATION=ROOT/'work/hdmi-camera-snapshot-20261102-a/new-lens-fisheye-1080-c.json'
PROFILE_HEADER='board/hdmi-camera-fisheye-profile.vh'
TABLE_HEADER='board/hdmi-camera-fisheye-radial-table.vh'
SCHEMA='hdmi-camera-fisheye-r2-profile-v1'
NODES=1025
R2_MAX=8
NATIVE_WIDTH=1920
NATIVE_HEIGHT=1080


def require(value,message):
    if not value:raise ValueError(message)


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def ref(path):return {'Path':str(Path(path).resolve()),'SHA256':sha(path)}
def quant(value,scale):return np.floor(np.asarray(value,dtype=np.float64)*scale+.5).astype(np.int64)
def round_shift(value,bits):return (value+(1<<(bits-1)))>>bits


def read_calibration(path=CALIBRATION):
    path=Path(path).resolve();c=json.loads(path.read_text(encoding='utf-8-sig'))
    require(c.get('schema')=='hdmi-new-lens-fisheye-calibration-v1'and c.get('model')=='opencv_fisheye'and
        c.get('native_size')==[1920,1080],'new native HDMI fisheye calibration required')
    k=np.asarray(c['K_native'],np.float64);d=np.asarray(c['D_normalized'],np.float64)
    snapshot=np.asarray(c['preview']['new_K_snapshot'],np.float64)
    require(k.shape==snapshot.shape==(3,3)and d.shape==(4,)and np.isfinite(k).all()and
        np.isfinite(snapshot).all()and np.isfinite(d).all()and np.allclose(k[2],[0,0,1])and
        c['preview']['balance']==.5,'finite C balance=.5 conventional profile required')
    require(k[0,1]==k[1,0]==snapshot[0,1]==snapshot[1,0]==0 and min(k[0,0],k[1,1],snapshot[0,0],snapshot[1,1])>0,
        'positive zero-skew intrinsics required')
    fit=c['source_fit'];require(sha(fit['path'])==fit['sha256'],'source calibration fit changed')
    a=np.array([[2.,0.,.5],[0.,2.,.5],[0.,0.,1.]])
    return c,k,d,a@snapshot


def radial_scale(r2,d):
    r2=np.asarray(r2,np.float64);require(np.isfinite(r2).all()and np.all(r2>=0),'finite nonnegative radius squared required')
    r=np.sqrt(r2);t=np.arctan(r);z=t*t
    td=t*(1+z*(d[0]+z*(d[1]+z*(d[2]+z*d[3]))))
    return np.divide(td,r,out=np.ones_like(r),where=r!=0)


def config(calibration=CALIBRATION,width=1920,height=1080):
    require(type(width)is int and type(height)is int and 1<=width<=8192 and 1<=height<=8192,'positive bounded mapper geometry required')
    _,k,d,ko=read_calibration(calibration)
    names=('OUT_CX','OUT_CY','SRC_CX','SRC_CY','SRC_FX','SRC_FY')
    values=(ko[0,2],ko[1,2],k[0,2],k[1,2],k[0,0],k[1,1])
    native={name:int(quant(v,256))for name,v in zip(names,values)}
    native.update(INV_FX=int(quant(1/ko[0,0],1<<30)),INV_FY=int(quant(1/ko[1,1],1<<30)))
    # Match the RTL's parameter-only rescaling of the frozen native integers.
    # Pixel-centre resize maps native(x+.5)*scale-.5; never refit K or D.
    def scale_integer(value,numerator,denominator):return (value*numerator+denominator//2)//denominator
    out=dict(native)
    for axis,size,denom in [('X',width,1920),('Y',height,1080)]:
        for prefix in ('OUT_C','SRC_C'):
            name=prefix+axis;out[name]=scale_integer(native[name]+128,size,denom)-128
        name='SRC_F'+axis;out[name]=scale_integer(native[name],size,denom)
        name='INV_F'+axis;out[name]=scale_integer(native[name],denom,size)
    t=np.linspace(0,8,1025);lut=quant(radial_scale(t,d),1<<30)
    require(np.all((lut>0)&(lut<=1<<30))and np.all(np.diff(lut)<=0),'bounded monotone Q30 radial scale required')
    require(all(-(1<<31)<=v<(1<<31)for v in out.values()),'geometry-scaled fixed constants exceed signed32')
    return {'Constants':out,'NativeConstants':native,'LUTQ30':lut,'Width':width,'Height':height,
        'SourceK':k,'OutputK':ko,'D':d}


def fixed_map(u_q8,v_q8,corrected=True,config=None,width=1920,height=1080,in_black=False):
    """Vectorized RTL oracle; coordinates remain signed Q15.8 through stalls.

    Only r2/overflow/input-black is masked here. Source image footprint masking
    and DDR sampling retain the existing core/cache contracts independently.
    """
    cfg=config if config is not None else globals()['config'](width=width,height=height)
    u,v=np.broadcast_arrays(np.asarray(u_q8,np.int64),np.asarray(v_q8,np.int64))
    black=np.broadcast_to(np.asarray(in_black,bool),u.shape).copy()
    require(np.all((u>=-(1<<23))&(u<(1<<23)))and np.all((v>=-(1<<23))&(v<(1<<23))), 'signed24 Q8 input required')
    if corrected:
        c=cfg['Constants'];nx=round_shift((u-c['OUT_CX'])*c['INV_FX'],16);ny=round_shift((v-c['OUT_CY'])*c['INV_FY'],16)
        fits=lambda x:(x>=-(1<<31))&(x<(1<<31))
        black|=~fits(nx)|~fits(ny)
        # All valid profile coordinates are below signed32 product overflow.
        # Clamp invalid arithmetic before the square so Python int64 never wraps.
        safe_nx=np.where(fits(nx),nx,0);safe_ny=np.where(fits(ny),ny,0)
        xx=round_shift(safe_nx*safe_nx,22);yy=round_shift(safe_ny*safe_ny,22);z=xx+yy
        black|=~fits(xx)|~fits(yy)|~fits(z)|(z<0)|(z>(8<<22))
        z=np.clip(z,0,8<<22);index=np.minimum(z>>15,1023);fraction=z-(index<<15)
        lut=cfg['LUTQ30'];scale=lut[index]+round_shift((lut[index+1]-lut[index])*fraction,15)
        xd=round_shift(safe_nx*scale,30);yd=round_shift(safe_ny*scale,30)
        black|=~fits(xd)|~fits(yd)
        sx=round_shift(xd*c['SRC_FX'],22)+c['SRC_CX'];sy=round_shift(yd*c['SRC_FY'],22)+c['SRC_CY']
        black|=(sx<-(1<<23))|(sx>=(1<<23))|(sy<-(1<<23))|(sy>=(1<<23))
    else:sx=u;sy=v
    return np.where(black,-(1<<23),sx).astype(np.int64),np.where(black,-(1<<23),sy).astype(np.int64),black


def header_bytes(cfg):
    lines=['// Generated from the source-bound new HDMI C calibration; no Brown surrogate.',
        '// Native1920x1080, C preview balance=.5, output centre transform 2*c+.5.',
        '// Pixel/focal Q8, inverse focal Q30; round nearest, ties toward +infinity.']
    for key,value in cfg['NativeConstants'].items():lines.append(f"localparam signed [31:0] FISHEYE_{key}=32'sh{value&0xffffffff:08x};")
    lines+=['localparam integer FISHEYE_R2_MAX_Q22=33554432;',
        'localparam integer FISHEYE_RADIAL_SEGMENTS=1024;']
    return ('\n'.join(lines)+'\n').encode('ascii')


def table_bytes(cfg):
    lut=cfg['LUTQ30'];lines=['// 1025 Q30 nodes on uniform r2[0,8] packed as1024 adjacent segments.',
        '// ROM word[31:0]=baseQ30; word[63:32]=signed(next-base)Q30.',
        'function [63:0] fisheye_radial_pair(input [9:0] address);',
        '    begin', '        case(address)']
    for i in range(1024):
        word=((int(lut[i+1]-lut[i])&0xffffffff)<<32)|int(lut[i])
        lines.append(f"            10'd{i}: fisheye_radial_pair=64'h{word:016x};")
    lines+=['        endcase','    end','endfunction']
    return ('\n'.join(lines)+'\n').encode('ascii')


def metrics(calibration=CALIBRATION):
    cfg=config(calibration);k,d,ko=cfg['SourceK'],cfg['D'],cfg['OutputK']
    yy,xx=np.indices((1080,1920),dtype=np.int64);x=(xx-ko[0,2])/ko[0,0];y=(yy-ko[1,2])/ko[1,1]
    scale=radial_scale(x*x+y*y,d);sx=k[0,0]*x*scale+k[0,2];sy=k[1,1]*y*scale+k[1,2]
    cvx,cvy=cv2.fisheye.initUndistortRectifyMap(k,d,np.eye(3),ko,(1920,1080),cv2.CV_32FC1)
    analytic=np.hypot(sx-cvx,sy-cvy)
    qx,qy,black=fixed_map(xx*256,yy*256,config=cfg);error=np.hypot(qx/256-sx,qy/256-sy)
    cverror=np.hypot(qx/256-cvx,qy/256-cvy)
    require(not black.any()and error.max()<=.125 and analytic.max()<.0001,'complete native coordinate error gate failed')
    return {'NativeCoordinatesChecked':1920*1080,'ArithmeticMaskedCoordinates':int(black.sum()),
        'AnalyticVsOpenCVMaxNativePixels':float(analytic.max()),
        'FixedVsAnalyticMaxNativePixels':float(error.max()),'FixedVsAnalyticRMSNativePixels':float(np.sqrt(np.mean(error**2))),
        'FixedVsOpenCVMaxNativePixels':float(cverror.max()),'FixedVsOpenCVP99NativePixels':float(np.percentile(cverror,99)),
        'MaximumAllowedNativePixels':.125,'Passed':True,
        'MaximumNormalizedR2':float((x*x+y*y).max()),
        'WithinSourceImageFraction':float(((sx>=0)&(sx<=1919)&(sy>=0)&(sy<=1079)).mean())}


def vectors(work,width,height,calibration=CALIBRATION):
    cfg=config(calibration,width,height);work=Path(work);work.mkdir(parents=True,exist_ok=True)
    yy,xx=np.indices((height,width),dtype=np.int64);sx,sy,bad=fixed_map(xx*256,yy*256,config=cfg)
    with(work/'coordinates.mem').open('x',encoding='ascii',newline='\n')as stream:
        for x,y,b in zip(sx.ravel(),sy.ravel(),bad.ravel()):stream.write(f'{(int(b)<<48)|((int(x)&0xffffff)<<24)|(int(y)&0xffffff):013x}\n')
    return {'Width':width,'Height':height,'Coordinates':width*height,'Golden':ref(work/'coordinates.mem')}


def generate(work,calibration=CALIBRATION):
    work=Path(work).resolve();require(not work.exists(),'fresh profile output directory required')
    cfg=config(calibration);data={PROFILE_HEADER:header_bytes(cfg),TABLE_HEADER:table_bytes(cfg)}
    require(all(not (ROOT/name).exists()for name in data),'generated profile headers must be new files')
    checked=metrics(calibration);work.mkdir(parents=True)
    for name,content in data.items():(ROOT/name).write_bytes(content)
    value={'Schema':SCHEMA,'Passed':True,'Calibration':ref(calibration),'SourceFit':read_calibration(calibration)[0]['source_fit'],
        'SourceKNative':cfg['SourceK'].tolist(),'OutputKNative':cfg['OutputK'].tolist(),'DNormalized':cfg['D'].tolist(),
        'Projection':'C preview balance=.5 rectilinear, R=identity, exact native centre2*c+.5',
        'Format':{'NormalizedFractionBits':22,'RadialScaleFractionBits':30,'PixelFractionBits':8,
            'R2Domain':[0,8],'Nodes':1025,'Segments':1024,'SegmentFractionBits':15,
            'ROMWord':'{signedDeltaQ30[31:0],baseQ30[31:0]}','SynchronousWordBits':64,'Expected18KHalves':4,
            'MemoryResourceClaim':'four18K halves by1024x64 capacity; actual mapped usage requires native build'},
        'IdentityCoordinatesExact':True,'FullGridError':checked,
        'GeneratedFiles':{str(ROOT/name):hashlib.sha256(content).hexdigest()for name,content in data.items()},
        'Generator':ref(SELF),'OpenCVVersion':cv2.__version__,'NumPyVersion':np.__version__,
        'HardwareProgrammed':False,'RTLExecuted':False,'ExternalACAccepted':False}
    with(work/'profile.json').open('x',encoding='utf-8')as stream:json.dump(value,stream,indent=2,allow_nan=False)
    return value


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--work-dir',type=Path,required=True)
    p.add_argument('--calibration',type=Path,default=CALIBRATION);a=p.parse_args();v=generate(a.work_dir,a.calibration)
    print(json.dumps({'Passed':v['Passed'],'FullGridError':v['FullGridError'],'OutputKNative':v['OutputKNative']}));return 0


if __name__=='__main__':raise SystemExit(main())
