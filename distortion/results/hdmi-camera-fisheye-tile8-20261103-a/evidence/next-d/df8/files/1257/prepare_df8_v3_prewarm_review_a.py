"""Generate only the reviewed v3 wrapper source manifest after real freeze/roles.

No provider is imported or invoked. This tool performs byte/JSON/source checks
and writes one fresh source manifest. It does not run prewarm, prepare a request,
authorize release, access P:, or accept any physical proof.
"""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import ast
import hashlib
import json
import os
import re

SELF = Path(__file__).resolve()
OUT = SELF.parent
REPO = OUT.parents[1]
ROOT = REPO / 'distortion'
WORK = ROOT / 'work/hdmi-camera-fisheye-tile8df8-20261103-a'
PROVIDER = WORK / 'physical-release-provider-source-manifest-v3-a.json'
ROOT_REVIEW = WORK / 'root-independent-complete-source-review-v3-a.json'
ROLES = WORK / 'release-input-manifest-v3-a.json'
ROLE_PROOF = WORK / 'selected-four-role-binding-proof-v3-a.json'
OUTPUT = WORK / 'release-prewarm-wrapper-source-manifest-v3-a.json'
WRAPPER = WORK / 'prewarm_release_v3_a.py'
RELEASE = WORK / 'run_release_v3_a.py'
BIT = ROOT / 'tools/hdmi_camera_fisheye_tile8df8v3_bitstream.py'
ORIGINAL = WORK / 'physical-release-provider-source-manifest-a.json'
ORIGINAL_ROOT = WORK / 'root-independent-complete-source-review-a.json'
DRIVER_PEER = OUT / 'v3-drivers-freeze-roles-independent-peer-b.json'
PROVIDER_PEER = OUT / 'v3-physical-provider-independent-peer-a.json'
REVISION = 'tile8df8v3-budget1800-a'
ACTUAL_PROVIDER_SHA = '7b2c444b1e6e7d482c1875307fbc7b717689d0f5da9eaf8fac49ef249540a8fb'
ACTUAL_ROOT_REVIEW_SHA = '714242e526fc1a9952cddf3eb9188437f5fed9cb7dc4c1b351077c03b6af150a'
ROLE_NAMES = {'MapperSimulation', 'SystemSimulation', 'IOSimulation', 'Profile'}
PINS = {
    ORIGINAL: '8914c4c46ab950866747400cf1d668f3436720e562f10d76870c4440019fb50d',
    ORIGINAL_ROOT: '27e614d3e584d1a8a278254b12fba992462a19a76bda445d54528a70012a9374',
    DRIVER_PEER: 'f799a8572af956f646571ce831695ca47a3e115c67f7fe6163783ee7be82c2bb',
    PROVIDER_PEER: '0d0c041668ee5e89695c04ff7ee786f8f03749b3ef2207edcafc801aab57f1ab',
    WRAPPER: 'bba198a7c7af7446dd6edea92f2022368c78bcc5bd171f3293b76a081d9dee6d',
    RELEASE: 'f1293fdc533ade33268bf2cdf9b259cb5d6aaf63c2c4bb2b81dc1210b21220fc',
    BIT: 'f927da4c78a205d4cb96cf532685cf4abec2063023a9bcb1e9a1c670907c0517',
}
FUTURE_FILES = {OUTPUT, WORK / 'final-proof-v3-a.json', WORK / 'physical-to-release-v3-go-a.json',
    WORK / 'bit-request-v3-a.json', WORK / 'release-prewarm-bit-request-v3-a.snapshot.json',
    WORK / 'release-prewarm-authority-v3-a.json', WORK / 'release-prewarm-authorized-transition-v3-a.json',
    WORK / 'release-prewarm-recreated-request-check-v3-a.json'}
FUTURE_DIRS = (WORK / 'bit-v3-a', WORK / 'program-v3-a')


def require(value, message):
    if not value:
        raise ValueError(message)


def canonical(path):
    path = Path(path).absolute()
    require(path == path.resolve() and path.drive.upper() != 'P:' and not str(path).startswith('\\\\?\\'),
            'original canonical D:/C: input identity required')
    return path


