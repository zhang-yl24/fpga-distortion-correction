"""One bounded, source-bound lens1080 core simulation; no CAD/device access.

The work directory and two synthetic vector directories must already exist
under approved scratch. Existing files are never replaced. Importing this
module does not generate fixtures, invoke a simulator, or create a directory.
"""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import csv
import hashlib
import json
import math
import os
import re
import time

from run_gamma_pipeline_d5_sim import tool

ROOT = Path(__file__).resolve().parents[1]
APPROVED = ROOT / "build/offline-20261024"
TOP = "tb_lens1080_core"
SNAPSHOT = "lens1080_core_snapshot"
REPORT = "lens1080-core-simulation.json"
COMPILE = (
    "rtl/mul32_pipe.v", "rtl/pixel_inverse_rotation.v",
    "rtl/bounded_brown_inverse_mapper.v", "rtl/bilinear_rgb.v",
    "rtl/ddr_remap_sample.v", "rtl/ddr_read_arbiter.v", "rtl/ddr_video_reader.v",
    "rtl/experimental/ddr_compact_neighbour_cache.v",
    "rtl/experimental/rotated_remap_core_gamma.v",
    "rtl/experimental/adaptive_gamma_stream.v",
    "rtl/experimental/adaptive_gamma_tagged.v",
    "rtl/experimental/ddr_adaptive_result_writer.v",
    "rtl/experimental/pipeline_gamma_frame_engine_1080_core.v",
    "rtl/experimental/lens1080_bank_core.v", "tests/tb_lens1080_core.sv",
)
HEADERS = ("rtl/experimental/gamma_curves.vh", "rtl/video_crc32.vh")
HELPERS = ("tools/run_lens1080_core_sim.py", "tools/run_gamma_pipeline_d5_sim.py")
DA07_SHA256 = "da07e9ac7efa0ca53fd470c47b74039276de35069c5bb8f77ed8620565c2e531"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"),
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError("nonfinite JSON")))


def approved_directory(path):
    result = Path(path).resolve()
    if not result.is_dir() or result == APPROVED.resolve() or not result.is_relative_to(APPROVED.resolve()):
        raise ValueError("an existing child of approved scratch is required; no mkdir")
    return result


def vector_record(path, variant):
    path = Path(path).resolve()
    metadata = path / "vectors.json" if path.is_dir() else path
    directory = approved_directory(metadata.parent)
    if metadata != directory / "vectors.json":
        raise ValueError("vectors must name a directory or its vectors.json")
    record = load(metadata)
    flags = {"VectorsGenerated": True, "SyntheticInput": True, "DevelopmentOnly": True,
             "CalibrationAccepted": False, "HardwareReleaseAllowed": False,
             "NewLensCorrectionVerified": False, "HardwareAccessed": False,
             "PDSAccessed": False, "SimulationExecuted": False, "RTLResultUsedForGolden": False}
    if any(record.get(key) is not value for key, value in flags.items()):
        raise ValueError("explicit independent synthetic/development vector flags required")
    width, height = record.get("Width"), record.get("Height")
    if (type(width) is not int or type(height) is not int or not 8 <= width <= 1920
            or not 8 <= height <= 1080 or width % 8 or height % 8
            or width * height % 256 or record.get("PixelCount") != width * height
            or record.get("TextureVariant") != variant):
        raise ValueError("vector geometry/variant does not meet the full-frame engine contract")
    if (record.get("Rotation", {}).get("AngleDegrees") != 0
            or record["Rotation"].get("CosQ30") != 1 << 30
            or record["Rotation"].get("SinQ30") != 0
            or record.get("Gamma", {}).get("ExpectedMode") != 0
            or record.get("PixelFormat") != "RGB565"):
        raise ValueError("this bench requires exact zero rotation and reset GM0 RGB565 vectors")
    if record.get("ReferenceSHA256") != record.get("ReferenceSHA256After"):
        raise ValueError("vector generator/reference inputs changed during generation")
    watched = {str(metadata): sha(metadata)}
    for name, digest in record["ReferenceSHA256"].items():
        source = (ROOT / name).resolve()
        if not source.is_relative_to(ROOT) or sha(source) != digest:
            raise ValueError("vector reference helper differs: " + name)
        watched[str(source)] = digest
    for name in ("source.mem", "expected.mem", "masks.mem", "crcs.mem", "config.vh"):
        item = record["Files"][name]
        source = (directory / name).resolve()
        if (Path(item["Path"]).resolve() != source or not source.is_relative_to(directory)
                or sha(source) != item["SHA256"] or source.stat().st_size != item["Bytes"]):
            raise ValueError("vector named file/hash differs: " + name)
        watched[str(source)] = item["SHA256"]
    if (directory / "crcs.mem").read_text(encoding="ascii").strip().upper() != record["ExpectedPixelCRC32"]:
        raise ValueError("vector CRC file/metadata differ")
    return directory, record, watched


