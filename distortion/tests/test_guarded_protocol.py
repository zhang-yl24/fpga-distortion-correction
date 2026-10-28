"""Synthetic codecs, replay discipline and frame-boundary safety tests."""
from pathlib import Path
import struct
import sys
import zlib

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
import guarded_protocol as gp
from frame_protocol import encode as frame_encode


def test_crc_known_check_and_command_layout():
    assert gp.crc16_ccitt_false(b'123456789') == 0x29B1
    packet = gp.encode_grant(0x1234, 0x11223344, 3, 24000)
    assert packet[:14] == bytes.fromhex('A55A021034124433221103C05D00')
    assert len(packet) == 16
    assert gp.decode_command(packet) == {'version': 2, 'opcode': 0x10, 'seq': 0x1234,
        'session': 0x11223344, 'arg': (24000 << 8) | 3, 'requested_frames': 3, 'lease_ms': 24000}


def test_status_frozen_offsets_crc_and_flags():
    fields = {'session_id': 0x11223344, 'last_received_seq': 19, 'last_accepted_seq': 18,
        'last_opcode': gp.Opcode.GRANT, 'last_result': gp.Result.GRANT_REJECTED,
        'flag_bits': (1 << 15) | (1 << 10) | 15, 'remaining_frames': 2,
        'remaining_cycles': 125001, 'completed_frames': 7, 'temperature_raw': 0xB00F,
        'temperature_code': 0xB00, 'temperature_age_27mhz': 123, 'safety_snapshot_age_core': 42}
    packet = gp.encode_status(fields)
    assert packet[:16] == b'PGSTAT02'+struct.pack('<HHI', 128, 2, 0x52473201)
    assert packet[20:24] == bytes.fromhex('44332211')
    assert packet[124:] == b'ST02' and struct.unpack_from('<I', packet, 120)[0] == zlib.crc32(packet[:120])
    decoded = gp.decode_status(packet)
    assert all(decoded[name] == value for name, value in fields.items())
    assert decoded['flags']['core_idle'] and decoded['flags']['temp_valid']
    assert not decoded['flags']['armed'] and decoded['remaining_lease_ms_ceil'] == 2


@pytest.mark.parametrize('offset', [0, 8, 10, 12, 30, 76, 120, 124])
def test_status_tampering_is_rejected(offset):
    packet = bytearray(gp.encode_status({}))
    packet[offset] ^= 1
    with pytest.raises(ValueError):
        gp.decode_status(packet)


@pytest.mark.parametrize('frames,milliseconds', [(0, 1), (4, 100), (1, 0), (1, 24001), (True, 100)])
def test_grant_encoder_rejects_outside_fixed_limits(frames, milliseconds):
    with pytest.raises(ValueError):
        gp.encode_grant(1, 1, frames, milliseconds)


def model_open():
    model = gp.GuardedCommandModel(rx_timeout_cycles=20, grant_timeout_cycles=64)
    assert model.feed(gp.encode_open(1, 0x12345678))[0]['result'] == gp.Result.ACCEPTED
    return model


def test_no_session_cannot_grant_or_query():
    model = gp.GuardedCommandModel()
    assert model.feed(gp.encode_grant(1, 1, 1, 10))[0]['result'] == gp.Result.NO_SESSION
    assert model.feed(gp.encode_query(2, 0))[0]['result'] == gp.Result.NO_SESSION
    assert model.session_id == 0 and model.accepted_count == 0


def test_open_requires_idle_no_fault_and_nonzero_session():
    model = gp.GuardedCommandModel()
    assert model.feed(gp.encode_open(1, 1), core_idle=False)[0]['result'] == gp.Result.NOT_IDLE
    assert model.feed(gp.encode_open(1, 1), fault_active=True)[0]['result'] == gp.Result.FAULT
    assert model.feed(gp.encode_command(gp.Opcode.OPEN, 1, 0))[0]['result'] == gp.Result.BAD_ARG
    assert model.feed(gp.encode_open(1, 1))[0]['result'] == gp.Result.ACCEPTED


