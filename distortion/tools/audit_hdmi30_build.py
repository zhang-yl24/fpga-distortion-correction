"""Collect a completed HDMI30 build; diagnostic only, never EDA or release.

Receipts/hash binding are not independent process attestation. Only the explicit
new output is written; no prior timing evidence or SHA override is accepted.
"""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import json
import re
import xml.etree.ElementTree as ET

import prepare_board1080_hdmi30 as profile
import audit_ddr_final_timing as native
import board1080_timing_audit as tables
import audit_board1080_pin_contract as pins

PROJECT = Path(__file__).resolve().parents[1]
sha, require = native.sha, native.require
STAGES = ('compile -top_module board1080_top', 'synthesize -ads -selected_syn_tool_opt 2',
    'dev_map', 'pnr -optimize_multi_corner_timing -fix_hold_violation',
    'route_optimize -force_to_run -fix_hold_violation_in_route TRUE -fix_hold_violation_threshold_for_clk_tree 200',
    'report_timing -force_to_run -delay_type min_max -max_path 20')
ARTIFACTS = ('native-console.log', 'run.log', 'place_route/board1080_top_pnr.adf',
    'pre-sta-final.adf', 'report_timing/board1080_top.rtr', 'report_timing/rtr.db',
    'report_timing/board1080_top_exception.rtr', 'device_map/board1080_top.pcf',
    'place_route/board1080_top_prr_route_optimize.prt')


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def stamp(value):
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    require(result.tzinfo is not None, 'receipt timestamp needs timezone')
    return result.timestamp()


def bind(watched, path, digest=None):
    path = Path(path).resolve()
    require(path.is_file() and path.stat().st_size > 0, 'missing or empty evidence: ' + str(path))
    actual = sha(path)
    require(digest is None or actual == digest, 'input hash drift: ' + str(path))
    require(path not in watched or watched[path] == actual, 'conflicting evidence identity')
    watched[path] = actual
    return path


def check_plan(project, work, roles, watched):
    plan = read_json(bind(watched, work / 'plan.json'))
    require(plan['Schema'] == 'board1080-hdmi30-timing-preparation-v1' and
            plan['Manifest'] == profile.MANIFEST, 'wrong HDMI30 plan identity')
    require(Path(plan['ProjectRoot']).resolve() == project and
            Path(plan['WorkDirectory']).resolve() == work, 'plan project/work identity differs')
    require(plan['HDMIEDIDProfileVerified'] is True and all(plan[k] is False for k in
            ('PreviousCandidateTimingReused', 'PreviousCandidateBitstreamReused', 'HardwareReleaseAllowed',
             'TimingAccepted', 'HardwareAccessed', 'BitstreamRequested')), 'unsafe preparation claims')
    require(plan['RepoAlias'] == 'P:/', 'unexpected repository alias')
    alias = 'P:/' + work.relative_to(project.parent).as_posix()
    require(plan['AliasWorkDirectory'] == alias and plan['EDAStageCommands'] == list(STAGES),
            'build command profile differs')
    expected = {**roles['SourceSHA256'], **roles['ConstraintSHA256'], **roles['AuxiliarySHA256']}
    for helper in (profile.timing, profile, profile.edid):
        path = Path(helper.__file__).resolve()
        expected[path.relative_to(PROJECT).as_posix()] = sha(path)
    require(len(expected) == 115 and plan['InputSHA256'] == expected, '115 exact inputs required')
    for name, digest in expected.items():
        path = (project / name).resolve()
        require(path.is_relative_to(project), 'input escapes project')
        bind(watched, path, digest)
    copies = plan['CompiledInputs']
    require(len(copies) == 109 and [r['Source'] for r in copies] == roles['Sources'],
            '109 exact ordered compiled copies required')
    rewrites = []
    for row in copies:
        name = row['Source']
        data = (project / name).read_bytes()
        require(row['OriginalSHA256'] == expected[name], 'compiled original identity differs')
        if name in profile.timing.INCLUDE_BINDINGS:
            original, header = profile.timing.INCLUDE_BINDINGS[name]
            matches = list(profile.timing.INCLUDE.finditer(data))
            require(len(matches) == 1 and matches[0][1] == original.encode('ascii'), 'include identity differs')
            target = alias + '/compiled/' + header
            match = matches[0]
            data = data[:match.start(1)] + target.encode('ascii') + data[match.end(1):]
            rewrites.append(dict(Source=name, OriginalInclude=original, CompiledInclude=target,
                Header=header, HeaderSHA256=expected[header], ReplacementCount=1))
        digest = profile.timing.sha_bytes(data)
        require(row['CompiledPath'] == alias + '/compiled/' + name and
                row['CompiledSHA256'] == digest, 'compiled path or transformation differs')
        copied = bind(watched, work / 'compiled' / name, digest)
        require(copied.is_relative_to(work / 'compiled'), 'compiled copy escapes build')
    require(plan['IncludeRewrites'] == rewrites, 'include rewrite inventory differs')
    explicit = [alias + '/compiled/' + name for name in roles['ExplicitDesigns']]
    require(plan['ExplicitDesigns'] == explicit, 'explicit design list differs')
    snapshot = alias + '/pre-sta-final.adf'
    tcl = profile.timing.make_tcl(explicit, 'P:/distortion/' + roles['Constraint'],
        'P:/distortion/' + roles['RouteConstraint'], alias, snapshot, 200).encode('ascii')
    require(plan['PreSTAFinalDatabase'] == snapshot and plan['Tcl'] ==
            {'Path': alias + '/timing.tcl', 'SHA256': profile.timing.sha_bytes(tcl)}, 'Tcl identity differs')
    bind(watched, work / 'timing.tcl', plan['Tcl']['SHA256'])
    exe = bind(watched, plan['PDS']['Executable'], plan['PDS']['ExecutableSHA256'])
    require(plan['PDS']['ExpectedVersion'] == profile.timing.PDS_VERSION, 'PDS version profile differs')
    command = [str(exe), '-file', alias + '/timing.tcl', '-work_dir', alias, '-project_name', 'board1080_top']
    require(Path(plan['CommandToRunSeparately'][0]).resolve() == exe and
            plan['CommandToRunSeparately'][1:] == command[1:], 'prepared invocation differs')
    return plan


