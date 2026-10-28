"""Receive native PGFRAME1 pixels with explicit single-eye identity binding.

Replay is offline and never becomes physical-camera provenance. Live mode only
receives bytes: no UART commands, PDS, JTAG, downloads or automatic idle helpers.
PGFRAME1 does not carry camera identity; operator connection declarations and
file hashes are preserved separately from on-wire CRC verification.
"""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import hashlib
import json
import math
import re
import sys
import time
import zlib

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from frame_protocol import FrameParser
from camera_eye_pin_audit import audit_pin_map

cv2.setNumThreads(1)
cv2.ocl.setUseOpenCL(False)
IDENTITY_FIELDS = ('camera_id', 'lens_id', 'profile_id', 'capture_mode_id', 'eye')
CONNECTION_FIELDS = ('new_module_pinout_verified', 'power_and_io_verified',
                     'selected_eye_verified', 'programmed_bound_bitstream')


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b''):
            digest.update(chunk)
    return digest.hexdigest()


def valid_digest(value):
    return isinstance(value, str) and len(value) == 64 and all(c in '0123456789abcdefABCDEF' for c in value)


def load_json(path):
    def invalid_constant(value):
        raise ValueError('nonfinite JSON value: '+value)
    return json.loads(Path(path).read_text(encoding='utf-8-sig'), parse_constant=invalid_constant)


def safe_label(value, name):
    if not isinstance(value, str) or not value or len(value) > 100 or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_' for c in value):
        raise ValueError(name+' must contain 1..100 ASCII letters/digits/hyphens/underscores')
    return value


def validate_binding(binding):
    if not isinstance(binding, dict) or type(binding.get('schema')) is not int or binding['schema'] != 1:
        raise ValueError('binding schema must be integer 1')
    identity = {}
    for name in IDENTITY_FIELDS:
        value = binding.get(name)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(name+' must explicitly identify this camera/lens/mode')
        identity[name] = value
    if identity['eye'] not in ('CAM1', 'CAM2'):
        raise ValueError('eye must be CAM1 or CAM2 connector signal group, not a guessed left/right')
    size = binding.get('image_size')
    if not isinstance(size, list) or len(size) != 2 or any(type(v) is not int for v in size) or not 1 <= size[0] <= 1920 or not 1 <= size[1] <= 1080:
        raise ValueError('image_size must fit the current PGFRAME1 contract: 1..1920 x 1..1080')
    if binding.get('pixel_format') != 'RGB565_LE':
        raise ValueError('only the verified native RGB565_LE wire format is accepted')
    return identity


def _bound_file(record, label, base):
    if not isinstance(record, dict) or not isinstance(record.get('path'), str) or not valid_digest(record.get('sha256')):
        raise ValueError(label+' requires path and explicit SHA256')
    path = Path(record['path'])
    path = path if path.is_absolute() else Path(base)/path
    path = path.resolve()
    if not path.is_file() or sha(path) != record['sha256'].lower():
        raise ValueError(label+' is missing or SHA256 differs')
    return path


