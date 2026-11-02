"""Read-only bounded inspection of this measured-candidate720 build only.

No old transport/raw authority, repairs or release is inherited. Native build
completion and exact generated-source/compiled/Tcl/receipt bindings are required.
"""
import argparse
import hashlib
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
import sys

import prepare_camera720_calibrated as prep
import run_camera720_calibrated_diagnostic as diagnostic

SELF = Path(__file__).resolve()
SCHEMA = 'camera720-calibrated-readonly-inspection-v1'
MARKER = 'CAMERA720_CALIBRATED_INSPECTION_COMPLETE'
INIT = 'mpnr_report_timing -force_to_run -delay_type min_max -max_path 1000 -nworst 4 -report_exception TRUE'
require, sha = prep.require, prep.sha


def utc():
    return datetime.now(timezone.utc).isoformat()


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


def scan_diagnostics(work):
    """Critical native diagnostics remain failures even when PDS returns zero."""
    result = []
    for path in sorted(Path(work).rglob('*.log')):
        text = path.read_text(encoding='gb18030', errors='replace')
        result.extend(path.relative_to(work).as_posix()+': '+line.strip() for line in re.findall(
            r'(?m)^\s*(?:C:|E:|F:|CRITICAL:|ERROR:|FATAL:|Traceback).*$', text))
    return result


def native_netlist_valid(path):
    text = path.read_text(encoding='ascii', errors='replace') if path.is_file() else ''
    return (re.findall(r'(?m)^module\s+(\w+)', text) == [prep.TARGET]
            and bool(re.search(r'V_\w+\s*/\*\s*(?:CLMA|CLMS|IOLHR)_\d+_\d+\s*\*/', text)))


def timing_report(work,mode):
    path=work/('report_timing' if mode=='export' else '')/(prep.TARGET+'.rtr')
    if not path.is_file():
        return None
    with path.open(encoding='utf-8-sig',errors='replace') as stream:
        header=''.join(stream.readline() for _ in range(16))
    if re.findall(r'(?m)^\| Design\s*:\s*(\S+)\s*$',header)!=[prep.TARGET]:
        return None
    return {'Path':str(path),'SHA256':sha(path),'Bytes':path.stat().st_size}


def readonly_review_payload(plan_path,receipt_path,source,result):
    """Explicit file-bound permission to inspect known width diagnostics only."""
    items=result.get('Diagnostics')
    require(result.get('ExecutionCompletedWithoutError') is False and isinstance(items,list) and items,
            'failed diagnostic set required for a read-only review')
    pattern=(r'[^:\r\n]+: C: Sdm-3003: \[[^\r\n]+\] Reduce accumulator ([A-Za-z_][A-Za-z0-9_]*) '
             r'size from [0-9]+ to [0-9]+\. If this is not intended behavior, please drive \1 with valid values\.')
    require(all(isinstance(x,str) and re.fullmatch(pattern,x) for x in items),
            'only explicit accumulator-width critical diagnostics permit read-only investigation; other C/E/F remain blocked')
    return {'Schema':'camera720-calibrated-failed-build-readonly-review-v1',
        'Scope':'ReadOnlyInspectionOfFailedCandidate',
        'BuildPlan':{'Path':str(plan_path),'SHA256':sha(plan_path)},
        'BuildReceipt':{'Path':str(receipt_path),'SHA256':sha(receipt_path)},
        'SourceADF':{'Path':str(source),'SHA256':sha(source)},
        'Diagnostics':items,'LogSHA256':result['LogSHA256'],
        'BuildExecutionCompletedWithoutError':False,'BuildDiagnosticsCleared':False,
        'TimingAccepted':False,'HardwareReleaseAllowed':False,
        'Limits':'Exact known-width diagnostics may be investigated read-only. The original failed receipt and all timing/functional issues remain unaccepted.'}


