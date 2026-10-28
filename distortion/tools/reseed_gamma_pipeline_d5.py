"""Fixed seed3 complete offline flow after a sealed failed attempt. Plan by default."""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import json
import math
import os
import re
import subprocess
import sys
import build_gamma_pipeline_d5 as core

ROOT, TARGET, APPROVED = core.ROOT, core.TARGET, core.APPROVED
sha, load, write_new, stop_owned = core.sha, core.load, core.write_new, core.stop_owned
SEED = 3


def source_context(previous, profile_binding):
    previous = Path(previous).resolve()
    result_path, plan_path = previous / "gamma-pipeline-build-result.json", previous / "plan.json"
    if (not previous.is_dir() or not previous.is_relative_to(APPROVED.resolve())
            or not result_path.is_file() or not plan_path.is_file()):
        raise ValueError("only a sealed failed attempt is eligible; active/unknown attempts are refused")
    plan, result = load(plan_path), load(result_path)
    before = core.verify_prepared(profile_binding)
    if (plan.get("Target") != TARGET or result.get("Target") != TARGET or result.get("Passed") is not False
            or result.get("CleanupError")
            or type(result.get("TimedOut")) is not bool or not result.get("EndedUtc")
            or (type(result.get("ProcessExitCode")) is not int and not
                (result.get("TimedOut") is True and result.get("ProcessExitCode") is None))
            or not (result.get("Error") or result.get("CleanupError"))
            or (previous / "validated-build.json").exists()
            or Path(result.get("OutputDirectory", "")).resolve() != previous
            or len(before["SourceSHA256"]) != 123
            or any(record.get("SourceSHA256") != before["SourceSHA256"] for record in (plan, result))
            or result.get("SourceSHA256After") != before["SourceSHA256"]
            or plan.get("ProfileBinding") != before.get("ProfileBinding")):
        raise ValueError("sealed failed source123/profile/native completion contract differs")
    simulation = core.validate_simulation(plan["SimulationEvidence"]["Path"], profile_binding)
    if simulation != plan["SimulationEvidence"]:
        raise ValueError("previous attempt does not bind the current completed simulation")
    mapping = previous / "device_map" / f"{TARGET}_map.adf"
    pcf = previous / "device_map" / f"{TARGET}.pcf"
    for path in (mapping, pcf):
        if not path.resolve().is_relative_to(previous) or not path.is_file() or path.stat().st_size == 0:
            raise ValueError("nonempty sealed map and PCF inputs required")
    context = {"PreviousAttempt": str(previous), "PreviousPlan": str(plan_path), "PreviousPlanSHA256": sha(plan_path),
               "PreviousResult": str(result_path), "PreviousResultSHA256": sha(result_path),
               "PreviousPassed": False, "PreviousTimedOut": result["TimedOut"],
               "PreviousProcessExitCode": result.get("ProcessExitCode"), "MapDatabase": str(mapping),
               "PreviousDatabaseSHA256": {str(path): sha(path) for path in (mapping, pcf)},
               "PreviousMapUsedAsInput": False,
               "Seed": SEED, "Scope": "full compile/synthesis/map/placement/route with fixed seed3; previous map and PCF are historical references only"}
    return before, simulation, context


def derive_tcl(work, context):
    text = (ROOT / f"board/build-{TARGET}.tcl").read_text(encoding="utf-8")
    marker = f"compile -force_to_run -top_module {TARGET}\n"
    if text.count(marker) != 1 or text.count(core.prepared.pre_bit_timing_gate()) != 1:
        raise ValueError("fixed main compile boundary or strict pre-bit timing gate differs")
    if "set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG676" not in text.split(marker)[0]:
        raise ValueError("fixed source/constraint/architecture prefix missing")
    if text.count("-gplace_seed 2") != 1 or "-input_db_file" in text or "-input_place_db_file" in text:
        raise ValueError("fixed complete main flow must contain exactly seed2 and no DB reuse")
    # Native PDS ignores the earlier unverified map-only resume invocation.
    # Preserve every main command and the strict pre-bit gate byte-for-byte.
    return text.replace("-gplace_seed 2", "-gplace_seed 3")


