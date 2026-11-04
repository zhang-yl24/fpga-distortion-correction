"""Local comparison guard/decoder tests; never assemble a successful new result."""
import copy
import importlib.util
import json
from pathlib import Path
import sys

import pytest
import verify_directfill_v3_vs_tile8_a as c
import test_saved_fps_stability_d as fixtures


def metadata(seconds=30, baseline=False):
    return {'Schema': 'tile8df8-saved-uart-stability-review-v1' if baseline else
        'tile8df8v3-saved-uart-stability-review-v1', 'Passed': True,
        'Role': 'baseline-selftest' if baseline else 'candidate', 'BaselineSelfTestOnly': baseline,
        'NewCandidateMeasured': not baseline, 'HardwareAccessedByVerifier': False,
        'EDAExecuted': False, 'FrozenSourceModified': False,
        'Identity': {'IdentityChainVerified': True}, 'WireAnalysis': {'AcquisitionBudgetSeconds': seconds}}


@pytest.mark.parametrize('baseline', [False, True])
def test_correct_role_metadata_fragment_only(baseline):
    c.check_review_metadata(metadata(baseline=baseline), 30, baseline)


@pytest.mark.parametrize('key,value', [('Schema', 'tile8df8-saved-uart-stability-review-v1'),
    ('Schema', 'diagnostic-only'), ('Role', 'baseline-selftest'), ('Passed', False),
    ('BaselineSelfTestOnly', True), ('NewCandidateMeasured', False), ('EDAExecuted', True),
    ('HardwareAccessedByVerifier', True), ('FrozenSourceModified', True)])
def test_v2_baseline_or_failed_review_cannot_pass_as_new_candidate(key, value):
    review = metadata(); review[key] = value
    with pytest.raises(ValueError): c.check_review_metadata(review, 30, False)


@pytest.mark.parametrize('which', ['identity', 'wall'])
def test_review_must_bind_identity_and_explicit_budget(which):
    review = metadata()
    if which == 'identity': review['Identity']['IdentityChainVerified'] = False
    else: review['WireAnalysis']['AcquisitionBudgetSeconds'] = 600
    with pytest.raises(ValueError): c.check_review_metadata(review, 30, False)


def test_every_saved_input_is_rehashed_and_later_drift_rejected(tmp_path):
    path = tmp_path / 'saved'; path.write_bytes(b'old')
    evidence = c.Evidence(); evidence.mapping({str(path): c.sha(path)})
    path.write_bytes(b'new')
    assert evidence.unchanged() is False
    with pytest.raises(ValueError): evidence.mapping({str(path): evidence.inputs[str(path)]})


@pytest.mark.parametrize('values', [{}, {'relative': '0' * 64}, {'D:/not-real': True}])
def test_empty_or_bad_saved_input_mapping_is_refused(values):
    with pytest.raises(ValueError): c.Evidence().mapping(values)


def test_duplicate_json_member_and_nonfinite_are_refused(tmp_path):
    for text in ('{"Passed":true,"Passed":false}', '{"rate":NaN}'):
        path = tmp_path / 'fragment.json'; path.write_text(text)
        with pytest.raises(ValueError): c.read(path)


@pytest.mark.parametrize('value', [None, 'bad', True])
def test_pending_e_source_pin_is_refused_before_loading_or_reading_evidence(monkeypatch, value):
    monkeypatch.setattr(c, 'E_SHA256', value)
    class NoIO:
        def add(self, *ignored): raise AssertionError('unexpected input read')
    with pytest.raises(ValueError, match='pending'): c.load_analyzers(NoIO())


@pytest.mark.parametrize('key', ['Manifest', 'RootReview', 'Wrapper'])
def test_each_pending_final_source_pin_is_refused(monkeypatch, key):
    monkeypatch.setattr(c, 'SOURCE_PINS', {**c.SOURCE_PINS, key: None})
    class NoIO:
        def add(self, *ignored): raise AssertionError('unexpected input read')
    with pytest.raises(ValueError, match='pending'): c.load_analyzers(NoIO())


def test_final_e_and_d_are_loaded_as_read_only_sources_without_provenance_call():
    evidence = c.Evidence(); d = c.load_analyzers(evidence)
    assert d.analyze.__code__.co_filename == str(c.D_SOURCE)
    assert evidence.inputs == {str(c.D_SOURCE): c.D_SHA256, str(c.E_SOURCE): c.E_SHA256}


