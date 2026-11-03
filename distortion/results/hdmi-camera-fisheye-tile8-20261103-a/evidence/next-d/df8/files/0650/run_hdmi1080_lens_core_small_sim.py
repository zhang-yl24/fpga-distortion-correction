"""One bounded32x16 actual-input/core/readback test; no CAD/device access.

Reuse the existing vector/source/tool checks. Work and vector directories must
already exist below approved scratch. This never generates native1080 fixtures.
"""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import csv
import json
import math
import os
import re
import time

import run_lens1080_core_sim as base

ROOT, APPROVED = base.ROOT, base.APPROVED
TOP = "tb_hdmi1080_lens_core_small"
SNAPSHOT = "hdmi1080_lens_core_small"
REPORT = "hdmi1080-lens-core-small-simulation.json"
MARKER = "PASS actual-input core-small:"
REPLACEMENTS = {
    "rtl/experimental/pipeline_gamma_frame_engine_1080_core.v":
        "rtl/experimental/pipeline_gamma_frame_engine_1080_scatter4.v",
    "tests/tb_lens1080_core.sv": "tests/tb_hdmi1080_lens_core_small.sv",
}
COMPILE = tuple(REPLACEMENTS.get(name, name) for name in base.COMPILE) + (
    "rtl/experimental/ddr_compact_neighbour_cache_scatter4.v",
    "rtl/experimental/ddr_remap_sample_scatter4.v",
    "rtl/experimental/rotated_remap_core_gamma_scatter4.v",
    "rtl/video_async_fifo.v", "rtl/ddr_write_arbiter.v",
    "rtl/experimental/hdmi1080_capture_cdc.v",
    "rtl/experimental/hdmi1080_input_dma.v",
    "rtl/experimental/hdmi1080_input_write_link.v",
)
HELPERS = (*base.HELPERS, "tools/run_hdmi1080_lens_core_small_sim.py")
FROZEN = {
    "rtl/experimental/ddr_compact_neighbour_cache.v": base.DA07_SHA256,
    "rtl/experimental/ddr_compact_neighbour_cache_scatter4.v":
        "db3c8f924f22d6a67d80d3e7a9e10ec8dba39d6ae30d12637ab5aa06d6005d2b",
    "rtl/experimental/hdmi1080_input_dma.v":
        "ba4c24e483452bd4a3c52bc74ecece429eb793e17c73c1a037af3ebec4c48660",
    "rtl/experimental/hdmi1080_capture_cdc.v":
        "bff4e78d9fdedb0d23c31e499044768946428ce4b70059acd1be27c582903d3c",
    "rtl/experimental/hdmi1080_input_write_link.v":
        "276441de0a0d5b04cb4a9564e8715a517fbec12d891489ba54ff8d6b348d44e4",
}


