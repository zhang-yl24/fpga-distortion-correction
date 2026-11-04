"""Compare two actual saved v3 UART reviews with the frozen old 15 FPS self-test.

Only saved bytes are read. No public provider, COM, EDA or new measurement is
invoked. A comparison is written only after both real candidate windows pass.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
WORK = REPO / 'distortion/work/hdmi-camera-fisheye-tile8df8-20261103-a'
BASELINE_WORK = WORK.with_name('hdmi-camera-fisheye-tile8-20261103-a')
D_SOURCE = HERE / 'verify_saved_fps_stability_d.py'
D_SHA256 = '1599309e9b8a6e9db305858774d08972ce1b59b794d196393673956a1a1032f9'
E_SOURCE = HERE / 'verify_saved_fps_stability_e.py'
E_SHA256 = 'b27dbad9d57438087de7b02ca752d84383abec759d5dd6da4bba104f8f01d767'
BASELINE_REVIEW = HERE / 'saved-fps-old15fps-selftest-d.json'
BASELINE_REVIEW_SHA256 = '0948d88d17a711cac7aadd6e499d154091e06b47e665e9a802638a99c1f8e236'
BASELINE_BIT_SHA256 = '1236d82f113e1ddb1c5e24502ed1aa03e4758db0a7d6ff17bf9216f0fbd0e4f3'
SOURCE_PINS = {
    'Manifest': '7b2c444b1e6e7d482c1875307fbc7b717689d0f5da9eaf8fac49ef249540a8fb',
    'RootReview': '714242e526fc1a9952cddf3eb9188437f5fed9cb7dc4c1b351077c03b6af150a',
    'Wrapper': 'c8ac2c6b18b7a54cb6890d714f8d2a6f26880fcf5c318c84ba4166292be326a7',
}
PIN_PATHS = {
    'Manifest': WORK / 'physical-release-provider-source-manifest-v3-a.json',
    'RootReview': WORK / 'root-independent-complete-source-review-v3-a.json',
    'Wrapper': WORK / 'release-prewarm-wrapper-source-manifest-v3-a.json',
}
ORIGINAL_PINS = {
    WORK / 'physical-release-provider-source-manifest-a.json':
        '8914c4c46ab950866747400cf1d668f3436720e562f10d76870c4440019fb50d',
    WORK / 'root-independent-complete-source-review-a.json':
        '27e614d3e584d1a8a278254b12fba992462a19a76bda445d54528a70012a9374',
}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def local(path):
    text = str(Path(path).absolute())
    if os.name == 'nt' and not text.startswith('\\\\?\\'):
        text = '\\\\?\\UNC\\' + text[2:] if text.startswith('\\\\') else '\\\\?\\' + text
    return Path(text)


def sha(path):
    digest = hashlib.sha256()
    with local(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def read(path):
    def unique(rows):
        result = {}
        for key, value in rows:
            require(key not in result, 'duplicate JSON key: ' + key)
            result[key] = value
        return result
    return json.loads(local(path).read_text(encoding='utf-8-sig'), object_pairs_hook=unique,
        parse_constant=lambda value: (_ for _ in ()).throw(ValueError('nonfinite JSON: ' + value)))


def digest(value):
    return type(value) is str and re.fullmatch('[0-9a-f]{64}', value) is not None


def same(left, right):
    """Preserve JSON scalar types, including bool versus integer counters."""
    if type(left) is not type(right):
        return False
    if type(left) is dict:
        return left.keys() == right.keys() and all(same(left[k], right[k]) for k in left)
    if type(left) is list:
        return len(left) == len(right) and all(same(a, b) for a, b in zip(left, right))
    return left == right


class Evidence:
    def __init__(self):
        self.inputs = {}

    def add(self, path, expected=None):
        require(type(path) is str or isinstance(path, Path), 'input path required')
        path = Path(path).absolute()
        require(path == path.resolve() and path.drive.upper() != 'P:' and
            not str(path).startswith('\\\\?\\') and local(path).is_file(), 'canonical original input required')
        require(expected is None or digest(expected), 'input SHA256 must be canonical')
        actual = sha(path)
        require(expected is None or actual == expected, 'input byte SHA mismatch: ' + str(path))
        require(str(path) not in self.inputs or self.inputs[str(path)] == actual, 'conflicting input identity')
        self.inputs[str(path)] = actual
        return path

    def mapping(self, values):
        require(type(values) is dict and values, 'complete nonempty saved InputSHA256 required')
        for name, value in values.items():
            require(type(name) is str and Path(name).is_absolute(), 'absolute saved input path required')
            self.add(name, value)

    def ref(self, path):
        path = self.add(path)
        return {'Path': str(path), 'SHA256': self.inputs[str(path)]}

    def bound(self, value):
        require(type(value) is dict and set(value) == {'Path', 'SHA256'}, 'exact Path/SHA256 reference required')
        return self.add(value['Path'], value['SHA256'])

    def unchanged(self):
        return all(sha(path) == value for path, value in self.inputs.items())


def load_analyzers(evidence):
    require(digest(E_SHA256) and all(digest(value) for value in SOURCE_PINS.values()),
        'final e source and v3 pins are pending')
    modules = []
    for name, path, expected in (('compare_v3_saved_wire_d', D_SOURCE, D_SHA256),
            ('compare_v3_saved_identity_e', E_SOURCE, E_SHA256)):
        evidence.add(path, expected)
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        modules.append(module)
    d, e = modules
    require(e.PINS == SOURCE_PINS and e.D_SHA == D_SHA256 and e.analyze is e._d.analyze and
        e.frozen_compatibility is e._d.frozen_compatibility, 'final e pins or immutable d function reuse differs')
    return d


def check_review_metadata(review, seconds, baseline):
    require(type(seconds) is int and seconds in (30, 600), 'explicit acquisition budget required')
    require(review.get('Schema') == ('tile8df8-saved-uart-stability-review-v1' if baseline else
        'tile8df8v3-saved-uart-stability-review-v1') and review.get('Passed') is True,
        'successful exact saved review schema required')
    require(review.get('Role') == ('baseline-selftest' if baseline else 'candidate') and
        review.get('BaselineSelfTestOnly') is baseline and review.get('NewCandidateMeasured') is (not baseline),
        'old baseline and new candidate review roles cannot be interchanged')
    require(all(review.get(name) is False for name in ('HardwareAccessedByVerifier', 'EDAExecuted', 'FrozenSourceModified')),
        'saved review exceeded pure verification scope')
    require(review['Identity'].get('IdentityChainVerified') is True and
        review['WireAnalysis'].get('AcquisitionBudgetSeconds') == seconds,
        'identity chain or acquisition budget differs')


def require_review_input(review, path, expected=None):
    value = review['InputSHA256'].get(str(path))
    require(digest(value) and (expected is None or value == expected), 'review omits exact required input: ' + str(path))
    return value


def identity_from_saved(review, receipt, work, baseline, evidence):
    identity = review['Identity']
    family = 'v2' if baseline else 'v3'
    suffix = 'v2-a' if baseline else 'v3-a'
    expected = {'ProgramReceipt': work / ('program-' + suffix + '/receipt.json'),
        'BitVerification': work / ('bit-' + suffix + '/verification.json'),
        'FinalProof': work / ('final-proof-' + suffix + '.json'),
        'SourceManifest': work / ('physical-release-provider-source-manifest-a.json' if baseline else
            'physical-release-provider-source-manifest-v3-a.json'),
        'ReleaseGO': work / ('physical-to-release-' + family + '-go-a.json'),
        'Prewarm': work / ('release-prewarm-authority-a.json' if baseline else 'release-prewarm-authority-v3-a.json')}
    values = {}
    for name, path in expected.items():
        require(evidence.bound(identity[name]) == path, 'identity names another candidate/attempt: ' + name)
        require_review_input(review, path, identity[name]['SHA256'])
        values[name] = read(path)
    bit = identity['Bitstream']
    bit_path = work / ('bit-' + suffix + '/generate_bitstream/hdmi_camera_fisheye_top.sbit')
    require(Path(bit['Path']) == bit_path and bit['Bytes'] == 3791112 and digest(bit['SHA256']), 'own complete bit identity required')
    evidence.add(bit_path, bit['SHA256'])
    require(local(bit_path).stat().st_size == bit['Bytes'], 'actual bit size changed')
    require_review_input(review, bit_path, bit['SHA256'])
    require((bit['SHA256'] == BASELINE_BIT_SHA256) is baseline, 'baseline binary cannot stand in for new INDEX8')
    program, verified, proof = (values[k] for k in ('ProgramReceipt', 'BitVerification', 'FinalProof'))
    require(same(program['Bitstream'], bit) and same(verified['Bitstream'], bit) and same(receipt['bitstream'], bit),
        'review/measurement/program/verified bit differ')
    require(digest(identity['FinalADFSHA256']) and identity['FinalADFSHA256'] == program['FinalADFSHA256'] ==
        verified['FinalADFSHA256'] == receipt['final_adf_sha256'] == proof['FinalADF']['SHA256'], 'review FinalADF chain differs')
    require(receipt['program_receipt'] == {'path': str(expected['ProgramReceipt']), 'sha256': identity['ProgramReceipt']['SHA256']},
        'measurement names another program event')
    final_adf = evidence.bound(proof['FinalADF'])
    require_review_input(review, final_adf, identity['FinalADFSHA256'])
    if not baseline:
        prefix = 'hdmi-camera-fisheye-tile8df8v3-'
        require(program.get('Schema') == prefix + 'sram-execution-v1' and verified.get('Schema') == prefix +
            'bitstream-verification-v1' and proof.get('Schema') == prefix + 'final-physical-proof-v1', 'actual saved v3 identities required')
        require(identity['SourceManifest'] == {'Path': str(PIN_PATHS['Manifest']), 'SHA256': SOURCE_PINS['Manifest']},
            'review is not bound to the final new v3 source freeze')
        for key, path in PIN_PATHS.items():
            evidence.add(path, SOURCE_PINS[key]); require_review_input(review, path, SOURCE_PINS[key])
        for path, expected_sha in ORIGINAL_PINS.items():
            evidence.add(path, expected_sha); require_review_input(review, path, expected_sha)
    return identity


def recompute_wire(review, receipt, raw, seconds, d, evidence):
    analysis = d.analyze(receipt, raw, seconds)
    require(same(analysis, review['WireAnalysis']), 'recomputed WireAnalysis differs from saved review')
    compatibility = d.frozen_compatibility(receipt, raw, evidence)
    require(same(compatibility, review['FrozenCompatibility']), 'recomputed frozen compatibility differs from saved review')
    return analysis, compatibility


def inspect_review(path, seconds, baseline, d, evidence):
    path = evidence.add(path, BASELINE_REVIEW_SHA256 if baseline else None)
    require(path == BASELINE_REVIEW if baseline else path.parent == HERE, 'saved review outside reviewed output scope')
    review = read(path)
    check_review_metadata(review, seconds, baseline)
    require(str(path) not in review['InputSHA256'], 'saved review cannot include itself')
    evidence.mapping(review['InputSHA256'])
    require_review_input(review, D_SOURCE, D_SHA256)
    if not baseline:
        require_review_input(review, E_SOURCE, E_SHA256)
    work = BASELINE_WORK if baseline else WORK
    measurement = work / ('fps-corrected-v2-a' if baseline else
        'fps-corrected-v3-long-a' if seconds == 600 else 'fps-corrected-v3-a')
    receipt_path, wire = measurement / 'receipt.json', measurement / 'wire.bin'
    receipt = read(evidence.add(receipt_path, require_review_input(review, receipt_path)))
    evidence.add(wire, require_review_input(review, wire))
    require(receipt['wire'] == {'path': str(wire), 'sha256': evidence.inputs[str(wire)]}, 'measurement wire reference differs')
    raw = local(wire).read_bytes()
    analysis, compatibility = recompute_wire(review, receipt, raw, seconds, d, evidence)
    require(d.utc(review['CheckedUTC']) >= d.utc(receipt['ended_utc']), 'saved review predates measurement completion')
    identity = identity_from_saved(review, receipt, work, baseline, evidence)
    return {'Review': evidence.ref(path), 'MeasurementReceipt': evidence.ref(receipt_path), 'Wire': evidence.ref(wire),
        'BaselineSelfTestOnly': baseline, 'Identity': identity, 'WireAnalysis': analysis,
        'FrozenCompatibility': compatibility, 'OriginalWireAndReceiptRecomputed': True}


def window_metrics(analysis):
    mhz = analysis['ObservedCoreMHzFromHostArrival']
    gauges = analysis['LastProcessCycles']
    require(type(mhz) in (int, float) and math.isfinite(mhz) and mhz > 0, 'finite observed clock required')
    return {'AcquisitionBudgetSeconds': analysis['AcquisitionBudgetSeconds'],
        'ActualAcquisitionWallSeconds': analysis['ActualAcquisitionWallSeconds'],
        'HostFirstToLastWindowSeconds': analysis['HostFirstToLastWindowSeconds'],
        'NominalCounterWindowSeconds': analysis['NominalCounterWindowSeconds'],
        'CompleteSamples': analysis['CompleteSamples'],
        'IndependentHostRates': analysis['IndependentHostRates'], 'NominalRates': analysis['NominalRates'],
        'WindowCounterIncrements': analysis['PerAdjacentSampleModulo32Totals'],
        'ObservedCoreMHzFromHostArrival': mhz, 'LastProcessCycles': gauges,
        'ProcessGaugeMSUsingObservedHostClock': {key: value / mhz / 1000 for key, value in gauges.items()},
        'ProcessGaugeMSUsingNominal125MHz': {key: value / 125000 for key, value in gauges.items()},
        'ProcessGaugeIsSampledLastCompletedFrameNotPerFrameLatencyDistribution': True,
        'BlankScanIncrements': analysis['BlankScanIncrements'], 'FaultSamples': analysis['FaultSamples'],
        'SourceMinusCapturedFrames': analysis['SourceMinusCapturedFrames'],
        'SourceMinusCapturedIsAdmissionDifferenceNotInvalidDropCount': True,
        'DroppedOrOverflowFramesObservable': False, 'UnderflowCounterObservable': False}


def compare_metrics(baseline, candidate):
    metric = 'unique_presented_frames_per_second'
    old, new = (item['IndependentHostRates'][metric] for item in (baseline, candidate))
    require(all(type(x) in (int, float) and math.isfinite(x) and x > 0 for x in (old, new)), 'positive real measured unique rates required')
    return {'Baseline': window_metrics(baseline), 'Candidate': window_metrics(candidate),
        'HostUniquePresentedFPSRatio': new / old,
        'HostUniquePresentedFPSImprovementPercent': (new / old - 1) * 100,
        'HostUniquePresentedFPSDifference': new - old,
        'DifferentAcquisitionAndCountingWindowsComparedAsMeasuredRates': True,
        'Target30FPSAsserted': False}


def prepare_comparison(review30, review600):
    evidence = Evidence(); evidence.add(__file__)
    d = load_analyzers(evidence)
    require(Path(review30).resolve() != Path(review600).resolve(), 'two distinct 30/600 reviews required')
    # New evidence is always checked first. Missing new data cannot fall back to the baseline.
    short = inspect_review(review30, 30, False, d, evidence)
    long = inspect_review(review600, 600, False, d, evidence)
    require(same(short['Identity'], long['Identity']), '30/600 reviews must bind the same complete program/bit/ADF/source identity')
    require(short['MeasurementReceipt'] != long['MeasurementReceipt'] and short['Wire'] != long['Wire'],
        '30/600 acquisition records must be distinct')
    baseline = inspect_review(BASELINE_REVIEW, 30, True, d, evidence)
    require(evidence.unchanged(), 'comparison input drift')
    return {'Schema': 'tile8df8v3-vs-published-tile8-saved-wire-comparison-v1', 'Passed': True,
        'CheckedUTC': datetime.now(timezone.utc).isoformat(), 'Candidate': 'tile8df8v3',
        'SourcePins': SOURCE_PINS, 'FrozenDSource': evidence.ref(D_SOURCE), 'FrozenESource': evidence.ref(E_SOURCE),
        'Baseline': baseline, 'Candidate30Seconds': short, 'Candidate600Seconds': long,
        'Comparison30Seconds': compare_metrics(baseline['WireAnalysis'], short['WireAnalysis']),
        'Comparison600Seconds': compare_metrics(baseline['WireAnalysis'], long['WireAnalysis']),
        'InputSHA256': evidence.inputs, 'InputDrift': [], 'Target30FPSAsserted': False,
        'PublicProviderVerificationInvoked': False, 'EDAExecuted': False, 'HardwareAccessed': False,
        'NewMeasurementPerformed': False, 'InputFilesModified': False, 'PhysicalAcceptanceConferred': False,
        'Limits': ['Digital saved UART telemetry only; no optical FPS, latency or visual acceptance.',
            '30/600 seconds are acquisition wall budgets, not full first-to-last counter windows.',
            'Reported process times are sampled last-completed-frame gauges, not end-to-end latency.',
            'HDMI scan, repeated scans and unique presented result IDs remain separate metrics.',
            'Serial CRC rejection is not an image-frame drop counter. No invalid-drop/overflow/live-underflow counter exists.',
            'Host UART/USB arrival timing includes buffering and scheduling uncertainty.',
            'Baseline is the frozen old 30-second-wall self-test only; it is not a ten-minute baseline test.']}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--review-30', required=True, type=Path)
    parser.add_argument('--review-600', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args(argv)
    output = args.output.absolute()
    require(output == output.resolve() and output.parent == HERE and not local(output).exists(),
        'fresh comparison JSON in the isolated output directory required')
    require(output.suffix == '.json', 'comparison output must be JSON')
    value = prepare_comparison(args.review_30, args.review_600)
    with local(output).open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, allow_nan=False); stream.write('\n')
    print(json.dumps({'Passed': True, 'Output': str(output), 'SHA256': sha(output), 'Target30FPSAsserted': False}))


if __name__ == '__main__':
    main()
