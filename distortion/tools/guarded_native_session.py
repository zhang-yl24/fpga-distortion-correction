"""Source-bound guarded CAM2 SRAM session; default plans only, never Flash.

Only an explicit --execute may start JTAG/UART. The root task owns real hardware.
Every execution is finite, retains RX/TX evidence and attempts the prevalidated
fixed heartbeat after closing COM, including unknown programming outcomes.
"""
from pathlib import Path
from datetime import datetime, timezone
from dataclasses import dataclass, asdict
from types import MappingProxyType
import argparse
import copy
import json
import math
import re
import secrets
import time
import uuid

import native_camera_capture as capture
import program_native_raw as hw
import program_idle_heartbeat as idle

ROOT = Path(__file__).resolve().parents[1]
TARGET = 'raw_camera_capture_cam2_guarded'
BUILD_TAG = 0x52473201


@dataclass(frozen=True)
class Variant:
    target: str
    eye: str
    build_tag: int
    mode: str
    capture_mode_id: str
    connector_slot: int
    camera_id_tag: int
    factory: str = ''


VARIANTS = MappingProxyType({
    TARGET: Variant(TARGET, 'CAM2', BUILD_TAG, 'cam2-guarded',
                    'reference-vga-rgb565-cam2-guarded', 2, 0x43414D32),
    'raw_camera_capture_cam1_guarded': Variant('raw_camera_capture_cam1_guarded', 'CAM1',
                    0x52473101, 'cam1-guarded', 'reference-vga-rgb565-cam1-guarded',
                    1, 0x43414D31, 'prepare_guarded_cam1'),
    'raw_camera_capture_cam2_guarded_bars': Variant('raw_camera_capture_cam2_guarded_bars', 'CAM2',
                    0x52473242, 'sensor-internal-bars', 'reference-vga-rgb565-cam2-guarded-bars',
                    2, 0x43414D32, 'prepare_guarded_colorbars'),
    'raw_camera_capture_cam1_guarded_sccb25': Variant('raw_camera_capture_cam1_guarded_sccb25', 'CAM1',
                    0x52473125, 'cam1-guarded-sccb25', 'reference-vga-rgb565-cam1-guarded-sccb25',
                    1, 0x43414D31, 'prepare_guarded_cam1_sccb25'),
    'raw_camera_capture_cam1_guarded_isolated': Variant('raw_camera_capture_cam1_guarded_isolated', 'CAM1',
                    0x52473149, 'cam1-guarded-isolated', 'reference-vga-rgb565-cam1-guarded-isolated',
                    1, 0x43414D31, 'prepare_guarded_cam1_isolated'),
})
SCENARIOS = ('boot-idle', 'idle', 'capture', 'duplicate-grant', 'lease-expiry', 'host-silence', 'stop-drain', 'negative-commands')
RAW_CONTRACT = {'protocol': 'PGFRAME1', 'payload_role': 'native_raw',
                'geometry_applied': False, 'image_size': [640, 480]}


def protocol():
    import guarded_protocol
    return guarded_protocol


def variant_for(target=TARGET):
    if not isinstance(target, str) or target not in VARIANTS:
        raise ValueError('select an explicit whitelisted guarded target variant')
    return VARIANTS[target]


def _variant_factory(variant):
    if variant.factory == 'prepare_guarded_cam1_isolated':
        import prepare_guarded_cam1_isolated as factory
        return factory.verify_clone(), None
    if variant.factory == 'prepare_guarded_cam1_sccb25':
        import prepare_guarded_cam1_sccb25 as factory
        return factory.verify_clone(), None
    if variant.factory == 'prepare_guarded_cam1':
        import prepare_guarded_cam1 as factory
        return factory.verify_clone(), None
    if variant.factory == 'prepare_guarded_colorbars':
        import prepare_guarded_colorbars as factory
        return factory.validate(), copy.deepcopy(factory.SENSOR_OUTPUT_CONTRACT)
    return None, None


def _same_contract(left, right):
    # Unlike dict equality, preserve the distinction between False and integer0.
    return json.dumps(left, sort_keys=True, allow_nan=False) == json.dumps(right, sort_keys=True, allow_nan=False)


def _fixed(base, name):
    path = (Path(base)/name).resolve()
    if not path.is_relative_to(Path(base).resolve()) or not path.is_file():
        raise ValueError('missing or escaped guarded artifact: '+str(name))
    return path


def _helpers(target=TARGET):
    variant = variant_for(target)
    names = ('guarded_native_session.py', 'guarded_protocol.py', 'program_native_raw.py',
             'program_idle_heartbeat.py', 'native_camera_capture.py',
             'camera_eye_pin_audit.py', 'frame_protocol.py')
    result = {str(Path('tools')/name): hw.sha(ROOT/'tools'/name) for name in names}
    result['output/project/guarded-protocol-v2.json'] = hw.sha(ROOT/'output/project/guarded-protocol-v2.json')
    if variant.factory:
        result['tools/'+variant.factory+'.py'] = hw.sha(ROOT/'tools'/(variant.factory+'.py'))
    if variant.factory in ('prepare_guarded_cam1_sccb25', 'prepare_guarded_cam1_isolated'):
        result['tools/prepare_guarded_cam1.py'] = hw.sha(ROOT/'tools/prepare_guarded_cam1.py')
    return result


def _limits(port, scenario, frames, seconds, lease_ms, frequency):
    if not isinstance(port, str) or not re.fullmatch(r'COM[1-9][0-9]*', port):
        raise ValueError('an explicit Windows COM port is required')
    if scenario not in SCENARIOS or type(frames) is not int or not 0 <= frames <= 3:
        raise ValueError('select a listed finite scenario and a total frame budget 0..3')
    if (scenario in ('boot-idle', 'idle', 'negative-commands')) != (frames == 0):
        raise ValueError('idle/negative scenarios require zero frames; capture scenarios require 1..3')
    if type(seconds) not in (int, float) or not math.isfinite(seconds) or not 15 <= seconds <= 60:
        raise ValueError('UART session wall bound must be finite within 15..60 seconds')
    if type(lease_ms) is not int or not 1 <= lease_ms <= 24000:
        raise ValueError('one bounded grant lease is 1..24000 ms')
    if frequency not in ('1MHz', '5MHz', '10MHz'):
        raise ValueError('SRAM requires 1/5/10MHz; 100KHz is read-only scanning, never this download')
    if scenario in ('lease-expiry', 'host-silence') and (frames < 2 or lease_ms > 4000):
        raise ValueError('expiry/silence needs an unused second frame and lease <=4000ms, shorter than a VGA UART packet')
    if scenario == 'stop-drain' and (frames < 2 or lease_ms < 8000):
        raise ValueError('STOP drain needs an unused second frame and lease >=8000ms')
    if scenario == 'duplicate-grant' and frames != 1:
        raise ValueError('duplicate-grant uses exactly one admitted frame budget')


def _routed_pins(path):
    result = {}
    for line in path.read_text(encoding='utf-8', errors='replace').splitlines():
        fields = line.split('|')
        if len(fields) >= 7 and fields[4]:
            if fields[6] != 'YES' or fields[4] in result:
                raise ValueError('duplicate/inactive routed guarded port')
            result[fields[4]] = fields[0]
    if len(result) != len(set(result.values())):
        raise ValueError('routed guarded pin collision')
    return result


