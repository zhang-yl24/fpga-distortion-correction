"""Independent CPU exact-calibration real-frame fixture. No RTL/EDA/device access.

Only a SHA-bound a-model/contract.json with original exact decimal parameters and
resolved zero-based pixel-centre convention is accepted. Rounded README values
are deliberately rejected. Run once only after that contract exists. CPU and
wall-clock work is bounded to 300 seconds and exactly one 1920x1080 raster.
"""
import os
for _key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):
    os.environ[_key]='1'
from pathlib import Path
from decimal import Decimal, ROUND_FLOOR
from contextlib import ExitStack
import argparse, hashlib, importlib.util, json, math, sys, time, zlib
sys.dont_write_bytecode=True
import numpy as np
from PIL import Image

ap=argparse.ArgumentParser(description="Private-input exact frame240 CPU oracle; internal research only")
for flag in ("contract","source-dir","review-dir","calibration-file","origin-evidence","output-dir"):
    ap.add_argument("--"+flag,type=Path,required=True)
args=ap.parse_args()
ROOT=Path(__file__).resolve().parents[1]
CONTRACT=args.contract.resolve(); SOURCE=args.source_dir.resolve(); REVIEW=args.review_dir.resolve()
B=args.output_dir.resolve(); B.mkdir(exist_ok=False)
W,H,N,Q=1920,1080,2073600,1<<22
PARAM_NAMES=['out_cx','out_cy','src_cx','src_cy','src_fx','src_fy','inv_fx','inv_fy','k1','k2','k3','p1','p2']
BITS=[24]*6+[32]*7

def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for chunk in iter(lambda:f.read(1<<20),b''): h.update(chunk)
    return h.hexdigest()
def load(p): return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def save(name,record):
    with (B/name).open('x',encoding='utf-8') as f: json.dump(record,f,indent=2);f.write('\n')
def absmax(v):
    return max(abs(int(np.min(v))),abs(int(np.max(v)))) if np.ndim(v) else abs(int(v))

def rs(v,bits):
    # Check the rounding addition before an int64 operation can wrap.
    half=1<<(bits-1)
    assert absmax(v)+half < (1<<63), 'int64 rounding addition overflow risk'
    return (v+half)>>bits

def checked_mul(a,b):
    assert absmax(a)*absmax(b) < (1<<63), 'int64 product overflow risk'
    return a*b

def signed_roundtrip(cfg):
    encoded=[v&((1<<bits)-1) for v,bits in zip(cfg,BITS)]
    decoded=[v-(1<<bits) if v&(1<<(bits-1)) else v for v,bits in zip(encoded,BITS)]
    assert decoded==cfg, '13 signed parameter encode/decode mismatch'
    return encoded
def quant(v,scale): return int((v*scale+Decimal('.5')).to_integral_value(rounding=ROUND_FLOOR))
def hexes(f,values,digits): f.write(''.join(f'{int(v):0{digits}x}\n' for v in values))
def path_in_contract(c,key):
    return (args.calibration_file if key=='source_calibration_file' else args.origin_evidence).resolve()

def exact_contract():
    assert sha(CONTRACT)=='4be4883514d792116e4a0b8866356699314dd981e7ee312ddecf4261efd8d63b', 'Restore exact private contract'
    c=load(CONTRACT)
    assert c['exact_original_parameters'] is True, 'Exact original coefficients required'
    assert c['coordinate_origin']=='zero_based_pixel_centres', 'Unresolved origin is a hard gate'
    assert c['source_size']==c['output_size']==[W,H]
    assert c['output_intrinsics']=='same_as_source' and c['angle_deg']==0
    protected={str(CONTRACT):sha(CONTRACT)}
    for key in ['source_calibration','origin_evidence']:
        p=path_in_contract(c,key+'_file')
        assert sha(p)==c[key+'_sha256'], f'{key} provenance SHA mismatch'
        protected[str(p)]=sha(p)
    p=c['exact_parameters']
    assert set(p)==set(['fx','fy','cx','cy','k1','k2','k3','p1','p2'])
    assert all(isinstance(v,str) for v in p.values()), 'Preserve original decimal precision as strings'
    e={k:Decimal(v) for k,v in p.items()}
    assert all(v.is_finite() for v in e.values()) and e['fx']>0 and e['fy']>0
    cfg=[quant(e[k],256) for k in ['cx','cy','cx','cy','fx','fy']]
    cfg += [quant(1/e[k],1<<30) for k in ['fx','fy']]
    cfg += [quant(e[k],Q) for k in ['k1','k2','k3','p1','p2']]
    assert all(-(1<<(b-1))<=v<(1<<(b-1)) for v,b in zip(cfg,BITS))
    if 'integer_config' in c: assert c['integer_config']==cfg
    signed_roundtrip(cfg)
    assert c['radius_guard_q22']==1387217
    assert c['source_binding']['frame_index_zero_based']==240
    assert c['source_binding']['source_rgb565_sha256']=='2705e97a9ef24f744b4ac081032ef4a97d62608e51e6fefc9b0d0782b419f338'
    return c,e,cfg,protected

