"""Pure recovery refusal/identity tests. No providers, P: access or native run."""
import ast
import copy
from pathlib import Path

import pytest
import run_df8_v3_tail_recovery_b as c
import freeze_df8_v3_tail_recovery_b as f


def failed_fragment():
    return {'Schema': 'hdmi-camera-fisheye-tile8df8v3-targeted-native-query-v1',
        'ExecutionPassed': False, 'TimedOut': True, 'MaximumSeconds': 1200, 'ExitCode': 1,
        'Cleanup': {'Complete': True, 'OwnedPID': c.PRIOR_NATIVE_PID}, 'SourceProof': {'Path': str(c.APP), 'SHA256': c.APP_SHA},
        'SourceADF': str(c.FINAL_ADF), 'SourceADFSHA256': c.FINAL_ADF_SHA, 'QueryBody': str(c.BODY),
        'FinishedUTC': '2026-11-03T20:27:24+00:00'}


def test_failed_timeout_metadata_is_only_provenance_and_missing_drift_is_disclosed():
    c.check_prior_failure(failed_fragment())


@pytest.mark.parametrize('key,value', [('ExecutionPassed', True), ('TimedOut', False), ('MaximumSeconds', 1800),
    ('ExitCode', 0), ('ExitCode', False), ('SourceADFSHA256', '0' * 64), ('SourceADF', 'P:/input.adf'),
    ('QueryBody', 'another-body'), ('Cleanup', {'Complete': False}), ('InputDrift', ['changed'])])
def test_prior_stage_must_really_fail_cleanly_at_its_original_bound(key, value):
    v = failed_fragment(); v[key] = value
    with pytest.raises(ValueError): c.check_prior_failure(v)


def go_fragment():
    manifest = {'Path': str(c.MANIFEST), 'SHA256': 'a' * 64}
    prior = {'Path': str(c.PRIOR_EXIT), 'SHA256': 'b' * 64}
    root_observation = {'Path': str(c.ROOT_EXIT_OBSERVATION), 'SHA256': 'c' * 64}
    value = {'Schema': 'tile8df8v3-tail-recovery-root-go-v1', 'ProviderRevision': c.REVISION,
        'RecoveryRevision': c.RECOVERY_REVISION, 'RootAuthorizedTailRecovery': True,
        'PriorWorkerEnded': True, 'PDriveReleased': True,
        'ProviderSourceManifest': {'Path': str(c.ORIGINAL_MANIFEST), 'SHA256': c.ORIGINAL_SHA},
        'RecoverySourceManifest': manifest, 'PriorWorkerExitObservation': prior, 'RootProcessExitObservation': root_observation}
    return value, manifest, prior, root_observation


def test_root_go_fragment_needs_both_manifest_families_and_actual_exit_ref():
    c.check_handoff(*go_fragment())


@pytest.mark.parametrize('key', ['RootAuthorizedTailRecovery', 'PriorWorkerEnded', 'PDriveReleased',
    'ProviderSourceManifest', 'RecoverySourceManifest', 'PriorWorkerExitObservation', 'RootProcessExitObservation'])
def test_missing_or_changed_root_authority_cannot_execute(key):
    value, manifest, prior, root_observation = go_fragment(); value.pop(key)
    with pytest.raises(ValueError): c.check_handoff(value, manifest, prior, root_observation)


def test_no_explicit_exact_handoff_does_not_reach_a_manifest_or_provider(tmp_path, monkeypatch):
    monkeypatch.setattr(c, 'bind_recovery_manifest', lambda *a: (_ for _ in ()).throw(AssertionError('unexpected bind')))
    with pytest.raises(ValueError): c.execute(tmp_path / 'caller-created-go.json', 'a' * 64)


def test_original_146_command_body_is_retained_without_public_derivation():
    assert c.sha(c.BODY) == c.BODY_SHA
    c.check_body(c.local(c.BODY).read_text(encoding='ascii'))


