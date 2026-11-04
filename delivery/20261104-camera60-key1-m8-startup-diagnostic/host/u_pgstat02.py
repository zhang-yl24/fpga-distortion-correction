"""Offline U PGSTAT02 decoding and pure request builders. No serial access."""
import argparse
import json
import struct
import zlib
from pathlib import Path

HEADER = b"PGSTAT02\x02\x01\x54\x00"
ENVELOPES = (
    (b"PGSTAT02", 84, 12, 10, 80, b""),
    (b"PGSIG001", 128, 14, 12, 120, b"SG01"),
    (b"SGK1", 24, 8, 6, 20, b""),
    (b"SGA1", 24, 8, 6, 20, b""),
    (b"SGT1", 24, 8, 6, 20, b""),
)

class PacketError(ValueError):
    pass

def _crc(data):
    return zlib.crc32(data) & 0xFFFFFFFF

def _u32(data, offset):
    return int.from_bytes(data[offset:offset + 4], "little")

def decode_packet(packet):
    """Exact U packet; nonzero fault bytes are valid diagnostic data."""
    p = bytes(packet)
    if len(p) != 84:
        raise PacketError("length: expected exactly 84 bytes")
    if p[:12] != HEADER:
        raise PacketError("header: magic/version/domain/length mismatch")
    if _crc(p[:80]) != _u32(p, 80):
        raise PacketError("crc: PGSTAT02")
    valid = _u32(p, 20)
    completion = dict(zip(
        ("cycles_raw", "frame_id", "param_id", "mode"),
        (_u32(p, n) for n in (40, 44, 48, 52))))
    issues = []
    if valid not in (6, 7):
        issues.append("unexpected_U_valid_flags")
    if not (valid & 1) and any(completion.values()):
        issues.append("nonzero_completion_when_last_valid_is_clear")
    if completion["mode"] > 3:
        issues.append("unexpected_U_mode")
    if _u32(p, 24) == 0:
        issues.append("zero_core_hz")
    return {
        "ticket": _u32(p, 12), "nonce": _u32(p, 16),
        "valid_flags": valid, "last_completion_valid": bool(valid & 1),
        "counters_valid": bool(valid & 2), "ticks_valid": bool(valid & 4),
        "core_hz": _u32(p, 24), "sequence": _u32(p, 28),
        "core_ticks": int.from_bytes(p[32:40], "little"),
        "completion_raw": completion,
        "last_completion": completion.copy() if valid & 1 else None,
        "captured": _u32(p, 56), "processed": _u32(p, 60),
        "presented": _u32(p, 64), "repeated": _u32(p, 68),
        "dropped": _u32(p, 72), "state_flags": p[76],
        "fault": p[77], "input_fault": p[78], "controller_fault": p[79],
        "state_word_raw": _u32(p, 76), "schema_issues": issues,
    }

def _build_request(magic, ticket, nonce):
    for name, value in (("ticket", ticket), ("nonce", nonce)):
        if type(value) is not int or not 1 <= value <= 0xFFFFFFFF:
            raise ValueError(f"{name}: require explicit nonzero uint32")
    body = struct.pack("<4sBBHIII", magic, 1, 1, 24, ticket, nonce, 0)
    return body + _crc(body).to_bytes(4, "little")

def make_arm(ticket, nonce):
    """Build SGA1; a load nonce is not a hardware reset epoch."""
    return _build_request(b"SGA1", ticket, nonce)

def request(ticket, nonce):
    """Build SGT1; an echo nonce provides request correlation only."""
    return _build_request(b"SGT1", ticket, nonce)

class StreamDecoder:
    """Incremental framing; retains damaged/unknown/truncated spans."""
    def __init__(self):
        self._buffer = bytearray()
        self._offset = 0
        self._finished = False
        self.records = []

    def _consume(self, count):
        del self._buffer[:count]
        self._offset += count

    def _gap(self, count, reason):
        preview = bytes(self._buffer[:min(count, 16)]).hex()
        if self.records and self.records[-1]["kind"] == "gap":
            previous = self.records[-1]
            if previous["offset"] + previous["length"] == self._offset:
                previous["length"] += count
                if reason not in previous["reasons"]:
                    previous["reasons"].append(reason)
                self._consume(count)
                return
        self.records.append({"kind": "gap", "offset": self._offset,
            "length": count, "reasons": [reason], "initial_hex": preview})
        self._consume(count)

    def feed(self, data, *, final=False):
        if self._finished:
            raise ValueError("feed after final")
        self._buffer.extend(data)
        while self._buffer:
            envelope = next(
                (e for e in ENVELOPES if self._buffer.startswith(e[0])), None)
            if envelope is None:
                if not final and any(
                        e[0].startswith(bytes(self._buffer)) for e in ENVELOPES):
                    break
                self._gap(1, "unknown_or_unframed_byte")
                continue
            magic, size, header_size, length_offset, body_size, tail = envelope
            if len(self._buffer) < header_size:
                if not final:
                    break
                self._gap(len(self._buffer), "truncated_header")
                continue
            declared = int.from_bytes(
                self._buffer[length_offset:length_offset + 2], "little")
            header_ok = declared == size
            if magic == b"PGSTAT02":
                header_ok = header_ok and self._buffer[:12] == HEADER
            if not header_ok:
                self._gap(1, "invalid_header")
                continue
            if len(self._buffer) < size:
                if not final:
                    break
                self._gap(len(self._buffer), "truncated_packet")
                continue
            packet = bytes(self._buffer[:size])
            if (_crc(packet[:body_size]) != _u32(packet, body_size)
                    or (tail and packet[-len(tail):] != tail)):
                self._gap(1, "invalid_crc_or_tail")
                continue
            record = {"kind": "pgstat02" if magic == b"PGSTAT02" else "opaque",
                      "offset": self._offset, "length": size}
            if magic == b"PGSTAT02":
                record["packet"] = decode_packet(packet)
            else:
                record.update(magic=magic.decode("ascii"), framing_only=True)
            self.records.append(record)
            self._consume(size)
        if final:
            self._finished = True

    def finish(self):
        self.feed(b"", final=True)

    def report(self):
        stats = [r for r in self.records if r["kind"] == "pgstat02"]
        gaps = [r for r in self.records if r["kind"] == "gap"]
        return {
            "format": "U-PGSTAT02-offline-diagnostic-v1",
            "finalized": self._finished, "consumed_bytes": self._offset,
            "pending_bytes": len(self._buffer), "pgstat02_count": len(stats),
            "clean_framing": self._finished and bool(self.records) and not gaps,
            "measurement_eligible": False,
            "measurement_reason": (
                "Offline decoding does not establish loaded-image identity, "
                "reset continuity, source timing, or a measurement epoch."),
            "fps": None, "latency": None, "records": self.records}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wire", required=True, type=Path,
                        help="saved binary stream; no serial access")
    args = parser.parse_args()
    decoder = StreamDecoder()
    with args.wire.open("rb") as stream:
        while True:
            chunk = stream.read(65536)
            if not chunk:
                break
            decoder.feed(chunk)
    decoder.finish()
    print(json.dumps(decoder.report(), indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