def validate_live_binding(binding, *, base_dir, require_programmed=True):
    if type(require_programmed) is not bool:
        raise ValueError('require_programmed must be a boolean stage selector')
    identity = validate_binding(binding)
    review = binding.get('connection_review', {})
    required_reviews = CONNECTION_FIELDS if require_programmed else CONNECTION_FIELDS[:-1]
    if not isinstance(review, dict) or any(review.get(name) is not True for name in required_reviews):
        raise ValueError('live receive requires explicit new-module electrical/pinout/eye/programming review declarations')
    files = binding.get('build_binding', {})
    manifest_path = _bound_file(files.get('validated_build'), 'validated_build', base_dir)
    bitstream = _bound_file(files.get('bitstream'), 'bitstream', base_dir)
    pins_path = _bound_file(files.get('pinout'), 'pinout', base_dir)
    timing_path = _bound_file(files.get('timing_report'), 'timing_report', base_dir)
    manifest = load_json(manifest_path)
    if str(manifest.get('SHA256', '')).lower() != sha(bitstream):
        raise ValueError('bitstream does not match the validated-build SHA256')
    timing_text = timing_path.read_text(encoding='utf-8', errors='replace')
    timing_pass = re.search(r'(?m)^\s*(?:Design Summary\s*:\s*)?All Constraints Met\.?\s*$', timing_text)
    if str(manifest.get('TimingSHA256', '')).lower() != sha(timing_path) or not timing_pass:
        raise ValueError('final timing report is not hash-bound or does not meet all constraints')
    contract = manifest.get('RawCaptureContract')
    expected_contract = {'protocol': 'PGFRAME1', 'payload_role': 'native_raw',
                         'geometry_applied': False, 'image_size': binding['image_size']}
    if contract != expected_contract:
        raise ValueError('build lacks the bound raw-only native capture contract for this mode')
    sources = manifest.get('SourceSHA256')
    if not isinstance(sources, dict) or not sources:
        raise ValueError('a source-bound validated build is required')
    for name, expected in sources.items():
        source = (ROOT/name).resolve()
        if not source.is_relative_to(ROOT) or not source.is_file() or not valid_digest(expected) or sha(source) != expected.lower():
            raise ValueError('bound build source is missing, changed or escapes project: '+str(name))
    pins = load_json(pins_path)
    pin_audit = audit_pin_map(pins, identity['eye'])
    if not pin_audit['passed']:
        raise ValueError('pinout differs from selected board-side eye reference; new mapping requires a reviewed adapter path')
    if not any((ROOT/name).resolve() == pins_path for name in sources):
        raise ValueError('pinout JSON is not bound in validated-build source hashes')
    return {'validated_build': str(manifest_path), 'validated_build_sha256': sha(manifest_path),
            'bitstream_sha256': sha(bitstream), 'pinout_sha256': sha(pins_path),
            'timing_report_sha256': sha(timing_path), 'raw_capture_contract': contract,
            'bound_source_count': len(sources), 'selected_eye': identity['eye'],
            'programmed_bitstream_review_required': require_programmed,
            'actual_programming_and_connection_independently_observed': False,
            'limits': 'File hashes and explicit operator review declarations only; this tool does not identify which firmware is currently on the FPGA or inspect connector voltages.'}


def png_from_rgb565(payload, width, height):
    pixels = np.frombuffer(payload, dtype='<u2').reshape(height, width)
    red, green, blue = (pixels >> 11) & 31, (pixels >> 5) & 63, pixels & 31
    bgr = np.stack(((blue << 3) | (blue >> 2), (green << 2) | (green >> 4),
                    (red << 3) | (red >> 2)), axis=-1).astype(np.uint8)
    ok, encoded = cv2.imencode('.png', bgr)
    if not ok:
        raise ValueError('PNG encoding failed')
    return encoded.tobytes()


