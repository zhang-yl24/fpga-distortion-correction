"""Plan/default or bounded DIGITAL input-status unit; no board/DDR/PDS/devices."""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import hashlib
import json
import os
import re
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "build/offline-20261024/board1080-integration-20261027-a"
SOURCES = ("rtl/experimental/dvp_mode_admission_monitor.v", "rtl/experimental/hdmi1080_input_status.v",
           "tests/tb_board1080_input_status.sv", "tools/run_board1080_input_status_sim.py")
BIN = Path(r"E:/Vivado/Vivado/2017.4/bin")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--workdir", type=Path, required=True)
    p.add_argument("--execute-sim", action="store_true")
    p.add_argument("--timeout-seconds", type=int, default=120)
    a = p.parse_args()
    work = a.workdir.resolve()
    if work.parent != BASE.resolve() or not work.name.startswith("b-board-status-"):
        p.error("fresh b-board-status-* child of the approved board1080 base required")
    if not 30 <= a.timeout_seconds <= 120:
        p.error("one bounded30..120s offline unit budget required")
    before = {n: sha(ROOT / n) for n in SOURCES}
    r = {"Schema": "board1080-input-status-unit-v1", "Passed": False, "Executed": False,
         "SourceSHA256": before, "Workdir": str(work), "MaximumSeconds": a.timeout_seconds,
         "ReferenceClockHz": 27000000, "PixelClockHz": 74250000,
         "Raster": [2200, 1125, 1920, 1080], "MaximumReferenceCycles": 9000000,
         "PhysicalTimingReady": False, "DDRIPElaborated": False, "BoardTopElaborated": False,
         "SynthesisExecuted": False, "PDSAccessed": False, "HardwareAccessed": False,
         "Limits": "Digital observer only. No MS7200 lock/format/readback/AC, board pin/PLL/DDRIP verification or routed STA. Input FDC75.1MHz envelope covers digital75MHz admission window; missing I/O AC remains blocked."}
    if not a.execute_sim:
        print(json.dumps(r, indent=2))
        return 0
    if not BASE.is_dir() or work.exists():
        p.error("approved base must exist and run directory must be fresh; no overwrite")
    work.mkdir()
    r.update(Executed=True, StartedUtc=datetime.now(timezone.utc).isoformat(), Commands=[])
    deadline = time.monotonic() + a.timeout_seconds
    child = None
    try:
        stages = (("xvlog.bat", ["--sv", *[str(ROOT / n) for n in SOURCES if n.endswith((".v", ".sv"))]], "compile"),
                  ("xelab.bat", ["tb_board1080_input_status", "-s", "board1080_input_status_tb"], "elaborate"),
                  ("xsim.bat", ["board1080_input_status_tb", "-runall", "-log", "simulation.log"], "simulate"))
        for name, args, stage in stages:
            if not (BIN / name).is_file():
                raise ValueError("configured existing Vivado runtime missing")
            with (work / (stage + "-stdout.log")).open("wb") as output:
                child = subprocess.Popen([os.environ.get("COMSPEC", "cmd.exe"), "/d", "/c", str(BIN / name), *args],
                                         cwd=work, stdout=output, stderr=subprocess.STDOUT,
                                         creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                item = {"Stage": stage, "PID": child.pid, "ReturnCode": None}
                r["Commands"].append(item)
                item["ReturnCode"] = child.wait(timeout=max(0.01, deadline - time.monotonic()))
                child = None
                if item["ReturnCode"]:
                    raise ValueError(stage + " nonzero native exit")
        text = (work / "simulation.log").read_text(errors="replace")
        markers = ("PASS input_status: exact2200x1125", "PASS input_status: changed-format", "PASS input_status: common reset",
                   "PASS input_status: stopped PCLK", "INPUT_STATUS_COVERAGE", "PASS board1080 input_status unit:")
        if any(s not in text for s in markers) or re.search(r"(?im)^\s*(?:fatal|error):", text):
            raise ValueError("unit assertions/coverage incomplete")
        summary = json.loads((work / "input-status-unit-summary.json").read_text())
        expected = {"passed": True, "qualification_phases": 2, "polarity_mask": 3, "changed_format": 1,
                    "stopped_pclk": 1, "sticky_checks": 2, "common_reset_checks": 3, "reset_requalified": 1,
                    "DDRIPElaborated": False, "HardwareVerified": False}
        if any(type(summary.get(k)) is not type(v) or summary[k] != v for k, v in expected.items()) or summary.get("complete_rasters", 0) < 6:
            raise ValueError("unit summary coverage differs")
        r.update(Passed=True, Summary=summary, PassLines=[s for s in text.splitlines() if s.startswith(("PASS", "INPUT_STATUS_COVERAGE"))])
    except (Exception, KeyboardInterrupt) as exc:
        r["Error"] = type(exc).__name__ + ": " + str(exc)
        if isinstance(exc, subprocess.TimeoutExpired):
            r["TimedOut"] = True
    finally:
        if child is not None and child.poll() is None:
            try:
                stopped = subprocess.run(["taskkill", "/PID", str(child.pid), "/T", "/F"], capture_output=True, timeout=8)
                r["OwnedCleanup"] = {"PID": child.pid, "ReturnCode": stopped.returncode}
                child.wait(timeout=8)
            except Exception as exc:
                r.update(Passed=False, CleanupError=type(exc).__name__ + ": " + str(exc))
        r["SourceSHA256After"] = {n: sha(ROOT / n) for n in SOURCES}
        if r["SourceSHA256After"] != before:
            r.update(Passed=False, SourceDrift=True)
        r["EndedUtc"] = datetime.now(timezone.utc).isoformat()
        r["LogSHA256"] = {q.name: sha(q) for q in work.glob("*.log")}
        (work / "input-status-unit-simulation.json").write_text(json.dumps(r, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(r, indent=2))
    return 0 if r["Passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
