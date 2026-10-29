"""Run real MS7200/MS7210 sequencers with stub or actual wire-level driver.

Default uses a transaction stub; --wire-level uses the real checked driver.
Neither mode accesses PDS/hardware or proves board integration or PHY lock.
"""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import csv
import hashlib
import json
import re
import time

from simulation_tools import resolve_vivado_bin
from run_gamma_pipeline_d5_sim import tool
import board1080_edid as edid

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "build/board1080-checked"
RTL = ("rtl/experimental/ms7200_1080p30_ctl.v",
       "rtl/experimental/ms7210_checked_ctl.v",
       "rtl/experimental/ms72xx_checked_ctl.v",
       "tests/tb_ms72xx_checked_ctl.sv")
SOURCES = RTL + ("platform/video_base/source/hdmi/ms7210_ctl.v",
                 "platform/video_base/source/hdmi/ms7200_ctl.v", "tools/board1080_edid.py",
                 "tools/run_ms72xx_checked_sim.py", "tools/simulation_tools.py",
                 "tools/run_gamma_pipeline_d5_sim.py")
TX_REFERENCE_SHA256 = "c9b101e58f381ddf3c6d663d0003c18065302659424b8345022161413ccf09ae"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def command_rows(path, count):
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    rows = re.findall(r"\d+\s*'d(\d+)\s*:\s*cmd_data\s*=\s*\{16\s*'h([0-9a-fA-F]+),\s*8\s*'h([0-9a-fA-F]+)\}", text)
    indices = [int(i) for i, _, _ in rows]
    if indices != list(range(count)):
        raise ValueError("source command table indices differ")
    return [f"{int(address, 16):04x}{int(data, 16):02x}" for _, address, data in rows]


def audit_tx_copy(reference, checked):
    if sha(reference) != TX_REFERENCE_SHA256:
        raise ValueError("original TX source SHA256 differs")
    original = Path(reference).read_text(encoding="utf-8")
    old = ("                CONECT   ,\n                INIT     ,\n"
           "                SETING   ,\n                STA_RD   : iic_trig <= busy_falling;")
    new = ("                CONECT   : iic_trig <= busy_falling;\n"
           "                // Final INIT write enters WAIT: do not issue a ghost write.\n"
           "                INIT     : iic_trig <= busy_falling && (dri_cnt != 5'd18);\n"
           "                // Final SETING write transfers the bus back to RX.\n"
           "                SETING   : iic_trig <= busy_falling && (dri_cnt != 5'd29);\n"
           "                STA_RD   : iic_trig <= 1'b0;")
    header = ("// Isolated checked-controller development copy; original vendor source unchanged.\n"
              "// Original ms7210_ctl.v SHA256:\n// " + TX_REFERENCE_SHA256 + "\n"
              "// Only module name and transaction-trigger terminal guards differ below.\n"
              "// All 49 command entries and the 0x30D399 wait interval are preserved.\n")
    if original.count(old) != 1 or original.count("module ms7210_ctl(") != 1:
        raise ValueError("TX transformation anchors differ")
    expected = header + original.replace("module ms7210_ctl(", "module ms7210_checked_ctl(").replace(old, new)
    if Path(checked).read_text(encoding="utf-8") != expected:
        raise ValueError("checked TX differs from exact allowed module/trigger transformation")
    if command_rows(reference, 49) != command_rows(checked, 49):
        raise ValueError("checked TX command table changed")
    return {"ReferenceSHA256": TX_REFERENCE_SHA256, "ExactTransformationVerified": True,
            "CommandRowsUnchanged": 49, "OriginalWaitPreserved": True}


