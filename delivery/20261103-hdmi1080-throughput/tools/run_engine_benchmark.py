"""Bound, independent integer-golden processing-engine benchmark (no hardware).

Requires numpy and Vivado xsim. Outputs go into a NEW directory. All four
variants use identical source texture, quantized Brown parameters and DDR model.
"""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import time
import zlib
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
FROZEN = ROOT.parent / '20261103-hdmi1080-demo-source/native'
GEOM = 'source/build/offline-20261024/geometry-bypass-parallel-20261029-coordination/'
NAMES = [
    'source/rtl/mul32_pipe.v', 'source/rtl/pixel_inverse_rotation.v',
    'source/rtl/bounded_brown_inverse_mapper.v', 'source/rtl/bilinear_rgb.v',
    'source/rtl/experimental/adaptive_gamma_stream.v',
    'source/rtl/experimental/adaptive_gamma_tagged.v',
    'source/rtl/experimental/ddr_adaptive_result_writer.v',
    'source/rtl/experimental/ddr_compact_neighbour_cache_scatter4.v',
    'source/rtl/experimental/ddr_remap_sample_scatter4.v',
    GEOM+'rotated_remap_core_gamma_geometry_bypass_scatter4.v',
    GEOM+'pipeline_gamma_frame_engine_1080_geometry_bypass.v',
]
HEADERS = ['source/rtl/video_crc32.vh','source/rtl/experimental/gamma_curves.vh']
PARAM = 'source/build/offline-20261024/boardtop-penn-prep-20261029-a/board1080-penn.vh'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def project(u, v, c):
    """Independent vector integer oracle from generate_1080_core_vectors.py.

    Rounding/saturation mirror the numeric contract, with no RTL output input.
    Coordinate samples are also cross-checked against its separate scalar oracle.
    """
    def rs(a,n): return (a+(1<<(n-1)))>>n
    bad=np.zeros(np.broadcast_shapes(u.shape,v.shape),dtype=bool)
    def s32(a):
        nonlocal bad
        bad|=(a<-(1<<31))|(a>=(1<<31))
        return np.clip(a,-(1<<31),(1<<31)-1)
    nx,ny=rs((u-c[0])*c[6],16),rs((v-c[1])*c[7],16)
    bad|=(np.abs(nx)>2*(1<<22))|(np.abs(ny)>2*(1<<22))
    nx,ny=s32(nx),s32(ny)
    xx,yy,xy=rs(nx*nx,22),rs(ny*ny,22),rs(nx*ny,22)
    r2=xx+yy
    xx,yy,xy,r2=s32(xx),s32(yy),s32(xy),s32(r2)
    txf,tyf=s32(r2+2*xx),s32(r2+2*yy)
    tx,ty=s32(rs(2*c[11]*xy+c[12]*txf,22)),s32(rs(c[11]*tyf+2*c[12]*xy,22))
    h5=s32(c[9]+rs(c[10]*r2,22))
    h7=s32(c[8]+rs(h5*r2,22))
    radial=s32((1<<22)+rs(h7*r2,22))
    xd,yd=s32(rs(nx*radial,22)+tx),s32(rs(ny*radial,22)+ty)
    sx,sy=rs(xd*c[4],22)+c[2],rs(yd*c[5],22)+c[3]
    bad|=(sx<-(1<<23))|(sx>=(1<<23))|(sy<-(1<<23))|(sy>=(1<<23))
    return np.where(bad,-(1<<23),sx),np.where(bad,-(1<<23),sy),bad,r2