def local_io(path):
    path = canonical(path)
    return Path('\\\\?\\' + str(path)) if os.name == 'nt' else path


def sha(path):
    digest = hashlib.sha256()
    with local_io(path).open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def read(path):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, 'duplicate JSON key: ' + key)
            result[key] = value
        return result
    return json.loads(local_io(path).read_text(encoding='utf-8-sig'), object_pairs_hook=pairs,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError('nonfinite JSON: ' + value)))


def reject_future(path):
    path = canonical(path)
    require(path not in FUTURE_FILES and not any(path.is_relative_to(folder) for folder in FUTURE_DIRS),
            'source manifest cannot include itself or future v3 proof/GO/request/prewarm/bit/program evidence')


def add(watched, path, expected=None):
    path = canonical(path)
    reject_future(path)
    require(expected is None or isinstance(expected, str) and re.fullmatch('[0-9a-f]{64}', expected), 'actual SHA256 required')
    digest = sha(path)
    require(expected is None or digest == expected, 'actual source SHA differs: ' + str(path))
    key = str(path)
    require(key not in watched or watched[key] == digest, 'conflicting immutable input SHA: ' + key)
    watched[key] = digest
    return path


def reference(path):
    path = canonical(path)
    return {'Path': str(path), 'SHA256': sha(path)}


def bound(watched, value):
    require(type(value) is dict and set(value) == {'Path', 'SHA256'}, 'exact Path/SHA256 reference required')
    return add(watched, value['Path'], value['SHA256'])


def merge(watched, inputs):
    require(type(inputs) is dict and bool(inputs), 'complete nonempty source input map required')
    for name, digest in inputs.items():
        add(watched, name, digest)


def check_role_references(provider, roles, proof, watched):
    expected = provider['SelectedFourRoleInputs']['RoleReferences']
    require(type(expected) is dict and set(expected) == ROLE_NAMES and proof.get('RoleReferences') == expected
            and all(roles.get(name) == value for name, value in expected.items()),
            'exact four actual roles must equal both source freeze and public binding proof')
    for value in expected.values():
        bound(watched, value)
    require(expected['SystemSimulation'] == reference(WORK / 'system-native-a/simulation.json'),
            'actual original same-source INDEX8 normal native role required')
    return expected


def source_contract(watched):
    """Review source only; never import wrapper/release/bit public providers."""
    source = local_io(WRAPPER).read_text(encoding='utf-8-sig')
    tree = ast.parse(source)
    fields = next(node.value for node in tree.body if isinstance(node, ast.Assign)
                  and any(isinstance(target, ast.Name) and target.id == 'EXPECTED_FIELDS' for target in node.targets))
    require(ast.literal_eval(fields) == {'Schema', 'Target', 'PhysicalProof', *ROLE_NAMES}, 'exact seven request fields required')
    for text in ('bit.audit_request(REQUEST,use_cache=False)', 'proof_ref=wait_proof(args.wait_proof_seconds)',
                 'remove_owned_request(expected,SNAPSHOT)', 'return release.main()', 'bit.physical_flags(value)'):
        require(text in source, 'reviewed wrapper public authority contract changed')
    bit_source = local_io(BIT).read_text(encoding='utf-8-sig')
    bit_functions = {node.name: ast.get_source_segment(bit_source, node) for node in ast.parse(bit_source).body
                     if isinstance(node, ast.FunctionDef)}
    require('fresh_authority=True' in bit_functions['gate'] and 'use_cache=not fresh_authority' in bit_functions['recipe'],
            'separate uncached fresh runtime bit gate still required')
    for path in (WRAPPER, RELEASE, BIT, SELF):
        add(watched, path)


