"""Independent FAST saved-wire and exact SRAM provenance review; no hardware access."""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
ROOT = REPO / 'distortion'
WORK = ROOT / 'work/hdmi-camera-fisheye-assoc2way256-fastpipe-20261104-a'
D_SOURCE = REPO / 'output/tile8_next15h_20261103/verify_saved_fps_stability_d.py'
D_SHA = '1599309e9b8a6e9db305858774d08972ce1b59b794d196393673956a1a1032f9'
if hashlib.sha256(D_SOURCE.read_bytes()).hexdigest() != D_SHA:
    raise ValueError('immutable independent decoder changed')
spec = importlib.util.spec_from_file_location('fast_saved_wire_original_d', D_SOURCE)
d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d)
require, local, sha, read, utc = d.require, d.local, d.sha, d.read, d.utc
Evidence, program_flags, bit_header = d.Evidence, d.program_flags, d.bit_header
analyze, frozen_compatibility = d.analyze, d.frozen_compatibility
BASELINE_BIT, HZ = d.BASELINE_BIT, d.HZ
OLD_BOARD_BIT = 'aa21991374fbeb4a6733741095f38e27336f1e47dd67b963feb243428a5b353b'

def release_history_state(authority):
    require(authority.get('Schema') == 'fastpipe-saved-firstpass-release-authority-v4' and
            authority.get('FirstPassCompleted') is True and
            authority.get('FullFinalReevaluationSkippedAtUserRequest') is True and
            authority.get('FlashAuthorized') is False, 'exact saved first-pass V4 authority required')
    handoff = authority.get('RootHandoff', {})
    require(handoff.get('UserAuthorizedVolatileSRAM') is True and
            handoff.get('UserNotifiedBeforeExecution') is True,
            'existing user volatile SRAM authorization required')
    return True


def interrupted_identity(observed, launch, ended, proof_ref):
    require(observed.get('Schema') == 'fastpipe-firstpass-proof-root-observation-v4' and
            observed.get('PhysicalProof') == proof_ref and
            all(observed.get(k) is True for k in ('FirstPassCompleted', 'SecondVerificationInterrupted',
                'WorkerAbsent', 'PDSAbsent', 'PDriveReleased', 'UserRequestedSkipRedundantRecomputation',
                'SecondPassSuccessNotClaimed')), 'preserved first pass and actual interrupted second pass required')
    require(type(observed.get('ExitCode')) is int and observed['ExitCode'] == -1 and
            type(ended.get('ExitCode')) is int and ended['ExitCode'] == -1 and
            type(launch.get('PID')) is int and launch['PID'] == 45352 and
            launch['PID'] == ended.get('PID') == observed.get('PID') and
            launch.get('CreationUTC') == ended.get('CreationUTC') == observed.get('CreationUTC') ==
                '2026-11-04T07:36:08.2626237Z' and
            launch.get('ProcessHandleRetained') is True and ended.get('ProcessHandleRetained') is True,
            'actual retained-handle interruption identity differs')
    return True


def witness_identity(witness, authority_ref, request_ref, expected_inputs):
    require(witness.get('Schema') == 'fastpipe-saved-firstpass-closure-sha-witness-v4' and
            witness.get('Authority') == authority_ref and witness.get('Request') == request_ref and
            witness.get('InputSHA256') == expected_inputs and isinstance(expected_inputs, dict) and expected_inputs and
            witness.get('AllSHA256VerifiedOnce') is True and
            witness.get('FullPhysicalOrSimulationRederived') is False,
            'exact initial closure SHA witness required')
    states = witness.get('FileIdentity', {})
    require(isinstance(states, dict) and set(states) == set(expected_inputs), 'witness identities omit closure paths')
    for name, digest in expected_inputs.items():
        require(isinstance(name, str) and Path(name).is_absolute() and str(Path(name).resolve()) == name and
                isinstance(digest, str) and re.fullmatch('[0-9a-f]{64}', digest) and
                isinstance(states[name], list) and len(states[name]) == 4 and
                all(type(n) is int for n in states[name]), 'invalid saved closure identity')
    return states


