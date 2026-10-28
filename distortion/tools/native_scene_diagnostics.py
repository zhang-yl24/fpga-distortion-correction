"""Read-only integrity and natural-scene diagnostics for native RGB565 captures.

No serial/JTAG access, calibration fit, display dependency or driver changes.
Dark pixels, repeated rows and unchanged frames are observations, not proof of
a defective camera: a lens cap, texture, static scene and fish-eye black borders
can produce those observations. PGFRAME1 transaction IDs are not exposure IDs.
"""
from pathlib import Path
import argparse
import hashlib
import json
import zlib

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
IDENTITY_FIELDS = ('camera_id', 'lens_id', 'profile_id', 'capture_mode_id', 'eye')
cv2.setNumThreads(1)
cv2.ocl.setUseOpenCL(False)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def canonical_sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


def _path(value, base, label):
    if not isinstance(value, str) or not value:
        raise ValueError(label+' requires an explicit file path')
    path = Path(value)
    path = (path if path.is_absolute() else Path(base)/path).resolve()
    if not path.is_file():
        raise ValueError(label+' is missing: '+str(path))
    return path


def _hash_matches(value, expected, label):
    if not isinstance(expected, str) or len(expected) != 64 or value.lower() != expected.lower():
        raise ValueError(label+' SHA256 mismatch or missing expected hash')


def _identity(value):
    if not isinstance(value, dict) or any(not isinstance(value.get(key), str) or not value[key].strip() for key in IDENTITY_FIELDS):
        raise ValueError('explicit camera/lens/profile/mode/eye identity binding is required')
    if value['eye'] not in ('CAM1', 'CAM2'):
        raise ValueError('eye must identify the operator-declared CAM1/CAM2 connector group')
    return {key: value[key] for key in IDENTITY_FIELDS}


def verify_build_role(metadata, *, binding=None, binding_base=None):
    """Re-read bound build files independently of the receiver implementation."""
    size = [metadata['width'], metadata['height']]
    contract = {'protocol': 'PGFRAME1', 'payload_role': 'native_raw',
                'geometry_applied': False, 'image_size': size}
    record = metadata.get('build_binding')
    claimed_raw = bool(metadata.get('upstream_raw_contract_hash_bound') is True and
        metadata.get('upstream_payload_role') == 'native_raw' and metadata.get('geometry_applied') is False and
        isinstance(record, dict) and record.get('raw_capture_contract') == contract)
    result = {'native_role_claim_present': claimed_raw, 'binding_file_supplied': binding is not None,
              'bound_build_files_verified': False, 'native_source_contract_verified': False,
              'actual_programmed_bitstream_independently_observed': False}
    if binding is None:
        result['verification_gap'] = 'No original binding file supplied; role/build assertions remain unverified.'
        return result
    identity = _identity(binding)
    if identity != _identity(metadata.get('identity_binding')) or binding.get('image_size') != size or binding.get('pixel_format') != 'RGB565_LE':
        raise ValueError('capture identity/mode differs from the original binding file')
    _hash_matches(canonical_sha(binding), metadata.get('binding_sha256'), 'canonical binding')
    if not claimed_raw:
        result['verification_gap'] = 'Upstream native-raw contract is absent/unknown; content diagnostics do not establish raw-camera provenance.'
        return result
    files = binding.get('build_binding', {})
    paths = {}
    for key in ('validated_build', 'bitstream', 'pinout', 'timing_report'):
        entry = files.get(key)
        if not isinstance(entry, dict):
            raise ValueError('binding requires '+key+' file and SHA256')
        path = _path(entry.get('path'), binding_base, key)
        _hash_matches(digest(path), entry.get('sha256'), key)
        paths[key] = path
    manifest = read_json(paths['validated_build'])
    if manifest.get('RawCaptureContract') != contract or record.get('raw_capture_contract') != contract:
        raise ValueError('capture/build native raw role or image size differs')
    expected_record = {'validated_build_sha256': digest(paths['validated_build']),
                       'bitstream_sha256': digest(paths['bitstream']),
                       'pinout_sha256': digest(paths['pinout']),
                       'timing_report_sha256': digest(paths['timing_report'])}
    for field, actual in expected_record.items():
        _hash_matches(actual, record.get(field), 'metadata '+field)
    _hash_matches(digest(paths['bitstream']), manifest.get('SHA256'), 'build bitstream')
    _hash_matches(digest(paths['timing_report']), manifest.get('TimingSHA256'), 'build timing')
    if 'All Constraints Met' not in paths['timing_report'].read_text(encoding='utf-8', errors='replace'):
        raise ValueError('bound final timing report does not meet all constraints')
    sources = manifest.get('SourceSHA256')
    if not isinstance(sources, dict) or not sources:
        raise ValueError('build source SHA256 closure is absent')
    pinout_in_sources = False
    for name, expected in sources.items():
        source = (ROOT/name).resolve()
        if not source.is_relative_to(ROOT) or not source.is_file():
            raise ValueError('build source missing or outside project: '+str(name))
        _hash_matches(digest(source), expected, 'build source '+name)
        pinout_in_sources |= source == paths['pinout']
    if not pinout_in_sources:
        raise ValueError('pinout file is not in the bound build source closure')
    if record.get('selected_eye') != identity['eye']:
        raise ValueError('build selected_eye differs from the declared connector group')
    reference = ROOT/('board/camera_sync-pins.json' if identity['eye'] == 'CAM1' else 'board/corrected_gamma_d5-pins.json')
    expected_pins, actual_pins = read_json(reference), read_json(paths['pinout'])
    camera_ports = [key for key in expected_pins if key.startswith('cam_')]
    if any(actual_pins.get(key) != expected_pins[key] for key in camera_ports):
        raise ValueError('bound camera pins differ from the selected legacy connector reference')
    result.update(bound_build_files_verified=True, native_source_contract_verified=True,
                  verified_source_files=len(sources), validated_build_sha256=expected_record['validated_build_sha256'],
                  bitstream_sha256=expected_record['bitstream_sha256'])
    return result


