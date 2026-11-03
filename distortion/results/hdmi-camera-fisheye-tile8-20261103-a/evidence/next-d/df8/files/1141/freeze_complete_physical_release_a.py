"""Freeze this candidate's complete source/evidence closure after actual raw exit.

This CPU tool never creates a handoff/ready, runs a native stage, or accesses
an alias or the board. Run only after pinning the actual warning inventory and
rerunning the final contracts/owner review. Earlier draft receipts are accepted
only if every recorded input still has its actual SHA256 and candidate schema.
"""
from pathlib import Path
from datetime import datetime
import argparse
import importlib
import json
import sys
import xml.etree.ElementTree as ET

WORK = Path(__file__).resolve().parent
PEER_WORK = WORK.with_name('hdmi-camera-fisheye-tile8df9-20261103-a')
ROOT = WORK.parents[1]
REPO = ROOT.parent
sys.path[:0] = [str(ROOT / 'tools'), str(REPO / '.venv/Lib/site-packages')]
import hdmi_camera_fisheye_tile8df8_build as build
import hdmi_camera_fisheye_tile8df8_native as raw
import hdmi_camera_fisheye_tile8df8_warnings as warnings
import hdmi_camera_fisheye_tile8df8v2_bitstream as bit
import hdmi_camera_fisheye_tile8df8v2_physical as physical
import hdmi_camera_fisheye_directfill_contract as cache_contract

SELF = Path(__file__).resolve()
MANIFEST = WORK / 'physical-release-provider-source-manifest-a.json'
MANIFEST_SCHEMA = 'hdmi-camera-fisheye-tile8df8v2-provider-source-manifest-v1'
REVISION = 'tile8df8v2-bounded-b'
PEER_SCHEMA = 'hdmi-camera-fisheye-tile8df8v2-complete-source-independent-peer-review-v1'
RAW_EXIT = WORK / 'raw-worker-exit-observed-a.json'
MONITOR_EXIT = REPO / 'output/tile8_next15h_20261103/df8-raw-worker-exit-a.json'
RAW_LAUNCH = REPO / 'output/tile8_next15h_20261103/df8-raw-worker-launch-a.json'
ROOT_ROLES = ('build', 'native', 'scoped_native', 'audit', 'protocol', 'startup', 'warnings')
PHYSICAL_ROLES = ('physical', 'scoped_native', 'target_query', 'physical_checks', 'final', 'bitstream', 'program')
SUPPLEMENT_ROLES = ('macro_we_aliases', 'startup_timing', 'vendor_startup_bounded_b')
DRIVERS = ('run_physical_v2_a.py', 'run_release_v2_a.py', 'prewarm_release_v2_a.py',
           'compress_completed_physical_v2_evidence_a.py')
SCRIPT_NAMES = ('freeze_complete_physical_release_a.py', 'bind_selected_four_roles_a.py')
FUTURE = (MANIFEST, WORK / 'final-proof-v2-a.json', WORK / 'release-input-manifest-v2-a.json',
          WORK / 'selected-four-role-binding-proof-a.json', WORK / 'native-to-physical-v2-go-a.json',
          WORK / 'physical-to-release-v2-go-a.json', WORK / 'bit-request-v2-a.json')
require = build.require


def add(watched, path, digest=None):
    """The selected public API preserves canonical identity and long-path IO."""
    return bit.add(watched, path, digest)


def merge(watched, rows):
    bit.merge(watched, rows)


def load(watched, path, digest=None):
    path = add(watched, path, digest)
    return build.read(path)


def write_fresh(path, value):
    require(path.parent == WORK and not path.exists(), 'fresh own-WORK output required')
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def source_roots():
    return [*(ROOT / 'tools' / ('hdmi_camera_fisheye_tile8df8v2_' + role + '.py')
              for role in PHYSICAL_ROLES),
            *(ROOT / 'tools' / ('hdmi_camera_fisheye_tile8df8_' + role + '.py')
              for role in (*ROOT_ROLES, *SUPPLEMENT_ROLES)),
            *(WORK / name for name in (*DRIVERS, *SCRIPT_NAMES)),
            WORK / 'run_build_native.py', WORK / 'run_physical_release_contracts_a.py',
            WORK / 'review_physical_release_group_a.py', PEER_WORK / 'review_directfill_independent_peer_a.py',
            WORK / 'prepare_df8_physical_release_sources_a.py',
            WORK / 'prepare_source_warning_inventory_b.py', WORK / 'review_source_warning_inventory_draft_b.py',
            ROOT / 'tests/test_tile8df8_actual_warning_draft_b.py']


