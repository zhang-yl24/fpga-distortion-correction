"""Physical-CLM boundary observations with explicit packed-Q through queries.

Fresh diagnostic plans/receipts; frozen BLE collector and executor stay intact.
Physical-boundary coverage does not establish per-logical-FF aggregation.
"""
import argparse
import copy
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time

import camera720_cdc_native as old
import camera720_cdc_clm as clm
import camera720_through_probe as probe

fast, grouped = probe.fast, old.grouped
native, prep, inspect, diagnostic = probe.native, probe.prep, probe.inspect, probe.diagnostic
require, sha, read = probe.require, probe.sha, probe.read
SELF = Path(__file__).resolve()
SCHEMA = 'camera720-physical-clm-through-plan-v1'
COVERAGE = 'camera720-physical-clm-through-coverage-v1'
STAGE = 'camera720-physical-clm-through-stage-v1'
RECEIPT = 'camera720-physical-clm-through-result-v1'
MARKER = 'CAMERA720_PHYSICAL_CLM_THROUGH_COMPLETE'
MAP_NAME, MAP_SHA = 'physical-clm-boundaries-b.json', '84c66dffc42fa4b84fc32e92dc0a93f38e5d239972096a72634905873f1ddf23'
BLE_NAME, BLE_SHA = 'native-endpoints-d.json', 'eaec79611cbee64e04253f0e3c3f2c62e5fbd5f97947d9f3d67c1283111ce319'
BATCH_NAME, BATCH_SHA = 'cdc-batch-final-a/batch-plan.json', '3ccd658fe0c06c9eaf369b08f22decbb07d7facfd2a7977e669e2b3c2dbab31b'
SEED_NAME, SEED_SHA = 'inspection-seed-a.json', 'f3486b4bfd1999821bca836a2fcf02d52576595b0bb10a6514f918025196f063'
LEGACY_PLAN_NAME, LEGACY_PLAN_SHA = 'cdc-qualified-b/native-plan.json', probe.CDC_PLAN_SHA
PROBE_NAME, PROBE_SHA = 'through-native-a/result.json', 'f449ee328da1fd59d78a83c1ccc5d1952f5ea2b633c8aba3aeb46bd43d8b404e'
ORDINARY = {
    '08': '1bd7433b9dafcac1208fca871398176df2c055fe621155890017d8f3a75ea91e',
    '09': '0b43906ba06ac6adc71e998f3d2f90754e2d95a2b44bd752c205665ed8a4502c',
    '10': 'e82cdddef9af0eb5641a0a20b23f383c948b1d93fd0df623b5282cd9f3fc8181',
    '11': '87485fa41c70fd79ea63b1fbbbc35bf9a4208a8af5fdb56874ae56b1b73ead8d',
    '12': 'bad2edc98a2747f3494061ea85f88aa755fa2546d8fb6940ab39d180e2df9909'}


def fixed(name, digest):
    return {'Path': str((prep.WORK/name).resolve()), 'SHA256': digest}


def command(sources, outputs, endpoints):
    return ('report_path_timing -delay_type min_max -max_path 1000 -nworst 8 -report_exception TRUE'
            ' -from {'+' '.join(sorted(sources))+'} -through {'+' '.join(sorted(outputs))+'} -to {'+
            ' '.join(sorted(endpoints))+'}')


def groups_for(queries, missing):
    missing_ids = {old.identity(m) for m in missing}
    groups = []
    for q in sorted((q for q in queries if old.identity(q) in missing_ids), key=lambda q: (old.domain(q), old.identity(q))):
        require('Clock' not in q, 'ordinary setup/hold must already have complete actual evidence')
        for g in groups:
            if g['Domain'] != list(old.domain(q)):
                continue
            sources = dict(g['SourceLaunches'])
            if q['Source'] in sources and sources[q['Source']] != q['LaunchOutput']:
                continue
            sources[q['Source']] = q['LaunchOutput']
            endpoints = sorted(set(g['Endpoints'])|{q['Endpoint']})
            if len(sources) > 4 or len(sources)*len(endpoints) > 64 or len(g['ExpectedIdentities']) >= 64:
                continue
            g['SourceLaunches'], g['Endpoints'] = sources, endpoints
            g['ExpectedIdentities'].append({k:q[k] for k in old.IDENTITY})
            break
        else:
            groups.append({'Domain': list(old.domain(q)), 'SourceLaunches': {q['Source']: q['LaunchOutput']},
                'Endpoints': [q['Endpoint']], 'ExpectedIdentities': [{k:q[k] for k in old.IDENTITY}]})
    for g in groups:
        g['Command'] = command(g['SourceLaunches'], g['SourceLaunches'].values(), g['Endpoints'])
    return groups


