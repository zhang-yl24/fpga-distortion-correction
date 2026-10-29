"""Bounded digital HDMI observer CDC regression; no PDS or hardware access."""
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
SOURCES = (
    "rtl/experimental/dvp_mode_admission_monitor_cdc.v",
    "rtl/experimental/hdmi1080_input_status_cdc.v",
    "tests/tb_board1080_input_status_cdc.sv",
)
HELPERS = (
    "tools/run_hdmi_input_cdc_sim.py", "tools/simulation_tools.py",
    "tools/run_gamma_pipeline_d5_sim.py", "tools/prepare_gamma_pipeline_d5.py",
)
SMALL_CASES = (
    "atomic_held_snapshot_gray_and_first_new_frame",
    "enable_restart_discards_pending_old_snapshot",
    "stopped_clock_enable_requires_observed_source_disable",
    "common_reset_while_pclk_stopped_has_no_old_epoch",
    "source_fault_code_sticky_and_enable_recovery",
)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(work, maximum_seconds=240):
    work = Path(work).resolve()
    if work.parent != BASE.resolve() or not work.name.startswith("input-cdc-sim-"):
        raise ValueError("fresh input-cdc-sim-* child of build/hdmi-uart-diagnostic required")
    if not 1 <= maximum_seconds <= 240:
        raise ValueError("whole simulation deadline must be 1..240 seconds")
    work.mkdir(exist_ok=False)
    hashes = {name: sha(ROOT / name) for name in (*SOURCES, *HELPERS)}
    report = {
        "Schema": "hdmi-input-cdc-simulation-v1", "Passed": False,
        "StartedUTC": datetime.now(timezone.utc).isoformat(),
        "SourceSHA256": hashes, "CompileSources": list(SOURCES),
        "Commands": [], "Cases": {}, "HardwareAccessed": False, "PDSAccessed": False,
        "HardwareReleaseAllowed": False,
        "Limits": "Actual digital observer RTL with synthetic exact 1080p30 raster and small enable/clock-stop tests. No physical CDC/skew/AC sign-off, real HDMI pixels, DDR or optical acceptance.",
    }
    deadline = time.monotonic() + maximum_seconds
    try:
        bin_dir = resolve_vivado_bin(ROOT.parent)

        def stage(name, args, label):
            row = {"Stage": label, "Argv": [str(bin_dir / name), *args], "ReturnCode": None}
            report["Commands"].append(row)
            tool(bin_dir, name, args, work, deadline, label)
            row["ReturnCode"] = 0

        stage("xvlog.bat", ["--sv", *[str(ROOT / s) for s in SOURCES]], "compile")
        for label, top in (
            ("small", "tb_dvp_mode_admission_monitor_cdc_small"),
            ("native", "tb_board1080_input_status_cdc"),
        ):
            stage("xelab.bat", [top, "-s", "input_cdc_" + label], label + "-elaborate")
            stage("xsim.bat", ["input_cdc_" + label, "-runall", "-log", label + "-simulation.log"], label + "-simulate")
            text = (work / (label + "-simulation.log")).read_text(encoding="utf-8", errors="replace")
            if re.search(r"(?im)^\s*(?:fatal|error):", text):
                raise ValueError(label + " simulation emitted an error")
            if label == "small":
                names = re.findall(r"(?m)^HDMI_INPUT_CDC_CASE ([a-z0-9_]+) PASS\s*$", text)
                if names != list(SMALL_CASES) or len(re.findall(r"(?m)^PASS hdmi_input_cdc small\s*$", text)) != 1:
                    raise ValueError("small CDC regression did not pass all five cases")
                summary = re.findall(r"(?m)^HDMI_INPUT_CDC_SMALL_SUMMARY cases=(\d+) applications=(\d+) source_snapshots=(\d+) gray_checks=(\d+)\s*$", text)
                if len(summary) != 1 or int(summary[0][0]) != 5 or any(int(v) < 8 for v in summary[0][1:3]) or int(summary[0][3]) < 100:
                    raise ValueError("small CDC event coverage is incomplete")
                report["Cases"][label] = {"Names": names, "Counts": list(map(int, summary[0]))}
            else:
                markers = (
                    "PASS input_status: exact2200x1125", "PASS input_status: changed-format",
                    "PASS input_status: common reset", "PASS input_status: stopped PCLK",
                    "INPUT_STATUS_COVERAGE", "PASS board1080 input_status_cdc unit:",
                )
                if any(marker not in text for marker in markers):
                    raise ValueError("native 1080 CDC observer assertions incomplete")
                summary = json.loads((work / "input-status-cdc-unit-summary.json").read_text())
                expected = {"passed": True, "qualification_phases": 2, "polarity_mask": 3,
                            "changed_format": 1, "stopped_pclk": 1, "sticky_checks": 2,
                            "common_reset_checks": 3, "reset_requalified": 1,
                            "DDRIPElaborated": False, "HardwareVerified": False}
                if any(type(summary.get(k)) is not type(v) or summary[k] != v for k, v in expected.items()) or summary.get("complete_rasters", 0) < 6:
                    raise ValueError("native 1080 observer coverage differs")
                report["Cases"][label] = summary
        report["Passed"] = True
    except (Exception, KeyboardInterrupt) as error:
        report["Error"] = f"{type(error).__name__}: {error}"
    finally:
        report["SourceDrift"] = [name for name, digest in hashes.items()
                                 if not (ROOT / name).is_file() or sha(ROOT / name) != digest]
        report["Passed"] = bool(report["Passed"] and not report["SourceDrift"])
        report["EndedUTC"] = datetime.now(timezone.utc).isoformat()
        report["EvidenceSHA256"] = {p.name: sha(p) for p in work.iterdir()
                                    if p.is_file() and p.suffix in (".log", ".json", ".jou")}
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
