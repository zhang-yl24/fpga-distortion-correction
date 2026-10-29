"""Run isolated checked I2C driver against a line-level open-drain slave.

No board, PDS, pin-delay, pull-up, analog timing or MS72xx silicon verification.
Each native run owns a fresh directory below build/iic-checked and a finite
whole-process deadline; failed logs are retained and never promoted as passes.
"""
from datetime import datetime, timezone
from pathlib import Path
import argparse
import csv
import hashlib
import json
import re
import time

from simulation_tools import resolve_vivado_bin
from run_gamma_pipeline_d5_sim import tool as vivado_tool

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "build/iic-checked"
TOP = "tb_iic_dri_checked"
REPORT = "iic-checked-simulation.json"
SOURCES = ("rtl/experimental/iic_dri_checked.v", "tests/tb_iic_dri_checked.sv",
           "tools/run_iic_dri_checked_sim.py", "tools/simulation_tools.py",
           "tools/run_gamma_pipeline_d5_sim.py")
# name,error,completion count,START count,STOP count,read data if checked.
EXPECTED = (
    ("write_success", 0, 1, 1, 1, None),
    ("read_success", 0, 1, 2, 1, 0xA6),
    ("nack_device_write", 1, 0, 1, 1, None),
    ("nack_register_low", 2, 0, 1, 1, None),
    ("nack_register_high", 3, 0, 1, 1, None),
    ("nack_write_data", 4, 0, 1, 1, None),
    ("nack_device_read", 5, 0, 2, 1, None),
    ("missing_slave", 1, 0, 1, 1, None),
    ("sda_stuck_before_start", 15, 0, 0, 0, None),
    ("scl_stuck_before_start", 15, 0, 0, 0, None),
    ("sda_stuck_at_stop", 15, 0, 1, 0, None),
    ("clock_stretch_read", 0, 1, 2, 1, 0x59),
    ("unsupported_byte_length", 14, 0, 0, 0, None),
    ("reset_during_transaction", 0, 0, 1, 0, None),
    ("read_after_reset_recovery", 0, 1, 2, 1, 0x3C),
    ("trigger_while_busy", 0, 1, 1, 1, None),
    ("sda_conflict_during_transmit", 15, 0, 1, 0, None),
)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate_results(work):
    work = Path(work)
    summary = json.loads((work / "summary.json").read_text(encoding="utf-8"))
    expected = {"Passed": True, "Cases": len(EXPECTED), "ClockHz": 10_000_000,
                "ConfiguredMaximumI2CHz": 400_000, "ActualDriverExecuted": True,
                "ParameterRejections": 8, "WideTimingArithmeticChecked": True,
                "OpenDrainSlaveModel": True, "HardwareAccessed": False}
    if any(type(summary.get(k)) is not type(v) or summary[k] != v for k, v in expected.items()):
        raise ValueError("driver coverage or verification scope differs")
    for key, minimum, maximum in (("MinimumSCLLowNs", 1300, 3000),
                                  ("MinimumSCLHighNs", 600, 3000),
                                  ("MeasuredLowPhases", 80, 200),
                                  ("MeasuredHighPhases", 80, 200)):
        if type(summary.get(key)) is not int or not minimum <= summary[key] <= maximum:
            raise ValueError("required bounded physical-line digital timing observation differs")
    with (work / "iic-checked-cases.csv").open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    fields = {"id", "name", "expected_error", "observed_error", "read_data", "byte_over_count",
              "start_count", "stop_count", "elapsed_cycles"}
    if len(rows) != len(EXPECTED) or any(set(row) != fields for row in rows):
        raise ValueError("complete ordered driver case log required")
    for number, (row, case) in enumerate(zip(rows, EXPECTED), 1):
        name, error, over, starts, stops, read_data = case
        if (int(row["id"]), row["name"], int(row["expected_error"]), int(row["observed_error"]),
            int(row["byte_over_count"]), int(row["start_count"]), int(row["stop_count"])) != (
                number, name, error, error, over, starts, stops):
            raise ValueError(f"case {number} completion, fault, or bus event evidence differs")
        if read_data is not None and int(row["read_data"], 16) != read_data:
            raise ValueError("actual wire read data differs")
        if not 1 <= int(row["elapsed_cycles"]) <= 8050:
            raise ValueError("finite transaction completion bound differs")
    return summary, rows


def run(workdir, maximum_seconds=120):
    if type(maximum_seconds) is not int or not 30 <= maximum_seconds <= 180:
        raise ValueError("whole-run budget must be integer30..180 seconds")
    work = Path(workdir).resolve()
    if work.parent != BASE.resolve() or not work.is_dir() or any(work.iterdir()):
        raise ValueError("fresh existing child of build/iic-checked required")
    before = {name: sha(ROOT / name) for name in SOURCES}
    bin_dir = resolve_vivado_bin(ROOT.parent)
    report = {"Schema": "iic-checked-line-simulation-v1", "Passed": False,
              "StartedUTC": datetime.now(timezone.utc).isoformat(), "MaximumSeconds": maximum_seconds,
              "SourceSHA256": before, "Commands": [], "ActualDriverExecuted": False,
              "OpenDrainSlaveModel": True, "HardwareAccessed": False, "PDSAccessed": False,
              "MS72xxSequencersExecuted": False, "HardwareReleaseAllowed": False}
    started = time.monotonic()
    try:
        for executable, arguments, stage in (
                ("xvlog.bat", ["--sv", str(ROOT / SOURCES[0]), str(ROOT / SOURCES[1])], "compile"),
                ("xelab.bat", [TOP, "-s", "iic_checked"], "elaborate"),
                ("xsim.bat", ["iic_checked", "-runall", "-log", "simulation.log"], "simulate")):
            command = {"Stage": stage, "NativeArgv": [str(bin_dir / executable), *arguments], "ReturnCode": None}
            report["Commands"].append(command)
            vivado_tool(bin_dir, executable, arguments, work, started + maximum_seconds, stage)
            command["ReturnCode"] = 0
        log = (work / "simulation.log").read_text(encoding="utf-8", errors="replace")
        if "IIC_DRI_CHECKED_SIM_PASS" not in log or re.search(r"(?im)^\s*(?:fatal|error):", log):
            raise ValueError("driver assertions did not complete successfully")
        summary, rows = validate_results(work)
        report.update(Passed=True, ActualDriverExecuted=True, Summary=summary, CaseCount=len(rows),
                      PassLines=[line for line in log.splitlines() if line.startswith("PASS")])
    except (Exception, KeyboardInterrupt) as error:
        report["Error"] = str(error)
    finally:
        report["InputDrift"] = [name for name, digest in before.items()
                                if not (ROOT / name).is_file() or sha(ROOT / name) != digest]
        report["Passed"] = report["Passed"] and not report["InputDrift"]
        report["EvidenceSHA256"] = {path.name: sha(path) for path in work.iterdir()
                                    if path.is_file() and path.suffix in (".log", ".csv", ".json")}
        report["ElapsedSeconds"] = round(time.monotonic() - started, 3)
        report["EndedUTC"] = datetime.now(timezone.utc).isoformat()
        with (work / REPORT).open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(report, stream, indent=2, ensure_ascii=False); stream.write("\n")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-dir", required=True, type=Path)
    parser.add_argument("--maximum-seconds", type=int, default=120)
    args = parser.parse_args(argv)
    result = run(args.work_dir, args.maximum_seconds)
    print(json.dumps({"Passed": result["Passed"], "Error": result.get("Error"),
                      "Report": str(args.work_dir / REPORT)}))
    return 0 if result["Passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
