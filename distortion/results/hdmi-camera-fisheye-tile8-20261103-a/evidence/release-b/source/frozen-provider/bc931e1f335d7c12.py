"""Prepare/execute only measured 720p hold-branch routes on an ADF copy.

No reset exception, new placement, bitstream, device access or timing waiver.
Actual setup margin, unused native waypoints and every unrequested route are
checked independently. Saved results still require fresh full STA.
"""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time

import camera720_inspect as inspect
import audit_camera720_hold as hold
import audit_raw_camera_routes as routes

prep, require, sha = inspect.prep, inspect.require, inspect.sha
SELF = Path(__file__).resolve()
SCHEMA = 'camera720-measured-hold-route-v1'
MARKER = 'CAMERA720_MEASURED_HOLD_ROUTES_SAVED'
DUMMY = b'module physical_dummy(input a, output y); assign y=a; endmodule\n'


def select_waypoints(parsed, targets):
    wire = Path(routes.common.WIRE_DEFAULT).resolve()
    lines = wire.read_text().splitlines()
    rules = {}
    for channel in range(4):
        hits = [(i+1, line) for i, line in enumerate(lines) if line.startswith(f'ZDNE[{channel}] :')]
        require(len(hits) == 1 and f'[ IDNE[{channel}] ]' in hits[0][1], 'official NE wire rule differs')
        rules[channel] = {'Line': hits[0][0], 'Text': hits[0][1]}
    selections, reserved = [], set()
    for target in targets:
        branch = parsed['BranchInventory'][target['Net']]['Leaves'][target['ToRoutePin']]
        sites = [tuple(map(int, re.search(r':SRB_(\d+)_(\d+)$', pin).groups())) for pin in branch if ':SRB_' in pin]
        require(sites, 'measured branch has no native routing sites')
        cx, cy = sites[0][0]-12, sites[0][1]-24
        choices = []
        for (x, y, dx, dy), proof in parsed['_ObservedNE'].items():
            for channel in range(4):
                pins = [f'ZDNE[{channel}]:SRB_{x}_{y}', f'IDNE[{channel}]:SRB_{dx}_{dy}']
                if all(not parsed['_Occupied'].get(pin) and pin not in reserved for pin in pins):
                    choices.append({'Pins': pins, 'Distance': abs(x-cx)+abs(y-cy),
                                    'CoordinateProof': proof[0], 'OfficialWireRule': rules[channel]})
        require(choices, 'no unused officially connected native waypoint pair')
        choice = min(choices, key=lambda row: (row['Distance'], row['Pins']))
        reserved.update(choice['Pins'])
        selections.append({'Target': target, 'SearchCentre': [cx, cy], 'Selected': choice})
    return selections, wire


def derive(query_receipt):
    query_receipt = Path(query_receipt).absolute()
    value, watched = inspect.bind_receipt(query_receipt)
    require(value['Mode'] == 'query' and 'route-dump.txt' in value['Artifacts'], 'bound original route query required')
    report = Path(value['BuildPlan']).parent/'report_timing'/(prep.TARGET+'.rtr')
    inventory, _ = hold.build([report], prep.TARGET)
    require(inventory['Paths'] and not inventory['MissingExactSetup'], 'measured hold failures and both setup corners required')
    targets = []
    for row in inventory['Paths']:
        require(all(m['ExactSetupSlackNS'] > 3.0 for m in row['Margins'].values()), 'insufficient measured setup margin')
        target = {**row['PhysicalRepairCandidate'], 'Endpoint': row['Endpoint']}
        require(target['TimingWaiverAllowed'] is False and target['ExternalInputBudgetChanged'] is False,
                'data-path waiver or changed input budget prohibited')
        require(re.fullmatch(r'_N[0-9]+', target['Net']), 'unsupported measured net identifier')
        targets.append(target)
    dump = query_receipt.parent/'route-dump.txt'
    parsed = routes.inspect(dump, targets)
    selections, wire = select_waypoints(parsed, targets)
    for module in (hold, hold.common, routes, routes.common, inspect, inspect.diagnostic, inspect.diagnostic.cleanup):
        path = Path(module.__file__).resolve()
        watched[path] = sha(path)
    for path in (SELF, report, wire):
        watched[path] = sha(path)
    require(not inspect.drift(watched), 'route derivation input drift')
    return value, watched, inventory, targets, parsed, selections, wire


