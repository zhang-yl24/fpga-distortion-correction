"""Pure CPU/synthetic draft tests; never prepare an actual warning inventory."""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import importlib.util
import json
import re

import pytest

WORK = Path(__file__).resolve().parents[1] / 'work/hdmi-camera-fisheye-tile8df8-20261103-a'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


p = load('test_df8_actual_warning_prepare', WORK / 'prepare_source_warning_inventory_b.py')
r = load('test_df8_actual_warning_review', WORK / 'review_source_warning_inventory_draft_b.py')
KNOWN = "W: Adm-4021: The attribute '.name' of object 'synthetic_known' is overwritten by new value."
NEW = "W: Adm-4021: The attribute '.name' of object 'synthetic_new' is overwritten by new value."
UNKNOWN = 'W: Unreviewed-9999: synthetic test-only business-data deletion.'


def classify(body):
    if re.fullmatch(r"W: Adm-4021: The attribute '\.name' of object '[^']+' is overwritten by new value\.", body):
        return 'CompilerLogicalNameMetadataOnly'
    raise ValueError('synthetic unknown body requires review')


def baseline():
    return {'BodyClasses': {KNOWN: 'CompilerLogicalNameMetadataOnly'},
            'WarningBodiesByLog': {'compile/run.log': {KNOWN: 2}},
            'Simulations': {'MapperSimulation': {'Path': str(WORK / 'synthetic-old/mapper.json'), 'SHA256': 'a' * 64},
                            'SystemSmallSimulation': {'Path': str(WORK / 'synthetic-old/system.json'), 'SHA256': 'b' * 64},
                            'IOSimulation': {'Path': str(WORK / 'synthetic-old/io.json'), 'SHA256': 'c' * 64}}}


def synthetic_draft(include_unknown=False):
    actual = {'compile/run.log': {KNOWN: 3, NEW: 4}}
    if include_unknown:
        actual['compile/run.log'][UNKNOWN] = 1
    difference = p.warning_difference(actual, baseline(), classify)
    value = {'Schema': p.DRAFT_SCHEMA, 'DraftComplete': True, 'RootReviewRequired': True,
             'NewBodiesRequireExplicitRootReview': True, 'Target': 'hdmi_camera_fisheye_top',
             'BuildPlan': {'Path': 'SYNTHETIC-NOT-AN-ACTUAL-BUILD', 'SHA256': '0' * 64},
             'SourceBuildReceipt': {'Path': 'SYNTHETIC-NOT-AN-ACTUAL-RECEIPT', 'SHA256': '1' * 64},
             'DifferenceFrom15FPSTile8': difference, 'UnknownWarningBodies': difference['UnknownWarningBodies'],
             'UnchangedCacheSourceEvidence': {
                 'SourceSHA256': p.CACHE_SOURCE_SHA256,
                 'UnitReceipt': {'Path': str(p.UNIT_RECEIPT.resolve()), 'SHA256': p.UNIT_RECEIPT_SHA256},
                 'CollisionReceipt': {'Path': str(p.COLLISION_RECEIPT.resolve()), 'SHA256': p.COLLISION_RECEIPT_SHA256},
                 'ActualEvidenceWork': str(p.CACHE_EVIDENCE_WORK.resolve()),
                 'INDEX9NativeMappingOrTimingInherited': False, 'INDEX8NativeTimingAccepted': False,
                 'HardwareReleaseAllowed': False},
             'SharePinSourceComparison': {'SourceBytesEqual': True, 'BodiesDifferOnlyByEqualByteFilename': True,
                                           'NativeElectricalAcceptanceConferred': False}}
    value['ProposedInventory'] = {'Schema': 'hdmi-camera-fisheye-tile8df8-warning-inventory-v1',
                                 'Target': value['Target'], 'BuildPlan': value['BuildPlan'],
                                 'SourceBuildReceipt': value['SourceBuildReceipt'], 'WarningBodiesByLog': actual,
                                 'BodyClasses': difference['ProposedBodyClasses'],
                                 'Counts': difference['ActualCountsByCode'], 'UniqueBodies': difference['ActualUniqueBodies']}
    for key in ('Passed', 'FinalInventoryWritten', 'PriorCompilerOrTimingAcceptanceInherited',
                'SourceDiagnosticReviewPassed', 'UnknownWarningsAccepted', 'TimingAccepted',
                'NativeEquivalent', 'CDCAccepted', 'HardwareReleaseAllowed', 'HardwareAccessed', 'EDAExecuted'):
        value[key] = False
    return value


