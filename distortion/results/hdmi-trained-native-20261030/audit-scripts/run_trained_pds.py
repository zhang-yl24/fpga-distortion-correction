"""Run the isolated trained candidate's own build; no bitstream or hardware."""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import subprocess
import sys
import time

ROOT = Path(r"D:\GravityLRT\thu\semester_4.5\FPGAchina\fpga-distortion-correction\distortion")
sys.path.insert(0, str(ROOT / "tools"))
import prepare_hdmi_trained_diagnostic as candidate

WORK = ROOT / "build/hdmi-uart-diagnostic/trained-pds-1030-a"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    WORK.mkdir()
    plan = candidate.prepare(WORK)
    bound = {ROOT / name: wanted for name, wanted in plan["InputSHA256"].items()}
    bound.update({WORK / name: wanted for name, wanted in plan["FrozenInputSHA256"].items()})
    bound.update({WORK / "build.tcl": plan["TclSHA256"], WORK / "hdmi_uart_diag.fdc": plan["FDCSHA256"]})
    before = sha(WORK / "build-plan.json")
    result = dict(Schema="hdmi-trained-pds-execution-v1", Target=candidate.TARGET,
                  StartedUTC=datetime.now(timezone.utc).isoformat(), Command=plan["Command"],
                  Passed=False, HardwareAccessed=False, BitstreamRequested=False,
                  PlanSHA256=before, RunnerSHA256=sha(__file__))
    start = time.monotonic()
    with (WORK / "native-stdout.log").open("xb") as out, (WORK / "native-stderr.log").open("xb") as err:
        process = subprocess.Popen(plan["Command"], cwd=WORK, stdout=out, stderr=err,
                                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        result["OwnedPID"] = process.pid
        try:
            result["ReturnCode"] = process.wait(timeout=600)
        except subprocess.TimeoutExpired:
            process.kill()
            result["ReturnCode"] = process.wait()
            result["Error"] = "owned PDS build exceeded 600 seconds"
    result["ElapsedSeconds"] = round(time.monotonic() - start, 3)
    result["SourceDrift"] = [str(path) for path, wanted in bound.items() if sha(path) != wanted]
    result["PlanUnchanged"] = sha(WORK / "build-plan.json") == before
    result["LogSHA256"] = {name: sha(WORK / name) for name in ("native-stdout.log", "native-stderr.log")}
    result["Passed"] = result["ReturnCode"] == 0 and not result["SourceDrift"] and result["PlanUnchanged"] and "Error" not in result
    result["EndedUTC"] = datetime.now(timezone.utc).isoformat()
    with (WORK / "execution.json").open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2)
    print(json.dumps(result))
    return 0 if result["Passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
