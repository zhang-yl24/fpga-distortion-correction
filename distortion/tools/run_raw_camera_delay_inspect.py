"""Read-only queries/export bound to the independent input-delay candidate.

Only a completed independent upright diagnostic is accepted. New plans bind
its own source closure, native receipt, actual ADF and tools. Native execution
is explicit and bounded; no inherited physical names, repairs or exceptions.
"""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time

import prepare_raw_camera_delay as prep
import run_raw_camera_delay_diagnostic as diagnostic

SELF = Path(__file__).resolve()
SCHEMA = 'raw-camera-delay-readonly-inspection-v1'
MARKER = 'RAW_CAMERA_DELAY_INSPECTION_COMPLETE'
INIT = 'mpnr_report_timing -force_to_run -delay_type min_max -max_path 1000 -nworst 4 -report_exception TRUE'
require, sha = prep.require, prep.sha


def canonical(path, parent=prep.PROJECT):
    p = Path(path).absolute()
    require(p == p.resolve() and p.is_relative_to(parent) and p.is_file(), 'canonical existing input required: '+str(p))
    return p


def drift(watched):
    result = []
    for p, h in watched.items():
        try:
            if p != p.resolve() or not p.is_file() or sha(p) != h:
                result.append(str(p))
        except OSError:
            result.append(str(p))
    return result


def bind_technology_source(plan, watched):
    """Only this PDS installation's actual Logos2 technology library is allowed."""
    expected = (Path(plan['PDS']['Executable']).absolute().parent.parent /
                'arch/vendor/pango/logos2/common/lib/gtp_lib.v')
    value = plan['TechnologyPrimitiveSource']
    require(isinstance(value, dict) and value.get('Path') == str(expected)
            and expected == expected.resolve(), 'technology library escapes this PDS installation')
    require(value == prep.validate_primitive_library(expected), 'technology primitive proof differs')
    require(expected not in watched or watched[expected] == value['SHA256'], 'conflicting technology library identity')
    watched[expected] = value['SHA256']
    return expected


