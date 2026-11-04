"""CPU-only additional source/evidence freeze for the unchanged v3 query tail.

This is not an EDA prepare call. It writes no GO, creates no P: alias, imports
no production provider and cannot replace the original 1038-input freeze.
"""
import argparse
from datetime import datetime, timezone
from pathlib import Path
import xml.etree.ElementTree as ET

import run_df8_v3_tail_recovery_b as c

SELF = Path(__file__).resolve()
TESTS = c.OUT / 'test_df8_v3_tail_recovery_b.py'
require = c.require


def check_peer(peer, required):
    require(peer.get('Passed') is True and peer.get('IndependentPeerReviewPerformed') is True and
        peer.get('ProviderRevision') == c.REVISION and peer.get('RecoveryRevision') == c.RECOVERY_REVISION and
        peer.get('InputDrift') == [] and peer.get('SourceContractReviewOnly') is True and
        peer.get('EDAExecuted') is False and peer.get('HardwareAccessed') is False and
        all(peer.get('InputSHA256', {}).get(str(path)) == c.sha(path) for path in required),
        'independent complete current recovery source peer required')


def junit_counts(path):
    root = ET.parse(c.local(path)).getroot()
    suites = [root] if root.tag == 'testsuite' else root.findall('testsuite')
    counts = {key: sum(int(s.attrib.get(key, 0)) for s in suites) for key in ('tests', 'errors', 'failures', 'skipped')}
    require(counts['tests'] >= 20 and all(counts[k] == 0 for k in ('errors', 'failures', 'skipped')),
        'actual complete local recovery tests must pass')
    return counts


def bind_saved_receipt(inputs, path, schema):
    value = c.read(c.add(inputs, path))
    require(value.get('Schema') == schema and value.get('ExecutionPassed') is True and
        value.get('ExitCode') == 0 and value.get('TimedOut') is False and value.get('InputDrift') == [] and
        value.get('Cleanup', {}).get('Complete') is True, 'actual completed preserved v3 receipt required: ' + str(path))
    c.merge(inputs, value['InputSHA256'])
    for name, digest in value.get('Artifacts', {}).items():
        part = Path(name)
        require(not part.is_absolute() and '..' not in part.parts, 'saved receipt artifact escapes stage')
        c.add(inputs, path.parent / part, digest)
    for group in ('EvidenceSHA256',):
        for name, digest in value.get(group, {}).items():
            part = Path(name)
            require(not part.is_absolute() and '..' not in part.parts, 'saved physical evidence escapes stage')
            c.add(inputs, path.parent / part, digest)
    return value