def bind_static_sources(watched):
    sources = {}
    physical.static_helpers(sources, *source_roots())
    require(cache_contract.SELF in sources and len(sources) >= 95,
            'recursive complete candidate helper closure missing direct-fill support')
    merge(watched, sources)
    return {str(path): digest for path, digest in sources.items()}


def junit_counts(path):
    root = ET.parse(path).getroot()
    suites = [root] if root.tag == 'testsuite' else root.findall('testsuite')
    require(bool(suites), 'actual JUnit test suites required')
    counts = {name: sum(int(s.attrib.get(name, 0)) for s in suites)
              for name in ('tests', 'errors', 'failures', 'skipped')}
    require(counts['tests'] >= 695 and all(counts[n] == 0 for n in ('errors', 'failures', 'skipped')),
            'all physical, original cache-contract and independent peer CPU tests must actually pass')
    return counts


def bind_final_contracts(watched, owner_path, run_path, junit_path):
    owner = load(watched, owner_path)
    run = load(watched, run_path)
    add(watched, junit_path)
    counts = junit_counts(junit_path)
    require(run.get('Schema') == 'tile8df8-physical-release-contract-run-v1' and run.get('Passed') is True
            and run.get('PytestExitCode') == 0 and run.get('InputDrift') == []
            and run.get('Counts') == counts and run.get('JUnit') == bit.ref(junit_path)
            and all(run.get(k) is False for k in ('EDAExecuted', 'HardwareAccessed', 'PDriveAccessed')),
            'fresh actual source-bound CPU contract run required')
    require(owner.get('Schema') == 'hdmi-camera-fisheye-tile8df8v2-physical-release-owner-review-v1'
            and owner.get('Passed') is True and owner.get('SourceContractReviewOnly') is True
            and owner.get('IndependentPeerReviewPerformed') is False
            and owner.get('ActualOwnerContracts') == counts['tests']
            and owner.get('OriginalFrozenTile8ProvidersAndDriversUnchanged') is True
            and owner.get('OldPhysicalOrHardwareAcceptanceInherited') is False
            and owner.get('ProviderManifestFrozen') is False,
            'current completed owner review, without inherited physical acceptance, required')
    merge(watched, run['InputSHA256'])
    merge(watched, owner['InputSHA256'])
    require(owner['InputSHA256'].get(str(Path(run_path).resolve())) == build.sha(run_path)
            and owner['InputSHA256'].get(str(Path(junit_path).resolve())) == build.sha(junit_path),
            'owner review must bind this exact actual contract run and JUnit')
    physical_tests = sorted((WORK / 'physical-release-tests-a').glob('*.py'))
    peer_tests = [ROOT / 'tests/test_hdmi_camera_fisheye_directfill_contract.py',
                  *sorted((WORK / 'directfill-peer-tests-a').glob('test_*.py'))]
    warning_tests = [ROOT / 'tests/test_tile8df8_actual_warning_draft_b.py']
    require(run.get('PhysicalContractFiles') == list(map(str, physical_tests))
            and run.get('DirectFillContractAndPeerFiles') == list(map(str, peer_tests))
            and run.get('WarningInventoryContractFiles') == list(map(str, warning_tests))
            and all(run['InputSHA256'].get(str(p)) == build.sha(p) for p in (*physical_tests, *peer_tests, *warning_tests)),
            'actual final run must include every current physical/sustained and independent peer contract file')
    required = [*source_roots()[:17], *(WORK / n for n in DRIVERS)]
    require(all(run['InputSHA256'].get(str(p)) == build.sha(p) for p in required),
            'final CPU run must bind all actual physical/root providers and drivers after warning pin')
    return counts


