"""Small actual snapshot packetizer/UART wire smoke; no capture/RAM/EDA proof."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import zlib

import hdmi_gray_frame_protocol as gray
from simulation_tools import resolve_vivado_bin

ROOT=Path(__file__).resolve().parents[1]
SELF=Path(__file__).resolve()
PYTHON=Path('D:/anaconda3/python.exe')
COMPILE=('rtl/experimental/hdmi_camera_snapshot_ref.v','rtl/uart_tx.v',
         'tests/tb_hdmi_camera_snapshot_uart_wire.sv')
HELPERS=(SELF,SELF.parent/'simulation_tools.py',SELF.parent/'hdmi_gray_frame_protocol.py',
         SELF.parent/'frame_protocol.py')
CLOCK_HZ=27000000
BAUD=921600
BIT_CYCLES=(CLOCK_HZ+BAUD//2)//BAUD
SCHEMA='hdmi-camera-snapshot-uart-wire-simulation-v1'
LIMITS=('Actual snapshot_ref and uart_tx only, 8x4 fixed-byte fixture; source descriptor and byte RAM '
        'are explicit models. Does not execute sampler/capture/production RAM, prove native timing/CDC, '
        'or access hardware. Nominal 921600 baud is rounded by production UART to 29 ref clocks per bit.')
FLAGS={'ActualReferenceRTLExecuted':True,'ActualUARTBaudRTLExecuted':True,
       'Independent8N1PinDecodeVerified':True,'GrayHostParserCRCVerified':True,
       'NextRequestWaitsForFinalStopDone':True,'SourceDescriptorModel':True,'ByteRAMModel':True,
       'ActualCaptureRTLExecuted':False,'ProductionRAMBodyExecuted':False,'HardwareAccessed':False,
       'PDSAccessed':False,'ExternalACAccepted':False,'HardwareReleaseAllowed':False}


def require(value,message):
    if not value:raise ValueError(message)


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def decode_samples(text):
    """Decode every complete 8N1 bit cell from independent ref-negedge samples."""
    levels=[]
    for index,line in enumerate(text.splitlines()):
        fields=line.split()
        require(len(fields)==2 and fields[0]==str(index) and fields[1] in ('0','1'),
                'nonconsecutive or unknown pin sample')
        levels.append(int(fields[1]))
    require(22040<len(levels)<30000 and levels[0]==1,'bounded complete UART sample stream required')
    cursor=0;result=bytearray();starts=[]
    while cursor<len(levels):
        while cursor<len(levels) and levels[cursor]:cursor+=1
        if cursor==len(levels):break
        start=cursor;end=start+10*BIT_CYCLES
        require(start>0 and levels[start-1]==1 and end<=len(levels),'truncated UART frame')
        bits=[]
        for bit in range(10):
            cell=levels[start+bit*BIT_CYCLES:start+(bit+1)*BIT_CYCLES]
            require(len(set(cell))==1,'shortened or unstable UART bit cell')
            bits.append(cell[BIT_CYCLES//2])
        require(bits[0]==0 and bits[9]==1,'invalid UART start/stop framing')
        result.append(sum(bits[n+1]<<n for n in range(8)));starts.append(start);cursor=end
    require(len(result)==76,'exactly 76 complete UART bytes required')
    return bytes(result),{'PinSamples':len(levels),'DecodedBytes':len(result),
        'FirstStartSample':starts[0],'FinalStopEndSample':starts[-1]+10*BIT_CYCLES,
        'BitCycles':BIT_CYCLES,'ClockHz':CLOCK_HZ,'NominalBaud':BAUD,
        'EffectiveBaudHz':CLOCK_HZ/BIT_CYCLES}


def packet(data):
    parser=gray.FrameParser(expected_size=(8,4));frames=[]
    # Exercise the actual bounded host parser with split headers/trailers.
    for offset in range(0,len(data),7):frames.extend(parser.feed(data[offset:offset+7]))
    require(len(data)==76 and len(frames)==1 and parser.rejected==0 and parser.discarded==0 and not parser.buffer,
            'one clean complete GRAY8 packet required')
    frame=frames[0];golden=bytes(range(32));crc=zlib.crc32(golden)
    require((frame.width,frame.height,frame.frame_id)==(8,4,1) and frame.payload==golden and frame.source_crc==crc,
            'independent byte fixture, frame identity or source CRC differs')
    require(data==gray.encode(8,4,1,golden),'full header/payload/trailer byte identity differs')
    return {'Width':8,'Height':4,'FrameID':1,'FormatTag':'0x3859','PayloadBytes':32,
        'CRC32':f'{crc:08x}','PayloadSHA256':hashlib.sha256(golden).hexdigest()}


def validate_log(text,pin):
    require(not re.search(r'(?im)^\s*(?:fatal|error):',text),'UART wire RTL assertion failed')
    rows=re.findall(r'^SNAPSHOT_UART_WIRE_PASS bytes=(\d+) reads=(\d+) accepted=(\d+) done=(\d+) '
        r'requests=(\d+) final_done_cycle=(\d+) sent_cycle=(\d+) next_request_cycle=(\d+) samples=(\d+) bit_cycles=(\d+)$',text,re.M)
    require(len(rows)==1,'one wire completion marker required')
    values=list(map(int,rows[0]));count,reads,accepted,done,requests,last,sent,nxt,samples,bits=values
    require((count,reads,accepted,done,requests,bits)==(76,32,76,76,2,29) and 0<last<sent<nxt<samples and
        samples==pin['PinSamples'] and last==pin['FinalStopEndSample']+1,
        'actual completion/request ordering or full stop-bit timing differs')
    return dict(zip(('WireBytes','RAMReads','AcceptedBytes','ActualUARTDonePulses','SourceRequests',
        'FinalStopDoneCycle','FrameSentCycle','NextRequestCycle','PinSamples','BitCycles'),values))


def expected_commands(binary,work):
    return [('xvlog.bat',['--sv',*[str(work/'compiled'/n)for n in COMPILE]],'compile'),
        ('xelab.bat',['tb_hdmi_camera_snapshot_uart_wire','-s','hdmi_camera_snapshot_uart_wire','--timescale','1ns/1ps'],'elaborate'),
        ('xsim.bat',['hdmi_camera_snapshot_uart_wire','-runall','-log','simulation.log'],'simulate')]


def source_inputs(binary):
    paths={ROOT/n for n in COMPILE}|set(HELPERS)|{PYTHON,Path(os.environ['ComSpec']).resolve(),
        Path(os.environ['SystemRoot'])/'System32/taskkill.exe'}
    for name in ('xvlog','xelab','xsim'):
        paths.update((binary/(name+'.bat'),binary/'unwrapped/win64.o'/(name+'.exe')))
    return {str(p.resolve()):sha(p)for p in sorted(paths)}


def tool(binary,name,args,work,deadline,stage):
    tokens=[str(binary/name),*args];comspec=os.environ['ComSpec']
    require(all(not re.search(r'["\r\n&|<>^%!]',t)for t in [comspec,*tokens]),'unsafe fixed simulator argument')
    line='"'+comspec+'" /d /s /c "'+' '.join('"'+t+'"'for t in tokens)+'"'
    process=None
    with(work/(stage+'-stdout.log')).open('wb')as out,(work/(stage+'-stderr.log')).open('wb')as err:
        try:
            process=subprocess.Popen(line,cwd=work,stdout=out,stderr=err,
                creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            remaining=deadline-time.monotonic();require(remaining>0,'UART wire simulation budget exhausted')
            code=process.wait(timeout=remaining)
            require(code==0,name+' failed; see '+str(work/(stage+'-stdout.log')))
        finally:
            if process is not None and process.poll()is None:
                killed=subprocess.run([str(Path(os.environ['SystemRoot'])/'System32/taskkill.exe'),
                    '/PID',str(process.pid),'/T','/F'],capture_output=True,timeout=15)
                (work/(stage+'-owned-stop.log')).write_bytes(killed.stdout+killed.stderr);process.wait(timeout=15)


def artifacts(work):
    return {p.relative_to(work).as_posix():sha(p)for p in sorted(work.rglob('*'))
            if p.is_file()and p!=work/'simulation.json'}


def coverage(work):
    data,pin=decode_samples((work/'tx-samples.txt').read_text(encoding='ascii'))
    require((work/'decoded-uart.bin').read_bytes()==data,'RTL and independent host pin decoders disagree')
    return {'PinDecode':pin,'Frame':packet(data),
        'Summary':validate_log((work/'simulation.log').read_text(encoding='utf-8',errors='strict'),pin)}


def run(work,maximum=120):
    require(type(maximum)is int and 10<=maximum<=240,'integer simulation budget 10..240 required')
    work=Path(work).resolve()
    require(work.is_relative_to(ROOT/'work')and not work.exists(),'fresh snapshot UART work directory required')
    require(Path(sys.executable).resolve()==PYTHON.resolve(),'run with the fixed producer interpreter '+str(PYTHON))
    binary=resolve_vivado_bin(ROOT.parent).resolve();watched=source_inputs(binary)
    work.mkdir(parents=True)
    for name in COMPILE:
        target=work/'compiled'/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes((ROOT/name).read_bytes())
    start=time.monotonic();value={'Schema':SCHEMA,'Passed':False,'SourceSHA256':watched,
        'CompileSources':list(COMPILE),'VivadoBin':str(binary),
        'ProducerInterpreter':{'Path':str(PYTHON),'SHA256':sha(PYTHON)},
        'StartedUTC':datetime.now(timezone.utc).isoformat(),'Commands':[],'Limits':LIMITS,
        **{key:False for key in FLAGS}}
    try:
        for name,args,stage in expected_commands(binary,work):
            record={'Stage':stage,'NativeArgv':[str(binary/name),*args],'ReturnCode':None};value['Commands'].append(record)
            tool(binary,name,args,work,start+maximum,stage);record['ReturnCode']=0
        value.update(coverage(work));value.update(FLAGS);value['Passed']=True
    except(Exception,KeyboardInterrupt)as error:value['Error']=type(error).__name__+': '+str(error)
    value['SourceDrift']=[p for p,h in watched.items()if not Path(p).is_file()or sha(p)!=h]
    value['Passed']=value['Passed']and not value['SourceDrift'];value['ElapsedSeconds']=round(time.monotonic()-start,3)
    value['Artifacts']=artifacts(work)
    with(work/'simulation.json').open('x',encoding='utf-8')as stream:json.dump(value,stream,indent=2,allow_nan=False)
    return value


def verify(path):
    """Rebind actual RTL, pin samples, logs, tools and interpreter; no EDA run."""
    path=Path(path).resolve();work=path.parent;value=json.loads(path.read_text(encoding='utf-8'))
    require(path.name=='simulation.json'and work.is_relative_to(ROOT/'work')and value.get('Schema')==SCHEMA and
        value.get('Passed')is True and value.get('SourceDrift')==[]and not value.get('Error'),'unclean UART wire receipt')
    require(value['CompileSources']==list(COMPILE)and value['Limits']==LIMITS,'wire scope differs')
    for key,expected in FLAGS.items():require(value.get(key)is expected,'wire boundary flag differs: '+key)
    watched={Path(p):h for p,h in value['SourceSHA256'].items()}
    require(all(p.is_absolute()and p==p.resolve()and p.is_file()and sha(p)==h for p,h in watched.items()),'wire source/runtime closure drifted')
    binary=Path(value['VivadoBin'])
    require(binary.is_absolute()and binary==binary.resolve()and value['SourceSHA256']==source_inputs(binary)and
        value['ProducerInterpreter']=={'Path':str(PYTHON),'SHA256':sha(PYTHON)},'complete static wire source/tool/interpreter closure differs')
    for name in COMPILE:require(sha(work/'compiled'/name)==watched[ROOT/name],'compiled actual RTL snapshot differs')
    require(value['Artifacts']==artifacts(work),'wire native artifacts/logs/samples drifted')
    expected=[{'Stage':stage,'NativeArgv':[str(binary/name),*args],'ReturnCode':0}
        for name,args,stage in expected_commands(binary,work)]
    require(value['Commands']==expected,'wire native command or completion differs')
    require(all(value.get(k)==v for k,v in coverage(work).items()),'wire independent decode/CRC/ordering differs')
    watched.update({work/name:h for name,h in value['Artifacts'].items()});watched[path]=sha(path)
    return value,watched


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--work-dir',type=Path)
    parser.add_argument('--verify',type=Path);parser.add_argument('--maximum-seconds',type=int,default=120);args=parser.parse_args(argv)
    if args.verify:
        value,watched=verify(args.verify);print(json.dumps({'Verified':True,'Watched':len(watched),'Summary':value['Summary']}));return 0
    require(args.work_dir is not None,'work-dir or verify required');value=run(args.work_dir,args.maximum_seconds)
    print(json.dumps({k:value.get(k)for k in ('Passed','Summary','PinDecode','ElapsedSeconds','Error')}));return 0 if value['Passed']else 1


if __name__=='__main__':raise SystemExit(main())