def brown(u,v,c,guard=None):
    """Vector implementation checked against independently maintained scalar."""
    ocx,ocy,scx,scy,sfx,sfy,ifx,ify,k1,k2,k3,p1,p2=c
    bad=np.zeros(u.shape,dtype=bool); maximum_product=0
    def mul(a,b):
        nonlocal maximum_product
        # Test mathematical bound before NumPy multiplication can wrap int64.
        result=checked_mul(a,b)
        maximum_product=max(maximum_product,absmax(result))
        return result
    def add(*args):
        bound=sum(absmax(a) for a in args)
        assert bound<(1<<63),'int64 addition overflow risk'
        return sum(args)
    def clip(x):
        nonlocal bad
        bad|=(x<-(1<<31))|(x>=(1<<31))
        return np.clip(x,-(1<<31),(1<<31)-1)
    nx,ny=rs(mul(u-ocx,ifx),16),rs(mul(v-ocy,ify),16)
    bad|=(np.abs(nx)>2*Q)|(np.abs(ny)>2*Q)
    nx,ny=clip(nx),clip(ny)
    xx,yy,xy=clip(rs(mul(nx,nx),22)),clip(rs(mul(ny,ny),22)),clip(rs(mul(nx,ny),22))
    r2=clip(add(xx,yy))
    if guard is not None: bad|=r2>guard
    txf,tyf=clip(add(r2,mul(2,xx))),clip(add(r2,mul(2,yy)))
    tx=clip(rs(add(mul(2*p1,xy),mul(p2,txf)),22))
    ty=clip(rs(add(mul(p1,tyf),mul(2*p2,xy)),22))
    h5=clip(add(k2,rs(mul(k3,r2),22)))
    h7=clip(add(k1,rs(mul(h5,r2),22)))
    radial=clip(add(Q,rs(mul(h7,r2),22)))
    xd=clip(add(rs(mul(nx,radial),22),tx));yd=clip(add(rs(mul(ny,radial),22),ty))
    sx=add(rs(mul(xd,sfx),22),scx);sy=add(rs(mul(yd,sfy),22),scy)
    bad|=(sx<-(1<<23))|(sx>=(1<<23))|(sy<-(1<<23))|(sy>=(1<<23))
    return np.where(bad,-(1<<23),sx),np.where(bad,-(1<<23),sy),bad,int(r2.max()),maximum_product

def expand(p):
    p=p.astype(np.int64)
    r,g,b=p>>11,(p>>5)&63,p&31
    return (r<<3)|(r>>2),(g<<2)|(g>>4),(b<<3)|(b>>2)
def sample(sx,sy,src):
    ix,iy,fx,fy=sx>>8,sy>>8,sx&255,sy&255
    accum=[np.zeros(sx.shape,dtype=np.int64) for _ in range(3)]
    for dx,dy,wt in [(0,0,(256-fx)*(256-fy)),(1,0,fx*(256-fy)),(0,1,(256-fx)*fy),(1,1,fx*fy)]:
        x,y=ix+dx,iy+dy
        inside=(x>=0)&(x<W)&(y>=0)&(y<H)
        idx=np.clip(y,0,H-1)*W+np.clip(x,0,W-1)
        pixel=np.where(inside,src[idx],0).astype(np.uint16)
        for ch,rgb in enumerate(expand(pixel)): accum[ch]+=rgb*wt
    return [(x+32768)>>16 for x in accum]