def validate_guarded_build(build_dir, *, target=TARGET):
    variant = variant_for(target)
    base = Path(build_dir).resolve()
    if not base.is_dir() or not base.is_relative_to(hw.APPROVED.resolve()):
        raise ValueError('select an existing guarded build inside approved offline scratch')
    manifest_path = _fixed(base, 'validated-build.json')
    manifest = capture.load_json(manifest_path)
    if any(manifest.get(k) != v for k, v in {
            'Target': variant.target, 'Device': 'PG2L100H', 'Package': 'FBG676',
            'SCBV': 'High Voltage', 'UnusedIO': 'UNUSED'}.items()):
        raise ValueError('only the exact guarded CAM2 PG2L100H FBG676 SRAM target is permitted')
    prepared_path = _fixed(ROOT, 'board/'+variant.target+'-sources.json')
    prepared = capture.load_json(prepared_path)
    contract = {**protocol().GUARDED_CONTROL_CONTRACT, 'build_tag': variant.build_tag}
    if capture.load_json(_fixed(ROOT, 'output/project/guarded-protocol-v2.json')) != protocol().protocol_spec():
        raise ValueError('shared protocol specification differs from the host codec')
    if (prepared.get('target') != variant.target or not _same_contract(manifest.get('RawCaptureContract'), RAW_CONTRACT)
            or not _same_contract(prepared.get('RawCaptureContract'), RAW_CONTRACT)
            or not _same_contract(manifest.get('GuardedControlContract'), contract)
            or not _same_contract(prepared.get('GuardedControlContract'), contract)):
        raise ValueError('guarded/raw control contracts differ from the shared fixed protocol')
    factory_manifest, sensor_contract = _variant_factory(variant)
    if ((variant.factory and factory_manifest is None)
            or (factory_manifest is not None and not _same_contract(factory_manifest, prepared))):
        raise ValueError('selected variant differs from its exact read-only clone factory')
    trial_contract = _expected_sccb_trial_contract(variant)
    if trial_contract is not None:
        if (not _same_contract(prepared.get('SCCBTrialContract'), trial_contract)
                or not _same_contract(manifest.get('SCCBTrialContract'), trial_contract)):
            raise ValueError('SCCB25 diagnostic contract differs from its exact factory')
        top = _fixed(ROOT, 'board/'+variant.target+'.v').read_text(encoding='utf-8-sig')
        top = re.sub(r'/\*.*?\*/|//[^\r\n]*', '', top, flags=re.S)
        values = re.findall(r'\.I2C_QUARTER_CYCLES\s*\(\s*([^()]+)\s*\)', top)
        if len(values) != 1 or values[0].strip() != '270':
            raise ValueError('SCCB25 requires its one explicit camera I2C_QUARTER_CYCLES(270)')
    elif 'SCCBTrialContract' in manifest or 'SCCBTrialContract' in prepared:
        raise ValueError('ordinary variants cannot masquerade as the SCCB25 diagnostic')
    reset_contract = _expected_other_sensor_reset_contract(variant)
    if reset_contract is not None:
        if (not _same_contract(prepared.get('OtherSensorResetTrialContract'), reset_contract)
                or not _same_contract(manifest.get('OtherSensorResetTrialContract'), reset_contract)):
            raise ValueError('isolated diagnostic reset contract differs from its exact factory')
        top = _fixed(ROOT, 'board/'+variant.target+'.v').read_text(encoding='utf-8-sig')
        top = re.sub(r'/\*.*?\*/|//[^\r\n]*', '', top, flags=re.S)
        drives = re.findall(r'assign\s+cam2_hold_rst_n\s*=\s*([^;]+);', top)
        if len(drives) != 1 or drives[0].strip() != "1'b0":
            raise ValueError('isolated reset must be one explicit constant-zero sink-only assignment')
    elif 'OtherSensorResetTrialContract' in manifest or 'OtherSensorResetTrialContract' in prepared:
        raise ValueError('ordinary variants cannot carry an isolated reset diagnostic contract')
    if sensor_contract is not None:
        if (not _same_contract(manifest.get('SensorOutputContract'), sensor_contract)
                or not _same_contract(prepared.get('SensorOutputContract'), sensor_contract)):
            raise ValueError('sensor internal pattern contract differs from its exact factory')
    elif 'SensorOutputContract' in manifest or 'SensorOutputContract' in prepared:
        raise ValueError('natural variants cannot carry the internal-test-pattern contract')
    if variant.eye == 'CAM1':
        if (manifest.get('CameraID') != variant.camera_id_tag or manifest.get('ConnectorSlot') != variant.connector_slot
                or prepared.get('camera_id') != variant.camera_id_tag
                or prepared.get('connector_slot_tag') != variant.connector_slot
                or manifest.get('ReferenceSHA256') != prepared.get('ReferenceSHA256')):
            raise ValueError('CAM1 model-independent electrical identity/reference differs')
        for name, digest in prepared['ReferenceSHA256'].items():
            if hw.sha(_fixed(ROOT, name)) != str(digest).lower():
                raise ValueError('CAM1 electrical pin reference changed')
    sources = manifest.get('SourceSHA256')
    expected = prepared.get('SourceSHA256')
    if (not isinstance(sources, dict) or not sources or not isinstance(expected, dict)
            or set(sources) != set(expected) or set(prepared.get('source_files', [])) != set(expected)
            or any(str(sources[n]).lower() != str(h).lower() for n, h in expected.items())):
        raise ValueError('guarded source closure differs from the prepared candidate')
    for name, expected_sha in sources.items():
        if hw.sha(_fixed(ROOT, name)) != str(expected_sha).lower():
            raise ValueError('guarded source changed: '+name)
    pins_path = _fixed(ROOT, 'board/'+variant.target+'-pins.json')
    pins = capture.load_json(pins_path)
    reference = capture.load_json(_fixed(ROOT, 'board/raw_camera_capture_cam2_ref-pins.json'))
    other_reset_pad = reference.get('cam_rst_n')
    if variant.eye == 'CAM1':
        camera_pins = {n: p for n, p in capture.load_json(_fixed(ROOT, 'board/camera_sync-pins.json')).items()
                       if n.startswith('cam_')}
        if len(camera_pins) != 14 or camera_pins.get('cam_data[5]') != 'Y21':
            raise ValueError('CAM1 needs its explicit fourteen-pad Y21 reference')
        reference.update(camera_pins)
    wanted = {**reference, 'uart_rxd': 'B24'}
    if reset_contract is not None:
        reset_reference = capture.load_json(_fixed(ROOT, 'board/raw_camera_capture_cam2_guarded-pins.json'))
        if other_reset_pad != 'Y20' or reset_reference.get('cam_rst_n') != other_reset_pad:
            raise ValueError('isolated CAM2 reset pad must match both validated CAM2 Y20 references')
        wanted['cam2_hold_rst_n'] = other_reset_pad
    expected_pin_count = 130 if reset_contract is not None else 129
    if pins != wanted or len(pins) != len(set(pins.values())) or len(pins) != expected_pin_count:
        raise ValueError('guarded pins must be the exact selected electrical-eye reference plus UART RX B24')
    if str(pins_path.relative_to(ROOT)).replace('\\', '/') not in {str(n).replace('\\', '/') for n in sources}:
        raise ValueError('guarded pin JSON is not hash-bound in the source closure')
    report = _fixed(base, 'place_route/'+variant.target+'_prr.prt')
    if _routed_pins(report) != wanted:
        raise ValueError('all actual routed guarded ports must match the fixed pin map')
    if reset_contract is not None:
        rows = [line.split('|') for line in report.read_text(encoding='utf-8', errors='replace').splitlines()]
        rows = [row for row in rows if len(row) >= 7 and row[4] == 'cam2_hold_rst_n']
        if len(rows) != 1 or rows[0][0] != 'Y20' or rows[0][5:7] != ['inout', 'YES']:
            raise ValueError('isolated Y20 must be an active routed inout, never a high-driving output')
    timing = _fixed(base, 'place_route/'+variant.target+'_timing_summary_after_hold_fix.txt')
    if (Path(manifest.get('TimingReport', '')).resolve() != timing
            or hw.sha(timing) != str(manifest.get('TimingSHA256', '')).lower()
            or not re.search(r'(?m)^\s*(?:Design Summary\s*:\s*)?All Constraints Met\.\s*$',
                             timing.read_text(encoding='utf-8', errors='replace'))):
        raise ValueError('hash-bound final after-hold timing must meet all constraints')
    declared_pin = manifest.get('PinReport', manifest.get('RoutedPinReport', ''))
    declared_pin_sha = manifest.get('PinReportSHA256', manifest.get('RoutedPinSHA256', ''))
    if Path(declared_pin).resolve() != report or str(declared_pin_sha).lower() != hw.sha(report):
        raise ValueError('routed pin report is not hash-bound')
    bit = _fixed(base, 'generate_bitstream/'+variant.target+'.sbit')
    if Path(manifest.get('Bitstream', '')).resolve() != bit or hw.sha(bit) != str(manifest.get('SHA256', '')).lower():
        raise ValueError('fixed guarded bitstream path/SHA differs')
    result = {'target': variant.target, 'variant': asdict(variant),
            'build_dir': str(base), 'manifest_path': str(manifest_path),
            'manifest_sha256': hw.sha(manifest_path), 'bitstream_path': str(bit),
            'bitstream_sha256': hw.sha(bit), 'pinout_path': str(pins_path),
            'pinout_sha256': hw.sha(pins_path), 'timing_report_path': str(timing),
            'timing_sha256': hw.sha(timing), 'pin_report_sha256': hw.sha(report),
            'source_sha256': dict(sources), 'prepared_source_manifest_sha256': hw.sha(prepared_path),
            'guarded_control_contract': contract, 'raw_capture_contract': RAW_CONTRACT}
    if sensor_contract is not None:
        result['sensor_output_contract'] = sensor_contract
    if trial_contract is not None:
        result['sccb_trial_contract'] = trial_contract
    if reset_contract is not None:
        result['other_sensor_reset_trial_contract'] = reset_contract
    return result