def bind(plan_path, source, expected_sha):
    path = canonical(plan_path, prep.WORK)
    work = prep.work_path(path.parent)
    require(path.name == 'plan.json', 'exact build plan.json required')
    plan = json.loads(path.read_text())
    require(plan.get('Schema') == prep.SCHEMA and plan.get('Target') == prep.TARGET, 'wrong upright build identity')
    expected, payloads, tcl = prep.recipe(work, plan['PDS']['Executable'], plan['MaximumSecondsForExternalExecutor'])
    require(set(plan) == set(expected)|{'PreparedUTC'} and {k:v for k,v in plan.items() if k!='PreparedUTC'} == expected,
            'upright build plan differs from its independent recipe')
    require((work/'timing.tcl').read_bytes() == tcl, 'upright build Tcl drift')
    require({p for p in (work/'compiled').rglob('*') if p.is_file()} == set(payloads), 'upright compiled inventory differs')
    watched = {canonical(prep.PROJECT/n):h for n,h in plan['InputSHA256'].items()}
    bind_technology_source(plan, watched)
    for p, data in payloads.items():
        require(canonical(p) == p and p.read_bytes() == data, 'upright compiled bytes differ')
        watched[p] = prep.baseline.paths.sha_bytes(data)
    result_path = canonical(work/'execution-result.json', prep.WORK)
    result = json.loads(result_path.read_text())
    require(result.get('Schema') == 'raw-camera-delay-diagnostic-execution-v1' and result.get('Target') == prep.TARGET,
            'wrong upright native receipt identity')
    require(result.get('ExecutionCompletedWithoutError') is True and result.get('NativeExitCode') == 0
            and result.get('SourcesStable') is True and result.get('ActualStagesComplete') is True
            and result.get('InputDrift') == [] and result.get('Diagnostics') == []
            and result.get('TimedOut') is False and result.get('StoppedForUnexpectedStage') is False
            and result.get('Cleanup',{}).get('Complete') is True
            and result.get('PlanSHA256') == sha(path), 'upright diagnostic did not complete cleanly')
    expected_events = [[s,e] for s in plan['ExpectedActualStages'] for e in ('started','done')]
    require(result.get('ActualEvents') == expected_events, 'upright native stage events differ')
    source = canonical(source, prep.WORK)
    require(source == work/'place_route'/(prep.TARGET+'_pnr.adf'), 'only this upright native final ADF is accepted')
    require(re.fullmatch('[0-9a-f]{64}', expected_sha) and sha(source) == expected_sha, 'requested upright ADF SHA differs')
    audit = result.get('DatabaseSnapshotAudit',{})
    before = canonical(work/'pre-sta-final.adf', prep.WORK)
    require(audit.get('UnchangedAcrossSTA') is True and audit.get('Snapshot') == str(before)
            and audit.get('FinalRoutedDatabase') == str(source)
            and audit.get('SnapshotSHA256') == expected_sha and audit.get('FinalRoutedDatabaseSHA256') == expected_sha
            and sha(before) == expected_sha, 'upright ADF snapshot proof differs')
    require(result.get('ExecutorSHA256') == sha(Path(diagnostic.__file__).resolve()), 'build executor changed since execution')
    logs=result.get('LogSHA256',{})
    require(isinstance(logs,dict) and {'execution-stdout.log','execution-stderr.log'} <= set(logs),
            'upright native log bindings missing')
    for name, h in logs.items():
        watched[canonical(work/name, work)] = h
    for p in (path, result_path, source, before, work/'timing.tcl', SELF,
              Path(diagnostic.__file__).resolve(), Path(prep.__file__).resolve()):
        watched[canonical(p)] = sha(p)
    watched[Path(plan['PDS']['Executable'])] = plan['PDS']['ExecutableSHA256']
    require(not drift(watched), 'upright build/source/receipt/tool drift')
    return plan, watched


def query_commands(body):
    require(body and body.isascii(), 'nonempty ASCII body required')
    brace = r'\{[^{}\r\n]*\}'
    patterns = [r'puts '+brace,
        r'get_(?:pins|ports|clocks) -hierarchical -regexp '+brace,
        r'get_(?:ports|clocks) -regexp '+brace,
        r'show -(?:design_net|dev_instance) '+brace,
        r'\.switch_db -route -input \{@WORK@/input\.adf\} -output \{@WORK@/[A-Za-z0-9_-]+\.txt\}',
        r'dump_net -grid_unit '+brace+r' -print_site -out_file \{@WORK@/[A-Za-z0-9_-]+\.txt\}',
        r'report_path_timing -delay_type min_max -max_path (?:[1-9][0-9]{0,2}|1000) -nworst [1-8] -report_exception TRUE -from '+brace+r' -to '+brace,
        r'(?:mpnr_report_timing|report_path_timing|show|show_device|get_pins|get_ports|get_clocks) -help']
    commands = []
    for line in body.splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        require(not re.search(r'\\[{}\r\n]',line) and all(ord(c) >= 32 for c in line),
                'escaped braces/continuations/control characters forbidden')
        require(any(re.fullmatch(p,line) for p in patterns), 'unsupported read-only query: '+line[:100])
        require(MARKER not in line, 'reserved completion marker')
        commands.append(line)
    require(commands and len(commands) <= 300, 'query command count out of bounds')
    return commands


