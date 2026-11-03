"""Actual new mapper/ROM/mul32 regression, full pixel coordinates and stalls."""
import argparse
import ast
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

import cv2
import numpy as np
import generate_hdmi_fisheye_profile as cpu
from simulation_tools import resolve_vivado_bin,prepare_compile_sources,verify_compile_sources

ROOT=cpu.ROOT
SELF=Path(__file__).resolve()
PYTHON=Path('D:/anaconda3/python.exe')
COMPILE=('rtl/mul32_pipe.v','rtl/experimental/hdmi_camera_fisheye_rom.v',
    'rtl/experimental/hdmi_camera_fisheye_mapper.v','tests/tb_hdmi_camera_fisheye_mapper.sv')
HEADERS=(cpu.PROFILE_HEADER,cpu.TABLE_HEADER)
SCHEMA='hdmi-camera-fisheye-mapper-simulation-v1'
require,sha=cpu.require,cpu.sha


def helpers():
    pending=[SELF];seen=set()
    while pending:
        path=pending.pop()
        if path in seen:continue
        seen.add(path)
        for node in ast.walk(ast.parse(path.read_text(encoding='utf-8-sig'))):
            names=[v.name for v in node.names]if isinstance(node,ast.Import)else [node.module]if isinstance(node,ast.ImportFrom)and node.module else []
            for name in names:
                child=SELF.parent/(name.split('.')[-1]+'.py')
                if child.is_file()and child not in seen:pending.append(child)
    return sorted(seen)


def sources(binary):
    _,_,_,_=cpu.read_calibration();cal=json.loads(cpu.CALIBRATION.read_text())
    paths={ROOT/n for n in (*COMPILE,*HEADERS)}|set(helpers())|{cpu.CALIBRATION,Path(cal['source_fit']['path']),
        PYTHON,Path(os.environ['ComSpec']).resolve(),Path(os.environ['SystemRoot'])/'System32/taskkill.exe'}
    for name in ('xvlog','xelab','xsim'):paths.update((binary/(name+'.bat'),binary/'unwrapped/win64.o'/(name+'.exe')))
    for module in (np,cv2):
        where=Path(module.__file__).resolve();paths.add(where);paths.update(where.parent.rglob('*.pyd'))
    return {str(p.resolve()):sha(p)for p in sorted(paths)}


def fixtures(work,width,height):
    cfg=cpu.config(width=width,height=height)
    def emit(name,u,v,corrected,black=False):
        u,v=np.broadcast_arrays(np.asarray(u,np.int64),np.asarray(v,np.int64));mask=np.broadcast_to(np.asarray(black,bool),u.shape)
        x,y,b=cpu.fixed_map(u,v,corrected,config=cfg,in_black=mask)
        with(work/name).open('x',encoding='ascii',newline='\n')as stream:
            for uu,vv,ib,xx,yy,ob in zip(u.ravel(),v.ravel(),mask.ravel(),x.ravel(),y.ravel(),b.ravel()):
                word=(int(ib)<<97)|((int(uu)&0xffffff)<<73)|((int(vv)&0xffffff)<<49)|(int(ob)<<48)|((int(xx)&0xffffff)<<24)|(int(yy)&0xffffff)
                stream.write(f'{word:025x}\n')
    yy,xx=np.indices((height,width),dtype=np.int64);emit('corrected.mem',xx*256,yy*256,True)
    rng=np.random.default_rng(0x72101080);u=rng.integers(-(1<<23),1<<23,4096,dtype=np.int64);v=rng.integers(-(1<<23),1<<23,4096,dtype=np.int64)
    emit('identity.mem',u,v,False,np.arange(4096)%31==0)
    # Fractional/negative/extreme coordinates exercise the radius guard and
    # preserve input-black independently of source footprint clipping.
    u=rng.integers(-1024*256,3072*256,1024,dtype=np.int64);v=rng.integers(-1024*256,2048*256,1024,dtype=np.int64)
    emit('domain.mem',u,v,True,np.arange(1024)%29==0)


