"""Bounded TEST-ONLY boardtop-control wiring test, not a hardware/IP test.

Only the actual board1080_top control body is compiled with the explicit stub
file. Production System/DDR/PLL/IIC/status module headers are checked for port
compatibility but their bodies are NOT executed. Root runs this after native.
"""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import csv
import hashlib
import json
import re
import time

from run_gamma_pipeline_d5_sim import tool as vivado_tool

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/"build/offline-20261024/board1080-integration-20261027-a"
COMPILE = ("tests/board1080_control_stubs.sv", "board/board1080_top.v", "tests/tb_board1080_control.sv")
EXTRA = ("board/board1080-synthetic.vh", "tools/run_board1080_control_sim.py", "tools/run_gamma_pipeline_d5_sim.py")
TOP = "tb_board1080_control"
MARKER = "PASS board1080 control:"
REPORT = "board1080-control-simulation.json"
EXPECTED_STUBS = {"cfg_pll", "bringup_pll", "ddr3_test", "ms72xx_ctl", "hdmi1080_input_status", "hdmi1080_video_system"}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def bound_headers():
    """Verify the six auto-extracted ANSI declarations; do not generate code."""
    result = {}
    stub = (ROOT/COMPILE[0]).read_text(encoding="utf-8")
    for line in stub.splitlines():
        if not line.startswith("// HEADER_BINDING "):
            continue
        record = json.loads(line[len("// HEADER_BINDING "):])
        module = record["Module"]
        if module in result or module not in EXPECTED_STUBS:
            raise ValueError("unexpected/duplicate test stub header")
        path = (ROOT/record["Path"]).resolve()
        if not path.is_relative_to(ROOT.resolve()):
            raise ValueError("header reference leaves workspace")
        actual = path.read_text(encoding="utf-8")
        match = re.search(r"\bmodule\s+"+re.escape(module)+r"\b", actual)
        if match is None:
            raise ValueError("real referenced module is absent")
        header = actual[match.start():actual.index(");", match.start())+2]
        digest = hashlib.sha256(header.encode()).hexdigest()
        if digest != record["HeaderSHA256"]:
            raise ValueError("actual header changed after opaque stub extraction: "+module)
        result[module] = {"Path": str(path), "HeaderSHA256": digest,
                          "FullReferenceSHA256": sha(path), "ProductionBodyCompiled": False}
    if set(result) != EXPECTED_STUBS:
        raise ValueError("all six exact real module-header bindings are required")
    return result


