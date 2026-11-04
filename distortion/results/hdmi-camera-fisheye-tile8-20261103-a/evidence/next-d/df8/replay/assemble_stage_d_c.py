"""Assemble an explicit stage D only after complete REAL saved evidence exists.

Default is read-only validation. --write copies approved bytes into a separate
package and writes fresh D manifests. No provider verify(), EDA, hardware, Git
or subprocess is invoked. Saved public-gate evidence is checked, not rerun.
"""
from pathlib import Path, PurePosixPath
from datetime import datetime
from types import ModuleType
import argparse
import ast
import hashlib
import json
import math
import os
import re
import shutil
import sys
try:
    import v3_authority as authority
except ModuleNotFoundError:
    from publication import v3_authority as authority

SELF = Path(__file__).resolve()
PROVIDER_SHA = '7b2c444b1e6e7d482c1875307fbc7b717689d0f5da9eaf8fac49ef249540a8fb'
ROOT_REVIEW_SHA = '714242e526fc1a9952cddf3eb9188437f5fed9cb7dc4c1b351077c03b6af150a'
PORTABLE_SHA = 'df228ebd19c15ab4281f329bfb8c595d22e0595775f238fe24440be9837e319a'
PORTABLE_TEST_SHA = '135df5f4db87c952d60ffeb0e1106c361b21a5db3edf731c2c6d06849bfab40f'
_portable_path = SELF.parent / 'portable_source_contract.py'
if hashlib.sha256(_portable_path.read_bytes()).hexdigest() != PORTABLE_SHA:
    raise ValueError('frozen portable adapter source differs before import')
portable = ModuleType('stage_d_frozen_portable_source_contract'); portable.__file__ = str(_portable_path)
exec(compile(_portable_path.read_bytes(), str(_portable_path), 'exec'), portable.__dict__)
FPS_REVIEWER_NAME = 'verify_saved_fps_stability_d.py'
FPS_REVIEWER_SHA = '1599309e9b8a6e9db305858774d08972ce1b59b794d196393673956a1a1032f9'
WRAPPER_SHA = 'c8ac2c6b18b7a54cb6890d714f8d2a6f26880fcf5c318c84ba4166292be326a7'
AUTHORITY_SHA = '7232f5e3b7e4fed2a50753a729c68049004aaf20b8c7d57dfbcdffcba67b4b8a'
DESTINATION = 'distortion/work/tile8df8-publish-20261104/distortion/results/hdmi-camera-fisheye-tile8-20261103-a'
SCHEMA = 'tile8-next-stage-d-assembly-request-v1'
BASE_C_SHA = 'ab2f88a9ef8fdc53b503ad74403f5869738ff2867c3525f7c2e1141baabfcbcc'
TARGET = 'hdmi_camera_fisheye_top'
MAX_COPY = 4 * 1024 * 1024
ROLES = {'FinalProof', 'BitVerification', 'BitPlan', 'BitExecution', 'PreBitGate',
    'ProgramPlan', 'ProgramReceipt', 'FPS30', 'FPS600', 'ResourceIdentity',
    'ProviderManifest', 'RootSourceReview', 'BuildPlan', 'ProductionManifest',
    'SourceContractReview', 'UnitReceipt', 'CollisionReceipt', 'NormalSmall', 'NormalNative',
    'SustainedSmall', 'SustainedNative', 'WarningsReview', 'WarningsInventory',
    'MapperSimulation', 'IOSimulation', 'Profile', 'ReleaseGO', 'PrewarmAuthority',
    'PrewarmWrapper', 'PrewarmTransition', 'ReleaseInputManifest', 'RequestSnapshot', 'RequestComparison',
    'OriginalProviderManifest', 'OriginalRootSourceReview'}
PHYSICAL_FLAGS = ('Passed', 'STAAllTenPassed', 'NativeWarningsReviewed', 'SourceDiagnosticReviewPassed',
    'NetlistEquivalent', 'AllFFPlacementsEquivalent', 'RoutesUnchanged', 'ResetAccepted',
    'SourceSamplingIsolatedVerified', 'VendorDDRClockResetAccepted', 'FrameBoundaryViewSelectionAccepted',
    'FisheyeProfileAccepted', 'UserCDCAccepted')
GENERATION_FLAGS = ('ActualCommandAfterGateBeforeNativeStart', 'BGRInputAndOutputRolesVerified',
    'BGRHighVoltageVerified', 'NativeBGROmittedDefaultUnused', 'UnusedIOExplicitInTclAndStdout',
    'RuntimeGateWithinExecutionWindow', 'BitArtifactNotOlderThanGate')
EXPECTED_EVENTS = [['Report Timing', 'started'], ['Report Timing', 'done'], ['Runtime gate', 'passed'],
    ['Generate Bitstream', 'started'], ['Generate Bitstream', 'done'], ['Bitstream', 'complete']]
WIRE_LIBRARIES = {'hdmi_camera_fisheye_fps.py': '3c44b93436c8420f4fe8194f7d19060caaeae8b6a6ab295402c351fb760734fd',
    'measure_hdmi_fisheye_fps.py': 'deb9da1b02f55deb750baa09c4b4a01675beec5d76c325855d83cd994c389cc5'}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def local_io(path):
    text = str(Path(path).absolute())
    if os.name == 'nt' and not text.startswith('\\\\?\\'):
        text = '\\\\?\\UNC\\' + text[2:] if text.startswith('\\\\') else '\\\\?\\' + text
    return Path(text)


def sha(path):
    h = hashlib.sha256()
    with local_io(path).open('rb') as stream:
        for data in iter(lambda: stream.read(8 * 1024 * 1024), b''): h.update(data)
    return h.hexdigest()


def read(path):
    def unique(rows):
        result = {}
        for key, value in rows:
            require(key not in result, 'duplicate JSON key')
            result[key] = value
        return result
    return json.loads(local_io(path).read_text(encoding='utf-8-sig'), object_pairs_hook=unique,
        parse_constant=lambda x: (_ for _ in ()).throw(ValueError('nonfinite JSON')))


def reference(path):
    path = Path(path).resolve()
    return {'Path': str(path), 'SHA256': sha(path)}


def canonical(path):
    path = Path(path).absolute()
    require(path == path.resolve() and path.drive.upper() != 'P:' and local_io(path).is_file(),
            'existing canonical source file required; P: aliases are not evidence identities')
    return path


def flags(value, names, description):
    require(all(value.get(name) is True for name in names), description + ' flags incomplete')


def relative(name):
    require(type(name) is str and '\\' not in name and ':' not in name and not any(ord(c) < 32 for c in name),
            'portable POSIX path required')
    path = PurePosixPath(name)
    require(path.parts and not path.is_absolute() and '..' not in path.parts and path.as_posix() == name,
            'escaped or noncanonical relative destination')
    return path


def snapshot(package):
    package = Path(package).resolve()
    result = {}
    for path in sorted(package.rglob('*')):
        if path.is_file():
            require(path.resolve().is_relative_to(package), 'base package symlink escape')
            result[path.relative_to(package).as_posix()] = {'SHA256': sha(path), 'Bytes': path.stat().st_size}
    return result


