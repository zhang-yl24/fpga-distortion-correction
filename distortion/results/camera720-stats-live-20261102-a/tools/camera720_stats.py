"""Decode experimental core-domain UART statistics; no serial port is opened.

Rates use a supplied nominal core frequency, not an independent time standard.
source_accepted counts accepted complete source frames, not sensor input frames.
unique_presented counts successful distinct completed scans, not HDMI refreshes.
This module does not authorize an FPGA image or identify it by truncated ID alone.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import struct
import zlib

MAGIC = b"PGFPS01\n"
LENGTH = 64
LAYOUT = struct.Struct("<8sBBHIQIIIIB3xQQI")
MASK32 = (1 << 32) - 1


def validate_frequency(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        raise ValueError("finite positive nominal core frequency required")


def decode_packet(packet: bytes) -> dict:
    if len(packet) != LENGTH:
        raise ValueError("one complete 64-byte statistics packet required")
    (magic, version, flags, length, sequence, ticks, accepted, processed,
     presented, underflows, fault, build_id, profile_id, crc) = LAYOUT.unpack(packet)
    if magic != MAGIC or version != 1 or length != LENGTH:
        raise ValueError("statistics framing/version/length differs")
    if flags & ~3 or packet[41:44] != bytes(3) or underflows != 0:
        raise ValueError("reserved statistics fields are nonzero")
    if not flags & 2 and (flags & 1 or fault):
        raise ValueError("unavailable status cannot carry failed/fault data")
    if zlib.crc32(packet[:60]) != crc:
        raise ValueError("statistics CRC32 mismatch")
    return {
        "Sequence": sequence, "CoreTicks": ticks,
        "SourceAccepted": accepted, "Processed": processed,
        "UniquePresented": presented,
        "UnderflowsAvailable": False, "Underflows": None,
        "StatusAvailable": bool(flags & 2),
        "Failed": bool(flags & 1) if flags & 2 else None,
        "Fault": fault if flags & 2 else None,
        "BuildID": f"{build_id:016x}", "ProfileID": f"{profile_id:016x}",
        "CRC32": f"{crc:08x}",
    }


class StreamDecoder:
    """Bounded resynchronization; malformed or partial packets never emit data."""
    def __init__(self):
        self.pending = bytearray()
        self.discarded_bytes = 0
        self.rejected_packets = 0

    def feed(self, data: bytes) -> list[dict]:
        self.pending.extend(data)
        records = []
        while self.pending:
            start = self.pending.find(MAGIC)
            if start < 0:
                keep = next((n for n in range(min(7, len(self.pending)), 0, -1)
                             if self.pending[-n:] == MAGIC[:n]), 0)
                remove = len(self.pending) - keep
                self.discarded_bytes += remove
                del self.pending[:remove]
                break
            if start:
                self.discarded_bytes += start
                del self.pending[:start]
            if len(self.pending) < 12:
                break
            if self.pending[8] != 1 or self.pending[10:12] != b"\x40\x00":
                self.rejected_packets += 1
                self.discarded_bytes += 1
                del self.pending[0]
                continue
            if len(self.pending) < LENGTH:
                break
            try:
                record = decode_packet(bytes(self.pending[:LENGTH]))
            except ValueError:
                self.rejected_packets += 1
                self.discarded_bytes += 1
                del self.pending[0]
            else:
                records.append(record)
                del self.pending[:LENGTH]
        return records


def rate_between(previous: dict, current: dict, nominal_core_hz: float) -> dict:
    validate_frequency(nominal_core_hz)
    result = {"RatesAvailable": False, "NominalCoreHz": nominal_core_hz,
              "IndependentTimeReference": False, "SensorInputFPSMeasured": False,
              "HDMIRefreshFPSMeasured": False, "UnderflowsAvailable": False,
              "AssumesContinuousResetEpoch": True, "ResetEpochContinuityProven": False}
    if any(previous[k] != current[k] for k in ("BuildID", "ProfileID")):
        return {**result, "Reason": "build_or_profile_changed"}
    ticks = current["CoreTicks"] - previous["CoreTicks"]
    sequence = (current["Sequence"] - previous["Sequence"]) & MASK32
    if ticks <= 0 or sequence == 0 or sequence >= 1 << 31:
        return {**result, "Reason": "reset_duplicate_or_out_of_order"}
    delta = {key: (current[key] - previous[key]) & MASK32
             for key in ("SourceAccepted", "Processed", "UniquePresented")}
    # No frame counter can legitimately advance faster than one per core edge.
    # This rejects apparent counter wrap caused by an unobserved reset/dropback.
    if any(value > ticks for value in delta.values()):
        return {**result, "Reason": "counter_discontinuity"}
    seconds = ticks / nominal_core_hz
    if not math.isfinite(seconds) or seconds <= 0:
        raise ValueError("nominal interval is outside finite numeric range")
    rates = {key: value / seconds for key, value in delta.items()}
    if any(not math.isfinite(value) for value in rates.values()):
        raise ValueError("nominal rate is outside finite numeric range")
    return {**result, "RatesAvailable": True, "CoreTickDelta": ticks,
            "NominalSeconds": seconds, "SequenceDelta": sequence,
            "SkippedTelemetrySamples": sequence - 1, "FrameDeltas": delta,
            "SourceAcceptedFPS": rates["SourceAccepted"],
            "ProcessedFPS": rates["Processed"],
            "UniquePresentedFPS": rates["UniquePresented"],
            "CounterDeltaAssumesFewerThan2To32EventsPerInterval": True,
            "StatusKnownAtBothSamples": previous["StatusAvailable"] and current["StatusAvailable"],
            "FaultObserved": previous["Failed"] is True or current["Failed"] is True,
            "TruncatedIDsNonzero": all(int(current[k], 16) != 0 for k in ("BuildID", "ProfileID")),
            "IdentityCryptographicallyVerified": False}


def read_file(path: Path, nominal_core_hz: float) -> dict:
    validate_frequency(nominal_core_hz)
    decoder, records = StreamDecoder(), []
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        while chunk := stream.read(4096):
            digest.update(chunk)
            records.extend(decoder.feed(chunk))
    intervals = [rate_between(a, b, nominal_core_hz) for a, b in zip(records, records[1:])]
    return {"Schema": "camera720-core-statistics-file-v1", "Input": str(Path(path).resolve()),
            "InputSHA256": digest.hexdigest(), "HardwareAccessed": False,
            "SerialPortOpened": False, "FPGAImageAuthorized": False,
            "NominalCoreHz": nominal_core_hz, "Records": records, "Intervals": intervals,
            "RejectedPackets": decoder.rejected_packets, "DiscardedBytes": decoder.discarded_bytes,
            "TrailingPartialBytes": len(decoder.pending),
            "Limits": "Experimental packet decoder. A file is not board provenance. IDs are 64-bit "
                      "labels requiring an external full-hash mapping. Core ticks use nominal clock "
                      "frequency. Underflows are unavailable; fault status is explicitly optional. "
                      "Rates assume no unobserved reset between samples: a reset followed by enough "
                      "lost packets can regain larger ticks, sequence and counts and is not identifiable "
                      "from this packet alone. Only observed regressions/discontinuities are rejected."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--nominal-core-hz", type=float, default=125000000)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    # Validate even when a file contains fewer than two complete records.
    if not math.isfinite(args.nominal_core_hz) or args.nominal_core_hz <= 0:
        parser.error("--nominal-core-hz must be finite and positive")
    report = read_file(args.input, args.nominal_core_hz)
    text = json.dumps(report, indent=2) + "\n"
    if args.output:
        with args.output.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
    else:
        print(text, end="")
    return 0 if report["Records"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
