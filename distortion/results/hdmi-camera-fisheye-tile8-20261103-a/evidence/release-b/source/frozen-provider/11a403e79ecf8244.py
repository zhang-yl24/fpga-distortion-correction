"""Read-only native inspection of this independent fill8r2 candidate's own routed ADF.

Export/report/exact queries use independent ADF copies and the complete current
fisheye build closure. No timing exception, route edit, bitstream or hardware
operation is accepted. An existing Sdm-3003 source reduction stays recorded
and unreviewed; successful inspection does not clear source diagnostics.
"""
import argparse
from pathlib import Path
import json
import os
import re
import shutil
import subprocess
import time

import hdmi_camera_fisheye_tile8_build as build

SELF=Path(__file__).resolve()
TARGET=build.TARGET
SCHEMA='hdmi-camera-fisheye-tile8-native-inspection-v1'
MARKER='HDMI_CAMERA_FISHEYE_TILE8_NATIVE_INSPECTION_COMPLETE'
MAX_PATHS=10000
INIT='mpnr_report_timing -force_to_run -delay_type min_max -max_path 10000 -nworst 4 -report_exception TRUE'
BOUNDARY='report_timing -force_to_run -delay_type min_max -max_path 10000 -nworst 4 -report_exception TRUE\n'
DUMMY='module fisheye_inspection_context(input a,output y);assign y=a;endmodule\n'
SUFFIXES={'.tcl','.v','.txt','.rtr','.log','.gnr','.fdc','.adf','.pcf','.prt'}
require,sha,read,write,utc=build.require,build.sha,build.read,build.write,build.utc


def ref(path):return {'Path':str(Path(path).resolve()),'SHA256':sha(path)}


def add(watched,path,expected=None):
    path=Path(path).absolute();require(path==path.resolve() and build.local_io(path).is_file(),'canonical native fisheye input required')
    actual=sha(path);require(expected is None or actual==expected,'native fisheye input SHA differs: '+str(path))
    require(path not in watched or watched[path]==actual,'conflicting native fisheye input SHA');watched[path]=actual
    return path


def merge(watched,inputs):
    for name,h in inputs.items():add(watched,name,h)


def drift(watched):return [str(p) for p,h in watched.items() if not build.local_io(p).is_file() or sha(p)!=h]


def diagnostic_body(value):
    match=re.search(r'(?:^|: )((?:C:|E:|F:|CRITICAL:|ERROR:|FATAL:|Traceback).*)$',value)
    require(match is not None,'unparsed native fisheye diagnostic')
    return match[1]


def retained_reductions(source_diagnostics,current_diagnostics=(),reviewed_bodies=None):
    source_bodies=[]
    for row in source_diagnostics:
        body=diagnostic_body(row)
        require(body.startswith('C: Sdm-3003: ') if reviewed_bodies is None else body in reviewed_bodies,
                'unknown critical/error in source fisheye build: '+row)
        source_bodies.append(body)
    allowed=set(source_bodies)
    for row in current_diagnostics:
        require(diagnostic_body(row) in allowed,'new critical/error in read-only fisheye inspection: '+row)
    return {'SourceDiagnostics':list(source_diagnostics),'CurrentDiagnostics':list(current_diagnostics),
        'AllowedSourceDiagnosticCode':'Sdm-3003' if reviewed_bodies is None else 'SourceBoundReadonlySidecar',
        'SourceReductionBodies':sorted(allowed),'ReviewedReadonlyBodies':reviewed_bodies,
        'DiagnosticsCleared':not source_diagnostics and not current_diagnostics,
        'SourceDiagnosticReviewPassed':False,'IndependentDiagnosticReviewStillRequired':True}


