from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import re
import sys
import time

REPO = Path(r"D:\GravityLRT\thu\semester_4.5\FPGAchina\fpga-distortion-correction")
OUT = Path(__file__).resolve().parent
WORK = OUT / "hdmi-first-de-transient-native"
sys.path.insert(0, str(REPO / "distortion/tools"))
from run_gamma_pipeline_d5_sim import tool
from simulation_tools import resolve_vivado_bin

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

sources = [REPO / "distortion/rtl/experimental/hdmi1080_input_status_cdc.v",
           REPO / "distortion/rtl/experimental/dvp_mode_admission_monitor_cdc.v",
           OUT / "tb_hdmi_first_de_transient.sv"]
hashes = {str(path): sha(path) for path in sources}
WORK.mkdir(exist_ok=False)
result = dict(Schema="hdmi-first-de-transient-counterexample-v1", Passed=False,
              StartedUTC=datetime.now(timezone.utc).isoformat(), SourceSHA256=hashes,
              HardwareAccessed=False, PDSAccessed=False, FrozenRTLModified=False,
              Limits="Directed digital counterexample only. One injected first-DE sync sample is hypothetical and does not prove that the physical source produced this transient.")
deadline = time.monotonic() + 300
try:
    bin_dir = resolve_vivado_bin(REPO)
    commands = [("xvlog.bat", ["--sv", *map(str, sources)], "compile"),
                ("xelab.bat", ["tb_hdmi_first_de_transient", "-s", "first_de_transient"], "elaborate"),
                ("xsim.bat", ["first_de_transient", "-runall", "-log", "simulation.log"], "simulate")]
    result["Commands"] = [{"Executable": str(bin_dir / name), "Arguments": args} for name, args, stage in commands]
    for name, args, stage in commands:
        tool(bin_dir, name, args, WORK, deadline, stage)
    text = (WORK / "simulation.log").read_text(encoding="utf-8", errors="replace")
    if "PASS first DE one-sample opposite sync" not in text or re.search(r"(?im)^\s*(?:fatal|error):", text):
        raise ValueError("counterexample did not pass all assertions")
    result["Summary"] = json.loads((WORK / "counterexample-summary.json").read_text())
    result["Samples"] = re.findall(r"(?m)^COUNTEREXAMPLE_SAMPLE .+$", text)
    if len(result["Samples"]) != 2 or not result["Summary"]["passed"]:
        raise ValueError("two continuing-state samples required")
    result["Passed"] = True
except Exception as error:
    result["Error"] = type(error).__name__ + ": " + str(error)
finally:
    result["EndedUTC"] = datetime.now(timezone.utc).isoformat()
    result["SourceDrift"] = [name for name, wanted in hashes.items() if sha(Path(name)) != wanted]
    result["Passed"] = result["Passed"] and not result["SourceDrift"]
    result["EvidenceSHA256"] = {path.name: sha(path) for path in WORK.iterdir() if path.is_file()}
    (WORK / "simulation-result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print(json.dumps(result, indent=2))
raise SystemExit(0 if result["Passed"] else 1)