def ordinary_core_rows(report):
    tables, _ = physical.summaries(report)
    core = {}
    rows = []
    # Same ordinary core selection as this candidate's raw worker, rederived
    # from the actual native report rather than a copied Passed flag.
    for (corner, kind), entries in tables.items():
        pair = ('ddrphy_sysclk',) if kind == 'mpw' else ('ddrphy_sysclk', 'ddrphy_sysclk')
        if pair in entries:
            core[(corner, kind)] = {pair: entries[pair]}
            rows.append({'Corner': corner, 'Kind': kind, **entries[pair]})
    physical.all_ten_pass(core)
    require(len(rows) == 10, 'exactly ten independently reparsed ordinary core checks required')
    return rows


def bind_raw_worker_observation(watched, exit_digest, launch_digest, build_manifest_digest):
    observed = load(watched, RAW_EXIT, exit_digest)
    require(observed.get('Schema') == 'tile8df8-raw-worker-exit-observation-v1'
            and observed.get('ProcessExited') is True
            and type(observed.get('ExitCode')) is int and observed['ExitCode'] == 0
            and observed.get('PDriveReleased') is True
            and observed.get('WorkerSource') == bit.ref(WORK / 'run_build_native.py')
            and observed.get('RawCompleted') == bit.ref(WORK / 'raw-native-completed-a.json'),
            'root observation of the actual raw worker exit 0 and released alias required')
    require(type(observed.get('PID')) is int and observed['PID'] > 0
            and type(observed.get('MonitorSessionID')) is int and observed['MonitorSessionID'] > 0,
            'actual observed df8 raw process and monitor session identities required')
    stamp = datetime.fromisoformat(observed['ObservedUTC'].replace('Z', '+00:00'))
    require(stamp.tzinfo is not None, 'actual timezone-aware raw exit observation timestamp required')
    bit.binding(observed['WorkerSource'], watched)
    bit.binding(observed['RawCompleted'], watched)
    require(observed.get('LaunchReceipt') == bit.ref(RAW_LAUNCH),
            'raw exit must identify the actual original df8 raw launch receipt')
    launch_path = bit.binding(observed['LaunchReceipt'], watched)
    add(watched, launch_path, launch_digest)
    launch = build.read(launch_path)
    build_manifest = WORK / 'build-provider-source-manifest-a.json'
    require(launch.get('Schema') == 'tile8df8-raw-build-worker-launch-v1'
            and type(launch.get('PID')) is int and launch['PID'] == observed['PID']
            and launch.get('BuildProviderManifest') == str(build_manifest)
            and launch.get('BuildProviderManifestSHA256') == build_manifest_digest
            and launch.get('UserAuthorizedNewCandidate') is True and launch.get('HardwareAccessPlanned') is False,
            'actual raw launch PID/schema/selected build-provider manifest differs')
    if 'MonitorSessionID' in launch:
        require(launch['MonitorSessionID'] == observed['MonitorSessionID'], 'observed monitor differs from actual launch')
    add(watched, build_manifest, build_manifest_digest)
    launched = datetime.fromisoformat(launch['StartedUTC'].replace('Z', '+00:00'))
    require(launched.tzinfo is not None and stamp >= launched,
            'actual raw exit observation must follow this launch')
    for name in ('Stdout', 'Stderr'):
        add(watched, launch[name])
    monitor_reference = observed.get('ActualMonitorExitReceipt')
    require(not MONITOR_EXIT.exists() or monitor_reference == bit.ref(MONITOR_EXIT),
            'existing actual monitor exit receipt must remain bound by the independent observation')
    if monitor_reference is not None:
        require(Path(monitor_reference['Path']).resolve() == MONITOR_EXIT,
                'actual raw monitor exit receipt path differs')
        bit.binding(monitor_reference, watched)
    return observed


