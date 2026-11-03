"""Synthetic decoder refusal cases; no hardware and no candidate measurements."""
import argparse
import copy
from datetime import datetime, timedelta, timezone
import importlib.util
import io
import json
from pathlib import Path
import unittest
import zlib

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location('saved_fps_review_tested', HERE / 'verify_saved_fps_stability_d.py')
M = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(M)


def fixture(seconds=30):
    increments = (60, 15, 15, 15, 30, 0, 112000000, 750000, 31000000, 30, 15, 0)
    rows = []
    for i in range(seconds):
        row = {'sequence': (M.U32 - 12 + i) & M.U32, 'core_ticks': 3750000000 + i * M.HZ,
               'status_valid': True, 'failed': False, 'corrected_requested': True, 'fault': 0,
               'profile_id': f'{M.PROFILE:016x}', 'build_id': f'{M.BUILD:08x}', 'host_elapsed_seconds': .25 + i}
        row.update({key: (M.U32 - 100 + i * rate) & M.U32 for key, rate in zip(M.COUNTERS, increments)})
        row['last_process_cycles'] = 5540000
        rows.append(row)
    start = datetime(2026, 11, 4, tzinfo=timezone.utc)
    return {'schema': 'hdmi-camera-fisheye-host-timed-fps-v1', 'passed': True, 'started_utc': start.isoformat(),
            'ended_utc': (start + timedelta(seconds=seconds + .01)).isoformat(), 'port': 'COM7', 'baud': 115200,
            'uart_transmit_bytes': 0, 'frames': rows, 'crc_rejected_packets': 0, 'discarded_bytes': 0}


def wire(value):
    result = bytearray()
    for row in value['frames']:
        flags = int(row['failed']) | (int(row['status_valid']) << 1) | (int(row['corrected_requested']) << 2)
        packet = M.PACKET.pack(M.MAGIC, 2, flags, 96, row['sequence'], row['core_ticks'],
                               *(row[k] for k in M.COUNTERS), 0, row['fault'],
                               int(row['profile_id'], 16), int(row['build_id'], 16), 0)
        result.extend(packet[:92] + zlib.crc32(packet[:92]).to_bytes(4, 'little'))
    return bytes(result)


