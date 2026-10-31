"""Synthetic wire assessment tests; none of these access a serial port."""
from pathlib import Path
import json
import struct
import sys
import zlib

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import assess_hdmi_input as assessment
import hdmi_status


def packet(*, sequence=1, ticks=0, flags=0x1BBF, cfg_error=0,
           input_fault=0, width=1920, height=1080, edges=74250,
           good=10, bad=0, age=100):
    data = bytearray(64)
    data[:8] = b'PGHDMI01'
    struct.pack_into('<IIHBBHHIIIIIHBBII', data, 8,
                     sequence & 0xffffffff, ticks & 0xffffffff, flags,
                     cfg_error, input_fault, width, height, edges,
                     good & 0xffffffff, bad, age, 1234, 0x209D, 0x2C, 1,
                     0x48444901, 0)
    struct.pack_into('<I', data, 56, zlib.crc32(data[:56]))
    data[60:] = b'HM01'
    return bytes(data)


def stream(count=5, *, sequence=1, ticks=0, good=10, rate=30, overrides=None):
    packets = []
    for index in range(count):
        fields = dict(sequence=sequence + index, ticks=ticks + 13_500_000 * index,
                      good=good + round(rate * .5 * index))
        fields.update((overrides or {}).get(index, {}))
        packets.append(packet(**fields))
    return b''.join(packets)


def test_nominal_window_passes_without_claiming_hardware_or_display():
    result = assessment.assess(stream())
    assert result['passed'] and result['transport_integrity_passed']
    window = result['qualified_window']
    assert window['reference_seconds'] == 2
    assert window['good_frames_advanced'] == 60
    assert window['frame_rate_estimate_fps'] == 30
    assert window['pixel_clock_mhz_range'] == [74.25, 74.25]
    assert window['frame_count_rate_compatible_with_admitted_pixel_clock']
    for key in ('hardware_accessed_by_assessor', 'physical_source_verified',
                'bitstream_identity_verified', 'display_verified',
                'ddr_or_distortion_pipeline_verified', 'hardware_release_allowed'):
        assert result[key] is False


def test_uart_boundary_fragments_allowed_but_never_accepted_as_records():
    before = packet(sequence=0, ticks=-13_500_000, good=0)[19:]
    after = packet(sequence=6, ticks=67_500_000, good=85)[:17]
    result = assessment.assess(before + stream() + after)
    assert result['passed'] and result['records'] == 5
    assert result['boundary'] == {'leading_partial_bytes': 45, 'trailing_partial_bytes': 17}


@pytest.mark.parametrize('offset', [0, 24, 60])
def test_corrupt_complete_packet_cannot_be_skipped_to_get_a_pass(offset):
    wire = bytearray(stream())
    wire[64 + offset] ^= 1
    result = assessment.assess(wire)
    assert not result['passed'] and not result['transport_integrity_passed']


def test_interior_or_trailing_garbage_is_not_treated_as_uart_boundary():
    for wire in (stream()[:64] + b'x' + stream()[64:], stream() + b'garbage'):
        assert not assessment.assess(wire)['passed']


def test_valid_crc_does_not_hide_reserved_bits():
    wire = bytearray(stream())
    wire[64 + 52] = 1
    struct.pack_into('<I', wire, 64 + 56, zlib.crc32(wire[64:64 + 56]))
    result = assessment.assess(wire)
    assert not result['transport_integrity_passed']
    assert 'reserved' in result['errors'][0]


def test_old_configuration_only_diagnostic_is_not_a_video_pass():
    result = assessment.assess(stream(overrides={i: dict(flags=0x003F, good=0,
        width=0, height=0, edges=0) for i in range(5)}))
    assert result['transport_integrity_passed'] and not result['passed']
    assert 'no_qualified_input_window' in result['errors']


def test_initial_configuration_wait_allowed_before_continuous_qualified_window():
    result = assessment.assess(stream(overrides={0: dict(flags=0, good=0, width=0,
        height=0, edges=0, age=0xffffffff), 1: dict(flags=0x003F, good=0, width=0,
        height=0, edges=0), 2: dict(good=10), 3: dict(good=25), 4: dict(good=40)}))
    # Initial waiting rows are allowed, but the first visible frame advance
    # must remain possible within the reference-clock interval.
    assert result['passed']
    assert result['qualified_window']['first_packet_index'] == 2
    assert result['qualified_window']['reference_seconds'] == 1


