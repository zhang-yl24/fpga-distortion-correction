"""Address-trace study only: tiled traversal requires a future reorder buffer."""
from pathlib import Path
import importlib.util,json,sys
import numpy as np
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
from model.rotation import cordic,phase_from_degrees,inverse_rotate
spec=importlib.util.spec_from_file_location('brown',root/'tools/generate-brown-vectors.py')
brown=importlib.util.module_from_spec(spec);spec.loader.exec_module(brown)
c=json.loads((root/'results/calibration-fpga-candidate-20261006/candidate.json').read_text())['integer_config']
bench=json.loads((root/'results/rotated-native-regression-20261006.json').read_text())
rows=[]
for angle,frame_index in ((30,1),(90,3)):
    co,si=cordic(phase_from_degrees(angle));blocks=[]
    for y in range(480):
        for x in range(640):
            u,v,bad=inverse_rotate(x*256,y*256,81792,61312,co,si)
            sx,sy,bad=brown.project(u,v,c);ix,iy=sx>>8,sy>>8
            blocks.append(tuple(((iy+dy)*640+ix+dx)//256 for dx,dy in ((0,0),(1,0),(0,1),(1,1)) if 0<=ix+dx<640 and 0<=iy+dy<480))
    def misses(bits,tile):
        tags=[-1]*(1<<bits);miss=0
        order=range(307200) if tile==1 else (y*640+x for ty in range(0,480,tile) for tx in range(0,640,tile) for y in range(ty,min(480,ty+tile)) for x in range(tx,min(640,tx+tile)))
        for index in order:
            for block in blocks[index]:
                slot=block&((1<<bits)-1)
                if tags[slot]!=block:tags[slot]=block;miss+=1
        return miss
    baseline=misses(3,1)
    assert baseline==bench['frames'][frame_index]['cache_misses'],(angle,baseline)
    for bits,tile in ((3,1),(4,1),(5,1),(3,4),(4,4),(4,8),(5,8),(4,16),(5,16)):
        count=misses(bits,tile)
        row={'angle_deg':angle,'cache_lines':1<<bits,'cache_kib':(1<<bits)/2,'output_tile_side':tile,
            'read_bursts':count,'read_payload_mib':count*512/(1<<20),'burst_reduction_percent':100*(baseline-count)/baseline,
            'implemented_in_current_bitstream':bits==3 and tile==1}
        rows.append(row)
        print(f'angle={angle}, cache_lines={1<<bits}, tile={tile}, bursts={count}, reduction={row["burst_reduction_percent"]:.1f}%',flush=True)
out={'address_trace_matches_current_native_rtl_misses':True,'experiments':rows,'hardware_accessed':False,
    'limits':'Memory-address locality only; not RTL speed, physical bandwidth or FPS. Tiled output breaks the current raster writer contract and needs a stripe/tile reorder buffer before publication, CRC and DDR writes. None of the larger-cache/tiled variants is integrated. Must measure physical frame rate before selecting next optimization.'}
(root/'results/cache-locality-study-20261006.json').write_text(json.dumps(out,indent=2)+'\n')
