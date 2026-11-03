"""Bind four selected public roles after the actual complete df8 source freeze.

No physical proof, ready/handoff, bit request, EDA stage, alias or board action
is created. The manifest SHA is supplied by the independent root reviewer.
"""
from pathlib import Path
import argparse
import json
import sys
import time

WORK = Path(__file__).resolve().parent
sys.path.insert(0, str(WORK))
import freeze_complete_physical_release_a as freeze

bit = freeze.bit
PROOF = WORK / 'selected-four-role-binding-proof-a.json'
OUTPUT = WORK / 'release-input-manifest-v2-a.json'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--provider-manifest-sha256', required=True)
    args = parser.parse_args(argv)
    started = time.monotonic()
    bit.require(not PROOF.exists() and not OUTPUT.exists(), 'fresh post-freeze four-role outputs required')
    watched = {}
    manifest = freeze.verify_manifest(freeze.MANIFEST, args.provider_manifest_sha256, watched)
    bit.require(manifest['InputSHA256'].get(str(Path(__file__).resolve())) == bit.sha(__file__),
                'selected binding script must be reviewed and bound by the frozen manifest')
    freeze.bind_static_sources(watched)
    plan_path = WORK / 'build-a/plan.json'
    plan, receipt, _, inputs = freeze.raw.bind_build(plan_path)
    freeze.merge(watched, inputs)
    bit.require(receipt.get('BuildCompleted') is True and manifest['BuildPlan'] == bit.ref(plan_path),
                'actual completed build differs from frozen candidate')
    selected = manifest['SelectedFourRoleInputs']
    paths = {}
    for role, reference in selected['RoleReferences'].items():
        paths[role] = bit.binding(reference, watched)
    actual = freeze.bind_actual_four_roles(watched, plan, paths)
    bit.require(actual == selected, 'public role recomputation differs from selected immutable source freeze')
    sustained = bit.bind_sustained(plan, watched)
    sustained_ref = bit.ref(WORK / 'system-sustained-native-a/simulation.json')
    bit.require(manifest.get('SustainedSimulation') == sustained_ref and
                manifest.get('SustainedFourCorrectedFramesWithReadWriteContentionPassed') is True and
                manifest.get('SustainedFutureSourceWriteOverlapCycles') == sustained['FutureSourceWriteOverlapCycles'],
                'actual separate sustained contention gate differs from source freeze')
    bit.require(bit.drift(watched) == [], 'four-role inputs changed during post-freeze public binding')
    proof = {'Schema': 'hdmi-camera-fisheye-tile8df8v2-four-role-binding-proof-v1', 'Passed': True,
             'ProviderRevision': freeze.REVISION, 'SelectedBitstreamProvider': bit.ref(bit.SELF),
             'ProviderSourceManifest': bit.ref(freeze.MANIFEST), 'BuildPlan': bit.ref(plan_path),
             'SourceBuildReceipt': bit.ref(plan_path.parent / 'execution-result.json'), **actual,
             'SustainedSimulation': sustained_ref, 'SustainedContentionGateRecomputed': True,
             'AllRoleProvidersUseUnchangedPublicBindingAPIs': True,
             'AllExecutedSystemProductionAndHeadersBoundToBuiltCompiledInputs': True,
             'PhysicalProofAccepted': False, 'BitRecipeCreated': False, 'ReadyCreated': False,
             'EDAExecuted': False, 'HDLSimulationExecuted': False, 'PDriveAccessed': False,
             'HardwareAccessed': False, 'InputDrift': [], 'InputSHA256': dict(sorted(watched.items()))}
    freeze.write_fresh(PROOF, proof)
    freeze.add(watched, PROOF)
    bit.require(bit.drift(watched) == [], 'bound proof or selected role inputs changed before release-input manifest')
    value = {'Schema': 'hdmi-camera-fisheye-tile8df8v2-readonly-release-input-manifest-v1', 'Passed': True,
             'ProviderRevision': freeze.REVISION, 'SelectedBitstreamProvider': bit.ref(bit.SELF),
             'ProviderSourceManifest': bit.ref(freeze.MANIFEST), **actual['RoleReferences'],
             'BindingProof': bit.ref(PROOF), 'BuildPlan': bit.ref(plan_path), 'InputDrift': [],
             'PhysicalProofAccepted': False, 'BitRecipeCreated': False, 'ReadyCreated': False,
             'ReleaseAuthorizationGranted': False, 'EDAExecuted': False, 'HDLSimulationExecuted': False,
             'PDriveAccessed': False, 'HardwareAccessed': False,
             'CompletedUTC': freeze.build.utc(), 'ElapsedSeconds': time.monotonic() - started,
             'InputSHA256': dict(sorted(watched.items()))}
    freeze.write_fresh(OUTPUT, value)
    print(json.dumps({'Passed': True, 'Manifest': bit.ref(OUTPUT), 'Proof': bit.ref(PROOF),
                      'Watched': len(watched), 'ReadyCreated': False, 'EDAExecuted': False}), flush=True)


if __name__ == '__main__':
    main()
