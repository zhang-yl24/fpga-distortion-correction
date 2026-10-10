"""Reuse independent real-camera/arbitrary-angle pixel oracle; add exact tone/masks."""
from pathlib import Path
import argparse,json,sys,numpy as np
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
from model.rotation import cordic,phase_from_degrees
from model.reference import remap_fixed
parser=argparse.ArgumentParser();parser.add_argument('--dark-source',action='store_true');args=parser.parse_args()
name='gamma_native_tone' if args.dark_source else 'gamma_native'
work=root/'build'/(name+'_sim');work.mkdir(exist_ok=True)
src=root/'build/host_angle_native_sim'
ref=json.loads((src/'reference.json').read_text());c=json.loads((root/'results/calibration-fpga-candidate-20261006/candidate.json').read_text())['integer_config']
bound=json.loads((root/'results/rotation-domain-20261006.json').read_text())['guard_radius_squared_q22']
import shutil,zlib
count=3 if args.dark_source else 6
for filename in ('source.mem','rotations.mem'):
    if not args.dark_source:shutil.copy2(src/filename,work/filename)
    elif filename=='rotations.mem':(work/filename).write_text('\n'.join((src/filename).read_text().splitlines()[:count])+'\n')
y,x=np.indices((480,640),dtype=np.int64);rs=lambda v,n:(v+(1<<(n-1)))>>n
tables={bits:[np.array([round((v/((1<<bits)-1))**g*((1<<bits)-1)) for v in range(1<<bits)]) for g in (1,.65,1.45)] for bits in (5,6)}
previous=next_mode=0;frames=[];masks=[];goldens=[];crcs=[];modes=[]
original=(src/'result.mem').read_text().splitlines()
raw_source=(src/'source.mem').read_text().splitlines() if args.dark_source else []
source_words=[]
for i,f in enumerate(ref['frames'][:count]):
    co,si=cordic(phase_from_degrees(f['angle_deg']))
    u=rs(co*(x*256-81792)+si*(y*256-61312),30)+81792
    v=rs(-si*(x*256-81792)+co*(y*256-61312),30)+61312
    nx=rs((u-c[0])*c[6],16);ny=rs((v-c[1])*c[7],16)
    xx=rs(nx*nx,22);yy=rs(ny*ny,22);xy=rs(nx*ny,22);r2=xx+yy
    radial=2**22+rs((c[8]+rs((c[9]+rs(c[10]*r2,22))*r2,22))*r2,22)
    tx=rs(2*c[11]*xy+c[12]*(r2+2*xx),22);ty=rs(c[11]*(r2+2*yy)+2*c[12]*xy,22)
    sx=rs((rs(nx*radial,22)+tx)*c[4],22)+c[2];sy=rs((rs(ny*radial,22)+ty)*c[5],22)+c[3]
    mask=(r2>bound)|(sx<=-256)|(sy<=-256)|(sx>=640*256)|(sy>=480*256)
    raw=b''.join(int(line,16).to_bytes(32,'little') for line in original[i*19200:(i+1)*19200])
    p=np.frombuffer(raw,dtype='<u2').reshape(480,640)
    if args.dark_source:
        raw=b''.join(int(line,16).to_bytes(32,'little') for line in raw_source[i*19200:(i+1)*19200])
        original_pixels=np.frombuffer(raw,dtype='<u2').reshape(480,640)
        dark=((((original_pixels>>11)>>2)<<11)|((((original_pixels>>5)&63)>>2)<<5)|((original_pixels&31)>>2)).astype('<u2')
        payload=dark.tobytes();source_words.extend(int.from_bytes(payload[j:j+32],'little') for j in range(0,len(payload),32))
        r5=dark>>11;g6=(dark>>5)&63;b5=dark&31
        rgb=np.stack(((r5<<3)|(r5>>2),(g6<<2)|(g6>>4),(b5<<3)|(b5>>2)),axis=-1).astype(np.uint8)
        projected=remap_fixed(rgb,np.where(r2>bound,-(1<<23),sx)/256,np.where(r2>bound,-(1<<23),sy)/256).astype(np.uint16)
        p=(((projected[...,0]>>3)<<11)|((projected[...,1]>>2)<<5)|(projected[...,2]>>3)).astype('<u2')
    r=(p>>11).astype(np.int64);g=((p>>5)&63).astype(np.int64);b=(p&31).astype(np.int64)
    luminance=(77*((r<<3)|(r>>2))+150*((g<<2)|(g>>4))+29*((b<<3)|(b>>2)))>>8
    mode=next_mode;modes.append(mode)
    out=((tables[5][mode][r]<<11)|(tables[6][mode][g]<<5)|tables[5][mode][b]).astype('<u2')
    out[mask]=0
    samples=luminance[~mask];n=len(samples)
    decision=0 if n<307200//4 else 1 if int((samples<64).sum())>=(n+1)//2 else 2 if int((samples>=192).sum())>=(n+1)//2 else 0
    if decision==previous:next_mode=decision
    previous=decision
    payload=out.tobytes();crc=zlib.crc32(payload);crcs.append(crc)
    goldens.extend(int.from_bytes(payload[j:j+32],'little') for j in range(0,len(payload),32))
    masks.extend(mask.ravel().astype(int).tolist())
    frames.append({**f,'tone_mode':mode,'raw_statistic_decision':decision,'masked_pixels':int(mask.sum()),'crc32':f'{crc:08X}'})