def check_execution(work, plan, watched):
    start = read_json(bind(watched, work / 'execution-start.json'))
    end = read_json(bind(watched, work / 'execution-complete.json'))
    require(Path(start['Executable']).resolve() == Path(plan['PDS']['Executable']).resolve() and
            start['Arguments'] == plan['CommandToRunSeparately'][1:], 'execution command identity differs')
    require(end['StartedUTC'] == start['StartedUTC'] and end['HardwareAccessed'] is False,
            'completion receipt identity differs')
    require(type(end['NativeReturnCode']) is int and end['NativeReturnCode'] == 0, 'native process did not succeed')
    begin, finish = stamp(start['StartedUTC']), stamp(end['EndedUTC'])
    require(stamp(plan['PreparedUTC']) <= begin < finish, 'execution timestamps out of order')
    for name in ARTIFACTS:
        path = bind(watched, work / name)
        require(path.is_relative_to(work), 'artifact escapes build directory')
        require(begin - 2 <= path.stat().st_mtime <= finish + 2, 'stale or future build artifact: ' + name)
    log = (work / 'native-console.log').read_text(encoding='utf-8-sig', errors='strict')
    require(not re.search(r'(?im)^\s*(?:E:|F:|ERROR:|FATAL:)', log), 'native console contains errors')
    sequence = []
    for command in STAGES:
        a = list(re.finditer(r'(?m)^Executing : ' + re.escape(command) + r'\s*$', log))
        b = list(re.finditer(r'(?m)^Executing : ' + re.escape(command) + r' successfully\.\s*$', log))
        require(len(a) == len(b) == 1, 'incomplete or duplicate native stages')
        sequence.extend((a[0].start(), b[0].start()))
    require(sequence == sorted(sequence), 'native stage order differs')
    require('gen_bitstream' not in log, 'unexpected bitstream stage')
    version_log = (work / 'run.log').read_text(encoding='utf-8-sig', errors='strict')
    require('#Build: Fabric Compiler 2023.2-SP3, Build 154097,' in version_log, 'native version differs')
    require(watched[(work / 'place_route/board1080_top_pnr.adf').resolve()] ==
            watched[(work / 'pre-sta-final.adf').resolve()], 'final ADF differs from pre-STA snapshot')
    return start, end