def run(workdir, vectors0, vectors1, maximum_seconds=1800):
    if type(maximum_seconds) not in (int, float) or not math.isfinite(maximum_seconds) or not 1 <= maximum_seconds <= 7200:
        raise ValueError("maximum-seconds must be finite in [1,7200]")
    work = approved_directory(workdir)
    vector_sets = [vector_record(vectors0, 0), vector_record(vectors1, 1)]
    first, second = [item[1] for item in vector_sets]
    for key in ("Width", "Height", "PixelCount", "IntegerConfig", "RadiusGuardQ22", "FixedPoint", "Model", "Rotation"):
        if first.get(key) != second.get(key):
            raise ValueError("two texture banks must use the same model: " + key)
    if first["SourcePixelCRC32"] == second["SourcePixelCRC32"]:
        raise ValueError("two distinct synthetic source banks required")
    strip_crc = lambda data: re.sub(rb"(?m)^localparam \[31:0\] VEC_EXPECTED_CRC32=.*\r?\n?", b"", data)
    configs = [(item[0] / "config.vh").read_bytes() for item in vector_sets]
    if strip_crc(configs[0]) != strip_crc(configs[1]):
        raise ValueError("vector configs differ beyond their per-frame expected CRC")
    destinations = {"config.vh": configs[0]}
    for variant, (directory, _, _) in enumerate(vector_sets):
        for source, target in (("source.mem", "source"), ("expected.mem", "expected"),
                               ("masks.mem", "masks"), ("crcs.mem", "crc")):
            destinations[f"{target}{variant}.mem"] = (directory / source).read_bytes()
    reserved = (*destinations, REPORT, "cycles.csv", "simulation.log", "summary.json", "summary.txt",
                *(stage + suffix for stage in ("compile", "elaborate", "simulate")
                  for suffix in ("-stdout.log", "-stderr.log")))
    if any((work / name).exists() for name in reserved) or (work / "xsim.dir").exists():
        raise ValueError("fresh work outputs required; existing evidence is never overwritten")
    before = {name: sha(ROOT / name) for name in (*COMPILE, *HEADERS, *HELPERS)}
    if before["rtl/experimental/ddr_compact_neighbour_cache.v"] != DA07_SHA256:
        raise ValueError("this isolated benchmark requires the declared DA07 cache")
    inputs = {}
    for _, _, watched in vector_sets:
        for name, digest in watched.items():
            if name in inputs and inputs[name] != digest:
                raise ValueError("conflicting vector reference bindings")
            inputs[name] = digest
    report = {"Passed": False, "Target": "lens1080_core_offline", "HardwareAccessed": False,
              "PDSAccessed": False, "SyntheticInput": True, "DevelopmentOnly": True,
              "CalibrationAccepted": False, "NewLensCorrectionVerified": False,
              "HardwareReleaseAllowed": False, "StartedUtc": datetime.now(timezone.utc).isoformat(),
              "OutputDirectory": str(work), "MaximumSeconds": maximum_seconds,
              "Width": first["Width"], "Height": first["Height"], "BankStrideUnits4": 1048576,
              "PixelWordFormat": "one16-bit RGB565 word/four hex digits per line; CRC low byte first",
              "ConfigSourceVariant": 0, "PerFrameCRCFiles": ["crc0.mem", "crc1.mem"],
              "VectorMetadata": [{"Path": str(item[0] / "vectors.json"), "SHA256": sha(item[0] / "vectors.json"),
                                  "TextureVariant": i, "SourceCRC32": item[1]["SourcePixelCRC32"],
                                  "ExpectedCRC32": item[1]["ExpectedPixelCRC32"]} for i, item in enumerate(vector_sets)],
              "SourceSHA256": before, "InputSHA256": inputs, "Commands": []}
    deadline = time.monotonic() + maximum_seconds
    try:
        for name, data in destinations.items():
            with (work / name).open("xb") as out:
                out.write(data)
        fixture_hashes = {name: sha(work / name) for name in destinations}
        report["FixtureSHA256"] = fixture_hashes
        bin_dir = Path(os.environ.get("FPGA_VIVADO_BIN", "E:/Vivado/Vivado/2017.4/bin"))
        stages = (("xvlog.bat", ["--sv", *[str(ROOT / name) for name in COMPILE]], "compile"),
                  ("xelab.bat", [TOP, "-s", SNAPSHOT], "elaborate"),
                  ("xsim.bat", [SNAPSHOT, "-runall", "-log", "simulation.log"], "simulate"))
        for executable, arguments, stage in stages:
            command = {"Stage": stage, "NativeArgv": [str(bin_dir / executable), *arguments], "ReturnCode": None}
            report["Commands"].append(command)
            try:
                tool(bin_dir, executable, arguments, work, deadline, stage)
                command.update(ReturnCode=0, ReturnCodeEvidence="fixed tool returned after native wait(0)")
            except (Exception, KeyboardInterrupt) as exc:
                match = re.search(r"failed, exit=(-?\d+)", str(exc))
                if match:
                    command["ReturnCode"] = int(match.group(1))
                command["Error"] = type(exc).__name__ + ": " + str(exc)
                raise
        log = (work / "simulation.log").read_text(encoding="utf-8", errors="replace")
        if "PASS native1080 core:" not in log or re.search(r"(?im)^\s*(?:fatal|error):", log):
            raise ValueError("completed full-frame success marker is absent or simulation reported an error")
        with (work / "cycles.csv").open(newline="", encoding="utf-8-sig") as stream:
            rows = list(csv.DictReader(stream))
        if not rows:
            raise ValueError("nonempty cycles.csv required")
        report.update(Passed=True, PassLines=[line for line in log.splitlines() if line.startswith("PASS")],
                      Cycles=rows, CyclesSHA256=sha(work / "cycles.csv"))
    except (Exception, KeyboardInterrupt) as exc:
        report["Error"] = type(exc).__name__ + ": " + str(exc)
    finally:
        report["SourceSHA256After"] = {name: sha(ROOT / name) if (ROOT / name).is_file() else None for name in before}
        report["InputSHA256After"] = {name: sha(name) if Path(name).is_file() else None for name in inputs}
        report["FixtureSHA256After"] = {name: sha(work / name) if (work / name).is_file() else None for name in destinations}
        if (report["SourceSHA256After"] != before or report["InputSHA256After"] != inputs
                or report.get("FixtureSHA256") != report["FixtureSHA256After"]):
            report.update(Passed=False, SourceOrFixtureDrift=True)
        report["LogSHA256"] = {path.name: sha(path) for path in work.glob("*.log") if path.is_file()}
        report["BenchSummarySHA256"] = {name: sha(work / name) for name in ("summary.json", "summary.txt") if (work / name).is_file()}
        report["EndedUtc"] = datetime.now(timezone.utc).isoformat()
        report["Limits"] = ("Offline synthetic zero-degree/raster core and bank-ownership benchmark only. "
            "Source/golden files contain per-pixel16-bit words; config0 CRC is not substituted for crc1. "
            "No sensor1080 mode, lens calibration, full-system1080p30, HDMI, physical FPS, PDS timing, bitstream or hardware claim.")
        with (work / REPORT).open("x", encoding="utf-8") as out:
            json.dump(report, out, indent=2, allow_nan=False)
            out.write("\n")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workdir", type=Path, required=True)
    parser.add_argument("--vectors0", type=Path, required=True)
    parser.add_argument("--vectors1", type=Path, required=True)
    parser.add_argument("--maximum-seconds", type=float, default=1800.)
    args = parser.parse_args()
    try:
        result = run(args.workdir, args.vectors0, args.vectors1, args.maximum_seconds)
    except (ValueError, OSError, KeyError) as exc:
        parser.exit(1, str(exc) + "\n")
    print(json.dumps({"Report": str(args.workdir.resolve() / REPORT), "Passed": result["Passed"],
                      "Commands": result["Commands"], "Error": result.get("Error")}, indent=2))
    return 0 if result["Passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
