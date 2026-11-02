"""Bounded digital-only UART wire simulation; no PDS or hardware access."""
from __future__ import annotations
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import time

import camera720_stats as stats
from run_gamma_pipeline_d5_sim import tool
from simulation_tools import resolve_vivado_bin

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "work/camera720-core-stats"
COMPILE = ("rtl/uart_tx.v", "rtl/experimental/camera720_core_stats_uart.v",
           "tests/tb_camera720_core_stats_uart.sv")
HELPERS = ("tools/run_camera720_stats_sim.py", "tools/camera720_stats.py",
           "tools/run_gamma_pipeline_d5_sim.py", "tools/simulation_tools.py")
REPORT = "camera720-core-stats-simulation.json"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def inspect_wire(work):
    with (work / "scheduled-snapshots.csv").open(encoding="ascii", newline="") as stream:
        golden = list(csv.DictReader(stream))
    reports = {}
    for name, sequences in (("main", [0, 1, 0, 1, 2]),
                            ("slow", [0, 7, 14, 21, 0, 7, 14, 21, 28])):
        wire = bytes(int(line, 16) for line in (work / f"{name}-wire.hex").read_text().splitlines())
        decoder = stats.StreamDecoder()
        records = []
        # Exercise streaming reception of genuine pin-decoded bytes.
        for index in range(0, len(wire), 17):
            records.extend(decoder.feed(wire[index:index + 17]))
        if [r["Sequence"] for r in records] != sequences:
            raise ValueError(f"{name}: unexpected actual packet sequence: {records!r}")
        epoch, previous = 0, None
        for record in records:
            if previous is not None and record["CoreTicks"] < previous["CoreTicks"]:
                epoch += 1
            matches = [row for row in golden if row["stream"] == name
                       and int(row["epoch"]) == epoch and int(row["sequence"]) == record["Sequence"]]
            if len(matches) != 1:
                raise ValueError("independent scheduled snapshot is missing/ambiguous")
            row = matches[0]
            expected = {"CoreTicks": int(row["ticks"]), "SourceAccepted": int(row["accepted"], 16),
                        "Processed": int(row["processed"], 16), "UniquePresented": int(row["presented"], 16),
                        "StatusAvailable": row["status_valid"] == "1", "UnderflowsAvailable": False,
                        "Underflows": None, "BuildID": "123456789abcdef0", "ProfileID": "fedcba9876543210",
                        "Failed": row["failed"] == "1" if row["status_valid"] == "1" else None,
                        "Fault": int(row["fault"], 16) if row["status_valid"] == "1" else None}
            if any(record[key] != value for key, value in expected.items()):
                raise ValueError(f"{name}: torn/incorrect actual UART snapshot: {record!r} vs {expected!r}")
            previous = record
        if decoder.rejected_packets < 1 or epoch != 1:
            raise ValueError("mid-packet reset/resynchronization was not covered")
        intervals = [stats.rate_between(a, b, 100000) for a, b in zip(records, records[1:])]
        if sum(not r["RatesAvailable"] for r in intervals) != 1:
            raise ValueError("exactly one reset boundary must suppress FPS")
        if name == "slow":
            if not any(a["CoreTicks"] < 1 << 32 <= b["CoreTicks"]
                       for a, b in zip(records, records[1:])):
                raise ValueError("64-bit tick low-word wrap was not exercised")
            if any(r["SkippedTelemetrySamples"] != 6 for r in intervals if r["RatesAvailable"]):
                raise ValueError("oversubscribed UART did not report skipped samples")
        reports[name] = {"WireBytes": len(wire), "Records": records, "Intervals": intervals,
                         "RejectedPartialPackets": decoder.rejected_packets,
                         "TrailingPartialBytes": len(decoder.pending)}
    return reports


def run(workdir, maximum_seconds=180):
    work = Path(workdir).resolve()
    if work.parent != BASE.resolve() or work.exists():
        raise ValueError("fresh direct child of work/camera720-core-stats required")
    if not 30 <= maximum_seconds <= 600:
        raise ValueError("digital simulation deadline must be 30..600 seconds")
    before = {name: sha(ROOT / name) for name in (*COMPILE, *HELPERS)}
    work.mkdir(parents=True)
    started = time.monotonic()
    report = {"Schema": "camera720-core-stats-digital-simulation-v1", "Passed": False,
              "StartedUTC": datetime.now(timezone.utc).isoformat(), "MaximumSeconds": maximum_seconds,
              "SourceSHA256": before, "HardwareAccessed": False, "PDSAccessed": False,
              "IntegratedIntoCameraTop": False, "ActualCameraFPSMeasured": False, "Commands": [],
              "Limits": "Real UART RTL with accelerated core frequency/cadence and synthetic counters. "
                        "Oversubscribed instance tick register seeded near 32-bit rollover in testbench. "
                        "No physical pins, hardware clocks, camera pixels, CDC or native timing tested."}
    try:
        bin_dir = resolve_vivado_bin(ROOT.parent)
        for executable, args, stage in (
                ("xvlog.bat", ["--sv", *[str(ROOT / name) for name in COMPILE]], "compile"),
                ("xelab.bat", ["tb_camera720_core_stats_uart", "-s", "camera720_core_stats_tb",
                               "--timescale", "1ns/1ps"], "elaborate"),
                ("xsim.bat", ["camera720_core_stats_tb", "-runall", "-log", "simulation.log"], "simulate")):
            command = {"Stage": stage, "NativeArgv": [str(bin_dir / executable), *args], "ReturnCode": None}
            report["Commands"].append(command)
            tool(bin_dir, executable, args, work, started + maximum_seconds, stage)
            command["ReturnCode"] = 0
        log = (work / "simulation.log").read_text(encoding="utf-8", errors="replace")
        if "CAMERA720_CORE_STATS_UART_PASS" not in log or re.search(r"(?im)^\s*(?:fatal|error):", log):
            raise ValueError("UART wire assertions did not complete")
        summary = json.loads((work / "summary.json").read_text(encoding="utf-8"))
        if summary.get("Passed") is not True or summary.get("Epochs") != 2:
            raise ValueError("UART simulation summary is incomplete")
        report.update(Passed=True, Summary=summary, WireObservations=inspect_wire(work))
    except (Exception, KeyboardInterrupt) as error:
        report["Error"] = str(error)
    finally:
        report["SourceDrift"] = [name for name, digest in before.items() if sha(ROOT / name) != digest]
        report["Passed"] = report["Passed"] and not report["SourceDrift"]
        report["ElapsedSeconds"] = round(time.monotonic() - started, 3)
        report["EvidenceSHA256"] = {p.name: sha(p) for p in work.iterdir()
                                    if p.is_file() and p.suffix in (".log", ".json", ".hex", ".csv")}
        (work / REPORT).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n")
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
