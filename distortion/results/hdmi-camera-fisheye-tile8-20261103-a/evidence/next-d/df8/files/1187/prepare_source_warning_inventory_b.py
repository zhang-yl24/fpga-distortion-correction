"""Prepare an unsigned warning-inventory DRAFT from this completed df8 build.

No final inventory is written. Every proposed disposition, including an exact
baseline body, requires root review; unknown W bodies remain explicit blockers.
This script never runs EDA, a simulator, JTAG, serial IO or a build subprocess.
"""
from collections import Counter
from pathlib import Path
import argparse
import hashlib
import importlib
import json
import os
import re
import sys

WORK = Path(__file__).resolve().parent
ROOT = WORK.parents[1]
SELF = Path(__file__).resolve()
REVIEW_HELPER = WORK / 'review_source_warning_inventory_draft_b.py'
BASELINE_WORK = ROOT / 'work/hdmi-camera-fisheye-tile8-20261103-a'
BASELINE_INVENTORY = BASELINE_WORK / 'source-warning-inventory-a.json'
BASELINE_SHA256 = '89b8ff5108083737e35668bc29c1c2899d3359f700b6a9fb1adc87b8fc727465'
BASELINE_FDC = ROOT / 'board/hdmi-camera-fisheye-tile8-internal.fdc'
BASELINE_FDC_SHA256 = 'e27a18c4a5f228ac8543e50c9b50a145f14bf1d4e640ff34361422d32f1bf78a'
DRAFT_SCHEMA = 'hdmi-camera-fisheye-tile8df8-warning-inventory-draft-v1'
EXPECTED_REDUCTIONS = (
    ('board/hdmi_camera_fisheye_top.v', 47, 'cfg_wait_count', 32, 22),
    ('board/hdmi_camera_fisheye_top.v', 172, 'pclk_age', 32, 22),
    ('rtl/experimental/iic_dri_checked.v', 93, 'watchdog', 32, 17),
    ('platform/video_base/ipcore/ddr3_test/rtl/mcdq_ctrl/ips2l_mcdq_dcp_buf_v1_2.vp', 541, 'cnt', 7, 6),
    ('platform/video_base/ipcore/ddr3_test/rtl/ddrphy/ips2l_ddrphy_data_slice_wrcal_v1_10.vp', 614, 'delay_cnt', 4, 2),
)
DIAGNOSTIC_LOGS = ('compile/run.log', 'flow.log', 'run.log', 'stdout.log')
DDR_PARAMETERS_SHA256 = '95e39e516343108c06d7ff878606f0f5a0bca8af96bee6eb0cf4434197775857'
CACHE_SOURCE_SHA256 = 'd4730a733bc8f84886d268fcc90bb702db035a41867c812d6119694fbbf35b1e'
# These remain in their actual INDEX9 work directory. Their finite cache/source
# evidence covers the unchanged bytes; INDEX9 native mapping/STA is not reused.
CACHE_EVIDENCE_WORK = ROOT / 'work/hdmi-camera-fisheye-tile8df9-20261103-a'
UNIT_RECEIPT = CACHE_EVIDENCE_WORK / 'cache-unit-a/simulation.json'
UNIT_RECEIPT_SHA256 = '3340fb27a7d6953e10e98cf07dba0cb8ed85181beaaf049eb392d8fc72870b27'
COLLISION_RECEIPT = CACHE_EVIDENCE_WORK / 'cache-commit-collision-a/simulation.json'
COLLISION_RECEIPT_SHA256 = '2ceef24b77af4243907ce7dc343ce321f10e02384e7966aba910b95b1aef02d3'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def local_io(path):
    """Match the build verifier's exact Windows long-path byte access."""
    text = str(Path(path).absolute())
    if os.name == 'nt' and not text.startswith('\\\\?\\'):
        text = '\\\\?\\UNC\\' + text[2:] if text.startswith('\\\\') else '\\\\?\\' + text
    return Path(text)


def sha(path):
    return hashlib.sha256(local_io(path).read_bytes()).hexdigest()


