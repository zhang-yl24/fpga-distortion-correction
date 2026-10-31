"""Source-bound upright init SCCB simulation; no hardware or PDS access."""
from __future__ import annotations
import argparse
import csv
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
BASE = ROOT / "work/camera-vga-upright"
TEMP_BASE = Path(tempfile.gettempdir()) / "codex-camera-vga-upright"
TABLE = "board/ov5640_cadence_trial_commands.vh"
TABLE_SHA = "53428872aa14e6120eed93d876c889ef5155b3c196c014db77c4578b2bd50674"
COMPILE = ("rtl/reg16_i2c.v", "rtl/experimental/ov5640_cadence_upright_init.v",
           "tests/tb_ov5640_cadence_upright.sv")
SOURCES = (*COMPILE, TABLE, "rtl/experimental/ov5640_cadence_trial_init.v",
           "tools/run_ov5640_cadence_upright_sim.py", "tools/simulation_tools.py",
           "tools/run_gamma_pipeline_d5_sim.py")
CHECKABLE = {0x3103, 0x3108, 0x3034, 0x3035, 0x3036, 0x3037, 0x3017, 0x3018,
             0x300e, 0x3808, 0x3809, 0x380a, 0x380b, 0x4300, 0x501f, 0x4740}
VERIFY = [(0x3808, 2), (0x3809, 0x80), (0x380a, 1), (0x380b, 0xe0),
          (0x4300, 0x6f), (0x501f, 1), (0x4740, 0x23), (0x3820, 0), (0x3821, 6)]
REPORT = "upright-simulation.json"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def base_commands():
    if sha(ROOT / TABLE) != TABLE_SHA:
        raise ValueError("Frozen cadence table changed")
    pairs = re.findall(r"9'd(\d+):\s*camera_command=32'h([0-9a-fA-F]{8});",
                       (ROOT / TABLE).read_text(encoding="utf-8-sig"))
    if [int(i) for i, _ in pairs] != list(range(264)):
        raise ValueError("Expected exact contiguous 264 commands")
    words = [int(word, 16) for _, word in pairs]
    if [(i, w) for i, w in enumerate(words) if w >> 16 in (0x3820, 0x3821)] != [
            (40, 0x38200600), (41, 0x38210000)]:
        raise ValueError("Orientation source identity differs")
    return words


def expected_case(words, unit, case):
    """Independent sequence; includes every expected read and injection."""
    if unit not in (0, 1) or case not in (range(8) if unit == 0 else range(3)):
        raise ValueError("Unknown case")
    sequence = []
    add = lambda kind, a, v, ack=1, phase=0, index=-1: sequence.append(
        (kind, a, v, ack, phase, index))
    add("R", 0x300a, 0x56)
    add("R", 0x300b, 0x42 if case == 7 else 0x40)
    if case == 7:
        return sequence
    limit = {1: 41, 2: 42, 3: 263, 6: 42}.get(case, 264)
    for index, word in enumerate(words[:limit]):
        if index == 263:
            for address, value in VERIFY:
                add("R", address, value, phase=2)
        address, value = word >> 16, (word >> 8) & 255
        value = {0x3820: 0, 0x3821: 6}.get(address, value)
        if unit == 1:
            value = {0x3017: 0x12, 0x3018: 0x34}.get(address, value)
        ack = int(not (unit == 1 and case == 0 and index == 41))
        add("W", address, value, ack=ack, index=index)
        if not ack or (unit == 0 and address in CHECKABLE) or address in (0x3820, 0x3821):
            corrupt = (case == 1 and index == 40) or (case == 2 and index == 41)
            add("R", address, value ^ int(corrupt), int(not (case == 6 and index == 41)), 1)
    if case == 3:
        for i, (address, value) in enumerate(VERIFY[:8]):
            add("R", address, value ^ int(i == 7), phase=2)
    elif case in (0, 4, 5):
        for i, (address, value) in enumerate(VERIFY[:8] if case == 4 else VERIFY):
            add("R", address, value ^ int((case == 4 and i == 7) or (case == 5 and i == 8)), phase=3)
        if case in (4, 5):
            for i, (address, value) in enumerate(VERIFY):
                add("R", address, value ^ int(case == 5 and i == 8), phase=4)
    return sequence