def bind_build(path,build_review=None):
    path=Path(path).absolute();require(path.name=='plan.json','exact fisheye build plan required')
    source_receipt=path.parent/'execution-result.json'
    watched={};reviewed_bodies=None
    require(build_review is None,'fisheye read-only diagnostic bridge is not implemented')
    receipt=build.verify_execution(source_receipt)
    plan=build.validate(path)
    merge(watched,plan['InputSHA256']);merge(watched,plan['PreparedSHA256'])
    add(watched,path);add(watched,source_receipt)
    reduction=retained_reductions(receipt['Diagnostics'],reviewed_bodies=reviewed_bodies)
    for name,h in receipt['NativeLogSHA256'].items():add(watched,path.parent/name,h)
    source=add(watched,receipt['ADF'],receipt['ADFSHA256'])
    require(source==path.parent/'place_route'/(TARGET+'_pnr.adf'),'fisheye routed source ADF role differs')
    if receipt['TimingReport']:add(watched,receipt['TimingReport']['Path'],receipt['TimingReport']['SHA256'])
    return plan,receipt,reduction,watched


def current_source(build_plan,source_proof=None,build_review=None):
    require(source_proof is None,'fill8r2 native physical application provider not yet implemented')
    return bind_build(build_plan,build_review)


def query_commands(body):
    """Target-independent, bounded read-only grammar without arbitrary Tcl."""
    require(body and body.isascii(),'nonempty ASCII fisheye query body required')
    brace=r'\{[^{}\r\n]*\}'
    patterns=[r'puts '+brace,
        r'get_(?:pins|ports|clocks) -hierarchical -regexp '+brace,
        r'get_(?:ports|clocks) -regexp '+brace,
        r'show -(?:design_net|dev_instance) '+brace,
        r'\.switch_db -route -input \{@WORK@/input\.adf\} -output \{@WORK@/[A-Za-z0-9_-]+\.txt\}',
        r'dump_net -grid_unit '+brace+r' -print_site -out_file \{@WORK@/[A-Za-z0-9_-]+\.txt\}',
        r'report_path_timing -delay_type min_max -max_path (?:[1-9][0-9]{0,3}|10000) -nworst [1-8] -report_exception TRUE -from '
            +brace+r'(?: -through '+brace+r')? -to '+brace,
        r'(?:mpnr_report_timing|report_path_timing|show|show_device|get_pins|get_ports|get_clocks) -help']
    commands=[]
    for line in body.splitlines():
        line=line.strip()
        if not line or line.startswith('#'):continue
        require(not re.search(r'\\[{}\r\n]',line) and all(ord(c)>=32 for c in line),
                'fisheye query escapes/continuations/control characters forbidden')
        require(any(re.fullmatch(p,line) for p in patterns),'unsupported read-only fisheye query: '+line[:120])
        require(MARKER not in line,'fisheye query spoofs completion marker');commands.append(line)
    require(commands and len(commands)<=300,'fisheye query command count out of bounds')
    return commands


def context_prefix(build_plan):
    original=(Path(build_plan).parent/'build.tcl').read_text(encoding='ascii')
    require(original.count(BOUNDARY)==1 and original.endswith(BOUNDARY),'fisheye native build context boundary differs')
    prefix=original[:-len(BOUNDARY)]
    require(prefix.endswith('-fix_hold_violation_in_route TRUE\n') and
            not any(word in prefix for word in ('file copy','gen_bit_stream','cfg_program','save_adif')),
            'fisheye native declaration prefix differs')
    return prefix


def render(build_plan,work,mode,alias,body=None):
    w=build.paths.alias_path(build.ROOT,alias,Path(work))
    if mode=='export':
        require(body is None,'fisheye export accepts no query body')
        return (context_prefix(build_plan)+
            'report_timing -force_to_run -input_db_file {'+w+'/input.adf} -delay_type min_max -max_path 10000 -nworst 4 -report_exception TRUE\n'
            'if {[info script] ne {}} {\n    gen_netlist -force_to_run -input_db_file {'+w+'/input.adf} -func_sim_only\n'
            '    puts {'+MARKER+'}\n    flush stdout\n}\n')
    require(mode in ('report','query'),'fisheye native report/export/query mode required')
    commands=query_commands(body) if mode=='query' else ['.switch_db -route -input {@WORK@/input.adf} -output {@WORK@/route-dump.txt}']
    require(mode=='query' or body is None,'fisheye report accepts no arbitrary body')
    return ('set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG676\n'
        'add_design {'+w+'/dummy.v}\nif {[info script] ne {}} {\n'
        '    mpnr -input {'+w+'/input.adf}\n    '+INIT+'\n'
        +'\n'.join(commands).replace('@WORK@',w)+'\n    puts {'+MARKER+'}\n    flush stdout\n}\n')