def render(work, groups):
    require(1 <= len(groups) <= 3, 'one to three timing commands per native context required')
    aw = work.as_posix()
    return ('set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG676\n'
            'add_design {'+aw+'/dummy.v}\nif {[info script] ne {}} {\n'
            '    mpnr -input {'+aw+'/input.adf}\n    '+inspect.INIT+'\n'+
            '\n'.join(g['Command'] for g in groups)+'\n    puts {'+MARKER+'}\n    flush stdout\n}\n')


def bind_mapping():
    original, inventory, _, context, watched = old.bind_inputs(fixed(BLE_NAME,BLE_SHA), fixed(BATCH_NAME,BATCH_SHA), fixed(SEED_NAME,SEED_SHA))
    path = grouped.watch(watched, prep.WORK/MAP_NAME, MAP_SHA)
    actual = read(path)
    net = Path(original['Netlist']['Path'])
    text = net.read_text(encoding='utf-8-sig')
    graph = old.mapping_tool.monitor.Graph(old.mapping_tool.structure.functional(text))
    placements = clm.placed_luts(text, graph)
    parents = {n.rsplit('/',2)[0] for n in placements}
    parents.update(old.mapping_tool.base.native_parent(r[k]) for r in inventory['LogicalRelationships'] for k in ('SourceFF','DestinationFF'))
    route_paths = [Path(p) for p,h in inventory['InputSHA256'].items() if h == inventory['RouteProvenance']['ArtifactSHA256']]
    require(len(route_paths) == 1, 'one exact bound native route required')
    route = old.mapping_tool.route_objects(route_paths[0], parents)
    require(clm.derive(graph,route,inventory,placements) == actual, 'physical CLM mapping cannot be reproduced')
    augmented = copy.deepcopy(actual)
    offset = len(augmented['LogicalRelationships'])
    supplement = inventory['SameBLESupplement']
    augmented['LogicalRelationships'].extend(copy.deepcopy(supplement['LogicalRelationships']))
    for q in supplement['Queries']:
        q = copy.deepcopy(q); q['LogicalRelationships'] = [i+offset for i in q['LogicalRelationships']]
        augmented['Queries'].append(q)
    augmented['MappingPassed'] = True
    queries = old.normalize_queries(augmented, original['Constraints'])
    for p in (SELF, clm.SELF, probe.SELF):
        grouped.watch(watched,p)
    return original, inventory, actual, queries, context, watched


def clean_logs(refs, watched):
    rows = []
    for reference in refs:
        path = grouped.watch(watched, reference['Path'], reference['SHA256'])
        receipt = read(path)
        for name,digest in receipt['Artifacts'].items():
            artifact = grouped.watch(watched,path.parent/name,digest)
            if artifact.suffix == '.log':
                for line,text in enumerate(artifact.read_text(encoding='gb18030', errors='replace').splitlines(),1):
                    if re.match(r'^\s*(?:C:|E:|F:|ERROR:|FATAL:|Traceback)',text):
                        rows.append({'Log':str(artifact),'Line':line,'Text':text.strip()})
    require(not rows, 'critical native diagnostics: '+json.dumps(rows[:5]))


def bind_through_capability(watched, original):
    path = grouped.watch(watched, prep.WORK/PROBE_NAME, PROBE_SHA)
    value = read(path)
    require(value['Schema'] == probe.RESULT_SCHEMA and value['Producer'] == fast.binding(probe.SELF)
            and value['SourceADFSHA256'] == original['CandidateADF']['SHA256']
            and value['InspectionSeed'] == fixed(SEED_NAME,SEED_SHA)
            and value['ExecutionPassed'] is True and value['ProbeObserved'] is True
            and value['ObservationFailures'] == [] and value['Diagnostics'] == []
            and value['InputDrift'] == [] and value['TimingCommands'] == probe.commands()
            and value['InputADFUnchanged'] is True, 'completed exact through capability proof required')
    require(all(value[k] is False for k in fast.FALSE_FLAGS), 'through capability exceeds diagnostic scope')
    fast.rehash(value['InputSHA256'],watched,Path(value['Command'][0]))
    clean_logs([fast.binding(path)],watched)
    require((path.parent/'stage.tcl').read_bytes() == probe.render(path.parent).encode('ascii')
            and sha(path.parent/'input.adf') == value['SourceADFSHA256']
            and sha(path.parent/'executor-snapshot.py') == sha(probe.SELF), 'through capability byte drift')
    observed,issues = probe.observations(path.parent,value)
    require(not issues and observed == value['Observations'], 'actual through observations differ')
    return [Path(v['Report']['Path']) for v in observed]


