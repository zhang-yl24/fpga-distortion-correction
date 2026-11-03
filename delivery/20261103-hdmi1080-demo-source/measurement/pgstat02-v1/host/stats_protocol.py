"""PGSTAT01 passive internal measurements; never a physical HDMI latency probe.

Keep mixed-stream packet boundaries: a PGSTAT magic in a PGFRAME payload is
pixel data. No serial library is needed to decode an existing capture.
"""
from pathlib import Path
import argparse
import json
import struct
import zlib

MAGIC = b"PGSTAT01"
LIGHT_MAGIC = b"PGSTAT02"
LIGHT_BODY_BYTES = 80
LIGHT_PACKET_BYTES = 84
BODY_BYTES = 140
PACKET_BYTES = 144
WORD_FIELDS = (
    "last_process_cycles", "completed_frame_id", "completed_param_id", "completed_mode",
    "captured_frames", "processed_frames", "presented_frames", "scan_good_frames",
    "scan_repeat_frames", "scan_blank_frames", "dropped_frames", "overflow_frames",
    "no_free_frames", "last_presented_id", "last_drop_fault", "state_flags",
    "source_wait_cycles", "processing_cycles", "pending_cycles", "display_lease_cycles",
    "read_busy_cycles", "write_busy_cycles", "snapshot_busy_cycles", "stage_valid_mask", "reserved",
)
COUNTERS = WORD_FIELDS[4:13] + WORD_FIELDS[16:23]


def _completion_duration(result):
    # Keep the wire value and its legacy name unchanged. The bank's counter
    # omits the final successful-completion edge, so edge distance is raw+1,
    # provided no legacy uint32 overflow occurred. This is internal core time.
    result["last_process_cycles_legacy"] = result["last_process_cycles"]
    cycles = result["last_process_cycles"] + 1 if result["last_process_valid"] else None
    result["last_process_cycles_including_final_edge"] = cycles
    result["last_process_seconds_nominal"] = cycles / result["nominal_core_hz"] if cycles is not None else None


def request(ticket, nonce):
    if not (0 < ticket < 2**32 and 0 < nonce < 2**32):
        raise ValueError("ticket and nonce must be nonzero uint32")
    body = struct.pack("<4sBBHIII", b"SGT1", 1, 1, 24, ticket, nonce, 0)
    return body + struct.pack("<I", zlib.crc32(body))


def _decode_full(packet, *, ticket=None, nonce=None):
    if len(packet) != PACKET_BYTES:
        raise ValueError("PGSTAT01 length")
    if zlib.crc32(packet[:BODY_BYTES]) != struct.unpack_from("<I", packet, BODY_BYTES)[0]:
        raise ValueError("PGSTAT01 CRC")
    magic, version, domain, size, t, n, valid, hz, seq, ticks = struct.unpack_from("<8sBBHIIIIIQ", packet)
    if (magic, version, domain, size) != (MAGIC, 1, 1, PACKET_BYTES):
        raise ValueError("PGSTAT01 schema")
    if not t or not n or hz == 0 or valid & ~0xF or (valid & 0xE) != 0xE:
        raise ValueError("PGSTAT01 identity/validity")
    if (ticket is not None and t != ticket) or (nonce is not None and n != nonce):
        raise ValueError("stale or unrelated request identity")
    result = dict(magic=magic.decode(), version=version, domain="core_clk", packet_bytes=size,
                  ticket=t, nonce=n, valid_mask=valid, nominal_core_hz=hz,
                  sequence=seq, core_tick=ticks)
    result.update(zip(WORD_FIELDS, struct.unpack_from("<25I", packet, 40)))
    if result["stage_valid_mask"] or result["reserved"] or result["completed_mode"] & ~3 or result["state_flags"] & ~0xFF:
        raise ValueError("unsupported stage/reserved/mode flags")
    if not valid & 1 and any(result[k] for k in WORD_FIELDS[:4]):
        raise ValueError("invalid completion must have zero fields")
    result["last_process_valid"] = bool(valid & 1)
    _completion_duration(result)
    return result


def decode(packet, *, ticket=None, nonce=None):
    if packet[:8] != LIGHT_MAGIC:
        return _decode_full(packet, ticket=ticket, nonce=nonce)
    if len(packet) != LIGHT_PACKET_BYTES or zlib.crc32(packet[:80]) != struct.unpack_from("<I", packet, 80)[0]:
        raise ValueError("PGSTAT02 length/CRC")
    magic, version, domain, size, t, n, valid, hz, seq, ticks = struct.unpack_from("<8sBBHIIIIIQ", packet)
    if (version, domain, size) != (2, 1, 84) or not t or not n or not hz or valid & ~7 or valid & 6 != 6:
        raise ValueError("PGSTAT02 schema/identity/validity")
    if (ticket is not None and t != ticket) or (nonce is not None and n != nonce):
        raise ValueError("stale or unrelated request identity")
    keys = ("last_process_cycles", "completed_frame_id", "completed_param_id", "completed_mode",
            "captured_frames", "processed_frames", "presented_frames", "scan_repeat_frames", "dropped_frames", "state_flags")
    result = dict(magic=magic.decode(), version=version, domain="core_clk", packet_bytes=size,
                  ticket=t, nonce=n, valid_mask=valid, nominal_core_hz=hz, sequence=seq, core_tick=ticks)
    result.update(zip(keys, struct.unpack_from("<10I", packet, 40)))
    if result["completed_mode"] & ~3 or result["state_flags"] & ~0xFF:
        raise ValueError("unsupported flags")
    if not valid & 1 and any(result[k] for k in keys[:4]):
        raise ValueError("invalid completion must have zero fields")
    result["last_process_valid"] = bool(valid & 1)
    _completion_duration(result)
    result["stage_valid_mask"] = 0 # no stage timestamps exist in either profile
    result["omitted_fields"] = [k for k in WORD_FIELDS if k not in keys and k != "stage_valid_mask"]
    return result


