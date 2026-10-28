"""Classify bound sensor-internal bars; never optical/colorimetric calibration."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import zlib
import cv2
import numpy as np

from prepare_guarded_colorbars import TARGET, BUILD_TAG, SENSOR_OUTPUT_CONTRACT
from native_camera_capture import load_json, sha

ROOT = Path(__file__).resolve().parents[1]
NAMES = ('white', 'yellow', 'cyan', 'green', 'magenta', 'red', 'blue', 'black')
PALETTE = np.array([[255,255,255], [255,255,0], [0,255,255], [0,255,0],
                    [255,0,255], [255,0,0], [0,0,255], [0,0,0]], dtype=np.float64)
cv2.setNumThreads(1)
cv2.ocl.setUseOpenCL(False)
MAX_CHANNEL_DISTANCE = 40
RAW_CONTRACT = {'protocol': 'PGFRAME1', 'payload_role': 'native_raw',
                'geometry_applied': False, 'image_size': [640, 480]}


def rgb_from_words(words):
    red, green, blue = (words >> 11) & 31, (words >> 5) & 63, words & 31
    return np.stack(((red << 3) | (red >> 2), (green << 2) | (green >> 4),
                     (blue << 3) | (blue >> 2)), axis=-1).astype(np.uint8)


def describe(words):
    if not isinstance(words, np.ndarray) or words.shape != (480,640) or words.dtype != np.uint16:
        raise ValueError('require full native 640x480 uint16 RGB565 pixels')
    rgb = rgb_from_words(words)
    regions = [rgb[120:360, x-12:x+12].reshape(-1,3) for x in range(40,640,80)]
    medians = np.stack([np.median(region, axis=0) for region in regions])
    distances = np.max(np.abs(medians[:,None,:]-PALETTE[None,:,:]), axis=2)
    closest = distances.argmin(axis=1)
    errors = distances[np.arange(8), closest]
    order = [NAMES[int(index)] for index in closest]
    ordered = order == list(NAMES) or order == list(reversed(NAMES))
    bit_ones = [float(np.mean((words & (1 << bit)) != 0)) for bit in range(16)]
    d5_signature = bit_ones[5] == 0 and bit_ones[13] == 0
    d5_high_signature = bit_ones[5] == 1 and bit_ones[13] == 1
    return {'central_bar_rgb_medians': medians.tolist(), 'observed_order': order,
        'max_channel_code_distance_to_ideal_per_bar': errors.tolist(),
        'central_region_p05_p95_rgb': [np.percentile(region,[5,95],axis=0).tolist() for region in regions],
        'order_matches_standard_eight_bars': ordered,
        'levels_within_existing_40_code_policy': bool(np.max(errors) <= MAX_CHANNEL_DISTANCE),
        'word_bit_one_fractions_lsb_first': bit_ones,
        'historical_d5_both_byte_bits_constant_zero_signature': d5_signature,
        'd5_both_byte_bits_constant_one_signature': d5_high_signature,
        'palette_order_and_levels_accepted': bool(ordered and np.max(errors) <= MAX_CHANNEL_DISTANCE),
        'limits': 'Fixed native central regions, existing diagnostic 40-code policy. These are digital RGB code comparisons; PRE ISP bars can still be changed by sensor ISP. A stuck-bit-like signature is observational, not a unique electrical diagnosis.'}


def compare(words):
    normal = describe(words)
    swapped = describe(words.byteswap())
    passed = (normal['palette_order_and_levels_accepted'] and
              not swapped['palette_order_and_levels_accepted'] and
              not normal['historical_d5_both_byte_bits_constant_zero_signature'] and
              not normal['d5_both_byte_bits_constant_one_signature'])
    return {'normal': normal, 'swapped_byte_order_counterexample': swapped,
        'central_color_sequence_matches_standard': normal['order_matches_standard_eight_bars'],
        'central_code_levels_meet_40_policy': normal['levels_within_existing_40_code_policy'],
        'byte_order_color_sequence_verified': normal['order_matches_standard_eight_bars'] and not swapped['order_matches_standard_eight_bars'],
        'digital_pattern_check_passed': passed,
        'check_scope': 'fixed central sample-region medians and word-bit observations only',
        'sampled_palette_pixel_fraction': 8*240*24/(640*480),
        'full_frame_pattern_shape_verified': False,
        'optical_color_accuracy_verified': False, 'lens_calibration_eligible': False,
        'all_electrical_lanes_individually_proven': False,
        'limits': 'Sensor-generated digital test pattern only. No illumination, lens sharpness/distortion, AWB fidelity, HDMI colorimetry or calibrated color error is measured.'}


def compare_historical(words, historical_words):
    """Exact decoded-word compatibility, independent of the 40-code acceptance."""
    for pixels in (words, historical_words):
        if not isinstance(pixels, np.ndarray) or pixels.shape != (480,640) or pixels.dtype != np.uint16:
            raise ValueError('historical comparison requires native 640x480 uint16 arrays')
    equal = int(np.count_nonzero(words == historical_words))
    return {'equal_words': equal, 'total_words': int(words.size),
        'exact_word_match': equal == words.size, 'affects_40_code_acceptance': False,
        'optical_acceptance': False, 'all_possible_dvp_words_verified': False,
        'limits': 'Compatibility of these two decoded digital-pattern snapshots only; not provenance authentication, optics, calibration, all input words or future behavior.'}


def _local(path):
    path = Path(path).resolve()
    if not path.is_relative_to(ROOT) or not path.is_file():
        raise ValueError('missing or non-project evidence path')
    return path


def _pattern_metadata(record):
    return (isinstance(record, dict) and record.get('source_kind') == 'physical_sensor_internal_test_pattern' and
        record.get('input_origin') == SENSOR_OUTPUT_CONTRACT['input_origin'] and
        record.get('sensor_output_contract') == SENSOR_OUTPUT_CONTRACT and
        record.get('calibration_scene_eligible') is False and
        record.get('lens_optical_acceptance_eligible') is False and
        record.get('guarded_target') == TARGET and record.get('guarded_build_tag') == BUILD_TAG and
        record.get('guarded_mode') == 'sensor-internal-bars')


def _hash_matches(path, digest):
    return isinstance(digest, str) and bool(re.fullmatch(r'[a-fA-F0-9]{64}', digest)) and sha(path) == digest.lower()


def _crc_matches(value, expected):
    return isinstance(value, str) and bool(re.fullmatch(r'[a-fA-F0-9]{8}', value)) and value.upper() == expected


def analyze_summary(summary_path, *, historical_path=None):
    summary_path = _local(summary_path)
    summary = load_json(summary_path)
    if summary.get('passed') is not True or not _pattern_metadata(summary):
        raise ValueError('require a completed explicitly classified physical sensor-pattern session')
    if summary.get('sensor_output_contract') != SENSOR_OUTPUT_CONTRACT or summary.get('calibration_scene_eligible') is not False:
        raise ValueError('session lacks the exact test-pattern contract or exclusion from calibration')
    historical_words = None
    if historical_path is not None:
        historical_path = _local(historical_path)
        historical_sha = sha(historical_path)
        historical_words = np.load(historical_path, allow_pickle=False)
    frames = summary.get('frames')
    if not isinstance(frames, list) or not frames:
        raise ValueError('no completed sensor-pattern frames')
    reports, seen = [], set()
    for frame in frames:
        metadata_path = _local(frame['metadata_path'])
        if metadata_path in seen or not _hash_matches(metadata_path, frame['metadata_sha256']):
            raise ValueError('frame metadata changed')
        seen.add(metadata_path)
        metadata = load_json(metadata_path)
        if not _pattern_metadata(metadata):
            raise ValueError('frame is not explicitly quarantined as a sensor internal test pattern')
        raw_path, png_path = _local(metadata['raw_path']), _local(metadata['image_path'])
        payload = raw_path.read_bytes()
        crc = f'{zlib.crc32(payload):08X}'
        if (not _hash_matches(raw_path, metadata['raw_sha256']) or not _hash_matches(png_path, metadata['image_sha256']) or
                len(payload) != 640*480*2 or metadata['width'] != 640 or metadata['height'] != 480 or
                metadata.get('payload_bytes') != len(payload) or metadata.get('pixel_format') != 'RGB565_LE' or
                not _crc_matches(metadata.get('source_crc32'), crc) or not _crc_matches(metadata.get('received_crc32'), crc) or
                metadata.get('upstream_payload_role') != 'native_raw' or metadata.get('geometry_applied') is not False or
                metadata.get('geometry_applied_by_receiver') is not False or
                metadata.get('photometric_processing_applied_by_receiver') is not False or
                metadata.get('upstream_raw_contract_hash_bound') is not True):
            raise ValueError('native pixel/source CRC/hash/role evidence differs')
        build = metadata['build_binding']
        manifest_path = _local(build['validated_build'])
        if not _hash_matches(manifest_path, build['validated_build_sha256']):
            raise ValueError('source-bound build manifest changed')
        manifest = load_json(manifest_path)
        sources = manifest.get('SourceSHA256')
        control = manifest.get('GuardedControlContract')
        if (manifest.get('Target') != TARGET or manifest.get('SensorOutputContract') != SENSOR_OUTPUT_CONTRACT or
                manifest.get('RawCaptureContract') != RAW_CONTRACT or build.get('raw_capture_contract') != RAW_CONTRACT or
                not isinstance(control, dict) or control.get('build_tag') != BUILD_TAG or
                not isinstance(sources, dict) or not sources or type(build.get('bound_source_count')) is not int or
                build['bound_source_count'] != len(sources)):
            raise ValueError('manifest is not the explicit sensor-bars target')
        bit = _local(manifest['Bitstream'])
        if not _hash_matches(bit, manifest['SHA256']) or not _hash_matches(bit, build.get('bitstream_sha256')):
            raise ValueError('test-pattern bitstream changed')
        for name, digest in sources.items():
            if not _hash_matches(_local(ROOT/name), digest):
                raise ValueError('test-pattern bound source changed: '+name)
        words = np.frombuffer(payload, dtype='<u2').reshape(480,640)
        image = cv2.imread(str(png_path), cv2.IMREAD_UNCHANGED)
        if image is None or image.shape != (480,640,3) or not np.array_equal(image[:,:,::-1], rgb_from_words(words)):
            raise ValueError('PNG differs from lossless RGB565 bit replication')
        report = {'metadata_path': str(metadata_path), 'raw_sha256': metadata['raw_sha256'],
                  'frame_id': metadata['frame_id'], **compare(words)}
        if historical_words is not None:
            report['historical_compatibility'] = {**compare_historical(words, historical_words),
                'historical_path': str(historical_path), 'historical_file_sha256': historical_sha,
                'historical_rgb565_le_payload_sha256': hashlib.sha256(historical_words.astype('<u2').tobytes()).hexdigest()}
        reports.append(report)
    if not reports:
        raise ValueError('no completed sensor-pattern frames')
    if (type(summary.get('saved_frames')) is not int or summary['saved_frames'] != len(reports) or
            (historical_path is not None and sha(historical_path) != historical_sha)):
        raise ValueError('frame count or historical input changed')
    return {'schema': 1, 'hardware_accessed_by_analyzer': False,
        'source_kind': 'physical_sensor_internal_test_pattern', 'sensor_output_contract': SENSOR_OUTPUT_CONTRACT,
        'summary_path': str(summary_path), 'summary_sha256': sha(summary_path), 'frames': reports,
        'digital_pattern_checks_passed': all(report['digital_pattern_check_passed'] for report in reports),
        'historical_digital_compatibility_observed': (all(report['historical_compatibility']['exact_word_match'] for report in reports)
                                                     if historical_words is not None else None),
        'physical_programming_event_verified_by_analyzer': False,
        'calibration_scene_eligible': False, 'optical_quality_verified': False,
        'limits': 'Separate pixel classification and source-file integrity audit. Actual SRAM/UART event provenance is provided by the separately retained programming and independent hardware audit, not inferred from color bars alone.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--summary', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--historical-words', type=Path, help='optional existing native RGB565 .npy snapshot; never changes acceptance')
    args = parser.parse_args()
    if not args.output.parent.is_dir() or args.output.exists():
        parser.error('output must be new in an existing directory')
    result = analyze_summary(args.summary, historical_path=args.historical_words)
    result['analyzer_sha256'] = sha(Path(__file__))
    with args.output.open('x', encoding='utf-8') as stream:
        stream.write(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'digital_pattern_checks_passed': result['digital_pattern_checks_passed'], 'frames': len(result['frames'])}))


if __name__ == '__main__':
    main()