def load_trace(path):
    result = {}
    with Path(path).open(newline="", encoding="utf-8-sig") as stream:
        for row in csv.DictReader(stream):
            item = (row["kind"], int(row["address"], 16), int(row["value"], 16),
                    int(row["ack"]), int(row["phase"]), int(row["index"]))
            result.setdefault(int(row["case"]), []).append((item, int(row["start"]), int(row["stop"])))
    return result


def validate_trace(rows, expected):
    if [r[0] for r in rows] != expected:
        raise ValueError("Wire transaction sequence/data differs from independent oracle")
    previous = -1
    for item, start, stop in rows:
        if not previous < start < stop:
            raise ValueError("Invalid line transaction chronology")
        previous = stop
    return len(rows)


def audit_results(work, words):
    cases = []
    for unit in (0, 1):
        traces = load_trace(work / f"trace-{unit}.csv")
        with (work / f"cases-{unit}.csv").open(newline="", encoding="utf-8-sig") as stream:
            summaries = list(csv.DictReader(stream))
        expected_ids = list(range(8 if unit == 0 else 3))
        if list(traces) != expected_ids or [int(r["case"]) for r in summaries] != expected_ids:
            raise ValueError("Missing/duplicate/reordered scenario coverage")
        for summary in summaries:
            case = int(summary["case"])
            sequence = expected_case(words, unit, case)
            count = validate_trace(traces[case], sequence)
            success = case in (0, 4)
            error = {1: 0x70, 2: 0x70, 3: 0x51, 5: 0x50, 6: 0x61, 7: 0x20}.get(case, 0)
            written = {1: 40, 2: 41, 3: 263, 6: 41, 7: 0}.get(case, 264)
            writes = sum(item[0] == "W" for item in sequence)
            retries = int(case in (4, 5))
            expected = {"unit": unit, "case": case, "ready": int(success), "failed": int(not success),
                        "written": written, "writes": writes, "transactions": count,
                        "delay_entries": written + retries, "retry_delays": retries,
                        "noacks": int(unit == 1 and case == 0),
                        "starts": sum(1 if item[0] == "W" or not item[3] else 2 for item in sequence),
                        "read3820": sum(item[0] == "R" and item[1] == 0x3820 for item in sequence),
                        "read3821": sum(item[0] == "R" and item[1] == 0x3821 for item in sequence)}
            if any(int(summary[k]) != value for k, value in expected.items()) or int(summary["error"], 16) != error:
                raise ValueError(f"Scenario status/count disagreement: unit={unit} case={case}: {summary}")
            if int(summary["periods"]) < 40:
                raise ValueError("Insufficient physical-line TX period observations")
            cases.append({**expected, "Error": f"{error:02x}", "CheckedTXPeriods": int(summary["periods"])})
    # Full all-ACK, default-pad successful wire writes differ at exactly two rows.
    baseline = load_trace(work / "trace-0.csv")[0]
    writes = [item for item, _, _ in baseline if item[0] == "W"]
    changes = [i for i, (item, word) in enumerate(zip(writes, words))
               if (item[1], item[2]) != (word >> 16, (word >> 8) & 255)]
    if len(writes) != 264 or changes != [40, 41]:
        raise ValueError("Unexpected non-orientation frozen-table write delta")
    return {"Cases": cases, "CaseCount": len(cases), "WriteDeltaIndices": changes,
            "TotalWireTransactions": sum(c["transactions"] for c in cases),
            "CheckedTXPeriods": sum(c["CheckedTXPeriods"] for c in cases),
            "NonOrientationWritesMatchFrozenTable": True, "QuarterCycles": 68,
            "ObservedTransmitBitPeriodCoreCycles": 274, "CheckWritesDisabledMandatoryReadsVerified": True,
            "ImmediateMismatchRejectedBothAddressesBothModes": True,
            "PreFinalStartMismatchRejected": True, "PostStartRetryThenSuccess": True,
            "PersistentPostStartMismatchRejected": True, "ReadbackAddressNackRejected": True,
            "TableDelayValuesChecked": True, "DynamicPadOverrideChecked": True,
            "AllCasesTerminalStable2000Cycles": True}