def sample_scalar(sx,sy,src):
    ix,iy,fx,fy=sx>>8,sy>>8,sx&255,sy&255
    accum=[0,0,0]
    for dx,dy,wt in [(0,0,(256-fx)*(256-fy)),(1,0,fx*(256-fy)),(0,1,(256-fx)*fy),(1,1,fx*fy)]:
        x,y=ix+dx,iy+dy
        p=int(src[y*W+x]) if 0<=x<W and 0<=y<H else 0
        r,g,b=p>>11,(p>>5)&63,p&31
        for ch,a in enumerate(((r<<3)|(r>>2),(g<<2)|(g>>4),(b<<3)|(b>>2))): accum[ch]+=a*wt
    return tuple((a+32768)>>16 for a in accum)

def analytic(u,v,e):
    e={k:float(v) for k,v in e.items()}
    x=(u/256-e['cx'])/e['fx'];y=(v/256-e['cy'])/e['fy']
    r2=x*x+y*y;k1,k2,k3,p1,p2=[e[k] for k in ['k1','k2','k3','p1','p2']]
    rad=1+r2*(k1+r2*(k2+r2*k3));dr=k1+2*k2*r2+3*k3*r2*r2
    sx=(x*rad+2*p1*x*y+p2*(r2+2*x*x))*e['fx']+e['cx']
    sy=(y*rad+p1*(r2+2*y*y)+2*p2*x*y)*e['fy']+e['cy']
    jxx=rad+2*x*x*dr+2*p1*y+6*p2*x
    jyy=rad+2*y*y*dr+6*p1*y+2*p2*x
    jxy=2*x*y*dr+2*p1*x+2*p2*y
    return sx,sy,rad,rad+2*r2*dr,jxx*jyy-jxy*jxy

