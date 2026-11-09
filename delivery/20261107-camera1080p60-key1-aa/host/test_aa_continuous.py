"""Long observation arithmetic and streaming tests, using synthetic bytes only."""
import copy
import hashlib
import io
import itertools
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch
import zlib

from aa_capture import collect
from aa_measure import CORE_HZ, UINT32, analyze, analyze_file, analyze_stream, file_sha256
from aa_protocol import make_arm, make_stats
from test_aa_tools import FakeClock, FakeTransport, ack, fixture, signature, stats


def write_continuous(path, *, seconds=600, signatures_per_second=60, bad_middle=None):
    """Construct 600 nominal seconds without sleeping or opening a serial port."""
    _, manifest = fixture()
    manifest['EpochLabel'] = 'SYNTHETIC_CONTINUOUS_NOT_BOARD_EVIDENCE'
    manifest['Requests'] = [{'PacketHex': make_arm(1, 10).hex(), 'Outcome': 'sent'}]
    sequence = 1
    with Path(path).open('wb') as stream:
        stream.write(ack())
        stream.write(signature(99, sequence))
        for second in range(seconds + 1):
            if second:
                for step in range(signatures_per_second):
                    sequence += 1
                    frame = 100 + (second - 1) * signatures_per_second + step
                    stream.write(signature(frame, sequence))
            ticket = second + 2
            nonce = ticket + 10000
            manifest['Requests'].append({'PacketHex': make_stats(ticket, nonce).hex(), 'Outcome': 'sent'})
            extra = bad_middle if second == seconds // 2 and bad_middle else {}
            stream.write(stats(ticket, nonce, second, (second + 1) * CORE_HZ,
                               100 + second * signatures_per_second, **extra))
    manifest['RawSHA256'] = file_sha256(path)
    return manifest


