"""Full 1080p RTL-to-independent-reference comparison and measured cycle budget."""
from pathlib import Path
import argparse, hashlib, json, re, subprocess, time, zlib
import numpy as np
from prepare_candidate import prepare,HERE
from fisheye_integer_reference import integer_map

def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def reference(map_path,corrected):
    w,h=1920,1080
    if corrected:
        coords=np.load(map_path).astype(np.int64);x,y=coords[:,:,0],coords[:,:,1]
    else:
        y,x=np.indices((h,w),dtype=np.int64);x=x*256;y=y*256
    ix,iy=x//256,y//256;fx=x%256;fy=y%256
    channels=[]
    for dx,dy in [(0,0),(1,0),(0,1),(1,1)]:
        xx,yy=ix+dx,iy+dy;index=yy*w+xx
        value=((index*13)^(index>>3)^0x5a31)&0xffff
        value=np.where((xx>=0)&(xx<w)&(yy>=0)&(yy<h),value,0)
        r=(value>>11)&31;g=(value>>5)&63;b=value&31
        channels.append(np.stack([(r<<3)|(r>>2),(g<<2)|(g>>4),(b<<3)|(b>>2)],axis=-1))
    wx=fx[:,:,None];wy=fy[:,:,None]
    rgb=((channels[0]*(256-wx)+channels[1]*wx)*(256-wy)+(channels[2]*(256-wx)+channels[3]*wx)*wy+32768)>>16
    rgb=np.where(((x<=-256)|(y<=-256)|(x>=w*256)|(y>=h*256))[:,:,None],0,rgb)
    return (((rgb[:,:,0]>>3)<<11)|((rgb[:,:,1]>>2)<<5)|(rgb[:,:,2]>>3)).astype('<u2')

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--work',type=Path,required=True)
    p.add_argument('--map',type=Path,help='Optional precomputed integer map; generated from the frozen C profile by default');p.add_argument('--tile-width',type=int,default=8,choices=(8,32))
    p.add_argument('--read-latency',type=int,default=12);p.add_argument('--pressure',action='store_true');p.add_argument('--raw',action='store_true')
    p.add_argument('--cache-index-bits',type=int,choices=(7,8,9,10))
    p.add_argument('--cache-profile',choices=('rowpad','balanced'),default='rowpad')
    p.add_argument('--ddr-fanout16',action='store_true')
    p.add_argument('--test-top-rows',type=int,help='Simulation-only lane split experiment, multiple of eight')
    p.add_argument('--vivado-bin',type=Path,default=Path('D:/Vicado/Vivado/2017.4/bin'));a=p.parse_args()
    work=a.work.resolve();receipt=prepare(work,a.tile_width,a.cache_index_bits,a.cache_profile,a.ddr_fanout16);compiled=work/'compiled';run=work/'sim';run.mkdir()
    if a.map is None:
        coords,_=integer_map(1920,1080,compiled/'board/hdmi-camera-fisheye-profile.vh',compiled/'board/hdmi-camera-fisheye-radial-table.vh')
        a.map=run/'integer-map.npy';np.save(a.map,coords)
    names=['rtl/mul32_pipe.v','rtl/bilinear_rgb.v','rtl/ddr_read_arbiter.v','rtl/ddr_write_arbiter.v',
           'rtl/experimental/ddr_adaptive_result_writer.v','rtl/experimental/ddr_neighbour_cache_scatter4_rowpipe.v',
           'rtl/experimental/ddr_remap_sample_scatter4_rowpipe.v','rtl/experimental/hdmi_camera_fisheye_mapper.v',
           'rtl/experimental/hdmi_camera_fisheye_rom.v','rtl/experimental/hdmi_camera_fisheye_core.v',
           'rtl/experimental/hdmi_camera_fisheye_lane.v','rtl/experimental/hdmi_camera_fisheye_engine.v']
    params={'TW':a.tile_width,'READ_LATENCY':a.read_latency,'PRESSURE':int(a.pressure),'CORRECTED':int(not a.raw)}
    testbench=run/'engine_full.sv'
    tb=(HERE/'tests/engine_full.sv').read_text(encoding='utf-8')
    assert 'TW=8,READ_LATENCY=12,PRESSURE=0,CORRECTED=1' in tb
    tb=tb.replace('TW=8,READ_LATENCY=12,PRESSURE=0,CORRECTED=1',','.join(f'{k}={v}' for k,v in params.items()))
    if a.test_top_rows is not None:
        if not 8<=a.test_top_rows<=1072 or a.test_top_rows%8:raise ValueError('Top rows must be an interior multiple of eight')
        tb=tb.replace('#(.TILE_W(TW)) dut',f'#(.TILE_W(TW),.TOP_ROWS({a.test_top_rows})) dut')
        params['test_top_rows']=a.test_top_rows
    testbench.write_text(tb,encoding='utf-8')
    sources=[compiled/n for n in names]+[testbench]
    commands=[['xvlog.bat','--sv',*[str(x) for x in sources]],
        ['xelab.bat','tb_fisheye60','-s','engine_full'],
        ['xsim.bat','engine_full','-runall']]
    report={'passed':False,'hardware_tested':False,'source_identity':receipt['source_identity'],'parameters':params,'cache_configuration':receipt['cache_configuration'],
            'sources':{str(x):digest(x) for x in sources},'map_sha256':digest(a.map),'commands':[]}
    try:
        for cmd in commands:
            start=time.monotonic();proc=subprocess.run([str(a.vivado_bin/cmd[0]),*cmd[1:]],cwd=run,capture_output=True,text=True,errors='replace',timeout=1800)
            output=proc.stdout+proc.stderr;log=run/(cmd[0]+'.log');log.write_text(output,encoding='utf-8')
            report['commands'].append({'command':cmd,'returncode':proc.returncode,'seconds':time.monotonic()-start,'log_sha256':digest(log)})
            if proc.returncode or re.search(r'(?im)^\s*(fatal|error)(?:\s|:|\[)',output):raise RuntimeError(cmd[0]+': '+output[-4000:])
            print(cmd[0]+' passed',flush=True)
        assert 'PASS FULL FISHEYE60' in output,'Completion marker absent'
        measured=json.loads((run/'engine-result.json').read_text());actual=np.fromfile(run/'output.bin',dtype='<u2').reshape(1080,1920)
        expected=reference(a.map,not a.raw)
        differences=np.flatnonzero(actual.ravel()!=expected.ravel())
        report['mismatched_pixels']=len(differences)
        if len(differences):
            report['first_mismatches']=[{'index':int(i),'expected':int(expected.ravel()[i]),'actual':int(actual.ravel()[i])} for i in differences[:16]]
            raise AssertionError(f'{len(differences)} pixel mismatches')
        expected_crc=zlib.crc32(expected.tobytes())
        assert measured['crc']==expected_crc,(measured['crc'],expected_crc)
        report.update(measured);report.update({'passed':True,'crc_matches':True,'output_sha256':digest(run/'output.bin'),
            'ms_at_125mhz':measured['cycles']/125000,'engine_fps_at_125mhz':125000000/measured['cycles'],
            'within_60fps_engine_budget':measured['cycles']<=125000000/60})
        print(json.dumps({k:v for k,v in report.items() if k not in ('sources','commands')},indent=2))
    except Exception as e:
        report['error']=str(e);raise
    finally:(work/'engine-report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')

if __name__=='__main__':main()
