"""Synthetic protocol and transport tests. These are not hardware evidence."""
import copy
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib

from aa_capture import collect
from aa_measure import AA_PARAM_ID, AA_SHA256, CORE_HZ, WireParser, analyze
from aa_protocol import make_arm, make_stats


def crc_packet(body):
    return body + struct.pack('<I', zlib.crc32(body))


def ack(ticket=1, nonce=10, status=1):
    return crc_packet(struct.pack('<4sBBHIII', b'SGK1', 1, status, 24, ticket, nonce, 1))


def stats(ticket, nonce, sequence, tick, count, *, mode=1, flags=0, param=AA_PARAM_ID,
          frame_id=None, repeats=0):
    header = struct.pack('<8sBBHIIIIIQ', b'PGSTAT02', 2, 1, 84, ticket, nonce,
                         7, CORE_HZ, sequence, tick)
    words = (1000, count if frame_id is None else frame_id, param, mode,
             count + 1, count, count - 1, repeats, 0, flags)
    return crc_packet(header + struct.pack('<10I', *words))


def signature(frame, sequence, *, mode=1, nonce=10, param=AA_PARAM_ID):
    body = bytearray(120)
    struct.pack_into('<8sBBBBHBB', body, 0, b'PGSIG001', 1, 2, 1, 1, 128, 8, 0)
    struct.pack_into('<10I', body, 16, nonce, sequence + 1, frame, param, sequence,
                     2073600, 0x12345678, 0, 0, 0)
    struct.pack_into('<HHBB', body, 56, 1920, 1080, 255, mode)
    # Legal payload may contain protocol magic and must never be resynchronized.
    body[70:78] = b'PGSTAT02'
    return crc_packet(bytes(body)) + b'SG01'


def fixture(*, first=100, last=160, first_tick=CORE_HZ, last_tick=2 * CORE_HZ,
            first_mode=1, last_mode=1, flags=0):
    raw = (ack() + signature(first - 1, 1, mode=first_mode) +
           stats(2, 20, 0, first_tick, first, mode=first_mode) +
           signature(first - 1, 2, mode=first_mode) +
           signature(last - 1, 3, mode=last_mode) +
           stats(3, 30, 1, last_tick, last, mode=last_mode, flags=flags))
    manifest = {'Status': 'complete', 'EpochLabel': 'synthetic-only',
                'KnownCleanResetBoundaryAttested': True, 'ExpectedMode': 'corr',
                'LoadedBitstreamSHA256OperatorSupplied': AA_SHA256,
                'RawSHA256': hashlib.sha256(raw).hexdigest(),
                'Requests': [{'PacketHex': p.hex(), 'Outcome': 'sent'}
                             for p in (make_arm(1, 10), make_stats(2, 20), make_stats(3, 30))]}
    return raw, manifest


class FakeClock:
    now = 0.0
    def __call__(self):
        return self.now


class FakeTransport:
    def __init__(self, clock, *, partial=False, corrupt=False, silent=False, extra_tail=False):
        self.clock = clock
        self.queue = bytearray()
        self.commands = []
        self.partial, self.corrupt, self.silent = partial, corrupt, silent
        self.extra_tail = extra_tail
        self.seq = 0
        self.sig_seq = 1
        self.nonce = None

    def write(self, data):
        self.commands.append(bytes(data))
        if self.partial:
            return 7
        ticket, nonce = struct.unpack_from('<II', data, 8)
        if not self.silent:
            if data[:4] == b'SGA1':
                self.nonce = nonce
                packet = ack(ticket, nonce) + signature(100, self.sig_seq, nonce=nonce)
            else:
                count = 102 + int(self.clock.now * 60)
                packet = stats(ticket, nonce, self.seq, int(self.clock.now * CORE_HZ), count)
                self.seq += 1
                self.sig_seq += 1
                packet += signature(count - 1, self.sig_seq, nonce=self.nonce)
                if self.extra_tail:
                    self.sig_seq += 1
                    packet += signature(count - 1, self.sig_seq, nonce=self.nonce)
            if self.corrupt:
                packet = packet[:12] + bytes([packet[12] ^ 1]) + packet[13:]
            self.queue.extend(packet)
        return len(data)

    def read(self, size):
        self.clock.now += 0.01
        size = min(size, 17)
        data = bytes(self.queue[:size])
        del self.queue[:size]
        return data


