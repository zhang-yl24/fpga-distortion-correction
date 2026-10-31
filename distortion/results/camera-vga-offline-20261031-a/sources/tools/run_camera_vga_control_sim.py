"""Run the actual camera board startup/fault control with explicit status stubs.

The real 27 MHz warmup uses an 8 ms test parameter. The fixed power-on delay is
accelerated, and no sensor bus, camera data, memory or physical IP is exercised.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import tempfile
import time

from run_gamma_pipeline_d5_sim import tool
from simulation_tools import resolve_vivado_bin

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "build/camera-vga-control"
TEMP_BASE = Path(tempfile.gettempdir()) / "codex-camera-vga-control"
COMPILE = ("rtl/experimental/capture_warmup.v", "board/camera_vga_output_top.v",
           "tests/processed_output_ip_stubs.sv", "tests/camera_vga_control_stubs.sv",
           "tests/tb_camera_vga_control.sv")
HEADERS = ("board/board1080-synthetic.vh",)
HELPERS = ("tools/run_camera_vga_control_sim.py", "tools/simulation_tools.py",
           "tools/run_gamma_pipeline_d5_sim.py")
REPORT = "camera-vga-control-simulation.json"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def module_header(raw, module):
    match = re.search(r"\bmodule\s+" + re.escape(module) + r"\b", raw)
    if match is None:
        raise ValueError("stub/reference module missing: " + module)
    return raw[match.start():raw.index(");", match.start()) + 2]


def header_bindings():
    bindings = {}
    for name in ("tests/processed_output_ip_stubs.sv", "tests/camera_vga_control_stubs.sv"):
        raw_stub = (ROOT / name).read_text(encoding="utf-8-sig")
        for line in raw_stub.splitlines():
            if not line.startswith("// HEADER_BINDING "):
                continue
            item = json.loads(line[len("// HEADER_BINDING "):])
            raw = (ROOT / item["Path"]).read_text(encoding="utf-8-sig")
            header = module_header(raw, item["Module"])
            if (hashlib.sha256(header.encode()).hexdigest() != item["HeaderSHA256"]
                    or module_header(raw_stub, item["Module"]) != header):
                raise ValueError("explicit stub/reference header drift: " + item["Module"])
            if item["Module"] in bindings:
                raise ValueError("duplicate explicit stub module")
            bindings[item["Module"]] = {**item, "Stub": name,
                                        "FullReferenceSHA256": sha(ROOT / item["Path"]),
                                        "ProductionBodyCompiled": False}
    if set(bindings) != {"bringup_pll", "hdmi_tx_init", "ddr3_test",
                         "ov5640_cadence_trial_init", "camera_vga_video_system"}:
        raise ValueError("exact five explicit high-level stub bindings required")
    return bindings


def run(workdir, maximum_seconds=180):
    work = Path(workdir).resolve()
    if work.parent not in (BASE.resolve(), TEMP_BASE.resolve()) or work.exists():
        raise ValueError("fresh direct child of build/camera-vga-control or the canonical "
                         "temporary codex-camera-vga-control directory required")
    if not 30 <= maximum_seconds <= 600:
        raise ValueError("whole-run deadline must be 30..600 seconds")
    bindings = header_bindings()
    references = tuple(item["Path"] for item in bindings.values())
    before = {name: sha(ROOT / name) for name in (*COMPILE, *HEADERS, *HELPERS, *references)}
    work.mkdir(parents=True)
    started = time.monotonic()
    report = {"Schema": "camera-vga-board-control-digital-simulation-v1", "Passed": False,
              "StartedUTC": datetime.now(timezone.utc).isoformat(), "MaximumSeconds": maximum_seconds,
              "SourceSHA256": before, "ExplicitStubBindings": bindings, "Commands": [],
              "ActualBoardTopExecuted": True, "ActualWarmupExecuted": True,
              "ProductionSystemExecuted": False, "CameraInitBodyExecuted": False,
              "PhysicalIPExecuted": False, "HardwareAccessed": False, "PDSAccessed": False,
              "PhysicalInputExercised": False, "PowerDelayAccelerated": True,
              "Limits": "Board startup, fault retention and LED control only. Warmup shortened to 8 ms; "
                        "fixed power-on counter accelerated. Sensor/System/PLL/TX/DDR are status stubs. "
                        "No SCCB, camera pixels, memory transactions, native throughput, stopped-clock "
                        "recovery or physical HDMI acceptance."}
    try:
        for name in HEADERS:
            staged = work / name
            staged.parent.mkdir(parents=True, exist_ok=True)
            with staged.open("xb") as stream:
                stream.write((ROOT / name).read_bytes())
        bin_dir = resolve_vivado_bin(ROOT.parent)
        for executable, arguments, stage in (
                ("xvlog.bat", ["--sv", *[str(ROOT / name) for name in COMPILE]], "compile"),
                ("xelab.bat", ["tb_camera_vga_control", "-s", "camera_vga_control_tb",
                               "--timescale", "1ps/1ps"], "elaborate"),
                ("xsim.bat", ["camera_vga_control_tb", "-runall", "-log", "simulation.log"], "simulate")):
            command = {"Stage": stage, "NativeArgv": [str(bin_dir / executable), *arguments],
                       "ReturnCode": None}
            report["Commands"].append(command)
            tool(bin_dir, executable, arguments, work, started + maximum_seconds, stage)
            command["ReturnCode"] = 0
        log = (work / "simulation.log").read_text(encoding="utf-8", errors="replace")
        if "CAMERA_VGA_CONTROL_PASS" not in log or re.search(r"(?im)^\s*(?:fatal|error):", log):
            raise ValueError("camera board-control assertions did not complete")
        summary = json.loads((work / "summary.json").read_text(encoding="utf-8"))
        expected = {"Passed": True, "StartupCases": 8, "RuntimeCases": 7, "ResetChecks": 17,
                    "ReleaseEvents": 9, "LEDChecks": 4, "ChatterChecks": 1, "WarmupCycles": 216000,
                    "ReferenceClockHz": 27000000, "PowerDelayAccelerated": True}
        if summary != expected:
            raise ValueError("camera control coverage summary differs: " + repr(summary))
        report.update(Passed=True, Summary=summary,
                      PassLines=[line for line in log.splitlines() if "_PASS" in line])
    except (Exception, KeyboardInterrupt) as error:
        report["Error"] = str(error)
    finally:
        report["SourceDrift"] = [name for name, digest in before.items() if sha(ROOT / name) != digest]
        report["HeaderDrift"] = [name for name in HEADERS
                                 if not (work / name).is_file() or sha(work / name) != before[name]]
        report["Passed"] = report["Passed"] and not report["SourceDrift"] and not report["HeaderDrift"]
        report["ElapsedSeconds"] = round(time.monotonic() - started, 3)
        report["EvidenceSHA256"] = {p.name: sha(p) for p in work.iterdir()
                                    if p.is_file() and p.suffix in (".log", ".json")}
        (work / REPORT).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--maximum-seconds", type=int, default=180)
    args = parser.parse_args()
    report = run(args.work_dir, args.maximum_seconds)
    print(json.dumps({"Passed": report["Passed"], "Error": report.get("Error"),
                      "ElapsedSeconds": report["ElapsedSeconds"], "Report": str(args.work_dir / REPORT)}))
    return 0 if report["Passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
