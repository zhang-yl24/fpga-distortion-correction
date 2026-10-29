"""Bounded delayed-HDMI startup control simulation; no PDS/hardware access."""
from datetime import datetime, timezone
from pathlib import Path
import argparse
import hashlib
import json
import re
import time

from simulation_tools import resolve_vivado_bin
from run_gamma_pipeline_d5_sim import tool

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "build/hdmi-uart-diagnostic"
SOURCES = ("board/hdmi_uart_delayed_diag.v", "tests/tb_hdmi_diag_startup.sv")
HELPERS = (
    "tools/run_hdmi_diag_startup_sim.py", "tools/simulation_tools.py",
    "tools/run_gamma_pipeline_d5_sim.py", "tools/prepare_gamma_pipeline_d5.py",
)
CASES = (
    "g25_then_exact_settle_before_first_request",
    "uart_and_pattern_continue_during_configuration_hold",
    "failure_does_not_trigger_automatic_retry",
    "manual_reset_after_release_requires_full_delay_again",
    "manual_reset_during_hold_restarts_full_delay",
)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(work, maximum_seconds=240):
    work = Path(work).resolve()
    if work.parent != BASE.resolve() or not work.name.startswith("startup-"):
        raise ValueError("fresh startup-* child of build/hdmi-uart-diagnostic required")
    if not 1 <= maximum_seconds <= 600:
        raise ValueError("whole-run deadline must be 1..600 seconds")
    work.mkdir(exist_ok=False)
    hashes = {name: sha(ROOT / name) for name in (*SOURCES, *HELPERS)}
    report = {
        "Schema": "hdmi-diagnostic-startup-simulation-v1", "Passed": False,
        "StartedUTC": datetime.now(timezone.utc).isoformat(),
        "CompileSources": list(SOURCES), "SourceSHA256": hashes,
        "Commands": [], "HardwareAccessed": False, "PDSAccessed": False,
        "HardwareReleaseAllowed": False,
        "Limits": "Actual delayed top with interface-matched test-only PLL, I2C controller, UART and pattern stubs. Tests new reset ordering only; original cold-power count is forced to its terminal value. No real I2C acknowledgement, UART packet, PLL frequency, HDMI timing or board acceptance.",
    }
    deadline = time.monotonic() + maximum_seconds
    try:
        bin_dir = resolve_vivado_bin(ROOT.parent)
        for name, arguments, stage in (
            ("xvlog.bat", ["--sv", *[str(ROOT / s) for s in SOURCES]], "compile"),
            ("xelab.bat", ["tb_hdmi_diag_startup", "-s", "hdmi_diag_startup_tb"], "elaborate"),
            ("xsim.bat", ["hdmi_diag_startup_tb", "-runall", "-log", "simulation.log"], "simulate"),
        ):
            row = {"Stage": stage, "Argv": [str(bin_dir / name), *arguments], "ReturnCode": None}
            report["Commands"].append(row)
            tool(bin_dir, name, arguments, work, deadline, stage)
            row["ReturnCode"] = 0
        log = (work / "simulation.log").read_text(encoding="utf-8", errors="replace")
        if re.search(r"(?im)^\s*(?:fatal|error):", log):
            raise ValueError("native simulation reported an error")
        case_names = re.findall(r"(?m)^HDMI_STARTUP_CASE ([a-z0-9_]+) PASS\s*$", log)
        if case_names != list(CASES):
            raise ValueError("exact five startup cases did not pass in order")
        if len(re.findall(r"(?m)^PASS hdmi_diag_startup\s*$", log)) != 1:
            raise ValueError("unique final startup PASS marker missing")
        summaries = re.findall(
            r"(?m)^HDMI_STARTUP_SUMMARY cases=(\d+) first_requests=(\d+) settle_cycles=(\d+)\s*$", log
        )
        if summaries != [("5", "3", "12")]:
            raise ValueError("startup coverage summary differs")
        report["Cases"] = case_names
        report["Summary"] = {"Cases": 5, "FirstRequests": 3, "SimulatedSettleCycles": 12}
        report["Passed"] = True
    except (Exception, KeyboardInterrupt) as error:
        report["Error"] = f"{type(error).__name__}: {error}"
    finally:
        report["SourceDrift"] = [
            name for name, digest in hashes.items()
            if not (ROOT / name).is_file() or sha(ROOT / name) != digest
        ]
        report["Passed"] = bool(report["Passed"] and not report["SourceDrift"])
        report["EndedUTC"] = datetime.now(timezone.utc).isoformat()
        report["EvidenceSHA256"] = {
            p.name: sha(p) for p in work.iterdir() if p.is_file() and p.suffix in (".log", ".jou")
        }
        with (work / "simulation-result.json").open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workdir", type=Path, required=True)
    parser.add_argument("--maximum-seconds", type=int, default=240)
    args = parser.parse_args()
    result = run(args.workdir, args.maximum_seconds)
    print(json.dumps({"Passed": result["Passed"], "Error": result.get("Error"), "Work": str(args.workdir)}))
    raise SystemExit(0 if result["Passed"] else 1)
