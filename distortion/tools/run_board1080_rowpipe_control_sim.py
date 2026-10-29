"""Execute the actual rowpipe board-top control with explicit test-only stubs.

The independent stub clocks exercise board control crossings, not physical PLL,
DDR, FIFO or pixel processing. Reuse the seven-startup/A1-A6 test bench; bind
its current production module headers and the exact rowpipe top in the report.
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
from simulation_tools import prepare_compile_sources, resolve_vivado_bin, verify_compile_sources


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "build/board1080-rowpipe-control"
COMPILE = ("tests/board1080_cdc_control_stubs.sv", "board/board1080_rowpipe_top.v",
           "tests/tb_board1080_control.sv")
HEADER = "board/board1080-synthetic.vh"
HELPERS = ("tools/run_board1080_rowpipe_control_sim.py", "tools/simulation_tools.py",
           "tools/run_gamma_pipeline_d5_sim.py")
TOP = "tb_board1080_control"
REPORT = "board1080-rowpipe-control-simulation.json"
EXPECTED_STUBS = {"cfg_pll", "bringup_pll", "ddr3_test", "ms72xx_ctl",
                  "hdmi1080_input_status", "hdmi1080_video_system"}
CDC_SYSTEM = "rtl/experimental/hdmi1080_video_system_cdc_reset.v"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def bound_headers(root=ROOT):
    """Bind stub interfaces to current production headers; execute no IP body."""
    root = Path(root).resolve()
    result = {}
    for line in (root / COMPILE[0]).read_text(encoding="utf-8").splitlines():
        if not line.startswith("// HEADER_BINDING "):
            continue
        record = json.loads(line[len("// HEADER_BINDING "):])
        module = record["Module"]
        if module not in EXPECTED_STUBS or module in result:
            raise ValueError("unexpected or duplicate explicit test stub")
        relative = CDC_SYSTEM if module == "hdmi1080_video_system" else record["Path"]
        path = (root / relative).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError("stub header reference missing or outside project")
        actual = path.read_text(encoding="utf-8")
        match = re.search(r"\bmodule\s+" + re.escape(module) + r"\b", actual)
        if match is None:
            raise ValueError("production header module missing: " + module)
        header = actual[match.start():actual.index(");", match.start()) + 2]
        digest = hashlib.sha256(header.encode()).hexdigest()
        if digest != record["HeaderSHA256"]:
            raise ValueError("production interface differs from explicit stub: " + module)
        result[module] = {"Path": str(path), "RelativePath": relative, "HeaderSHA256": digest,
                          "FullReferenceSHA256": sha(path), "ProductionBodyCompiled": False}
    if set(result) != EXPECTED_STUBS:
        raise ValueError("all six explicitly bound stub interfaces required")
    return result


def prepare_sources(root, work):
    """Keep current top bytes; stage its one bound relative include under cwd."""
    root, work = Path(root).resolve(), Path(work).resolve()
    top = (root / COMPILE[1]).read_bytes()
    includes = re.findall(rb'(?m)^\s*`include\s+"([^"\r\n]+)"', top)
    if includes != [HEADER.encode("ascii")]:
        raise ValueError("rowpipe top must use exactly its bound synthetic header")
    compiled, relocated = prepare_compile_sources(root, COMPILE, (HEADER,), work)
    target = work / HEADER
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("xb") as stream:
        stream.write((root / HEADER).read_bytes())
    return compiled, relocated, {"Header": HEADER, "Path": str(target), "SHA256": sha(target)}


def validate_results(work):
    summary = json.loads((work / "summary.json").read_text(encoding="utf-8"))
    expected = {"passed": True, "test_only_stubs": True, "startup_missing_qualifiers_blocked": 7,
                "runtime_fault_cases": 6, "first_fault_sticky_cases": 6,
                "held_stub_aw_routing_cases": 6, "common_reset_cases": 6,
                "actual_system_datapath_verified": False, "actual_fifo_verified": False,
                "physical_ddr_or_pll_or_iic_verified": False, "clock_stop_recovery_verified": False}
    if any(type(summary.get(k)) is not type(v) or summary[k] != v for k, v in expected.items()):
        raise ValueError("control coverage or explicit test-only limits differ")
    cold = summary.get("cold_power_delay_reference_cycles")
    if type(cold) is not int or not 1000000 <= cold <= 1100000:
        raise ValueError("actual top power-delay coverage is absent")
    with (work / "control-events.csv").open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    by_event = {event: [r for r in rows if r["event"] == event] for event in (
        "runtime_fault_quarantined", "first_fault_still_sticky", "missing_qualifier_blocked")}
    for event, required in (("runtime_fault_quarantined", range(1, 7)),
                            ("first_fault_still_sticky", range(1, 7)),
                            ("missing_qualifier_blocked", range(7))):
        if [int(r["case"]) for r in by_event[event]] != list(required):
            raise ValueError("seven startup and six sticky runtime cases required")
    for row in by_event["runtime_fault_quarantined"] + by_event["first_fault_still_sticky"]:
        if (int(row["board_fault"], 16) != 0xA0 + int(row["case"]) or
                any(row[key] != "1" for key in ("global_reset_n", "pipeline_reset_n", "board_failed",
                                                "physical_stub_awvalid", "external_fault")) or
                row["capture_admit"] != "0" or row["scan_enable"] != "0"):
            raise ValueError("actual top quarantine, held AW or common-reset state differs")
    return summary, rows


def run(workdir, maximum_seconds=120):
    if type(maximum_seconds) is not int or not 1 <= maximum_seconds <= 120:
        raise ValueError("control-test budget must be integer 1..120 seconds")
    work = Path(workdir).resolve()
    if work.parent != BASE.resolve() or not work.is_dir() or any(work.iterdir()):
        raise ValueError("fresh existing child of build/board1080-rowpipe-control required")
    headers = bound_headers(ROOT)
    sources = {name: sha(ROOT / name) for name in (*COMPILE, HEADER, *HELPERS)}
    references = {value["Path"]: value["FullReferenceSHA256"] for value in headers.values()}
    bin_dir = resolve_vivado_bin(ROOT.parent)
    report = {"Schema": "board1080-rowpipe-control-simulation-v1", "Passed": False,
              "StartedUTC": datetime.now(timezone.utc).isoformat(), "MaximumSeconds": maximum_seconds,
              "ActualBoardTop": COMPILE[1], "ActualBoardTopSHA256": sources[COMPILE[1]],
              "SourceSHA256": sources, "OpaqueModuleHeaderBindings": headers,
              "ReferencedProductionBodiesNotExecutedSHA256": references,
              "VivadoBin": str(bin_dir), "ExplicitTestOnlyStubs": True,
              "StubClocks": "Independent nominal125MHz core,10MHz configuration,74.25MHz output; no physical PLL or metastability model.",
              "ActualSystemDatapathVerified": False, "ActualFIFOFunctionVerified": False,
              "PhysicalDDRPLLOrIICVerified": False, "ClockStopRecoveryVerified": False,
              "HardwareAccessed": False, "PDSAccessed": False, "HardwareReleaseAllowed": False,
              "Commands": []}
    deadline = time.monotonic() + maximum_seconds
    relocated = staged = None
    try:
        compiled, relocated, staged = prepare_sources(ROOT, work)
        report.update(RelocatedSources=relocated, StagedRelativeHeader=staged)
        for executable, argv, stage in (
                ("xvlog.bat", ["--sv", *[str(path) for path in compiled]], "compile"),
                ("xelab.bat", [TOP, "-s", "board1080_rowpipe_control"], "elaborate"),
                ("xsim.bat", ["board1080_rowpipe_control", "-runall", "-log", "simulation.log"], "simulate")):
            command = {"Stage": stage, "NativeArgv": [str(bin_dir / executable), *argv], "ReturnCode": None}
            report["Commands"].append(command)
            try:
                vivado_tool(bin_dir, executable, argv, work, deadline, stage)
                command["ReturnCode"] = 0
            except (Exception, KeyboardInterrupt) as error:
                match = re.search(r"failed, exit=(-?\d+)", str(error))
                if match:
                    command["ReturnCode"] = int(match[1])
                command["Error"] = str(error)
                raise
        log = (work / "simulation.log").read_text(encoding="utf-8", errors="replace")
        if "PASS board1080 control:" not in log or re.search(r"(?im)^\s*(?:fatal|error):", log):
            raise ValueError("actual board-top control completion absent or RTL fatal/error")
        summary, rows = validate_results(work)
        report.update(Passed=True, ActualBoardTopControlBodyExecuted=True, Summary=summary, ControlEvents=rows,
                      NoSystemResetOnAssumedRuntimeFault=True, StubHeldAWPreservedAtActualBoardWiring=True,
                      PassLines=[line for line in log.splitlines() if line.startswith("PASS")])
    except (Exception, KeyboardInterrupt) as error:
        report["Error"] = type(error).__name__ + ": " + str(error)
    finally:
        after = {name: sha(ROOT / name) for name in sources}
        after_references = {name: sha(name) for name in references}
        report.update(SourceSHA256After=after, ReferencedProductionBodiesNotExecutedSHA256After=after_references)
        if after != sources or after_references != references:
            report.update(Passed=False, SourceDrift=True)
        try:
            if relocated is not None:
                verify_compile_sources(ROOT, COMPILE, (HEADER,), work, relocated)
            if staged is not None and (sha(staged["Path"]) != staged["SHA256"] or
                                       sha(ROOT / HEADER) != staged["SHA256"]):
                raise ValueError("bound relative include changed")
        except (ValueError, OSError) as error:
            report.update(Passed=False, CompiledSourceDrift=True, VerificationError=str(error))
        report["LogSHA256"] = {p.name: sha(p) for p in work.glob("*.log")}
        report["ResultFiles"] = {name: sha(work / name) for name in ("summary.json", "control-events.csv")
                                 if (work / name).is_file()}
        report["EndedUTC"] = datetime.now(timezone.utc).isoformat()
        report["Limits"] = "Actual rowpipe board-top control only with opaque IP/status/System flags and a stub held-AW producer. No actual FIFO, pixel pipeline, DDR/IP/HDMI initialization, physical CDC/timing, metastability, optical or board acceptance."
        with (work / REPORT).open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(report, stream, indent=2, ensure_ascii=False, allow_nan=False)
            stream.write("\n")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workdir", type=Path, required=True)
    parser.add_argument("--maximum-seconds", type=int, default=120)
    args = parser.parse_args(argv)
    try:
        report = run(args.workdir, args.maximum_seconds)
    except (ValueError, KeyError, OSError) as error:
        parser.exit(1, str(error) + "\n")
    print(json.dumps({"Passed": report["Passed"], "Report": str(args.workdir / REPORT),
                      "ActualBoardTop": report["ActualBoardTop"], "Error": report.get("Error")}))
    return 0 if report["Passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
