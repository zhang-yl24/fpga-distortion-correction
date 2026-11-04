import itertools
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "host"))
from u_pgstat02 import PacketError, StreamDecoder, decode_packet, make_arm, request

def oracle_crc(data):
    value = 0xFFFFFFFF
    for byte in data:
        value ^= byte
        for _ in range(8):
            value = (value >> 1) ^ (0xEDB88320 if value & 1 else 0)
    return value ^ 0xFFFFFFFF

def seal(body):
    return bytes(body) + oracle_crc(body).to_bytes(4, "little")

def put32(data, offset, value):
    data[offset:offset + 4] = value.to_bytes(4, "little")

def fixture(*, mode=3, param=0x708006B9, ticks=0xFEDCBA9876543210,
            fault=0, input_fault=0, controller_fault=0, valid=7):
    body = bytearray(80)
    body[:12] = b"PGSTAT02\x02\x01\x54\x00"
    for offset, value in ((12, 0x01020304), (16, 0x05060708), (20, valid),
            (24, 125000000), (28, 11), (40, 123), (44, 42),
            (48, param), (52, mode), (56, 101), (60, 100),
            (64, 88), (68, 4), (72, 2)):
        put32(body, offset, value)
    body[32:40] = ticks.to_bytes(8, "little")
    body[76:80] = bytes((0xA5, fault, input_fault, controller_fault))
    return seal(body)

def stream(data):
    decoder = StreamDecoder()
    decoder.feed(data)
    decoder.finish()
    return decoder.report()

def opaque_signature(inner):
    body = bytearray(120)
    body[:8] = b"PGSIG001"
    body[8:16] = b"\x01\x02\x01\x01\x80\x00\x08\x00"
    body[20:20 + len(inner)] = inner
    return seal(body) + b"SG01"