def test_synthetic_known_classes_remain_unsigned_and_require_root_review():
    value = synthetic_draft()
    result = r.inspect_unsigned_draft(value, p)
    assert result['DraftIntegrityVerified'] and result['RootReviewRequired']
    assert not result['WarningDispositionAccepted'] and not result['FinalInventoryWritten']
    assert result['ReadyForRootDispositionReview'] and result['ActualUniqueBodies'] == 2
    assert all(row['RootReviewRequired'] and not row['AcceptedByThisTool']
               for row in value['DifferenceFrom15FPSTile8']['BodyClassProposals'])


def test_unknown_W_is_saved_as_a_blocker_not_silently_accepted():
    value = synthetic_draft(True)
    result = r.inspect_unsigned_draft(value, p)
    assert result['UnknownWarningBodies'] == [UNKNOWN]
    assert not result['ReadyForRootDispositionReview']
    assert UNKNOWN not in value['ProposedInventory']['BodyClasses']
    assert not value['UnknownWarningsAccepted']


@pytest.mark.parametrize('multiplicity', [1, 17, 83, 317])
def test_actual_counts_are_derived_without_prior_fixed_addition_numbers(multiplicity):
    value = p.warning_difference({'stdout.log': {NEW: multiplicity}}, baseline(), classify)
    assert value['ActualCountsByCode'] == {'Adm-4021': multiplicity}
    assert value['AddedUniqueCountsByCode'] == {'Adm-4021': 1}
    assert value['RemovedUniqueCountsByCode'] == {'Adm-4021': 1}
    assert value['AddedComparedWithTile8'] == [NEW] and value['RemovedComparedWithTile8'] == [KNOWN]
    assert value['AnyWarningAcceptedByThisTool'] is False


@pytest.mark.parametrize('bad', [0, -1, True, 1.0, '1'])
def test_warning_multiplicities_cannot_be_invalid_or_boolean(bad):
    with pytest.raises(ValueError, match='positive integer'):
        p.warning_difference({'stdout.log': {NEW: bad}}, baseline(), classify)


@pytest.mark.parametrize('name', ['../outside.log', '/outside.log', 'receipt.json'])
def test_warning_log_cannot_escape_the_completed_build(name):
    with pytest.raises(ValueError, match='relative .log'):
        p.warning_difference({name: {NEW: 1}}, baseline(), classify)


@pytest.mark.parametrize('field', ['Passed', 'FinalInventoryWritten', 'PriorCompilerOrTimingAcceptanceInherited',
    'SourceDiagnosticReviewPassed', 'UnknownWarningsAccepted', 'TimingAccepted', 'NativeEquivalent',
    'CDCAccepted', 'HardwareReleaseAllowed', 'HardwareAccessed', 'EDAExecuted'])
def test_unsigned_draft_cannot_confer_final_acceptance(field):
    value = synthetic_draft()
    value[field] = True
    with pytest.raises(ValueError, match='overclaims'):
        r.inspect_unsigned_draft(value, p)


@pytest.mark.parametrize('change', ['hide_unknown', 'invent_unknown_class', 'accept_proposal',
                                   'drop_proposal', 'change_count', 'different_build'])
def test_draft_review_rejects_hidden_unknowns_and_rebound_results(change):
    value = synthetic_draft(True)
    if change == 'hide_unknown':
        value['UnknownWarningBodies'] = []
        value['DifferenceFrom15FPSTile8']['UnknownWarningBodies'] = []
    elif change == 'invent_unknown_class':
        value['ProposedInventory']['BodyClasses'][UNKNOWN] = 'SafeByCallerAssertion'
    elif change == 'accept_proposal':
        value['DifferenceFrom15FPSTile8']['BodyClassProposals'][0]['AcceptedByThisTool'] = True
    elif change == 'drop_proposal':
        value['DifferenceFrom15FPSTile8']['BodyClassProposals'].pop()
    elif change == 'change_count':
        value['ProposedInventory']['Counts']['Adm-4021'] = 9
    else:
        value['ProposedInventory']['BuildPlan'] = {'Path': 'OTHER', 'SHA256': 'f' * 64}
    with pytest.raises(ValueError):
        r.inspect_unsigned_draft(value, p)


