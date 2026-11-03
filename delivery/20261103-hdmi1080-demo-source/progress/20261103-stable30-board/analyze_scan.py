"""Analyze existing PGSIG001 UART bytes without opening a serial port.

Rates use the supplied wall-clock capture window. They measure complete digital
scan records and new displayed IDs, not internal processing rate or latency.
"""
from pathlib import Path
import argparse
import hashlib
import json
import math
import struct
import zlib

MAGIC = b'PGSIG001'


def decode(blob):
    records, errors = [], []
    offset = 0
    while True:
        at = blob.find(MAGIC, offset)
        if at < 0:
            break
        packet = blob[at:at + 128]
        if len(packet) < 128:
            # A fixed host window can end partway through its final packet.
            return records, errors, len(packet)
        offset = at + 1
        if packet[8:15] != b'\x01\x02\x01\x01\x80\x00\x08' or packet[124:] != b'SG01':
            errors.append({'offset': at, 'error': 'header_or_tail'})
            continue
        if zlib.crc32(packet[:120]) != struct.unpack_from('<I', packet, 120)[0]:
            errors.append({'offset': at, 'error': 'packet_crc'})
            continue
        words = struct.unpack_from('<10I', packet, 16)
        record = dict(zip(('session', 'epoch', 'frame_id', 'param_id', 'sequence', 'pixels',
                           'scan_crc', 'dropped', 'aborted', 'malformed'), words))
        record.update(width=struct.unpack_from('<H', packet, 56)[0],
                      height=struct.unpack_from('<H', packet, 58)[0],
                      mask=packet[60], mode=packet[61], bank=packet[15])
        records.append(record)
        offset = at + 128
    return records, errors, 0


def analyze(blob, seconds, param_id, session_id, width=1920, height=1080):
    if not math.isfinite(seconds) or seconds <= 0 or not 0 < session_id <= 0xffffffff:
        raise ValueError('Positive finite capture seconds and nonzero session ID required')
    if not 0 <= param_id <= 0xffffffff or width < 4 or height < 4:
        raise ValueError('Invalid identity or geometry')
    records, decode_errors, trailing_bytes = decode(blob)
    issues = list(decode_errors)
    seen, repeat = {}, 0
    sequence_gaps = epoch_gaps = 0
    previous = None
    for index, r in enumerate(records):
        def issue(name):
            issues.append({'record': index, 'error': name})
        if r['param_id'] != param_id or r['session'] != session_id:
            issue('identity_mismatch')
        if r['mode'] != 1:
            issue('requires_fixed_correction_gamma_off')
        if (r['width'], r['height'], r['pixels'], r['mask'], r['bank']) not in (
                (width, height, width * height, 255, 0),
                (width, height, width * height, 255, 1)):
            issue('geometry_or_sample_mask')
        if r['frame_id'] == 0:
            issue('zero_frame_id')
        if any(r[name] for name in ('dropped', 'aborted', 'malformed')):
            issue('firmware_observer_error')
        if previous is not None:
            seq_delta = (r['sequence'] - previous['sequence']) & 0xffffffff
            epoch_delta = (r['epoch'] - previous['epoch']) & 0xffffffff
            if seq_delta != 1:
                sequence_gaps += 1
                issue('signature_sequence_gap_or_duplicate')
            if epoch_delta != 1:
                epoch_gaps += 1
                issue('scan_epoch_gap_or_duplicate')
            if r['frame_id'] < previous['frame_id']:
                issue('frame_id_decrease_or_wrap_use_new_window')
        if r['frame_id'] in seen:
            repeat += 1
            if seen[r['frame_id']] != r['scan_crc']:
                issue('repeated_frame_crc_changed')
        else:
            seen[r['frame_id']] = r['scan_crc']
        previous = r
    if len(records) < 2:
        issues.append({'error': 'need_at_least_two_complete_records'})
    good = not issues
    return {
        'schema': 'hdmi1080-pure-correction-scan-v1',
        'input_sha256': hashlib.sha256(blob).hexdigest(),
        'capture_seconds': seconds, 'expected_param_id_hex': f'{param_id:08x}',
        'expected_session_id_hex': f'{session_id:08x}',
        'complete_scan_records': len(records), 'distinct_frame_ids': len(seen),
        'repeat_scan_records': repeat,
        'observed_scan_records_per_second': len(records) / seconds,
        'observed_distinct_ids_per_second': len(seen) / seconds,
        'repeat_fraction': repeat / len(records) if records else None,
        'valid_fixed_correction_window': good,
        'accepted_unique_display_fps': len(seen) / seconds if good else None,
        'signature_sequence_gap_events': sequence_gaps, 'scan_epoch_gap_events': epoch_gaps,
        'trailing_partial_packet_bytes': trailing_bytes,
        'issues': issues,
        'scope': 'Host-window complete digital scans; processing FPS and end-to-end latency are unmeasured.',
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('binary', type=Path)
    parser.add_argument('--seconds', required=True, type=float)
    parser.add_argument('--param-id', required=True, type=lambda x: int(x, 16))
    parser.add_argument('--session-id', required=True, type=lambda x: int(x, 16))
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = analyze(args.binary.read_bytes(), args.seconds, args.param_id, args.session_id)
    text = json.dumps(result, indent=2) + '\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding='utf-8')
    print(text, end='')
    raise SystemExit(0 if result['valid_fixed_correction_window'] else 1)