def bind_raw_completion(watched, exit_digest, launch_digest, build_manifest_digest):
    bind_raw_worker_observation(watched, exit_digest, launch_digest, build_manifest_digest)
    path = WORK / 'raw-native-completed-a.json'
    completed = load(watched, path)
    expected = {'BuildPlan': WORK / 'build-a/plan.json', 'ExportReceipt': WORK / 'export-a/result.json',
                'RouteReceipt': WORK / 'route-a/result.json'}
    require(completed.get('Schema') == 'hdmi-camera-fisheye-tile8df8-raw-native-completed-v1'
            and completed.get('PriorWorkerEnded') is True and completed.get('PDriveReleased') is True
            and completed.get('HardwareAccessed') is False
            and all(completed.get(k) == bit.ref(p) for k, p in expected.items()),
            'complete own df8 raw native handoff required')
    plan, receipt, _, inputs = raw.bind_build(expected['BuildPlan'])
    merge(watched, inputs)
    for mode, key in (('export', 'ExportReceipt'), ('report', 'RouteReceipt')):
        result, inputs = raw.bind_receipt(expected[key])
        require(result.get('Mode') == mode and result.get('BuildPlan') == str(expected['BuildPlan'])
                and result.get('SourceADFSHA256') == receipt['ADFSHA256'],
                'actual raw native inspection belongs to another source ADF/build')
        merge(watched, inputs)
    core_path = WORK / 'raw-core-timing-a.json'
    saved = load(watched, core_path)
    report = WORK / 'build-a/report_timing' / (build.TARGET + '.rtr')
    add(watched, report)
    actual_rows = ordinary_core_rows(report)
    # The raw worker emits all MPW rows first, then the other kinds.
    actual_rows.sort(key=lambda row: (row['Kind'] != 'mpw'))
    require(saved.get('Schema') == 'hdmi-camera-fisheye-tile8df8-raw-core-timing-v1'
            and saved.get('Passed') is True and saved.get('Report') == bit.ref(report)
            and saved.get('Rows') == actual_rows and saved.get('OnlyOrdinaryCoreChecks') is True
            and saved.get('PhysicalReleaseAllowed') is False,
            'saved raw ordinary ten checks differ from actual report recomputation')
    return plan, receipt


def bind_collision(watched):
    path = PEER_WORK / 'cache-commit-collision-a/simulation.json'
    value = load(watched, path)
    require(value.get('Schema') == 'tile8-directfill-independent-peer-commit-collision-v1'
            and value.get('Passed') is True and value.get('HDLSimulationExecuted') is True
            and value.get('InputDrift') == [] and value.get('NativeRAMMappingOrTimingAccepted') is False
            and value.get('PDSAccessed') is False and value.get('HardwareAccessed') is False,
            'actual independent final-commit collision XSim evidence required')
    merge(watched, value['SourceSHA256'])
    require(value['SourceSHA256'].get(str(cache_contract.SOURCE)) == cache_contract.SOURCE_SHA256,
            'independent collision executed another cache source')
    for name, digest in value['ArtifactsSHA256'].items():
        relative = Path(name)
        require(not relative.is_absolute() and '..' not in relative.parts, 'collision artifact escaped output')
        add(watched, path.parent / relative, digest)
    summary = value['Summary']
    require(summary.get('IndexBits') == 9 and summary.get('Cases') == 4
            and summary.get('IndependentRAMPixelsChecked') == 864
            and summary.get('SuccessfulCommonResetRecoveries') == 4
            and all(summary.get(k) is True for k in ('Passed', 'NinthRAndLastCommitCollision',
                'MalformedFinalRID', 'MissingFinalRLAST', 'ResetBeforeFinalRAMCommit', 'FaultQuarantineChecked')),
            'complete actual independent collision/reset/quarantine cases required')
    require((path.parent / 'peer-commit-cases.csv').read_text().splitlines()[1:] == [
        '0,ninth_R_vs_last_commit,128,4,0', '1,malformed_final_R,112,3,0',
        '2,malformed_final_R,112,3,0', '3,common_reset_vs_last_commit,0,0,0'],
        'independent actual collision trace differs')
    log = (path.parent / 'simulation.log').read_text(encoding='utf-8', errors='replace')
    require('PASS DIRECTFILL PEER real final-commit/fault/reset collisions' in log and '$finish called' in log,
            'independent RTL collision simulation did not actually finish')
    return bit.ref(path)