def recipe(query_receipt, work, maximum=300):
    work = prep.work_path(work)
    require(type(maximum) is int and 120 <= maximum <= 300, 'native deadline must be 120..300 seconds')
    value, watched, inventory, targets, parsed, selections, wire = derive(query_receipt)
    commands = []
    for row in selections:
        t = row['Target']
        pins = '>'.join(row['Selected']['Pins'])+';'
        commands += ['show -design_net {'+t['Net']+'}',
                     'unroute -branch {'+t['Net']+':'+t['ToRoutePin']+';}',
                     'manual_route -net {'+t['Net']+'} -branch {'+t['ToRoutePin']+'} -pins {'+pins+'}',
                     'show -design_net {'+t['Net']+'}']
    w = work.as_posix()
    tcl = ('set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG676\n'
           'add_design {'+w+'/dummy.v}\nif {[info script] ne {}} {\n'
           '    mpnr -input {'+w+'/input.adf}\n'+'\n'.join(commands)+'\n'
           '    save_adif\n    file copy {'+w+'/input.adf} {'+w+'/saved-route.adf}\n'
           '    .switch_db -route -input {'+w+'/input.adf} -output {'+w+'/route-dump.txt}\n'
           '    puts {'+MARKER+'}\n    flush stdout\n}\n')
    plan = {'Schema': SCHEMA, 'Target': prep.TARGET, 'WorkDirectory': str(work),
            'QueryReceipt': str(Path(query_receipt).absolute()), 'BuildPlan': value['BuildPlan'],
            'BuildPlanSHA256': value['BuildPlanSHA256'], 'SourceADF': value['SourceADF'],
            'SourceADFSHA256': value['SourceADFSHA256'], 'MaximumSeconds': maximum,
            'Targets': targets, 'Waypoints': selections, 'WirePattern': {'Path': str(wire), 'SHA256': sha(wire)},
            'ExactCommands': commands, 'InputSHA256': {str(p): h for p, h in watched.items()},
            'TclSHA256': prep.baseline.paths.sha_bytes(tcl.encode('ascii')),
            'Command': [value['Command'][0], '-file', w+'/stage.tcl', '-work_dir', w, '-project_name', prep.TARGET],
            'HardwareAccessed': False, 'BitstreamRequested': False, 'TimingAccepted': False,
            'HardwareReleaseAllowed': False, 'DataTimingWaiverAllowed': False,
            'ConstraintsChanged': False, 'FinalSTAExecuted': False}
    return plan, tcl, watched, parsed


def prepare(query_receipt, work, maximum=300):
    plan, tcl, watched, _ = recipe(query_receipt, work, maximum)
    work = Path(plan['WorkDirectory'])
    require(not work.exists() and not inspect.drift(watched), 'fresh stage and stable inputs required')
    work.mkdir()
    shutil.copyfile(plan['SourceADF'], work/'input.adf')
    (work/'stage.tcl').write_text(tcl, encoding='ascii', newline='\n')
    (work/'dummy.v').write_bytes(DUMMY)
    plan['PreparedUTC'] = inspect.utc()
    inspect.diagnostic.write(work/'stage-plan.json', plan)
    return work/'stage-plan.json'


def validate(path, fresh=True):
    path = inspect.canonical(path, prep.WORK)
    require(path.name == 'stage-plan.json', 'exact stage-plan.json required')
    plan = json.loads(path.read_text())
    expected, tcl, watched, parsed = recipe(plan['QueryReceipt'], path.parent, plan['MaximumSeconds'])
    require(set(plan) == set(expected)|{'PreparedUTC'} and {k: v for k, v in plan.items() if k != 'PreparedUTC'} == expected,
            'hold route plan changed')
    work = path.parent
    if fresh:
        require({p.name for p in work.iterdir()} == {'stage-plan.json', 'stage.tcl', 'dummy.v', 'input.adf'}, 'stage contaminated')
        require(sha(work/'input.adf') == plan['SourceADFSHA256'], 'ADF input copy differs')
    require((work/'stage.tcl').read_bytes() == tcl.encode('ascii') and (work/'dummy.v').read_bytes() == DUMMY,
            'native instructions changed')
    for p in (path, work/'stage.tcl', work/'dummy.v'):
        watched[p] = sha(p)
    return plan, watched, parsed