def bind(plan_path,source,expected_sha,review_path=None,review_sha=None):
    path=canonical(plan_path,prep.WORK);work=prep.work_path(path.parent)
    require(path.name=='plan.json','exact build plan.json required')
    plan=json.loads(path.read_text(encoding='utf-8'))
    require(plan.get('Schema')==prep.SCHEMA and plan.get('Target')==prep.TARGET,'wrong calibrated720 build identity')
    # The execution validator only accepts a fresh directory. Reconstruct its
    # complete deterministic recipe here, permitting actual native artifacts.
    expected,payloads,tcl=prep.recipe(plan['Request']['Path'],work,plan['PDS']['Executable'],plan['MaximumSecondsForExternalExecutor'])
    require(set(plan)==set(expected)|{'PreparedUTC'} and isinstance(plan['PreparedUTC'],str) and plan['PreparedUTC']
            and {k:v for k,v in plan.items() if k!='PreparedUTC'}==expected,'calibrated720 build plan differs from recipe')
    require((work/'timing.tcl').read_bytes()==tcl,'calibrated720 build Tcl drift')
    actual={p for area in ('source','compiled') for p in (work/area).rglob('*') if p.is_file()}
    require(actual==set(payloads),'generated-source/compiled inventory differs')
    watched={Path(p):h for p,h in plan['InputSHA256'].items()}
    for p,data in payloads.items():
        require(p==p.resolve() and p.read_bytes()==data,'generated-source or compiled bytes differ')
        watched[p]=hashlib.sha256(data).hexdigest()
    generated_top=work/'source'/prep.TOP
    generated_header=work/'source'/prep.HEADER
    compiled_top=work/'compiled'/prep.TOP
    compiled_header=work/'compiled'/prep.HEADER
    require(all(p in payloads for p in (generated_top,generated_header,compiled_top,compiled_header)),
            'explicit current generated/compiled top and header required')
    require(plan['GeneratedSourceSHA256'][str(generated_top)]==sha(generated_top)
            and plan['GeneratedSourceSHA256'][str(generated_header)]==sha(generated_header),
            'generated top/header identity differs')
    for p in (compiled_top,compiled_header):
        matches=[x for x in plan['CompiledInputs'] if x['CompiledPath']==str(p)]
        require(len(matches)==1 and matches[0]['CompiledSHA256']==sha(p),'explicit compiled top/header SHA missing')
    result_path=canonical(work/'execution-result.json',prep.WORK);result=json.loads(result_path.read_text(encoding='utf-8'))
    require(result.get('Schema')=='camera720-calibrated-diagnostic-execution-v1' and result.get('Target')==prep.TARGET,
            'wrong calibrated720 execution receipt')
    require(result.get('NativeExitCode')==0 and result.get('SourcesStable') is True and result.get('ActualStagesComplete') is True
            and result.get('InputDrift')==[] and result.get('TimedOut') is False
            and result.get('StoppedForUnexpectedStage') is False and result.get('Cleanup',{}).get('Complete') is True
            and not result.get('Error') and result.get('PlanSHA256')==sha(path),
            'build native completion/source/cleanup proof failed')
    require(result.get('EDAExecuted') is True and result.get('Plan')==str(path)
            and result.get('Command')==plan['CommandToRunSeparately'],'native execution provenance differs')
    for flag in ('HardwareAccessed','BitstreamRequested','TimingAccepted','HardwareReleaseAllowed'):
        require(result.get(flag) is False,'build scope differs: '+flag)
    events=[[s,e] for s in plan['ExpectedActualStages'] for e in ('started','done')]
    require(result.get('ActualEvents')==events,'actual build stage list differs')
    logs=result.get('LogSHA256',{})
    require(isinstance(logs,dict) and {'execution-stdout.log','execution-stderr.log'}<=set(logs)
            and set(logs)=={p.relative_to(work).as_posix() for p in work.rglob('*.log')},'actual log inventory differs')
    for name,h in logs.items():watched[canonical(work/name,work)]=h
    require(sorted(scan_diagnostics(work))==sorted(result.get('Diagnostics',[])),'unreported C/E/F diagnostic present')
    log=(work/'execution-stdout.log').read_text(encoding='gb18030',errors='replace')
    require([list(x) for x in diagnostic.stage_events(log)]==events,'stdout lacks exact native stage sequence')
    source=canonical(source,prep.WORK)
    require(source==work/'place_route'/(prep.TARGET+'_pnr.adf'),'only this calibrated build final ADF is accepted')
    require(re.fullmatch('[0-9a-f]{64}',expected_sha) and sha(source)==expected_sha,'requested ADF SHA differs')
    before=canonical(work/'pre-sta-final.adf',prep.WORK);audit=result.get('DatabaseSnapshotAudit',{})
    require(audit.get('UnchangedAcrossSTA') is True and audit.get('Snapshot')==str(before)
            and audit.get('FinalRoutedDatabase')==str(source)
            and audit.get('SnapshotSHA256')==expected_sha and audit.get('FinalRoutedDatabaseSHA256')==expected_sha
            and sha(before)==expected_sha,'build ADF before/after STA snapshot differs')
    if result.get('ExecutionCompletedWithoutError') is True:
        require(result.get('Diagnostics')==[] and review_path is None and review_sha is None,
                'clean build cannot carry diagnostics review')
    else:
        require(review_path is not None and review_sha is not None,'failed build requires explicit read-only review')
        review_path=canonical(review_path,prep.WORK)
        require(sha(review_path)==review_sha and json.loads(review_path.read_text(encoding='utf-8'))==
                readonly_review_payload(path,result_path,source,result),'read-only diagnostic review differs')
        watched[review_path]=review_sha
    require(result.get('ExecutorSHA256')==sha(diagnostic.__file__),'build executor changed')
    for p in (path,result_path,source,before,work/'timing.tcl',SELF,Path(prep.__file__).resolve(),
              Path(diagnostic.__file__).resolve(),Path(diagnostic.cleanup.__file__).resolve(),Path(sys.executable).resolve()):
        watched[p]=sha(p)
    watched[Path(plan['PDS']['Executable'])]=plan['PDS']['ExecutableSHA256']
    require(not drift(watched),'completed build evidence or input drift')
    return plan,watched