class SavedWireTests(unittest.TestCase):
    def reject(self, change, seconds=30, raw_change=None):
        value = fixture(seconds); change(value)
        data = wire(value)
        if raw_change is not None: data = raw_change(data)
        with self.assertRaises((ValueError, KeyError, TypeError)): M.analyze(value, data, seconds)

    def test_30_second_wall_has_29_second_counter_window(self):
        v = fixture(); r = M.analyze(v, wire(v), 30)
        self.assertEqual(r['HostFirstToLastWindowSeconds'], 29)
        self.assertEqual(r['ActualAcquisitionWallSeconds'], 30.01)
        self.assertEqual(r['IndependentHostRates']['unique_presented_frames_per_second'], 15)
        self.assertEqual(r['ProtocolWidths']['CoreTimerBits'], 64)

    def test_600_seconds_sums_many_cache_wraps_per_sample(self):
        v = fixture(600); r = M.analyze(v, wire(v), 600)
        self.assertEqual(r['HostFirstToLastWindowSeconds'], 599)
        self.assertEqual(r['PerAdjacentSampleModulo32Totals']['cache_hits'], 599 * 112000000)
        self.assertGreater(r['PerAdjacentSampleModulo32Totals']['cache_hits'], M.U32)
        self.assertNotEqual(r['PerAdjacentSampleModulo32Totals']['cache_hits'], r['CounterEndpointModulo32']['cache_hits'])

    def test_600_wall_need_not_have_exact_600_samples(self):
        v = fixture(600); v['frames'] = v['frames'][:595]
        for i, row in enumerate(v['frames']): row['host_elapsed_seconds'] = .25 + i * (599 / 594)
        r = M.analyze(v, wire(v), 600)
        self.assertEqual(r['CompleteSamples'], 595)
        self.assertEqual(r['HostFirstToLastWindowSeconds'], 599)
        self.assertTrue(r['ClockCrossCheckWithin3Percent'])

    def test_600_wall_595_counter_seconds_explicit(self):
        v = fixture(600); v['frames'] = v['frames'][:596]
        r = M.analyze(v, wire(v), 600)
        self.assertEqual(r['ActualAcquisitionWallSeconds'], 600.01)
        self.assertEqual(r['NominalCounterWindowSeconds'], 595)
        self.assertEqual(r['HostFirstToLastWindowSeconds'], 595)

    def test_600_wall_insufficient_coverage_rejected(self):
        v = fixture(600); v['frames'] = v['frames'][:550]
        with self.assertRaises(ValueError): M.analyze(v, wire(v), 600)

    def test_sequence_wrap_is_legal(self):
        v = fixture(); self.assertGreater(v['frames'][0]['sequence'], v['frames'][-1]['sequence'])
        M.analyze(v, wire(v), 30)

    def test_structurally_valid_partial_tail_disclosed(self):
        v = fixture(); nxt = copy.deepcopy(v['frames'][-1]); nxt['sequence'] = (nxt['sequence'] + 1) & M.U32; nxt['core_ticks'] += M.HZ
        tail = wire({'frames': [nxt]})[:25]; r = M.analyze(v, wire(v) + tail, 30)
        self.assertEqual(r['TrailingPartialPacketBytes'], 25)

    def next_packet(self, v):
        nxt = copy.deepcopy(v['frames'][-1]); nxt['sequence'] = (nxt['sequence'] + 1) & M.U32; nxt['core_ticks'] += M.HZ
        return wire({'frames': [nxt]})

    def test_all_95_legal_tail_boundaries(self):
        v = fixture(); packet = self.next_packet(v)
        for size in range(1, 96):
            with self.subTest(size=size):
                r = M.analyze(v, wire(v) + packet[:size], 30)
                self.assertEqual(r['TrailingPartialPacketBytes'], size)
                self.assertFalse(r['TrailingPartialPacketCountedAsComplete'])
                self.assertFalse(r['TrailingPartialPacketCRCVerified'])
                self.assertEqual(r['TrailingPartialReceivedCRCBytesChecked'], max(0, size - 92))

    def reject_tail(self, size, offset):
        v = fixture(); tail = bytearray(self.next_packet(v)[:size]); tail[offset] ^= 1
        with self.assertRaises(ValueError): M.analyze(v, wire(v) + tail, 30)

    def test_partial_length_low_byte_rejected(self): self.reject_tail(11, 10)
    def test_partial_timer_low_byte_rejected(self): self.reject_tail(18, 16)
    def test_partial_reserved_low_byte_rejected(self): self.reject_tail(73, 72)
    def test_partial_profile_low_byte_rejected(self): self.reject_tail(81, 80)
    def test_partial_crc_first_byte_rejected(self): self.reject_tail(93, 92)
    def test_partial_next_sequence_low_byte_rejected(self): self.reject_tail(13, 12)
    def test_partial_build_low_byte_rejected(self): self.reject_tail(89, 88)
    def test_partial_fault_high_byte_rejected(self): self.reject_tail(78, 77)
    def test_partial_visible_fault_health_rejected(self): self.reject_tail(77, 76)
    def test_partial_visible_failed_health_rejected(self): self.reject_tail(10, 9)

    def test_bad_crc_rejected(self):
        self.reject(lambda v: None, raw_change=lambda b: b[:32] + bytes([b[32] ^ 1]) + b[33:])

    def test_leading_noise_rejected(self): self.reject(lambda v: None, raw_change=lambda b: b'x' + b)
    def test_trailing_noise_rejected(self): self.reject(lambda v: None, raw_change=lambda b: b + b'bad')
    def test_bad_profile_rejected(self): self.reject(lambda v: v['frames'][5].update(profile_id='0000000000000001'))
    def test_bad_build_rejected(self): self.reject(lambda v: v['frames'][5].update(build_id='00000001'))
    def test_fault_rejected(self): self.reject(lambda v: v['frames'][5].update(fault=1))
    def test_failed_rejected(self): self.reject(lambda v: v['frames'][5].update(failed=True))
    def test_inactive_rejected(self): self.reject(lambda v: v['frames'][5].update(status_valid=False))
    def test_raw_mode_rejected(self): self.reject(lambda v: v['frames'][5].update(corrected_requested=False))
    def test_sequence_gap_rejected(self): self.reject(lambda v: v['frames'][5].update(sequence=123))
    def test_core_reset_rejected(self): self.reject(lambda v: v['frames'][5].update(core_ticks=1))
    def test_host_reset_rejected(self): self.reject(lambda v: v['frames'][5].update(host_elapsed_seconds=0))
    def test_host_clock_disagreement_rejected(self):
        self.reject(lambda v: [row.update(host_elapsed_seconds=.25 + i * .97) for i, row in enumerate(v['frames'])])
    def test_counter_reset_rejected(self): self.reject(lambda v: v['frames'][5].update(processed_frames=1))
    def test_cache_reset_rejected(self): self.reject(lambda v: v['frames'][5].update(cache_hits=1))
    def test_blank_increment_rejected(self): self.reject(lambda v: v['frames'][5].update(scan_blank_frames=1))
    def test_zero_cycle_gauge_rejected(self): self.reject(lambda v: v['frames'][5].update(last_process_cycles=0))
    def test_nonfinite_arrival_rejected(self): self.reject(lambda v: v['frames'][5].update(host_elapsed_seconds=float('nan')))
    def test_crc_rejection_receipt_rejected(self): self.reject(lambda v: v.update(crc_rejected_packets=1))
    def test_too_few_samples_rejected(self): self.reject(lambda v: v.update(frames=v['frames'][:28]))
    def test_30_seconds_cannot_claim_600(self):
        v = fixture()
        with self.assertRaises(ValueError): M.analyze(v, wire(v), 600)
    def test_receipt_counter_differs_from_wire_rejected(self):
        v = fixture(); data = wire(v); v['frames'][5]['processed_frames'] += 1
        with self.assertRaises(ValueError): M.analyze(v, data, 30)
    def test_bool_counter_cannot_equal_integer(self):
        v = fixture(); data = wire(v); v['frames'][5]['fault'] = False
        with self.assertRaises(ValueError): M.analyze(v, data, 30)

    def test_program_missing_done_rejected(self):
        with self.assertRaises(ValueError): M.program_flags({'Passed': True})
    def test_program_flash_or_cleanup_failure_rejected(self):
        good = {k: True for k in ('Passed', 'DoneConfirmed', 'ExpectedDeviceAndIDConfirmed', 'HardwareAccessed',
                                  'ProgrammingAttempted', 'UserConfirmedBoardPowered', 'UserNotifiedBeforeExecution')}
        good.update(FlashWritten=False, CleanupErrors=[])
        M.program_flags(good)
        for change in ({'FlashWritten': True}, {'CleanupErrors': ['owned cleanup failed']}, {'Error': 'program failed'}):
            with self.assertRaises(ValueError): M.program_flags({**good, **change})

    def test_release_metadata_exact_roles(self):
        bit = {k: {'Path': k, 'SHA256': '0' * 64} for k in ('PhysicalProof', 'MapperSimulation', 'SystemSimulation', 'IOSimulation', 'Profile')}
        go = {'Schema': 'hdmi-camera-fisheye-tile8df8v2-physical-to-release-go-v1', 'ProviderRevision': 'tile8df8v2-bounded-b', **bit}
        warm = {'Schema': 'hdmi-camera-fisheye-tile8df8v2-release-authority-prewarm-v1', 'RequestExclusiveCreatedByWrapper': True,
                'PublicAuditRequestUseCache': False, 'FreshRuntimeGateStillRequired': True,
                'ExactRequest': {'Schema': 'hdmi-camera-fisheye-tile8df8v2-bitstream-request-v1', 'Target': 'hdmi_camera_fisheye_top', **bit}}
        warm.update({k: False for k in ('PrivateCacheAccessed', 'ProvidersPatched', 'BitStagePrepared', 'PDriveCreated', 'EDAExecuted',
                                      'HardwareAccessed', 'ReleaseAuthorizedByPrewarm')})
        M.release_metadata('tile8df8', bit, go, warm)
        mutations = [('Schema', 'other'), ('PublicAuditRequestUseCache', True), ('PrivateCacheAccessed', True),
                     ('ProvidersPatched', True), ('ReleaseAuthorizedByPrewarm', True), ('FreshRuntimeGateStillRequired', False),
                     ('RequestExclusiveCreatedByWrapper', False)]
        for key, value in mutations:
            with self.subTest(key=key), self.assertRaises(ValueError):
                M.release_metadata('tile8df8', bit, go, {**warm, key: value})
        bad = copy.deepcopy(warm); bad['ExactRequest']['SystemSimulation']['SHA256'] = '1' * 64
        with self.assertRaises(ValueError): M.release_metadata('tile8df8', bit, go, bad)
        bad = copy.deepcopy(warm); bad['ExactRequest']['Extra'] = True
        with self.assertRaises(ValueError): M.release_metadata('tile8df8', bit, go, bad)
        with self.assertRaises(ValueError): M.release_metadata('tile8df8', bit, {**go, 'ProviderRevision': 'old'}, warm)

    def test_source_hash_mismatch_rejected(self):
        with self.assertRaises(ValueError): M.Evidence().add(HERE / 'verify_saved_fps_stability_d.py', '0' * 64)