def diagnostics():
    prefix = 'P:/synthetic-current/build-a'
    rows = []
    for log in p.DIAGNOSTIC_LOGS:
        for source, line, name, old, new in p.EXPECTED_REDUCTIONS:
            rows.append(f'{log}: C: Sdm-3003: [{prefix}/compiled/{source}(line number: {line})] '
                        f'Reduce accumulator {name} size from {old} to {new}. '
                        'If this is not intended behavior, please drive ' + name + ' with valid values.')
    return prefix, rows


def test_only_the_five_exact_counter_diagnostics_with_actual_log_multiplicity_are_allowed():
    prefix, rows = diagnostics()
    result = p.critical_diagnostics(rows, prefix, p.EXPECTED_REDUCTIONS)
    assert len(result['DistinctReductionBodies']) == 5 and len(result['ExactLogMultiplicity']) == 20
    assert not result['CompilerDiagnosticsCleared']
    assert not result['ProtectedVendorIndependentRangeProofClaimed']


@pytest.mark.parametrize('change', ['missing', 'duplicate', 'unknown', 'line', 'width', 'counter', 'other_prefix'])
def test_unknown_or_changed_critical_C_diagnostics_are_rejected(change):
    prefix, rows = diagnostics()
    if change == 'missing':
        rows.pop()
    elif change == 'duplicate':
        rows.append(rows[0])
    elif change == 'unknown':
        rows.append('stdout.log: C: Sdm-9999: caller wants this ignored')
    elif change == 'line':
        rows[0] = rows[0].replace('line number: 47', 'line number: 48')
    elif change == 'width':
        rows[0] = rows[0].replace('from 32 to 22', 'from 32 to 21')
    elif change == 'counter':
        rows[0] = rows[0].replace('cfg_wait_count', 'business_pixels')
    else:
        rows[0] = rows[0].replace('synthetic-current', 'old-tile8')
    with pytest.raises(ValueError, match='critical reduction'):
        p.critical_diagnostics(rows, prefix, p.EXPECTED_REDUCTIONS)


def test_caller_cannot_expand_the_protected_reduction_list():
    prefix, rows = diagnostics()
    with pytest.raises(ValueError, match='five unchanged'):
        p.critical_diagnostics(rows, prefix, (*p.EXPECTED_REDUCTIONS, ('other', 1, 'new', 8, 1)))


def test_system_small_is_new_while_mapper_and_IO_are_exact_baseline_references():
    prior = baseline()
    path = WORK / 'system-small-a/simulation.json'
    current = {'Path': str(path), 'SHA256': 'd' * 64}
    result = p.select_simulations(prior, current, path)
    assert result['MapperSimulation'] == prior['Simulations']['MapperSimulation']
    assert result['IOSimulation'] == prior['Simulations']['IOSimulation']
    assert result['SystemSmallSimulation'] == current
    assert result['SystemSmallSimulation'] != prior['Simulations']['SystemSmallSimulation']


@pytest.mark.parametrize('change', ['old_system', 'other_new_work', 'extra_role', 'extra_field'])
def test_system_small_cannot_reuse_old_result_or_wrong_provider_role(change):
    prior = baseline()
    path = WORK / 'system-small-a/simulation.json'
    current = {'Path': str(path), 'SHA256': 'd' * 64}
    if change == 'old_system':
        current = prior['Simulations']['SystemSmallSimulation']
    elif change == 'other_new_work':
        current['Path'] = str(WORK / 'unrelated/simulation.json')
    elif change == 'extra_role':
        prior['Simulations']['CallerPassed'] = current
    else:
        current['Passed'] = True
    with pytest.raises(ValueError):
        p.select_simulations(prior, current, path)


def test_sharepin_uses_equal_actual_FDC_bytes_and_only_filename_normalization(tmp_path):
    old = tmp_path / 'hdmi-camera-fisheye-tile8-internal.fdc'
    new = tmp_path / 'hdmi-camera-fisheye-tile8df8-internal.fdc'
    old.write_bytes(p.BASELINE_FDC.read_bytes())
    new.write_bytes(old.read_bytes())
    old_body = f'W: ConstraintEditor-4040: [@BUILD@/compiled/board/{old.name}(line number: 1)] Port p:test has been placed at location TEST, whose type is share pin.'
    new_body = old_body.replace(old.name, new.name)
    prior = {'BodyClasses': {old_body: 'PriorSharePinScope'}}
    result = p.sharepin_review({'stdout.log': {new_body: 2}}, prior, new, old)
    assert result['SourceBytesEqual'] and result['BodiesDifferOnlyByEqualByteFilename']
    assert not result['NativeElectricalAcceptanceConferred']
    new.write_bytes(new.read_bytes() + b'\n')
    with pytest.raises(ValueError, match='FDC source bytes changed'):
        p.sharepin_review({'stdout.log': {new_body: 2}}, prior, new, old)


