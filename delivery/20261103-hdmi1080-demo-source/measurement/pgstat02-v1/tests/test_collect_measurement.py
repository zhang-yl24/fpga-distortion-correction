"""Pure memory fixtures: no serial import/open, real waiting or device access."""
from pathlib import Path
import copy
import hashlib
import struct
import sys
import unittest
import zlib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "host"))
import collect_measurement as collector
from measurement_report import analyze_run
import fixture_packets as fixtures


class Clock:
    def __init__(self): self.now = 0.0
    def __call__(self): return self.now


class Sink:
    def __init__(self):
        self.raw = bytearray()
        self.records = {kind: [] for kind in ("rx", "tx", "events")}
        self.states = []
    def write_raw(self, data): self.raw.extend(data)
    def emit(self, kind, value): self.records[kind].append(copy.deepcopy(value))
    def save(self, value): self.states.append(copy.deepcopy(value))


class Transport:
    def __init__(self, clock, first, second, last, pattern=None, partial=False):
        self.clock = clock
        self.responses = (first, second, last)
        self.writes = []
        self.buffer = bytearray()
        self.pattern = pattern or [4096]
        self.reads = 0
        self.is_open = True
        self.partial = partial
    @property
    def in_waiting(self): return len(self.buffer)
    def write(self, data):
        self.writes.append(bytes(data))
        if self.partial: return len(data) - 1
        self.buffer.extend(self.responses[len(self.writes) - 1])
        return len(data)
    def flush(self): pass
    def read(self, count):
        if not self.buffer:
            self.clock.now += .05
            return b""
        self.clock.now += .001
        count = min(count, len(self.buffer), self.pattern[self.reads % len(self.pattern)])
        self.reads += 1
        data = bytes(self.buffer[:count])
        del self.buffer[:count]
        return data
    def close(self): self.is_open = False


class CollectorTests(unittest.TestCase):
    def setUp(self):
        _, self.manifest, self.plan, self.attestation, _ = fixtures.run()
        self.prefix = b"OLD-PARTIAL-PAYLOAD-SGK1-PGSTAT02"
        self.attestation["known_packet_boundary_offset"] = len(self.prefix)
        old_body = struct.pack("<4sBBHIII", b"SGK1", 1, 1, 24, 99, 123, 2)
        self.old_ack = old_body + struct.pack("<I", zlib.crc32(old_body))
        self.old_signature = fixtures.signature(frame_id=1999)
        first_stats = dict(ticks=(1 << 32) - 100000000, sequence=17, frame_id=2000,
                           counts=(401, 400, 350, 100, 2), raw_cycles=6249999)
        last_stats = dict(ticks=first_stats["ticks"] + 2500000000, sequence=18, frame_id=2400,
                          counts=(801, 800, 650, 400, 4), raw_cycles=6374999)
        self.first = self.prefix + self.old_ack + self.old_signature + fixtures.ack() + fixtures.signature(embedded_magic=True)
        self.second = fixtures.stat(0, **first_stats) + fixtures.signature(frame_id=2001)
        self.tail = b"PGSIG001\x01"
        self.last = fixtures.signature(frame_id=2400) + fixtures.stat(1, **last_stats) + self.tail

    def session(self, transport, sink, clock, attestation=None):
        return collector.CaptureSession(transport, sink, self.plan, self.manifest,
            self.attestation if attestation is None else attestation,
            capture_kind="SYNTHETIC_OFFLINE_FIXTURE", clock=clock)

    def healthy(self, pattern):
        clock, sink = Clock(), Sink()
        transport = Transport(clock, self.first, self.second, self.last, pattern)
        meta = self.session(transport, sink, clock).run()
        raw = bytes(sink.raw)
        meta["raw_sha256"] = hashlib.sha256(raw).hexdigest()
        self.assertEqual(meta["outcome"], "CAPTURE_COMPLETE_TWO_SNAPSHOTS")
        self.assertEqual(transport.writes, [bytes.fromhex(c["Hex"]) for c in self.plan["Commands"]])
        self.assertEqual(meta["requests_attempted"], 3)
        self.assertEqual(meta["responses_selected"], 2)
        self.assertEqual(meta["selected_ack_start_offset"], len(self.prefix) + len(self.old_ack) + len(self.old_signature))
        self.assertEqual(raw[meta["validated_analysis_end_offset"]:], self.tail)
        delay = meta["TX_requests"][2]["host_seconds"] - meta["selected_snapshots"][0]["host_seconds"]
        self.assertGreaterEqual(delay, 20)
        self.assertLess(delay, 20.1)
        self.assertFalse(transport.is_open)
        for snapshot in meta["selected_snapshots"]:
            decoded = snapshot["decoded"]
            self.assertNotIn("last_process_seconds_nominal", decoded)
            self.assertNotIn("last_process_cycles_including_final_edge", decoded)
            self.assertIn("legacy_seconds_candidate_no_wrap_unverified", decoded)
            self.assertIn("raw+1", decoded["decoded_scope"])
        report = analyze_run(raw, self.manifest, self.plan, self.attestation, meta)
        self.assertEqual(report["status"], "PASS_OFFLINE_SYNTHETIC_FIXTURE")
        self.assertEqual(report["core_window"]["seconds_nominal"], 20)
        self.assertNotIn("serial", sys.modules)

    def test_prefix_embedded_magic_and_retained_tail(self):
        self.healthy([4096])

    def test_fragmented_stream_same_exact_three_commands(self):
        self.healthy([1, 3, 7, 2, 19])

    def test_strict_CRC_stop_preserves_complete_incoming_read(self):
        bad = bytearray(fixtures.signature())
        bad[90] ^= 1
        incoming = self.prefix + fixtures.ack() + bytes(bad) + b"UNPARSED-TAIL"
        clock, sink = Clock(), Sink()
        transport = Transport(clock, incoming, b"", b"")
        meta = self.session(transport, sink, clock).run()
        self.assertEqual(meta["outcome"], "STOPPED_STRICT_PARSER")
        self.assertEqual(bytes(sink.raw), incoming)
        self.assertEqual(len(transport.writes), 1)
        self.assertFalse(transport.is_open)

    def test_partial_command_write_is_uncertain_and_not_retried(self):
        clock, sink = Clock(), Sink()
        transport = Transport(clock, b"", b"", b"", partial=True)
        meta = self.session(transport, sink, clock).run()
        self.assertEqual(meta["outcome"], "STOPPED_TX_UNCERTAIN")
        self.assertEqual(len(transport.writes), 1)
        self.assertTrue(meta["TX_requests"][0]["outcome_uncertain"])
        self.assertFalse(transport.is_open)

    def test_missing_boundary_evidence_rejected_before_TX(self):
        clock, sink = Clock(), Sink()
        transport = Transport(clock, b"", b"", b"")
        with self.assertRaises(ValueError):
            self.session(transport, sink, clock, dict(self.attestation, boundary_evidence=""))
        self.assertEqual(transport.writes, [])
        self.assertNotIn("serial", sys.modules)


if __name__ == "__main__":
    unittest.main()