def saved_firstpass_authority(evidence, authority_path, fp, bitplan, proof):
    authority = read(authority_path)
    release_history_state(authority)
    proof_ref = evidence.ref(fp)
    require(proof_ref['SHA256'] == '4e331eb3b6bf21e12b5f9446e03e477156fefeeeddaeb760ab5eb3224a3b85e0' and
            authority.get('PhysicalProof') == proof_ref, 'exact completed first-pass proof required')
    names = ('PhysicalProof', 'MapperSimulation', 'SystemSimulation', 'IOSimulation', 'Profile')
    selected = authority.get('SelectedReleaseInputs', {})
    require(set(selected) == set(names) and all(selected[k] == bitplan[k] for k in names),
            'selected saved release input scope differs')
    request_path = evidence.add(WORK / 'bit-request-v4-a.json')
    request = read(request_path)
    require(set(request) == {'Schema', 'Target', 'Authority', *names} and
            request.get('Schema') == 'hdmi-camera-fisheye-assoc2way256fastpipev4-bitstream-request-v1' and
            request.get('Target') == 'hdmi_camera_fisheye_top' and
            request['Authority'] == evidence.ref(authority_path) and
            all(request[k] == selected[k] for k in names) and bitplan['Request'] == evidence.ref(request_path),
            'exact V4 request/authority/plan binding differs')
    witness_path = evidence.add(WORK / 'bit-request-v4-a-closure-sha-witness.json')
    witness = read(witness_path)
    require(bitplan['InputSHA256'].get(str(witness_path)) == evidence.ref(witness_path)['SHA256'],
            'bit plan does not bind the actual initial SHA witness')
    expected_inputs = dict(authority['InputSHA256'])
    expected_inputs[str(authority_path)] = evidence.ref(authority_path)['SHA256']
    expected_inputs[str(request_path)] = evidence.ref(request_path)['SHA256']
    require(bitplan.get('SavedAuthority') == evidence.ref(authority_path) and
            bitplan.get('ClosureWitness') == evidence.ref(witness_path) and
            bitplan.get('FullPhysicalOrSimulationRederived') is False and
            bitplan.get('FirstPassReusedAtUserRequest') is True, 'actual bit plan did not use the saved first pass')
    states = witness_identity(witness, evidence.ref(authority_path), evidence.ref(request_path), expected_inputs)
    for name, state in states.items():
        current = local(name).stat()
        require([current.st_size, current.st_mtime_ns, current.st_ctime_ns, current.st_ino] == state,
                'saved checked closure file identity changed: ' + name)
    for mapping in (proof['InputSHA256'], bitplan['InputSHA256']):
        for name, digest in mapping.items():
            if name in authority['InputSHA256']:
                require(authority['InputSHA256'][name] == digest, 'saved hash maps disagree')
    require(all(authority['InputSHA256'].get(name) == digest for name, digest in proof['InputSHA256'].items()),
            'authority omits the saved physical proof input scope')
    # This independent post-run reviewer is not an input to generation.
    # Pin its actual bytes and the immutable decoder in this review's own closure.
    evidence.add(Path(__file__).resolve())
    evidence.add(D_SOURCE, D_SHA)
    for source in (ROOT / 'tools/hdmi_camera_fisheye_assoc2way256_fastpipev4_bitstream.py',
                   ROOT / 'tools/hdmi_camera_fisheye_assoc2way256_fastpipev4_program.py'):
        evidence.add(source, authority['InputSHA256'][str(source)])
    observation_path = evidence.bound(authority['RootObservation'])
    require(observation_path == HERE / 'firstpass-proof-root-observation-v4-a.json', 'exact root observation path required')
    observed = read(observation_path)
    launch_path = evidence.bound(observed['ActualLaunchReceipt'])
    exit_path = evidence.bound(observed['ActualExitReceipt'])
    launch, ended = read(launch_path), read(exit_path)
    interrupted_identity(observed, launch, ended, proof_ref)
    require(ended.get('LaunchReceiptSHA256') == evidence.ref(launch_path)['SHA256'], 'actual interrupted exit/launch hash differs')
    first_path = evidence.bound(observed['FirstPassObservation'])
    stop_path = evidence.bound(observed['OriginalStopObservation'])
    first, stopped = read(first_path), read(stop_path)
    require(first.get('FirstPassProofComplete') is True and first.get('FirstPassProof') == proof_ref and
            stopped.get('FirstPassProof') == proof_ref and stopped.get('ActualExitCode') == -1 and
            stopped.get('SecondPassPassed') is False and stopped.get('SecondPassIntentionallyInterrupted') is True and
            stopped.get('OriginalExitReceiptPreserved') is True and
            stopped.get('ActualLaunchReceipt') == observed['ActualLaunchReceipt'] and
            stopped.get('ActualExitReceipt') == observed['ActualExitReceipt'], 'original stop result was changed')
    return {'FirstPassPhysicalProofReused': True, 'OriginalSecondPassExitCode': -1,
            'SecondPassSuccessClaimed': False, 'ClosureSHAWitness': evidence.ref(witness_path),
            'RootFirstPassObservation': evidence.ref(observation_path),
            'FullClosureRehashedByThisReview': False, 'SavedClosureFileIdentitiesChecked': len(states),
            'PhysicalAndSimulationRederivedByThisReview': False}



