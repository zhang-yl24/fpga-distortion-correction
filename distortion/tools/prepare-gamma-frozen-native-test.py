"""Native frozen-source capture references, with calibrated Brown parameters."""
from pathlib import Path
import argparse,json,numpy as np,zlib,re
import sys
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
from model.reference import remap_fixed
parser=argparse.ArgumentParser();parser.add_argument('--work-name',default='gamma_frozen_native_sim');parser.add_argument('--radius-bound',type=int,default=0);args=parser.parse_args()
assert re.fullmatch(r'[A-Za-z0-9_]+',args.work_name) and 0<=args.radius_bound<1<<24
work=root/'build'/args.work_name;work.mkdir(exist_ok=True)
test_name='tb_'+args.work_name.removesuffix('_sim')
c=json.loads((root/'results/calibration-fpga-candidate-20261006/candidate.json').read_text())['integer_config']
w,h=640,480;y,x=np.indices((h,w),dtype=np.int64)
rs=lambda value,shift:(value+(1<<(shift-1)))>>shift
nx=rs((x*256-c[0])*c[6],16);ny=rs((y*256-c[1])*c[7],16)
xx=rs(nx*nx,22);yy=rs(ny*ny,22);xy=rs(nx*ny,22);r2=xx+yy
rad=(1<<22)+rs((c[8]+rs((c[9]+rs(c[10]*r2,22))*r2,22))*r2,22)
tx=rs(2*c[11]*xy+c[12]*(r2+2*xx),22);ty=rs(c[11]*(r2+2*yy)+2*c[12]*xy,22)
sx=rs((rs(nx*rad,22)+tx)*c[4],22)+c[2];sy=rs((rs(ny*rad,22)+ty)*c[5],22)+c[3]
domain=(r2>args.radius_bound) if args.radius_bound else np.zeros_like(r2,dtype=bool)
sx=np.where(domain,-(1<<23),sx);sy=np.where(domain,-(1<<23),sy)
mask=domain|(sx<=-256)|(sy<=-256)|(sx>=w*256)|(sy>=h*256)
assert np.all((sx>=-(1<<23))&(sx<(1<<23))&(sy>=-(1<<23))&(sy<(1<<23)))
tables={bits:[[round((v/((1<<bits)-1))**g*((1<<bits)-1)) for v in range(1<<bits)] for g in (1,.65,1.45)] for bits in (5,6)}
reference=[]
streams=[(work/name).open('w') for name in ('source.mem','result.mem','tone.mem')]
try:
    for phase,mode in enumerate((1,2,0)):
        pattern=(x+y)%4
        if phase==0:r=pattern+2;g=pattern*2+4;b=pattern+1
        elif phase==1:r=31-pattern;g=63-pattern*2;b=31-pattern
        else:r=15+pattern%2;g=30+pattern;b=15+pattern%2
        raw=((r<<11)|(g<<5)|b).astype('<u2')
        rgb=np.stack(((r<<3)|(r>>2),(g<<2)|(g>>4),(b<<3)|(b>>2)),axis=-1).astype(np.uint8)
        corrected=remap_fixed(rgb,sx/256,sy/256).astype(np.uint16)
        p=((corrected[...,0]>>3)<<11)|((corrected[...,1]>>2)<<5)|(corrected[...,2]>>3)
        assert not np.any(p[mask])
        t5=np.array(tables[5][mode],dtype=np.uint16);t6=np.array(tables[6][mode],dtype=np.uint16)
        toned=(t5[p>>11]<<11)|(t6[(p>>5)&63]<<5)|t5[p&31];toned[mask]=0
        rr=(p>>11).astype(np.int64);gg=((p>>5)&63).astype(np.int64);bb=(p&31).astype(np.int64)
        luminance=(77*(rr*8+(rr>>2))+150*(gg*4+(gg>>4))+29*(bb*8+(bb>>2)))>>8
        values=luminance[~mask];decision=1 if np.count_nonzero(values<64)>=(len(values)+1)//2 else 2 if np.count_nonzero(values>=192)>=(len(values)+1)//2 else 0
        assert len(values)>=w*h//4 and decision==mode
        payloads=[value.astype('<u2').tobytes() for value in (raw,p,toned)]
        for stream,payload in zip(streams,payloads):stream.write(''.join(f'{int.from_bytes(payload[i:i+32],"little"):064x}\n' for i in range(0,len(payload),32)))
        reference.append({'source_phase':phase,'mode':mode,'crcs':[zlib.crc32(value) for value in payloads],'source_kind':'synthetic_same_source'})
finally:
    for stream in streams:stream.close()
