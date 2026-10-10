"""Versioned FPGA rotation commands and fresh telemetry acknowledgement checks."""
import binascii
import math
import re

def angle_phase(degrees):
    value=float(degrees)
    if not math.isfinite(value):raise ValueError('Angle must be finite')
    return round((value%360.0)*(1<<32)/360.0)&0xffffffff

def command_packet(opcode,sequence,argument):
    if opcode not in (1,2) or not 0<=sequence<=65535 or not 0<=argument<=0xffffffff:
        raise ValueError('Invalid command range')
    if opcode==2 and argument not in (0,1):raise ValueError('Auto argument must be 0 or 1')
    body=bytes((1,opcode))+sequence.to_bytes(2,'little')+argument.to_bytes(4,'little')
    return b'\xa5\x5a'+body+binascii.crc_hqx(body,0xffff).to_bytes(2,'little')

def telemetry_fields(line):
    if not line.startswith('CAM='):raise ValueError('Not a telemetry line')
    fields={}
    for name,value in re.findall(r'\b([A-Z]+)=([0-9A-Fa-f]+)\b',line):
        if name in fields:raise ValueError('Duplicate telemetry field '+name)
        fields[name]=int(value,16)
    return fields

def require_ready(fields):
    for key,value in {'HV':1,'CAM':0x5640,'E':0,'I':1,'H':1,'D':1,'V':1,'X':0,'UF':0,'MF':0,'OW':0,'TV':1,'TF':0}.items():
        if fields.get(key)!=value:raise ValueError('Firmware not ready: '+key)
    for key in ('HQ','HR','HC','HX','HD','HE','RA','AU','CF','TR','TA','AL'):
        if key not in fields:raise ValueError('Missing telemetry field '+key)
    raw=fields['TR'];alarm=fields['AL'];temperature=(raw>>4)*0.1219-273.15
    if raw>65535 or raw>>4==0 or not -40<=temperature<=85 or fields['TA']>=54000000 or alarm&0x60 or not alarm&0x80:
        raise ValueError('Temperature unavailable, stale or above diagnostic limit')
    return temperature

def acknowledged(fields,before,opcode,sequence,argument):
    require_ready(fields)
    if any(fields[k]!=before[k] for k in ('HX','HD','HE')):
        raise ValueError('UART command rejected, duplicated or framing fault observed')
    if fields['HQ']!=sequence or fields['HC']!=((before['HC']+1)&0xffffffff):return False
    if opcode==2:return fields['AU']==argument
    return fields['HR']==argument and fields['RA']==argument and fields['CF']!=before['CF'] and fields['AU']==0