def prepare(peer_path, peer_sha, junit_path, additional_peers=()):
    require(not any(c.local(path).exists() for path in (c.MANIFEST, c.HANDOFF, c.START, c.RESULT, c.FINAL_PROOF, c.QUERY_WORK)),
        'fresh additional freeze must precede all recovery/native/final outputs')
    inputs = {}
    for path in (c.SELF, SELF, TESTS): c.add(inputs, path)
    c.add(inputs, c.LAUNCHER, c.LAUNCHER_SHA)
    peer_path = c.add(inputs, peer_path, peer_sha); peer = c.read(peer_path)
    check_peer(peer, (c.SELF, SELF, TESTS, c.LAUNCHER))
    c.merge(inputs, peer['InputSHA256'])
    peer_refs = [c.ref(peer_path)]
    for extra_path, extra_sha in additional_peers:
        extra_path = c.add(inputs, extra_path, extra_sha)
        require(all(row['Path'] != str(extra_path) for row in peer_refs), 'distinct additional peers required')
        extra = c.read(extra_path); check_peer(extra, (c.SELF, SELF, TESTS, c.LAUNCHER))
        c.merge(inputs, extra['InputSHA256']); peer_refs.append(c.ref(extra_path))
    c.add(inputs, junit_path); counts = junit_counts(junit_path)
    require(peer['InputSHA256'].get(str(Path(junit_path).resolve())) == c.sha(junit_path),
        'independent peer must bind this exact actual local JUnit')
    original = c.read(c.add(inputs, c.ORIGINAL_MANIFEST, c.ORIGINAL_SHA))
    require(original.get('Schema') == 'hdmi-camera-fisheye-tile8df8v3-provider-source-manifest-v1' and
        original.get('Passed') is True and original.get('ProviderRevision') == c.REVISION and
        original.get('InputDrift') == [] and len(original.get('InputSHA256', {})) == 1038,
        'actual original complete immutable provider source freeze required')
    c.merge(inputs, original['InputSHA256'])
    c.add(inputs, c.BODY, c.BODY_SHA); c.check_body(c.local(c.BODY).read_text(encoding='ascii'))
    c.add(inputs, c.APP, c.APP_SHA); c.add(inputs, c.FINAL_ADF, c.FINAL_ADF_SHA)
    c.add(inputs, c.SCOPE); c.add(inputs, c.BUILD_PLAN)
    app = bind_saved_receipt(inputs, c.APP, 'hdmi-camera-fisheye-tile8df8v3-physical-application-v1')
    exported = bind_saved_receipt(inputs, c.EXPORT, 'hdmi-camera-fisheye-tile8df8v3-scoped-native-inspection-v1')
    routed = bind_saved_receipt(inputs, c.ROUTE, 'hdmi-camera-fisheye-tile8df8v3-scoped-native-inspection-v1')
    require(app['ResultADF'] == {'Path': str(c.FINAL_ADF), 'SHA256': c.FINAL_ADF_SHA} and
        all(v['SourceProof'] == c.ref(c.APP) and v['SourceADF'] == str(c.FINAL_ADF) and
            v['SourceADFSHA256'] == c.FINAL_ADF_SHA for v in (exported, routed)),
        'preserved actual application/export/route final ADF chain differs')
    failed = c.read(c.add(inputs, c.FAILED)); c.check_prior_failure(failed)
    c.merge(inputs, failed['InputSHA256'])
    for name in ('stage-plan.json', 'stage.tcl', 'stdout.log', 'stderr.log'):
        c.add(inputs, c.FAILED.parent / name)
    launch = c.read(c.add(inputs, c.LAUNCH)); observed = c.read(c.add(inputs, c.PRIOR_EXIT))
    c.check_prior_exit(observed, launch, failed)
    root_observation = c.read(c.add(inputs, c.ROOT_EXIT_OBSERVATION))
    c.check_root_exit_observation(root_observation, c.ref(c.PRIOR_EXIT), observed)
    require(not any(str(path) in inputs for path in c.FUTURE) and
        not any(Path(name).is_relative_to(c.QUERY_WORK) for name in inputs), 'self/future recovery inputs cannot be frozen')
    c.verify_closure(inputs)
    value = {'Schema': 'tile8df8v3-supplemental-recovery-source-manifest-v1', 'Passed': True,
        'ProviderRevision': c.REVISION, 'RecoveryRevision': c.RECOVERY_REVISION,
        'FrozenUTC': datetime.now(timezone.utc).isoformat(), 'OriginalProviderManifest': c.ref(c.ORIGINAL_MANIFEST),
        'OriginalFrozenInputCount': 1038, 'ReplacesOriginalProviderManifest': False,
        'RecoveryControl': c.ref(c.SELF), 'IndependentSourcePeer': c.ref(peer_path),
        'IndependentSourcePeers': peer_refs,
        'RecoveryLauncher': c.ref(c.LAUNCHER),
        'ActualLocalTestJUnit': c.ref(junit_path), 'ActualLocalTestCounts': counts,
        'PassedApplication': c.ref(c.APP), 'PassedScopedExport': c.ref(c.EXPORT), 'PassedScopedRoute': c.ref(c.ROUTE),
        'OriginalScope': c.ref(c.SCOPE), 'OriginalBody': c.ref(c.BODY), 'OriginalBodyCommandCount': 146,
        'MaximumNativeQuerySeconds': 1200, 'NewQueryDirectory': str(c.QUERY_WORK),
        'FinalADF': c.ref(c.FINAL_ADF), 'OriginalFailedQuery': c.ref(c.FAILED),
        'OriginalFailedQueryUsedAsAcceptedEvidence': False,
        'PriorWorkerLaunch': c.ref(c.LAUNCH), 'PriorWorkerExitObservation': c.ref(c.PRIOR_EXIT),
        'RootProcessExitObservation': c.ref(c.ROOT_EXIT_OBSERVATION),
        'PDriveFreeAtOriginalWorkerExitObservation': True, 'FreshRuntimeProcessAndAliasCheckStillRequired': True,
        'RootExecutionAuthorizationGranted': False, 'NativeStagePrepared': False,
        'EDAExecuted': False, 'HardwareAccessed': False, 'PDriveAccessed': False,
        'InputSHA256': dict(sorted(inputs.items())), 'InputDrift': []}
    c.fresh(c.MANIFEST, value)
    return value


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--independent-peer', required=True, type=Path)
    parser.add_argument('--independent-peer-sha256', required=True)
    parser.add_argument('--tests-junit', required=True, type=Path)
    parser.add_argument('--additional-peer', action='append', default=[], type=Path)
    parser.add_argument('--additional-peer-sha256', action='append', default=[])
    args = parser.parse_args(argv)
    require(len(args.additional_peer) == len(args.additional_peer_sha256), 'additional peer path/SHA count differs')
    value = prepare(args.independent_peer, args.independent_peer_sha256, args.tests_junit,
        tuple(zip(args.additional_peer, args.additional_peer_sha256)))
    print(c.json.dumps({'Passed': value['Passed'], 'Manifest': c.ref(c.MANIFEST), 'EDAExecuted': False}))


if __name__ == '__main__': main()
