"""Run actual independent output top and production System with explicit IP stubs.

Small32x16 geometry exercises ownership, pixel correctness and board control;
it is not a physical DDR/PLL/TX or native1080 throughput/clock-stop test.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import time
import zlib

import numpy as np
from PIL import Image

import generate_1080_core_vectors as cpu
from run_gamma_pipeline_d5_sim import tool
from simulation_tools import prepare_compile_sources, resolve_vivado_bin, verify_compile_sources

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "build/processed-output-integration"
COMPILE = (
    "rtl/mul32_pipe.v", "rtl/pixel_inverse_rotation.v", "rtl/bounded_brown_inverse_mapper.v",
    "rtl/bilinear_rgb.v", "rtl/ddr_read_arbiter.v", "rtl/ddr_video_reader.v", "rtl/video_async_fifo.v",
    "rtl/ddr_write_arbiter.v", "rtl/experimental/ddr_neighbour_cache_scatter4_rowpipe.v",
    "rtl/experimental/ddr_remap_sample_scatter4_rowpipe.v", "rtl/experimental/rotated_remap_core_gamma_scatter4.v",
    "rtl/experimental/adaptive_gamma_stream.v", "rtl/experimental/adaptive_gamma_tagged.v",
    "rtl/experimental/ddr_adaptive_result_writer.v", "rtl/experimental/pipeline_gamma_frame_engine_1080_scatter4.v",
    "rtl/experimental/lens1080_bank_core.v", "rtl/experimental/hdmi1080_capture_cdc.v",
    "rtl/experimental/hdmi1080_input_dma.v", "rtl/experimental/hdmi1080_input_write_link.v",
    "rtl/experimental/ddr_video_output_1080_board.v", "rtl/experimental/hdmi1080_video_system_cdc_reset.v",
    "rtl/experimental/processed_output_pattern.v", "board/processed_output_top.v",
    "tests/processed_output_ip_stubs.sv", "tests/tb_processed_output.sv",
)
HEADERS = ("rtl/experimental/gamma_curves.vh", "rtl/video_crc32.vh", "board/board1080-synthetic.vh")
HELPERS = ("tools/run_processed_output_sim.py", "tools/generate_1080_core_vectors.py",
           "tools/generate_continuous1080_vectors.py", "tools/generate-brown-vectors.py", "model/reference.py",
           "tools/simulation_tools.py", "tools/run_gamma_pipeline_d5_sim.py")
REPORT = "processed-output-simulation.json"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def crc(words):
    return zlib.crc32(np.asarray(words, dtype="<u2").tobytes()) & 0xffffffff


def header_bindings():
    bindings = {}
    for line in (ROOT / "tests/processed_output_ip_stubs.sv").read_text(encoding="utf-8").splitlines():
        if not line.startswith("// HEADER_BINDING "):
            continue
        item = json.loads(line[len("// HEADER_BINDING "):])
        raw = (ROOT / item["Path"]).read_text(encoding="utf-8-sig")
        start = re.search(r"\bmodule\s+" + item["Module"] + r"\b", raw).start()
        header = raw[start:raw.index(");", start) + 2]
        if hashlib.sha256(header.encode()).hexdigest() != item["HeaderSHA256"]:
            raise ValueError("explicit IP stub production header drift: " + item["Module"])
        if item["Module"] in bindings:
            raise ValueError("duplicate stub module")
        bindings[item["Module"]] = {**item, "FullReferenceSHA256": sha(ROOT / item["Path"]),
                                    "ProductionBodyCompiled": False}
    if set(bindings) != {"bringup_pll", "hdmi_tx_init", "ddr3_test"}:
        raise ValueError("exact three explicit high-level IP stubs required")
    return bindings


def fixtures(work):
    width, height = 32, 16
    y, x = np.indices((height, width), dtype=np.int64)
    cx, cy = (width - 1)*128, (height - 1)*128
    fx, fy = width*128, height*1152//5
    config = [cx, cy, cx, cy, fx, fy, ((1 << 38)+fx//2)//fx, ((1 << 38)+fy//2)//fy,
              0x51eb8, -0xf5c3, 0x20c5, 0x1062, -0xb78]
    checker = ((x >> 5) ^ (y >> 5)) & 1
    r = np.where(checker != 0, 20, 4)+(x & 7)
    g = 8+(y & 31)
    b = np.where(checker != 0, 4, 20)+(y & 7)
    source = ((r << 11) | (g << 5) | b).astype(np.uint16)
    source[((x & 31) == 0) | ((y & 31) == 0)] = 0x07e0
    source[(np.abs(x-width//2) <= (width//256 if width >= 256 else 0)) |
           (np.abs(y-height//2) <= (height//256 if height >= 256 else 0))] = 0xf800
    source[(x == 0) | (x == width-1) | (y == 0) | (y == height-1)] = 0xffff
    sx, sy, bad, radius = cpu.project_integer(x*256, y*256, config)
    mask = bad | (radius > 2*cpu.Q) | (sx <= -256) | (sy <= -256) | (sx >= width*256) | (sy >= height*256)
    scalar = cpu.scalar_oracle()
    for yy in range(height):
        for xx in range(width):
            px, py, pb = scalar.project(xx*256, yy*256, config)
            if (px, py, bool(pb)) != (int(sx[yy, xx]), int(sy[yy, xx]), bool(bad[yy, xx])):
                raise ValueError("independent scalar/vector coordinate mismatch")
    expected = cpu.tone(cpu.pack565(cpu.remap_fixed(cpu.expand565(source),
        np.where(mask, -(1 << 23), sx)/256., np.where(mask, -(1 << 23), sy)/256.)), mask, 0)
    statistics = {"MaskedPixels": int(mask.sum()), "UnmaskedPixels": int((~mask).sum()),
                  "ScalarCoordinateCrosschecks": width*height}
    for name, pixels in (("source", source), ("result", expected)):
        payload = pixels.astype("<u2").tobytes()
        (work / f"{name}-beats.mem").write_text("".join(f"{int.from_bytes(payload[i:i+32], 'little'):064x}\n" for i in range(0, len(payload), 32)), encoding="ascii")
    (work / "expected.mem").write_text("".join(f"{int(v):04x}\n" for v in expected.ravel()), encoding="ascii")
    (work / "oracle.vh").write_text(f"localparam [31:0] SOURCE_CRC=32'h{crc(source):08x},RESULT_CRC=32'h{crc(expected):08x};\n", encoding="ascii")
    Image.fromarray(cpu.expand565(source)).save(work / "synthetic-source.png")
    Image.fromarray(cpu.expand565(expected)).save(work / "expected-output.png")
    return expected, {"Width": width, "Height": height, "IntegerConfig": config,
                      "SourceCRC32": f"{crc(source):08X}", "ResultCRC32": f"{crc(expected):08X}",
                      "Statistics": statistics, "MaskedPixels": int(mask.sum()), "GammaEnabled": False}


def run(workdir, maximum_seconds):
    work = Path(workdir).resolve()
    if work.parent != BASE.resolve() or work.exists():
        raise ValueError("new direct child of build/processed-output-integration required")
    if not 30 <= maximum_seconds <= 600:
        raise ValueError("whole run deadline must be30..600 seconds")
    work.mkdir(parents=True, exist_ok=False)
    bindings = header_bindings()
    references = tuple(item["Path"] for item in bindings.values())
    source_hashes = {name: sha(ROOT / name) for name in (*COMPILE, *HEADERS, *HELPERS, *references)}
    report = {"Passed": False, "Schema": "processed-output-top-real-system-simulation-v1",
              "StartedUTC": datetime.now(timezone.utc).isoformat(), "MaximumSeconds": maximum_seconds,
              "SourceSHA256": source_hashes, "ExplicitStubBindings": bindings, "Commands": [],
              "ActualBoardTopExecuted": True, "ProductionSystemExecuted": True, "ProductionBankManagerExecuted": True,
              "RealOutputAsyncFIFO": True, "PhysicalIPExecuted": False, "HardwareAccessed": False, "PDSAccessed": False,
              "HDMIRXExecuted": False, "PhysicalInputExercised": False, "RTLResultUsedForGolden": False,
              "Limits": "Small32x16 synthetic test only. Stub PLL/DDR PHY/TX status; no physical timing, silicon, native1080 throughput, optical calibration or clock-stop recovery claim. Normal final drain uses test-only private DMA-grant withholding; top has no host stop API. Five runtime faults are injected at the first source AW, before source commit or an active display lease; sticky board faults persist until common reset. Active-display-lease fault isolation is not exercised."}
    fixture_hashes = {}
    started = time.monotonic()
    deadline = started+maximum_seconds
    try:
        expected, model = fixtures(work)
        report["Model"] = model
        stage_header = work / "board/board1080-synthetic.vh"
        stage_header.parent.mkdir()
        stage_header.write_bytes((ROOT / "board/board1080-synthetic.vh").read_bytes())
        fixture_hashes = {p.relative_to(work).as_posix(): sha(p) for p in work.rglob("*") if p.is_file()}
        report["FixtureSHA256"] = fixture_hashes
        compiled, relocated = prepare_compile_sources(ROOT, COMPILE, HEADERS, work)
        report["CompileBindings"] = relocated
        bin_dir = resolve_vivado_bin(ROOT.parent)
        for executable, argv, stage in (
                ("xvlog.bat", ["--sv", *map(str, compiled)], "compile"),
                ("xelab.bat", ["tb_processed_output", "-s", "processed_output", "--timescale", "1ps/1ps"], "elaborate"),
                ("xsim.bat", ["processed_output", "-runall", "-log", "simulation.log"], "simulate")):
            command = {"Stage": stage, "NativeArgv": [str(bin_dir / executable), *argv], "ReturnCode": None}
            report["Commands"].append(command)
            tool(bin_dir, executable, argv, work, deadline, stage)
            command["ReturnCode"] = 0
        log = (work / "simulation.log").read_text(encoding="utf-8", errors="replace")
        if "PASS processed output:" not in log or "$finish called" not in log or re.search(r"(?im)^\s*(?:fatal|error):", log):
            raise ValueError("full independent output integration completion marker missing")
        summary = json.loads((work / "summary.json").read_text(encoding="ascii"))
        exact = {"passed": True, "startup_cases": 4, "runtime_fault_cases": 5, "sticky_fault_cases": 5,
                 "held_aw_cases": 5, "fault_bus_drains": 5, "directed_normal_final_drain": True,
                 "runtime_fault_sticky_until_common_reset": True, "active_display_lease_fault_tested": False, "production_system_executed": True,
                 "physical_ip_executed": False}
        if any(type(summary.get(k)) is not type(v) or summary[k] != v for k, v in exact.items()):
            raise ValueError("production ownership/normal drain/fault coverage differs")
        if any(summary.get(k, 0) <= 0 for k in ("repeat_scans", "source_bank_reuses", "result_bank_reuses")) or summary["unique_frames_scanned"] < 8:
            raise ValueError("production bank reuse/eight unique frames/repeat scan coverage absent")
        if not summary["frames_committed"] == summary["frames_processed"] == summary["frames_published"]:
            raise ValueError("normal production frame counters differ")
        with (work / "scanned-pixels.csv").open(encoding="ascii", newline="") as stream:
            rows = list(csv.DictReader(stream))
        if len(rows) != summary["scanned_pixels"] or len(rows) % 512:
            raise ValueError("actual scan dump is incomplete")
        for i, row in enumerate(rows):
            if int(row["pixel"]) != i % 512 or int(row["rgb565"], 16) != int(expected.ravel()[i % 512]):
                raise ValueError("postparsed actual RGB pixels differ from independent CPU reference")
        verify_compile_sources(ROOT, COMPILE, HEADERS, work, relocated)
        report.update(Passed=True, Summary=summary, ActualDERGBScanned=True, ActualScanPixelsCompared=len(rows))
    except (Exception, KeyboardInterrupt) as exc:
        report["Error"] = type(exc).__name__ + ": " + str(exc)
    finally:
        report["SourceSHA256After"] = {name: sha(ROOT / name) for name in source_hashes}
        report["FixtureSHA256After"] = {name: sha(work / name) for name in fixture_hashes}
        if report["SourceSHA256After"] != source_hashes or report["FixtureSHA256After"] != fixture_hashes:
            report.update(Passed=False, SourceOrFixtureDrift=True)
        report["ElapsedSeconds"] = round(time.monotonic()-started, 3)
        report["LogSHA256"] = {p.name: sha(p) for p in work.glob("*.log")}
        report["ResultSHA256"] = {p.name: sha(p) for p in work.iterdir() if p.is_file() and p.name in ("summary.json", "events.csv", "scanned-pixels.csv")}
        (work / REPORT).write_text(json.dumps(report, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({"Passed": report["Passed"], "Error": report.get("Error"), "Report": str(work / REPORT)}))
    return 0 if report["Passed"] else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workdir", type=Path, required=True)
    parser.add_argument("--maximum-seconds", type=int, default=240)
    args = parser.parse_args()
    return run(args.workdir, args.maximum_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