@pytest.mark.parametrize('mutation', ['remove_site', 'reorder', 'drop_selector', 'change_report_bound', 'catch', 'env'])
def test_body_command_set_order_and_budget_cannot_be_reduced_or_patched(mutation):
    text = c.local(c.BODY).read_text(encoding='ascii'); lines = text.splitlines()
    if mutation == 'remove_site': lines.pop(0)
    elif mutation == 'reorder': lines[0], lines[1] = lines[1], lines[0]
    elif mutation == 'drop_selector': lines.pop(144)
    elif mutation == 'change_report_bound': lines[145] = lines[145].replace('-max_path 10000', '-max_path 1')
    elif mutation == 'catch': lines[144] = 'catch {' + lines[144] + '}'
    else: lines.insert(0, 'set env(OMP_NUM_THREADS) 1')
    with pytest.raises(ValueError): c.check_body('\n'.join(lines) + '\n')


@pytest.mark.parametrize('flag', c.PHYSICAL_FLAGS)
def test_every_complete_public_physical_flag_is_mandatory(flag):
    proof = {'Schema': 'hdmi-camera-fisheye-tile8df8v3-final-physical-proof-v1', 'Target': 'hdmi_camera_fisheye_top',
        **{key: True for key in c.PHYSICAL_FLAGS}, 'NativeMaxPaths': 10000, 'DataCDC': {'Missing': [], 'Violations': []},
        'FinalADF': {'Path': str(c.FINAL_ADF), 'SHA256': c.FINAL_ADF_SHA}}
    proof[flag] = False
    with pytest.raises(ValueError): c.check_final_flags(proof)


@pytest.mark.parametrize('row', [{'ProcessId': c.PRIOR_PID, 'Name': 'python.exe', 'CommandLine': 'unrelated'},
    {'ProcessId': 42, 'Name': 'pds_shell.exe', 'CommandLine': None},
    {'ProcessId': 43, 'Name': 'python.exe', 'CommandLine': 'python run_physical_v3_a.py'},
    {'ProcessId': 44, 'Name': 'python.exe', 'CommandLine': 'python run_df8_v3_tail_recovery_b.py'}])
def test_live_prior_native_or_competing_worker_is_refused_in_pure_os_fragment(row):
    with pytest.raises(ValueError): c.check_process_rows([row], 99)


def test_own_control_process_and_unrelated_process_are_not_terminated_or_rejected():
    c.check_process_rows([{'ProcessId': 99, 'Name': 'python.exe', 'CommandLine': c.SELF.name},
        {'ProcessId': 72, 'Name': 'powershell.exe', 'CommandLine': 'python ' + c.SELF.name},
        {'ProcessId': 71, 'Name': 'unrelated.exe', 'CommandLine': None}], 99)


@pytest.mark.parametrize('actual,rows', [(None, []), ({'Cleanup': {'Complete': False}}, []),
    ({'Cleanup': {'Complete': True}, 'OwnedPID': 12}, [{'ProcessId': 12, 'Name': 'native.exe'}]),
    ({'Cleanup': {'Complete': True}, 'OwnedPID': 12}, [{'ProcessId': 13, 'Name': 'pds_shell.exe'}])])
def test_alias_release_is_refused_if_native_cleanup_or_actual_exit_is_unknown(actual, rows):
    with pytest.raises(ValueError): c.check_native_exit_before_alias_release(rows, actual, True)


def test_alias_release_guard_accepts_only_clean_and_observed_absent_native():
    c.check_native_exit_before_alias_release([{'ProcessId': 70, 'Name': 'unrelated.exe'}],
        {'Cleanup': {'Complete': True}, 'OwnedPID': 12}, True)


def test_input_hash_map_refuses_drift_and_does_not_overwrite_a_conflicting_pin(tmp_path):
    p = tmp_path / 'local-input'; p.write_bytes(b'original')
    inputs = {}; c.add(inputs, p)
    p.write_bytes(b'changed')
    with pytest.raises(ValueError): c.verify_closure(inputs)
    with pytest.raises(ValueError): c.add(inputs, p)


def test_fresh_json_never_overwrites_prior_evidence(tmp_path):
    p = tmp_path / 'saved.json'; p.write_bytes(b'preserve')
    with pytest.raises(FileExistsError): c.fresh(p, {'synthetic': True})
    assert p.read_bytes() == b'preserve'


