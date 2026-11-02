"""Apply measured DDR hold detours on an isolated view-toggle ADF.

Every launch output needs exact dual-corner setup/hold evidence. Only the
measured single-load branches may change; all functional, placement and CDB
semantics and all other routes are compared after the native save.
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
import camera720_view_toggle_hold as hold
import camera720_stats_delay_hold_route as preservation
import run_raw_camera_delay_route_reset as route_helpers

SELF = Path(__file__).resolve()
SCHEMA = 'camera720-view-toggle-hold-route-application-v1'
REQUEST_SCHEMA = 'camera720-view-toggle-hold-route-request-v1'
TARGET = build.TARGET
MARKER = 'CAMERA720_VIEW_TOGGLE_HOLD_ROUTE_SAVED'
INIT = preservation.INIT
DUMMY = preservation.DUMMY
require, sha, read, write = build.require, build.sha, build.read, build.write


def ref(path):
    path = Path(path).resolve()
    return {'Path': str(path), 'SHA256': sha(path)}


def drift(watched):
    return [str(p) for p, h in watched.items() if not Path(p).is_file() or sha(p) != h]


def binding(value, watched):
    require(isinstance(value, dict) and set(value) == {'Path', 'SHA256'}, 'exact Path/SHA256 binding required')
    p = Path(value['Path']).absolute()
    wire = Path(hold.routes.common.WIRE_DEFAULT).resolve()
    require(p == p.resolve() and p.is_file() and (p.is_relative_to(build.ROOT) or p == wire),
            'canonical bound project or vendor wire file required')
    require(sha(p) == value['SHA256'], 'input SHA differs: ' + str(p))
    require(str(p) not in watched or watched[str(p)] == value['SHA256'], 'conflicting evidence')
    watched[str(p)] = value['SHA256']
    return p


def bind_request(path):
    from camera720_view_toggle_receipts import bind_native_receipt as bind_receipt
    path = Path(path).resolve()
    watched = {str(path): sha(path)}
    r = read(path)
    fields = {'Schema', 'Target', 'BuildPlan', 'ExportReceipt', 'RouteReceipt', 'QueryReceipt', 'HoldAnalysis', 'RoutePlan'}
    require(set(r) == fields and r['Schema'] == REQUEST_SCHEMA and r['Target'] == TARGET, 'exact hold-route request required')
    bp = binding(r['BuildPlan'], watched)
    plan = build.validate(bp)
    receipts = []
    for name, mode in (('ExportReceipt', 'export'), ('RouteReceipt', 'report'), ('QueryReceipt', 'query')):
        rp = binding(r[name], watched)
        value, bound = bind_receipt(rp)
        watched.update({str(p): h for p, h in bound.items()})
        require(value['Mode'] == mode and value['BuildPlan'] == str(bp), 'inspection mode/build differs')
        receipts.append((rp, value))
    require(len({(v['SourceADF'], v['SourceADFSHA256']) for _, v in receipts}) == 1, 'inspection ADF identities differ')
    source = Path(receipts[0][1]['SourceADF']).resolve()
    require(source == bp.parent/'place_route'/(TARGET+'_pnr.adf'), 'route only the original candidate')
    ap = binding(r['HoldAnalysis'], watched)
    record = read(ap)
    full = receipts[0][0].parent/'report_timing'/(TARGET+'.rtr')
    extras = sorted(receipts[2][0].parent.glob('report_path_timing/*/report_timing/'+TARGET+'.rtr'))
    require(len(extras) == 3, 'three exact current launch reports required')
    require(receipts[0][1]['Artifacts'].get(full.relative_to(receipts[0][0].parent).as_posix()) == sha(full), 'full report unbound')
    for p in extras:
        require(receipts[2][1]['Artifacts'].get(p.relative_to(receipts[2][0].parent).as_posix()) == sha(p), 'exact launch report unbound')
    actual, _, _ = hold.extract(full, extras)
    require({k:v for k,v in record.items() if k != 'CreatedUTC'} == {k:v for k,v in actual.items() if k != 'CreatedUTC'},
            'hold analysis differs from native reports')
    require(actual['MissingExactSetup'] == [] and actual['MissingLaunchCases'] == [] and actual['HoldFailingPathCount'] == 2,
            'complete two-branch setup/hold measurement required')
    for p in extras:
        header = ''.join(p.open(encoding='utf-8-sig').readlines()[:16])
        command = re.findall(r'(?m)^\| Tcl Command\s*:\s*(.+)$', header)
        require(len(command) == 1 and command[0].startswith('report_path_timing '), 'native targeted command required')
        matches = [row for row in actual['Paths'] if ('-from {t:'+row['Source']+'}') in command[0]
                   and ('-to {t:'+row['Endpoint']+'}') in command[0]]
        require(len(matches) == 1 and any(('-through {t:'+t+'}') in command[0] for t in matches[0]['ActualLaunchOutputs']),
                'exact native launch selector differs')
    dump = receipts[1][0].parent/'route-dump.txt'
    require(receipts[1][1]['Artifacts'].get('route-dump.txt') == sha(dump), 'full route dump unbound')
    route_path = binding(r['RoutePlan'], watched)
    route = read(route_path)
    require(route == hold.derive_waypoints(ap, dump), 'route plan differs from measured unoccupied waypoints')
    binding(route['WirePattern'], watched)
    for mod in (hold, hold.timing, hold.routes, hold.routes.common, hold.waypoint, route_helpers, preservation):
        watched[str(Path(mod.__file__).resolve())] = sha(mod.__file__)
    for p in (SELF, preservation.SERIALIZER):
        watched[str(p)] = sha(p)
    require(not drift(watched), 'hold route input drift')
    return r, plan, source, route, watched


def render(commands, work):
    w = work.as_posix()
    lines = ['set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG676',
        'add_design {'+w+'/dummy.v}', 'if {[info script] ne {}} {',
        '    mpnr -input {'+w+'/input.adf}', '    '+INIT,
        '    file copy {'+w+'/input.adf} {'+w+'/post-init.adf}',
        *commands, '    save_adif',
        '    file copy {'+w+'/input.adf} {'+w+'/saved-route.adf}',
        '    .switch_db -route -input {'+w+'/input.adf} -output {'+w+'/route-dump.txt}',
        '    puts {'+MARKER+'}', '    flush stdout', '}', '']
    return chr(10).join(lines)


def recipe(request, work):
    work = build.work_path(work)
    r, plan, source, route, watched = bind_request(request)
    body = render(route['Commands'], work)
    value = {'Schema': SCHEMA, 'Target': TARGET, 'Mode':'save-route-only',
        'Request': ref(request), 'BuildPlan':r['BuildPlan']['Path'], 'BuildPlanSHA256':r['BuildPlan']['SHA256'],
        'SourceADF':str(source), 'SourceADFSHA256':sha(source), 'WorkDirectory':str(work),
        'OriginalExportReceipt':r['ExportReceipt'], 'OriginalRouteReceipt':r['RouteReceipt'],
        'OriginalRouteDump':route['RouteDump'], 'MeasuredTargets':route['Targets'], 'Routes':route['Routes'],
        'ExactRouteCommands':route['Commands'], 'ExactResetCommands':[], 'InputSHA256':watched,
        'MaximumSeconds':300, 'Command':[plan['PDS']['Executable'], '-file', (work/'stage.tcl').as_posix(),
            '-work_dir', work.as_posix(), '-project_name', TARGET],
        'HardwareAccessed':False, 'BitstreamRequested':False, 'TimingAccepted':False, 'ConstraintsApplied':False}
    return value, body


def prepare(request, work):
    value, body = recipe(request, work)
    work = Path(value['WorkDirectory'])
    require(not work.exists(), 'fresh hold route stage required')
    work.mkdir(parents=True)
    shutil.copyfile(value['SourceADF'], work/'input.adf')
    (work/'stage.tcl').write_text(body, encoding='ascii', newline=chr(10))
    (work/'dummy.v').write_text(DUMMY, encoding='ascii', newline=chr(10))
    for p in (work/'stage.tcl', work/'dummy.v'):
        value['InputSHA256'][str(p)] = sha(p)
    write(work/'stage-plan.json', value)
    return work/'stage-plan.json'


def bind_plan(path, fresh=False):
    path = Path(path).resolve()
    value = read(path)
    work = build.work_path(path.parent)
    expected, body = recipe(value['Request']['Path'], work)
    for p in (work/'stage.tcl', work/'dummy.v'):
        expected['InputSHA256'][str(p)] = sha(p)
    require(path.name == 'stage-plan.json' and value == expected, 'route stage plan differs from exact recipe')
    require((work/'stage.tcl').read_bytes() == body.encode('ascii') and (work/'dummy.v').read_bytes() == DUMMY.encode('ascii'),
            'route stage instructions changed')
    require(not drift(value['InputSHA256']), 'route stage input drift')
    if fresh:
        require({p.name for p in work.iterdir()} == {'stage-plan.json','stage.tcl','dummy.v','input.adf'}
                and sha(work/'input.adf') == value['SourceADFSHA256'], 'route stage contaminated/reused')
    return value


def execute(path):
    value = bind_plan(path, True)
    require(os.name == 'nt', 'Windows native PDS required')
    work = Path(value['WorkDirectory'])
    result = {**value, 'StagePlanSHA256':sha(path), 'StartedUTC':datetime.now(timezone.utc).isoformat(),
              'ExecutionPassed':False, 'EDAExecuted':False, 'TimedOut':False}
    watched = {**value['InputSHA256'], str(Path(path).resolve()):sha(path)}
    write(work/'execution-start.json', result)
    process = None
    start = time.monotonic()
    try:
        with (work/'stdout.log').open('xb') as out, (work/'stderr.log').open('xb') as err:
            process = subprocess.Popen(value['Command'], cwd=work, stdout=out, stderr=err, shell=False,
                                       creationflags=subprocess.CREATE_NO_WINDOW)
            result.update(EDAExecuted=True, OwnedPID=process.pid)
            try:
                result['ExitCode'] = process.wait(timeout=300)
            except subprocess.TimeoutExpired:
                result['TimedOut'] = True
    except BaseException as error:
        result['Error'] = type(error).__name__+': '+str(error)
    finally:
        if process is not None and process.poll() is None:
            result['Cleanup'] = build.cleanup.stop_owned_tree(process,work,'bounded hold route save')
        else:
            result['Cleanup'] = {'Complete':True,'ParentExited':process is not None}
        result['ExitCode'] = process.poll() if process is not None else None
    try:
        log = (work/'stdout.log').read_text(encoding='gb18030',errors='replace')
        result.update(InputDrift=drift(watched), ActualEvents=re.findall(r'^Process "([^"]+)" (started|done)\.',log,re.M),
            CompletionMarker=MARKER in log, Diagnostics=preservation.inspect.scan_diagnostics(work))
        result['InitializationPreservedADF'] = sha(work/'post-init.adf') == value['SourceADFSHA256']
        result['ResultADF'] = ref(work/'input.adf')
        result['ResultADFSHA256'] = sha(work/'input.adf')
        result['SavedADFReadbackMatches'] = sha(work/'saved-route.adf') == result['ResultADFSHA256']
        require(result['ExitCode'] == 0 and not result['TimedOut'] and not result.get('Error')
            and not result['InputDrift'] and not result['Diagnostics'] and not result['ActualEvents']
            and result['CompletionMarker'] and result['InitializationPreservedADF'] and result['SavedADFReadbackMatches']
            and result['Cleanup']['Complete'] and result['ResultADFSHA256'] != value['SourceADFSHA256'], 'native hold route save failed')
        result['RouteComparison'] = preservation.compare_route_dumps(value['OriginalRouteDump']['Path'], work/'route-dump.txt',
            value['MeasuredTargets'], value['Routes'])
        result['ExecutionPassed'] = result['RouteComparison']['Passed']
    except Exception as error:
        result['Error'] = type(error).__name__+': '+str(error)
    result['ElapsedSeconds'] = round(time.monotonic()-start,3)
    result['Artifacts'] = {p.relative_to(work).as_posix():sha(p) for p in work.rglob('*') if p.is_file()
                           and p.name not in ('result.json','execution-start.json')}
    write(work/'result.json', result)
    return result


def bind_completed(path):
    path = Path(path).resolve()
    value = read(path)
    plan = bind_plan(path.parent/'stage-plan.json')
    require(value.get('ExecutionPassed') is True and not value.get('Error') and all(value.get(k) == v for k,v in plan.items())
            and value['StagePlanSHA256'] == sha(path.parent/'stage-plan.json'), 'clean exact hold route receipt required')
    require(value.get('EDAExecuted') is True and value.get('ExitCode') == 0 and value.get('TimedOut') is False
            and value.get('InputDrift') == [] and value.get('Diagnostics') == [] and value.get('ActualEvents') == []
            and value.get('CompletionMarker') is True and value.get('Cleanup',{}).get('Complete') is True
            and value.get('InitializationPreservedADF') is True and value.get('SavedADFReadbackMatches') is True
            and value.get('ResultADFSHA256') != plan['SourceADFSHA256'], 'native hold route completion evidence failed')
    log = (path.parent/'stdout.log').read_text(encoding='gb18030',errors='replace')
    require(MARKER in log and not re.findall(r'^Process "([^"]+)" (started|done).',log,re.M)
            and preservation.inspect.scan_diagnostics(path.parent) == [], 'actual route native log differs')
    watched = {**plan['InputSHA256'], str(path):sha(path)}
    artifacts = {p.relative_to(path.parent).as_posix():sha(p) for p in path.parent.rglob('*') if p.is_file()
                 and p.name not in ('result.json','execution-start.json')}
    require(value['Artifacts'] == artifacts, 'route artifact inventory differs')
    for name,h in value['Artifacts'].items():
        p = path.parent/name
        require(p.resolve().is_relative_to(path.parent) and sha(p) == h, 'route artifact drift')
        watched[str(p)] = h
    require(value['ResultADF'] == ref(path.parent/'input.adf')
            and value['ResultADFSHA256'] == sha(path.parent/'input.adf') == sha(path.parent/'saved-route.adf')
            and sha(path.parent/'post-init.adf') == plan['SourceADFSHA256'], 'saved route ADF chain differs')
    comparison = preservation.compare_route_dumps(value['OriginalRouteDump']['Path'],path.parent/'route-dump.txt',
                                                value['MeasuredTargets'],value['Routes'])
    require(value['RouteComparison'] == comparison and not drift(watched), 'route preservation or inputs differ')
    return value, watched


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--request',type=Path); p.add_argument('--work-dir',type=Path)
    p.add_argument('--execute-plan',type=Path); p.add_argument('--verify',type=Path)
    a = p.parse_args()
    if a.execute_plan:
        value = execute(a.execute_plan)
        print(json.dumps({k:value.get(k) for k in ('ExecutionPassed','ResultADF','ElapsedSeconds','Error')}))
        return 0 if value['ExecutionPassed'] else 1
    if a.verify:
        value,_ = bind_completed(a.verify);print(json.dumps({'Verified':True,'ResultADF':value['ResultADF']}));return 0
    print(json.dumps({'Prepared':True,'Plan':str(prepare(a.request,a.work_dir))}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