def derive(provider_sha, root_review_sha, roles_sha, generator_peer_path, generator_peer_sha):
    require(not local_io(OUTPUT).exists(), 'fresh v3 wrapper source manifest output required')
    require(provider_sha == ACTUAL_PROVIDER_SHA and root_review_sha == ACTUAL_ROOT_REVIEW_SHA,
            'only this run actual completed frozen v3 provider and root review may be selected')
    watched = {}
    for path, digest in PINS.items():
        add(watched, path, digest)
    add(watched, PROVIDER, provider_sha)
    add(watched, ROOT_REVIEW, root_review_sha)
    add(watched, ROLES, roles_sha)
    add(watched, ROLE_PROOF)
    provider, root_review, roles, proof = (read(path) for path in (PROVIDER, ROOT_REVIEW, ROLES, ROLE_PROOF))
    old, old_root = read(ORIGINAL), read(ORIGINAL_ROOT)
    require(old.get('Passed') is True and old.get('InputDrift') == [] and len(old['InputSHA256']) == 991
            and old_root.get('Passed') is True and old_root.get('IndependentPeerReviewPerformed') is True
            and old_root.get('InputDrift') == [], 'both actual original source authorities required')
    original_refs = {'OriginalProviderManifest': reference(ORIGINAL), 'OriginalRootReview': reference(ORIGINAL_ROOT)}
    require(provider.get('Schema') == 'hdmi-camera-fisheye-tile8df8v3-provider-source-manifest-v1'
            and provider.get('ProviderRevision') == REVISION and provider.get('Passed') is True
            and provider.get('InputDrift') == [] and provider.get('ManifestSelfIncluded') is False
            and provider.get('FuturePhysicalProofIncluded') is False
            and provider.get('PriorPhysicalTimingOrAcceptanceInherited') is False
            and provider.get('ApplicationMaximumSeconds') == 1800,
            'actual complete isolated v3 source freeze required')
    require(root_review.get('Schema') == 'hdmi-camera-fisheye-tile8df8v3-complete-source-independent-peer-review-v1'
            and root_review.get('ProviderRevision') == REVISION and root_review.get('Passed') is True
            and root_review.get('InputDrift') == [] and root_review.get('IndependentPeerReviewPerformed') is True
            and root_review.get('PhysicalAcceptanceInherited') is False
            and provider.get('IndependentClosedGroupReview') == reference(ROOT_REVIEW), 'actual new root source review required')
    for key, value in original_refs.items():
        require(provider.get(key) == root_review.get(key) == value,
                'new freeze and new root review must both bind original source provenance')
        require(provider['InputSHA256'].get(value['Path']) == root_review['InputSHA256'].get(value['Path']) == value['SHA256'],
                'both original authority files must enter both new closures')
    for value, schema in ((roles, 'hdmi-camera-fisheye-tile8df8v3-readonly-release-input-manifest-v1'),
                          (proof, 'hdmi-camera-fisheye-tile8df8v3-four-role-binding-proof-v1')):
        require(value.get('Schema') == schema and value.get('Passed') is True and value.get('InputDrift') == []
                and value.get('ProviderRevision') == REVISION and value.get('ProviderSourceManifest') == reference(PROVIDER)
                and value.get('SelectedBitstreamProvider') == reference(BIT)
                and all(value.get(name) is False for name in ('PhysicalProofAccepted', 'BitRecipeCreated', 'ReadyCreated',
                                                             'EDAExecuted', 'HardwareAccessed')),
                'actual readonly post-freeze v3 four-role binding required')
    require(roles.get('BindingProof') == reference(ROLE_PROOF), 'roles must select the actual v3 public binding proof')
    expected = check_role_references(provider, roles, proof, watched)
    for path in (DRIVER_PEER, PROVIDER_PEER):
        peer = read(path)
        require(peer.get('Passed') is True and peer.get('IndependentPeerReviewPerformed') is True
                and peer.get('InputDrift') == [] and peer.get('ProviderRevision') == REVISION,
                'actual frozen v3 independent source peer required')
        merge(watched, peer['InputSHA256'])
    generator_peer_path = add(watched, generator_peer_path, generator_peer_sha)
    require(generator_peer_path.parent == OUT and generator_peer_path not in (PROVIDER_PEER, DRIVER_PEER),
            'distinct actual new generator independent review under own output directory required')
    generator_peer = read(generator_peer_path)
    require(generator_peer.get('Schema') == 'tile8df8v3-prewarm-generator-independent-source-review-v1'
            and generator_peer.get('Passed') is True and generator_peer.get('IndependentPeerReviewPerformed') is True
            and generator_peer.get('SourceContractReviewOnly') is True and generator_peer.get('InputDrift') == []
            and generator_peer.get('EDAExecuted') is False and generator_peer.get('HardwareAccessed') is False
            and generator_peer['InputSHA256'].get(str(SELF)) == sha(SELF),
            'actual independent review of this exact generator source required')
    merge(watched, generator_peer['InputSHA256'])
    for value in (old, old_root, provider, root_review, roles, proof):
        merge(watched, value['InputSHA256'])
    require(provider['InputSHA256'].get(str(WRAPPER)) == sha(WRAPPER)
            and provider['InputSHA256'].get(str(RELEASE)) == sha(RELEASE)
            and provider['InputSHA256'].get(str(BIT)) == sha(BIT)
            and read(DRIVER_PEER)['InputSHA256'].get(str(WRAPPER)) == sha(WRAPPER)
            and read(DRIVER_PEER)['InputSHA256'].get(str(RELEASE)) == sha(RELEASE),
            'actual wrapper/release/bit must be bound by fresh complete freeze and driver peer')
    source_contract(watched)
    require(all(sha(name) == digest for name, digest in watched.items()), 'source closure changed during CPU verification')
    return {'Schema': 'hdmi-camera-fisheye-tile8df8v3-release-prewarm-wrapper-source-v1',
            'CheckedUTC': datetime.now(timezone.utc).isoformat(), 'ProviderSourceManifest': reference(PROVIDER),
            'ProviderRevision': REVISION, 'ExpectedRoleReferences': expected,
            'ActualSelectedFourRoleManifest': reference(ROLES), 'ActualFourRoleBindingProof': reference(ROLE_PROOF),
            'RootIndependentCompleteSourceReview': reference(ROOT_REVIEW),
            'IndependentDriverSourceReview': reference(DRIVER_PEER), 'IndependentProviderSourceReview': reference(PROVIDER_PEER),
            'IndependentGeneratorSourceReview': reference(generator_peer_path), 'Generator': reference(SELF),
            'Wrapper': reference(WRAPPER), 'FrozenReleaseDriver': reference(RELEASE), 'FrozenBitstreamProvider': reference(BIT),
            **original_refs, 'RootIndependentASTReviewPerformed': True, 'SourceClosureFrozen': True,
            'Original991SourceInputsRehashed': True, 'NewFreezeAndActualRolesAndBindingProofRehashed': True,
            'AllRecordedInputsActuallyRehashed': len(watched), 'ManifestSelfIncluded': False,
            'FutureV3ProofGORequestPrewarmBitOrProgramIncluded': False,
            'OnlyStartAfterOwnCompleteFinalPhysicalProofExists': True,
            'PublicUncachedPrewarmAndSeparateFreshRuntimeGateStillRequired': True,
            'PrewarmExecuted': False, 'SourceFreezeCreatedByThisTool': False, 'ReadyCreated': False,
            'RequestCreated': False, 'ProviderImportedOrExecuted': False, 'HardwareAccessed': False,
            'EDAExecuted': False, 'PDriveAccessed': False, 'ReleaseAuthorizedByThisSourceReview': False,
            'InputDrift': [], 'InputSHA256': dict(sorted(watched.items()))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--provider-manifest-sha256', required=True)
    parser.add_argument('--root-review-sha256', required=True)
    parser.add_argument('--roles-sha256', required=True)
    parser.add_argument('--generator-peer-review', type=Path, required=True)
    parser.add_argument('--generator-peer-review-sha256', required=True)
    args = parser.parse_args()
    value = derive(args.provider_manifest_sha256, args.root_review_sha256, args.roles_sha256,
                   args.generator_peer_review, args.generator_peer_review_sha256)
    require(not local_io(OUTPUT).exists(), 'immutable wrapper source manifest already exists')
    with local_io(OUTPUT).open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps({'SourceManifestCreated': reference(OUTPUT), 'InputsActuallyRehashed': len(value['InputSHA256']),
                      'PrewarmExecuted': False, 'ReadyCreated': False, 'ProviderImportedOrExecuted': False}))


if __name__ == '__main__':
    main()
