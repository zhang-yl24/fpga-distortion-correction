"""Run existing HDMI TX-only initialization and real resolved-wire I2C offline.

Production RTL and all 27 MHz delay/driver constants remain unchanged. Only a
bound legacy include pathname is relocated into the fresh simulation directory.
No physical board, PDS, RX controller, camera, DDR, or PHY lock is exercised.
"""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import time

from run_gamma_pipeline_d5_sim import tool
from simulation_tools import (prepare_compile_sources, resolve_vivado_bin,
                              verify_compile_sources)

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "build/hdmi-tx-only"
COMPILE = ("board/hdmi_tx_init.v", "rtl/reg16_i2c.v", "tests/tb_hdmi_tx_init.sv")
HEADERS = ("board/ms7210_commands.vh",)
VENDOR = "platform/video_base/source/hdmi/ms7210_ctl.v"
CHECKED = "rtl/experimental/ms7210_checked_ctl.v"
SOURCES = COMPILE + HEADERS + (VENDOR, CHECKED, "tools/run_hdmi_tx_only_sim.py",
           "tools/simulation_tools.py", "tools/run_gamma_pipeline_d5_sim.py")
VENDOR_SHA256 = "c9b101e58f381ddf3c6d663d0003c18065302659424b8345022161413ccf09ae"
REPORT = "hdmi-tx-only-simulation.json"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def vendor_rows(path):
    rows = re.findall(r"\d+\s*'d(\d+)\s*:\s*cmd_data\s*=\s*\{16\s*'h([0-9a-fA-F]+),\s*8\s*'h([0-9a-fA-F]+)\}",
                      Path(path).read_text(encoding="utf-8"))
    if [int(i) for i, _, _ in rows] != list(range(49)):
        raise ValueError("independent vendor table must contain ordered indices 0..48")
    return [(int(addr, 16), int(data, 16)) for _, addr, data in rows]


def audit_vectors():
    if sha(ROOT / VENDOR) != VENDOR_SHA256:
        raise ValueError("original vendor MS7210 source SHA256 differs")
    rows = vendor_rows(ROOT / VENDOR)
    if vendor_rows(ROOT / CHECKED) != rows:
        raise ValueError("checked MS7210 table differs from original vendor")
    rom = re.findall(r"6'd(\d+):\s*hdmi_command=24'h([0-9a-fA-F]+)",
                     (ROOT / HEADERS[0]).read_text(encoding="utf-8"))
    if [int(i) for i, _ in rom] != list(range(49)) or [int(v, 16) for _, v in rom] != [a << 8 | d for a, d in rows]:
        raise ValueError("TX-only ROM differs from independent vendor expectations")
    return rows