def verify_base(package):
    package = Path(package).resolve()
    manifest = package / 'portable-evidence-manifest-c.json'
    require(sha(manifest) == BASE_C_SHA, 'actual immutable published C manifest required')
    value = read(manifest); require(value['Schema'] == 'hdmi-camera-fisheye-tile8-portable-archive-v1', 'base schema')
    require(len(value['BundledFiles']) == 449, 'complete published A/B/C boundary required')
    before = snapshot(package)
    for row in value['BundledFiles']:
        name = relative(row['Path']).as_posix()
        require(before.get(name) == {'SHA256': row['SHA256'], 'Bytes': row['Bytes']}, 'published A/B/C byte drift: ' + name)
    require(set(before) == {row['Path'] for row in value['BundledFiles']} | {'portable-evidence-manifest-c.json'},
            'base must be the complete unchanged C package, without unreviewed additions')
    return before


def bit_identity(bit, program, plan, adf):
    require(bit.get('Schema') == 'hdmi-camera-fisheye-tile8df8v3-bitstream-verification-v1' and
            bit.get('Verified') is True and bit.get('Target') == TARGET and
            bit['Bitstream'] == program['Bitstream'] == plan['Bitstream'] and
            bit['FinalADFSHA256'] == program['FinalADFSHA256'] == plan['FinalADFSHA256'] == adf,
            'own final ADF/bit/program identity differs')
    require(bit['ActualEvents'] == EXPECTED_EVENTS, 'real STA/gate/generation events differ')
    flags(bit['FreshSTA'], ('STAAllTenPassed', 'ClockAndSummaryIdentityPreserved', 'AllExceptionPathsPreserved'), 'fresh bit STA')
    flags(bit['GenerationEvidence'], GENERATION_FLAGS, 'actual generation and runtime gate')


def parse_bit_header(data):
    prefix = bytes.fromhex('00090ff00ff00ff00ff000') + b'PANGO MICROSYSTEMS, INC.\0\1'
    require(len(data) == 3791112 and data.startswith(prefix), 'actual native bit length/prefix differs')
    offset, fields = len(prefix), {}
    for tag, name in zip(b'abcdef', ('Design','Device','Date','Time','Generator','Version')):
        require(offset + 3 < len(data) and data[offset] == tag, 'native bit header tag missing')
        count = int.from_bytes(data[offset+1:offset+3], 'big'); value = data[offset+3:offset+3+count]
        require(count > 0 and len(value) == count and value[-1:] == b'\0' and b'\0' not in value[:-1], 'native bit string malformed')
        fields[name] = value[:-1].decode('ascii'); offset += 3 + count
    require(data[offset:offset+3] == b'ghi' and all(fields[k] == v for k,v in {
        'Design':TARGET,'Device':'Logos2-PG2L100H--6-FBG676','Generator':'Fabric Compiler','Version':'2023.2-SP3<154097>'}.items()),
        'actual native bit device/design/generator differs')
    return fields


def check_bit_execution(execution):
    require(execution.get('Schema') == 'hdmi-camera-fisheye-tile8df8v3-bitstream-execution-v1' and
            execution.get('EDAExecuted') is True and execution.get('HardwareAccessed') is False and
            execution.get('ExitCode') == 0 and execution.get('InputDrift') == [] and
            execution.get('TimedOut') is False and execution.get('StoppedForUnexpectedStage') is False and
            execution.get('Cleanup', {}).get('Complete') is True and
            not execution.get('Error') and execution.get('Diagnostics') == [], 'actual bit execution failed')


def replay_compiled(original, changes):
    data = original
    for change in changes:
        if change['Kind'] == 'BoundHeaderIncludeRelocation':
            old, new = change['Original'].encode(), change['Compiled'].encode()
        elif change['Kind'] == 'SelectedDigitalTimingOnly':
            require(change['Parameter'] == 'INPUT_TIMING_CONFIGURED' and change['Original'] == 0 and change['Compiled'] == 1,
                    'unexpected selected timing transformation')
            old, new = b'parameter integer INPUT_TIMING_CONFIGURED=0', b'parameter integer INPUT_TIMING_CONFIGURED=1'
        else: raise ValueError('unknown prepared source transformation')
        require(data.count(old) == change['ReplacementCount'] == 1, 'compiled transformation count differs')
        data = data.replace(old, new)
    return data


def check_saved_cache(root, unit_path, collision_path, peer, add):
    config = portable.CANDIDATES['df8']
    require(unit_path == root / config['UnitWork'] / 'simulation.json' and
            collision_path == root / config['CollisionWork'] / 'simulation.json',
            'INDEX8 cache evidence must retain its actual original WORK9 paths')
    add(unit_path, config['UnitReceiptSHA256'], 'actual original same-source cache unit')
    add(collision_path, config['CollisionReceiptSHA256'], 'actual original same-source final-commit collision')
    add(root / config['Source'], config['SourceSHA256'], 'frozen direct-fill source')
    add(root / config['Baseline'], config['BaselineSHA256'], 'source contract baseline')
    add(root / config['Helper'], config['HelperSHA256'], 'frozen pure source contract')
    require(peer.get('Passed') is True and peer.get('InputDrift') == [] and
            peer['OriginalUnitReceipt'] == reference(unit_path) and peer['IndependentCollisionReceipt'] == reference(collision_path) and
            peer['SourceFacts']['SourceSHA256'] == config['SourceSHA256'] and peer.get('STAInherited') is False,
            'actual completed same-source independent cache review required')
    unit = read(unit_path)
    require(unit.get('Passed') is True and unit.get('InputDrift') == [] and
            set(unit['Cases']) == {'639-i3','1920-i7','1920-i8','1920-i9'}, 'actual complete four-case unit required')
    for name, case in unit['Cases'].items():
        summary = unit_path.parent / ('summary-' + name + '.json')
        trace = unit_path.parent / ('trace-' + name + '.txt')
        add(summary, unit['ArtifactsSHA256'][summary.name], 'actual saved unit summary')
        add(trace, unit['ArtifactsSHA256'][trace.name], 'actual independent pixel stream')
        portable.validate_case(case, read(summary), config)
        checked = portable.validate_trace(local_io(trace).read_text(encoding='utf-8'), case['width'], case['height'])
        require(checked == case['IndependentTrace'], 'actual unit pixel/CRC stream differs')
    collision = read(collision_path)
    require(collision.get('Passed') is True and collision.get('InputDrift') == [] and
            collision['Summary']['Cases'] == 4 and collision['Summary']['IndependentRAMPixelsChecked'] == 864 and
            collision.get('NativeRAMMappingOrTimingAccepted') is False, 'actual independent collision evidence required')
    csv = collision_path.parent / 'peer-commit-cases.csv'
    add(csv, collision['ArtifactsSHA256'][csv.name], 'actual final-commit/fault/reset trace')
    require(local_io(csv).read_text(encoding='utf-8').splitlines() == [
        'case,kind,checked_pixels,fault,last_valid','0,ninth_R_vs_last_commit,128,4,0',
        '1,malformed_final_R,112,3,0','2,malformed_final_R,112,3,0','3,common_reset_vs_last_commit,0,0,0'],
        'actual collision trace differs')


