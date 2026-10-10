"""Independent small-frame rotation/Brown/tone/DDR oracle with tangential terms."""
from pathlib import Path
import importlib.util,json,sys,zlib,numpy as np
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
from model.rotation import cordic,phase_from_degrees,inverse_rotate
from model.reference import remap_fixed
spec=importlib.util.spec_from_file_location('brown',root/'tools/generate-brown-vectors.py')
brown=importlib.util.module_from_spec(spec);spec.loader.exec_module(brown)
work=root/'build/gamma_frame_sim';work.mkdir(exist_ok=True)
c=[3968]*4+[4608,4608]+[round(2**30/18)]*2+[round(v*2**22) for v in (-.05,.03,-.005,.002,-.001)]
bound=round(.49*2**22)
names='OUT_CX OUT_CY SRC_CX SRC_CY SRC_FX SRC_FY INV_FX INV_FY K1 K2 K3 P1 P2'.split()
(work/'config.vh').write_text(''.join(f"localparam signed [{bits-1}:0] CAL_{name}={bits}'sh{v&((1<<bits)-1):x};\n" for name,v,bits in zip(names,c,[24]*6+[32]*7))+f"localparam ROT_MAX_R2_Q22=32'd{bound};\n")
angles=[0,30,13.7,90,0,120,180,333.375,7.5,-23.45]
sources=[];goldens=[];masks=[];rotations=[];crcs=[];modes=[];frames=[]
previous=next_mode=0;y,x=np.indices((32,32))
tables={bits:[[round((v/((1<<bits)-1))**g*((1<<bits)-1)) for v in range(1<<bits)] for g in (1,.65,1.45)] for bits in (5,6)}
for f,angle in enumerate(angles):
    if f in (0,1,7):base=24
    elif f in (4,5):base=235
    elif f==6:base=0
    else:base=110
    variation=(x+3*y)%13
    r=np.clip(base+variation,0,255).astype(np.uint16);g=np.clip(base+variation//2,0,255).astype(np.uint16);b=np.clip(base+variation//3,0,255).astype(np.uint16)
    if f==6:r=g=b=np.zeros((32,32),dtype=np.uint16)
    raw=((r>>3)<<11)|((g>>2)<<5)|(b>>3)
    rgb=np.stack((((raw>>11)<<3)|((raw>>11)>>2),(((raw>>5)&63)<<2)|(((raw>>5)&63)>>4),((raw&31)<<3)|((raw&31)>>2)),axis=-1).astype(np.uint8)
    co,si=cordic(phase_from_degrees(angle));rotations.append((co&0xffffffff)<<32|(si&0xffffffff))
    sx=np.zeros((32,32),np.int64);sy=sx.copy();masked=np.zeros((32,32),bool)
    for yy in range(32):
        for xx in range(32):
            u,v,bad=inverse_rotate(xx*256,yy*256,3968,3968,co,si)
            nx=brown.round_shift((u-c[0])*c[6],16);ny=brown.round_shift((v-c[1])*c[7],16)
            r2=brown.round_shift(nx*nx,22)+brown.round_shift(ny*ny,22)
            px,py,fault=brown.project(u,v,c)
            if bad or fault or r2>bound:px=py=-(1<<23)
            sx[yy,xx]=px;sy[yy,xx]=py
            masked[yy,xx]=px<=-256 or py<=-256 or px>=8192 or py>=8192
    res=remap_fixed(rgb,sx/256,sy/256).astype(np.uint16)
    quant=((res[...,0]>>3)<<11)|((res[...,1]>>2)<<5)|(res[...,2]>>3)
    mode=next_mode;modes.append(mode)
    out=np.zeros((32,32),dtype='<u2')
    for yy in range(32):
        for xx in range(32):
            p=int(quant[yy,xx]);out[yy,xx]=0 if masked[yy,xx] else (tables[5][mode][p>>11]<<11)|(tables[6][mode][(p>>5)&63]<<5)|tables[5][mode][p&31]
    rr=quant>>11;gg=(quant>>5)&63;bb=quant&31
    # Promote before multiply: do not let uint16 sums wrap at white.
    rr=rr.astype(np.int64);gg=gg.astype(np.int64);bb=bb.astype(np.int64)
    luminance=(77*((rr<<3)|(rr>>2))+150*((gg<<2)|(gg>>4))+29*((bb<<3)|(bb>>2)))>>8
    sample=luminance[~masked];n=len(sample)
    decision=0 if n<256 else 1 if int((sample<64).sum())>=(n+1)//2 else 2 if int((sample>=192).sum())>=(n+1)//2 else 0
    if decision==previous:next_mode=decision
    previous=decision
    for payload,arr in ((raw.astype('<u2').tobytes(),sources),(out.tobytes(),goldens)):
        arr.extend(int.from_bytes(payload[j:j+32],'little') for j in range(0,len(payload),32))
    masks.extend(masked.ravel().astype(int).tolist());crc=zlib.crc32(out.tobytes());crcs.append(crc)
    frames.append({'angle_deg':angle,'tone_mode':mode,'raw_statistic_decision':decision,'masked_pixels':int(masked.sum()),'crc32':f'{crc:08X}','pixels':1024})
assert modes==[0,0,1,1,0,0,2,2,1,1],modes
for name,arr,digits in [('source.mem',sources,64),('result.mem',goldens,64),('crcs.mem',crcs,8),('rotations.mem',rotations,16),('masks.mem',masks,1),('modes.mem',modes,1)]:
    (work/name).write_text(''.join(f'{v:0{digits}x}\n' for v in arr))
(work/'reference.json').write_text(json.dumps({'frames':frames,'integer_config':c,'radius_q22':bound,'pixels':10240,'scope':'Synthetic small frames, nonzero radial and tangential terms, arbitrary rotation, integer interpolation and tone curves; no physical optical claim.'},indent=2)+'\n')
tb=(root/'tests/tb_host_angle_native_regression.sv').read_text()
tb=tb.replace('tb_host_angle_native_regression','tb_gamma_frame').replace('adaptive_tiled_frame_engine #','adaptive_gamma_frame_engine #')
tb=tb.replace('    `include "D:/English/FPGA/distortion/board/calibration-trial.vh"\n    `include "D:/English/FPGA/distortion/board/rotation-domain.vh"',f'    `include "{work.as_posix()}/config.vh"')
tb=tb.replace('[0:5]','[0:9]').replace('[0:115199]','[0:639]').replace('phase<6','phase<10')
for old,new in [('WIDTH(640)','WIDTH(32)'),('HEIGHT(480)','HEIGHT(32)'),('81792','3968'),('61312','3968'),('19200','64'),('307200','1024'),('1843200','10240'),('153600','512'),('415744','262656')]:tb=tb.replace(old,new)
tb=tb.replace('real-camera','synthetic-tone').replace('PASS adaptive native regression:','PASS Gamma integrated regression:')
tb=tb.replace('integer phase=0;',"integer phase=0;wire [1:0] gamma_mode;wire [31:0] gamma_frames;reg [1:0] modes[0:9];reg masks[0:10239];")
tb=tb.replace('.source_base(28\'d0)',".gamma_enable(1'b1),.gamma_mode(gamma_mode),.gamma_frames(gamma_frames),.source_base(28'd0)")
tb=tb.replace('if(failed) $fatal', 'if(dut.result_valid && dut.result_ready && dut.result_masked!==masks[phase*1024+dut.result_tag])$fatal(1,"Geometry mask tag mismatch");\n            if(failed) $fatal')
tb=tb.replace('$readmemh("source.mem",source);','$readmemh("masks.mem",masks);$readmemh("modes.mem",modes);$readmemh("source.mem",source);')
tb=tb.replace('            if(completed_base!=', '            if(gamma_mode!==modes[phase] || gamma_frames!=phase+1)$fatal(1,"Wrong frame-locked Gamma mode/count");\n            if(completed_base!=')
(root/'tests/tb_gamma_frame.sv').write_text(tb)
print('Prepared 10 complete 32x32 Gamma/remap/DDR frames, masks, CRCs and nonzero tangential oracle.')