def validate_trace(work, vectors):
    with (work / "wire-transactions.csv").open(encoding="ascii", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != ["scenario", "request", "device", "read", "addr", "data", "response", "nack", "gap_cycles"]:
            raise ValueError("TX wire trace schema differs")
        rows = list(reader)
    observed = [(int(r["scenario"]), int(r["request"]), int(r["device"], 16),
                 int(r["read"]), int(r["addr"], 16), int(r["data"], 16),
                 int(r["response"], 16), int(r["nack"])) for r in rows]
    expected = [(0, 1, 0xb2, 0, 3, 0x5a, 0, 0), (0, 2, 0xb2, 1, 3, 0, 0x5a, 0)]
    expected += [(0, i+3, 0xb2, 0, addr, data, 0, 0) for i, (addr, data) in enumerate(vectors)]
    expected += [(1, 1, 0xb2, 0, 0, 0, 0, 1), (2, 1, 0xb2, 0, 3, 0x5a, 0, 0),
                 (2, 2, 0xb2, 1, 3, 0, 0xa5, 0)]
    if observed != expected:
        raise ValueError("actual ordered TX wire transactions/fault boundaries differ")
    for i in range(1, 49):
        if int(rows[i+2]["gap_cycles"]) < (8100000 if i == 19 else 27000):
            raise ValueError("real controller inter-command delay shortened")
    return {"Transactions": len(rows), "ScenarioCounts": [51, 1, 2],
            "Exact49VendorWrites": True, "OnlyDeviceWriteByteB2": True,
            "InterCommandDelaysVerified": True, "TraceSHA256": sha(work / "wire-transactions.csv")}


def run(workdir, maximum_seconds=180):
    if type(maximum_seconds) is not int or not 60 <= maximum_seconds <= 300:
        raise ValueError("whole-run deadline must be integer 60..300 seconds")
    work = Path(workdir).resolve()
    if work.parent != BASE.resolve() or work.exists():
        raise ValueError("fresh child of build/hdmi-tx-only required")
    before = {name: sha(ROOT / name) for name in SOURCES}
    vectors = audit_vectors()
    work.mkdir(parents=True)
    (work / "tx_expected.hex").write_text("".join(f"{a:04x}{d:02x}\n" for a, d in vectors), encoding="ascii")
    vector_sha = sha(work / "tx_expected.hex")
    compiled, bindings = prepare_compile_sources(ROOT, COMPILE, HEADERS, work)
    report = {"Schema": "hdmi-tx-only-real-i2c-simulation-v1", "Passed": False,
              "StartedUTC": datetime.now(timezone.utc).isoformat(), "SourceSHA256": before,
              "MaximumSeconds": maximum_seconds, "CompileBindings": bindings, "Commands": [],
              "IndependentVectorSource": VENDOR, "VendorSourceSHA256": VENDOR_SHA256,
              "VectorSHA256": vector_sha, "VendorAndCheckedAndROM49RowsMatch": True,
              "ClockHz": 27000000, "DelayConstantsModified": False,
              "TransactionStub": False, "RXControllerExecuted": False,
              "HardwareAccessed": False, "PDSAccessed": False,
              "Limits": "Digital wire simulation only; does not prove MS7210 silicon/PHY lock or visible HDMI output. Retry START delay is covered; retry completion is not."}
    started = time.monotonic()
    try:
        bin_dir = resolve_vivado_bin(ROOT.parent)
        for executable, args, stage in (
            ("xvlog.bat", ["--sv", *[str(p) for p in compiled]], "compile"),
            ("xelab.bat", ["tb_hdmi_tx_init", "-s", "hdmi_tx_only_tb", "--timescale", "1ns/1ps"], "elaborate"),
            ("xsim.bat", ["hdmi_tx_only_tb", "-runall", "-log", "simulation.log"], "simulate")):
            command = {"Stage": stage, "NativeArgv": [str(bin_dir / executable), *args], "ReturnCode": None}
            report["Commands"].append(command)
            tool(bin_dir, executable, args, work, started+maximum_seconds, stage)
            command["ReturnCode"] = 0
        log = (work / "simulation.log").read_text(encoding="utf-8", errors="replace")
        if "HDMI_TX_ONLY_SIM_PASS" not in log or re.search(r"(?im)^\s*(?:fatal|error):", log):
            raise ValueError("TX-only wire assertions did not complete")
        if re.findall(r"HDMI_TX_ONLY_SCENARIO_PASS scenario=(\d+)", log) != ["0", "1", "2"]:
            raise ValueError("three ordered scenario passes required")
        summary = json.loads((work / "summary.json").read_text(encoding="utf-8"))
        expected = {"Passed": True, "Scenarios": 3, "VendorTableWrites": 49,
                    "ActualControllerExecuted": True, "ActualDriverExecuted": True,
                    "WireLevelI2CExecuted": True, "ClockHz": 27000000,
                    "InternalCountersModified": False, "RXControllerExecuted": False,
                    "NACKWithoutReady": True, "SignatureMismatchWithoutReady": True,
                    "FullRetryMinimumDelayVerified": True, "RetryCompletionCovered": False,
                    "HardwareAccessed": False}
        if summary != expected:
            raise ValueError("TX-only scenario coverage differs")
        report.update(Passed=True, Summary=summary, WireTraceAudit=validate_trace(work, vectors),
                      PassLines=[line for line in log.splitlines() if "_PASS" in line])
    except (Exception, KeyboardInterrupt) as error:
        report["Error"] = str(error)
    finally:
        report["SourceDrift"] = [name for name, digest in before.items() if sha(ROOT / name) != digest]
        report["VectorDrift"] = sha(work / "tx_expected.hex") != vector_sha
        try:
            verify_compile_sources(ROOT, COMPILE, HEADERS, work, bindings)
            report["ExactIncludeOnlyRelocationVerified"] = True
        except Exception as error:
            report["CompileBindingError"] = str(error)
        report["Passed"] = report["Passed"] and not report["SourceDrift"] and not report["VectorDrift"] and report.get("ExactIncludeOnlyRelocationVerified", False)
        report["EvidenceSHA256"] = {p.name: sha(p) for p in work.iterdir() if p.is_file() and p.suffix in (".log", ".json", ".csv", ".hex")}
        report["ElapsedSeconds"] = round(time.monotonic()-started, 3)
        with (work / REPORT).open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(report, stream, indent=2); stream.write("\n")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--maximum-seconds", type=int, default=180)
    args = parser.parse_args()
    result = run(args.work_dir, args.maximum_seconds)
    print(json.dumps({"Passed": result["Passed"], "Error": result.get("Error"),
                      "ElapsedSeconds": result["ElapsedSeconds"], "Report": str(args.work_dir / REPORT)}))
    return 0 if result["Passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