def window(first, second, *, uninterrupted_reset_epoch=False):
    """Modulo32 deltas within one uninterrupted FPGA reset epoch.

    Explicit epoch confirmation is required: the hardware has no persistent
    boot identifier. Nonces identify requests, not reset epochs.
    """
    if not uninterrupted_reset_epoch:
        raise ValueError("confirm no FPGA reset occurred between snapshots")
    hz = first["nominal_core_hz"]
    if second["nominal_core_hz"] != hz or not (second["valid_mask"] & first["valid_mask"] & 4):
        raise ValueError("incompatible clock/measurement window")
    cycles = second["core_tick"] - first["core_tick"]
    if not (0 < cycles < 2**32):
        raise ValueError("window must be positive and shorter than one uint32 cycle wrap")
    if (second["sequence"] - first["sequence"]) % 2**32 == 0:
        raise ValueError("same snapshot")
    if first["magic"] != second["magic"]:
        raise ValueError("incompatible statistics profiles")
    delta = {key: (second[key] - first[key]) % 2**32 for key in COUNTERS if key in first and key in second}
    return dict(core_cycles=cycles, seconds_nominal=cycles / hz, delta=delta,
                processed_fps_nominal=delta["processed_frames"] * hz / cycles,
                new_presented_fps_nominal=delta["presented_frames"] * hz / cycles,
                occupancy={k: delta[k] / cycles for k in delta if k.endswith("_cycles")})


class MixedParser:
    """Strict incremental boundary parser for B4, snapshot, frames and stats.

    It does not resynchronize after errors: that could hide mixed-owner bytes.
    It returns (kind, parsed stats dict or original opaque packet).
    """
    def __init__(self):
        self.buffer = bytearray()

    def feed(self, data):
        self.buffer.extend(data)
        packets = []
        while len(self.buffer) >= 8:
            b = self.buffer
            magic = bytes(b[:8])
            if magic == MAGIC:
                size, body, kind = PACKET_BYTES, BODY_BYTES, "PGSTAT01"
            elif magic == LIGHT_MAGIC:
                size, body, kind = LIGHT_PACKET_BYTES, LIGHT_BODY_BYTES, "PGSTAT02"
            elif b[:4] == b"SGK1":
                size, body, kind = 24, 20, "SGK1"
            elif magic == b"PGSIG001":
                size, body, kind = 128, 120, "PGSIG001"
            elif magic == b"PGSNAP01":
                size, body, kind = 48, 44, "PGSNAP01"
            elif magic == b"PGFRAME1":
                if len(b) < 32:
                    break
                _, w, h, ident, count, source_crc, fmt, crc = struct.unpack_from("<8sHHIIIII", b)
                if not (0 < w <= 1920 and 0 < h <= 1080 and count == 2*w*h and fmt == 0x5651 and zlib.crc32(b[:28]) == crc):
                    raise ValueError("PGFRAME1 header")
                size, body, kind = 32 + count + 12, None, "PGFRAME1"
            else:
                raise ValueError(f"unknown/interleaved bytes at packet boundary: {bytes(b[:8]).hex()}")
            if len(b) < size:
                break
            packet = bytes(b[:size])
            if body is not None:
                if zlib.crc32(packet[:body]) != struct.unpack_from("<I", packet, body)[0]:
                    raise ValueError(kind + " CRC")
            else:
                payload = packet[32:-12]
                computed = zlib.crc32(payload)
                if packet[-12:-4] != b"PGEND001" or struct.unpack_from("<I", packet, size-4)[0] != computed or source_crc != computed:
                    raise ValueError("PGFRAME1 payload/trailer")
            packets.append((kind, decode(packet) if kind in ("PGSTAT01", "PGSTAT02") else packet))
            del b[:size]
        return packets

    def finish(self):
        if self.buffer:
            raise ValueError("truncated mixed-stream packet")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--wire", type=Path)
    group.add_argument("--request-out", type=Path)
    ap.add_argument("--ticket", type=lambda s: int(s, 0))
    ap.add_argument("--nonce", type=lambda s: int(s, 0))
    args = ap.parse_args()
    if args.request_out:
        if args.ticket is None or args.nonce is None:
            ap.error("--request-out requires --ticket and --nonce")
        args.request_out.write_bytes(request(args.ticket, args.nonce))
        return
    parser = MixedParser()
    packets = parser.feed(args.wire.read_bytes()); parser.finish()
    stats = [value for kind, value in packets if kind in ("PGSTAT01", "PGSTAT02")]
    if args.ticket is not None or args.nonce is not None:
        stats = [v for v in stats if (args.ticket is None or v["ticket"] == args.ticket) and
                 (args.nonce is None or v["nonce"] == args.nonce)]
        if len(stats) != 1:
            raise ValueError("expected exactly one matching request response")
    print(json.dumps(dict(packet_order=[k for k, _ in packets], stats=stats), indent=2))


if __name__ == "__main__":
    main()