def save_frame(frame, binding, directory, session_id, *, source_kind, build_record=None, replay_record=None):
    identity = validate_binding(binding)
    safe_label(session_id, 'session_id')
    directory = Path(directory).resolve()
    if not directory.is_dir():
        raise ValueError('capture directory must already exist; no directory is created')
    if [frame.width, frame.height] != binding['image_size']:
        raise ValueError('native dimensions differ from bound capture mode')
    if source_kind not in ('physical_native_camera', 'offline_uart_replay'):
        raise ValueError('source_kind must explicitly distinguish live reception from offline replay')
    if source_kind == 'physical_native_camera' and not build_record:
        raise ValueError('live frame requires the validated build/connection binding record')
    if len(frame.payload) != frame.width*frame.height*2 or zlib.crc32(frame.payload) != frame.source_crc:
        raise ValueError('frame payload length or source CRC differs')
    stem = session_id+'-'+identity['eye']+f'-frame{frame.frame_id:010d}'
    raw_path, image_path, metadata_path = [directory/(stem+suffix) for suffix in ('.rgb565', '.png', '.json')]
    if any(path.exists() for path in (raw_path, image_path, metadata_path)):
        raise ValueError('capture files already exist; choose a new session_id, never overwrite evidence')
    encoded = png_from_rgb565(frame.payload, frame.width, frame.height)
    upstream_raw_contract = bool(build_record and build_record.get('raw_capture_contract') == {
        'protocol': 'PGFRAME1', 'payload_role': 'native_raw', 'geometry_applied': False,
        'image_size': binding['image_size']})
    metadata = {'schema': 1, 'received_at_utc': datetime.now(timezone.utc).isoformat(),
        'session_id': session_id, 'source_kind': source_kind, 'frame_id': frame.frame_id,
        'frame_id_kind': 'firmware_capture_transaction_id',
        'frame_id_is_sensor_exposure_counter': False,
        'received_time_is_exposure_time': False,
        'identity_binding': identity, 'identity_binding_kind': 'operator_declared_single_eye_connection',
        'identity_verified_on_wire': False, 'eye_synchronization_verified': False,
        'width': frame.width, 'height': frame.height, 'pixel_format': 'RGB565_LE',
        'geometry_applied': False if upstream_raw_contract else None,
        'geometry_applied_by_receiver': False,
        'upstream_payload_role': 'native_raw' if upstream_raw_contract else 'unknown',
        'upstream_raw_contract_hash_bound': upstream_raw_contract,
        'photometric_processing_applied_by_receiver': False,
        'png_conversion': 'lossless RGB565 bit replication to RGB888; sensor ISP behavior is separate',
        'payload_bytes': len(frame.payload), 'source_crc32': f'{frame.source_crc:08X}',
        'received_crc32': f'{zlib.crc32(frame.payload):08X}',
        'raw_path': str(raw_path), 'raw_sha256': hashlib.sha256(frame.payload).hexdigest(),
        'image_path': str(image_path), 'image_sha256': hashlib.sha256(encoded).hexdigest(),
        'build_binding': build_record, 'replay_source': replay_record,
        'binding_sha256': hashlib.sha256(json.dumps(binding, sort_keys=True, allow_nan=False).encode()).hexdigest(),
        'hardware_accessed': source_kind == 'physical_native_camera',
        'hardware_release_allowed': False,
        'limits': 'PGFRAME1 authenticates pixel integrity with CRC, not sensor identity, raw-versus-corrected role or simultaneous exposures. The selected eye/profile and actual firmware connection are operator declarations. Upstream raw geometry is known only from a hash-bound raw-only build contract, never inferred from CRC. Offline replay defaults to unknown upstream role and never establishes new physical camera data.'}
    # Encode and check all names before writing. The JSON is the final record;
    # incomplete saves retain their files for inspection and are never overwritten.
    for path, data in ((raw_path, frame.payload), (image_path, encoded)):
        with path.open('xb') as stream:
            stream.write(data)
    with metadata_path.open('x', encoding='utf-8') as stream:
        stream.write(json.dumps(metadata, indent=2, ensure_ascii=False, allow_nan=False)+'\n')
    return {'metadata_path': str(metadata_path), 'metadata_sha256': sha(metadata_path), **metadata}


def receive_chunks(chunks, binding, directory, session_id, *, frames=1, source_kind='offline_uart_replay',
                   build_record=None, replay_record=None):
    validate_binding(binding)
    if type(frames) is not int or not 1 <= frames <= 10000:
        raise ValueError('frames must be an integer in [1,10000]')
    parser, saved, seen = FrameParser(), [], set()
    for data in chunks:
        for frame in parser.feed(data):
            if frame.frame_id in seen:
                raise ValueError('duplicate on-wire frame_id within one capture session')
            seen.add(frame.frame_id)
            saved.append(save_frame(frame, binding, directory, session_id, source_kind=source_kind,
                build_record=build_record, replay_record=replay_record))
            if len(saved) >= frames:
                break
        if len(saved) >= frames:
            break
    return {'schema': 1, 'passed': len(saved) == frames and parser.rejected == 0,
        'expected_frames': frames, 'saved_frames': len(saved), 'frames': saved,
        'rejected_packets': parser.rejected, 'discarded_stream_bytes': parser.discarded,
        'remaining_parser_bytes': len(parser.buffer), 'source_kind': source_kind,
        'hardware_accessed': source_kind == 'physical_native_camera', 'hardware_release_allowed': False,
        'incomplete_or_timed_out': len(saved) != frames,
        'synchronization_verified': False, 'identity_verified_on_wire': False,
        'limits': 'Complete CRC-valid packets can be retained after corrupt input, but the session does not pass if any packet was rejected. No frame is sent to a calibration model automatically.'}