def main():
    ap = argparse.ArgumentParser(description=__doc__); ap.add_argument('--output', type=Path, required=True); a = ap.parse_args()
    output = a.output.resolve(); M.require(output.parent == HERE and not output.exists(), 'fresh isolated test report required')
    log = io.StringIO(); result = unittest.TextTestRunner(stream=log, verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(SavedWireTests))
    report = {'Schema': 'saved-fps-stability-synthetic-refusal-tests-v1', 'Passed': result.wasSuccessful(),
              'TestsRun': result.testsRun, 'Failures': len(result.failures), 'Errors': len(result.errors), 'Log': log.getvalue(),
              'SyntheticOnly': True, 'LegalTrailingPrefixBoundaryCases': 95, 'NewCandidateAcceptanceClaimed': False, 'HardwareAccessed': False,
              'InputSHA256': {str(Path(__file__).resolve()): M.sha(__file__), str(HERE / 'verify_saved_fps_stability_d.py'): M.sha(HERE / 'verify_saved_fps_stability_d.py')}}
    with output.open('x', encoding='utf-8') as stream: json.dump(report, stream, indent=2, allow_nan=False); stream.write('\n')
    print(json.dumps({k: report[k] for k in ('Passed', 'TestsRun', 'Failures', 'Errors')}))
    print(log.getvalue())
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__': raise SystemExit(main())
