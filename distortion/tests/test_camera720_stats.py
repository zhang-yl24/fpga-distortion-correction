"""Independent binary fixtures; never opens UART/JTAG or runs native EDA."""
from pathlib import Path
import struct
import sys
import tempfile
import unittest
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import camera720_stats as stats


def packet(*, sequence=0, ticks=125000000, counts=(15, 14, 13), flags=0,
           fault=0, build=0x123456789abcdef0, profile=0xfedcba9876543210):
    # Build the wire reference by offsets, independently of decoder's struct.
    raw = bytearray(64)
    raw[:8] = b"PGFPS01\n"
    raw[8:10] = bytes((1, flags))
    struct.pack_into("<H", raw, 10, 64)
    struct.pack_into("<I", raw, 12, sequence)
    struct.pack_into("<Q", raw, 16, ticks)
    struct.pack_into("<III", raw, 24, *counts)
    raw[40] = fault
    struct.pack_into("<QQ", raw, 44, build, profile)
    return recalculate(raw)


def recalculate(raw):
    raw = bytearray(raw)
    struct.pack_into("<I", raw, 60, zlib.crc32(raw[:60]))
    return bytes(raw)


class StatisticsProtocolTest(unittest.TestCase):
    def test_complete_packet_and_unavailable_status_are_distinct(self):
        result = stats.decode_packet(packet())
        self.assertEqual(result["SourceAccepted"], 15)
        self.assertEqual(result["BuildID"], "123456789abcdef0")
        self.assertIsNone(result["Underflows"])
        self.assertFalse(result["UnderflowsAvailable"])
        self.assertIsNone(result["Failed"])
        self.assertIsNone(result["Fault"])

    def test_valid_failed_status_is_retained(self):
        result = stats.decode_packet(packet(flags=3, fault=0xA2))
        self.assertTrue(result["Failed"])
        self.assertEqual(result["Fault"], 0xA2)

    def test_unknown_reserved_and_unavailable_fields_rejected_even_with_crc(self):
        for offset, value in ((8, 2), (9, 4), (9, 1), (10, 65), (36, 1), (40, 2), (42, 1)):
            with self.subTest(offset=offset, value=value):
                raw = bytearray(packet())
                raw[offset] = value
                with self.assertRaises(ValueError):
                    stats.decode_packet(recalculate(raw))

    def test_every_single_bit_error_is_rejected(self):
        original = packet(flags=3, fault=0xA2)
        for bit in range(64 * 8):
            raw = bytearray(original)
            raw[bit // 8] ^= 1 << (bit % 8)
            with self.assertRaises(ValueError):
                stats.decode_packet(raw)

    def test_all_truncations_emit_no_sample(self):
        for length in range(64):
            with self.subTest(length=length):
                raw = packet()[:length]
                with self.assertRaises(ValueError):
                    stats.decode_packet(raw)
                decoder = stats.StreamDecoder()
                self.assertEqual(decoder.feed(raw), [])

    def test_every_chunk_boundary_preserves_one_packet(self):
        raw = packet()
        for split in range(65):
            decoder = stats.StreamDecoder()
            records = decoder.feed(raw[:split]) + decoder.feed(raw[split:])
            self.assertEqual(records, [stats.decode_packet(raw)])
            self.assertEqual(len(decoder.pending), 0)

    def test_noise_corruption_and_midpacket_reset_resynchronize(self):
        good = packet()
        broken = bytearray(packet(sequence=2))
        broken[29] ^= 0x40
        data = b"noise" + good[:37] + good + broken + good + b"PGF"
        decoder, records = stats.StreamDecoder(), []
        for byte in data:
            records.extend(decoder.feed(bytes((byte,))))
        self.assertEqual(records, [stats.decode_packet(good)] * 2)
        self.assertEqual(decoder.rejected_packets, 2)
        self.assertEqual(bytes(decoder.pending), b"PGF")

    def test_nonmagic_noise_does_not_accumulate(self):
        decoder = stats.StreamDecoder()
        self.assertEqual(decoder.feed(b"x" * 100000), [])
        self.assertLessEqual(len(decoder.pending), 7)
        self.assertEqual(decoder.discarded_bytes, 100000)

    def test_file_parser_reports_partial_tail_and_never_claims_hardware(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "stream.bin"
            path.write_bytes(packet() + packet(sequence=1, ticks=250000000) + b"PGFPS")
            report = stats.read_file(path, 125000000)
        self.assertEqual(len(report["Records"]), 2)
        self.assertEqual(report["TrailingPartialBytes"], 5)
        self.assertFalse(report["HardwareAccessed"])
        self.assertFalse(report["FPGAImageAuthorized"])


class StatisticsRateTest(unittest.TestCase):
    def sample(self, **kwargs):
        return stats.decode_packet(packet(**kwargs))

    def test_rates_and_dropped_telemetry_are_not_video_drops(self):
        a = self.sample(ticks=125000000, counts=(10, 9, 8))
        b = self.sample(sequence=3, ticks=500000000, counts=(55, 39, 35))
        result = stats.rate_between(a, b, 125000000)
        self.assertEqual(result["SourceAcceptedFPS"], 15)
        self.assertEqual(result["ProcessedFPS"], 10)
        self.assertEqual(result["UniquePresentedFPS"], 9)
        self.assertEqual(result["SkippedTelemetrySamples"], 2)
        self.assertFalse(result["IndependentTimeReference"])
        self.assertFalse(result["SensorInputFPSMeasured"])
        self.assertFalse(result["StatusKnownAtBothSamples"])

    def test_counter_and_sequence_wrap_use_modular_delta(self):
        a = self.sample(sequence=0xffffffff, counts=(0xfffffffe, 0xffffffff, 0xfffffffd))
        b = self.sample(sequence=0, ticks=250000000, counts=(2, 3, 0))
        result = stats.rate_between(a, b, 125000000)
        self.assertEqual(result["FrameDeltas"], {"SourceAccepted": 4, "Processed": 4, "UniquePresented": 3})
        self.assertEqual(result["SequenceDelta"], 1)

    def test_clock_is_64bit_and_low_word_wrap_does_not_reset(self):
        a = self.sample(ticks=(1 << 32) - 50)
        b = self.sample(sequence=1, ticks=(1 << 32) + 50, counts=(16, 15, 14))
        self.assertEqual(stats.rate_between(a, b, 100)["NominalSeconds"], 1)

    def test_epoch_and_identity_changes_have_no_rate(self):
        a = self.sample(sequence=10)
        for kwargs in ({"sequence": 11, "ticks": 1}, {"sequence": 10, "ticks": 250000000},
                       {"sequence": 9, "ticks": 250000000},
                       {"sequence": 11, "ticks": 250000000, "build": 9},
                       {"sequence": 11, "ticks": 250000000, "profile": 9}):
            with self.subTest(kwargs=kwargs):
                self.assertFalse(stats.rate_between(a, self.sample(**kwargs), 125000000)["RatesAvailable"])

    def test_hidden_reset_cannot_be_claimed_identifiable_from_v1(self):
        # A reset plus missing early packets can produce the same two records
        # as an uninterrupted run. Neither monotonic ticks nor sequence proves
        # continuity; the API must carry the explicit assumption with its rate.
        a = self.sample(sequence=0, ticks=125000000, counts=(10, 9, 8))
        b = self.sample(sequence=2, ticks=375000000, counts=(30, 27, 24))
        result = stats.rate_between(a, b, 125000000)
        self.assertTrue(result["RatesAvailable"])
        self.assertTrue(result["AssumesContinuousResetEpoch"])
        self.assertFalse(result["ResetEpochContinuityProven"])

    def test_unobserved_counter_reset_not_claimed_as_four_billion_frames(self):
        a = self.sample(counts=(200, 200, 200))
        b = self.sample(sequence=1, ticks=250000000, counts=(1, 1, 1))
        result = stats.rate_between(a, b, 125000000)
        self.assertFalse(result["RatesAvailable"])
        self.assertEqual(result["Reason"], "counter_discontinuity")

    def test_fault_kept_visible_with_counter_rates(self):
        a = self.sample(flags=2)
        b = self.sample(sequence=1, ticks=250000000, flags=3, fault=0xA2)
        result = stats.rate_between(a, b, 125000000)
        self.assertTrue(result["RatesAvailable"])
        self.assertTrue(result["FaultObserved"])
        self.assertTrue(result["StatusKnownAtBothSamples"])

    def test_nominal_frequency_must_be_positive_finite(self):
        for value in (0, -1, float("nan"), float("inf"), True, "125000000"):
            with self.assertRaises(ValueError):
                stats.rate_between(self.sample(), self.sample(), value)

    def test_empty_file_still_validates_nominal_frequency(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "empty.bin"
            path.write_bytes(b"")
            with self.assertRaises(ValueError):
                stats.read_file(path, float("nan"))

    def test_extreme_frequency_cannot_emit_infinity(self):
        a = self.sample(ticks=1, counts=(0, 0, 0))
        b = self.sample(sequence=1, ticks=1001, counts=(1000, 1000, 1000))
        with self.assertRaises(ValueError):
            stats.rate_between(a, b, 1e-310)


if __name__ == "__main__":
    unittest.main()