def file_chunks(path):
    with Path(path).open('rb') as stream:
        for data in iter(lambda: stream.read(65536), b''):
            yield data


def serial_chunks(port_name, baud, seconds):
    # Import and open only after live metadata, evidence and output checks pass.
    import serial
    port = serial.Serial(port=None, baudrate=baud, timeout=.25, write_timeout=1,
                         dsrdtr=False, rtscts=False, xonxoff=False)
    port.dtr, port.rts, port.port = False, False, port_name
    try:
        port.open()
        if hasattr(port, 'set_buffer_size'):
            port.set_buffer_size(rx_size=1048576, tx_size=4096)
        deadline = time.monotonic()+seconds
        while time.monotonic() < deadline:
            yield port.read(min(max(port.in_waiting, 1), 65536))
    finally:
        port.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--replay', type=Path)
    source.add_argument('--port')
    parser.add_argument('--binding', type=Path, required=True)
    parser.add_argument('--directory', type=Path, required=True, help='existing approved capture directory')
    parser.add_argument('--session-id', required=True)
    parser.add_argument('--frames', type=int, default=1)
    parser.add_argument('--baud', type=int, default=921600)
    parser.add_argument('--seconds', type=float, default=90.)
    parser.add_argument('--summary', type=Path, required=True, help='new JSON file in an existing directory')
    args = parser.parse_args()
    if not args.directory.is_dir() or not args.summary.parent.is_dir() or args.summary.exists():
        parser.error('capture/summary parents must already exist and summary must be a new filename')
    if not 1 <= args.frames <= 10000 or args.baud <= 0 or not math.isfinite(args.seconds) or args.seconds <= 0:
        parser.error('positive finite capture limits and frames<=10000 are required')
    safe_label(args.session_id, 'session_id')
    original_binding_sha = sha(args.binding)
    binding = load_json(args.binding)
    validate_binding(binding)
    build_record, replay_record = None, None
    if args.replay:
        replay_record = {'path': str(args.replay.resolve()), 'sha256': sha(args.replay)}
        chunks = file_chunks(args.replay)
        kind = 'offline_uart_replay'
    else:
        build_record = validate_live_binding(binding, base_dir=args.binding.parent)
        chunks, kind = serial_chunks(args.port, args.baud, args.seconds), 'physical_native_camera'
    try:
        result = receive_chunks(chunks, binding, args.directory, args.session_id, frames=args.frames,
            source_kind=kind, build_record=build_record, replay_record=replay_record)
    finally:
        if hasattr(chunks, 'close'):
            chunks.close()
    result['binding_file_sha256'] = original_binding_sha
    result['binding_unchanged_during_capture'] = sha(args.binding) == original_binding_sha
    result['passed'] &= result['binding_unchanged_during_capture']
    result['source_sha256'] = {str(path.relative_to(ROOT)): sha(path) for path in
        (Path(__file__), ROOT/'tools/frame_protocol.py', ROOT/'tools/camera_eye_pin_audit.py')}
    with args.summary.open('x', encoding='utf-8') as stream:
        stream.write(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False)+'\n')
    print(json.dumps({key: result[key] for key in ('passed', 'saved_frames', 'rejected_packets', 'source_kind', 'hardware_accessed')}))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
