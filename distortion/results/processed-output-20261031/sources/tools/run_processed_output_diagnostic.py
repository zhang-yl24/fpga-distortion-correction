"""Execute one frozen independent output diagnostic, never release hardware.

The executor validates source, compiled copies, alias, Tcl and PDS bindings.
Native exit zero is only an execution result, not timing acceptance. No
bitstream, download, physical input operation or environment override is added.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

import prepare_board1080_timing as paths
import prepare_processed_output as preparation


PROJECT = Path(__file__).resolve().parents[1]
TARGET = "processed_output_top"
SCHEMA = "independent-processed-output-diagnostic-preparation-v1"
MAXIMUM_SECONDS = 1800
START_NAME = "execution-start.json"
RESULT_NAME = "execution-result.json"


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(path):
    return paths.sha(Path(path))


def utc():
    return datetime.now(timezone.utc).isoformat()


def owned_path(value, parent, *, file_required=True):
    """Reject missing, escaped, linked, or ambiguous task paths."""
    raw = Path(value).absolute()
    resolved = raw.resolve()
    require(raw == resolved and resolved.is_relative_to(parent),
            "task path escaped its canonical workspace tree: " + str(value))
    if file_required:
        require(resolved.is_file(), "required task file is missing: " + str(value))
    return resolved


def alias_file(value, expected, project, alias):
    canonical = owned_path(expected, project)
    require(value == paths.alias_path(project, alias, canonical), "aliased file path differs")
    require(Path(value).is_file() and Path(value).samefile(canonical),
            "aliased file does not identify the bound workspace file")
    return canonical


def validate_plan(plan_path, maximum_seconds=None):
    """Read-only fail-closed preflight; does not write files or start EDA."""
    project = PROJECT.resolve()
    plan_file = owned_path(plan_path, project)
    work = plan_file.parent
    base = project / "build/processed-output"
    require(base.absolute() == base.resolve() and work.parent == base,
            "plan must be in a canonical direct child of build/processed-output")
    require(plan_file.name == "plan.json", "exact plan.json entry required")
    paths.relative_name(work.name)
    require(set(item.name for item in work.iterdir()) == {"plan.json", "timing.tcl", "compiled"},
            "prepared work directory is reused or contains unexpected artifacts")
    plan_bytes = plan_file.read_bytes()
    plan = json.loads(plan_bytes.decode("utf-8"))
    require(isinstance(plan, dict) and plan.get("Schema") == SCHEMA and plan.get("Target") == TARGET,
            "unsupported diagnostic plan identity")
    require(plan.get("Scope") == "PrepareOnlyNoEDA" and plan.get("EDAExecuted") is False,
            "plan must be the unused preparation-only recipe")
    for flag in (*preparation.FALSE_FLAGS, "HardwareAccessed", "BitstreamRequested"):
        require(plan.get(flag) is False, "diagnostic plan cannot claim or request acceptance: " + flag)
    require(plan.get("ProjectRoot") == str(project) and plan.get("WorkDirectory") == str(work),
            "project or work directory binding differs")
    alias = paths.validate_repo_alias(project, plan.get("RepoAlias"))
    work_alias = paths.alias_path(project, alias, work)
    require(plan.get("AliasWorkDirectory") == work_alias
            and plan.get("WorkingDirectoryForCommand") == work_alias,
            "command working directory alias differs")
    require(Path(work_alias).is_dir() and Path(work_alias).samefile(work),
            "command working directory alias is not this work directory")
    budget = plan.get("MaximumSecondsForExternalExecutor")
    require(type(budget) is int and 60 <= budget <= MAXIMUM_SECONDS
            and plan.get("ExternalDeadlineRequired") is True, "invalid prepared execution deadline")
    maximum = budget if maximum_seconds is None else maximum_seconds
    require(type(maximum) is int and 30 <= maximum <= budget,
            "executor deadline must not exceed the prepared deadline")

    roles = preparation.validate(project)
    expected_input_names = set(roles["SourceSHA256"]) | set(roles["ConstraintSHA256"]) | {
        preparation.MANIFEST, preparation.BASE, "tools/prepare_processed_output.py",
        "tools/prepare_board1080_timing.py"}
    inputs = plan.get("InputSHA256")
    require(isinstance(inputs, dict) and set(inputs) == expected_input_names,
            "plan source closure differs from the validated independent candidate")
    input_files = {}
    for name, digest in inputs.items():
        paths._bound_hash(digest, name)
        source = paths.inside(project, name)
        require(source.absolute() == source.resolve(), "linked source path is unsupported")
        require(sha(source) == digest, "prepared input hash drift: " + name)
        input_files[name] = source
    require(plan.get("Manifest") == preparation.MANIFEST, "manifest binding differs")
    names = list(roles["Sources"]) + [roles["RouteConstraint"]]
    compiled = plan.get("CompiledInputs")
    require(isinstance(compiled, list) and [entry.get("Source") for entry in compiled] == names,
            "compiled closure order or membership differs")
    compiled_files = {}
    for entry in compiled:
        name = entry["Source"]
        require(entry.get("OriginalSHA256") == inputs[name], "compiled original binding differs: " + name)
        destination = alias_file(entry.get("CompiledPath"), work / "compiled" / name, project, alias)
        expected = input_files[name].read_bytes()
        if name in preparation.INCLUDES:
            old, header = preparation.INCLUDES[name]
            matches = list(paths.INCLUDE.finditer(expected))
            require(len(matches) == 1 and matches[0][1] == old.encode("ascii"),
                    "bound include transform differs: " + name)
            replacement = paths.alias_path(project, alias, work / "compiled" / header)
            match = matches[0]
            expected = expected[:match.start(1)] + replacement.encode("ascii") + expected[match.end(1):]
        expected_hash = hashlib.sha256(expected).hexdigest()
        require(entry.get("CompiledSHA256") == expected_hash and destination.read_bytes() == expected,
                "compiled bytes differ outside the exact include transformation: " + name)
        compiled_files[name] = destination
    require(set(p.resolve() for p in (work / "compiled").rglob("*") if p.is_file())
            == set(compiled_files.values()), "unexpected file in frozen compiled tree")
    designs = [paths.alias_path(project, alias, work / "compiled" / name) for name in names
               if name in roles["ExplicitDesigns"]]
    require(plan.get("ExplicitDesigns") == designs, "explicit design roles differ")
    require(plan.get("Constraints") == {"FDC": preparation.FDC, "RCF": roles["RouteConstraint"],
                                       "CopiedIntoFrozenCompiledTree": True}, "constraint binding differs")
    expected_tcl = preparation.make_tcl(
        designs, paths.alias_path(project, alias, work / "compiled" / preparation.FDC),
        paths.alias_path(project, alias, work / "compiled" / roles["RouteConstraint"]), work_alias).encode("ascii")
    tcl = plan.get("Tcl")
    require(isinstance(tcl, dict), "Tcl binding missing")
    tcl_file = alias_file(tcl.get("Path"), work / "timing.tcl", project, alias)
    require(tcl_file.read_bytes() == expected_tcl and tcl.get("SHA256") == sha(tcl_file),
            "Tcl differs from exact diagnostic flow or prepared hash")
    require(plan.get("PreSTAFinalDatabase") == work_alias + "/pre-sta-final.adf",
            "pre-STA snapshot binding differs")
    pds = plan.get("PDS")
    require(isinstance(pds, dict), "PDS executable binding missing")
    tool = Path(pds.get("Executable", "")).absolute()
    require(tool == tool.resolve() and tool.is_file() and tool.name.casefold() == "pds_shell.exe",
            "canonical PDS shell executable required")
    paths._bound_hash(pds.get("ExecutableSHA256"), "PDS executable")
    require(sha(tool) == pds["ExecutableSHA256"], "PDS executable hash drift")
    require(pds.get("ExpectedVersion") == paths.PDS_VERSION, "PDS version binding differs")
    command = [str(tool), "-file", work_alias + "/timing.tcl", "-work_dir", work_alias,
               "-project_name", TARGET]
    require(plan.get("CommandToRunSeparately") == command, "plan command differs from exact diagnostic invocation")
    return {"Plan": plan, "PlanPath": plan_file, "PlanSHA256": hashlib.sha256(plan_bytes).hexdigest(),
            "Work": work, "Alias": alias, "Command": command, "MaximumSeconds": maximum,
            "InputFiles": input_files, "CompiledFiles": compiled_files, "TclFile": tcl_file,
            "Tool": tool, "ExecutorSHA256": sha(Path(__file__))}


def write_exclusive(path, value):
    with Path(path).open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")


def stop_owned_tree(process, work, reason):
    """Only the launched, still-live PID tree; never image-name termination."""
    record = {"Reason": reason, "OwnedPID": process.pid, "TreeKillAttempted": False,
              "ParentExitCodeBeforeCleanup": process.poll(), "Complete": False}
    if process.poll() is None:
        record["TreeKillAttempted"] = True
        try:
            if os.name == "nt":
                taskkill = Path(os.environ["SystemRoot"]) / "System32/taskkill.exe"
                with (work / "cleanup-stdout.log").open("xb") as out, (work / "cleanup-stderr.log").open("xb") as err:
                    killed = subprocess.run([str(taskkill), "/PID", str(process.pid), "/T", "/F"],
                                            stdout=out, stderr=err, shell=False, timeout=20,
                                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                record["TaskkillExitCode"] = killed.returncode
            else:
                # This recipe is Windows-only; retain an owned-parent fallback
                # so an interrupted import/test cannot abandon a spawned child.
                process.kill()
                record["OwnedParentKillFallback"] = True
            process.wait(timeout=10)
        except Exception as error:
            record["Error"] = str(error)
    record["ParentExitCodeAfterCleanup"] = process.poll()
    record["Complete"] = process.poll() is not None
    return record


def snapshot_audit(work):
    snapshot = work / "pre-sta-final.adf"
    final = work / "place_route" / (TARGET + "_pnr.adf")
    result = {"Snapshot": str(snapshot), "FinalRoutedDatabase": str(final),
              "SnapshotExists": False, "FinalRoutedDatabaseExists": False,
              "UnchangedAcrossSTA": False, "TimingAccepted": False}
    try:
        for file, flag, key in ((snapshot, "SnapshotExists", "SnapshotSHA256"),
                                (final, "FinalRoutedDatabaseExists", "FinalRoutedDatabaseSHA256")):
            require(file.absolute() == file.resolve() and file.resolve().is_relative_to(work),
                    "database path escaped canonical work directory")
            result[flag] = file.is_file()
            if result[flag]:
                result[key] = sha(file)
        result["UnchangedAcrossSTA"] = (result["SnapshotExists"] and result["FinalRoutedDatabaseExists"]
                                         and result["SnapshotSHA256"] == result["FinalRoutedDatabaseSHA256"])
    except Exception as error:
        result["Error"] = str(error)
    return result


def readback(context):
    plan, project = context["Plan"], PROJECT.resolve()
    result = {"InputDrift": [], "CompiledDrift": [], "TclDrift": False,
              "PlanDrift": False, "PDSExecutableDrift": False, "ExecutorDrift": False,
              "AliasStable": False, "SourcesStable": False}
    try:
        for name, file in context["InputFiles"].items():
            if sha(file) != plan["InputSHA256"][name]:
                result["InputDrift"].append(name)
        expected_compiled = {entry["Source"]: entry["CompiledSHA256"] for entry in plan["CompiledInputs"]}
        for name, file in context["CompiledFiles"].items():
            if sha(file) != expected_compiled[name]:
                result["CompiledDrift"].append(name)
        result["TclDrift"] = sha(context["TclFile"]) != plan["Tcl"]["SHA256"]
        result["PlanDrift"] = sha(context["PlanPath"]) != context["PlanSHA256"]
        result["PDSExecutableDrift"] = sha(context["Tool"]) != plan["PDS"]["ExecutableSHA256"]
        result["ExecutorDrift"] = sha(Path(__file__)) != context["ExecutorSHA256"]
        result["AliasStable"] = paths.validate_repo_alias(project, context["Alias"]) == context["Alias"]
        result["SourcesStable"] = not (result["InputDrift"] or result["CompiledDrift"] or result["TclDrift"]
                                          or result["PlanDrift"] or result["PDSExecutableDrift"]
                                          or result["ExecutorDrift"]) and result["AliasStable"]
    except Exception as error:
        result["Error"] = str(error)
    return result


def execute(plan_path, maximum_seconds=None):
    context = validate_plan(plan_path, maximum_seconds)
    work, process = context["Work"], None
    start = {"Schema": "independent-processed-output-diagnostic-execution-start-v1",
             "StartedUTC": utc(), "Plan": str(context["PlanPath"]), "PlanSHA256": context["PlanSHA256"],
             "ExecutorSHA256": context["ExecutorSHA256"], "Command": context["Command"],
             "WorkingDirectory": context["Plan"]["WorkingDirectoryForCommand"],
             "MaximumSeconds": context["MaximumSeconds"], "HardwareAccessed": False,
             "BitstreamRequested": False, "TimingAccepted": False}
    write_exclusive(work / START_NAME, start)
    started = time.monotonic()
    result = {"Schema": "independent-processed-output-diagnostic-execution-result-v1",
              **start, "EDAExecuted": False, "NativeExitCode": None,
              "NativeCommandSucceeded": False, "ExecutionCompletedWithoutError": False,
              "TimedOut": False, "Interrupted": False, "TimingAccepted": False,
              "HardwareReleaseAllowed": False, "HardwareAccessed": False,
              "BitstreamRequested": False, "Cleanup": {"Required": False, "TreeKillAttempted": False}}
    result["Schema"] = "independent-processed-output-diagnostic-execution-result-v1"
    try:
        require(os.name == "nt", "PDS execution is supported only on Windows")
        with (work / "execution-stdout.log").open("xb") as out, (work / "execution-stderr.log").open("xb") as err:
            process = subprocess.Popen(context["Command"], cwd=context["Plan"]["WorkingDirectoryForCommand"],
                                       stdout=out, stderr=err, shell=False,
                                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            result["OwnedPID"] = process.pid
            result["EDAExecuted"] = True
            remaining = context["MaximumSeconds"] - (time.monotonic()-started)
            require(remaining > 0, "execution deadline exhausted before process wait")
            result["NativeExitCode"] = process.wait(timeout=remaining)
            result["NativeCommandSucceeded"] = result["NativeExitCode"] == 0
    except subprocess.TimeoutExpired:
        result["TimedOut"] = True
        result["Error"] = "bounded PDS execution deadline exceeded"
    except KeyboardInterrupt:
        result["Interrupted"] = True
        result["Error"] = "execution interrupted"
    except Exception as error:
        result["Error"] = str(error)
        if process is not None and process.poll() is None:
            result["Interrupted"] = True
    finally:
        if process is not None:
            if process.poll() is None:
                result["Cleanup"] = stop_owned_tree(process, work, "timeout" if result["TimedOut"] else "interrupted")
            else:
                result["Cleanup"] = {"Required": False, "TreeKillAttempted": False, "OwnedPID": process.pid,
                                     "ParentExited": True, "Complete": True,
                                     "DescendantLivenessIndependentlyVerified": False}
            result["NativeExitCodeAfterCleanup"] = process.poll()
        result["Readback"] = readback(context)
        result["SourcesStable"] = result["Readback"]["SourcesStable"]
        result["DatabaseSnapshotAudit"] = snapshot_audit(work)
        result["ExecutionCompletedWithoutError"] = (result["NativeCommandSucceeded"] and result["SourcesStable"]
                                                       and not result.get("Error") and result["Cleanup"].get("Complete", False))
        result["FinishedUTC"] = utc()
        result["ElapsedSeconds"] = round(time.monotonic()-started, 3)
        result["LogSHA256"] = {file.name: sha(file) for file in work.iterdir()
                               if file.is_file() and file.name.endswith(".log")}
        result["Limits"] = ("Native execution receipt only. Stage logs, actual final netlist, pin/CDC/reset "
                           "and dual-corner timing still require separate review. Missing/mismatched snapshots "
                           "cannot prove unchanged across STA. No bitstream or hardware release.")
        write_exclusive(work / RESULT_NAME, result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--maximum-seconds", type=int)
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.validate_only:
            context = validate_plan(args.plan, args.maximum_seconds)
            print(json.dumps({"Validated": True, "EDAExecuted": False,
                              "PlanSHA256": context["PlanSHA256"], "Command": context["Command"],
                              "MaximumSeconds": context["MaximumSeconds"], "TimingAccepted": False}))
            return 0
        result = execute(args.plan, args.maximum_seconds)
        print(json.dumps({"ExecutionCompletedWithoutError": result["ExecutionCompletedWithoutError"],
                          "NativeExitCode": result["NativeExitCode"], "TimedOut": result["TimedOut"],
                          "SourcesStable": result["SourcesStable"], "TimingAccepted": False,
                          "Result": str(Path(args.plan).parent / RESULT_NAME), "Error": result.get("Error")}))
        return 0 if result["ExecutionCompletedWithoutError"] else 1
    except Exception as error:
        print(json.dumps({"Validated": False, "EDAExecuted": False, "TimingAccepted": False, "Error": str(error)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