def _derive_binding(review_path, build):
    variant = variant_for(build['target'])
    path = Path(review_path).resolve()
    binding = copy.deepcopy(capture.load_json(path))
    identity = capture.validate_binding(binding)
    if identity['eye'] != variant.eye or binding['image_size'] != [640, 480]:
        raise ValueError('the engineering binding must explicitly select the requested electrical eye and VGA mode')
    review = binding.get('connection_review', {})
    if any(review.get(key) is not True for key in capture.CONNECTION_FIELDS[:-1]):
        raise ValueError('new-module pinout/electrical/selected-eye engineering reviews are required')
    basis = binding.get('connection_review_basis', {})
    record = basis.get('review_record')
    if not isinstance(record, dict):
        raise ValueError('connection review needs its explicit document/visual/operator evidence record')
    capture._bound_file(record, 'connection_review_basis', path.parent)
    binding['connection_review']['programmed_bound_bitstream'] = False
    binding['capture_mode_id'] = variant.capture_mode_id
    binding['guarded_variant'] = asdict(variant)
    trial_contract = _expected_sccb_trial_contract(variant)
    if trial_contract is not None:
        binding['sccb_trial_contract'] = copy.deepcopy(build['sccb_trial_contract'])
    elif 'sccb_trial_contract' in binding:
        raise ValueError('a diagnostic binding cannot be silently reused as an ordinary camera binding')
    reset_contract = _expected_other_sensor_reset_contract(variant)
    if reset_contract is not None:
        binding['other_sensor_reset_trial_contract'] = copy.deepcopy(build['other_sensor_reset_trial_contract'])
    elif 'other_sensor_reset_trial_contract' in binding:
        raise ValueError('an isolated reset binding cannot be silently reused as an ordinary camera binding')
    if variant.mode == 'sensor-internal-bars':
        binding['profile_id'] = 'ov5640-cam2-internal-bars-uncalibrated'
        binding.update(_mode_metadata(variant, build['sensor_output_contract']))
    elif 'sensor_output_contract' in binding or binding.get('input_origin') == 'ov5640_internal_pre_isp_test_pattern':
        raise ValueError('an internal-pattern binding cannot be reused as a natural-camera binding')
    binding['build_binding'] = {
        'validated_build': {'path': build['manifest_path'], 'sha256': build['manifest_sha256']},
        'bitstream': {'path': build['bitstream_path'], 'sha256': build['bitstream_sha256']},
        'pinout': {'path': build['pinout_path'], 'sha256': build['pinout_sha256']},
        'timing_report': {'path': build['timing_report_path'], 'sha256': build['timing_sha256']}}
    binding['guarded_control_contract'] = build['guarded_control_contract']
    binding['derived_review_binding'] = {'path': str(path), 'sha256': hw.sha(path)}
    binding.pop('programming_receipt', None)
    binding['notes'] = ('Fresh '+variant.mode+' preprogram binding. Arrival camera/lens IDs are operator labels, '
                        'the profile remains uncalibrated, physical left/right is unknown. '
                        'Programming is not yet observed; a new successful receipt is required.')
    capture.validate_live_binding(binding, base_dir=path.parent, require_programmed=False)
    return binding


def _validate_mode_binding(binding, variant, sensor_contract=None):
    if (binding.get('eye') != variant.eye or binding.get('capture_mode_id') != variant.capture_mode_id
            or binding.get('guarded_variant') != asdict(variant)
            or not _same_contract(binding.get('guarded_control_contract'),
                                  {**protocol().GUARDED_CONTROL_CONTRACT, 'build_tag': variant.build_tag})):
        raise ValueError('binding target/eye/mode/tag does not match the sealed variant')
    trial_contract = _expected_sccb_trial_contract(variant)
    if trial_contract is not None:
        if not _same_contract(binding.get('sccb_trial_contract'), trial_contract):
            raise ValueError('binding SCCB25 diagnostic contract differs from its selected target')
    elif 'sccb_trial_contract' in binding:
        raise ValueError('ordinary camera binding cannot carry an SCCB25 diagnostic contract')
    reset_contract = _expected_other_sensor_reset_contract(variant)
    if reset_contract is not None:
        if not _same_contract(binding.get('other_sensor_reset_trial_contract'), reset_contract):
            raise ValueError('binding isolated reset diagnostic contract differs from selected target')
    elif 'other_sensor_reset_trial_contract' in binding:
        raise ValueError('ordinary camera binding cannot carry an isolated reset diagnostic contract')
    if variant.mode == 'sensor-internal-bars':
        if (binding.get('input_origin') != 'ov5640_internal_pre_isp_test_pattern'
                or binding.get('calibration_scene_eligible') is not False
                or not _same_contract(binding.get('sensor_output_contract'), sensor_contract)
                or 'uncalibrated' not in binding.get('profile_id', '')):
            raise ValueError('internal bars must keep their exact sensor contract and exclude calibration')
    elif 'sensor_output_contract' in binding or binding.get('input_origin') == 'ov5640_internal_pre_isp_test_pattern':
        raise ValueError('natural camera binding cannot masquerade as internal bars')


def _mode_metadata(variant, sensor_contract=None):
    result = {'guarded_target': variant.target, 'guarded_build_tag': variant.build_tag,
              'guarded_mode': variant.mode, 'guarded_variant': asdict(variant)}
    trial_contract = _expected_sccb_trial_contract(variant)
    if trial_contract is not None:
        result['sccb_trial_contract'] = trial_contract
    reset_contract = _expected_other_sensor_reset_contract(variant)
    if reset_contract is not None:
        result['other_sensor_reset_trial_contract'] = reset_contract
    if variant.mode == 'sensor-internal-bars':
        if sensor_contract is None:
            raise ValueError('internal-pattern mode requires its validated factory sensor contract')
        result.update(input_origin='ov5640_internal_pre_isp_test_pattern',
                      sensor_output_contract=copy.deepcopy(sensor_contract),
                      calibration_scene_eligible=False, lens_optical_acceptance_eligible=False)
    return result


def _expected_sensor_contract(variant):
    if variant.mode == 'sensor-internal-bars':
        import prepare_guarded_colorbars
        return copy.deepcopy(prepare_guarded_colorbars.SENSOR_OUTPUT_CONTRACT)
    return None


def _expected_sccb_trial_contract(variant):
    if variant.factory == 'prepare_guarded_cam1_sccb25':
        import prepare_guarded_cam1_sccb25
        return copy.deepcopy(prepare_guarded_cam1_sccb25.SCCB_TRIAL_CONTRACT)
    return None


def _expected_other_sensor_reset_contract(variant):
    if variant.factory == 'prepare_guarded_cam1_isolated':
        import prepare_guarded_cam1_isolated
        return copy.deepcopy(prepare_guarded_cam1_isolated.OTHER_SENSOR_RESET_TRIAL_CONTRACT)
    return None


def _reported_source_kind(source_kind, variant):
    if source_kind == 'physical_native_camera' and variant.mode == 'sensor-internal-bars':
        return 'physical_sensor_internal_test_pattern'
    return source_kind


