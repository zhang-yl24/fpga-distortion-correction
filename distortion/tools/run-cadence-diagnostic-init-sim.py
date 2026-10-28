"""Offline-only, source-bound simulation of the diagnostic init and real I2C.

Creates one fresh log directory below the already approved scratch root. Never
loads PDS, opens a serial port, programs a board, or edits existing evidence.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
APPROVED = ROOT / "build" / "offline-20261024"
TOP = "tb_ov5640_cadence_diagnostic_init"
SOURCES = (
    "rtl/reg16_i2c.v",
    "rtl/experimental/ov5640_cadence_trial_init.v",
    "rtl/experimental/ov5640_cadence_diagnostic_init.v",
    "board/ov5640_cadence_trial_commands.vh",
    "tests/tb_ov5640_cadence_diagnostic_init.sv",
    "tools/run-cadence-diagnostic-init-sim.py",
)
CASES = (
    "original_success_full_264",
    "final_data_noack_equal_readback",
    "final_data_noack_then_read_address_nack",
    "final_data_noack_then_wrong_valid_value",
    "write_device_address_nack",
    "acknowledged_write_then_read_address_nack",
    "read_phase_device_nack_and_bounded_probe_timeout",
)
SUMMARY = ("PASS diagnostic init: seven real-controller line-model cases; legacy miter; "
           "quarter68/full7FF0; three read-only probes maximum; no hardware or RAW authorization.")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_minimal_clone() -> None:
    """All old text, after normalized newlines, survives the marked additions."""
    baseline = (ROOT / SOURCES[1]).read_text(encoding="utf-8")
    draft = (ROOT / SOURCES[2]).read_text(encoding="utf-8")
    for name in ("DECLARATIONS", "RESET", "OBSERVATIONS", "FAILED_READ_ONLY_PROBES"):
        pattern = (r"(?m)^// DIAGNOSTIC_ADDITION_BEGIN " + name +
                   r"\n.*?^// DIAGNOSTIC_ADDITION_END " + name + r"\n")
        draft, count = re.subn(pattern, "", draft, flags=re.S)
        if count != 1:
            raise ValueError("Expected exactly one marked diagnostic insertion: " + name)
    draft = draft.replace("module ov5640_cadence_diagnostic_init #(",
                          "module ov5640_cadence_trial_init #(", 1)
    draft = draft.replace("DYNAMIC_PAD_MASK=0, DIAGNOSTIC_PROBES=1", "DYNAMIC_PAD_MASK=0", 1)
    draft, count = re.subn(r"    output reg \[7:0\] observed_value, expected_value,\n.*?"
                          r"    output reg diagnostic_probe_done\);",
                          "    output reg [7:0] observed_value, expected_value);", draft, count=1, flags=re.S)
    if count != 1 or draft != baseline:
        raise ValueError("New diagnostic RTL changes unmarked original initialization text")


def stop_owned(process: subprocess.Popen, work: Path, stem: str) -> None:
    if process.poll() is not None:
        return
    # PID is obtained directly from this Popen; never discover/kill other tools.
    if os.name == "nt":
        result = subprocess.run([str(Path(os.environ["SystemRoot"]) / "System32" / "taskkill.exe"),
                                 "/PID", str(process.pid), "/T", "/F"],
                                capture_output=True, timeout=15, check=False)
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
    tool = bin_dir / name
    if not tool.is_file():
        raise ValueError("Configured Vivado simulation tool missing: " + str(tool))
    tokens = [str(tool), *arguments]
    if any(re.search(r'["\r\n&|<>^%!]', token) for token in tokens):
        raise ValueError("Unsupported shell metacharacter in fixed simulation argument")
    # Windows .bat entry points require cmd, with every fixed argument quoted.
    command = " ".join('"' + token + '"' for token in tokens)
    # Pass the already validated cmd command line verbatim. A list would run
    # Python's C-runtime quoting, adding backslashes that cmd does not unescape.
    comspec = os.environ.get("ComSpec", "cmd.exe")
    if re.search(r'["\r\n&|<>^%!]', comspec):
        raise ValueError("Unsupported command interpreter path")
    invocation = '"' + comspec + '" /d /s /c "' + command + '"'
    process = None
    with (work / (stem + "-stdout.log")).open("wb") as stdout, (work / (stem + "-stderr.log")).open("wb") as stderr:
        try:
            process = subprocess.Popen(invocation, cwd=work, stdout=stdout, stderr=stderr,
                                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("Whole offline simulation bound exhausted")
            code = process.wait(timeout=remaining)
            if code != 0:
                raise RuntimeError(name + " exited " + str(code) + "; see " + stem + " logs")
        finally:
            if process is not None:
                stop_owned(process, work, stem)


def audit_trace(work: Path) -> dict:
    path = work / "diagnostic-transactions.csv"
    with path.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    probes = {n: [] for n in range(7)}
    for row in rows:
        if int(row["state"]) == 13:
            if row["read"] != "1":
                raise ValueError("Failed-state transaction was not read-only")
            probes[int(row["case"])].append((int(row["address"], 16), int(row["bus_error"], 16)))
    for case, observed in probes.items():
        expected = [] if case < 2 else [(0x300A, 15 if case == 6 else 0),
                                        (0x300B, 1 if case == 2 else 0), (0x3018, 0)]
        if observed != expected:
            raise ValueError("Unexpected bounded probe trace in case " + str(case))
    return {"Path": str(path), "SHA256": sha(path), "Rows": len(rows),
            "FailedStateProbeCounts": {str(k): len(v) for k, v in probes.items()},
            "ReadValueValidity": "raw_read_value is usable only when bus_error=0; errors retain invalid placeholders"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-directory", type=Path)
    parser.add_argument("--maximum-seconds", type=int, default=600)
    args = parser.parse_args()
    if not 30 <= args.maximum_seconds <= 1800:
        parser.error("--maximum-seconds must be in 30..1800")
    if not APPROVED.is_dir():
        parser.error("Approved scratch root must already exist")
    verify_minimal_clone()
    work = (args.output_directory or APPROVED / ("cadence-diagnostic-sim-" +
            datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + "-" + uuid.uuid4().hex[:6])).resolve()
    if not work.is_relative_to(APPROVED.resolve()) or work == APPROVED.resolve() or work.exists():
        parser.error("Use a fresh directory strictly below approved scratch; never overwrite")
    config_path = ROOT.parent / "team-config.local.json"
    config = json.loads(config_path.read_text(encoding="utf-8-sig")) if config_path.is_file() else {}
    bin_dir = Path(os.environ.get("FPGA_VIVADO_BIN") or config.get("vivado_bin") or r"E:\Vivado\Vivado\2017.4\bin")
    before = {name: sha(ROOT / name) for name in SOURCES}
    report = {"Passed": False, "HardwareAccessed": False, "PDSAccessed": False,
              "SourceSHA256": before, "SourceSHA256After": {}, "OutputDirectory": str(work),
              "StartedUtc": datetime.now(timezone.utc).isoformat(), "RequiredCases": list(CASES),
              "OriginalTextPreservedExceptNamedDiagnosticAdditions": True,
              "Parameters": {"I2C_QUARTER_CYCLES": 68, "I2C_TIMEOUT_CYCLES": 1350000,
                             "trial_pad_mask": "7FF0", "CHECK_WRITES": 1, "DIAGNOSTIC_PROBES": 1,
                             "RESET_CYCLES_simulation_only": 8, "WAIT_CYCLES_simulation_only": 12,
                             "MS_CYCLES_simulation_only": 2},
              "Limits": "Synthetic open-drain line model with real reg16_i2c and original-init miter. No hardware acceptance, measured voltage/physical timing, wiring diagnosis, optical claim, or RAW authorization. Probe results cannot clear the original failure. Physical FPC repair is assessed by separate real-board baseline runs."}
    work.mkdir(parents=True, exist_ok=False)
    report_path = work / "cadence-diagnostic-init-simulation.json"
    deadline = time.monotonic() + args.maximum_seconds
    try:
        files = [str(ROOT / n) for n in SOURCES if n.endswith((".v", ".sv"))]
        run_tool(bin_dir, "xvlog.bat", ["--sv", *files], work, deadline, "compile")
        run_tool(bin_dir, "xelab.bat", [TOP, "-s", "cadence_diagnostic_init"], work, deadline, "elaborate")
        run_tool(bin_dir, "xsim.bat", ["cadence_diagnostic_init", "-runall", "-log", "diagnostic-init-simulation.log"], work, deadline, "simulate")
        log = work / "diagnostic-init-simulation.log"
        text = log.read_text(encoding="utf-8", errors="replace")
        observed = re.findall(r"(?m)^PASS_CASE (\S+)\s*$", text)
        if observed != list(CASES) or SUMMARY not in text or re.search(r"(?im)^\s*(?:fatal|error):", text):
            raise ValueError("Simulation missing exact required success markers or contains an error")
        report["PassedCases"] = observed
        report["TransactionTrace"] = audit_trace(work)
        report["SimulationLogSHA256"] = sha(log)
        report["MeasuredConsecutiveBitPeriodCoreCycles"] = 274
        report["SourceSHA256After"] = {name: sha(ROOT / name) for name in SOURCES}
        if report["SourceSHA256After"] != before:
            raise ValueError("Source changed during simulation")
        verify_minimal_clone()
        report["Passed"] = True
    except Exception as exc:
        report["Error"] = str(exc)
        print(str(exc), file=sys.stderr)
    finally:
        report["EndedUtc"] = datetime.now(timezone.utc).isoformat()
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(str(report_path))
    return 0 if report["Passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
