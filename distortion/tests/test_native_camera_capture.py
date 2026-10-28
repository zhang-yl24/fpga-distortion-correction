"""Native receiver integrity/provenance tests use only synthetic byte streams."""
from pathlib import Path
import copy
import hashlib
import importlib.util
import json
import sys
import zlib

import cv2
import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from frame_protocol import Frame, encode
from native_camera_capture import receive_chunks, save_frame, validate_binding, validate_live_binding


def binding():
    return {'schema': 1, 'camera_id': 'SYNTHETIC-CAMERA', 'lens_id': 'SYNTHETIC-LENS',
        'profile_id': 'synthetic-v1', 'capture_mode_id': 'rgb565-test', 'eye': 'CAM2',
        'image_size': [32, 16], 'pixel_format': 'RGB565_LE'}


def payload():
    return np.tile(np.array([0xF800, 0x07E0, 0x001F, 0xFFFF], dtype='<u2'), 128).tobytes()


def test_fragmented_stream_preserves_native_pixels_and_explicit_replay(tmp_path):
    wire = b'partial-telemetry\n'+encode(32, 16, 8, payload())
    result = receive_chunks((wire[i:i+37] for i in range(0, len(wire), 37)), binding(), tmp_path, 'test-session')
    assert result['passed'] and not result['hardware_accessed']
    frame = result['frames'][0]
    assert Path(frame['raw_path']).read_bytes() == payload()
    assert frame['raw_sha256'] == hashlib.sha256(payload()).hexdigest()
    assert frame['source_kind'] == 'offline_uart_replay'
    assert not frame['frame_id_is_sensor_exposure_counter'] and not frame['received_time_is_exposure_time']
    assert not frame['identity_verified_on_wire'] and not frame['eye_synchronization_verified']
    assert frame['geometry_applied'] is None and not frame['hardware_release_allowed']
    assert not frame['geometry_applied_by_receiver'] and frame['upstream_payload_role'] == 'unknown'
    image = cv2.imdecode(np.fromfile(frame['image_path'], dtype=np.uint8), cv2.IMREAD_COLOR)
    np.testing.assert_array_equal(image[0, :4], [[0, 0, 255], [0, 255, 0], [255, 0, 0], [255, 255, 255]])
    assert json.loads(Path(frame['metadata_path']).read_text())['identity_binding']['eye'] == 'CAM2'


def test_corrupt_packet_is_not_saved_and_session_does_not_pass_after_recovery(tmp_path):
    bad = bytearray(encode(32, 16, 2, payload()))
    bad[100] ^= 1
    result = receive_chunks([bad+encode(32, 16, 3, payload())], binding(), tmp_path, 'corrupt-test')
    assert result['saved_frames'] == 1 and result['rejected_packets'] >= 1 and not result['passed']
    assert len(list(tmp_path.glob('*.rgb565'))) == 1


def test_truncated_packet_never_creates_capture_files(tmp_path):
    result = receive_chunks([encode(32, 16, 1, payload())[:-1]], binding(), tmp_path, 'truncated')
    assert not result['passed'] and result['saved_frames'] == 0
    assert list(tmp_path.iterdir()) == []


def test_wrong_capture_dimensions_are_rejected_before_writing(tmp_path):
    config = binding()
    config['image_size'] = [16, 32]
    with pytest.raises(ValueError, match='dimensions'):
        receive_chunks([encode(32, 16, 1, payload())], config, tmp_path, 'wrong-mode')
    assert list(tmp_path.iterdir()) == []


def test_duplicate_ids_and_overwrites_are_rejected(tmp_path):
    wire = encode(32, 16, 7, payload())
    with pytest.raises(ValueError, match='duplicate on-wire'):
        receive_chunks([wire+wire], binding(), tmp_path, 'duplicates', frames=2)
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    with pytest.raises(ValueError, match='already exist'):
        receive_chunks([wire], binding(), tmp_path, 'duplicates')
    assert before == {p.name: p.read_bytes() for p in tmp_path.iterdir()}


@pytest.mark.parametrize('change', [{'camera_id': None}, {'eye': 'left'}, {'pixel_format': 'YUV422'},
    {'image_size': [True, 16]}, {'image_size': [2592, 1944]}, {'schema': True}])
def test_invalid_or_ambiguous_identity_is_rejected(change):
    config = binding()
    config.update(change)
    with pytest.raises(ValueError):
        validate_binding(config)


def test_live_mode_cannot_start_with_replay_metadata_only(tmp_path):
    with pytest.raises(ValueError, match='explicit new-module'):
        validate_live_binding(binding(), base_dir=tmp_path)


