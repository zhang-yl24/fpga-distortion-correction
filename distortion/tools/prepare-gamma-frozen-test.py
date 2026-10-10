"""Independent small full-packet references: dark, bright and neutral sources."""
from pathlib import Path
import importlib.util,json,sys,zlib
import numpy as np
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
from model.reference import bilinear_u8
spec=importlib.util.spec_from_file_location('brown',root/'tools/generate-brown-vectors.py');brown=importlib.util.module_from_spec(spec);spec.loader.exec_module(brown)
work=root/'build/gamma_frozen_capture_sim';work.mkdir(exist_ok=True)
w,h=32,16;yy,xx=np.indices((h,w),dtype=np.uint32)
c=[3968,1920,4096,1920,8192,8192,1<<25,1<<25,-524288,0,0,0,0]
sources=[];results=[];tones=[];reference=[]
tables={bits:[[round((v/((1<<bits)-1))**g*((1<<bits)-1)) for v in range(1<<bits)] for g in (1,.65,1.45)] for bits in (5,6)}
for phase,mode in enumerate((1,2,0)):
    pattern=(xx+yy)%4
    if phase==0:r=pattern+2;g=pattern*2+4;b=pattern+1
    elif phase==1:r=31-pattern;g=63-pattern*2;b=31-pattern
    else:r=15+pattern%2;g=30+pattern;b=15+pattern%2
    raw=((r<<11)|(g<<5)|b).astype('<u2')
    rgb=np.stack(((r<<3)|(r>>2),(g<<2)|(g>>4),(b<<3)|(b>>2)),axis=-1).astype(np.uint8)
    before=[];after=[];mask=[]
    for y in range(h):
        for x in range(w):
            sx,sy,bad=brown.project(x*256,y*256,c);ix,iy=sx>>8,sy>>8
            masked=bad or sx<=-256 or sy<=-256 or sx>=w*256 or sy>=h*256
            neighbours=[rgb[iy+dy,ix+dx] if 0<=ix+dx<w and 0<=iy+dy<h else np.zeros(3,dtype=np.uint8) for dx,dy in ((0,0),(1,0),(0,1),(1,1))]
            v=bilinear_u8(*neighbours,sx&255,sy&255)
            p=((int(v[0])>>3)<<11)|((int(v[1])>>2)<<5)|(int(v[2])>>3)
            before.append(p);mask.append(masked)
            after.append(0 if masked else (tables[5][mode][p>>11]<<11)|(tables[6][mode][(p>>5)&63]<<5)|tables[5][mode][p&31])
    p=np.array(before,dtype='<u2');rr=(p>>11).astype(np.int64);gg=((p>>5)&63).astype(np.int64);bb=(p&31).astype(np.int64)
    y=(77*(rr*8+(rr>>2))+150*(gg*4+(gg>>4))+29*(bb*8+(bb>>2)))>>8;y=y[~np.array(mask)]
    decision=1 if np.count_nonzero(y<64)>=(len(y)+1)//2 else 2 if np.count_nonzero(y>=192)>=(len(y)+1)//2 else 0
    assert len(y)>=w*h//4 and decision==mode
    payloads=(raw.tobytes(),p.tobytes(),np.array(after,dtype='<u2').tobytes())
    for dest,payload in zip((sources,results,tones),payloads):dest.extend(int.from_bytes(payload[i:i+32],'little') for i in range(0,len(payload),32))
    reference.append({'source_phase':phase,'mode':mode,'crcs':[zlib.crc32(v) for v in payloads],'source_kind':'synthetic_same_source'})
for name,values in (('source.mem',sources),('result.mem',results),('tone.mem',tones)):(work/name).write_text(''.join(f'{v:064x}\n' for v in values))
(work/'reference.json').write_text(json.dumps({'shape':[h,w],'frames':reference,'parameters':c,'limits':'Synthetic frozen-source validation; no board target or physical light-quality claim.'},indent=2)+'\n')
t=(root/'tests/tb_ddr_corrected_capture.sv').read_text().replace('tb_ddr_corrected_capture','tb_gamma_frozen_capture').replace('ddr_corrected_capture #','gamma_frozen_capture #')
t=t.replace('frozen[0:95];','frozen[0:95],tones[0:95],locked_source[0:31];')
start=t.index('            if(dut.engine_start) begin');end=t.index('            if(awvalid && awready)',start)
t=t[:start]+'''            if(dut.engine_start) begin
                active_phase=pairs_completed;
                if(memory[0]!==source[active_phase*32]) $fatal(1,"Unknown frozen source phase=%0d",active_phase);
                if(dut.process_pass==0) for(i=0;i<32;i=i+1) locked_source[i]=memory[i];
            end
            if(dut.state!=0 && dut.state!=1) for(i=0;i<32;i=i+1)
                if(memory[i]!==locked_source[i]) $fatal(1,"Source changed between before/after processing or export");
''' + t[end:]
t=t.replace('wi=0,ri=0','wi=0,ri=0,wlen=0,rlen=0')
t=t.replace('wi==15','wi==wlen').replace('ri==15','ri==rlen')
t=t.replace('wbase=awaddr/8;wi=0;writing=1;','wbase=awaddr/8;wi=0;wlen=awlen;writing=1;')
t=t.replace('rbase=araddr/8;ri=0;reading=1;','rbase=araddr/8;ri=0;rlen=arlen;reading=1;')
t=t.replace('awlen!=15 || awaddr%128','(awlen!=15 && awlen!=7) || awaddr%64').replace('arlen!=15 || araddr%128','(arlen!=15 && arlen!=7) || araddr%64')
t=t.replace('if(dut.state>=3) $fatal','if(dut.state!=1 && dut.state!=2) $fatal')
t=t.replace('wdata!==golden[active_phase*32+(wbase%64)+wi]', 'wdata!==(dut.process_pass==2 ? tones[active_phase*32+(wbase%64)+wi]:golden[active_phase*32+(wbase%64)+wi])')
t=t.replace('if(dut.state>=3 && dut.state<=7)', 'if(dut.state==3 || dut.state==4 || dut.state==5 || dut.state==6 || dut.state==7 || dut.state==9 || dut.state==10)')
t=t.replace('(1+camera_frame%2)*32','(pairs_completed%3)*32')
t=t.replace('$readmemh("result.mem",golden);','$readmemh("result.mem",golden);$readmemh("tone.mem",tones);')
t=t.replace('bytes!=6*(1024+44)','bytes!=9*(1024+44)')
t=t.replace('PASS raw/corrected pair export: three camera/remap transactions, changing source bank, immutable raw/result ownership, integer-model corrected beats, DDR stalls, UART stalls and six complete binary packets.', 'PASS frozen Gamma capture: three dark/bright/neutral source transactions, nine complete CRC packets, two bypass warmup passes, enhanced pixels, immutable source and export banks, DDR/UART stalls.')
(root/'tests/tb_gamma_frozen_capture.sv').write_text(t)
print('Prepared three synthetic scene modes and independent full UART-packet references.')
