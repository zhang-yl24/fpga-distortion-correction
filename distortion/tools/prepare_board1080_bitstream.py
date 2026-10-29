"""Prepare offline bitstream export from the exact, independently audited ADF.

No PDS or hardware is executed. The PDS recipe declares the original full-flow
context, then explicitly loads the same repaired ADF for STA and bit generation.
PDS may skip earlier calculations when input_db_file is supplied; this recipe
does not claim a fresh synthesis/PNR. A new native audit runs before generation.
"""
from pathlib import Path
import argparse
import hashlib
import json

import audit_ddr_final_timing as timing
import prepare_board1080_timing as closure
import prepare_ddr_native_recovery_constraints as recovery


PROJECT = Path(__file__).resolve().parents[1]
SELF = Path(__file__).resolve()
FINAL_ADF_SHA256 = "309238d4ad6ee94c64182f41b30dbbdec0a28ae25d0dd7f6f03a98ad96342dce"
MANIFEST_SHA256 = "7aa056eeb40f1cbce938ecc2c59b00500f8fa3d15b787243c987288e68bb05c9"
RCF_SHA256 = "981934688d526e8d686635859d811070752570a34738548154d544e41be48516"
PASS_FLAGS = ("AuditPassed", "AllReportedNativeTimingChecksMet", "AllTenTimingTypesAndCornersChecked",
              "NativeClockDefinitionsUnchanged", "ExactExceptionPathEffectsVerified",
              "NoDataSetupOrHoldFalsePaths", "AllOtherSummaryRowsUnchanged")


def require(value, message):
    if not value:
        raise ValueError(message)


def inside(project, value):
    project, path = Path(project).resolve(), Path(value).resolve()
    require(path.is_relative_to(project) and path.is_file(), "audit input must be a file inside distortion")
    return path


def native_arguments(project, final_adf, audit_file):
    """Resolve the two native report sets from the hash-bound audit receipt."""
    final_adf, audit_file = inside(project, final_adf), inside(project, audit_file)
    require(final_adf.suffix.lower() == ".adf" and closure.sha(final_adf) == FINAL_ADF_SHA256,
            "final ADF differs from the exact audited repaired candidate")
    evidence = json.loads(audit_file.read_text(encoding="utf-8-sig"))
    require(evidence.get("Schema") == "board1080-ddr-final-native-audit-v1" and
            all(evidence.get(flag) is True for flag in PASS_FLAGS), "complete passing native audit required")
    require(evidence.get("HardwareReleaseAllowed") is False and evidence.get("PhysicalTimingReady") is False,
            "offline audit must not claim hardware release")
    bound = evidence.get("FinalRoutedADF", {})
    require(Path(bound.get("Path", "")).resolve() == final_adf and bound.get("SHA256") == FINAL_ADF_SHA256,
            "audit is bound to a different final ADF")
    require(evidence.get("ToolSHA256") == closure.sha(timing.__file__), "native audit tool has changed")
    watched = {audit_file: closure.sha(audit_file)}
    for name, digest in evidence.get("InputsSHA256", {}).items():
        path = inside(project, name)
        require(closure.SHA.fullmatch(digest) is not None and closure.sha(path) == digest,
                "native audit input SHA256 mismatch: " + path.name)
        watched[path] = digest
    require(watched.get(final_adf) == FINAL_ADF_SHA256, "final ADF is missing from audit input hashes")
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
    for label, report in (("baseline_log", baseline), ("candidate_log", candidate)):
        logs = [path for path in watched if path.parent == report.parent and path.name == "stdout.log"]
        require(len(logs) == 1, "both native IO warning logs must be hash-bound")
        args[label] = logs[0]
    rebuilt = timing.audit(**args, final_adf=final_adf, expected_adf_sha256=FINAL_ADF_SHA256)
    for key in (*PASS_FLAGS, "FalsePathCounts", "CornerSummaries", "ExternalIOWarningEvidence"):
        require(rebuilt.get(key) == evidence.get(key), "curated audit differs from native evidence: " + key)
    return args, watched


def generation_tail(work_alias, python_alias):
    path = lambda name: closure.tcl_path(work_alias + "/" + name)
    return "\n".join([
        "report_timing -force_to_run -input_db_file " + path("audited-final.adf")
        + " -delay_type min_max -max_path 1000 -nworst 4 -report_exception TRUE",
        "# PDS pre-parses Tcl; audit and bit generation execute only at runtime.",
        "if {[info script] ne {}} {",
        "    set audit_result [exec " + closure.tcl_path(python_alias) + " " + path("pre-bit-audit.py") + "]",
        "    puts $audit_result",
        "    if {[string first {PRE_BIT_NATIVE_AUDIT_PASS " + FINAL_ADF_SHA256
        + "} $audit_result] < 0} {error {Pre-bit native audit marker absent}}",
        "    gen_bit_stream -force_to_run -input_db_file " + path("audited-final.adf")
        + " -scbv {High Voltage} -unused_io_status UNUSED",
        "    puts {OFFLINE_AUDITED_BITSTREAM_COMPLETE}", "    flush stdout", "}", ""])


