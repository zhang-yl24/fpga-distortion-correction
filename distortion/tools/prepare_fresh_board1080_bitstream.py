"""Prepare an offline bitstream from the exact fresh, repaired native ADF.

The old bitstream profile is unchanged. This profile binds the fresh source
closure, both native report sets, and every audit implementation hash. PDS
must rerun the fresh native audit before generating from the same ADF copy.
Preparation never executes EDA or hardware.
"""
from pathlib import Path
import argparse
import json

import audit_fresh_ddr_timing as timing
import prepare_board1080_bitstream as previous
import prepare_board1080_timing as closure


PROJECT = Path(__file__).resolve().parents[1]
SELF = Path(__file__).resolve()
FINAL_ADF_SHA256 = "b7ee4ac251b5d97c6887ef1fd7aeacf22d8a6ce93be821ca4255823f03c74f5c"
SOURCE_ADF_SHA256 = "0f6101036b3c3981544e032ec93c3ad2b5468c79e55fa4f8f6a8014265fb15be"
SOURCE_PLAN = "build/board1080-timing/fresh-1029-b/plan.json"
SOURCE_PLAN_SHA256 = "8848732ae1727a968467df48c4dc87f485d2fcafc229fb849721e738612d5b6c"
PASS_FLAGS = previous.PASS_FLAGS
require, inside = previous.require, previous.inside


def audit_tools():
    return [Path(timing.__file__), Path(timing.native.__file__),
            Path(timing.variants.__file__), Path(timing.variants.recovery.__file__)]


def native_arguments(project, final_adf, audit_file):
    final_adf, audit_file = inside(project, final_adf), inside(project, audit_file)
    require(final_adf.suffix.lower() == ".adf" and closure.sha(final_adf) == FINAL_ADF_SHA256,
            "final ADF differs from the exact fresh repaired candidate")
    evidence = json.loads(audit_file.read_text(encoding="utf-8-sig"))
    require(evidence.get("Schema") == "board1080-fresh-ddr-final-native-audit-v1" and
            all(evidence.get(flag) is True for flag in PASS_FLAGS), "complete passing fresh native audit required")
    require(evidence.get("HardwareReleaseAllowed") is False and evidence.get("PhysicalTimingReady") is False,
            "offline audit must not claim hardware release")
    bound = evidence.get("FinalRoutedADF", {})
    require(Path(bound.get("Path", "")).resolve() == final_adf and bound.get("SHA256") == FINAL_ADF_SHA256,
            "audit is bound to a different final ADF")
    tool_hashes = {Path(name).resolve(): digest for name, digest in evidence.get("ToolsSHA256", {}).items()}
    require(set(tool_hashes) == {path.resolve() for path in audit_tools()},
            "all four fresh native audit implementation identities are required")
    watched = {audit_file: closure.sha(audit_file)}
    for path, digest in tool_hashes.items():
        require(closure.SHA.fullmatch(digest) is not None and closure.sha(path) == digest,
                "native audit implementation SHA256 mismatch")
        watched[path] = digest
    for name, digest in evidence.get("InputsSHA256", {}).items():
        path = inside(project, name)
        require(closure.SHA.fullmatch(digest) is not None and closure.sha(path) == digest,
                "native audit input SHA256 mismatch: " + path.name)
        watched[path] = digest
    require(watched.get(final_adf) == FINAL_ADF_SHA256, "final ADF missing from audit input hashes")
    reports = [path for path in watched if path.name == "board1080_top.rtr"]
    exceptions = [path for path in watched if path.name == "board1080_top_exception.rtr"]
    require(len(reports) == len(exceptions) == 2, "two complete native report sets required")
    candidates = [path for path in reports if path.is_relative_to(final_adf.parent)]
    require(len(candidates) == 1, "one report set must belong to the repaired ADF")
    candidate = candidates[0]
    baseline = next(path for path in reports if path != candidate)
    args = {"baseline_report": baseline, "baseline_exceptions": baseline.parent / "board1080_top_exception.rtr",
            "candidate_report": candidate, "candidate_exceptions": candidate.parent / "board1080_top_exception.rtr"}
    require(set(exceptions) == {args["baseline_exceptions"], args["candidate_exceptions"]},
            "native exception report identity differs")
    for label, report, filename in (("baseline_log", baseline, "query.log"),
                                     ("candidate_log", candidate, "stdout.log")):
        logs = [path for path in watched if path.parent == report.parent and path.name == filename]
        require(len(logs) == 1, "both native IO warning logs must be hash-bound")
        args[label] = logs[0]
    rebuilt = timing.audit(**args, final_adf=final_adf, expected_adf_sha256=FINAL_ADF_SHA256)
    keys = (*PASS_FLAGS, "FalsePathCounts", "CornerSummaries", "ExternalIOWarningEvidence",
            "BaselineRecoveryVariantEvidence", "BaselineEntryPaths",
            "InternalResetChecksPerCorner", "EntryResetChecksPerCorner", "BaselineInternalNativeVariantsPerCorner")
    for key in keys:
        require(rebuilt.get(key) == evidence.get(key), "curated audit differs from native evidence: " + key)
    return args, watched


