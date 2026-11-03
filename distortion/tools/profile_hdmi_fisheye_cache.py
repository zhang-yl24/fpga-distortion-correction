"""Current C-map cache address study; estimates only, never measured FPS."""
import argparse
import hashlib
import json
from pathlib import Path
import time

import numpy as np
import generate_hdmi_fisheye_profile as profile

ROOT=Path(__file__).resolve().parents[1]


def trace(width=1920,height=1080,corrected=True,order='raster'):
    v,u=np.indices((height,width),dtype=np.int64)
    x,y,bad=profile.fixed_map(u*256,v*256,corrected,profile.config(width=width,height=height))
    # Identical full-footprint mask and signed floor as the RTL cache interface.
    bad=bad|(x<=-256)|(y<=-256)|(x>=width*256)|(y>=height*256)
    x=np.where(bad,-(1<<23),x)>>8;y=np.where(bad,-(1<<23),y)>>8
    blocks=np.empty((width*height,4),np.int32)
    for n,(dx,dy)in enumerate(((0,0),(1,0),(0,1),(1,1))):
        valid=(x+dx>=0)&(x+dx<width)&(y+dy>=0)&(y+dy<height)
        blocks[:,n]=np.where(valid,((y+dy)*width+x+dx)>>7,-1).ravel()
    if order=='tiled':
        if width%8 or height%8:raise ValueError('8x8 tile order requires aligned geometry')
        blocks=blocks.reshape(height//8,8,width//8,8,4).transpose(0,2,1,3,4).reshape(-1,4)
    elif order!='raster':raise ValueError('unknown query order')
    return blocks


def cache_trace(blocks,index_bits):
    tags=[-1]*(1<<index_bits);mask=len(tags)-1
    hits=misses=fast=slow=0;slow_valid=slow_invalid=0
    for row in blocks.tolist():
        if all(b<0 or tags[b&mask]==b for b in row):
            fast+=1;hits+=sum(b>=0 for b in row)
        else:
            slow+=1
            # Four neighbours are checked and captured in order. A fill may
            # evict another line; do not approximate this with unique blocks.
            for b in row:
                if b<0:slow_invalid+=1
                else:
                    slow_valid+=1
                    if tags[b&mask]==b:hits+=1
                    else:misses+=1;tags[b&mask]=b
    optimistic=fast+2*slow+4*slow_valid+slow_invalid+40*misses
    return {'index_bits':index_bits,'lines':len(tags),'logical_cache_pixel_bytes':len(tags)*256,
        'output_pixels':len(blocks),'all_hit_queries':fast,'slow_queries':slow,
        'valid_neighbour_hits':hits,'ddr_256byte_fills':misses,'fill_bytes':misses*256,
        'neighbour_miss_fraction':misses/(hits+misses)if hits+misses else 0,
        'scatter_core_cycles':misses*32,'optimistic_no_stall_core_cycles':optimistic,
        'optimistic_no_stall_frame_ms_at_125mhz':optimistic/125000,
        'omissions':'No measured DDR latency, miss-boundary pipeline drain, read arbitration, writer stalls, scan scheduling or placed timing.'}


def run(output,order='raster'):
    output=Path(output).resolve()
    if output.exists():raise ValueError('fresh output required')
    start=time.monotonic();rows=[]
    for mode in (True,False):
        blocks=trace(corrected=mode,order=order)
        for bits in (7,8,9,10):
            item={'mode':'corrected'if mode else'identity','query_order':order,**cache_trace(blocks,bits)};rows.append(item)
            print(json.dumps(item),flush=True)
    cal=profile.CALIBRATION
    value={'schema':'hdmi-camera-fisheye-address-profile-v1','hardware_measured':False,
        'calibration':profile.ref(cal),'size':[1920,1080],'query_order':order,'cache_source':profile.ref(ROOT/'rtl/experimental/ddr_neighbour_cache_scatter4_rowpipe.v'),
        'mapper_reference':profile.ref(Path(profile.__file__)),'configurations':rows,
        'elapsed_seconds':time.monotonic()-start,
        'limits':'Address-trace cache behavior only. These are planning bounds, not achieved FPS; compare baseline board counters before modifying RTL.'}
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('x',encoding='utf-8')as out:json.dump(value,out,indent=2)
    return value


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--order',choices=('raster','tiled'),default='raster');a=p.parse_args();run(a.output,a.order)