def ref(path):
    path = Path(path).resolve()
    return {'Path': str(path), 'SHA256': sha(path)}


def warning_code(body):
    match = re.match(r'W: ([A-Za-z]+-\d+):', body)
    return match[1] if match else 'Unnumbered'


def validate_warning_map(actual):
    require(isinstance(actual, dict), 'actual W inventory must be a dictionary')
    for name, rows in actual.items():
        path = Path(name)
        require(not path.anchor and not path.is_absolute() and '..' not in path.parts and path.suffix == '.log' and
                isinstance(rows, dict) and rows, 'warning log must be an owned nonempty relative .log')
        for body, count in rows.items():
            require(type(body) is str and body.startswith('W:') and '\n' not in body and '\r' not in body and
                    type(count) is int and count > 0, 'exact W body and positive integer multiplicity required')


def warning_difference(actual, baseline, classify):
    """Propose finite classes; never treat a returned class as acceptance."""
    validate_warning_map(actual)
    prior = baseline['BodyClasses']
    require(isinstance(prior, dict) and all(type(body) is str and type(kind) is str for body, kind in prior.items()),
            'baseline body classes required for difference only')
    now = {body for rows in actual.values() for body in rows}
    proposals, unknown, classes = [], [], {}
    for body in sorted(now):
        error = None
        try:
            kind = classify(body)
            require(type(kind) is str and kind, 'finite nonempty class required')
        except (ValueError, KeyError, TypeError) as failure:
            kind, error = None, str(failure)
            unknown.append(body)
        if kind is not None:
            classes[body] = kind
        proposals.append({'Body': body, 'ProposedClass': kind, 'BaselineExactBody': body in prior,
                          'BaselineClassForComparisonOnly': prior.get(body),
                          'RootReviewRequired': True, 'AcceptedByThisTool': False,
                          'ClassificationError': error})
    counts = Counter()
    multiplicity = Counter()
    for rows in actual.values():
        for body, count in rows.items():
            counts[warning_code(body)] += count
            multiplicity[body] += count
    old_multiplicity = Counter()
    for rows in baseline.get('WarningBodiesByLog', {}).values():
        old_multiplicity.update(rows)
    deltas = [{'Body': body, 'BaselineOccurrences': old_multiplicity[body],
               'ActualOccurrences': multiplicity[body], 'Delta': multiplicity[body] - old_multiplicity[body]}
              for body in sorted(now | set(old_multiplicity))
              if multiplicity[body] != old_multiplicity[body]]
    added, removed = sorted(now - set(prior)), sorted(set(prior) - now)
    return {'BodyClassProposals': proposals, 'ProposedBodyClasses': classes,
            'UnknownWarningBodies': unknown, 'ActualCountsByCode': dict(sorted(counts.items())),
            'ActualUniqueBodies': len(now), 'AddedComparedWithTile8': added,
            'RemovedComparedWithTile8': removed,
            'AddedUniqueCountsByCode': dict(sorted(Counter(map(warning_code, added)).items())),
            'RemovedUniqueCountsByCode': dict(sorted(Counter(map(warning_code, removed)).items())),
            'WarningMultiplicityDeltas': deltas,
            'RootReviewRequired': True, 'AnyWarningAcceptedByThisTool': False}