def run(workdir, maximum_seconds=600):
    work = Path(workdir).resolve()
    if work.parent not in (BASE.resolve(), TEMP_BASE.resolve()) or work.exists():
        raise ValueError("Fresh direct child of work/camera-vga-upright or canonical temp base required")
    if not 60 <= maximum_seconds <= 1200:
        raise ValueError("MaximumSeconds must be 60..1200")
    words = base_commands()
    before = {name: sha(ROOT / name) for name in SOURCES}
    work.mkdir(parents=True)
    (work / "board").mkdir()
    (work / TABLE).write_bytes((ROOT / TABLE).read_bytes())
    (work / "base-commands.mem").write_text("".join(f"{word:08x}\n" for word in words), encoding="ascii")
    started = time.monotonic()
    report = {"Schema": "ov5640-cadence-upright-line-simulation-v1", "Passed": False,
              "StartedUTC": datetime.now(timezone.utc).isoformat(), "SourceSHA256": before,
              "Commands": [], "HardwareAccessed": False, "PDSAccessed": False,
              "ActualReg16I2CExecuted": True, "ControllerForced": False,
              "FrozenOldInitExecuted": False, "IndependentFrozenTableOracle": True,
              "ResetWaitMillisecondsAccelerated": True, "PhysicalCameraOrientationProven": False,
              "Limits": "Digital SCCB line model only. Reset=8, wait=12, ms=2 core cycles; controller quarter=68 unchanged. "
                        "Preflight is only before final command263; earlier command245 3008=02 is preserved. "
                        "No claim sensor never wakes early, analogue timing, physical orientation or full-system video."}
    try:
        bin_dir = resolve_vivado_bin(ROOT.parent)
        for executable, arguments, stage in (
            ("xvlog.bat", ["--sv", *[str(ROOT / name) for name in COMPILE]], "compile"),
            ("xelab.bat", ["tb_ov5640_cadence_upright", "-s", "upright_tb", "--timescale", "1ps/1ps"], "elaborate"),
            ("xsim.bat", ["upright_tb", "-runall", "-log", "simulation.log"], "simulate")):
            command = {"Stage": stage, "NativeArgv": [str(bin_dir / executable), *arguments], "ReturnCode": None}
            report["Commands"].append(command)
            tool(bin_dir, executable, arguments, work, started + maximum_seconds, stage)
            command["ReturnCode"] = 0
        log = (work / "simulation.log").read_text(encoding="utf-8", errors="replace")
        if "OV5640_CADENCE_UPRIGHT_PASS cases=11 quarter=68 digital_only=1" not in log or re.search(r"(?im)^\s*(fatal|error):", log):
            raise ValueError("Line assertions incomplete; inspect simulation.log")
        report.update(Passed=True, Summary=audit_results(work, words))
    except (Exception, KeyboardInterrupt) as error:
        report["Error"] = str(error)
    finally:
        report["SourceDrift"] = [name for name, digest in before.items() if sha(ROOT / name) != digest]
        report["FixtureDrift"] = sha(work / TABLE) != TABLE_SHA or (work / "base-commands.mem").read_text().split() != [f"{word:08x}" for word in words]
        report["Passed"] = report["Passed"] and not report["SourceDrift"] and not report["FixtureDrift"]
        report["ElapsedSeconds"] = round(time.monotonic() - started, 3)
        report["EvidenceSHA256"] = {p.name: sha(p) for p in work.iterdir() if p.is_file() and p.suffix in (".log", ".csv", ".mem")}
        (work / REPORT).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--maximum-seconds", type=int, default=600)
    args = parser.parse_args()
    report = run(args.work_dir, args.maximum_seconds)
    print(json.dumps({"Passed": report["Passed"], "Error": report.get("Error"),
                      "ElapsedSeconds": report["ElapsedSeconds"], "Report": str(args.work_dir / REPORT)}))
    return 0 if report["Passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