def bind_cache_and_independent_peer(watched):
    facts, inputs = cache_contract.review()
    require(facts.get('Passed') is True and len(inputs) >= 31
            and facts.get('HardwareReleaseAllowed') is False,
            'actual complete source-specific cache contract and saved original unit required')
    merge(watched, inputs)
    collision = bind_collision(watched)
    peer_path = PEER_WORK / 'directfill-independent-peer-review-a.json'
    peer = load(watched, peer_path)
    require(peer.get('Schema') == 'hdmi-camera-fisheye-directfill-independent-peer-review-v1'
            and peer.get('Passed') is True and peer.get('InputDrift') == []
            and peer.get('SourceFacts') == facts and peer.get('Source') == bit.ref(cache_contract.SOURCE)
            and peer.get('SourceContractProvider') == bit.ref(cache_contract.SELF)
            and peer.get('OriginalUnitReceipt') == bit.ref(cache_contract.UNIT_RECEIPT)
            and peer.get('IndependentCollisionReceipt') == collision
            and peer.get('HDLSimulationExecutedByPeer') is True
            and peer.get('HardwareReleaseAllowed') is False,
            'actual independent direct-fill source review and separate collision binding required')
    merge(watched, peer['InputSHA256'])
    report = bit.binding(peer['PeerCPUContractJUnit'], watched)
    root = ET.parse(report).getroot()
    suites = [root] if root.tag == 'testsuite' else root.findall('testsuite')
    require(sum(int(s.attrib.get('tests', 0)) for s in suites) == peer['ActualPeerCPUContractTests'] >= 59
            and all(int(s.attrib.get(k, 0)) == 0 for s in suites for k in ('failures', 'errors', 'skipped')),
            'actual original independent peer CPU suite did not cleanly complete')
    unit = build.read(cache_contract.UNIT_RECEIPT)
    require(cache_contract.UNIT_RECEIPT == PEER_WORK / 'cache-unit-a/simulation.json'
            and unit.get('Cases', {}).get('1920-i8', {}).get('passed') is True
            and unit['Cases']['1920-i8'].get('index_bits') == 8,
            'unchanged cache source must retain its actual INDEX8 unit case in the original receipt')
    return {'SourceContract': bit.ref(cache_contract.SELF), 'SourceContractWatchedFiles': len(inputs),
            'OriginalCacheUnit': bit.ref(cache_contract.UNIT_RECEIPT), 'IndependentCollision': collision,
            'IndependentCacheReview': bit.ref(peer_path), 'SameCacheSourceEvidenceWork': str(PEER_WORK),
            'CandidateCacheIndexBits': 8, 'OriginalCacheUnitIncludesINDEX8': True,
            'IndependentCollisionExecutedIndexBits': 9, 'CollisionIsSourceLevelEvidenceOnly': True,
            'OwnINDEX8SystemAndSustainedEvidenceRequired': True}


def selected_role_paths(mapper, io, profile):
    return {'MapperSimulation': Path(mapper).resolve(), 'SystemSimulation': WORK / 'system-native-a/simulation.json',
            'IOSimulation': Path(io).resolve(), 'Profile': Path(profile).resolve()}


def bind_actual_four_roles(watched, plan, paths):
    require(set(paths) == {'MapperSimulation', 'SystemSimulation', 'IOSimulation', 'Profile'},
            'exact four public role bindings required')
    results = {}
    values = {}
    for kind in bit.SIMULATIONS:
        value = bit.bind_simulation(kind, paths[kind], plan, watched)
        values[kind] = value
        results[kind] = {'Passed': True, 'Receipt': bit.ref(paths[kind]), 'Mode': value.get('Mode'),
                         'SelectedPublicProvider': bit.ref(bit.simulation_provider(kind).__file__)}
    system = values['SystemSimulation']
    small_path = WORK / 'system-small-a/simulation.json'
    require(system.get('SmallGate') == bit.ref(small_path), 'normal native gate must select own exact small receipt')
    small, inputs = bit.simulation_provider('SystemSimulation').verify(small_path)
    merge(watched, inputs)
    add(watched, small_path)
    require(small.get('Mode') == 'small' and small.get('SourceSHA256') == system.get('SourceSHA256')
            and small.get('DirectFillCache') is True and small.get('CacheIndexBits') == 8
            and small.get('ScatterCyclesPerFill') == 0 and small.get('CacheRAMWriteCyclesPerFill') == 8,
            'own small gate must execute the exact normal native production/header closure')
    bit.directfill_frame_counts(small.get('Frames'))
    profile = bit.bind_profile(paths['Profile'], plan, watched)
    results['Profile'] = {'Passed': True, 'Profile': profile['Profile'], 'FullGridError': profile['FullGridError'],
                          'ExactGeneratedHeadersMatchActualBuild': True}
    return {'RoleReferences': {name: bit.ref(path) for name, path in paths.items()}, 'Bindings': results,
            'SmallSystemGate': bit.ref(small_path), 'NativeSystemFrames': system['Frames'],
            'AllExecutedProductionAndHeadersMatchActualOriginalAndPreparedInputs': True}