def fixtures(work,w,h,pressure,scatter):
    # These are the exact frozen Penn coefficients; small runs scale intrinsics.
    c=[251104,134128,251104,134128,501718,501603,547873,547999,891415,-1930345,0,0,0]
    radius=1387217
    if (w,h)!=(1920,1080):
        for i in (0,2,4): c[i]=int(np.floor(c[i]*w/1920+0.5))
        for i in (1,3,5): c[i]=int(np.floor(c[i]*h/1080+0.5))
        c[6]=int(np.floor(c[6]*1920/w+0.5));c[7]=int(np.floor(c[7]*1080/h+0.5))
    # Verify hard-coded numeric fixture provenance before using it.
    text=(FROZEN/PARAM).read_text()
    for name,val,bits in zip(('OUT_CX','OUT_CY','SRC_CX','SRC_CY','SRC_FX','SRC_FY','INV_FX','INV_FY','K1','K2','K3','P1','P2'),
                            [251104,134128,251104,134128,501718,501603,547873,547999,891415,-1930345,0,0,0],[24]*6+[32]*7):
        m=re.search(r'B1080_'+name+r"=\d+'sh([0-9a-fA-F]+)",text)
        if not m or int(m.group(1),16)!=(val&((1<<bits)-1)): raise ValueError('Frozen parameter changed: '+name)
    y,x=np.indices((h,w),dtype=np.int64);idx=y*w+x
    src=((idx*73)^(idx>>3)^(y*997))&65535
    r,g,b=(src>>11)&31,(src>>5)&63,src&31
    rgb=np.stack(((r<<3)|(r>>2),(g<<2)|(g>>4),(b<<3)|(b>>2)),axis=-1)
    sx,sy,bad,r2=project(x*256,y*256,c)
    mask=bad|(r2>radius)|(sx<=-256)|(sy<=-256)|(sx>=w*256)|(sy>=h*256)
    scalar_path=REPO/'distortion/tools/generate-brown-vectors.py'
    spec=importlib.util.spec_from_file_location('scalar_brown',scalar_path)
    scalar=importlib.util.module_from_spec(spec);spec.loader.exec_module(scalar)
    crosschecks=0
    for yy in np.linspace(0,h-1,min(h,13),dtype=int):
        for xx in np.linspace(0,w-1,min(w,17),dtype=int):
            a=scalar.project(int(xx)*256,int(yy)*256,c)
            if a!=(int(sx[yy,xx]),int(sy[yy,xx]),int(bad[yy,xx])): raise AssertionError('scalar/vector disagreement')
            crosschecks+=1
    ix,iy=sx>>8,sy>>8;fx,fy=(sx&255)[...,None],(sy&255)[...,None]
    def gather(dx,dy):
        xx,yy=ix+dx,iy+dy;valid=(xx>=0)&(yy>=0)&(xx<w)&(yy<h)
        return rgb[np.clip(yy,0,h-1),np.clip(xx,0,w-1)]*valid[...,None]
    h0=gather(0,0)*(256-fx)+gather(1,0)*fx
    h1=gather(0,1)*(256-fx)+gather(1,1)*fx
    out=(h0*(256-fy)+h1*fy+32768)>>16
    words=((out[...,0]>>3)<<11)|((out[...,1]>>2)<<5)|(out[...,2]>>3)
    words=np.where(mask,0,words).astype('<u2')
    crc=zlib.crc32(words.tobytes())
    np.savetxt(work/'expected.mem',words.reshape(-1),fmt='%04x')
    np.savetxt(work/'masks.mem',mask.astype(np.uint8).reshape(-1),fmt='%01x')
    cfg=[f'localparam W={w},H={h},RADIUS={radius},PRESSURE={int(pressure)},SCATTER_PER_FILL={scatter};']
    for name,i in [('CX',0),('CY',1),('FX',4),('FY',5),('IFX',6),('IFY',7),('K1',8),('K2',9)]:
        bits=24 if i<6 else 32
        cfg.append(f"localparam signed [{bits-1}:0] {name}={bits}'sh{c[i]&((1<<bits)-1):x};")
    cfg.append(f"localparam [31:0] EXPECTED_CRC=32'h{crc:08x};")
    (work/'engine_config.vh').write_text('\n'.join(cfg)+'\n')
    return {'config':c,'expected_crc32':f'{crc:08x}','masked_pixels':int(mask.sum()),
            'scalar_crosschecks':crosschecks,'scalar_source_sha256':sha(scalar_path),
            'parameter_header_sha256':sha(FROZEN/PARAM)}


