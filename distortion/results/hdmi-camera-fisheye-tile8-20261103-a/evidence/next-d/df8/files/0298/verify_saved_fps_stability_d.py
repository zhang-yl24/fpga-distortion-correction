"""Pure saved-wire PGHFPS02/identity review. Never opens COM/JTAG or runs EDA."""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import statistics
import struct
import sys
import types
import zlib

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
ROOT = REPO / 'distortion'
PACKET = struct.Struct('<8sBBHIQ14IQII')
MAGIC = b'PGHFPS02'
HZ = 125000000
PROFILE = 0xed59f83e3cfbc77b
BUILD = 0x11030001
U32 = 0xffffffff
COUNTERS = ('source_frames', 'captured_frames', 'processed_frames', 'unique_presented_frames',
            'scan_refreshes', 'last_process_cycles', 'cache_hits', 'cache_misses', 'queries',
            'scan_good_frames', 'scan_repeat_frames', 'scan_blank_frames')
FRAME_COUNTERS = ('source_frames', 'captured_frames', 'processed_frames', 'unique_presented_frames',
                  'scan_refreshes', 'scan_good_frames', 'scan_repeat_frames', 'scan_blank_frames')
LIBRARIES = {
    'hdmi_camera_fisheye_fps.py': '3c44b93436c8420f4fe8194f7d19060caaeae8b6a6ab295402c351fb760734fd',
    'measure_hdmi_fisheye_fps.py': 'deb9da1b02f55deb750baa09c4b4a01675beec5d76c325855d83cd994c389cc5',
}
S3 = ROOT / 'work/hdmi-camera-fisheye-fill8r3s3-20261103-a/verify_live_fps_v2_a.py'
S3_SHA = 'd1ddd2730dd038b6dcb4116444a0973036e2a09bfa3b8f8ed46d622fc6dbf758'
BASELINE_BIT = '1236d82f113e1ddb1c5e24502ed1aa03e4758db0a7d6ff17bf9216f0fbd0e4f3'
ROLES = {
    'candidate': ('tile8df8', '8914c4c46ab950866747400cf1d668f3436720e562f10d76870c4440019fb50d'),
    'baseline-selftest': ('tile8', 'a198f18308b81a11a5b95796b8882330dd2a44469d4acbb815329bbe24301d8c'),
}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def local(path):
    path = Path(path).absolute()
    require(path.drive.upper() != 'P:', 'P drive access forbidden')
    text = str(path)
    prefix = chr(92) * 2 + '?' + chr(92)
    return Path(prefix + text) if os.name == 'nt' and not text.startswith(prefix) else path


def sha(path):
    digest = hashlib.sha256()
    with local(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def read(path):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, 'duplicate JSON key: ' + key)
            result[key] = value
        return result
    return json.loads(local(path).read_text(encoding='utf-8-sig'), object_pairs_hook=pairs,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError('nonfinite JSON ' + value)))


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def utc(value):
    require(type(value) is str, 'UTC timestamp string required')
    result = datetime.fromisoformat(value)
    require(result.tzinfo is not None and result.utcoffset().total_seconds() == 0, 'explicit UTC timestamp required')
    return result