def bind_actual_warnings(watched, plan_path):
    path = WORK / 'source-warnings-a.json'
    require(warnings.INVENTORY_SHA is not None, 'actual candidate warning inventory must first be pinned')
    value, inputs = warnings.verify(path)
    require(value.get('Passed') is True and value.get('SourceDiagnosticReviewPassed') is True
            and value.get('BuildPlan') == bit.ref(plan_path)
            and value.get('SourceBuildReceipt') == bit.ref(plan_path.parent / 'execution-result.json')
            and value.get('Inventory') == bit.ref(warnings.INVENTORY),
            'actual own warning review/source proof required')
    merge(watched, inputs)
    add(watched, path)
    return bit.ref(path)


def bind_root_independent_review(watched, path, digest, static):
    review = load(watched, path, digest)
    require(review.get('Schema') == PEER_SCHEMA and review.get('Passed') is True
            and review.get('IndependentPeerReviewPerformed') is True
            and review.get('ProviderRevision') == REVISION and review.get('InputDrift') == []
            and review.get('PhysicalAcceptanceInherited') is False,
            'actual independent complete candidate source review required')
    merge(watched, review['InputSHA256'])
    required = [*source_roots(), cache_contract.SELF]
    require(all(review['InputSHA256'].get(str(p)) == build.sha(p) for p in required),
            'independent reviewer must bind every selected provider, driver, helper and both freeze/binding scripts')
    require(all(static.get(str(p)) == build.sha(p) for p in required), 'reviewed source outside static source closure')
    return bit.ref(path)