def render(mode, original, base, work, body=None):
    aw = work.as_posix()
    if mode == 'query':
        commands = query_commands(body)
        # Native get_pins needs STA context; only one initialization per process.
        return ('set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG676\n'
                'add_design {'+aw+'/dummy.v}\nif {[info script] ne {}} {\n'
                '    mpnr -input {'+aw+'/input.adf}\n    '+INIT+'\n'
                +'\n'.join(commands).replace('@WORK@',aw)+'\n    puts {'+MARKER+'}\n    flush stdout\n}\n')
    require(mode == 'export' and body is None, 'export accepts no query body')
    suffix = ('if {[file exists '+prep.literal(base/'place_route'/(prep.TARGET+'_pnr.adf'))+']} {\n'
              '    file copy '+prep.literal(base/'place_route'/(prep.TARGET+'_pnr.adf'))+' '+prep.literal(base/'pre-sta-final.adf')+'\n}\n'
              'report_timing -force_to_run -delay_type min_max -max_path 1000 -nworst 4 -report_exception TRUE\n')
    require(original.endswith(suffix) and original.count(suffix)==1, 'upright build suffix differs')
    prefix = original[:-len(suffix)]
    require(prefix.endswith('pnr -optimize_multi_corner_timing -fix_hold_violation\n'), 'upright placement context differs')
    # PDS flow context retains real source/IP/FDC roles. Explicit input_db_file
    # selects only fresh Report Timing and Generate Netlist actual stages.
    return (prefix+'report_timing -force_to_run -input_db_file {'+aw+'/input.adf} -delay_type min_max -max_path 1000 -nworst 4 -report_exception TRUE\n'
            'if {[info script] ne {}} {\n    gen_netlist -force_to_run -input_db_file {'+aw+'/input.adf} -func_sim_only\n'
            '    puts {'+MARKER+'}\n    flush stdout\n}\n')


def recipe(build_plan, source, source_sha, work, mode, body_path=None, maximum=300):
    work = prep.work_path(work)
    require(type(maximum) is int and 120 <= maximum <= 300, 'inspection bound must be120..300 seconds')
    plan, watched = bind(build_plan, source, source_sha)
    body = None
    if mode == 'query':
        body_path = canonical(body_path, prep.WORK)
        watched[body_path] = sha(body_path)
        body = body_path.read_text(encoding='ascii')
    else:
        require(body_path is None, 'export accepts no body path')
    tcl = render(mode, (Path(build_plan).parent/'timing.tcl').read_text(encoding='ascii'), Path(build_plan).absolute().parent, work, body)
    value = {'Schema':SCHEMA,'Target':prep.TARGET,'Mode':mode,'WorkDirectory':str(work),
        'BuildPlan':str(Path(build_plan).absolute()),'BuildPlanSHA256':sha(build_plan),
        'SourceADF':str(Path(source).absolute()),'SourceADFSHA256':source_sha,
        'QueryBody':str(body_path) if body_path else None,'MaximumSeconds':maximum,
        'ExpectedActualStages':[] if mode=='query' else ['Report Timing','Generate Netlist'],
        'InputSHA256':{str(p):h for p,h in watched.items()},'TclSHA256':prep.baseline.paths.sha_bytes(tcl.encode('ascii')),
        'Command':[plan['PDS']['Executable'],'-file',(work/'stage.tcl').as_posix(),'-work_dir',work.as_posix(),'-project_name',prep.TARGET],
        'HardwareAccessed':False,'BitstreamRequested':False,'TimingAccepted':False,'HardwareReleaseAllowed':False,
        'Limits':'Read-only independent upright inspection; native timing and CDC acceptance require separate review.'}
    return value,tcl,watched


def prepare(*args, **kwargs):
    value,tcl,watched = recipe(*args, **kwargs)
    work = Path(value['WorkDirectory'])
    require(not work.exists(), 'fresh inspection directory required')
    require(not drift(watched), 'input drift before preparation')
    work.mkdir()
    shutil.copyfile(value['SourceADF'], work/'input.adf')
    require(sha(work/'input.adf') == value['SourceADFSHA256'], 'ADF copy differs')
    (work/'stage.tcl').write_text(tcl,encoding='ascii',newline='\n')
    shutil.copyfile(SELF,work/'executor-snapshot.py')
    if value['Mode']=='query':
        (work/'dummy.v').write_text('module physical_dummy(input a, output y); assign y=a; endmodule\n',encoding='ascii',newline='\n')
    value['PreparedUTC'] = prep.utc()
    diagnostic.write(work/'stage-plan.json',value)
    return work/'stage-plan.json'