class DecoderTests(unittest.TestCase):
    def test_oracle_reference_and_values(self):
        self.assertEqual(oracle_crc(b"123456789"), 0xCBF43926)
        d = decode_packet(fixture())
        self.assertEqual(d["core_ticks"], 0xFEDCBA9876543210)
        self.assertEqual((d["captured"], d["processed"], d["state_flags"]),
                         (101, 100, 0xA5))
        self.assertEqual(d["last_completion"], {"cycles_raw": 123,
            "frame_id": 42, "param_id": 0x708006B9, "mode": 3})
        self.assertEqual(d["schema_issues"], [])

    def test_fault_bytes_cartesian_representatives(self):
        for f, i, c in itertools.product((0, 1, 0x80, 0xFF), repeat=3):
            d = decode_packet(fixture(fault=f, input_fault=i, controller_fault=c))
            self.assertEqual((d["fault"], d["input_fault"], d["controller_fault"]),
                             (f, i, c))
            self.assertEqual(d["state_word_raw"], 0xA5 | f<<8 | i<<16 | c<<24)
            self.assertEqual(d["schema_issues"], [])

    def test_dynamic_mode_param_and_uint64_maximum(self):
        for m, p in ((0, 0), (1, 0xE5CCCEB0), (2, 0xFFFFFFFF),
                     (3, 0x708006B9), (0xFFFFFFFF, 0x12345678)):
            d = decode_packet(fixture(mode=m, param=p, ticks=0xFFFFFFFFFFFFFFFF))
            self.assertEqual(d["completion_raw"]["mode"], m)
            self.assertEqual(d["completion_raw"]["param_id"], p)
            self.assertEqual(d["core_ticks"], 0xFFFFFFFFFFFFFFFF)
            self.assertEqual(d["schema_issues"],
                             ["unexpected_U_mode"] if m>3 else [])

    def test_unknown_mode_retains_faults_and_raw_data(self):
        d = decode_packet(fixture(mode=4, param=0xABCDEF01, fault=0x80,
                                  input_fault=0x40, controller_fault=0x20))
        self.assertEqual(d["last_completion"]["mode"], 4)
        self.assertEqual(d["last_completion"]["param_id"], 0xABCDEF01)
        self.assertEqual(d["schema_issues"], ["unexpected_U_mode"])
        self.assertEqual((d["fault"],d["input_fault"],d["controller_fault"]),
                         (0x80, 0x40, 0x20))

    def test_strict_header_with_recomputed_crc_and_exact_length(self):
        p = fixture()
        for offset in (0, 7, 8, 9, 10, 11):
            bad = bytearray(p[:80]); bad[offset] ^= 1
            with self.assertRaises(PacketError): decode_packet(seal(bad))
        for bad in (p[:-1], p+b"\x00"):
            with self.assertRaises(PacketError): decode_packet(bad)

    def test_every_single_bit_corruption(self):
        p = fixture()
        for bit in range(84*8):
            bad = bytearray(p); bad[bit//8] ^= 1<<(bit%8)
            with self.assertRaises(PacketError): decode_packet(bad)

    def test_invalid_completion_not_fabricated(self):
        d = decode_packet(fixture(valid=6))
        self.assertIsNone(d["last_completion"])
        self.assertEqual(d["completion_raw"]["frame_id"], 42)
        self.assertIn("nonzero_completion_when_last_valid_is_clear",
                      d["schema_issues"])
        body = bytearray(fixture(valid=6)[:80]); body[40:56] = bytes(16)
        d = decode_packet(seal(body))
        self.assertIsNone(d["last_completion"])
        self.assertEqual(d["schema_issues"], [])
        self.assertIn("unexpected_U_valid_flags",
                      decode_packet(fixture(valid=0x80000007))["schema_issues"])

    def test_all_two_chunk_splits_and_bytewise_input(self):
        p = fixture(); expected = stream(p)
        for split in range(len(p)+1):
            d = StreamDecoder(); d.feed(p[:split]); d.feed(p[split:]); d.finish()
            self.assertEqual(d.report(), expected)
        d = StreamDecoder()
        for byte in p: d.feed(bytes((byte,)))
        d.finish(); self.assertEqual(d.report(), expected)

    def test_resynchronization_gap_lengths_and_offsets(self):
        p = fixture(); bad = bytearray(p); bad[-1] ^= 0x80
        report = stream(b"\x00junk"+bytes(bad)+p+p[:35])
        stats = [r for r in report["records"] if r["kind"]=="pgstat02"]
        gaps = [r for r in report["records"] if r["kind"]=="gap"]
        self.assertEqual(len(stats), 1)
        self.assertEqual(stats[0]["offset"], 89)
        self.assertEqual(sum(r["length"] for r in gaps), 124)
        self.assertTrue(any("invalid_crc_or_tail" in r["reasons"] for r in gaps))
        self.assertTrue(any("truncated_packet" in r["reasons"] for r in gaps))
        self.assertFalse(report["clean_framing"])

    def test_valid_signature_hides_nested_packet(self):
        p = fixture(); report = stream(opaque_signature(p)+p)
        self.assertEqual(report["pgstat02_count"], 1)
        self.assertEqual([r["kind"] for r in report["records"]],
                         ["opaque", "pgstat02"])
        self.assertEqual(report["records"][-1]["offset"], 128)
        self.assertTrue(report["clean_framing"])

    def test_valid_ack_hides_cross_boundary_nested_packet(self):
        body = bytearray(fixture()[:80])
        ack = seal(b"SGK1\x01\x01\x18\x00"+body[:12])
        body[12:16] = ack[20:24]; nested = seal(body)
        prefix = ack+nested[16:]
        self.assertEqual(prefix[8:], nested)
        self.assertEqual(decode_packet(prefix[8:])["sequence"], 11)
        report = stream(prefix+fixture())
        stats = [r for r in report["records"] if r["kind"]=="pgstat02"]
        self.assertEqual(len(stats), 1)
        self.assertEqual(stats[0]["offset"], len(prefix))
        self.assertEqual(report["records"][0]["magic"], "SGK1")
        self.assertTrue(any(r["kind"]=="gap" for r in report["records"]))
        self.assertFalse(report["clean_framing"])

    def test_partial_magic_and_measurements_remain_unqualified(self):
        d = StreamDecoder(); d.feed(b"PGSTA")
        self.assertEqual(d.report()["pending_bytes"], 5)
        d.finish(); self.assertEqual(d.report()["records"][0]["length"], 5)
        with self.assertRaises(ValueError): d.feed(b"")
        report = stream(fixture())
        self.assertFalse(report["measurement_eligible"])
        self.assertIsNone(report["fps"]); self.assertIsNone(report["latency"])
        self.assertFalse(stream(b"")["clean_framing"])

    def test_request_fixed_body_and_independent_crc(self):
        suffix = bytes.fromhex("01011800040302010807060500000000")
        for builder, magic in ((make_arm,b"SGA1"), (request,b"SGT1")):
            p = builder(0x01020304,0x05060708); expected = magic+suffix
            self.assertEqual(p[:20],expected); self.assertEqual(len(p),24)
            self.assertEqual(int.from_bytes(p[20:],"little"),oracle_crc(expected))
            self.assertEqual(stream(p)["records"][0]["kind"],"opaque")
            for bad in (0,-1,0x100000000,True,1.0,"1",None):
                with self.assertRaises(ValueError): builder(bad,1)
                with self.assertRaises(ValueError): builder(1,bad)

if __name__ == "__main__":
    unittest.main()
