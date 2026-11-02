"""Fresh, bounded native inspection of the runtime view-switch candidate.

Only report/export/query are supported. Each process uses a separate ADF copy;
this module cannot build a bitstream, program hardware or edit constraints.
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
from camera720_calibrated_inspect import query_commands

SELF = Path(__file__).resolve()
TARGET = build.TARGET
MARKER = 'CAMERA720_VIEW_TOGGLE_INSPECTION_COMPLETE'
INIT = 'mpnr_report_timing -force_to_run -delay_type min_max -max_path 1000 -nworst 4 -report_exception TRUE'
require, sha, read, write = build.require, build.sha, build.read, build.write


def prepare(build_plan, adf, work, mode, body=None):
    build_plan, adf = Path(build_plan).resolve(), Path(adf).resolve()
    work = build.work_path(work)
    require(mode in ('export','report','query') and not work.exists(), 'fresh read-only inspection required')
    p = build.validate(build_plan)
    require(adf.is_file() and adf.suffix=='.adf' and adf.is_relative_to(build.WORK.resolve()), 'candidate ADF required')
    result = read(build_plan.parent/'execution-result.json')
    require(result['BuildCompleted'] and result['InputDrift']==[], 'complete stable candidate build required')
    inputs = {**p['InputSHA256'], **p['PreparedSHA256'], str(build_plan):sha(build_plan),
              str(build_plan.parent/'execution-result.json'):sha(build_plan.parent/'execution-result.json'),
              str(adf):sha(adf), str(SELF):sha(SELF)}
    w = work.as_posix()
    if mode == 'export':
        require(body is None, 'export accepts no query body')
        original = (build_plan.parent/'timing.tcl').read_text(encoding='ascii')
        anchor = 'pnr -optimize_multi_corner_timing -fix_hold_violation\n'
        require(original.count(anchor)==1, 'build context differs')
        prefix = original[:original.index(anchor)+len(anchor)]
        tcl = (prefix+'report_timing -force_to_run -input_db_file {'+w+'/input.adf} -delay_type min_max -max_path 1000 -nworst 4 -report_exception TRUE\n'
               'if {[info script] ne {}} {\n    gen_netlist -force_to_run -input_db_file {'+w+'/input.adf} -func_sim_only\n'
               '    puts {'+MARKER+'}\n    flush stdout\n}\n')
        stages = ['Report Timing','Generate Netlist']
    else:
        if mode=='query':
            body = Path(body).resolve()
            inputs[str(body)] = sha(body)
            commands = query_commands(body.read_text(encoding='ascii'))
        else:
            require(body is None, 'route report accepts no custom body')
            commands = ['.switch_db -route -input {@WORK@/input.adf} -output {@WORK@/route-dump.txt}']
        tcl = ('set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG676\n'
               'add_design {'+w+'/dummy.v}\nif {[info script] ne {}} {\n'
               '    mpnr -input {'+w+'/input.adf}\n    '+INIT+'\n'
               +'\n'.join(commands).replace('@WORK@',w)+'\n    puts {'+MARKER+'}\n    flush stdout\n}\n')
        stages = []
    work.mkdir(parents=True)
    shutil.copyfile(adf, work/'input.adf')
    (work/'stage.tcl').write_text(tcl, encoding='ascii', newline='\n')
    (work/'dummy.v').write_text('module physical_dummy(input a, output y); assign y=a; endmodule\n',encoding='ascii',newline='\n')
    for name in ('stage.tcl','dummy.v','input.adf'):
        inputs[str(work/name)] = sha(work/name)
    plan = {'Schema':'camera720-view-toggle-inspection-v1','Target':TARGET,'Mode':mode,
            'CreatedUTC':datetime.now(timezone.utc).isoformat(),'BuildPlan':str(build_plan),
            'SourceADF':str(adf),'SourceADFSHA256':sha(adf),'WorkDirectory':str(work),
            'InputSHA256':inputs,'ExpectedStages':stages,'MaximumSeconds':300,
            'Command':[p['PDS']['Executable'],'-file',(work/'stage.tcl').as_posix(),
                       '-work_dir',w,'-project_name',TARGET],
            'HardwareAccessed':False,'BitstreamRequested':False,'TimingAccepted':False}
    write(work/'stage-plan.json',plan)
    return work/'stage-plan.json'


def execute(path):
    path = Path(path).resolve()
    p = read(path)
    work = build.work_path(path.parent)
    require(os.name=='nt' and p['Schema']=='camera720-view-toggle-inspection-v1' and p['Target']==TARGET,
            'native candidate inspection required')
    source_plan = Path(p['BuildPlan']).resolve()
    source = build.validate(source_plan)
    expected_command = [source['PDS']['Executable'],'-file',(work/'stage.tcl').as_posix(),
                        '-work_dir',work.as_posix(),'-project_name',TARGET]
    require(path.name=='stage-plan.json' and p['WorkDirectory']==str(work)
            and p['Mode'] in ('report','export','query') and p['MaximumSeconds']==300
            and p['Command']==expected_command
            and p['ExpectedStages']==(['Report Timing','Generate Netlist'] if p['Mode']=='export' else []),
            'inspection command, deadline, mode or directory differs')
    require(p['InputSHA256'].get(str(source_plan))==sha(source_plan)
            and p['InputSHA256'].get(str(SELF))==sha(SELF), 'inspection producer/build not bound')
    for name in ('stage.tcl','dummy.v','input.adf'):
        require(str(work/name) in p['InputSHA256'], 'unbound native stage input: '+name)
    require(not (work/'execution-start.json').exists(), 'inspection already executed')
    inputs = {**p['InputSHA256'],str(path):sha(path)}
    for name,digest in inputs.items():
        require(sha(name)==digest, 'inspection input drift: '+name)
    result = {**p,'StagePlanSHA256':sha(path),'StartedUTC':datetime.now(timezone.utc).isoformat(),
              'TimedOut':False,'ExitCode':None}
    write(work/'execution-start.json',result)
    process = None
    started = time.monotonic()
    try:
        with (work/'stdout.log').open('xb') as out,(work/'stderr.log').open('xb') as err:
            process = subprocess.Popen(p['Command'],cwd=work,stdout=out,stderr=err,
                shell=False,creationflags=subprocess.CREATE_NO_WINDOW)
            result['OwnedPID'] = process.pid
            try:
                result['ExitCode'] = process.wait(timeout=p['MaximumSeconds'])
            except subprocess.TimeoutExpired:
                result['TimedOut'] = True
    except BaseException as exc:
        result['Error'] = type(exc).__name__+': '+str(exc)
    finally:
        if process is not None and process.poll() is None:
            result['Cleanup'] = build.cleanup.stop_owned_tree(process,work,'timeout/interrupted')
        text = (work/'stdout.log').read_text(encoding='gb18030',errors='replace')
        result['ActualEvents'] = re.findall(r'^Process "([^"]+)" (started|done)\.',text,re.M)
        result['CompletionMarker'] = MARKER in text
        result['Diagnostics'] = [f'{f.relative_to(work)}: {line.strip()}'
            for f in work.rglob('*.log') for line in f.read_text(encoding='gb18030',errors='replace').splitlines()
            if re.match(r'\s*(C:|E:|F:|ERROR:|FATAL:)',line)]
        result['InputDrift'] = [n for n,h in inputs.items() if not Path(n).is_file() or sha(n)!=h]
        result['Passed'] = (result['ExitCode']==0 and not result['TimedOut'] and not result.get('Error')
            and result['ActualEvents']==[(s,e) for s in p['ExpectedStages'] for e in ('started','done')]
            and result['CompletionMarker'] and not result['Diagnostics'] and not result['InputDrift'])
        result['ElapsedSeconds'] = round(time.monotonic()-started,3)
        result['Artifacts'] = {f.relative_to(work).as_posix():sha(f) for f in work.rglob('*')
                               if f.is_file() and f.suffix in ('.log','.rtr','.v','.gnr','.txt','.fdc')}
        write(work/'result.json',result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build-plan',type=Path)
    parser.add_argument('--adf',type=Path)
    parser.add_argument('--work-dir',type=Path)
    parser.add_argument('--mode',choices=['export','report','query'])
    parser.add_argument('--body',type=Path)
    parser.add_argument('--execute-plan',type=Path)
    a = parser.parse_args()
    if a.execute_plan:
        r = execute(a.execute_plan)
        print(json.dumps({k:r[k] for k in ('Passed','ElapsedSeconds','ExitCode','InputDrift','Diagnostics')}))
        return 0 if r['Passed'] else 1
    path = prepare(a.build_plan,a.adf,a.work_dir,a.mode,a.body)
    print(json.dumps({'Prepared':True,'Plan':str(path)}))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
