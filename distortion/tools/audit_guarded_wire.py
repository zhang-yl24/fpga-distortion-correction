"""Strict independent sealed-wire audit for PGSTAT02 plus native PGFRAME1.

Does not import the live controller or its stream parser, open a port, or infer
physical provenance from CRC. Only boundary fragments can be omitted; arbitrary
bytes between complete packets and corrupt packets are retained as failures.
"""
from pathlib import Path
import argparse
import hashlib
import json
import struct
import zlib

STATUS_MAGIC = b'PGSTAT02'
FRAME_MAGIC = b'PGFRAME1'
FIELDS = {
    'build_tag': (12, 4), 'uptime_ms': (16, 4), 'session_id': (20, 4),
    'received_seq': (24, 2), 'accepted_seq': (26, 2), 'opcode': (28, 1), 'result': (29, 1),
    'flags': (30, 2), 'accepted_count': (32, 4), 'rejected_count': (36, 4),
    'duplicate_count': (40, 4), 'rx_error_count': (44, 4), 'admitted_frames': (48, 4),
    'completed_frames': (52, 4), 'remaining_frames': (56, 4), 'remaining_cycles': (60, 4),
    'held_frame_id': (64, 4), 'source_crc': (68, 4), 'written_beats': (72, 4),
    'temp_raw': (76, 2), 'temp_code': (78, 2), 'temp_age_27m': (80, 4),
    'temp_samples': (84, 4), 'temp_conversions': (88, 4), 'sensor_id': (92, 2),
    'camera_error': (94, 1), 'raw_fault': (95, 1), 'camera_failed_address': (96, 2),
    'camera_observed': (98, 1), 'camera_expected': (99, 1), 'camera_writes': (100, 2),
    'camera_noacks': (102, 2), 'stop_reason': (104, 1), 'raw_state': (105, 1),
    'adc_fault': (106, 1), 'adc_alarm': (107, 1), 'snapshot_seq': (108, 4),
    'safety_snapshot_age_core': (112, 4), 'requested_frames': (116, 2), 'lease_ms': (118, 2),
}


def _num(data, at, length):
    return int.from_bytes(data[at:at+length], 'little')


def status_packet(packet, expected_tag=0x52473201):
    if (len(packet) != 128 or packet[:8] != STATUS_MAGIC or packet[124:] != b'ST02' or
            _num(packet, 8, 2) != 128 or _num(packet, 10, 2) != 2):
        raise ValueError('status magic, version, length or end marker differs')
    if zlib.crc32(packet[:120]) != _num(packet, 120, 4):
        raise ValueError('status CRC32 differs')
    result = {name: _num(packet, *location) for name, location in FIELDS.items()}
    if result['build_tag'] != expected_tag:
        raise ValueError('status build tag differs from selected connector target')
    flags = result['flags']
    ready = flags & 15 == 15
    if ready:
        if (result['sensor_id'] != 0x5640 or not flags & (1 << 10) or
                flags & ((1 << 7) | (1 << 8) | (1 << 11) | (1 << 12) | (1 << 13) | (1 << 14)) or
                result['adc_fault'] or result['adc_alarm'] or result['camera_error'] or
                result['temp_raw'] >> 4 != result['temp_code'] or
                not 1913 <= result['temp_code'] <= 2732 or result['temp_age_27m'] >= 54000000 or
                result['safety_snapshot_age_core'] >= 125000000):
            raise ValueError('ready status contradicts reported sensor/temperature/fault evidence')
    result['resource_readiness_fields_consistent'] = ready
    result['packet_crc32'] = f'{zlib.crc32(packet[:120]):08X}'
    return result