def run(workdir, maximum_seconds=120):
    if type(maximum_seconds) is not int or not 1 <= maximum_seconds <= 120:
        raise ValueError("total offline control-test budget must be integer 1..120 seconds")
    work = Path(workdir).resolve()
    if not work.is_dir() or work == BASE.resolve() or not work.is_relative_to(BASE.resolve()) or any(work.iterdir()):
        raise ValueError("fresh existing child of approved board1080 scratch required; no mkdir/overwrite")
    headers = bound_headers()
    compiled = {name: sha(ROOT/name) for name in (*COMPILE, *EXTRA)}
    references = {item["Path"]: item["FullReferenceSHA256"] for item in headers.values()}
    report = {"Marker": "FPGA-1031-BOARD1080-CONTROL-ONLY", "Passed": False,
              "StartedUtc": datetime.now(timezone.utc).isoformat(), "MaximumSeconds": maximum_seconds,
              "CompiledSourceSHA256": compiled, "OpaqueModuleHeaderBindings": headers,
              "ReferencedProductionBodiesNotExecutedSHA256": references,
              "ActualBoardTopBodyInCompileList": True, "ActualBoardTopControlBodyExecuted": False,
              "ExplicitTestOnlyStubs": True, "SyntheticInput": True, "DevelopmentOnly": True,
              "TestReferenceClockHz": 27000000, "MaximumReferenceCycles": 7000000,
              "AssumedFlags": ["cfg/video PLL lock", "RX/TX initialization complete", "DDR init/PLL lock",
                               "input-status qualified/failed", "System failed", "System held AW request"],
              "StubClockModel": "All internal PLL/core/video clocks are test-only pass-through27MHz; DDR stub suppresses its core clock while common reset is low. No frequency/CDC/lock behavior is proved.",
              "ActualSystemDatapathVerified": False, "ActualFIFOFunctionVerified": False,
              "PhysicalDDRPLLOrIICVerified": False, "ClockStopRecoveryVerified": False,
              "HardwareAccessed": False, "PDSAccessed": False,
              "GateState": {key: False for key in ("HardwareReleaseAllowed", "NewLensCorrectionVerified", "CalibrationAccepted", "PreBitGateExecutionProven")},
              "StartupMissingQualifiers": ["configuration PLL lock", "video PLL lock", "RX init complete", "TX init complete", "DDR init complete", "DDR PLL lock", "input qualified"],
              "RuntimeFaultCases": {"A1": "input failed", "A2": "input unqualified", "A3": "DDR readiness lost",
                                    "A4": "configuration PLL lock flag lost; its stub clock continues",
                                    "A5": "TX init flag lost while RX/observer remain healthy",
                                    "A6": "System failed flag"},
              "Commands": []}
    deadline = time.monotonic()+maximum_seconds
    try:
        bin_dir = Path("E:/Vivado/Vivado/2017.4/bin")
        for executable, argv, stage in (
                ("xvlog.bat", ["--sv", *[str(ROOT/name) for name in COMPILE]], "compile"),
                ("xelab.bat", [TOP, "-s", "board1080_control"], "elaborate"),
                ("xsim.bat", ["board1080_control", "-runall", "-log", "simulation.log"], "simulate")):
            command = {"Stage": stage, "NativeArgv": [str(bin_dir/executable), *argv], "ReturnCode": None}
            report["Commands"].append(command)
            try:
                vivado_tool(bin_dir, executable, argv, work, deadline, stage)
                command["ReturnCode"] = 0
            except (Exception, KeyboardInterrupt) as error:
                match = re.search(r"failed, exit=(-?\d+)", str(error))
                if match:
                    command["ReturnCode"] = int(match.group(1))
                command["Error"] = str(error)
                raise
        log = (work/"simulation.log").read_text(encoding="utf-8", errors="replace")
        if MARKER not in log or re.search(r"(?im)^\s*(?:fatal|error):", log):
            raise ValueError("control-only completion absent or RTL fatal/error")
        summary = load(work/"summary.json")
        expected = {"passed": True, "test_only_stubs": True, "startup_missing_qualifiers_blocked": 7,
                    "runtime_fault_cases": 6, "first_fault_sticky_cases": 6,
                    "held_stub_aw_routing_cases": 6, "common_reset_cases": 6,
                    "actual_system_datapath_verified": False, "actual_fifo_verified": False,
                    "physical_ddr_or_pll_or_iic_verified": False, "clock_stop_recovery_verified": False}
        if any(type(summary.get(key)) is not type(value) or summary[key] != value for key, value in expected.items()):
            raise ValueError("control coverage/disclaimer contract differs")
        cold = summary.get("cold_power_delay_reference_cycles")
        if type(cold) is not int or not 1000000 <= cold <= 1100000:
            raise ValueError("actual top power-delay coverage is absent")
        with (work/"control-events.csv").open(encoding="utf-8-sig", newline="") as stream:
            rows = list(csv.DictReader(stream))
        runtime = [row for row in rows if row["event"] == "runtime_fault_quarantined"]
        sticky = [row for row in rows if row["event"] == "first_fault_still_sticky"]
        startup = [row for row in rows if row["event"] == "missing_qualifier_blocked"]
        if [int(row["case"]) for row in runtime] != list(range(1, 7)) or [int(row["case"]) for row in sticky] != list(range(1, 7)) or [int(row["case"]) for row in startup] != list(range(7)):
            raise ValueError("all seven startup and six sticky runtime cases must be retained")
        for row in runtime+sticky:
            case = int(row["case"])
            if (int(row["board_fault"], 16) != 0xA0+case or any(row[key] != "1" for key in
                    ("global_reset_n", "pipeline_reset_n", "board_failed", "physical_stub_awvalid", "external_fault")) or
                    row["capture_admit"] != "0" or row["scan_enable"] != "0"):
                raise ValueError("runtime top wiring/first fault/held-AW record differs")
        report.update(Passed=True, ActualBoardTopControlBodyExecuted=True, Summary=summary, ControlEvents=rows,
                      NoSystemResetOnAssumedRuntimeFault=True,
                      StubHeldAWPreservedAtActualBoardWiring=True,
                      PassLines=[line for line in log.splitlines() if line.startswith("PASS")])
    except (Exception, KeyboardInterrupt) as error:
        report["Error"] = type(error).__name__+": "+str(error)
    finally:
        report["CompiledSourceSHA256After"] = {name: sha(ROOT/name) for name in compiled}
        report["ReferencedProductionBodiesNotExecutedSHA256After"] = {name: sha(name) for name in references}
        if report["CompiledSourceSHA256After"] != compiled or report["ReferencedProductionBodiesNotExecutedSHA256After"] != references:
            report.update(Passed=False, SourceDrift=True)
        report["LogSHA256"] = {path.name: sha(path) for path in work.glob("*.log")}
        report["ResultFiles"] = {path.name: sha(path) for name in ("summary.json", "control-events.csv") if (path := work/name).is_file()}
        report["EndedUtc"] = datetime.now(timezone.utc).isoformat()
        report["Limits"] = "Actual board1080_top control wiring only under explicit test-driven opaque flags/held-AW producer. No actual FIFO, System/DDR datapath, IP, pixel geometry, chip register/init/readback, physical clock/CDC/timing/resources or hardware acceptance. RX-loss prioritization is not mislabeled A5; the A5 test uses TX loss. Real-System native8 is a separate source-bound result. No hardware plan or authorization is generated."
        with (work/REPORT).open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(report, stream, ensure_ascii=False, indent=2, allow_nan=False);stream.write("\n")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workdir", type=Path, required=True)
    parser.add_argument("--maximum-seconds", type=int, default=120)
    args = parser.parse_args(argv)
    try:
        record = run(args.workdir, args.maximum_seconds)
    except (ValueError, KeyError, OSError) as error:
        parser.exit(1, str(error)+"\n")
    print(json.dumps({"Report": str(args.workdir.resolve()/REPORT), "Passed": record["Passed"], "Commands": record["Commands"], "Error": record.get("Error")}, indent=2))
    return 0 if record["Passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
