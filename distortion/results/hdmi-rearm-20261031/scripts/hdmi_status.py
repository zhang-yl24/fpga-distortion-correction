"""Decode PGHDMI01 status packets or receive them without transmitting UART data.

Status describes configuration and a digital input observer, not HDMI PHY lock,
colour format, physical timing or successful image processing. Replay remains
replay even when its bytes originally came from a board.
"""
from collections import Counter
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
import argparse
import hashlib
import json
import math
import re
import struct
import time
import zlib

MAGIC = b"PGHDMI01"
TRAILER = b"HM01"
PACKET_SIZE = 64
BUILD_TAG = 0x48444901
BUILD_TAG_V2 = 0x48444902
BUILD_TAG_V3 = 0x48444903
BAUD = 115200
FLAG_NAMES = (
    "cfg_snapshot_valid", "cfg_fresh", "cfg_pll_locked", "video_pll_locked",
    "rx_init_done", "all_init_done", "cfg_failed", "observer_released",
    "polarity_known", "input_qualified", "input_failed", "vs_inactive", "hs_inactive",
)


def decode_packet(packet):
    """Validate transport/version fields, then retain raw values and interpretation."""
    if len(packet) != PACKET_SIZE:
        raise ValueError("length")
    if packet[:8] != MAGIC:
        raise ValueError("magic")
    if packet[60:] != TRAILER:
        raise ValueError("trailer")
    if zlib.crc32(packet[:56]) != struct.unpack_from("<I", packet, 56)[0]:
        raise ValueError("crc32")
    build_tag = struct.unpack_from("<I", packet, 48)[0]
    if build_tag not in (BUILD_TAG, BUILD_TAG_V2, BUILD_TAG_V3):
        raise ValueError("build_tag")
    flags = struct.unpack_from("<H", packet, 16)[0]
    if flags & ~0x1FFF or packet[18] & 0xF0 or packet[47] & ~3:
        raise ValueError("reserved")
    if build_tag == BUILD_TAG and packet[52:56] != bytes(4):
        raise ValueError("reserved")
    if build_tag == BUILD_TAG_V2 and (packet[52] & 0xE0 or packet[53:56] != bytes(3)):
        raise ValueError("reserved")
    if build_tag == BUILD_TAG_V3 and (packet[52] & 0xE0 or packet[55] != 0):
        raise ValueError("reserved")
    freshness_mask = packet[52] if build_tag in (BUILD_TAG_V2, BUILD_TAG_V3) else None
    values = {
        "sequence": struct.unpack_from("<I", packet, 8)[0],
        "reference_ticks": struct.unpack_from("<I", packet, 12)[0],
        "flags": flags, "cfg_error": packet[18], "input_fault": packet[19],
        "width": struct.unpack_from("<H", packet, 20)[0],
        "height": struct.unpack_from("<H", packet, 22)[0],
        "pclk_edges": struct.unpack_from("<I", packet, 24)[0],
        "good_frames": struct.unpack_from("<I", packet, 28)[0],
        "bad_frames": struct.unpack_from("<I", packet, 32)[0],
        "cfg_snapshot_age": struct.unpack_from("<I", packet, 36)[0],
        "completed_transactions": struct.unpack_from("<I", packet, 40)[0],
        "last_address": struct.unpack_from("<H", packet, 44)[0],
        "last_value": packet[46], "last_meta": packet[47],
        "build_tag": build_tag, "crc32": f"{zlib.crc32(packet[:56]):08x}",
        "wire_hex": bytes(packet).hex(),
        "monitor_freshness_mask": freshness_mask,
        "vs_edge_count_ref": struct.unpack_from("<H", packet, 53)[0] if build_tag == BUILD_TAG_V3 else None,
        "monitor_freshness": None if freshness_mask is None else {
            "pclk": bool(freshness_mask & 0x01),
            "vsync": bool(freshness_mask & 0x02),
            "de": bool(freshness_mask & 0x04),
            "frame": bool(freshness_mask & 0x08),
            "snapshot": bool(freshness_mask & 0x10),
        },
    }
    decoded = {name: bool(flags & (1 << bit)) for bit, name in enumerate(FLAG_NAMES)}
    values["flags_decoded"] = decoded
    issues = []
    if decoded["cfg_fresh"] and not decoded["cfg_snapshot_valid"]:
        issues.append("fresh_without_snapshot")
    if decoded["input_qualified"] and (not decoded["observer_released"] or not decoded["polarity_known"] or decoded["input_failed"]):
        issues.append("inconsistent_input_qualification")
    if decoded["cfg_failed"] and (decoded["rx_init_done"] or decoded["all_init_done"]):
        issues.append("configuration_failure_with_completion")
    if decoded["all_init_done"] and not decoded["rx_init_done"]:
        issues.append("all_complete_without_rx_complete")
    values["semantic_issues"] = issues
    if not decoded["cfg_snapshot_valid"]:
        state = "configuration_snapshot_missing"
    elif not decoded["cfg_fresh"]:
        state = "configuration_snapshot_stale"
    elif decoded["cfg_failed"]:
        state = "i2c_failure"
    elif decoded["input_failed"]:
        state = "digital_input_fault"
    elif decoded["input_qualified"] and not issues:
        state = "digital_input_qualified"
    elif not decoded["rx_init_done"]:
        # RX sequencer can wait for input before setting init_over. These bits
        # alone cannot distinguish an absent cable from other startup waits.
        state = "waiting_for_input_or_configuration"
    elif not decoded["all_init_done"]:
        state = "waiting_for_transmitter_configuration"
    else:
        state = "waiting_for_digital_input_qualification"
    values["state"] = state
    values["pclk_observation_available"] = decoded["observer_released"] and decoded["polarity_known"]
    values["pclk_edges_observed"] = values["pclk_edges"] if values["pclk_observation_available"] else None
    values["last_transaction_is_read"] = bool(packet[47] & 1)
    values["last_transaction_target"] = "TX" if packet[47] & 2 else "RX"
    values["last_transaction_available"] = decoded["cfg_snapshot_valid"] and values["completed_transactions"] > 0
    # Transport CRC is not a physical-source or optical acceptance certificate.
    values.update(phy_lock=None, colour_format=None, physical_timing_verified=False,
                  frame_rate_measured=False, hardware_release_allowed=False)
    return values