def runtime_gate():
    # ASCII source; all machine paths live in JSON using escaped Unicode.
    return '''from pathlib import Path
import hashlib,json,sys
work=Path(__file__).resolve().parent
project=work.parents[2]
sys.path.insert(0,str(project/'tools'))
import audit_ddr_final_timing as timing
config=json.loads((work/'pre-bit-inputs.json').read_text(encoding='utf-8'))
sha=lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
def verify():
 for name,digest in config['InputSHA256'].items():
  path=(project/name).resolve()
  if not path.is_relative_to(project) or not path.is_file() or sha(path)!=digest:
   raise ValueError('Pre-bit input changed: '+name)
verify()
arguments={name:project/value for name,value in config['BaselineArguments'].items()}
arguments.update(candidate_report=work/'report_timing/board1080_top.rtr',
 candidate_exceptions=work/'report_timing/board1080_top_exception.rtr')
result=timing.audit(**arguments,final_adf=work/'audited-final.adf',
 expected_adf_sha256=config['FinalADFSHA256'])
if not result['AuditPassed'] or not result['NoDataSetupOrHoldFalsePaths']:
 raise ValueError('Pre-bit native audit did not pass')
verify()
with (work/'pre-bit-audit.json').open('x',encoding='utf-8',newline='\\n') as stream:
 json.dump(result,stream,indent=2,ensure_ascii=False);stream.write('\\n')
print('PRE_BIT_NATIVE_AUDIT_PASS '+config['FinalADFSHA256'])
'''


def prepare(project, final_adf, audit_file, work_dir, *, repo_alias="P:/",
            pds_shell="D:/pango/PDS_2023.2/bin/pds_shell.exe", python_executable=None):
    project = Path(project).resolve()
    arguments, watched = native_arguments(project, final_adf, audit_file)
    final_adf, audit_file = inside(project, final_adf), inside(project, audit_file)
    roles = closure.validate_manifest(project)
    require(closure.sha(project / roles["Manifest"]) == MANIFEST_SHA256 and
            closure.sha(project / roles["RouteConstraint"]) == RCF_SHA256,
            "source/constraint profile differs from the repaired ADF")
    output = closure.fresh_work_dir(project, work_dir)
    alias = closure.validate_repo_alias(project, repo_alias)
    python = Path(python_executable or project.parent / ".venv/Scripts/python.exe").resolve()
    require(python.is_file(), "Python executable must exist; preparation does not run it")
    python_alias = closure.alias_path(project, alias, python)
    for helper in (SELF, Path(timing.__file__), Path(recovery.__file__), Path(closure.__file__)):
        watched[inside(project, helper)] = closure.sha(helper)
    for path, digest in watched.items():
        require(closure.sha(path) == digest, "audit input changed during preparation")
    # Keep the original timing preparer default behavior intact.
    plan = closure.prepare(project, output, repo_alias=repo_alias, pds_shell=pds_shell,
                           clock_tree_hold_target_ps=200)
    work_alias = plan["AliasWorkDirectory"]
    base = (output / "timing.tcl").read_text(encoding="ascii")
    anchor = "if {[file exists "
    require(base.count(anchor) == 1, "expected unique final snapshot anchor")
    script = base[:base.index(anchor)] + generation_tail(work_alias, python_alias)
    gate = runtime_gate()
    data = final_adf.read_bytes()
    require(closure.sha_bytes(data) == FINAL_ADF_SHA256, "final ADF changed before copy")
    (output / "audited-final.adf").write_bytes(data)
    (output / "source-native-audit.json").write_bytes(audit_file.read_bytes())
    (output / "pre-bit-audit.py").write_text(gate, encoding="ascii", newline="\n")
    (output / "timing.tcl").write_text(script, encoding="ascii", newline="\n")
    hashes = dict(plan["InputSHA256"])
    hashes.update({path.relative_to(project).as_posix(): digest for path, digest in watched.items()})
    for row in plan["CompiledInputs"]:
        path = Path(row["CompiledPath"]).resolve()
        hashes[path.relative_to(project).as_posix()] = row["CompiledSHA256"]
    for name in ("audited-final.adf", "source-native-audit.json", "pre-bit-audit.py", "timing.tcl"):
        hashes[(output / name).relative_to(project).as_posix()] = closure.sha(output / name)
    config = {"FinalADFSHA256": FINAL_ADF_SHA256, "InputSHA256": hashes,
              "BaselineArguments": {name: arguments[name].relative_to(project).as_posix()
                                    for name in ("baseline_report", "baseline_exceptions")}}
    (output / "pre-bit-inputs.json").write_text(json.dumps(config, indent=2) + "\n", encoding="ascii", newline="\n")
    hashes[(output / "pre-bit-inputs.json").relative_to(project).as_posix()] = closure.sha(output / "pre-bit-inputs.json")
    plan.update(Schema="board1080-offline-bitstream-preparation-v1", BitstreamRequested=True,
                Scope="PrepareOnlyOfflineAuditedADFExport", FreshSourcePNRClaimed=False,
                EDAExecuted=False, HardwareAccessed=False, HardwareReleaseAllowed=False,
                PhysicalTimingReady=False, InputSHA256=hashes,
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
    plan["EDAStageCommands"].extend(["runtime independent pre-bit native audit",
        "gen_bit_stream -force_to_run -input_db_file {" + work_alias + "/audited-final.adf} -scbv {High Voltage} -unused_io_status UNUSED"])
    (output / "plan.json").write_text(json.dumps(plan, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    return plan


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--final-adf", required=True, type=Path)
    parser.add_argument("--audit", required=True, type=Path)
    parser.add_argument("--work-dir", required=True, type=Path, help="fresh existing child of build/board1080-timing")
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