def main():
    start,cpustart=time.perf_counter(),time.process_time()
    def budget(): assert time.perf_counter()-start<=300 and time.process_time()-cpustart<=300,'300 second budget exceeded'
    contract,e,c,protected=exact_contract()
    dec=load(SOURCE/'decode.json')
    assert dec['exit_code']==0 and dec['frame_index_zero_based']==240
    assert dec['width']==W and dec['height']==H and dec['rgb565_roundtrip_mismatches']==0
    assert sha(SOURCE/'source.rgb565')==dec['files_sha256']['source.rgb565']==contract['source_binding']['source_rgb565_sha256']
    assert sha(SOURCE/'source.rgb24')==dec['files_sha256']['source.rgb24']==contract['source_binding']['source_rgb24_sha256']
    for name in ['source.rgb24','source.rgb565','decode.json']: protected[str(SOURCE/name)]=sha(SOURCE/name)
    protected[str(Path(__file__))]=sha(Path(__file__))
    scalarpath=ROOT/'tools/generate-brown-vectors.py'
    for path in [scalarpath,ROOT/'model/reference.py',ROOT/'tools/generate_1080_core_vectors.py',REVIEW/'cc4-exact.json',REVIEW/'result.json']:
        protected[str(path)]=sha(path)
    prior=load(REVIEW/'result.json')
    assert prior['pixels_examined']==N and prior['integer_config_oracle_order']==c and prior['numerical_pass']
    spec=importlib.util.spec_from_file_location('realframe_scalar',scalarpath)
    scalar=importlib.util.module_from_spec(spec);spec.loader.exec_module(scalar)
    sys.path.insert(0,str(ROOT))
    from model.reference import remap_fixed
    names=[f'{s}{i}.mem' for s in ['source','expected','masks','sourcecrc','crc'] for i in range(2)]
    names+=['corrected_maps.mem','corrected_rotated.mem','corrected_raw.mem','source.rgb565','expected.rgb565','expected.png','config.vh','config.mem','fixture.json','fixture-proof.json','before.json','directed-points.json']
    assert not any((B/n).exists() for n in names),'Preserve previous evidence; outputs must be fresh'
    save('before.json',dict(contract_sha256=sha(CONTRACT),protected_sha256=protected,CPUBudgetSeconds=300,RTLUsedForGolden=False,HardwareAccessed=False))
    src=np.fromfile(SOURCE/'source.rgb565',dtype='<u2');assert len(src)==N
    expanded=np.stack(expand(src),axis=-1).astype(np.uint8).reshape(H,W,3)
    # Independent light guard check: separable squared normalized axes attain
    # their maximum at endpoints, including the declared integer rounding.
    corners=[]
    for x,y in [(0,0),(W-1,0),(0,H-1),(W-1,H-1)]:
        nx=rs(checked_mul(x*256-c[0],c[6]),16);ny=rs(checked_mul(y*256-c[1],c[7]),16)
        xx=rs(checked_mul(nx,nx),22);yy=rs(checked_mul(ny,ny),22)
        assert abs(xx)+abs(yy)<(1<<63)
        corners.append(dict(x=x,y=y,nx=nx,ny=ny,r2=xx+yy))
    maxr2=max(p['r2'] for p in corners);guard=maxr2+2
    assert maxr2==1387215 and guard==contract['radius_guard_q22']==1387217
    spots={0,W-1,N-W,N-1,(H//2)*W+W//2,W//2,(H-1)*W+W//2,(H//2)*W,(H//2)*W+W-1}
    seed=0x20261029
    while len(spots)<257: seed=(seed*1664525+1013904223)&0xffffffff;spots.add(seed%N)
    scalarchecks=[];count=invalid=masked=partial=black=0;maxprod=observedr2=0
    crcs=[zlib.crc32(src.astype('<u2').tobytes()),0]
    outpixels=np.empty(N,dtype=np.uint16);sxall=np.empty(N,dtype=np.int32);syall=np.empty(N,dtype=np.int32)
    rawall=np.empty(N,dtype=np.uint32);maskall=np.empty(N,dtype=bool);badall=np.empty(N,dtype=bool)
    extents=[1<<62,-(1<<62),1<<62,-(1<<62)]
    with ExitStack() as stack:
        streams={n:stack.enter_context((B/n).open('x',encoding='ascii',newline='\n')) for n in names if n.endswith('.mem') and n not in ['sourcecrc0.mem','sourcecrc1.mem','crc0.mem','crc1.mem','config.mem']}
        for row in range(0,H,64):
            budget();end=min(row+64,H);tags=np.arange(row*W,end*W,dtype=np.int64)
            u,v=(tags%W)*256,(tags//W)*256
            sx,sy,bad,r2,prod=brown(u,v,c,guard)
            assert r2<=maxr2;maxprod=max(maxprod,prod);observedr2=max(observedr2,r2)
            mask=bad|(sx<=-256)|(sy<=-256)|(sx>=W*256)|(sy>=H*256)
            mapped=remap_fixed(expanded,sx/256.,sy/256.)
            red,green,blue=(mapped[:,i].astype(np.int64) for i in range(3))
            rgb=(red<<16)|(green<<8)|blue
            pixels=(((red>>3)<<11)|((green>>2)<<5)|(blue>>3)).astype(np.uint16)
            assert np.all(pixels[mask]==0) and np.all(rgb[mask]==0),'Geometry-masked sampling must be black'
            source=src[row*W:end*W]
            for i in [0,1]: hexes(streams[f'source{i}.mem'],source,4)
            hexes(streams['expected0.mem'],source,4);hexes(streams['expected1.mem'],pixels,4)
            hexes(streams['masks0.mem'],np.zeros(len(tags),dtype=np.uint8),1);hexes(streams['masks1.mem'],mask,1)
            hexes(streams['corrected_maps.mem'],(bad.astype(np.int64)<<48)|((sx&0xffffff)<<24)|(sy&0xffffff),13)
            hexes(streams['corrected_rotated.mem'],(u<<24)|v,13)
            hexes(streams['corrected_raw.mem'],(mask.astype(np.int64)<<24)|rgb,7)
            sl=slice(row*W,end*W);outpixels[sl]=pixels;sxall[sl]=sx;syall[sl]=sy;rawall[sl]=rgb;maskall[sl]=mask;badall[sl]=bad
            crcs[1]=zlib.crc32(pixels.astype('<u2').tobytes(),crcs[1])
            invalid+=int(bad.sum());masked+=int(mask.sum());black+=int(np.count_nonzero((~mask)&(pixels==0)))
            partial+=int(np.count_nonzero((~mask)&((sx<0)|(sy<0)|(sx>=(W-1)*256)|(sy>=(H-1)*256))))
            extents=[min(extents[0],int(sx.min())),max(extents[1],int(sx.max())),min(extents[2],int(sy.min())),max(extents[3],int(sy.max()))];count+=len(tags)
    budget()
    assert count==N and invalid==0 and observedr2==maxr2 and masked==84358 and partial==5759
    valid=~maskall
    left=valid&(sxall<0);right=valid&(sxall>=(W-1)*256);top=valid&(syall<0);bottom=valid&(syall>=(H-1)*256)
    categories={'partial_left':left,'partial_right':right,'partial_top':top,'partial_bottom':bottom,
        'partial_top_left':left&top,'partial_top_right':right&top,'partial_bottom_left':left&bottom,'partial_bottom_right':right&bottom,
        'fully_outside':maskall,'source_real_black':src==0,'corrected_rgb24_real_black':valid&(rawall==0),
        'corrected_rgb565_real_black':valid&(outpixels==0),'fractional':valid&(((sxall&255)!=0)|((syall&255)!=0)),
        'nonzero_color_difference':valid&(src!=outpixels)&(src!=0)&(outpixels!=0)}
    category_counts={};directed={0,W-1,N-W,N-1,(H//2)*W+W//2,W//2,(H-1)*W+W//2,(H//2)*W,(H//2)*W+W-1}
    representatives={}
    for name,condition in categories.items():
        indices=np.flatnonzero(condition);category_counts[name]=len(indices)
        selected=[int(indices[j]) for j in np.unique(np.linspace(0,len(indices)-1,min(4,len(indices)),dtype=int))] if len(indices) else []
        representatives[name]=selected;directed.update(selected)
    assert all(category_counts[k]>0 for k in ['partial_left','partial_right','partial_top','partial_bottom','fully_outside','source_real_black','corrected_rgb24_real_black','fractional','nonzero_color_difference'])
    while len(directed)<256: seed=(seed*1664525+1013904223)&0xffffffff;directed.add(seed%N)
    assert len(directed)==256
    spots.update(directed)
    # Scalar Python-int mapper and scalar per-neighbour sampler are independent
    # from vector mapping and the reused model.reference full-frame sampler.
    for tag in sorted(spots):
        u,v=(tag%W)*256,(tag//W)*256
        scx,scy,sbad=scalar.project(u,v,c)
        assert (int(sxall[tag]),int(syall[tag]),bool(badall[tag]))==(scx,scy,bool(sbad)),tag
        rgb=sample_scalar(scx,scy,src);word=(rgb[0]<<16)|(rgb[1]<<8)|rgb[2]
        pixel=((rgb[0]>>3)<<11)|((rgb[1]>>2)<<5)|(rgb[2]>>3)
        smask=bool(sbad or scx<=-256 or scy<=-256 or scx>=W*256 or scy>=H*256)
        assert word==int(rawall[tag]) and pixel==int(outpixels[tag]) and smask==bool(maskall[tag]),tag
        scalarchecks.append(dict(tag=tag,outq8=[u,v],mappedq8=[scx,scy],bad=bool(sbad),raw24=f'{word:06x}',rgb565=f'{pixel:04x}',mask=smask))
    # Deliberate boundary probes prove per-neighbour zero fill, including all
    # four partially outside corners, with the current frame240 pixel source.
    edgecoords=[(-257,128),(-256,128),(-255,128),(-1,128),(W*256-1,128),(W*256,128),
        (128,-255),(128,-1),(128,H*256-1),(128,H*256),(-1,-1),(W*256-1,-1),(-1,H*256-1),(W*256-1,H*256-1)]
    edgechecks=[]
    for x,y in edgecoords:
        rgb=tuple(int(a[0]) for a in sample(np.array([x]),np.array([y]),src));assert rgb==sample_scalar(x,y,src)
        ref=remap_fixed(expanded,np.array([x/256.]),np.array([y/256.]))[0]
        assert tuple(int(q) for q in ref)==rgb
        mask=x<=-256 or y<=-256 or x>=W*256 or y>=H*256
        if mask: assert rgb==(0,0,0)
        edgechecks.append(dict(sourceq8=[x,y],mask=mask,rgb=list(rgb)))
    # Requests use native output coordinates; each coordinate is exercised in
    # raw and corrected mode. Tags are transfer sequence, not raster index.
    requests=[]
    for coord in sorted(directed):
        u,v=(coord%W)*256,(coord//W)*256
        for corr in (0,1):
            if corr: sx,sy,bad,raw,pixel,mask=int(sxall[coord]),int(syall[coord]),bool(badall[coord]),int(rawall[coord]),int(outpixels[coord]),bool(maskall[coord])
            else:
                rgb=tuple(int(x) for x in expanded.reshape(N,3)[coord]);sx,sy,bad,raw,pixel,mask=u,v,False,(rgb[0]<<16)|(rgb[1]<<8)|rgb[2],int(src[coord]),False
            ispartial=corr and not mask and (sx<0 or sy<0 or sx>=(W-1)*256 or sy>=(H-1)*256)
            flags=int(bool(ispartial and raw!=0))|(int(mask)<<1)|(int(not mask and raw==0)<<2)
            requests.append(dict(outq8=[u,v],tag=len(requests),phase_tag=len(requests)//2,corr=corr,mappedq8=[sx,sy],bad=bad,raw24=f'{raw:06x}',rgb565=f'{pixel:04x}',mask=mask,raster_index=coord,coverage_flags=flags))
    formats={'directed_u.mem':(lambda q:q['outq8'][0],6),'directed_v.mem':(lambda q:q['outq8'][1],6),
        'directed_tag.mem':(lambda q:q['tag'],6),'directed_corr.mem':(lambda q:q['corr'],1),
        'directed_maps.mem':(lambda q:(int(q['bad'])<<48)|((q['mappedq8'][0]&0xffffff)<<24)|(q['mappedq8'][1]&0xffffff),13),
        'directed_raw.mem':(lambda q:(int(q['mask'])<<24)|int(q['raw24'],16),7),
        'directed_expected.mem':(lambda q:int(q['rgb565'],16),4),'directed_masks.mem':(lambda q:int(q['mask']),1),
        'directed_requests.mem':(lambda q:(q['corr']<<72)|(q['tag']<<48)|(q['outq8'][0]<<24)|q['outq8'][1],19)}
    for name,(getter,digits) in formats.items():
        with (B/name).open('x',encoding='ascii',newline='\n') as f:hexes(f,[getter(q) for q in requests],digits)
    save('directed-points.json',dict(schema=1,frame_index_zero_based=240,source_rgb565_sha256=sha(SOURCE/'source.rgb565'),contract_sha256=sha(CONTRACT),coordinate_count=256,request_count=len(requests),
        category_counts=category_counts,representative_raster_indices=representatives,request_format='19hex corr72|tag48|out_u24|out_v24; individual mem alternatives provided',
        phase_tag_rule='Group by corr=0 or corr=1 and preserve order; phase_tag=0..255 equals original request tag//2. Each phase starts a new accepted frame with matching source bank.',
        coverage_flags='bit0 partial footprint AND raw24!=0; bit1 geometry mask/full outside; bit2 unmasked raw24==0',
        sampling='Current original frame240; expand565; each missing neighbour zero; one merged +32768 >>16; Gamma0; RGB565 truncation',points=requests))
    print(json.dumps({'directed_ready':str(B/'directed-points.json'),'coordinates':256,'requests':len(requests),'categories':category_counts}),flush=True)
    with (B/'source.rgb565').open('xb') as f:f.write(src.astype('<u2').tobytes())
    with (B/'expected.rgb565').open('xb') as f:f.write(outpixels.astype('<u2').tobytes())
    Image.fromarray(np.stack(expand(outpixels),axis=-1).astype(np.uint8).reshape(H,W,3)).save(B/'expected.png')
    encoded=signed_roundtrip(c);confighex=''.join(f'{v:0{bits//4}x}' for v,bits in zip(encoded,BITS));assert len(confighex)==92
    with (B/'config.mem').open('x',encoding='ascii',newline='\n') as f:f.write(confighex+'\n')
    config=[f'localparam integer VEC_WIDTH={W},VEC_HEIGHT={H},VEC_PIXELS={N},VEC_RADIUS_GUARD_Q22={guard};']
    for name,v,bits in zip(PARAM_NAMES,c,BITS):config.append(f"localparam signed [{bits-1}:0] VEC_{name.upper()}={bits}'sh{v&((1<<bits)-1):0{bits//4}x};")
    config += [f"localparam signed [23:0] VEC_ROT_CX=24'sd{c[0]},VEC_ROT_CY=24'sd{c[1]};","localparam signed [31:0] VEC_ROT_COS=32'sd1073741824,VEC_ROT_SIN=32'sd0;","localparam [1:0] VEC_GAMMA_MODE=2'd0;"]
    with (B/'config.vh').open('x',encoding='ascii',newline='\n') as f:f.write('\n'.join(config)+'\n')
    for name,value in [('sourcecrc0.mem',crcs[0]),('sourcecrc1.mem',crcs[0]),('crc0.mem',crcs[0]),('crc1.mem',crcs[1])]:
        with (B/name).open('x',encoding='ascii',newline='\n') as f:f.write(f'{value:08x}\n')
    budget();assert all(sha(p)==v for p,v in protected.items())
    assert crcs[0]==0xc14e962f and np.count_nonzero(src!=outpixels)>0
    outputsha={p.name:sha(p) for p in B.iterdir() if p.is_file() and p.name not in ['before.json','fixture.json','fixture-proof.json']}
    record=dict(DevelopmentOnly=True,OpticalAcceptanceComplete=False,RealImage=True,RTLUsedForGolden=False,RTLExecuted=False,HardwareAccessed=False,PDSAccessed=False,FrameIndex=240,Width=W,Height=H,Pixels=count,ExactCalibrationContractSHA256=sha(CONTRACT),IntegerConfig=c,ParameterBits=BITS,ParameterOrder=PARAM_NAMES,ParameterConcatenationBits=sum(BITS),SignedParametersRoundtrip=True,GuardQ22=guard,MaximumRoundedNormalizedR2Q22=maxr2,GuardRule='Independent endpoint maximum +2, confirmed by current integer full raster',RotationQ=[c[0],c[1],1<<30,0],CORDICNotUsed=True,ArithmeticInvalid=invalid,MaximumObservedProductAbs=maxprod,MapExtentsQ8=extents,Masked=masked,PartialBorder=partial,RealBlackUnmasked=black,RealRGB24BlackUnmasked=category_counts['corrected_rgb24_real_black'],SourceRealBlack=int(np.count_nonzero(src==0)),RawCorrectedDifferentPixels=int(np.count_nonzero(src!=outpixels)),ScalarCrosschecks=len(scalarchecks),GammaMode=0,GammaEnable=False,CRC32=[f'{x:08x}' for x in crcs],SourceCRC32=f'{crcs[0]:08x}',SourceRGB565SHA256=sha(B/'source.rgb565'),CPUBudgetSeconds=300,CPUWallSeconds=time.perf_counter()-start,CPUProcessSeconds=time.process_time()-cpustart,FilesSHA256=outputsha,ProtectedSHA256=protected,
        FullFloatAuditReExecuted=False,PriorNumericReviewReused={'path':str(REVIEW/'result.json'),'sha256':sha(REVIEW/'result.json'),'pixels_examined':prior['pixels_examined'],'max_error_px':prior['fixed_vs_exact_MAT_float']['max_px']},
        ColorConvention='Original frame240 FFmpeg default swscale RGB24 conversion, then RGB565 truncation; source color metadata absent; matrix/range/chroma siting not forced and true HDMI color not claimed',
        Formats=dict(source='source0/1: one RGB565 pixel per 4hex LF line; identical real input to both stages',expected='expected0 source passthrough; expected1 corrected Gamma0',masks='one geometry-mask bit per line; real black retained as mask=0',maps='13hex bad48|sx24|sy24',rotated='13hex u24|v24, exact identity',raw='7hex mask24|rgb24',crc='CRC32 over little-endian RGB565 bytes; one8hex line',config='368bit 6signed24 + 7signed32; Q8 pixel/focal,Q30 inverse focal,Q22 distortion'))
    save('fixture.json',record);save('fixture-proof.json',dict(Passed=True,FullRasterPoints=count,ScalarChecks=scalarchecks,SupplementalBorderChecks=edgechecks,GuardCornerChecks=corners,DirectedCategoryCounts=category_counts,FixtureSHA256=sha(B/'fixture.json'),NoRTLResultsUsed=True))
    print(json.dumps({k:record[k] for k in ['Pixels','GuardQ22','MaximumRoundedNormalizedR2Q22','Masked','PartialBorder','RealBlackUnmasked','ScalarCrosschecks','CRC32','CPUWallSeconds','CPUProcessSeconds']},indent=2))
if __name__=='__main__': main()
