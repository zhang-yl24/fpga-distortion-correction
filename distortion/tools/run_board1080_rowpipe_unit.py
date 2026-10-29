"""Independent C row-product candidate; default plan, root alone runs RTL.

No production RTL, constraints, fixtures or hardware plan is changed. The
1920x1080 unit makes sparse cache queries; it is not a complete native frame.
"""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import hashlib
import json
import re
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from run_gamma_pipeline_d5_sim import tool
from simulation_tools import resolve_vivado_bin

TOP = "tb_rowpipe_cache"
MARKER = "PASS ROWPIPE candidate unit:"
COMPILE = (ROOT / "rtl/experimental/ddr_neighbour_cache_scatter4_rowpipe.v", ROOT / "tests/tb_rowpipe_cache.sv")
BASE_SOURCE = ROOT / "rtl/experimental/ddr_compact_neighbour_cache_scatter4.v"
BASE_SHA = "db3c8f924f22d6a67d80d3e7a9e10ec8dba39d6ae30d12637ab5aa06d6005d2b"
REFERENCES = (BASE_SOURCE, ROOT / "tests/tb_scatter4_neighbour_cache.sv",
              ROOT / "tools/run_gamma_pipeline_d5_sim.py", ROOT / "tools/simulation_tools.py")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"),
                      parse_constant=lambda x: (_ for _ in ()).throw(ValueError("nonfinite JSON " + x)))


