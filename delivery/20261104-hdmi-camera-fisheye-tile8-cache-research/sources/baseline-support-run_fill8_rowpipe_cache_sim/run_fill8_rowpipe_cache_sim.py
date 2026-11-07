"""Independent fill8/frozen-fill32 cache regression; no PDS or hardware."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time

from simulation_tools import resolve_vivado_bin

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'work/hdmi-camera-fisheye-fill8-20261103-a'
BENCH = ROOT/'tests/tb_fill8_rowpipe_cache.sv'
SOURCES = {'fill8': ROOT/'rtl/experimental/ddr_neighbour_cache_scatter16_rowpipe.v',
           'fill32': ROOT/'rtl/experimental/ddr_neighbour_cache_scatter4_rowpipe.v'}
PINNED = {'fill8': 'ebf3566e39589e7c383d5cf753675c440823b19b4eabfdd9bd33b68c37561091',
          'fill32': '15e7927a6d8069e5f204c46c90956a5a5839239376da69719a659745307448bb'}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run_tool(binary, name, args, work, deadline, stem):
    tokens = [str(binary/name), *args]
    if any(re.search(r'["\r\n&|<>^%!]', token) for token in tokens):
        raise ValueError('unsafe simulation argument')
    command = '"'+os.environ.get('ComSpec', 'cmd.exe')+'" /d /s /c "'+' '.join('"'+token+'"' for token in tokens)+'"'
    with (work/(stem+'-stdout.log')).open('xb') as out, (work/(stem+'-stderr.log')).open('xb') as err:
        completed = subprocess.run(command, cwd=work, stdout=out, stderr=err,
            timeout=max(.01, deadline-time.monotonic()), creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    if completed.returncode:
        raise ValueError(stem+' failed; inspect '+str(work/(stem+'-stdout.log')))


def validate(work, groups):
    text=(work/'simulation.log').read_text(encoding='utf-8',errors='replace')
    if 'PASS FILL8 complete independent cache regression' not in text or '$finish called' not in text:
        raise ValueError('full regression did not finish')
    if re.search(r'(?im)^\s*(?:fatal|error):', text):
        raise ValueError('simulator reported a failure')
    results={}
    for width in (639,1920):
        value=json.loads((work/f'summary-{width}.json').read_text())
        exact={'passed':True,'width':width,'groups_per_fill':groups,'reset_before_last_scatter':1,
               'fault_cases':6,'warm_stream_outputs':64,'warm_span_cycles':63,'warm_first_valid_latency':4}
        if any(type(value.get(k)) is not type(v) or value[k]!=v for k,v in exact.items()):
            raise ValueError('mandatory exact result differs: '+str(value))
        if value['complete_fills']<10 or value['ram_pixels_checked']!=value['complete_fills']*128:
            raise ValueError('all-lane RAM inspection missing')
        for key in ('normal_outputs','ar_stalls','r_gaps','output_stalls','input_stalls','queue_full',
                    'frame_pending','fast_queries','slow_queries','frame_drains'):
            if type(value.get(key)) is not int or value[key]<=0:
                raise ValueError('vacuous coverage: '+key)
        results[str(width)]=value
    return results


def run(output, maximum=180):
    output=Path(output).resolve()
    if output.exists() or not output.is_relative_to(BASE.resolve()) or not 30<=maximum<=600:
        raise ValueError('fresh output under fill8 work and bound30..600 required')
    for role,source in SOURCES.items():
        if sha(source)!=PINNED[role]:
            raise ValueError('reviewed candidate/frozen source changed: '+role)
    output.mkdir(parents=True)
    watched={str(path.resolve()):sha(path) for path in (*SOURCES.values(),BENCH,Path(__file__),Path(__file__).with_name('simulation_tools.py'))}
    result={'Schema':'fill8-rowpipe-independent-cache-simulation-v1','Passed':False,
        'StartedUTC':datetime.now(timezone.utc).isoformat(),'SourceSHA256':watched,
        'PDSAccessed':False,'HardwareAccessed':False,'FullFrameSimulated':False,
        'Oracle':'Independent signed coordinate/bounds and RGB565 source formula; neither RTL is the other pixel oracle.',
        'Modes':{}}
    deadline=time.monotonic()+maximum
    try:
        binary=resolve_vivado_bin(ROOT.parent)
        result['VivadoBin']=str(binary)
        for mode,groups in (('fill8',8),('fill32',32)):
            work=output/mode;work.mkdir()
            args=['--sv']
            if mode=='fill32':args+=['-d','FILL32_BASELINE']
            args += [str(SOURCES[mode]),str(BENCH)]
            run_tool(binary,'xvlog.bat',args,work,deadline,'compile')
            run_tool(binary,'xelab.bat',['tb_fill8_rowpipe_cache','-s','fill8_tb'],work,deadline,'elaborate')
            run_tool(binary,'xsim.bat',['fill8_tb','-runall','-log','simulation.log'],work,deadline,'simulate')
            result['Modes'][mode]=validate(work,groups)
        result['Passed']=True
    except BaseException as error:
        result['Error']=type(error).__name__+': '+str(error)
    result['InputDrift']=[path for path,digest in watched.items() if sha(path)!=digest]
    if result['InputDrift']:result['Passed']=False
    result['EndedUTC']=datetime.now(timezone.utc).isoformat()
    result['ArtifactsSHA256']={str(path.relative_to(output)):sha(path) for path in output.rglob('*')
        if path.is_file() and path.suffix in ('.log','.json')}
    (output/'simulation.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--maximum-seconds',type=int,default=180)
    args=parser.parse_args()
    result=run(args.output,args.maximum_seconds)
    print(json.dumps({k:result.get(k)for k in ('Passed','Error','Modes','InputDrift')},indent=2))
    raise SystemExit(0 if result['Passed'] else 1)