def initial_reports(original, inventory, context, watched):
    legacy_path = grouped.watch(watched, prep.WORK/LEGACY_PLAN_NAME,LEGACY_PLAN_SHA)
    legacy = read(legacy_path)
    require(legacy['Producer'] == fast.binding(old.SELF) and legacy['CandidateADF'] == original['CandidateADF'], 'legacy plan differs')
    initial_commands = [old.timing_command(q['Source'],q['Endpoint']) for q in inventory['SameBLESupplement']['Queries']]
    first, initial_refs, issues, _ = old.bind_reports(legacy['InitialEvidence'], original, fixed(SEED_NAME,SEED_SHA),
        context,watched,initial_commands=initial_commands)
    refs = [fixed('cdc-qualified-native-'+i+'/result.json',digest) for i,digest in ORDINARY.items()]
    bodies = set()
    for name,digest in legacy['QueryBodies'].items():
        p = grouped.watch(watched,legacy_path.parent/name,digest); bodies.add(p.read_text(encoding='ascii'))
    more,bound,more_issues,_ = old.bind_reports(refs,original,fixed(SEED_NAME,SEED_SHA),context,watched,bodies,legacy['Groups'])
    require(not issues and not more_issues, 'ordinary pin/query validation failed')
    clean_logs(initial_refs+bound,watched)
    # The final export supplies full STA. Ordinary contexts contribute their exact targeted paths only.
    reports = first+[p for p in more if 'report_path_timing' in p.parts]
    reports += bind_through_capability(watched,original)
    return sorted(set(reports)), initial_refs+bound+[fixed(PROBE_NAME,PROBE_SHA)]


def summary(queries, records, violations):
    result = old.coverage(queries,records,violations)
    lookup = {old.identity(q):q for q in queries}
    ordinary = [r for r in result['CaseCoverage'] if 'Clock' in lookup[old.identity(r)]]
    ordinary_missing = [r for r in result['MissingCases'] if 'Clock' in lookup[old.identity(r)]]
    result.update(PhysicalBoundaryCoverageComplete=result['Complete'],
        PhysicalBoundaryChecksPassed=result['EnumeratedPathsTimingPassed'],
        PhysicalCoverageComplete=result['Complete'],IndividualFFArcsEnumerated=False,
        PhysicalTimingAggregationProved=False, LogicalFFTimingAccepted=False, TimingAccepted=False,
        NativeTimingAccepted=False, HardwareReleaseAllowed=False, HardwareAccessed=False,
        OrdinaryCoveredCases=len(ordinary), OrdinaryMissingCases=ordinary_missing,
        Records=records, Violations=violations,
        Limits='Observed physical boundary paths only. Shared CLM clock aliases do not establish all logical capture-FF timing. No aggregation or release acceptance.')
    return result