def decode(raw):
    """No resynchronization: every complete saved packet must pass independently."""
    frames, packets = [], []
    count, tail_size = divmod(len(raw), 96)
    for index in range(count):
        packet = raw[index * 96:(index + 1) * 96]
        v = PACKET.unpack(packet)
        require(v[0] == MAGIC and v[1] == 2 and v[2] & ~7 == 0 and v[3] == 96, 'wire framing/version/flags/length differs')
        require(v[18] == 0 and v[19] <= 255, 'reserved field or fault width differs')
        require(v[20] == PROFILE and v[21] == BUILD, 'wire telemetry profile/build identity differs')
        require(zlib.crc32(packet[:92]) == v[22], 'wire CRC32 differs')
        frame = {'sequence': v[4], 'core_ticks': v[5], **dict(zip(COUNTERS, v[6:18])),
                 'status_valid': bool(v[2] & 2), 'failed': bool(v[2] & 1),
                 'corrected_requested': bool(v[2] & 4), 'fault': v[19],
                 'profile_id': f'{v[20]:016x}', 'build_id': f'{v[21]:08x}'}
        frames.append(frame)
        packets.append({'Index': index, 'Offset': index * 96, 'Bytes': 96, 'Sequence': v[4],
                        'CRC32': f'{v[22]:08x}', 'SHA256': hashlib.sha256(packet).hexdigest()})
    tail = raw[count * 96:]
    if tail:
        # Validate every received byte of every known field, even when that
        # field itself is incomplete. Counter payload bytes remain unknown.
        known = [(0, MAGIC), (8, bytes([2])), (10, (96).to_bytes(2, 'little')),
                 (72, bytes(4)), (77, bytes(3)), (80, PROFILE.to_bytes(8, 'little')),
                 (88, BUILD.to_bytes(4, 'little'))]
        if frames:
            next_ticks = frames[-1]['core_ticks'] + HZ
            require(next_ticks < (1 << 64), 'partial packet would wrap/reset core timer')
            known += [(12, ((frames[-1]['sequence'] + 1) & U32).to_bytes(4, 'little')),
                      (16, next_ticks.to_bytes(8, 'little'))]
        for offset, expected in known:
            received = min(len(expected), max(0, len(tail) - offset))
            require(tail[offset:offset + received] == expected[:received], 'partial packet known field prefix differs at offset ' + str(offset))
        if len(tail) >= 10: require(tail[9] & ~7 == 0, 'partial packet flags differ')
        if len(tail) > 92:
            expected_crc = zlib.crc32(tail[:92]).to_bytes(4, 'little')
            require(tail[92:] == expected_crc[:len(tail) - 92], 'partial packet received CRC prefix differs')
    return frames, packets, tail_size