def provenance(receipt, evidence, authority_sha):
    work, program_name, bit_name = WORK, 'program-v4-reuse-a', 'bit-v4-a'
    prefix = 'hdmi-camera-fisheye-assoc2way256fastpipev4-'
    program_dir, bit_dir = work / program_name, work / bit_name
    pp, bp, vp, fp = program_dir / 'plan.json', bit_dir / 'bitstream-plan.json', bit_dir / 'verification.json', work / 'final-proof-v2-b.json'
    pr = evidence.add(program_dir / 'receipt.json')
    program, plan, bitplan, verified, proof = read(pr), read(evidence.add(pp)), read(evidence.add(bp)), read(evidence.add(vp)), read(evidence.add(fp))
    program_flags(program)
    require(program.get('Schema') == prefix + 'sram-execution-v1' and plan.get('Schema') == prefix + 'sram-plan-v1' and
            verified.get('Schema') == prefix + 'bitstream-verification-v1' and bitplan.get('Schema') == prefix + 'bitstream-plan-v1' and
            proof.get('Schema') == 'hdmi-camera-fisheye-assoc2way256fastpipev2-final-physical-proof-v1' and
            all(x.get('Target') == 'hdmi_camera_fisheye_top' for x in (program, plan, bitplan, verified, proof)), 'selected candidate identity/schema differs')
    require(program['PlanSHA256'] == sha(pp) and program['ExecutorSHA256'] == sha(ROOT / 'tools/hdmi_camera_fisheye_assoc2way256_fastpipev4_program.py'), 'program plan/executor identity differs')
    evidence.add(ROOT / 'tools/hdmi_camera_fisheye_assoc2way256_fastpipev4_program.py', program['ExecutorSHA256'])
    bit = program['Bitstream']; selected = bit_dir / 'generate_bitstream/hdmi_camera_fisheye_top.sbit'
    require(Path(bit['Path']).resolve() == selected and bit['Bytes'] == 3791112 and
            local(selected).stat().st_size == bit['Bytes'], 'selected bit path/size differs')
    evidence.add(selected, bit['SHA256'])
    require(bit_header(local(selected).read_bytes()) == bit['Header'], 'actual bit header differs from receipt')
    require(bit['SHA256'] not in (BASELINE_BIT, OLD_BOARD_BIT), 'new/old bitstream roles confused')
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
    # The V4 saved authority binds the one completed full-closure SHA pass.
    # Do not repeat the full physical/simulation closure for a saved UART review.
    for source in (Path(__file__).resolve(), ROOT / 'tools/hdmi_camera_fisheye_assoc2way256_fastpipev4_bitstream.py'):
        evidence.add(source)
    for name, digest2 in verified['EvidenceSHA256'].items():
        path = (bit_dir / name).resolve(); require(path.is_relative_to(bit_dir), 'bit artifact escapes selected work'); evidence.add(path, digest2)
    execution = read(bit_dir / 'execution-result.json')
    require(execution.get('ExitCode') == 0 and execution.get('TimedOut') is False and execution.get('InputDrift') == [] and not execution.get('Error'), 'bit execution incomplete')
    require(utc(program['StartedUTC']) >= utc(execution['FinishedUTC']) and utc(program['EndedUTC']) > utc(program['StartedUTC']) and
            utc(receipt['started_utc']) >= utc(program['EndedUTC']), 'program/measurement chronological identity differs')
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
    manifest_path = evidence.add(work / 'release-v4-authority-a.json', authority_sha)
    authority_identity = saved_firstpass_authority(evidence, manifest_path, fp, bitplan, proof)
    return {'ProgramReceipt': evidence.ref(pr), 'Bitstream': bit, 'FinalADF': proof['FinalADF'],
            'SavedFirstPassAuthority': evidence.ref(manifest_path), **authority_identity,
            'ActualJTAGDeviceAndDONELogsVerified': True, 'FlashWritten': False,
            'BitwiseConfigurationReadbackPerformed': False, 'NewPixelAppearanceConfirmedByThisTool': False}

