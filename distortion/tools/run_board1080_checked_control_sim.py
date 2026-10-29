"""Execute actual checked board top with opaque IP/status/system stubs.

This verifies A7 startup and runtime control, not the I2C implementation,
datapath, DDR, physical CDC timing, or hardware acceptance.
"""
from datetime import datetime, timezone
from pathlib import Path
import argparse
import csv
import json
import re
import time

import prepare_board1080_checked_top as candidate
import run_board1080_rowpipe_control_sim as baseline
from run_gamma_pipeline_d5_sim import tool
from simulation_tools import resolve_vivado_bin

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "build/board1080-checked-control"
COMPILE = ("tests/board1080_cdc_control_stubs.sv", candidate.CANDIDATE,
           "tests/tb_board1080_checked_control.sv")
REFERENCES = (candidate.BASELINE, "rtl/experimental/ms72xx_checked_ctl.v")
HELPERS = ("tools/prepare_board1080_checked_top.py", "tools/run_board1080_checked_control_sim.py",
           "tools/run_board1080_rowpipe_control_sim.py", "tools/simulation_tools.py",
           "tools/run_gamma_pipeline_d5_sim.py")
REPORT = "checked-board-control-simulation.json"
EXPECTED_EVENTS = (
    ("initial_failure_blocked", 1), ("initial_failure_sticky", 1), ("common_reset_clears", 1),
    ("simultaneous_ready_failure", 2), ("common_reset_clears", 2), ("healthy_admitted", 3),
    ("late_failure_held_aw", 3), ("late_failure_sticky", 3), ("first_failure_preserved", 3),
    ("common_reset_clears", 3), ("common_reset_recovery", 4),
)
sha = candidate.sha


def validate_results(work):
    work = Path(work)
    summary = json.loads((work / "summary.json").read_text())
    required = {"Passed": True, "StartupFailureCases": 2, "LateFailureHeldAWCases": 1,
                "CommonResets": 3, "ActualCheckedTopExecuted": True, "TestOnlyIPStubs": True,
                "PipelineResetMonotonic": True, "DDRResetPreserved": True,
                "PhysicalI2CVerified": False, "ActualSystemDatapathVerified": False,
                "HardwareAccessed": False}
    if any(type(summary.get(k)) is not type(v) or summary[k] != v for k, v in required.items()):
        raise ValueError("checked board coverage or scope differs")
    cold = summary.get("ColdPowerReferenceCycles")
    if type(cold) is not int or not 1_000_000 <= cold <= 1_100_000:
        raise ValueError("bound baseline power delay not exercised")
    with (work / "checked-control-events.csv").open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    if [(row["event"], int(row["case"])) for row in rows] != list(EXPECTED_EVENTS):
        raise ValueError("complete ordered board failure events required")
    for row in rows:
        event = row["event"]
        if event == "common_reset_clears":
            zero = ("global_reset_n", "pipeline_reset_n", "board_failed", "led7", "physical_stub_awvalid", "ddr_reset_n")
            if any(row[k] != "0" for k in zero) or row["board_fault"] != "00":
                raise ValueError("common reset did not clear held state")
        elif event in ("healthy_admitted", "common_reset_recovery"):
            if any(row[k] != "1" for k in ("global_reset_n", "pipeline_reset_n", "ddr_reset_n", "capture_admit", "scan_enable")) or \
                    any(row[k] != "0" for k in ("board_failed", "led7", "external_fault")):
                raise ValueError("healthy epoch admission differs")
        else:
            runtime = event.startswith("late_") or event == "first_failure_preserved"
            if row["board_fault"] != "a7" or any(row[k] != "1" for k in ("global_reset_n", "ddr_reset_n", "board_failed", "led7")) or \
                    any(row[k] != "0" for k in ("capture_admit", "scan_enable")):
                raise ValueError("A7 visible quarantine differs")
            for key in ("pipeline_reset_n", "physical_stub_awvalid", "external_fault"):
                if row[key] != ("1" if runtime else "0"):
                    raise ValueError("startup blocked or runtime reset/AW preserved state differs")
    return summary, rows