def full_synthetic_wire_fragment(seconds):
    receipt = fixtures.fixture(seconds)
    tools = c.REPO / 'distortion/tools'
    sys.path.insert(0, str(tools))
    try:
        import hdmi_camera_fisheye_fps as protocol
        import measure_hdmi_fisheye_fps as measurement
        assert c.sha(Path(protocol.__file__)) == fixtures.M.LIBRARIES['hdmi_camera_fisheye_fps.py']
        assert c.sha(Path(measurement.__file__)) == fixtures.M.LIBRARIES['measure_hdmi_fisheye_fps.py']
        raw = fixtures.wire(receipt)
        parser = protocol.Parser(); decoded = parser.feed(raw)
        receipt['host_tools'] = {str(tools / name): digest for name, digest in fixtures.M.LIBRARIES.items()}
        receipt['nominal_clock_summary'] = protocol.summarize(decoded)
        receipt['independent_host_summary'] = measurement.arrival_summary(receipt['frames'])
    finally:
        sys.path.remove(str(tools))
    return receipt, raw


@pytest.mark.parametrize('seconds', [30, 600])
def test_real_d_wire_and_frozen_compatibility_recompute_exactly_for_local_fragments(seconds):
    receipt, raw = full_synthetic_wire_fragment(seconds)
    d = fixtures.M; evidence = c.Evidence()
    review = {'WireAnalysis': d.analyze(receipt, raw, seconds),
        'FrozenCompatibility': d.frozen_compatibility(receipt, raw, evidence)}
    analysis, _ = c.recompute_wire(review, receipt, raw, seconds, d, evidence)
    metrics = c.window_metrics(analysis)
    assert metrics['HostFirstToLastWindowSeconds'] == seconds - 1
    assert metrics['ActualAcquisitionWallSeconds'] == seconds + .01
    assert metrics['WindowCounterIncrements']['scan_repeat_frames'] == (seconds - 1) * 15
    assert metrics['WindowCounterIncrements']['scan_blank_frames'] == 0
    if seconds == 600:
        assert metrics['WindowCounterIncrements']['cache_hits'] == 599 * 112000000
        assert metrics['WindowCounterIncrements']['cache_hits'] > 0xffffffff


@pytest.mark.parametrize('mutation', ['analysis', 'analysis_bool', 'compatibility', 'wire', 'receipt'])
def test_saved_review_counter_crc_receipt_and_compatibility_differences_are_refused(mutation):
    receipt, raw = full_synthetic_wire_fragment(30)
    d = fixtures.M; evidence = c.Evidence()
    review = {'WireAnalysis': d.analyze(receipt, raw, 30),
        'FrozenCompatibility': d.frozen_compatibility(receipt, raw, evidence)}
    if mutation == 'analysis': review['WireAnalysis']['CompleteSamples'] += 1
    elif mutation == 'analysis_bool': review['WireAnalysis']['BlankScanIncrements'] = False
    elif mutation == 'compatibility': review['FrozenCompatibility']['FrozenRecordedSummariesVerified'] = False
    elif mutation == 'wire': raw = raw[:32] + bytes([raw[32] ^ 1]) + raw[33:]
    else: receipt['frames'][5]['processed_frames'] += 1
    with pytest.raises(ValueError): c.recompute_wire(review, receipt, raw, 30, d, evidence)


def test_comparison_uses_true_host_window_rates_and_does_not_assert_30fps():
    receipt, raw = full_synthetic_wire_fragment(30)
    baseline = fixtures.M.analyze(receipt, raw, 30)
    candidate = copy.deepcopy(baseline)
    candidate['IndependentHostRates']['unique_presented_frames_per_second'] = 22.5
    result = c.compare_metrics(baseline, candidate)
    assert result['HostUniquePresentedFPSRatio'] == 1.5
    assert result['HostUniquePresentedFPSImprovementPercent'] == 50.0
    assert result['Target30FPSAsserted'] is False
    assert result['Baseline']['HostFirstToLastWindowSeconds'] == 29


def test_missing_candidate_never_falls_back_or_creates_a_comparison(tmp_path):
    output = c.HERE / 'comparison-must-not-exist-peer-test.json'
    assert not output.exists()
    with pytest.raises(ValueError): c.main(['--review-30', str(tmp_path / 'missing-30.json'),
        '--review-600', str(tmp_path / 'missing-600.json'), '--output', str(output)])
    assert not output.exists()


def test_baseline_review_bytes_are_fixed_without_replaying_its_large_identity_closure():
    assert c.sha(c.BASELINE_REVIEW) == c.BASELINE_REVIEW_SHA256
    value = c.read(c.BASELINE_REVIEW)
    c.check_review_metadata(value, 30, True)
    assert value['WireAnalysis']['IndependentHostRates']['unique_presented_frames_per_second'] == 15.0002616769239
    assert value['WireAnalysis']['HostFirstToLastWindowSeconds'] == 28.99949410010595