@pytest.mark.parametrize('change', ['port', 'location', 'line', 'missing_body'])
def test_changed_sharepin_body_is_not_accepted_by_a_matching_filename(tmp_path, change):
    old = tmp_path / 'hdmi-camera-fisheye-tile8-internal.fdc'
    new = tmp_path / 'hdmi-camera-fisheye-tile8df8-internal.fdc'
    old.write_bytes(p.BASELINE_FDC.read_bytes())
    new.write_bytes(old.read_bytes())
    old_body = f'W: ConstraintEditor-4040: [@BUILD@/compiled/board/{old.name}(line number: 1)] Port p:test has been placed at location TEST, whose type is share pin.'
    new_body = old_body.replace(old.name, new.name)
    if change == 'port':
        new_body = new_body.replace('p:test', 'p:other')
    elif change == 'location':
        new_body = new_body.replace('location TEST', 'location OTHER')
    elif change == 'line':
        new_body = new_body.replace('line number: 1', 'line number: 2')
    actual = {} if change == 'missing_body' else {'stdout.log': {new_body: 1}}
    with pytest.raises(ValueError, match='bodies changed'):
        p.sharepin_review(actual, {'BodyClasses': {old_body: 'Prior'}}, new, old)


def test_incomplete_actual_build_is_rejected_before_warning_collection():
    called = []

    def incomplete(_):
        raise ValueError('synthetic actual build is incomplete')

    w = SimpleNamespace(__file__=str(p.ROOT / 'tools/hdmi_camera_fisheye_tile8df8_warnings.py'),
        build=SimpleNamespace(WORK=WORK, TARGET='hdmi_camera_fisheye_top', validate=lambda _: {},
                              verify_execution=incomplete),
        warning_inventory=lambda *args: called.append(args))
    with pytest.raises(ValueError, match='build is incomplete'):
        p.derive_draft(w)
    assert called == []


def test_prepare_cli_cannot_target_final_inventory_or_an_unowned_path(tmp_path):
    for target in (WORK / 'source-warning-inventory-a.json', tmp_path / 'source-warning-inventory-draft-a.json'):
        with pytest.raises(ValueError, match='draft filename'):
            p.main(['--output', str(target)])


def test_df8_namespace_changes_only_the_candidate_not_saved_df9_cache_evidence():
    assert p.WORK == WORK and 'tile8df8' in str(WORK)
    assert p.DRAFT_SCHEMA == 'hdmi-camera-fisheye-tile8df8-warning-inventory-draft-v1'
    assert p.UNIT_RECEIPT.parent.parent == p.CACHE_EVIDENCE_WORK
    assert p.COLLISION_RECEIPT.parent.parent == p.CACHE_EVIDENCE_WORK
    assert 'tile8df9' in str(p.CACHE_EVIDENCE_WORK)
    assert p.CACHE_EVIDENCE_WORK != WORK


@pytest.mark.parametrize('change', ['unit_df8', 'collision_df8', 'cache_sha', 'inherit_mapping',
    'accept_timing8', 'release', 'unit_sha', 'collision_sha'])
def test_review_rejects_misplaced_or_overclaimed_saved_cache_evidence(change):
    value = synthetic_draft()
    cache = value['UnchangedCacheSourceEvidence']
    if change == 'unit_df8':
        cache['UnitReceipt']['Path'] = str(WORK / 'cache-unit-a/simulation.json')
    elif change == 'collision_df8':
        cache['CollisionReceipt']['Path'] = str(WORK / 'cache-commit-collision-a/simulation.json')
    elif change == 'cache_sha':
        cache['SourceSHA256'] = '0' * 64
    elif change == 'inherit_mapping':
        cache['INDEX9NativeMappingOrTimingInherited'] = True
    elif change == 'accept_timing8':
        cache['INDEX8NativeTimingAccepted'] = True
    elif change == 'release':
        cache['HardwareReleaseAllowed'] = True
    elif change == 'unit_sha':
        cache['UnitReceipt']['SHA256'] = '0' * 64
    else:
        cache['CollisionReceipt']['SHA256'] = '0' * 64
    with pytest.raises(ValueError, match='same-source cache evidence'):
        r.inspect_unsigned_draft(value, p)


