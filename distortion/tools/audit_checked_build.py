"""Audit a completed checked-I2C build, without EDA or hardware authorization.

Native execution and timing parsers are shared; source selection and pin checks
belong to this candidate. Hash-bound local receipts are not process attestation.
"""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import json
import re

import prepare_board1080_checked as profile
import audit_hdmi30_build as common

PROJECT = Path(__file__).resolve().parents[1]
TOP = 'board/board1080_checked_top.v'
sha, require, bind = common.sha, common.require, common.bind


def check_plan(project, work, roles, watched):
    plan = common.read_json(bind(watched, work / 'plan.json'))
    require(plan['Schema'] == 'board1080-checked-timing-preparation-v1' and
            plan['Manifest'] == profile.MANIFEST, 'wrong checked plan identity')
    require(Path(plan['ProjectRoot']).resolve() == project and
            Path(plan['WorkDirectory']).resolve() == work, 'plan project/work identity differs')
    require(plan['CheckedI2CProfileVerified'] is True and plan['SCLDirectionOnlyConstraintChange'] is True,
            'checked source/constraint profile was not verified')
    require(all(plan[k] is False for k in ('PreviousCandidateTimingReused',
            'PreviousCandidateBitstreamReused', 'HardwareReleaseAllowed', 'PhysicalTimingReady',
            'TimingAccepted', 'HardwareAccessed', 'BitstreamRequested', 'EDAExecuted')),
            'unsafe preparation claims')
    require(plan['RepoAlias'] == 'P:/', 'unexpected repository alias')
    alias = 'P:/' + work.relative_to(project.parent).as_posix()
    require(plan['AliasWorkDirectory'] == alias and plan['EDAStageCommands'] == list(common.STAGES),
            'build command profile differs')
    require(roles['Constraint'] == profile.FDC and TOP in roles['Sources'] and
            len(roles['Sources']) == len(set(roles['Sources'])) == 109 and
            set(roles['SourceSHA256']) == set(roles['Sources']), 'checked source inventory differs')
    expected = profile.expected_inputs(project, roles)
    require(plan['InputSHA256'] == expected, 'exact checked inputs required')
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
        if name in profile.INCLUDE_BINDINGS:
            original, header = profile.INCLUDE_BINDINGS[name]
            matches = list(profile.timing.INCLUDE.finditer(data))
            require(len(matches) == 1 and matches[0][1] == original.encode('ascii'), 'include identity differs')
            target = alias + '/compiled/' + header
            match = matches[0]
            data = data[:match.start(1)] + target.encode('ascii') + data[match.end(1):]
            rewrites.append(dict(Source=name, OriginalInclude=original, CompiledInclude=target,
                Header=header, HeaderSHA256=expected[header], ReplacementCount=1))
        require(row['CompiledPath'] == alias + '/compiled/' + name and
                row['CompiledSHA256'] == profile.timing.sha_bytes(data), 'compiled transformation differs')
        copied = bind(watched, work / 'compiled' / name, row['CompiledSHA256'])
        require(copied.is_relative_to(work / 'compiled'), 'compiled copy escapes build')
    require(plan['IncludeRewrites'] == rewrites, 'include rewrite inventory differs')
    explicit = [alias + '/compiled/' + name for name in roles['ExplicitDesigns']]
    require(plan['ExplicitDesigns'] == explicit, 'explicit design list differs')
    require(plan['Constraints'] == dict(FDC=roles['Constraint'], RCF=roles['RouteConstraint'],
            SHA256=roles['ConstraintSHA256']), 'constraint identity differs')
    snapshot = alias + '/pre-sta-final.adf'
    tcl = profile.timing.make_tcl(explicit, 'P:/distortion/' + roles['Constraint'],
        'P:/distortion/' + roles['RouteConstraint'], alias, snapshot, 200).encode('ascii')
    require(plan['PreSTAFinalDatabase'] == snapshot and plan['Tcl'] ==
            dict(Path=alias + '/timing.tcl', SHA256=profile.timing.sha_bytes(tcl)), 'Tcl identity differs')
    bind(watched, work / 'timing.tcl', plan['Tcl']['SHA256'])
    exe = bind(watched, plan['PDS']['Executable'], plan['PDS']['ExecutableSHA256'])
    require(plan['PDS']['ExpectedVersion'] == profile.timing.PDS_VERSION, 'PDS version profile differs')
    command = ['-file', alias + '/timing.tcl', '-work_dir', alias, '-project_name', 'board1080_top']
    require(Path(plan['CommandToRunSeparately'][0]).resolve() == exe and
            plan['CommandToRunSeparately'][1:] == command, 'prepared invocation differs')
    return plan