def sharepin_review(actual, baseline, current_fdc, baseline_fdc):
    current_fdc, baseline_fdc = Path(current_fdc).resolve(), Path(baseline_fdc).resolve()
    require(current_fdc != baseline_fdc and current_fdc.name == 'hdmi-camera-fisheye-tile8df8-internal.fdc' and
            baseline_fdc.name == 'hdmi-camera-fisheye-tile8-internal.fdc', 'current and baseline FDC roles differ')
    require(sha(current_fdc) == sha(baseline_fdc) == BASELINE_FDC_SHA256,
            'share-pin FDC source bytes changed')
    current = {body for rows in actual.values() for body in rows if warning_code(body) == 'ConstraintEditor-4040'}
    old = {body for body in baseline['BodyClasses'] if warning_code(body) == 'ConstraintEditor-4040'}

    def normalize(body, name):
        if body.count(name) == 1:
            return body.replace(name, '@SAME_BYTE_FDC@')
        # The mapper also emits share-pin bodies against its generated PCF.
        # These receive no filename/line/port/location normalization: their
        # complete bodies must remain exactly equal to the existing baseline.
        require(re.fullmatch(r'W: ConstraintEditor-4040: \[@BUILD@/device_map/hdmi_camera_fisheye_top\.pcf'
                r'\(line number: [1-9][0-9]*\)\] Port [^\r\n]+ has been placed at location [^\s,]+, '
                r'whose type is share pin\.', body) is not None,
                'share-pin diagnostic names an unexpected FDC/PCF source')
        return body

    require({normalize(body, current_fdc.name) for body in current} ==
            {normalize(body, baseline_fdc.name) for body in old},
            'share-pin diagnostic bodies changed beyond the equal-byte FDC filename')
    return {'CurrentFDC': ref(current_fdc), 'BaselineFDC': ref(baseline_fdc),
            'SourceBytesEqual': True, 'BodiesDifferOnlyByEqualByteFilename': True,
            'ActualUniqueBodies': len(current), 'BaselineUniqueBodies': len(old),
            'GeneratedPCFBodiesComparedWithoutAnyNormalization': True,
            'GeneratedPCFUniqueBodies': sum('/device_map/hdmi_camera_fisheye_top.pcf(' in body for body in current),
            'NativeElectricalAcceptanceConferred': False}


def critical_diagnostics(diagnostics, native_prefix, reductions):
    require(tuple(tuple(row) for row in reductions) == EXPECTED_REDUCTIONS,
            'only the five unchanged counter reductions are allowed')
    require(type(native_prefix) is str and native_prefix.endswith('/build-a'), 'actual current native build prefix required')
    expected_bodies = [f'C: Sdm-3003: [{native_prefix}/compiled/{source}(line number: {line})] '
                       f'Reduce accumulator {name} size from {old} to {new}. '
                       'If this is not intended behavior, please drive ' + name + ' with valid values.'
                       for source, line, name, old, new in reductions]
    expected = Counter(log + ': ' + body for log in DIAGNOSTIC_LOGS for body in expected_bodies)
    require(Counter(diagnostics) == expected, 'unknown/missing/different critical reduction diagnostic')
    return {'DistinctReductionBodies': expected_bodies, 'ExactLogMultiplicity': dict(expected),
            'FiveReductionSourceSpecs': [list(row) for row in reductions],
            'CompilerDiagnosticsCleared': False, 'ProtectedVendorIndependentRangeProofClaimed': False}


def select_simulations(baseline, current_system, expected_system_path):
    simulations = baseline['Simulations']
    require(set(simulations) == {'MapperSimulation', 'SystemSmallSimulation', 'IOSimulation'},
            'exact baseline simulation roles required')
    require(set(current_system) == {'Path', 'SHA256'} and
            Path(current_system['Path']).resolve() == Path(expected_system_path).resolve() and
            Path(current_system['Path']).resolve() != Path(simulations['SystemSmallSimulation']['Path']).resolve(),
            'SystemSmallSimulation must be this new df8 runner result')
    return {'MapperSimulation': dict(simulations['MapperSimulation']),
            'SystemSmallSimulation': dict(current_system), 'IOSimulation': dict(simulations['IOSimulation'])}


