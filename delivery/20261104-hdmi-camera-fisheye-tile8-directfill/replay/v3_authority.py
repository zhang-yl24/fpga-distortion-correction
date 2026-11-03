"""Finite pure metadata checks for the isolated INDEX8 v3 release family.

No provider import, disk access, EDA or hardware action. Pending final pins
deliberately prevent final source authorization. Existing v2 evidence is
provenance only and must remain explicitly bound alongside the new freeze.
"""
import re

FAMILY = 'tile8df8v3'
REVISION = 'tile8df8v3-budget1800-a'
PREFIX = 'hdmi-camera-fisheye-' + FAMILY + '-'
TARGET = 'hdmi_camera_fisheye_top'
PROVIDER_SHA256 = '7b2c444b1e6e7d482c1875307fbc7b717689d0f5da9eaf8fac49ef249540a8fb'
ROOT_REVIEW_SHA256 = '714242e526fc1a9952cddf3eb9188437f5fed9cb7dc4c1b351077c03b6af150a'
WRAPPER_SHA256 = 'c8ac2c6b18b7a54cb6890d714f8d2a6f26880fcf5c318c84ba4166292be326a7'
ORIGINAL_PROVIDER_SHA256 = '8914c4c46ab950866747400cf1d668f3436720e562f10d76870c4440019fb50d'
ORIGINAL_ROOT_REVIEW_SHA256 = '27e614d3e584d1a8a278254b12fba992462a19a76bda445d54528a70012a9374'
FIVE_ROLES = ('PhysicalProof', 'MapperSimulation', 'SystemSimulation', 'IOSimulation', 'Profile')
GO_FLAGS = ('PriorWorkerEnded', 'PDriveReleased', 'UserAuthorizedVolatileSRAM', 'UserNotifiedBeforeExecution')
WARM_FALSE = ('PrivateCacheAccessed', 'ProvidersPatched', 'BitStagePrepared', 'PDriveCreated',
              'EDAExecuted', 'HardwareAccessed', 'ReleaseAuthorizedByPrewarm', 'PublicAuditRequestUseCache')
TRANSITION_FLAGS = ('ExactFiveRoleReferencesMatch', 'PDriveFree', 'UnchangedMainInvokedInSameInterpreter',
                    'FreshRuntimeGateStillRequired')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def exact_ref(value):
    require(type(value) is dict and set(value) == {'Path', 'SHA256'} and type(value['Path']) is str and
            value['Path'] and type(value['SHA256']) is str and re.fullmatch('[0-9a-f]{64}', value['SHA256']),
            'exact original Path/SHA256 authority reference required')
    return value


def pins_ready():
    require(all(type(value) is str and re.fullmatch('[0-9a-f]{64}', value) for value in
                (PROVIDER_SHA256, ROOT_REVIEW_SHA256, WRAPPER_SHA256)), 'v3 final source/wrapper pins are not frozen')


def check_source_freeze(provider_ref, root_ref, wrapper_ref, original_provider_ref, original_root_ref):
    pins_ready()
    for value, expected in ((provider_ref, PROVIDER_SHA256), (root_ref, ROOT_REVIEW_SHA256),
            (wrapper_ref, WRAPPER_SHA256), (original_provider_ref, ORIGINAL_PROVIDER_SHA256),
            (original_root_ref, ORIGINAL_ROOT_REVIEW_SHA256)):
        require(exact_ref(value)['SHA256'] == expected, 'new/original source freeze authority differs')
    return {'NewV3AndOriginalProvenanceBothRequired': True, 'SourcePinsFrozen': True}