def validate_prepared(path):
    path = canonical(path,prep.WORK)
    work = prep.work_path(path.parent)
    require(path.name=='stage-plan.json','exact stage-plan.json required')
    value = json.loads(path.read_text())
    require(value.get('Schema')==SCHEMA and value.get('Target')==prep.TARGET,'upright inspection identity differs')
    expected,tcl,watched = recipe(value['BuildPlan'],value['SourceADF'],value['SourceADFSHA256'],work,
                                value['Mode'],value['QueryBody'],value['MaximumSeconds'])
    require(set(value)==set(expected)|{'PreparedUTC'} and {k:v for k,v in value.items() if k!='PreparedUTC'}==expected,
            'inspection plan differs from bound recipe')
    files={'input.adf','stage.tcl','executor-snapshot.py','stage-plan.json'}
    if value['Mode']=='query':files.add('dummy.v')
    require({p.name for p in work.iterdir()}==files,'inspection stage reused or contaminated')
    require((work/'stage.tcl').read_bytes()==tcl.encode('ascii') and sha(work/'input.adf')==value['SourceADFSHA256']
            and sha(work/'executor-snapshot.py')==sha(SELF),'inspection prepared artifact drift')
    if value['Mode']=='query':
        require((work/'dummy.v').read_bytes()==b'module physical_dummy(input a, output y); assign y=a; endmodule\n','dummy context changed')
    for name in files:watched[canonical(work/name,work)]=sha(work/name)
    require(not drift(watched),'inspection input drift')
    return value,watched


