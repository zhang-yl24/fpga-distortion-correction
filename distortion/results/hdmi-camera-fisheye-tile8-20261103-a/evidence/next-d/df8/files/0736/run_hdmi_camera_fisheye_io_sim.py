"""Actual RGB565 quantizer and production UART pin test, independent host CRC."""
import argparse
from bisect import bisect_right
import hashlib
import json
from pathlib import Path
import sys
import time

import hdmi_camera_fisheye_fps as fps
import run_hdmi_camera_snapshot_uart_wire_sim as simulator
from simulation_tools import resolve_vivado_bin

ROOT=Path(__file__).resolve().parents[1]
COMPILE=('rtl/uart_tx.v','rtl/experimental/hdmi_camera_fisheye_status_uart.v',
         'rtl/experimental/hdmi_camera_rgb565_quantizer.v','tests/tb_hdmi_camera_fisheye_io.sv')
BIT_CYCLES=(125000000+115200//2)//115200
SCHEMA='hdmi-camera-fisheye-io-simulation-v1'
sha=simulator.sha


def coverage(work):
    transitions=[tuple(map(int,line.split()))for line in (work/'uart-edges.txt').read_text().splitlines()]
    assert transitions and transitions[0][1]==0
    positions=[r[0]for r in transitions];levels=[r[1]for r in transitions]
    assert positions==sorted(set(positions)) and all(a!=b for a,b in zip(levels,levels[1:]))
    def level(t):
        i=bisect_right(positions,t)-1
        return levels[i]if i>=0 else 1
    result=bytearray();starts=[];cursor=0
    while len(result)<96:
        i=bisect_right(positions,cursor)
        while i<len(positions)and levels[i]!=0:i+=1
        assert i<len(positions),'missing UART start'
        start=positions[i];bits=[level(start+BIT_CYCLES*(j+.5))for j in range(10)]
        assert bits[0]==0 and bits[9]==1
        # Every transition inside the character must be on a bit boundary.
        assert all((p-start)%BIT_CYCLES==0 for p in positions if start<=p<start+BIT_CYCLES*10)
        result.append(sum(bits[j+1]<<j for j in range(8)));starts.append(start)
        cursor=start+BIT_CYCLES*10-1
    tb=bytes(int(line,16)for line in (work/'uart-decoded.txt').read_text().splitlines())
    assert bytes(result)==tb,'independent pin and TB decoders differ'
    parser=fps.Parser();frames=parser.feed(result)
    assert len(frames)==1 and parser.rejected==parser.discarded==0
    f=frames[0]
    assert all(f[k]==v for k,v in {'source_frames':6,'captured_frames':5,'processed_frames':4,
        'unique_presented_frames':3,'scan_refreshes':30,'last_process_cycles':5000000,
        'cache_hits':1,'cache_misses':2,'queries':3,'scan_good_frames':4,'scan_repeat_frames':5,
        'scan_blank_frames':6,'corrected_requested':True,'failed':False,'fault':0,'status_valid':True}.items())
    log=(work/'simulation.log').read_text(encoding='utf-8')
    assert 'QUANTIZER_ALL_256_VALUES_AND_MATCHED_TIMING_PASS'in log
    assert 'FISHEYE_STATUS_REAL_125MHZ_115200_8N1_PASS bytes=96'in log and '$finish called'in log
    assert 'Fatal:'not in log
    return {'ActualUARTPinDecodePassed':True,'ActualQuantizerAll256ValuesAndTimingPassed':True,
        'AtomicSnapshotUnaffectedByLaterCounterAndFaultChanges':True,'Bytes':len(result),
        'BitCycles':BIT_CYCLES,'ActualBaud':125000000/BIT_CYCLES,'DecodedFrame':f,
        'DecodedWireSHA256':hashlib.sha256(result).hexdigest()}


def run(work):
    work=Path(work).resolve();assert work.is_relative_to(ROOT/'work')and not work.exists()
    binary=resolve_vivado_bin(ROOT.parent).resolve();work.mkdir(parents=True)
    watched={str(ROOT/name):sha(ROOT/name)for name in COMPILE}
    for p in (Path(__file__).resolve(),Path(fps.__file__),Path(simulator.__file__),
              Path(sys.executable),binary/'xvlog.bat',binary/'xelab.bat',binary/'xsim.bat'):
        watched[str(p)]=sha(p)
    for name in COMPILE:
        p=work/'compiled'/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes((ROOT/name).read_bytes())
    started=time.monotonic();result={'Schema':SCHEMA,'Passed':False,'SourceSHA256':watched,
                                    'HardwareAccessed':False,'PDSAccessed':False}
    commands=[('xvlog.bat',['--sv',*[str(work/'compiled'/n)for n in COMPILE]],'compile'),
        ('xelab.bat',['tb_hdmi_camera_fisheye_io','-s','fisheye_io','--timescale','1ns/1ps'],'elaborate'),
        ('xsim.bat',['fisheye_io','-runall','-log','simulation.log'],'simulate')]
    try:
        for name,args,stage in commands:simulator.tool(binary,name,args,work,started+180,stage)
        result.update(coverage(work));result['Passed']=True
    except BaseException as e:result['Error']=type(e).__name__+': '+str(e)
    result['SourceDrift']=[p for p,h in watched.items()if sha(p)!=h]
    result['Passed']=result['Passed']and not result['SourceDrift']
    result['ElapsedSeconds']=time.monotonic()-started
    result['Artifacts']={p.relative_to(work).as_posix():sha(p)for p in work.rglob('*')if p.is_file()}
    with(work/'simulation.json').open('x',encoding='utf-8')as out:json.dump(result,out,indent=2)
    return result


def verify(path):
    path=Path(path).resolve();r=json.loads(path.read_text());assert r['Schema']==SCHEMA and r['Passed']
    watched={Path(p):h for p,h in r['SourceSHA256'].items()}
    assert all(p.is_file()and sha(p)==h for p,h in watched.items())
    assert not r['SourceDrift']and all(r.get(k)==v for k,v in coverage(path.parent).items())
    for name,h in r['Artifacts'].items():
        p=path.parent/name;assert sha(p)==h;watched[p]=h
    watched[path]=sha(path);return r,watched


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work-dir',type=Path);p.add_argument('--verify',type=Path);a=p.parse_args()
    r=verify(a.verify)[0]if a.verify else run(a.work_dir)
    print(json.dumps({k:r.get(k)for k in ('Passed','ElapsedSeconds','Error','DecodedFrame')}))
    raise SystemExit(0 if r['Passed']else 1)