def test_alias_flag_is_cleared_before_post_cleanup_checkpoint_and_native_budget_is_exact():
    text = c.SELF.read_text(encoding='utf-8'); tree = ast.parse(text)
    assert text.index("result['OwnedAliasReleased'] = True") < text.index('owned_alias = False', text.index("result['OwnedAliasReleased'] = True")) < text.index("checkpoint('after-own-cleanup')")
    native = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
        and isinstance(n.func.value, ast.Name) and n.func.value.id == 'target' and n.func.attr == 'prepare']
    assert len(native) == 1 and next(k.value.value for k in native[0].keywords if k.arg == 'maximum') == 1200
    assert 'os.environ' not in text and 'taskkill' not in text and 'Stop-Process' not in text


def test_import_and_freezer_have_no_production_provider_calls_or_native_launch():
    tree = ast.parse(f.SELF.read_text(encoding='utf-8'))
    calls = [n.func for n in ast.walk(tree) if isinstance(n, ast.Call)]
    assert not any(isinstance(fn, ast.Attribute) and fn.attr in ('derive', 'prepare_application', 'execute', 'Popen', 'run') for fn in calls)
    top = ast.parse(c.SELF.read_text(encoding='utf-8')).body
    assert not any(isinstance(n, ast.Import) and any(a.name.startswith('hdmi_') for a in n.names) for n in top)


def test_freezer_never_grants_go_or_replaces_original_source_authority():
    text = f.SELF.read_text(encoding='utf-8')
    assert "'ReplacesOriginalProviderManifest': False" in text and "'RootExecutionAuthorizationGranted': False" in text
    assert "'OriginalFrozenInputCount': 1038" in text


def test_peer_must_cover_current_control_freezer_and_tests_sources():
    required = (c.SELF, f.SELF, Path(__file__).resolve(), c.LAUNCHER)
    peer = {'Passed': True, 'IndependentPeerReviewPerformed': True, 'ProviderRevision': c.REVISION,
        'RecoveryRevision': c.RECOVERY_REVISION, 'InputDrift': [], 'SourceContractReviewOnly': True,
        'EDAExecuted': False, 'HardwareAccessed': False, 'InputSHA256': {str(p): c.sha(p) for p in required}}
    f.check_peer(peer, required)
    peer['InputSHA256'].pop(str(required[0]))
    with pytest.raises(ValueError): f.check_peer(peer, required)


def test_actual_saved_original_exit_and_root_os_observation_are_consistent_without_new_runtime_io():
    failed, launch, observed = c.read(c.FAILED), c.read(c.LAUNCH), c.read(c.PRIOR_EXIT)
    c.check_prior_failure(failed); c.check_prior_exit(observed, launch, failed)
    c.check_root_exit_observation(c.read(c.ROOT_EXIT_OBSERVATION), c.ref(c.PRIOR_EXIT), observed)


@pytest.mark.parametrize('key,value', [('WorkerAndOwnedPDSAbsent', False), ('PDriveReleased', False),
    ('RootElevatedReadOnlyOSChecks', False), ('NoProcessTerminatedByObserver', False),
    ('PDSProcessList', [2336]), ('OriginalWorkerPID', 1), ('OriginalMonitorSessionID', 2),
    ('ObservedUTC', '2026-11-03T19:00:00+00:00')])
def test_root_os_observation_cannot_be_weakened_or_precede_actual_worker_exit(key, value):
    root = c.read(c.ROOT_EXIT_OBSERVATION); root[key] = value
    with pytest.raises(ValueError): c.check_root_exit_observation(root, c.ref(c.PRIOR_EXIT), c.read(c.PRIOR_EXIT))


def test_hidden_independent_launcher_is_an_explicit_frozen_source_root():
    assert c.sha(c.LAUNCHER) == c.LAUNCHER_SHA
    text = c.LAUNCHER.read_text()
    assert '-WindowStyle Hidden' in text and '$taskWorkerPin=' in text and '$taskLauncherPin=' in text
    assert text.index('$taskWorkerPin=') < text.index('Start-Process')
    assert text.index('$taskLauncherPin=') < text.index('Start-Process')
    assert 'Stop-Process' not in text and 'taskkill' not in text