def prepare(name):
    work = prep.work_path(prep.WORK/name)
    require(not work.exists(),'fresh physical CLM plan directory required')
    original,inventory,mapping,queries,context,watched = bind_mapping()
    reports,refs = initial_reports(original,inventory,context,watched)
    rows,violations,excluded = old.collect(queries,reports)
    initial = summary(queries,rows,violations)
    require(not violations and not initial['OrdinaryMissingCases'], 'initial ordinary checks incomplete or invalid')
    groups = groups_for(queries,initial['MissingCases'])
    plan = {'Schema':SCHEMA,'Target':prep.TARGET,'Producer':fast.binding(SELF),
        'PhysicalMapping':fixed(MAP_NAME,MAP_SHA),'PhysicalMapper':fast.binding(clm.SELF),
        'OriginalBLEInventory':fixed(BLE_NAME,BLE_SHA),'OriginalBatchPlan':fixed(BATCH_NAME,BATCH_SHA),
        'InspectionSeed':fixed(SEED_NAME,SEED_SHA),'LegacyPlan':fixed(LEGACY_PLAN_NAME,LEGACY_PLAN_SHA),
        'CandidateADF':original['CandidateADF'],'BuildPlanSHA256':original['BuildPlanSHA256'],
        'SameBLESupplement':inventory['SameBLESupplement'],'SupplementalLogicalRelationshipOffset':len(mapping['LogicalRelationships']),
        'Queries':queries,'InitialEvidence':refs,'InitialReports':[fast.binding(p) for p in reports],
        'InitialCoverage':{k:initial[k] for k in ('ExpectedCases','CoveredCases','MissingCases','Complete','EnumeratedPathsTimingPassed')},
        'Groups':groups,'NativeTimingCommands':len(groups),'NativeContexts':(len(groups)+2)//3,
        'MaximumCommandsPerContext':3,'MaximumSeconds':300,'CoverageAssumedFromGrouping':False,
        'PhysicalTimingAggregationProved':False,'EDAExecuted':False,'TimingAccepted':False,'HardwareReleaseAllowed':False,
        'InputSHA256':{str(p):h for p,h in watched.items()}}
    require(not inspect.drift(watched),'physical CLM preparation input drift')
    work.mkdir()
    diagnostic.write(work/'plan.json',plan)
    diagnostic.write(work/'initial-coverage.json',{**initial,'Schema':COVERAGE,'Producer':fast.binding(SELF),
        'Plan':fast.binding(work/'plan.json'),'ExcludedOtherLaunches':excluded})
    return work/'plan.json'


def rehash_inputs(values, watched, pds):
    values = dict(values)
    manual = str(old.MANUAL)
    if manual in values:
        require(values.pop(manual) == old.MANUAL_SHA and sha(old.MANUAL) == old.MANUAL_SHA, 'vendor policy document changed')
        watched[old.MANUAL] = old.MANUAL_SHA
    fast.rehash(values,watched,pds)


def bind_plan(path, expected_sha):
    path = inspect.canonical(path,prep.WORK)
    require(path.name == 'plan.json' and native.physical.digest(expected_sha) and sha(path) == expected_sha, 'explicit CLM plan SHA differs')
    plan = read(path)
    require(plan['Schema'] == SCHEMA and plan['Target'] == prep.TARGET and plan['Producer'] == fast.binding(SELF), 'CLM producer/schema differs')
    require(plan['PhysicalMapping'] == fixed(MAP_NAME,MAP_SHA) and plan['PhysicalMapper'] == fast.binding(clm.SELF)
        and plan['OriginalBLEInventory'] == fixed(BLE_NAME,BLE_SHA) and plan['OriginalBatchPlan'] == fixed(BATCH_NAME,BATCH_SHA)
        and plan['InspectionSeed'] == fixed(SEED_NAME,SEED_SHA) and plan['LegacyPlan'] == fixed(LEGACY_PLAN_NAME,LEGACY_PLAN_SHA),
        'fixed CLM authority references differ')
    require(all(plan.get(k) is False for k in ('PhysicalTimingAggregationProved','EDAExecuted','TimingAccepted',
        'HardwareReleaseAllowed','CoverageAssumedFromGrouping')), 'plan exceeds physical-boundary diagnostic scope')
    _,original,watched = fast.bind_seed(plan['InspectionSeed']['Path'],plan['InspectionSeed']['SHA256'])
    pds = Path(original['Command'][0])
    rehash_inputs(plan['InputSHA256'],watched,pds)
    require(plan['InputSHA256'].get(str(SELF)) == sha(SELF) and plan['InputSHA256'].get(str(clm.SELF)) == sha(clm.SELF),
            'new producer/mapping helper not in plan closure')
    require(plan['CandidateADF'] == {'Path':original['SourceADF'],'SHA256':original['SourceADFSHA256']}
        and plan['BuildPlanSHA256'] == original['BuildPlanSHA256'], 'CLM plan candidate/build changed')
    groups = groups_for(plan['Queries'],plan['InitialCoverage']['MissingCases'])
    require(groups == plan['Groups'] and plan['NativeTimingCommands'] == len(groups)
        and plan['NativeContexts'] == (len(groups)+2)//3 and plan['MaximumCommandsPerContext'] == 3
        and plan['MaximumSeconds'] == 300, 'CLM bounded grouping changed')
    native.add(watched,path,expected_sha)
    require(not inspect.drift(watched),'CLM plan input drift')
    return plan,original,watched