def expected_wire_trace():
    rx = [int(row, 16) for row in command_rows(ROOT / RTL[0], 311)]
    tx = [int(row, 16) for row in command_rows(ROOT / RTL[1], 49)]
    # Device, read, address, data, response, NACK. Expectations derive from
    # independently audited reference transformations, not simulation output.
    sequence = [(0x56, 0, 3, 0x5a, 0, 0), (0x56, 1, 3, 0, 0x5a, 0)]
    sequence += [(0x56, 0, row >> 8, row & 255, 0, 0) for row in rx[:300]]
    sequence += [(0x56, 1, 0x209c + i % 4, 0, 2 if i == 6 else 0, 0) for i in range(8)]
    sequence += [(0x56, 0, row >> 8, row & 255, 0, 0) for row in rx[304:311]]
    sequence += [(0xb2, 0, 3, 0x5a, 0, 0), (0xb2, 1, 3, 0, 0x5a, 0)]
    sequence += [(0xb2, 0, row >> 8, row & 255, 0, 0) for row in tx]
    sequence += [(0x56, 1, 0x209c + i, 0, 2 if i == 2 else 0, 0) for i in range(4)]
    if len(sequence) != 372:
        raise ValueError("reference trace length differs")
    counts = (372, 1, 317, 318, 368, 369, 372)
    result = []
    for scenario, count in enumerate(counts):
        for index, entry in enumerate(sequence[:count]):
            values = list(entry)
            if scenario in (1, 2, 3, 4, 5) and index == count - 1:
                values[-1] = 1
            result.append((scenario, index + 1, *values))
    return result


