"""Synthetic natural-scene diagnostics and independent capture integrity gates."""
from pathlib import Path
import copy
import hashlib
import json
import sys
import zlib

import cv2
import numpy as np
import pytest

SOURCE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SOURCE_ROOT))
from tools import native_scene_diagnostics as diagnostics
from tools.native_scene_diagnostics import (analyze_words, analyze_capture, load_verified_frame,
                                             canonical_sha, digest)


IDENTITY = {'camera_id': 'SYNTHETIC', 'lens_id': 'SYNTHETIC-LENS', 'profile_id': 'synthetic-scene',
            'capture_mode_id': 'synthetic-rgb565', 'eye': 'CAM2'}


@pytest.fixture
def build_project(tmp_path, monkeypatch):
    # Keep the build closure inside its own project, wherever pytest puts tmp_path.
    project = tmp_path/'project'
    reference = project/'board/corrected_gamma_d5-pins.json'
    reference.parent.mkdir(parents=True)
    reference.write_bytes((SOURCE_ROOT/'board/corrected_gamma_d5-pins.json').read_bytes())
    monkeypatch.setattr(diagnostics, 'ROOT', project)
    return project


def capture(tmp_path, words, index=0, binding=None, build_record=None):
    words = np.asarray(words, dtype='<u2')
    r, g, b = (words >> 11) & 31, (words >> 5) & 63, words & 31
    image = np.stack(((b << 3) | (b >> 2), (g << 2) | (g >> 4), (r << 3) | (r >> 2)), axis=-1).astype(np.uint8)
    raw, png, meta = [tmp_path/(f'frame-{index}'+suffix) for suffix in ('.rgb565', '.png', '.json')]
    raw.write_bytes(words.tobytes())
    png.write_bytes(cv2.imencode('.png', image)[1].tobytes())
    native = build_record is not None
    record = {'schema': 1, 'identity_binding': IDENTITY, 'frame_id': index+1, 'session_id': 'synthetic-test',
        'source_kind': 'physical_native_camera' if native else 'offline_uart_replay', 'hardware_accessed': native,
        'identity_verified_on_wire': False, 'identity_binding_kind': 'synthetic-test-fixture',
        'width': words.shape[1], 'height': words.shape[0], 'pixel_format': 'RGB565_LE',
        'raw_path': str(raw), 'raw_sha256': digest(raw), 'image_path': str(png), 'image_sha256': digest(png),
        'payload_bytes': words.nbytes, 'source_crc32': f'{zlib.crc32(words.tobytes()):08X}',
        'received_crc32': f'{zlib.crc32(words.tobytes()):08X}', 'build_binding': build_record,
        'geometry_applied': False if native else None, 'upstream_raw_contract_hash_bound': native,
        'upstream_payload_role': 'native_raw' if native else 'unknown',
        'binding_sha256': canonical_sha(binding) if binding else None}
    meta.write_text(json.dumps(record), encoding='utf-8')
    return meta, record


def build_fixture(project, size):
    source, pins, bitstream, timing, manifest, binding_path = [project/name for name in
        ('source.v', 'pins.json', 'synthetic.sbit', 'timing.txt', 'validated-build.json', 'binding.json')]
    source.write_text('// SYNTHETIC TEST SOURCE', encoding='utf-8')
    pins.write_bytes((project/'board/corrected_gamma_d5-pins.json').read_bytes())
    bitstream.write_bytes(b'SYNTHETIC BITSTREAM FIXTURE, NEVER PROGRAM')
    timing.write_text('SYNTHETIC TEST FIXTURE All Constraints Met', encoding='utf-8')
    contract = {'protocol': 'PGFRAME1', 'payload_role': 'native_raw', 'geometry_applied': False, 'image_size': size}
    manifest.write_text(json.dumps({'SHA256': digest(bitstream), 'TimingSHA256': digest(timing),
        'RawCaptureContract': contract, 'SourceSHA256': {str(path.relative_to(project)): digest(path) for path in (source, pins)}}), encoding='utf-8')
    binding = {**IDENTITY, 'schema': 1, 'image_size': size, 'pixel_format': 'RGB565_LE',
        'build_binding': {key: {'path': str(path), 'sha256': digest(path)} for key, path in
                          (('validated_build', manifest), ('bitstream', bitstream), ('pinout', pins), ('timing_report', timing))}}
    binding_path.write_text(json.dumps(binding), encoding='utf-8')
    build_record = {'selected_eye': 'CAM2', 'raw_capture_contract': contract,
        'validated_build_sha256': digest(manifest), 'bitstream_sha256': digest(bitstream),
        'pinout_sha256': digest(pins), 'timing_report_sha256': digest(timing)}
    return binding_path, binding, build_record, source, manifest


def test_synthetic_primary_colors_have_expected_native_code_means():
    words = np.tile(np.array([0xf800, 0x07e0, 0x001f, 0xffff], dtype=np.uint16), (16, 8))
    stats, masks = analyze_words(words)
    assert stats['rgb_mean_codes'] == [127.5, 127.5, 127.5]
    assert stats['exact_white_fraction'] == .25 and stats['exact_black_fraction'] == 0
    assert masks['exact_white'].shape == words.shape and masks['analysis_valid'].all()


def test_d5_drop_signature_is_detected_without_claiming_wiring_proof():
    rng = np.random.default_rng(20261025)
    words = rng.integers(0, 65536, size=(32, 64), dtype=np.uint16)
    good, _ = analyze_words(words)
    bad, _ = analyze_words(words & np.uint16(0xffff ^ ((1 << 5) | (1 << 13))))
    assert not good['d5_both_transferred_byte_bits_constant_zero']
    assert bad['d5_both_transferred_byte_bits_constant_zero']
    lane5 = [row for row in bad['constant_paired_dvp_lane_signatures'] if row['dvp_data_lane'] == 5]
    assert len(lane5) == 1 and not lane5[0]['wiring_failure_proven']


