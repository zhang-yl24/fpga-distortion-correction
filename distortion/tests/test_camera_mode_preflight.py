"""Pure in-memory admission/budget checks; no temporary directories or hardware."""
import importlib.util
import json
from pathlib import Path
from unittest.mock import patch
import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('camera_preflight', ROOT / 'tools/camera_mode_preflight.py')
preflight = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(preflight)


def complete_profile():
    return {'schema_version': 1, 'profile_id': 'synthetic-test-only', 'change_kind': 'lens-only',
            'sensor_model': 'synthetic-test-sensor', 'lens_model': 'synthetic-test-lens',
            'camera_count': 1, 'interface': 'DVP', 'synchronization': 'single-sensor-test',
            'electrical': {'io_voltage_v': 3.3, 'power_voltage_v': 3.3,
                           'pinout_reference': 'synthetic-test-pinout'},
            'input_mode': {'width': 640, 'height': 480, 'fps': 30, 'pixel_format': 'RGB565',
                           'bus_width_bits': 8, 'pclk_hz': 24_000_000},
            'verification': {name: True for name in preflight.VERIFICATIONS}}


def test_unknown_template_blocks_download():
    data = json.loads((ROOT / 'output/project/new-camera-profile.template.json').read_text(encoding='utf-8'))
    report = preflight.inspect_profile(data)
    assert report['new_configuration_download_blocked']
    assert not report['hardware_ready']
    assert not report['profile_checks_complete']
    assert len(report['blockers']) >= 10


def test_supplied_verifications_do_not_authorize_hardware():
    result = preflight.inspect_profile(complete_profile())
    assert result['profile_checks_complete']
    assert not result['download_authorized_by_tool']
    assert not result['hardware_ready']


@pytest.mark.parametrize('field,value', [('schema_version', True), ('camera_count', True),
                                      ('camera_count', 3), ('profile_id', 12),
                                      ('interface', 'Ethernet'), ('change_kind', 'guess')])
def test_invalid_profile_types(field, value):
    data = complete_profile()
    data[field] = value
    with pytest.raises(ValueError):
        preflight.inspect_profile(data)


def test_string_verification_is_rejected():
    data = complete_profile()
    data['verification']['pinout'] = 'true'
    with pytest.raises(ValueError, match='boolean'):
        preflight.inspect_profile(data)


@pytest.mark.parametrize('interface', ['MIPI', 'USB', None])
def test_unsupported_or_unknown_interface_blocks(interface):
    data = complete_profile()
    data['interface'] = interface
    assert preflight.inspect_profile(data)['new_configuration_download_blocked']


def test_simultaneous_dual_camera_blocks_existing_rtl():
    data = complete_profile()
    data['camera_count'] = 2
    report = preflight.inspect_profile(data)
    assert any('camera2 is single-input' in item for item in report['blockers'])


def test_lens_only_still_requires_new_calibration():
    data = complete_profile()
    data['verification']['new_lens_calibration'] = None
    assert any('new_lens_calibration' in item for item in preflight.inspect_profile(data)['blockers'])


def test_raw_capture_can_collect_new_calibration_with_explicit_single_camera_sync_na():
    data = complete_profile()
    data['verification']['new_lens_calibration'] = None
    data['synchronization'] = 'not-applicable-single-camera'
    data['verification']['synchronization'] = None
    raw = preflight.inspect_profile(data, scope='raw-capture')
    assert raw['profile_checks_complete']
    assert not raw['new_lens_calibration_required_for_this_scope']
    assert raw['single_camera_synchronization_explicitly_not_applicable']
    assert not raw['hardware_ready'] and not raw['download_authorized_by_tool']
    corrected = preflight.inspect_profile(data)
    assert corrected['new_configuration_download_blocked']
    assert any('new_lens_calibration' in item for item in corrected['blockers'])


def test_stereo_cannot_use_single_camera_sync_na_even_for_raw_capture():
    data = complete_profile()
    data['camera_count'] = 2
    data['synchronization'] = 'not-applicable-single-camera'
    data['verification']['synchronization'] = None
    result = preflight.inspect_profile(data, scope='raw-capture')
    assert result['new_configuration_download_blocked']
    assert not result['single_camera_synchronization_explicitly_not_applicable']
    assert any('cannot be declared' in item for item in result['blockers'])