class FrameParser:
    """Streaming recovery with at most 63 retained bytes after each feed."""
    def __init__(self):
        self.buffer = bytearray()
        self.rejected = 0
        self.noise_bytes = 0
        self.error_counts = Counter()
        self.accepted = 0

    def feed(self, data):
        if not isinstance(data, (bytes, bytearray, memoryview)):
            raise TypeError("feed expects bytes")
        view = memoryview(data).cast("B")
        offset = 0
        frames = []
        while offset < len(view):
            count = min(PACKET_SIZE - len(self.buffer), len(view) - offset)
            self.buffer.extend(view[offset:offset + count])
            offset += count
            while True:
                start = self.buffer.find(MAGIC)
                if start < 0:
                    # Keep a possible split magic prefix, never unbounded noise.
                    keep = min(len(MAGIC) - 1, len(self.buffer))
                    remove = len(self.buffer) - keep
                    self.noise_bytes += remove
                    del self.buffer[:remove]
                    break
                if start:
                    self.noise_bytes += start
                    del self.buffer[:start]
                if len(self.buffer) < PACKET_SIZE:
                    break
                try:
                    frame = decode_packet(bytes(self.buffer[:PACKET_SIZE]))
                except ValueError as error:
                    self.rejected += 1
                    self.error_counts[str(error)] += 1
                    self.noise_bytes += 1
                    del self.buffer[0]
                else:
                    frames.append(frame)
                    self.accepted += 1
                    del self.buffer[:PACKET_SIZE]
        return frames


def validate_serial_request(port_name, seconds):
    if not isinstance(port_name, str) or not re.fullmatch(r"COM[1-9][0-9]*", port_name, re.I):
        raise ValueError("an explicit Windows COM port is required")
    if type(seconds) not in (int, float) or not math.isfinite(seconds) or not 0 < seconds <= 30:
        raise ValueError("seconds must be finite and in (0, 30]")


