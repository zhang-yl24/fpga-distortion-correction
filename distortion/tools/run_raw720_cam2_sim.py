"""Source-bound new720 sensor admission -> guarded DDR -> complete mixed wire."""
from pathlib import Path
from datetime import datetime, timezone
import argparse, array, json, re, struct, sys, time, uuid, zlib
import build_raw720_cam2 as candidate
from run_gamma_pipeline_d5_sim import tool

ROOT=candidate.ROOT;APPROVED=candidate.APPROVED
TB='tests/tb_raw720_cam2.sv';RUNNER='tools/run_raw720_cam2_sim.py'

def audit_wire(path):
    data=Path(path).read_bytes();offset=0;statuses=[];raw=[];last_seq=0;last_uptime=0
    while offset<len(data):
        magic=data[offset:offset+8]
        if magic==b'PGSTAT02':
            packet=data[offset:offset+128]
            if len(packet)!=128 or struct.unpack_from('<HHI',packet,8)!=(128,2,candidate.BUILD_TAG) or packet[124:]!=b'ST02' or zlib.crc32(packet[:120])!=struct.unpack_from('<I',packet,120)[0]:raise ValueError('720 status CRC/identity/tail differs')
            u32=lambda n:struct.unpack_from('<I',packet,n)[0]
            seq=u32(108);uptime=u32(16)
            if not seq>last_seq or uptime<last_uptime:raise ValueError('720 status snapshot/uptime regressed')
            if u32(44) or u32(40) or packet[95]:raise ValueError('unexpected command/raw fault')
            statuses.append({'offset':offset,'snapshot_seq':seq,'uptime_ms':uptime,'accepted_seq':struct.unpack_from('<H',packet,26)[0],
                'opcode':packet[28],'result':packet[29],'flags':struct.unpack_from('<H',packet,30)[0],
                'accepted':u32(32),'rejected':u32(36),'admitted':u32(48),'completed':u32(52),'held_frame_id':u32(64),
                'source_crc':u32(68),'written_beats':u32(72),'camera_error':packet[94],'stop_reason':packet[104]})
            last_seq=seq;last_uptime=uptime;offset+=128
        elif magic==b'PGFRAME1':
            header=data[offset:offset+32]
            if len(header)!=32:raise ValueError('truncated raw header')
            _,w,h,ident,count,crc,fmt,hcrc=struct.unpack('<8sHHIIIII',header)
            if (w,h,ident,count,fmt)!=(1280,720,1,1843200,0x5651) or zlib.crc32(header[:28])!=hcrc:raise ValueError('720 raw dimensions/header differ')
            end=offset+32+count+12;payload=data[offset+32:offset+32+count];tail=data[offset+32+count:end]
            if len(tail)!=12 or tail[:8]!=b'PGEND001' or zlib.crc32(payload)!=crc or struct.unpack_from('<I',tail,8)[0]!=crc:raise ValueError('720 full raw CRC/trailer differs')
            pixels=array.array('H');pixels.frombytes(payload)
            if sys.byteorder!='little':pixels.byteswap()
            if len(pixels)!=921600 or any(p!=((0x4321^(i*53))&65535) for i,p in enumerate(pixels)):raise ValueError('720 independent921600 native pixel reference differs')
            if not any(s['accepted_seq']==3 and s['opcode']==16 and s['result']==1 for s in statuses):raise ValueError('raw preceded actual GRANT ACK status')
            raw.append({'offset':offset,'end_offset':end,'width':w,'height':h,'frame_id':ident,'payload_bytes':count,'crc32':f'{crc:08X}','pixels_verified':len(pixels)})
            offset=end
        else:raise ValueError('mixed wire boundary lost; never scan inside valid pixel payload')
    if len(raw)!=1 or len(statuses)<5:raise ValueError('one complete720 frame plus control/status proof required')
    last=statuses[-1]
    if (last['accepted_seq'],last['opcode'],last['result'],last['accepted'],last['rejected'],last['admitted'],last['completed'],last['held_frame_id'],last['written_beats'])!=(5,17,1,3,2,1,1,1,57600):raise ValueError('final STOP/completion/control counts differ')
    if not last['flags']&0x8000 or last['flags']&0x3f0 or not last['flags']&0x4000 or not last['camera_error']:raise ValueError('source-fault status/idle ownership differs')
    if last['source_crc']!=int(raw[0]['crc32'],16):raise ValueError('completed DDR source CRC/status differs')
    return {'WireSHA256':candidate.sha(path),'Bytes':len(data),'StatusPackets':len(statuses),'RawFrames':raw,
            'FinalStatus':last,'AllCRCValid':True,'PixelsVerified':921600,'HardwareAccessed':False,
            'Limits':'Actual new sensor wrapper with real SCCB line model; nominal synthetic DVP and guarded DDR. Byte-ready/done and RX bit timing accelerated; not20s physical UART, camera clocks/fps/PLL or optical evidence.'}

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--timeout-seconds',type=int,default=1800);args=parser.parse_args()
    if type(args.timeout_seconds) is not int or not 300<=args.timeout_seconds<=1800:parser.error('300..1800s bounded offline run required')
    prepared=candidate.verify_sources();names=prepared['source_files']+['tools/build_raw720_cam2.py',RUNNER,TB]
    before={n:candidate.sha(ROOT/n) for n in names}
    protected={}
    for target in ['corrected_gamma_pipeline_d5','gamma_capture_k320_dev',candidate.BASE]:
        document=candidate.load(ROOT/f'board/{target}-sources.json');paths=document if isinstance(document,list) else document['source_files']
        protected.update({n:candidate.sha(ROOT/n) for n in paths})
    protected.update({n:candidate.sha(ROOT/n) for n in ['tools/prepare_gamma_pipeline_d5.py','tools/run_gamma_pipeline_d5_sim.py','tools/build_gamma_pipeline_d5.py']})
    work=APPROVED/('raw720-cam2-sim-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'-'+uuid.uuid4().hex[:6]);work.mkdir(exist_ok=False)
    report={'Target':candidate.TARGET,'Passed':False,'HardwareAccessed':False,'PDSAccessed':False,'SourceSHA256':before,
        'PreparedSHA256':candidate.sha(ROOT/f'board/{candidate.TARGET}-sources.json'),'ProtectedBefore':protected,'Workdir':str(work)}
    try:
        bin_dir=Path(r'E:/Vivado/Vivado/2017.4/bin');deadline=time.monotonic()+args.timeout_seconds
        files=[n for n in names if n.endswith(('.v','.sv'))]
        for exe,argv,stage in [('xvlog.bat',['--sv',*[str(ROOT/n) for n in files]],'compile'),
            ('xelab.bat',['tb_raw720_cam2','-s','raw720_cam2_tb'],'elaborate'),
            ('xsim.bat',['raw720_cam2_tb','-runall','-log','simulation.log'],'simulate')]:
            report['Stage']=stage;tool(bin_dir,exe,argv,work,deadline,stage)
        text=(work/'simulation.log').read_text(errors='replace')
        if not all(n in text for n in ['PASS720 mode:','PASS720 transport:','PASS raw720 CAM2 candidate integration;']) or re.search(r'(?im)^\s*(fatal|error):',text):raise ValueError('complete720 integration did not pass')
        report.update(Passed=True,WireAudit=audit_wire(work/'raw720-cam2-stream.bin'),PassLines=[line for line in text.splitlines() if line.startswith('PASS')])
    except (Exception,KeyboardInterrupt) as exc:report['Error']=type(exc).__name__+': '+str(exc)
    finally:
        report['SourceSHA256After']={n:candidate.sha(ROOT/n) for n in names};report['ProtectedAfter']={n:candidate.sha(ROOT/n) for n in protected}
        if before!=report['SourceSHA256After'] or protected!=report['ProtectedAfter']:report.update(Passed=False,SourceDrift=True)
        report['LogSHA256']={p.name:candidate.sha(p) for p in work.glob('*.log')}
        output=work/'raw720-cam2-simulation.json';candidate.write_new(output,report)
        print(json.dumps({k:v for k,v in report.items() if not k.startswith(('Protected','SourceSHA'))},indent=2));print(output)
    return 0 if report['Passed'] else 1
if __name__=='__main__':raise SystemExit(main())
