"""Actual direct top/sampler digital regression; opaque configuration only.

No PDS, register access, hardware, optical RGB or external AC acceptance.
"""
import argparse
import ast
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import re
import sys
import time

from simulation_tools import resolve_vivado_bin
from run_gamma_pipeline_d5_sim import tool

ROOT=Path(__file__).resolve().parents[1]
SELF=Path(__file__).resolve()
COMPILE=('tests/hdmi_camera_direct_control_stubs.sv','rtl/experimental/hdmi_camera_pixel_sampler.v',
         'board/hdmi_camera_direct_top.v','tests/tb_hdmi_camera_direct_control.sv')
REFERENCES={'cfg_pll':'platform/video_base/ipcore/cfg_pll/cfg_pll.v',
    'ms72xx_rearm_observed_ctl':'rtl/experimental/ms72xx_rearm_observed_ctl.v'}


def require(value,message):
    if not value:raise ValueError(message)


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def module_header(text,module):
    matches=list(re.finditer(r'\bmodule\s+'+re.escape(module)+r'\b',text))
    require(len(matches)==1,'one actual module header required: '+module)
    start=matches[0].start();end=text.find(');',start)
    require(end>=0,'unterminated actual module header: '+module)
    return text[start:end+2]


def normalized_header(text):
    text=re.sub(r'/\*.*?\*/|//[^\n]*','',text,flags=re.S)
    return re.sub(r'\s+|\b(?:reg|wire)\b','',text)


def bound_headers(root=ROOT):
    root=Path(root).resolve();text=(root/COMPILE[0]).read_text(encoding='utf-8');rows={}
    modules=re.findall(r'(?m)^module\s+(\w+)',text)
    require(set(modules)==set(REFERENCES)and len(modules)==2,'only two opaque configuration modules permitted')
    for line in text.splitlines():
        if not line.startswith('// HEADER_BINDING '):continue
        row=json.loads(line[len('// HEADER_BINDING '):]);module=row['Module']
        require(module in REFERENCES and module not in rows and row['Path']==REFERENCES[module],'stub reference identity differs')
        path=root/row['Path'];actual=module_header(path.read_text(encoding='utf-8'),module)
        require(hashlib.sha256(actual.encode()).hexdigest()==row['HeaderSHA256'],'actual production header changed: '+module)
        require(normalized_header(actual)==normalized_header(module_header(text,module)),'opaque stub signature differs: '+module)
        rows[module]={'Path':str(path),'SHA256':sha(path),'HeaderSHA256':row['HeaderSHA256'],'ProductionBodyExecuted':False}
    require(set(rows)==set(REFERENCES),'complete two opaque bindings required')
    return rows


def static_helpers(root=SELF):
    pending=[Path(root).resolve()];seen=set()
    while pending:
        path=pending.pop()
        if path in seen:continue
        seen.add(path)
        for node in ast.walk(ast.parse(path.read_text(encoding='utf-8-sig'))):
            names=[]
            if isinstance(node,ast.Import):names=[x.name for x in node.names]
            elif isinstance(node,ast.ImportFrom):
                if node.module:names.append(node.module)
                if node.module=='tools':names += [x.name for x in node.names]
            for name in names:
                child=SELF.parent/(name.split('.')[-1]+'.py')
                if child.is_file()and child not in seen:pending.append(child)
    return sorted(seen)


def validate_log(text):
    require(not re.search(r'(?im)^\s*(?:fatal|error):',text),'direct RTL assertion failed')
    markers=('default_configuration_denies_de','same_sample_27bit_independent_oracle',
        'ready_exact_two_stage_latency','stopped_pclk_reset_masks_de','clock_forwarded_during_blank',
        'config_failure_wins_startup','cold_power_delay_executed','phase_short_pulses_unsampled')
    require(all(len(re.findall(r'^HDMI_DIRECT_CASE '+m+r'$',text,re.M))==1 for m in markers),'complete unique direct coverage markers required')
    faults=re.findall(r'^HDMI_DIRECT_FAULT (\w+) sticky_blank$',text,re.M)
    require(faults==['cfg_failed','pll_unlock','rx_not_done','tx_not_done'],'four independent runtime faults required')
    matches=re.findall(r'^HDMI_DIRECT_PASS bundle_checks=(\d+) phase_changes=(\d+) ready_checks=(\d+) '
        r'clock_edges=(\d+) resets=(\d+) cold_cycles=(\d+) warm_shortcuts=(\d+)$',text,re.M)
    require(len(matches)==1,'one direct completion marker required')
    values=list(map(int,matches[0]));checks,phase,ready,edges,resets,cold,warm=values
    require(checks>=1000 and phase>=576 and ready>=1000 and edges>=2000 and resets==6 and
        1000000<=cold<=1100000 and warm==6,'direct coverage counters incomplete')
    return dict(zip(('BundleChecks','PhaseChanges','ReadyChecks','ForwardedClockEdges','CommonResets',
        'ColdPowerReferenceCycles','WarmPowerCounterShortcuts'),values))


