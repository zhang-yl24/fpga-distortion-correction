"""No EDA: explicit1800 budget, original full Tcl, literal observations and provenance."""
from pathlib import Path
import importlib.util
import json
import re
import sys
import time

import pytest

WORK = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(WORK), str(WORK.parents[1] / 'tools')]
import hdmi_camera_fisheye_tile8df8v3_physical as physical
import hdmi_camera_fisheye_tile8df8v3_application_observer as observation
import freeze_complete_physical_release_v3_a as freeze


@pytest.mark.parametrize('maximum', [60, 600, 601, 1800])
def test_public_application_explicit_budget_reaches_full_source_gate(maximum, monkeypatch, tmp_path):
    monkeypatch.setattr(physical.build, 'work_path', lambda value: Path(value))
    def reached(path):
        raise RuntimeError('full-public-audit-still-required')
    monkeypatch.setattr(physical, 'bind_audit', reached)
    with pytest.raises(RuntimeError, match='full-public-audit'):
        physical.application_recipe('audit', 'warnings', ['preflight'], tmp_path, maximum)


@pytest.mark.parametrize('maximum', [59, 1801, 3600, True, 1800., None])
def test_public_application_rejects_unbounded_or_false_budget(maximum, monkeypatch, tmp_path):
    monkeypatch.setattr(physical.build, 'work_path', lambda value: Path(value))
    monkeypatch.setattr(physical, 'bind_audit', lambda value: pytest.fail('source gate must not run'))
    with pytest.raises(ValueError, match='60..1800'):
        physical.application_recipe('audit', 'warnings', ['preflight'], tmp_path, maximum)


@pytest.fixture(scope='module')
def original_plan():
    return json.loads((WORK / 'physical-v2-a/stage-plan.json').read_text())


def test_entire_actual_tcl_retains_all650_selectors_and3343_queries(original_plan):
    rendered = physical.render_application(original_plan)
    original = (WORK / 'physical-v2-a/stage.tcl').read_text(encoding='ascii')
    expected = original.replace('TILE8DF8V2', 'TILE8DF8V3')
    assert observation.strip_markers(rendered) == expected
    assert len(original_plan['NativeSelectors']) == 650
    assert len(original_plan['ExactCommands']) == 1096
    assert len(re.findall(r'get_pins -hierarchical -regexp \{([^{}]+)\}', rendered)) == 3343
    assert '[catch' not in rendered and '[clock' not in rendered
    assert rendered.count(observation.PREFIX + '|QUERY|') == 110


@pytest.mark.parametrize('label', ['lowercase', 'INIT}\nset_false_path', 'A;B', '', 'INIT [clock]'])
def test_observation_labels_cannot_inject_tcl(label):
    with pytest.raises(ValueError): observation.mark(label)


@pytest.mark.parametrize('text', ['puts {' + observation.PREFIX + '|INIT|BEGIN}\nset_false_path\n',
                                 'puts {' + observation.PREFIX + '|lowercase}\nflush stdout\n'])
def test_marker_strip_cannot_remove_unreviewed_command_pair(text):
    with pytest.raises(ValueError): observation.strip_markers(text)


def test_host_observation_defers_partial_lines_and_binds_real_native_match_count(tmp_path):
    path = tmp_path / 'stdout.log'
    path.write_bytes((observation.PREFIX + '|QUERY|0|BE').encode())
    observer = observation.HostObserver(tmp_path, time.monotonic())
    observer.poll()
    assert observer.records == []
    with path.open('ab') as stream:
        stream.write(('GIN\nI: Timing-5001: actual native line\n' + observation.PREFIX + '|QUERY|0|RETURN\n').encode())
    observer.poll()
    report = observer.close()
    assert len(report['Markers']) == 2 and report['ObservedNativeTiming5001Lines'] == 1
    assert report['Markers'][0]['NativeTiming5001LinesSeen'] == 0
    assert report['Markers'][1]['NativeTiming5001LinesSeen'] == 1
    assert report['Markers'][1]['ObservedHostMonotonicNS'] >= report['Markers'][0]['ObservedHostMonotonicNS']
    assert report['TimestampsAreExternalHostObservations'] is True
    assert report['ObservationCreatesNoSelectorOrPhysicalAcceptance'] is True


@pytest.mark.parametrize('constant', ['ORIGINAL_MANIFEST_SHA', 'ORIGINAL_ROOT_REVIEW_SHA'])
def test_overlay_provenance_cannot_choose_only_one_original_root(constant, monkeypatch):
    monkeypatch.setattr(freeze, constant, '0' * 64)
    with pytest.raises(ValueError): freeze.bind_original_frozen_v2({})


def test_postfreeze_verify_also_requires_original_overlay_provenance(tmp_path, monkeypatch):
    path = tmp_path / 'manifest.json'
    value = {'Schema':freeze.MANIFEST_SCHEMA, 'ProviderRevision':freeze.REVISION, 'Passed':True, 'InputDrift':[],
             'ManifestSelfIncluded':False, 'FuturePhysicalProofIncluded':False,
             'PriorPhysicalTimingOrAcceptanceInherited':False, 'InputSHA256':{}}
    path.write_text(json.dumps(value))
    monkeypatch.setattr(freeze, 'MANIFEST', path)
    def mandatory(watched): raise RuntimeError('both-original-provenance-files-required')
    monkeypatch.setattr(freeze, 'bind_original_frozen_v2', mandatory)
    with pytest.raises(RuntimeError, match='both-original'):
        freeze.verify_manifest(path, freeze.build.sha(path), {})