def serial_chunks(port_name, seconds, *, serial_factory=None, monotonic=time.monotonic):
    """Bounded receive-only 115200/8N1; never assert DTR/RTS or write bytes."""
    validate_serial_request(port_name, seconds)
    if serial_factory is None:
        import serial
        serial_factory = serial.Serial
    port = serial_factory(port=None, baudrate=BAUD, bytesize=8, parity="N", stopbits=1,
                          timeout=0.1, write_timeout=1, xonxoff=False, rtscts=False, dsrdtr=False)
    port.dtr = False
    port.rts = False
    port.port = port_name.upper()
    try:
        port.open()
        deadline = monotonic() + seconds
        while monotonic() < deadline:
            data = port.read(512)
            if data:
                yield data
    finally:
        port.close()


def replay_chunks(path):
    with Path(path).open("rb") as stream:
        while chunk := stream.read(4096):
            yield chunk


def capture(output, *, replay=None, port=None, seconds=5):
    """Save a new receipt and, for live reception, the exact unmodified wire."""
    if (replay is None) == (port is None):
        raise ValueError("select exactly one of replay or port")
    if port is not None:
        validate_serial_request(port, seconds)
    output = Path(output).resolve()
    if output.suffix.lower() != ".json" or not output.parent.is_dir():
        raise ValueError("output must be a new .json file in an existing directory")
    raw_path = output.with_suffix(".raw.bin")
    if output.exists() or (port is not None and raw_path.exists()):
        raise FileExistsError("output files already exist; choose a new filename")
    parser = FrameParser()
    report = {"schema": "hdmi-status-receive-v1", "passed": False,
              "passed_scope": "packet_integrity_only",
              "source_kind": "offline_uart_replay" if replay is not None else "receive_only_uart",
              "hardware_accessed": False, "bytes_written": 0, "port": port,
              "baudrate": BAUD, "frames": [], "received_bytes": 0,
              "started_utc": datetime.now(timezone.utc).isoformat(),
              "hardware_release_allowed": False,
              "limits": "Decoded FPGA status only; not PHY lock, colour format, physical timing, image quality or end-to-end video acceptance."}
    digest = hashlib.sha256()
    with output.open("x", encoding="utf-8", newline="\n") as result_file:
        raw = None
        try:
            if replay is not None:
                report["replay_path"] = str(Path(replay).resolve())
                chunks = replay_chunks(replay)
            else:
                raw = raw_path.open("xb")
                report["raw_path"] = str(raw_path)
                # True means serial access attempted, not successful reception
                # or identification of the board running this protocol.
                report["hardware_accessed"] = True
                chunks = serial_chunks(port, seconds)
            with closing(chunks):
                for chunk in chunks:
                    digest.update(chunk)
                    report["received_bytes"] += len(chunk)
                    if raw is not None:
                        raw.write(chunk)
                    report["frames"].extend(parser.feed(chunk))
            report["passed"] = bool(report["frames"]) and parser.rejected == 0
        except Exception as error:
            report["error"] = type(error).__name__ + ": " + str(error)
        finally:
            if raw is not None:
                raw.close()
            report.update(wire_sha256=digest.hexdigest(), rejected_packets=parser.rejected,
                          error_counts=dict(parser.error_counts), noise_bytes=parser.noise_bytes,
                          trailing_bytes=len(parser.buffer), accepted_packets=parser.accepted,
                          ended_utc=datetime.now(timezone.utc).isoformat())
            json.dump(report, result_file, indent=2, ensure_ascii=False)
            result_file.write("\n")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--replay", type=Path)
    source.add_argument("--port")
    parser.add_argument("--seconds", type=float, default=5)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if not math.isfinite(args.seconds) or not 0 < args.seconds <= 30:
        parser.error("seconds must be finite and in (0, 30]")
    try:
        report = capture(args.output, replay=args.replay, port=args.port, seconds=args.seconds)
    except (OSError, ValueError) as error:
        parser.exit(1, str(error) + "\n")
    print(json.dumps({"passed": report["passed"], "accepted_packets": report["accepted_packets"],
                      "rejected_packets": report["rejected_packets"], "output": str(args.output),
                      "last_state": report["frames"][-1]["state"] if report["frames"] else None,
                      "error": report.get("error")}, ensure_ascii=False))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
