"""Explicit, separately frozen recovery of the unchanged v3 query/final tail.

Importing this module performs no provider import/derive or native action.
Only --execute with the root's exact reviewed handoff can run one fresh query.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

SELF = Path(__file__).resolve()
OUT = SELF.parent
REPO = OUT.parents[1]
TOOLS = REPO / 'distortion/tools'
WORK = REPO / 'distortion/work/hdmi-camera-fisheye-tile8df8-20261103-a'
REVISION = 'tile8df8v3-budget1800-a'
RECOVERY_REVISION = 'tile8df8v3-same-source-tail-recovery-b'
ORIGINAL_MANIFEST = WORK / 'physical-release-provider-source-manifest-v3-a.json'
ORIGINAL_SHA = '7b2c444b1e6e7d482c1875307fbc7b717689d0f5da9eaf8fac49ef249540a8fb'
MANIFEST = OUT / 'df8-v3-tail-recovery-source-manifest-b.json'
HANDOFF = WORK / 'physical-tail-recovery-v3-b-go-a.json'
LAUNCH = OUT / 'df8-physical-worker-launch-v3-a.json'
PRIOR_EXIT = OUT / 'df8-physical-worker-exit-v3-a.json'
ROOT_EXIT_OBSERVATION = OUT / 'v3-original-physical-exit-root-observation-a.json'
PRIOR_WORKER = WORK / 'run_physical_v3_a.py'
PRIOR_PID = 43412
PRIOR_NATIVE_PID = 2336
FAILED = WORK / 'checks-scoped-v3-a-00/result.json'
BODY = WORK / 'physical-bodies-v3-a/checks-00.tcl'
BODY_SHA = '794cc64e335181ae8977d9e84474caa9ecc6e69fa9ac4334abf0677518dcb4a0'
APP = WORK / 'physical-v3-a/result.json'
APP_SHA = '23a00892c2ce82dc67945f87704e7fb3991a8765fb4696b680f716647f757d95'
FINAL_ADF = WORK / 'physical-v3-a/input.adf'
FINAL_ADF_SHA = '2b6e662fb25cfb774a494743947c80325fd4796b423b3e0756a0f877117ae430'
EXPORT = WORK / 'export-scoped-v3-a/result.json'
ROUTE = WORK / 'route-scoped-v3-a/result.json'
SCOPE = WORK / 'audit-a/scope.json'
BUILD_PLAN = WORK / 'build-a/plan.json'
QUERY_WORK = WORK / 'checks-scoped-v3-b-00'
FINAL_PROOF = WORK / 'final-proof-v3-a.json'
START = OUT / 'df8-v3-tail-recovery-start-b.json'
RESULT = OUT / 'df8-v3-tail-recovery-result-b.json'
LAUNCHER = OUT / 'launch_df8_v3_tail_recovery_b.ps1'
LAUNCHER_SHA = 'ca0dbc2a0ff72295ffc9002a45746195b9f039780383c4be651353b6aff0865b'
PHYSICAL_FLAGS = ('Passed', 'STAAllTenPassed', 'NativeWarningsReviewed', 'SourceDiagnosticReviewPassed',
    'NetlistEquivalent', 'AllFFPlacementsEquivalent', 'RoutesUnchanged', 'ResetAccepted',
    'SourceSamplingIsolatedVerified', 'VendorDDRClockResetAccepted', 'FrameBoundaryViewSelectionAccepted',
    'FisheyeProfileAccepted', 'UserCDCAccepted')
FUTURE = (MANIFEST, HANDOFF, START, RESULT, FINAL_PROOF)


def require(ok, message):
    if not ok: raise ValueError(message)


def utc(): return datetime.now(timezone.utc).isoformat()


def timestamp(value):
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    require(result.tzinfo is not None, 'timezone-aware timestamp required')
    return result


def local(path):
    text = str(Path(path).absolute())
    if os.name == 'nt' and not text.startswith('\\\\?\\'):
        text = '\\\\?\\UNC\\' + text[2:] if text.startswith('\\\\') else '\\\\?\\' + text
    return Path(text)


def sha(path):
    result = hashlib.sha256()
    with local(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b''): result.update(chunk)
    return result.hexdigest()


def read(path):
    def unique(rows):
        result = {}
        for key, value in rows:
            require(key not in result, 'duplicate JSON key'); result[key] = value
        return result
    return json.loads(local(path).read_text(encoding='utf-8-sig'), object_pairs_hook=unique,
        parse_constant=lambda value: (_ for _ in ()).throw(ValueError('nonfinite JSON: ' + value)))


def add(inputs, path, expected=None):
    path = Path(path).absolute()
    require(path == path.resolve() and path.drive.upper() != 'P:' and not str(path).startswith('\\\\?\\')
        and local(path).is_file(), 'canonical original existing input required: ' + str(path))
    require(expected is None or type(expected) is str and re.fullmatch('[0-9a-f]{64}', expected), 'exact SHA256 required')
    actual = sha(path)
    require(expected is None or actual == expected, 'input SHA mismatch: ' + str(path))
    require(str(path) not in inputs or inputs[str(path)] == actual, 'conflicting input SHA')
    inputs[str(path)] = actual
    return path


def merge(inputs, mapping):
    require(type(mapping) is dict and mapping, 'complete nonempty input map required')
    for path, digest in mapping.items():
        require(type(path) is str and Path(path).is_absolute(), 'absolute input map identity required')
        add(inputs, path, digest)


def ref(path): return {'Path': str(Path(path).resolve()), 'SHA256': sha(path)}


def binding(inputs, value):
    require(type(value) is dict and set(value) == {'Path', 'SHA256'}, 'exact Path/SHA256 reference required')
    return add(inputs, value['Path'], value['SHA256'])


def fresh(path, value):
    with local(path).open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, allow_nan=False); stream.write('\n')


def check_body(text):
    lines = text.splitlines()
    require(text.isascii() and len(lines) == 146 and len(set(lines[:144])) == 144 and
        all(re.fullmatch(r'show -dev_instance \{[A-Za-z0-9_]+\}', line) for line in lines[:144]) and
        lines[144].startswith('get_pins -hierarchical -regexp {') and
        lines[145].startswith('report_path_timing -delay_type min_max -max_path 10000 -nworst 8 -report_exception TRUE '),
        'complete unchanged 144-site/selector/interstage body required')
    require(hashlib.sha256(text.encode('ascii')).hexdigest() == BODY_SHA, 'original 146-command body changed')


def check_prior_failure(value):
    require(value.get('Schema') == 'hdmi-camera-fisheye-tile8df8v3-targeted-native-query-v1' and
        value.get('ExecutionPassed') is False and value.get('TimedOut') is True and
        value.get('MaximumSeconds') == 1200 and type(value.get('ExitCode')) is int and value['ExitCode'] != 0 and
        value.get('Cleanup', {}).get('Complete') is True and value.get('InputDrift') in (None, []) and
        value.get('Cleanup', {}).get('OwnedPID') == PRIOR_NATIVE_PID and
        value.get('SourceProof') == {'Path': str(APP), 'SHA256': APP_SHA} and
        value.get('SourceADF') == str(FINAL_ADF) and value.get('SourceADFSHA256') == FINAL_ADF_SHA and
        value.get('QueryBody') == str(BODY), 'real cleanly ended original bounded query timeout required')
    timestamp(value['FinishedUTC'])


def check_prior_exit(value, launch, failed):
    require(value.get('Schema') == 'tile8df8v3-physical-worker-exit-v1' and
        type(value.get('PID')) is int and value['PID'] == PRIOR_PID and
        type(value.get('ExitCode')) is int and value['ExitCode'] != 0 and value.get('ObserverOnly') is True and
        value.get('CurrentContextPVisible') is False, 'actual root-observed original worker exit/P-free evidence required')
    require(launch.get('Schema') == 'tile8df8v3-physical-worker-launch-v1' and launch.get('PID') == PRIOR_PID and
        launch.get('WorkerSource') == str(PRIOR_WORKER) and launch.get('WorkerSourceSHA256') == sha(PRIOR_WORKER) and
        launch.get('ProviderSourceManifest') == str(ORIGINAL_MANIFEST) and
        launch.get('ProviderSourceManifestSHA256') == ORIGINAL_SHA,
        'actual original PID/source/provider launch identity required')
    require(timestamp(value['ObservedExitUTC']) >= timestamp(failed['FinishedUTC']) >= timestamp(launch['StartedUTC']),
        'worker exit must follow this actual timed-out stage')


def check_root_exit_observation(value, prior_exit_ref, observed_exit):
    require(value.get('Schema') == 'tile8df8v3-original-physical-exit-root-observation-v1' and
        value.get('OriginalWorkerPID') == PRIOR_PID and value.get('OriginalMonitorSessionID') == 29731 and
        value.get('ActualMonitorExitReceipt') == prior_exit_ref and value.get('PDSProcessList') == [] and
        all(value.get(k) is True for k in ('WorkerAndOwnedPDSAbsent', 'PDriveReleased',
            'RootElevatedReadOnlyOSChecks', 'NoProcessTerminatedByObserver')) and
        value.get('PhysicalPassed') is False and value.get('HardwareAccessed') is False and
        timestamp(value['ObservedUTC']) >= timestamp(observed_exit['ObservedExitUTC']),
        'actual root OS observation of prior worker/native exit and P: release required')


def check_handoff(value, manifest_ref, prior_exit_ref, root_observation_ref):
    require(value.get('Schema') == 'tile8df8v3-tail-recovery-root-go-v1' and
        value.get('ProviderRevision') == REVISION and value.get('RecoveryRevision') == RECOVERY_REVISION and
        all(value.get(k) is True for k in ('RootAuthorizedTailRecovery', 'PriorWorkerEnded', 'PDriveReleased')) and
        value.get('ProviderSourceManifest') == {'Path': str(ORIGINAL_MANIFEST), 'SHA256': ORIGINAL_SHA} and
        value.get('RecoverySourceManifest') == manifest_ref and value.get('PriorWorkerExitObservation') == prior_exit_ref and
        value.get('RootProcessExitObservation') == root_observation_ref,
        'new root GO must explicitly bind old provider and separate recovery source/exit authority')


def check_final_flags(proof):
    require(proof.get('Schema') == 'hdmi-camera-fisheye-tile8df8v3-final-physical-proof-v1' and
        proof.get('Target') == 'hdmi_camera_fisheye_top' and all(proof.get(k) is True for k in PHYSICAL_FLAGS) and
        proof.get('NativeMaxPaths') == 10000 and proof.get('DataCDC', {}).get('Missing') == [] and
        proof.get('DataCDC', {}).get('Violations') == [] and proof.get('FinalADF') ==
        {'Path': str(FINAL_ADF), 'SHA256': FINAL_ADF_SHA}, 'complete unchanged final physical proof required')


def verify_closure(inputs):
    drift = [name for name, expected in inputs.items() if not local(name).is_file() or sha(name) != expected]
    require(not drift, 'recovery source/evidence input drift: ' + repr(drift))


def bind_recovery_manifest(path, expected):
    require(Path(path).resolve() == MANIFEST, 'exact separate recovery manifest required')
    inputs = {}; add(inputs, path, expected)
    value = read(path)
    require(value.get('Schema') == 'tile8df8v3-supplemental-recovery-source-manifest-v1' and value.get('Passed') is True and
        value.get('ProviderRevision') == REVISION and value.get('RecoveryRevision') == RECOVERY_REVISION and
        value.get('OriginalProviderManifest') == {'Path': str(ORIGINAL_MANIFEST), 'SHA256': ORIGINAL_SHA} and
        value.get('OriginalFrozenInputCount') == 1038 and value.get('InputDrift') == [] and
        value.get('ReplacesOriginalProviderManifest') is False and value.get('EDAExecuted') is False and
        value.get('HardwareAccessed') is False, 'separate complete reviewed recovery source freeze required')
    merge(inputs, value['InputSHA256'])
    require(all(str(path) not in value['InputSHA256'] for path in FUTURE) and
        not any(Path(name).is_relative_to(QUERY_WORK) for name in value['InputSHA256']), 'circular future recovery input')
    original = read(add(inputs, ORIGINAL_MANIFEST, ORIGINAL_SHA))
    require(original.get('Schema') == 'hdmi-camera-fisheye-tile8df8v3-provider-source-manifest-v1' and
        original.get('Passed') is True and original.get('ProviderRevision') == REVISION and
        len(original.get('InputSHA256', {})) == 1038, 'actual immutable original 1038-input provider authority required')
    require(all(value['InputSHA256'].get(name) == digest for name, digest in original['InputSHA256'].items()),
        'supplement must retain every original provider input unchanged')
    for selected in (SELF, LAUNCHER, BODY, APP, EXPORT, ROUTE, SCOPE, FAILED, LAUNCH, PRIOR_EXIT, ROOT_EXIT_OBSERVATION, FINAL_ADF, BUILD_PLAN):
        require(str(selected) in value['InputSHA256'], 'required recovery evidence omitted: ' + str(selected))
    require(value['InputSHA256'][str(LAUNCHER)] == LAUNCHER_SHA, 'reviewed hidden own-worker launcher changed')
    require(sha(BODY) == BODY_SHA, 'original body byte SHA changed')
    check_body(local(BODY).read_text(encoding='ascii'))
    require(sha(APP) == APP_SHA and sha(FINAL_ADF) == FINAL_ADF_SHA, 'actual passed application/final ADF changed')
    failed, launch, observed = read(FAILED), read(LAUNCH), read(PRIOR_EXIT)
    check_prior_failure(failed); check_prior_exit(observed, launch, failed)
    check_root_exit_observation(read(ROOT_EXIT_OBSERVATION), ref(PRIOR_EXIT), observed)
    require(value.get('PriorWorkerExitObservation') == ref(PRIOR_EXIT), 'supplement uses another worker observation')
    require(value.get('RootProcessExitObservation') == ref(ROOT_EXIT_OBSERVATION), 'supplement omits actual root OS exit observation')
    return value, inputs


def process_snapshot():
    """Read-only actual OS process observation; no terminate/suspend operation."""
    require(os.name == 'nt', 'Windows runtime required')
    command = "Get-CimInstance Win32_Process | Select-Object ProcessId,Name,CommandLine | ConvertTo-Json -Compress"
    result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-WindowStyle', 'Hidden', '-Command', command],
        capture_output=True, text=True, check=True, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    rows = json.loads(result.stdout)
    require(type(rows) is list and rows, 'actual process snapshot unavailable')
    return rows


def check_process_rows(rows, current_pid):
    require(type(rows) is list and rows, 'actual process rows required')
    require(not any(int(row['ProcessId']) in (PRIOR_PID, PRIOR_NATIVE_PID) or row['Name'].lower() == 'pds_shell.exe' or
        row['Name'].lower() in ('python.exe', 'pythonw.exe') and int(row['ProcessId']) != current_pid and row.get('CommandLine') and any(name in row['CommandLine'] for name in
        ('run_physical_v3_a.py', 'run_physical_v2_a.py', SELF.name)) for row in rows),
        'prior/native/another recovery worker is still alive')


def check_native_exit_before_alias_release(rows, actual, requested):
    if requested:
        require(type(actual) is dict and actual.get('Cleanup', {}).get('Complete') is True,
            'cannot release own alias without actual native cleanup evidence')
    owned_pid = actual.get('OwnedPID') if type(actual) is dict else None
    if type(actual) is dict and actual.get('EDAExecuted') is True:
        require(type(owned_pid) is int and owned_pid > 0, 'actual native PID required before alias release')
    require(not any(row['Name'].lower() == 'pds_shell.exe' or owned_pid is not None and
        int(row['ProcessId']) == owned_pid for row in rows), 'native process still alive; preserve its alias for root')


def require_quiescent():
    require(not Path('P:/').exists(), 'P: must be genuinely free before recovery')
    check_process_rows(process_snapshot(), os.getpid())
    return {'ObservedUTC': utc(), 'PriorPIDAbsent': True, 'NativePDSAbsent': True, 'PDriveFree': True}


def execute(handoff_path, handoff_sha):
    require(Path(handoff_path).resolve() == HANDOFF, 'exact root recovery handoff path required')
    root_inputs = {}; add(root_inputs, HANDOFF, handoff_sha); handoff = read(HANDOFF)
    manifest_path = binding(root_inputs, handoff['RecoverySourceManifest'])
    print(json.dumps({'Stage': 'recovery-manifest-bind', 'Started': True, 'UTC': utc()}), flush=True)
    manifest, inputs = bind_recovery_manifest(manifest_path, handoff['RecoverySourceManifest']['SHA256'])
    inputs.update(root_inputs)
    check_handoff(handoff, ref(MANIFEST), ref(PRIOR_EXIT), ref(ROOT_EXIT_OBSERVATION))
    require(not any(local(path).exists() for path in (START, RESULT, FINAL_PROOF, QUERY_WORK)), 'fresh recovery tail outputs required')
    observation = require_quiescent()
    verify_closure(inputs)
    result = {'Schema': 'tile8df8v3-tail-recovery-execution-v1', 'RecoveryRevision': RECOVERY_REVISION,
        'ProviderRevision': REVISION, 'StartedUTC': utc(), 'Passed': False, 'FinalProofVerified': False,
        'OriginalProviderManifest': ref(ORIGINAL_MANIFEST), 'RecoveryControlManifest': ref(MANIFEST),
        'RootRecoveryGO': ref(HANDOFF), 'PriorWorkerExitObservation': ref(PRIOR_EXIT), 'InitialQuiescence': observation,
        'RootProcessExitObservation': ref(ROOT_EXIT_OBSERVATION),
        'OriginalPhysicalWorkerClaimedSuccessful': False, 'OriginalFailedPartialUsedAsAcceptedEvidence': False,
        'EDARequested': False, 'EDAExecuted': False, 'HardwareAccessed': False, 'BitstreamGenerated': False, 'InputDrift': [],
        'RehashEvents': [], 'OwnedAliasCreated': False, 'OwnedAliasReleased': False}
    fresh(START, result)
    owned_alias = False
    actual = None
    error = None
    def checkpoint(stage):
        verify_closure(inputs)
        event = {'Stage': stage, 'UTC': utc(), 'Inputs': len(inputs), 'InputDrift': []}
        result['RehashEvents'].append(event)
        print(json.dumps(event), flush=True)
        if owned_alias: require(os.path.samefile('P:/', REPO), 'owned P: alias changed')
    try:
        sys.path[:0] = [str(TOOLS), str(REPO / '.venv/Lib/site-packages')]
        modules = {}
        for role in ('physical', 'scoped_native', 'physical_checks', 'target_query', 'final'):
            name = 'hdmi_camera_fisheye_tile8df8v3_' + role
            expected_path = TOOLS / (name + '.py')
            add(inputs, expected_path, manifest['InputSHA256'][str(expected_path)])
            module = importlib.import_module(name)
            require(Path(module.__file__).resolve() == expected_path, 'unexpected public provider location')
            modules[role] = module
        physical, native, checks, target, final = (modules[k] for k in
            ('physical', 'scoped_native', 'physical_checks', 'target_query', 'final'))
        checkpoint('before-existing-public-bind')
        scope, _ = physical.bind_audit(SCOPE)
        app, _ = physical.bind_application(APP)
        exported, _ = native.bind_receipt(EXPORT); native.bind_receipt(ROUTE)
        require(app['ResultADF'] == {'Path': str(FINAL_ADF), 'SHA256': FINAL_ADF_SHA}, 'passed application FinalADF differs')
        physical.all_ten_pass(physical.summaries(native.artifact(EXPORT, exported, 'hdmi_camera_fisheye_top.rtr'))[0])
        inventory, _ = checks.inventory(scope)
        require(checks.query_bodies(inventory) == [local(BODY).read_text(encoding='ascii')], 'complete original query/support matrix differs')
        checkpoint('after-existing-public-bind')
        # Recheck actual process/P: state immediately before claiming the alias.
        result['PreAliasQuiescence'] = require_quiescent()
        created = subprocess.run(['subst.exe', 'P:', str(REPO)], capture_output=True,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        require(created.returncode == 0, 'failed to create own free P: alias')
        owned_alias = True; result['OwnedAliasCreated'] = True
        require(os.path.samefile('P:/', REPO), 'new owned alias points elsewhere')
        checkpoint('before-query-prepare')
        plan = target.prepare(BUILD_PLAN, QUERY_WORK, 'query', body=BODY, maximum=1200, source_proof=APP)
        planned = read(plan)
        require(planned['MaximumSeconds'] == 1200 and planned['SourceProof'] == ref(APP) and
            planned['SourceADFSHA256'] == FINAL_ADF_SHA and planned['QueryBody'] == str(BODY), 'fresh public query plan differs')
        checkpoint('after-query-prepare-before-execute')
        result['EDARequested'] = True
        actual = target.execute(plan)
        result['EDAExecuted'] = actual.get('EDAExecuted') is True
        result['ActualQueryExecution'] = {'EDAExecuted': actual.get('EDAExecuted'), 'OwnedPID': actual.get('OwnedPID'),
            'ExitCode': actual.get('ExitCode'), 'Cleanup': actual.get('Cleanup'), 'ExecutionPassed': actual.get('ExecutionPassed')}
        require(actual.get('ExecutionPassed') is True, 'fresh complete unchanged query did not pass')
        checkpoint('after-query-execute')
        query_receipt = QUERY_WORK / 'result.json'
        target.bind_receipt(query_receipt)
        result['QueryReceipt'] = ref(query_receipt)
        checkpoint('after-public-query-bind-before-final')
        proof, _ = final.final_facts(APP, EXPORT, ROUTE, [query_receipt])
        check_final_flags(proof)
        checkpoint('after-public-final-facts-before-save')
        fresh(FINAL_PROOF, proof)
        final.verify(FINAL_PROOF)
        checkpoint('after-public-final-verify')
        result.update(FinalProof=ref(FINAL_PROOF), FinalProofVerified=True, Passed=True)
    except BaseException as exc:
        result['Passed'] = False; result['Error'] = type(exc).__name__ + ': ' + str(exc); error = exc
    finally:
        if owned_alias:
            try:
                check_native_exit_before_alias_release(process_snapshot(), actual, result['EDARequested'])
                result['NativeExitCheckedBeforeAliasRelease'] = True
                require(os.path.samefile('P:/', REPO), 'owned alias changed; refusing to remove a foreign mapping')
                subprocess.run(['subst.exe', 'P:', '/D'], check=True, capture_output=True,
                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                require(not Path('P:/').exists(), 'own alias cleanup incomplete')
                result['OwnedAliasReleased'] = True
                owned_alias = False
            except BaseException as exc:
                result['Passed'] = False; result['CleanupError'] = type(exc).__name__ + ': ' + str(exc)
        try: checkpoint('after-own-cleanup')
        except BaseException as exc:
            result['Passed'] = False; result['FinalRehashError'] = type(exc).__name__ + ': ' + str(exc)
        result['FinishedUTC'] = utc(); result['InputSHA256'] = inputs
        fresh(RESULT, result)
    if error is not None: raise error
    require(result['Passed'] and result['OwnedAliasReleased'], 'recovery did not complete cleanly')
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', required=True, type=Path)
    parser.add_argument('--handoff-sha256', required=True)
    args = parser.parse_args(argv)
    value = execute(args.execute, args.handoff_sha256)
    print(json.dumps({'Passed': value['Passed'], 'Result': ref(RESULT), 'HardwareAccessed': False}))


if __name__ == '__main__': main()