def run(workdir, maximum_seconds=180, execute=False):
    if type(maximum_seconds) is not int or not 1 <= maximum_seconds <= 180:
        raise ValueError("explicit whole compile/elaborate/simulate bound must be1..180 seconds")
    work = Path(workdir).resolve()
    if work == ROOT / "build" or not work.is_relative_to(ROOT / "build") or not work.is_dir():
        raise ValueError("existing child of distortion/build required; runner never mkdirs")
    proof = load(ROOT / "tests/rowpipe-candidate-source.json")
    if (sha(BASE_SOURCE) != BASE_SHA or proof.get("BaseSHA256") != BASE_SHA or
            proof.get("CandidateSHA256") != sha(COMPILE[0]) or
            proof.get("PublicFIFO2NormalizedBytesEqual") is not True or
            proof.get("SlowStateMachineBytesEqual") is not True):
        raise ValueError("candidate/base binding or invariant proof changed")
    watched = (*COMPILE, Path(__file__).resolve(), ROOT / "tests/rowpipe-candidate-source.json", *REFERENCES)
    before = {str(p): sha(p) for p in watched}
    bin_dir = resolve_vivado_bin(ROOT.parent)
    commands = [
        ("xvlog.bat", ["--sv", *map(str, COMPILE)], "compile"),
        ("xelab.bat", [TOP, "-s", TOP], "elaborate"),
        ("xsim.bat", [TOP, "-runall", "-log", "simulation.log"], "simulate"),
    ]
    report = {
        "Marker": "FPGA-1028-RESUME-PARALLEL-ONE-C-DECODE", "PlanOnly": not execute,
        "Passed": False, "RTLExecuted": False, "FullFrameTested": False,
        "SparseSourceFrameSize": [1920, 1080], "GenericArithmeticWidth": 639,
        "MaximumSeconds": maximum_seconds, "Workdir": str(work),
        "SourceSHA256": before, "HardwareAccessed": False, "PDSAccessed": False,
        "DevelopmentOnly": True, "ProductionSourceModified": False,
        "GateState": {k: False for k in ("HardwareReleaseAllowed", "NewLensCorrectionVerified",
                                         "CalibrationAccepted", "PreBitGateExecutionProven")},
        "Commands": [{"Stage": stage, "NativeArgv": [str(bin_dir / executable), *args], "ReturnCode": None}
                     for executable, args, stage in commands],
        "Limits": "Only actual candidate unit RTL, sparse1920 queries and generic639 arithmetic. No full1920x1080 frame, native8, routed timing, physical RAM/resource, CDC/PHY or camera/calibration/hardware claim.",
    }
    if not execute:
        return report
    if any(work.iterdir()):
        raise ValueError("fresh empty work child required; prior runs are never overwritten")
    report["StartedUtc"] = datetime.now(timezone.utc).isoformat()
    deadline = time.monotonic() + maximum_seconds
    try:
        report["RTLExecuted"] = True
        for index, (executable, argv, stage) in enumerate(commands):
            try:
                tool(bin_dir, executable, argv, work, deadline, stage)
                report["Commands"][index]["ReturnCode"] = 0
            except (Exception, KeyboardInterrupt) as error:
                match = re.search(r"failed, exit=(-?\d+)", str(error))
                if match:
                    report["Commands"][index]["ReturnCode"] = int(match.group(1))
                report["Commands"][index]["Error"] = str(error)
                raise
        log = (work / "simulation.log").read_text(encoding="utf-8", errors="replace")
        required = (MARKER, "PASS ROWPIPE signed64 native1920", "PASS ROWPIPE warmed first-latency4",
                    "PASS ROWPIPE varying warm metadata:", "PASS ROWPIPE varying metadata backpressure:",
                    "PASS ROWPIPE varying metadata hit-miss:",
                    "PASS ROWPIPE generic639", "PASS SCATTER4 FIFO2 full", "PASS SCATTER4 frame_valid at group31",
                    "PASS SCATTER4 reset on last", "PASS SCATTER4 RID/early-RLAST")
        if not all(x in log for x in required) or re.search(r"(?im)^\s*(?:fatal|error):", log):
            raise ValueError("actual RTL markers absent or fatal/error reported")
        main = load(work / "rowpipe-main-summary.json")
        generic = load(work / "rowpipe-generic-summary.json")
        if (main.get("passed") is not True or main.get("sparse_queries_only") is not True or
                main.get("width") != 1920 or main.get("height") != 1080 or
                main.get("first_valid_latency_cycles") != 4 or main.get("stream_outputs") != 64 or
                main.get("stream_span_cycles") != 63 or main.get("fault_cases") != 4):
            raise ValueError("rowpipe actual RTL functional/throughput contract differs")
        for key in ("numeric_checks", "pre_hold", "query_hold", "pre_refill", "query_refill", "pending_pre",
                    "ar_stall", "output_stall", "ram_checks", "reset_last_scatter",
                    "metadata_input_stall", "metadata_output_hold", "metadata_pre_hold", "metadata_query_hold",
                    "metadata_fast_queries", "metadata_slow_queries"):
            if type(main.get(key)) is not int or main[key] <= 0:
                raise ValueError("rowpipe mandatory coverage missing: " + key)
        metadata_expected = {"metadata_inputs": 68, "metadata_warm_outputs": 32,
                             "metadata_warm_span_cycles": 31, "metadata_stalled_outputs": 24,
                             "metadata_all_field_changes": 55, "metadata_mixed_outputs": 12}
        if any(type(main.get(key)) is not int or main[key] != value for key, value in metadata_expected.items()):
            raise ValueError("varying-query metadata coverage differs")
        if (type(main.get("metadata_hit_miss_switches")) is not int or main["metadata_hit_miss_switches"] < 2
                or main["metadata_fast_queries"] + main["metadata_slow_queries"] != 12):
            raise ValueError("varying-query hit/miss transitions were not covered")
        if main["numeric_checks"] < 64 or generic != {"passed": True, "width": 639, "signed64_arithmetic_cases": 6}:
            raise ValueError("independent signed64 numerical coverage differs")
        report.update(Passed=True, MainSummary=main, GenericSummary=generic,
                      PassLines=[x for x in log.splitlines() if x.startswith("PASS ")])
    except (Exception, KeyboardInterrupt) as error:
        report["Error"] = type(error).__name__ + ": " + str(error)
    finally:
        report["SourceSHA256After"] = {str(p): sha(p) for p in watched}
        if report["SourceSHA256After"] != before:
            report.update(Passed=False, SourceDrift=True)
        report["LogSHA256"] = {p.name: sha(p) for p in work.glob("*.log")}
        report["OutputSHA256"] = {p.name: sha(p) for p in work.glob("rowpipe-*-summary.json")}
        report["EndedUtc"] = datetime.now(timezone.utc).isoformat()
        with (work / "rowpipe-unit-result.json").open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(report, stream, indent=2, allow_nan=False); stream.write("\n")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workdir", type=Path, required=True)
    parser.add_argument("--maximum-seconds", type=int, default=180)
    parser.add_argument("--execute", action="store_true", help="Root only after serial RTL token; default is plan")
    args = parser.parse_args(argv)
    report = run(args.workdir, args.maximum_seconds, args.execute)
    print(json.dumps(report, indent=2))
    return 0 if report["PlanOnly"] or report["Passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