def timing_result(work):
    report = work / 'report_timing/board1080_top.rtr'
    with report.open(encoding='utf-8-sig') as stream:
        header = ''.join(next(stream) for _ in range(10))
    for value in ('2023.2-SP3 <build 154097>', '| Design       : board1080_top',
                  '| Device       : PG2L100H', '| Speed Grade  : -6', '| Package      : FBG676'):
        require(value in header, 'native report identity differs')
    with report.open(encoding='utf-8-sig') as stream:
        summaries, clocks_text = native.parse_summaries(stream)
    tree = ET.parse(work / 'report_timing/rtr.db')
    settings = {r['Name']: r['Value'] for r in tables.table(tree, 'report_timing_settings')}
    require(settings.get('Part') == 'PG2L100H-6FBG676' and settings.get('Top Module') == 'board1080_top',
            'native XML identity differs')
    groups, totals = {}, {}
    for (corner, kind), expected in summaries.items():
        key = corner + '_' + kind
        rows = tables.table(tree, 'report_timing_' + key)
        groups[key], rebuilt = rows, {}
        for row in rows:
            mpw, hold = kind == 'mpw', kind in ('hold', 'removal')
            identity = (row['Clock'],) if mpw else (row['Launch Clock'], row['Capture Clock'])
            require(identity not in rebuilt, 'duplicate XML summary row')
            rebuilt[identity] = dict(WorstSlackNS=float(row['WPWS' if mpw else 'WHS(ns)' if hold else 'WNS(ns)']),
                TotalNegativeSlackNS=float(row['TPWS' if mpw else 'THS(ns)' if hold else 'TNS(ns)']),
                FailingChecks=int(row['Failing End Point' if mpw else 'Failing Endpoints']),
                TotalChecks=int(row['Total End Point' if mpw else 'Total Endpoints']))
        require(rebuilt == expected, 'native RTR/XML summary differs: ' + key)
        totals[key] = dict(WorstSlackNS=min(r['WorstSlackNS'] for r in expected.values()),
            TotalNegativeSlackNS=sum(r['TotalNegativeSlackNS'] for r in expected.values()),
            FailingChecks=sum(r['FailingChecks'] for r in expected.values()),
            TotalChecks=sum(r['TotalChecks'] for r in expected.values()))
    counts = {r['Check']: int(r['Number of Issues']) for r in tables.table(tree, 'check_timing_summary')}
    clocks = tables.table(tree, 'report_timing_clock_summary', True)
    interactions = tables.table(tree, 'report_clock_interaction')
    same = {r['Launch Clock'] for k, rows in groups.items() if k.endswith(('setup', 'hold'))
            for r in rows if r['Launch Clock'] == r['Capture Clock']}
    missing = [r['Clock Name'] for r in clocks if r['Clock Name'] not in same]
    missing += ['native:' + k for k in ('no_clock', 'no_input_delay', 'no_output_delay', 'unexpandable_clocks') if counts.get(k, 1)]
    with (work / 'report_timing/board1080_top_exception.rtr').open(encoding='utf-8-sig') as stream:
        exceptions = native.parse_false_paths(stream)
    require(not any(exceptions.values()), 'unrepaired build unexpectedly contains false paths')
    warnings = native.io_warnings(work / 'native-console.log')
    return dict(CornerTotals=totals, NativeTextXMLSummariesAgree=True, NativeClockSummary=clocks_text,
        CheckTimingCounts=counts, UnsafeInteractions=[r for r in interactions if 'unsafe' in r['Inter-Clock Constrains'].lower()],
        CoverageNotAccepted=missing, FullCoverageAndTimingGate=tables.gate(groups, interactions, missing),
        AllReportedNativeTimingChecksMet=all(r['FailingChecks'] == 0 and r['WorstSlackNS'] >= 0 for r in totals.values()),
        FalsePathCounts={c + '_' + k: len(v) for (c, k), v in exceptions.items()},
        MissingInputDelayUniquePorts=sum(c == '4086' for c, _ in warnings),
        MissingOutputDelayUniquePorts=sum(c == '4087' for c, _ in warnings))


