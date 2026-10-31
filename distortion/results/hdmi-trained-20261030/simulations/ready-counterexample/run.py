"""Native simulation of one unchanged RX controller; no hardware access."""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import sys
import time

PROJECT = Path(r"D:\GravityLRT\thu\semester_4.5\FPGAchina\fpga-distortion-correction\distortion")
WORK = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT / "tools"))
from simulation_tools import resolve_vivado_bin
from run_gamma_pipeline_d5_sim import tool

sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
source = PROJECT / "rtl/experimental/ms7200_1080p30_ctl.v"
tb = WORK / "tb_ms7200_ready_level.sv"
inputs = {str(path): sha(path) for path in (source, tb, Path(__file__),
    PROJECT / "tools/simulation_tools.py", PROJECT / "tools/run_gamma_pipeline_d5_sim.py")}
result = dict(Schema="ms7200-ready-level-counterexample-v1", Passed=False,
              StartedUTC=datetime.now(timezone.utc).isoformat(), InputSHA256=inputs,
              HardwareAccessed=False, FrozenRTLModified=False, PDSExecuted=False,
              TransactionDriverStub=True, Commands=[])
started = time.monotonic()
try:
    bin_dir = resolve_vivado_bin(PROJECT.parent)
    for name, arguments, stage in (
        ("xvlog.bat", ["--sv", str(source), str(tb)], "compile"),
        ("xelab.bat", ["tb_ms7200_ready_level", "-s", "ms7200_ready_level_tb"], "elaborate"),
        ("xsim.bat", ["ms7200_ready_level_tb", "-runall", "-log", "simulation.log"], "simulate")):
        record = dict(Stage=stage, NativeArgv=[str(bin_dir / name), *arguments], ReturnCode=None)
        result["Commands"].append(record)
        tool(bin_dir, name, arguments, WORK, started + 180, stage)
        record["ReturnCode"] = 0
    text = (WORK / "simulation.log").read_text(encoding="utf-8", errors="replace")
    if "MS7200_READY_LEVEL_COUNTEREXAMPLE_PASS" not in text:
        raise ValueError("native counterexample assertions did not complete")
    result["Summary"] = json.loads((WORK / "summary.json").read_text())
    result["PassLines"] = [line for line in text.splitlines() if line.startswith("MS7200_")]
    result["Passed"] = result["Summary"]["CounterexampleReproduced"] is True
except Exception as error:
    result["Error"] = type(error).__name__ + ": " + str(error)
finally:
    result["InputDrift"] = [path for path, digest in inputs.items() if sha(path) != digest]
    result["Passed"] = result["Passed"] and not result["InputDrift"]
    result["ElapsedSeconds"] = round(time.monotonic() - started, 3)
    result["EvidenceSHA256"] = {path.name: sha(path) for path in WORK.iterdir()
        if path.is_file() and path.name not in ("counterexample-result.json",) and path.suffix in (".log", ".json", ".csv", ".sv", ".py")}
    with (WORK / "counterexample-result.json").open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2);stream.write("\n")
print(json.dumps({key: result.get(key) for key in ("Passed", "Error", "ElapsedSeconds", "PassLines")}))
raise SystemExit(0 if result["Passed"] else 1)