def test_raw_scope_retains_electrical_and_configuration_gates():
    data = complete_profile()
    data['verification']['new_lens_calibration'] = None
    data['verification']['electrical'] = None
    data['verification']['candidate_configuration'] = None
    result = preflight.inspect_profile(data, scope='raw-capture')
    assert result['new_configuration_download_blocked']
    assert any('electrical has not' in item for item in result['blockers'])
    assert any('candidate_configuration' in item for item in result['blockers'])


def test_invalid_scope_rejected():
    with pytest.raises(ValueError, match='scope'):
        preflight.inspect_profile(complete_profile(), scope='unsafe')


@pytest.mark.parametrize('field,value', [('io_voltage_v', None), ('io_voltage_v', 1.8),
                                       ('power_voltage_v', None), ('pinout_reference', None)])
def test_electrical_facts_unknown_or_mismatched_block(field, value):
    data = complete_profile()
    data['electrical'][field] = value
    assert preflight.inspect_profile(data)['new_configuration_download_blocked']


def test_boolean_voltage_rejected():
    data = complete_profile()
    data['electrical']['io_voltage_v'] = True
    with pytest.raises(ValueError):
        preflight.inspect_profile(data)


@pytest.mark.parametrize('review,evidence', [(None, None), (False, 'synthetic-review-source'),
                                          (True, None), (None, 'synthetic-review-source')])
def test_2v8_signal_level_requires_separate_review_and_evidence(review, evidence):
    data = complete_profile()
    data['electrical']['io_voltage_v'] = 2.8
    data['electrical']['io_compatibility_evidence'] = evidence
    data['verification']['io_level_compatibility'] = review
    result = preflight.inspect_profile(data)
    assert result['new_configuration_download_blocked']
    assert any('io_level_compatibility' in item for item in result['blockers'])


def test_2v8_reviewed_declaration_can_complete_profile_but_not_release_hardware():
    data = complete_profile()
    data['electrical']['io_voltage_v'] = 2.8
    data['electrical']['io_compatibility_evidence'] = 'SYNTHETIC TEST ONLY: documented device/adapter/bank review'
    data['verification']['io_level_compatibility'] = True
    result = preflight.inspect_profile(data)
    assert result['profile_checks_complete']
    assert result['separate_io_compatibility_review_required']
    assert result['io_compatibility_review_declared']
    assert not result['hardware_ready'] and not result['download_authorized_by_tool']
    data['verification']['electrical'] = None
    result = preflight.inspect_profile(data)
    assert result['new_configuration_download_blocked']
    assert any('electrical has not' in item for item in result['blockers'])


@pytest.mark.parametrize('value', ['true', 1, 0, {}, []])
def test_invalid_io_compatibility_verification_type_is_rejected(value):
    data = complete_profile()
    data['verification']['io_level_compatibility'] = value
    with pytest.raises(ValueError, match='boolean or null'):
        preflight.inspect_profile(data)


@pytest.mark.parametrize('value', [True, False, 1, {}, [], '', '   '])
def test_invalid_io_compatibility_evidence_type_or_empty_source_is_rejected(value):
    data = complete_profile()
    data['electrical']['io_compatibility_evidence'] = value
    with pytest.raises(ValueError, match='nonempty string'):
        preflight.inspect_profile(data)


def test_string_or_boolean_io_voltage_is_not_a_measured_level():
    for value in ('2.8', True, False):
        data = complete_profile()
        data['electrical']['io_voltage_v'] = value
        with pytest.raises(ValueError, match='finite positive'):
            preflight.inspect_profile(data)


@pytest.mark.parametrize('pclk', [1_000_000, 96_000_000])
def test_physical_pclk_boundaries(pclk):
    data = complete_profile()
    data['input_mode']['pclk_hz'] = pclk
    assert preflight.inspect_profile(data)['new_configuration_download_blocked']


def test_vga_budget_separates_input_processing_and_display():
    result = preflight.budget(640, 480, 30, new_output_fps=15, display_fps=60)
    assert result['minimum_effective_dvp_byte_clock_hz_per_camera'] == 18_432_000
    assert result['available_core_cycles_per_output_pixel_shared_engine'] == pytest.approx(125_000_000 / 4_608_000)
    traffic = result['ddr_requested_payload_bytes_per_second']
    assert traffic['capture_writes'] == 18_432_000
    assert traffic['result_writes'] == 9_216_000
    assert traffic['display_reads_including_repeated_frames'] == 36_864_000
    assert result['storage']['bank_stride_address_units'] == 262144
    assert result['storage']['total_reserved_bytes'] == 4 * 1024 * 1024
    assert not result['hardware_ready']