def recipe(build_plan,work,mode,body=None,maximum=600,require_alias=False,source_proof=None,build_review=None):
    build_plan=Path(build_plan).absolute();work=build.work_path(work)
    require(type(maximum) is int and 60<=maximum<=600,'fisheye inspection deadline must be60..600 seconds')
    require(mode in ('export','report','query'),'read-only fisheye native mode required')
    source_proof=Path(source_proof).absolute() if source_proof else None
    build_review=Path(build_review).absolute() if build_review else None
    plan,receipt,reductions,watched=current_source(build_plan,source_proof,build_review);alias=plan['RepoAlias']
    if require_alias:build.paths.validate_repo_alias(build.ROOT,alias)
    body=Path(body).absolute() if body else None
    if body:add(watched,body)
    require(mode=='query' or body is None,'only fisheye query mode accepts a body')
    text=render(build_plan,work,mode,alias,body.read_text(encoding='ascii') if body else None)
    add(watched,SELF);add(watched,build.__file__)
    require(not any(p.is_relative_to(work) for p in watched),'fisheye inspection output overlaps source evidence')
    native_work=build.paths.alias_path(build.ROOT,alias,work)
    result={'Schema':SCHEMA,'Target':TARGET,'Mode':mode,'BuildPlan':str(build_plan),'BuildPlanSHA256':sha(build_plan),
        'SourceBuildReceipt':ref(build_plan.parent/'execution-result.json'),
        'SourceProof':ref(source_proof) if source_proof else None,'SourceADF':receipt['ADF'],
        'SourceBuildReview':ref(build_review) if build_review else None,
        'SourceADFSHA256':receipt['ADFSHA256'],'WorkDirectory':str(work),'RepoAlias':alias,
        'AliasExpectedRepository':str(build.ROOT.parent.resolve()),'AliasRequiredForNativeExecutionOnly':True,
        'QueryBody':str(body) if body else None,'ExpectedStages':['Report Timing','Generate Netlist'] if mode=='export' else [],
        'MaximumSeconds':maximum,'ReportMaxPaths':MAX_PATHS,'ReportNWorst':4,'ReportDelayType':'min_max',
        'FullTimingPathEnumerationClaimed':False,'SourceReductionDiagnostics':reductions,
        'InputSHA256':{str(p):h for p,h in watched.items()},
        'Command':[plan['Command'][0],'-file',native_work+'/stage.tcl','-work_dir',native_work,'-project_name',TARGET],
        'HardwareAccessed':False,'BitstreamRequested':False,'HardwareReleaseAllowed':False,'TimingAccepted':False,
        'ConstraintsModified':False,'RoutesModified':False,'BaselineTimingOrCountsInherited':False,
        'Limits':'Read-only own fisheye candidate only. ADF copies, source diagnostics/reductions, ten-table timing, per-path coverage, all actual declared pads, active/unused inputs and complete CDC/reset still need independent interpretation. No prior RAW counts/proof or external AC/RGB/hardware acceptance.'}
    return result,text,watched


def prepare(build_plan,work,mode,body=None,maximum=600,source_proof=None,build_review=None):
    work=build.work_path(work);require(not work.exists(),'fresh fisheye native fisheyeory required')
    value,text,_=recipe(build_plan,work,mode,body,maximum,require_alias=True,source_proof=source_proof,build_review=build_review)
    work.mkdir();shutil.copyfile(value['SourceADF'],work/'input.adf')
    (work/'dummy.v').write_text(DUMMY,encoding='ascii',newline='\n')
    (work/'stage.tcl').write_text(text,encoding='ascii',newline='\n')
    value['PreparedUTC']=utc();write(work/'stage-plan.json',value)
    return work/'stage-plan.json'