def query_commands(body):
    require(body and body.isascii(), 'nonempty ASCII body required')
    brace = r'\{[^{}\r\n]*\}'
    patterns = [r'puts '+brace,
        r'get_(?:pins|ports|clocks) -hierarchical -regexp '+brace,
        r'get_(?:ports|clocks) -regexp '+brace,
        r'show -(?:design_net|dev_instance) '+brace,
        r'\.switch_db -route -input \{@WORK@/input\.adf\} -output \{@WORK@/[A-Za-z0-9_-]+\.txt\}',
        r'dump_net -grid_unit '+brace+r' -print_site -out_file \{@WORK@/[A-Za-z0-9_-]+\.txt\}',
        r'report_path_timing -delay_type min_max -max_path (?:[1-9][0-9]{0,2}|1000) -nworst [1-8] -report_exception TRUE -from '+brace+r'(?: -through '+brace+r')? -to '+brace,
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
    if mode in ('query','report'):
        commands = query_commands(body) if mode=='query' else ['.switch_db -route -input {@WORK@/input.adf} -output {@WORK@/route-dump.txt}']
        require(mode=='query' or body is None,'report accepts no query body')
        # Native get_pins needs STA context; only one initialization per process.
        return ('set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG676\n'
                'add_design {'+aw+'/dummy.v}\nif {[info script] ne {}} {\n'
                '    mpnr -input {'+aw+'/input.adf}\n    '+INIT+'\n'
                +'\n'.join(commands).replace('@WORK@',aw)+'\n    puts {'+MARKER+'}\n    flush stdout\n}\n')
    require(mode == 'export' and body is None, 'export accepts no query body')
    suffix = ('if {[file exists '+prep.transport.literal(base/'place_route'/(prep.TARGET+'_pnr.adf'))+']} {\n'
              '    file copy '+prep.transport.literal(base/'place_route'/(prep.TARGET+'_pnr.adf'))+' '+prep.transport.literal(base/'pre-sta-final.adf')+'\n}\n'
              'report_timing -force_to_run -delay_type min_max -max_path 1000 -nworst 4 -report_exception TRUE\n')
    require(original.endswith(suffix) and original.count(suffix)==1, 'calibrated720 build suffix differs')
    prefix = original[:-len(suffix)]
    require(prefix.endswith('pnr -optimize_multi_corner_timing -fix_hold_violation\n'), 'calibrated720 placement context differs')
    # PDS flow context retains real source/IP/FDC roles. Explicit input_db_file
    # selects only fresh Report Timing and Generate Netlist actual stages.
    return (prefix+'report_timing -force_to_run -input_db_file {'+aw+'/input.adf} -delay_type min_max -max_path 1000 -nworst 4 -report_exception TRUE\n'
            'if {[info script] ne {}} {\n    gen_netlist -force_to_run -input_db_file {'+aw+'/input.adf} -func_sim_only\n'
            '    puts {'+MARKER+'}\n    flush stdout\n}\n')



def recipe(build_plan,source,source_sha,work,mode,body_path=None,maximum=300,review_path=None,review_sha=None):
    work=prep.work_path(work)
    require(mode in ('report','export','query'),'read-only report/export/query modes required')
    require(type(maximum) is int and 120<=maximum<=300,'inspection bound must be120..300 seconds')
    plan,watched=bind(build_plan,source,source_sha,review_path,review_sha)
    body=None
    if mode=='query':
        body_path=canonical(body_path,prep.WORK);watched[body_path]=sha(body_path);body=body_path.read_text(encoding='ascii')
    else:require(body_path is None,'non-query mode accepts no body')
    build=Path(build_plan).resolve().parent
    tcl=render(mode,(build/'timing.tcl').read_text(encoding='ascii'),build,work,body)
    result=json.loads((build/'execution-result.json').read_text(encoding='utf-8'))
    value={'Schema':SCHEMA,'Target':prep.TARGET,'Mode':mode,'WorkDirectory':str(work),
        'BuildPlan':str(Path(build_plan).resolve()),'BuildPlanSHA256':sha(build_plan),
        'SourceADF':str(Path(source).resolve()),'SourceADFSHA256':source_sha,
        'BuildReceipt':{'Path':str(build/'execution-result.json'),'SHA256':sha(build/'execution-result.json')},
        'GeneratedTop':{'Path':str(build/'source'/prep.TOP),'SHA256':sha(build/'source'/prep.TOP)},
        'CompiledTop':{'Path':str(build/'compiled'/prep.TOP),'SHA256':sha(build/'compiled'/prep.TOP)},
        'CompiledHeader':{'Path':str(build/'compiled'/prep.HEADER),'SHA256':sha(build/'compiled'/prep.HEADER)},
        'BuildDiagnosticsReview':{'Path':str(Path(review_path).resolve()),'SHA256':review_sha} if review_path else None,
        'BuildExecutionCompletedWithoutError':result['ExecutionCompletedWithoutError'],'BuildDiagnosticsCleared':False,
        'QueryBody':str(body_path) if body_path else None,'MaximumSeconds':maximum,
        'ExpectedActualStages':['Report Timing','Generate Netlist'] if mode=='export' else [],
        'InputSHA256':{str(p):h for p,h in watched.items()},'TclSHA256':hashlib.sha256(tcl.encode('ascii')).hexdigest(),
        'Command':[plan['PDS']['Executable'],'-file',(work/'stage.tcl').as_posix(),'-work_dir',work.as_posix(),'-project_name',prep.TARGET],
        'HardwareAccessed':False,'BitstreamRequested':False,'TimingAccepted':False,'HardwareReleaseAllowed':False,
        'OpticalCorrectionAccepted':False,
        'Limits':'Current generated calibrated720 source and exact original build only. Read-only diagnosis, no inherited transport/raw route, reset, CDC, IO or hardware acceptance.'}
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
    if value['Mode']!='export':
        (work/'dummy.v').write_text('module physical_dummy(input a, output y); assign y=a; endmodule\n',encoding='ascii',newline='\n')
    value['PreparedUTC'] = utc()
    diagnostic.write(work/'stage-plan.json',value)
    return work/'stage-plan.json'


def validate_prepared(path):
    path = canonical(path,prep.WORK)
    work = prep.work_path(path.parent)
    require(path.name=='stage-plan.json','exact stage-plan.json required')
    value = json.loads(path.read_text())
    require(value.get('Schema')==SCHEMA and value.get('Target')==prep.TARGET,'calibrated720 inspection identity differs')
    expected,tcl,watched = recipe(value['BuildPlan'],value['SourceADF'],value['SourceADFSHA256'],work,
                                value['Mode'],value['QueryBody'],value['MaximumSeconds'],
                                (value.get('BuildDiagnosticsReview') or {}).get('Path'),
                                (value.get('BuildDiagnosticsReview') or {}).get('SHA256'))
    require(set(value)==set(expected)|{'PreparedUTC'} and {k:v for k,v in value.items() if k!='PreparedUTC'}==expected,
            'inspection plan differs from bound recipe')
    files={'input.adf','stage.tcl','executor-snapshot.py','stage-plan.json'}
    if value['Mode']!='export':files.add('dummy.v')
    require({p.name for p in work.iterdir()}==files,'inspection stage reused or contaminated')
    require((work/'stage.tcl').read_bytes()==tcl.encode('ascii') and sha(work/'input.adf')==value['SourceADFSHA256']
            and sha(work/'executor-snapshot.py')==sha(SELF),'inspection prepared artifact drift')
    if value['Mode']!='export':
        require((work/'dummy.v').read_bytes()==b'module physical_dummy(input a, output y); assign y=a; endmodule\n','dummy context changed')
    for name in files:watched[canonical(work/name,work)]=sha(work/name)
    require(not drift(watched),'inspection input drift')
    return value,watched


def bind_receipt(path):
    """Rebind a finished read-only inspection for downstream CPU audits.

    Unlike validate_prepared this permits generated artifacts, but every
    original input, stage command and artifact is checked against the receipt.
    Neither this function nor the receipt approves a timing exception.
    """
    path = canonical(path, prep.WORK)
    work = prep.work_path(path.parent)
    require(path.name == 'result.json', 'exact finished inspection result required')
    value = json.loads(path.read_text(encoding='utf-8'))
    require(value.get('Schema') == SCHEMA and value.get('Target') == prep.TARGET, 'wrong finished inspection identity')
    expected, tcl, watched = recipe(value['BuildPlan'], value['SourceADF'], value['SourceADFSHA256'],
                                   work, value['Mode'], value['QueryBody'], value['MaximumSeconds'],
                                   (value.get('BuildDiagnosticsReview') or {}).get('Path'),
                                   (value.get('BuildDiagnosticsReview') or {}).get('SHA256'))
    stage_path = canonical(work/'stage-plan.json', work)
    stage = json.loads(stage_path.read_text(encoding='utf-8'))
    require(set(stage) == set(expected)|{'PreparedUTC'} and isinstance(stage['PreparedUTC'], str)
            and stage['PreparedUTC'] and {k:v for k,v in stage.items() if k!='PreparedUTC'} == expected,
            'finished inspection stage differs from exact recipe')
    require(all(value.get(k) == v for k,v in stage.items()) and value.get('StagePlanSHA256') == sha(stage_path),
            'finished inspection receipt differs from its stage plan')
    require(value.get('EDAExecuted') is True and value.get('ExecutionPassed') is True
            and value.get('ExitCode') == 0 and value.get('TimedOut') is False
            and value.get('StoppedForUnexpectedStage') is False and not value.get('Error')
            and value.get('InputDrift') == [] and value.get('Diagnostics') == []
            and value.get('CompletionMarker') is True and value.get('InputADFUnchanged') is True
            and value.get('Cleanup', {}).get('Complete') is True, 'finished inspection was not clean')
    for flag in ('HardwareAccessed', 'BitstreamRequested', 'TimingAccepted',
                 'HardwareReleaseAllowed', 'OpticalCorrectionAccepted'):
        require(value.get(flag) is False, 'finished inspection exceeds read-only scope: '+flag)
    require((work/'stage.tcl').read_bytes() == tcl.encode('ascii')
            and sha(work/'executor-snapshot.py') == sha(SELF)
            and sha(work/'input.adf') == value['SourceADFSHA256'], 'finished inspection input copy drift')
    if value['Mode'] != 'export':
        require((work/'dummy.v').read_bytes() == b'module physical_dummy(input a, output y); assign y=a; endmodule\n',
                'finished query dummy context drift')
    stages = ['Report Timing', 'Generate Netlist'] if value['Mode']=='export' else []
    events = [[s,e] for s in stages for e in ('started','done')]
    log = (work/'stdout.log').read_text(encoding='gb18030', errors='replace')
    require(value['ExpectedActualStages'] == stages and value.get('ActualEvents') == events
            and [list(item) for item in diagnostic.stage_events(log)] == events and MARKER in log,
            'finished native stages or completion marker differ')
    artifacts = value.get('Artifacts')
    require(isinstance(artifacts, dict) and {'stage.tcl', 'stdout.log', 'stderr.log'} <= set(artifacts),
            'finished native artifact bindings missing')
    actual = {p.relative_to(work).as_posix() for p in work.rglob('*') if p.is_file()
              and p.suffix in ('.tcl', '.log', '.rtr', '.v', '.gnr', '.txt', '.fdc')}
    require(actual == set(artifacts), 'finished native artifact inventory differs')
    require(scan_diagnostics(work) == [], 'finished native critical/error diagnostics present')
    require(timing_report(work,value['Mode']) is not None
            and value.get('TimingReport')==timing_report(work,value['Mode']),
            'actual current-target native timing report missing or changed')
    for name, digest in artifacts.items():
        artifact = canonical(work/name, work)
        require(sha(artifact) == digest, 'finished native artifact drift: '+name)
        watched[artifact] = digest
    if value['Mode'] == 'export':
        netlist = canonical(work/'generate_netlist'/(prep.TARGET+'_sim.v'), work)
        require(native_netlist_valid(netlist) and value.get('NativeNetlistWithFFloc') is True and value.get('Netlist') == {
            'Path': str(netlist), 'SHA256': sha(netlist), 'Bytes': netlist.stat().st_size}, 'native placed export binding differs')
    for item in (path, stage_path, work/'executor-snapshot.py', work/'input.adf'):
        watched[item] = sha(item)
    require(not drift(watched), 'finished inspection input or artifact drift')
    return value, watched


def execute(path):
    value,watched = validate_prepared(path)
    require(os.name=='nt','native inspection requires Windows')
    work=Path(value['WorkDirectory']);result={**value,'StagePlanSHA256':sha(path),'StartedUTC':utc(),
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
    diagnostics=scan_diagnostics(work)
    netlist=work/'generate_netlist'/(prep.TARGET+'_sim.v')
    netvalid=native_netlist_valid(netlist)
    timed_report=timing_report(work,value['Mode'])
    result.update(FinishedUTC=utc(),ElapsedSeconds=round(time.monotonic()-started,3),ActualEvents=events,
        InputDrift=drift(watched),Diagnostics=diagnostics,CompletionMarker=MARKER in log,
        InputADFUnchanged=sha(work/'input.adf')==value['SourceADFSHA256'],NativeNetlistWithFFloc=netvalid if value['Mode']=='export' else None,
        Netlist={'Path':str(netlist),'SHA256':sha(netlist),'Bytes':netlist.stat().st_size} if netlist.is_file() else None,
        TimingReport=timed_report,
        Artifacts={p.relative_to(work).as_posix():sha(p) for p in work.rglob('*') if p.is_file()
                   and p.suffix in ('.tcl','.log','.rtr','.v','.gnr','.txt','.fdc')})
    result['ExecutionPassed']=(result['ExitCode']==0 and not result.get('Error') and not result['TimedOut']
        and not result['StoppedForUnexpectedStage'] and not result['InputDrift'] and not diagnostics
        and events==expected and result['CompletionMarker'] and result['InputADFUnchanged']
        and result['Cleanup'].get('Complete',False) and timed_report is not None and (value['Mode']!='export' or netvalid))
    diagnostic.write(work/'result.json',result)
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--plan',type=Path);p.add_argument('--source-adf',type=Path);p.add_argument('--source-adf-sha256')
    p.add_argument('--build-diagnostics-review',type=Path);p.add_argument('--build-diagnostics-review-sha256')
    p.add_argument('--name');p.add_argument('--mode',choices=('query','report','export'));p.add_argument('--body',type=Path)
    p.add_argument('--maximum-seconds',type=int,default=300);p.add_argument('--stage-plan',type=Path)
    modes=p.add_mutually_exclusive_group();modes.add_argument('--prepare-only',action='store_true')
    modes.add_argument('--validate-only',action='store_true');modes.add_argument('--execute',action='store_true')
    a=p.parse_args()
    if a.stage_plan:
        require(not any((a.plan,a.source_adf,a.source_adf_sha256,a.name,a.mode,a.body,a.prepare_only,a.build_diagnostics_review,a.build_diagnostics_review_sha256)), 'stage-plan accepts only validation or execution')
        if a.execute:result=execute(a.stage_plan)
        else:
            value,_=validate_prepared(a.stage_plan);result={'Validated':True,'StagePlan':str(a.stage_plan),'ExpectedActualStages':value['ExpectedActualStages']}
    else:
        require(a.plan and a.source_adf and a.source_adf_sha256 and a.name and a.mode,'build plan, exact ADF/hash, name and mode required')
        args=(a.plan,a.source_adf,a.source_adf_sha256,prep.WORK/a.name,a.mode,a.body,a.maximum_seconds,a.build_diagnostics_review,a.build_diagnostics_review_sha256)
        if a.prepare_only or a.execute:
            stage=prepare(*args)
            result=execute(stage) if a.execute else {'Prepared':True,'StagePlan':str(stage),'EDAExecuted':False,'HardwareAccessed':False}
        else:
            value,_,_=recipe(*args);result={'Validated':True,'ExpectedActualStages':value['ExpectedActualStages'],'EDAExecuted':False,'HardwareAccessed':False}
    print(json.dumps({k:result[k] for k in ('Prepared','Validated','StagePlan','ExecutionPassed','ExitCode','ElapsedSeconds','InputDrift','Diagnostics','ExpectedActualStages','EDAExecuted','HardwareAccessed') if k in result}))
    return 0 if result.get('ExecutionPassed',True) else 1


if __name__=='__main__':raise SystemExit(main())