def pin_result(project, work, roles):
    text = lambda path: path.read_text(encoding='utf-8-sig')
    pins = common.pins
    ports = pins.top_ports(text(project / TOP))
    declared = pins.fdc_pins(text(project / roles['Constraint']))
    generated = pins.pcf_pins(text(work / 'device_map/board1080_top.pcf'))
    pads, routed = pins.routed_pads(text(work / 'place_route/board1080_top_prr_route_optimize.prt'))
    require(len(ports) == 142 and set(ports) == set(declared) == set(generated), 'native pin inventory differs')
    require(set(ports) - set(routed) == pins.OMITTED_RGB565 and set(routed) <= set(ports),
            'unexpected missing or extra routed pin')
    require(len({v['LOC'] for v in generated.values()}) == 142, 'duplicate native pin location')
    for name, row in declared.items():
        require(row['DIRECTION'] == ports[name] and generated[name] ==
                {k: v for k, v in row.items() if k != 'DIRECTION'}, 'PCF pin attributes differ: ' + name)
        require(row['LOC'] in pads, 'declared package pad absent from route report')
        if name in routed:
            require(routed[name]['Pad'] == row['LOC'] and routed[name]['Direction'] == ports[name],
                    'routed pin identity differs: ' + name)
        else:
            require(not pads[row['LOC']]['Port'], 'optimized RGB input pad was reassigned')
    for name, location in (('hd_scl', 'K22'), ('hd_sda', 'K23')):
        require(ports[name] == 'INOUT' and declared[name]['LOC'] == location and
                declared[name]['VCCIO'] == '3.3' and declared[name]['STANDARD'] == 'LVCMOS33' and
                routed[name]['Bank'] == 'BANKL4', 'checked HDMI electrical declaration differs')
    return dict(DeclaredPins=142, RoutedPins=len(routed), OptimizedRGB565Inputs=sorted(pins.OMITTED_RGB565),
        OwnBuildPCFAndRoutedPadsVerified=True, HDMIControlPads={n: routed[n] for n in ('hd_scl', 'hd_sda')},
        SCLDirectionVerified=True, SCLReadbackAndTristatePhysicalImplementationVerified=False,
        ExternalSCLPullupVerified=False, ActualBoardVoltagesVerified=False,
        Limitation='PRT direction proves port assignment, not input-buffer connectivity, tri-state behavior or board pullups.')


def audit(project, work_dir):
    project, work = Path(project).resolve(), Path(work_dir).resolve()
    require(work.parent == project / 'build/board1080-timing' and
            re.fullmatch(r'checked-[A-Za-z0-9_-]+', work.name), 'checked build directory identity required')
    watched = {}
    for module in (common, common.native, common.native.recovery, common.tables, common.pins, profile):
        bind(watched, Path(module.__file__))
    bind(watched, Path(__file__))
    roles = profile.validate_profile(project)
    plan = check_plan(project, work, roles, watched)
    start, end = common.check_execution(work, plan, watched)
    timing = common.timing_result(work)
    require(set(timing['CornerTotals']) == {c + '_' + k for c in ('slow', 'fast')
            for k in common.native.KINDS}, 'all ten native timing totals required')
    pin_info = pin_result(project, work, roles)
    require(profile.validate_profile(project) == roles, 'checked profile changed during audit')
    require(all(sha(p) == digest for p, digest in watched.items()), 'input or evidence changed during audit')
    adf = (work / 'place_route/board1080_top_pnr.adf').resolve()
    return dict(Schema='board1080-checked-full-build-audit-v1', RecordedUTC=datetime.now(timezone.utc).isoformat(),
        DiagnosticOnly=True, ProcessSucceeded=True, NativeReturnCode=0, TimingAccepted=False,
        HardwareReleaseAllowed=False, HardwareAccessed=False, PhysicalTimingReady=False, BitstreamRequested=False,
        PreviousCandidateTimingReused=False, PreviousCandidateBitstreamReused=False, ADFUnchangedAcrossSTA=True,
        WorkDirectory=str(work), ExecutionStart=start, ExecutionComplete=end, NativeStages=list(common.STAGES),
        PDSVersion=profile.timing.PDS_VERSION, SourceCount=len(roles['Sources']), BoundInputCount=len(plan['InputSHA256']),
        SourceSHA256=roles['SourceSHA256'], InputSHA256=plan['InputSHA256'],
        FinalRoutedADF=dict(Path=str(adf), SHA256=watched[adf]), PinEvidence=pin_info,
        EvidenceSHA256={str(p): h for p, h in watched.items()}, **timing,
        Limitations=['Local execution receipts and hashes are not independent process attestation.',
            'Timing report generation and ten passing summaries do not establish IO/CDC/reset acceptance.',
            'PRT and PCF cannot prove SCL readback, tri-state implementation, pullups or actual board voltage.',
            'The max_path20 report is not expanded DDR recovery admission evidence.',
            'No hardware operation, bitstream generation or prior-candidate timing reuse is authorized.'])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work-dir', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args(argv)
    require(not args.output.exists(), 'output must be new')
    result = audit(PROJECT, args.work_dir)
    with args.output.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(result, stream, indent=2, ensure_ascii=False, allow_nan=False); stream.write('\n')
    print(json.dumps({k: result[k] for k in ('ProcessSucceeded', 'AllReportedNativeTimingChecksMet',
                                           'TimingAccepted', 'HardwareReleaseAllowed')}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
