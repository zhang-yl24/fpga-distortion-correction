"""Address locality only: investigate short cache bursts without changing RTL."""
from pathlib import Path
import importlib.util,json,sys
import numpy as np
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
from model.rotation import cordic,phase_from_degrees,inverse_rotate
spec=importlib.util.spec_from_file_location('brown',root/'tools/generate-brown-vectors.py')
brown=importlib.util.module_from_spec(spec);spec.loader.exec_module(brown)
config=json.loads((root/'results/calibration-fpga-candidate-20261006/candidate.json').read_text())['integer_config']
bound=json.loads((root/'results/rotation-domain-20261006.json').read_text())['guard_radius_squared_q22']
actual=json.loads((root/'results/lab-20261007/adaptive-native-check.json').read_text())
work=root/'build/short_burst_profile';work.mkdir(parents=True,exist_ok=True)
rows=[]
for angle in (30,90):
    path=work/f'pixel-indices-{angle}.npy'
    if path.exists():pixels=np.load(path)
    else:
        co,si=cordic(phase_from_degrees(angle));pixels=np.full((307200,4),-1,dtype=np.int32)
        for y in range(480):
            for x in range(640):
                u,v,bad=inverse_rotate(x*256,y*256,81792,61312,co,si)
                nx=brown.round_shift((u-config[0])*config[6],16);ny=brown.round_shift((v-config[1])*config[7],16)
                r2=brown.round_shift(nx*nx,22)+brown.round_shift(ny*ny,22)
                if bad or r2>bound:continue
                sx,sy,bad=brown.project(u,v,config)
                if bad:continue
                ix,iy=sx>>8,sy>>8
                for j,(dx,dy) in enumerate(((0,0),(1,0),(0,1),(1,1))):
                    if 0<=ix+dx<640 and 0<=iy+dy<480:pixels[y*640+x,j]=(iy+dy)*640+ix+dx
        np.save(path,pixels)
    order=[y*640+x for ty in range(0,480,8) for tx in range(0,640,8) for y in range(ty,ty+8) for x in range(tx,tx+8)]
    stream=pixels[order].reshape(-1);stream=stream[stream>=0].tolist()
    current=None
    for beats in (16,8,4,2):
        block_pixels=beats*16
        for bits in (4,5,6):
            tags=[-1]*(1<<bits);mask=(1<<bits)-1;misses=0
            for pixel in stream:
                block=pixel//block_pixels;slot=block&mask
                if tags[slot]!=block:tags[slot]=block;misses+=1
            row={'angle_deg':angle,'burst_beats':beats,'line_bytes':beats*32,'cache_lines':1<<bits,
                 'cache_bytes':(1<<bits)*beats*32,'read_bursts':misses,'payload_bytes':misses*beats*32}
            if beats==16 and bits==4:
                expected=next(f for f in actual['frames'] if f['angle_deg']==angle)['adaptive_read_bursts']
                assert misses==expected,(angle,misses,expected);current=row
            row['payload_reduction_from_current_percent']=100*(1-row['payload_bytes']/current['payload_bytes'])
            rows.append(row)
        print(f'Completed address trace angle={angle} burst_beats={beats}',flush=True)
out={'hardware_accessed':False,'current_trace_matches_native_rtl':True,'experiments':rows,
     'limits':'Address counts and payload only. Short bursts are not implemented; DDR fixed latency, arbitration, device timing and optical/high-resolution changes are not modeled. No physical bandwidth or FPS claim.'}
dest=root/'results/lab-20261007/short-burst-locality.json';dest.write_text(json.dumps(out,indent=2)+'\n')
print(str(dest))