def run(args):
    work=args.work.resolve();work.mkdir(parents=True,exist_ok=False)
    start=time.monotonic()
    report={'passed':False,'variant':args.variant,'width':args.width,'height':args.height,
            'hardware_accessed':False,'synthesis_executed':False,'input_preloaded':True,
            'capture_display_arbitration_modeled':False,'commands':[],'source_sha256':{}}
    try:
        cache=args.variant in ('cache','both');writer=args.variant in ('writer','both')
        report['fixtures']=fixtures(work,args.width,args.height,args.pressure,16 if cache else 32)
        selected={n:FROZEN/n for n in NAMES+HEADERS}
        if cache:selected['source/rtl/experimental/ddr_compact_neighbour_cache_scatter4.v']=ROOT/'rtl/ddr_compact_neighbour_cache_scatter4.v'
        if writer:selected['source/rtl/experimental/ddr_adaptive_result_writer.v']=ROOT/'rtl/ddr_adaptive_result_writer.v'
        compiled=[]
        for name,p in selected.items():
            raw=p.read_bytes();report['source_sha256'][str(p)]=sha(p)
            def inc(m):
                original=m.group(1).decode().replace('\\','/')
                rel=original.split('/native/',1)[1] if '/native/' in original else 'source/rtl/'+original.split('/rtl/',1)[-1]
                if rel not in selected:
                    if original in ('video_crc32.vh','gamma_curves.vh'):
                        rel=next(k for k in HEADERS if k.endswith('/'+original))
                    else:raise ValueError('Unbound include: '+original)
                return ('`include "'+(work/'compiled'/Path(rel).name).as_posix()+'"').encode()
            raw=re.sub(rb'`include\s+"([^"\r\n]+)"',inc,raw)
            dest=work/'compiled'/Path(name).name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(raw)
            if name in NAMES:compiled.append(str(dest))
        bench=ROOT/'tests/tb_engine_throughput.sv';report['source_sha256'][str(bench)]=sha(bench)
        compiled.append(str(bench))
        tools=args.vivado_bin
        steps=[('compile','xvlog.bat',['--sv',*compiled]),('elaborate','xelab.bat',['tb_engine_throughput','-s','engine']),
               ('simulate','xsim.bat',['engine','-runall','-log','simulation.log'])]
        for stage,exe,argv in steps:
            cmd=[str(tools/exe),*argv]
            report['commands'].append({'stage':stage,'argv':cmd})
            t=time.monotonic()
            with (work/(stage+'.log')).open('wb') as log:
                p=subprocess.run(cmd,cwd=work,stdout=log,stderr=subprocess.STDOUT,timeout=args.timeout)
            report['commands'][-1].update(returncode=p.returncode,seconds=time.monotonic()-t)
            if p.returncode:raise RuntimeError(stage+' failed; see '+str(work/(stage+'.log')))
        log=(work/'simulation.log').read_text(errors='replace')
        if 'PASS ENGINE_THROUGHPUT' not in log or re.search(r'(?im)^\s*(fatal|error):',log):raise RuntimeError('Simulation PASS absent or error present')
        report['metrics']=json.loads((work/'engine-summary.json').read_text())
        report['metrics']['processing_ms_at_125MHz']=report['metrics']['cycles']/125000
        report['metrics']['processing_capacity_fps_at_125MHz']=125000000/report['metrics']['cycles']
        report['output_sha256']=sha(work/'output.mem')
        report['passed']=True
    except Exception as exc:
        report['error']=str(exc)
    report['elapsed_seconds']=time.monotonic()-start
    report['source_drift']=[p for p,h in report['source_sha256'].items() if sha(p)!=h]
    if report['source_drift']:report['passed']=False
    report['file_sha256']={p.name:sha(p) for p in work.glob('*') if p.is_file()}
    (work/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
    return 0 if report['passed'] else 1


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--variant',choices=('baseline','writer','cache','both'),required=True)
    p.add_argument('--width',type=int,default=1920);p.add_argument('--height',type=int,default=1080)
    p.add_argument('--pressure',action='store_true')
    p.add_argument('--work',type=Path,required=True)
    p.add_argument('--vivado-bin',type=Path,default=Path(os.environ.get('FPGA_VIVADO_BIN','D:/Vicado/Vivado/2017.4/bin')))
    p.add_argument('--timeout',type=int,default=1800)
    args=p.parse_args()
    if args.width<16 or args.height<8 or args.width%16 or args.height%8 or args.width*args.height%256:
        p.error('geometry must meet the frame engine contract')
    raise SystemExit(run(args))
