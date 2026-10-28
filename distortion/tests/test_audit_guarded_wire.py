from pathlib import Path
import struct
import sys
import zlib
import json
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
import audit_guarded_wire as audit
from frame_protocol import encode


def status(seq=1, *, admitted=0, completed=0, remaining=0, cycles=0,
           duplicate=0, reason=0, flags=(1 << 15) | (1 << 10) | 15, tag=0x52473201):
    packet = bytearray(128)
    packet[:8] = b'PGSTAT02'
    struct.pack_into('<HHIIIHHBBH', packet, 8, 128, 2, tag, seq*500, 0x12345678, 3, 3, 0x10, 1, flags)
    struct.pack_into('<IIIIIIIII', packet, 32, 3, 0, duplicate, 0, admitted, completed, remaining, cycles, completed)
    struct.pack_into('<HHIIIH', packet, 76, 0x9d60, 0x9d6, 1000, 12, 5000, 0x5640)
    packet[104] = reason
    struct.pack_into('<IIHH', packet, 108, seq, 10000, 2, 2000)
    packet[124:] = b'ST02'
    struct.pack_into('<I', packet, 120, zlib.crc32(packet[:120]))
    return bytes(packet)


def raw(frame_id=1):
    # Deliberate magic strings inside pixels must remain in their raw packet.
    payload = (b'PGSTAT02PGFRAME1'+bytes(range(16)))*32
    assert len(payload) == 32*16*2
    return encode(32, 16, frame_id, payload)


def stream_audit(wire):
    return audit.audit_bytes(wire, expected_size=(32, 16))


def test_independent_crc_mixed_wire_and_payload_magic():
    result = stream_audit(status()+raw()+status(2, admitted=1, completed=1, reason=1))
    assert result['status_packets'] == 2 and result['raw_frames'] == 1
    assert [item['type'] for item in result['packet_order']] == ['status', 'raw', 'status']
    assert result['frames'][0]['payload_bytes'] == 1024
    assert not result['physical_provenance_verified_by_auditor']
    assert audit.check_scenario(result, 'capture')['counter_and_packet_checks_passed']


def test_idle_zero_frames_and_no_budget():
    result = stream_audit(b'rtial\r\n'+status()+status(2)+b'PGSTA')
    assert result['leading_boundary_bytes_unverified'] == 7
    assert result['raw_transport_complete'] and result['trailing_partial_packet']['type'] == 'status'
    audit.check_scenario(result, 'boot-idle')
    audit.check_scenario(result, 'idle')


def test_no_frames_without_working_inputs_is_not_authorization_acceptance():
    not_ready = stream_audit(status(flags=1 << 15)+status(2, flags=1 << 15))
    assert not_ready['raw_frames'] == 0
    with pytest.raises(ValueError, match='readiness|ready'):
        audit.check_scenario(not_ready, 'boot-idle')


@pytest.mark.parametrize('damage', ['status_crc', 'status_end', 'raw_crc', 'raw_end', 'raw_header'])
def test_corrupt_complete_packets_are_not_silently_resynchronized(damage):
    a, b = bytearray(status()), bytearray(raw())
    if damage == 'status_crc': a[48] ^= 1
    if damage == 'status_end': a[127] ^= 1
    if damage == 'raw_crc': b[50] ^= 1
    if damage == 'raw_end': b[-12] ^= 1
    if damage == 'raw_header': b[16] ^= 1
    with pytest.raises(ValueError):
        stream_audit(bytes(a)+bytes(b)+status(2))


def test_between_packet_noise_is_not_a_boundary_fragment():
    with pytest.raises(ValueError, match='unframed'):
        stream_audit(status()+b'noise'+status(2))


@pytest.mark.parametrize('suffix', [b'PG', b'PGFRAME', raw()[:32], raw()[:100]])
def test_truncated_or_ambiguous_extra_raw_never_passes_single_frame_scenario(suffix):
    result = stream_audit(status()+raw()+status(2, admitted=1, completed=1, reason=1)+suffix)
    assert not result['raw_transport_complete']
    with pytest.raises(ValueError):
        audit.check_scenario(result, 'capture')


def test_duplicate_snapshot_and_transaction_ids_reject():
    for wire in [status()+status(), status()+raw()+raw()+status(2)]:
        with pytest.raises(ValueError):
            stream_audit(wire)


def test_wrong_target_tag_and_contradictory_ready_temperature_reject():
    with pytest.raises(ValueError, match='tag'):
        stream_audit(status(tag=0x52473101))
    broken = bytearray(status())
    struct.pack_into('<H', broken, 78, 0)
    struct.pack_into('<I', broken, 120, zlib.crc32(broken[:120]))
    with pytest.raises(ValueError, match='contradicts'):
        stream_audit(bytes(broken))


def test_lease_and_stop_counter_checks_are_distinct():
    expired = stream_audit(status()+raw()+status(2, admitted=1, completed=1, remaining=1, reason=2))
    audit.check_scenario(expired, 'lease-expiry')
    with pytest.raises(ValueError): audit.check_scenario(expired, 'stop-drain')
    stopped = stream_audit(status()+raw()+status(2, admitted=1, completed=1, remaining=2, reason=3))
    audit.check_scenario(stopped, 'stop-drain')


def test_duplicate_counter_is_required_but_not_claimed_as_tx_ack_proof():
    wire = status()+raw()+status(2, admitted=1, completed=1, duplicate=1, reason=1)
    result = stream_audit(wire)
    checked = audit.check_scenario(result, 'duplicate-grant')
    assert not checked['tx_ack_timing_independently_verified']
    with pytest.raises(ValueError):
        audit.check_scenario(stream_audit(status()+raw()+status(2, admitted=1, completed=1, reason=1)), 'duplicate-grant')


