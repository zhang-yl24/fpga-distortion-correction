"""Run isolated complete-poll MS7200 readiness scenarios, without hardware."""
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
REFERENCE = "rtl/experimental/ms7200_1080p30_ctl.v"
REFERENCE_SHA256 = "e5055d02e8f7af1c4c3efc151f0a71f2ed50216e55c6f95e3ac4c3f74368b21e"
CANDIDATE = "rtl/experimental/ms7200_1080p30_ready_ctl.v"
TB = "tests/tb_ms7200_ready_level.sv"
HEADER = """// Isolated MS7200 ready-level candidate; not selected by accepted builds.
// Original current-source SHA256:
// e5055d02e8f7af1c4c3efc151f0a71f2ed50216e55c6f95e3ac4c3f74368b21e
// The 311-entry register/EDID table and original transfer FSM are preserved.
// Changed: module name and reset-safe complete-poll readiness admission only.
// A register-ready condition is not HDMI PHY lock or video acceptance.
"""


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def command_rows(text):
    rows = re.findall(r"\d+\s*'d(\d+)\s*:\s*cmd_data\s*=\s*\{16\s*'h([0-9a-fA-F]+),\s*8\s*'h([0-9a-fA-F]+)\}", text)
    if [int(index) for index, _, _ in rows] != list(range(311)):
        raise ValueError("all 311 ordered register commands are required")
    return [f"{int(address, 16):04x}{int(data, 16):02x}" for _, address, data in rows]


def audit_candidate():
    original_path, candidate_path = ROOT / REFERENCE, ROOT / CANDIDATE
    if sha(original_path) != REFERENCE_SHA256:
        raise ValueError("frozen original controller changed")
    original = original_path.read_text(encoding="utf-8")
    candidate = candidate_path.read_text(encoding="utf-8")
    if not candidate.startswith(HEADER):
        raise ValueError("candidate provenance header differs")
    old_start = original.index("    reg [31:0]   freq_rec_1d")
    old_end = original.index("    //===========================================================================", old_start)
    new_start = candidate.index("    // Only complete, successful four-byte status polls establish history.")
    new_end = candidate.index("    //===========================================================================", new_start)
    old_without_gate = original[:old_start] + original[old_end:]
    expected = "\n".join(old_without_gate.split("\n")[4:]).replace(
        "module ms7200_ctl(", "module ms7200_1080p30_ready_ctl(", 1)
    actual = candidate[len(HEADER):new_start] + candidate[new_end:]
    if actual != expected:
        raise ValueError("candidate modified logic outside its readiness/history block")
    before, after = command_rows(original), command_rows(candidate)
    if before != after:
        raise ValueError("candidate register command table changed")
    return {"ReferenceSHA256": REFERENCE_SHA256, "CandidateSHA256": sha(candidate_path),
            "OriginalControllerUnchanged": True, "All311RegisterCommandsUnchanged": True,
            "SourceChangesConfinedToModuleNameAndReadyHistoryBlock": True}, before