def test_dual_budget_aggregates_without_faking_shared_pclk():
    result = preflight.budget(640, 480, 30, 2)
    assert result['minimum_effective_dvp_byte_clock_hz_per_camera'] == 18_432_000
    assert result['aggregate_effective_input_bytes_per_second'] == 36_864_000
    assert result['available_core_cycles_per_output_pixel_shared_engine'] == pytest.approx(6.78168402778)
    assert len(result['storage']['banks']) == 8
    assert result['current_chain_constraints']
    assert result['storage']['layout_non_overlapping']
    banks = result['storage']['banks']
    assert all(left['reserved_end_address_units_exclusive'] <= right['base_address_units']
               for left, right in zip(banks, banks[1:]))


def test_720p_requires_2mib_banks_and_exceeds_48mhz_at_30fps():
    result = preflight.budget(1280, 720, 30)
    assert result['storage']['bank_stride_bytes'] == 2 * 1024 * 1024
    assert result['minimum_effective_dvp_byte_clock_hz_per_camera'] == 55_296_000
    assert not result['current_48mhz_dvp_constraint_covers_effective_minimum']


@pytest.mark.parametrize('kwargs', [
    {'width': True}, {'width': -1}, {'height': 0}, {'fps': float('nan')},
    {'fps': float('inf')}, {'fps': 10 ** 1000}, {'fps': '30'}, {'cameras': True}, {'cameras': 0},
    {'address_unit_bytes': 1}, {'address_unit_bytes': True},
    {'bank_stride_address_units': 153472},
    {'bank_stride_address_units': 262145},
    {'bank_stride_address_units': 1 << 27},
    {'ddr_capacity_bytes': 1024}, {'ddr_capacity_bytes': 4_194_305},
    {'display_streams': 2}, {'output_width': 0}, {'width': 16385},
])
def test_invalid_modes_units_capacity_and_overlap(kwargs):
    arguments = {'width': 640, 'height': 480, 'fps': 30}
    arguments.update(kwargs)
    with pytest.raises(ValueError):
        preflight.budget(**arguments)


def test_new_output_dimensions_are_an_explicit_unsupported_scenario():
    result = preflight.budget(640, 480, 30, output_width=1280, output_height=720)
    assert any('independently configure' in item for item in result['current_chain_constraints'])


def test_new_frame_rate_cannot_exceed_available_unique_source_frames():
    result = preflight.budget(640, 480, 30, new_output_fps=60)
    assert any('unique source frames' in item for item in result['current_chain_constraints'])


def test_output_cannot_overwrite_template_or_historical_evidence():
    template = ROOT / 'output/project/new-camera-profile.template.json'
    with pytest.raises(FileExistsError):
        preflight.write_new_json(template, {})
    with pytest.raises(ValueError, match='protected'):
        preflight.write_new_json(ROOT / 'results/new-proof.json', {})


def test_output_does_not_create_missing_parent():
    with patch.object(Path, 'is_dir', return_value=False):
        with pytest.raises(ValueError, match='already exist'):
            preflight.write_new_json(ROOT / 'output/project/missing/report.json', {})


def test_cli_profile_unknown_exits_blocked_without_writing(capsys):
    code = preflight.main(['--profile', str(ROOT / 'output/project/new-camera-profile.template.json')])
    assert code == 2
    assert json.loads(capsys.readouterr().out)['profile']['new_configuration_download_blocked']


def test_cli_exploration_requires_explicit_complete_mode():
    with pytest.raises(SystemExit):
        preflight.main(['--explore', '--width', '640'])
    with pytest.raises(SystemExit):
        preflight.main(['--profile', 'irrelevant', '--width', '640'])


def test_cli_exploration_is_hypothetical(capsys):
    assert preflight.main(['--explore', '--width', '640', '--height', '480', '--fps', '30', '--cameras', '2']) == 0
    result = json.loads(capsys.readouterr().out)
    assert not result['budget']['hardware_ready']
    assert result['budget']['kind'] == 'exploration_budget_only'
