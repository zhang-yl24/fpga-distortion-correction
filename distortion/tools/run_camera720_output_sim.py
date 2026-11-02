"""Full 720p synthetic remap/DDR/bank/1080p30 scan regression; no hardware.

The stress intrinsics are deliberately synthetic. They are neither scaled VGA
calibration nor a claim that the current lens is calibrated in 720p mode.
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

import generate_1080_core_vectors as cpu
from run_gamma_pipeline_d5_sim import tool
from simulation_tools import prepare_compile_sources, resolve_vivado_bin, verify_compile_sources

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "work/camera720-output"
WIDTH, HEIGHT, FRAME_COUNT = 1280, 720, 3
PIXELS = WIDTH * HEIGHT
COMPILE = (
    "rtl/mul32_pipe.v", "rtl/pixel_inverse_rotation.v", "rtl/bounded_brown_inverse_mapper.v",
    "rtl/bilinear_rgb.v", "rtl/ddr_read_arbiter.v", "rtl/ddr_video_reader.v", "rtl/video_async_fifo.v",
    "rtl/experimental/ddr_neighbour_cache_scatter4_rowpipe.v",
    "rtl/experimental/ddr_remap_sample_scatter4_rowpipe.v",
    "rtl/experimental/rotated_remap_core_gamma_scatter4.v",
    "rtl/experimental/adaptive_gamma_stream.v", "rtl/experimental/adaptive_gamma_tagged.v",
    "rtl/experimental/ddr_adaptive_result_writer.v", "rtl/experimental/pipeline_gamma_frame_engine_1080_scatter4.v",
    "rtl/experimental/lens1080_bank_core.v", "rtl/experimental/ddr_video_output_1080_board.v",
    "tests/tb_camera720_output.sv",
)
HEADERS = ("rtl/experimental/gamma_curves.vh", "rtl/video_crc32.vh")
HELPERS = ("tools/run_camera720_output_sim.py", "tools/generate_1080_core_vectors.py",
           "tools/generate-brown-vectors.py", "model/reference.py", "tools/simulation_tools.py",
           "tools/run_gamma_pipeline_d5_sim.py", "tools/prepare_gamma_pipeline_d5.py")
MARKER = "PASS camera720 output:"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def crc(words):
    return f"{zlib.crc32(np.asarray(words, dtype='<u2').tobytes()) & 0xffffffff:08X}"


def write_mem(path, words, *, beats=False):
    with Path(path).open("x", encoding="ascii", newline="\n") as out:
        if beats:
            payload = np.asarray(words, dtype="<u2").tobytes()
            out.writelines(f"{int.from_bytes(payload[i:i+32], 'little'):064x}\n" for i in range(0, len(payload), 32))
        else:
            out.writelines(f"{int(word):04x}\n" for word in np.asarray(words).ravel())


def geometry():
    config = cpu.parameters(WIDTH, HEIGHT)
    # Keep every bilinear neighbourhood in bounds while retaining nonzero
    # radial K1/K2/K3 and tangential P1/P2 terms throughout the full image.
    config[4] = (config[4] * 9 + 5) // 10
    config[5] = (config[5] * 9 + 5) // 10
    yy, xx = np.indices((HEIGHT, WIDTH), dtype=np.int64)
    sx, sy, bad, r2 = cpu.project_integer(xx * 256, yy * 256, config)
    guard = 2 << 22
    invalid = bad | (r2 > guard)
    neighbourhood_bad = invalid | (sx < 0) | (sy < 0) | ((sx >> 8) + 1 >= WIDTH) | ((sy >> 8) + 1 >= HEIGHT)
    if np.any(neighbourhood_bad):
        raise ValueError("synthetic full-neighbourhood geometry unexpectedly outside the source")
    scalar = cpu.scalar_oracle()
    checks = 0
    for y in np.unique(np.linspace(0, HEIGHT - 1, 13, dtype=int)):
        for x in np.unique(np.linspace(0, WIDTH - 1, 17, dtype=int)):
            a, b, failed = scalar.project(int(x) * 256, int(y) * 256, config)
            if (a, b, bool(failed)) != (int(sx[y, x]), int(sy[y, x]), bool(bad[y, x])):
                raise ValueError("scalar/vector coordinate oracle disagreement")
            checks += 1
    return config, guard, sx, sy, invalid, {
        "ScalarCoordinateCrosschecks": checks, "InvalidPixels": int(invalid.sum()),
        "MaximumRadiusSquaredQ22": int(r2.max()),
        "SourceXRangeQ8": [int(sx.min()), int(sx.max())],
        "SourceYRangeQ8": [int(sy.min()), int(sy.max())],
        "AllBilinearNeighboursInBounds": True,
    }


def fixtures(work):
    config, guard, sx, sy, invalid, stats = geometry()
    headers = [f"localparam integer VEC_WIDTH={WIDTH},VEC_HEIGHT={HEIGHT},VEC_RADIUS_GUARD_Q22={guard};"]
    for name, value in zip(cpu.NAMES, config):
        bits = 24 if name in cpu.NAMES[:6] else 32
        headers.append(f"localparam signed [{bits-1}:0] VEC_{name}={bits}'sh{value & ((1<<bits)-1):0{bits//4}x};")
    (work / "config.vh").write_text("\n".join(headers) + "\n", encoding="ascii", newline="\n")
    packed = ((invalid.astype(np.uint64) << 48)
              | ((sx.astype(np.uint64) & 0xffffff) << 24)
              | (sy.astype(np.uint64) & 0xffffff))
    with (work / "coordinates.mem").open("x", encoding="ascii", newline="\n") as out:
        out.writelines(f"{int(value):013x}\n" for value in packed.ravel())
    records, expected = [], []
    for index in range(FRAME_COUNT):
        source = cpu.texture(WIDTH, HEIGHT, index % 2)
        if index == 2:
            source = np.roll(source, (37, 53), (0, 1)) ^ np.uint16(0x0841)
        # Exact integer coordinate/bilinear reference, independent of RTL output.
        golden = cpu.pack565(cpu.remap_fixed(cpu.expand565(source), sx / 256., sy / 256.))
        write_mem(work / f"source{index}.mem", source, beats=True)
        write_mem(work / f"expected{index}.mem", golden)
        records.append({"FrameID": index + 1, "SourceCRC32": crc(source), "ExpectedCRC32": crc(golden)})
        expected.append(golden)
    if any(len({v[key] for v in records}) != FRAME_COUNT for key in ("SourceCRC32", "ExpectedCRC32")):
        raise ValueError("three distinct source/result epochs required")
    for filename, key in (("source-crcs.mem", "SourceCRC32"), ("expected-crcs.mem", "ExpectedCRC32")):
        (work / filename).write_text("\n".join(v[key] for v in records) + "\n", encoding="ascii", newline="\n")
    return records, expected, {"IntegerConfig": config, "RadiusGuardQ22": guard, "Geometry": stats,
        "Provenance": "synthetic_stress_only", "LensCalibrationAccepted": False, "GammaEnabled": False}


def validate_summary(summary):
    exact = {"passed": True, "frames_processed": FRAME_COUNT, "frames_unique_scanned": FRAME_COUNT,
             "coordinates_compared": FRAME_COUNT * PIXELS, "result_beats": FRAME_COUNT * PIXELS // 16,
             "underflows": 0, "crc_mismatches": 0, "final_drain": True,
             "source_bank_reuses": 1, "result_bank_reuses": 1}
    if any(type(summary.get(key)) is not type(value) or summary.get(key) != value for key, value in exact.items()):
        raise ValueError("full-frame processing/ownership/drain contract failed")
    if type(summary.get("scan_frames")) is not int or summary["scan_frames"] < FRAME_COUNT:
        raise ValueError("not all frame epochs reached the scan")
    count = summary["scan_frames"]
    if (summary.get("pixels_compared") != count * PIXELS or summary.get("display_read_beats") != count * PIXELS // 16
            or summary.get("bank_releases") != count):
        raise ValueError("scan/read/lease counts differ")
    for key in ("aw_stall_cycles", "w_stall_cycles", "ar_stall_cycles", "fifo_peak",
                "concurrent_process_display_cycles", "read_contention_cycles", "complete_hdmi_rasters", "border_pixels_checked"):
        if type(summary.get(key)) is not int or summary[key] <= 0:
            raise ValueError("missing full-raster, DDR or concurrency pressure: " + key)
    if summary["fifo_peak"] > 512 or summary["complete_hdmi_rasters"] < FRAME_COUNT:
        raise ValueError("FIFO/raster bounds differ")


def validate_pixels(work, records, expected, rows, summary):
    # Read complete scan epochs one at a time to bound Python memory, and check
    # the actual RGB output dump independently of the simulator assertions.
    if len(rows) != summary["scan_frames"]:
        raise ValueError("missing scan frame rows")
    actual_ids = set()
    with (work / "scan-pixels.mem").open(encoding="ascii") as pixels:
        for row in rows:
            frame_id = int(row["frame_id"])
            if not 1 <= frame_id <= FRAME_COUNT:
                raise ValueError("invalid scanned frame ID")
            record = records[frame_id - 1]
            if (int(row["pixels"]) != PIXELS or int(row["result_beats"]) != PIXELS // 16
                    or int(row["result_bank"]) != (frame_id - 1) % 2
                    or row["source_crc32"].upper() != record["SourceCRC32"]
                    or any(row[key].upper() != record["ExpectedCRC32"] for key in ("result_crc32", "reader_crc32", "scan_crc32"))
                    or not int(row["start_cycle"]) < int(row["process_done_cycle"]) < int(row["release_cycle"])):
                raise ValueError("per-frame source/result/read/scan CRC or ordering differs")
            actual = np.empty(PIXELS, dtype=np.uint16)
            for index in range(PIXELS):
                line = pixels.readline().split()
                if len(line) != 2 or int(line[0]) != frame_id:
                    raise ValueError("actual DE/RGB dump epoch or length differs")
                actual[index] = int(line[1], 16)
            if not np.array_equal(actual.reshape(HEIGHT, WIDTH), expected[frame_id - 1]) or crc(actual) != record["ExpectedCRC32"]:
                raise ValueError("independent post-run actual pixel comparison failed")
            actual_ids.add(frame_id)
        if pixels.read().strip():
            raise ValueError("unexpected extra actual pixels")
    if actual_ids != set(range(1, FRAME_COUNT + 1)):
        raise ValueError("a unique frame epoch was never displayed")


def run(workdir, maximum_seconds):
    work = Path(workdir).resolve()
    if not work.is_relative_to(BASE.resolve()) or work == BASE.resolve():
        raise ValueError("workdir must be a new child of work/camera720-output")
    if not 30 <= maximum_seconds <= 3600:
        raise ValueError("whole native run bound must be 30..3600 seconds")
    work.mkdir(parents=True, exist_ok=False)
    source_hashes = {name: sha(ROOT / name) for name in (*COMPILE, *HEADERS, *HELPERS)}
    report = {"Passed": False, "StartedUtc": datetime.now(timezone.utc).isoformat(), "MaximumSeconds": maximum_seconds,
        "HardwareAccessed": False, "PDSAccessed": False, "PhysicalInputExercised": False,
        "CurrentCameraVerified": False, "CalibrationAccepted": False, "HardwareReleaseAllowed": False,
        "SourcePreloadedInModeledDDR": True, "ProductionBankManager": True, "RealOutputAsyncFIFO": True,
        "RTLResultUsedForGolden": False, "Width": WIDTH, "Height": HEIGHT, "FrameCount": FRAME_COUNT,
        "CoreClockHz": 125000000, "PixelClockHz": 74250000,
        "OutputRaster": {"Width": 1920, "Height": 1080, "HT": 2200, "VT": 1125, "HS": 44, "VS": 5, "X0": 192, "Y0": 41,
                         "NativeImageX0": 512, "NativeImageY0": 221},
        "SourceSHA256": source_hashes, "Commands": [], "OutputDirectory": str(work),
        "Limits": "Synthetic stress geometry/textures; no lens calibration, live DVP, capture DMA, board top, physical DDR/HDMI, timing or hardware fps acceptance. Sources preload into modeled DDR. Scan handshakes use a bench parent with the production bank manager; this is not a test of the complete camera_vga_video_system controller."}
    fixture_hashes = {}
    deadline = time.monotonic() + maximum_seconds
    try:
        records, expected, binding = fixtures(work)
        report.update(FramesExpected=records, ModelBinding=binding)
        fixture_hashes = {p.name: sha(p) for p in work.iterdir() if p.is_file()}
        report["FixtureSHA256"] = fixture_hashes
        compiled, bindings = prepare_compile_sources(ROOT, COMPILE, HEADERS, work)
        report["RelocatedSources"] = bindings
        bin_dir = resolve_vivado_bin(ROOT.parent)
        stages = (("xvlog.bat", ["--sv", *map(str, compiled)], "compile"),
                  ("xelab.bat", ["tb_camera720_output", "-s", "camera720_output"], "elaborate"),
                  ("xsim.bat", ["camera720_output", "-runall", "-log", "simulation.log"], "simulate"))
        for executable, argv, stage in stages:
            command = {"Stage": stage, "NativeArgv": [str(bin_dir / executable), *argv], "ReturnCode": None}
            report["Commands"].append(command)
            tool(bin_dir, executable, argv, work, deadline, stage)
            command["ReturnCode"] = 0
        log = (work / "simulation.log").read_text(encoding="utf-8", errors="replace")
        if MARKER not in log or "$finish called" not in log or re.search(r"(?im)^\s*(?:fatal|error):", log):
            raise ValueError("full replay completion marker absent or RTL error")
        summary = load(work / "summary.json")
        validate_summary(summary)
        with (work / "frames.csv").open(encoding="ascii", newline="") as stream:
            rows = list(csv.DictReader(stream))
        validate_pixels(work, records, expected, rows, summary)
        verify_compile_sources(ROOT, COMPILE, HEADERS, work, bindings)
        report.update(Passed=True, Summary=summary, Frames=rows, ActualDERGBScanned=True,
                      PassLines=[line for line in log.splitlines() if line.startswith(("PASS", "OUTPUT720_FRAME_PASS"))])
    except (Exception, KeyboardInterrupt) as error:
        report["Error"] = type(error).__name__ + ": " + str(error)
    finally:
        after = {name: sha(ROOT / name) for name in source_hashes}
        report["SourceSHA256After"] = after
        report["FixtureSHA256After"] = {name: sha(work / name) for name in fixture_hashes}
        if after != source_hashes or report["FixtureSHA256After"] != fixture_hashes:
            report.update(Passed=False, SourceOrInputDrift=True)
        report["FinishedUtc"] = datetime.now(timezone.utc).isoformat()
        report["LogSHA256"] = {p.name: sha(p) for p in work.glob("*.log")}
        report["ResultSHA256"] = {p.name: sha(p) for p in work.iterdir() if p.is_file() and p.name in ("frames.csv", "summary.json", "scan-pixels.mem")}
        (work / "camera720-output-simulation.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"Passed": report["Passed"], "Error": report.get("Error"), "Report": str(work / "camera720-output-simulation.json")}, ensure_ascii=False))
    return 0 if report["Passed"] else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workdir", type=Path, required=True)
    parser.add_argument("--maximum-seconds", type=int, default=1800)
    args = parser.parse_args()
    return run(args.workdir, args.maximum_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