@pytest.mark.parametrize('word,field', [(0, 'exact_black_fraction'), (65535, 'exact_white_fraction')])
def test_lens_cap_or_uniform_white_is_descriptive(word, field):
    stats, _ = analyze_words(np.full((16, 24), word, dtype=np.uint16))
    assert stats[field] == 1 and stats['uniform_word_frame']
    assert stats['adjacent_identical_full_row_fraction'] == 1
    assert stats['unique_rows'] == stats['unique_columns'] == 1


def test_static_pixels_do_not_prove_sensor_freeze(tmp_path):
    words = np.arange(32*24, dtype=np.uint16).reshape(24, 32)
    first, _ = capture(tmp_path, words, 0)
    second, _ = capture(tmp_path, words, 1)
    report, masks = analyze_capture([first, second])
    difference = report['frames'][1]['previous_capture_difference']
    assert difference['identical_pixels'] and difference['changed_pixel_fraction'] == 0
    assert not difference['camera_freeze_verified']
    assert not report['native_source_contracts_verified']
    assert not report['hardware_accessed_by_analyzer']
    assert len(masks) == 10


def test_changed_scene_is_measured(tmp_path):
    words = np.zeros((16, 24), dtype=np.uint16)
    first, _ = capture(tmp_path, words, 0)
    words[:8] = 65535
    second, _ = capture(tmp_path, words, 1)
    report, _ = analyze_capture([first, second])
    difference = report['frames'][1]['previous_capture_difference']
    assert difference['changed_pixel_fraction'] == .5
    assert difference['mean_absolute_rgb_code_difference'] == 127.5


@pytest.mark.parametrize('case', ['truncated', 'raw_sha', 'png_sha', 'png_pixels', 'crc', 'metadata_sha'])
def test_truncation_and_tampering_are_rejected(tmp_path, case):
    meta, record = capture(tmp_path, np.arange(16*24, dtype=np.uint16).reshape(16, 24))
    old_meta_sha = digest(meta)
    if case == 'truncated':
        Path(record['raw_path']).write_bytes(Path(record['raw_path']).read_bytes()[:-2])
    elif case == 'raw_sha':
        record['raw_sha256'] = '0'*64
    elif case == 'png_sha':
        record['image_sha256'] = '0'*64
    elif case == 'png_pixels':
        png = Path(record['image_path'])
        png.write_bytes(cv2.imencode('.png', np.zeros((16, 24, 3), dtype=np.uint8))[1].tobytes())
        record['image_sha256'] = digest(png)
    elif case == 'crc':
        record['received_crc32'] = '00000000'
    else:
        record['session_id'] = 'tampered'
    meta.write_text(json.dumps(record), encoding='utf-8')
    with pytest.raises(ValueError):
        load_verified_frame(meta, expected_metadata_sha256=old_meta_sha if case == 'metadata_sha' else None)


def test_build_role_sources_and_identity_are_independently_reread(tmp_path, build_project):
    binding_path, binding, build, source, manifest = build_fixture(build_project, [24, 16])
    meta, record = capture(tmp_path, np.arange(16*24, dtype=np.uint16).reshape(16, 24), binding=binding, build_record=build)
    report, _ = analyze_capture([meta], binding_path=binding_path)
    assert report['native_source_contracts_verified']
    assert not report['physical_identity_independently_verified']
    source.write_text('// tampered synthetic source', encoding='utf-8')
    with pytest.raises(ValueError, match='build source'):
        analyze_capture([meta], binding_path=binding_path)


def test_identity_and_raw_role_mismatch_are_rejected(tmp_path, build_project):
    binding_path, binding, build, source, manifest = build_fixture(build_project, [24, 16])
    meta, record = capture(tmp_path, np.arange(16*24, dtype=np.uint16).reshape(16, 24), binding=binding, build_record=build)
    binding['lens_id'] = 'OTHER-LENS'
    binding_path.write_text(json.dumps(binding), encoding='utf-8')
    with pytest.raises(ValueError, match='identity/mode differs'):
        analyze_capture([meta], binding_path=binding_path)


def test_build_declaring_corrected_payload_cannot_verify_as_native_raw(tmp_path, build_project):
    binding_path, binding, build, source, manifest = build_fixture(build_project, [24, 16])
    changed = json.loads(manifest.read_text())
    changed['RawCaptureContract']['payload_role'] = 'corrected'
    manifest.write_text(json.dumps(changed), encoding='utf-8')
    binding['build_binding']['validated_build']['sha256'] = digest(manifest)
    binding_path.write_text(json.dumps(binding), encoding='utf-8')
    build['validated_build_sha256'] = digest(manifest)
    meta, record = capture(tmp_path, np.arange(16*24, dtype=np.uint16).reshape(16, 24), binding=binding, build_record=build)
    with pytest.raises(ValueError, match='native raw role'):
        analyze_capture([meta], binding_path=binding_path)


def test_masks_are_retained_without_changing_source_words():
    words = np.arange(16*24, dtype=np.uint16).reshape(16, 24)
    original = words.copy()
    mask = np.zeros(words.shape, dtype=bool)
    mask[4:12, 5:19] = True
    stats, masks = analyze_words(words, valid_mask=mask)
    np.testing.assert_array_equal(words, original)
    np.testing.assert_array_equal(masks['analysis_valid'], mask)
    assert stats['selected_pixels'] == 8*14
    assert not stats['masks_change_source_pixels']