def validate_wire_trace(path):
    with Path(path).open(encoding="ascii", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != ["scenario", "request", "device", "read", "addr", "data", "response", "nack"]:
            raise ValueError("wire transaction schema differs")
        rows = [(int(row["scenario"]), int(row["request"]), int(row["device"], 16),
                 int(row["read"]), int(row["addr"], 16), int(row["data"], 16),
                 int(row["response"], 16), int(row["nack"])) for row in reader]
    if rows != expected_wire_trace():
        raise ValueError("ordered wire trace, exact NACK boundary, or reset epoch differs")
    return {"OrderedTraceVerified": True, "Transactions": len(rows),
            "ScenarioCounts": [372, 1, 317, 318, 368, 369, 372],
            "TraceSHA256": sha(path), "StickyObservationConfigCycles": 40}


def run(workdir, maximum_seconds=180, wire_level=False):
    if type(maximum_seconds) is not int or not 30 <= maximum_seconds <= 240:
        raise ValueError("whole-run budget must be integer30..240 seconds")
    work = Path(workdir).resolve()
    if work.parent != BASE.resolve() or work.exists():
        raise ValueError("fresh child of build/board1080-checked required")
    compiled = RTL if not wire_level else RTL[:3] + (
        "rtl/experimental/iic_dri_checked.v", "tests/tb_ms72xx_checked_e2e.sv")
    sources = tuple(dict.fromkeys(compiled + SOURCES[4:]))
    before = {name: sha(ROOT / name) for name in sources}
    tx_audit = audit_tx_copy(ROOT / SOURCES[4], ROOT / RTL[1])
    rx_audit = edid.audit_controller(ROOT / RTL[0], ROOT / SOURCES[5])
    vectors = {"rx_expected.hex": command_rows(ROOT / RTL[0], 311),
               "tx_expected.hex": command_rows(ROOT / RTL[1], 49)}
    if vectors["tx_expected.hex"] != command_rows(ROOT / SOURCES[4], 49):
        raise ValueError("checked TX changed the original 49 command entries")
    work.mkdir(parents=True)
    for filename, rows in vectors.items():
        with (work / filename).open("x", encoding="ascii", newline="\n") as stream:
            stream.write("\n".join(rows) + "\n")
    vector_hashes = {name: sha(work / name) for name in vectors}
    report = {"Schema": "ms72xx-checked-controller-simulation-v1", "Passed": False,
              "StartedUTC": datetime.now(timezone.utc).isoformat(),
              "SourceSHA256": before, "MaximumSeconds": maximum_seconds, "Commands": [],
              "TXCopyAudit": tx_audit,
              "RXCopyAudit": rx_audit,
              "TransactionDriverStub": not wire_level, "WireLevelI2CExecuted": wire_level,
              "PDSAccessed": False, "HardwareAccessed": False, "BoardTopIntegrated": False}
    started = time.monotonic()
    try:
        bin_dir = resolve_vivado_bin(ROOT.parent)
        top = "tb_ms72xx_checked_e2e" if wire_level else "tb_ms72xx_checked_ctl"
        for name, args, stage in (
                ("xvlog.bat", ["--sv", *[str(ROOT / s) for s in compiled]], "compile"),
                ("xelab.bat", [top, "-s", "ms72xx_checked_tb"], "elaborate"),
                ("xsim.bat", ["ms72xx_checked_tb", "-runall", "-log", "simulation.log"], "simulate")):
            command = {"Stage": stage, "NativeArgv": [str(bin_dir / name), *args], "ReturnCode": None}
            report["Commands"].append(command)
            tool(bin_dir, name, args, work, started + maximum_seconds, stage)
            command["ReturnCode"] = 0
        log = (work / "simulation.log").read_text(encoding="utf-8", errors="replace")
        marker = "MS72XX_CHECKED_E2E_SIM_PASS" if wire_level else "MS72XX_CHECKED_CTL_SIM_PASS"
        if marker not in log or re.search(r"(?im)^\s*(?:fatal|error):", log):
            raise ValueError("wrapper assertions did not complete")
        summary = json.loads((work / "summary.json").read_text(encoding="utf-8"))
        expected = {"Passed": True, "Scenarios": 7, "ActualRXControllerExecuted": True,
                    "ActualTXControllerExecuted": True, "TransactionDriverStub": not wire_level,
                    "WireLevelI2CExecuted": wire_level, "EarlyRXFailure": True,
                    "LastRXSettingFailure": True, "FirstTXFailureAfterRXDone": True,
                    "LastTXWriteFailure": True, "CommonResetRecovery": True,
                    "PostCompletionFailure": True,
                    "FailureSameCycleGating": True, "NoAutoRetry": True, "HardwareAccessed": False}
        if any(type(summary.get(key)) is not type(value) or summary[key] != value
               for key, value in expected.items()):
            raise ValueError("wrapper coverage differs")
        scenario_marker = "MS72XX_E2E_SCENARIO_PASS " if wire_level else "MS72XX_SCENARIO_PASS "
        if [int(value) for value in re.findall(r"(?m)^" + scenario_marker + r"scenario=(\d+)\b", log)] != list(range(7)):
            raise ValueError("missing scenario pass records")
        if wire_level and summary.get("BackgroundRXPollResumed") is not True:
            raise ValueError("background RX polling was not resumed")
        if wire_level:
            report["WireTraceAudit"] = validate_wire_trace(work / "wire-transactions.csv")
        report.update(Passed=True, Summary=summary,
                      PassLines=[line for line in log.splitlines() if "_PASS" in line])
    except (Exception, KeyboardInterrupt) as error:
        report["Error"] = str(error)
    finally:
        report["SourceDrift"] = [name for name, digest in before.items() if sha(ROOT / name) != digest]
        report["VectorDrift"] = [name for name, digest in vector_hashes.items() if sha(work / name) != digest]
        report["Passed"] = report["Passed"] and not report["SourceDrift"] and not report["VectorDrift"]
        report["ElapsedSeconds"] = round(time.monotonic() - started, 3)
        report["EvidenceSHA256"] = {p.name: sha(p) for p in work.iterdir()
                                    if p.is_file() and p.suffix in (".log", ".hex", ".json", ".csv")}
        with (work / "checked-controller-simulation.json").open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(report, stream, indent=2); stream.write("\n")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--maximum-seconds", type=int, default=180)
    parser.add_argument("--wire-level", action="store_true")
    args = parser.parse_args()
    result = run(args.work_dir, args.maximum_seconds, args.wire_level)
    print(json.dumps({"Passed": result["Passed"], "Error": result.get("Error"),
                      "ElapsedSeconds": result["ElapsedSeconds"],
                      "Report": str(args.work_dir / "checked-controller-simulation.json")}))
    return 0 if result["Passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