def saved_bit_reuse(evidence, receipt, authority_sha):
    path = evidence.add(WORK / 'saved-verification-program-continuation-v4-b.json')
    claim = read(path)
    helper = WORK / 'run_program_saved_v4_b.py'
    evidence.add(helper, '254167c6d88fbb6ca0a7b7ee1f2bb972a83b5870f374c0fe6f85c0b90664f92a')
    vp = WORK / 'bit-v4-a/verification.json'
    evidence.add(vp, '68ae96b8aedcedc0f01a9ac3fe122b1976a60b3935d36b4ef8e7f434a27caf91')
    require(claim.get('Schema') == 'fastpipe-saved-bit-verification-continuation-v4-b' and
            claim.get('Source') == evidence.ref(helper) and claim.get('SavedVerification') == evidence.ref(vp) and
            claim.get('Authority') == {'Path': str(WORK / 'release-v4-authority-a.json'), 'SHA256': authority_sha} and
            claim.get('ReusedVerification') is True and claim.get('STAReexecuted') is False and
            claim.get('BitstreamRegenerated') is False and claim.get('PreviousWorkerPID') == 24952 and
            claim.get('PreviousWorkerAbsentObserved') is True and
            claim.get('ProgramDirectory') == str(WORK / 'program-v4-reuse-a') and
            claim.get('MeasurementDirectory') == str(WORK / 'fps-corrected-v4-reuse-a') and
            claim.get('OriginalProgramSource') == evidence.ref(ROOT / 'tools/hdmi_camera_fisheye_assoc2way256_fastpipev4_program.py'),
            'exact saved-bit continuation helper identity required')
    lp = evidence.add(HERE / 'release-launch-v4-a.json')
    ep = evidence.add(HERE / 'release-exit-v4-a.json')
    sp = evidence.add(HERE / 'skip-repeated-bit-verification-v4-a.json')
    launch, ended, skipped = read(lp), read(ep), read(sp)
    require(launch.get('Schema') == 'fastpipe-release-launch-v4' and ended.get('Schema') == 'fastpipe-release-exit-v4' and
            launch.get('PID') == ended.get('PID') == skipped.get('PID') == 24952 and
            launch.get('CreationUTC') == ended.get('CreationUTC') == '2026-11-04T09:34:00.0337276Z' and
            type(ended.get('ExitCode')) is int and ended['ExitCode'] == -1 and
            launch.get('ProcessHandleRetained') is True and ended.get('ProcessHandleRetained') is True and
            launch.get('AuthoritySHA256') == ended.get('AuthoritySHA256') == authority_sha and
            ended.get('LaunchReceiptSHA256') == evidence.ref(lp)['SHA256'],
            'original release interrupted exit must remain actual -1')
    require(skipped.get('Schema') == 'fastpipe-skip-repeated-bit-verification-v4-a' and
            skipped.get('UserRequestedSkipDuplicate') is True and skipped.get('HardwareClaimAbsent') is True and
            skipped.get('BitVerificationPath') == str(vp) and skipped.get('BitVerificationSHA256') == evidence.ref(vp)['SHA256'] and
            skipped.get('BitstreamSHA256') == receipt['bitstream']['SHA256'] ==
                'e92cb8d00f11b1d4d1c239bd457fd9095289ac38c9215c9cfcf7e738d7eda26e',
            'exact completed bit reuse and skip request required')
    program = read(WORK / 'program-v4-reuse-a/receipt.json')
    require(utc(claim['CreatedUTC']) <= utc(program['StartedUTC']) and
            utc(ended['ObservedUTC']) < utc(program['StartedUTC']), 'reuse program chronology differs')
    return {'SavedBitVerificationReused': True, 'STAReexecutedForProgramming': False,
            'BitstreamRegeneratedForProgramming': False, 'OriginalReleaseWorkerExitCode': -1,
            'OriginalReleaseWorkerSuccessClaimed': False, 'ProgramContinuation': evidence.ref(path),
            'ProgramContinuationHelper': evidence.ref(helper), 'OriginalReleaseExit': evidence.ref(ep),
            'SkipRepeatedBitVerification': evidence.ref(sp)}



