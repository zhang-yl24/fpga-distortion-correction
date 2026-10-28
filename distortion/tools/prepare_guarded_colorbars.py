"""Exact separate CAM2 internal-test-pattern clone, never hardware access."""
from pathlib import Path
import argparse
import copy
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parents[1]
BASE = 'raw_camera_capture_cam2_guarded'
TARGET = BASE+'_bars'
BUILD_TAG = 0x52473242
BASE_PREPARED_SHA256 = '538F357C33503EAF777D1780A11E04C8E455D1612EE172934ED134CD14AFC823'
BASE_VALIDATED_SHA256 = 'E98777D2AB580A6BBDEF5FD3F4D5DA9EE9DF0E0629D5A4293248C39344E00CD9'
APPROVED = ROOT/'build/offline-20261024'
BASE_BUILD = APPROVED/'raw-guarded-board-20261025-183203-296/validated-build.json'
BASE_SIM = APPROVED/'guarded-board-sim-20261025-182211-132/guarded-board-simulation.json'
SENSOR_OUTPUT_CONTRACT = {
    'input_origin': 'ov5640_internal_pre_isp_test_pattern',
    'control_register': '0x503D', 'control_value': '0x80',
    'pattern': 'standard_eight_color_bars', 'scene_light_required': False,
    'lens_optical_acceptance_eligible': False, 'calibration_scene_eligible': False,
}
COLOR_SOURCES = {
    'rtl/experimental/ov5640_colorbars_init.v': 'BAC47AB4178A5ABC23EAA053808784C39676AC630A5EA5137CF1572C2EE00421',
    'board/ov5640_colorbars_commands.vh': '39049F0F5F99AEF45AB89A329BC743A639F350E344DCA5A9B4DADE624E040144',
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest().upper()


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def expected():
    parent_path = ROOT/f'board/{BASE}-sources.json'
    if sha(parent_path) != BASE_PREPARED_SHA256:
        raise ValueError('the frozen natural CAM2 prepared manifest changed')
    parent = load(parent_path)
    if parent.get('target') != BASE or parent['GuardedControlContract']['build_tag'] != 0x52473201:
        raise ValueError('expected the frozen natural CAM2 guarded source identity')
    if (not isinstance(parent.get('source_files'), list) or len(parent['source_files']) != 107 or
            not all(isinstance(name, str) for name in parent['source_files']) or
            len(set(parent['source_files'])) != 107 or not isinstance(parent.get('SourceSHA256'), dict) or
            set(parent['SourceSHA256']) != set(parent['source_files'])):
        raise ValueError('parent source/hash closure differs')
    for name, digest in parent['SourceSHA256'].items():
        path = (ROOT/name).resolve()
        if (not isinstance(digest, str) or not re.fullmatch(r'[0-9A-Fa-f]{64}', digest) or
                not path.is_relative_to(ROOT.resolve()) or sha(path) != digest.upper()):
            raise ValueError('parent guarded source changed: '+name)
    for name, digest in COLOR_SOURCES.items():
        if sha(ROOT/name) != digest:
            raise ValueError('previously validated sensor colorbar source changed: '+name)
    mapping = {f'board/{BASE}{suffix}': f'board/{TARGET}{suffix}' for suffix in ('.v', '.fdc', '-pins.json')}
    mapping[f'board/build-{BASE}.tcl'] = f'board/build-{TARGET}.tcl'
    mapping['rtl/experimental/ov5640_cadence_trial_init.v'] = 'rtl/experimental/ov5640_colorbars_init.v'
    mapping['board/ov5640_cadence_trial_commands.vh'] = 'board/ov5640_colorbars_commands.vh'
    source_top = (ROOT/f'board/{BASE}.v').read_text(encoding='utf-8')
    if source_top.count('GUARDED_BUILD_TAG=32\'h52473201') != 1 or source_top.count('ov5640_cadence_trial_init #') != 1:
        raise ValueError('parent top does not have the one reviewed tag/init site')
    top = source_top.replace(BASE, TARGET).replace("GUARDED_BUILD_TAG=32'h52473201", "GUARDED_BUILD_TAG=32'h52473242")
    top = top.replace('ov5640_cadence_trial_init #', 'ov5640_colorbars_init #')
    top = '// Sensor internal PRE ISP bars (503D=80), not a natural optical scene.\n'+top
    source_tcl = (ROOT/f'board/build-{BASE}.tcl').read_text(encoding='utf-8')
    if source_tcl.count('rtl/experimental/ov5640_cadence_trial_init.v') != 1:
        raise ValueError('parent Tcl does not have one reviewed camera init source')
    tcl = source_tcl.replace(BASE, TARGET).replace('rtl/experimental/ov5640_cadence_trial_init.v', 'rtl/experimental/ov5640_colorbars_init.v')
    files = {
        f'board/{TARGET}.v': top,
        f'board/{TARGET}.fdc': (ROOT/f'board/{BASE}.fdc').read_text(encoding='utf-8'),
        f'board/{TARGET}-pins.json': (ROOT/f'board/{BASE}-pins.json').read_text(encoding='utf-8'),
        f'board/build-{TARGET}.tcl': tcl,
    }
    names = [mapping.get(name, name) for name in parent['source_files']]
    if len(names) != len(set(names)) or len(names) != 107:
        raise ValueError('unexpected colorbar/source dependency closure')
    pins = load(ROOT/f'board/{BASE}-pins.json')
    if len(pins) != 129 or pins.get('cam_data[5]') != 'AA23' or pins.get('uart_rxd') != 'B24':
        raise ValueError('colorbar target must retain the exact guarded CAM2 physical pads')
    return files, names, parent, parent_path


def prepare():
    files, names, parent, parent_path = expected()
    for name, content in files.items():
        path = ROOT/name
        if path.exists() and path.read_text(encoding='utf-8') != content:
            raise ValueError('refusing to overwrite a differing colorbar candidate: '+name)
    for name, content in files.items():
        path = ROOT/name
        if not path.exists():
            with path.open('x', encoding='utf-8', newline='\n') as stream:
                stream.write(content)
    contract = copy.deepcopy(parent['GuardedControlContract'])
    contract['build_tag'] = BUILD_TAG
    manifest = {'target': TARGET, 'hardware_accessed': False, 'physical_eye': None,
        'connector_slot_tag': 2, 'reference_board_port': 'CAM2 AA23 + RX B24; sensor internal bars only',
        'RawCaptureContract': parent['RawCaptureContract'], 'GuardedControlContract': contract,
        'SensorOutputContract': SENSOR_OUTPUT_CONTRACT,
        'source_files': names, 'SourceSHA256': {name: sha(ROOT/name) for name in names},
        'parent_prepared_source_manifest': {'path': str(parent_path), 'sha256': sha(parent_path)},
        'validated_colorbar_component_sha256': COLOR_SOURCES,
        'limits': 'Separate prepared digital test-pattern candidate. No sensor configuration, PDS or JTAG executed. PRE ISP pattern can still pass through sensor ISP; it does not measure illumination, optical color fidelity, lens calibration, physical eye or stereo timing.'}
    path = ROOT/f'board/{TARGET}-sources.json'
    if path.exists():
        if load(path) != manifest:
            raise ValueError('colorbar source manifest differs; use another candidate name')
    else:
        with path.open('x', encoding='utf-8') as stream:
            stream.write(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n')
    return manifest


def validate():
    files, names, parent, parent_path = expected()
    for name, content in files.items():
        if (ROOT/name).read_text(encoding='utf-8') != content:
            raise ValueError('unreviewed colorbar clone difference: '+name)
    manifest = load(ROOT/f'board/{TARGET}-sources.json')
    if (manifest.get('target') != TARGET or manifest.get('source_files') != names or
            manifest.get('hardware_accessed') is not False or manifest.get('physical_eye') is not None or
            manifest.get('connector_slot_tag') != 2 or
            manifest.get('validated_colorbar_component_sha256') != COLOR_SOURCES or
            manifest.get('SensorOutputContract') != SENSOR_OUTPUT_CONTRACT or
            manifest.get('RawCaptureContract') != parent['RawCaptureContract'] or
            manifest.get('GuardedControlContract') != {**parent['GuardedControlContract'], 'build_tag': BUILD_TAG} or
            manifest.get('parent_prepared_source_manifest') != {'path': str(parent_path), 'sha256': sha(parent_path)}):
        raise ValueError('colorbar clone contract or parent reference changed')
    hashes = manifest.get('SourceSHA256', {})
    if (not isinstance(hashes, dict) or set(hashes) != set(names) or
            any(not isinstance(digest, str) or not re.fullmatch(r'[0-9A-Fa-f]{64}', digest) or
                sha(ROOT/name) != digest.upper() for name, digest in hashes.items())):
        raise ValueError('colorbar source/hash closure changed')
    return manifest


def _verify_current_hashes(hashes):
    if not isinstance(hashes, dict) or not hashes:
        raise ValueError('source hash dictionary is absent')
    for name, digest in hashes.items():
        if (not isinstance(name, str) or not isinstance(digest, str) or
                not re.fullmatch(r'[0-9A-Fa-f]{64}', digest)):
            raise ValueError('malformed source hash entry')
        path = (ROOT/name).resolve()
        if not path.is_relative_to(ROOT.resolve()) or sha(path) != digest.upper():
            raise ValueError('current source differs from evidence: '+name)


def validate_build_inputs(colorbar_simulation=None):
    """Read-only build gate; an omitted colorbar simulation yields plan-only."""
    prepared = validate()
    if sha(BASE_BUILD) != BASE_VALIDATED_SHA256:
        raise ValueError('the specific validated natural CAM2 artifact changed')
    base = load(BASE_BUILD)
    base_prepared = load(ROOT/f'board/{BASE}-sources.json')
    if (base.get('Target') != BASE or type(base.get('ProcessExitCode')) is not int or
            base['ProcessExitCode'] != 0 or base.get('HardwareAccessed') is not False or
            base.get('PreparedSourceManifestSHA256') != BASE_PREPARED_SHA256 or
            base.get('SourceSHA256') != base_prepared['SourceSHA256'] or
            base.get('RawCaptureContract') != prepared['RawCaptureContract'] or
            base.get('GuardedControlContract') != base_prepared['GuardedControlContract']):
        raise ValueError('natural CAM2 validated artifact contract/source binding differs')
    _verify_current_hashes(base['SourceSHA256'])
    for name, key, suffix in [('Bitstream', 'SHA256', f'generate_bitstream/{BASE}.sbit'),
                              ('TimingReport', 'TimingSHA256', f'place_route/{BASE}_timing_summary_after_hold_fix.txt'),
                              ('PinReport', 'PinReportSHA256', f'place_route/{BASE}_prr.prt')]:
        path = BASE_BUILD.parent/suffix
        if Path(base[name]).resolve() != path.resolve() or sha(path) != base[key]:
            raise ValueError('natural CAM2 final artifact path/hash differs: '+name)
    if not Path(base['TimingReport']).read_text().startswith('Design Summary : All Constraints Met.'):
        raise ValueError('natural CAM2 final after-hold-fix timing failed')
    sim = load(BASE_SIM)
    tops = {'tb_raw_capture_lease', 'tb_guarded_raw_camera_capture', 'tb_guarded_temperature_cdc',
            'tb_guarded_status_uart', 'tb_guarded_board_pipeline'}
    if (sim.get('Passed') is not True or sim.get('HardwareAccessed') is not False or
            sim.get('OriginalRaw97SourceBindingPreserved') is not True or
            not isinstance(sim.get('RegressionTops'), list) or
            set(sim.get('RegressionTops', [])) != tops or len(sim.get('RegressionTops', [])) != 5):
        raise ValueError('complete five-top natural CAM2 RTL regression is required')
    _verify_current_hashes(sim.get('SourceSHA256'))
    if not isinstance(sim.get('LogSHA256'), dict) or set(sim['LogSHA256']) != {top+'-simulation.log' for top in tops}:
        raise ValueError('complete five-top actual log set is required')
    for name, digest in sim['LogSHA256'].items():
        path = BASE_SIM.parent/name
        if path.parent.resolve() != BASE_SIM.parent.resolve() or sha(path) != digest:
            raise ValueError('natural CAM2 simulation log changed')
        log = path.read_text()
        if not re.search(r'^PASS ', log, re.M) or re.search(r'fatal:|error:', log, re.I):
            raise ValueError('natural CAM2 simulation log did not pass')
    if (Path(sim['MixedStream']).resolve() != (BASE_SIM.parent/'guarded-board-mixed-stream.bin').resolve() or
            sha(Path(sim['MixedStream'])) != sim['MixedStreamSHA256']):
        raise ValueError('natural CAM2 regression logs/mixed stream are incomplete')
    result = {'ReadyForBuild': False, 'HardwareAccessed': False,
              'PreparedSourceManifestSHA256': sha(ROOT/f'board/{TARGET}-sources.json'),
              'ParentValidatedBuild': str(BASE_BUILD), 'ParentValidatedBuildSHA256': sha(BASE_BUILD),
              'BaseSimulationEvidence': str(BASE_SIM), 'BaseSimulationEvidenceSHA256': sha(BASE_SIM)}
    if colorbar_simulation is None:
        result['Reason'] = 'An additional source-bound colorbar initializer simulation is required for ExecuteBuild.'
        return result
    path = Path(colorbar_simulation).resolve()
    if not path.is_relative_to(APPROVED.resolve()) or path.name != 'guarded-colorbars-simulation.json':
        raise ValueError('colorbar simulation must be the named report below approved scratch')
    bars = load(path)
    required = {'rtl/reg16_i2c.v', 'rtl/experimental/ov5640_colorbars_init.v', 'board/ov5640_colorbars_commands.vh',
                'tests/tb_ov5640_colorbars.sv', 'tests/tb_guarded_colorbars_init.sv', 'tools/run-guarded-colorbars-sim.ps1'}
    if (bars.get('Passed') is not True or bars.get('HardwareAccessed') is not False or
            bars.get('PDSAccessed') is not False or type(bars.get('DynamicPadMask')) is not int or
            bars['DynamicPadMask'] != 1 or bars.get('TrialPadMask') != '7ff0' or
            bars.get('Fixture') != 'tb_ov5640_colorbars' or bars.get('OpticalSceneVerified') is not False or
            bars.get('TemperatureSafetyVerified') is not False or
            not isinstance(bars.get('SourceSHA256'), dict) or set(bars['SourceSHA256']) != required or
            bars['SourceSHA256'] != bars.get('SourceSHA256After')):
        raise ValueError('colorbar ready/readback/bad-pattern simulation is not source-bound')
    _verify_current_hashes(bars['SourceSHA256'])
    log_path = path.parent/'simulation.log'
    if Path(bars['SimulationLog']).resolve() != log_path or sha(log_path) != bars['SimulationLogSHA256']:
        raise ValueError('colorbar initializer actual simulation log changed')
    text = log_path.read_text()
    if ('PASS camera colorbars: 265 writes, preserved RGB565, test-pattern readback and wrong-ID/NACK/pad/PLL/format/test-pattern failures rejected' not in text or
            re.search(r'fatal:|error:', text, re.I)):
        raise ValueError('colorbar initializer log does not demonstrate the required pass')
    result.update(ReadyForBuild=True, ColorbarSimulationEvidence=str(path),
                  ColorbarSimulationEvidenceSHA256=sha(path), ColorbarSimulationLogSHA256=sha(log_path))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', action='store_true', help='create only this exact separate source candidate')
    parser.add_argument('--build-inputs', action='store_true', help='read-only natural-parent and initializer-simulation build gate')
    parser.add_argument('--colorbar-simulation', type=Path)
    args = parser.parse_args()
    if args.stage and (args.build_inputs or args.colorbar_simulation):
        parser.error('--stage cannot be combined with build-input validation')
    if args.colorbar_simulation and not args.build_inputs:
        parser.error('--colorbar-simulation requires --build-inputs')
    if args.build_inputs:
        print(json.dumps(validate_build_inputs(args.colorbar_simulation)))
        return
    manifest = prepare() if args.stage else validate()
    print(json.dumps({'target': TARGET, 'source_files': len(manifest['source_files']),
                      'hardware_accessed': False, 'sensor_internal_test_pattern': True}))


if __name__ == '__main__':
    main()
