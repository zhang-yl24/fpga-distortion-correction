"""Bind the original view-switch inspector without modifying its frozen producer.

Stage Tcl is reconstructed from the bound build context. Query instructions
are recovered only from the exact hashed stage, then validated by the same
read-only grammar. This performs no EDA or hardware access.
"""
from pathlib import Path
import re

import camera720_view_toggle_build as build
import camera720_view_toggle_native as native

require, sha, read = build.require, build.sha, build.read
SELF = Path(__file__).resolve()


def add(watched, path, expected=None):
    path = Path(path).absolute()
    require(path == path.resolve() and path.is_file(), 'canonical existing evidence required: '+str(path))
    digest = sha(path)
    require(expected is None or re.fullmatch('[0-9a-f]{64}', expected) and digest == expected,
            'evidence SHA differs: '+str(path))
    require(path not in watched or watched[path] == digest, 'conflicting evidence SHA')
    watched[path] = digest
    return path


def ref(path):
    path = Path(path).resolve()
    return {'Path':str(path), 'SHA256':sha(path)}


def merge(watched, bindings):
    for path, digest in bindings.items():
        add(watched, path, digest)


def drift(watched):
    return [str(p) for p,h in watched.items() if not Path(p).is_file() or sha(p) != h]


def render(plan, build_plan, work):
    w = work.as_posix()
    mode = plan['Mode']
    if mode == 'export':
        original = (build_plan.parent/'timing.tcl').read_text(encoding='ascii')
        anchor = 'pnr -optimize_multi_corner_timing -fix_hold_violation\n'
        require(original.count(anchor) == 1, 'build timing context differs')
        prefix = original[:original.index(anchor)+len(anchor)]
        return (prefix+'report_timing -force_to_run -input_db_file {'+w+'/input.adf} -delay_type min_max -max_path 1000 -nworst 4 -report_exception TRUE\n'
                'if {[info script] ne {}} {\n    gen_netlist -force_to_run -input_db_file {'+w+'/input.adf} -func_sim_only\n'
                '    puts {'+native.MARKER+'}\n    flush stdout\n}\n'), None
    require(mode in ('query','report'), 'unsupported native inspection mode')
    prefix = ('set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG676\n'
              'add_design {'+w+'/dummy.v}\nif {[info script] ne {}} {\n'
              '    mpnr -input {'+w+'/input.adf}\n    '+native.INIT+'\n')
    suffix = '\n    puts {'+native.MARKER+'}\n    flush stdout\n}\n'
    actual = (work/'stage.tcl').read_text(encoding='ascii')
    if mode == 'report':
        commands = ['.switch_db -route -input {@WORK@/input.adf} -output {@WORK@/route-dump.txt}']
        body = None
    else:
        require(actual.startswith(prefix) and actual.endswith(suffix), 'native query envelope differs')
        body = actual[len(prefix):-len(suffix)].replace(w,'@WORK@')
        commands = native.query_commands(body)
        require(not any(native.MARKER in c for c in commands), 'query spoofs native completion')
    return prefix+'\n'.join(commands).replace('@WORK@',w)+suffix, body