def check_release_metadata(bitplan, go, warm, transition, refs):
    """Check already byte-bound records; caller must verify canonical paths/bytes.

    This finite function intentionally does not authorize source pins. The
    production callers must also call check_source_freeze() before accepting.
    """
    names = {'ProviderManifest', 'RootSourceReview', 'PrewarmWrapper', 'ReleaseGO', 'PrewarmAuthority',
             'ReleaseDriver', 'ReleaseInputManifest', 'RequestSnapshot', 'RequestComparison', 'ActualRequest', *FIVE_ROLES}
    require(set(refs) == names, 'complete exact v3 authority reference set required')
    for value in refs.values(): exact_ref(value)
    require(bitplan.get('Schema') == PREFIX + 'bitstream-plan-v1' and bitplan.get('Target') == TARGET and
            bitplan.get('Request') == refs['ActualRequest'], 'own v3 bit plan/request identity required')
    require(go.get('Schema') == PREFIX + 'physical-to-release-go-v1' and go.get('ProviderRevision') == REVISION and
            all(go.get(k) is True for k in GO_FLAGS), 'own v3 release GO flags/revision required')
    require(go.get('ProviderSourceManifest') == refs['ProviderManifest'] and
            go.get('SelectedReleaseInputManifest') == refs['ReleaseInputManifest'], 'v3 GO source/selected roles differ')
    require(warm.get('Schema') == PREFIX + 'release-authority-prewarm-v1' and warm.get('Passed') is True and
            warm.get('InputDrift') == [] and warm.get('RequestExclusiveCreatedByWrapper') is True and
            warm.get('FreshRuntimeGateStillRequired') is True and all(warm.get(k) is False for k in WARM_FALSE),
            'own uncached v3 prewarm scope/flags required')
    request = warm.get('ExactRequest', {})
    require(set(request) == {'Schema', 'Target', *FIVE_ROLES} and request['Schema'] == PREFIX + 'bitstream-request-v1' and
            request['Target'] == TARGET, 'exact v3 seven-field runtime request required')
    for name in FIVE_ROLES:
        require(bitplan.get(name) == go.get(name) == request[name] == refs[name], 'v3 exact runtime role differs: ' + name)
    require(warm.get('ProviderSourceManifest') == refs['ProviderManifest'] and
            warm.get('ReviewedWrapperManifest') == refs['PrewarmWrapper'] and
            warm.get('ActualSelectedFourRoleManifest') == refs['ReleaseInputManifest'] and
            warm.get('FrozenReleaseDriver') == refs['ReleaseDriver'], 'v3 prewarm source/wrapper/driver/roles differ')
    require(warm.get('RequestSnapshot') == refs['RequestSnapshot'] and warm.get('RequestPath') == refs['ActualRequest']['Path'] and
            warm.get('RequestSHA256') == refs['RequestSnapshot']['SHA256'] == refs['ActualRequest']['SHA256'],
            'v3 actual request/snapshot identity differs')
    require(transition.get('Schema') == PREFIX + 'release-prewarm-authorized-transition-v1' and
            transition.get('Passed') is True and transition.get('PrivateCacheAccessed') is False and
            all(transition.get(k) is True for k in TRANSITION_FLAGS), 'own v3 authorized transition scope required')
    require(transition.get('RootReleaseGo') == refs['ReleaseGO'] and transition.get('PrewarmReceipt') == refs['PrewarmAuthority'] and
            transition.get('ExpectedRealRequestSHA256') == refs['ActualRequest']['SHA256'] and
            transition.get('FrozenReleaseDriver') == refs['ReleaseDriver'] and
            transition.get('RequestComparison') == refs['RequestComparison'] and
            refs['RequestComparison']['SHA256'] == refs['RequestSnapshot']['SHA256'], 'v3 transition/request byte identity differs')
    return {'ReleaseFamily': FAMILY, 'ProviderRevision': REVISION, 'ExactFiveRoleReferencesMatch': True,
            'AuthorizedTransitionChecked': True, 'FreshGateStillRequired': True,
            'OldV2AcceptanceInherited': False, 'DiagnosticAcceptedAsPhysicalProof': False,
            'ProviderVerificationInvoked': False, 'EDAExecuted': False, 'HardwareAccessed': False}