def analyze(receipt, raw, seconds):
    require(type(seconds) is int and seconds in (30, 600), 'explicit 30 or 600 second acquisition budget required')
    require(receipt.get('schema') == 'hdmi-camera-fisheye-host-timed-fps-v1' and receipt.get('passed') is True and
            receipt.get('uart_transmit_bytes') == 0 and receipt.get('port') == 'COM7' and receipt.get('baud') == 115200 and
            not receipt.get('error'), 'successful receive-only saved measurement required')
    elapsed = (utc(receipt['ended_utc']) - utc(receipt['started_utc'])).total_seconds()
    require(seconds - .05 <= elapsed <= seconds + 3, 'actual acquisition wall duration differs from explicit budget')
    frames, packets, tail_size = decode(raw)
    rows = receipt['frames']
    if tail_size >= 10:
        require(raw[len(frames) * 96 + 9] == 6, 'partial packet exposes inactive/failed/non-corrected status')
    if tail_size >= 77:
        require(raw[len(frames) * 96 + 76] == 0, 'partial packet exposes hardware fault')
    require(isinstance(rows, list) and len(rows) == len(frames) and 10 <= len(rows) <= math.ceil(seconds * 1.05) + 3,
            'insufficient or excessive complete samples for acquisition budget')
    for decoded, row in zip(frames, rows):
        require(set(row) == set(decoded) | {'host_elapsed_seconds'}, 'receipt frame field set differs')
        for key, value in decoded.items():
            require(type(row[key]) is type(value) and row[key] == value, 'wire/receipt field differs: ' + key)
        require(finite(row['host_elapsed_seconds']) and row['host_elapsed_seconds'] >= 0, 'invalid host monotonic arrival time')
        require(decoded['status_valid'] and not decoded['failed'] and not decoded['fault'] and decoded['corrected_requested'],
                'inactive/failed/faulted or non-corrected sample')
        require(0 < decoded['last_process_cycles'] <= 2 * HZ, 'last process cycle gauge invalid')
    require(receipt.get('crc_rejected_packets') == 0 and receipt.get('discarded_bytes') == 0, 'reported rejected/discarded wire bytes')
    counters = tuple(k for k in COUNTERS if k != 'last_process_cycles')
    totals = {key: 0 for key in counters}
    intervals = []
    for index, (a, b) in enumerate(zip(rows, rows[1:])):
        require(((b['sequence'] - a['sequence']) & U32) == 1, 'sample sequence gap/reset')
        require(b['core_ticks'] - a['core_ticks'] == HZ, 'core timer reset/gap or non-one-second sample period')
        host_delta = b['host_elapsed_seconds'] - a['host_elapsed_seconds']
        require(host_delta > 0, 'host monotonic arrival stopped/reset')
        delta = {key: (b[key] - a[key]) & U32 for key in counters}
        require(all(delta[key] <= 1000 for key in FRAME_COUNTERS), 'frame counter reset/implausible adjacent delta')
        require(delta['queries'] <= HZ and delta['cache_hits'] <= 4 * HZ and delta['cache_misses'] <= 4 * HZ,
                'cache/query reset or ambiguous adjacent modulo wrap')
        require(delta['scan_blank_frames'] == 0, 'blank scan counter increased')
        require(delta['unique_presented_frames'] <= delta['processed_frames'] + 2 and
                delta['processed_frames'] <= delta['captured_frames'] + 2 and
                delta['captured_frames'] <= delta['source_frames'] + 2, 'frame pipeline conservation differs')
        require(abs(delta['scan_good_frames'] - delta['unique_presented_frames'] - delta['scan_repeat_frames']) <= 2,
                'good/unique/repeat scan conservation differs')
        for key in counters: totals[key] += delta[key]
        intervals.append({'FirstSample': index, 'NominalSeconds': 1, 'HostSeconds': host_delta, 'CounterDelta': delta})
    nominal_window = (rows[-1]['core_ticks'] - rows[0]['core_ticks']) / HZ
    host_window = rows[-1]['host_elapsed_seconds'] - rows[0]['host_elapsed_seconds']
    minimum_host_window = seconds - (5 if seconds == 600 else 2)
    require(minimum_host_window <= host_window <= seconds + 1 and rows[-1]['host_elapsed_seconds'] <= elapsed + .1,
            'host first-to-last counter coverage differs from acquisition wall budget')
    observed_mhz = (rows[-1]['core_ticks'] - rows[0]['core_ticks']) / host_window / 1e6
    require(abs(observed_mhz - 125) / 125 < .03, 'independent host/core clock cross-check outside 3 percent')
    require(totals['processed_frames'] > 0 and totals['unique_presented_frames'] > 0 and totals['scan_refreshes'] > 0,
            'no processing/presentation/HDMI scanning during saved window')
    gauges = [r['last_process_cycles'] for r in rows]
    return {'CompleteSamples': len(rows), 'RawWireBytes': len(raw), 'CompletePacketBytes': len(rows) * 96,
            'TrailingPartialPacketBytes': tail_size, 'TrailingPartialPacketCountedAsComplete': False,
            'TrailingPartialPacketCRCVerified': False if tail_size else None,
            'TrailingPartialReceivedCRCBytesChecked': max(0, tail_size - 92), 'Packets': packets, 'AcquisitionBudgetSeconds': seconds,
            'ActualAcquisitionWallSeconds': elapsed,
            'AcquisitionWallDurationBasis': 'receipt UTC ended-started; configured acquisition uses frozen monotonic loop',
            'MinimumHostFirstToLastWindowSeconds': minimum_host_window, 'NominalCounterWindowSeconds': nominal_window,
            'HostFirstToLastWindowSeconds': host_window, 'AcquisitionWallIsNotCounterWindow': True,
            'ObservedCoreMHzFromHostArrival': observed_mhz, 'ClockCrossCheckWithin3Percent': True,
            'PerAdjacentSampleModulo32Totals': totals,
            'CounterEndpointModulo32': {key: (rows[-1][key] - rows[0][key]) & U32 for key in counters},
            'NominalRates': {key + '_per_second': totals[key] / nominal_window for key in FRAME_COUNTERS},
            'IndependentHostRates': {key + '_per_second': totals[key] / host_window for key in FRAME_COUNTERS},
            'LastProcessCycles': {'First': gauges[0], 'Last': gauges[-1], 'Minimum': min(gauges),
                                  'Maximum': max(gauges), 'Mean': statistics.mean(gauges)},
            'LastProcessMSUsingObservedHostClock': gauges[-1] / observed_mhz / 1000,
            'SourceMinusCapturedFrames': totals['source_frames'] - totals['captured_frames'],
            'CacheMissFractionPerSampleModulo': totals['cache_misses'] / (totals['cache_hits'] + totals['cache_misses']),
            'CacheFillsPerQueryPerSampleModulo': totals['cache_misses'] / totals['queries'] if totals['queries'] else None,
            'Intervals': intervals, 'FaultSamples': 0, 'BlankScanIncrements': 0,
            'DroppedOrOverflowFramesObservable': False, 'UnderflowCounterObservable': False,
            'SourceMinusCapturedIsAdmissionDifferenceNotInvalidDropCount': True,
            'ProtocolWidths': {'PacketBytes': 96, 'SequenceBits': 32, 'CoreTimerBits': 64,
                               'CounterBits': 32, 'ProfileIDBits': 64, 'BuildIDBits': 32, 'CRC32BytesCovered': 92},
            'TargetFPSNotAsserted': True}