def stage_recipe(plan_path, plan_sha, index, work):
    plan,original,watched = bind_plan(plan_path,plan_sha)
    require(type(index) is int and 0 <= index < plan['NativeContexts'],'invalid CLM context index')
    work = prep.work_path(work)
    groups = plan['Groups'][index*3:index*3+3]
    script = render(work,groups)
    value = {'Schema':STAGE,'Target':prep.TARGET,'Producer':fast.binding(SELF),
        'Plan':fast.binding(Path(plan_path)),'ContextIndex':index,'Groups':groups,
        'InspectionSeed':plan['InspectionSeed'],'CandidateADF':plan['CandidateADF'],
        'BuildPlanSHA256':plan['BuildPlanSHA256'],'WorkDirectory':str(work),
        'MaximumSeconds':300,'ExpectedActualStages':[],
        'Command':[original['Command'][0],'-file',(work/'stage.tcl').as_posix(),'-work_dir',work.as_posix(),'-project_name',prep.TARGET],
        'TclSHA256':prep.baseline.paths.sha_bytes(script.encode('ascii')),
        'InputSHA256':{str(p):h for p,h in watched.items()},'EDAExecuted':False,
        **{k:False for k in fast.FALSE_FLAGS}}
    return value,script,watched,plan


def prepare_stage(plan_path,plan_sha,index,name):
    work = prep.work_path(prep.WORK/name)
    require(not work.exists(),'fresh CLM native directory required')
    value,script,watched,_ = stage_recipe(plan_path,plan_sha,index,work)
    work.mkdir()
    shutil.copyfile(value['CandidateADF']['Path'],work/'input.adf')
    shutil.copyfile(SELF,work/'executor-snapshot.py')
    (work/'stage.tcl').write_bytes(script.encode('ascii'))
    (work/'dummy.v').write_bytes(native.physical.DUMMY.encode('ascii'))
    require(sha(work/'input.adf') == value['CandidateADF']['SHA256'] and not inspect.drift(watched),'CLM stage preparation drift')
    value['PreparedUTC'] = inspect.utc()
    diagnostic.write(work/'stage-plan.json',value)
    return work/'stage-plan.json'


def validate_stage(path,expected_sha,finished=False):
    path = inspect.canonical(path,prep.WORK)
    require(path.name == 'stage-plan.json' and native.physical.digest(expected_sha) and sha(path) == expected_sha,'explicit CLM stage SHA differs')
    value = read(path)
    expected,script,watched,plan = stage_recipe(value['Plan']['Path'],value['Plan']['SHA256'],value['ContextIndex'],path.parent)
    require(set(value) == set(expected)|{'PreparedUTC'} and isinstance(value['PreparedUTC'],str) and value['PreparedUTC']
        and {k:v for k,v in value.items() if k != 'PreparedUTC'} == expected,'CLM stage recipe differs')
    if not finished:
        require({p.name for p in path.parent.iterdir()} == probe.FILES,'CLM stage reused or contaminated')
    require((path.parent/'stage.tcl').read_bytes() == script.encode('ascii')
        and sha(path.parent/'input.adf') == value['CandidateADF']['SHA256']
        and sha(path.parent/'executor-snapshot.py') == sha(SELF)
        and (path.parent/'dummy.v').read_bytes() == native.physical.DUMMY.encode('ascii'),'CLM stage byte drift')
    for name in probe.FILES:
        native.add(watched,path.parent/name)
    require(not inspect.drift(watched),'CLM prepared input drift')
    return value,watched,plan


def selector_set(command,option):
    values = re.findall(r'-'+option+r'\s+\{([^}]*)\}',command)
    require(len(values) == 1,'one exact '+option+' collection required')
    values = [p[2:] if p.startswith(('t:','p:')) else p for p in values[0].split()]
    require(values and len(values) == len(set(values)),'empty/duplicate selector')
    return set(values)


def inspect_report(report,group,queries):
    text = report.read_text(encoding='gb18030')
    head = '\n'.join(text.splitlines()[:18])
    require('2023.2-SP3 <build 154097>' in head and
        re.search(r'^\| Design\s*:\s*'+re.escape(prep.TARGET)+r'\s*$',head,re.M),'wrong native physical report')
    commands = re.findall(r'^\| Tcl Command\s*:\s*(.*?)\s*$',head,re.M)
    require(len(commands) == 1 and commands[0].startswith('report_path_timing ')
        and all(selector_set(commands[0],o) == selector_set(group['Command'],o) for o in ('from','through','to')),
        'complete native from/through/to selector equality required')
    lookup = {old.identity(q):q for q in queries}
    rows,unmapped = [],[]
    for lines,line in old.native.blocks(report):
        text = ''.join(lines)
        source = old.field(r'^Startpoint\s*:\s*(\S+)\s*$',text,'source')
        endpoint = old.field(r'^Endpoint\s*:\s*(\S+)\s*$',text,'endpoint')
        launch = old.launch_row(text)['LaunchOutput']
        require(source in group['SourceLaunches'] and launch == group['SourceLaunches'][source]
            and endpoint in group['Endpoints'],'actual tco/source/endpoint escapes selected through group')
        key = source,launch,endpoint
        if key not in lookup:
            unmapped.append({'Source':source,'LaunchOutput':launch,'Endpoint':endpoint,'ReportLine':line})
            continue
        rows.append(old.parse_record(lines,report,line,lookup[key]))
    require(rows,'no mapped actual through path returned')
    return rows,unmapped