def synthetic_cache_files(tmp_path, monkeypatch):
    evidence = tmp_path / 'work/hdmi-camera-fisheye-tile8df9-20261103-a'
    unit = evidence / 'cache-unit-a/simulation.json'
    collision = evidence / 'cache-commit-collision-a/simulation.json'
    unit.parent.mkdir(parents=True); collision.parent.mkdir(parents=True)
    unit.write_text('{"SyntheticUnitOnly":true}', encoding='utf-8')
    source = tmp_path / 'rtl/experimental/ddr_neighbour_cache_scatter16_rowpipe_directfill.v'
    source.parent.mkdir(parents=True); source.write_text('// synthetic cache bytes', encoding='utf-8')
    summary = {'Passed': True, 'IndexBits': 9, 'Cases': 4, 'SuccessfulCommonResetRecoveries': 4,
        'IndependentRAMPixelsChecked': 864, 'NinthRAndLastCommitCollision': True, 'MalformedFinalRID': True,
        'MissingFinalRLAST': True, 'ResetBeforeFinalRAMCommit': True, 'FaultQuarantineChecked': True}
    summary_path = collision.parent / 'peer-commit-summary.json'
    summary_path.write_text(json.dumps(summary), encoding='utf-8')
    log = collision.parent / 'simulation.log'
    log.write_text('PASS DIRECTFILL PEER real final-commit/fault/reset collisions and independent RAM/pixel oracle\n$finish called\n', encoding='utf-8')
    receipt = {'Schema': 'tile8-directfill-independent-peer-commit-collision-v1', 'Passed': True,
        'InputDrift': [], 'HDLSimulationExecuted': True, 'PDSAccessed': False, 'HardwareAccessed': False,
        'NativeRAMMappingOrTimingAccepted': False, 'Summary': summary,
        'SourceSHA256': {str(source): p.sha(source)},
        'ArtifactsSHA256': {summary_path.name: p.sha(summary_path), log.name: p.sha(log)}}
    collision.write_text(json.dumps(receipt), encoding='utf-8')
    for key, value in {'ROOT': tmp_path, 'CACHE_EVIDENCE_WORK': evidence, 'UNIT_RECEIPT': unit,
        'UNIT_RECEIPT_SHA256': p.sha(unit), 'COLLISION_RECEIPT': collision,
        'COLLISION_RECEIPT_SHA256': p.sha(collision), 'CACHE_SOURCE_SHA256': p.sha(source)}.items():
        monkeypatch.setattr(p, key, value)
    facts = {'DirectFillCacheSourceContract': {'SourceSHA256': p.CACHE_SOURCE_SHA256,
             'CompletedUnitReceipt': p.ref(unit)}}
    return facts, {str(unit): p.sha(unit)}, receipt, collision, source, log


def test_saved_cache_binding_only_reads_completed_synthetic_files(tmp_path, monkeypatch):
    facts, inputs, _, _, _, _ = synthetic_cache_files(tmp_path, monkeypatch)
    result, watched = p.saved_cache_source_bindings(facts, inputs)
    assert result['UnitReceipt'] == facts['DirectFillCacheSourceContract']['CompletedUnitReceipt']
    assert result['CollisionCases']['Cases'] == 4
    assert not result['INDEX9NativeMappingOrTimingInherited']
    assert not result['INDEX8NativeTimingAccepted'] and not result['HardwareReleaseAllowed']
    assert len(watched) == 4


@pytest.mark.parametrize('change', ['not_passed', 'drift', 'pds', 'hardware', 'native_acceptance',
    'missing_case', 'missing_unit_watch', 'wrong_source', 'escaped_artifact', 'missing_marker',
    'source_drift', 'unit_drift', 'unbound_log'])