def test_unverified_live_frame_cannot_be_saved_as_physical(tmp_path):
    data = payload()
    with pytest.raises(ValueError, match='validated build'):
        save_frame(Frame(32, 16, 1, zlib.crc32(data), data), binding(), tmp_path, 'test-live', source_kind='physical_native_camera')


def test_path_injection_and_invalid_source_are_rejected(tmp_path):
    data = payload()
    frame = Frame(32, 16, 1, zlib.crc32(data), data)
    for label in ('../escape', 'bad:session', ''):
        with pytest.raises(ValueError):
            save_frame(frame, binding(), tmp_path, label, source_kind='offline_uart_replay')
    with pytest.raises(ValueError):
        save_frame(frame, binding(), tmp_path, 'good', source_kind='synthetic-disguised-as-live')


def test_manual_bad_payload_cannot_bypass_protocol_crc(tmp_path):
    data = payload()
    with pytest.raises(ValueError, match='payload length or source CRC'):
        save_frame(Frame(32, 16, 1, 0, data), binding(), tmp_path, 'bad-crc', source_kind='offline_uart_replay')


def live_fixture(tmp_path):
    config = binding()
    bitstream, timing, manifest_path = [tmp_path/name for name in ('synthetic.sbit', 'synthetic-timing.rtr', 'synthetic-build.json')]
    bitstream.write_bytes(b'SYNTHETIC TEST ONLY - NOT A REAL BITSTREAM')
    timing.write_text('SYNTHETIC TEST ONLY\nAll Constraints Met\n', encoding='utf-8')
    pin_path = ROOT/'board/corrected_gamma_d5-pins.json'
    digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    contract = {'protocol': 'PGFRAME1', 'payload_role': 'native_raw', 'geometry_applied': False, 'image_size': [32, 16]}
    manifest = {'SHA256': digest(bitstream), 'TimingSHA256': digest(timing), 'RawCaptureContract': contract,
        'SourceSHA256': {'board/corrected_gamma_d5-pins.json': digest(pin_path)}}
    manifest_path.write_text(json.dumps(manifest), encoding='utf-8')
    config['connection_review'] = {name: True for name in ('new_module_pinout_verified', 'power_and_io_verified',
        'selected_eye_verified', 'programmed_bound_bitstream')}
    config['build_binding'] = {name: {'path': str(path), 'sha256': digest(path)} for name, path in
        (('validated_build', manifest_path), ('bitstream', bitstream), ('pinout', pin_path), ('timing_report', timing))}
    return config, manifest, manifest_path


def test_live_file_contract_checks_do_not_claim_actual_hardware_observation(tmp_path):
    config, _, _ = live_fixture(tmp_path)
    record = validate_live_binding(config, base_dir=tmp_path)
    assert record['selected_eye'] == 'CAM2'
    assert not record['actual_programming_and_connection_independently_observed']
    assert record['raw_capture_contract']['payload_role'] == 'native_raw'


def test_program_stage_does_not_require_prior_programming_but_capture_does(tmp_path):
    config, _, _ = live_fixture(tmp_path)
    config['connection_review']['programmed_bound_bitstream'] = False
    result = validate_live_binding(config, base_dir=tmp_path, require_programmed=False)
    assert not result['programmed_bitstream_review_required']
    with pytest.raises(ValueError, match='explicit new-module'):
        validate_live_binding(config, base_dir=tmp_path)


@pytest.mark.parametrize('case', ['missing_raw_contract', 'changed_timing', 'negative_timing_summary', 'wrong_eye', 'changed_source_sha', 'missing_review'])
def test_live_contract_faults_rejected_without_opening_uart(tmp_path, case):
    config, manifest, manifest_path = live_fixture(tmp_path)
    if case == 'missing_raw_contract':
        del manifest['RawCaptureContract']
    elif case == 'changed_timing':
        Path(config['build_binding']['timing_report']['path']).write_text('timing failed', encoding='utf-8')
    elif case == 'negative_timing_summary':
        path = Path(config['build_binding']['timing_report']['path'])
        path.write_text('Design Summary : Not All Constraints Met.\n', encoding='utf-8')
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        config['build_binding']['timing_report']['sha256'] = digest
        manifest['TimingSHA256'] = digest
    elif case == 'wrong_eye':
        config['eye'] = 'CAM1'
    elif case == 'changed_source_sha':
        manifest['SourceSHA256']['board/corrected_gamma_d5-pins.json'] = '0'*64
    else:
        config['connection_review']['power_and_io_verified'] = False
    manifest_path.write_text(json.dumps(manifest), encoding='utf-8')
    config['build_binding']['validated_build']['sha256'] = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    with pytest.raises(ValueError):
        validate_live_binding(config, base_dir=tmp_path)