def _save_guarded_frame(frame, binding, work, session_id, *, variant, source_kind, build_record):
    """Enrich only metadata just created by the frozen shared receiver.

    save_frame rejects existing names first. Verify its fresh SHA before local
    enrichment; never change raw/PNG bytes or revisit sealed historical files.
    """
    descriptor = capture.save_frame(frame, binding, work, session_id,
        source_kind=source_kind, build_record=build_record,
        replay_record={'kind': 'guarded_stream_replay_not_new_hardware'} if source_kind == 'offline_uart_replay' else None)
    path = Path(descriptor['metadata_path'])
    if path.parent.resolve() != Path(work).resolve() or hw.sha(path) != descriptor['metadata_sha256']:
        raise ValueError('new metadata changed before variant enrichment')
    metadata = capture.load_json(path)
    metadata.update(_mode_metadata(variant, _expected_sensor_contract(variant)))
    metadata['source_kind'] = _reported_source_kind(source_kind, variant)
    if variant.mode == 'sensor-internal-bars':
        metadata['limits'] += (' This frame is sensor-internal PRE ISP test-pattern output. '
                               'It is ineligible for natural-scene, lens/optical, illumination or calibration acceptance.')
    with path.open('w', encoding='utf-8') as stream:
        stream.write(json.dumps(metadata, indent=2, ensure_ascii=False, allow_nan=False)+'\n')
    return {'metadata_path': str(path), 'metadata_sha256': hw.sha(path), **metadata}


def validate_program_binding(binding_path, build_dir, *, target=TARGET):
    variant = variant_for(target)
    path = Path(binding_path).resolve()
    binding = capture.load_json(path)
    build = validate_guarded_build(build_dir, target=variant.target)
    capture.validate_live_binding(binding, base_dir=path.parent, require_programmed=False)
    capture._bound_file(binding.get('derived_review_binding'), 'original_operator_review_binding', path.parent)
    capture._bound_file(binding.get('connection_review_basis', {}).get('review_record'),
                        'connection_review_record', path.parent)
    _validate_mode_binding(binding, variant, build.get('sensor_output_contract'))
    if (not _same_contract(binding.get('guarded_control_contract'), build['guarded_control_contract'])
            or Path(binding['build_binding']['validated_build']['path']).resolve() != Path(build['manifest_path'])):
        raise ValueError('fresh guarded binding differs from the selected guarded build')
    return {'binding_path': str(path), 'binding_file_sha256': hw.sha(path),
            'binding': binding, 'build': build, 'bitstream_path': build['bitstream_path'],
            'helper_source_sha256': _helpers(variant.target)}


def _check_tcl(plan, provider):
    work = Path(plan['workdir']).resolve()
    if not work.is_dir() or (work/'receipt.json').exists():
        raise ValueError('a fresh program plan is required')
    for stage, text in provider(plan['validation'], plan['frequency']).items():
        record = plan['tcl'][stage]
        path = Path(record['path']).resolve()
        if path != work/(stage+'.tcl') or path.read_text(encoding='utf-8') != text or hw.sha(path) != record['sha256']:
            raise ValueError('program Tcl differs from the exact sealed SRAM-only plan')
    hw.resolve_pds_bin(plan['pds_bin'])


