"""Offline camera admission and arithmetic budgets; never programs hardware.

The current shipped chain has one 8-bit RGB565 DVP input. ``camera2`` is
an alternative single-input pin mapping, not a simultaneous stereo pipeline.
All mode calculations describe requests/assumptions, not achieved performance.
"""
import argparse
import json
import math
from pathlib import Path


ADDRESS_UNIT_BYTES = 4
ADDRESS_SPACE_UNITS = 1 << 28
CORE_HZ = 125_000_000
VERIFICATIONS = (
    'identity', 'interface', 'electrical', 'pinout', 'capture_mode',
    'synchronization', 'new_lens_calibration', 'candidate_configuration',
)


def positive_int(value, name):
    if type(value) is not int or value <= 0:
        raise ValueError(f'{name} must be a positive integer (not a boolean)')
    return value


def positive_number(value, name):
    try:
        valid = type(value) in (int, float) and math.isfinite(value) and value > 0
    except OverflowError:
        valid = False
    if not valid:
        raise ValueError(f'{name} must be a finite positive number')
    return value


def camera_count(value):
    if type(value) is not int or value not in (1, 2):
        raise ValueError('cameras must be 1 or 2')
    return value


def budget(width, height, fps, cameras=1, *, output_width=None,
           output_height=None, new_output_fps=None, display_fps=60,
           display_streams=1, bank_stride_address_units=None,
           address_unit_bytes=4, ddr_capacity_bytes=None):
    width = positive_int(width, 'width')
    height = positive_int(height, 'height')
    fps = positive_number(fps, 'fps')
    cameras = camera_count(cameras)
    if width > 16384 or height > 16384:
        raise ValueError('exploration dimensions must be at most 16384')
    ow = width if output_width is None else positive_int(output_width, 'output_width')
    oh = height if output_height is None else positive_int(output_height, 'output_height')
    if ow > 16384 or oh > 16384:
        raise ValueError('exploration dimensions must be at most 16384')
    ofps = fps if new_output_fps is None else positive_number(new_output_fps, 'new_output_fps')
    display_fps = positive_number(display_fps, 'display_fps')
    display_streams = positive_int(display_streams, 'display_streams')
    if display_streams > cameras:
        raise ValueError('display_streams cannot exceed cameras in this budget')
    if type(address_unit_bytes) is not int or address_unit_bytes != ADDRESS_UNIT_BYTES:
        raise ValueError('the current DDR address unit is exactly 4 bytes')
    if ddr_capacity_bytes is not None:
        positive_int(ddr_capacity_bytes, 'ddr_capacity_bytes')
        if ddr_capacity_bytes % ADDRESS_UNIT_BYTES:
            raise ValueError('ddr_capacity_bytes must be divisible by 4')
    input_bytes = width * height * 2
    result_bytes = ow * oh * 2
    required_bytes = max(input_bytes, result_bytes)
    suggested_stride_bytes = 1 << (max(required_bytes, 512) - 1).bit_length()
    stride = (suggested_stride_bytes // ADDRESS_UNIT_BYTES if bank_stride_address_units is None
              else positive_int(bank_stride_address_units, 'bank_stride_address_units'))
    if stride % 128:
        raise ValueError('bank_stride_address_units must be 128-unit (512-byte) aligned')
    if stride * ADDRESS_UNIT_BYTES < required_bytes:
        raise ValueError('bank stride is smaller than a source/result frame; banks would overlap')
    bank_names = ('source0', 'source1', 'result0', 'result1')
    banks = []
    for eye in range(cameras):
        for index, name in enumerate(bank_names):
            base = (eye * 4 + index) * stride
            payload_bytes = input_bytes if name.startswith('source') else result_bytes
            payload_units = (payload_bytes + 3) // 4
            banks.append({'camera_index': eye, 'role': name,
                          'base_address_units': base, 'base_bytes': base * 4,
                          'reserved_end_address_units_exclusive': base + stride,
                          'payload_end_address_units_exclusive': base + payload_units})
    reserved_units = cameras * 4 * stride
    if reserved_units > ADDRESS_SPACE_UNITS:
        raise ValueError('bank layout exceeds the current 28-bit DDR address space')
    required_storage = reserved_units * ADDRESS_UNIT_BYTES
    if ddr_capacity_bytes is not None and required_storage > ddr_capacity_bytes:
        raise ValueError('bank layout exceeds the declared physical DDR capacity')
    capture_write = cameras * input_bytes * fps
    result_write = cameras * result_bytes * ofps
    display_read = display_streams * result_bytes * display_fps
    full_source_once = cameras * input_bytes * ofps
    four_neighbour_payload = cameras * ow * oh * ofps * 4 * 2
    constraints = []
    if cameras != 1:
        constraints.append('current RTL has one DVP input; dual admission/arbitration/synchronization is absent')
    if ofps > fps:
        constraints.append('requested newly corrected FPS exceeds source FPS; unique source frames are insufficient')
    if (width, height, ow, oh) != (640, 480, 640, 480):
        constraints.append('current validated camera chain is 640x480; this mode requires new configuration and validation')
    if width != ow or height != oh:
        constraints.append('current shared WIDTH/HEIGHT chain does not independently configure source/output dimensions')
    if any(v < 8 or v > 4095 or v % 8 for v in (width, height, ow, oh)):
        constraints.append('current video-bank checks require dimensions 8..4095 and multiples of 8')
    if required_bytes % 32:
        constraints.append('full frames do not align to current 32-byte DDR beats')
    if ddr_capacity_bytes is None:
        constraints.append('physical DDR capacity is unverified')
    return {
        'kind': 'exploration_budget_only', 'hardware_accessed': False,
        'hardware_ready': False, 'assumed_format': 'RGB565, 2 bytes/pixel; 8-bit DVP',
        'input': {'width': width, 'height': height, 'fps_per_camera': fps, 'cameras': cameras},
        'output': {'width': ow, 'height': oh, 'new_fps_per_camera': ofps,
                   'display_refresh_fps': display_fps, 'display_streams': display_streams},
        'minimum_effective_dvp_byte_clock_hz_per_camera': width * height * fps * 2,
        'aggregate_effective_input_bytes_per_second': capture_write,
        'aggregate_is_not_a_shared_physical_pclk': True,
        'current_48mhz_dvp_constraint_covers_effective_minimum': width * height * fps * 2 <= 48_000_000,
        'core_hz': CORE_HZ,
        'available_core_cycles_per_output_pixel_shared_engine': CORE_HZ / (cameras * ow * oh * ofps),
        'storage': {'source_frame_bytes': input_bytes, 'result_frame_bytes': result_bytes,
                    'address_unit_bytes': 4, 'bank_stride_address_units': stride,
                    'bank_stride_bytes': stride * 4, 'banks_per_camera_assumed': 4,
                    'total_reserved_bytes': required_storage, 'declared_ddr_capacity_bytes': ddr_capacity_bytes,
                    'banks': banks, 'layout_non_overlapping': True},
        'ddr_requested_payload_bytes_per_second': {
            'capture_writes': capture_write, 'result_writes': result_write,
            'display_reads_including_repeated_frames': display_read,
            'known_stream_lower_bound_excluding_sampling_reads': capture_write + result_write + display_read,
            'sampling_full_source_once_per_processed_frame_assumption': full_source_once,
            'total_with_full_source_once_assumption': capture_write + result_write + display_read + full_source_once,
            'uncached_four_neighbour_pixel_payload_before_bursts': four_neighbour_payload,
        },
        'current_chain_constraints': constraints,
        'limits': [
            'Effective DVP clock excludes blanking; a passing minimum does not establish electrical/timing support.',
            'Four banks per camera are a storage proposal; dual-camera RTL and ownership are not implemented.',
            'Known stream lower bound assumes requested capture/result/display transfers; mapping sampling reads are additional.',
            'Reading each full source exactly once assumes full-source coverage and perfect reuse; this is a scenario, not a universal lower bound.',
            'Four-neighbour payload excludes zero-border pixels and reuse; actual DDR burst amplification can exceed it.',
            'DDR refresh, command overhead, stalls, burst wastage, arbitration and cache misses are unmeasured; no bandwidth/FPS pass is inferred.',
            'Capture FPS, newly corrected FPS and display refresh are distinct requested values, not measurements.',
        ],
    }