def expected_commands(binary,work):
    binary=Path(binary);work=Path(work)
    return [(name,args,stage)for name,args,stage in [
        ('xvlog.bat',['--sv',*[str(work/'compiled'/n)for n in COMPILE]],'compile'),
        ('xelab.bat',['tb_hdmi_camera_direct_control','-s','hdmi_camera_direct_control','--timescale','1ns/1ps'],'elaborate'),
        ('xsim.bat',['hdmi_camera_direct_control','-runall','-log','simulation.log'],'simulate')]]


def artifacts(work):
    return {p.relative_to(work).as_posix():sha(p)for p in sorted(Path(work).rglob('*'))
        if p.is_file()and p!=Path(work)/'simulation.json'}


def verify(path):
    """Rebind immutable run evidence and current sources without executing tools."""
    path=Path(path).resolve();work=path.parent
    require(path.name=='simulation.json'and work.is_relative_to(ROOT/'work'),'direct simulation receipt path differs')
    value=json.loads(path.read_text(encoding='utf-8'))
    require(value.get('Schema')=='hdmi-camera-direct-control-simulation-v1'and value.get('Passed')is True and
        value.get('SourceDrift')==[]and not value.get('Error'),'unclean direct simulation receipt')
    for flag in ('ActualTopRTLExecuted','ActualSamplerRTLExecuted','Full27BitDigitalBundleVerified'):
        require(value.get(flag)is True,'actual RTL coverage flag absent: '+flag)
    for flag in ('IICOrPLLBodyExecuted','ExternalACAccepted','OpticalRGBVerified','HardwareAccessed','PDSAccessed','HardwareReleaseAllowed'):
        require(value.get(flag)is False,'direct simulation acceptance boundary differs: '+flag)
    bindings=bound_headers();require(value['OpaqueModuleHeaderBindings']==bindings,'opaque production header evidence differs')
    require(value['CompileSources']==list(COMPILE),'actual direct compilation closure differs')
    watched={Path(p):h for p,h in value['SourceSHA256'].items()}
    require(all(p.is_absolute()and p==p.resolve()and p.is_file()and sha(p)==h for p,h in watched.items()),'direct source/runtime evidence drifted')
    required={ROOT/n for n in COMPILE}|{Path(r['Path'])for r in bindings.values()}|set(static_helpers())
    required.add(Path(value['Interpreter']['Path']))
    binary=Path(value['VivadoBin'])
    for name in ('xvlog','xelab','xsim'):
        required.add(binary/(name+'.bat'));required.add(binary/'unwrapped'/'win64.o'/(name+'.exe'))
    require(set(watched)==required and value['Interpreter']=={'Path':str(Path(value['Interpreter']['Path'])),'SHA256':watched[Path(value['Interpreter']['Path'])]},
        'complete static source/tool/interpreter closure differs')
    require(value['Artifacts']==artifacts(work),'native compilation/snapshot/log evidence differs')
    require(value['CompiledSources']==[{'Source':str(ROOT/n),'Compiled':str(work/'compiled'/n),'SHA256':watched[ROOT/n]}for n in COMPILE],
        'compiled source copy bindings differ')
    for row in value['CompiledSources']:require(sha(row['Compiled'])==row['SHA256'],'actual compiled source snapshot differs')
    commands=[{'Stage':stage,'NativeArgv':[str(binary/name),*args],'ReturnCode':0}
              for name,args,stage in expected_commands(binary,work)]
    require(value['Commands']==commands,'actual native commands or completed stages differ')
    require(value['Summary']==validate_log((work/'simulation.log').read_text(encoding='utf-8',errors='strict')),'direct oracle/log summary differs')
    require(value['LogSHA256']=={p.name:sha(p)for p in work.glob('*.log')},'direct native log set differs')
    for name,h in value['Artifacts'].items():watched[work/name]=h
    watched[path]=sha(path)
    return value,watched