def audit_bytes(data, *, expected_size=(640, 480), expected_tag=0x52473201):
    if not isinstance(data, bytes) or len(data) > 64*1024*1024:
        raise ValueError('sealed wire must be bytes within the finite 64MiB audit bound')
    starts = [at for magic in (STATUS_MAGIC, FRAME_MAGIC) if (at := data.find(magic)) >= 0]
    if not starts:
        raise ValueError('no complete packet magic in received wire')
    position = leading = min(starts)
    statuses, frames, order = [], [], []
    partial = None
    while position < len(data):
        rest = data[position:]
        if len(rest) < 8 and any(magic.startswith(rest) for magic in (STATUS_MAGIC, FRAME_MAGIC)):
            # A shared short prefix (e.g. PG) cannot exclude a new raw frame.
            partial = {'type': 'raw_header' if FRAME_MAGIC.startswith(rest) else 'status', 'bytes': len(rest)}
            break
        if rest.startswith(STATUS_MAGIC):
            if len(rest) < 128:
                partial = {'type': 'status', 'bytes': len(rest)}
                break
            value = status_packet(rest[:128], expected_tag)
            value['wire_offset'] = position
            if statuses:
                previous = statuses[-1]
                delta = (value['snapshot_seq']-previous['snapshot_seq']) & 0xffffffff
                if not 0 < delta < 0x80000000 or value['uptime_ms'] < previous['uptime_ms']:
                    raise ValueError('status snapshot sequence/uptime did not advance monotonically')
                for name in ('accepted_count', 'rejected_count', 'duplicate_count', 'rx_error_count', 'completed_frames'):
                    if value[name] < previous[name]:
                        raise ValueError('status counter regressed within one configured run: '+name)
            statuses.append(value)
            order.append({'type': 'status', 'offset': position, 'snapshot_seq': value['snapshot_seq']})
            position += 128
        elif rest.startswith(FRAME_MAGIC):
            if len(rest) < 32:
                partial = {'type': 'raw_header', 'bytes': len(rest)}
                break
            magic, width, height, frame_id, count, source_crc, fmt, header_crc = struct.unpack('<8sHHIIIII', rest[:32])
            if ((width, height) != tuple(expected_size) or not 0 < width <= 1920 or not 0 < height <= 1080 or
                    count != width*height*2 or fmt != 0x5651 or zlib.crc32(rest[:28]) != header_crc):
                raise ValueError('raw dimensions/format/length/header CRC differ')
            total = 44+count
            if len(rest) < total:
                partial = {'type': 'raw_payload', 'bytes': len(rest), 'expected_bytes': total}
                break
            payload = rest[32:32+count]
            crc = zlib.crc32(payload)
            if rest[32+count:40+count] != b'PGEND001' or _num(rest, 40+count, 4) != crc or source_crc != crc:
                raise ValueError('raw payload/source/trailer CRC differs')
            if frames and frame_id <= frames[-1]['frame_id']:
                raise ValueError('duplicate or regressed raw transaction ID')
            frames.append({'wire_offset': position, 'frame_id': frame_id, 'width': width, 'height': height,
                'payload_bytes': count, 'source_crc32': f'{crc:08X}', 'payload_sha256': hashlib.sha256(payload).hexdigest()})
            order.append({'type': 'raw', 'offset': position, 'frame_id': frame_id})
            position += total
        else:
            raise ValueError('unframed bytes between complete packets at offset '+str(position))
    if not statuses:
        raise ValueError('no complete status snapshot; cannot assess authorization state')
    return {'schema': 1, 'complete_packets_verified': True, 'wire_bytes': len(data), 'wire_sha256': hashlib.sha256(data).hexdigest(),
        'leading_boundary_bytes_unverified': leading, 'trailing_partial_packet': partial,
        'raw_transport_complete': not partial or partial['type'] not in ('raw_header', 'raw_payload'),
        'status_packets': len(statuses), 'raw_frames': len(frames), 'statuses': statuses, 'frames': frames,
        'packet_order': order, 'hardware_accessed_by_auditor': False, 'physical_provenance_verified_by_auditor': False,
        'limits': 'Only sealed byte structure, CRC and counter consistency. Leading/trailing fragments are not certified. A separate source-bound programming and TX/ACK/scenario receipt is required for hardware behavior, identity, geometry role, temperature policy or lease/stop claims.'}


