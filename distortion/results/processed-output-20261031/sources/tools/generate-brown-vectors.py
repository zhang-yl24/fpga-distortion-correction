"""Bit-accurate integer oracle plus independent floating Brown projection."""
from pathlib import Path
import json
import math
import numpy as np

Q=1<<22
def quant(value,scale): return math.floor(value*scale+0.5)
def round_shift(value,bits): return (value+(1<<(bits-1)))>>bits
def clip32(value): return max(-(1<<31),min((1<<31)-1,value))
def overflow32(value): return not -(1<<31)<=value<(1<<31)

def parameters(coefficients):
    # Synthetic test intrinsics, not a measured lens calibration.
    return [quant(v,256) for v in (319.5,239.5,319.5,239.5,320,333)]+[quant(1/320,1<<30),quant(1/333,1<<30)]+[quant(v,Q) for v in coefficients]

def project(u,v,c):
    ocx,ocy,scx,scy,sfx,sfy,ifx,ify,k1,k2,k3,p1,p2=c
    nx=round_shift((u-ocx)*ifx,16);ny=round_shift((v-ocy)*ify,16)
    bad=abs(nx)>2*Q or abs(ny)>2*Q
    nx,ny=clip32(nx),clip32(ny)
    xx=round_shift(nx*nx,22);yy=round_shift(ny*ny,22);xy=round_shift(nx*ny,22)
    r2=xx+yy
    bad|=any(overflow32(t) for t in (xx,yy,xy,r2))
    xx,yy,xy,r2=map(clip32,(xx,yy,xy,r2))
    txf=r2+2*xx;tyf=r2+2*yy
    bad|=overflow32(txf) or overflow32(tyf)
    tx=round_shift(2*p1*xy+p2*clip32(txf),22)
    ty=round_shift(p1*clip32(tyf)+2*p2*xy,22)
    h5=k2+round_shift(k3*r2,22)
    bad|=any(overflow32(t) for t in (tx,ty,h5))
    tx,ty,h5=map(clip32,(tx,ty,h5))
    h7=k1+round_shift(h5*r2,22);bad|=overflow32(h7);h7=clip32(h7)
    radial=Q+round_shift(h7*r2,22);bad|=overflow32(radial);radial=clip32(radial)
    xd=round_shift(nx*radial,22)+tx;yd=round_shift(ny*radial,22)+ty
    bad|=overflow32(xd) or overflow32(yd);xd,yd=map(clip32,(xd,yd))
    sx=round_shift(xd*sfx,22)+scx;sy=round_shift(yd*sfy,22)+scy
    bad|=not -(1<<23)<=sx<(1<<23) or not -(1<<23)<=sy<(1<<23)
    return (-(1<<23),-(1<<23),1) if bad else (sx,sy,0)

def floating(u,v,c):
    ocx,ocy,scx,scy,sfx,sfy,ifx,ify,k1,k2,k3,p1,p2=c
    x=((u-ocx)/256)*(ifx/(1<<30));y=((v-ocy)/256)*(ify/(1<<30))
    k1,k2,k3,p1,p2=(v/Q for v in (k1,k2,k3,p1,p2))
    r2=x*x+y*y;rad=1+k1*r2+k2*r2*r2+k3*r2*r2*r2
    return ((x*rad+2*p1*x*y+p2*(r2+2*x*x))*sfx/256+scx/256,
            (y*rad+p1*(r2+2*y*y)+2*p2*x*y)*sfy/256+scy/256)

def main():
    root=Path(__file__).resolve().parents[1];work=root/'build/brown_sim';work.mkdir(parents=True,exist_ok=True)
    configs=[parameters(x) for x in ((0,0,0,0,0),(-.24,.065,-.007,.003,-.002),(-.4,.12,-.008,.02,-.015),(500,0,0,0,0))]
    points=[(x*256+(x%13),y*256+(y%19)) for y in range(0,480,4) for x in range(0,640,4)]
    # Domain endpoints, overflow and signed extreme inputs.
    points += [(x,y) for x in (-(1<<23),-500*256,-1,0,639*256,1000*256,(1<<23)-1) for y in (-(1<<23),-1,0,479*256,(1<<23)-1)]
    rng=np.random.default_rng(0x20261006)
    points += [(int(rng.integers(-300*256,950*256)),int(rng.integers(-300*256,780*256))) for _ in range(1024)]
    rows=[];errors=[];black_counts=[]
    for ci,c in enumerate(configs):
        black_count=0
        for u,v in points:
            sx,sy,bad=project(u,v,c);black_count+=bad
            values=[u&0xffffff,v&0xffffff,sx&0xffffff,sy&0xffffff]
            packed=(values[0]<<73)|(values[1]<<49)|(bad<<48)|(values[2]<<24)|values[3]
            rows.append(f'{packed:025x}')
            if not bad and ci<3:
                fx,fy=floating(u,v,c)
                errors.append(max(abs(sx/256-fx),abs(sy/256-fy)))
        black_counts.append(black_count)
    configrows=[]
    for c in configs:
        configrows.append(''.join(f'{x&((1<<bits)-1):0{bits//4}x}' for x,bits in zip(c,[24]*6+[32]*7)))
    (work/'configs.mem').write_text('\n'.join(configrows)+'\n')
    (work/'vectors.mem').write_text('\n'.join(rows)+'\n')
    (work/'counts.vh').write_text(f'`define BROWN_N {len(points)}\n`define BROWN_TOTAL {len(rows)}\n')
    result={'queries_per_configuration':len(points),'total_queries':len(rows),'configurations':4,
            'coefficients_are_synthetic':True,'fixed_vs_float_max_axis_error_pixels':max(errors),
            'black_queries_per_config':black_counts,'fraction_bits_normalized':22,
            'fraction_bits_pixel':8,'rounding':'nearest, ties toward +infinity',
            'valid_normalized_axis_domain':[-2,2],
            'limits':'Brown model only, identity/radial/tangential/extreme coefficient tests; no real calibration. Error against analytic quantized parameters, not a full image-quality measurement.'}
    assert max(errors)<0.01,result
    (work/'vectors.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