def run(workdir, vectors0, vectors1, maximum_seconds=120):
    if (type(maximum_seconds) not in (int, float) or not math.isfinite(maximum_seconds)
            or not 1 <= maximum_seconds <= 120):
        raise ValueError("maximum-seconds must be finite in [1,120]")
    work = base.approved_directory(workdir)
    vectors = [base.vector_record(vectors0, 0), base.vector_record(vectors1, 1)]
    first, second = [item[1] for item in vectors]
    for record in (first, second):
        if (record["Width"], record["Height"]) != (32, 16):
            raise ValueError("only independent32x16 small vectors are allowed")
    for key in ("IntegerConfig", "RadiusGuardQ22", "FixedPoint", "Model", "Rotation"):
        if first.get(key) != second.get(key):
            raise ValueError("two textures must share the same independent model: " + key)
    if first["SourcePixelCRC32"] == second["SourcePixelCRC32"]:
        raise ValueError("distinct source textures required")
    configs = [(item[0] / "config.vh").read_bytes() for item in vectors]
    strip_crc = lambda data: re.sub(rb"(?m)^localparam \[31:0\] VEC_EXPECTED_CRC32=.*\r?\n?", b"", data)
    if strip_crc(configs[0]) != strip_crc(configs[1]):
        raise ValueError("vector configs differ beyond their expected CRC")
    fixtures = {"config.vh": configs[0]}
    inputs = {}
    for variant, (directory, record, watched) in enumerate(vectors):
        for source, target in (("source.mem", "source"), ("expected.mem", "expected"),
                               ("masks.mem", "masks"), ("crcs.mem", "crc")):
            fixtures[f"{target}{variant}.mem"] = (directory / source).read_bytes()
        fixtures[f"sourcecrc{variant}.mem"] = (record["SourcePixelCRC32"] + "\n").encode("ascii")
        for name, digest in watched.items():
            if name in inputs and inputs[name] != digest:
                raise ValueError("conflicting vector reference bindings")
            inputs[name] = digest
    reserved = (*fixtures, REPORT, "summary.json", "cycles.csv", "simulation.log",
                *(stage + suffix for stage in ("compile", "elaborate", "simulate")
                  for suffix in ("-stdout.log", "-stderr.log")))
    if any((work / name).exists() for name in reserved) or (work / "xsim.dir").exists():
        raise ValueError("fresh outputs required; previous evidence is never replaced")
    before = {name: base.sha(ROOT / name) for name in (*COMPILE, *base.HEADERS, *HELPERS)}
    if any(before.get(name) != digest for name, digest in FROZEN.items()):
        raise ValueError("declared frozen cache/input/link revision differs")
    report = {
        "Passed": False, "Marker": "FPGA-1031-A-ACTUAL-INPUT-CORE-SMALL",
        "Target": "hdmi1080_lens_core_small_offline", "Width": 32, "Height": 16,
        "HardwareAccessed": False, "PDSAccessed": False, "HardwareReleaseAllowed": False,
        "SyntheticInput": True, "DevelopmentOnly": True, "CalibrationAccepted": False,
        "NewLensCorrectionVerified": False, "InputPreloadedNotDMA": False,
        "DisplayDDRReadbackOnly": True, "PerformanceComparableToFull1080": False,
        "OutputDirectory": str(work), "MaximumSeconds": maximum_seconds, "MaxSystemCycles": 2000000,
        "StartedUtc": datetime.now(timezone.utc).isoformat(), "SourceSHA256": before,
        "InputSHA256": inputs, "Commands": [],
        "VectorMetadata": [{"Path": str(item[0] / "vectors.json"),
                            "SHA256": base.sha(item[0] / "vectors.json"),
                            "TextureVariant": i, "SourceCRC32": item[1]["SourcePixelCRC32"],
                            "ExpectedCRC32": item[1]["ExpectedPixelCRC32"]} for i, item in enumerate(vectors)],
    }
    deadline = time.monotonic() + maximum_seconds
    try:
        for name, data in fixtures.items():
            with (work / name).open("xb") as stream:
                stream.write(data)
        report["FixtureSHA256"] = {name: base.sha(work / name) for name in fixtures}
        bin_dir = Path(os.environ.get("FPGA_VIVADO_BIN", "E:/Vivado/Vivado/2017.4/bin"))
        stages = (("xvlog.bat", ["--sv", *[str(ROOT / name) for name in COMPILE]], "compile"),
                  ("xelab.bat", [TOP, "-s", SNAPSHOT], "elaborate"),
                  ("xsim.bat", [SNAPSHOT, "-runall", "-log", "simulation.log"], "simulate"))
        for executable, args, stage in stages:
            command = {"Stage": stage, "NativeArgv": [str(bin_dir / executable), *args], "ReturnCode": None}
            report["Commands"].append(command)
            try:
                base.tool(bin_dir, executable, args, work, deadline, stage)
                command.update(ReturnCode=0, ReturnCodeEvidence="fixed tool native wait(0)")
            except (Exception, KeyboardInterrupt) as exc:
                match = re.search(r"failed, exit=(-?\d+)", str(exc))
                if match:
                    command["ReturnCode"] = int(match.group(1))
                command["Error"] = type(exc).__name__ + ": " + str(exc)
                raise
        log = (work / "simulation.log").read_text(encoding="utf-8", errors="replace")
        if MARKER not in log or "$finish called" not in log or re.search(r"(?im)^\s*(?:fatal|error):", log):
            raise ValueError("completed small-integration marker absent or simulation error")
        summary = base.load(work / "summary.json")
        expected = {"passed": True, "width": 32, "height": 16, "frames": 2,
                    "source_beats": 64, "result_beats": 64, "readback_beats": 64,
                    "input_preloaded_not_DMA": False, "actual_input_DMA": True,
                    "display_DDR_readback_only": True, "final_drain": True,
                    "hardware_verified": False, "performance_comparable_to_full1080": False}
        if any(type(summary.get(k)) is not type(v) or summary[k] != v for k, v in expected.items()):
            raise ValueError("small integration summary/geometry/drain differs")
        for key, metadata_key in (("source_crc32", "SourcePixelCRC32"), ("result_crc32", "ExpectedPixelCRC32")):
            if [value.upper() for value in summary[key]] != [item[1][metadata_key] for item in vectors]:
                raise ValueError("software metadata and actual summary CRC differ: " + key)
        if (summary["aw_stall"] <= 0 or summary["w_stall"] <= 0 or summary["commit_stall"] < 20
                or summary["display_ar_stall"] <= 0 or summary["write_contention"] <= 0):
            raise ValueError("explicit small pressure coverage missing")
        with (work / "cycles.csv").open(newline="", encoding="utf-8-sig") as stream:
            rows = list(csv.DictReader(stream))
        if len(rows) != 2 or [int(row["frame"]) for row in rows] != [0, 1]:
            raise ValueError("two actual core completion rows required")
        report.update(Passed=True, Summary=summary, Cycles=rows, CyclesSHA256=base.sha(work / "cycles.csv"),
                      PassLines=[line for line in log.splitlines() if line.startswith("PASS")])
    except (Exception, KeyboardInterrupt) as exc:
        report["Error"] = type(exc).__name__ + ": " + str(exc)
    finally:
        report["SourceSHA256After"] = {name: base.sha(ROOT / name) if (ROOT / name).is_file() else None for name in before}
        report["InputSHA256After"] = {name: base.sha(name) if Path(name).is_file() else None for name in inputs}
        report["FixtureSHA256After"] = {name: base.sha(work / name) if (work / name).is_file() else None for name in fixtures}
        if (report["SourceSHA256After"] != before or report["InputSHA256After"] != inputs or
                report.get("FixtureSHA256") != report["FixtureSHA256After"]):
            report.update(Passed=False, SourceOrFixtureDrift=True)
        report["LogSHA256"] = {p.name: base.sha(p) for p in work.glob("*.log") if p.is_file()}
        report["BenchSummarySHA256"] = {name: base.sha(work / name) for name in ("summary.json", "cycles.csv") if (work / name).is_file()}
        report["EndedUtc"] = datetime.now(timezone.utc).isoformat()
        report["Limits"] = ("Only two32x16 synthetic frames with normalized pixel-domain input, DMA-written source DDR, "
            "SCATTER4 zero-angle GM0 correction, software masks/CRC, shared write/read arbiters and complete DDR readback. "
            "No HDMI pixel display, physical source mode/lock/polarity, native1080 contention FPS, CDC/STA/resources, optics or hardware proof. "
            "Small pressure counts are recorded, not compared with the earlier full1080 cycle benchmark.")
        with (work / REPORT).open("x", encoding="utf-8") as stream:
            json.dump(report, stream, indent=2, allow_nan=False)
            stream.write("\n")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workdir", type=Path, required=True)
    parser.add_argument("--vectors0", type=Path, required=True)
    parser.add_argument("--vectors1", type=Path, required=True)
    parser.add_argument("--maximum-seconds", type=float, default=120)
    args = parser.parse_args()
    try:
        result = run(args.workdir, args.vectors0, args.vectors1, args.maximum_seconds)
    except (ValueError, KeyError, OSError) as exc:
        parser.exit(1, str(exc) + "\n")
    print(json.dumps({"Report": str(args.workdir.resolve() / REPORT), "Passed": result["Passed"],
                      "Commands": result["Commands"], "Error": result.get("Error")}, indent=2))
    return 0 if result["Passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