def validate(path,require_alias=False,fresh=False):
    path=Path(path).absolute();work=build.work_path(path.parent);saved=read(path)
    require(path.name=='stage-plan.json' and saved.get('Schema')==SCHEMA and saved.get('Target')==TARGET,
            'exact native fisheye plan required')
    expected,text,watched=recipe(saved['BuildPlan'],work,saved['Mode'],saved['QueryBody'],saved['MaximumSeconds'],require_alias,
        saved['SourceProof']['Path'] if saved['SourceProof'] else None,
        saved['SourceBuildReview']['Path'] if saved['SourceBuildReview'] else None)
    require(set(saved)==set(expected)|{'PreparedUTC'} and {k:v for k,v in saved.items() if k!='PreparedUTC'}==expected,
            'native fisheye plan differs from exact recipe')
    require((work/'stage.tcl').read_text(encoding='ascii')==text and (work/'dummy.v').read_text(encoding='ascii')==DUMMY
            and sha(work/'input.adf')==saved['SourceADFSHA256'],'native fisheye Tcl/dummy/ADF copy differs')
    initial={'stage-plan.json','stage.tcl','dummy.v','input.adf'}
    if fresh:require({p.name for p in work.iterdir()}==initial,'native fisheye stage reused/contaminated')
    for name in initial:add(watched,work/name)
    return saved,watched


def artifacts(work):
    return {p.relative_to(work).as_posix():sha(p) for p in work.rglob('*') if p.is_file() and p.suffix in SUFFIXES}


def artifact(receipt_path,value,name):
    found=[Path(receipt_path).parent/n for n in value['Artifacts']
           if Path(n).name==name and 'report_path_timing' not in Path(n).parts]
    require(len(found)==1,'one receipt-bound native fisheye artifact required: '+name)
    return found[0]


def evidence(value,work,watched):
    log=(work/'stdout.log').read_text(encoding='gb18030',errors='strict')
    expected=[[s,e] for s in value['ExpectedStages'] for e in ('started','done')]
    current=build.diagnostics(work)
    reductions=retained_reductions(value['SourceReductionDiagnostics']['SourceDiagnostics'],current,
                                  value['SourceReductionDiagnostics']['ReviewedReadonlyBodies'])
    require(build.events(log)==expected and log.splitlines().count(MARKER)==1,'fisheye inspection stage sequence/completion differs')
    require(sha(value['SourceADF'])==sha(work/'input.adf')==value['SourceADFSHA256'],
            'fisheye read-only STA changed source or independent ADF copy')
    entries=artifacts(work)
    require(entries,'fisheye inspection produced no bound artifacts')
    if value['Mode']=='export':
        for n in ('generate_netlist/'+TARGET+'_sim.v','report_timing/'+TARGET+'.rtr','report_timing/'+TARGET+'_exception.rtr'):
            require(n in entries,'fisheye export expected artifact missing: '+n)
    else:
        require(TARGET+'.rtr' in entries and TARGET+'_exception.rtr' in entries,'fisheye native initialization reports missing')
        if value['Mode']=='report':require('route-dump.txt' in entries,'fisheye native route dump missing')
    return {'ActualEvents':build.events(log),'CompletionMarker':True,'Diagnostics':current,
        'RetainedReductionDiagnostics':reductions,'DiagnosticsCleared':reductions['DiagnosticsCleared'],
        'IndependentSourceDiagnosticReviewPassed':False,'InputDrift':drift(watched),
        'SourceADFUnchanged':True,'IndependentADFCopyUnchanged':True,'FinalCopySHA256':sha(work/'input.adf'),
        'Artifacts':entries}