def bind_source_closure(project, roles):
    """Bind the 109 source files and their actual fresh-build compiled copies."""
    project = Path(project).resolve()
    path = inside(project, project / SOURCE_PLAN)
    require(closure.sha(path) == SOURCE_PLAN_SHA256, "fresh source plan differs from the fixed profile")
    plan = json.loads(path.read_text(encoding="utf-8-sig"))
    require(plan.get("Schema") == "board1080-timing-preparation-v1", "fresh source plan schema differs")
    require(len(roles["SourceSHA256"]) == 109, "exact109 source closure required")
    hashes = plan["InputSHA256"]
    expected = {**roles["SourceSHA256"], **roles["ConstraintSHA256"], **roles["AuxiliarySHA256"]}
    require(all(hashes.get(name) == digest for name, digest in expected.items()),
            "current source or constraint differs from the actual fresh build")
    watched = {path: SOURCE_PLAN_SHA256}
    for name, digest in hashes.items():
        source = inside(project, project / name)
        require(closure.sha(source) == digest, "fresh source input changed: " + name)
        watched[source] = digest
    compiled = plan["CompiledInputs"]
    require(len(compiled) == 109 and {row["Source"] for row in compiled} == set(roles["SourceSHA256"]),
            "fresh compiled source closure differs from109 original sources")
    for row in compiled:
        require(row["OriginalSHA256"] == hashes[row["Source"]], "fresh compiled original hash differs")
        source = inside(project, path.parent / "compiled" / row["Source"])
        require(closure.sha(source) == row["CompiledSHA256"], "fresh compiled input changed")
        watched[source] = row["CompiledSHA256"]
    source_adf = inside(project, path.parent / "place_route/board1080_top_pnr.adf")
    require(closure.sha(source_adf) == SOURCE_ADF_SHA256, "fresh source routed ADF changed")
    watched[source_adf] = SOURCE_ADF_SHA256
    return watched


def generation_tail(work_alias, python_alias):
    # Reuse the proven full-context Tcl sequencing; change only the exact profile marker.
    tail = previous.generation_tail(work_alias, python_alias)
    require(tail.count(previous.FINAL_ADF_SHA256) == 1, "historical tail marker contract changed")
    return tail.replace(previous.FINAL_ADF_SHA256, FINAL_ADF_SHA256)


def runtime_gate():
    gate = previous.runtime_gate()
    old = "import audit_ddr_final_timing as timing"
    require(gate.count(old) == 1, "historical runtime import contract changed")
    return gate.replace(old, "import audit_fresh_ddr_timing as timing")