def check_scan_program(scan, programmed):
    require(re.findall(r'(?m)^\s*(PG\w+)\s*$', scan) == ['PG2L100H'] and
            [x.lower() for x in re.findall(r'(?im)^\s*The ID value is:\s*(0x[0-9a-f]{8})\s*$', scan)] == ['0x00602899'],
            'actual SRAM device/ID scan differs')
    success = re.search(r'(?m)^Executing : cfg_program\b[^\r\n]* successfully\.\s*$', programmed)
    require(success is not None, 'actual cfg_program completion missing')
    devices = re.findall(r'(?m)^\s*(PG\w+)\s*$', programmed)
    require(devices and all(d == 'PG2L100H' for d in devices), 'actual programming device differs')
    scans = re.findall(r'(?ms)^Executing : cfg_scan_chain\s*$(.*?)^Executing : cfg_scan_chain successfully\.\s*$', programmed[success.end():])
    require(len(scans) == 1 and re.findall(r'(?m)^\s*(PG\w+)\s*$', scans[0]) == ['PG2L100H'] and
            re.findall(r'(?m)^\s*This device configure situation \(done bit\):\s*([01])\s*$', scans[0]) == ['1'],
            'exact post-program device/DONE scan required')


def native_log(path):
    # Match the public program verifier: ASCII command/device markers are
    # checked while original mixed Windows diagnostic bytes stay SHA-bound.
    return local_io(path).read_text(encoding='utf-8', errors='replace')


def check_resource_identity(resource, bit, proof, proof_ref, program_ref):
    flags(resource, ('ExtractionPassed', 'FinalAttributionPassed', 'OnBoardResourceBinding'), 'actual resource attribution')
    require(resource.get('Schema') == 'tile8-next15h-independent-resource-attribution-v3' and resource.get('Candidate') == 'df8' and
            resource.get('Draft') is False and resource.get('InputDrift') == [], 'only final own resource attribution allowed')
    chain = resource['EvidenceChain']
    require(chain['Bitstream'] == bit['Bitstream'] and chain['FinalADF'] == proof['FinalADF'] and
            chain['FinalPhysicalProof'] == proof_ref and chain['SRAMReceipt'] == program_ref,
            'resource鈫抐inal graph鈫抌it鈫扴RAM identity differs')
    flags(chain, ('PerPrimitiveCountsEquivalent', 'FunctionalGraphAndFFPlacementsIndependentlyEqual',
        'RouteTreesAndPlacementsIndependentlyEqual', 'SavedPublicVerificationChecked',
        'ActualProgramDeviceAndPostProgramDONELogsChecked'), 'saved independently verified resource identity chain')
    require(chain.get('BitVerificationPublicAPIRecomputedByThisTool') is False,
            'resource saved-byte reviewer must disclose no public API recomputation')


def load_wire_libraries(root, add):
    modules = {}
    for filename, expected in WIRE_LIBRARIES.items():
        path = add(root / 'tools' / filename, expected, 'frozen pure saved-wire decoder')
        module = ModuleType(filename[:-3]); module.__file__ = str(path)
        old = sys.modules.get('hdmi_camera_fisheye_fps')
        if filename.startswith('measure_'): sys.modules['hdmi_camera_fisheye_fps'] = modules['protocol']
        try: exec(compile(local_io(path).read_bytes(), str(path), 'exec'), module.__dict__)
        finally:
            if filename.startswith('measure_'):
                if old is None: sys.modules.pop('hdmi_camera_fisheye_fps', None)
                else: sys.modules['hdmi_camera_fisheye_fps'] = old
        modules['measurement' if filename.startswith('measure_') else 'protocol'] = module
    return modules


def load_fps_reviewer(repo, add):
    require(isinstance(FPS_REVIEWER_SHA, str) and len(FPS_REVIEWER_SHA) == 64, 'final strict-prefix FPS reviewer is not frozen')
    path = add(repo / 'output/tile8_next15h_20261103' / FPS_REVIEWER_NAME, FPS_REVIEWER_SHA,
               'frozen pure adjacent-sample modulo32 wire/coverage reviewer')
    module = ModuleType('stage_d_frozen_fps_reviewer'); module.__file__ = str(path)
    exec(compile(local_io(path).read_bytes(), str(path), 'exec'), module.__dict__)
    return module


def reparse_fps(value, wire_bytes, program, minimum_seconds, libraries, reviewer=None):
    require(value.get('schema') == 'hdmi-camera-fisheye-host-timed-fps-v1' and value.get('passed') is True and
            value.get('uart_transmit_bytes') == 0 and value.get('port') == 'COM7' and value.get('baud') == 115200 and
            value['bitstream'] == program['Bitstream'] and value['final_adf_sha256'] == program['FinalADFSHA256'],
            'successful actual own receive-only measurement required')
    elapsed = (datetime.fromisoformat(value['ended_utc']) - datetime.fromisoformat(value['started_utc'])).total_seconds()
    require(elapsed >= minimum_seconds - 0.05, 'actual measurement duration/sample coverage too short')
    require(reviewer is not None, 'frozen adjacent-sample FPS reviewer required')
    analysis = reviewer.analyze(value, wire_bytes, minimum_seconds)
    arrivals = [row['host_elapsed_seconds'] for row in value['frames']]
    require(all(type(x) in (int,float) and math.isfinite(x) and x >= 0 for x in arrivals) and
            all(b > a for a,b in zip(arrivals,arrivals[1:])), 'host arrival sequence is not finite and monotonic')
    require({str(Path(module.__file__).resolve()):sha(module.__file__) for module in libraries.values()} == value['host_tools'],
            'actual measurement did not bind the frozen wire libraries')
    parser = libraries['protocol'].Parser(); frames = parser.feed(wire_bytes)
    require(frames == [{k: v for k, v in row.items() if k != 'host_elapsed_seconds'} for row in value['frames']] and
            parser.rejected == value['crc_rejected_packets'] == 0 and parser.discarded == value['discarded_bytes'] == 0,
            'actual saved wire differs, lost sync or rejected CRC')
    require(all(row['corrected_requested'] and row['status_valid'] and not row['failed'] and not row['fault'] for row in frames) and
            all(((b['sequence'] - a['sequence']) & 0xffffffff) == 1 for a, b in zip(frames, frames[1:])),
            'actual corrected status or sequence differs')
    summary = libraries['protocol'].summarize(frames); host = libraries['measurement'].arrival_summary(value['frames'])
    require(summary == value['nominal_clock_summary'] and host == value['independent_host_summary'] and
            host['clock_cross_check_within_3percent'] is True and summary['counter_delta']['scan_blank_frames'] == 0,
            'independent wire/counter/host clock summary differs')
    require(analysis['TrailingPartialPacketCountedAsComplete'] is False and
            analysis['DroppedOrOverflowFramesObservable'] is False and analysis['UnderflowCounterObservable'] is False,
            'wire reviewer telemetry scope differs')
    return {'AdjacentSampleWireAnalysis': analysis, 'FrozenReceiptSummariesMatch': True,
            'FrozenEndpointCacheTotalsUsedForLongMeasurement': False,
            'SerialParserRejectedPackets': parser.rejected, 'SerialParserDiscardedBytes': parser.discarded,
            'ActualElapsedSeconds': elapsed, 'Samples': len(frames)}