class Evidence:
    def __init__(self): self.inputs = {}
    def add(self, path, expected=None):
        path = Path(path).resolve()
        require(expected is None or type(expected) is str and re.fullmatch('[0-9a-f]{64}', expected), 'canonical SHA required')
        key = str(path)
        if key not in self.inputs: self.inputs[key] = sha(path)
        require(expected is None or self.inputs[key] == expected, 'identity SHA mismatch: ' + key)
        return path
    def ref(self, path):
        path = self.add(path)
        return {'Path': str(path), 'SHA256': self.inputs[str(path)]}
    def bound(self, ref):
        require(type(ref) is dict and set(ref) == {'Path', 'SHA256'}, 'exact Path/SHA256 reference required')
        return self.add(ref['Path'], ref['SHA256'])
    def mapping(self, value):
        require(type(value) is dict and value, 'complete nonempty input hash map required')
        for path, digest in value.items(): self.add(path, digest)


def program_flags(value):
    require(all(value.get(k) is True for k in ('Passed', 'DoneConfirmed', 'ExpectedDeviceAndIDConfirmed',
            'HardwareAccessed', 'ProgrammingAttempted', 'UserConfirmedBoardPowered', 'UserNotifiedBeforeExecution')) and
            value.get('FlashWritten') is False and value.get('CleanupErrors') == [] and not value.get('Error'),
            'actual successful volatile SRAM event required')


def bit_header(data):
    require(len(data) == 3791112, 'exact device bitstream size required')
    prefix = bytes.fromhex('00090ff00ff00ff00ff000') + b'PANGO MICROSYSTEMS, INC.\0\1'
    require(data.startswith(prefix), 'native bit prefix differs')
    offset, fields = len(prefix), {}
    for tag, name in zip(b'abcdef', ('Design', 'Device', 'Date', 'Time', 'Generator', 'Version')):
        require(data[offset] == tag, 'bit header tag differs')
        length = int.from_bytes(data[offset + 1:offset + 3], 'big')
        value = data[offset + 3:offset + 3 + length]
        require(length > 0 and len(value) == length and value[-1:] == b'\0' and b'\0' not in value[:-1], 'bit header string invalid')
        fields[name] = value[:-1].decode('ascii'); offset += 3 + length
    require(data[offset:offset + 3] == b'ghi' and fields['Design'] == 'hdmi_camera_fisheye_top' and
            fields['Device'] == 'Logos2-PG2L100H--6-FBG676' and fields['Generator'] == 'Fabric Compiler' and
            fields['Version'] == '2023.2-SP3<154097>', 'bit header identity differs')
    return fields


