"""Board FPS with host monotonic arrival timing independent of PLL assumptions."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import time

import hdmi_camera_fisheye_fps as protocol


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def arrival_summary(frames):
    if len(frames)<10:raise ValueError('at least ten valid samples required for clock cross-check')
    first,last=frames[0],frames[-1]
    seconds=last['host_elapsed_seconds']-first['host_elapsed_seconds']
    if seconds<8:raise ValueError('host interval too short')
    deltas={k:(last[k]-first[k])&0xffffffff for k in protocol.COUNTERS if k!='last_process_cycles'}
    measured_mhz=(last['core_ticks']-first['core_ticks'])/seconds/1e6
    rates={k+'_per_second':deltas[k]/seconds for k in ('source_frames','captured_frames',
        'processed_frames','unique_presented_frames','scan_refreshes','scan_good_frames',
        'scan_repeat_frames','scan_blank_frames')}
    return {'host_window_seconds':seconds,'observed_core_mhz_from_uart_arrival':measured_mhz,
        'constrained_core_mhz':125.,'clock_cross_check_within_3percent':abs(measured_mhz-125.)/125.<.03,
        'host_timed_rates':rates,'last_process_ms_using_observed_clock':last['last_process_cycles']/measured_mhz/1000,
        'limits':'Independent host monotonic arrival interval; USB/UART buffering and scheduling introduce timing uncertainty. This is not a frequency-counter calibration.'}


def measure(output,receipt,seconds=30,port='COM7'):
    import serial
    output,receipt=Path(output).resolve(),Path(receipt).resolve()
    if output.exists()or not 12<=seconds<=600:raise ValueError('fresh directory and 12..600 seconds required')
    programmed=json.loads(receipt.read_text(encoding='utf-8-sig'))
    if not(programmed.get('Target')=='hdmi_camera_fisheye_top'and programmed.get('Passed')is True
        and programmed.get('DoneConfirmed')is True and programmed.get('FlashWritten')is False
        and programmed.get('ExpectedDeviceAndIDConfirmed')is True and programmed.get('CleanupErrors')==[]):
        raise ValueError('actual successful volatile fisheye program receipt required')
    bit=Path(programmed['Bitstream']['Path'])
    if sha(bit)!=programmed['Bitstream']['SHA256']:raise ValueError('programmed bitstream changed')
    output.mkdir(parents=True);parser=protocol.Parser();frames=[];start=time.monotonic()
    result={'schema':'hdmi-camera-fisheye-host-timed-fps-v1','passed':False,
        'started_utc':datetime.now(timezone.utc).isoformat(),'port':port,'baud':115200,'uart_transmit_bytes':0,
        'program_receipt':{'path':str(receipt),'sha256':sha(receipt)},'bitstream':programmed['Bitstream'],
        'final_adf_sha256':programmed['FinalADFSHA256'],'frames':frames,
        'host_tools':{str(Path(__file__).resolve()):sha(Path(__file__)),str(Path(protocol.__file__)):sha(protocol.__file__)}}
    try:
        with serial.Serial(port=None,baudrate=115200,timeout=.05)as stream:
            stream.dtr=False;stream.rts=False;stream.port=port;stream.open()
            with(output/'wire.bin').open('xb')as raw:
                while time.monotonic()-start<seconds:
                    chunk=stream.read(96);raw.write(chunk);arrived=time.monotonic()-start
                    for f in parser.feed(chunk):
                        f['host_elapsed_seconds']=arrived;frames.append(f)
                        print(json.dumps({k:f[k]for k in ('sequence','host_elapsed_seconds','processed_frames',
                            'unique_presented_frames','scan_refreshes','corrected_requested','failed','fault')}),flush=True)
        result['nominal_clock_summary']=protocol.summarize(frames)
        result['independent_host_summary']=arrival_summary(frames)
        if parser.rejected:raise ValueError('telemetry CRC/identity rejection during measurement')
        if not result['independent_host_summary']['clock_cross_check_within_3percent']:
            raise ValueError('host arrival/core timer cross-check differs from constrained clock')
        result['passed']=True
    except BaseException as e:result['error']=type(e).__name__+': '+str(e)
    wire=output/'wire.bin'
    result.update(ended_utc=datetime.now(timezone.utc).isoformat(),crc_rejected_packets=parser.rejected,
        discarded_bytes=parser.discarded,wire={'path':str(wire),'sha256':sha(wire)}if wire.exists()else None)
    with(output/'receipt.json').open('x',encoding='utf-8')as out:json.dump(result,out,indent=2,allow_nan=False)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--program-receipt',type=Path,required=True);p.add_argument('--port',default='COM7')
    p.add_argument('--seconds',type=float,default=30);a=p.parse_args()
    r=measure(a.output,a.program_receipt,a.seconds,a.port)
    print(json.dumps({k:r.get(k)for k in ('passed','independent_host_summary','error')},indent=2))
    raise SystemExit(0 if r['passed']else 1)