def test_grant_ack_depends_on_real_lease_feedback():
    model = model_open()
    request = gp.encode_grant(2, model.session_id, 3, 24000)
    event = model.feed(request)[0]
    assert event['result'] == gp.Result.NONE and not event['reply']
    assert event['grant']['cycles'] == 3000000000 and model.command_busy
    assert model.accepted_count == 1 and model.last_accepted_seq == 1
    feedback = model.grant_feedback(accepted=True)
    assert feedback['result'] == gp.Result.ACCEPTED
    assert model.accepted_count == 2 and model.last_accepted_seq == 2 and not model.command_busy


def test_lease_rejection_is_not_parsed_acceptance():
    model = model_open()
    model.feed(gp.encode_grant(2, model.session_id, 1, 100))
    assert model.grant_feedback(accepted=True, rejected=True)['result'] == gp.Result.GRANT_REJECTED
    assert model.accepted_count == 1 and model.last_accepted_seq == 1
    assert model.rejected_count == 1


def test_rejected_forward_sequence_is_consumed_and_retry_is_duplicate():
    model = model_open()
    command = gp.encode_grant(2, model.session_id, 1, 100)
    assert model.feed(command, can_grant=False)[0]['result'] == gp.Result.NOT_READY
    assert model.last_received_seq == 2 and model.last_accepted_seq == 1
    assert model.feed(command, can_grant=True)[0]['result'] == gp.Result.DUPLICATE
    assert model.pending is None and model.accepted_count == 1
    assert model.feed(gp.encode_grant(2, model.session_id, 2, 100))[0]['result'] == gp.Result.SEQ_CONFLICT
    assert model.feed(gp.encode_query(1, model.session_id))[0]['result'] == gp.Result.OLD_SEQ


def test_sequence_half_range_wrap_and_wrong_session():
    model = gp.GuardedCommandModel()
    model.feed(gp.encode_open(65534, 7))
    assert model.feed(gp.encode_query(65535, 7))[0]['result'] == gp.Result.ACCEPTED
    assert model.feed(gp.encode_query(0, 7))[0]['result'] == gp.Result.ACCEPTED
    assert model.feed(gp.encode_query(32768, 7))[0]['result'] == gp.Result.OLD_SEQ
    assert model.feed(gp.encode_query(1, 8))[0]['result'] == gp.Result.SESSION_MISMATCH
    assert model.last_received_seq == 0


def test_stop_query_and_duplicate_never_emit_new_grant_or_renew():
    model = model_open()
    command = gp.encode_grant(2, model.session_id, 1, 100)
    model.feed(command); model.grant_feedback(accepted=True)
    assert model.feed(command)[0]['grant'] is None
    assert model.feed(gp.encode_query(3, model.session_id))[0]['grant'] is None
    event = model.feed(gp.encode_stop(4, model.session_id))[0]
    assert event['stop'] and event['grant'] is None
    assert model.requested_frames == 1 and model.lease_ms == 100


def test_pending_grant_stop_preempts_and_late_feedback_is_ignored():
    model = model_open()
    model.feed(gp.encode_grant(2, model.session_id, 1, 100))
    assert model.feed(gp.encode_query(3, model.session_id))[0]['result'] == gp.Result.BUSY
    event = model.feed(gp.encode_stop(4, model.session_id))[0]
    assert event['stop'] and event['result'] == gp.Result.ACCEPTED
    assert model.grant_feedback(accepted=True) is None
    assert model.last_accepted_seq == 4 and model.rejected_count == 2


def test_missing_feedback_times_out_and_stops_without_accepting_grant():
    model = model_open()
    model.feed(gp.encode_grant(2, model.session_id, 1, 100))
    assert model.tick(63) == []
    event = model.tick(1)[0]
    assert event['result'] == gp.Result.GRANT_TIMEOUT and event['stop']
    assert model.accepted_count == 1 and model.last_accepted_seq == 1


