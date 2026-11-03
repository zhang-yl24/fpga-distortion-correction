"""Pure offline SGR1 encoder/exporter. No serial import or hardware operation."""
import argparse,hashlib,json,math,re,struct,zlib
from pathlib import Path

def from_phase(phase,base_id=0xe5ccceb0,request_id=1):
    if not 0<=phase<=0xffffffff or not 0<=base_id<=0xffffffff or not 1<=request_id<=0xffffffff:
        raise ValueError('phase/base_id must be u32; request_id must be nonzero u32')
    theta=phase*(2*math.pi/(1<<32))
    c=max(-(1<<30),min(1<<30,math.floor(math.cos(theta)*(1<<30)+0.5)))
    s=max(-(1<<30),min(1<<30,math.floor(math.sin(theta)*(1<<30)+0.5)))
    identity=struct.pack('<IIii',base_id,phase,c,s)
    pid=zlib.crc32(identity)&0xffffffff
    body=b'SGR1'+struct.pack('<BBHIIIiiI',1,1,36,request_id,base_id,phase,c,s,pid)
    packet=body+struct.pack('<I',zlib.crc32(body)&0xffffffff)
    assert len(packet)==36
    return {'protocol':'SGR1/version1/SET_ROTATION/36B','hardware_accessed':False,
        'request_id':request_id,'base_param_id':f'{base_id:08x}','param_id':f'{pid:08x}',
        'phase_u32':phase,'phase_hex':f'{phase:08x}','represented_degrees':phase*360/(1<<32),
        'cos_q30':c,'sin_q30':s,'cos_hex':f'{c&0xffffffff:08x}','sin_hex':f'{s&0xffffffff:08x}',
        'represented_cos':c/(1<<30),'represented_sin':s/(1<<30),'packet_hex':packet.hex(),
        'parameter_id_identity_le_hex':identity.hex(),
        'verification':'Confirm a FRESH SGA1-ticket/nonce PGSIG frame with this param_id and correction mode bit0=1. Sending is not acknowledgement.'}

def encode(degrees,base_id=0xe5ccceb0,request_id=1):
    if not math.isfinite(degrees):raise ValueError('angle must be finite')
    phase=math.floor((degrees%360)*(1<<32)/360+0.5)&0xffffffff
    result=from_phase(phase,base_id,request_id);result['requested_degrees']=degrees
    return result

def header_constants(text):
    values={}
    for m in re.finditer(r"\b(B1080_[A-Z0-9_]+)\s*=\s*(\d+)'(s?)([hdb])(-?[0-9a-fA-F]+)",text):
        name,width,signed,radix,digits=m.groups();width=int(width)
        v=int(digits,{'h':16,'d':10,'b':2}[radix])
        if signed and not digits.startswith('-') and v&(1<<(width-1)):v-=1<<width
        values[name]=v
    m=re.search(r'B1080_RADIUS_Q22\s*=\s*(\d+)',text)
    if m:values['B1080_RADIUS_Q22']=int(m[1])
    return values

def main():
    p=argparse.ArgumentParser(description=__doc__);g=p.add_mutually_exclusive_group(required=True)
    g.add_argument('--angle',type=float);g.add_argument('--phase',type=lambda x:int(x,0))
    p.add_argument('--base-id',type=lambda x:int(x,0),default=0xe5ccceb0)
    p.add_argument('--request-id',type=lambda x:int(x,0),default=1)
    p.add_argument('--output',type=Path,help='Write the exact values and packet JSON; does not send it')
    a=p.parse_args();r=encode(a.angle,a.base_id,a.request_id) if a.angle is not None else from_phase(a.phase,a.base_id,a.request_id)
    cfg=Path(__file__).resolve().parents[1]/'deps/board1080-penn.vh'
    if cfg.exists():
        r['base_header_sha256']=hashlib.sha256(cfg.read_bytes()).hexdigest();r['base_header']=cfg.read_text()
        r['base_integer_constants']=header_constants(r['base_header'])
        q8=['OUT_CX','OUT_CY','SRC_CX','SRC_CY','SRC_FX','SRC_FY','ROT_CX','ROT_CY']
        q30=['INV_FX','INV_FY','ROT_COS','ROT_SIN']
        q22=['K1','K2','K3','P1','P2','RADIUS_Q22']
        r['base_decoded_constants']={}
        for names,scale in [(q8,256),(q30,1<<30),(q22,1<<22)]:
            for n in names:
                if 'B1080_'+n in r['base_integer_constants']:
                    r['base_decoded_constants'][n]=r['base_integer_constants']['B1080_'+n]/scale
    text=json.dumps(r,indent=2,ensure_ascii=False)+'\n'
    if a.output:a.output.write_text(text,encoding='utf-8')
    print(text,end='')
if __name__=='__main__':main()