def test_host_silence_requires_actual_expiry_reason_and_remaining_budget():
    expired = stream_audit(status()+raw()+status(2, admitted=1, completed=1, remaining=1, reason=2))
    audit.check_scenario(expired, 'host-silence')
    for remaining, cycles, reason in ((0,0,2),(1,1,2),(1,0,3)):
        candidate = stream_audit(status()+raw()+status(2, admitted=1, completed=1,
                                                       remaining=remaining, cycles=cycles, reason=reason))
        with pytest.raises(ValueError):
            audit.check_scenario(candidate, 'host-silence')


def test_negative_commands_need_exact_error_rejection_and_query_readback_counters():
    packet = bytearray(status(2))
    struct.pack_into('<HHBB', packet, 24, 10, 10, 0x12, 1)
    struct.pack_into('<IIII', packet, 32, 8, 4, 0, 2)
    struct.pack_into('<I', packet, 120, zlib.crc32(packet[:120]))
    accepted = stream_audit(status()+bytes(packet))
    assert audit.check_scenario(accepted, 'negative-commands')['counter_and_packet_checks_passed']
    # One missing board rejection must not become a successful no-frame test.
    packet[36] = 3
    struct.pack_into('<I', packet, 120, zlib.crc32(packet[:120]))
    with pytest.raises(ValueError):
        audit.check_scenario(stream_audit(status()+bytes(packet)), 'negative-commands')


def test_negative_command_test_cannot_end_with_a_bank_still_owned():
    packet = bytearray(status(2, flags=(1 << 15) | (1 << 10) | (1 << 6) | 15))
    struct.pack_into('<HHBB', packet, 24, 10, 10, 0x12, 1)
    struct.pack_into('<IIII', packet, 32, 8, 4, 0, 2)
    struct.pack_into('<I', packet, 120, zlib.crc32(packet[:120]))
    with pytest.raises(ValueError):
        audit.check_scenario(stream_audit(status()+bytes(packet)), 'negative-commands')


def test_sccb25_status_cannot_be_mistaken_for_the_original_cam1_target():
    wire = status(tag=0x52473125)+status(2, tag=0x52473125)
    assert audit.audit_bytes(wire, expected_tag=0x52473125)['status_packets'] == 2
    with pytest.raises(ValueError, match='tag'):
        audit.audit_bytes(wire, expected_tag=0x52473101)


def test_sccb25_cli_requires_explicit_cam1_profile(tmp_path, monkeypatch):
    wire, output = tmp_path/'wire.bin', tmp_path/'audit.json'
    wire.write_bytes(status(tag=0x52473125))
    monkeypatch.setattr(sys, 'argv', ['audit', '--wire', str(wire), '--output', str(output),
                                     '--eye', 'CAM1', '--sccb-profile', '25khz-trial'])
    audit.main()
    result = json.loads(output.read_text(encoding='utf-8'))
    assert result['statuses'][0]['build_tag'] == 0x52473125
    assert result['declared_sccb_profile'] == '25khz-trial'
    assert result['input_mode'] == 'native-scene'
    assert not result['physical_provenance_verified_by_auditor']


@pytest.mark.parametrize('arguments', [[], ['--mode', 'sensor-internal-bars']])
def test_sccb25_cli_rejects_other_connector_or_pattern_mode(tmp_path, monkeypatch, arguments):
    output = tmp_path/'must-not-write.json'
    monkeypatch.setattr(sys, 'argv', ['audit', '--wire', str(tmp_path/'absent.bin'), '--output', str(output),
                                     '--sccb-profile', '25khz-trial', *arguments])
    with pytest.raises(SystemExit) as error:
        audit.main()
    assert error.value.code == 2 and not output.exists()


def test_other_sensor_reset_trial_tag_and_cli_do_not_prove_physical_isolation(tmp_path, monkeypatch):
    wire, output = tmp_path/'wire.bin', tmp_path/'audit.json'
    wire.write_bytes(status(tag=0x52473149))
    with pytest.raises(ValueError, match='tag'):
        audit.audit_bytes(wire.read_bytes(), expected_tag=0x52473101)
    monkeypatch.setattr(sys, 'argv', ['audit', '--wire', str(wire), '--output', str(output),
                                     '--eye', 'CAM1', '--other-reset-profile', 'hold-cam2-low'])
    audit.main()
    result = json.loads(output.read_text(encoding='utf-8'))
    assert result['statuses'][0]['build_tag'] == 0x52473149
    assert result['other_sensor_reset_control_intent'] == 'hold-cam2-low'
    assert result['declared_sccb_profile'] == 'baseline'
    assert not result['physical_other_sensor_reset_state_verified']
    assert not result['physical_provenance_verified_by_auditor']


@pytest.mark.parametrize('arguments', [[], ['--eye','CAM1','--sccb-profile','25khz-trial'],
                                      ['--mode','sensor-internal-bars']])
def test_other_reset_trial_cli_rejects_combined_or_wrong_modes(tmp_path, monkeypatch, arguments):
    output = tmp_path/'must-not-write.json'
    monkeypatch.setattr(sys, 'argv', ['audit', '--wire', str(tmp_path/'absent.bin'), '--output', str(output),
                                     '--other-reset-profile', 'hold-cam2-low', *arguments])
    with pytest.raises(SystemExit) as error:
        audit.main()
    assert error.value.code == 2 and not output.exists()
