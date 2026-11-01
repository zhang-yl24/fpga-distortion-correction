"""Self-contained offline real-I2C and full-size 720p sensor/frontend tests.

Requires Vivado xvlog/xelab/xsim only. No absent historical build tree, PDS,
camera, serial or JTAG access. Every run gets a fresh source-bound work folder.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import uuid

import prepare_camera720_sensor as sensor

ROOT = sensor.ROOT
SOURCES = tuple(dict.fromkeys((
    "rtl/reg16_i2c.v", *sensor.RETAINED, sensor.INIT, sensor.FRONTEND,
    "tests/tb_ov5640_current720_init.sv", "tests/tb_ov5640_current720_frontend.sv",
    "tools/prepare_camera720_sensor.py", "tools/run_camera720_sensor_sim.py",
)))
INIT_CASES = (
    "complete720_readback_unique_wake_rmw_and_verified_data_high",
    "pad_read_address_nack_no_wake",
    "initial_clock_default_mismatch_no_pll_writes",
    "preflight_geometry_mismatch_no_wake",
    "postwake_read_nack_never_configured",
    "masked_rmw_match_cannot_excuse_fullbyte_noack",
)
FRONTEND_MARKERS = (
    "PASS frontend configured remains disarmed before live geometry",
    "PASS frontend one complete good frame remains disarmed",
    "PASS frontend full2560x720 lines and PCLK-domain edge accounting; two fresh frames",
    "PASS frontend resumed PCLK cannot clear sticky failure",
    "PASS CURRENT720 frontend:",
)


def stop_owned(process: subprocess.Popen, work: Path, stem: str) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        result = subprocess.run(
            [str(Path(os.environ["SystemRoot"]) / "System32/taskkill.exe"),
             "/PID", str(process.pid), "/T", "/F"],
            capture_output=True, timeout=15, check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        (work / (stem + "-owned-stop.log")).write_bytes(result.stdout + result.stderr)
    else:
        process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=10)


def run_tool(bin_dir: Path, name: str, arguments: list[str], work: Path,
             deadline: float, stem: str) -> None:
    executable = bin_dir / (name + (".bat" if os.name == "nt" else ""))
    if not executable.is_file():
        raise ValueError("Vivado simulation tool missing: " + str(executable))
    tokens = [str(executable), *arguments]
    if os.name == "nt":
        if any(re.search(r'["\r\n&|<>^%!]', token) for token in tokens):
            raise ValueError("Unsupported shell metacharacter in simulation argument")
        comspec = os.environ.get("ComSpec", "cmd.exe")
        if re.search(r'["\r\n&|<>^%!]', comspec):
            raise ValueError("Unsupported command interpreter path")
        command = " ".join('"' + token + '"' for token in tokens)
        invocation = '"' + comspec + '" /d /s /c "' + command + '"'
    else:
        invocation = tokens
    if deadline <= time.monotonic():
        raise TimeoutError("Whole sensor simulation time bound exhausted")
    process = None
    with (work / (stem + "-stdout.log")).open("wb") as stdout, \
            (work / (stem + "-stderr.log")).open("wb") as stderr:
        try:
            process = subprocess.Popen(invocation, cwd=work, stdout=stdout, stderr=stderr,
                                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            code = process.wait(timeout=max(0.1, deadline - time.monotonic()))
            if code:
                raise RuntimeError(name + " exited " + str(code) + "; see " + stem + " logs")
        finally:
            if process is not None:
                stop_owned(process, work, stem)


def checked_log(work: Path, name: str) -> str:
    text = (work / name).read_text(encoding="utf-8", errors="replace")
    if re.search(r"(?im)^\s*(?:fatal|error):", text):
        raise ValueError("Simulation reported an error: " + name)
    return text


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--maximum-seconds", type=int, default=900)
    parser.add_argument("--output-directory", type=Path)
    parser.add_argument("--vivado-bin", type=Path)
    args = parser.parse_args()
    if not 60 <= args.maximum_seconds <= 1800:
        parser.error("--maximum-seconds must be within 60..1800")
    port = sensor.verify()
    work_root = (ROOT / "work").resolve()
    work = (args.output_directory or work_root / ("camera720-sensor-sim-" +
            datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + "-" + uuid.uuid4().hex[:6])).resolve()
    if work == work_root or not work.is_relative_to(work_root) or work.exists():
        parser.error("Use a fresh output directory strictly below distortion/work")
    config_path = ROOT.parent / "team-config.local.json"
    config = json.loads(config_path.read_text(encoding="utf-8-sig")) if config_path.is_file() else {}
    configured_bin = args.vivado_bin or os.environ.get("FPGA_VIVADO_BIN") or config.get("vivado_bin")
    if not configured_bin:
        parser.error("Set --vivado-bin, FPGA_VIVADO_BIN, or team-config.local.json vivado_bin")
    bin_dir = Path(configured_bin)
    before = {name: sensor.sha(ROOT / name) for name in SOURCES}
    work.mkdir(parents=True, exist_ok=False)
    report = {
        "Passed": False, "HardwareAccessed": False, "PDSAccessed": False,
        "SyntheticOnly": True, "HardwareReleaseAllowed": False,
        "HistoricalGeneratorReproduced": False, "PortVerification": port,
        "SourceSHA256": before, "SourceSHA256After": {}, "OutputDirectory": str(work),
        "MeasuredFPS": None, "TestCases": [],
        "Limits": "Real reg16_i2c with synthetic open-drain sensor register model and two full-size synthetic 2560-byte by 720-line frames per PCLK scenario. No pixel-content/DDR/UART transport, board pins, measured clocks/fps, analog PLL lock, optical calibration or physical CDC/timing acceptance. Model reset/delay timings are accelerated; production initializer delays and bus defaults remain unchanged.",
    }
    deadline = time.monotonic() + args.maximum_seconds
    try:
        files = [str(ROOT / name) for name in SOURCES
                 if name.endswith((".v", ".sv")) and name != sensor.BASE_INIT]
        run_tool(bin_dir, "xvlog", ["--sv", "-i", str(ROOT), *files], work, deadline, "compile")
        for top in ("tb_ov5640_current720_init", "tb_ov5640_current720_frontend"):
            run_tool(bin_dir, "xelab", [top, "-s", top], work, deadline, "elaborate-" + top)
        run_tool(bin_dir, "xsim", ["tb_ov5640_current720_init", "-runall", "-log", "init.log"],
                 work, deadline, "simulate-init")
        text = checked_log(work, "init.log")
        if re.findall(r"(?m)^PASS_CASE (\S+)\s*$", text) != list(INIT_CASES) or "PASS RGB565720 init:" not in text:
            raise ValueError("Required retained-sequence success/failure tests did not all pass")
        report["TestCases"].extend(INIT_CASES)
        for scenario, plusargs in (("pclk42", []), ("pclk47_25", ["-testplusarg", "pclk_upper"])):
            run_tool(bin_dir, "xsim", ["tb_ov5640_current720_frontend", "-runall", "-log",
                     scenario + ".log", *plusargs], work, deadline, "simulate-" + scenario)
            text = checked_log(work, scenario + ".log")
            if not all(marker in text for marker in FRONTEND_MARKERS):
                raise ValueError("Required two-frame admission/clock-stop checks failed: " + scenario)
            report["TestCases"].append(scenario + "_two_good_frames_and_sticky_clock_stop")
        run_tool(bin_dir, "xsim", ["tb_ov5640_current720_frontend", "-runall", "-log", "bad_line.log",
                 "-testplusarg", "bad_line"], work, deadline, "simulate-bad-line")
        text = checked_log(work, "bad_line.log")
        if "PASS CURRENT720 frontend malformed line blocks admission despite configured registers" not in text:
            raise ValueError("Malformed line did not block frontend admission")
        report["TestCases"].append("malformed_first_line_blocks_admission")
        sensor.verify()
        report["SourceSHA256After"] = {name: sensor.sha(ROOT / name) for name in SOURCES}
        if report["SourceSHA256After"] != before:
            raise ValueError("Sensor simulation inputs changed during run")
        report["EvidenceSHA256"] = {name: sensor.sha(work / name)
                                   for name in ("init.log", "pclk42.log", "pclk47_25.log", "bad_line.log", "rgb565720-transactions.csv")}
        report["Passed"] = True
    except Exception as error:
        report["Error"] = str(error)
        print(str(error), file=sys.stderr)
    finally:
        report["EndedUtc"] = datetime.now(timezone.utc).isoformat()
        path = work / "camera720-sensor-simulation.json"
        path.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8", newline="\n")
        print(path)
    return 0 if report["Passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
