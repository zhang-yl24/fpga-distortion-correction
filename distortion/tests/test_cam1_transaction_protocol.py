import importlib.util
from pathlib import Path
import struct
import binascii

import pytest

PATH = Path(__file__).resolve().parents[1]/'tools/cam1_transaction_protocol.py'
spec = importlib.util.spec_from_file_location('cam1_transaction_protocol', PATH)
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)


def packet(*, seq=1, write_error=4, read_error=1, mismatch=False, recovered=False):
    # Independently assemble the frozen 64-byte wire layout; no production encoder.
    b = bytearray(64)
    b[:12] = b'PGCAMD01\x01\x40\x01\x00'
    struct.pack_into('<H', b, 12, 0x5640)
    b[14] = 0x70 if mismatch else 0x61
    b[15] = 0x3f if write_error == 4 else 0x33
    if read_error == 0:
        b[15] |= 0x40
    struct.pack_into('<HHH', b, 16, 0x3018, 262, 0)
    b[23:27] = bytes((0xf0, write_error, read_error, 0 if read_error else 0xef))
    b[27:32] = bytes((14, 7, 7, 7 if recovered else 0, 3))
    struct.pack_into('<H', b, 32, 0 if recovered else 0x111)
    b[34:37] = bytes((0x56, 0x40, 0xf0)) if recovered else bytes(3)
    struct.pack_into('<HHII', b, 37, 0x7ff0, 68, 500*seq, seq)
    b[49] = 7
    b[60:] = b'CD01'
    return seal(b)


def seal(b):
    struct.pack_into('<I', b, 56, binascii.crc32(b[:56]))
    return bytes(b)


def successful_packet(write_noack=False, seq=1):
    b = bytearray(packet(seq=seq))
    b[14] = 0
    b[15] = 0xf7 if write_noack else 0xf3
    struct.pack_into('<HHH', b, 16, 0, 264, int(write_noack))
    b[22:27] = bytes((0x23, 0x23, 4 if write_noack else 0, 0, 0xf0))
    b[27:37] = bytes((9, 0, 0, 0, 0, 0, 0, 0, 0, 0))
    return seal(b)


def test_pending_last_write_is_distinct_from_old_zero_verified_count():
    r = p.decode(packet())
    assert r['write_bus_error'] == 4 and r['noack_pending']
    assert r['verified_write_noacks'] == 0 and r['read_bus_error'] == 1
    assert not r['read_value_valid'] and r['camera_failed']


def test_later_successful_probe_does_not_clear_first_fault():
    r = p.decode(packet(recovered=True))
    assert r['camera_error'] == 0x61 and not r['camera_ready']
    assert [x['value'] for x in r['probes']] == [0x56, 0x40, 0xf0]
    assert all(x['value_valid'] for x in r['probes'])
    assert r['noack_pending']


def test_valid_mismatch_is_a_real_value_but_not_equal():
    r = p.decode(packet(read_error=0, mismatch=True))
    assert r['read_value_valid'] and not r['read_equal'] and r['read_value'] == 0xef


@pytest.mark.parametrize('write_noack', [False, True])
def test_full264_success_retains3018_f0_while_global_last_expected_is4740_23(write_noack):
    r = p.decode(successful_packet(write_noack))
    assert r['camera_ready'] and not r['camera_failed'] and r['completed_writes'] == 264
    assert r['read_equal'] and r['read_value'] == r['read_expected_value'] == 0xf0
    assert r['expected_value'] == 0x23 and not r['noack_pending']


def test_pending_cannot_clear_when_readback_nacked():
    b = bytearray(packet()); b[15] &= ~8
    with pytest.raises(ValueError): p.decode(seal(b))


def test_failed_initialization_cannot_turn_into_ready_in_the_same_stream():
    with pytest.raises(ValueError): p.audit_wire(packet()+successful_packet(seq=2))


def test_first_fault_cannot_be_replaced_with_a_different_one():
    b = bytearray(packet(seq=2)); b[14] = 0x70
    with pytest.raises(ValueError): p.audit_wire(packet()+seal(b))


def test_finished_probe_evidence_cannot_regress():
    b = bytearray(packet(seq=2)); b[27] = 10; b[29] = 3; b[31] = 2
    with pytest.raises(ValueError): p.audit_wire(packet()+seal(b))


def test_partial_opening_and_closing_boundaries_and_sequence():
    data = packet()[19:]+packet(seq=2)+packet(seq=3)+packet(seq=4)[:23]
    r = p.audit_wire(data)
    assert (r['packets'], r['leading_partial_bytes'], r['trailing_partial_bytes']) == (2, 45, 23)


@pytest.mark.parametrize('position', [0, 8, 15, 23, 32, 49, 56, 63])
def test_every_packet_region_rejects_single_bit_corruption(position):
    b = bytearray(packet()); b[position] ^= 1
    with pytest.raises(ValueError): p.decode(bytes(b))


@pytest.mark.parametrize('position,value', [(9, 63), (11, 1), (24, 16), (27, 30),
    (28, 8), (31, 4), (33, 0x10), (37, 0), (39, 67), (49, 8), (50, 1)])
def test_semantically_invalid_fields_rejected_even_with_good_crc(position, value):
    b = bytearray(packet()); b[position] = value
    with pytest.raises(ValueError): p.decode(seal(b))


def test_invalid_read_cannot_be_equal_even_with_matching_garbage():
    b = bytearray(packet()); b[26] = 0xf0; b[15] |= 0x80
    with pytest.raises(ValueError): p.decode(seal(b))


def test_incomplete_probes_cannot_claim_done():
    b = bytearray(packet()); b[29] = 3; b[31] = 2
    with pytest.raises(ValueError): p.decode(seal(b))


@pytest.mark.parametrize('data', [packet()+packet(), packet()+b'noise',
    b'x'*64+packet(), packet()+b'bad'*22+packet(seq=2), b'', packet()[:40]])
def test_replay_noise_and_missing_complete_packets_rejected(data):
    with pytest.raises(ValueError): p.audit_wire(data)