def prepare(project, final_adf, audit_file, work_dir, *, repo_alias="P:/",
            pds_shell="D:/pango/PDS_2023.2/bin/pds_shell.exe", python_executable=None):
    project = Path(project).resolve()
    arguments, watched = native_arguments(project, final_adf, audit_file)
    final_adf, audit_file = inside(project, final_adf), inside(project, audit_file)
    roles = closure.validate_manifest(project)
    require(closure.sha(project / roles["Manifest"]) == previous.MANIFEST_SHA256 and
            closure.sha(project / roles["RouteConstraint"]) == previous.RCF_SHA256,
            "source/constraint profile differs from the repaired ADF")
    watched.update(bind_source_closure(project, roles))
    output = closure.fresh_work_dir(project, work_dir)
    alias = closure.validate_repo_alias(project, repo_alias)
    python = Path(python_executable or project.parent / ".venv/Scripts/python.exe").resolve()
    require(python.is_file(), "Python executable must exist; preparation does not run it")
    python_alias = closure.alias_path(project, alias, python)
    for helper in (SELF, Path(previous.__file__), Path(closure.__file__), *audit_tools()):
        watched[inside(project, helper)] = closure.sha(helper)
    for path, digest in watched.items():
        require(closure.sha(path) == digest, "audit input changed during preparation")
    plan = closure.prepare(project, output, repo_alias=repo_alias, pds_shell=pds_shell,
                           clock_tree_hold_target_ps=200)
    work_alias = plan["AliasWorkDirectory"]
    base = (output / "timing.tcl").read_text(encoding="ascii")
    anchor = "if {[file exists "
    require(base.count(anchor) == 1, "expected unique final snapshot anchor")
    script = base[:base.index(anchor)] + generation_tail(work_alias, python_alias)
    data = final_adf.read_bytes()
    require(closure.sha_bytes(data) == FINAL_ADF_SHA256, "final ADF changed before copy")
    (output / "audited-final.adf").write_bytes(data)
    (output / "source-native-audit.json").write_bytes(audit_file.read_bytes())
    (output / "pre-bit-audit.py").write_text(runtime_gate(), encoding="ascii", newline="\n")
    (output / "timing.tcl").write_text(script, encoding="ascii", newline="\n")
    hashes = dict(plan["InputSHA256"])
    hashes.update({path.relative_to(project).as_posix(): digest for path, digest in watched.items()})
    for row in plan["CompiledInputs"]:
        path = output / "compiled" / row["Source"]
        require(closure.sha(path) == row["CompiledSHA256"], "new compiled input differs from plan")
        hashes[path.relative_to(project).as_posix()] = row["CompiledSHA256"]
    for name in ("audited-final.adf", "source-native-audit.json", "pre-bit-audit.py", "timing.tcl"):
        hashes[(output / name).relative_to(project).as_posix()] = closure.sha(output / name)
    config = {"FinalADFSHA256": FINAL_ADF_SHA256, "InputSHA256": hashes,
              "BaselineArguments": {name: arguments[name].relative_to(project).as_posix()
                                    for name in ("baseline_report", "baseline_exceptions")}}
    (output / "pre-bit-inputs.json").write_text(json.dumps(config, indent=2) + "\n", encoding="ascii", newline="\n")
    hashes[(output / "pre-bit-inputs.json").relative_to(project).as_posix()] = closure.sha(output / "pre-bit-inputs.json")
    plan.update(Schema="board1080-fresh-offline-bitstream-preparation-v1", BitstreamRequested=True,
                Scope="PrepareOnlyFreshAuditedADFExport", FreshSourcePNRClaimed=False,
                EDAExecuted=False, HardwareAccessed=False, HardwareReleaseAllowed=False,
                PhysicalTimingReady=False, InputSHA256=hashes,
                FreshSourceClosureVerified=True, OriginalSourceCount=109, FreshBuildCompiledSourceCount=109,
                BasePreparedTclSHA256=plan["Tcl"]["SHA256"],
                Tcl={"Path": work_alias + "/timing.tcl", "SHA256": closure.sha(output / "timing.tcl")})
    plan["OfflineBitstreamExport"] = {
        "OriginalADF": str(final_adf), "OriginalADFSHA256": FINAL_ADF_SHA256,
        "ExplicitFinalADF": work_alias + "/audited-final.adf", "SameADFForSTAAndBitstream": True,
        "PreBitAuditRequired": True, "SourceContextDeclarationsMayBeSkippedByPDS": True,
        "ExpectedOutput": work_alias + "/generate_bitstream/board1080_top.sbit",
        "PythonExecutable": str(python), "PythonExecutableSHA256": closure.sha(python),
        "NoHardwareOrFlashCommands": True, "ArtifactGenerationOnly": True}
    plan["EDAStageCommands"][-1] = "report_timing -force_to_run -input_db_file {" + work_alias + "/audited-final.adf} -delay_type min_max -max_path 1000 -nworst 4 -report_exception TRUE"
    plan["EDAStageCommands"].extend(["runtime independent fresh pre-bit native audit",
        "gen_bit_stream -force_to_run -input_db_file {" + work_alias + "/audited-final.adf} -scbv {High Voltage} -unused_io_status UNUSED"])
    (output / "plan.json").write_text(json.dumps(plan, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    return plan


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--final-adf", required=True, type=Path)
    parser.add_argument("--audit", required=True, type=Path)
    parser.add_argument("--work-dir", required=True, type=Path)
    parser.add_argument("--repo-alias", default="P:/")
    parser.add_argument("--pds-shell", default="D:/pango/PDS_2023.2/bin/pds_shell.exe")
    parser.add_argument("--python-executable", type=Path)
    args = parser.parse_args(argv)
    try:
        plan = prepare(PROJECT, args.final_adf, args.audit, args.work_dir, repo_alias=args.repo_alias,
                       pds_shell=args.pds_shell, python_executable=args.python_executable)
    except (ValueError, OSError, KeyError, UnicodeError, TypeError) as exc:
        parser.error(str(exc))
    print(json.dumps({"PreparedOnly": True, "EDAExecuted": False, "BitstreamRequested": True,
                      "HardwareReleaseAllowed": False, "Plan": str(Path(plan["WorkDirectory"]) / "plan.json")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
