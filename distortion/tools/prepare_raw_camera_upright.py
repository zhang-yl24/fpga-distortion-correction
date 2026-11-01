"""Prepare an independent native-raw upright VGA diagnostic, without running EDA.

Only copied include paths change. The diagnostic has its own pin and CDC
constraints and does not inherit the display candidate's timing acceptance.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re

import prepare_camera_vga_output as baseline
from pds_source_manifest import expand_sources

PROJECT = Path(__file__).resolve().parents[1]
SELF = Path(__file__).resolve()
TARGET = 'raw_camera_capture_cam2_upright'
TOP = 'board/' + TARGET + '.v'
MANIFEST = 'board/' + TARGET + '-sources.json'
WORK = PROJECT / 'work/raw-camera-upright'
RUNNER = 'tools/run_raw_camera_upright_diagnostic.py'
SCHEMA = 'raw-camera-upright-diagnostic-preparation-v1'
BASE_TOP = 'board/raw_camera_capture_cam2_ref.v'
BASE_TCL = 'board/build-raw_camera_capture_cam2_ref.tcl'
FDC = 'board/camera-vga-output-diagnostic.fdc'
RCF = 'board/board1080-ddr-ioclk-priority.rcf'
OLD_INIT = 'rtl/experimental/ov5640_cadence_trial_init.v'
INIT = 'rtl/experimental/ov5640_cadence_upright_init.v'
MANIFEST_SHA = 'a495f34cc1dd39d350b57a8523c99840bbbd934506a0764a4b98374716c6c830'
INCLUDES = {
    'rtl/camera_live_bridge.v': ('D:/English/FPGA/distortion/rtl/video_crc32.vh', 'rtl/video_crc32.vh'),
    'rtl/ddr_video_writer.v': ('D:/English/FPGA/distortion/rtl/video_crc32.vh', 'rtl/video_crc32.vh'),
    INIT: ('board/ov5640_cadence_trial_commands.vh', 'board/ov5640_cadence_trial_commands.vh'),
    'board/hdmi_tx_init.v': ('D:/English/FPGA/distortion/board/ms7210_commands.vh', 'board/ms7210_commands.vh'),
}
require, sha = baseline.require, baseline.paths.sha


def utc():
    return datetime.now(timezone.utc).isoformat()


def normalized(text):
    return ''.join(re.sub(r'/\*.*?\*/|//[^\n]*', '', text, flags=re.S).split())


def work_path(value):
    p = Path(value).absolute()
    require(p == p.resolve() and p.parent == WORK and p.parent == p.parent.resolve()
            and re.fullmatch(r'[A-Za-z0-9_-]+', p.name), 'canonical direct raw-camera-upright child required')
    return p


def literal(path):
    p = Path(path).absolute()
    require(p == p.resolve() and p.is_relative_to(PROJECT), 'recipe path escaped project')
    return baseline.paths.tcl_path(p.as_posix())


def constraint_bytes():
    original = (PROJECT / FDC).read_text(encoding='utf-8')
    require('set_clock_groups' not in original and 'set_false_path' not in original,
            'diagnostic base must not import broad exceptions')
    lines = [line for line in original.splitlines()
             if not line.startswith('#') and not line.startswith('define_attribute {p:reset_n}')]
    lines.insert(0, '# Independent raw VGA diagnostic; provisional external IO budgets, no hardware acceptance.')
    raw = (PROJECT / baseline.RAW_FDC).read_text()
    lines += [line for line in raw.splitlines() if line.startswith('define_attribute {p:uart_txd}')]
    lines += ['define_attribute {p:uart_txd} {PAP_IO_DIRECTION} {OUTPUT}',
              '# Raw preview adds direct camera/pixel CDC, separately bounded for diagnosis.']
    for first, last in [('camera_pclk', 'pixel_clk'), ('pixel_clk', 'camera_pclk')]:
        lines += [f'set_max_delay -datapath_only -from [get_clocks {{{first}}}] -to [get_clocks {{{last}}}] 8.0',
                  f'set_min_delay -from [get_clocks {{{first}}}] -to [get_clocks {{{last}}}] 0.0']
    result = '\n'.join(lines) + '\n'
    attributes = {}
    for line in result.splitlines():
        match = baseline.PIN_ATTRIBUTE.fullmatch(line)
        if match:
            pin, key, value = match.groups()
            require(key not in attributes.setdefault(pin, {}), 'duplicate raw pin attribute')
            attributes[pin][key] = value
    expected = json.loads((PROJECT / baseline.RAW_PINS).read_text())
    require(set(attributes) == set(expected) and len(attributes) == 128, 'exact raw 128-port map required')
    require(all(attributes[n]['LOC'] == pad for n, pad in expected.items()), 'raw pad location differs')
    require(len(set(expected.values())) == 128 and expected['cam_data[5]'] == 'AA23'
            and expected['uart_txd'] == 'C24' and 'reset_n' not in attributes, 'raw port ownership differs')
    old_attributes = {(m[1], m[2]): m[3] for m in baseline.PIN_ATTRIBUTE.finditer(raw)}
    require(all(attributes[n][key] == value for (n, key), value in old_attributes.items()),
            'historical raw electrical/pad attributes differ')
    return result.encode('ascii'), {'PortCount': 128, 'LocationsMatchRawReference': True,
                                    'CAM2D5': 'AA23', 'UARTTX': 'C24', 'ResetNExternalPort': False,
                                    'ExternalTimingMeasured': False}


def validate_sources():
    require(sha(PROJECT / MANIFEST) == MANIFEST_SHA, 'raw source manifest changed')
    manifest = json.loads((PROJECT / MANIFEST).read_text())
    names, hashes = manifest['source_files'], manifest['SourceSHA256']
    require(manifest['Target'] == TARGET and len(names) == len(set(names))
            and set(names) == set(hashes), 'raw source inventory differs')
    for name in names:
        path = baseline.paths.inside(PROJECT, name)
        require(path.absolute() == path.resolve() and sha(path).lower() == hashes[name].lower(), 'source drift: ' + name)
    require(sha(PROJECT / BASE_TOP) == manifest['BaseTop']['SHA256'], 'raw reference top drift')
    reference = (PROJECT / BASE_TOP).read_text().replace('module raw_camera_capture_cam2_ref(', 'module ' + TARGET + '(')
    reference = reference.replace('ov5640_cadence_trial_init #', 'ov5640_cadence_upright_init #')
    require(normalized(reference) == normalized((PROJECT / TOP).read_text()), 'raw top changes exceed names/init')
    mode = manifest['SensorModeReference']
    require(sha(PROJECT / mode['Path']) == mode['SHA256'], 'display sensor-mode reference drift')
    sensor_instance = re.compile(r"ov5640_cadence_upright_init#\(\.DYNAMIC_PAD_MASK\(1\)\)\w+\((.*?)\);", re.S)
    for name in (TOP, mode['Path']):
        matches = sensor_instance.findall(normalized((PROJECT / name).read_text()))
        require(len(matches) == 1 and ".trial_pad_mask(16'h7ff0)" in matches[0],
                'sensor init/mask differs from display: ' + name)
    old = (PROJECT / BASE_TCL).read_text()
    designs = re.findall(r'^add_design \{D:/English/FPGA/distortion/([^}]+)\}', old, re.M)
    designs = [{BASE_TOP: TOP, OLD_INIT: INIT}.get(n, n) for n in designs]
    require(len(designs) == 17 and len(set(designs)) == 17, '17 explicit designs required')
    extras = [baseline.RAW_FDC, baseline.RAW_PINS, 'rtl/video_crc32.vh',
              'board/ov5640_cadence_trial_commands.vh', 'board/ms7210_commands.vh']
    require(expand_sources(PROJECT, designs + extras) == names, 'IDF/source closure differs')
    for name in names:
        if Path(name).suffix not in ('.v', '.vh'):
            continue
        data = (PROJECT / name).read_bytes()
        includes = baseline.paths.INCLUDE.findall(data)
        expected = [] if name not in INCLUDES else [INCLUDES[name][0].encode()]
        require(includes == expected and len(baseline.paths.INCLUDE_DIRECTIVE.findall(data)) == len(expected),
                'include closure differs: ' + name)
    fdc, pins = constraint_bytes()
    return {'Manifest': manifest, 'Sources': names, 'ExplicitDesigns': designs,
            'SourceSHA256': {n: sha(PROJECT / n) for n in names}, 'FDCBytes': fdc, 'PinAudit': pins}


def recipe(work, pds_shell='D:/pango/PDS_2023.2/bin/pds_shell.exe', maximum_seconds=1800):
    work = work_path(work)
    require(type(maximum_seconds) is int and 60 <= maximum_seconds <= 1800, 'deadline must be60..1800')
    roles = validate_sources()
    pds = Path(pds_shell).absolute()
    require(pds == pds.resolve() and pds.is_file() and pds.name.lower() == 'pds_shell.exe', 'native PDS path required')
    extra = [MANIFEST, BASE_TOP, BASE_TCL, FDC, RCF, roles['Manifest']['SensorModeReference']['Path'],
             SELF.relative_to(PROJECT).as_posix(), RUNNER, 'tools/pds_source_manifest.py',
             'tools/prepare_camera_vga_output.py', 'tools/prepare_board1080_timing.py',
             'tools/run_camera_vga_output_diagnostic.py']
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
    fdc = work / 'compiled/board/raw-camera-upright-diagnostic.fdc'
    payloads[fdc] = roles['FDCBytes']
    lines = ['# Raw upright diagnostic only; no bitstream or hardware.',
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
            'Preview': {'HDMIScan': '1280x720p60', 'SourcePreview': [160, 120], 'UARTSource': [640, 480]},
            'Tcl': {'Path': (work / 'timing.tcl').as_posix(), 'SHA256': baseline.paths.sha_bytes(tcl)},
            'PDS': {'Executable': str(pds), 'ExecutableSHA256': sha(pds), 'ExpectedVersion': baseline.paths.PDS_VERSION},
            'CommandToRunSeparately': [str(pds), '-file', (work / 'timing.tcl').as_posix(), '-work_dir', work.as_posix(), '-project_name', TARGET],
            'MaximumSecondsForExternalExecutor': maximum_seconds, 'ExternalDeadlineRequired': True,
            'PreSTAFinalDatabase': (work / 'pre-sta-final.adf').as_posix(),
            'ExpectedActualStages': ['Compile', 'Synthesize', 'Device Map', 'Place', 'Route', 'Route Optimize', 'Report Timing'],
            'HardwareAccessed': False, 'EDAExecuted': False, 'BitstreamRequested': False,
            **{k: False for k in baseline.FALSE_FLAGS},
            'Limits': 'Independent raw diagnostic. No display timing acceptance or old reset/route repair is inherited. Native CDC/IO/reset review remains required.'}
    require(all(len(str(p)) < 260 for p in payloads), 'compiled path exceeds Windows native path limit; shorten run name')
    require(all(sha(PROJECT / n) == h for n, h in inputs.items()), 'recipe input drift')
    return plan, payloads, tcl


def prepare(work, pds_shell='D:/pango/PDS_2023.2/bin/pds_shell.exe', maximum_seconds=1800):
    work = work_path(work)
    require(not work.exists(), 'fresh raw workspace required')
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