def saved_cache_source_bindings(facts, source_inputs):
    """Bind saved unit/collision evidence for identical cache bytes, not STA."""
    contract = facts['DirectFillCacheSourceContract']
    require(contract['SourceSHA256'] == CACHE_SOURCE_SHA256 and
            contract['CompletedUnitReceipt'] == ref(UNIT_RECEIPT) and
            sha(UNIT_RECEIPT) == UNIT_RECEIPT_SHA256,
            'saved cache unit must remain the real unchanged-source INDEX9 work evidence')
    require(any(Path(path).resolve() == UNIT_RECEIPT.resolve() and digest == UNIT_RECEIPT_SHA256
                for path, digest in source_inputs.items()), 'source helper did not bind its actual unit receipt')
    require(sha(COLLISION_RECEIPT) == COLLISION_RECEIPT_SHA256,
            'saved collision receipt SHA changed')
    receipt = json.loads(COLLISION_RECEIPT.read_text(encoding='utf-8'))
    require(receipt.get('Schema') == 'tile8-directfill-independent-peer-commit-collision-v1' and
            receipt.get('Passed') is True and receipt.get('InputDrift') == [] and
            receipt.get('HDLSimulationExecuted') is True and receipt.get('PDSAccessed') is False and
            receipt.get('HardwareAccessed') is False and receipt.get('NativeRAMMappingOrTimingAccepted') is False,
            'saved collision evidence is incomplete, drifted or overclaims native acceptance')
    expected_summary = {'Passed': True, 'IndexBits': 9, 'Cases': 4, 'SuccessfulCommonResetRecoveries': 4,
        'IndependentRAMPixelsChecked': 864, 'NinthRAndLastCommitCollision': True, 'MalformedFinalRID': True,
        'MissingFinalRLAST': True, 'ResetBeforeFinalRAMCommit': True, 'FaultQuarantineChecked': True}
    require(receipt['Summary'] == expected_summary, 'saved collision fault/reset/RAM coverage differs')
    inputs = {str(COLLISION_RECEIPT.resolve()): COLLISION_RECEIPT_SHA256}
    cache_path = ROOT / 'rtl/experimental/ddr_neighbour_cache_scatter16_rowpipe_directfill.v'
    require(any(Path(path).resolve() == cache_path.resolve() and digest == CACHE_SOURCE_SHA256
                for path, digest in receipt['SourceSHA256'].items()), 'collision source is not the unchanged cache')
    for path, digest in receipt['SourceSHA256'].items():
        require(sha(path) == digest, 'saved collision source drift: ' + path)
        inputs[str(Path(path).resolve())] = digest
    for name, digest in receipt['ArtifactsSHA256'].items():
        path = (COLLISION_RECEIPT.parent / name).resolve()
        require(path.is_relative_to(COLLISION_RECEIPT.parent.resolve()) and sha(path) == digest,
                'saved collision artifact escaped or changed: ' + name)
        inputs[str(path)] = digest
    summary_path = COLLISION_RECEIPT.parent / 'peer-commit-summary.json'
    require(json.loads(summary_path.read_text(encoding='utf-8')) == expected_summary,
            'saved collision summary differs from actual artifact')
    log_path = COLLISION_RECEIPT.parent / 'simulation.log'
    text = log_path.read_text(encoding='utf-8', errors='strict')
    require('PASS DIRECTFILL PEER real final-commit/fault/reset collisions and independent RAM/pixel oracle' in text and
            '$finish called' in text and not re.search(r'(?im)^\s*(?:fatal|error):', text),
            'saved collision RTL completion marker absent')
    require(str(summary_path.resolve()) in inputs and str(log_path.resolve()) in inputs,
            'saved collision summary/log artifacts are not hash bound')
    return {'UnitReceipt': ref(UNIT_RECEIPT), 'CollisionReceipt': ref(COLLISION_RECEIPT),
            'SourceSHA256': CACHE_SOURCE_SHA256, 'ActualEvidenceWork': str(CACHE_EVIDENCE_WORK.resolve()),
            'Scope': 'Finite unchanged-cache source/protocol/reset evidence only; unit includes INDEX8; collision used INDEX9.',
            'CollisionCases': expected_summary, 'INDEX9NativeMappingOrTimingInherited': False,
            'INDEX8NativeTimingAccepted': False, 'HardwareReleaseAllowed': False}, inputs