def bind_native_receipt(path):
    watched = {}
    path = add(watched, path)
    work = build.work_path(path.parent)
    require(path.name == 'result.json', 'exact native result.json required')
    plan_path = add(watched, work/'stage-plan.json')
    plan, value = read(plan_path), read(path)
    require(plan.get('Schema') == 'camera720-view-toggle-inspection-v1'
            and plan.get('Target') == build.TARGET and plan.get('WorkDirectory') == str(work),
            'native view-switch plan identity differs')
    require(all(value.get(k) == v for k,v in plan.items())
            and value.get('StagePlanSHA256') == sha(plan_path), 'native receipt plan differs')
    build_path = add(watched, plan['BuildPlan'])
    source = build.validate(build_path)
    result_path = add(watched, build_path.parent/'execution-result.json')
    result = read(result_path)
    require(result.get('Schema') == 'camera720-view-toggle-build-execution-v1'
            and result.get('PlanSHA256') == sha(build_path) and result.get('BuildCompleted') is True
            and result.get('ExitCode') == 0 and result.get('InputDrift') == []
            and result.get('TimedOut') is False and result.get('UnchangedAcrossSTA') is True
            and result.get('Stages') == [[s,e] for s in build.STAGES for e in ('started','done')],
            'build receipt lacks exact completed current provenance')
    inputs = {**source['InputSHA256'], **source['PreparedSHA256'], str(build_path):sha(build_path),
              str(result_path):sha(result_path), str(Path(plan['SourceADF']).resolve()):plan['SourceADFSHA256'],
              str(Path(native.__file__).resolve()):sha(native.__file__)}
    for name in ('stage.tcl','dummy.v','input.adf'):
        inputs[str(work/name)] = sha(work/name)
    # Query preparation binds one caller body in addition to these exact roles.
    extras = set(plan['InputSHA256'])-set(inputs)
    require(len(extras) == (1 if plan['Mode']=='query' else 0), 'native bound input role set differs')
    for extra in extras:
        inputs[extra] = sha(extra)
    require(plan['InputSHA256'] == inputs, 'native source/input closure differs')
    merge(watched, inputs)
    require(sha(work/'input.adf') == plan['SourceADFSHA256'], 'native ADF copy differs')
    expected, body = render(plan, build_path, work)
    require((work/'stage.tcl').read_bytes() == expected.encode('ascii'), 'native Tcl recipe differs')
    if extras:
        query = Path(next(iter(extras)))
        require(native.query_commands(query.read_text(encoding='ascii')) == native.query_commands(body),
                'native query body differs from bound caller instructions')
    command = [source['PDS']['Executable'],'-file',(work/'stage.tcl').as_posix(),
               '-work_dir',work.as_posix(),'-project_name',build.TARGET]
    stages = ['Report Timing','Generate Netlist'] if plan['Mode']=='export' else []
    require(plan['Command'] == command and plan['ExpectedStages'] == stages and plan['MaximumSeconds'] == 300,
            'native execution command or scope differs')
    require(value.get('Passed') is True and value.get('ExitCode') == 0
            and value.get('TimedOut') is False and value.get('InputDrift') == []
            and value.get('Diagnostics') == [] and value.get('CompletionMarker') is True
            and not value.get('Error'), 'native inspector did not complete cleanly')
    log = (work/'stdout.log').read_text(encoding='gb18030',errors='replace')
    events = [list(x) for x in re.findall(r'^Process "([^"]+)" (started|done)\.', log, re.M)]
    require(events == value.get('ActualEvents') == [[s,e] for s in stages for e in ('started','done')]
            and native.MARKER in log, 'native event sequence or marker differs')
    artifacts = {p.relative_to(work).as_posix():sha(p) for p in work.rglob('*')
                 if p.is_file() and p.suffix in ('.log','.rtr','.v','.gnr','.txt','.fdc')}
    require(value.get('Artifacts') == artifacts, 'native artifact inventory differs')
    for name,digest in artifacts.items():
        add(watched,work/name,digest)
    require(not any(re.search(r'(?m)^\s*(?:C:|E:|F:|ERROR:|FATAL:|CRITICAL:|Traceback)',
                    (work/name).read_text(encoding='gb18030',errors='replace'))
                    for name in artifacts if name.endswith('.log')), 'native critical diagnostic remains')
    result = {**value, 'ExecutionPassed':True, 'BuildPlanSHA256':sha(build_path),
              'InputSHA256':{str(p):h for p,h in watched.items()}}
    if body is not None:
        result['QueryBody'] = next(iter(extras))
    if plan['Mode'] == 'export':
        netlist = work/'generate_netlist'/(build.TARGET+'_sim.v')
        text = netlist.read_text(encoding='ascii')
        require(re.findall(r'(?m)^module\s+(\w+)',text) == [build.TARGET]
                and re.search(r'V_\w+\s*/\*\s*(?:CLMA|CLMS|IOLHR)_\d+_\d+\s*\*/',text),
                'actual placed native view-switch netlist required')
        result.update(Netlist=ref(netlist), NativeNetlistWithFFloc=True,
                      TimingReport=ref(work/'report_timing'/(build.TARGET+'.rtr')))
    add(watched, SELF)
    require(not drift(watched), 'native binding input drift')
    return result, watched