def execute(path):
    value,watched=validate(path,require_alias=True,fresh=True);work=Path(value['WorkDirectory'])
    require(os.name=='nt','native fisheye inspection requires Windows')
    result={**value,'StagePlanSHA256':sha(path),'StartedUTC':utc(),'EDAExecuted':False,'ExecutionPassed':False,
            'ExitCode':None,'TimedOut':False,'StoppedForUnexpectedStage':False}
    write(work/'execution-start.json',result);process=None;start=time.monotonic()
    expected=[[s,e] for s in value['ExpectedStages'] for e in ('started','done')]
    try:
        with (work/'stdout.log').open('xb') as out,(work/'stderr.log').open('xb') as err:
            process=subprocess.Popen(value['Command'],cwd=work,stdout=out,stderr=err,shell=False,
                                     creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            result.update(EDAExecuted=True,OwnedPID=process.pid)
            while process.poll() is None:
                remaining=value['MaximumSeconds']-(time.monotonic()-start)
                if remaining<=0:result['TimedOut']=True;break
                try:process.wait(timeout=min(2,remaining))
                except subprocess.TimeoutExpired:pass
                current=build.events((work/'stdout.log').read_text(encoding='gb18030',errors='replace'))
                if current!=expected[:len(current)]:result['StoppedForUnexpectedStage']=True;break
    except BaseException as error:result['Error']=type(error).__name__+': '+str(error)
    finally:
        result['Cleanup']=(build.cleanup.stop_owned_tree(process,work,'bounded fisheye read-only inspection')
                           if process is not None and process.poll() is None else {'Complete':True,'ParentExited':True})
        if process is not None:result['ExitCode']=process.poll()
    try:
        result.update(evidence(value,work,watched))
        result['ExecutionPassed']=(result['ExitCode']==0 and result['EDAExecuted'] is True and not result['TimedOut']
            and not result['StoppedForUnexpectedStage'] and not result.get('Error') and result['InputDrift']==[]
            and result['Cleanup']['Complete'])
    except Exception as error:result['Error']=type(error).__name__+': '+str(error)
    result.update(FinishedUTC=utc(),ElapsedSeconds=round(time.monotonic()-start,3));write(work/'result.json',result)
    return result


def bind_receipt(path):
    path=Path(path).absolute();work=build.work_path(path.parent);saved=read(path)
    value,watched=validate(work/'stage-plan.json')
    require(path.name=='result.json' and all(saved.get(k)==v for k,v in value.items())
            and saved['StagePlanSHA256']==sha(work/'stage-plan.json') and saved.get('ExecutionPassed') is True
            and saved.get('EDAExecuted') is True and saved.get('ExitCode')==0 and saved.get('TimedOut') is False
            and saved.get('StoppedForUnexpectedStage') is False and not saved.get('Error')
            and saved.get('Cleanup',{}).get('Complete') is True,'unclean fisheye native inspection receipt')
    expected=evidence(value,work,watched)
    require(all(saved.get(k)==v for k,v in expected.items()) and saved['InputDrift']==[],
            'fisheye native receipt/source/log/artifact evidence differs')
    for name,h in expected['Artifacts'].items():add(watched,work/name,h)
    add(watched,path)
    return saved,watched


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--build-plan',type=Path);p.add_argument('--work-dir',type=Path)
    p.add_argument('--source-proof',type=Path)
    p.add_argument('--build-review',type=Path)
    p.add_argument('--mode',choices=('export','report','query'));p.add_argument('--body',type=Path)
    p.add_argument('--maximum-seconds',type=int,default=600);p.add_argument('--execute',type=Path)
    p.add_argument('--verify-result',type=Path);a=p.parse_args()
    if a.verify_result:bind_receipt(a.verify_result);print('{"Verified":true,"HardwareAccessed":false}');return 0
    if a.execute:
        v=execute(a.execute);print(json.dumps({k:v.get(k) for k in ('ExecutionPassed','ElapsedSeconds','Error')}));return 0 if v['ExecutionPassed'] else 1
    plan=prepare(a.build_plan,a.work_dir,a.mode,a.body,a.maximum_seconds,a.source_proof,a.build_review)
    print(json.dumps({'Prepared':True,'Plan':str(plan)}));return 0


if __name__=='__main__':raise SystemExit(main())
