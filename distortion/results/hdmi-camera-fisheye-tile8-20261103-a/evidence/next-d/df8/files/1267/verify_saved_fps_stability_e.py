"""Read-only v3 release identity review using the immutable d saved-wire analyzer.

No COM/JTAG/EDA access. Exact new v3 pins must be filled only after root freeze.
Original provider, root review and all raw/HDL evidence retain their own bytes.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
ROOT = REPO / 'distortion'
D_SOURCE = HERE / 'verify_saved_fps_stability_d.py'
D_SHA = '1599309e9b8a6e9db305858774d08972ce1b59b794d196393673956a1a1032f9'
if hashlib.sha256(D_SOURCE.read_bytes()).hexdigest() != D_SHA:
    raise ValueError('immutable d wire analyzer changed')
_spec = importlib.util.spec_from_file_location('tile8_saved_uart_d_immutable', D_SOURCE)
_d = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_d)
require, local, sha, read, utc = _d.require, _d.local, _d.sha, _d.read, _d.utc
Evidence, program_flags, bit_header = _d.Evidence, _d.program_flags, _d.bit_header
analyze, frozen_compatibility = _d.analyze, _d.frozen_compatibility
BASELINE_BIT, HZ = _d.BASELINE_BIT, _d.HZ
json = _d.json
PINS = {
    'Manifest': '7b2c444b1e6e7d482c1875307fbc7b717689d0f5da9eaf8fac49ef249540a8fb',
    'RootReview': '714242e526fc1a9952cddf3eb9188437f5fed9cb7dc4c1b351077c03b6af150a',
    'Wrapper': 'c8ac2c6b18b7a54cb6890d714f8d2a6f26880fcf5c318c84ba4166292be326a7',
}
ORIGINAL = {
    'physical-release-provider-source-manifest-a.json': '8914c4c46ab950866747400cf1d668f3436720e562f10d76870c4440019fb50d',
    'root-independent-complete-source-review-a.json': '27e614d3e584d1a8a278254b12fba992462a19a76bda445d54528a70012a9374',
}


def release_metadata(variant, bitplan, go, warm):
    require(variant == 'tile8df8', 'only actual selected v3 family allowed')
    prefix = 'hdmi-camera-fisheye-' + variant + 'v3-'
    names = ('PhysicalProof', 'MapperSimulation', 'SystemSimulation', 'IOSimulation', 'Profile')
    require(go.get('Schema') == prefix + 'physical-to-release-go-v1' and
            go.get('ProviderRevision') == 'tile8df8v3-budget1800-a', 'selected own release GO schema/revision differs')
    require(warm.get('Schema') == prefix + 'release-authority-prewarm-v1' and
            warm.get('RequestExclusiveCreatedByWrapper') is True and warm.get('PublicAuditRequestUseCache') is False and
            warm.get('FreshRuntimeGateStillRequired') is True, 'own exact uncached prewarm required')
    require(all(warm.get(k) is False for k in ('PrivateCacheAccessed', 'ProvidersPatched', 'BitStagePrepared',
            'PDriveCreated', 'EDAExecuted', 'HardwareAccessed', 'ReleaseAuthorizedByPrewarm')), 'prewarm exceeded reviewed read-only scope')
    request = warm['ExactRequest']
    require(set(request) == {'Schema', 'Target', *names} and request['Schema'] == prefix + 'bitstream-request-v1' and
            request['Target'] == 'hdmi_camera_fisheye_top', 'exact seven-field prewarm request required')
    require(all(go[k] == request[k] == bitplan[k] for k in names), 'release GO/prewarm/actual bit-plan five roles differ')


def provenance(work, program_name, bit_name, role, receipt, evidence):
    require(role == 'candidate' and all(type(v) is str and re.fullmatch(r'[0-9a-f]{64}', v) for v in PINS.values()), 'final exact v3 source/review/wrapper pins required')
    variant, manifest_sha = 'tile8df8', PINS['Manifest']
    require(program_name == 'program-v3-a' and bit_name == 'bit-v3-a', 'exact v3 program/bit family required')
    require(work == (ROOT / ('work/hdmi-camera-fisheye-' + variant + '-20261103-a')).resolve(), 'only selected INDEX8 or explicit old baseline role allowed')
    prefix = 'hdmi-camera-fisheye-' + variant + 'v3-'
    program_dir, bit_dir = work / program_name, work / bit_name
    pp, bp, vp, fp = program_dir / 'plan.json', bit_dir / 'bitstream-plan.json', bit_dir / 'verification.json', work / 'final-proof-v3-a.json'
    pr = evidence.add(program_dir / 'receipt.json')
    program, plan, bitplan, verified, proof = read(pr), read(evidence.add(pp)), read(evidence.add(bp)), read(evidence.add(vp)), read(evidence.add(fp))
    program_flags(program)
    require(program.get('Schema') == prefix + 'sram-execution-v1' and plan.get('Schema') == prefix + 'sram-plan-v1' and
            verified.get('Schema') == prefix + 'bitstream-verification-v1' and bitplan.get('Schema') == prefix + 'bitstream-plan-v1' and
            proof.get('Schema') == prefix + 'final-physical-proof-v1' and
            all(x.get('Target') == 'hdmi_camera_fisheye_top' for x in (program, plan, bitplan, verified, proof)), 'selected candidate identity/schema differs')
    require(program['PlanSHA256'] == sha(pp) and program['ExecutorSHA256'] == sha(ROOT / ('tools/hdmi_camera_fisheye_' + variant + 'v3_program.py')), 'program plan/executor identity differs')
    evidence.add(ROOT / ('tools/hdmi_camera_fisheye_' + variant + 'v3_program.py'), program['ExecutorSHA256'])
    bit = program['Bitstream']; selected = bit_dir / 'generate_bitstream/hdmi_camera_fisheye_top.sbit'
    require(Path(bit['Path']).resolve() == selected and bit['Bytes'] == 3791112 and
            local(selected).stat().st_size == bit['Bytes'], 'selected bit path/size differs')
    evidence.add(selected, bit['SHA256'])
    require(bit_header(local(selected).read_bytes()) == bit['Header'], 'actual bit header differs from receipt')
    require((bit['SHA256'] != BASELINE_BIT) if role == 'candidate' else (bit['SHA256'] == BASELINE_BIT), 'new/old bitstream roles confused')
    require(plan['Bitstream'] == verified['Bitstream'] == receipt['bitstream'] == bit and
            Path(plan['BitstreamWorkDirectory']).resolve() == bit_dir and Path(plan['WorkDirectory']).resolve() == program_dir and
            plan['Operation'] == 'volatile_sram_only' and plan['ExpectedDevice'] == 'PG2L100H' and plan['ExpectedDeviceID'] == '0x00602899', 'program/bit/measurement identity differs')
    require(receipt['program_receipt'] == {'path': str(pr), 'sha256': sha(pr)}, 'measurement program receipt binding differs')
    digest = program['FinalADFSHA256']
    require(plan['FinalADFSHA256'] == verified['FinalADFSHA256'] == bitplan['FinalADFSHA256'] == receipt['final_adf_sha256'] == digest,
            'FinalADF identity differs')
    require(bitplan['PhysicalProof'] == evidence.ref(fp) and bitplan['BuildPlan'] == proof['BuildPlan'] == evidence.ref(work / 'build-a/plan.json') and
            bitplan['FinalADF'] == proof['FinalADF'] and bitplan['FinalADF']['SHA256'] == digest, 'proof/build/final ADF links differ')
    evidence.bound(bitplan['FinalADF']); evidence.add(bit_dir / 'audited-final.adf', digest)
    require(verified.get('Verified') is True and all(verified['FreshSTA'].get(k) is True for k in
            ('STAAllTenPassed', 'ClockAndSummaryIdentityPreserved', 'AllExceptionPathsPreserved')), 'bit fresh STA verification incomplete')
    require(proof.get('Passed') is True and all(proof.get(k) is True for k in ('STAAllTenPassed', 'NetlistEquivalent',
            'AllFFPlacementsEquivalent', 'RoutesUnchanged', 'ResetAccepted', 'SourceSamplingIsolatedVerified',
            'NativeWarningsReviewed', 'VendorDDRClockResetAccepted', 'FrameBoundaryViewSelectionAccepted',
            'FisheyeProfileAccepted', 'UserCDCAccepted')), 'complete own final physical acceptance required')
    require(proof['FPSClockBasis']['FrequencyHz'] == HZ and proof['FPSClockBasis']['CurrentGeneratedClockVerified'] is True and
            proof['FPSClockBasis']['PLLParametersVerified'] is True, 'actual constrained core clock proof missing')
    for value, key in ((plan, 'BoundInputSHA256'), (bitplan, 'InputSHA256'), (proof, 'InputSHA256')): evidence.mapping(value[key])
    build = read(work / 'build-a/plan.json'); evidence.mapping(build['InputSHA256']); evidence.mapping(build['PreparedSHA256'])
    for name, digest2 in verified['EvidenceSHA256'].items():
        path = (bit_dir / name).resolve(); require(path.is_relative_to(bit_dir), 'bit artifact escapes selected work'); evidence.add(path, digest2)
    execution = read(bit_dir / 'execution-result.json')
    require(execution.get('ExitCode') == 0 and execution.get('TimedOut') is False and execution.get('InputDrift') == [] and not execution.get('Error'), 'bit execution incomplete')
    require(utc(program['StartedUTC']) >= utc(execution['FinishedUTC']) and utc(program['EndedUTC']) > utc(program['StartedUTC']) and
            utc(receipt['started_utc']) >= utc(program['EndedUTC']), 'program/measurement chronological identity differs')
    require(isinstance(program.get('Logs'), dict) and {'scan.out.log', 'program.out.log'} <= set(program['Logs']),
            'both actual device scan and programming logs must be hash-bound')
    for name, digest2 in program['Logs'].items():
        path = (program_dir / name).resolve(); require(path.is_relative_to(program_dir), 'program log escapes selected work'); evidence.add(path, digest2)
    scan = local(program_dir / 'scan.out.log').read_text(errors='replace')
    output = local(program_dir / 'program.out.log').read_text(errors='replace')
    require(re.findall(r'(?m)^\s*(PG\w+)\s*$', scan) == ['PG2L100H'] and
            [x.lower() for x in re.findall(r'(?im)^\s*The ID value is:\s*(0x[0-9a-f]{8})\s*$', scan)] == ['0x00602899'], 'actual device scan identity differs')
    success = re.search(r'(?m)^Executing : cfg_program\b[^\r\n]* successfully\.\s*$', output)
    require(success is not None, 'actual successful cfg_program log missing')
    after = re.findall(r'(?ms)^Executing : cfg_scan_chain\s*$(.*?)^Executing : cfg_scan_chain successfully\.\s*$', output[success.end():])
    require(len(after) == 1 and re.findall(r'(?m)^\s*(PG\w+)\s*$', after[0]) == ['PG2L100H'] and
            re.findall(r'(?m)^\s*This device configure situation \(done bit\):\s*([01])\s*$', after[0]) == ['1'], 'actual post-program DONE scan differs')
    common = ['cfg_set_tcl_break -flag true', 'cfg_connect -ip 127.0.0.1 -port 65420',
              'cfg_set_cable_property -index 0 -freq 1MHz', 'cfg_scan_chain']
    expected_scripts = {'scan': common + ['cfg_read_device_property -mode 0 -device_index 0', 'cfg_disconnect', 'cfg_close'],
                        'program': common + ['cfg_assign_file -file {' + selected.as_posix() + '} -device_index 0',
                            'cfg_program -device_index 0', 'cfg_scan_chain', 'cfg_read_device_property -mode 3 -device_index 0', 'cfg_disconnect', 'cfg_close']}
    for key, lines in expected_scripts.items():
        path = evidence.bound(plan['Tcl'][key]); require(path == program_dir / (key + '.tcl') and local(path).read_text().splitlines() == lines, 'exact volatile SRAM Tcl differs')
    manifest_path = evidence.add(work / 'physical-release-provider-source-manifest-v3-a.json', manifest_sha)
    manifest = read(manifest_path)
    require(manifest.get('Passed') is True and manifest.get('InputDrift') == [] and manifest.get('PriorPhysicalTimingOrAcceptanceInherited') is False,
            'frozen selected source manifest incomplete')
    evidence.mapping(manifest['InputSHA256'])
    require(manifest.get('Schema') == 'hdmi-camera-fisheye-tile8df8v3-provider-source-manifest-v1' and
            manifest.get('ProviderRevision') == 'tile8df8v3-budget1800-a', 'own complete isolated v3 revision required')
    for name, expected in ORIGINAL.items():
        original_path = evidence.add(work / name, expected)
        original_value = read(original_path)
        require(original_value.get('Passed') is True and original_value.get('InputDrift') == [], 'original source provenance incomplete')
        evidence.mapping(original_value['InputSHA256'])
    require(manifest.get('OriginalProviderManifest') == evidence.ref(work / 'physical-release-provider-source-manifest-a.json') and
            manifest.get('OriginalRootReview') == evidence.ref(work / 'root-independent-complete-source-review-a.json'),
            'v3 original 991-source provenance references differ')

    if role == 'candidate':
        review_path = evidence.add(work / 'root-independent-complete-source-review-v3-a.json', PINS['RootReview'])
        review = read(review_path)
        require(review.get('Passed') is True and review.get('IndependentPeerReviewPerformed') is True and review.get('InputDrift') == [], 'selected root source review missing')
        evidence.mapping(review['InputSHA256'])
    go_path, warm_path = work / 'physical-to-release-v3-go-a.json', work / 'release-prewarm-authority-v3-a.json'
    go, warm = read(evidence.add(go_path)), read(evidence.add(warm_path))
    require(all(go.get(k) is True for k in ('PriorWorkerEnded', 'PDriveReleased', 'UserAuthorizedVolatileSRAM', 'UserNotifiedBeforeExecution')) and
            go['ProviderSourceManifest'] == evidence.ref(manifest_path) and go['PhysicalProof'] == evidence.ref(fp), 'own release GO identity missing')
    require(warm.get('Passed') is True and warm.get('InputDrift') == [] and warm['ProviderSourceManifest'] == evidence.ref(manifest_path) and
            warm['ExactRequest']['PhysicalProof'] == evidence.ref(fp), 'own prewarm identity missing')
    evidence.mapping(warm['WatchedInputSHA256'])
    release_metadata(variant, bitplan, go, warm)
    wrapper_sha = PINS['Wrapper']
    wrapper = evidence.add(work / 'release-prewarm-wrapper-source-manifest-v3-a.json', wrapper_sha)
    require(warm['ReviewedWrapperManifest'] == evidence.ref(wrapper), 'approved wrapper manifest identity differs')
    require(warm['SelectedBitstreamProvider'] == evidence.ref(ROOT / ('tools/hdmi_camera_fisheye_' + variant + 'v3_bitstream.py')) and
            warm['FrozenReleaseDriver'] == evidence.ref(work / 'run_release_v3_a.py') and
            warm['ActualSelectedFourRoleManifest'] == go['SelectedReleaseInputManifest'] == evidence.ref(work / 'release-input-manifest-v3-a.json'),
            'selected release provider/driver/role manifest differs')
    snapshot = evidence.bound(warm['RequestSnapshot'])
    request_path = evidence.bound(bitplan['Request'])
    require(snapshot == work / 'release-prewarm-bit-request-v3-a.snapshot.json' and
            Path(warm['RequestPath']).resolve() == request_path == work / 'bit-request-v3-a.json' and
            warm['RequestSHA256'] == sha(snapshot) == sha(request_path) and
            local(snapshot).read_bytes() == local(request_path).read_bytes() and read(snapshot) == warm['ExactRequest'],
            'exact real request/snapshot bytes differ')
    transition_path = evidence.add(work / 'release-prewarm-authorized-transition-v3-a.json')
    transition = read(transition_path)
    require(transition.get('Schema') == prefix + 'release-prewarm-authorized-transition-v1' and transition.get('Passed') is True and
            transition['RootReleaseGo'] == evidence.ref(go_path) and transition['PrewarmReceipt'] == evidence.ref(warm_path) and
            transition['ExpectedRealRequestSHA256'] == sha(snapshot) and transition['FrozenReleaseDriver'] == warm['FrozenReleaseDriver'] and
            all(transition.get(k) is True for k in ('ExactFiveRoleReferencesMatch', 'PDriveFree', 'UnchangedMainInvokedInSameInterpreter',
                'FreshRuntimeGateStillRequired')) and transition.get('PrivateCacheAccessed') is False,
            'exact root authorized transition missing')
    comparison = evidence.bound(transition['RequestComparison'])
    require(comparison == work / 'release-prewarm-recreated-request-check-v3-a.json' and
            local(comparison).read_bytes() == local(snapshot).read_bytes(), 'authorized transition request comparison differs')
    return {'Bitstream': bit, 'FinalADFSHA256': digest, 'SourceManifest': evidence.ref(manifest_path),
            'ProgramReceipt': evidence.ref(pr), 'BitVerification': evidence.ref(vp), 'FinalProof': evidence.ref(fp),
            'ReleaseGO': evidence.ref(go_path), 'Prewarm': evidence.ref(warm_path), 'IdentityChainVerified': True}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--work', type=Path, required=True)
    ap.add_argument('--measurement-name', required=True)
    ap.add_argument('--wall-seconds', type=int, choices=(30, 600), required=True)
    ap.add_argument('--program-name', default='program-v3-a')
    ap.add_argument('--bit-name', default='bit-v3-a')
    ap.add_argument('--role', choices=('candidate',), default='candidate')
    ap.add_argument('--output', type=Path, required=True)
    a = ap.parse_args(); output = a.output.resolve(); work = a.work.resolve()
    require(output.parent == HERE and not local(output).exists(), 'fresh output filename in this isolated output directory required')
    require(a.measurement_name == ('fps-corrected-v3-long-a' if a.wall_seconds == 600 else 'fps-corrected-v3-a'), 'explicit 30/600 second saved measurement directory differs')
    require(re.fullmatch(r'program-[A-Za-z0-9-]+', a.program_name) and re.fullmatch(r'bit-[A-Za-z0-9-]+', a.bit_name), 'safe explicit program/bit child names required')
    evidence = Evidence(); evidence.add(__file__); evidence.add(D_SOURCE, D_SHA)
    path, wire = work / a.measurement_name / 'receipt.json', work / a.measurement_name / 'wire.bin'
    receipt = read(evidence.add(path)); evidence.add(wire, receipt['wire']['sha256'])
    require(Path(receipt['wire']['path']).resolve() == wire, 'wire path is outside selected measurement')
    raw = local(wire).read_bytes(); result = analyze(receipt, raw, a.wall_seconds)
    compatibility = frozen_compatibility(receipt, raw, evidence)
    identity = provenance(work, a.program_name, a.bit_name, a.role, receipt, evidence)
    require(all(sha(p) == h for p, h in evidence.inputs.items()), 'input changed during read-only verification')
    value = {'Schema': 'tile8df8v3-saved-uart-stability-review-v1', 'Passed': True, 'CheckedUTC': datetime.now(timezone.utc).isoformat(),
             'Role': a.role, 'BaselineSelfTestOnly': a.role == 'baseline-selftest', 'NewCandidateMeasured': a.role == 'candidate',
             'Identity': identity, 'WireAnalysis': result, 'FrozenCompatibility': compatibility, 'InputSHA256': evidence.inputs,
             'HardwareAccessedByVerifier': False, 'EDAExecuted': False, 'FrozenSourceModified': False,
             'Limits': ['Saved digital telemetry only; no optical latency or visual pixel acceptance.',
                        'Receive-only source/bit/program/ADF identity does not perform configuration readback.',
                        'Acquisition wall budget and first-to-last sample counting window are separate.',
                        'Host USB/UART arrival clock cross-check is not frequency-counter calibration.',
                        'Protocol has no independent invalid-drop, overflow or live underflow counter.']}
    with output.open('x', encoding='utf-8') as stream: json.dump(value, stream, indent=2, allow_nan=False); stream.write('\n')
    print(json.dumps({'Passed': True, 'BaselineSelfTestOnly': value['BaselineSelfTestOnly'], 'Output': str(output),
                      'SHA256': sha(output), 'InputFiles': len(evidence.inputs), 'HostWindowSeconds': result['HostFirstToLastWindowSeconds'],
                      'UniquePresentedFPS': result['IndependentHostRates']['unique_presented_frames_per_second']}))


if __name__ == '__main__': main()