def execute(path):
    plan, watched, before = validate(path)
    work = Path(plan['WorkDirectory'])
    require(os.name == 'nt', 'native Windows process required')
    result = {**plan, 'StagePlanSHA256': sha(path), 'StartedUTC': inspect.utc(),
              'EDAExecuted': False, 'ExecutionPassed': False, 'TimedOut': False,
              'StoppedForUnexpectedStage': False, 'ExitCode': None}
    inspect.diagnostic.write(work/'execution-start.json', result)
    started, process = time.monotonic(), None
    try:
        with (work/'stdout.log').open('xb') as out, (work/'stderr.log').open('xb') as err:
            process = subprocess.Popen(plan['Command'], cwd=work, stdout=out, stderr=err, shell=False,
                                       creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            result.update(EDAExecuted=True, OwnedPID=process.pid)
            while process.poll() is None:
                remaining = plan['MaximumSeconds']-(time.monotonic()-started)
                if remaining <= 0:
                    result['TimedOut'] = True
                    break
                try:
                    process.wait(timeout=min(2, remaining))
                except subprocess.TimeoutExpired:
                    pass
                if inspect.diagnostic.stage_events((work/'stdout.log').read_text(encoding='gb18030', errors='replace')):
                    result['StoppedForUnexpectedStage'] = True
                    break
    except BaseException as error:
        result['Error'] = type(error).__name__+': '+str(error)
    finally:
        if process is not None:
            if process.poll() is None:
                result['Cleanup'] = inspect.diagnostic.cleanup.stop_owned_tree(process, work, 'bounded 720 hold route')
            else:
                result['Cleanup'] = {'Complete': True, 'ParentExited': True, 'OwnedPID': process.pid,
                                     'DescendantLivenessIndependentlyVerified': False}
            result['ExitCode'] = process.poll()
        else:
            result['Cleanup'] = {'Complete': True, 'Required': False}
    try:
        log = (work/'stdout.log').read_text(encoding='gb18030', errors='replace')
        diagnostics = []
        for p in work.rglob('*.log'):
            diagnostics += re.findall(r'(?m)^\s*(?:E:|F:|ERROR:|FATAL:|Traceback).*$', p.read_text(encoding='gb18030', errors='replace'))
        result.update(CompletionMarker=MARKER in log, ActualEvents=inspect.diagnostic.stage_events(log), Diagnostics=diagnostics)
        require(result['ExitCode'] == 0 and not result.get('Error') and not result['TimedOut'] and
                not result['StoppedForUnexpectedStage'] and not diagnostics and result['CompletionMarker'] and
                not result['ActualEvents'], 'native route command failed')
        result['ResultADFSHA256'] = sha(work/'input.adf')
        require(result['ResultADFSHA256'] == sha(work/'saved-route.adf') and
                result['ResultADFSHA256'] != plan['SourceADFSHA256'], 'saved ADF readback differs or no route saved')
        after = routes.inspect(work/'route-dump.txt', plan['Targets'])
        result['RouteComparison'] = routes.compare(before, after, plan['Targets'])
        for item in plan['Waypoints']:
            target = item['Target']
            chain = after['BranchInventory'][target['Net']]['Leaves'][target['ToRoutePin']]
            pins = item['Selected']['Pins']
            require(any(chain[i:i+2] == pins for i in range(len(chain)-1)), 'requested waypoint absent from saved route')
        result['ExecutionPassed'] = True
    except Exception as error:
        result['Error'] = type(error).__name__+': '+str(error)
        result['ExecutionPassed'] = False
    result['InputDrift'] = inspect.drift(watched)
    result['ExecutionPassed'] &= not result['InputDrift'] and result['Cleanup'].get('Complete', False)
    result.update(FinishedUTC=inspect.utc(), ElapsedSeconds=round(time.monotonic()-started, 3),
                  Artifacts={p.relative_to(work).as_posix(): sha(p) for p in work.rglob('*') if p.is_file()})
    inspect.diagnostic.write(work/'result.json', result)
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--query-receipt', type=Path)
    p.add_argument('--name')
    p.add_argument('--stage-plan', type=Path)
    p.add_argument('--execute', action='store_true')
    args = p.parse_args()
    if args.stage_plan:
        require(not args.query_receipt and not args.name, 'stage mode accepts no new inputs')
        if args.execute:
            r = execute(args.stage_plan)
            print(json.dumps({k: r[k] for k in ('ExecutionPassed', 'ExitCode', 'ElapsedSeconds', 'Error', 'ResultADFSHA256') if k in r}))
            return 0 if r['ExecutionPassed'] else 1
        validate(args.stage_plan)
        print(json.dumps({'Validated': True, 'EDAExecuted': False}))
    else:
        require(args.query_receipt and args.name and not args.execute, 'prepare query-receipt/name before execution')
        print(json.dumps({'Prepared': str(prepare(args.query_receipt, prep.WORK/args.name)), 'EDAExecuted': False}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