(work/'reference.json').write_text(json.dumps({'shape':[h,w],'frames':reference,'parameters':c,'radius_guard':args.radius_bound,'limits':'Native synthetic frozen-source validation. Uses calibration coefficients but synthetic light patterns, no physical image-quality claim.'},indent=2)+'\n')
names=('OUT_CX','OUT_CY','SRC_CX','SRC_CY','SRC_FX','SRC_FY','INV_FX','INV_FY','K1','K2','K3','P1','P2')
(work/'config.vh').write_text(''.join(f"`define CAP_{name} {24 if i<6 else 32}'sh{value&((1<<(24 if i<6 else 32))-1):x}\n" for i,(name,value) in enumerate(zip(names,c))))
t=(root/'tests/tb_gamma_frozen_capture.sv').read_text().replace('tb_gamma_frozen_capture',test_name)
t=t.replace('module '+test_name+';','module '+test_name+';\n    `include "'+(work/'config.vh').as_posix()+'"')
t=t.replace('.WIDTH(32),.HEIGHT(16),.BANK_STRIDE(512)','.WIDTH(640),.HEIGHT(480),.BANK_STRIDE(262144)')
t=t.replace('.BANK_STRIDE(262144))','.BANK_STRIDE(262144),.MAX_RADIUS_Q22('+str(args.radius_bound)+'))')
start=t.index('        .cfg_out_cx(');end=t.index('        .awaddr(',start)
ports=('out_cx','out_cy','src_cx','src_cy','src_fx','src_fy','inv_fx','inv_fy','k1','k2','k3','p1','p2')
t=t[:start]+'        '+','.join(f'.cfg_{port}(`CAP_{name})' for port,name in zip(ports,names))+',\n'+t[end:]
t=t.replace('memory[0:95],source[0:95],golden[0:95],frozen[0:95],tones[0:95],locked_source[0:31]','memory[0:51967],source[0:57599],golden[0:57599],frozen[0:51967],tones[0:57599],locked_source[0:19199]')
t=t.replace('active_phase*32','active_phase*19200').replace('(wbase%64)','(wbase-32768)').replace('wbase>=64','wbase>=32768')
t=t.replace('for(i=0;i<32;i=i+1)','for(i=0;i<19200;i=i+1)')
t=t.replace('if(dut.state!=0 && dut.state!=1)','if(dut.engine_start || dut.engine_done || dut.export_start)')
t=t.replace('for(i=0;i<96;i=i+1) frozen[i]=memory[i];','for(i=0;i<19200;i=i+1) begin frozen[i]=memory[i];frozen[32768+i]=memory[32768+i];end')
t=t.replace('if(dut.state==3 || dut.state==4 || dut.state==5 || dut.state==6 || dut.state==7 || dut.state==9 || dut.state==10)','if(dut.export_start || dut.export_done)')
t=t.replace('memory[64+i]','memory[32768+i]').replace('frozen[64+i]','frozen[32768+i]')
t=t.replace('awaddr<256 || (awaddr>=512 && awaddr<768)','awaddr<153600 || (awaddr>=262144 && awaddr<415744)')
t=t.replace('araddr<256 || (araddr>=512 && araddr<768)','araddr<153600 || (araddr>=262144 && araddr<415744)')
t=t.replace('row<16','row<480').replace('col<32','col<640')
t=t.replace('(pairs_completed%3)*32+(row*32+col)/16','(pairs_completed%3)*19200+(row*640+col)/16').replace('((row*32+col)%16)','((row*640+col)%16)')
t=t.replace('txwait=3+(bytes%11)','txwait=1+(bytes%3)')
t=t.replace('bytes!=9*(1024+44)','bytes!=9*(614400+44)').replace('#20000000','#2000000000')
t=t.replace('PASS frozen Gamma capture:', 'PASS native frozen Gamma capture:')
(root/'tests'/(test_name+'.sv')).write_text(t)
runner=(root/'tools/run-gamma-frozen-sim.ps1').read_text().replace('gamma_frozen_capture_sim',args.work_name).replace('tb_gamma_frozen_capture',test_name).replace('PASS frozen Gamma capture:', 'PASS native frozen Gamma capture:')
runner=runner.replace("'build\\"+args.work_name+"\\reference.json'", "'build\\"+args.work_name+"\\reference.json','build\\"+args.work_name+"\\config.vh'")
(root/'tools'/('run-'+args.work_name.removesuffix('_sim').replace('_','-')+'-sim.ps1')).write_text(runner)
print('Prepared native 640x480 dark/bright/neutral triplets and source/DDR/UART packet checks.')
