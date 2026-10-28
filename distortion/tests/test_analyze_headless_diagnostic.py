from pathlib import Path
import binascii
import sys
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
import analyze_headless_diagnostic as analyzer


def thermal(q=1, samples=3, **overrides):
    fields = dict(V=1, B=921600, Q=q, TV=1, TF=0, E=0, TR=0xa400, TC=0xa40,
                  TA=1000, TS=samples, CV=samples+4, OT=0, AL=0)
    fields.update(overrides)
    widths = (2, 8, 8, 1, 1, 2, 4, 3, 8, 8, 8, 1, 2)
    body = ('THERMAL_IDLE '+' '.join(f'{key}={fields[key]:0{width}X}' for key, width in
                                   zip(analyzer.THERMAL_KEYS, widths))).encode('ascii')
    assert len(body) == 116
    return body+f' Z={binascii.crc_hqx(body, 0xffff):04X}\r\n'.encode('ascii')


def isp_scan(epoch=1):
    regs = dict.fromkeys(analyzer.ISP_ADDRESSES, 0)
    regs.update({0x5001: 0xa3, 0x4300: 0x6f, 0x501f: 1, 0x3017: 0x7f, 0x3018: 0xf0,
                 0x3035: 0x21, 0x3036: 0x60, 0x3400: 4, 0x3402: 4, 0x3404: 4, 0x3501: 0x10, 0x350b: 0x10})
    return [f'ISP T={epoch*1000+i:08X} A={address:04X} V={regs[address]:02X} E=0\r\n'.encode()
            for i, address in enumerate(analyzer.ISP_ADDRESSES)]


def test_crc_fresh_snapshots_and_explicit_temperature_limits():
    result = analyzer.analyze_thermal(thermal()+thermal(q=2, samples=4))
    assert result['transport_integrity_passed'] and result['fresh_adc_samples_observed']
    assert result['all_records_valid_and_fault_free'] and result['fresh_snapshots_below_project_ceiling']
    assert result['approximate_celsius_range'] == [46.716, 46.716]
    assert not result['future_active_load_temperature_verified']
    assert not result['continuous_thermal_interlock_installed']


@pytest.mark.parametrize('change', [dict(TV=0), dict(TF=1, E=4), dict(TA=54000000), dict(TR=0, TC=0)])
def test_invalid_failed_stale_and_zero_never_become_temperature_evidence(change):
    result = analyzer.analyze_thermal(thermal(**change)+thermal(q=2, samples=4, **change))
    assert not result['fresh_adc_samples_observed']
    assert not result['all_records_valid_and_fault_free']
    assert not result['fresh_snapshots_below_project_ceiling']
    assert result['approximate_celsius_range'] is None


def test_over_temperature_is_not_hidden_by_good_uart_crc():
    result = analyzer.analyze_thermal(thermal(TR=0xc000, TC=0xc00, OT=1)+thermal(q=2, samples=4, TR=0xc000, TC=0xc00, OT=1))
    assert result['fresh_adc_samples_observed'] and result['over_temp_or_alarm_observed']
    assert not result['fresh_snapshots_below_project_ceiling']


@pytest.mark.parametrize('stream', [thermal()+thermal(), thermal()+thermal(q=3, samples=4),
                                     thermal()+thermal(q=2, samples=2), thermal(TC=0xa41),
                                     thermal().replace(b'TR=A400', b'TR=A401')])
def test_bad_sequence_code_and_crc_are_rejected(stream):
    with pytest.raises(ValueError):
        analyzer.analyze_thermal(stream)


def test_only_boundary_partial_bytes_can_be_skipped():
    result = analyzer.analyze_thermal(b'IAL\r\n'+thermal()+thermal(q=2, samples=4)+b'THERMAL_')
    assert result['records'] == 2 and result['boundary']['leading_partial_bytes'] == 5
    with pytest.raises(ValueError):
        analyzer.analyze_thermal(thermal()+b'noise\r\n'+thermal(q=2, samples=4))


def test_repeated_adc_sample_counter_is_not_fresh_sampling():
    result = analyzer.analyze_thermal(thermal()+thermal(q=2))
    assert not result['fresh_adc_samples_observed']


def test_implausible_low_code_does_not_pass_ceiling_policy():
    result = analyzer.analyze_thermal(thermal(TR=0x10, TC=1)+thermal(q=2, samples=4, TR=0x10, TC=1))
    assert result['fresh_adc_samples_observed'] and not result['temperature_values_pass_sanity_check']
    assert not result['fresh_snapshots_below_project_ceiling']
    assert not result['physical_input_provenance_verified_by_analyzer']


@pytest.mark.parametrize('stream', [thermal()+thermal(q=2, samples=4, CV=7), thermal(samples=8, CV=7)])
def test_sample_count_cannot_advance_without_conversion_epochs(stream):
    with pytest.raises(ValueError, match='conversion epochs'):
        analyzer.analyze_thermal(stream)


def test_alarm_below_numeric_ceiling_still_fails_combined_policy():
    result = analyzer.analyze_thermal(thermal(OT=1)+thermal(q=2, samples=4, OT=1))
    assert result['fresh_snapshots_below_project_ceiling']
    assert not result['observed_low_load_status_meets_project_snapshot_policy']


def test_fault_row_between_fresh_samples_fails_combined_policy():
    result = analyzer.analyze_thermal(thermal()+thermal(q=2, samples=4, TF=1, E=4)+thermal(q=3, samples=5))
    assert result['fresh_snapshots_below_project_ceiling']
    assert not result['all_records_valid_and_fault_free']
    assert not result['observed_low_load_status_meets_project_snapshot_policy']


def test_isp_complete_scans_controls_and_non_atomic_boundaries():
    result = analyzer.analyze_isp(b''.join(isp_scan()+isp_scan(2)))
    assert result['at_least_two_complete_scans'] and result['all_complete_scans_match_reference']
    first = result['scans'][0]
    assert all(first['controls'][key] for key in ('awb_isp_enabled', 'awb_automatic', 'aec_automatic', 'agc_automatic'))
    assert first['non_atomic_rgb_gain_codes'] == [1024]*3
    assert first['non_atomic_exposure_code'] == 4096
    assert not result['uart_records_have_crc'] and not result['optical_color_or_exposure_quality_verified']


def test_isp_corrupt_order_sccb_error_and_regression_reject():
    original = b''.join(isp_scan()+isp_scan(2))
    bad = [original.replace(b'A=3406', b'A=3407', 1), original.replace(b'E=0', b'E=1', 1),
           b''.join(isp_scan(2)+isp_scan(1))]
    for data in bad:
        with pytest.raises(ValueError):
            analyzer.analyze_isp(data)


def test_isp_configuration_mismatch_is_reported_not_silently_accepted():
    data = b''.join(isp_scan()+isp_scan(2)).replace(b'A=4300 V=6F', b'A=4300 V=61')
    result = analyzer.analyze_isp(data)
    assert result['at_least_two_complete_scans'] and not result['all_complete_scans_match_reference']


def test_complete_initial_partial_isp_scan_suffix_may_be_skipped():
    result = analyzer.analyze_isp(b''.join(isp_scan()[17:]+isp_scan(2)+isp_scan(3)[:4]))
    assert result['complete_scans'] == 1 and result['leading_partial_scan_rows'] == 7
    assert result['trailing_partial_scan_rows'] == 4
    with pytest.raises(ValueError):
        analyzer.analyze_isp(b''.join([isp_scan()[17], isp_scan()[19]]+isp_scan(2)))