def test_crc_version_timeout_framing_and_resynchronization():
    model = model_open()
    bad = bytearray(gp.encode_query(2, model.session_id));bad[14] ^= 1
    assert model.feed(bad)[0]['result'] == gp.Result.BAD_CRC
    old = bytearray(gp.encode_query(2, model.session_id));old[2] = 1
    old[14:] = gp.crc16_ccitt_false(old[2:14]).to_bytes(2, 'little')
    assert model.feed(old)[0]['result'] == gp.Result.BAD_VERSION
    model.feed(b'\xa5\x5a\x02')
    assert model.tick(20)[0]['result'] == gp.Result.RX_TIMEOUT
    model.feed(b'\xa5')
    assert model.feed(b'', framing_error=True)[0]['result'] == gp.Result.RX_FRAMING
    events = model.feed(b'NOISE\xa5'+gp.encode_query(2, model.session_id))
    assert events[-1]['result'] == gp.Result.ACCEPTED and model.rx_error_count == 4


@pytest.mark.parametrize('chunk_size', [1, 7, 31, 128, 257])
def test_mixed_stream_never_cuts_magic_inside_raw_payload(chunk_size):
    first = gp.encode_status({'snapshot_seq': 1})
    last = gp.encode_status({'snapshot_seq': 2})
    payload = bytearray(512)
    payload[19:147] = gp.encode_status({'snapshot_seq': 999})
    payload[200:208] = b'PGFRAME1'
    frame = frame_encode(16, 16, 41, payload)
    stream = b'noise'+first+frame+last
    parser = gp.GuardedStreamParser(); events = []
    for start in range(0, len(stream), chunk_size):
        events.extend(parser.feed(stream[start:start+chunk_size]))
    assert [event['kind'] for event in events] == ['status', 'frame', 'status']
    assert events[1]['frame'].payload == payload
    assert [event['status']['snapshot_seq'] for event in events if event['kind'] == 'status'] == [1, 2]
    assert parser.discarded == 5 and parser.rejected == 0 and not parser.buffer


def test_corrupt_frame_consumes_owned_payload_not_fake_status_inside_it():
    payload = bytearray(512)
    payload[32:160] = gp.encode_status({'snapshot_seq': 999})
    frame = bytearray(frame_encode(16, 16, 9, payload));frame[200] ^= 1
    good = gp.encode_status({'snapshot_seq': 2})
    parser = gp.GuardedStreamParser()
    events = parser.feed(frame+good)
    assert len(events) == 1 and events[0]['status']['snapshot_seq'] == 2
    assert parser.rejected == 1


def test_invalid_status_header_and_bad_crc_resynchronize():
    bad = bytearray(gp.encode_status({}));bad[8] = 1
    crc_bad = bytearray(gp.encode_status({}));crc_bad[70] ^= 1
    good = gp.encode_status({'snapshot_seq': 12})
    parser = gp.GuardedStreamParser()
    events = parser.feed(bad+crc_bad+good)
    assert len(events) == 1 and events[0]['status']['snapshot_seq'] == 12
    assert parser.rejected >= 2


def test_cam1_status_requires_explicit_tag_selection_and_keeps_cam2_default():
    packet = gp.encode_status({'snapshot_seq': 8}, build_tag=gp.CAM1_BUILD_TAG)
    assert struct.unpack_from('<I', packet, 12)[0] == 0x52473101
    with pytest.raises(ValueError, match='build tag mismatch'):
        gp.decode_status(packet)
    assert gp.decode_status(packet, expected_build_tag=gp.CAM1_BUILD_TAG)['build_tag'] == gp.CAM1_BUILD_TAG
    assert gp.GuardedStreamParser().feed(packet) == []
    events = gp.GuardedStreamParser(expected_build_tag=gp.CAM1_BUILD_TAG).feed(packet)
    assert len(events) == 1 and events[0]['status']['snapshot_seq'] == 8
    assert gp.BUILD_TAG == gp.GUARDED_CONTROL_CONTRACT['build_tag'] == 0x52473201
    assert gp.decode_status(gp.encode_status({}))['build_tag'] == gp.BUILD_TAG


def test_cam1_parser_rejects_cam2_status_and_resynchronizes_to_expected_tag():
    wrong = gp.encode_status({'snapshot_seq': 1})
    correct = gp.encode_status({'snapshot_seq': 2}, build_tag=gp.CAM1_BUILD_TAG)
    parser = gp.GuardedStreamParser(expected_build_tag=gp.CAM1_BUILD_TAG)
    events = parser.feed(wrong+correct)
    assert len(events) == 1 and events[0]['status']['build_tag'] == gp.CAM1_BUILD_TAG
    assert parser.rejected == 1