def helper_hashes():
    paths = (Path(__file__), Path(core.__file__), Path(core.prepared.__file__), ROOT / "tools/run_gamma_pipeline_d5_sim.py",
             Path(core.gate_log.__file__))
    return {str(path): sha(path) for path in paths}


def check_inputs(context, helpers):
    for name, digest in context["PreviousDatabaseSHA256"].items():
        if sha(Path(name)) != digest:
            raise ValueError("sealed previous DB SHA changed: " + name)
    for name, key in (("PreviousPlan", "PreviousPlanSHA256"), ("PreviousResult", "PreviousResultSHA256")):
        if sha(Path(context[name])) != context[key]:
            raise ValueError("previous failed evidence changed")
    if helper_hashes() != helpers:
        raise ValueError("reseed/build/preparation/simulation helper changed")


def verify_fresh_placement(work):
    text = core.read_text(Path(work) / "place_route/run.log")
    if not all(marker in text for marker in ("Placement started.", "Global placement started.", "Routing started.")):
        raise ValueError("logs do not prove fresh global placement and routing")
    project = core.read_text(Path(work) / (TARGET + ".pds"))
    if re.findall(r"\(_option\s+gplace_seed\s+\(_integer\s+(\d+)\)\)", project) != ["3"]:
        raise ValueError("actual saved project does not confirm fixed placement seed3")
    placed = Path(work) / "place_route" / f"{TARGET}_plc.adf"
    if not placed.is_file() or not placed.stat().st_size:
        raise ValueError("fresh placement DB missing")
    return {"Seed": 3, "PlacementDatabase": str(placed), "PlacementSHA256": sha(placed),
            "PlacementLogSHA256": sha(Path(work) / "place_route/run.log"), "ProjectSHA256": sha(Path(work) / (TARGET + ".pds"))}


