"""Prepare an isolated current720 raw capture build; no EDA or hardware.

The source derivative, complete include closure and copied bytes are checked.
Transport timing and VGA repairs are not inherited by this new design.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re

import prepare_camera_vga_output as baseline
import prepare_camera720_raw_sources as sources
import prepare_raw_camera_delay as legacy
import run_camera_vga_output_diagnostic as cleanup
from types import ModuleType
from pds_source_manifest import expand_sources

PROJECT = Path(__file__).resolve().parents[1]
SELF = Path(__file__).resolve()
TARGET = sources.TARGET
TOP = sources.TOP
MANIFEST = sources.MANIFEST
WORK = PROJECT / 'work/camera720-raw'
RUNNER = 'tools/run_camera720_raw_diagnostic.py'
SCHEMA = 'camera720-current-raw-preparation-v1'
FDC = legacy.FDC
RCF = legacy.RCF
INCLUDES = {
    'rtl/camera_live_bridge.v': ('D:/English/FPGA/distortion/rtl/video_crc32.vh', 'rtl/video_crc32.vh'),
    'rtl/ddr_video_writer.v': ('D:/English/FPGA/distortion/rtl/video_crc32.vh', 'rtl/video_crc32.vh'),
    sources.sensor.INIT: ('board/ov5640_rgb565_720_commands.vh', 'board/ov5640_rgb565_720_commands.vh'),
    'board/hdmi_tx_init.v': ('D:/English/FPGA/distortion/board/ms7210_commands.vh', 'board/ms7210_commands.vh'),
}
require, sha = baseline.require, baseline.paths.sha


def utc():
    return datetime.now(timezone.utc).isoformat()


def validate_primitive_library(path):
    return legacy.validate_primitive_library(path)


def work_path(value):
    p = Path(value).absolute()
    require(p == p.resolve() and p.parent == WORK and p.parent == p.parent.resolve()
            and re.fullmatch(r'[A-Za-z0-9_-]+', p.name), 'canonical direct camera720-raw child required')
    return p


def literal(path):
    p = Path(path).absolute()
    require(p == p.resolve() and p.is_relative_to(PROJECT), 'recipe path escaped project')
    return baseline.paths.tcl_path(p.as_posix())


def constraint_bytes():
    payload, pins = legacy.constraint_bytes()
    old = b'# Independent raw VGA diagnostic; provisional external IO budgets, no hardware acceptance.'
    require(payload.count(old) == 1, 'raw reference constraint preamble changed')
    payload = payload.replace(old, b'# Independent current720 raw diagnostic; external budgets require new physical verification.')
    return payload, pins


def tool_dependencies():
    pending, seen, files = [sources, legacy, baseline, cleanup], set(), {SELF, PROJECT / RUNNER,
        PROJECT / 'tools/pds_source_manifest.py'}
    while pending:
        module = pending.pop()
        if id(module) in seen:
            continue
        seen.add(id(module))
        name = getattr(module, '__file__', None)
        if name:
            path = Path(name).resolve()
            if path.suffix == '.py' and path.is_relative_to(PROJECT / 'tools'):
                files.add(path)
                pending.extend(v for v in vars(module).values() if isinstance(v, ModuleType))
    return sorted(p.relative_to(PROJECT).as_posix() for p in files)


def validate_sources():
    roles = sources.validate_sources()
    names, designs = roles['Sources'], roles['ExplicitDesigns']
    require(len(names) == len(set(names)) and len(designs) == len(set(designs)), 'duplicate raw720 source role')
    require(TOP in designs and sum(Path(n).suffix == '.idf' for n in designs) == 1,
            'one top and one recursively owned DDR IDF required')
    require(all(Path(n).suffix in ('.v', '.idf') for n in designs), 'invalid explicit design source')
    extras = [n for n in names if Path(n).suffix in ('.fdc', '.json', '.vh')]
    require(expand_sources(PROJECT, designs + extras) == names, 'raw720 expanded source closure differs')
    for name in names:
        if Path(name).suffix not in ('.v', '.vh'):
            continue
        data = (PROJECT / name).read_bytes()
        includes = baseline.paths.INCLUDE.findall(data)
        expected = [] if name not in INCLUDES else [INCLUDES[name][0].encode('ascii')]
        require(includes == expected and len(baseline.paths.INCLUDE_DIRECTIVE.findall(data)) == len(expected),
                'raw720 include closure differs: ' + name)
    fdc, pins = constraint_bytes()
    return {**roles, 'FDCBytes': fdc, 'PinAudit': pins}


def recipe(work, pds_shell='D:/pango/PDS_2023.2/bin/pds_shell.exe', maximum_seconds=1800):
    work = work_path(work)
    require(type(maximum_seconds) is int and 60 <= maximum_seconds <= 1800, 'deadline must be60..1800')
    roles = validate_sources()
    pds = Path(pds_shell).absolute()
    require(pds == pds.resolve() and pds.is_file() and pds.name.lower() == 'pds_shell.exe', 'native PDS path required')
    primitive_source = pds.parent.parent / 'arch/vendor/pango/logos2/common/lib/gtp_lib.v'
    primitive_proof = validate_primitive_library(primitive_source)
    extra = [MANIFEST, sources.PARENT_TOP, sources.PARENT_MANIFEST, FDC, RCF,
             'tools/prepare_camera720_raw_sources.py', *tool_dependencies()]
    inputs = {**roles['SourceSHA256'], **{n: sha(PROJECT / n) for n in extra}}
    payloads, copies, rewrites, designs = {}, [], [], []
    for name in roles['Sources'] + [RCF]:
        data = (PROJECT / name).read_bytes()
        require(baseline.paths.sha_bytes(data) == inputs[name], 'input drift: ' + name)
        transformed = data
        if name in INCLUDES:
            original, header = INCLUDES[name]
            match = list(baseline.paths.INCLUDE.finditer(data))[0]
            replacement = (work / 'compiled' / header).as_posix()
            baseline.paths.tcl_path(replacement)
            transformed = data[:match.start(1)] + replacement.encode('ascii') + data[match.end(1):]
            rewrites.append({'Source': name, 'OriginalInclude': original, 'CompiledInclude': replacement,
                             'Header': header, 'HeaderSHA256': inputs[header]})
        destination = work / 'compiled' / name
        payloads[destination] = transformed
        copies.append({'Source': name, 'OriginalSHA256': inputs[name], 'CompiledPath': destination.as_posix(),
                       'CompiledSHA256': baseline.paths.sha_bytes(transformed)})
        if name in roles['ExplicitDesigns']:
            designs.append(destination)
    fdc = work / 'compiled/board/camera720-raw-diagnostic.fdc'
    payloads[fdc] = roles['FDCBytes']
    lines = ['# Current720 raw diagnostic only; no bitstream or hardware.',
             'set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG676']
    lines += ['add_design ' + literal(p) for p in designs]
    lines += ['add_constraint ' + literal(fdc), 'compile -top_module ' + TARGET,
              'synthesize -ads -selected_syn_tool_opt 2', 'dev_map',
              'add_constraint ' + literal(work / 'compiled' / RCF),
              'pnr -optimize_multi_corner_timing -fix_hold_violation',
              'if {[file exists ' + literal(work / 'place_route' / (TARGET + '_pnr.adf')) + ']} {',
              '    file copy ' + literal(work / 'place_route' / (TARGET + '_pnr.adf')) + ' ' + literal(work / 'pre-sta-final.adf'),
              '}', 'report_timing -force_to_run -delay_type min_max -max_path 1000 -nworst 4 -report_exception TRUE']
    tcl = ('\n'.join(lines) + '\n').encode('ascii')
    plan = {'Schema': SCHEMA, 'Target': TARGET, 'Scope': 'PrepareOnlyNoEDA', 'ProjectRoot': str(PROJECT),
            'WorkDirectory': str(work), 'ScratchRoot': str(WORK), 'RepoAlias': 'direct', 'Manifest': MANIFEST,
            'InputSHA256': inputs, 'CompiledInputs': copies, 'ExplicitDesigns': [p.as_posix() for p in designs],
            'IncludeRewrites': rewrites, 'PinAudit': roles['PinAudit'],
            'Constraints': {'FDC': str(fdc), 'SHA256': baseline.paths.sha_bytes(roles['FDCBytes']), 'RCF': RCF,
                            'CDCClockPairs': 12, 'BroadFalsePathsOrClockGroups': False},
            'RawCaptureContract': roles['Manifest']['RawCaptureContract'],
            'InputDelay': roles['Manifest']['InputDelay'],
            'TechnologyPrimitiveSource': primitive_proof,
            'Preview': {'HDMIScan': '1280x720p60', 'SourcePreview': [160, 90], 'UARTSource': [1280, 720],
                        'PreviewDecimation': 8, 'RawPayloadBytes': 1843200},
            'Tcl': {'Path': (work / 'timing.tcl').as_posix(), 'SHA256': baseline.paths.sha_bytes(tcl)},
            'PDS': {'Executable': str(pds), 'ExecutableSHA256': sha(pds), 'ExpectedVersion': baseline.paths.PDS_VERSION},
            'CommandToRunSeparately': [str(pds), '-file', (work / 'timing.tcl').as_posix(), '-work_dir', work.as_posix(), '-project_name', TARGET],
            'MaximumSecondsForExternalExecutor': maximum_seconds, 'ExternalDeadlineRequired': True,
            'PreSTAFinalDatabase': (work / 'pre-sta-final.adf').as_posix(),
            'ExpectedActualStages': ['Compile', 'Synthesize', 'Device Map', 'Place', 'Route', 'Route Optimize', 'Report Timing'],
            'HardwareAccessed': False, 'EDAExecuted': False, 'BitstreamRequested': False,
            **{k: False for k in baseline.FALSE_FLAGS},
            'Limits': 'Independent current720 native raw diagnostic. Nominal input delay, new monitor and preview require their own physical IO/CDC/timing review. No old routed reset/hold repair or transport timing is inherited. No bit or hardware acceptance.'}
    require(all(len(str(p)) < 260 for p in payloads), 'compiled path exceeds Windows native path limit; shorten run name')
    require(all(sha(PROJECT / n) == h for n, h in inputs.items()), 'recipe input drift')
    return plan, payloads, tcl


def prepare(work, pds_shell='D:/pango/PDS_2023.2/bin/pds_shell.exe', maximum_seconds=1800):
    work = work_path(work)
    require(not work.exists(), 'fresh current720 raw workspace required')
    plan, payloads, tcl = recipe(work, pds_shell, maximum_seconds)
    work.mkdir(parents=True)
    for path, data in payloads.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    (work / 'timing.tcl').write_bytes(tcl)
    plan['PreparedUTC'] = utc()
    with (work / 'plan.json').open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(plan, stream, indent=2)
        stream.write('\n')
    return plan


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--audit-only', action='store_true')
    mode.add_argument('--work-dir', type=Path)
    parser.add_argument('--maximum-seconds', type=int, default=1800)
    parser.add_argument('--pds-shell', default='D:/pango/PDS_2023.2/bin/pds_shell.exe')
    args = parser.parse_args()
    if args.audit_only:
        roles = validate_sources()
        result = {'Validated': True, 'Sources': len(roles['Sources']), 'ExplicitDesigns': len(roles['ExplicitDesigns']),
                  'PinAudit': roles['PinAudit']}
    else:
        plan = prepare(args.work_dir, args.pds_shell, args.maximum_seconds)
        result = {'PreparedOnly': True, 'Plan': str(Path(plan['WorkDirectory']) / 'plan.json')}
    print(json.dumps({**result, 'EDAExecuted': False, 'HardwareAccessed': False}))


if __name__ == '__main__':
    main()