def load_verified_frame(metadata_path, *, binding=None, binding_base=None, expected_metadata_sha256=None):
    path = Path(metadata_path).resolve()
    if expected_metadata_sha256 is not None:
        _hash_matches(digest(path), expected_metadata_sha256, 'capture metadata')
    metadata = read_json(path)
    identity = _identity(metadata.get('identity_binding'))
    if type(metadata.get('frame_id')) is not int or not 0 <= metadata['frame_id'] < 1 << 32:
        raise ValueError('frame_id must be an unsigned transaction ID')
    width, height = metadata.get('width'), metadata.get('height')
    if type(width) is not int or type(height) is not int or not 1 <= width <= 1920 or not 1 <= height <= 1080:
        raise ValueError('capture size must fit native PGFRAME1 dimensions')
    if metadata.get('pixel_format') != 'RGB565_LE':
        raise ValueError('capture format must be explicit RGB565_LE')
    raw = _path(metadata.get('raw_path'), path.parent, 'raw payload')
    png = _path(metadata.get('image_path'), path.parent, 'native PNG')
    payload = raw.read_bytes()
    if len(payload) != width*height*2 or metadata.get('payload_bytes', len(payload)) != len(payload):
        raise ValueError('truncated payload or payload_bytes/image size mismatch')
    _hash_matches(hashlib.sha256(payload).hexdigest(), metadata.get('raw_sha256'), 'raw payload')
    crc = f'{zlib.crc32(payload):08X}'
    if any(not isinstance(metadata.get(key), str) or metadata[key].upper() != crc for key in ('source_crc32', 'received_crc32')):
        raise ValueError('source/received/raw CRC32 mismatch')
    _hash_matches(digest(png), metadata.get('image_sha256'), 'native PNG')
    words = np.frombuffer(payload, dtype='<u2').reshape(height, width)
    red, green, blue = (words >> 11) & 31, (words >> 5) & 63, words & 31
    rgb = np.stack(((red << 3) | (red >> 2), (green << 2) | (green >> 4), (blue << 3) | (blue >> 2)), axis=-1).astype(np.uint8)
    image = cv2.imdecode(np.fromfile(png, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None or image.shape != (height, width, 3) or not np.array_equal(image[..., ::-1], rgb):
        raise ValueError('PNG differs from raw RGB565 bit replication')
    build = verify_build_role(metadata, binding=binding, binding_base=binding_base)
    result = {'metadata_path': str(path), 'metadata_sha256': digest(path),
        'raw_path': str(raw), 'raw_sha256': hashlib.sha256(payload).hexdigest(),
        'png_path': str(png), 'png_sha256': digest(png), 'crc32': crc,
        'identity_binding': identity, 'identity_verified_on_wire': metadata.get('identity_verified_on_wire') is True,
        'identity_binding_kind': metadata.get('identity_binding_kind', 'unspecified'),
        'source_kind': metadata.get('source_kind', 'unspecified'), 'frame_id': metadata.get('frame_id'),
        'session_id': metadata.get('session_id'), 'received_at_utc': metadata.get('received_at_utc'),
        'frame_id_is_sensor_exposure_counter': False, 'received_time_is_exposure_time': False,
        'file_integrity_passed': True, 'build_role_verification': build}
    return result, words, rgb


def analyze_words(words, *, valid_mask=None):
    words = np.asarray(words)
    if words.ndim != 2 or words.dtype != np.uint16 or not words.size:
        raise ValueError('nonempty native uint16 HxW RGB565 words required')
    mask = np.ones(words.shape, dtype=bool) if valid_mask is None else np.asarray(valid_mask)
    if mask.dtype != np.bool_ or mask.shape != words.shape or not mask.any():
        raise ValueError('analysis mask must be nonempty boolean with native image shape')
    r, g, b = (words >> 11) & 31, (words >> 5) & 63, words & 31
    rgb = np.stack(((r << 3) | (r >> 2), (g << 2) | (g >> 4), (b << 3) | (b >> 2)), axis=-1).astype(np.uint8)
    masks = {'analysis_valid': mask, 'exact_black': words == 0, 'exact_white': words == 65535,
             'any_channel_max': (r == 31) | (g == 63) | (b == 31),
             'near_black_all_channels': (rgb.max(axis=-1) <= 8)}
    samples = rgb[mask].astype(np.float64)
    bit_fractions = [float(((words[mask] >> bit) & 1).mean()) for bit in range(16)]
    dynamic_bits = sum(0 < fraction < 1 for fraction in bit_fractions)
    lane_signatures = []
    for lane in range(8):
        low, high = bit_fractions[lane], bit_fractions[lane+8]
        if low == high and low in (0., 1.):
            lane_signatures.append({'dvp_data_lane': lane, 'word_bits': [lane, lane+8],
                'constant_level': int(low), 'other_varying_word_bits': dynamic_bits,
                'wiring_failure_proven': False})
    height, width = words.shape
    row_equal = float(np.all(words[1:] == words[:-1], axis=1).mean()) if height > 1 else None
    col_equal = float(np.all(words[:, 1:] == words[:, :-1], axis=0).mean()) if width > 1 else None
    periodic = []
    for axis, length in (('rows', height), ('columns', width)):
        for lag in (1, 2, 4, 8, 16, 32):
            if lag >= length:
                continue
            equality = words[lag:] == words[:-lag] if axis == 'rows' else words[:, lag:] == words[:, :-lag]
            periodic.append({'axis': axis, 'lag_pixels': lag, 'equal_pixel_fraction': float(equality.mean())})
    stats = {'pixels': int(words.size), 'selected_pixels': int(mask.sum()),
        'masks_change_source_pixels': False,
        'exact_black_fraction': float(masks['exact_black'][mask].mean()),
        'exact_white_fraction': float(masks['exact_white'][mask].mean()),
        'near_black_all_channels_fraction': float(masks['near_black_all_channels'][mask].mean()),
        'any_channel_max_fraction': float(masks['any_channel_max'][mask].mean()),
        'rgb_mean_codes': samples.mean(axis=0).tolist(), 'rgb_std_codes': samples.std(axis=0).tolist(),
        'rgb_p01_codes': np.percentile(samples, 1, axis=0).tolist(),
        'rgb_p50_codes': np.percentile(samples, 50, axis=0).tolist(),
        'rgb_p99_codes': np.percentile(samples, 99, axis=0).tolist(),
        'rgb_channel_at_max_fractions': (samples == 255).mean(axis=0).tolist(),
        'word_bit_one_fractions_lsb_first': bit_fractions, 'varying_word_bits': dynamic_bits,
        'constant_paired_dvp_lane_signatures': lane_signatures,
        'd5_both_transferred_byte_bits_constant_zero': bit_fractions[5] == bit_fractions[13] == 0,
        'uniform_word_frame': bool(np.all(words == words.flat[0])),
        'adjacent_identical_full_row_fraction': row_equal, 'adjacent_identical_full_column_fraction': col_equal,
        'unique_rows': int(np.unique(words, axis=0).shape[0]),
        'unique_columns': int(np.unique(words, axis=1).shape[1]), 'periodic_pixel_equality': periodic,
        'row_column_structure_scope': 'full native image; source pixels are never masked out of structure checks',
        'limits': 'Code statistics only. A paired stuck-bit signature can be scene-dependent and does not identify a failed DVP lane. Black lens borders/caps, clipped exposure, static or periodic textures require controlled follow-up; no calibrated color error, MTF or geometric calibration is estimated.'}
    return stats, masks


def analyze_capture(metadata_paths, *, binding_path=None, metadata_hashes=None, analysis_mask=None):
    binding = read_json(binding_path) if binding_path else None
    binding_base = Path(binding_path).resolve().parent if binding_path else None
    result, previous, previous_record, mask_arrays = [], None, None, {}
    for index, path in enumerate(metadata_paths):
        record, words, rgb = load_verified_frame(path, binding=binding, binding_base=binding_base,
            expected_metadata_sha256=metadata_hashes[index] if metadata_hashes else None)
        stats, masks = analyze_words(words, valid_mask=analysis_mask)
        record['scene_diagnostics'] = stats
        if previous is not None:
            if record['identity_binding'] != previous_record['identity_binding'] or words.shape != previous.shape:
                raise ValueError('temporal comparison requires the same declared camera/lens/mode/eye and image size')
            previous_rgb = previous_record.pop('_rgb')
            delta = np.abs(rgb.astype(np.int16)-previous_rgb.astype(np.int16))
            record['previous_capture_difference'] = {
                'previous_raw_sha256': previous_record['raw_sha256'],
                'identical_pixels': bool(np.array_equal(words, previous)),
                'changed_pixel_fraction': float((words != previous).mean()),
                'mean_absolute_rgb_code_difference': float(delta.mean()),
                'per_channel_mean_absolute_code_difference': delta.mean(axis=(0, 1)).tolist(),
                'camera_freeze_verified': False,
                'limits': 'Unchanged pixels can be a static scene or repeated capture; transaction ID progress and host receive times do not prove independent exposures or a sensor frame rate.'}
        record['_rgb'] = rgb
        for name, mask in masks.items():
            mask_arrays[f'frame_{index:04d}_{name}'] = mask
        result.append(record)
        previous, previous_record = words, record
    if not result:
        raise ValueError('at least one explicit native metadata file is required')
    result[-1].pop('_rgb')
    return {'schema': 1, 'hardware_accessed_by_analyzer': False, 'hardware_release_allowed': False,
        'file_integrity_passed': True, 'frames_analyzed': len(result), 'frames': result,
        'native_source_contracts_verified': all(row['build_role_verification']['native_source_contract_verified'] for row in result),
        'source_kind': sorted(set(row['source_kind'] for row in result)),
        'physical_identity_independently_verified': False, 'optical_calibration_complete': False,
        'natural_scene_is_calibration': False, 'display_required': False,
        'binding_file_sha256': digest(binding_path) if binding_path else None,
        'analysis_mask_supplied': analysis_mask is not None,
        'source_sha256': {'tools/native_scene_diagnostics.py': digest(Path(__file__))},
        'limits': 'Read-only independent file/bit-replication/build evidence audit and initial scene diagnostics. It does not observe actual programming, connector voltage, sensor identity, exposures, display behavior, lens calibration, professional color accuracy or MTF. No mask or scene statistic silently removes source pixels.'}, mask_arrays


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--summary', type=Path)
    source.add_argument('--metadata', type=Path, nargs='+')
    parser.add_argument('--binding', type=Path)
    parser.add_argument('--analysis-mask', type=Path, help='optional native boolean NPY; source pixels remain untouched')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--masks-output', type=Path, required=True, help='new compressed NPZ retaining all native masks')
    args = parser.parse_args()
    for path in (args.output, args.masks_output):
        if not path.parent.is_dir() or path.exists():
            parser.error('outputs must be new files in existing directories')
    summary, metadata, hashes = None, args.metadata, None
    if args.summary:
        summary = read_json(args.summary)
        entries = summary.get('frames', [])
        if summary.get('saved_frames') != len(entries):
            parser.error('summary saved_frames differs from its explicit frame list')
        metadata = [_path(entry.get('metadata_path'), args.summary.parent, 'summary metadata') for entry in entries]
        hashes = [entry.get('metadata_sha256') for entry in entries]
        if any(not isinstance(value, str) or len(value) != 64 for value in hashes):
            parser.error('summary requires a metadata SHA256 for every frame')
    mask = np.load(args.analysis_mask, allow_pickle=False) if args.analysis_mask else None
    report, masks = analyze_capture(metadata, binding_path=args.binding, metadata_hashes=hashes, analysis_mask=mask)
    if summary is not None:
        report['capture_summary'] = {'path': str(args.summary.resolve()), 'sha256': digest(args.summary),
            'session_receiver_passed': summary.get('passed'), 'rejected_packets': summary.get('rejected_packets'),
            'incomplete_or_timed_out': summary.get('incomplete_or_timed_out')}
    with args.masks_output.open('xb') as stream:
        np.savez_compressed(stream, **masks)
    report['retained_native_masks'] = {'path': str(args.masks_output.resolve()), 'sha256': digest(args.masks_output), 'arrays': sorted(masks)}
    if args.analysis_mask:
        report['analysis_mask_sha256'] = digest(args.analysis_mask)
    with args.output.open('x', encoding='utf-8') as stream:
        stream.write(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False)+'\n')
    print(json.dumps({key: report[key] for key in ('file_integrity_passed', 'frames_analyzed', 'native_source_contracts_verified', 'source_kind')}))


if __name__ == '__main__':
    main()