def test_saved_collision_binding_rejects_faulty_or_overclaimed_evidence(tmp_path, monkeypatch, change):
    facts, inputs, receipt, collision, source, log = synthetic_cache_files(tmp_path, monkeypatch)
    if change == 'not_passed': receipt['Passed'] = False
    elif change == 'drift': receipt['InputDrift'] = ['changed']
    elif change == 'pds': receipt['PDSAccessed'] = True
    elif change == 'hardware': receipt['HardwareAccessed'] = True
    elif change == 'native_acceptance': receipt['NativeRAMMappingOrTimingAccepted'] = True
    elif change == 'missing_case': receipt['Summary']['NinthRAndLastCommitCollision'] = False
    elif change == 'missing_unit_watch': inputs.clear()
    elif change == 'wrong_source': receipt['SourceSHA256'][str(source)] = '0' * 64
    elif change == 'escaped_artifact': receipt['ArtifactsSHA256']['../outside.log'] = '0' * 64
    elif change == 'missing_marker':
        log.write_text('$finish called\n', encoding='utf-8')
        receipt['ArtifactsSHA256'][log.name] = p.sha(log)
    elif change == 'source_drift': source.write_text('// changed cache', encoding='utf-8')
    elif change == 'unit_drift': p.UNIT_RECEIPT.write_text('{}', encoding='utf-8')
    else: del receipt['ArtifactsSHA256'][log.name]
    collision.write_text(json.dumps(receipt), encoding='utf-8')
    monkeypatch.setattr(p, 'COLLISION_RECEIPT_SHA256', p.sha(collision))
    with pytest.raises(ValueError):
        p.saved_cache_source_bindings(facts, inputs)


def pcf_body():
    return 'W: ConstraintEditor-4040: [@BUILD@/device_map/hdmi_camera_fisheye_top.pcf(line number: 10)] Port mem_dq[5] has been placed at location K7, whose type is share pin.'


def test_generated_PCF_body_is_compared_byte_for_byte_without_FDC_normalization(tmp_path):
    old = tmp_path / 'hdmi-camera-fisheye-tile8-internal.fdc'
    new = tmp_path / 'hdmi-camera-fisheye-tile8df8-internal.fdc'
    old.write_bytes(p.BASELINE_FDC.read_bytes()); new.write_bytes(old.read_bytes())
    body = pcf_body()
    result = p.sharepin_review({'stdout.log': {body: 2}}, {'BodyClasses': {body: 'Prior'}}, new, old)
    assert result['GeneratedPCFBodiesComparedWithoutAnyNormalization']
    assert result['GeneratedPCFUniqueBodies'] == 1
    assert not result['NativeElectricalAcceptanceConferred']


@pytest.mark.parametrize('change', ['port', 'location', 'line', 'path', 'target', 'missing', 'extra'])
def test_generated_PCF_changes_are_not_accepted_by_same_byte_FDC(tmp_path, change):
    old = tmp_path / 'hdmi-camera-fisheye-tile8-internal.fdc'
    new = tmp_path / 'hdmi-camera-fisheye-tile8df8-internal.fdc'
    old.write_bytes(p.BASELINE_FDC.read_bytes()); new.write_bytes(old.read_bytes())
    body = pcf_body(); actual = body
    if change == 'port': actual = actual.replace('mem_dq[5]', 'mem_dq[6]')
    elif change == 'location': actual = actual.replace('K7', 'K8')
    elif change == 'line': actual = actual.replace('number: 10', 'number: 11')
    elif change == 'path': actual = actual.replace('/device_map/', '/other/')
    elif change == 'target': actual = actual.replace('fisheye_top.pcf', 'other_top.pcf')
    rows = {} if change == 'missing' else {actual: 1}
    if change == 'extra': rows[actual.replace('number: 10', 'number: 11')] = 1
    with pytest.raises(ValueError):
        p.sharepin_review({'stdout.log': rows} if rows else {}, {'BodyClasses': {body: 'Prior'}}, new, old)


def test_long_compiled_path_still_receives_complete_byte_hash(tmp_path):
    target = tmp_path
    for index in range(8): target = target / ('owned_long_component_' + str(index) + 'x' * 24)
    p.local_io(target).mkdir(parents=True)
    path = target / 'compiled.vp'; p.local_io(path).write_bytes(b'complete protected body bytes')
    assert p.sha(path) == p.hashlib.sha256(b'complete protected body bytes').hexdigest()
    assert p.ref(path)['SHA256'] == p.sha(path)