def commands(binary,work,mode):
    name='hdmi_camera_fisheye_mapper_'+mode
    relocated={n:str(work/'relocated-sources'/n)for n in COMPILE if n.endswith(('hdmi_camera_fisheye_rom.v','hdmi_camera_fisheye_mapper.v'))}
    return [('xvlog.bat',['--sv',*[relocated.get(n,str(ROOT/n))for n in COMPILE]],'compile'),
        ('xelab.bat',['tb_'+name,'-s',name,'--timescale','1ns/1ps'],'elaborate'),
        ('xsim.bat',[name,'-runall','-log','simulation.log'],'simulate')]


def tool(binary,name,args,work,deadline,stage):
    tokens=[str(binary/name),*args];shell=os.environ['ComSpec']
    require(all(not re.search(r'["\r\n&|<>^%!]',p)for p in [shell,*tokens]),'unsafe simulator argument')
    line='"'+shell+'" /d /s /c "'+' '.join('"'+p+'"'for p in tokens)+'"';process=None
    with(work/(stage+'-stdout.log')).open('wb')as out,(work/(stage+'-stderr.log')).open('wb')as err:
        try:
            process=subprocess.Popen(line,cwd=work,stdout=out,stderr=err,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            code=process.wait(timeout=max(.01,deadline-time.monotonic()));require(code==0,name+' failed; see '+str(work/(stage+'-stdout.log')))
        finally:
            if process is not None and process.poll()is None:
                result=subprocess.run([str(Path(os.environ['SystemRoot'])/'System32/taskkill.exe'),'/PID',str(process.pid),'/T','/F'],capture_output=True,timeout=15)
                (work/(stage+'-owned-stop.log')).write_bytes(result.stdout+result.stderr);process.wait(timeout=15)


def artifacts(work):return {p.relative_to(work).as_posix():sha(p)for p in sorted(work.rglob('*'))if p.is_file()and p!=work/'simulation.json'}


def validate_log(mode,text):
    require(not re.search(r'(?im)^\s*(?:fatal|error):',text),'mapper RTL assertion failed')
    rows=re.findall(r'^FISHEYE_MAPPER_PASS native=(\d+) corrected=(\d+) identity=4096 domain=1024 matched=(\d+) stalls=(\d+) stable_holds=(\d+) rejected_busy_configs=(\d+) longest_input_run=(\d+) enabled_latency=23$',text,re.M)
    require(len(rows)==1,'one mapper completion marker required')
    native,count,matched,stalls,holds,busy,run=map(int,rows[0]);expected=2073600 if mode=='native'else 512
    require(native==int(mode=='native')and count==expected and matched==expected+5120 and stalls>=10 and holds>=10 and busy>=2 and run>=32,
        'complete coordinate/identity/domain/stall/config/II1 coverage required')
    return {'Native':native,'CorrectedCoordinates':count,'ExactIdentityCoordinates':4096,'DomainCoordinates':1024,
        'TotalCoordinatesMatched':matched,'StalledCycles':stalls,'StableOutputHoldChecks':holds,
        'BusyConfigurationRejectCycles':busy,'ConsecutiveInputAccepts':run,'PipelineEnabledStages':23,'InitiationInterval':1}


def run(work,mode='small',maximum=600,small_gate=None):
    require(mode in ('small','native')and type(maximum)is int and 30<=maximum<=900,'bounded small/native mapper simulation required')
    require((mode=='native')==(small_gate is not None),'native requires successful same-source small gate')
    work=Path(work).resolve();require(work.is_relative_to(ROOT/'work')and not work.exists(),'fresh mapper simulation work required')
    binary=resolve_vivado_bin(ROOT.parent).resolve();watched=sources(binary);gate=None
    if small_gate:
        small_gate=Path(small_gate).resolve();v,w=verify(small_gate);require(v['Mode']=='small'and v['SourceSHA256']==watched,'native/small mapper source closure differs')
        watched.update({str(p):h for p,h in w.items()});gate=cpu.ref(small_gate)
    work.mkdir(parents=True);start=time.monotonic();value={'Schema':SCHEMA,'Mode':mode,'Passed':False,'SourceSHA256':watched,
        'SmallGate':gate,'VivadoBin':str(binary),'CompileSources':list(COMPILE),'Headers':list(HEADERS),'Commands':[],
        'StartedUTC':datetime.now(timezone.utc).isoformat(),'ActualMapperROMAndMultipliersExecuted':False,
        'HardwareAccessed':False,'PDSAccessed':False,'ExternalACAccepted':False,'HardwareReleaseAllowed':False}
    try:
        _,relocations=prepare_compile_sources(ROOT,COMPILE,HEADERS,work);value['RelocatedIncludes']=relocations
        fixtures(work,1920 if mode=='native'else 32,1080 if mode=='native'else 16)
        for name,args,stage in commands(binary,work,mode):
            record={'Stage':stage,'NativeArgv':[str(binary/name),*args],'ReturnCode':None};value['Commands'].append(record)
            tool(binary,name,args,work,start+maximum,stage);record['ReturnCode']=0
        value['Summary']=validate_log(mode,(work/'simulation.log').read_text(encoding='utf-8',errors='strict'))
        value['FullNativeCPUError']=cpu.metrics();value.update(Passed=True,ActualMapperROMAndMultipliersExecuted=True)
    except(Exception,KeyboardInterrupt)as error:value['Error']=type(error).__name__+': '+str(error)
    value['SourceDrift']=[p for p,h in watched.items()if not Path(p).is_file()or sha(p)!=h]
    value['Passed']=value['Passed']and not value['SourceDrift'];value['ElapsedSeconds']=round(time.monotonic()-start,3);value['Artifacts']=artifacts(work)
    with(work/'simulation.json').open('x',encoding='utf-8')as stream:json.dump(value,stream,indent=2,allow_nan=False)
    return value


def verify(path):
    path=Path(path).resolve();work=path.parent;v=json.loads(path.read_text())
    require(path.name=='simulation.json'and work.is_relative_to(ROOT/'work')and v.get('Schema')==SCHEMA and v.get('Passed')is True and
        v.get('SourceDrift')==[]and not v.get('Error'),'clean actual mapper regression required')
    expected=sources(Path(v['VivadoBin']))
    if v.get('SmallGate'):
        require(v['Mode']=='native'and sha(v['SmallGate']['Path'])==v['SmallGate']['SHA256'],'mapper small gate changed')
        small,inputs=verify(v['SmallGate']['Path']);require(small['Mode']=='small'and small['SourceSHA256']==expected,'mapper native small gate source differs')
        expected.update({str(p):h for p,h in inputs.items()})
    else:require(v['Mode']=='small','native requires small gate')
    require(v['SourceSHA256']==expected and all(Path(p).is_file()and sha(p)==h for p,h in expected.items()),'mapper complete source/runtime/tool closure drifted')
    require(v['CompileSources']==list(COMPILE)and v['Headers']==list(HEADERS),'mapper compilation closure differs')
    verify_compile_sources(ROOT,COMPILE,HEADERS,work,v['RelocatedIncludes'])
    require(v['Artifacts']==artifacts(work),'mapper executed artifacts/vectors/logs changed')
    require(v['Commands']==[{'Stage':stage,'NativeArgv':[str(Path(v['VivadoBin'])/name),*args],'ReturnCode':0}
        for name,args,stage in commands(Path(v['VivadoBin']),work,v['Mode'])],'mapper native commands differ')
    require(v['Summary']==validate_log(v['Mode'],(work/'simulation.log').read_text(encoding='utf-8'))and v['FullNativeCPUError']==cpu.metrics(),
        'mapper coordinate/coverage/oracle evidence differs')
    require(v['ActualMapperROMAndMultipliersExecuted']is True and all(v[k]is False for k in ('HardwareAccessed','PDSAccessed','ExternalACAccepted','HardwareReleaseAllowed')),
        'mapper acceptance scope differs')
    watched={Path(p):h for p,h in expected.items()};watched.update({work/n:h for n,h in v['Artifacts'].items()});watched[path]=sha(path)
    return v,watched


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--work-dir',type=Path);p.add_argument('--verify',type=Path)
    p.add_argument('--mode',choices=('small','native'),default='small');p.add_argument('--small-gate',type=Path);p.add_argument('--maximum-seconds',type=int,default=600);a=p.parse_args()
    if a.verify:v,w=verify(a.verify);print(json.dumps({'Verified':True,'Watched':len(w)}));return 0
    require(a.work_dir,'work-dir or verify required');v=run(a.work_dir,a.mode,a.maximum_seconds,a.small_gate)
    print(json.dumps({k:v.get(k)for k in ('Passed','Mode','Summary','ElapsedSeconds','Error')}));return 0 if v['Passed']else 1


if __name__=='__main__':raise SystemExit(main())