def run_reseed(previous, workdir, *, profile_binding, execute=False, timeout_seconds=7200, pds_bin=None):
    if (type(execute) is not bool or type(timeout_seconds) not in (int, float)
            or not math.isfinite(timeout_seconds) or not 60 <= timeout_seconds <= 7200):
        raise ValueError("explicit execute and finite60..7200s offline bound required")
    work = Path(workdir).resolve()
    if (not APPROVED.is_dir() or work == APPROVED.resolve() or not work.is_relative_to(APPROVED.resolve())
            or not work.parent.is_dir() or work.exists()):
        raise ValueError("fresh child of existing approved scratch required; no overwrite")
    before, simulation, context = source_context(previous, profile_binding)
    helpers = helper_hashes()
    config_path = ROOT.parent / "team-config.local.json"
    config = load(config_path) if config_path.is_file() else {}
    pds = Path(pds_bin or os.environ.get("FPGA_PDS_BIN") or config.get("pds_bin") or r"E:\Pango\PDS_2022.2-SP6.4\bin").resolve()
    if execute and not (pds / "pds_shell.exe").is_file():
        raise ValueError("existing PDS pds_shell.exe required")
    script = derive_tcl(work, context)
    work.mkdir(exist_ok=False)
    tcl = work / "reseed.tcl"
    with tcl.open("x", encoding="utf-8") as out:
        out.write(script)
    command = [str(pds / "pds_shell.exe"), "-file", str(tcl), "-work_dir", str(work), "-project_name", TARGET]
    plan = {"Target": TARGET, "ExecuteReseed": execute, "HardwareAccessed": False, "Seed": 3,
            "OutputDirectory": str(work), "TimeoutSeconds": timeout_seconds, "SourceSHA256": before["SourceSHA256"],
            "ProfileBinding": before.get("ProfileBinding"), "SimulationEvidence": simulation,
            "Context": context, "HelperSHA256": helpers, "DerivedTclSHA256": sha(tcl), "Command": command,
            "Limits": "Complete compile/synthesis/map/placement/route flow, changing only seed2 to fixed seed3. Prior DBs are unused historical references; prior failed results are preserved. No hardware/Flash path or new-lens acceptance."}
    write_new(work / "reseed-plan.json", plan)
    if not execute:
        return plan
    result = {"Target": TARGET, "Passed": False, "Seed": 3, "HardwareAccessed": False, "TimedOut": False,
              "ProcessExitCode": None, "OutputDirectory": str(work), "SourceSHA256": before["SourceSHA256"],
              "Context": context, "StartedUtc": datetime.now(timezone.utc).isoformat()}
    child = None
    try:
        check_inputs(context, helpers)
        if core.verify_prepared(profile_binding) != before:
            raise ValueError("source/profile binding changed before reseed")
        flags = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
        with (work / "build-stdout.log").open("xb") as out, (work / "build-stderr.log").open("xb") as err:
            child = subprocess.Popen(command, cwd=work, stdout=out, stderr=err, **flags)
            result["OwnedPID"] = child.pid
            try:
                result["ProcessExitCode"] = child.wait(timeout=timeout_seconds)
            except subprocess.TimeoutExpired:
                result["TimedOut"] = True
                stop_owned(child, work)
                raise ValueError("owned reseed PDS exceeded explicit offline bound")
        if type(result["ProcessExitCode"]) is not int or result["ProcessExitCode"] != 0:
            raise ValueError("reseed native exit nonzero or unavailable")
        check_inputs(context, helpers)
        if sha(tcl) != plan["DerivedTclSHA256"]:
            raise ValueError("derived reseed Tcl changed")
        result["FreshPlacement"] = verify_fresh_placement(work)
        manifest = core.validate_artifacts(work, before, simulation, profile_binding, core.gate_log.RESEEDED_MAIN)
        write_new(work / "validated-build.json", manifest)
        result.update(Passed=True, ValidatedBuild=str(work / "validated-build.json"),
                      ValidatedBuildSHA256=sha(work / "validated-build.json"))
    except (Exception, KeyboardInterrupt) as exc:
        result["Error"] = type(exc).__name__ + ": " + str(exc)
    finally:
        if child is not None and child.poll() is None:
            try:
                stop_owned(child, work)
            except Exception as exc:
                result["CleanupError"] = str(exc)
                result["Passed"] = False
        result["SourceSHA256After"] = {n: sha(ROOT / n) if (ROOT / n).is_file() else None for n in before["SourceSHA256"]}
        result["PreviousDatabaseSHA256After"] = {n: sha(Path(n)) if Path(n).is_file() else None for n in context["PreviousDatabaseSHA256"]}
        if result["SourceSHA256After"] != before["SourceSHA256"] or result["PreviousDatabaseSHA256After"] != context["PreviousDatabaseSHA256"]:
            result.update(Passed=False, PreviousReferenceOrSourceDrift=True)
        result["EndedUtc"] = datetime.now(timezone.utc).isoformat()
        write_new(work / "reseed-result.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--previous", type=Path, required=True)
    parser.add_argument("--workdir", type=Path, required=True)
    parser.add_argument("--profile-binding", type=Path, required=True)
    parser.add_argument("--pds-bin", type=Path)
    parser.add_argument("--timeout-seconds", type=float, default=7200)
    parser.add_argument("--execute-reseed", action="store_true")
    args = parser.parse_args()
    try:
        result = run_reseed(args.previous, args.workdir, profile_binding=args.profile_binding,
                            pds_bin=args.pds_bin, timeout_seconds=args.timeout_seconds, execute=args.execute_reseed)
    except (ValueError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0 if not args.execute_reseed or result["Passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
