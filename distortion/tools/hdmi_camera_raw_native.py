"""Bound read-only native inspection of the fresh150MHz raw HDMI candidate.

Export, report and exact read-only query only. Native data always comes from
an independent copy of this build's ADF. No exceptions, bits or hardware.
"""
import argparse
from pathlib import Path
import json
import os
import re
import shutil
import subprocess
import time

import hdmi_camera_raw_build as build
from camera720_calibrated_inspect import query_commands

SELF=Path(__file__).resolve();TARGET=build.TARGET
SCHEMA='hdmi-camera-raw-native-inspection-v1'
MARKER='HDMI_CAMERA_RAW_INSPECTION_COMPLETE'
INIT='mpnr_report_timing -force_to_run -delay_type min_max -max_path 1000 -nworst 4 -report_exception TRUE'
require,sha,read,write,utc=build.require,build.sha,build.read,build.write,build.utc
SUFFIXES={'.tcl','.v','.txt','.rtr','.log','.gnr','.fdc'}
DUMMY='module physical_dummy(input a, output y); assign y=a; endmodule\n'


def ref(path):return {'Path':str(Path(path).resolve()),'SHA256':sha(path)}


def add(watched,path,digest=None):
    path=Path(path).absolute();require(path==path.resolve() and path.is_file(),'canonical native input required')
    actual=sha(path);require(digest is None or digest==actual,'native input SHA differs: '+str(path))
    require(path not in watched or watched[path]==actual,'conflicting native input SHA');watched[path]=actual
    return path


def merge(watched,inputs):
    for p,h in inputs.items():add(watched,p,h)


def bind_build(path):
    path=Path(path).absolute();plan=build.validate(path);work=path.parent;watched={}
    merge(watched,{**plan['InputSHA256'],**plan['PreparedSHA256']});add(watched,path)
    receipt_path=add(watched,work/'execution-result.json');receipt=read(receipt_path)
    require(receipt['Schema']=='hdmi-camera-raw-build-execution-v1' and receipt['Target']==TARGET
        and receipt['BuildCompleted'] is True and receipt['PlanSHA256']==sha(path)
        and receipt['Command']==plan['Command'] and receipt['ExitCode']==0
        and receipt['InputDrift']==[] and receipt['TimedOut'] is False
        and receipt['NativeErrors']==[]
        and not receipt.get('Error') and receipt['StoppedForUnexpectedStage'] is False
        and receipt['Cleanup']['Complete'] is True,'current raw build did not complete cleanly')
    actual={p.relative_to(work).as_posix():sha(p) for p in work.rglob('*.log')}
    require(receipt['LogSHA256']==actual and receipt['Diagnostics']==build.diagnostics(work),
            'build log or diagnostic inventory differs')
    events=build.events((work/'stdout.log').read_text(encoding='gb18030',errors='replace'))
    require(receipt['ActualEvents']==events==[[s,e] for s in build.STAGES for e in ('started','done')],
            'actual raw build stage sequence differs')
    for name,h in actual.items():add(watched,work/name,h)
    adf=add(watched,receipt['ADF'],receipt['ADFSHA256'])
    require(adf==work/'place_route'/(TARGET+'_pnr.adf'),'raw build final ADF role differs')
    return plan,receipt,watched


def context_prefix(build_plan):
    original=(Path(build_plan).parent/'build.tcl').read_text(encoding='ascii')
    boundary='report_timing -force_to_run -delay_type min_max -max_path 1000 -nworst 4 -report_exception TRUE\n'
    require(original.count(boundary)==1 and original.endswith(boundary),'raw build context boundary differs')
    prefix=original[:-len(boundary)]
    require(not any(word in prefix for word in ('file copy','gen_bit_stream','cfg_program'))
        and prefix.endswith('-fix_hold_violation_in_route TRUE\n'),'raw native declaration prefix differs')
    return prefix