def check_scenario(result, scenario):
    statuses, frames = result['statuses'], result['frames']
    last = statuses[-1]
    if scenario in ('boot-idle', 'idle', 'negative-commands'):
        if frames or any(status['admitted_frames'] or status['completed_frames'] or
                         status['remaining_frames'] or status['flags'] & (1 << 4) for status in statuses):
            raise ValueError('unauthorized frame/admission/budget observed in idle scenario')
        if not any(status['resource_readiness_fields_consistent'] and status['flags'] & (1 << 15) for status in statuses):
            raise ValueError('idle scenario lacks a ready, fully idle observation; absent input could hide auto-capture')
        if scenario == 'negative-commands':
            expected = {'accepted_count': 8, 'rejected_count': 4, 'rx_error_count': 2,
                        'duplicate_count': 0, 'received_seq': 10, 'accepted_seq': 10,
                        'opcode': 0x12, 'result': 1, 'remaining_cycles': 0, 'stop_reason': 0}
            if (any(last[key] != value for key, value in expected.items()) or not last['session_id']
                    or any(status['flags'] & sum(1 << bit for bit in range(4,10)) for status in statuses)):
                raise ValueError('fixed negative-command counters/sequence or idle ownership differ')
    elif scenario in ('capture', 'duplicate-grant', 'lease-expiry', 'stop-drain', 'host-silence'):
        if len(frames) != 1 or not result['raw_transport_complete']:
            raise ValueError('single-frame scenario did not retain exactly one complete raw frame')
        if not any(status['resource_readiness_fields_consistent'] and status['wire_offset'] < frames[0]['wire_offset'] for status in statuses):
            raise ValueError('need resource-ready status before the retained frame')
        if last['flags'] & ((1 << 4) | (1 << 5) | (1 << 6) | (1 << 7) | (1 << 8) | (1 << 9)):
            raise ValueError('final status does not show drained, fault-free ownership')
        if last['admitted_frames'] != 1 or last['completed_frames'] != 1:
            raise ValueError('final board frame counters do not match one frame')
        if not any(item['type'] == 'status' and item['offset'] > frames[-1]['wire_offset'] for item in result['packet_order']):
            raise ValueError('need a status snapshot after the retained frame')
        expected_reason = {'capture': 1, 'duplicate-grant': 1, 'lease-expiry': 2, 'host-silence': 2, 'stop-drain': 3}
        if scenario in expected_reason and last['stop_reason'] != expected_reason[scenario]:
            raise ValueError('final stop reason differs from selected scenario')
        if scenario == 'duplicate-grant' and last['duplicate_count'] <= statuses[0]['duplicate_count']:
            raise ValueError('duplicate-grant scenario has no observed duplicate counter progress')
        if scenario in ('lease-expiry', 'host-silence') and (last['remaining_cycles'] or last['remaining_frames'] != 1):
            raise ValueError('short two-frame lease did not expire with one unadmitted frame')
    else:
        raise ValueError('unknown finite audit scenario')
    return {'scenario': scenario, 'counter_and_packet_checks_passed': True,
        'tx_ack_timing_independently_verified': False,
        'limits': 'Scenario RX consistency only; audit the retained transmitted packets and programming receipt separately. QUERY not renewing a lease requires sufficiently late/repeated queries, not only one early query.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--wire', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--scenario', choices=('boot-idle', 'idle', 'capture', 'duplicate-grant', 'lease-expiry', 'stop-drain', 'host-silence', 'negative-commands'))
    parser.add_argument('--eye', choices=('CAM1', 'CAM2'), default='CAM2')
    parser.add_argument('--mode', choices=('native-scene', 'sensor-internal-bars'), default='native-scene')
    parser.add_argument('--sccb-profile', choices=('baseline', '25khz-trial'), default='baseline')
    parser.add_argument('--other-reset-profile', choices=('not-controlled', 'hold-cam2-low'), default='not-controlled')
    args = parser.parse_args()
    if args.mode == 'sensor-internal-bars' and args.eye != 'CAM2':
        parser.error('the validated sensor-bars target is CAM2 only')
    if args.sccb_profile == '25khz-trial' and (args.eye != 'CAM1' or args.mode != 'native-scene'):
        parser.error('the SCCB25 trial is the explicit CAM1 natural-input target only')
    if args.other_reset_profile == 'hold-cam2-low' and (args.eye != 'CAM1' or
            args.mode != 'native-scene' or args.sccb_profile != 'baseline'):
        parser.error('holding CAM2 reset is the explicit baseline-SCCB CAM1 natural-input target only')
    if not args.output.parent.is_dir() or args.output.exists():
        parser.error('output must be new in an existing directory')
    expected_tag = (0x52473149 if args.other_reset_profile == 'hold-cam2-low' else
                    0x52473125 if args.sccb_profile == '25khz-trial' else
                    0x52473242 if args.mode == 'sensor-internal-bars' else
                    0x52473201 if args.eye == 'CAM2' else 0x52473101)
    result = audit_bytes(args.wire.read_bytes(), expected_tag=expected_tag)
    result['input_mode'] = args.mode
    result['declared_sccb_profile'] = args.sccb_profile
    result['other_sensor_reset_control_intent'] = args.other_reset_profile
    result['physical_other_sensor_reset_state_verified'] = False
    result['excluded_from_calibration_by_input_mode'] = args.mode == 'sensor-internal-bars'
    result['wire_path'] = str(args.wire.resolve())
    if args.scenario:
        result['scenario_audit'] = check_scenario(result, args.scenario)
    result['auditor_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    with args.output.open('x', encoding='utf-8') as stream:
        stream.write(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'status_packets': result['status_packets'], 'raw_frames': result['raw_frames'],
                      'raw_transport_complete': result['raw_transport_complete']}))


if __name__ == '__main__':
    main()