def release_metadata(variant, bitplan, go, warm):
    prefix = 'hdmi-camera-fisheye-' + variant + 'v2-'
    names = ('PhysicalProof', 'MapperSimulation', 'SystemSimulation', 'IOSimulation', 'Profile')
    require(go.get('Schema') == prefix + 'physical-to-release-go-v1' and
            go.get('ProviderRevision') == variant + 'v2-bounded-b', 'selected own release GO schema/revision differs')
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
    variant, manifest_sha = ROLES[role]
    require(work == (ROOT / ('work/hdmi-camera-fisheye-' + variant + '-20261103-a')).resolve(), 'only selected INDEX8 or explicit old baseline role allowed')
    prefix = 'hdmi-camera-fisheye-' + variant + 'v2-'
    program_dir, bit_dir = work / program_name, work / bit_name
    pp, bp, vp, fp = program_dir / 'plan.json', bit_dir / 'bitstream-plan.json', bit_dir / 'verification.json', work / 'final-proof-v2-a.json'
    pr = evidence.add(program_dir / 'receipt.json')
    program, plan, bitplan, verified, proof = read(pr), read(evidence.add(pp)), read(evidence.add(bp)), read(evidence.add(vp)), read(evidence.add(fp))
    program_flags(program)
    require(program.get('Schema') == prefix + 'sram-execution-v1' and plan.get('Schema') == prefix + 'sram-plan-v1' and
            verified.get('Schema') == prefix + 'bitstream-verification-v1' and bitplan.get('Schema') == prefix + 'bitstream-plan-v1' and
            proof.get('Schema') == prefix + 'final-physical-proof-v1' and
            all(x.get('Target') == 'hdmi_camera_fisheye_top' for x in (program, plan, bitplan, verified, proof)), 'selected candidate identity/schema differs')
    require(program['PlanSHA256'] == sha(pp) and program['ExecutorSHA256'] == sha(ROOT / ('tools/hdmi_camera_fisheye_' + variant + 'v2_program.py')), 'program plan/executor identity differs')
    evidence.add(ROOT / ('tools/hdmi_camera_fisheye_' + variant + 'v2_program.py'), program['ExecutorSHA256'])
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
    manifest_path = evidence.add(work / 'physical-release-provider-source-manifest-a.json', manifest_sha)
    manifest = read(manifest_path)
    require(manifest.get('Passed') is True and manifest.get('InputDrift') == [] and manifest.get('PriorPhysicalTimingOrAcceptanceInherited') is False,
            'frozen selected source manifest incomplete')
    evidence.mapping(manifest['InputSHA256'])
    if role == 'candidate':
        review_path = evidence.add(work / 'root-independent-complete-source-review-a.json', '27e614d3e584d1a8a278254b12fba992462a19a76bda445d54528a70012a9374')
        review = read(review_path)
        require(review.get('Passed') is True and review.get('IndependentPeerReviewPerformed') is True and review.get('InputDrift') == [], 'selected root source review missing')
        evidence.mapping(review['InputSHA256'])
    go_path, warm_path = work / 'physical-to-release-v2-go-a.json', work / 'release-prewarm-authority-a.json'
    go, warm = read(evidence.add(go_path)), read(evidence.add(warm_path))
    require(all(go.get(k) is True for k in ('PriorWorkerEnded', 'PDriveReleased', 'UserAuthorizedVolatileSRAM', 'UserNotifiedBeforeExecution')) and
            go['ProviderSourceManifest'] == evidence.ref(manifest_path) and go['PhysicalProof'] == evidence.ref(fp), 'own release GO identity missing')
    require(warm.get('Passed') is True and warm.get('InputDrift') == [] and warm['ProviderSourceManifest'] == evidence.ref(manifest_path) and
            warm['ExactRequest']['PhysicalProof'] == evidence.ref(fp), 'own prewarm identity missing')
    evidence.mapping(warm['WatchedInputSHA256'])
    release_metadata(variant, bitplan, go, warm)
    wrapper_sha = {'candidate': '1dce4ab27f0f4a8150942574376f4af84c0c916fa6033b3a40945922e0c4223b',
                   'baseline-selftest': '6b31463fd5300d97bc3ee923bb0d058a5e20b37caffef1652ece56134c4067de'}[role]
    wrapper = evidence.add(work / 'release-prewarm-wrapper-source-manifest-a.json', wrapper_sha)
    require(warm['ReviewedWrapperManifest'] == evidence.ref(wrapper), 'approved wrapper manifest identity differs')
    require(warm['SelectedBitstreamProvider'] == evidence.ref(ROOT / ('tools/hdmi_camera_fisheye_' + variant + 'v2_bitstream.py')) and
            warm['FrozenReleaseDriver'] == evidence.ref(work / 'run_release_v2_a.py') and
            warm['ActualSelectedFourRoleManifest'] == go['SelectedReleaseInputManifest'] == evidence.ref(work / 'release-input-manifest-v2-a.json'),
            'selected release provider/driver/role manifest differs')
    snapshot = evidence.bound(warm['RequestSnapshot'])
    request_path = evidence.bound(bitplan['Request'])
    require(snapshot == work / 'release-prewarm-bit-request-v2-a.snapshot.json' and
            Path(warm['RequestPath']).resolve() == request_path == work / 'bit-request-v2-a.json' and
            warm['RequestSHA256'] == sha(snapshot) == sha(request_path) and
            local(snapshot).read_bytes() == local(request_path).read_bytes() and read(snapshot) == warm['ExactRequest'],
            'exact real request/snapshot bytes differ')
    transition_path = evidence.add(work / 'release-prewarm-authorized-transition-a.json')
    transition = read(transition_path)
    require(transition.get('Schema') == prefix + 'release-prewarm-authorized-transition-v1' and transition.get('Passed') is True and
            transition['RootReleaseGo'] == evidence.ref(go_path) and transition['PrewarmReceipt'] == evidence.ref(warm_path) and
            transition['ExpectedRealRequestSHA256'] == sha(snapshot) and transition['FrozenReleaseDriver'] == warm['FrozenReleaseDriver'] and
            all(transition.get(k) is True for k in ('ExactFiveRoleReferencesMatch', 'PDriveFree', 'UnchangedMainInvokedInSameInterpreter',
                'FreshRuntimeGateStillRequired')) and transition.get('PrivateCacheAccessed') is False,
            'exact root authorized transition missing')
    comparison = evidence.bound(transition['RequestComparison'])
    require(comparison == work / 'release-prewarm-recreated-request-check-a.json' and
            local(comparison).read_bytes() == local(snapshot).read_bytes(), 'authorized transition request comparison differs')
    return {'Bitstream': bit, 'FinalADFSHA256': digest, 'SourceManifest': evidence.ref(manifest_path),
            'ProgramReceipt': evidence.ref(pr), 'BitVerification': evidence.ref(vp), 'FinalProof': evidence.ref(fp),
            'ReleaseGO': evidence.ref(go_path), 'Prewarm': evidence.ref(warm_path), 'IdentityChainVerified': True}