def render(build_plan,work,mode,body=None):
    w=Path(work).as_posix()
    if mode=='export':
        require(body is None,'export accepts no query body')
        return (context_prefix(build_plan)+
            'report_timing -force_to_run -input_db_file {'+w+'/input.adf} -delay_type min_max -max_path 1000 -nworst 4 -report_exception TRUE\n'
            'if {[info script] ne {}} {\n    gen_netlist -force_to_run -input_db_file {'+w+'/input.adf} -func_sim_only\n'
            '    puts {'+MARKER+'}\n    flush stdout\n}\n')
    require(mode in ('report','query'),'read-only native mode required')
    commands=query_commands(body) if mode=='query' else [
        '.switch_db -route -input {@WORK@/input.adf} -output {@WORK@/route-dump.txt}']
    require(mode=='query' or body is None,'report accepts no query body')
    require(not any(MARKER in c for c in commands),'query spoofs native completion marker')
    return ('set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG676\n'
        'add_design {'+w+'/dummy.v}\nif {[info script] ne {}} {\n    mpnr -input {'+w+'/input.adf}\n    '+INIT+'\n'
        +'\n'.join(commands).replace('@WORK@',w)+'\n    puts {'+MARKER+'}\n    flush stdout\n}\n')


def current_source(build_plan,proof_path=None):
    plan,result,watched=bind_build(build_plan)
    if proof_path is None:return plan,result['ADF'],result['ADFSHA256'],watched
    import hdmi_camera_raw_physical as physical
    proof,inputs=physical.bind_application(proof_path);merge(watched,inputs)
    require(proof['BuildPlan']==ref(build_plan),'scoped native source uses another build')
    return plan,proof['ResultADF']['Path'],proof['ResultADF']['SHA256'],watched


def prepare(build_plan,work,mode,body=None,source_proof=None):
    build_plan=Path(build_plan).resolve();work=build.work_path(work)
    require(not work.exists(),'fresh raw native stage required')
    source_proof=Path(source_proof).resolve() if source_proof else None
    plan,source,source_sha,watched=current_source(build_plan,source_proof)
    adf=Path(source);add(watched,SELF);add(watched,Path(build.__file__))
    body=Path(body).resolve() if body else None
    if body:add(watched,body)
    tcl=render(build_plan,work,mode,body.read_text(encoding='ascii') if body else None)
    work.mkdir();shutil.copyfile(adf,work/'input.adf')
    (work/'dummy.v').write_text(DUMMY,encoding='ascii',newline='\n')
    (work/'stage.tcl').write_text(tcl,encoding='ascii',newline='\n')
    for name in ('input.adf','dummy.v','stage.tcl'):add(watched,work/name)
    value={'Schema':SCHEMA,'Target':TARGET,'Mode':mode,'BuildPlan':str(build_plan),'BuildPlanSHA256':sha(build_plan),
        'SourceADF':str(adf),'SourceADFSHA256':source_sha,'SourceProof':ref(source_proof) if source_proof else None,'WorkDirectory':str(work),
        'QueryBody':str(body) if body else None,'InputSHA256':{str(p):h for p,h in watched.items()},
        'ExpectedStages':['Report Timing','Generate Netlist'] if mode=='export' else [],
        'MaximumSeconds':300,'Command':[plan['Command'][0],'-file',(work/'stage.tcl').as_posix(),
        '-work_dir',work.as_posix(),'-project_name',TARGET],'CreatedUTC':utc(),
        'HardwareAccessed':False,'BitstreamRequested':False,'TimingAccepted':False}
    write(work/'stage-plan.json',value);return work/'stage-plan.json'


def validate(path):
    path=Path(path).resolve();work=build.work_path(path.parent);value=read(path);watched={}
    require(path.name=='stage-plan.json' and value['Schema']==SCHEMA and value['Target']==TARGET
            and value['WorkDirectory']==str(work),'exact raw inspection plan required')
    proof=value['SourceProof']
    if proof:require(ref(proof['Path'])==proof,'scoped native source proof changed')
    plan,source,digest,bound=current_source(value['BuildPlan'],proof['Path'] if proof else None);merge(watched,bound)
    require(value['BuildPlanSHA256']==sha(value['BuildPlan']) and value['SourceADF']==source
        and value['SourceADFSHA256']==digest,'raw native source/build lineage differs')
    require(all(value['InputSHA256'].get(str(p))==h for p,h in watched.items()),'raw native plan omits build closure')
    merge(watched,value['InputSHA256'])
    require(value['InputSHA256'].get(str(SELF))==sha(SELF),'native producer unbound')
    body=Path(value['QueryBody']).read_text(encoding='ascii') if value['QueryBody'] else None
    require((work/'stage.tcl').read_text(encoding='ascii')==render(value['BuildPlan'],work,value['Mode'],body)
            and (work/'dummy.v').read_text(encoding='ascii')==DUMMY
            and sha(work/'input.adf')==value['SourceADFSHA256'],'raw native instructions or ADF copy differ')
    require(value['MaximumSeconds']==300 and value['Command']==[plan['Command'][0],'-file',
        (work/'stage.tcl').as_posix(),'-work_dir',work.as_posix(),'-project_name',TARGET]
        and value['ExpectedStages']==(['Report Timing','Generate Netlist'] if value['Mode']=='export' else []),
        'native command/deadline/stages differ')
    add(watched,path);return value,watched


