"""Prepare an independent 1280x720 transport candidate; no EDA or hardware.

The first candidate has exact identity geometry, not a transplanted VGA lens
calibration. Sensor-mode calibration and physical signoff remain separate.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re

import prepare_camera_vga_calibrated as previous
import prepare_camera720_sensor as sensor

baseline = previous.baseline
PROJECT = Path(__file__).resolve().parents[1]
SELF = Path(__file__).resolve()
TARGET = 'camera720_transport_top'
TOP = 'board/camera720_transport_top.v'
HEADER = 'board/camera720-identity.vh'
FDC = 'board/camera720-output-diagnostic.fdc'
MANIFEST = 'board/camera720-output-sources.json'
WORK = PROJECT/'work/camera720-output'
RUNNER = 'tools/run_camera720_output_diagnostic.py'
SCHEMA = 'camera720-output-diagnostic-preparation-v1'
SOURCE_SCHEMA = 'camera720-output-source-closure-v1'
BASE_SHA = 'cdb5645f89566a17fdc3274f5d41da1f45d4f8dd4abe30f7316d9f5663915100'
BASE_PREP_SHA = '47b01ebb7aaf41a4a9cff4e468a3ea0fd017a4c547cd70f7972822d4907c862d'
REPLACE = {
    previous.TOP: TOP, previous.HEADER: HEADER,
    'board/camera-vga-output-diagnostic.fdc': FDC,
    'rtl/experimental/ov5640_cadence_upright_init.v': sensor.INIT,
    'board/ov5640_cadence_trial_commands.vh': sensor.ROM,
}
ADDED = [sensor.FRONTEND, sensor.MONITOR]
INCLUDES = {REPLACE.get(n, n): (REPLACE.get(a, a), REPLACE.get(b, b))
            for n, (a, b) in previous.INCLUDES.items()}
INCLUDES[TOP] = (HEADER, HEADER)
INCLUDES[sensor.INIT] = (sensor.ROM, sensor.ROM)
require, sha = previous.require, previous.sha


def expected_header():
    # 1024 and 1/1024 are exactly represented in the mapper's fixed-point
    # formats. All input pixels map to their original integer coordinates.
    values = [163712, 92032, 163712, 92032, 262144, 262144,
              1048576, 1048576, 0, 0, 0, 0, 0]
    names = ['OUT_CX', 'OUT_CY', 'SRC_CX', 'SRC_CY', 'SRC_FX', 'SRC_FY',
             'INV_FX', 'INV_FY', 'K1', 'K2', 'K3', 'P1', 'P2']
    lines = ['// Exact identity transport at 1280x720; NOT a camera calibration.',
             '// A new sensor-mode lens profile is required before correction acceptance.']
    for i, (name, value) in enumerate(zip(names, values)):
        bits = 24 if i < 6 else 32
        lines.append(f"localparam signed [{bits-1}:0] C720_{name}={bits}'sd{value};")
    lines.append('localparam C720_RADIUS_Q22=8388608;')
    return '\n'.join(lines)+'\n'


def expected_top():
    text = (PROJECT/previous.TOP).read_text(encoding='utf-8')
    text = text.replace('module camera_vga_calibrated_top', 'module '+TARGET)
    text = text.replace('localparam WIDTH=640,HEIGHT=480', 'localparam WIDTH=1280,HEIGHT=720')
    begin = text.index('    wire camera_ready,camera_failed;')
    end = text.index('    wire ddr_ref_clk', begin)
    text = text[:begin]+'''    wire camera_ready,camera_failed,camera_configured;
    wire [7:0] camera_fault;
    // Observe complete DVP frames before releasing capture. The camera monitor
    // has its own reset; loss of authorization only stops new pipeline work.
    ov5640_current720_frontend camera_configuration(
        .ref_clk(clk_27m),.pclk(cam_pclk),.rst_n(global_reset_n),
        .vsync_active(!cam_vsync),.href_active(!cam_href),
        .cam_rst_n(cam_rst_n),.cam_scl(cam_scl),.cam_sda(cam_sda),
        .configured(camera_configured),.raw_authorize(camera_ready),
        .failed(camera_failed),.fault(camera_fault));

'''+text[end:]
    text = text.replace(previous.HEADER, HEADER).replace('CAL_', 'C720_')
    text = text.replace('// Isolated current-lens calibrated VGA candidate. Separate routed and hardware verification required.',
                        '// Independent 720p transport candidate. New physical and board verification required.')
    text = text.replace('// Isolated CAM2 VGA input -> production-derived DDR/remap/output candidate.',
                        '// CAM2 1280x720 input -> existing DDR/remap/output implementation.')
    text = text.replace('// Fixed current-lens mapping: f240 output, no rotation, gamma bypass.',
                        '// Exact identity mapping, no rotation, gamma bypass. Not lens correction.')
    return text


def expected_fdc():
    return ((PROJECT/'board/camera-vga-output-diagnostic.fdc').read_bytes()+
            b'\n# Independent 720p transport candidate: same CAM2 pads and 48MHz PCLK budget.\n'
            b'# All new monitor CDC paths require their own routed structural/timing audit.\n')


def roles():
    require(sha(PROJECT/previous.MANIFEST) == BASE_SHA, 'published VGA source manifest changed')
    require(sha(PROJECT/'tools/prepare_camera_vga_calibrated.py') == BASE_PREP_SHA, 'published VGA preparation changed')
    old = previous.validate_sources()
    sensor.verify()
    require((PROJECT/TOP).read_text(encoding='utf-8') == expected_top(), '720 top differs from declared integration')
    require((PROJECT/HEADER).read_text(encoding='utf-8') == expected_header(), '720 identity configuration differs')
    require((PROJECT/FDC).read_bytes() == expected_fdc(), '720 clock/pad constraints differ')
    names = [REPLACE.get(n, n) for n in old['Sources']]+ADDED
    designs = [REPLACE.get(n, n) for n in old['ExplicitDesigns']]+ADDED
    require(len(names) == len(set(names)) and set(REPLACE).isdisjoint(names), '720 replacement inventory differs')
    for name in names:
        if Path(name).suffix in ('.v', '.vh'):
            data = (PROJECT/name).read_bytes()
            inc = baseline.paths.INCLUDE.findall(data)
            binding = INCLUDES.get(name)
            require(len(baseline.paths.INCLUDE_DIRECTIVE.findall(data)) == len(inc) and
                    inc == ([] if binding is None else [binding[0].encode('ascii')]), '720 include differs: '+name)
    # The package DDR body, APB tie-offs and physical port declarations are
    # preserved literally by expected_top; prior routed timing is not reused.
    return {**old, 'Manifest': MANIFEST, 'Sources': names,
            'SourceSHA256': {n: sha(PROJECT/n) for n in names}, 'ExplicitDesigns': designs,
            'Headers': sorted(n for n in names if Path(n).suffix == '.vh'), 'Constraint': FDC,
            'ConstraintSHA256': {FDC: sha(PROJECT/FDC), old['RouteConstraint']: sha(PROJECT/old['RouteConstraint'])},
            'RoleCounts': {**old['RoleCounts'], 'ManifestSources': len(names),
                           'ExplicitVerilog': old['RoleCounts']['ExplicitVerilog']+2},
            'DDRBodyComparison': {'PublishedTop': previous.TOP, 'CandidateTop': TOP,
                                  'DDRBodyUnchanged': True, 'InheritedPhysicalTimingPass': False}}


def source_manifest():
    r = roles()
    return {'Schema': SOURCE_SCHEMA, 'Target': TARGET,
            'BaseManifest': {'Path': previous.MANIFEST, 'SHA256': BASE_SHA},
            'SourceReplacements': REPLACE, 'AddedSources': ADDED,
            'source_files': r['Sources'], 'SourceSHA256': r['SourceSHA256'],
            'Constraint': r['Constraint'], 'RouteConstraint': r['RouteConstraint'],
            'ConstraintSHA256': r['ConstraintSHA256'], 'RoleCounts': r['RoleCounts'],
            'PinAudit': r['PinAudit'], 'DDRBodyComparison': r['DDRBodyComparison'],
            'SensorPort': sensor.verify(), 'Geometry': [1280, 720],
            'OutputActiveArea': [1920, 1080], 'OutputRaster': [2200, 1125],
            'Mapping': 'identity transport; no lens calibration',
            'BankStrideUIUnits': 1048576, 'UIAddressUnitBytes': 4,
            'FrameBytes': 1843200, 'FrameBeats256': 57600,
            'OpticalCorrectionAccepted': False, 'HardwareAccessed': False,
            'EDAExecuted': False, 'HardwareReleaseAllowed': False}


def validate_sources():
    actual = json.loads((PROJECT/MANIFEST).read_text(encoding='utf-8'))
    require(actual == source_manifest(), '720 manifest differs from current source closure')
    return roles()


def work_path(value):
    p = Path(value).absolute()
    require(p == p.resolve() and p.parent == WORK and p.parent == p.parent.resolve() and
            re.fullmatch(r'[A-Za-z0-9_-]+', p.name), 'fresh canonical direct 720 workspace child required')
    return p


def literal(value):
    p = Path(value).absolute()
    require(p == p.resolve() and p.is_relative_to(PROJECT), '720 recipe path escaped project')
    return baseline.paths.tcl_path(p.as_posix())


def make_tcl(designs, fdc, rcf, work):
    lines = ['# Independent 720p transport compile/map/route/STA; no bitstream or hardware.',
             'set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG676']
    lines += ['add_design '+literal(p) for p in designs]
    lines += ['add_constraint '+literal(fdc), 'compile -top_module '+TARGET,
              'synthesize -ads -selected_syn_tool_opt 2', 'dev_map', 'add_constraint '+literal(rcf),
              'pnr -optimize_multi_corner_timing -fix_hold_violation',
              'if {[file exists '+literal(work/'place_route'/(TARGET+'_pnr.adf'))+']} {',
              '    file copy '+literal(work/'place_route'/(TARGET+'_pnr.adf'))+' '+literal(work/'pre-sta-final.adf'),
              '}', 'report_timing -force_to_run -delay_type min_max -max_path 1000 -nworst 4 -report_exception TRUE']
    return '\n'.join(lines)+'\n'


def recipe(work, pds_shell='D:/pango/PDS_2023.2/bin/pds_shell.exe', maximum_seconds=1800):
    work = work_path(work)
    require(type(maximum_seconds) is int and 60 <= maximum_seconds <= 1800, 'deadline must be 60..1800s')
    r = validate_sources()
    pds = Path(pds_shell).absolute()
    require(pds == pds.resolve() and pds.is_file() and pds.name.lower() == 'pds_shell.exe', 'canonical native PDS shell required')
    auxiliary = {**previous.FIXED_HELPERS, previous.MANIFEST: BASE_SHA,
                 'tools/prepare_camera_vga_calibrated.py': BASE_PREP_SHA,
                 previous.PROFILE: previous.PROFILE_SHA, previous.MAPPING: previous.MAPPING_SHA,
                 baseline.BASE: baseline.BASE_SHA256, baseline.RAW_FDC: baseline.RAW_FDC_SHA,
                 baseline.RAW_PINS: baseline.RAW_PINS_SHA, **sensor.RETAINED}
    for name in (MANIFEST, TOP, HEADER, FDC, RUNNER, SELF.relative_to(PROJECT).as_posix(),
                 'tools/prepare_camera720_sensor.py', previous.TOP,
                 'tools/run_camera_vga_calibrated_diagnostic.py',
                 'board/camera-vga-output-diagnostic.fdc'):
        auxiliary[name] = sha(PROJECT/name)
    # previous.validate_sources reads all published sources. Bind those reads
    # too, including the replaced VGA files, rather than just the new designs.
    auxiliary.update(previous.validate_sources()['SourceSHA256'])
    inputs = {**auxiliary, **r['SourceSHA256'], **r['ConstraintSHA256']}
    payloads, copies, rewrites, designs = {}, [], [], []
    for name in r['Sources']+[r['RouteConstraint']]:
        data = (PROJECT/name).read_bytes()
        require(baseline.paths.sha_bytes(data) == inputs[name], 'source changed: '+name)
        transformed = data
        if name in INCLUDES:
            old, header = INCLUDES[name]
            match = list(baseline.paths.INCLUDE.finditer(data))
            require(len(match) == 1 and match[0][1] == old.encode('ascii'), 'include transformation differs')
            replacement = (work/'compiled'/header).as_posix()
            baseline.paths.tcl_path(replacement)
            transformed = data[:match[0].start(1)]+replacement.encode('ascii')+data[match[0].end(1):]
            rewrites.append({'Source': name, 'OriginalInclude': old, 'CompiledInclude': replacement,
                             'Header': header, 'HeaderSHA256': inputs[header]})
        destination = work/'compiled'/name
        payloads[destination] = transformed
        copies.append({'Source': name, 'OriginalSHA256': inputs[name], 'CompiledPath': destination.as_posix(),
                       'CompiledSHA256': baseline.paths.sha_bytes(transformed)})
        if name in r['ExplicitDesigns']:
            designs.append(destination)
    tcl = make_tcl(designs, work/'compiled'/r['Constraint'], work/'compiled'/r['RouteConstraint'], work).encode('ascii')
    plan = {'Schema': SCHEMA, 'Target': TARGET, 'Scope': 'PrepareOnlyNoEDA',
            'ProjectRoot': str(PROJECT), 'WorkDirectory': str(work), 'ScratchRoot': str(WORK),
            'Manifest': MANIFEST, 'InputSHA256': inputs, 'RoleCounts': r['RoleCounts'],
            'CompiledInputs': copies, 'ExplicitDesigns': [p.as_posix() for p in designs],
            'IDFExpandedSourcesNotAdded': r['IDFExpandedSources'], 'IncludeRewrites': rewrites,
            'Tcl': {'Path': (work/'timing.tcl').as_posix(), 'SHA256': baseline.paths.sha_bytes(tcl)},
            'PDS': {'Executable': str(pds), 'ExecutableSHA256': sha(pds), 'ExpectedVersion': baseline.paths.PDS_VERSION},
            'CommandToRunSeparately': [str(pds), '-file', (work/'timing.tcl').as_posix(),
                                     '-work_dir', work.as_posix(), '-project_name', TARGET],
            'MaximumSecondsForExternalExecutor': maximum_seconds, 'ExternalDeadlineRequired': True,
            'ExpectedActualStages': ['Compile', 'Synthesize', 'Device Map', 'Place', 'Route', 'Route Optimize', 'Report Timing'],
            'HardwareAccessed': False, 'EDAExecuted': False, 'BitstreamRequested': False,
            'TimingAccepted': False, 'HardwareReleaseAllowed': False, 'OpticalCorrectionAccepted': False,
            'Limits': 'Identity 720p transport only. No inherited timing, CDC, pin, sensor-mode optical calibration or board acceptance.'}
    require(all(sha(PROJECT/n) == h for n, h in inputs.items()), 'source drift during preparation')
    return plan, payloads, tcl


def prepare(work, pds_shell='D:/pango/PDS_2023.2/bin/pds_shell.exe', maximum_seconds=1800):
    work = work_path(work)
    require(not work.exists(), 'fresh 720 stage required')
    plan, payloads, tcl = recipe(work, pds_shell, maximum_seconds)
    work.mkdir(parents=True)
    for path, data in payloads.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    (work/'timing.tcl').write_bytes(tcl)
    plan['PreparedUTC'] = datetime.now(timezone.utc).isoformat()
    with (work/'plan.json').open('x', encoding='utf-8', newline='\n') as f:
        json.dump(plan, f, indent=2)
        f.write('\n')
    return plan


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--freeze-manifest', action='store_true')
    mode.add_argument('--audit-only', action='store_true')
    mode.add_argument('--work-dir', type=Path)
    parser.add_argument('--pds-shell', default='D:/pango/PDS_2023.2/bin/pds_shell.exe')
    parser.add_argument('--maximum-seconds', type=int, default=1800)
    args = parser.parse_args()
    if args.freeze_manifest:
        value = source_manifest()
        with (PROJECT/MANIFEST).open('x', encoding='utf-8', newline='\n') as f:
            json.dump(value, f, indent=2)
            f.write('\n')
        result = {'Manifest': MANIFEST, 'SHA256': sha(PROJECT/MANIFEST)}
    elif args.audit_only:
        result = {'Validated': True, 'RoleCounts': validate_sources()['RoleCounts']}
    else:
        value = prepare(args.work_dir, args.pds_shell, args.maximum_seconds)
        result = {'PreparedOnly': True, 'Plan': str(Path(value['WorkDirectory'])/'plan.json')}
    print(json.dumps({**result, 'EDAExecuted': False, 'HardwareAccessed': False}))


if __name__ == '__main__':
    main()
