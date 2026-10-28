"""Bounded OFFLINE small-input simulation; default plan, no PDS/hardware."""
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
APPROVED = ROOT / "build/offline-20261024/parallel-1031-20261027-a/b-input"
NAMES = ("rtl/video_async_fifo.v", "rtl/experimental/hdmi1080_capture_cdc.v", "rtl/experimental/hdmi1080_input_dma.v",
         "tests/tb_hdmi1080_input_dma.sv", "tools/run_hdmi1080_input_dma_sim.py")
BIN = Path(r"E:/Vivado/Vivado/2017.4/bin")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workdir", type=Path, required=True)
    parser.add_argument("--execute-sim", action="store_true")
    parser.add_argument("--timeout-seconds", type=int, default=120)
    args = parser.parse_args()
    work = args.workdir.resolve()
    approved = APPROVED.resolve()
    if not 30 <= args.timeout_seconds <= 120:
        parser.error("only30..120s total offline budget")
    if work == approved or approved not in work.parents:
        parser.error("fresh workdir must be below the approved b-input directory")
    before = {n: sha(ROOT / n) for n in NAMES}
    record = {"Schema": "hdmi1080-input-small-simulation-v1", "Passed": False,
              "Executed": False, "HardwareAccessed": False, "PDSAccessed": False,
              "Dimensions": [32, 16], "AsyncClockPeriodsNs": [14, 8], "MaxSystemCycles": 2000000,
              "SourceSHA256": before, "Workdir": str(work),
              "Limits": "Development small chain only; not1080 throughput/30fps/MS7200 lock/polarity/pin adapter/CDC constraints/STA. Coordinated global reset only; no clock-stop watchdog; no AXI B response."}
    if not args.execute_sim:
        print(json.dumps(record, indent=2))
        return 0
    if not approved.is_dir():
        parser.error("root must create the already-approved b-input base")
    if work.exists():
        parser.error("fresh absent child workdir required; old failed evidence is preserved")
    work.mkdir()
    deadline = time.monotonic() + args.timeout_seconds
    record["Executed"] = True
    record["StartedUtc"] = datetime.now(timezone.utc).isoformat()
    stages = (("xvlog.bat", ["--sv", *[str(ROOT / n) for n in NAMES if n.endswith((".v", ".sv"))]], "compile"),
              ("xelab.bat", ["tb_hdmi1080_input_dma", "-s", "hdmi1080_input_dma_tb"], "elaborate"),
              ("xsim.bat", ["hdmi1080_input_dma_tb", "-runall", "-log", "simulation.log"], "simulate"))
    record["Stages"] = []
    child = None
    try:
        for name, argv, stage in stages:
            if not (BIN / name).is_file():
                raise ValueError("configured existing Vivado executable missing")
            log = work / (stage + "-stdout.log")
            with log.open("wb") as output:
                child = subprocess.Popen([os.environ.get("COMSPEC", "cmd.exe"), "/d", "/c", str(BIN / name), *argv],
                                         cwd=work, stdout=output, stderr=subprocess.STDOUT,
                                         creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                entry = {"Stage": stage, "PID": child.pid}
                record["Stages"].append(entry)
                code = child.wait(timeout=max(0.01, deadline - time.monotonic()))
                entry.update(ExitCode=code, LogSHA256=sha(log))
                child = None
                if code:
                    raise ValueError(stage + " native nonzero exit")
        text = (work / "simulation.log").read_text(errors="replace")
        required = ("PASS HDMI input normal", "PASS HDMI input short/long", "PASS HDMI input FIFO overflow",
                    "PASS HDMI input coordinated", "HDMI_INPUT_COVERAGE", "HDMI_INPUT_AW_W_COVERAGE",
                    "PASS hdmi1080_input_dma directed")
        if any(line not in text for line in required) or re.search(r"(?im)^\s*(fatal|error):", text):
            raise ValueError("directed coverage/PASS incomplete")
        record.update(Passed=True, PassLines=[s for s in text.splitlines() if s.startswith(("PASS", "HDMI_INPUT_COVERAGE"))])
    except (Exception, KeyboardInterrupt) as exc:
        record["Error"] = type(exc).__name__ + ": " + str(exc)
        if isinstance(exc, subprocess.TimeoutExpired):
            record["TimedOut"] = True
    finally:
        if child is not None and child.poll() is None:
            # Only the PID subtree launched above, never taskkill by image name.
            try:
                stop = subprocess.run(["taskkill", "/PID", str(child.pid), "/T", "/F"], capture_output=True, timeout=8)
                record["OwnedCleanup"] = {"PID": child.pid, "ExitCode": stop.returncode}
                child.wait(timeout=8)
            except Exception as exc:
                record.update(Passed=False, CleanupError=type(exc).__name__ + ": " + str(exc))
        record["SourceSHA256After"] = {n: sha(ROOT / n) for n in NAMES}
        if record["SourceSHA256After"] != before:
            record.update(Passed=False, SourceDrift=True)
        record["EndedUtc"] = datetime.now(timezone.utc).isoformat()
        record["LogSHA256"] = {p.name: sha(p) for p in work.glob("*.log")}
        (work / "hdmi1080-input-dma-simulation.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(record, indent=2))
    return 0 if record["Passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
