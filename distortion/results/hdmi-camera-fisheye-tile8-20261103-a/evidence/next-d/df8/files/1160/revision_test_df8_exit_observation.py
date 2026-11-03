"""Actual release witness identities must agree; these are CPU data fixtures."""
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

WORK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORK))
import freeze_complete_physical_release_a as freeze


@pytest.fixture
def observation(tmp_path, monkeypatch):
    work = tmp_path / 'own-df8-work'
    work.mkdir()
    output = tmp_path / 'root-observations'
    output.mkdir()
    monkeypatch.setattr(freeze, 'WORK', work)
    monkeypatch.setattr(freeze, 'RAW_EXIT', work / 'raw-worker-exit-observed-a.json')
    monkeypatch.setattr(freeze, 'RAW_LAUNCH', output / 'df8-raw-worker-launch-a.json')
    monkeypatch.setattr(freeze, 'MONITOR_EXIT', output / 'df8-raw-worker-exit-a.json')
    for name in ('run_build_native.py', 'raw-native-completed-a.json', 'build-provider-source-manifest-a.json'):
        (work / name).write_text('actual fixture ' + name)
    stdout = output / 'df8.stdout.log'
    stderr = output / 'df8.stderr.log'
    stdout.write_text('actual process finished fixture')
    stderr.write_text('')
    launch = {'Schema': 'tile8df8-raw-build-worker-launch-v1', 'PID': 13579,
              'StartedUTC': '2026-11-03T15:10:41Z',
              'BuildProviderManifest': str(work / 'build-provider-source-manifest-a.json'),
              'BuildProviderManifestSHA256': freeze.bit.sha(work / 'build-provider-source-manifest-a.json'),
              'Stdout': str(stdout), 'Stderr': str(stderr),
              'UserAuthorizedNewCandidate': True, 'HardwareAccessPlanned': False}
    value = {'Schema': 'tile8df8-raw-worker-exit-observation-v1', 'PID': 13579,
             'ProcessExited': True, 'ExitCode': 0, 'MonitorSessionID': 24680, 'PDriveReleased': True,
             'ObservedUTC': '2026-11-03T15:35:41Z', 'WorkerSource': freeze.bit.ref(work / 'run_build_native.py'),
             'RawCompleted': freeze.bit.ref(work / 'raw-native-completed-a.json')}

    def save():
        freeze.RAW_LAUNCH.write_text(json.dumps(launch))
        value['LaunchReceipt'] = freeze.bit.ref(freeze.RAW_LAUNCH)
        freeze.RAW_EXIT.write_text(json.dumps(value))

    def bind(watched=None):
        return freeze.bind_raw_worker_observation({} if watched is None else watched,
            freeze.bit.sha(freeze.RAW_EXIT), freeze.bit.sha(freeze.RAW_LAUNCH),
            freeze.bit.sha(work / 'build-provider-source-manifest-a.json'))
    save()
    return SimpleNamespace(work=work, launch=launch, value=value, save=save, bind=bind)


def test_real_launch_pid_is_bound_dynamically_and_every_actual_reference_is_watched(observation):
    watched = {}
    result = observation.bind(watched)
    assert result['PID'] == 13579
    assert watched[str(freeze.RAW_LAUNCH)] == freeze.bit.sha(freeze.RAW_LAUNCH)
    for key in ('WorkerSource', 'RawCompleted', 'LaunchReceipt'):
        row = result[key]
        assert watched[row['Path']] == row['SHA256']
    assert watched[observation.launch['Stdout']] == freeze.bit.sha(observation.launch['Stdout'])


@pytest.mark.parametrize('field,value', [('ExitCode', 2), ('ExitCode', False), ('ProcessExited', False),
    ('PDriveReleased', False), ('PID', 892), ('PID', True), ('MonitorSessionID', 0),
    ('Schema', 'tile8df9-raw-worker-exit-observation-v1'), ('ObservedUTC', '2026-11-03T15:00:00Z')])
def test_failed_prior_or_unfinished_worker_cannot_supply_candidate_exit(observation, field, value):
    observation.value[field] = value
    observation.save()
    with pytest.raises(ValueError):
        observation.bind()


@pytest.mark.parametrize('field,value', [('Schema', 'tile8df9-raw-build-worker-launch-v1'), ('PID', 892),
    ('BuildProviderManifestSHA256', '0' * 64), ('BuildProviderManifest', 'another-work/manifest.json'),
    ('UserAuthorizedNewCandidate', False), ('HardwareAccessPlanned', True), ('MonitorSessionID', 111)])
def test_launch_and_observation_must_identify_same_authorized_own_build(observation, field, value):
    observation.launch[field] = value
    observation.save()
    with pytest.raises(ValueError):
        observation.bind()


@pytest.mark.parametrize('field', ['WorkerSource', 'RawCompleted', 'LaunchReceipt'])
def test_a_same_shape_reference_to_another_existing_file_is_rejected(observation, field):
    other = observation.work / 'another-actual-file.json'
    other.write_text('different worker source or evidence')
    observation.value[field] = freeze.bit.ref(other)
    observation.save()
    # save rebinds the normal launch reference; change that after saving.
    if field == 'LaunchReceipt':
        observation.value[field] = freeze.bit.ref(other)
        freeze.RAW_EXIT.write_text(json.dumps(observation.value))
    with pytest.raises(ValueError):
        observation.bind()


@pytest.mark.parametrize('which', ['exit', 'launch', 'build'])
def test_root_supplied_actual_sha_pins_are_mandatory(observation, which):
    pins = [freeze.bit.sha(freeze.RAW_EXIT), freeze.bit.sha(freeze.RAW_LAUNCH),
            freeze.bit.sha(observation.work / 'build-provider-source-manifest-a.json')]
    pins[['exit', 'launch', 'build'].index(which)] = '0' * 64
    with pytest.raises(ValueError):
        freeze.bind_raw_worker_observation({}, *pins)


def test_available_actual_monitor_exit_receipt_cannot_be_omitted(observation):
    freeze.MONITOR_EXIT.write_text('actual monitor result fixture')
    with pytest.raises(ValueError, match='monitor exit receipt'):
        observation.bind()
    observation.value['ActualMonitorExitReceipt'] = freeze.bit.ref(freeze.MONITOR_EXIT)
    observation.save()
    assert observation.bind()['ActualMonitorExitReceipt'] == freeze.bit.ref(freeze.MONITOR_EXIT)


def test_reused_source_level_cache_evidence_retains_true_index9_location():
    assert freeze.PEER_WORK.name == 'hdmi-camera-fisheye-tile8df9-20261103-a'
    assert freeze.cache_contract.UNIT_RECEIPT == freeze.PEER_WORK / 'cache-unit-a/simulation.json'
    value = freeze.bind_cache_and_independent_peer({})
    assert value['CandidateCacheIndexBits'] == 8 and value['OriginalCacheUnitIncludesINDEX8'] is True
    assert value['IndependentCollisionExecutedIndexBits'] == 9
    assert value['CollisionIsSourceLevelEvidenceOnly'] is True