def artifacts(work):
    return {p.relative_to(work).as_posix():sha(p) for p in work.rglob('*') if p.is_file() and p.suffix in SUFFIXES}


def execute(path):
    value,watched=validate(path);work=Path(value['WorkDirectory'])
    require(os.name=='nt' and not (work/'execution-start.json').exists(),'fresh native Windows inspection required')
    result={**value,'StagePlanSHA256':sha(path),'StartedUTC':utc(),'EDAExecuted':False,'ExitCode':None,
        'ExecutionPassed':False,'TimedOut':False};write(work/'execution-start.json',result);process=None;start=time.monotonic()
    try:
        with (work/'stdout.log').open('xb') as out,(work/'stderr.log').open('xb') as err:
            process=subprocess.Popen(value['Command'],cwd=work,stdout=out,stderr=err,shell=False,
                creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0));result.update(EDAExecuted=True,OwnedPID=process.pid)
            try:result['ExitCode']=process.wait(timeout=value['MaximumSeconds'])
            except subprocess.TimeoutExpired:result['TimedOut']=True
    except BaseException as error:result['Error']=type(error).__name__+': '+str(error)
    finally:
        if process is not None and process.poll() is None:result['Cleanup']=build.cleanup.stop_owned_tree(process,work,'raw readonly stage')
        else:result['Cleanup']={'Complete':True,'ParentExited':True}
        log=(work/'stdout.log').read_text(encoding='gb18030',errors='replace')
        result.update(ElapsedSeconds=round(time.monotonic()-start,3),ActualEvents=build.events(log),
            CompletionMarker=MARKER in log,Diagnostics=build.diagnostics(work),
            InputDrift=[str(p) for p,h in watched.items() if not p.is_file() or sha(p)!=h],Artifacts=artifacts(work))
        result['ExecutionPassed']=(result['ExitCode']==0 and not result['TimedOut'] and not result.get('Error')
            and result['ActualEvents']==[[s,e] for s in value['ExpectedStages'] for e in ('started','done')]
            and result['CompletionMarker'] and result['InputDrift']==result['Diagnostics']==[]
            and result['Cleanup']['Complete'])
        write(work/'result.json',result)
    return result


def bind_receipt(path):
    path=Path(path).resolve();work=build.work_path(path.parent);saved=read(path)
    stage,watched=validate(work/'stage-plan.json')
    require(path.name=='result.json' and all(saved.get(k)==v for k,v in stage.items())
        and saved['StagePlanSHA256']==sha(work/'stage-plan.json') and saved['ExecutionPassed'] is True
        and saved['ExitCode']==0 and not saved.get('Error') and saved['TimedOut'] is False
        and saved['InputDrift']==saved['Diagnostics']==[] and saved['Cleanup']['Complete'],'raw native receipt not clean')
    log=(work/'stdout.log').read_text(encoding='gb18030',errors='replace')
    require(saved['ActualEvents']==build.events(log)==[[s,e] for s in stage['ExpectedStages'] for e in ('started','done')]
        and saved['CompletionMarker'] is True and MARKER in log and build.diagnostics(work)==[]
        and saved['Artifacts']==artifacts(work),'raw native events/artifacts differ')
    for name,h in saved['Artifacts'].items():add(watched,work/name,h)
    add(watched,path);return saved,watched


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--build-plan',type=Path);p.add_argument('--work-dir',type=Path)
    p.add_argument('--mode',choices=('export','report','query'));p.add_argument('--body',type=Path);p.add_argument('--execute',type=Path)
    p.add_argument('--source-proof',type=Path)
    a=p.parse_args()
    if a.execute:v=execute(a.execute);print(json.dumps({k:v.get(k) for k in ('ExecutionPassed','ElapsedSeconds','Error')}));return 0 if v['ExecutionPassed'] else 1
    plan=prepare(a.build_plan,a.work_dir,a.mode,a.body,a.source_proof);print(json.dumps({'Prepared':True,'Plan':str(plan)}));return 0


if __name__=='__main__':raise SystemExit(main())
