"""Receive-only PGHFPS02 diagnostics: refresh is separate from new-frame FPS."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import struct
import time
import zlib

MAGIC=b'PGHFPS02'
PACKET=struct.Struct('<8sBBHIQ14IQII')
CORE_HZ=125_000_000
PROFILE_ID=0xed59f83e3cfbc77b
BUILD_ID=0x11036003
# prepare variants: rowpad640, historical rowpad544, uniform7/8/9/10,
# tile32 and fanout16. Explicit selection always enforces one exact identity.
SUPPORTED_BUILD_IDS=frozenset(base+tile+fanout
    for base in (0x11036002,0x11036003,0x11036007,0x11036008,0x11036009,0x1103600a)
    for tile in (0,0x100) for fanout in (0,0x1000))


def checked_build_id(value):
    if type(value) is not int or value not in SUPPORTED_BUILD_IDS:
        raise ValueError('unsupported build ID; choose an exact prepared candidate ID')
    return value


def build_id_argument(value):
    try:
        return checked_build_id(int(value,16))
    except (TypeError,ValueError) as error:
        raise argparse.ArgumentTypeError('expected a supported 8-digit hexadecimal BuildID, e.g. 11036003') from error


def validate_identities(frames,expected_build_id=BUILD_ID):
    expected=f'{checked_build_id(expected_build_id):08x}'
    if any(f.get('build_id')!=expected or f.get('profile_id')!=f'{PROFILE_ID:016x}' for f in frames):
        raise ValueError('build/profile identity changed or differs from the selected candidate')

COUNTERS=('source_frames','captured_frames','processed_frames','unique_presented_frames',
          'scan_refreshes','last_process_cycles','cache_hits','cache_misses','queries',
          'scan_good_frames','scan_repeat_frames','scan_blank_frames')


class Parser:
    def __init__(self,expected_build_id=BUILD_ID):
        self.expected_build_id=checked_build_id(expected_build_id)
        self.buffer=bytearray();self.rejected=0;self.discarded=0

    def feed(self,data):
        self.buffer.extend(data);result=[]
        while True:
            start=self.buffer.find(MAGIC)
            if start<0:
                n=max(0,len(self.buffer)-7);self.discarded+=n;del self.buffer[:n];break
            if start:self.discarded+=start;del self.buffer[:start]
            if len(self.buffer)<PACKET.size:break
            raw=bytes(self.buffer[:PACKET.size]);v=PACKET.unpack(raw)
            if not(v[1]==2 and v[2]&~7==0 and v[3]==96 and v[18]==0 and v[19]<=255 and
                   v[20]==PROFILE_ID and v[21]==self.expected_build_id and zlib.crc32(raw[:92])==v[22]):
                self.rejected+=1;del self.buffer[0];continue
            result.append({'sequence':v[4],'core_ticks':v[5],**dict(zip(COUNTERS,v[6:18])),
                           'status_valid':bool(v[2]&2),'failed':bool(v[2]&1),
                           'corrected_requested':bool(v[2]&4),'fault':v[19],
                           'profile_id':f'{v[20]:016x}','build_id':f'{v[21]:08x}'})
            del self.buffer[:96]
        return result


def summarize(frames,expected_build_id=BUILD_ID):
    validate_identities(frames,expected_build_id)
    if len(frames)<2:raise ValueError('at least two complete status samples required')
    if any(not f['status_valid'] or f['failed'] or f['fault'] for f in frames):
        raise ValueError('hardware reported an inactive or failed pipeline')
    if any(b['core_ticks']<=a['core_ticks'] for a,b in zip(frames,frames[1:])):
        raise ValueError('core timer stopped or reset during measurement')
    if len({f['corrected_requested'] for f in frames})!=1:
        raise ValueError('view mode changed during the FPS window; measure each mode separately')
    first,last=frames[0],frames[-1]
    seconds=(last['core_ticks']-first['core_ticks'])/CORE_HZ
    delta={key:(last[key]-first[key])&0xffffffff for key in COUNTERS if key!='last_process_cycles'}
    if any(delta[k]/seconds>1000 for k in ('source_frames','captured_frames','processed_frames',
                                          'unique_presented_frames','scan_refreshes')):
        raise ValueError('frame counter reset or implausible frame rate')
    rates={k+'_per_second':delta[k]/seconds for k in ('source_frames','captured_frames','processed_frames',
        'unique_presented_frames','scan_refreshes','scan_good_frames','scan_repeat_frames','scan_blank_frames')}
    return {'expected_build_id':f'{expected_build_id:08x}','profile_id':f'{PROFILE_ID:016x}','sample_count':len(frames),'hardware_window_seconds':seconds,'core_clock_hz':CORE_HZ,
        'clock_basis':'DDR IP PLL core clock; verify against this bitstream timing/PLL configuration',
        'corrected_requested':first['corrected_requested'],'counter_delta':delta,**rates,
        'last_process_cycles':last['last_process_cycles'],
        'last_process_seconds':last['last_process_cycles']/CORE_HZ,
        'cache_miss_fraction':delta['cache_misses']/(delta['cache_hits']+delta['cache_misses'])
            if delta['cache_hits']+delta['cache_misses'] else None,
        'cache_burst_fills_per_output_pixel':delta['cache_misses']/delta['queries'] if delta['queries'] else None,
        'limits':'Source and scan counters measure digital timing. Unique-presented counts complete new DDR result IDs; optical exposure FPS is not inferred.'}


def receive(output,seconds=30,port='COM7',program_receipt=None,expected_build_id=BUILD_ID):
    import serial
    output=Path(output).resolve()
    if output.exists() or not 2<=seconds<=600:raise ValueError('fresh output and 2..600 second window required')
    expected_build_id=checked_build_id(expected_build_id)
    output.mkdir(parents=True);parser=Parser(expected_build_id);frames=[];start=time.monotonic()
    result={'schema':'hdmi-camera-fisheye-live-fps-v1','started_utc':datetime.now(timezone.utc).isoformat(),
            'port':port,'baud':115200,'uart_transmit_bytes':0,'passed':False,'frames':frames,
            'expected_build_id':f'{expected_build_id:08x}','expected_profile_id':f'{PROFILE_ID:016x}'}
    if program_receipt is not None:
        receipt_path=Path(program_receipt).resolve()
        programmed=json.loads(receipt_path.read_text(encoding='utf-8-sig'))
        if not(programmed.get('Target')=='hdmi_camera_fisheye_top' and programmed.get('Passed') is True
              and programmed.get('DoneConfirmed') is True and programmed.get('FlashWritten') is False
              and programmed.get('ExpectedDeviceAndIDConfirmed') is True and programmed.get('CleanupErrors')==[]):
            raise ValueError('successful exact volatile fisheye programming receipt required')
        bit=Path(programmed['Bitstream']['Path'])
        if hashlib.sha256(bit.read_bytes()).hexdigest()!=programmed['Bitstream']['SHA256']:
            raise ValueError('programmed bitstream file changed')
        result['programmed_firmware']={'receipt':{'path':str(receipt_path),
            'sha256':hashlib.sha256(receipt_path.read_bytes()).hexdigest()},'bitstream':programmed['Bitstream'],
            'final_adf_sha256':programmed['FinalADFSHA256']}
    try:
        with serial.Serial(port=None,baudrate=115200,timeout=.1) as stream:
            stream.dtr=False;stream.rts=False;stream.port=port;stream.open()
            with (output/'wire.bin').open('xb') as wire:
                while time.monotonic()-start<seconds:
                    data=stream.read(4096);wire.write(data)
                    for frame in parser.feed(data):
                        frames.append(frame)
                        print(json.dumps({k:frame[k] for k in ('sequence','processed_frames',
                            'unique_presented_frames','scan_refreshes','failed','fault','corrected_requested')}),flush=True)
        result['summary']=summarize(frames,expected_build_id)
        if parser.rejected:raise ValueError('telemetry CRC/identity rejection during measurement')
        result['passed']=True
    except BaseException as error:result['error']=type(error).__name__+': '+str(error)
    result.update(ended_utc=datetime.now(timezone.utc).isoformat(),crc_rejected_packets=parser.rejected,
                  discarded_bytes=parser.discarded)
    wire=output/'wire.bin'
    if wire.exists():result['wire']={'path':str(wire),'sha256':hashlib.sha256(wire.read_bytes()).hexdigest()}
    with (output/'receipt.json').open('x',encoding='utf-8')as f:json.dump(result,f,indent=2,allow_nan=False)
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--seconds',type=float,default=30);p.add_argument('--port',default='COM7')
    p.add_argument('--program-receipt',type=Path,required=True)
    p.add_argument('--build-id',type=build_id_argument,default=BUILD_ID,help='exact prepared candidate BuildID in hex; default 11036003')
    a=p.parse_args()
    r=receive(a.output,a.seconds,a.port,a.program_receipt,a.build_id)
    print(json.dumps({k:r.get(k)for k in ('passed','summary','error','crc_rejected_packets')},indent=2))
    return 0 if r['passed']else 1


if __name__=='__main__':raise SystemExit(main())