def execute(path):
    value,watched = validate_prepared(path)
    require(os.name=='nt','native inspection requires Windows')
    work=Path(value['WorkDirectory']);result={**value,'StagePlanSHA256':sha(path),'StartedUTC':prep.utc(),
        'EDAExecuted':False,'ExecutionPassed':False,'TimedOut':False,'StoppedForUnexpectedStage':False,'ExitCode':None}
    diagnostic.write(work/'execution-start.json',result)
    process=None;started=time.monotonic()
    expected=[(s,e) for s in value['ExpectedActualStages'] for e in ('started','done')]
    try:
        with (work/'stdout.log').open('xb') as out,(work/'stderr.log').open('xb') as err:
            process=subprocess.Popen(value['Command'],cwd=work,stdout=out,stderr=err,shell=False,
                                     creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            result.update(EDAExecuted=True,OwnedPID=process.pid)
            while process.poll() is None:
                remaining=value['MaximumSeconds']-(time.monotonic()-started)
                if remaining<=0:result['TimedOut']=True;break
                try:process.wait(timeout=min(2,remaining))
                except subprocess.TimeoutExpired:pass
                events=diagnostic.stage_events((work/'stdout.log').read_text(encoding='gb18030',errors='replace'))
                if events!=expected[:len(events)]:result['StoppedForUnexpectedStage']=True;break
    except BaseException as error:
        result['Error']=type(error).__name__+': '+str(error)
    finally:
        if process is not None:
            if process.poll() is None:result['Cleanup']=diagnostic.cleanup.stop_owned_tree(process,work,'bounded inspection')
            else:result['Cleanup']={'Complete':True,'OwnedPID':process.pid,'ParentExited':True,'DescendantLivenessIndependentlyVerified':False}
            result['ExitCode']=process.poll()
        else:result['Cleanup']={'Complete':True,'Required':False}
    log=(work/'stdout.log').read_text(encoding='gb18030',errors='replace') if (work/'stdout.log').exists() else ''
    events=diagnostic.stage_events(log)
    diagnostics=[]
    for p in work.rglob('*.log'):
        diagnostics += [p.relative_to(work).as_posix()+': '+line.strip() for line in re.findall(
            r'(?m)^\s*(?:E:|F:|ERROR:|FATAL:|Traceback).*$',p.read_text(encoding='gb18030',errors='replace'))]
    netlist=work/'generate_netlist'/(prep.TARGET+'_sim.v')
    nettext=netlist.read_text(encoding='ascii',errors='replace') if netlist.is_file() else ''
    netvalid=bool(re.search(r'(?m)^module '+prep.TARGET+r'\s*$',nettext)) and bool(re.search(r'V_\w+\s*/\*\s*(?:CLMA|CLMS|IOLHR)_\d+_\d+\s*\*/',nettext))
    result.update(FinishedUTC=prep.utc(),ElapsedSeconds=round(time.monotonic()-started,3),ActualEvents=events,
        InputDrift=drift(watched),Diagnostics=diagnostics,CompletionMarker=MARKER in log,
        InputADFUnchanged=sha(work/'input.adf')==value['SourceADFSHA256'],NativeNetlistWithFFloc=netvalid if value['Mode']=='export' else None,
        Netlist={'Path':str(netlist),'SHA256':sha(netlist),'Bytes':netlist.stat().st_size} if netlist.is_file() else None,
        Artifacts={p.relative_to(work).as_posix():sha(p) for p in work.rglob('*') if p.is_file()
                   and p.suffix in ('.tcl','.log','.rtr','.v','.gnr','.txt','.fdc')})
    result['ExecutionPassed']=(result['ExitCode']==0 and not result.get('Error') and not result['TimedOut']
        and not result['StoppedForUnexpectedStage'] and not result['InputDrift'] and not diagnostics
        and events==expected and result['CompletionMarker'] and result['InputADFUnchanged']
        and result['Cleanup'].get('Complete',False) and (value['Mode']!='export' or netvalid))
    diagnostic.write(work/'result.json',result)
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--plan',type=Path);p.add_argument('--source-adf',type=Path);p.add_argument('--source-adf-sha256')
    p.add_argument('--name');p.add_argument('--mode',choices=('query','export'));p.add_argument('--body',type=Path)
    p.add_argument('--maximum-seconds',type=int,default=300);p.add_argument('--stage-plan',type=Path)
    modes=p.add_mutually_exclusive_group();modes.add_argument('--prepare-only',action='store_true')
    modes.add_argument('--validate-only',action='store_true');modes.add_argument('--execute',action='store_true')
    a=p.parse_args()
    if a.stage_plan:
        require(not any((a.plan,a.source_adf,a.source_adf_sha256,a.name,a.mode,a.body,a.prepare_only)), 'stage-plan accepts only validation or execution')
        if a.execute:result=execute(a.stage_plan)
        else:
            value,_=validate_prepared(a.stage_plan);result={'Validated':True,'StagePlan':str(a.stage_plan),'ExpectedActualStages':value['ExpectedActualStages']}
    else:
        require(a.plan and a.source_adf and a.source_adf_sha256 and a.name and a.mode,'build plan, exact ADF/hash, name and mode required')
        args=(a.plan,a.source_adf,a.source_adf_sha256,prep.WORK/a.name,a.mode,a.body,a.maximum_seconds)
        if a.prepare_only or a.execute:
            stage=prepare(*args)
            result=execute(stage) if a.execute else {'Prepared':True,'StagePlan':str(stage),'EDAExecuted':False,'HardwareAccessed':False}
        else:
            value,_,_=recipe(*args);result={'Validated':True,'ExpectedActualStages':value['ExpectedActualStages'],'EDAExecuted':False,'HardwareAccessed':False}
    print(json.dumps({k:result[k] for k in ('Prepared','Validated','StagePlan','ExecutionPassed','ExitCode','ElapsedSeconds','InputDrift','Diagnostics','ExpectedActualStages','EDAExecuted','HardwareAccessed') if k in result}))
    return 0 if result.get('ExecutionPassed',True) else 1


if __name__=='__main__':raise SystemExit(main())
