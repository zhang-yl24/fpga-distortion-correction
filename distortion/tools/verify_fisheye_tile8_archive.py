"""Reparse packaged S3/tile8 UART evidence offline; never access serial/JTAG or EDA."""
from pathlib import Path
import hashlib
import json
import math

from verify_fisheye_fill8_archive import check, read, require


ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / 'distortion/results/hdmi-camera-fisheye-tile8-20261103-a'
EVIDENCE = PACKAGE / 'evidence/release-b'
COUNTERS = ('source_frames', 'captured_frames', 'processed_frames',
            'unique_presented_frames', 'scan_refreshes', 'scan_good_frames',
            'scan_repeat_frames', 'scan_blank_frames')
METRIC = 'unique_presented_frames_per_second'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inspect(label, comparison):
    folder = EVIDENCE if label == 'tile8' else EVIDENCE / 'baseline-S3'
    paths = {'BitVerification': folder / 'bit-verification.json',
             'ProgramReceipt': folder / 'program-receipt.json',
             'FPSReceipt': folder / 'corrected-fps-receipt.json',
             'Wire': folder / 'corrected-wire.bin'}
    bit = (EVIDENCE / 'hdmi_camera_fisheye_top.sbit' if label == 'tile8' else ROOT /
           'distortion/results/hdmi-camera-fisheye-fill8r3s3-20261103-a/artifacts/hdmi_camera_fisheye_top.sbit')
    block = comparison['Candidate' if label == 'tile8' else 'Baseline']
    verified, program, receipt = (read(paths[key]) for key in
                                  ('BitVerification', 'ProgramReceipt', 'FPSReceipt'))
    require(block['Candidate'] == label and block['WireReparsed'] is True and
            block['CorrectedModeThroughout'] is True, label + ' comparison mode differs')
    for role, path in paths.items():
        require(sha(path) == block['Evidence'][role]['SHA256'], label + ' evidence SHA differs: ' + role)
    require(verified.get('Verified') is True and verified['Target'] == program['Target'] == 'hdmi_camera_fisheye_top'
            and verified['Bitstream'] == program['Bitstream'] == receipt['bitstream'] == block['Bitstream']
            and verified['FinalADFSHA256'] == program['FinalADFSHA256'] == receipt['final_adf_sha256']
            == block['FinalADFSHA256'], label + ' bit/ADF identity differs')
    summary, host = check(paths['FPSReceipt'], paths['Wire'], paths['ProgramReceipt'], bit)
    require(summary == block['NominalClockSummary'] and host == block['IndependentHostSummary'],
            label + ' independently reparsed rates differ')
    frames = receipt['frames']
    require(block['SampleCount'] == len(frames) and block['FirstSequence'] == frames[0]['sequence']
            and block['LastSequence'] == frames[-1]['sequence'], label + ' sample identity differs')
    require(block['FirstCounters'] == {key: frames[0][key] for key in COUNTERS}
            and block['LastCounters'] == {key: frames[-1][key] for key in COUNTERS}
            and block['FrameCounterDeltas'] == {key: summary['counter_delta'][key] for key in COUNTERS},
            label + ' frame counter comparison differs')
    totals = {key: sum((b[key] - a[key]) & 0xffffffff for a, b in zip(frames, frames[1:]))
              for key in ('cache_hits', 'cache_misses', 'queries')}
    require(totals == block['PerSampleCacheTotals'] and
            math.isclose(totals['cache_misses'] / (totals['cache_hits'] + totals['cache_misses']),
                         block['PerSampleCacheMissFraction'], rel_tol=1e-12), label + ' cache totals differ')
    return summary, host, program


