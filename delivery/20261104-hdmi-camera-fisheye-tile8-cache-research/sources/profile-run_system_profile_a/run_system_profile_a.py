"""New observational XSim run using actual frozen INDEX8 sustained prepared bytes.

Never imports/executes a physical provider. No PDS/P:/COM/hardware access.
The frozen assess() function alone is AST-extracted without importing its module.
"""
import ast
import csv
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
BASE=ROOT/'distortion/work/hdmi-camera-fisheye-tile8df8-20261103-a/system-sustained-native-a'
RECEIPT_SHA='7cbf1c64700193df6fb29aae911a3c227d2d8a9e62617753655594a5f0124e52'
LEGACY=ROOT/'distortion/tools/run_hdmi_camera_fisheye_tile8df8_sustained_sim.py'
LEGACY_SHA='a5155524505ce28fa074ea239e778e4a9f865ba9fa912656e9aa3b6e642b38b7'
BENCH_KEY='tests/tb_hdmi_camera_fisheye_tile8df8_sustained.sv'
TOP='tb_hdmi_camera_fisheye_tile8df8_profile'
RUN=HERE/'native-a'
MAXIMUM_SECONDS=3600

def require(value,message):
    if not value:raise ValueError(message)

def sha(path):
    digest=hashlib.sha256()
    with Path(path).open('rb')as stream:
        while block:=stream.read(1024*1024):digest.update(block)
    return digest.hexdigest()

def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))

def write(path,value):
    with Path(path).open('x',encoding='utf-8',newline='\n')as stream:
        json.dump(value,stream,indent=2);stream.write('\n')

def stamp(stage,**facts):
    print(json.dumps(dict(Stage=stage,UTC=datetime.now(timezone.utc).isoformat(),**facts)),flush=True)