class ContinuousTests(unittest.TestCase):
    def test_600_second_hardware_window_uses_streaming_and_retains_no_signature_list(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'synthetic.raw'
            manifest = write_continuous(path)
            with patch.object(Path, 'read_bytes', side_effect=AssertionError('Do not load whole file')):
                result = analyze_file(path, manifest, uninterrupted_reset_epoch=True)
            self.assertEqual(result['CoreCycles'], 600 * CORE_HZ)
            self.assertEqual(result['SecondsNominal'], 600)
            self.assertEqual(result['Delta']['presented_frames'], 36000)
            self.assertEqual(result['Rates']['presented_fps_nominal'], 60)
            self.assertEqual(len(result['Windows']), 600)
            self.assertEqual(result['SignatureCrosscheck']['Packets'], 36001)
            self.assertEqual(result['SignatureCrosscheck']['DistinctPresentedFrameIDsObserved'], 36001)
            self.assertFalse(result['HardwarePassClaim'])
            self.assertFalse(result['Sustained60FPSPassClaim'])

    def test_multiple_counter_wraps_are_summed_per_adjacent_window(self):
        _, manifest = fixture()
        manifest['Requests'] = [{'PacketHex': make_arm(1, 10).hex(), 'Outcome': 'sent'}]
        packets = [ack(), signature(99, 1)]
        per_window = UINT32 - 100
        count = UINT32 - 10
        for index in range(6):
            ticket = index + 2
            nonce = ticket + 10000
            manifest['Requests'].append({'PacketHex': make_stats(ticket, nonce).hex(), 'Outcome': 'sent'})
            packet = bytearray(stats(ticket, nonce, index, (index + 1) * (UINT32 - 1),
                                     100, frame_id=100 + index))
            struct.pack_into('<5I', packet, 56, count, count, count, 0, 0)
            packet[80:] = struct.pack('<I', zlib.crc32(packet[:80]))
            packets.extend((bytes(packet), signature(100 + index, 2 + index)))
            count = (count + per_window) % UINT32
        raw = b''.join(packets)
        manifest['RawSHA256'] = hashlib.sha256(raw).hexdigest()
        result = analyze(raw, manifest, uninterrupted_reset_epoch=True)
        self.assertEqual(result['Delta']['presented_frames'], 5 * per_window)
        self.assertGreater(result['Delta']['presented_frames'], UINT32 * 4)
        self.assertEqual(result['CoreCycles'], 5 * (UINT32 - 1))

    def test_one_excessive_middle_interval_rejects_entire_capture(self):
        # Total duration alone says nothing about whether a middle modulo
        # interval is unambiguous. Exactly 2^32 is forbidden as well.
        for gap in (UINT32, UINT32 + 1, 0, -1):
            _, changed_manifest = fixture()
            changed_manifest['Requests'] = [{'PacketHex': make_arm(1, 10).hex(), 'Outcome': 'sent'}]
            packets = [ack()]
            for index, tick in enumerate((CORE_HZ, 2 * CORE_HZ,
                                          2 * CORE_HZ + gap, 3 * CORE_HZ + gap)):
                ticket, nonce = index + 2, (index + 2) * 10
                changed_manifest['Requests'].append({'PacketHex': make_stats(ticket, nonce).hex(),
                                                    'Outcome': 'sent'})
                packets.extend((signature(99 + index * 60, index + 1),
                                stats(ticket, nonce, index, tick, 100 + index * 60)))
            changed = b''.join(packets)
            changed_manifest['RawSHA256'] = hashlib.sha256(changed).hexdigest()
            with self.subTest(gap=gap), self.assertRaisesRegex(ValueError, 'Adjacent measurement'):
                analyze(changed, changed_manifest, uninterrupted_reset_epoch=True)

    def test_short_nonseekable_reads_match_existing_bytes_entrypoint(self):
        raw, manifest = fixture()
        class ShortStream:
            def __init__(self):
                self.source = io.BytesIO(raw)
            def read(self, size):
                return self.source.read(min(size, 7))
        self.assertEqual(analyze_stream(ShortStream(), manifest, uninterrupted_reset_epoch=True),
                         analyze(raw, manifest, uninterrupted_reset_epoch=True))

    def test_late_hash_crc_and_truncation_fail_before_any_acceptance(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'synthetic.raw'
            manifest = write_continuous(path, seconds=40, signatures_per_second=2)
            digest = file_sha256(path)
            wrong = copy.deepcopy(manifest)
            wrong['RawSHA256'] = '0' * 64
            with self.assertRaisesRegex(ValueError, 'SHA256'):
                analyze_file(path, wrong, uninterrupted_reset_epoch=True)
            self.assertEqual(file_sha256(path), digest)
            original = path.read_bytes()
            for altered in (original[:-1], original[:-3] + bytes([original[-3] ^ 1]) + original[-2:]):
                path.write_bytes(altered)
                with self.assertRaises(ValueError):
                    analyze_file(path, manifest, uninterrupted_reset_epoch=True)
                self.assertEqual(path.read_bytes(), altered)

    def test_late_mode_or_fault_rejects_entire_long_run(self):
        with tempfile.TemporaryDirectory() as directory:
            for problem in ({'mode': 3}, {'flags': 64}):
                path = Path(directory) / 'synthetic.raw'
                manifest = write_continuous(path, seconds=80, signatures_per_second=2,
                                            bad_middle=problem)
                with self.subTest(problem=problem), self.assertRaises(ValueError):
                    analyze_file(path, manifest, uninterrupted_reset_epoch=True)

    def test_arm_must_be_first_recorded_command(self):
        raw, manifest = fixture()
        manifest['Requests'][0]['PacketHex'] = make_stats(1, 20).hex()
        manifest['Requests'][1]['PacketHex'] = make_arm(2, 10).hex()
        with self.assertRaisesRegex(ValueError, 'ARM must be the first'):
            analyze(raw, manifest, uninterrupted_reset_epoch=True)

    def test_collector_runs_beyond_old_limit_and_anchors_duration_after_first_stats(self):
        _, template = fixture()
        clock = FakeClock()
        transport = FakeTransport(clock)
        nonces = iter(range(100, 300))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'run'
            manifest = collect(transport, path, template, seconds=40, interval=1,
                               clock=clock, nonce_source=lambda: next(nonces))
            result = analyze_file(path / 'camera-uart.raw.bin', manifest,
                                  uninterrupted_reset_epoch=True)
            self.assertGreaterEqual(result['SecondsNominal'], 40)
            self.assertEqual(manifest['Status'], 'complete')
            self.assertIn('first statistics reply', manifest['DurationAnchor'])

    def test_poll_interval_cap_and_invalid_duration_fail_before_creation(self):
        _, manifest = fixture()
        for seconds, interval in ((600, 6), (3601, 1), (float('nan'), 1), (10, float('inf'))):
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / 'must-not-exist'
                with self.subTest(seconds=seconds, interval=interval), self.assertRaises(ValueError):
                    collect(None, path, manifest, seconds=seconds, interval=interval)
                self.assertFalse(path.exists())

    def test_unused_nonce_collision_is_redrawn_without_command_retry(self):
        _, template = fixture()
        clock = FakeClock()
        transport = FakeTransport(clock)
        nonces = itertools.chain.from_iterable((n, n) for n in range(100, 1000))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'run'
            manifest = collect(transport, path, template, seconds=1, interval=0.25,
                               clock=clock, nonce_source=lambda: next(nonces))
            identities = [entry['Nonce'] for entry in manifest['Requests']]
            self.assertEqual(len(set(identities)), len(identities))
            self.assertEqual(len(transport.commands), len(identities))
            self.assertTrue(all(entry['Outcome'] == 'sent' for entry in manifest['Requests']))

    def test_bad_nonce_source_stops_without_uncertain_command_retry(self):
        _, template = fixture()
        clock = FakeClock()
        transport = FakeTransport(clock)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'run'
            with self.assertRaisesRegex(ValueError, 'exhausted 16'):
                collect(transport, path, template, seconds=1, interval=0.25,
                        clock=clock, nonce_source=lambda: 100)
            manifest = json.loads((path / 'capture.json').read_text())
            self.assertEqual(manifest['Status'], 'failed')
            self.assertEqual(len(transport.commands), 1)


if __name__ == '__main__':
    unittest.main(verbosity=2)