for name,arr,digits in [('result.mem',goldens,64),('crcs.mem',crcs,8),('masks.mem',masks,1),('modes.mem',modes,1)]:
    (work/name).write_text(''.join(f'{v:0{digits}x}\n' for v in arr))
if args.dark_source:
    assert modes==[0,0,1],modes
    (work/'source.mem').write_text(''.join(f'{v:064x}\n' for v in source_words))
name='gamma_native_tone' if args.dark_source else 'gamma_native'
(work/'reference.json').write_text(json.dumps({'frames':frames,'pixels':count*307200,'synthetically_darkened_source':args.dark_source,'scope':'Independent Brown/rotation/interpolation plus exact Gamma/mask oracle. Darkened source is a synthetic channel reduction of real-camera data, not a physical low-light measurement.'},indent=2)+'\n')
tb=(root/'tests/tb_host_angle_native_regression.sv').read_text().replace('tb_host_angle_native_regression','tb_'+name).replace('adaptive_tiled_frame_engine #','adaptive_gamma_frame_engine #')
tb=tb.replace('integer phase=0;', 'integer phase=0;wire [1:0] gamma_mode;wire [31:0] gamma_frames;reg [1:0] modes[0:5];reg masks[0:1843199];')
tb=tb.replace('.source_base(28\'d0)',".gamma_enable(1'b1),.gamma_mode(gamma_mode),.gamma_frames(gamma_frames),.source_base(28'd0)")
tb=tb.replace('if(failed) $fatal','if(dut.result_valid && dut.result_ready && dut.result_masked!==masks[phase*307200+dut.result_tag])$fatal(1,"Native geometry mask mismatch");\n            if(failed) $fatal')
tb=tb.replace('$readmemh("source.mem",source);','$readmemh("masks.mem",masks);$readmemh("modes.mem",modes);$readmemh("source.mem",source);')
tb=tb.replace('            if(completed_base!=','            if(gamma_mode!==modes[phase] || gamma_frames!=phase+1)$fatal(1,"Native Gamma mode/count mismatch");\n            if(completed_base!=')
if args.dark_source:tb=tb.replace('[0:5]','[0:2]').replace('[0:115199]','[0:57599]').replace('phase<6','phase<3').replace('1843200','921600').replace('1843199','921599')
tb=tb.replace('PASS adaptive native regression:','PASS Gamma native regression:')
(root/'tests'/('tb_'+name+'.sv')).write_text(tb)
runner=(root/'tools/run-gamma-frame-sim.ps1').read_text().replace('gamma_frame_sim',name+'_sim').replace('tb_gamma_frame','tb_'+name).replace('PASS Gamma integrated regression:','PASS Gamma native regression:')
runner=runner.replace("'build\\"+name+"_sim\\config.vh'","'board\\calibration-trial.vh','board\\rotation-domain.vh'")
(root/'tools'/('run-'+name.replace('_','-')+'-sim.ps1')).write_text(runner)
print('Prepared',count,'full native Gamma frames,',count*307200,'pixels, modes:',modes)