def run(workdir, maximum_seconds=120):
    if type(maximum_seconds) is not int or not 30 <= maximum_seconds <= 180:
        raise ValueError("whole-run budget must be integer30..180 seconds")
    work = Path(workdir).resolve()
    if work.parent != BASE.resolve() or not work.is_dir() or any(work.iterdir()):
        raise ValueError("fresh existing child of build/board1080-checked-control required")
    audit = candidate.audit(ROOT)
    headers = baseline.bound_headers(ROOT)
    names = (*COMPILE, *REFERENCES, *HELPERS, baseline.HEADER)
    before = {name: sha(ROOT / name) for name in names}
    header_refs = {item["Path"]: item["FullReferenceSHA256"] for item in headers.values()}
    report = {"Schema": "checked-board-control-v1", "Passed": False,
              "StartedUTC": datetime.now(timezone.utc).isoformat(), "SourceSHA256": before,
              "TopTransformation": audit, "OpaqueStubHeaderBindings": headers,
              "ActualCheckedTopExecuted": False, "TestOnlyIPStubs": True,
              "PhysicalI2CVerified": False, "ActualSystemDatapathVerified": False,
              "PDSAccessed": False, "HardwareAccessed": False, "HardwareReleaseAllowed": False,
              "Commands": []}
    started = time.monotonic()
    try:
        staged = work / baseline.HEADER
        staged.parent.mkdir()
        with staged.open("xb") as stream:
            stream.write((ROOT / baseline.HEADER).read_bytes())
        bin_dir = resolve_vivado_bin(ROOT.parent)
        for name, args, stage in (
            ("xvlog.bat", ["--sv", *[str(ROOT / name) for name in COMPILE]], "compile"),
            ("xelab.bat", ["tb_board1080_checked_control", "-s", "checked_control"], "elaborate"),
            ("xsim.bat", ["checked_control", "-runall", "-log", "simulation.log"], "simulate")):
            record = {"Stage": stage, "NativeArgv": [str(bin_dir / name), *args], "ReturnCode": None}
            report["Commands"].append(record)
            tool(bin_dir, name, args, work, started + maximum_seconds, stage)
            record["ReturnCode"] = 0
        log = (work / "simulation.log").read_text(errors="replace")
        if "BOARD1080_CHECKED_CONTROL_SIM_PASS" not in log or re.search(r"(?im)^\s*(?:fatal|error):", log):
            raise ValueError("checked board assertions did not complete")
        summary, rows = validate_results(work)
        report.update(Passed=True, ActualCheckedTopExecuted=True, Summary=summary, Events=rows)
    except (Exception, KeyboardInterrupt) as error:
        report["Error"] = str(error)
    finally:
        report["SourceDrift"] = [name for name, digest in before.items() if sha(ROOT / name) != digest]
        report["ReferencedHeaderDrift"] = [name for name, digest in header_refs.items() if sha(name) != digest]
        report["StagedHeaderDrift"] = not (work / baseline.HEADER).is_file() or sha(work / baseline.HEADER) != before[baseline.HEADER]
        report["Passed"] = report["Passed"] and not report["SourceDrift"] and not report["ReferencedHeaderDrift"] and not report["StagedHeaderDrift"]
        report["EvidenceSHA256"] = {p.name: sha(p) for p in work.iterdir() if p.is_file() and p.suffix in (".csv", ".json", ".log")}
        report["ElapsedSeconds"] = round(time.monotonic() - started, 3)
        with (work / REPORT).open("x") as stream:
            json.dump(report, stream, indent=2);stream.write("\n")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-dir", required=True, type=Path)
    parser.add_argument("--maximum-seconds", type=int, default=120)
    args = parser.parse_args(argv)
    result = run(args.work_dir, args.maximum_seconds)
    print(json.dumps({"Passed": result["Passed"], "Error": result.get("Error"), "Report": str(args.work_dir / REPORT)}))
    return 0 if result["Passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