def frozen_compatibility(receipt, raw, evidence):
    evidence.add(S3, S3_SHA)
    modules = {}
    for filename, expected in LIBRARIES.items():
        path = evidence.add(ROOT / 'tools' / filename, expected)
        module = types.ModuleType(filename[:-3]); module.__file__ = str(path)
        previous = sys.modules.get('hdmi_camera_fisheye_fps')
        if filename.startswith('measure_'): sys.modules['hdmi_camera_fisheye_fps'] = modules['protocol']
        try: exec(compile(local(path).read_bytes(), str(path), 'exec'), module.__dict__)
        finally:
            if filename.startswith('measure_'):
                if previous is None: sys.modules.pop('hdmi_camera_fisheye_fps', None)
                else: sys.modules['hdmi_camera_fisheye_fps'] = previous
        modules['measurement' if filename.startswith('measure_') else 'protocol'] = module
    require(receipt['host_tools'] == {str((ROOT / 'tools' / n).resolve()): h for n, h in LIBRARIES.items()}, 'frozen measurement library identities differ')
    parser = modules['protocol'].Parser(); decoded = parser.feed(raw)
    own, _, tail = decode(raw)
    require(decoded == own and parser.rejected == parser.discarded == 0 and len(parser.buffer) == tail, 'independent decoder differs from frozen protocol')
    require(modules['protocol'].summarize(decoded) == receipt['nominal_clock_summary'] and
            modules['measurement'].arrival_summary(receipt['frames']) == receipt['independent_host_summary'], 'recorded frozen summaries differ')
    return {'FrozenRecordedSummariesVerified': True, 'S3Reparser': evidence.ref(S3),
            'S3ReparseRequiresMinimumSamples': 10, 'S3ReparseAcceptsExplicitMeasurementName': True,
            'S3MainUsesFixedDirectories': True, 'FrozenEndpointModuloCacheSummaryNotUsedForLongWindowTotals': True}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--work', type=Path, required=True)
    ap.add_argument('--measurement-name', required=True)
    ap.add_argument('--wall-seconds', type=int, choices=(30, 600), required=True)
    ap.add_argument('--program-name', default='program-v2-a')
    ap.add_argument('--bit-name', default='bit-v2-a')
    ap.add_argument('--role', choices=tuple(ROLES), default='candidate')
    ap.add_argument('--output', type=Path, required=True)
    a = ap.parse_args(); output = a.output.resolve(); work = a.work.resolve()
    require(output.parent == HERE and not local(output).exists(), 'fresh output filename in this isolated output directory required')
    require(a.measurement_name == ('fps-corrected-v2-long-a' if a.wall_seconds == 600 else 'fps-corrected-v2-a'), 'explicit 30/600 second saved measurement directory differs')
    require(re.fullmatch(r'program-[A-Za-z0-9-]+', a.program_name) and re.fullmatch(r'bit-[A-Za-z0-9-]+', a.bit_name), 'safe explicit program/bit child names required')
    evidence = Evidence(); evidence.add(__file__)
    path, wire = work / a.measurement_name / 'receipt.json', work / a.measurement_name / 'wire.bin'
    receipt = read(evidence.add(path)); evidence.add(wire, receipt['wire']['sha256'])
    require(Path(receipt['wire']['path']).resolve() == wire, 'wire path is outside selected measurement')
    raw = local(wire).read_bytes(); result = analyze(receipt, raw, a.wall_seconds)
    compatibility = frozen_compatibility(receipt, raw, evidence)
    identity = provenance(work, a.program_name, a.bit_name, a.role, receipt, evidence)
    require(all(sha(p) == h for p, h in evidence.inputs.items()), 'input changed during read-only verification')
    value = {'Schema': 'tile8df8-saved-uart-stability-review-v1', 'Passed': True, 'CheckedUTC': datetime.now(timezone.utc).isoformat(),
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