def main():
    comparison = read(EVIDENCE / 'independent-tile8-vs-S3-comparison.json')
    require(comparison['Schema'] == 'hdmi-camera-fisheye-tile8-vs-s3-saved-fps-comparison-v1'
            and comparison['Passed'] is True and comparison['HardwareAccessedByVerifier'] is False
            and comparison['InputFilesModified'] is False, 'passed saved comparison required')
    # These immutable snapshots document the historical decoder; this portable
    # check uses its already shipped pure saved-byte checks, without its WORK paths.
    require(sha(EVIDENCE / 'source/verify_tile8_vs_s3_fps.py') == comparison['Verifier']['SHA256']
            and sha(EVIDENCE / 'source/S3-verify_live_fps_v2_a.py') == comparison['PreservedReparser']['SHA256'],
            'historical verifier snapshot differs')
    libraries = {Path(record['Path'].replace('\\', '/')).name: record['SHA256']
                 for record in comparison['VerifiedLibraries']}
    require(set(libraries) == {'hdmi_camera_fisheye_fps.py', 'measure_hdmi_fisheye_fps.py'}
            and all(sha(ROOT / 'distortion/tools' / name) == digest for name, digest in libraries.items()),
            'saved decoder library identity differs')
    baseline, baseline_host, _ = inspect('S3', comparison)
    candidate, candidate_host, program = inspect('tile8', comparison)
    nominal_ratio = candidate[METRIC] / baseline[METRIC]
    host_ratio = candidate_host['host_timed_rates'][METRIC] / baseline_host['host_timed_rates'][METRIC]
    for prefix, ratio in (('Nominal', nominal_ratio), ('Host', host_ratio)):
        require(math.isclose(comparison[prefix + 'UniqueFrameRateRatio'], ratio, rel_tol=1e-12)
                and math.isclose(comparison[prefix + 'UniqueFrameRateImprovementPercent'],
                                 (ratio - 1) * 100, rel_tol=1e-12, abs_tol=1e-12),
                prefix + ' comparison ratio differs')
    plan_path = EVIDENCE / 'program/plan.json'
    plan = read(plan_path)
    require(sha(plan_path) == program['PlanSHA256'] and plan['Operation'] == 'volatile_sram_only'
            and plan['FlashWritten'] is False, 'selected SRAM plan identity differs')
    delivery = ROOT / 'delivery/20261103-hdmi-camera-fisheye-tile8'
    manifest = read(delivery / 'delivery-manifest.json')
    require(manifest['Schema'] == 'hdmi-camera-fisheye-tile8-portable-delivery-v1'
            and manifest['SelectedBitstream']['SHA256'] == program['Bitstream']['SHA256']
            and manifest['SelectedBitstream']['FinalADFSHA256'] == program['FinalADFSHA256']
            and manifest['MeasuredCorrectedUniqueFPS'] == candidate[METRIC]
            and manifest['BaselineS3CorrectedUniqueFPS'] == baseline[METRIC]
            and manifest['NominalRateRatio'] == nominal_ratio
            and manifest['SourceManifest']['SHA256'] == sha(delivery / 'source-manifest.json'),
            'delivery claims differ from source/bit/saved telemetry')
    require(sha(ROOT / manifest['PortableResultsManifest']) == manifest['PortableResultsManifestSHA256'],
            'published results inventory differs')
    for record in manifest['DeliveryFiles']:
        name = record['Path']
        require(not Path(name).is_absolute() and '..' not in Path(name).parts
                and ':' not in name and '\\' not in name, 'invalid relative delivery path')
        path = (ROOT / name).resolve()
        require(path.is_relative_to(ROOT) and path.is_file() and path.stat().st_size == record['Bytes']
                and sha(path) == record['SHA256'], 'delivery file bytes differ: ' + name)
    print(json.dumps({'Passed': True, 'BaselineUniqueFPS': baseline[METRIC],
        'CandidateUniqueFPS': candidate[METRIC], 'HostRateRatio': host_ratio,
        'HostImprovementPercent': (host_ratio - 1) * 100,
        'Samples': candidate['sample_count'], 'CounterWindowSeconds': candidate['hardware_window_seconds'],
        'ScanRefreshHz': candidate['scan_refreshes_per_second'], 'FlashWritten': False,
        'HardwareAccessed': False, 'EDAExecuted': False, 'OpticalLatencyMeasured': False}))


if __name__ == '__main__':
    main()