def _optional_text(value, name):
    if value is not None and (type(value) is not str or not value.strip()):
        raise ValueError(f'{name} must be null or a nonempty string')


def inspect_profile(profile, scope='corrected'):
    if scope not in ('raw-capture', 'corrected'):
        raise ValueError('scope must be raw-capture or corrected')
    if type(profile) is not dict:
        raise ValueError('profile must be a JSON object')
    if type(profile.get('schema_version')) is not int or profile['schema_version'] != 1:
        raise ValueError('schema_version must be integer 1')
    blockers = []
    for name in ('profile_id', 'sensor_model', 'lens_model', 'synchronization'):
        value = profile.get(name)
        _optional_text(value, name)
        if value is None:
            blockers.append(f'{name} is unknown')
    kind = profile.get('change_kind')
    if kind not in (None, 'lens-only', 'camera-module'):
        raise ValueError('change_kind must be null, lens-only or camera-module')
    if kind is None:
        blockers.append('change_kind is unknown: lens-only versus camera-module is unresolved')
    interface = profile.get('interface')
    if interface not in (None, 'DVP', 'MIPI', 'USB'):
        raise ValueError('interface must be null, DVP, MIPI or USB')
    if interface is None:
        blockers.append('interface is unknown')
    elif interface != 'DVP':
        blockers.append(f'{interface} acquisition is not implemented by the shipped DVP chain')
    count = profile.get('camera_count')
    if count is None:
        blockers.append('camera_count is unknown')
    else:
        camera_count(count)
        if count == 2:
            blockers.append('two simultaneous cameras need new RTL, synchronization and bank ownership; camera2 is single-input')
            if profile.get('synchronization') == 'not-applicable-single-camera':
                blockers.append('stereo synchronization cannot be declared not applicable for two cameras')
    single_sync_na = count == 1 and profile.get('synchronization') == 'not-applicable-single-camera'
    electrical = profile.get('electrical', {})
    if type(electrical) is not dict:
        raise ValueError('electrical must be an object')
    for name in ('io_voltage_v', 'power_voltage_v'):
        value = electrical.get(name)
        if value is None:
            blockers.append(f'electrical.{name} is unknown')
        else:
            positive_number(value, f'electrical.{name}')
    _optional_text(electrical.get('pinout_reference'), 'electrical.pinout_reference')
    if electrical.get('pinout_reference') is None:
        blockers.append('electrical.pinout_reference is unknown')
    verified = profile.get('verification', {})
    if type(verified) is not dict:
        raise ValueError('verification must be an object')
    compatibility_review = verified.get('io_level_compatibility')
    if compatibility_review is not None and type(compatibility_review) is not bool:
        raise ValueError('verification.io_level_compatibility must be boolean or null')
    compatibility_evidence = electrical.get('io_compatibility_evidence')
    _optional_text(compatibility_evidence, 'electrical.io_compatibility_evidence')
    distinct_level_review_required = interface == 'DVP' and electrical.get('io_voltage_v') not in (None, 3.3)
    if distinct_level_review_required and (compatibility_review is not True or compatibility_evidence is None):
        blockers.append('declared DVP signal level requires explicit io_level_compatibility review and io_compatibility_evidence; sensor rail and FPGA IOSTANDARD are distinct facts')
    for name in VERIFICATIONS:
        value = verified.get(name)
        if value is not None and type(value) is not bool:
            raise ValueError(f'verification.{name} must be boolean or null')
        if name == 'new_lens_calibration' and scope == 'raw-capture':
            continue
        if name == 'synchronization' and single_sync_na:
            continue
        if value is not True:
            blockers.append(f'{name} has not been verified')
    mode = profile.get('input_mode', {})
    if type(mode) is not dict:
        raise ValueError('input_mode must be an object')
    for name in ('width', 'height', 'bus_width_bits'):
        if mode.get(name) is not None:
            positive_int(mode[name], f'input_mode.{name}')
        else:
            blockers.append(f'input_mode.{name} is unknown')
    for name in ('fps', 'pclk_hz'):
        if mode.get(name) is not None:
            positive_number(mode[name], f'input_mode.{name}')
        else:
            blockers.append(f'input_mode.{name} is unknown')
    _optional_text(mode.get('pixel_format'), 'input_mode.pixel_format')
    if mode.get('pixel_format') != 'RGB565':
        blockers.append('current capture requires independently verified RGB565 byte order/format')
    if mode.get('bus_width_bits') not in (None, 8):
        blockers.append('current DVP capture is 8-bit')
    if (mode.get('width'), mode.get('height')) != (640, 480):
        blockers.append('new dimensions require a separate camera/core/display candidate and timing validation')
    if mode.get('pclk_hz') is not None and mode['pclk_hz'] > 48_000_000:
        blockers.append('declared PCLK exceeds the current 48MHz input constraint')
    if all(mode.get(n) is not None for n in ('width', 'height', 'fps', 'pclk_hz')):
        minimum = mode['width'] * mode['height'] * mode['fps'] * 2
        if mode['pclk_hz'] < minimum:
            blockers.append('declared PCLK is below even the RGB565 effective-pixel minimum')
    return {
        'profile_id': profile.get('profile_id'), 'scope': scope,
        'profile_checks_complete': not blockers,
        'new_lens_calibration_required_for_this_scope': scope == 'corrected',
        'single_camera_synchronization_explicitly_not_applicable': single_sync_na,
        'separate_io_compatibility_review_required': distinct_level_review_required,
        'io_compatibility_review_declared': compatibility_review is True,
        'io_compatibility_evidence': compatibility_evidence,
        'new_configuration_download_blocked': bool(blockers), 'blockers': blockers,
        'hardware_ready': False, 'download_authorized_by_tool': False, 'hardware_accessed': False,
        'current_chain': 'one 8-bit RGB565 DVP input; camera2 is an alternate single-input mapping',
        'pin_boundary': 'AA23 D5 is verified only for the previous board/sensor wiring; recheck the new pinout',
        'limits': 'Verification fields are supplied declarations and candidate_configuration must refer to the selected scope. Sensor supply/DOVDD rail, interface signal level and FPGA bank voltage/IOSTANDARD are distinct facts. A non-3.3-V declared DVP level requires a documented compatibility review, not an automatic rejection or a numerical compatibility verdict; this tool does not calculate device thresholds. Even complete reviewed declarations do not inspect hardware, validate timing/bitstreams, or authorize downloading. A lens change invalidates previous optical calibration; raw-capture scope permits collecting that new calibration without first claiming corrected readiness.',
    }