def pin_result(project, work):
    text = lambda path: path.read_text(encoding='utf-8-sig')
    declared = pins.fdc_pins(text(project / 'board/board1080-cdc-reset-diagnostic.fdc'))
    generated = pins.pcf_pins(text(work / 'device_map/board1080_top.pcf'))
    ports = pins.top_ports(text(project / 'board/board1080_rowpipe_top.v'))
    _, routed = pins.routed_pads(text(work / 'place_route/board1080_top_prr_route_optimize.prt'))
    require(len(ports) == 142 and set(ports) == set(declared) == set(generated), 'native pin inventory differs')
    require(set(ports) - set(routed) == pins.OMITTED_RGB565 and set(routed) <= set(ports), 'routed pin inventory differs')
    require(len({v['LOC'] for v in generated.values()}) == len(ports), 'duplicate native pin location')
    for name, row in declared.items():
        require(row['DIRECTION'] == ports[name] and generated[name] == {k: v for k, v in row.items() if k != 'DIRECTION'},
                'PCF pin attributes differ: ' + name)
        if name in routed:
            require(routed[name]['Pad'] == row['LOC'] and routed[name]['Direction'] == ports[name], 'routed pin identity differs')
    return dict(DeclaredPins=len(ports), RoutedPins=len(routed), OptimizedRGB565Inputs=sorted(pins.OMITTED_RGB565),
                OwnBuildPCFAndRoutedPadsVerified=True, ActualBoardVoltagesVerified=False)


def audit(project, work_dir):
    project, work = Path(project).resolve(), Path(work_dir).resolve()
    require(work.parent == project / 'build/board1080-timing' and
            re.fullmatch(r'hdmi30-[A-Za-z0-9_-]+', work.name), 'HDMI30 build directory identity required')
    watched = {}
    for helper in (Path(__file__), Path(native.__file__), Path(native.recovery.__file__), Path(tables.__file__), Path(pins.__file__)):
        bind(watched, helper)
    roles = profile.validate_profile(project)
    plan = check_plan(project, work, roles, watched)
    start, end = check_execution(work, plan, watched)
    timing, pin_info = timing_result(work), pin_result(project, work)
    require(profile.validate_profile(project) == roles, 'profile changed during audit')
    require(all(sha(p) == digest for p, digest in watched.items()), 'input or evidence changed during audit')
    return dict(Schema='board1080-hdmi30-full-build-audit-v1', RecordedUTC=datetime.now(timezone.utc).isoformat(),
        DiagnosticOnly=True, ProcessSucceeded=True, NativeReturnCode=0, TimingAccepted=False,
        HardwareReleaseAllowed=False, HardwareAccessed=False, PhysicalTimingReady=False, BitstreamRequested=False,
        PreviousCandidateTimingReused=False, PreviousCandidateBitstreamReused=False, ADFUnchangedAcrossSTA=True,
        WorkDirectory=str(work), ExecutionStart=start, ExecutionComplete=end, NativeStages=list(STAGES),
        PDSVersion=profile.timing.PDS_VERSION, SourceCount=109, BoundInputCount=115,
        SourceSHA256=roles['SourceSHA256'], FinalRoutedADF=dict(Path=str(work / ARTIFACTS[2]), SHA256=watched[(work / ARTIFACTS[2]).resolve()]),
        PinEvidence=pin_info, EvidenceSHA256={str(p): h for p, h in watched.items()}, **timing,
        Limitations=['Local receipts and file hashes are not independent process attestation.',
            'Report generation is not timing acceptance; incomplete IO/CDC and reset safety remain separate.',
            'The max_path20 build report is not the expanded DDR recovery admission report.',
            'No board operation, new bitstream, or physical voltage measurement was performed.'])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work-dir', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args(argv)
    require(not args.output.exists(), 'output must be new')
    result = audit(PROJECT, args.work_dir)
    with args.output.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(result, stream, indent=2, ensure_ascii=False, allow_nan=False); stream.write('\n')
    print(json.dumps({k: result[k] for k in ('ProcessSucceeded', 'AllReportedNativeTimingChecksMet', 'TimingAccepted', 'HardwareReleaseAllowed')}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
