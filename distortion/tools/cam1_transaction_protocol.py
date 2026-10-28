"""Offline decoder for the fixed register-only PGCAMD01 target, never PGFRAME1."""
from pathlib import Path
import argparse
import hashlib
import json
import struct
import zlib

MAGIC = b'PGCAMD01'
TRAILER = b'CD01'
SIZE = 64
DIAG_NAMES = ('write_issued', 'write_completed', 'final_data_noack', 'noack_pending',
              'read_issued', 'read_completed', 'read_value_valid', 'read_equal')


def decode(packet):
    if len(packet) != SIZE or packet[:8] != MAGIC or packet[60:] != TRAILER:
        raise ValueError('wrong diagnostic packet size/magic/trailer')
    if packet[8:12] != bytes((1, 64, 1, 0)) or any(packet[50:56]):
        raise ValueError('wrong fixed version/variant or reserved bytes')
    if zlib.crc32(packet[:56]) != struct.unpack_from('<I', packet, 56)[0]:
        raise ValueError('diagnostic CRC32 differs')
    u16 = lambda offset: struct.unpack_from('<H', packet, offset)[0]
    u32 = lambda offset: struct.unpack_from('<I', packet, offset)[0]
    if (u16(37), u16(39)) != (0x7ff0, 68):
        raise ValueError('diagnostic target must retain full7FF0 and quarter68')
    row = dict(sensor_id=u16(12), camera_error=packet[14], failed_address=u16(16),
        completed_writes=u16(18), verified_write_noacks=u16(20), observed_value=packet[22],
        expected_value=packet[23], write_bus_error=packet[24], read_bus_error=packet[25],
        read_value=packet[26], camera_ready=bool(packet[27] & 1),
        camera_failed=bool(packet[27] & 2), probe_done=bool(packet[27] & 4),
        probes_enabled=bool(packet[27] & 8), probe_attempted=packet[28],
        probe_completed=packet[29], probe_valid=packet[30], probe_count=packet[31],
        pad_mask=u16(37), quarter_cycles=u16(39), uptime_ms=u32(41), snapshot_seq=u32(45),
        sampled_scl=bool(packet[49] & 1), sampled_sda=bool(packet[49] & 2),
        sampled_reset=bool(packet[49] & 4), crc32=f'{u32(56):08X}')
    row.update({name: bool(packet[15] & (1 << bit)) for bit, name in enumerate(DIAG_NAMES)})
    errors = u16(32)
    row['probes'] = [{'address': address, 'attempted': bool(packet[28] & (1 << index)),
        'completed': bool(packet[29] & (1 << index)), 'value_valid': bool(packet[30] & (1 << index)),
        'bus_error': (errors >> (4*index)) & 15, 'value': packet[34+index]}
        for index, address in enumerate((0x300a, 0x300b, 0x3018))]
    if (packet[27] & 0xf0 or any(value & ~7 for value in packet[28:31])
            or packet[31] > 3 or errors > 0xfff or packet[49] > 7
            or row['write_bus_error'] > 15 or row['read_bus_error'] > 15
            or row['completed_writes'] > 511 or row['verified_write_noacks'] > 511):
        raise ValueError('out-of-range diagnostic field or reserved bits')
    if not row['probes_enabled']:
        raise ValueError('this fixed diagnostic target requires bounded probes enabled')
    for stage in ('write', 'read'):
        if row[stage+'_completed'] and not row[stage+'_issued']:
            raise ValueError('completed transaction lacks an issued transaction')
    if row['final_data_noack'] != (row['write_completed'] and row['write_bus_error'] == 4):
        raise ValueError('final-data-high observation differs from the raw write bus error')
    if row['noack_pending'] and not row['final_data_noack']:
        raise ValueError('pending noack lacks its raw write observation')
    if row['read_value_valid'] != (row['read_completed'] and row['read_bus_error'] == 0):
        raise ValueError('read value validity differs from the completed read bus result')
    # The global last-readback expected byte advances after3018 (e.g.4740=23).
    # The separately retained3018 observation must use its fixed pad-mask byte.
    row['read_expected_value'] = row['pad_mask'] & 255
    if row['read_equal'] != (row['read_value_valid'] and row['read_value'] == row['read_expected_value']):
        raise ValueError('read equality cannot override invalid/error read data')
    if row['read_equal'] and row['noack_pending']:
        raise ValueError('matching valid readback must clear pending noack')
    if row['noack_pending'] != (row['final_data_noack'] and not row['read_equal']):
        raise ValueError('only the original valid matching readback may clear pending noack')
    if (row['probe_completed'] & ~row['probe_attempted'] or row['probe_valid'] & ~row['probe_completed']
            or row['probe_count'] != row['probe_completed'].bit_count()):
        raise ValueError('probe completion/validity/count lacks its bounded request')
    if any(probe['value_valid'] != (probe['completed'] and probe['bus_error'] == 0) for probe in row['probes']):
        raise ValueError('probe value validity differs from its own bus result')
    if row['probe_done'] != (row['probe_count'] == 3 and row['probe_completed'] == 7):
        raise ValueError('probe completion requires exactly the three fixed reads')
    if row['probe_attempted'] and not row['camera_failed']:
        raise ValueError('extra reads must follow a retained initialization failure')
    if row['camera_ready'] and (row['camera_failed'] or row['camera_error'] or row['sensor_id'] != 0x5640):
        raise ValueError('camera ready conflicts with the retained first fault or model ID')
    return row