def tool(binary,argv,stage,deadline,report):
    tokens=[str(binary),*map(str,argv)]
    require(all(not re.search(r'["\r\n&|<>^%!]',value)for value in tokens),'unsafe simulation token')
    line='"'+os.environ.get('ComSpec','cmd.exe')+'" /d /s /c "'+' '.join('"'+value+'"'for value in tokens)+'"'
    row=dict(Stage=stage,Argv=tokens,StartedUTC=datetime.now(timezone.utc).isoformat());report['Commands'].append(row)
    stamp(stage+'-start')
    process=None
    with (RUN/(stage+'-stdout.log')).open('xb')as out,(RUN/(stage+'-stderr.log')).open('xb')as err:
        try:
            process=subprocess.Popen(line,cwd=RUN,stdout=out,stderr=err,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            row['OwnedPID']=process.pid
            code=process.wait(timeout=max(1,deadline-time.monotonic()))
            row['ReturnCode']=code;require(code==0,'simulation tool failed: '+stage)
        finally:
            if process is not None and process.poll()is None:
                stop=subprocess.run([str(Path(os.environ['SystemRoot'])/'System32/taskkill.exe'),'/PID',str(process.pid),'/T','/F'],capture_output=True,timeout=15)
                (RUN/(stage+'-owned-stop.log')).write_bytes(stop.stdout+stop.stderr);process.wait(timeout=15)
    stamp(stage+'-complete')

def rows(name):
    with (RUN/name).open(newline='',encoding='utf-8-sig')as stream:return list(csv.DictReader(stream))

def main():
    require(not RUN.exists(),'fresh independent native-a directory required')
    report=dict(Schema='tile8df8-enhanced-native-system-profile-v1',Passed=False,FunctionalPassed=False,
        ProfilingOnly=True,OriginalRunReusedAsNewRun=False,ProductionRTLModified=False,
        PhysicalOrReleaseAcceptance=False,HardwareAccessed=False,PDSAccessed=False,PDriveAccessed=False,
        Mode='native',Width=1920,Height=1080,InputSourceFrames=16,AcceptedCompleteFrames=4,
        DDRFirstBeatLatencyCycles=40,MaximumSeconds=MAXIMUM_SECONDS,Commands=[],
        StartedUTC=datetime.now(timezone.utc).isoformat(),InputSHA256={})
    watched=report['InputSHA256']
    def pin(path,digest=None):
        path=Path(path).resolve();actual=sha(path)
        require(digest is None or actual==digest,'frozen input drift: '+str(path))
        watched[str(path)]=actual;return actual
    pin(BASE/'simulation.json',RECEIPT_SHA);pin(LEGACY,LEGACY_SHA)
    pin(Path(__file__));pin(HERE/'profile_observer_a.sv')
    original=read(BASE/'simulation.json');require(original['Passed'] is True,'actual completed native required')
    require(original['DDRFirstBeatLatencyCycles']==40 and original['CacheIndexBits']==8,'selected native identity differs')
    RUN.mkdir()
    try:
        fixture=original['Fixture'];report['Fixture']=fixture
        for name,digest in original['FixtureSHA256'].items():
            pin(BASE/name,digest);shutil.copyfile(BASE/name,RUN/name)
        header_dir=BASE/'relocated-headers'
        for path in header_dir.rglob('*'):
            if path.is_file():
                original_name=path.relative_to(header_dir).as_posix();pin(path,original['SourceSHA256'][original_name])
                target=RUN/'relocated-headers'/original_name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,target)
        paths=[];prepared={}
        oldbench=Path(original['CompileSnapshot'][BENCH_KEY]['Path'])
        pin(oldbench,original['CompileSnapshot'][BENCH_KEY]['SHA256'])
        base_bytes=oldbench.read_bytes();oldtext=base_bytes.decode('utf-8')
        require(oldtext.count('module tb_hdmi_camera_fisheye_tile8df8_sustained;')==1,'original module declaration differs')
        insertion='        profile_finish();\n'
        anchor='        $display("PASS hdmi_camera_fisheye_tile8df8_sustained:'
        require(oldtext.count(anchor)==1,'original completion anchor differs')
        observer=(HERE/'profile_observer_a.sv').read_text()
        augmented=oldtext.replace('module tb_hdmi_camera_fisheye_tile8df8_sustained;',f'module {TOP};').replace(anchor,insertion+anchor)
        suffix='endmodule\r\n' if augmented.endswith('endmodule\r\n') else 'endmodule\n'
        require(augmented.endswith(suffix),'original endmodule shape differs')
        augmented=augmented[:-len(suffix)]+observer+'\n'+suffix
        stripped=augmented.replace(observer+'\n','').replace(insertion,'').replace(f'module {TOP};','module tb_hdmi_camera_fisheye_tile8df8_sustained;')
        require(stripped==oldtext,'profiling changes more than observations/module name')
        report['OriginalBenchPreservedAfterRemovingObserver']=True
        for name,row in original['CompileSnapshot'].items():
            path=Path(row['Path']);pin(path,row['SHA256'])
            if name!=BENCH_KEY:pin(ROOT/'distortion'/name,original['SourceSHA256'][name])
            target=RUN/'compiled-sources'/name;target.parent.mkdir(parents=True,exist_ok=True)
            if name==BENCH_KEY:target.write_bytes(augmented.encode('utf-8'))
            else:shutil.copyfile(path,target)
            paths.append(target);prepared[name]={'Path':str(target),'SHA256':sha(target),'OriginalPreparedSHA256':row['SHA256'],'SameProductionBytes':name!=BENCH_KEY}
        report['CompileSnapshot']=prepared
        report['FrozenProductionCount']=len(prepared)-1
        for name,digest in original['SourceSHA256'].items():
            if name.endswith('.vh'):pin(ROOT/'distortion'/name,digest)
        write(RUN/'input-source-manifest.json',dict(InputSHA256=watched,CompileSnapshot=prepared,OriginalBenchSHA256=sha(oldbench),ObserverSHA256=sha(HERE/'profile_observer_a.sv')))
        stamp('prepared',ProductionSources=len(prepared)-1,Fixtures=len(original['FixtureSHA256']),PixelsPerFrame=1920*1080)
        bindir=Path(original['Commands'][0]['Argv'][0]).parent
        deadline=time.monotonic()+MAXIMUM_SECONDS
        tool(bindir/'xvlog.bat',['--sv',*paths],'compile',deadline,report)
        tool(bindir/'xelab.bat',[TOP,'-s',TOP],'elaborate',deadline,report)
        tool(bindir/'xsim.bat',[TOP,'-runall','-log','simulation.log'],'simulate',deadline,report)
        log=(RUN/'simulation.log').read_text(encoding='utf-8',errors='replace')
        require('PROFILE_COMPLETE offers=4 accepts=4 starts=4 dones=4' in log,'complete profiling marker absent')
        require('PASS hdmi_camera_fisheye_tile8df8_sustained:' in log and '$finish called' in log,'original native completion absent')
        require(not re.search(r'(?im)^\s*(?:fatal|error):',log),'actual RTL/oracle assertion failed')
        tree=ast.parse(LEGACY.read_text());function=next(node for node in tree.body if isinstance(node,ast.FunctionDef)and node.name=='assess')
        code=compile(ast.Module(body=[function],type_ignores=[]),str(LEGACY),'exec')
        scope={'require':require,'read':read,'csv':csv};exec(code,scope)
        summary,frames=scope['assess'](RUN,fixture,'directfill')
        timeline=rows('profile-timeline.csv');metrics=rows('profile-cycles.csv');states=rows('profile-cache-fsm.csv');hist=rows('profile-ddr-histograms.csv')
        for event in ('source_offer','source_accept','engine_start','engine_done'):
            require([int(row['frame_id'])for row in timeline if row['event']==event]==[1,2,3,4],'profiling event IDs differ: '+event)
        for frame in frames:
            ident=int(frame['frame_id']);metric=metrics[ident-1]
            require(int(metric['cache_r_beats'])==8*int(frame['fills']),'actual cache beats/fills differ')
            require(sum(int(row['cycles'])for row in states if int(row['frame_id'])==ident)==int(metric['processing_cycles']),'FSM cycle partition differs')
            require(sum(int(row['count'])for row in hist if row['client']=='cache' and int(row['frame_id'])==ident and row['metric']=='ar_to_first_r')==int(frame['fills']),'actual read-burst histogram differs')
        report.update(Passed=True,FunctionalPassed=True,Summary=summary,Frames=frames,ProfileCycles=metrics,
            CacheFSM=states,DDRHistograms=hist,Timeline=timeline,
            OriginalOracleCRCAndDrainAssessPassed=True,ActualPixelsScanned=8294400,
            Limits='Additional observational simulation only. Original production bytes and original oracle/CRC/drain assertions retained. No new RTL, physical timing, bitstream, hardware or FPS acceptance.')
    except Exception as error:
        report['Error']=type(error).__name__+': '+str(error)
        stamp('failed',Error=report['Error'])
    finally:
        drift=[name for name,digest in watched.items()if sha(name)!=digest]
        for name,row in report.get('CompileSnapshot',{}).items():
            if sha(row['Path'])!=row['SHA256']:drift.append(row['Path'])
        for name,digest in original['FixtureSHA256'].items():
            if (RUN/name).is_file()and sha(RUN/name)!=digest:drift.append(str(RUN/name))
        report['InputDrift']=drift
        if drift:report.update(Passed=False,FunctionalPassed=False)
        report['EndedUTC']=datetime.now(timezone.utc).isoformat()
        report['ArtifactsSHA256']={path.relative_to(RUN).as_posix():sha(path)for path in RUN.iterdir()if path.is_file()and path.suffix in ('.csv','.json','.log')}
        write(RUN/'profiling.json',report)
    stamp('complete',Passed=report['Passed'],Report=str(RUN/'profiling.json'),SHA256=sha(RUN/'profiling.json'))
    return 0 if report['Passed'] else 2

if __name__=='__main__':sys.exit(main())