class ToolTests(unittest.TestCase):
    def check_rejected(self, raw, manifest, text):
        manifest['RawSHA256'] = hashlib.sha256(raw).hexdigest()
        with self.assertRaisesRegex(ValueError, text):
            analyze(raw, manifest, uninterrupted_reset_epoch=True)

    def test_valid_nominal_measurement_and_repeat_crosscheck(self):
        raw, manifest = fixture()
        result = analyze(raw, manifest, uninterrupted_reset_epoch=True)
        self.assertEqual(result['Rates']['presented_fps_nominal'], 60)
        self.assertEqual(result['SignatureCrosscheck']['RepeatedFrameIDPackets'], 1)
        self.assertFalse(result['HardwarePassClaim'])
        self.assertFalse(result['Sustained60FPSPassClaim'])

    def test_actual_5994_is_not_rounded_to_60(self):
        raw, manifest = fixture(last_tick=2 * CORE_HZ + CORE_HZ // 1000)
        result = analyze(raw, manifest, uninterrupted_reset_epoch=True)
        self.assertAlmostEqual(result['Rates']['presented_fps_nominal'], 60000 / 1001)

    def test_every_packet_split_and_one_byte_stream(self):
        raw, _ = fixture()
        expected = WireParser().feed(raw)
        for split in range(len(raw) + 1):
            parser = WireParser()
            self.assertEqual(parser.feed(raw[:split]) + parser.feed(raw[split:]), expected)
            parser.finish()
        parser = WireParser()
        actual = []
        for byte in raw:
            actual.extend(parser.feed(bytes([byte])))
        parser.finish()
        self.assertEqual(actual, expected)

    def test_epoch_and_identity_required(self):
        raw, manifest = fixture()
        with self.assertRaisesRegex(ValueError, 'Operator must confirm'):
            analyze(raw, manifest)
        for field, value, message in (
            ('KnownCleanResetBoundaryAttested', False, 'boundary/reset epoch'),
            ('LoadedBitstreamSHA256OperatorSupplied', '0' * 64, 'bitstream'),
            ('RawSHA256', '0' * 64, 'SHA256'), ('Status', 'failed', 'incomplete'),
            ('ExpectedMode', 'raw', 'mismatch')):
            changed = copy.deepcopy(manifest)
            changed[field] = value
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, message):
                analyze(raw, changed, uninterrupted_reset_epoch=True)

    def test_never_resync_after_unknown_corrupt_or_truncated(self):
        raw, manifest = fixture()
        self.check_rejected(b'junk' + raw, manifest, 'Unknown packet boundary')
        self.check_rejected(raw[:-1], manifest, 'Truncated')
        changed = bytearray(raw)
        changed[20] ^= 1
        self.check_rejected(bytes(changed), manifest, 'Invalid SGK1')

    def test_missing_duplicate_or_unrelated_responses(self):
        raw, manifest = fixture()
        for altered in (raw + stats(3, 30, 2, 3 * CORE_HZ, 220),
                        raw[:-84], raw[:-84] + stats(3, 99, 1, 2 * CORE_HZ, 160)):
            with self.subTest(size=len(altered)):
                self.check_rejected(altered, copy.deepcopy(manifest), 'statistics response')

    def test_mode_gamma_fault_and_param_mismatches(self):
        raw, manifest = fixture()
        for tail in (stats(3, 30, 1, 2 * CORE_HZ, 160, mode=0),
                     stats(3, 30, 1, 2 * CORE_HZ, 160, mode=3),
                     stats(3, 30, 1, 2 * CORE_HZ, 160, param=123)):
            self.check_rejected(raw[:-84] + tail, copy.deepcopy(manifest), 'mismatch')
        for flag in (64, 1 << 8, 1 << 16, 1 << 24):
            altered, changed = fixture(flags=flag)
            self.check_rejected(altered, changed, 'Fault detail')

    def test_reset_stale_tick_and_frame_rollover(self):
        for tick in (0, CORE_HZ, CORE_HZ + (1 << 32)):
            raw, manifest = fixture(last_tick=tick)
            self.check_rejected(raw, manifest, 'measurement')
        raw, manifest = fixture()
        for tail, message in (
            (stats(3, 30, 0, 2 * CORE_HZ, 160), 'sequence'),
            (stats(3, 30, 1, 2 * CORE_HZ, 1), 'FrameID'),
            (stats(3, 30, 1, CORE_HZ + 50, 160), 'Counter delta')):
            self.check_rejected(raw[:-84] + tail, copy.deepcopy(manifest), message)
        raw = (ack() + signature(0xffffffff, 1) + stats(2, 20, 0, CORE_HZ, 100) +
               signature(1, 3) + stats(3, 30, 1, 2 * CORE_HZ, 160))
        self.check_rejected(raw, manifest, 'FrameID')

    def test_counter_modulo_wrap_is_bounded_and_not_frame_rollover(self):
        raw, manifest = fixture()
        # Counter rollover is valid if independent frame identities do not roll
        # over and the bounded delta is plausible within one uninterrupted epoch.
        def counter_packet(ticket, nonce, sequence, tick, count):
            packet = bytearray(stats(ticket, nonce, sequence, tick, 100, frame_id=100))
            struct.pack_into('<5I', packet, 56, count, count, count, 0, 0)
            packet[80:] = struct.pack('<I', zlib.crc32(packet[:80]))
            return bytes(packet)
        raw = (ack() + signature(99, 1) + counter_packet(2, 20, 0, CORE_HZ, (1 << 32) - 20) +
               signature(100, 2) + counter_packet(3, 30, 1, 2 * CORE_HZ, 40))
        manifest['RawSHA256'] = hashlib.sha256(raw).hexdigest()
        result = analyze(raw, manifest, uninterrupted_reset_epoch=True)
        self.assertEqual(result['Delta']['presented_frames'], 60)

    def test_repeats_without_fresh_frames_rejected(self):
        raw, manifest = fixture(first=100, last=100)
        self.check_rejected(raw, manifest, 'Repeated scans alone')

    def test_request_journal_requires_full_unique_writes(self):
        raw, manifest = fixture()
        for change, message in ((lambda m: m['Requests'][1].update(Outcome='pending'), 'full write'),
                                (lambda m: m['Requests'][1].update(PacketHex=make_stats(2, 10).hex()), 'nonce'),
                                (lambda m: m['Requests'][2].update(PacketHex=make_stats(1, 30).hex()), 'tickets')):
            changed = copy.deepcopy(manifest)
            change(changed)
            self.check_rejected(raw, changed, message)

    def test_fake_transport_collection_to_analysis(self):
        _, template = fixture()
        clock = FakeClock()
        transport = FakeTransport(clock, extra_tail=True)
        nonces = iter(range(100, 300))
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp) / 'run'
            manifest = collect(transport, directory, template, seconds=1, interval=0.25,
                               clock=clock, nonce_source=lambda: next(nonces))
            raw = (directory / 'camera-uart.raw.bin').read_bytes()
            result = analyze(raw, manifest, uninterrupted_reset_epoch=True)
            self.assertGreater(result['Delta']['presented_frames'], 0)
            self.assertEqual(manifest['UnfinishedTailBytes'], 0)
            self.assertEqual(len(transport.commands), len(manifest['Requests']))
            self.assertGreater(len(transport.queue), 0)  # Do not consume a new tail packet.
            with self.assertRaises(FileExistsError):
                collect(transport, directory, template)

    def test_transport_failure_preserves_evidence_and_never_retries(self):
        for kwargs, error in (({'partial': True}, ValueError),
                              ({'corrupt': True}, ValueError),
                              ({'silent': True}, TimeoutError)):
            _, template = fixture()
            clock = FakeClock()
            transport = FakeTransport(clock, **kwargs)
            with tempfile.TemporaryDirectory() as tmp:
                directory = Path(tmp) / 'run'
                with self.assertRaises(error):
                    collect(transport, directory, template, seconds=1, interval=0.25,
                            arm_timeout=0.5, clock=clock)
                manifest = json.loads((directory / 'capture.json').read_text())
                self.assertEqual(manifest['Status'], 'failed')
                self.assertEqual(len(transport.commands), 1)
                if kwargs.get('corrupt'):
                    self.assertGreater((directory / 'camera-uart.raw.bin').stat().st_size, 0)

    def test_cli_guard_before_serial_import_or_port_open(self):
        script = str(Path(__file__).with_name('aa_capture.py'))
        command = [sys.executable, script, '--port', 'DO_NOT_OPEN', '--out-dir', 'unused',
                   '--epoch-label', 'test', '--mode', 'corr', '--loaded-bitstream-sha256', AA_SHA256]
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn('Establish and attest', result.stderr)


if __name__ == '__main__':
    unittest.main(verbosity=2)
