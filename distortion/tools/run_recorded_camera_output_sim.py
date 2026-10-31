"""Replay immutable archival camera images through production processing/output RTL.

No camera, HDMI RX, physical DDR, board download or PDS is accessed. The source
starts in modeled DDR, exactly640x480; synthetic Brown stress intrinsics and an
adapted640x480 raster are test settings, never an optical or display-mode claim.
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
from generate_continuous1080_vectors import remap_source
from run_gamma_pipeline_d5_sim import tool
from simulation_tools import prepare_compile_sources, resolve_vivado_bin, verify_compile_sources

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "build/recorded-camera-output"
FRAMES = ("grid-left-adjusted-20261009", "grid-right-20261009")
RAW_SHA = ("df3b9f5fe855c53d0078425f7affbc222ccbdda79ddba76c5812e0f3e5553efe", None)
COMPILE = (
    "rtl/mul32_pipe.v", "rtl/pixel_inverse_rotation.v", "rtl/bounded_brown_inverse_mapper.v",
    "rtl/bilinear_rgb.v", "rtl/ddr_read_arbiter.v", "rtl/ddr_video_reader.v", "rtl/video_async_fifo.v",
    "rtl/experimental/ddr_neighbour_cache_scatter4_rowpipe.v",
    "rtl/experimental/ddr_remap_sample_scatter4_rowpipe.v",
    "rtl/experimental/rotated_remap_core_gamma_scatter4.v",
    "rtl/experimental/adaptive_gamma_stream.v", "rtl/experimental/adaptive_gamma_tagged.v",
    "rtl/experimental/ddr_adaptive_result_writer.v", "rtl/experimental/pipeline_gamma_frame_engine_1080_scatter4.v",
    "rtl/experimental/ddr_video_output_1080_board.v", "tests/tb_recorded_camera_output.sv",
)
HEADERS = ("rtl/experimental/gamma_curves.vh", "rtl/video_crc32.vh")
HELPERS = ("tools/run_recorded_camera_output_sim.py", "tools/generate_1080_core_vectors.py",
           "tools/generate_continuous1080_vectors.py", "tools/generate-brown-vectors.py",
           "model/reference.py", "tools/simulation_tools.py", "tools/run_gamma_pipeline_d5_sim.py")
MARKER = "PASS recorded camera output:"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def crc(words):
    return f"{zlib.crc32(np.asarray(words, dtype='<u2').tobytes()) & 0xffffffff:08X}"


def write_mem(path, words, *, beats=False):
    with Path(path).open("x", encoding="ascii", newline="\n") as stream:
        if beats:
            payload = np.asarray(words, dtype="<u2").tobytes()
            stream.writelines(f"{int.from_bytes(payload[i:i+32], 'little'):064x}\n" for i in range(0, len(payload), 32))
        else:
            stream.writelines(f"{int(word):04x}\n" for word in np.asarray(words).ravel())


def fixtures(work):
    config = cpu.parameters(640, 480)
    headers = ["localparam integer VEC_WIDTH=640,VEC_HEIGHT=480,VEC_RADIUS_GUARD_Q22=8388608;"]
    for name, value in zip(cpu.NAMES, config):
        bits = 24 if name in cpu.NAMES[:6] else 32
        headers.append(f"localparam signed [{bits-1}:0] VEC_{name}={bits}'sh{value & ((1<<bits)-1):0{bits//4}x};")
    (work/"config.vh").write_text("\n".join(headers)+"\n", encoding="ascii")
    records, watched, goldens, sources = [], {}, [], []
    for index, scene in enumerate(FRAMES):
        directory = ROOT / "captures/gamma-triplets" / scene
        metadata = directory / "summary.json"
        path = directory / "group-00000001/raw.npy"
        record = load(metadata)
        group = record["groups"][0]
        digest = sha(path)
        if (record.get("passed") is not True or record.get("target") != "gamma_capture_settled_d5"
                or record.get("input_origin") != "optical_camera_scene" or record.get("source_kind") != "physical_same_source"
                or group["files_sha256"].get("raw.npy") != digest or (RAW_SHA[index] and digest != RAW_SHA[index])):
            raise ValueError("archival corrected-D5 camera source provenance/hash differs")
        source = np.load(path, allow_pickle=False)
        if source.shape != (480, 640) or source.dtype != np.uint16 or crc(source) != group["crc32"][0].upper():
            raise ValueError("archival camera frame geometry/type/payload CRC differs")
        expected, mask, stats = remap_source(source, config, 2*cpu.Q)
        # Reset mode0; these two real scenes both have neutral decisions, so
        # hysteresis keeps both complete frames in mode0. Verify independently.
        rgb = cpu.expand565(expected).astype(np.int64)
        luminance = (77*rgb[..., 0]+150*rgb[..., 1]+29*rgb[..., 2]) >> 8
        samples = int((~mask).sum()); dark = int(((luminance < 64) & ~mask).sum())
        bright = int(((luminance >= 192) & ~mask).sum())
        decision = 0 if samples < source.size//4 else (1 if dark >= (samples+1)//2 else 2 if bright >= (samples+1)//2 else 0)
        if decision != 0:
            raise ValueError("fixture gamma decision changed; require explicit sequential golden modes")
        write_mem(work/f"source{index}.mem", source, beats=True)
        write_mem(work/f"expected{index}.mem", expected)
        Image.fromarray(cpu.expand565(source)).save(work/f"frame{index+1}-source.png")
        Image.fromarray(cpu.expand565(expected)).save(work/f"frame{index+1}-expected.png")
        item = {"FrameID": index+1, "Path": str(path), "SHA256": digest, "Metadata": str(metadata),
                "MetadataSHA256": sha(metadata), "CaptureTarget": record["target"], "RecordedUtc": record["recorded_utc"],
                "Scene": record.get("scene_label"), "SourceCRC32": crc(source), "ExpectedCRC32": crc(expected),
                "GammaMode": 0, "GammaDecision": decision, "ValidSamples": samples, "DarkSamples": dark,
                "BrightSamples": bright, "Statistics": stats}
        records.append(item); goldens.append(expected); sources.append(source)
        watched[str(path)] = digest; watched[str(metadata)] = sha(metadata)
    if records[0]["SourceCRC32"] == records[1]["SourceCRC32"] or records[0]["ExpectedCRC32"] == records[1]["ExpectedCRC32"]:
        raise ValueError("same-bank new epoch requires two distinct actual camera images/results")
    (work/"source-crcs.mem").write_text("\n".join(r["SourceCRC32"] for r in records)+"\n", encoding="ascii")
    (work/"expected-crcs.mem").write_text("\n".join(r["ExpectedCRC32"] for r in records)+"\n", encoding="ascii")
    return records, watched, goldens


def run(workdir, maximum_seconds):
    work = Path(workdir).resolve()
    if not work.is_relative_to(BASE.resolve()) or work == BASE.resolve():
        raise ValueError("workdir must be a new child of build/recorded-camera-output")
    if not 30 <= maximum_seconds <= 1800:
        raise ValueError("whole native run bound must be30..1800 seconds")
    work.mkdir(parents=True, exist_ok=False)
    source_hashes = {name: sha(ROOT/name) for name in (*COMPILE, *HEADERS, *HELPERS)}
    report = {"Passed": False, "StartedUtc": datetime.now(timezone.utc).isoformat(), "MaximumSeconds": maximum_seconds,
              "HardwareAccessed": False, "PDSAccessed": False, "PhysicalInputExercised": False,
              "CurrentCameraVerified": False, "CalibrationAccepted": False, "HardwareReleaseAllowed": False,
              "SourcePreloadedInModeledDDR": True, "RealOutputAsyncFIFO": True, "RTLResultUsedForGolden": False,
              "Width": 640, "Height": 480, "FrameCount": 2, "CoreClockHz": 125000000, "PixelClockHz": 25000000,
              "AdaptedRaster": {"HT": 800, "VT": 525, "HS": 96, "VS": 2, "X0": 144, "Y0": 35},
              "SourceSHA256": source_hashes, "Commands": [], "OutputDirectory": str(work),
              "Model": "Independent synthetic nonzero radial/tangential Brown stress intrinsics, exact zero-angle rotation; not lens calibration",
              "Limits": "Archival clean-D5 optical camera images only. No current CAM2/lens/input, physical DDR/HDMI mode, fps, timing or board acceptance. Bench owns serialized source/result leases; production bank manager and concurrency are not exercised."}
    watched = {}; fixture_hashes = {}
    deadline = time.monotonic()+maximum_seconds
    try:
        records, watched, expected = fixtures(work)
        report["ArchivalFrames"] = records
        report["IntegerConfig"] = cpu.parameters(640, 480)
        fixture_hashes = {p.name: sha(p) for p in work.iterdir() if p.is_file()}
        report["FixtureSHA256"] = fixture_hashes
        compiled, bindings = prepare_compile_sources(ROOT, COMPILE, HEADERS, work)
        report["RelocatedSources"] = bindings
        bin_dir = resolve_vivado_bin(ROOT.parent)
        stages = (("xvlog.bat", ["--sv", *map(str, compiled)], "compile"),
                  ("xelab.bat", ["tb_recorded_camera_output", "-s", "recorded_camera_output"], "elaborate"),
                  ("xsim.bat", ["recorded_camera_output", "-runall", "-log", "simulation.log"], "simulate"))
        for executable, argv, stage in stages:
            command = {"Stage": stage, "NativeArgv": [str(bin_dir/executable), *argv], "ReturnCode": None}
            report["Commands"].append(command)
            tool(bin_dir, executable, argv, work, deadline, stage)
            command["ReturnCode"] = 0
        log = (work/"simulation.log").read_text(encoding="utf-8", errors="replace")
        if MARKER not in log or "$finish called" not in log or re.search(r"(?im)^\s*(?:fatal|error):", log):
            raise ValueError("full replay completion marker absent or RTL error")
        summary = load(work/"summary.json")
        checks = {"passed": True, "frames_processed": 2, "frames_unique_scanned": 2, "pixels_compared": 614400,
                  "source_bank_reuses": 1, "result_bank_reuses": 1, "bank_releases": 2,
                  "result_beats": 38400, "display_read_beats": 38400, "underflows": 0, "crc_mismatches": 0, "final_drain": True}
        if any(type(summary.get(k)) is not type(v) or summary.get(k) != v for k, v in checks.items()):
            raise ValueError("all-frame processing/real pixel scan/epoch/drain contract failed")
        if any(type(summary.get(k)) is not int or summary[k] <= 0 for k in ("aw_stall_cycles", "w_stall_cycles", "ar_stall_cycles", "fifo_peak")):
            raise ValueError("DDR/FIFO pressure was not exercised")
        with (work/"frames.csv").open(encoding="ascii", newline="") as stream:
            rows = list(csv.DictReader(stream))
        if len(rows) != 2:
            raise ValueError("missing replay frame rows")
        for item, row in zip(records, rows):
            if (int(row["frame_id"]) != item["FrameID"] or int(row["source_epoch"]) != item["FrameID"]
                    or int(row["result_epoch"]) != item["FrameID"] or int(row["pixels"]) != 307200
                    or row["source_crc32"].upper() != item["SourceCRC32"]
                    or any(row[k].upper() != item["ExpectedCRC32"] for k in ("result_crc32", "reader_crc32", "scan_crc32"))
                    or not int(row["start_cycle"]) < int(row["process_done_cycle"]) < int(row["release_cycle"])):
                raise ValueError("per-frame source/result/read/scan CRC or event order differs")
        actual = np.loadtxt(work/"scan-pixels.mem", dtype=np.uint16, converters={0: lambda value: int(value, 16)}, ndmin=1)
        if actual.shape != (614400,):
            raise ValueError("actual pixel dump is incomplete")
        for index, golden in enumerate(expected):
            pixels = actual[index*307200:(index+1)*307200].reshape(480, 640)
            if not np.array_equal(pixels, golden) or crc(pixels) != records[index]["ExpectedCRC32"]:
                raise ValueError("independent post-run actual DE/RGB pixel comparison failed")
            Image.fromarray(cpu.expand565(pixels)).save(work/f"frame{index+1}-actual-scan.png")
        verify_compile_sources(ROOT, COMPILE, HEADERS, work, bindings)
        report.update(Passed=True, Summary=summary, Frames=rows, ActualDERGBScanned=True,
                      PassLines=[line for line in log.splitlines() if line.startswith(("PASS", "REPLAY_FRAME_PASS"))])
    except (Exception, KeyboardInterrupt) as error:
        report["Error"] = type(error).__name__+": "+str(error)
    finally:
        after = {name: sha(ROOT/name) for name in source_hashes}
        report["SourceSHA256After"] = after
        report["InputSHA256"] = watched
        report["InputSHA256After"] = {name: sha(name) for name in watched}
        report["FixtureSHA256After"] = {name: sha(work/name) for name in fixture_hashes}
        if after != source_hashes or report["InputSHA256After"] != watched or report["FixtureSHA256After"] != fixture_hashes:
            report.update(Passed=False, SourceOrInputDrift=True)
        report["FinishedUtc"] = datetime.now(timezone.utc).isoformat()
        report["LogSHA256"] = {p.name: sha(p) for p in work.glob("*.log")}
        report["ResultSHA256"] = {p.name: sha(p) for p in work.iterdir() if p.is_file() and p.name in ("frames.csv", "summary.json", "scan-pixels.mem", "frame1-actual-scan.png", "frame2-actual-scan.png")}
        (work/"recorded-camera-output-simulation.json").write_text(json.dumps(report, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({"Passed": report["Passed"], "Error": report.get("Error"), "Report": str(work/"recorded-camera-output-simulation.json")}, ensure_ascii=False))
    return 0 if report["Passed"] else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workdir", type=Path, required=True)
    parser.add_argument("--maximum-seconds", type=int, default=900)
    args = parser.parse_args()
    return run(args.workdir, args.maximum_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
