"""Send once, verify fresh controller/frame telemetry, and always return FPGA to idle."""
from pathlib import Path
import argparse,json,secrets,sys,time,subprocess,os
from datetime import datetime,timezone
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
from model.host_protocol import angle_phase,command_packet,telemetry_fields,require_ready,acknowledged
p=argparse.ArgumentParser(description=__doc__)
group=p.add_mutually_exclusive_group(required=True)
group.add_argument('--angle',type=float);group.add_argument('--auto',type=int,choices=(0,1))
p.add_argument('--sequence',type=int);p.add_argument('--port',default='COM5')
p.add_argument('--execute',action='store_true',help='Access UART; otherwise print packet only')
p.add_argument('--observe-seconds',type=int,choices=range(0,46),default=0,metavar='0..45')
p.add_argument('--output',type=Path)
args=p.parse_args();opcode=1 if args.angle is not None else 2
argument=angle_phase(args.angle) if opcode==1 else args.auto
sequence=args.sequence if args.sequence is not None else secrets.randbelow(65536)
packet=command_packet(opcode,sequence,argument)
result={'hardware_accessed':False,'opcode':opcode,'sequence':sequence,'argument':f'{argument:08X}','packet_hex':packet.hex(),'acknowledged':False,
    'ack_scope':('Controller acceptance and a newly completed processed frame at the requested angle.' if opcode==1 else 'Controller acceptance and automatic-mode state; sustained new frames are checked during observation.')+' The HDMI on-screen frame phase and optical response require separate observation.'}
if not args.execute:print(json.dumps(result));sys.exit(0)
import serial
serial_port=None;failure=None
try:
    serial_port=serial.Serial(None,115200,timeout=.25,write_timeout=1)
    serial_port.dtr=False;serial_port.rts=False;serial_port.port=args.port
    serial_port.open();result['hardware_accessed']=True
    # No packet is sent until the live firmware advertises protocol version 1.
    deadline=time.monotonic()+8;before=None
    while time.monotonic()<deadline:
        line=serial_port.readline().decode('ascii',errors='replace').strip()
        if not line.startswith('CAM='):continue
        fields=telemetry_fields(line)
        try:require_ready(fields)
        except ValueError:continue
        before=fields;break
    if before is None:raise RuntimeError('No ready host-control firmware; no command sent')
    if sequence==before['HQ']:
        sequence=(sequence+1)&65535;packet=command_packet(opcode,sequence,argument)
        result.update(sequence=sequence,packet_hex=packet.hex())
    result['before']=before
    if serial_port.write(packet)!=len(packet):raise RuntimeError('Partial UART write; no automatic retry')
    serial_port.flush();result['writes']=1;deadline=time.monotonic()+8
    while time.monotonic()<deadline:
        line=serial_port.readline().decode('ascii',errors='replace').strip()
        if not line.startswith('CAM='):continue
        fields=telemetry_fields(line)
        if acknowledged(fields,before,opcode,sequence,argument):
            result.update(acknowledged=True,after=fields);break
    if not result['acknowledged']:raise RuntimeError('No fresh matching controller/frame acknowledgement; no automatic retry')
    result['acknowledged_at_utc']=datetime.now(timezone.utc).isoformat()
    if args.observe_seconds:
        print('Host command accepted and matching completed frame observed; finite monitor interval started.',flush=True)
        deadline=time.monotonic()+args.observe_seconds;observations=[]
        while time.monotonic()<deadline:
            line=serial_port.readline().decode('ascii',errors='replace').strip()
            if not line.startswith('CAM='):continue
            fields=telemetry_fields(line);require_ready(fields)
            if any(fields[k]!=result['after'][k] for k in ('HX','HD','HE')):
                raise RuntimeError('UART counter fault during observation')
            if opcode==1 and (fields['HR']!=argument or fields['RA']!=argument or fields['AU']!=0):
                raise RuntimeError('Requested angle changed during observation')
            if opcode==2 and fields['AU']!=argument:
                raise RuntimeError('Requested automatic mode changed during observation')
            observations.append({'received_utc':datetime.now(timezone.utc).isoformat(),'line':line,'fields':fields})
        result['observations']=observations
        if args.observe_seconds>=4 and (len(observations)<2 or observations[-1]['fields']['CF']==result['after']['CF']):
            raise RuntimeError('No new completed frames during finite observation')
except Exception as exc:
    failure=str(exc);result['error']=failure
finally:
    if serial_port is not None:serial_port.close()
    # Closing a COM port does not stop FPGA logic. Respect the thermal policy
    # even on failed capability checks, writes or acknowledgements.
    task_env={k:v for k,v in os.environ.items() if k.upper()!='PSMODULEPATH'}
    # The idle helper uses Windows PowerShell 5, which cannot import the
    # PowerShell 7 module locations inherited from the parent terminal.
    stamp=time.strftime('%Y%m%d-%H%M%S')
    idle_log=root/'build/host_control_sim'/('host-idle-'+stamp+'.log')
    try:
        # Stream child output into a file. Do not depend on captured stdout /
        # stderr being strings, and retain the program evidence on log errors.
        with idle_log.open('w',encoding='utf-8') as output:
            idle=subprocess.run(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(root/'tools/program-heartbeat.ps1'),'-Target','heartbeat','-Frequency','5MHz'],stdout=output,stderr=subprocess.STDOUT,env=task_env,timeout=90)
        result['idle_return_code']=idle.returncode
    except Exception as exc:
        result['idle_return_code']=-1;idle_log.write_text(str(exc),encoding='utf-8')
    result['idle_log']=str(idle_log)
    if result['idle_return_code']!=0:result['error']=(result.get('error','')+'; heartbeat idle failed').strip('; ')
    if args.output:args.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps(result));sys.exit(0 if result['acknowledged'] and result['idle_return_code']==0 and 'error' not in result else 1)
