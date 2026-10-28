"""One bounded display-consumer directed RTL run. No CAD or device access."""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import hashlib
import json
import math
import os
import re
import time

from run_gamma_pipeline_d5_sim import tool

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "build/offline-20261024/board1080-integration-20261027-a/scan"
REPORT = "board1080-scan-simulation.json"
TOP = "tb_board1080_scan"
SNAPSHOT = "board1080_scan"
COMPILE = ("rtl/experimental/ddr_video_output_1080_board.v", "rtl/video_async_fifo.v",
           "tests/tb_board1080_scan.sv")
SOURCES = (*COMPILE, "rtl/video_crc32.vh", "tools/run_board1080_scan_sim.py",
           "tools/run_gamma_pipeline_d5_sim.py")
OLD_CORE = "rtl/experimental/ddr_video_output_1080_core.v"
OLD_CORE_SHA = "8a8923343c440e3ade133bf1b90ff88dfe1a7d56444b8b64a3fa33d04f3bb6c8"
OLD_B = ROOT / "build/offline-20261024/gamma-pipeline-da07-k320-build-20261027-b/validated-build.json"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"),
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError("nonfinite JSON")))


def run(workdir, maximum_seconds=120):
    if (type(maximum_seconds) not in (int, float) or not math.isfinite(maximum_seconds)
            or not 1 <= maximum_seconds <= 120):
        raise ValueError("maximum-seconds must be finite in [1,120]")
    work = Path(workdir).resolve()
    if not work.is_dir() or work == BASE.resolve() or not work.is_relative_to(BASE.resolve()):
        raise ValueError("existing fresh child of the approved scan directory required; no mkdir")
    outputs = (REPORT, "summary.json", "simulation.log",
               *(stage + suffix for stage in ("compile", "elaborate", "simulate")
                 for suffix in ("-stdout.log", "-stderr.log")))
    if any((work / name).exists() for name in outputs) or (work / "xsim.dir").exists():
        raise ValueError("fresh outputs required; old failures/evidence are never replaced")
    before = {name: sha(ROOT / name) for name in SOURCES}
    protected = dict(load(OLD_B)["SourceSHA256"])
    protected[OLD_CORE] = OLD_CORE_SHA
    if any(sha(ROOT / name) != value for name, value in protected.items()):
        raise ValueError("old B or original1080 display source differs from its frozen binding")
    old_manifest = sha(OLD_B)
    report = {
        "Passed": False, "Marker": "FPGA-1031-BOARD1080-SCAN-DIRECTED",
        "Target": "ddr_video_output_1080_board", "StartedUtc": datetime.now(timezone.utc).isoformat(),
        "MaximumSeconds": maximum_seconds, "MaxPixelCycles": 2000000, "Geometry": [32, 16],
        "HardwareAccessed": False, "PDSAccessed": False, "HardwareReleaseAllowed": False,
        "NativeTimingVerified": False, "PHYVerified": False, "RealSynchronousReadFIFO": True,
        "DefaultRasterContract": {"size": [1920, 1080], "total": [2200, 1125],
                                  "nominal_pixel_hz": 74250000, "nominal_fps": 30},
        "SourceSHA256": before, "ProtectedSourceSHA256": protected,
        "ProtectedBManifest": {"Path": str(OLD_B), "SHA256": old_manifest},
        "OutputDirectory": str(work), "Commands": [],
    }
    deadline = time.monotonic() + maximum_seconds
    try:
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
        text = (work / "simulation.log").read_text(encoding="utf-8", errors="replace")
        if ("PASS board1080 scan:" not in text or "$finish called" not in text
                or re.search(r"(?im)^\s*(?:fatal|error):", text)):
            raise ValueError("all-case scan completion marker absent or RTL failure")
        summary = load(work / "summary.json")
        expected = {"passed": True, "width": 32, "height": 16, "cases": 9, "good_frames": 8,
                    "real_synchronous_fifo": True, "native_timing_verified": False, "hardware_verified": False}
        if any(type(summary.get(key)) is not type(value) or summary[key] != value for key, value in expected.items()):
            raise ValueError("directed scan result/geometry/coverage differs")
        for key in ("fifo_requests", "fifo_returns", "ready_stall_cycles", "return_latency_events"):
            if type(summary.get(key)) is not int or summary[key] <= 0:
                raise ValueError("nonzero actual FIFO pressure/latency required: " + key)
        if summary["bad_events"] < 4 or summary["fault_cases"] < 6:
            raise ValueError("required failure/quarantine cases did not execute")
        report.update(Passed=True, Summary=summary,
                      PassLines=[line for line in text.splitlines() if line.startswith("PASS")])
    except (Exception, KeyboardInterrupt) as exc:
        report["Error"] = type(exc).__name__ + ": " + str(exc)
    finally:
        report["SourceSHA256After"] = {name: sha(ROOT / name) if (ROOT / name).is_file() else None for name in before}
        report["ProtectedSourceSHA256After"] = {name: sha(ROOT / name) if (ROOT / name).is_file() else None for name in protected}
        report["ProtectedBManifestSHA256After"] = sha(OLD_B)
        if (report["SourceSHA256After"] != before or report["ProtectedSourceSHA256After"] != protected
                or report["ProtectedBManifestSHA256After"] != old_manifest):
            report.update(Passed=False, SourceDrift=True)
        report["LogSHA256"] = {p.name: sha(p) for p in work.glob("*.log") if p.is_file()}
        report["SummarySHA256"] = sha(work / "summary.json") if (work / "summary.json").is_file() else None
        report["EndedUtc"] = datetime.now(timezone.utc).isoformat()
        report["Limits"] = ("Small functional consumer/FIFO test only. No DDR-reader/system release integration, "
            "native timing/resource/CDC constraints/HDMI PHY, sensor mode, optics or hardware proof. "
            "draining means fault-discard mode until common reset; a held old good done bus is historical, "
            "and parent release MUST also require !failed, reader CRC/done and actual FIFO/transaction drain.")
        with (work / REPORT).open("x", encoding="utf-8") as stream:
            json.dump(report, stream, indent=2, allow_nan=False)
            stream.write("\n")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workdir", type=Path, required=True)
    parser.add_argument("--maximum-seconds", type=float, default=120)
    args = parser.parse_args()
    try:
        result = run(args.workdir, args.maximum_seconds)
    except (ValueError, KeyError, OSError) as exc:
        parser.exit(1, str(exc) + "\n")
    print(json.dumps({"Report": str(args.workdir.resolve() / REPORT), "Passed": result["Passed"],
                      "Commands": result["Commands"], "Error": result.get("Error")}, indent=2))
    return 0 if result["Passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
