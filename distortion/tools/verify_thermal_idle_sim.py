"""Independently decode the two synthetic UART snapshots emitted by the RTL test."""
from pathlib import Path
import argparse
import binascii
import hashlib
import json


def verify(path):
    data=Path(path).read_bytes()
    lines=data.splitlines(keepends=True)
    expected=[dict(V=1,B=921600,Q=1,TV=1,TF=0,E=0,TR=0x98df,TC=0x98d,TA=0x1234,TS=3,CV=7,OT=0,AL=0),
              dict(V=1,B=921600,Q=2,TV=0,TF=1,E=4,TR=0x000f,TC=0,TA=0x87654321,TS=8,CV=12,OT=1,AL=0x15)]
    if len(lines)!=2:
        raise ValueError('require exactly two complete synthetic snapshots')
    rows=[]
    for line,want in zip(lines,expected):
        if not line.endswith(b'\r\n') or len(line)!=125:
            raise ValueError('truncated, duplicated or unexpected thermal snapshot length')
        body,crc=line[:-2].rsplit(b' Z=',1)
        if len(crc)!=4 or int(crc,16)!=binascii.crc_hqx(body,0xffff):
            raise ValueError('thermal snapshot CRC16 differs')
        parts=body.decode('ascii').split(' ')
        if parts[0]!='THERMAL_IDLE':
            raise ValueError('wrong diagnostic prefix')
        fields={}
        for field in parts[1:]:
            key,value=field.split('=')
            if key in fields:
                raise ValueError('duplicate field')
            fields[key]=int(value,16)
        if fields!=want:
            raise ValueError('snapshot tore or failed/invalid state was hidden: '+repr(fields))
        rows.append(fields)
    return {'passed':True,'source':'synthetic RTL UART wire decoder','snapshots':rows,
            'stream_sha256':hashlib.sha256(data).hexdigest(),'hardware_accessed':False,
            'analog_temperature_accuracy_verified':False,'thermal_safety_verified':False}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('stream',type=Path);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();result=verify(a.stream)
    if not a.output.parent.is_dir():raise ValueError('output parent must already exist')
    with a.output.open('x',encoding='utf-8') as stream:stream.write(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'passed':True,'snapshots':len(result['snapshots']),'hardware_accessed':False}))


if __name__=='__main__':main()