def run(workdir, maximum_seconds=180):
    if type(maximum_seconds) is not int or not 30 <= maximum_seconds <= 240:
        raise ValueError("whole-run bound must be an integer in 30..240 seconds")
    work = Path(workdir).resolve()
    if work.exists() and (not work.is_dir() or any(work.iterdir())):
        raise ValueError("simulation work directory must be new or empty")
    source_audit, commands = audit_candidate()
    names = (REFERENCE, CANDIDATE, TB, "tools/run_ms7200_ready_level_sim.py",
             "tools/simulation_tools.py", "tools/run_gamma_pipeline_d5_sim.py")
    inputs = {name: sha(ROOT / name) for name in names}
    work.mkdir(parents=True, exist_ok=True)
    (work / "rx_expected.hex").write_text("\n".join(commands) + "\n", encoding="ascii")
    vector_sha = sha(work / "rx_expected.hex")
    result = dict(Schema="ms7200-ready-level-candidate-simulation-v1", Passed=False,
                  StartedUTC=datetime.now(timezone.utc).isoformat(), InputSHA256=inputs,
                  SourceAudit=source_audit, HardwareAccessed=False, PDSExecuted=False,
                  TransactionDriverStub=True, WireLevelI2CExecuted=False, Commands=[],
                  Limits="Isolated receiver register sequencer and transaction response model only; no actual I2C lines, PHY lock, input pixels, physical timing, integrated board build or hardware acceptance.")
    started = time.monotonic()
    try:
        bin_dir = resolve_vivado_bin(ROOT.parent)
        for name, arguments, stage in (
            ("xvlog.bat", ["--sv", str(ROOT / CANDIDATE), str(ROOT / TB)], "compile"),
            ("xelab.bat", ["tb_ms7200_ready_level", "-s", "ms7200_ready_level_tb"], "elaborate"),
            ("xsim.bat", ["ms7200_ready_level_tb", "-runall", "-log", "simulation.log"], "simulate")):
            record = dict(Stage=stage, NativeArgv=[str(bin_dir / name), *arguments], ReturnCode=None)
            result["Commands"].append(record)
            tool(bin_dir, name, arguments, work, started + maximum_seconds, stage)
            record["ReturnCode"] = 0
        text = (work / "simulation.log").read_text(encoding="utf-8", errors="replace")
        scenarios = [int(value) for value in re.findall(r"(?m)^MS7200_READY_CANDIDATE_SCENARIO_PASS scenario=(\d+)\b", text)]
        if scenarios != list(range(7)) or "MS7200_READY_CANDIDATE_SIM_PASS" not in text:
            raise ValueError("native candidate assertions did not all complete")
        if re.search(r"(?im)^\s*(?:fatal|error):", text):
            raise ValueError("native simulator reported an error")
        summary = json.loads((work / "summary.json").read_text(encoding="utf-8"))
        expected = dict(Passed=True, Scenarios=7, ColdAlreadyReadyCompleted=True,
                        SteadyReadyDoesNotReconfigure=True, LaterZeroToTwoRelockCompleted=True,
                        ResetClearsReadyHistory=True, NormalZeroToTwoCompleted=True,
                        ConstantNotReadyBlocked=True, IncompletePollRejected=True,
                        InitialWritesPerEpoch=300, SettingsPerAdmission=7,
                        TransactionDriverStub=True, WireLevelI2CExecuted=False, HardwareAccessed=False)
        if any(type(summary.get(key)) is not type(value) or summary[key] != value for key, value in expected.items()):
            raise ValueError("candidate coverage summary differs")
        result.update(Passed=True, Summary=summary,
                      PassLines=[line for line in text.splitlines() if line.startswith("MS7200_READY_")])
    except Exception as error:
        result["Error"] = type(error).__name__ + ": " + str(error)
    finally:
        result["InputDrift"] = [name for name, digest in inputs.items() if sha(ROOT / name) != digest]
        result["VectorDrift"] = sha(work / "rx_expected.hex") != vector_sha
        result["Passed"] = result["Passed"] and not result["InputDrift"] and not result["VectorDrift"]
        result["ElapsedSeconds"] = round(time.monotonic() - started, 3)
        result["EvidenceSHA256"] = {path.name: sha(path) for path in work.iterdir()
            if path.is_file() and path.suffix in (".log", ".json", ".csv", ".hex")}
        with (work / "simulation-result.json").open("x", encoding="utf-8") as stream:
            json.dump(result, stream, indent=2);stream.write("\n")
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workdir", type=Path, required=True)
    parser.add_argument("--maximum-seconds", type=int, default=180)
    args = parser.parse_args(argv)
    result = run(args.workdir, args.maximum_seconds)
    print(json.dumps({key: result.get(key) for key in ("Passed", "Error", "ElapsedSeconds", "PassLines")}))
    return 0 if result["Passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