def run(work,maximum=240):
    require(type(maximum)is int and 10<=maximum<=600,'integer wall-clock budget 10..600 required')
    work=Path(work).resolve()
    require(work.is_relative_to(ROOT/'work')and not work.exists(),'fresh simulation directory under distortion/work required')
    bindings=bound_headers();watched={str(ROOT/n):sha(ROOT/n)for n in COMPILE}
    watched.update({r['Path']:r['SHA256']for r in bindings.values()})
    watched.update({str(p):sha(p)for p in static_helpers()})
    watched[str(Path(sys.executable).resolve())]=sha(sys.executable)
    require(all('`include'not in(ROOT/n).read_text()for n in COMPILE),'unbound direct simulation include')
    binary=resolve_vivado_bin(ROOT.parent).resolve()
    for name in ('xvlog','xelab','xsim'):
        for p in (binary/(name+'.bat'),binary/'unwrapped'/'win64.o'/(name+'.exe')):watched[str(p)]=sha(p)
    work.mkdir(parents=True);started=time.monotonic();deadline=started+maximum
    copied=[]
    for name in COMPILE:
        source=ROOT/name;destination=work/'compiled'/name;destination.parent.mkdir(parents=True,exist_ok=True)
        with destination.open('xb')as stream:stream.write(source.read_bytes())
        copied.append({'Source':str(source),'Compiled':str(destination),'SHA256':watched[str(source)]})
    result={'Schema':'hdmi-camera-direct-control-simulation-v1','Passed':False,'StartedUTC':datetime.now(timezone.utc).isoformat(),
        'SourceSHA256':watched,'OpaqueModuleHeaderBindings':bindings,'CompileSources':list(COMPILE),'Commands':[],
        'CompiledSources':copied,'VivadoBin':str(binary),
        'Interpreter':{'Path':str(Path(sys.executable).resolve()),'SHA256':sha(sys.executable)},
        'ActualTopRTLExecuted':False,'ActualSamplerRTLExecuted':False,'Full27BitDigitalBundleVerified':False,
        'IICOrPLLBodyExecuted':False,'ExternalACAccepted':False,'OpticalRGBVerified':False,
        'HardwareAccessed':False,'PDSAccessed':False,'HardwareReleaseAllowed':False,
        'Limits':'Actual direct top and sampler with only cfgPLL/IIC opaque stubs. '
                 'Digital sequence/ready/reset checks do not prove RGB channel interpretation, analog clocks, '
                 'register writes, HDMI electrical timing or external setup/hold. One cold power delay executes; warm shortcuts are counted.'}
    try:
        for name,args,stage in expected_commands(binary,work):
            record={'Stage':stage,'NativeArgv':[str(binary/name),*args],'ReturnCode':None};result['Commands'].append(record)
            tool(binary,name,args,work,deadline,stage);record['ReturnCode']=0
        result['Summary']=validate_log((work/'simulation.log').read_text(encoding='utf-8',errors='strict'))
        result.update(Passed=True,ActualTopRTLExecuted=True,ActualSamplerRTLExecuted=True,Full27BitDigitalBundleVerified=True)
    except (Exception,KeyboardInterrupt)as error:result['Error']=type(error).__name__+': '+str(error)
    result['SourceDrift']=[p for p,h in watched.items()if sha(p)!=h]
    result['Passed']=result['Passed']and not result['SourceDrift']
    result['ElapsedSeconds']=round(time.monotonic()-started,3);result['EndedUTC']=datetime.now(timezone.utc).isoformat()
    result['LogSHA256']={p.name:sha(p)for p in work.glob('*.log')}
    result['Artifacts']=artifacts(work)
    with(work/'simulation.json').open('x',encoding='utf-8')as stream:json.dump(result,stream,indent=2,allow_nan=False)
    return result


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--work-dir',type=Path);p.add_argument('--verify',type=Path)
    p.add_argument('--maximum-seconds',type=int,default=240);args=p.parse_args(argv)
    if args.verify:
        value,watched=verify(args.verify);print(json.dumps({'Verified':True,'Watched':len(watched)}));return 0
    require(args.work_dir is not None,'--work-dir or --verify required');value=run(args.work_dir,args.maximum_seconds)
    print(json.dumps({k:value.get(k)for k in ('Passed','Summary','ElapsedSeconds','Error')}));return 0 if value['Passed']else 1


if __name__=='__main__':raise SystemExit(main())
