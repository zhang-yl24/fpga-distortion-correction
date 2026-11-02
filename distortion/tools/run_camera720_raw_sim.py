"""Bounded full720 raw/preview and unchanged real-I2C frontend simulations.

Synthetic DVP, DDR and accelerated UART byte sink only. No PDS or hardware.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import struct
import time
import zlib

import numpy as np
import prepare_camera720_raw_sources as source
from frame_protocol import FrameParser
from run_camera720_sensor_sim import run_tool, checked_log, FRONTEND_MARKERS
from simulation_tools import resolve_vivado_bin

ROOT = source.PROJECT
SOURCES = (
    "rtl/raw_camera_capture.v", "rtl/experimental/capture_warmup.v",
    "rtl/ddr_uart_frame.v", "rtl/rgb565_burst_pack.v", "rtl/video_async_fifo.v",
    "rtl/camera_live_bridge.v", "rtl/ddr_video_writer.v", "rtl/dvp_rgb565_capture.v",
    source.PREVIEW, "rtl/reg16_i2c.v", source.sensor.INIT,
    source.sensor.FRONTEND, source.sensor.MONITOR,
    "tests/tb_camera720_raw_capture.sv", "tests/tb_camera720_raw_preview.sv",
    "tests/tb_ov5640_current720_frontend.sv",
)
HEADERS = ("rtl/video_crc32.vh", source.sensor.ROM)
HELPERS = ("tools/prepare_camera720_raw_sources.py", "tools/run_camera720_raw_sim.py",
           "tools/prepare_camera720_sensor.py", "tools/run_camera720_sensor_sim.py",
           "tools/frame_protocol.py", "tools/simulation_tools.py")


def audit_wire(path):
    wire = Path(path).read_bytes()
    if len(wire) != 1843244:
        raise ValueError("complete720 wire length differs")
    magic, width, height, ident, count, crc, fmt, hcrc = struct.unpack("<8sHHIIIII", wire[:32])
    if (magic, width, height, ident, count, fmt) != (b"PGFRAME1", 1280, 720, 41, 1843200, 0x5651):
        raise ValueError("720 wire header differs")
    payload = wire[32:-12]
    if (zlib.crc32(wire[:28]) != hcrc or zlib.crc32(payload) != crc
            or wire[-12:-4] != b"PGEND001" or struct.unpack("<I", wire[-4:])[0] != crc):
        raise ValueError("720 wire CRC/trailer differs")
    expected = ((np.arange(921600, dtype=np.uint32) * 53) ^ 0x4321).astype("<u2")
    if not np.array_equal(np.frombuffer(payload, dtype="<u2"), expected):
        raise ValueError("one or more full720 pixels differ from independent source")
    parser = FrameParser()
    frames = []
    for offset in range(0, len(wire), 4093):
        frames.extend(parser.feed(wire[offset:offset + 4093]))
    if (len(frames) != 1 or parser.rejected or parser.discarded or parser.buffer
            or frames[0].payload != payload):
        raise ValueError("unchanged PGFRAME1 receiver did not recover exact full frame")
    return {"PayloadBytes": count, "WireBytes": len(wire), "PixelsCompared": 921600,
            "SourceCRC32": f"{crc:08X}", "HostParserPassed": True, "WireSHA256": source.sha(path)}


def run(work, maximum_seconds=1800):
    work = Path(work).absolute()
    base = (ROOT / "work/camera720-raw-sim").resolve()
    source.require(work == work.resolve() and work.parent == base and not work.exists(),
                   "fresh canonical direct child of work/camera720-raw-sim required")
    source.require(type(maximum_seconds) is int and 60 <= maximum_seconds <= 2400,
                   "whole simulation bound must be60..2400 seconds")
    roles = source.validate_sources()
    names = list(dict.fromkeys([*roles["Sources"], source.MANIFEST, source.PARENT_MANIFEST,
                                source.PARENT_TOP, *SOURCES, *HEADERS, *HELPERS]))
    hashes = {n: source.sha(ROOT / n) for n in names}
    work.mkdir(parents=True)
    report = {"Schema": "camera720-current-raw-simulation-v1", "Passed": False,
              "SourceSHA256": hashes, "HardwareAccessed": False, "PDSAccessed": False,
              "HardwareReleaseAllowed": False, "SyntheticOnly": True, "TestCases": [],
              "Limits": "Full raw pipeline, preview, and real403-action SCCB/frontend are separate tests. "
                        "Board top wiring is source-checked, not physical DDR/IO execution. Synthetic clocks, "
                        "DDR and accelerated UART sink do not measure camera FPS,20s UART, optical geometry or timing."}
    start = time.monotonic()
    try:
        compiled = work / "compiled"
        # Only copy include paths. Preserve frozen original bytes and bind every staged byte.
        copies = {}
        for name in (*SOURCES, *HEADERS):
            data = (ROOT / name).read_bytes()
            for header in HEADERS:
                for old in ("D:/English/FPGA/distortion/" + header, header):
                    literal = ('`include "' + old + '"').encode()
                    replacement = ('`include "' + (compiled / header).as_posix() + '"').encode()
                    data = data.replace(literal, replacement)
            path = compiled / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            copies[name] = {"Path": str(path), "SHA256": source.sha(path)}
        report["CompiledCopies"] = copies
        bin_dir = resolve_vivado_bin(ROOT.parent)
        deadline = start + maximum_seconds
        run_tool(bin_dir, "xvlog", ["--sv", *[str(compiled / n) for n in SOURCES]], work, deadline, "compile")
        cases = [
            ("tb_camera720_raw_capture", "raw", [], ("PASS current720 raw digital:", "PASS current720 raw admission:")),
            ("tb_camera720_raw_preview", "preview", [], ("PASS current720 preview:",)),
            ("tb_ov5640_current720_frontend", "sensor", [], FRONTEND_MARKERS),
            ("tb_ov5640_current720_frontend", "bad-line", ["-testplusarg", "bad_line"],
             ("PASS CURRENT720 frontend malformed line blocks admission despite configured registers",)),
        ]
        elaborated = set()
        for top, label, plusargs, markers in cases:
            if top not in elaborated:
                run_tool(bin_dir, "xelab", [top, "-s", top], work, deadline, "elaborate-" + label)
                elaborated.add(top)
            run_tool(bin_dir, "xsim", [top, "-runall", "-log", label + ".log", *plusargs],
                     work, deadline, "simulate-" + label)
            text = checked_log(work, label + ".log")
            if not all(m in text for m in markers) or "$finish called" not in text:
                raise ValueError("full required simulation markers missing: " + label)
            report["TestCases"].append({"Name": label, "Passed": True,
                                        "PassLines": [s for s in text.splitlines() if s.startswith("PASS ")]})
        report["WireAudit"] = audit_wire(work / "current720-raw-stream.bin")
        source.validate_sources()
        report["Passed"] = True
    except (Exception, KeyboardInterrupt) as error:
        report["Error"] = type(error).__name__ + ": " + str(error)
    finally:
        report["SourceSHA256After"] = {n: source.sha(ROOT / n) for n in names}
        if report["SourceSHA256After"] != hashes:
            report.update(Passed=False, SourceDrift=True)
        report["ElapsedSeconds"] = round(time.monotonic() - start, 3)
        report["LogSHA256"] = {p.name: source.sha(p) for p in work.glob("*.log")}
        path = work / "camera720-raw-simulation.json"
        path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"Passed": report["Passed"], "Error": report.get("Error"), "Report": str(path)}))
    return 0 if report["Passed"] else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workdir", type=Path, required=True)
    parser.add_argument("--maximum-seconds", type=int, default=1800)
    args = parser.parse_args()
    raise SystemExit(run(args.workdir, args.maximum_seconds))
