"""Address-trace estimate only: this is not measured DDR bandwidth or FPS."""
from pathlib import Path
import importlib.util
import json

root=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('brown_reference',Path(__file__).with_name('generate-brown-vectors.py'))
brown=importlib.util.module_from_spec(spec);spec.loader.exec_module(brown)
c=brown.parameters((-.24,.065,-.007,.003,-.002))
trace=[];valid_neighbours=0
for y in range(480):
    for x in range(640):
        sx,sy,_=brown.project(x*256,y*256,c);ix,iy=sx>>8,sy>>8
        for dx,dy in ((0,0),(1,0),(0,1),(1,1)):
            if 0<=ix+dx<640 and 0<=iy+dy<480:
                trace.append(((iy+dy)*640+ix+dx)>>8);valid_neighbours+=1
results=[]
for count in (8,16,32):
    tags=[None]*count;hits=misses=0
    for block in trace:
        index=block&(count-1)
        if tags[index]==block:hits+=1
        else:misses+=1;tags[index]=block
    # IDLE/RESULT plus SELECT, LOOKUP, LOAD, PICK for each valid neighbour;
    # invalid neighbours only SELECT. Misses add AR and at least 16 FILL cycles.
    minimum_cycles=307200*6+3*valid_neighbours+17*misses
    results.append({'cache_lines':count,'hits':hits,'misses':misses,
                    'miss_burst_bytes':misses*512,'minimum_no_stall_core_cycles':minimum_cycles,
                    'optimistic_minimum_frame_ms_at_125mhz':round(minimum_cycles/125000,3)})
result={'output_size':[640,480],'model':'synthetic Brown test, raster output',
        'trace_valid_neighbours':valid_neighbours,'configurations':results,
        'limits':'Address trace and state-machine lower bound only; omits actual DDR latency, arbitration, capture/output writes, and board timing. It is not measured throughput. This serial neighbourhood reader must be optimized for higher-resolution/high-FPS goals.'}
(root/'results/remap-cache-profile-20261006.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