def derive_draft(provider=None):
    """Read/rederive completed actual facts without writing an inventory."""
    if provider is None:
        sys.path[:0] = [str(ROOT / 'tools'), str(ROOT.parent / '.venv/Lib/site-packages')]
        provider = importlib.import_module('hdmi_camera_fisheye_tile8df8_warnings')
    w = provider
    require(Path(w.__file__).resolve() == ROOT / 'tools/hdmi_camera_fisheye_tile8df8_warnings.py' and
            w.build.WORK.resolve() == WORK and w.build.TARGET == 'hdmi_camera_fisheye_top',
            'exact current df8 warning/build provider required')
    build_work = WORK / 'build-a'
    plan_path = build_work / 'plan.json'
    receipt_path = build_work / 'execution-result.json'
    plan = w.build.validate(plan_path)
    receipt = w.build.verify_execution(receipt_path)
    require(receipt['BuildCompleted'] is True and receipt['NativeErrors'] == [] and receipt['InputDrift'] == [],
            'actual completed clean build required before warning draft')
    watched = {}

    def add(path, expected=None):
        return w.add(watched, path, expected)

    add(BASELINE_INVENTORY, BASELINE_SHA256)
    baseline = w.read(BASELINE_INVENTORY)
    require(baseline['Schema'] == 'hdmi-camera-fisheye-tile8-warning-inventory-v1' and
            baseline['Target'] == w.build.TARGET, 'current 15FPS tile8 baseline required for comparison only')
    actual = w.warning_inventory(build_work, plan)
    difference = warning_difference(actual, baseline, w.body_class)
    sharepins = sharepin_review(actual, baseline, ROOT / w.build.FDC, BASELINE_FDC)
    for record in (sharepins['CurrentFDC'], sharepins['BaselineFDC']):
        add(record['Path'], record['SHA256'])
    native_prefix = w.build.paths.alias_path(w.build.ROOT, plan['RepoAlias'], build_work)
    critical = critical_diagnostics(receipt['Diagnostics'], native_prefix, w.REDUCTIONS)
    compile_text = (build_work / 'compile/run.log').read_text(encoding='gb18030', errors='strict')
    blocks = w.parameters(compile_text)
    wanted = {w.build.TARGET: {'INPUT_TIMING_CONFIGURED': 1, 'RX_VS_ACTIVE_LEVEL': 1, 'RX_DE_ACTIVE_LEVEL': 1,
              'CFG_SETTLE_CYCLES': 2700000, 'PCLK_STALE_REF_CYCLES': 2700000},
              w.build.TARGET + '/hdmi_configuration': {'CLK_FRE': 10000000, 'IIC_FREQ': 400000, 'TIMEOUT_CYCLES': 100000},
              w.build.TARGET + '/hdmi_configuration/driver': {'CLK_FRE': 10000000, 'IIC_FREQ': 400000, 'T_WR': 1,
              'ADDR_BYTE': 2, 'LEN_WIDTH': 3, 'DATA_BYTE': 1, 'TIMEOUT_CYCLES': 100000}}
    require(all(w.integer_parameters(blocks.get(name, [])) == expected for name, expected in wanted.items()),
            'actual readable counter parameter values changed')
    source_counters = {}
    for name, spec in w.PUBLIC.items():
        binding = w.source_binding(plan, build_work, spec['Source'], watched)
        contract = w.counter_contract((build_work / 'compiled' / spec['Source']).read_text(encoding='utf-8-sig'), name)
        source_counters[name] = {'SourceBinding': binding, 'GuardAndAllUses': contract,
                                 'Range': w.enumerate_bound(spec['Maximum'], spec['Old'], spec['New'])}
    vendor, protected = w.vendor_basis(plan, build_work, blocks, compile_text, watched)
    require(vendor['ParameterBlockCount'] == 121 and vendor['ParameterBlockSHA256'] == DDR_PARAMETERS_SHA256 and
            vendor['EveryVendorOriginalAndCompiledByteMatchesCheckedManifest'] is True,
            'actual vendor source or elaborated parameters changed')
    facts, source_inputs = w.source_facts(build_work, plan)
    require(facts['DirectFillCacheSourceContract']['SourceSHA256'] == CACHE_SOURCE_SHA256,
            'actual direct-fill source facts absent')
    for path, digest in source_inputs.items():
        add(path, digest)
    cache_evidence, cache_inputs = saved_cache_source_bindings(facts, source_inputs)
    for path, digest in cache_inputs.items():
        add(path, digest)
    current_small = WORK / 'system-small-a/simulation.json'
    simulations = select_simulations(baseline, ref(current_small), current_small)
    simulation_facts = w.bind_simulation_receipts({'Simulations': simulations}, plan, watched)
    for group in ('InputSHA256', 'PreparedSHA256'):
        for path, digest in plan[group].items():
            add(path, digest)
    for name, digest in receipt['NativeLogSHA256'].items():
        add(build_work / name, digest)
    for path in (plan_path, receipt_path, Path(w.__file__).resolve(), Path(w.build.__file__).resolve(),
                 SELF, REVIEW_HELPER, Path(sys.executable).resolve()):
        add(path)
    require(all(sha(name) == digest for name, digest in watched.items()), 'actual warning draft input drift')
    candidate = {'Schema': 'hdmi-camera-fisheye-tile8df8-warning-inventory-v1', 'Target': w.build.TARGET,
                 'BuildPlan': ref(plan_path), 'SourceBuildReceipt': ref(receipt_path),
                 'CompiledSources': [{key: row[key] for key in ('Source', 'OriginalSHA256', 'CompiledSHA256')}
                                     for row in plan['CompiledInputs']],
                 'WarningBodiesByLog': actual, 'BodyClasses': difference['ProposedBodyClasses'],
                 'UniqueBodies': difference['ActualUniqueBodies'], 'Counts': difference['ActualCountsByCode'],
                 'SourceFacts': facts, 'Simulations': simulations}
    draft = {'Schema': DRAFT_SCHEMA, 'DraftComplete': True, 'Passed': False,
             'RootReviewRequired': True, 'FinalInventoryWritten': False, 'Target': w.build.TARGET,
             'BuildPlan': ref(plan_path), 'SourceBuildReceipt': ref(receipt_path),
             'PriorInventoryForDifferenceOnly': ref(BASELINE_INVENTORY), 'DifferenceFrom15FPSTile8': difference,
             'SharePinSourceComparison': sharepins, 'ExactFiveCounterReductions': critical,
             'ReadableCounterSourceChecks': source_counters, 'ActualReadableParameters': wanted,
              'UnchangedCacheSourceEvidence': cache_evidence,
             'UnchangedVendorSourceAndParameters': vendor, 'ProtectedVendorCompilerFacts': protected,
             'ActualSourceSimulationBindings': simulation_facts, 'ProposedInventory': candidate,
             'UnknownWarningBodies': difference['UnknownWarningBodies'],
             'NewBodiesRequireExplicitRootReview': True, 'PriorCompilerOrTimingAcceptanceInherited': False,
             'SourceDiagnosticReviewPassed': False, 'UnknownWarningsAccepted': False,
             'TimingAccepted': False, 'NativeEquivalent': False, 'CDCAccepted': False,
             'HardwareReleaseAllowed': False, 'HardwareAccessed': False, 'EDAExecuted': False,
             'InputSHA256': dict(sorted(watched.items()))}
    return draft, watched


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=WORK / 'source-warning-inventory-draft-a.json')
    args = parser.parse_args(argv)
    target = args.output.resolve()
    require(target.parent == WORK and target.name.startswith('source-warning-inventory-draft-') and
            target.suffix == '.json' and not target.exists(), 'fresh root-review draft filename required')
    require(not (WORK / 'source-warning-inventory-a.json').exists(), 'final inventory already exists; no draft overwrite')
    value, _ = derive_draft()
    with target.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps({'DraftWritten': True, 'RootReviewRequired': True, 'Passed': False,
                      'FinalInventoryWritten': False, 'Draft': ref(target),
                      'UniqueBodies': value['ProposedInventory']['UniqueBodies'],
                      'UnknownWarningBodyCount': len(value['UnknownWarningBodies'])}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