@pytest.mark.parametrize('tag', [0, 0x52473301, True, -1])
def test_unknown_or_invalid_status_build_tags_are_not_generalized(tag):
    with pytest.raises(ValueError):
        gp.encode_status({}, build_tag=tag)
    with pytest.raises(ValueError):
        gp.decode_status(gp.encode_status({}), expected_build_tag=tag)
    with pytest.raises(ValueError):
        gp.GuardedStreamParser(expected_build_tag=tag)


def test_cam2_bars_tag_is_explicit_and_default_contract_is_unchanged():
    packet = gp.encode_status({'snapshot_seq': 19}, build_tag=gp.CAM2_BARS_BUILD_TAG)
    assert gp.CAM2_BARS_BUILD_TAG == 0x52473242
    assert gp.decode_status(packet, expected_build_tag=gp.CAM2_BARS_BUILD_TAG)['snapshot_seq'] == 19
    assert gp.GuardedStreamParser(expected_build_tag=gp.CAM2_BARS_BUILD_TAG).feed(packet)[0]['status']['build_tag'] == 0x52473242
    assert gp.DECLARED_BUILD_TAGS == {'CAM2': 0x52473201, 'CAM1': 0x52473101,
                                    'CAM2_BARS': 0x52473242, 'CAM1_SCCB25': 0x52473125,
                                    'CAM1_ISOLATED': 0x52473149}
    assert gp.BUILD_TAG == gp.GUARDED_CONTROL_CONTRACT['build_tag'] == 0x52473201
    assert gp.decode_status(gp.encode_status({}))['build_tag'] == gp.BUILD_TAG


@pytest.mark.parametrize('expected,other', [(a, b) for a in (0x52473201, 0x52473101, 0x52473242, 0x52473125, 0x52473149)
                                          for b in (0x52473201, 0x52473101, 0x52473242, 0x52473125, 0x52473149) if a != b])
def test_all_declared_variants_reject_each_other_and_resynchronize(expected, other):
    wrong = gp.encode_status({'snapshot_seq': 1}, build_tag=other)
    with pytest.raises(ValueError, match='build tag mismatch'):
        gp.decode_status(wrong, expected_build_tag=expected)
    right = gp.encode_status({'snapshot_seq': 2}, build_tag=expected)
    parser = gp.GuardedStreamParser(expected_build_tag=expected)
    events = parser.feed(wrong+right)
    assert len(events) == 1 and events[0]['status']['build_tag'] == expected
    assert parser.rejected == 1 and not parser.buffer


def test_sccb25_tag_is_explicit_and_default_spec_is_unchanged():
    assert gp.CAM1_SCCB25_BUILD_TAG == 0x52473125
    packet = gp.encode_status({'snapshot_seq': 25}, build_tag=gp.CAM1_SCCB25_BUILD_TAG)
    with pytest.raises(ValueError, match='build tag mismatch'): gp.decode_status(packet)
    assert gp.decode_status(packet, expected_build_tag=gp.CAM1_SCCB25_BUILD_TAG)['snapshot_seq'] == 25
    assert gp.GUARDED_CONTROL_CONTRACT['build_tag'] == gp.BUILD_TAG == 0x52473201
    assert gp.protocol_spec()['contract'] == gp.GUARDED_CONTROL_CONTRACT
    assert gp.decode_status(gp.encode_status({}))['build_tag'] == gp.BUILD_TAG


def test_isolated_tag_is_explicit_and_default_spec_is_unchanged():
    assert gp.CAM1_ISOLATED_BUILD_TAG == 0x52473149
    packet = gp.encode_status({'snapshot_seq': 49}, build_tag=gp.CAM1_ISOLATED_BUILD_TAG)
    with pytest.raises(ValueError, match='build tag mismatch'): gp.decode_status(packet)
    assert gp.decode_status(packet, expected_build_tag=gp.CAM1_ISOLATED_BUILD_TAG)['snapshot_seq'] == 49
    assert gp.protocol_spec()['contract']['build_tag'] == gp.BUILD_TAG == 0x52473201
    assert gp.decode_status(gp.encode_status({}))['build_tag'] == gp.BUILD_TAG