def verify_manifest(path, expected_digest, watched):
    require(Path(path).resolve() == MANIFEST, 'selected exact df8 manifest path required')
    value = load(watched, path, expected_digest)
    require(value.get('Schema') == MANIFEST_SCHEMA and value.get('ProviderRevision') == REVISION
            and value.get('Passed') is True and value.get('InputDrift') == []
            and value.get('ManifestSelfIncluded') is False
            and value.get('FuturePhysicalProofIncluded') is False
            and value.get('PriorPhysicalTimingOrAcceptanceInherited') is False,
            'complete frozen df8 provider closure required')
    merge(watched, value['InputSHA256'])
    require(all(str(path) not in value['InputSHA256'] for path in FUTURE), 'manifest contains circular downstream inputs')
    require(all(value['InputSHA256'].get(str(p)) == build.sha(p) for p in source_roots()),
            'frozen manifest omits a selected provider/driver/source support root')
    return value


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--independent-peer-review', type=Path, required=True)
    parser.add_argument('--independent-peer-review-sha256', required=True)
    parser.add_argument('--raw-worker-exit-sha256', required=True)
    parser.add_argument('--raw-launch-sha256', required=True)
    parser.add_argument('--raw-build-provider-manifest-sha256', required=True)
    parser.add_argument('--owner-review', type=Path, required=True)
    parser.add_argument('--contract-run', type=Path, required=True)
    parser.add_argument('--contracts', type=Path, required=True)
    parser.add_argument('--mapper-simulation', type=Path, required=True)
    parser.add_argument('--io-simulation', type=Path, required=True)
    parser.add_argument('--profile', type=Path, required=True)
    args = parser.parse_args(argv)
    require(not MANIFEST.exists(), 'immutable candidate source manifest already exists')
    require(not any(p.exists() for p in FUTURE[1:]), 'downstream physical/release outputs must not precede final freeze')
    watched = {}
    static = bind_static_sources(watched)
    counts = bind_final_contracts(watched, args.owner_review, args.contract_run, args.contracts)
    plan, _ = bind_raw_completion(watched, args.raw_worker_exit_sha256, args.raw_launch_sha256,
                                 args.raw_build_provider_manifest_sha256)
    plan_path = WORK / 'build-a/plan.json'
    warning = bind_actual_warnings(watched, plan_path)
    cache = bind_cache_and_independent_peer(watched)
    paths = selected_role_paths(args.mapper_simulation, args.io_simulation, args.profile)
    roles = bind_actual_four_roles(watched, plan, paths)
    sustained = bit.bind_sustained(plan, watched)
    build_manifest_path = WORK / 'build-provider-source-manifest-a.json'
    built = load(watched, build_manifest_path)
    require(built.get('Schema') == 'hdmi-camera-fisheye-tile8df8-build-provider-source-freeze-v1'
            and built.get('Passed') is True and built.get('Variant') == 'tile8df8'
            and built.get('PriorPhysicalTimingOrAcceptanceInherited') is False,
            'own immutable raw build source manifest required')
    merge(watched, built['InputSHA256'])
    independent = bind_root_independent_review(watched, args.independent_peer_review,
                                             args.independent_peer_review_sha256, static)
    require(all(str(p) not in watched for p in FUTURE), 'self or future physical/release evidence entered source closure')
    require(bit.drift(watched) == [], 'complete source/evidence closure drift before immutable freeze')
    value = {'Schema': MANIFEST_SCHEMA, 'ProviderRevision': REVISION, 'Passed': True, 'FrozenUTC': build.utc(),
             'Target': build.TARGET, 'BuildPlan': bit.ref(plan_path), 'RawBuildProviderManifest': bit.ref(build_manifest_path),
             'RawWorkerExitObservation': bit.ref(RAW_EXIT), 'RawNativeHandoff': bit.ref(WORK / 'raw-native-completed-a.json'),
             'OwnAllTenOrdinaryCoreChecksPassed': True, 'OwnRawNativeReceiptsCompleted': True,
             'SourceWarningReview': warning, 'SourceWarningInventory': bit.ref(warnings.INVENTORY),
             'OwnerSourceReview': bit.ref(args.owner_review), 'ActualCPUContractRun': bit.ref(args.contract_run),
             'ActualCPUContractJUnit': bit.ref(args.contracts), 'ActualCPUContractCounts': counts,
             'IndependentClosedGroupReview': independent, 'CacheIndependentEvidence': cache,
             'SelectedFourRoleInputs': roles,
             'SustainedSimulation': bit.ref(WORK / 'system-sustained-native-a/simulation.json'),
             'SustainedFourCorrectedFramesWithReadWriteContentionPassed': True,
             'SustainedFutureSourceWriteOverlapCycles': sustained['FutureSourceWriteOverlapCycles'],
             'RecursiveLocalPythonSourceCount': len(static),
             'OriginalFrozenTile8ProvidersAndDriversUnchanged': True,
             'PriorTile8SourcesAndReceiptsAreProvenanceOnly': True, 'PriorPhysicalTimingOrAcceptanceInherited': False,
             'ManifestSelfIncluded': False, 'FuturePhysicalProofIncluded': False, 'InputDrift': [],
             'FreshFullAuditAndBoundedStartupReviewStillRequired': True, 'OwnFinalPhysicalProofStillRequired': True,
             'RootGoPreparedByThisTool': False, 'PhysicalStagePrepared': False, 'BitStagePrepared': False,
             'EDAExecuted': False, 'HDLSimulationExecuted': False, 'PDriveAccessed': False,
             'HardwareAccessed': False, 'HardwareReleaseAllowed': False, 'InputSHA256': dict(sorted(watched.items()))}
    write_fresh(MANIFEST, value)
    print(json.dumps({'Passed': True, 'Manifest': bit.ref(MANIFEST), 'Inputs': len(watched),
                      'ActualTests': counts['tests'], 'ReadyCreated': False, 'EDAExecuted': False}), flush=True)


if __name__ == '__main__':
    main()
