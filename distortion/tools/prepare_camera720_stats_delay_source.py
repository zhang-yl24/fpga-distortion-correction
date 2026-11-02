"""Prepare an isolated core-counter UART and matched capture-control delay candidate; never execute EDA.

The explicit existing build plan supplies source provenance, not inherited
timing or hardware authority. A separate native executor is deliberately absent.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re

PROJECT = Path(__file__).resolve().parents[1]
SELF = Path(__file__).resolve()
WORK = PROJECT / 'work/camera720-stats-delay'
TARGET = 'camera720_calibrated_stats_delay_top'
BASE_TARGET = 'camera720_calibrated_top'
BASE_TOP = 'board/' + BASE_TARGET + '.v'
TOP = 'board/' + TARGET + '.v'
FDC = 'board/camera720-calibrated-stats-delay.fdc'
STATS = 'rtl/experimental/camera720_core_stats_uart.v'
UART = 'rtl/uart_tx.v'
CONTROL_DELAY = 'rtl/experimental/raw_camera_control_input_delay.v'
CONTROL_DELAY_SHA = '78c3b56145f6531b4fd8605b0ec2dc6a7d79466b9f3c5d48594448b1bb4f4fc9'
PIN_REFERENCE = 'board/raw_camera_capture_cam2_ref.fdc'
SCHEMA = 'camera720-calibrated-stats-delay-source-preparation-v1'
STATS_SHA = 'd886f7b2a37df5e607bedbb1ec33ee572427438a89c6167c33915b086a200e74'
INCLUDE = re.compile(rb'`include\s+"([^"\r\n]+)"')
UART_ATTRIBUTES = (
    ('PAP_IO_LOC', 'C24'), ('PAP_IO_VCCIO', '3.3'),
    ('PAP_IO_STANDARD', 'LVCMOS33'), ('PAP_IO_DRIVE', '4'), ('PAP_IO_SLEW', 'SLOW'))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def sha(path):
    return digest(Path(path).read_bytes())


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def encoded(value):
    return (json.dumps(value, indent=2, allow_nan=False) + '\n').encode('utf-8')


def bind(watched, path, expected=None):
    path = Path(path).resolve()
    require(path.is_file(), 'missing bound input: ' + str(path))
    actual = sha(path)
    require(expected is None or actual == expected, 'bound input changed: ' + str(path))
    require(str(path) not in watched or watched[str(path)] == actual, 'conflicting input hash')
    watched[str(path)] = actual
    return path


def ref(path):
    return {'Path': str(Path(path).resolve()), 'SHA256': sha(path)}


def relative_name(name):
    require(isinstance(name, str) and not Path(name).is_absolute()
            and not name.startswith('/') and ':' not in name
            and '\\' not in name and '..' not in Path(name).parts,
            'canonical project-relative source required')
    return name


def render_top(original, build_id, profile_id):
    require(re.fullmatch('[0-9a-f]{16}', build_id) and re.fullmatch('[0-9a-f]{16}', profile_id),
            'explicit 64-bit identity labels required')
    module = 'module ' + BASE_TARGET + ' #('
    port = '    input clk_27m,clk_p,clk_n,reset_n,\n'
    end = '\nendmodule\n'
    require(original.count(module) == original.count(port) == original.count(end) == 1,
            'exact current generated top anchors required')
    require('uart_txd' not in original and 'camera720_core_stats_uart' not in original,
            'baseline already contains telemetry')
    block = f'''
    // Read-only observations of existing core-domain counters. No feedback.
    // Existing local reset release is reused; status/underflows are unavailable.
    camera720_core_stats_uart #(.CLOCK_HZ(125000000),.BAUD(115200),
        .SAMPLE_CYCLES(125000000),.BUILD_ID(64'h{build_id}),
        .PROFILE_ID(64'h{profile_id})) core_statistics(
        .clk(core_clk),.rst_n(core_reset[1]),
        .source_accepted(captured_frames),.processed(processed_frames),
        .unique_presented(presented_frames),
        .status_valid(1'b0),.failed(1'b0),.fault(8'b0),.tx(uart_txd));
'''
    value = original.replace(module, 'module ' + TARGET + ' #(', 1).replace(
        port, port + '    output uart_txd,\n', 1).replace(end, block + end, 1)
    anchor = '    raw_camera_input_delay camera_data_delay(.pad_data(cam_data),.capture_data(delayed_cam_data));\n'
    capture = '.cam_vsync(cam_vsync),.cam_href(cam_href),.cam_data(delayed_cam_data)'
    require(value.count(anchor) == value.count(capture) == 1, 'exact capture input wiring required')
    require('delayed_cam_href' not in value and 'delayed_cam_vsync' not in value, 'controls already delayed')
    controls = '''    wire delayed_cam_href, delayed_cam_vsync;
    raw_camera_control_input_delay camera_control_delay(
        .pad_href(cam_href),.pad_vsync(cam_vsync),
        .capture_href(delayed_cam_href),.capture_vsync(delayed_cam_vsync));
'''
    value = value.replace(anchor, anchor+controls, 1).replace(capture,
        '.cam_vsync(delayed_cam_vsync),.cam_href(delayed_cam_href),.cam_data(delayed_cam_data)', 1)
    require(value.count('.vsync_active(!cam_vsync),.href_active(!cam_href)') == 1, 'raw monitor controls changed')
    require(value.count('.ref_clk(clk_27m),.pclk(cam_pclk),.rst_n(global_reset_n)') == 1, 'raw monitor clock changed')
    return value


def render_fdc(original, pin_reference):
    require('uart_txd' not in original and not re.search(r'\{PAP_IO_LOC\}\s*\{C24\}', original),
            'new UART pin already occupied or constrained')
    lines = [f'define_attribute {{p:uart_txd}} {{{key}}} {{{value}}}'
             for key, value in UART_ATTRIBUTES]
    require(all(pin_reference.splitlines().count(line) == 1 for line in lines),
            'UART C24 electrical contract differs from existing board reference')
    return original + '\n# Isolated statistics UART; new candidate requires native IO checks.\n' + '\n'.join(lines) + '\n'


def source_inputs(base_path, explicit_sha, watched):
    require(isinstance(explicit_sha, str) and re.fullmatch('[0-9a-f]{64}', explicit_sha),
            'explicit complete baseline plan SHA256 required')
    base_path = bind(watched, base_path, explicit_sha)
    base = read(base_path)
    require(base.get('Schema') == 'camera720-calibrated-diagnostic-preparation-v1'
            and base.get('Target') == BASE_TARGET and base_path.name == 'plan.json'
            and Path(base['WorkDirectory']).resolve() == base_path.parent,
            'exact calibrated source plan required')
    for path, h in base['InputSHA256'].items():
        bind(watched, path, h)
    for path, h in base['GeneratedSourceSHA256'].items():
        bind(watched, path, h)
    manifest_path = bind(watched, base['SourceManifest'])
    require(manifest_path == base_path.parent / 'source/manifest.json', 'unexpected source manifest path')
    manifest = read(manifest_path)
    require(manifest['Target'] == BASE_TARGET, 'wrong baseline source manifest target')
    names = [relative_name(n) for n in manifest['source_files']]
    route = relative_name(manifest['RouteConstraint'])
    require(len(names) == len(set(names)) and set(manifest['SourceSHA256']) == set(names),
            'baseline source inventory differs')
    items = base['CompiledInputs']
    require(len(items) == len(names) + 1 and {x['Source'] for x in items} == set(names) | {route},
            'baseline compiled source inventory differs')
    rewrites = {r['Source']: r for r in base['IncludeRewrites']}
    require(len(rewrites) == len(base['IncludeRewrites']), 'duplicate include rewrite')
    sources = {}
    for item in items:
        name = relative_name(item['Source'])
        generated = base_path.parent / 'source' / name
        source = generated if str(generated) in base['GeneratedSourceSHA256'] else PROJECT / name
        source = bind(watched, source, item['OriginalSHA256'])
        data = source.read_bytes()
        if name in names:
            require(digest(data) == manifest['SourceSHA256'][name], 'source manifest bytes differ')
        compiled = bind(watched, item['CompiledPath'], item['CompiledSHA256'])
        require(compiled == base_path.parent / 'compiled' / name, 'compiled input escapes baseline')
        transformed = data
        if name in rewrites:
            row = rewrites[name]
            matches = list(INCLUDE.finditer(data))
            require(len(matches) == 1 and matches[0][1].decode('ascii') == row['OriginalInclude']
                    and row['CompiledInclude'] == (base_path.parent / 'compiled' / row['Header']).as_posix(),
                    'baseline include rewrite differs')
            hit = matches[0]
            transformed = data[:hit.start(1)] + row['CompiledInclude'].encode('ascii') + data[hit.end(1):]
        require(compiled.read_bytes() == transformed, 'compiled bytes exceed declared include rewrite')
        sources[name] = data
    bind(watched, base['Tcl']['Path'], base['Tcl']['SHA256'])
    require(Path(base['Tcl']['Path']).resolve() == base_path.parent / 'timing.tcl', 'unexpected baseline Tcl')
    return base_path, base, manifest, sources, rewrites


def recipe(base_path, explicit_sha, work):
    work = Path(work).absolute()
    require(work == work.resolve() and work.parent == WORK.resolve()
            and re.fullmatch('[A-Za-z0-9_-]+', work.name), 'direct isolated statistics work directory required')
    watched = {}
    base_path, base, old, sources, rewrites = source_inputs(base_path, explicit_sha, watched)
    stats = bind(watched, PROJECT / STATS, STATS_SHA)
    uart = bind(watched, PROJECT / UART)
    controls = bind(watched, PROJECT / CONTROL_DELAY, CONTROL_DELAY_SHA)
    pinref = bind(watched, PROJECT / PIN_REFERENCE)
    bind(watched, SELF)
    require(all(n not in sources for n in (STATS, UART, CONTROL_DELAY)), 'added module already in baseline closure')
    profile_ref = base['CalibrationEvidence']['Profile']
    bind(watched, profile_ref['Path'], profile_ref['SHA256'])
    identity = {'Schema': 'camera720-calibrated-stats-delay-source-identity-v1',
                'BaselinePlan': ref(base_path), 'StatisticsRTL': ref(stats), 'UART': ref(uart),
                'CaptureControlDelayRTL': ref(controls), 'CaptureControlDelayPS': 1500,
                'MonitorInputPath': 'raw controls and raw pixel clock; monitor has no data port',
                'Producer': ref(SELF), 'Profile': profile_ref, 'Target': TARGET,
                'NominalCoreHz': 125000000, 'UARTBaud': 115200, 'SampleCycles': 125000000,
                'StatusAvailable': False, 'UnderflowsAvailable': False}
    identity_sha = digest(json.dumps(identity, sort_keys=True, separators=(',', ':')).encode('utf-8'))
    old_constraint = old['Constraint']
    replacements = {BASE_TOP: TOP, old_constraint: FDC}
    top = render_top(sources[BASE_TOP].decode('utf-8'), identity_sha[:16], profile_ref['SHA256'][:16])
    fdc = render_fdc(sources[old_constraint].decode('utf-8'), pinref.read_text(encoding='utf-8'))
    current = {replacements.get(n, n): data for n, data in sources.items()}
    current[TOP], current[FDC] = top.encode('utf-8'), fdc.encode('utf-8')
    current[STATS], current[UART], current[CONTROL_DELAY] = stats.read_bytes(), uart.read_bytes(), controls.read_bytes()
    names = [replacements.get(n, n) for n in old['source_files']] + [STATS, UART, CONTROL_DELAY]
    compiled, new_rewrites = {}, []
    for name, data in current.items():
        row = rewrites.get(BASE_TOP if name == TOP else name)
        compiled[name] = data
        if row:
            hits = list(INCLUDE.finditer(data))
            require(len(hits) == 1 and hits[0][1].decode('ascii') == row['OriginalInclude'], 'new source include differs')
            inc = (work / 'compiled' / row['Header']).as_posix()
            hit = hits[0]
            compiled[name] = data[:hit.start(1)] + inc.encode('ascii') + data[hit.end(1):]
            new_rewrites.append({**row, 'Source': name, 'CompiledInclude': inc})
    explicit = []
    for path in base['ExplicitDesigns']:
        name = Path(path).resolve().relative_to(base_path.parent / 'compiled').as_posix()
        require(name in sources and Path(path).is_file(), 'explicit baseline source absent')
        explicit.append(work / 'compiled' / replacements.get(name, name))
    explicit += [work / 'compiled' / STATS, work / 'compiled' / UART, work / 'compiled' / CONTROL_DELAY]
    tcl = Path(base['Tcl']['Path']).read_text(encoding='ascii')
    tcl = tcl.replace(base_path.parent.as_posix(), work.as_posix())
    require(tcl.count('compile -top_module ' + BASE_TARGET + '\n') == 1, 'baseline compile target differs')
    tcl = tcl.replace(BASE_TARGET, TARGET).replace(old_constraint, FDC)
    marker = 'add_constraint {' + (work / 'compiled' / FDC).as_posix() + '}'
    require(tcl.count(marker) == 1, 'exact baseline source constraint marker required')
    tcl = tcl.replace(marker, '\n'.join('add_design {' + p.as_posix() + '}' for p in explicit[-3:]) + '\n' + marker, 1)
    require(re.findall(r'^add_design \{(.+)\}$', tcl, re.M) == [p.as_posix() for p in explicit],
            'new Tcl explicit design order differs')
    require(base_path.parent.as_posix() not in tcl and BASE_TARGET + '_pnr.adf' not in tcl,
            'new Tcl retains baseline output path')
    role_counts = {**old['RoleCounts'], 'ManifestSources': len(names),
                   'ExplicitVerilog': old['RoleCounts']['ExplicitVerilog'] + 3}
    manifest = {'Schema': 'camera720-calibrated-stats-delay-source-closure-v1', 'Target': TARGET,
                'BaselinePlan': ref(base_path), 'BaselineManifest': ref(base['SourceManifest']),
                'SourceReplacements': replacements, 'AddedSources': [STATS, UART, CONTROL_DELAY],
                'source_files': names, 'SourceSHA256': {n: digest(current[n]) for n in names},
                'Constraint': FDC, 'RouteConstraint': old['RouteConstraint'], 'RoleCounts': role_counts,
                'Calibration': base['CalibrationEvidence'], 'SourceIdentity': identity,
                'BuildID': identity_sha[:16], 'BuildIdentitySHA256': identity_sha,
                'ProfileID': profile_ref['SHA256'][:16], 'ProfileSHA256': profile_ref['SHA256'],
                'IDsAreBitstreamHashes': False, 'StatusAvailable': False, 'UnderflowsAvailable': False,
                'CounterDomain': 'core_clk', 'CounterReset': 'core_reset[1]',
                'AddedClockDomainCrossings': 0, 'InheritedRoutedTiming': False,
                'CaptureControlDelayPS': 1500, 'CaptureControlDelayLanes': 2, 'CaptureDataDelayLanes': 8,
                'MonitorInputPath': 'raw controls and raw pixel clock; monitor has no data port', 'SensorRegisterSettingsChanged': False,
                'PixelClockOrFrameProcessingChanged': False,
                'HardwareReleaseAllowed': False, 'OpticalCorrectionAccepted': False}
    payloads = {work / 'source' / n: data for n, data in current.items()}
    payloads.update({work / 'compiled' / n: data for n, data in compiled.items()})
    payloads[work / 'source/manifest.json'] = encoded(manifest)
    payloads[work / 'timing.tcl'] = tcl.encode('ascii')
    require(all(len(str(path)) < 260 for path in payloads),
            'native source paths must remain below the Windows260-character limit; use a shorter work directory')
    plan = {'Schema': SCHEMA, 'Target': TARGET, 'WorkDirectory': str(work),
            'BaselinePlan': ref(base_path), 'InputSHA256': watched, 'SourceManifest': str(work / 'source/manifest.json'),
            'OutputSHA256': {str(p): digest(data) for p, data in payloads.items()},
            'ExplicitDesigns': [str(p) for p in explicit], 'IncludeRewrites': new_rewrites,
            'Tcl': {'Path': str(work / 'timing.tcl'), 'SHA256': digest(tcl.encode('ascii'))},
            'RoleCounts': role_counts, 'BuildID': identity_sha[:16], 'BuildIdentitySHA256': identity_sha,
            'ProfileID': profile_ref['SHA256'][:16], 'UARTPin': dict(UART_ATTRIBUTES),
            'HardwareAccessed': False, 'EDAExecuted': False, 'HardwareReleaseAllowed': False,
            'NativeExecutorImplemented': False, 'InheritedTimingAccepted': False,
            'RequiredNextChecks': ['native source/build receipt for this new target',
                '129 final pins and C24 bank/electrical/output timing',
                'fresh10-lane native delay topology with no capture bypass and raw monitor alignment',
                'vendor-model simultaneous control/data boundary delay regression',
                'fresh full setup/hold/recovery/removal/MPW and resource limits',
                'current-netlist core counter taps/reset topology and all existing CDC paths',
                'candidate-specific DDR hold/reset treatment only if actual reports require it',
                'actual-lens image pipeline regression and physical image/UART observation'],
            'Limits': 'Offline source preparation only. Counter fanout may change placement/timing. '
                      'No old ADF, delay, CDC result or hardware authority is inherited. 64-bit labels '
                      'map to full source/profile identities, not a bitstream SHA. Rates assume a '
                      'continuous reset epoch and nominal 125 MHz core frequency.'}
    require(all(sha(p) == h for p, h in watched.items()), 'input changed during preparation')
    return plan, payloads


def prepare(base_path, explicit_sha, work):
    plan, payloads = recipe(base_path, explicit_sha, work)
    work = Path(plan['WorkDirectory'])
    require(not work.exists(), 'fresh statistics source directory required')
    for path, data in payloads.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as stream:
            stream.write(data)
    with (work / 'source-plan.json').open('xb') as stream:
        stream.write(encoded(plan))
    return work / 'source-plan.json'


def verify(path):
    path = Path(path).resolve()
    saved = read(path)
    require(saved.get('Schema') == SCHEMA and path == Path(saved['WorkDirectory']) / 'source-plan.json',
            'wrong isolated statistics source plan')
    plan, payloads = recipe(saved['BaselinePlan']['Path'], saved['BaselinePlan']['SHA256'], path.parent)
    require(plan == saved, 'statistics plan differs from source recomputation')
    for item, data in payloads.items():
        require(item.is_file() and item.read_bytes() == data, 'generated statistics artifact changed: ' + str(item))
    return plan


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--base-plan', type=Path)
    p.add_argument('--base-plan-sha256')
    p.add_argument('--work-dir', type=Path)
    p.add_argument('--verify-source-plan', type=Path)
    a = p.parse_args()
    if a.verify_source_plan:
        require(not any((a.base_plan, a.base_plan_sha256, a.work_dir)), 'verify only accepts a source plan')
        value = verify(a.verify_source_plan)
        print(json.dumps({'Verified': True, 'Target': value['Target'], 'EDAExecuted': False}))
    else:
        require(a.base_plan and a.base_plan_sha256 and a.work_dir, 'explicit baseline and fresh work directory required')
        out = prepare(a.base_plan, a.base_plan_sha256, a.work_dir)
        print(json.dumps({'Prepared': True, 'SourcePlan': ref(out), 'EDAExecuted': False, 'HardwareAccessed': False}))


if __name__ == '__main__':
    main()