def prepare_plan(review_binding, build_dir, workdir, *, port, scenario='capture', frames=1,
                 seconds=45., lease_ms=12000, frequency='1MHz', pds_bin=None, target=TARGET):
    variant = variant_for(target)
    if scenario == 'negative-commands' and variant.target != TARGET:
        raise ValueError('fixed negative commands are permitted only for natural CAM2')
    _limits(port, scenario, frames, seconds, lease_ms, frequency)
    base = Path(workdir).resolve()
    if not base.is_dir() or not base.is_relative_to(hw.APPROVED.resolve()):
        raise ValueError('use an existing approved offline scratch directory')
    build = validate_guarded_build(build_dir, target=variant.target)
    binding = _derive_binding(review_binding, build)
    idle.validate_heartbeat()
    pds = hw.resolve_pds_bin(pds_bin)
    run = base/('guarded-native-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'-'+uuid.uuid4().hex[:8])
    run.mkdir(exist_ok=False)
    binding_path = run/'preprogram-binding.json'
    hw._new_json(binding_path, binding)
    validation = validate_program_binding(binding_path, build_dir, target=variant.target)
    program_work = run/'guarded-program'
    program_work.mkdir()
    program = {'schema': 1, 'target': variant.target, 'variant': asdict(variant), 'operation': 'volatile_sram_only',
               'executed': False, 'hardware_accessed': False, 'requires_explicit_execute_flag': True,
               'workdir': str(program_work), 'pds_bin': str(pds), 'frequency': frequency,
               'validation': validation, 'tcl': {}}
    for stage, text in hw._scripts(validation, frequency).items():
        path = program_work/(stage+'.tcl')
        with path.open('x', encoding='utf-8') as stream:
            stream.write(text)
        program['tcl'][stage] = {'path': str(path), 'sha256': hw.sha(path)}
    hw._new_json(program_work/'plan.json', program)
    exit_plan = idle.prepare_plan(run, pds_bin=pds, frequency=frequency)
    _check_tcl(program, hw._scripts)
    _check_tcl(exit_plan, idle._scripts)
    plan = {'schema': 1, 'operation': 'bounded_guarded_native_then_heartbeat',
            'target': variant.target, 'variant': asdict(variant),
            'executed': False, 'hardware_accessed': False, 'workdir': str(run),
            'requires_explicit_execute_flag': True,
            'port': port, 'baud': 921600, 'scenario': scenario, 'frames': frames,
            'seconds': seconds, 'lease_ms': lease_ms, 'frequency': frequency,
            'host_session': secrets.randbelow(0xffffffff)+1,
            'program_plan': program, 'idle_plan': exit_plan, 'source_sha256': _helpers(variant.target),
            'limits': 'Default plan only. At most three frames and one bounded grant; duplicate grant is byte-identical and must not renew its lease. Physical eye/calibration/optical quality are not certified.'}
    hw._new_json(run/'plan.json', plan)
    return plan


def execute_program(plan):
    """Only the named guarded SRAM; reuse owned-server primitives, not old target authorization."""
    work = Path(plan['workdir']).resolve()
    variant = variant_for(plan.get('target'))
    if (plan.get('variant') != asdict(variant) or plan.get('operation') != 'volatile_sram_only'
            or plan.get('frequency') not in ('1MHz', '5MHz', '10MHz')
            or not work.is_relative_to(hw.APPROVED.resolve()) or not work.is_dir()):
        raise ValueError('a fresh fixed guarded SRAM plan inside approved scratch is required')
    result = {'schema': 1, 'target': variant.target, 'variant': asdict(variant), 'operation': 'volatile_sram_only',
              'executed': True, 'hardware_accessed': False, 'programming_attempted': False,
              'done_confirmed': False, 'passed': False, 'workdir': str(work)}
    owned = []
    try:
        current = validate_program_binding(plan['validation']['binding_path'], plan['validation']['build']['build_dir'], target=variant.target)
        if current != plan['validation']:
            raise ValueError('guarded binding/build/helper changed after planning')
        _check_tcl(plan, hw._scripts)
        if hw.listening_pids(hw.PORT):
            raise RuntimeError('JTAG listener is occupied; no foreign server is used or stopped')
        pds = hw.resolve_pds_bin(plan['pds_bin'])
        server = hw._start_owned([str(pds/'cdt_js.exe'), '-port', str(hw.PORT), '-work_dir', str(work)], work, owned, 'server')
        result['hardware_accessed'] = True
        hw._await_owned_server(server)
        hw._owned_server_check(server)
        hw._check_scan(hw._client(plan, 'scan', owned, 90.))
        if validate_program_binding(current['binding_path'], current['build']['build_dir'], target=variant.target) != current:
            raise ValueError('guarded bound files changed before programming')
        prior = server
        server = hw._program_server_after_scan(server, plan, owned)
        result['server_restarted_after_scan'] = server is not prior
        result['programming_attempted'] = True
        hw._check_program(hw._client(plan, 'program', owned, 90.))
        if validate_program_binding(current['binding_path'], current['build']['build_dir'], target=variant.target) != current:
            raise ValueError('guarded bound files changed during programming')
        result['passed'] = result['done_confirmed'] = True
        result['bitstream_sha256'] = current['build']['bitstream_sha256']
    except Exception as error:
        result['error'] = str(error)
    finally:
        result['owned_pids'] = [p.pid for p in owned]
        result['terminated_owned_pids'], result['cleanup_errors'] = hw._stop_owned(owned)
        if result['cleanup_errors']:
            result['passed'] = False
        result['logs'] = {str(p): hw.sha(p) for p in work.glob('*.log') if p.is_file()}
        result['checked_at_utc'] = datetime.now(timezone.utc).isoformat()
        hw._new_json(work/'receipt.json', result)
    if result['passed']:
        binding = copy.deepcopy(current['binding'])
        binding['connection_review']['programmed_bound_bitstream'] = True
        binding['notes'] = variant.mode+' SRAM programming confirmed for this receipt only; later configuration is not continuously observed. Operator identity/eye labels and uncalibrated profile remain declarations.'
        binding['programming_receipt'] = {'path': str(work/'receipt.json'), 'sha256': hw.sha(work/'receipt.json'),
                                        'scope': 'this cfg_program success plus fresh post-program DONE only'}
        hw._new_json(work/'session-binding.json', binding)
        result['session_binding_path'] = str(work/'session-binding.json')
        result['session_binding_sha256'] = hw.sha(work/'session-binding.json')
    return result


def healthy_status(status):
    """Conservative host pre-GRANT check; the live RTL interlock is independent."""
    flags = status['flags']
    required = ('camera_ready', 'ddr_ready', 'warmup_ready', 'safety_ok', 'temp_valid')
    forbidden = ('raw_failed', 'requires_reset', 'temp_failed', 'temp_over_temp', 'temp_stale', 'camera_failed')
    code = status['temperature_code']
    celsius = code*.1219-273.15
    return (all(flags[k] for k in required) and not any(flags[k] for k in forbidden)
            and status['camera_error'] == status['raw_fault'] == status['adc_fault'] == status['adc_alarm'] == 0
            and status['sensor_id'] == 0x5640 and 0 < code <= 4095
            and status['temperature_raw'] >> 4 == code
            and status['temperature_age_27mhz'] < 54000000
            and status['safety_snapshot_age_core'] < 125000000
            and 0 < status['temperature_samples'] <= status['temperature_conversions']-2
            and -40 <= celsius < 60)


def _idle_status(status):
    return (status['flags']['core_idle'] and not any(status['flags'][k] for k in
            ('armed', 'inflight', 'bank_locked', 'draining', 'raw_failed', 'requires_reset')))


def _frame_header_pending(parser):
    # Inspect only the current packet boundary; never scan a pixel payload.
    import struct
    import zlib
    data = parser.buffer
    if len(data) < 32 or data[:8] != b'PGFRAME1':
        return False
    _, width, height, _, count, _, fmt, crc = struct.unpack_from('<8sHHIIIII', data)
    return (width == 640 and height == 480 and count == 614400 and fmt == 0x5651
            and zlib.crc32(data[:28]) == crc)


def _negative_script(session, baseline):
    """Fixed zero-legal-GRANT probes, each followed by an independent QUERY.

    No CLI payload, opcode, sequence or argument override is exposed. Every
    expected tuple/counter is derived from the successful OPEN1/QUERY2 state.
    """
    import struct
    gp = protocol()
    if baseline['last_received_seq'] != 2 or baseline['last_accepted_seq'] != 2:
        raise ValueError('negative commands require this fresh OPEN1/QUERY2 session')
    bad_crc = bytearray(gp.encode_query(3, session))
    bad_crc[-1] ^= 1
    bad_version = bytearray(gp.encode_query(4, session))
    bad_version[2] = 1
    bad_version[14:] = struct.pack('<H', gp.crc16_ccitt_false(bad_version[2:14]))
    # name, packet, result, consumed seq, accepted seq, echoed opcode,
    # accepted/rejected/RX-error increments relative to the initial QUERY.
    recipes = [
        ('bad-crc', bytes(bad_crc), gp.Result.BAD_CRC, 2, 2, gp.Opcode.QUERY, 0, 0, 1),
        ('query-after-bad-crc', gp.encode_query(3, session), gp.Result.ACCEPTED, 3, 3, gp.Opcode.QUERY, 1, 0, 1),
        ('bad-version-valid-crc', bytes(bad_version), gp.Result.BAD_VERSION, 3, 3, gp.Opcode.QUERY, 1, 0, 2),
        ('query-after-bad-version', gp.encode_query(4, session), gp.Result.ACCEPTED, 4, 4, gp.Opcode.QUERY, 2, 0, 2),
        ('grant-zero-frames', gp.encode_command(gp.Opcode.GRANT, 5, session, 1000 << 8), gp.Result.BAD_ARG, 5, 4, gp.Opcode.GRANT, 2, 1, 2),
        ('query-after-zero-frames', gp.encode_query(6, session), gp.Result.ACCEPTED, 6, 6, gp.Opcode.QUERY, 3, 1, 2),
        ('grant-four-frames', gp.encode_command(gp.Opcode.GRANT, 7, session, (1000 << 8) | 4), gp.Result.BAD_ARG, 7, 6, gp.Opcode.GRANT, 3, 2, 2),
        ('query-after-four-frames', gp.encode_query(8, session), gp.Result.ACCEPTED, 8, 8, gp.Opcode.QUERY, 4, 2, 2),
        ('same-sequence-conflict', gp.encode_stop(8, session), gp.Result.SEQ_CONFLICT, 8, 8, gp.Opcode.STOP, 4, 3, 2),
        ('query-after-conflict', gp.encode_query(9, session), gp.Result.ACCEPTED, 9, 9, gp.Opcode.QUERY, 5, 3, 2),
        ('old-sequence', gp.encode_query(8, session), gp.Result.OLD_SEQ, 9, 9, gp.Opcode.QUERY, 5, 4, 2),
        ('query-after-old-sequence', gp.encode_query(10, session), gp.Result.ACCEPTED, 10, 10, gp.Opcode.QUERY, 6, 4, 2),
    ]
    result = []
    for name, packet, code, seen, accepted_seq, opcode, accepts, rejects, errors in recipes:
        result.append({'name': name, 'wire': packet,
            'expected': {'session_id': session, 'last_received_seq': seen,
                'last_accepted_seq': accepted_seq, 'last_opcode': int(opcode), 'last_result': int(code),
                'accepted_commands': baseline['accepted_commands']+accepts,
                'rejected_commands': baseline['rejected_commands']+rejects,
                'duplicate_commands': baseline['duplicate_commands'],
                'rx_errors': baseline['rx_errors']+errors}})
    return result


def run_uart(io, plan, binding, work, *, build_record=None, source_kind='offline_uart_replay',
             clock=time.monotonic):
    """Finite controller, dependency-injected for mock/replay; never opens COM."""
    gp = protocol()
    variant = variant_for(plan.get('target', TARGET))
    if plan['scenario'] == 'negative-commands' and variant.target != TARGET:
        raise ValueError('fixed negative commands are permitted only for natural CAM2')
    if ('variant' in plan and plan['variant'] != asdict(variant)) or (variant.target != TARGET and plan.get('variant') != asdict(variant)):
        raise ValueError('UART plan variant differs from the explicit target')
    parser = gp.GuardedStreamParser(expected_build_tag=variant.build_tag)
    work = Path(work)
    if not work.is_dir():
        raise ValueError('UART output directory must already exist')
    _limits(plan['port'], plan['scenario'], plan['frames'], plan['seconds'], plan['lease_ms'], plan['frequency'])
    if source_kind not in ('physical_native_camera', 'offline_uart_replay'):
        raise ValueError('live/replay source kind must be explicit')
    if source_kind == 'physical_native_camera' and not build_record:
        raise ValueError('physical data requires its programmed source-bound build record')
    if source_kind == 'physical_native_camera' or variant.target != TARGET or 'guarded_variant' in binding:
        _validate_mode_binding(binding, variant, _expected_sensor_contract(variant))
    elif binding.get('eye') != variant.eye:
        raise ValueError('replay binding eye differs from selected variant')
    session = plan['host_session']
    if type(session) is not int or not 1 <= session <= 0xffffffff:
        raise ValueError('host session must be a fresh nonzero uint32')
    started = clock()
    deadline = started+plan['seconds']
    statuses, frames, commands, headers = [], [], [], []
    phase = 'boot'
    pending = None
    last = None
    seq = 0
    grant_packet = None
    grant_ack = None
    # Every invocation freshly programs/reset-boots and sends at most one legal GRANT.
    # completed_frames is nevertheless global; admitted_frames is per GRANT.
    completed_baseline = 0
    duplicate_ack = stop_ack = False
    flood = []
    flood_next = None
    quiet = []
    emergency = None
    leading_discard = 0
    observed_first = False
    header_for_current = False
    negative_steps, negative_verified = [], []
    negative_index, negative_pending = 0, None
    rxpath, txpath, statuspath = work/'received-wire.bin', work/'tx-commands.jsonl', work/'status-events.jsonl'

    def stamp():
        return {'host_elapsed_seconds': clock()-started, 'host_utc': datetime.now(timezone.utc).isoformat()}

    def send(opcode, arg=0, *, duplicate=False, wait_ack=True):
        nonlocal seq, pending
        if duplicate:
            packet = grant_packet
            decoded = gp.decode_command(packet)
        else:
            seq = (seq+1) & 0xffff
            packet = gp.encode_command(opcode, seq, session, arg)
            decoded = gp.decode_command(packet)
        baseline = {key: last[key] for key in ('accepted_commands', 'rejected_commands', 'duplicate_commands', 'rx_errors')}
        if opcode == gp.Opcode.STOP and flood and grant_ack is not None:
            # QUERY replies may coalesce behind a whole raw packet. A STOP ACK
            # must account for every written QUERY, not only an older snapshot.
            baseline = {key: grant_ack[key] for key in baseline}
            baseline['accepted_commands'] += len(flood)
        record = {**stamp(), **decoded, 'wire_hex': packet.hex(), 'duplicate_retransmission': duplicate,
                  'execution_acknowledged': False}
        commands.append(record)
        txlog.write(json.dumps(record, allow_nan=False)+'\n')
        txlog.flush()
        if io.write(packet) != len(packet):
            raise RuntimeError('UART write was incomplete; no execution is inferred')
        io.flush()
        if wait_ack:
            pending = {'command': record, 'baseline': baseline,
                       'result': gp.Result.DUPLICATE if duplicate else gp.Result.ACCEPTED}
        return packet, record

    def ack_matches(status):
        if pending is None:
            return False
        command = pending['command']
        if status['session_id'] != session or status['last_received_seq'] != command['seq']:
            return False
        if status['last_opcode'] != command['opcode'] or status['last_result'] != int(pending['result']):
            raise RuntimeError('command was rejected or ACK tuple differs')
        base = pending['baseline']
        duplicate = pending['result'] == gp.Result.DUPLICATE
        if (status['last_accepted_seq'] != command['seq']
                or status['accepted_commands'] != base['accepted_commands']+(0 if duplicate else 1)
                or status['duplicate_commands'] != base['duplicate_commands']+(1 if duplicate else 0)
                or status['rejected_commands'] != base['rejected_commands']
                or status['rx_errors'] != base['rx_errors']):
            raise RuntimeError('ACK is not supported by exact hardware execution counters')
        command['execution_acknowledged'] = True
        command['ack_snapshot_seq'] = status['snapshot_seq']
        return True

    def send_negative(step):
        import struct
        nonlocal negative_pending
        packet = step['wire']
        version, opcode, packet_seq, packet_session, arg = struct.unpack_from('<BBHII', packet, 2)
        record = {**stamp(), 'version': version, 'opcode': opcode, 'seq': packet_seq,
            'session': packet_session, 'arg': arg, 'requested_frames': arg & 255, 'lease_ms': arg >> 8,
            'wire_hex': packet.hex(), 'intentional_negative_case': step['name'],
            'expected_response': step['expected'], 'response_verified': False,
            'execution_acknowledged': False}
        commands.append(record)
        txlog.write(json.dumps(record, allow_nan=False)+'\n')
        txlog.flush()
        if io.write(packet) != 16:
            raise RuntimeError('negative-probe UART write was incomplete')
        io.flush()
        keys = tuple(step['expected'])
        negative_pending = {'step': step, 'record': record, 'before': {key: last[key] for key in keys}}

    def verify_negative(status):
        nonlocal negative_pending, negative_index, phase
        if negative_pending is None:
            return
        expected = negative_pending['step']['expected']
        if all(status[key] == value for key, value in expected.items()):
            record = negative_pending['record']
            record['response_verified'] = True
            record['ack_snapshot_seq'] = status['snapshot_seq']
            record['execution_acknowledged'] = expected['last_result'] == int(gp.Result.ACCEPTED)
            record['expected_rejection_or_RX_error_verified'] = not record['execution_acknowledged']
            negative_verified.append({'case': negative_pending['step']['name'],
                'snapshot_seq': status['snapshot_seq'], 'expected_and_observed': dict(expected)})
            negative_index += 1
            negative_pending = None
            if negative_index < len(negative_steps):
                send_negative(negative_steps[negative_index])
            else:
                phase = 'negative-complete'
        elif any(status[key] != value for key, value in negative_pending['before'].items()):
            raise RuntimeError('negative command changed sequence/result/counters differently from the fixed expected rejection')

    def completed(status):
        scenario = plan['scenario']
        if scenario == 'boot-idle':
            return (len(statuses) >= 3 and not commands and not frames
                    and _idle_status(status) and healthy_status(status))
        if scenario == 'idle':
            return phase == 'observe-idle' and not frames and _idle_status(status) and healthy_status(status)
        if scenario == 'negative-commands':
            return (phase == 'negative-complete' and len(negative_verified) == 12 and not frames
                and _idle_status(status) and healthy_status(status)
                and all(status[key] == value for key, value in negative_steps[-1]['expected'].items())
                and all(status[key] == 0 for key in ('admitted_frames', 'completed_frames', 'remaining_frames', 'remaining_cycles', 'stop_reason')))
        if (grant_ack is None or pending is not None or not _idle_status(status)
                or not healthy_status(status)):
            return False
        if (status['admitted_frames'] != len(frames)
                or status['completed_frames']-completed_baseline != len(frames)):
            return False
        if scenario in ('capture', 'duplicate-grant'):
            return (len(frames) == plan['frames'] and status['remaining_frames'] == 0
                    and status['stop_reason'] == int(gp.StopReason.FRAME_BUDGET)
                    and (scenario != 'duplicate-grant' or duplicate_ack))
        if scenario in ('lease-expiry', 'host-silence'):
            if not (len(frames) == 1 < plan['frames'] and status['remaining_cycles'] == 0
                    and status['stop_reason'] == int(gp.StopReason.LEASE_EXPIRED)):
                return False
            return scenario == 'host-silence' or (len(flood) >= 4 and flood[-1].get('execution_acknowledged'))
        return (scenario == 'stop-drain' and stop_ack and len(frames) == 1
                and status['stop_reason'] == int(gp.StopReason.OPERATOR_STOP))

    with rxpath.open('xb') as rx, txpath.open('x', encoding='utf-8') as txlog, statuspath.open('x', encoding='utf-8') as statuslog:
        while clock() < deadline:
            chunk = io.read(8192)
            if chunk:
                rx.write(chunk)
                events = parser.feed(chunk)
                if parser.rejected:
                    raise RuntimeError('mixed status/frame CRC or framing failure')
                if not observed_first:
                    leading_discard = parser.discarded
                    if leading_discard > 127:
                        raise RuntimeError('boot stream has more than one partial status boundary')
                elif parser.discarded != leading_discard:
                    raise RuntimeError('unrelated/corrupt bytes inside the guarded stream')
                for event in events:
                    observed_first = True
                    if event['kind'] == 'frame':
                        if grant_ack is None:
                            raise RuntimeError('raw frame appeared without an acknowledged GRANT')
                        frame = event['frame']
                        if [frame.width, frame.height] != [640, 480] or any(f['frame_id'] == frame.frame_id for f in frames):
                            raise RuntimeError('frame mode or transaction ID differs/repeats')
                        if len(frames) >= 3 or len(frames) >= plan['frames']:
                            raise RuntimeError('more frames than the explicit total host budget')
                        saved = _save_guarded_frame(frame, binding, work, 'guarded-'+str(session),
                            variant=variant, source_kind=source_kind, build_record=build_record)
                        frames.append(saved)
                        header_for_current = False
                        quiet = []
                        if len(frames) > 1 and plan['scenario'] in ('lease-expiry', 'host-silence', 'stop-drain'):
                            emergency = 'unexpected additional frame after stop/expiry test'
                        continue
                    status = event['status']
                    if status['build_tag'] != variant.build_tag:
                        raise RuntimeError('unexpected guarded runtime build tag')
                    if last is not None:
                        delta = (status['snapshot_seq']-last['snapshot_seq']) & 0xffffffff
                        if not 0 < delta < 0x80000000 or status['uptime_ms'] < last['uptime_ms']:
                            raise RuntimeError('guarded status snapshot replay/regression')
                        if (status['temperature_samples'] < last['temperature_samples']
                                or status['temperature_conversions'] < last['temperature_conversions']
                                or status['temperature_samples']-last['temperature_samples'] >
                                   status['temperature_conversions']-last['temperature_conversions']):
                            raise RuntimeError('ADC sample/conversion epochs are inconsistent')
                    if (status['completed_frames'] < completed_baseline
                            or status['completed_frames']-completed_baseline > status['admitted_frames']
                            or status['admitted_frames'] > 3):
                        raise RuntimeError('invalid hardware frame counters')
                    if grant_ack is None and (status['admitted_frames'] or status['completed_frames']) and phase not in ('grant',):
                        raise RuntimeError('boot/OPEN/QUERY admitted a frame without GRANT')
                    if plan['scenario'] == 'negative-commands' and (
                            (phase != 'boot' and not _idle_status(status))
                            or status['remaining_frames'] or status['remaining_cycles']):
                        raise RuntimeError('zero-GRANT negative probes armed/budgeted a raw transaction')
                    statuses.append({**status, **stamp()})
                    statuslog.write(json.dumps(statuses[-1], allow_nan=False)+'\n')
                    statuslog.flush()
                    previous = last
                    last = status
                    if phase == 'boot':
                        if (status['session_id'] or status['accepted_commands'] or status['rejected_commands']
                                or status['duplicate_commands'] or status['rx_errors']):
                            raise RuntimeError('freshly programmed boot has prior session/command state')
                        if plan['scenario'] != 'boot-idle':
                            ready = _idle_status(status) and not status['camera_error']
                            if plan['scenario'] != 'idle':
                                ready &= (healthy_status(status) and previous is not None and healthy_status(previous)
                                          and status['temperature_samples'] > previous['temperature_samples'])
                            if ready:
                                send(gp.Opcode.OPEN)
                                phase = 'open'
                    elif ack_matches(status):
                        command = pending['command']
                        pending = None
                        if phase == 'open':
                            send(gp.Opcode.QUERY)
                            phase = 'query'
                        elif phase == 'query':
                            if plan['scenario'] == 'negative-commands':
                                if not healthy_status(status) or not _idle_status(status):
                                    raise RuntimeError('negative-probe preflight is not healthy/idle')
                                negative_steps = _negative_script(session, status)
                                phase = 'negative'
                                send_negative(negative_steps[0])
                            elif plan['scenario'] == 'idle':
                                phase = 'observe-idle'
                            else:
                                if not healthy_status(status) or not _idle_status(status):
                                    raise RuntimeError('latest QUERY reports unsafe/stale/not-ready state; no GRANT sent')
                                completed_baseline = status['completed_frames']
                                grant_packet, _ = send(gp.Opcode.GRANT, gp.grant_argument(plan['frames'], plan['lease_ms']))
                                phase = 'grant'
                        elif phase == 'grant':
                            grant_ack = dict(status)
                            phase = 'active'
                            if plan['scenario'] == 'duplicate-grant':
                                send(gp.Opcode.GRANT, duplicate=True)
                                phase = 'duplicate'
                            elif plan['scenario'] == 'lease-expiry':
                                flood_next = clock()
                        elif phase == 'duplicate':
                            duplicate_ack = True
                            if (status['remaining_cycles'] > grant_ack['remaining_cycles']
                                    or status['remaining_frames'] > grant_ack['remaining_frames']):
                                raise RuntimeError('duplicate GRANT renewed a lease or budget')
                            phase = 'active'
                        elif phase == 'stopping':
                            stop_ack = True
                            phase = 'active'
                    if phase == 'negative':
                        verify_negative(status)
                    if flood and phase == 'active' and status['last_opcode'] == int(gp.Opcode.QUERY):
                        index = next((i for i, command in enumerate(flood) if command['seq'] == status['last_received_seq']), None)
                        if index is not None:
                            if (status['session_id'] != session or status['last_result'] != int(gp.Result.ACCEPTED)
                                    or status['last_accepted_seq'] != flood[index]['seq']
                                    or status['accepted_commands'] != grant_ack['accepted_commands']+index+1
                                    or status['rejected_commands'] != grant_ack['rejected_commands']
                                    or status['duplicate_commands'] != grant_ack['duplicate_commands']
                                    or status['rx_errors'] != grant_ack['rx_errors']
                                    or status['remaining_cycles'] > grant_ack['remaining_cycles']):
                                raise RuntimeError('coalesced QUERY ACK/counters or non-renewal evidence differs')
                            for command in flood[:index+1]:
                                command['execution_acknowledged'] = True
                    if completed(status) and emergency is None:
                        quiet.append(status)
                        if len(quiet) >= 2 and quiet[-1]['uptime_ms']-quiet[0]['uptime_ms'] >= 500:
                            if parser.buffer and (len(parser.buffer) >= 128 or not b'PGSTAT02'.startswith(bytes(parser.buffer[:8]))):
                                raise RuntimeError('unexpected incomplete packet at completion')
                            rx.flush()
                            return {'schema': 1, 'passed': True,
                                **_mode_metadata(variant, _expected_sensor_contract(variant)),
                                'target': variant.target, 'eye': variant.eye,
                                'source_kind': _reported_source_kind(source_kind, variant),
                                'scenario': plan['scenario'], 'host_session': session, 'frames': frames,
                                'saved_frames': len(frames), 'status_records': len(statuses), 'last_status': status,
                                'tx_commands': commands, 'grant_execution_acknowledged': grant_ack is not None,
                                'duplicate_execution_acknowledged': duplicate_ack, 'stop_execution_acknowledged': stop_ack,
                                'leading_partial_status_bytes': leading_discard, 'trailing_partial_status_bytes': len(parser.buffer),
                                'parser_rejected': parser.rejected, 'parser_discarded': parser.discarded,
                                'frame_headers': headers, 'wire_path': str(rxpath), 'wire_sha256': hw.sha(rxpath),
                                'negative_command_checks': negative_verified,
                                'negative_commands_scope': ['bad-crc', 'bad-version-valid-crc', 'grant-zero-frames',
                                    'grant-four-frames', 'same-sequence-conflict', 'old-sequence'] if plan['scenario'] == 'negative-commands' else None,
                                'legal_GRANT_commands_sent': 0 if plan['scenario'] == 'negative-commands' else None,
                                'tx_path': str(txpath), 'status_path': str(statuspath),
                                'host_silence_means': 'COM remained open for RX; no TX after GRANT ACK' if plan['scenario'] == 'host-silence' else None,
                                'limits': 'CRC/ACK and hash-bound role do not authenticate a sensor serial, physical eye, simultaneous exposure, optical quality or long-term thermal safety. Replay is never new physical evidence.'}
                    else:
                        quiet = []
            if last is not None and grant_ack is not None:
                header_pending = _frame_header_pending(parser)
                if header_pending and not header_for_current:
                    headers.append({**stamp(), 'after_grant_ack': True, 'index': len(frames)+1})
                    header_for_current = True
                    if plan['scenario'] == 'stop-drain' and not stop_ack and pending is None:
                        send(gp.Opcode.STOP)
                        phase = 'stopping'
                    elif len(frames) >= 1 and plan['scenario'] in ('lease-expiry', 'host-silence'):
                        emergency = 'second frame header after expiry/silence test'
                        if pending is None:
                            send(gp.Opcode.STOP)
                            phase = 'stopping'
                if (plan['scenario'] == 'lease-expiry' and phase == 'active' and flood_next is not None
                        and clock() >= flood_next and len(flood) < 16 and not frames and emergency is None):
                    _, command = send(gp.Opcode.QUERY, wait_ack=False)
                    flood.append(command)
                    flood_next = clock()+.5
                if emergency and _idle_status(last) and not _frame_header_pending(parser):
                    raise RuntimeError(emergency+'; observed drain/STOP retained as failed evidence')
        raise TimeoutError('bounded guarded scenario did not complete with required ACK/drain evidence')


def _serial(port):
    import serial
    link = serial.Serial(port=None, baudrate=921600, timeout=.05, write_timeout=1,
                         rtscts=False, dsrdtr=False)
    try:
        link.dtr = False
        link.rts = False
        link.port = port
        link.open()
    except BaseException:
        link.close()
        raise
    return link


def _validate_exit(plan):
    exit_plan = plan['idle_plan']
    if (exit_plan.get('target') != 'heartbeat' or exit_plan.get('operation') != 'volatile_sram_only'
            or exit_plan.get('frequency') != plan['frequency']
            or not Path(exit_plan['workdir']).resolve().is_relative_to(Path(plan['workdir']).resolve())
            or idle.validate_heartbeat() != exit_plan['validation']):
        raise ValueError('fixed heartbeat exit must be fresh, source-bound and inside this invocation')
    _check_tcl(exit_plan, idle._scripts)


def execute_plan(plan):
    variant = variant_for(plan.get('target', TARGET))
    if plan['scenario'] == 'negative-commands' and variant.target != TARGET:
        raise ValueError('fixed negative commands are permitted only for natural CAM2')
    work = Path(plan['workdir']).resolve()
    if (plan.get('operation') != 'bounded_guarded_native_then_heartbeat'
            or not work.is_dir() or not work.is_relative_to(hw.APPROVED.resolve())
            or (work/'result.json').exists()):
        raise ValueError('a fresh sealed guarded plan inside approved scratch is required')
    _limits(plan['port'], plan['scenario'], plan['frames'], plan['seconds'], plan['lease_ms'], plan['frequency'])
    if capture.load_json(work/'plan.json') != plan or plan['source_sha256'] != _helpers(variant.target):
        raise ValueError('guarded plan/configuration/helper sources changed after planning')
    if (plan.get('variant') != asdict(variant) or plan['program_plan'].get('target') != variant.target
            or plan['program_plan'].get('variant') != asdict(variant)
            or plan['program_plan'].get('frequency') != plan['frequency']
            or not Path(plan['program_plan']['workdir']).resolve().is_relative_to(work)):
        raise ValueError('nested guarded program frequency/workdir differs from the bounded invocation')
    _validate_exit(plan)
    current = validate_program_binding(plan['program_plan']['validation']['binding_path'],
                                       plan['program_plan']['validation']['build']['build_dir'], target=variant.target)
    if current != plan['program_plan']['validation']:
        raise ValueError('guarded build/binding changed after planning')
    _check_tcl(plan['program_plan'], hw._scripts)
    result = {'schema': 1, 'operation': plan['operation'], 'executed': True, 'passed': False,
              'target': variant.target, 'variant': asdict(variant),
              'hardware_accessed': False, 'workdir': str(work), 'guarded_program': None,
              'session_summary': None, 'idle_program': None, 'idle_restoration_attempted': False,
              'idle_done_confirmed': False, 'physical_eye_independently_verified': False,
              'optical_calibration_verified': False, 'hardware_interlock_acceptance_verified': False}
    link = None
    entered = attempted = False
    started = time.monotonic()
    try:
        entered = True
        result['guarded_program'] = execute_program(plan['program_plan'])
        active = result['guarded_program']
        if not isinstance(active, dict) or type(active.get('programming_attempted')) is not bool:
            attempted = True
            result['programming_state_unknown'] = True
            raise RuntimeError('guarded programming returned no trustworthy attempt-state receipt')
        attempted = bool(active.get('programming_attempted'))
        result['hardware_accessed'] |= bool(active.get('hardware_accessed'))
        if not active.get('passed') or not active.get('done_confirmed'):
            raise RuntimeError('guarded SRAM/DONE not confirmed; COM remains unopened')
        binding_path = Path(active['session_binding_path'])
        binding_sha = hw.sha(binding_path)
        binding = capture.load_json(binding_path)
        build_record = capture.validate_live_binding(binding, base_dir=binding_path.parent)
        link = _serial(plan['port'])
        summary = run_uart(link, plan, binding, work, build_record=build_record,
                           source_kind='physical_native_camera')
        summary['binding_file_sha256'] = binding_sha
        summary['binding_unchanged_during_session'] = hw.sha(binding_path) == binding_sha
        summary['passed'] &= summary['binding_unchanged_during_session']
        hw._new_json(work/'session-summary.json', summary)
        result['session_summary'] = {'path': str(work/'session-summary.json'),
                                     'sha256': hw.sha(work/'session-summary.json'), 'passed': summary['passed'],
                                     'saved_frames': summary['saved_frames']}
        result['session_binding_path'] = str(binding_path)
    except (Exception, KeyboardInterrupt) as error:
        result['error'] = type(error).__name__+': '+str(error)
    finally:
        if link is not None:
            try:
                link.close()
            except (Exception, KeyboardInterrupt) as error:
                result['serial_close_error'] = str(error)
        if entered and result['guarded_program'] is None:
            receipt = Path(plan['program_plan']['workdir'])/'receipt.json'
            try:
                result['guarded_program'] = capture.load_json(receipt)
            except (Exception, KeyboardInterrupt) as error:
                result['programming_state_unknown'] = True
                result['guarded_receipt_error'] = str(error)
                attempted = True
        if isinstance(result['guarded_program'], dict):
            active = result['guarded_program']
            if type(active.get('programming_attempted')) is not bool:
                attempted = True
                result['programming_state_unknown'] = True
            attempted |= bool(active.get('programming_attempted') or active.get('passed') or active.get('done_confirmed'))
            result['hardware_accessed'] |= bool(active.get('hardware_accessed'))
        if attempted:
            result['idle_restoration_attempted'] = True
            try:
                result['idle_program'] = idle.execute_plan(plan['idle_plan'], timeout_seconds=90.)
                result['hardware_accessed'] |= bool(result['idle_program'].get('hardware_accessed'))
                result['idle_done_confirmed'] = bool(result['idle_program'].get('passed')
                                                     and result['idle_program'].get('done_confirmed'))
            except (Exception, KeyboardInterrupt) as error:
                result['idle_error'] = str(error)
        for name in ('received-wire.bin', 'tx-commands.jsonl', 'status-events.jsonl'):
            path = work/name
            if path.is_file():
                result[name] = {'path': str(path), 'sha256': hw.sha(path), 'bytes': path.stat().st_size}
        result['passed'] = bool(isinstance(result['guarded_program'], dict) and result['guarded_program'].get('passed')
            and result['session_summary'] and result['session_summary']['passed']
            and result['idle_done_confirmed'] and 'error' not in result and 'serial_close_error' not in result)
        result['elapsed_seconds'] = time.monotonic()-started
        result['checked_at_utc'] = datetime.now(timezone.utc).isoformat()
        result['limits'] = ('Finite UART session <=60s; JTAG scan/program clients are individually bounded at90s, '
                            'owned-server startup at10s, followed by the independently bounded heartbeat attempt. '
                            'Host finally is not a hardware watchdog. A successful selected scenario does not certify '
                            'all interlock faults, unattended longevity, sensor serial, physical eye, stereo timing, '
                            'optics or temperature under a different later configuration.')
        hw._new_json(work/'result.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binding', type=Path, required=True, help='reviewed arrival/operator connection binding')
    parser.add_argument('--target', choices=tuple(VARIANTS), default=TARGET)
    parser.add_argument('--build-dir', type=Path, required=True)
    parser.add_argument('--workdir', type=Path, required=True)
    parser.add_argument('--port', required=True)
    parser.add_argument('--scenario', choices=SCENARIOS, default='capture')
    parser.add_argument('--frames', type=int, default=1)
    parser.add_argument('--seconds', type=float, default=45.)
    parser.add_argument('--lease-ms', type=int, default=12000)
    parser.add_argument('--frequency', choices=('1MHz', '5MHz', '10MHz'), default='1MHz')
    parser.add_argument('--pds-bin', type=Path)
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    plan = prepare_plan(args.binding, args.build_dir, args.workdir, port=args.port,
        scenario=args.scenario, frames=args.frames, seconds=args.seconds,
        lease_ms=args.lease_ms, frequency=args.frequency, pds_bin=args.pds_bin, target=args.target)
    print(json.dumps({'plan': str(Path(plan['workdir'])/'plan.json'), 'executing': args.execute}), flush=True)
    result = execute_plan(plan) if args.execute else plan
    print(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False))
    return 0 if not args.execute or result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
