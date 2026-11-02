"""Current720 first-frame provenance and corrupt-wire checks; no device access."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import zlib

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
import camera720_capture as tool
from frame_protocol import encode


@pytest.fixture(scope='module')
def payload():
    # Genuine full-size synthetic byte stream, including asymmetric end pixels.
    data = bytearray(bytes.fromhex('00f8e0071f00ffff')*(tool.PAYLOAD_BYTES//8))
    data[:2] = bytes.fromhex('3412'); data[-2:] = bytes.fromhex('cdab')
    return bytes(data)


def template():
    return {'schema': 1, 'camera_id': 'same-physical-camera', 'lens_id': 'same-installed-lens',
            'eye': 'CAM2', 'profile_id': 'old-vga-calibrated', 'capture_mode_id': 'old-vga',
            'image_size': [640, 480], 'pixel_format': 'RGB565_LE',
            'calibration_accepted': True, 'K': [[1, 0, 320], [0, 1, 240], [0, 0, 1]],
            'connection_review': {'programmed_bound_bitstream': True}}


def test_identity_preserves_camera_lens_but_never_inherits_old_calibration():
    old = template(); new = tool.identity_from_template(old)
    assert new['camera_id'] == old['camera_id'] and new['lens_id'] == old['lens_id']
    assert new['image_size'] == [1280, 720] and new['capture_mode_id'] == tool.MODE
    assert new['profile_id'] != old['profile_id'] and new['calibration_accepted'] is False
    assert 'K' not in new and 'connection_review' not in new
    assert new['checkerboard']['inner_corners'] == [6, 9]
    assert new['checkerboard']['square_size_mm'] == 25.0
    with pytest.raises(ValueError, match='CAM2'):
        tool.identity_from_template({**old, 'eye': 'CAM1'})


def test_missing_future_release_provider_fails_closed_before_import(tmp_path, monkeypatch):
    monkeypatch.setattr(tool, 'ROOT', tmp_path)
    monkeypatch.setattr(tool.importlib, 'import_module', lambda *a: pytest.fail('missing provider was imported'))
    with pytest.raises(ValueError, match='unavailable'):
        tool.providers()


@pytest.mark.parametrize('verified', [
    {'Verified': False, 'Target': tool.TARGET},
    {'Verified': True, 'Target': 'camera720_transport_top'},
    {'Verified': True, 'Target': 'raw_camera_capture_cam2_delay'},
])
def test_unverified_or_old_bit_rejected_before_build_or_program_check(tmp_path, monkeypatch, verified):
    provider = SimpleNamespace(verify=lambda p: verified,
                               validate=lambda p: pytest.fail('unaudited candidate reached build validation'))
    monkeypatch.setattr(tool, 'providers', lambda: (provider, object()))
    with pytest.raises(ValueError, match='fully verified actual'):
        tool.release_context(tmp_path, tmp_path/'receipt.json')


@pytest.mark.parametrize('change', [{'Schema': 'camera720-sram-execution-v1'},
                                   {'Target': 'camera720_transport_top'}, {'DoneConfirmed': False},
                                   {'Passed': False}, {'FlashWritten': True}, {'CleanupErrors': ['live process']}])
def test_wrong_or_incomplete_program_receipt_rejected_before_validation(tmp_path, change):
    value = dict(Schema=tool.PROGRAM_SCHEMA, Target=tool.TARGET, FlashWritten=False, CleanupErrors=[])
    value.update({k: True for k in ('Passed', 'Executed', 'HardwareAccessed', 'ProgrammingAttempted',
                                   'DoneConfirmed', 'UserConfirmedBoardPowered', 'UserNotifiedBeforeExecution')})
    value.update(change)
    path = tmp_path/'receipt.json'; path.write_text(json.dumps(value))
    program = SimpleNamespace(validate=lambda p: pytest.fail('invalid receipt reached native plan validation'))
    with pytest.raises(ValueError):
        tool.checked_program(path, tmp_path, {}, program)


def test_generic_fake_binding_cannot_open_uart(tmp_path, monkeypatch):
    path = tmp_path/'binding.json'; path.write_text(json.dumps(tool.identity_from_template(template())))
    monkeypatch.setattr(tool.capture, 'serial_chunks', lambda *a: pytest.fail('unverified binding opened UART'))
    with pytest.raises(ValueError, match='generic bindings are insufficient'):
        tool.receive(path, tmp_path/'out', 'first', port='COM3')
    assert not (tmp_path/'out').exists()


def test_full_fragmented_frame_retains_every_pixel(payload):
    wire = b'partial preceding transmission'+encode(1280, 720, 17, payload)
    frame, stats = tool.first_frame(wire[i:i+10007] for i in range(0, len(wire), 10007))
    assert (frame.width, frame.height, frame.frame_id) == (1280, 720, 17)
    assert frame.payload == payload and frame.source_crc == zlib.crc32(payload)
    assert hashlib.sha256(frame.payload).digest() == hashlib.sha256(payload).digest()
    assert stats['RejectedPackets'] == 0


@pytest.mark.parametrize('fault', ['header_crc', 'payload', 'tail', 'truncated'])
def test_corrupt_or_incomplete_frame_never_accepted(payload, fault):
    wire = bytearray(encode(1280, 720, 4, payload))
    if fault == 'header_crc': wire[28] ^= 1
    elif fault == 'payload': wire[123456] ^= 1
    elif fault == 'tail': wire[-12] ^= 1
    else: wire = wire[:-1]
    with pytest.raises(ValueError, match='malformed|incomplete'):
        tool.first_frame([wire])


def test_corrupt_packet_followed_by_good_packet_cannot_pass(payload):
    wire = bytearray(encode(1280, 720, 1, payload)); wire[100] ^= 1
    with pytest.raises(ValueError, match='malformed'):
        tool.first_frame([wire+encode(1280, 720, 2, payload)])


def test_crc_valid_vga_frame_is_not_a720_capture():
    with pytest.raises(ValueError, match='exactly1280x720'):
        tool.first_frame([encode(640, 480, 3, b'\x00\x00'*(640*480))])


def test_passive_one_frame_save_and_replay_metadata_are_not_physical(tmp_path, monkeypatch, payload):
    raw = tmp_path/'wire.bin'; raw.write_bytes(encode(1280, 720, 91, payload))
    binding_file = tmp_path/'binding.json'; value = tool.identity_from_template(template())
    binding_file.write_text(json.dumps(value))
    monkeypatch.setattr(tool, 'validate_session_binding', lambda p: (deepcopy(value), {}, {str(binding_file): tool.sha(binding_file)}))
    monkeypatch.setattr(tool.capture, 'serial_chunks', lambda *a: pytest.fail('replay accessed UART'))
    result = tool.receive(binding_file, tmp_path/'out', 'replay', replay=raw)
    assert result['Passed'] and result['SourceKind'] == 'offline_uart_replay'
    assert not result['HardwareAccessed'] and not result['HeartbeatProgrammed'] and result['UARTTransmitBytes'] == 0
    assert Path(result['Frame']['raw_path']).read_bytes() == payload
    assert result['Frame']['geometry_applied'] is None and not result['Frame']['hardware_accessed']
    assert result['Checkerboard']['inner_corners'] == [6, 9]
    assert result['FrameRateMeasured'] is False and result['OpticalCorrectionAccepted'] is False
    with pytest.raises(ValueError, match='fresh session'):
        tool.receive(binding_file, tmp_path/'out', 'replay', replay=raw)


def test_live_validation_precedes_generator_and_evidence_drift_fails_session(tmp_path, monkeypatch, payload):
    value = tool.identity_from_template(template()); path = tmp_path/'binding.json'; path.write_text(json.dumps(value))
    watched = {str(path): tool.sha(path)}; calls = []
    def validate(p):
        calls.append('validated'); return value, {'raw_capture_contract': tool.CONTRACT}, watched
    def chunks(*args):
        assert calls == ['validated']; calls.append('receive')
        path.write_text('changed during receive')
        yield encode(1280, 720, 1, payload)
    monkeypatch.setattr(tool, 'validate_session_binding', validate)
    monkeypatch.setattr(tool.capture, 'serial_chunks', chunks)
    result = tool.receive(path, tmp_path/'out', 'drift', port='COM3')
    assert not result['Passed'] and result['InputDrift'] == [str(path)]
    assert list((tmp_path/'out').glob('*.rgb565')) == []
    assert calls == ['validated', 'receive']


def test_stream_close_failure_retains_evidence_and_cannot_pass(tmp_path, monkeypatch, payload):
    path = tmp_path/'binding.json'; value = tool.identity_from_template(template())
    path.write_text(json.dumps(value))
    monkeypatch.setattr(tool, 'validate_session_binding', lambda p: (
        value, {'raw_capture_contract': tool.CONTRACT}, {str(path): tool.sha(path)}))
    class Stream:
        def __iter__(self):
            yield encode(1280, 720, 8, payload)
        def close(self):
            raise OSError('synthetic close failure')
    monkeypatch.setattr(tool.capture, 'serial_chunks', lambda *a: Stream())
    result = tool.receive(path, tmp_path/'out', 'close-test', port='COM3')
    assert result['Passed'] is False and result['ReceiverStreamClosed'] is False
    assert 'synthetic close failure' in result['CloseError']
    assert (tmp_path/'out/session-summary.json').is_file()
    assert Path(result['Frame']['raw_path']).read_bytes() == payload


@pytest.mark.parametrize('seconds', [0, -1, 181, float('nan'), float('inf'), True])
def test_invalid_timeout_cannot_reach_live_validation(tmp_path, monkeypatch, seconds):
    monkeypatch.setattr(tool, 'validate_session_binding', lambda *a: pytest.fail('invalid bound reached release validation'))
    with pytest.raises(ValueError, match='bounded'):
        tool.receive(tmp_path/'binding.json', tmp_path/'out', 'x', port='COM3', seconds=seconds)