def expected_program_scripts(bit_path):
    name = Path(bit_path).resolve().as_posix()
    require(not any(c in name for c in '{}\r\n'), 'unsafe Tcl bit path')
    common = ['cfg_set_tcl_break -flag true', 'cfg_connect -ip 127.0.0.1 -port 65420',
              'cfg_set_cable_property -index 0 -freq 1MHz', 'cfg_scan_chain']
    return {'scan': common + ['cfg_read_device_property -mode 0 -device_index 0', 'cfg_disconnect', 'cfg_close'],
        'program': common + ['cfg_assign_file -file {' + name + '} -device_index 0', 'cfg_program -device_index 0',
            'cfg_scan_chain', 'cfg_read_device_property -mode 3 -device_index 0', 'cfg_disconnect', 'cfg_close']}


def check_program_identity(plan, program, work, bit_path, executor_sha, bound):
    directory = work / 'program-v3-a'
    require(plan.get('Schema') == 'hdmi-camera-fisheye-tile8df8v3-sram-plan-v1' and
        all(v.get('Target') == TARGET for v in (plan, program)) and
        plan.get('WorkDirectory') == program.get('WorkDirectory') == str(directory) and
        plan.get('BitstreamWorkDirectory') == str(work / 'bit-v3-a'), 'exact SRAM schema/target/work identity required')
    flags(program, ('UserConfirmedBoardPowered', 'UserNotifiedBeforeExecution'), 'actual board power/notification')
    require(not program.get('Error') and program.get('ExecutorSHA256') == executor_sha and
        plan.get('CableIndex') == 0 and plan.get('Frequency') == '1MHz' and plan.get('ServerPort') == 65420 and
        all(plan.get(k) is True for k in ('RequiresExplicitExecute', 'RequiresCurrentSessionBoardPower',
            'UserMustBeNotifiedBeforeExecution')), 'frozen SRAM executor/power/notification/cable differs')
    logs = program.get('Logs')
    required_logs = {'scan.out.log', 'program.out.log'}
    require(type(logs) is dict and required_logs <= set(logs) and
        all(type(logs[name]) is str and re.fullmatch('[0-9a-f]{64}', logs[name]) for name in required_logs),
        'actual scan/program log SHA identities are mandatory')
    for name in sorted(required_logs):
        path = bound({'Path':str(directory / name),'SHA256':logs[name]}, 'actual required SRAM log')
        require(path == directory / name, 'required SRAM log path differs')
    require(set(plan['Tcl']) == {'scan', 'program'}, 'exact SRAM scan/program scripts required')
    for name, expected in expected_program_scripts(bit_path).items():
        path = bound(plan['Tcl'][name], 'exact SRAM script for selected bit')
        require(path == directory / (name + '.tcl') and local_io(path).read_text(encoding='utf-8').splitlines() == expected,
                'exact SRAM Tcl or selected bit path differs')


def check_release_identity(work, paths, data, add, bound, reviewer):
    go, warm, transition = (data[k] for k in ('ReleaseGO', 'PrewarmAuthority', 'PrewarmTransition'))
    role_refs = {name: reference(paths['FinalProof'] if name == 'PhysicalProof' else
        paths['NormalNative'] if name == 'SystemSimulation' else paths[name]) for name in authority.FIVE_ROLES}
    role_refs.update({name: reference(paths[name]) for name in ('ProviderManifest', 'RootSourceReview', 'PrewarmWrapper',
        'ReleaseGO', 'PrewarmAuthority', 'ReleaseInputManifest', 'RequestSnapshot', 'RequestComparison')})
    role_refs['ReleaseDriver'] = reference(work / 'run_release_v3_a.py')
    role_refs['ActualRequest'] = data['BitPlan']['Request']
    authority.check_release_metadata(data['BitPlan'], go, warm, transition, role_refs)
    flags(go, ('PriorWorkerEnded', 'PDriveReleased', 'UserAuthorizedVolatileSRAM', 'UserNotifiedBeforeExecution'), 'release GO')
    require(go['ProviderSourceManifest'] == reference(paths['ProviderManifest']) and
        go['PhysicalProof'] == reference(paths['FinalProof']) and warm.get('Passed') is True and warm.get('InputDrift') == [] and
        warm['ProviderSourceManifest'] == go['ProviderSourceManifest'], 'release GO/prewarm final proof/source identity differs')
    require(sha(paths['PrewarmWrapper']) == WRAPPER_SHA and warm['ReviewedWrapperManifest'] == reference(paths['PrewarmWrapper']),
            'frozen prewarm wrapper identity differs')
    provider = work.parents[1] / 'tools/hdmi_camera_fisheye_tile8df8v3_bitstream.py'
    require(warm['SelectedBitstreamProvider'] == reference(provider) and
        warm['FrozenReleaseDriver'] == reference(work / 'run_release_v3_a.py') and
        warm['ActualSelectedFourRoleManifest'] == go['SelectedReleaseInputManifest'] == reference(paths['ReleaseInputManifest']),
        'release selected provider/driver/four roles differ')
    snapshot, actual = paths['RequestSnapshot'], bound(data['BitPlan']['Request'])
    require(warm['RequestSnapshot'] == reference(snapshot) and Path(warm['RequestPath']).resolve() == actual == work / 'bit-request-v3-a.json' and
        warm['RequestSHA256'] == sha(snapshot) == sha(actual) and local_io(snapshot).read_bytes() == local_io(actual).read_bytes() and
        read(snapshot) == warm['ExactRequest'], 'prewarm real request/snapshot bytes differ')
    require(transition.get('Schema') == 'hdmi-camera-fisheye-tile8df8v3-release-prewarm-authorized-transition-v1' and
        transition.get('Passed') is True and transition['RootReleaseGo'] == reference(paths['ReleaseGO']) and
        transition['PrewarmReceipt'] == reference(paths['PrewarmAuthority']) and transition['ExpectedRealRequestSHA256'] == sha(snapshot) and
        transition['FrozenReleaseDriver'] == warm['FrozenReleaseDriver'] and transition.get('PrivateCacheAccessed') is False,
        'root authorized transition identity differs')
    flags(transition, ('ExactFiveRoleReferencesMatch', 'PDriveFree', 'UnchangedMainInvokedInSameInterpreter',
        'FreshRuntimeGateStillRequired'), 'root authorized transition')
    require(transition['RequestComparison'] == reference(paths['RequestComparison']) and
        local_io(paths['RequestComparison']).read_bytes() == local_io(snapshot).read_bytes(), 'authorized recreated request bytes differ')
    for name, h in warm['WatchedInputSHA256'].items(): add(name, h, 'prewarm exact watched input')
    for value in (go, warm, transition):
        for item in value.values():
            if isinstance(item, dict) and set(item) == {'Path', 'SHA256'}: bound(item, 'saved release authority reference')
    return {'ExactFiveRoleReferencesMatch': True, 'AuthorizedTransitionChecked': True, 'FreshGateStillRequired': True}


