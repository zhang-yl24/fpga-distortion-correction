"""Verify the synthesizable controlled processing/output source, without hardware.

An independent Python RGB565 oracle supplies every active pixel. Small tests
cover complete raster timing, midframe disable, restart and asynchronous reset;
native verifies one complete1920x1080 raster at nominal27MHz.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import time
import zlib

from run_gamma_pipeline_d5_sim import tool
from simulation_tools import resolve_vivado_bin

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "build/processed-output-pattern"
COMPILE = ("rtl/experimental/processed_output_pattern.v", "tests/tb_processed_output_pattern.sv")
SOURCES = (*COMPILE, "tools/run_processed_output_pattern_sim.py", "tools/simulation_tools.py", "tools/run_gamma_pipeline_d5_sim.py")
REPORT = "processed-output-pattern-simulation.json"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def pixel565(x, y, width, height):
    """Public oracle formula, suitable for the parent integration's raw input."""
    cross_x = width // 256 if width >= 256 else 0
    cross_y = height // 256 if height >= 256 else 0
    if x in (0, width-1) or y in (0, height-1):
        return 0xffff
    if abs(x-width//2) <= cross_x or abs(y-height//2) <= cross_y:
        return 0xf800
    if x % 32 == 0 or y % 32 == 0:
        return 0x07e0
    light = (x // 32 + y // 32) % 2
    red = (20 if light else 4) + x % 8
    green = 8 + y % 32
    blue = (4 if light else 20) + y % 8
    return red << 11 | green << 5 | blue


def expand565(pixel):
    red, green, blue = pixel >> 11, (pixel >> 5) & 63, pixel & 31
    return ((red << 3 | red >> 2) << 16
            | (green << 2 | green >> 4) << 8 | blue << 3 | blue >> 2)


def create_oracle(work, width, height):
    words = [pixel565(x, y, width, height) for y in range(height) for x in range(width)]
    if any(word == 0 for word in words):
        raise ValueError("every active pixel must be nonblack")
    with (work / "expected-rgb.mem").open("x", encoding="ascii", newline="\n") as stream:
        stream.writelines(f"{expand565(word):06x}\n" for word in words)
    raw = b"".join(word.to_bytes(2, "little") for word in words)
    return {"Width": width, "Height": height, "Pixels": len(words),
            "RGB565CRC32": f"{zlib.crc32(raw):08X}", "EveryActivePixelNonBlack": True,
            "ExpectedSHA256": sha(work / "expected-rgb.mem")}


def run(workdir, native=False, maximum_seconds=180):
    if not 30 <= maximum_seconds <= 300:
        raise ValueError("whole-run deadline must be30..300seconds")
    work = Path(workdir).resolve()
    if work.parent != BASE.resolve() or work.exists():
        raise ValueError("fresh child of build/processed-output-pattern required")
    before = {name: sha(ROOT / name) for name in SOURCES}
    work.mkdir(parents=True)
    started = time.monotonic()
    report = {"Schema": "processed-output-pattern-digital-simulation-v1", "Passed": False,
              "StartedUTC": datetime.now(timezone.utc).isoformat(), "Native": native,
              "ClockHz": 27000000, "SourceSHA256": before, "Commands": [],
              "HardwareAccessed": False, "PDSAccessed": False,
              "Limits": "Controlled synthetic source only; no camera, DDR, processing, PHY or physical HDMI acceptance."}
    try:
        width, height = (1920, 1080) if native else (64, 32)
        report["Oracle"] = create_oracle(work, width, height)
        bin_dir = resolve_vivado_bin(ROOT.parent)
        compile_args = ["--sv", *(["-d", "NATIVE"] if native else []), *[str(ROOT / p) for p in COMPILE]]
        for executable, arguments, stage in (
            ("xvlog.bat", compile_args, "compile"),
            ("xelab.bat", ["tb_processed_output_pattern", "-s", "processed_output_pattern_tb"], "elaborate"),
            ("xsim.bat", ["processed_output_pattern_tb", "-runall", "-log", "simulation.log"], "simulate")):
            command = {"Stage": stage, "NativeArgv": [str(bin_dir / executable), *arguments], "ReturnCode": None}
            report["Commands"].append(command)
            tool(bin_dir, executable, arguments, work, started+maximum_seconds, stage)
            command["ReturnCode"] = 0
        log = (work / "simulation.log").read_text(encoding="utf-8", errors="replace")
        if "PROCESSED_OUTPUT_PATTERN_PASS" not in log or re.search(r"(?im)^\s*(?:fatal|error):", log):
            raise ValueError("pattern assertions did not complete")
        summary = json.loads((work / "summary.json").read_text(encoding="utf-8"))
        expected_rasters = 1 if native else 3
        if (not summary["Passed"] or summary["Width"] != width or summary["Height"] != height
                or summary["FullRasters"] != expected_rasters
                or summary["PixelsCompared"] < expected_rasters*width*height
                or summary["AsyncResetChecks"] != (0 if native else 1)
                or summary["ClockHz"] != 27000000 or not summary["MidFrameDisableCompleted"]):
            raise ValueError("pattern coverage summary differs")
        report.update(Passed=True, Summary=summary,
                      PassLines=[line for line in log.splitlines() if "_PASS" in line])
    except (Exception, KeyboardInterrupt) as error:
        report["Error"] = str(error)
    finally:
        report["SourceDrift"] = [name for name, digest in before.items() if sha(ROOT / name) != digest]
        report["FixtureDrift"] = ("Oracle" in report and sha(work / "expected-rgb.mem") != report["Oracle"]["ExpectedSHA256"])
        report["Passed"] = report["Passed"] and not report["SourceDrift"] and not report["FixtureDrift"]
        report["ElapsedSeconds"] = round(time.monotonic()-started, 3)
        report["EvidenceSHA256"] = {p.name: sha(p) for p in work.iterdir() if p.is_file() and p.suffix in (".log", ".mem", ".json")}
        (work / REPORT).write_text(json.dumps(report, indent=2)+"\n", encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--native", action="store_true")
    parser.add_argument("--maximum-seconds", type=int, default=180)
    args = parser.parse_args()
    report = run(args.work_dir, args.native, args.maximum_seconds)
    print(json.dumps({"Passed": report["Passed"], "Error": report.get("Error"),
                      "ElapsedSeconds": report["ElapsedSeconds"], "Report": str(args.work_dir / REPORT)}))
    return 0 if report["Passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