def read_json(path):
    def invalid_constant(value):
        raise ValueError(f'JSON nonfinite constant is not allowed: {value}')
    return json.loads(Path(path).read_text(encoding='utf-8-sig'), parse_constant=invalid_constant)


def write_new_json(path, report):
    destination = Path(path).resolve()
    if not destination.parent.is_dir():
        raise ValueError('output parent directory must already exist; no directory is created')
    allowed = Path(__file__).resolve().parents[1] / 'output' / 'project'
    if destination.parent != allowed.resolve():
        raise ValueError('output must be a new file directly in distortion/output/project; historical evidence is protected')
    with destination.open('x', encoding='utf-8') as stream:
        stream.write(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + '\n')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', type=Path)
    parser.add_argument('--scope', choices=('raw-capture', 'corrected'), default='corrected',
                        help='profile admission scope; raw-capture permits collecting new calibration')
    parser.add_argument('--explore', action='store_true', help='explicit hypothetical mode; never admits hardware')
    for name in ('width', 'height', 'cameras', 'output-width', 'output-height', 'display-streams',
                 'bank-stride-address-units', 'address-unit-bytes', 'ddr-capacity-bytes'):
        parser.add_argument('--' + name, type=int)
    for name in ('fps', 'new-output-fps', 'display-fps'):
        parser.add_argument('--' + name, type=float)
    parser.add_argument('--output', type=Path, help='new JSON file directly in existing distortion/output/project')
    args = parser.parse_args(argv)
    if not args.profile and not args.explore:
        parser.error('provide --profile and/or --explore')
    values = vars(args)
    mode_names = ('width', 'height', 'fps', 'cameras', 'output_width', 'output_height',
                  'new_output_fps', 'display_fps', 'display_streams', 'bank_stride_address_units',
                  'address_unit_bytes', 'ddr_capacity_bytes')
    if not args.explore and any(values[n] is not None for n in mode_names):
        parser.error('mode arguments require --explore; they cannot silently amend the camera profile')
    try:
        report = {'hardware_accessed': False}
        if args.profile:
            report['profile'] = inspect_profile(read_json(args.profile), scope=args.scope)
        if args.explore:
            if any(values[n] is None for n in ('width', 'height', 'fps', 'cameras')):
                parser.error('--explore requires --width --height --fps --cameras')
            report['budget'] = budget(**{n: values[n] for n in mode_names if values[n] is not None})
        if args.output:
            write_new_json(args.output, report)
        print(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False))
        return 2 if report.get('profile', {}).get('new_configuration_download_blocked') else 0
    except (OSError, ValueError, OverflowError) as error:
        parser.error(str(error))


if __name__ == '__main__':
    raise SystemExit(main())