def portable_closure(root, add):
    config = portable.CANDIDATES['df8']
    roles = {key: root / config[key] for key in ('Source', 'Baseline', 'Helper', 'HelperTests')}
    roles.update(ProductionManifest=root / 'board/hdmi-camera-fisheye-tile8df8-build-sources.json',
        UnitReceipt=root / config['UnitWork'] / 'simulation.json', CollisionReceipt=root / config['CollisionWork'] / 'simulation.json')
    members = {}
    def member(path, expected=None):
        path = add(path, expected, 'portable finite source/unit/collision replay closure')
        key = portable.windows_identity(str(path))
        require(key not in members or members[key] == str(path), 'portable Windows identity collision')
        members[key] = str(path)
    for name, path in roles.items(): member(path, config[name + 'SHA256'])
    for name, h in read(roles['ProductionManifest'])['SourceSHA256'].items(): member(root / name, h)
    for key in ('UnitReceipt', 'CollisionReceipt'):
        receipt = read(roles[key])
        for name, h in receipt['SourceSHA256'].items(): member(name, h)
        for name, h in receipt['ArtifactsSHA256'].items():
            member(roles[key].parent.joinpath(*portable.relative_artifact(name).parts), h)
    return {name: str(path) for name, path in roles.items()}, set(members.values())


def source_contract_map(roles, members, files):
    rows = {row['Path']: row for row in files}
    require(members <= set(rows), 'portable member missing from archive')
    require(all(rows[name]['Mode'] == 'copy' for name in members), 'portable closure requires actual copied bytes')
    return {'Schema': portable.SCHEMA, 'Candidate': 'df8', 'Roles': roles,
        'Files': [{'OriginalPath': name, 'BundlePath': rows[name]['Destination'],
            'SHA256': rows[name]['SHA256'], 'Bytes': rows[name]['Bytes']} for name in sorted(members)]}


def check_destination(repo, base, destination):
    require(destination == (repo / DESTINATION).resolve(), 'only reviewed new INDEX8 publication worktree archive destination allowed')
    require(base != destination and not destination.is_relative_to(base) and not base.is_relative_to(destination),
            'read-only base and separate destination required')
    for parent in (destination, *destination.parents):
        require(not parent.exists() or parent.is_dir(), 'archive destination ancestor is not a directory')
        require(not parent.is_symlink(), 'archive destination ancestor cannot be a symlink')