def audit_wire(data):
    start = data.find(MAGIC)
    if not 0 <= start < SIZE:
        raise ValueError('no diagnostic packet within one opening boundary fragment')
    rows = []
    offset = start
    while len(data)-offset >= SIZE:
        row = decode(data[offset:offset+SIZE])
        if rows:
            previous = rows[-1]
            delta = (row['snapshot_seq']-previous['snapshot_seq']) & 0xffffffff
            if not 0 < delta < 0x80000000 or row['uptime_ms'] < previous['uptime_ms']:
                raise ValueError('diagnostic sequence replay/regression')
            if previous['camera_failed']:
                frozen = ('sensor_id', 'camera_error', 'failed_address', 'completed_writes',
                    'verified_write_noacks', 'observed_value', 'expected_value', 'write_bus_error',
                    'read_bus_error', 'read_value', *DIAG_NAMES)
                if row['camera_ready'] or not row['camera_failed'] or any(row[key] != previous[key] for key in frozen):
                    raise ValueError('later probes cannot clear or replace the retained initialization fault')
            if (previous['probe_attempted'] & ~row['probe_attempted']
                    or previous['probe_completed'] & ~row['probe_completed']):
                raise ValueError('bounded probe requests/completions cannot regress')
            for old, current in zip(previous['probes'], row['probes']):
                if old['completed'] and old != current:
                    raise ValueError('completed probe evidence must remain held')
        rows.append(row)
        offset += SIZE
    trailing = data[offset:]
    if trailing and not (MAGIC.startswith(trailing) if len(trailing) < len(MAGIC) else trailing.startswith(MAGIC)):
        raise ValueError('unrelated bytes inside/after diagnostic stream')
    if not rows:
        raise ValueError('no complete diagnostic packet')
    return {'schema': 1, 'source_kind': 'camera_transaction_diagnostic',
        'diagnostic_transport_passed': True, 'packets': len(rows), 'leading_partial_bytes': start,
        'trailing_partial_bytes': len(trailing), 'wire_bytes': len(data),
        'wire_sha256': hashlib.sha256(data).hexdigest(), 'first': rows[0], 'last': rows[-1],
        'statuses': rows, 'hardware_accessed_by_decoder': False, 'raw_frame_certified': False,
        'hardware_cause_established': False, 'physical_eye_or_voltage_verified': False,
        'limits': 'CRC and digital snapshots only. Invalid read/probe bytes are not register values. '
        'A final write-data high is pending until exact valid readback; the old verified counter is separate. '
        'A recovered later probe never clears the retained first fault or certifies native input. '
        'Sampled pads are digital thresholds at packet snapshot time, not waveforms or voltage measurements.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--wire', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if not args.output.parent.is_dir() or args.output.exists():
        parser.error('output must be a fresh file in an existing directory')
    result = audit_wire(args.wire.read_bytes())
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps({'packets': result['packets'], 'transport_passed': True,
        'camera_ready': result['last']['camera_ready'], 'camera_error': result['last']['camera_error']}))


if __name__ == '__main__':
    main()
