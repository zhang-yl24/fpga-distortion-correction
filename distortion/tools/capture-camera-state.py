"""Finite read-only live sensor-register diagnostic, then actual heartbeat download."""
from pathlib import Path
from datetime import datetime,timezone
import argparse,hashlib,importlib.util,json,re,sys,time
import serial
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('triplet_capture',ROOT/'tools/capture-gamma-triplets.py')
capture=importlib.util.module_from_spec(spec);spec.loader.exec_module(capture)
ADDRESSES=[0x5001,0x3406,0x3503,0x4300,0x501f,0x503d,*range(0x3400,0x3406),
    0x3500,0x3501,0x3502,0x350a,0x350b,0x3a00,0x3a19,0x5000,0x3017,0x3018,0x3035,0x3036]
PATTERN=re.compile(r'^ISP T=([0-9A-F]{8}) A=([0-9A-F]{4}) V=([0-9A-F]{2}) E=([0-9A-F])$')

def main():
    p=argparse.ArgumentParser();p.add_argument('--port',default='COM5');p.add_argument('--seconds',type=float,default=16)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if not 1<=a.seconds<=24:raise ValueError('Require finite 1..24-second observation')
    out=a.output.resolve()
    if not out.is_relative_to(ROOT.resolve()):raise ValueError('Output outside project')
    out.mkdir(parents=True,exist_ok=False)
    result={'recorded_utc':datetime.now(timezone.utc).isoformat(),'passed':False,'hardware_accessed':True,
        'target':'camera_isp_probe','read_only_after_initialization':True,'rows':[],
        'limits':'SCCB rows are individual non-atomic reads; gains/exposure can change between bytes. Unattended lighting is uncontrolled. Readback proves control state, not final optical color quality.'}
    failure=None;port=None;scans=[];current=[]
    try:
        port=serial.Serial(a.port,921600,timeout=.15,dsrdtr=False,rtscts=False,xonxoff=False)
        port.set_buffer_size(rx_size=65536,tx_size=4096);port.reset_input_buffer()
        result['capture_transfer']=capture.program('camera_isp_probe',out/'program-probe.log')
        deadline=time.monotonic()+a.seconds
        with (out/'registers.txt').open('w',encoding='ascii') as raw:
            while time.monotonic()<deadline:
                line=port.readline().decode('ascii',errors='replace').strip()
                if not line:continue
                raw.write(line+'\n')
                match=PATTERN.fullmatch(line)
                if not match:raise ValueError('Malformed or unrelated register UART row: '+line)
                milliseconds,address,value,error=[int(v,16) for v in match.groups()]
                row={'received_utc':datetime.now(timezone.utc).isoformat(),'sensor_ready_elapsed_ms':milliseconds,
                    'address':f'{address:04X}','value':f'{value:02X}','error':error}
                result['rows'].append(row)
                if error:raise ValueError('SCCB read fault at '+row['address'])
                if address!=ADDRESSES[len(current)]:raise ValueError('Unexpected register scan order')
                if current and milliseconds<current[-1]['sensor_ready_elapsed_ms']:raise ValueError('Nonmonotonic sensor time')
                current.append(row)
                if len(current)==24:scans.append(current);current=[]
        if len(scans)<2:raise ValueError('Need at least two complete fresh sensor-state scans')
        result['scans']=[]
        for scan in scans:
            regs={int(r['address'],16):int(r['value'],16) for r in scan}
            controls={'awb_isp_enabled':bool(regs[0x5001]&1),'awb_automatic':not bool(regs[0x3406]&1),
                'aec_automatic':not bool(regs[0x3503]&1),'agc_automatic':not bool(regs[0x3503]&2),
                'test_pattern_enabled':bool(regs[0x503d]&128)}
            actual={f'{x:04X}':f'{regs[x]:02X}' for x in (0x4300,0x501f,0x3017,0x3018,0x3035,0x3036)}
            expected={'4300':'6F','501F':'01','3017':'7F','3018':'F0','3035':'21','3036':'60'}
            if actual!=expected:raise ValueError('Sensor configuration readback differs from tested table')
            result['scans'].append({'first_ms':scan[0]['sensor_ready_elapsed_ms'],'last_ms':scan[-1]['sensor_ready_elapsed_ms'],
                'controls':controls,'configuration_readback':actual,
                'non_atomic_rgb_gain_codes':[f'{regs[x]<<8|regs[x+1]:04X}' for x in (0x3400,0x3402,0x3404)],
                'non_atomic_exposure_code':f'{regs[0x3500]<<16|regs[0x3501]<<8|regs[0x3502]:06X}',
                'non_atomic_agc_code':f'{regs[0x350a]<<8|regs[0x350b]:04X}'})
        result['complete_scans']=len(scans);result['trailing_partial_scan_rows']=len(current)
    except Exception as exc:
        failure=exc;result['error']=f'{type(exc).__name__}: {exc}'
    finally:
        if port is not None:port.close()
        try:result['idle_transfer']=capture.program('heartbeat',out/'idle-after-probe.log')
        except Exception as exc:
            result['idle_error']=f'{type(exc).__name__}: {exc}';failure=failure or exc
        result['passed']=failure is None and len(scans)>=2
        if (out/'registers.txt').exists():result['register_log_sha256']=hashlib.sha256((out/'registers.txt').read_bytes()).hexdigest().upper()
        (out/'summary.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'passed':result['passed'],'complete_scans':len(scans),'output':str(out)}),flush=True)
    if failure:raise failure

if __name__=='__main__':main()