def observe(work,value,plan):
    rows,issues,unmapped = [],[],[]
    root = work/'report_path_timing'
    expected = {f'report_path_timing_{i}' for i in range(1,len(value['Groups'])+1)}
    if not root.is_dir() or {p.name for p in root.iterdir() if p.is_dir()} != expected:
        issues.append({'Stage':'native-report-count','Error':'exact prepared report directories required'})
    for i,g in enumerate(value['Groups'],1):
        report = root/f'report_path_timing_{i}'/'report_timing'/(prep.TARGET+'.rtr')
        try:
            actual,other = inspect_report(report,g,plan['Queries']); rows.extend(actual); unmapped.extend(other)
        except (OSError,ValueError) as error:
            issues.append({'Stage':'native-through-report','TimingCommandIndex1Based':i,'Error':str(error)})
    expected_ids = {old.identity(q) for g in value['Groups'] for q in g['ExpectedIdentities']}
    selected = [q for q in plan['Queries'] if old.identity(q) in expected_ids]
    selected_rows = [r for r in rows if old.identity(r) in expected_ids]
    partial = old.coverage(selected,selected_rows,issues)
    return rows,issues,unmapped,partial


def execute(path,expected_sha):
    value,watched,plan = validate_stage(path,expected_sha)
    require(os.name == 'nt','native CLM query requires Windows')
    work,process,started = Path(value['WorkDirectory']),None,time.monotonic()
    result = {**value,'Schema':RECEIPT,'PlanSchema':STAGE,'StagePlanSHA256':expected_sha,
        'StartedUTC':inspect.utc(),'ExecutionPassed':False,'ObservationValid':False,
        'TimedOut':False,'StoppedForUnexpectedStage':False,'ExitCode':None}
    diagnostic.write(work/'execution-start.json',result)
    try:
        with (work/'stdout.log').open('xb') as out,(work/'stderr.log').open('xb') as err:
            process = subprocess.Popen(value['Command'],cwd=work,stdout=out,stderr=err,shell=False,
                creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            result.update(EDAExecuted=True,OwnedPID=process.pid)
            while process.poll() is None:
                remaining = 300-(time.monotonic()-started)
                if remaining <= 0:
                    result['TimedOut'] = True; break
                try:
                    process.wait(timeout=min(2,remaining))
                except subprocess.TimeoutExpired:
                    pass
                if diagnostic.stage_events((work/'stdout.log').read_text(encoding='gb18030',errors='replace')):
                    result['StoppedForUnexpectedStage'] = True; break
    except BaseException as error:
        result['Error'] = type(error).__name__+': '+str(error)
    finally:
        if process is not None:
            result['Cleanup'] = (diagnostic.cleanup.stop_owned_tree(process,work,'bounded physical CLM query')
                if process.poll() is None else {'Complete':True,'OwnedPID':process.pid,'ParentExited':True,
                                               'DescendantLivenessIndependentlyVerified':False})
            result['ExitCode'] = process.poll()
        else:
            result['Cleanup'] = {'Complete':True,'Required':False}
    try:
        log = (work/'stdout.log').read_text(encoding='gb18030',errors='replace') if (work/'stdout.log').exists() else ''
        rows,issues,unmapped,partial = observe(work,value,plan)
        result.update(ActualEvents=[list(x) for x in diagnostic.stage_events(log)],CompletionMarker=MARKER in log,
            InputDrift=inspect.drift(watched),Diagnostics=probe.scan_diagnostics(work),
            InputADFUnchanged=sha(work/'input.adf') == value['CandidateADF']['SHA256'],
            Records=rows,ObservationFailures=issues,UnmappedObservedPaths=unmapped,GroupCoverage=partial)
        result['ExecutionPassed'] = (result['ExitCode'] == 0 and not result.get('Error') and not result['TimedOut']
            and not result['StoppedForUnexpectedStage'] and result['Cleanup'].get('Complete') is True
            and result['ActualEvents'] == [] and result['CompletionMarker'] and not result['InputDrift']
            and not result['Diagnostics'] and result['InputADFUnchanged'])
        result['ObservationValid'] = result['ExecutionPassed'] and not issues
    except Exception as error:
        result['ReadbackError'] = type(error).__name__+': '+str(error)
        result['ExecutionPassed'] = False
    result.update(FinishedUTC=inspect.utc(),ElapsedSeconds=round(time.monotonic()-started,3),
        Artifacts={p.relative_to(work).as_posix():sha(p) for p in work.rglob('*') if p.is_file()
                   and p.name not in ('result.json','execution-start.json')})
    diagnostic.write(work/'result.json',result)
    return result


def bind_completed(reference,plan_path,plan_sha,watched):
    path = grouped.watch(watched,reference['Path'],reference['SHA256'])
    value = read(path)
    require(path.name == 'result.json' and value['Schema'] == RECEIPT and value['PlanSchema'] == STAGE
        and value['Producer'] == fast.binding(SELF) and value['Plan'] == {'Path':str(Path(plan_path).resolve()),'SHA256':plan_sha},
        'wrong new CLM native receipt')
    stage,inputs,plan = validate_stage(path.parent/'stage-plan.json',value['StagePlanSHA256'],finished=True)
    require(all(value.get(k) == v for k,v in stage.items() if k not in ('Schema','EDAExecuted')), 'CLM receipt differs from exact stage')
    require(value['EDAExecuted'] is True and value['ExecutionPassed'] is True and value['ObservationValid'] is True
        and value['ExitCode'] == 0 and value['TimedOut'] is False and value['StoppedForUnexpectedStage'] is False
        and not value.get('Error') and not value.get('ReadbackError') and value['InputDrift'] == []
        and value['Diagnostics'] == [] and value['ObservationFailures'] == [] and value['InputADFUnchanged'] is True
        and value['CompletionMarker'] is True and value['ActualEvents'] == [] and value['Cleanup'].get('Complete') is True,
        'native physical CLM execution or observation failed')
    require(all(value[k] is False for k in fast.FALSE_FLAGS),'native receipt exceeds diagnostic scope')
    rehash_inputs({str(p):h for p,h in inputs.items()},watched,Path(value['Command'][0]))
    actual = {p.relative_to(path.parent).as_posix() for p in path.parent.rglob('*') if p.is_file()
              and p.name not in ('result.json','execution-start.json')}
    require(actual == set(value['Artifacts']),'native CLM artifact inventory differs')
    clean_logs([reference],watched)
    log = (path.parent/'stdout.log').read_text(encoding='gb18030',errors='replace')
    require(MARKER in log and diagnostic.stage_events(log) == [],'native CLM completion/events differ')
    rows,issues,unmapped,partial = observe(path.parent,stage,plan)
    require(not issues and rows == value['Records'] and unmapped == value['UnmappedObservedPaths']
        and partial == value['GroupCoverage'],'native CLM report records differ')
    return value['ContextIndex'],rows


def validate_supplement(plan,inventory,mapping):
    require(plan['SameBLESupplement'] == inventory['SameBLESupplement']
        and plan['SupplementalLogicalRelationshipOffset'] == len(mapping['LogicalRelationships']),
        'recomputed supplemental mapping or offset differs')


def audit_value(plan_path,plan_sha,receipts):
    plan,_,watched = bind_plan(plan_path,plan_sha)
    # Bind and reparse the original clean evidence; no new native context is inferred.
    original,inventory,mapping,queries,context,inputs = bind_mapping()
    validate_supplement(plan,inventory,mapping)
    rehash_inputs({str(p):h for p,h in inputs.items()},watched,Path(context[1]['Command'][0]))
    reports,refs = initial_reports(original,inventory,context,watched)
    rows,violations,excluded = old.collect(queries,reports)
    initial = summary(queries,rows,violations)
    require(queries == plan['Queries'] and refs == plan['InitialEvidence']
        and [fast.binding(p) for p in reports] == plan['InitialReports']
        and {k:initial[k] for k in plan['InitialCoverage']} == plan['InitialCoverage'], 'initial physical CLM proof differs')
    seen = set()
    for reference in receipts:
        index,more = bind_completed(reference,plan_path,plan_sha,watched)
        require(index not in seen,'duplicate completed CLM context')
        seen.add(index);rows.extend(more)
    rows = list({r['PathSHA256']:r for r in rows}.values())
    result = summary(queries,rows,violations)
    require(not inspect.drift(watched),'physical CLM audit input drift')
    result.update(Schema=COVERAGE,Target=prep.TARGET,Producer=fast.binding(SELF),Plan=fast.binding(plan_path),
        PhysicalMapping=plan['PhysicalMapping'],PhysicalMapper=plan['PhysicalMapper'],
        CandidateADF=plan['CandidateADF'],BuildPlanSHA256=plan['BuildPlanSHA256'],
        InitialEvidence=refs,NativeReceipts=receipts,CompletedContexts=sorted(seen),
        SameBLESupplement=plan['SameBLESupplement'],SupplementalLogicalRelationshipOffset=plan['SupplementalLogicalRelationshipOffset'],
        ExportReceipt=original['ExportReceipt'],OriginalBatchPlan=plan['OriginalBatchPlan'],
        InspectionSeed=plan['InspectionSeed'],Policy=old.policy_reference(),
        NativeSTAContext={'Engine':'PDS 2023.2-SP3 build154097','Scope':'Native physical sequential endpoints',
            'ActualTcoRequired':True,'CriticalDiagnosticsRejected':True,'IndividualFFArcsEnumerated':False,
            'SharedClockAliasUsedAsCaptureFFProof':False},
        LogicalRelationshipsRetained=len(mapping['LogicalRelationships'])+len(inventory['SameBLESupplement']['LogicalRelationships']),
        AllLogicalRelationshipsStructurallyRepresented=True,EDAExecuted=False,ExcludedOtherLaunches=excluded,
        InputSHA256={str(p):h for p,h in watched.items()})
    return result,watched


def audit(plan_path,plan_sha,receipts,name):
    result,_ = audit_value(plan_path,plan_sha,receipts)
    work = prep.work_path(prep.WORK/name)
    require(not work.exists(),'fresh physical CLM coverage directory required')
    work.mkdir();diagnostic.write(work/'coverage.json',result)
    return work/'coverage.json',result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action',required=True)
    p = sub.add_parser('prepare');p.add_argument('--name',required=True)
    for action in ('prepare-stage','audit'):
        p = sub.add_parser(action);p.add_argument('--plan',type=Path,required=True);p.add_argument('--plan-sha256',required=True)
        p.add_argument('--name',required=True)
        if action == 'prepare-stage':p.add_argument('--context',type=int,required=True)
        else:p.add_argument('--receipt',type=Path,action='append',default=[])
    for action in ('validate-stage','execute'):
        p = sub.add_parser(action);p.add_argument('--stage-plan',type=Path,required=True);p.add_argument('--stage-plan-sha256',required=True)
    args = parser.parse_args()
    if args.action == 'prepare':
        path = prepare(args.name);result={'Prepared':True,'Plan':fast.binding(path),'EDAExecuted':False}
    elif args.action == 'prepare-stage':
        path = prepare_stage(args.plan,args.plan_sha256,args.context,args.name)
        result={'Prepared':True,'StagePlan':fast.binding(path),'EDAExecuted':False}
    elif args.action == 'validate-stage':
        validate_stage(args.stage_plan,args.stage_plan_sha256);result={'Validated':True,'EDAExecuted':False}
    elif args.action == 'execute':
        value = execute(args.stage_plan,args.stage_plan_sha256)
        result={k:value[k] for k in ('ExecutionPassed','ObservationValid','ExitCode','ElapsedSeconds','Diagnostics','ObservationFailures')}
        result['GroupCoverageComplete']=value.get('GroupCoverage',{}).get('Complete',False)
    else:
        path,value=audit(args.plan,args.plan_sha256,[fast.binding(p) for p in args.receipt],args.name)
        result={'Coverage':fast.binding(path),'ExpectedCases':value['ExpectedCases'],'CoveredCases':value['CoveredCases'],
                'PhysicalBoundaryChecksPassed':value['PhysicalBoundaryChecksPassed'],'TimingAccepted':False}
    print(json.dumps(result,indent=2))
    return 0 if result.get('ObservationValid',result.get('PhysicalBoundaryChecksPassed',True)) else 1


if __name__ == '__main__':
    raise SystemExit(main())