def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--measurement', type=Path, required=True)
    parser.add_argument('--seconds', type=int, choices=(30,600), required=True)
    parser.add_argument('--authority-sha', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    require(not args.output.exists(), 'fresh saved review output required')
    evidence = Evidence()
    evidence.add(Path(__file__))
    evidence.add(D_SOURCE, D_SHA)
    path = evidence.add(args.measurement)
    expected_name = 'fps-corrected-v4-reuse-a' if args.seconds == 30 else 'fps-corrected-v4-reuse-long-a'
    require(path == WORK / expected_name / 'receipt.json', 'exact own V4 measurement required')
    receipt = read(path)
    wire = evidence.add(receipt['wire']['path'], receipt['wire']['sha256'])
    require(wire == path.parent / 'wire.bin', 'exact saved wire identity required')
    identity = provenance(receipt, evidence, args.authority_sha)
    identity.update(saved_bit_reuse(evidence, receipt, args.authority_sha))
    for name, pin in receipt['host_tools'].items():
        evidence.add(name, pin)
    raw = local(wire).read_bytes()
    analysis = analyze(receipt, raw, args.seconds)
    compatibility = frozen_compatibility(receipt, raw, evidence)
    drift = [name for name, h in evidence.inputs.items() if sha(name) != h]
    require(not drift, 'saved board review input drift')
    value = {'Schema':'fastpipe-independent-board-fps-review-v4','Passed':True,
             'FullClosureRehashedByThisReview':False,'FullPhysicalAndSimulationReevaluationPerformed':False,
             'ObservedUTC':datetime.now(timezone.utc).isoformat(),'Identity':identity,
             'Measurement':evidence.ref(path),'Analysis':analysis,'FrozenAnalyzerCrossCheck':compatibility,
             'InputSHA256':evidence.inputs,'InputDrift':[], 'HardwareAccessed':False,
             'TargetFPSNotAssumed':True,'PixelAppearanceNotVerified':True}
    with args.output.open('x',encoding='utf-8') as stream:
        json.dump(value,stream,indent=2,allow_nan=False)
        stream.write('\n')
    print(json.dumps({'Passed':True,'Review':str(args.output),'IndependentHostRates':analysis['IndependentHostRates']}))

if __name__ == '__main__':
    main()