def prepare(config_path):
    """Validate complete saved bytes and return an in-memory exclusive-copy plan."""
    config_path = canonical(config_path); request = read(config_path)
    require(set(request) == {'Schema', 'Candidate', 'Repository', 'BasePackage', 'DestinationPackage', 'Roles', 'AdditionalFiles'} and
            request['Schema'] == SCHEMA and request['Candidate'] == 'df8',
            'final selected INDEX8 stage D request required; S4 is failure analysis only')
    candidate = request['Candidate']; repo = Path(request['Repository']).resolve(); root = repo / 'distortion'
    authority.pins_ready()
    require((PROVIDER_SHA, ROOT_REVIEW_SHA, WRAPPER_SHA) ==
            (authority.PROVIDER_SHA256, authority.ROOT_REVIEW_SHA256, authority.WRAPPER_SHA256) and
            isinstance(AUTHORITY_SHA, str) and len(AUTHORITY_SHA) == 64, 'assembler/helper final v3 pins must match')
    work = root / f'work/hdmi-camera-fisheye-tile8{candidate}-20261103-a'
    base, destination = Path(request['BasePackage']).resolve(), Path(request['DestinationPackage']).absolute()
    require(destination == destination.resolve(), 'canonical publication destination required')
    check_destination(repo, base, destination)
    before = verify_base(base)
    required_roles = ROLES
    require(set(request['Roles']) == required_roles, 'all actual final proof/bit/SRAM/30+600s/resource/source roles required')
    watched, files = {}, {}

    def add(path, expected=None, reason='saved exact dependency'):
        path = canonical(path); key = str(path)
        if key not in files:
            digest = sha(path); require(expected is None or digest == expected, 'source SHA drift: ' + key)
            watched[key] = digest
            files[key] = {'Path': key, 'SHA256': digest, 'Bytes': local_io(path).stat().st_size, 'Reason': reason}
        else: require(expected is None or files[key]['SHA256'] == expected, 'conflicting saved source identity')
        return path

    def bound(value, reason='explicit saved role'):
        require(isinstance(value, dict) and set(value) == {'Path', 'SHA256'} and
                re.fullmatch('[0-9a-f]{64}', value['SHA256']) is not None, 'exact Path/SHA reference required')
        return add(value['Path'], value['SHA256'], reason)

    add(config_path, reason='exact archive assembly request')
    authority_path = add(Path(authority.__file__), AUTHORITY_SHA, 'frozen local v3 authority metadata contract')
    paths = {name: bound(value, name) for name, value in request['Roles'].items()}
    data = {name: read(path) for name, path in paths.items()}
    fixed = {'FinalProof': 'final-proof-v3-a.json', 'BuildPlan': 'build-a/plan.json',
        'BitVerification': 'bit-v3-a/verification.json', 'BitPlan': 'bit-v3-a/bitstream-plan.json',
        'BitExecution': 'bit-v3-a/execution-result.json', 'PreBitGate': 'bit-v3-a/pre-bit-audit.json',
        'ProgramPlan': 'program-v3-a/plan.json', 'ProgramReceipt': 'program-v3-a/receipt.json',
        'ProviderManifest': 'physical-release-provider-source-manifest-v3-a.json',
        'RootSourceReview': 'root-independent-complete-source-review-v3-a.json', 'WarningsInventory': 'source-warning-inventory-a.json',
        'ReleaseGO': 'physical-to-release-v3-go-a.json', 'PrewarmAuthority': 'release-prewarm-authority-v3-a.json',
        'PrewarmWrapper': 'release-prewarm-wrapper-source-manifest-v3-a.json', 'PrewarmTransition': 'release-prewarm-authorized-transition-v3-a.json',
        'ReleaseInputManifest': 'release-input-manifest-v3-a.json', 'RequestSnapshot': 'release-prewarm-bit-request-v3-a.snapshot.json',
        'RequestComparison': 'release-prewarm-recreated-request-check-v3-a.json',
        'OriginalProviderManifest': 'physical-release-provider-source-manifest-a.json',
        'OriginalRootSourceReview': 'root-independent-complete-source-review-a.json'}
    require(all(paths[name] == work / suffix for name, suffix in fixed.items()), 'another candidate/attempt role cannot satisfy this archive')
    proof, bit, plan, program = (data[name] for name in ('FinalProof', 'BitVerification', 'ProgramPlan', 'ProgramReceipt'))
    require(proof.get('Schema') == f'hdmi-camera-fisheye-tile8{candidate}v3-final-physical-proof-v1' and proof.get('Target') == TARGET,
            'own final physical proof required')
    flags(proof, PHYSICAL_FLAGS, 'complete saved final proof')
    require(proof.get('NativeMaxPaths') == 10000 and proof['DataCDC']['Missing'] == [] and proof['DataCDC']['Violations'] == [], 'full native/CDC proof core required')
    flags(program, ('Passed', 'DoneConfirmed', 'ExpectedDeviceAndIDConfirmed', 'HardwareAccessed', 'ProgrammingAttempted'), 'actual SRAM')
    require(program.get('Schema') == f'hdmi-camera-fisheye-tile8{candidate}v3-sram-execution-v1' and
            program.get('FlashWritten') is False and program.get('CleanupErrors') == [] and
            plan.get('Operation') == 'volatile_sram_only' and plan.get('FlashWritten') is False,
            'own volatile SRAM-only plan/clean completion required')
    require(program['PlanSHA256'] == sha(paths['ProgramPlan']) and plan['ExpectedDevice'] == 'PG2L100H' and
            plan['ExpectedDeviceID'] == '0x00602899', 'actual SRAM plan/device binding differs')
    bit_identity(bit, program, plan, proof['FinalADF']['SHA256'])
    bit_path = add(bit['Bitstream']['Path'], bit['Bitstream']['SHA256'], 'actual selected programming bit; explicit copy')
    require(bit_path == work / 'bit-v3-a/generate_bitstream/hdmi_camera_fisheye_top.sbit' and
            local_io(bit_path).stat().st_size == bit['Bitstream']['Bytes'] == 3791112, 'actual complete 3.79MB own bit required')
    require(parse_bit_header(local_io(bit_path).read_bytes()) == bit['Bitstream']['Header'], 'actual selected bit header differs from saved public verification')
    gate = data['PreBitGate']; require(gate.get('GatePassed') is True and gate['FinalADFSHA256'] == proof['FinalADF']['SHA256'], 'fresh runtime gate ADF differs')
    execution = data['BitExecution']; check_bit_execution(execution)
    require(execution['PlanSHA256'] == sha(paths['BitPlan']) and execution['FinalADFSHA256'] == proof['FinalADF']['SHA256'] and
            datetime.fromisoformat(execution['StartedUTC']) <= datetime.fromisoformat(gate['CheckedUTC']) <=
            datetime.fromisoformat(execution['FinishedUTC']) and gate['Checks'] == bit['FreshSTA'],
            'fresh runtime gate was not within this own execution/plan/STA event')
    require(data['BitPlan'].get('Schema') == 'hdmi-camera-fisheye-tile8df8v3-bitstream-plan-v1' and
            gate.get('Schema') == 'hdmi-camera-fisheye-tile8df8v3-pre-bit-gate-v1', 'own saved bit plan/runtime gate schemas required')
    bit_request_path = bound(data['BitPlan']['Request'], 'actual seven-field bit request')
    bit_request = read(bit_request_path)
    require(set(bit_request) == {'Schema','Target','PhysicalProof','MapperSimulation','SystemSimulation','IOSimulation','Profile'} and
            bit_request['Schema'] == 'hdmi-camera-fisheye-tile8df8v3-bitstream-request-v1' and bit_request['Target'] == TARGET,
            'exact real seven-field runtime request required')
    for name in ('PhysicalProof','MapperSimulation','SystemSimulation','IOSimulation','Profile'):
        require(bit_request[name] == data['BitPlan'][name], 'actual request/bit-plan dependency differs')
    for name, h in bit['EvidenceSHA256'].items():
        relative(name); add(work / 'bit-v3-a' / name, h, 'actual STA/runtime-gate/generation artifact')
    require(bit['EvidenceSHA256']['pre-bit-audit.json'] == sha(paths['PreBitGate']) and
            bit['EvidenceSHA256']['execution-result.json'] == sha(paths['BitExecution']), 'actual bit public verification core differs')
    for name, h in gate['EvidenceSHA256'].items():
        relative(name); add(work / 'bit-v3-a' / name, h, 'fresh gate evidence')
    require(datetime.fromisoformat(program['StartedUTC']) >= datetime.fromisoformat(execution['FinishedUTC']) and
            datetime.fromisoformat(program['EndedUTC']) >= datetime.fromisoformat(program['StartedUTC']), 'programming preceded bit generation or did not finish')
    for name, h in program['Logs'].items():
        relative(name); add(work / 'program-v3-a' / name, h, 'actual SRAM device/program/DONE log')
    check_scan_program(native_log(work / 'program-v3-a/scan.out.log'),
                       native_log(work / 'program-v3-a/program.out.log'))
    check_resource_identity(data['ResourceIdentity'], bit, proof, reference(paths['FinalProof']), reference(paths['ProgramReceipt']))
    provider, source_review = data['ProviderManifest'], data['RootSourceReview']
    authority.check_source_freeze(reference(paths['ProviderManifest']), reference(paths['RootSourceReview']),
        reference(paths['PrewarmWrapper']), reference(paths['OriginalProviderManifest']), reference(paths['OriginalRootSourceReview']))
    for original_role in ('OriginalProviderManifest', 'OriginalRootSourceReview'):
        original_path = str(paths[original_role]); original_sha = sha(paths[original_role])
        require(provider.get('InputSHA256', {}).get(original_path) == original_sha and
                source_review.get('InputSHA256', {}).get(original_path) == original_sha,
                'new v3 freeze/root review must both bind immutable original provenance')
    require(sha(paths['ProviderManifest']) == PROVIDER_SHA and sha(paths['RootSourceReview']) == ROOT_REVIEW_SHA,
            'final frozen provider/root independent source review differs')
    require(provider.get('Passed') is True and provider.get('InputDrift') == [] and
            provider.get('PriorPhysicalTimingOrAcceptanceInherited') is False and source_review.get('InputDrift') == [],
            'final source proof drift/inherited acceptance')
    require(source_review.get('OriginalPhysicalAcceptanceInherited') is False and
            source_review.get('PhysicalAcceptanceInherited') is False, 'source review inherited physical acceptance')
    require(provider.get('Schema') == f'hdmi-camera-fisheye-tile8{candidate}v3-provider-source-manifest-v1' and
            provider.get('ProviderRevision') == authority.REVISION and provider.get('InputSHA256'), 'final current provider closure required')
    bit_provider = root / 'tools/hdmi_camera_fisheye_tile8df8v3_bitstream.py'
    add(bit_provider, provider['InputSHA256'][str(bit_provider)], 'actual selected public bit provider source')
    require(execution['ExecutorSHA256'] == sha(bit_provider), 'actual bit executor differs from final source freeze')
    program_provider = root / 'tools/hdmi_camera_fisheye_tile8df8v3_program.py'
    add(program_provider, provider['InputSHA256'][str(program_provider)], 'frozen actual SRAM executor')
    check_program_identity(plan, program, work, bit_path, sha(program_provider), bound)
    flags(source_review, ('Passed', 'IndependentPeerReviewPerformed'), 'final independent complete source review')
    require(source_review.get('Schema') == f'hdmi-camera-fisheye-tile8{candidate}v3-complete-source-independent-peer-review-v1' and
            source_review.get('ProviderRevision') == provider['ProviderRevision'], 'preliminary/unrelated source review cannot substitute')
    flags(data['WarningsReview'], ('Passed', 'SourceDiagnosticReviewPassed'), 'final actual source-warning review')
    require(data['WarningsReview']['Inventory'] == reference(paths['WarningsInventory']), 'actual final warning pin/inventory differs')
    warning_provider = root / 'tools/hdmi_camera_fisheye_tile8df8_warnings.py'
    add(warning_provider, provider['InputSHA256'][str(warning_provider)], 'actual final pinned warning provider')
    tree = ast.parse(local_io(warning_provider).read_text(encoding='utf-8'))
    assignments = [node.value for node in tree.body if isinstance(node, ast.Assign) and
        any(isinstance(target, ast.Name) and target.id == 'INVENTORY_SHA' for target in node.targets)]
    require(len(assignments) == 1 and isinstance(assignments[0], ast.Constant) and
            assignments[0].value == sha(paths['WarningsInventory']), 'actual final warning inventory remains unpinned or differs')
    check_saved_cache(root, paths['UnitReceipt'], paths['CollisionReceipt'], data['SourceContractReview'], add)
    require(proof['BuildPlan'] == reference(paths['BuildPlan']) and data['BitPlan']['BuildPlan'] == proof['BuildPlan'] and
            data['BitPlan']['PhysicalProof'] == reference(paths['FinalProof']), 'own build/final proof/bit plan differ')
    for role in ('MapperSimulation', 'IOSimulation', 'Profile'):
        require(data['BitPlan'][role] == reference(paths[role]), 'real bit seven-field dependency differs: ' + role)
    require(data['BitPlan']['SystemSimulation'] == reference(paths['NormalNative']), 'real normal-system runtime-gate dependency differs')
    simulation_work = work
    for role, suffix in [('NormalSmall','system-small-a'), ('NormalNative','system-native-a'),
                         ('SustainedSmall','system-sustained-small-a'), ('SustainedNative','system-sustained-native-a')]:
        require(paths[role] == simulation_work / suffix / 'simulation.json' and data[role].get('Passed') is True and
                data[role].get('FunctionalPassed') is True and data[role].get('InputDrift') == [], 'actual selected same-source system evidence required')
    require(data['SustainedNative']['Summary']['unique_scanned_pixels'] == 8294400 and
            data['NormalNative']['Summary']['unique_scanned_pixels'] == 4147200, 'complete actual normal/stress scans required')
    manifest, build = data['ProductionManifest'], data['BuildPlan']
    require(paths['ProductionManifest'] == root / 'board/hdmi-camera-fisheye-tile8df8-build-sources.json' and
            build['Manifest'] == reference(paths['ProductionManifest']) and
            manifest.get('Schema') == 'hdmi-camera-fisheye-tile8df8-source-closure-v1', 'own selected source manifest required')
    require(len(manifest['source_files']) == len(set(manifest['source_files'])) == 110 and
            build['SourceFiles'] == manifest['source_files'] and len(build['CompiledInputs']) == 110,
            'exact selected 110-source/compiled snapshot closure required')
    for name in manifest['source_files']: add(root / name, manifest['SourceSHA256'][name], 'selected original production input')
    for row in build['CompiledInputs']:
        require(row['OriginalSHA256'] == manifest['SourceSHA256'][row['Source']], 'compiled original binding differs')
        add(row['CompiledPath'], row['CompiledSHA256'], 'selected compiled source snapshot')
        require(replay_compiled(local_io(root / row['Source']).read_bytes(), row['Changes']) ==
                local_io(row['CompiledPath']).read_bytes(), 'prepared snapshot changes exceed the real build recipe')
    transformed = [row for row in build['CompiledInputs'] if row['Changes']]
    require(len(transformed) == 6 and sum(change['Kind']=='BoundHeaderIncludeRelocation' for row in transformed for change in row['Changes']) == 5 and
            sum(change['Kind']=='SelectedDigitalTimingOnly' for row in transformed for change in row['Changes']) == 1,
            'six snapshots/five include/one selected timing transform boundary differs')
    require(manifest['FrozenTopParameterOverride'] ==
            {'Parameter':'INPUT_TIMING_CONFIGURED','Original':0,'Compiled':1}, 'original selected digital timing override must remain')
    reviewer = load_fps_reviewer(repo, add)
    release_identity = check_release_identity(work, paths, data, add, bound, reviewer)
    libraries = load_wire_libraries(root, add); fps = {}
    for role, seconds in [('FPS30',30), ('FPS600',600)]:
        value = data[role]; require(paths[role].is_relative_to(work) and paths['FPS30'] != paths['FPS600'], 'own distinct 30/600s measurement receipts required')
        require(datetime.fromisoformat(value['started_utc']) >= datetime.fromisoformat(program['EndedUTC']), 'measurement preceded actual programming completion')
        require(value['program_receipt'] == {'path':str(paths['ProgramReceipt']),'sha256':sha(paths['ProgramReceipt'])}, 'FPS receipt names another programming event')
        wire = add(value['wire']['path'], value['wire']['sha256'], role + ' actual saved wire')
        require(wire.parent == paths[role].parent and wire.name == 'wire.bin', 'actual wire outside selected measurement')
        fps[role] = reparse_fps(value, local_io(wire).read_bytes(), program, seconds, libraries, reviewer)
    # Bind current saved dependency maps, without invoking the producers again.
    for role, value in data.items():
        for group in ('InputSHA256', 'PreparedSHA256', 'BoundInputSHA256', 'SourceSHA256'):
            if isinstance(value.get(group), dict):
                for name, h in value[group].items():
                    path = Path(name) if Path(name).is_absolute() else root / name
                    add(path, h, role + ' saved dependency')
        for group in ('LogSHA256', 'ResultSHA256', 'FixtureSHA256', 'ArtifactsSHA256'):
            if isinstance(value.get(group), dict):
                for name, h in value[group].items():
                    item = Path(name); require(not item.is_absolute() and '..' not in item.parts, 'saved artifact escaped')
                    add(paths[role].parent / item, h, role + ' saved artifact')
    for row in request['AdditionalFiles']:
        require(set(row) == {'Source', 'Reason'} and type(row['Reason']) is str and row['Reason'], 'explicit extra-file reason required')
        bound(row['Source'], row['Reason'])
    portable_roles, portable_members = portable_closure(root, add)
    adapter = add(Path(portable.__file__), PORTABLE_SHA, 'portable source contract replay entry')
    adapter_tests = add(SELF.parent / 'test_portable_source_contract.py', PORTABLE_TEST_SHA, 'portable adapter tamper/path/trace rejection tests')
    fixture_source = add(SELF.parent / 'make_test_fixture.py', 'ee8aa0a663bec96175bb8aca2db36eb998b1036bd912ce1a2f424730798ae652',
                         'original portable test fixture builder source; not run during assembly')
    assembler = add(SELF, reason='exact stage D assembler source')
    assembler_tests = add(SELF.parent / 'test_assemble_stage_d_c.py', reason='stage D assembler rejection tests')
    # Never copy large physical/intermediate artifacts into Git delivery.
    blocked_suffixes = {'.rtr', '.db', '.adf', '.netlist', '.exe', '.dll', '.pyd', '.gzip', '.gz', '.zip'}
    prefix = f'evidence/next-d/{candidate}/'
    for index, row in enumerate(files.values()):
        path = Path(row['Path']); copied = path.is_relative_to(repo) and row['Bytes'] <= MAX_COPY and path.suffix.lower() not in blocked_suffixes
        if any(part in ('.git', '__pycache__', '.venv') for part in path.parts): copied = False
        row['Mode'] = 'copy' if copied else 'reference'
        row['Destination'] = prefix + f'files/{index:04d}/' + path.name if copied else None
    require(files[str(bit_path)]['Mode'] == 'copy', 'actual programming bit must be explicitly bundled')
    required_copy = portable_members | {str(adapter), str(adapter_tests), str(fixture_source), str(assembler), str(assembler_tests), str(authority_path)}
    require(all(files[name]['Mode'] == 'copy' for name in required_copy), 'portable replay entry/tests/closure must all be copied')
    for path in (adapter, adapter_tests, fixture_source, assembler, assembler_tests, authority_path):
        files[str(path)]['Destination'] = prefix + 'replay/' + path.name
    contract_map = source_contract_map(portable_roles, portable_members, files.values())
    require(snapshot(base) == before and all(sha(name) == h for name, h in watched.items()), 'archive preparation byte drift')
    return {'Candidate':candidate, 'BasePackage':str(base), 'DestinationPackage':str(destination), 'BaseSnapshot':before,
        'Files':list(files.values()), 'Roles':request['Roles'], 'FPSReparsed':fps, 'InputSHA256':watched,
        'ReleaseIdentity': release_identity, 'PortableSourceContractMap': contract_map,
        'PortableReplay': {'Adapter': files[str(adapter)]['Destination'], 'Tests': files[str(adapter_tests)]['Destination'],
            'Map': 'source-contract-map-d.json'},
        'ArchiveScope':'Saved-byte chain recheck only. No public physical/bit provider recomputation, EDA or hardware.',
        'ProviderVerificationInvoked':False, 'EDAExecuted':False, 'HardwareAccessed':False,
        'ExternalPublicationPerformed':False, 'HardwareReleaseAllowed':False}


