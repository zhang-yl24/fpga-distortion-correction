"""Bound fresh inspection of the view-switch candidate and its reset derivative.

No synthesis, routing, bitstream or hardware commands are accepted. Original
inspector receipts can also be rebound for exact same-ADF reset provenance.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time

import camera720_view_toggle_build as build
import camera720_view_toggle_native as native

SELF = Path(__file__).resolve()
SCHEMA = 'camera720-view-toggle-final-inspection-v1'
TARGET, require, sha, read = build.TARGET, build.require, build.sha, build.read
INIT = native.INIT
MARKER = 'CAMERA720_VIEW_TOGGLE_FINAL_INSPECTION_COMPLETE'
DUMMY = 'module physical_dummy(input a, output y); assign y=a; endmodule\n'
SUFFIXES = {'.tcl', '.log', '.rtr', '.v', '.gnr', '.txt', '.fdc'}


def utc():
    return datetime.now(timezone.utc).isoformat()


def ref(path):
    path = Path(path).resolve()
    return {'Path': str(path), 'SHA256': sha(path)}


def add(watched, path, digest=None):
    path = Path(path).absolute()
    require(path == path.resolve() and path.is_file(), 'canonical existing input required: '+str(path))
    value = sha(path)
    require(digest is None or value == digest, 'input digest differs: '+str(path))
    require(path not in watched or watched[path] == value, 'conflicting input identity')
    watched[path] = value
    return path


def merge(watched, other):
    for path, digest in other.items():
        add(watched, path, digest)


def drift(watched):
    return [str(p) for p, h in watched.items() if not p.is_file() or sha(p) != h]


def diagnostics(work):
    return [f'{p.relative_to(work).as_posix()}: {line.strip()}'
        for p in sorted(Path(work).rglob('*.log'))
        for line in p.read_text(encoding='gb18030', errors='replace').splitlines()
        if re.match(r'\s*(C:|E:|F:|CRITICAL:|ERROR:|FATAL:|Traceback)', line)]


def artifacts(work):
    return {p.relative_to(work).as_posix(): sha(p) for p in Path(work).rglob('*')
            if p.is_file() and p.suffix in SUFFIXES}


def events(log):
    return [list(v) for v in re.findall(r'^Process "([^"]+)" (started|done)\.', log, re.M)]


def export_prefix(build_plan):
    text = (Path(build_plan).parent/'timing.tcl').read_text(encoding='ascii')
    anchor = 'pnr -optimize_multi_corner_timing -fix_hold_violation\n'
    require(text.count(anchor) == 1, 'candidate timing context differs')
    return text[:text.index(anchor)+len(anchor)]


def render(build_plan, work, mode, body=None, marker=MARKER):
    require(mode in ('export', 'report', 'query'), 'read-only mode required')
    require(body is None or marker not in body, 'reserved completion marker in query')
    w = Path(work).as_posix()
    if mode == 'export':
        require(body is None, 'export accepts no query body')
        return (export_prefix(build_plan)+'report_timing -force_to_run -input_db_file {'+w+
            '/input.adf} -delay_type min_max -max_path 1000 -nworst 4 -report_exception TRUE\n'
            'if {[info script] ne {}} {\n    gen_netlist -force_to_run -input_db_file {'+w+
            '/input.adf} -func_sim_only\n    puts {'+marker+'}\n    flush stdout\n}\n')
    commands = native.query_commands(body) if mode == 'query' else [
        '.switch_db -route -input {@WORK@/input.adf} -output {@WORK@/route-dump.txt}']
    require(mode == 'query' or body is None, 'report accepts no custom body')
    return ('set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG676\n'
        'add_design {'+w+'/dummy.v}\nif {[info script] ne {}} {\n    mpnr -input {'+w+
        '/input.adf}\n    '+INIT+'\n'+ '\n'.join(commands).replace('@WORK@',w)+
        '\n    puts {'+marker+'}\n    flush stdout\n}\n')


def native_outputs(value, work):
    mode = value['Mode']
    report = work/('report_timing' if mode == 'export' else '')/(TARGET+'.rtr')
    require(report.is_file(), 'native candidate timing report missing')
    with report.open(encoding='utf-8-sig') as f:
        header = ''.join(f.readline() for _ in range(16))
    require(re.findall(r'(?m)^\| Design\s*:\s*(\S+)\s*$',header) == [TARGET],
            'native report has another Design')
    result = {'TimingReport': {**ref(report), 'Bytes': report.stat().st_size}}
    if mode == 'export':
        net = work/'generate_netlist'/(TARGET+'_sim.v')
        text = net.read_text(encoding='utf-8-sig')
        require(re.findall(r'(?m)^module\s+(\w+)',text) == [TARGET] and
                re.search(r'V_\w+\s*/\*\s*(?:CLMA|CLMS|IOLHR)_\d+_\d+\s*\*/',text),
                'native placed netlist missing or another target')
        result.update(Netlist={**ref(net), 'Bytes': net.stat().st_size}, NativeNetlistWithFFloc=True)
    return result


def bind_native_receipt(path):
    from camera720_view_toggle_receipts import bind_native_receipt as shared
    return shared(path)


def bind_source_receipt(path):
    candidate = read(path)
    if candidate.get('Schema') == 'camera720-view-toggle-hold-route-application-v1':
        import camera720_view_toggle_route as routing
        return routing.bind_completed(path)
    import camera720_view_toggle_reset_apply as application
    return application.bind_completed(path)


def prepare(build_plan, adf, work, mode, source_receipt=None, body=None):
    build_plan, adf = Path(build_plan).resolve(), Path(adf).resolve()
    work = build.work_path(work); plan = build.validate(build_plan)
    require(not work.exists() and adf.is_file() and adf.suffix == '.adf' and
            adf.is_relative_to(build.WORK.resolve()), 'fresh stage and candidate ADF required')
    watched = {}
    for name,h in {**plan['InputSHA256'],**plan['PreparedSHA256']}.items(): add(watched,name,h)
    for p in (build_plan,adf,SELF,Path(build.__file__),Path(native.__file__)): add(watched,p)
    source = None
    if source_receipt:
        source, inputs = bind_source_receipt(source_receipt)
        merge(watched,inputs)
        require(source['ResultADF']['Path'] == str(adf) and source['ResultADFSHA256'] == sha(adf)
                and source['BuildPlan'] == str(build_plan), 'source receipt belongs to another ADF')
    body_path = Path(body).resolve() if body else None
    if body_path: add(watched,body_path)
    text = render(build_plan,work,mode,body_path.read_text(encoding='ascii') if body_path else None)
    work.mkdir(); shutil.copyfile(adf,work/'input.adf')
    (work/'dummy.v').write_text(DUMMY,encoding='ascii',newline='\n')
    (work/'stage.tcl').write_text(text,encoding='ascii',newline='\n')
    for name in ('input.adf','dummy.v','stage.tcl'): add(watched,work/name)
    stages = ['Report Timing','Generate Netlist'] if mode == 'export' else []
    value = {'Schema':SCHEMA,'Target':TARGET,'Mode':mode,'BuildPlan':str(build_plan),
        'BuildPlanSHA256':sha(build_plan),'SourceADF':str(adf),'SourceADFSHA256':sha(adf),
        'SourceReceipt':ref(source_receipt) if source_receipt else None,
        'QueryBody':str(body_path) if body_path else None,'WorkDirectory':str(work),
        'MaximumSeconds':300,'ExpectedStages':stages,'CreatedUTC':utc(),
        'InputSHA256':{str(p):h for p,h in watched.items()},
        'Command':[plan['PDS']['Executable'],'-file',(work/'stage.tcl').as_posix(),
                   '-work_dir',work.as_posix(),'-project_name',TARGET],
        'HardwareAccessed':False,'BitstreamRequested':False,'TimingAccepted':False,
        'HardwareReleaseAllowed':False}
    build.write(work/'stage-plan.json',value)
    return work/'stage-plan.json'


def check_stage(path):
    path = Path(path).resolve(); work = build.work_path(path.parent); value = read(path)
    require(path.name == 'stage-plan.json' and value.get('Schema') == SCHEMA and
            value.get('Target') == TARGET and value['WorkDirectory'] == str(work), 'wrong final stage')
    watched = {}
    for name,h in value['InputSHA256'].items(): add(watched,name,h)
    require(value['InputSHA256'].get(str(SELF)) == sha(SELF), 'final inspector producer unbound')
    plan = build.validate(value['BuildPlan'])
    for name,h in {**plan['InputSHA256'],**plan['PreparedSHA256']}.items():
        require(value['InputSHA256'].get(name) == h, 'final stage omits current build closure')
    require(value['InputSHA256'].get(str(Path(value['BuildPlan']))) == value['BuildPlanSHA256']
            and value['InputSHA256'].get(value['SourceADF']) == value['SourceADFSHA256'],
            'final stage source/build unbound')
    if value['SourceReceipt']:
        receipt = value['SourceReceipt']
        require(ref(receipt['Path']) == receipt, 'final source receipt digest differs')
        source, bound = bind_source_receipt(receipt['Path'])
        require(source['ResultADF']['Path'] == value['SourceADF'] and
                source['ResultADFSHA256'] == value['SourceADFSHA256'] and
                source['BuildPlan'] == value['BuildPlan'], 'final source receipt belongs to another ADF')
        for p,h in bound.items():
            require(value['InputSHA256'].get(str(p)) == h, 'final stage omits source receipt closure')
    require(value['BuildPlanSHA256'] == sha(value['BuildPlan']) and value['MaximumSeconds'] == 300 and
            value['Command'] == [plan['PDS']['Executable'],'-file',(work/'stage.tcl').as_posix(),
                '-work_dir',work.as_posix(),'-project_name',TARGET], 'final command differs')
    body = Path(value['QueryBody']).read_text(encoding='ascii') if value['QueryBody'] else None
    require((work/'stage.tcl').read_text(encoding='ascii') == render(value['BuildPlan'],work,value['Mode'],body)
            and (work/'dummy.v').read_text(encoding='ascii') == DUMMY and
            sha(work/'input.adf') == value['SourceADFSHA256'] == sha(value['SourceADF']),
            'final input or instructions changed')
    require(value['ExpectedStages'] == (['Report Timing','Generate Netlist'] if value['Mode']=='export' else []),
            'final stage sequence differs')
    for flag in ('HardwareAccessed','BitstreamRequested','TimingAccepted','HardwareReleaseAllowed'):
        require(value.get(flag) is False,'read-only stage overclaims '+flag)
    add(watched,path)
    return value,watched


def execute(path):
    value,watched = check_stage(path); work = Path(value['WorkDirectory'])
    require(os.name == 'nt' and not (work/'execution-start.json').exists(), 'fresh native Windows inspection required')
    result = {**value,'StagePlanSHA256':sha(path),'StartedUTC':utc(),'EDAExecuted':False,
        'ExecutionPassed':False,'TimedOut':False,'ExitCode':None}; process=None; start=time.monotonic()
    build.write(work/'execution-start.json',result)
    try:
        with (work/'stdout.log').open('xb') as out, (work/'stderr.log').open('xb') as err:
            process = subprocess.Popen(value['Command'],cwd=work,stdout=out,stderr=err,shell=False,
                creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0)); result.update(EDAExecuted=True,OwnedPID=process.pid)
            try: result['ExitCode'] = process.wait(timeout=value['MaximumSeconds'])
            except subprocess.TimeoutExpired: result['TimedOut'] = True
    except BaseException as e: result['Error'] = type(e).__name__+': '+str(e)
    finally:
        if process is not None and process.poll() is None:
            result['Cleanup'] = build.cleanup.stop_owned_tree(process,work,'bounded final inspection')
        else: result['Cleanup'] = {'Complete':True,'ParentExited':True}
        result['ElapsedSeconds'] = round(time.monotonic()-start,3)
    try:
        log = (work/'stdout.log').read_text(encoding='gb18030',errors='replace')
        result.update(ActualEvents=events(log),CompletionMarker=MARKER in log,Diagnostics=diagnostics(work),
            InputDrift=drift(watched),InputADFUnchanged=sha(work/'input.adf')==value['SourceADFSHA256'],
            Artifacts=artifacts(work),**native_outputs(value,work))
        result['ExecutionPassed'] = (result['ExitCode']==0 and not result['TimedOut'] and not result.get('Error')
            and result['ActualEvents']==[[s,e] for s in value['ExpectedStages'] for e in ('started','done')]
            and result['CompletionMarker'] and result['InputDrift']==result['Diagnostics']==[]
            and result['InputADFUnchanged'] and result['Cleanup']['Complete'])
    except Exception as e: result['Error'] = type(e).__name__+': '+str(e)
    build.write(work/'result.json',result)
    return result


def bind_receipt(path):
    path=Path(path).resolve(); work=build.work_path(path.parent); value=read(path)
    if value.get('Schema') == 'camera720-view-toggle-inspection-v1': return bind_native_receipt(path)
    stage,watched = check_stage(work/'stage-plan.json')
    require(path.name=='result.json' and all(value.get(k)==v for k,v in stage.items()) and
            value['StagePlanSHA256']==sha(work/'stage-plan.json') and value.get('ExecutionPassed') is True
            and value.get('EDAExecuted') is True
            and value.get('ExitCode')==0 and value.get('TimedOut') is False and not value.get('Error')
            and value.get('InputDrift')==value.get('Diagnostics')==[] and value.get('InputADFUnchanged') is True
            and value.get('Cleanup',{}).get('Complete') is True,'unclean final inspection receipt')
    log=(work/'stdout.log').read_text(encoding='gb18030',errors='replace')
    require(value['ActualEvents']==events(log)==[[s,e] for s in stage['ExpectedStages'] for e in ('started','done')]
            and MARKER in log and value.get('CompletionMarker') is True and diagnostics(work)==[]
            and value['Artifacts']==artifacts(work), 'final artifacts/logs differ')
    for name,h in value['Artifacts'].items(): add(watched,work/name,h)
    for key,v in native_outputs(value,work).items(): require(value[key]==v,'final native output differs: '+key)
    add(watched,path); add(watched,SELF)
    return value,watched


def main():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--build-plan',type=Path)
    p.add_argument('--adf',type=Path);p.add_argument('--work-dir',type=Path)
    p.add_argument('--mode',choices=['export','report','query']);p.add_argument('--source-receipt',type=Path)
    p.add_argument('--body',type=Path);p.add_argument('--execute-plan',type=Path);a=p.parse_args()
    if a.execute_plan:
        r=execute(a.execute_plan);print(json.dumps({k:r.get(k) for k in ('ExecutionPassed','ExitCode','ElapsedSeconds','Error')}))
        return 0 if r['ExecutionPassed'] else 1
    path=prepare(a.build_plan,a.adf,a.work_dir,a.mode,a.source_receipt,a.body)
    print(json.dumps({'Prepared':True,'Plan':str(path)}));return 0


if __name__=='__main__': raise SystemExit(main())