@pytest.mark.parametrize('fields,expected', [
    ({'flags': 0x1BBB}, 'missing_cfg_pll_locked'),
    ({'flags': 0x1BBD}, 'missing_cfg_fresh'),
    ({'age': 270000}, 'configuration_age_is_stale'),
    ({'width': 1280, 'height': 720}, 'geometry_is_not_1920x1080'),
    ({'edges': 75001}, 'pixel_clock_count_outside_admitted_window'),
    ({'edges': 73499}, 'pixel_clock_count_outside_admitted_window'),
    ({'input_fault': 0x24}, 'input_failed'),
    ({'cfg_error': 1}, 'configuration_failed'),
    ({'flags': 0x13BF}, 'sync_polarity_changed_within_qualified_window'),
    ({'bad': 1}, 'bad_frames_observed'),
])
def test_any_mid_window_loss_or_fault_fails_without_silently_selecting_later_good_rows(fields, expected):
    result = assessment.assess(stream(overrides={2: fields}))
    assert not result['passed']
    assert any(expected in error for error in result['errors'])


@pytest.mark.parametrize('fields,expected', [
    ({'sequence': 4}, 'sequence_gap_duplicate_or_reset'),
    ({'ticks': 13_500_000}, 'reference_tick_interval_outside'),
    ({'ticks': 10}, 'reference_tick_interval_outside'),
    ({'good': 0}, 'good_frame_counter_regressed_or_advanced_too_far'),
])
def test_duplicate_skipped_reset_and_counter_regressions_fail(fields, expected):
    result = assessment.assess(stream(overrides={2: fields}))
    assert not result['passed']
    assert any(expected in error for error in result['errors'])


def test_single_sequence_and_reference_tick_wrap_are_allowed():
    result = assessment.assess(stream(sequence=0xfffffffe, ticks=0xff000000))
    assert result['passed']
    assert result['counter_wraps']['sequence'] == 1
    assert result['counter_wraps']['reference_ticks'] == 1
    assert result['qualified_window']['frame_rate_estimate_fps'] == 30


def test_one_second_and_multiple_records_are_required():
    assert not assessment.assess(stream(count=2))['passed']
    assert assessment.assess(stream(count=3))['passed']


def test_tick_span_cannot_use_unbounded_wrap_interpretation():
    assert not assessment.assess(stream(count=63))['passed']
    assert not assessment.assess(stream(count=65))['transport_integrity_passed']


def test_frozen_good_counter_does_not_pass_qualified_flags():
    result = assessment.assess(stream(overrides={i: {'good': 10} for i in range(5)}))
    assert not result['passed']
    assert 'good_frame_counter_did_not_advance' in result['errors']


def test_frame_rate_uses_quantization_model_not_exact_30_equality():
    short = assessment.assess(stream(count=3, rate=31))
    long = assessment.assess(stream(count=21, rate=31))
    assert short['passed']  # One endpoint frame can explain 31 over 1 second.
    assert not long['passed']
    assert 'frame_count_rate_inconsistent_with_pixel_clock_and_raster' in long['errors']
    assert long['qualified_window']['frame_rate_estimate_fps'] == 31


def test_capture_receipt_is_bound_to_raw_bytes_but_is_not_source_authentication(tmp_path):
    wire = tmp_path / 'wire.bin'
    receipt = tmp_path / 'capture.json'
    wire.write_bytes(stream())
    hdmi_status.capture(receipt, replay=wire)
    result = assessment.assess_files(wire, receipt)
    assert result['passed'] and result['capture_receipt_binding']['matched']
    assert result['capture_receipt_binding']['source_kind_claimed_by_receipt'] == 'offline_uart_replay'
    assert not result['physical_source_verified']
    data = json.loads(receipt.read_text())
    data['frames'][1]['width'] = 1280
    altered = assessment.assess(wire.read_bytes(), data)
    assert not altered['passed']
    assert 'frames' in altered['errors'][0]


@pytest.mark.parametrize('field,value', [('wire_sha256', '0' * 64), ('received_bytes', 0),
    ('accepted_packets', 99), ('passed', True), ('hardware_accessed', True)])
def test_receipt_claims_cannot_override_raw_or_failed_capture(tmp_path, field, value):
    wire, receipt = tmp_path / 'wire.bin', tmp_path / 'capture.json'
    wire.write_bytes(stream())
    original = hdmi_status.capture(receipt, replay=wire)
    if field == 'passed':
        original['error'] = 'read failed after final packet'
    original[field] = value
    assert not assessment.assess(wire.read_bytes(), original)['passed']


def test_output_is_exclusive_and_failure_still_has_a_receipt(tmp_path):
    wire, output = tmp_path / 'wire.bin', tmp_path / 'assessment.json'
    wire.write_bytes(b'not a packet')
    assert assessment.main(['--wire', str(wire), '--output', str(output)]) == 1
    before = output.read_bytes()
    assert not json.loads(before)['passed']
    with pytest.raises(SystemExit):
        assessment.main(['--wire', str(wire), '--output', str(output)])
    assert output.read_bytes() == before