def write_json(path, value):
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, indent=2, allow_nan=False); stream.write('\n')


def preflight_targets(operations, destination):
    destination = Path(destination).absolute()
    identities = set()
    for source, target, digest, size in operations:
        require(target.is_absolute(), 'absolute archive target required')
        require(target.resolve().is_relative_to(destination), 'archive target escaped')
        key = str(target).casefold()
        require(key not in identities, 'duplicate archive destination')
        identities.add(key)
        for ancestor in (target.parent, *target.parent.parents):
            require(not ancestor.is_symlink(), 'archive target ancestor cannot be a symlink')
            require(not ancestor.exists() or ancestor.is_dir(), 'archive target ancestor is not a directory')
        require(not target.exists() or target.is_file() and target.stat().st_size == size and sha(target) == digest,
                'existing D/A/B/C target differs; refusing overwrite')


def assemble(config_path):
    plan = prepare(config_path); base, destination = Path(plan['BasePackage']), Path(plan['DestinationPackage'])
    outputs = ('approved-evidence-sources-d.json', 'portable-evidence-manifest-d.json', 'copy-receipt-d.json', 'source-contract-map-d.json')
    require(not any((destination / name).exists() for name in outputs), 'fresh stage D output names required')
    operations = [(base / name, destination / name, row['SHA256'], row['Bytes']) for name, row in plan['BaseSnapshot'].items()]
    operations += [(Path(row['Path']), destination / row['Destination'], row['SHA256'], row['Bytes']) for row in plan['Files'] if row['Mode'] == 'copy']
    if destination.exists():
        allowed = set(plan['BaseSnapshot']) | {row['Destination'] for row in plan['Files'] if row['Mode']=='copy'}
        require(set(snapshot(destination)) <= allowed, 'unreviewed pre-existing file in destination package')
    # Inspect every existing target before any mutation. Differing bytes are never overwritten.
    preflight_targets(operations, destination)
    for name in outputs:
        for ancestor in ((destination / name).parent, *(destination / name).parent.parents):
            require(not ancestor.is_symlink() and (not ancestor.exists() or ancestor.is_dir()), 'output ancestor is not a directory')
    for source, target, digest, size in operations:
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            with local_io(source).open('rb') as src, target.open('xb') as dst: shutil.copyfileobj(src, dst, 8 * 1024 * 1024)
        require(target.stat().st_size == size and sha(target) == sha(source) == digest, 'copy byte drift')
    require(all(sha(name) == h for name,h in plan['InputSHA256'].items()), 'saved dependency changed during archive copy')
    require(snapshot(base) == plan['BaseSnapshot'], 'original A/B/C changed during copy')
    require(all((destination / name).stat().st_size == row['Bytes'] and sha(destination / name) == row['SHA256']
        for name,row in plan['BaseSnapshot'].items()), 'copied original A/B/C changed')
    write_json(destination / outputs[3], plan['PortableSourceContractMap'])
    portable_facts, portable_watch = portable.review(destination, destination / outputs[3])
    require(portable_facts.get('PortableSourceContractVerified') is True and
            portable_facts.get('PublicationComplete') is False, 'copied portable source replay failed or exceeded scope')
    approved = {'Schema':'hdmi-camera-fisheye-tile8-approved-evidence-sources-v1','ApprovedCompletedEvidenceOnly':True,
        'MaximumSingleCopyBytes':MAX_COPY,'Candidate':plan['Candidate'], 'Scope':plan['ArchiveScope'],
        'Entries':[{'ID':str(i),'Source':{'Path':row['Path'],'SHA256':row['SHA256'],'Bytes':row['Bytes']},
            'Mode':row['Mode'],'Destination':row['Destination'],'Reason':row['Reason']}
            for i,row in enumerate(plan['Files'])]}
    write_json(destination / outputs[0], approved)
    receipt = {'Schema':'hdmi-camera-fisheye-tile8-evidence-archive-receipt-v1','Passed':True,
        'Candidate':plan['Candidate'],'SourceFilesModified':False,'HistoricalABCBytesPreserved':True,
        'Scope':plan['ArchiveScope'],'SourcesManifest':reference(destination / outputs[0]),
        'InputSHA256':plan['InputSHA256'],'Roles':plan['Roles'],'FPSReparsed':plan['FPSReparsed'],
        'ReleaseIdentity': plan['ReleaseIdentity'], 'PortableSourceContractMap': reference(destination / outputs[3]),
        'PortableSourceContractReplay': portable_facts, 'PortableReplay': plan['PortableReplay'],
        'ProviderVerificationInvoked':False,'EDAExecuted':False,'HardwareAccessed':False,
        'ExternalPublicationPerformed':False,'CommitCreated':False,'ReleaseOrTimingAcceptanceConferred':False}
    write_json(destination / outputs[2], receipt)
    bundled = snapshot(destination)
    write_json(destination / outputs[1], {'Schema':'hdmi-camera-fisheye-tile8-portable-archive-v1',
        'BundledFiles':[{'Path':name,**row} for name,row in sorted(bundled.items())],
        'ManifestSelfExcluded':True,'LargePhysicalProofsBundled':False,'ExternalPhysicalEvidence':
            [row for row in plan['Files'] if row['Mode']=='reference']})
    require(snapshot(base) == plan['BaseSnapshot'], 'original A/B/C changed during copy')
    require(all((destination / name).stat().st_size == row['Bytes'] and sha(destination / name) == row['SHA256']
        for name,row in plan['BaseSnapshot'].items()), 'copied original A/B/C changed')
    return reference(destination / outputs[2])


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--config',type=Path,required=True)
    parser.add_argument('--write',action='store_true',help='Only after complete real validation: write fresh archive files')
    args=parser.parse_args(argv)
    if args.write: result={'ArchiveReceipt':assemble(args.config),'ExternalPublicationPerformed':False}
    else:
        plan=prepare(args.config);result={'ReadOnlyValidated':True,'Candidate':plan['Candidate'],
            'Files':len(plan['Files']),'ArchiveWritten':False,'HardwareAccessed':False}
    print(json.dumps(result));return 0


if __name__=='__main__':raise SystemExit(main())
