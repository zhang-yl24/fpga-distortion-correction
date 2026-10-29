"""Prepare offline bitstream generation for one fixed checked DDR candidate.

No PDS, programmer or hardware is executed. The original preparation remains
intact; bitstream.tcl requires new native STA and a CPU gate before generation.
"""
from datetime import datetime, timezone
from pathlib import Path
import argparse
import json
import re

import audit_checked_ddr_timing as checked
import prepare_board1080_checked as profile
import prepare_board1080_timing as paths

PROJECT = Path(__file__).resolve().parents[1]
FINAL_SHA256 = "857bf183e52cbd96fb9f378f5087f4c55aba66b22f8488822b7e2dc92450c142"
AUDIT_SHA256 = "eb5031f30d09165ec965689074364348c135ca203e8421e038488869a1472d8d"
FINAL = "build/board1080-timing/checked-final-sta-1029-a/input.adf"
AUDIT = "results/board1080-checked-ddr-final-20261029-a.json"
SCHEMA = "board1080-checked-offline-bitstream-preparation-v1"
CONFIG_SCHEMA = "board1080-checked-pre-bit-inputs-v1"
require, sha, read_json = checked.require, checked.sha, checked.read_json


def check_hashes(hashes):
    require(hashes, "empty input binding")
    for name, digest in hashes.items():
        require(isinstance(digest, str) and re.fullmatch(r"[0-9a-f]{64}", digest)
                and Path(name).is_file() and sha(name) == digest, "input SHA256 drift: " + str(name))


def canonical_replay(value):
    """Only this field is produced from set iteration in the frozen auditor."""
    result = {k: v for k, v in value.items() if k != "RecordedUTC"}
    rows = result.get("RemovedResetSummaryRows", [])
    key = lambda row: (row["Corner"], row["Kind"], tuple(row["Clocks"]))
    require(len({key(row) for row in rows}) == len(rows), "duplicate removed-reset row identity")
    if "RemovedResetSummaryRows" in result:
        result["RemovedResetSummaryRows"] = sorted(rows, key=key)
    return result


def admit(project):
    """The caller cannot substitute a candidate path, receipt or digest."""
    project = Path(project).resolve()
    final, receipt = project / FINAL, project / AUDIT
    require(sha(final) == FINAL_SHA256, "fixed checked final ADF changed")
    require(sha(receipt) == AUDIT_SHA256, "fixed checked audit receipt changed")
    saved = read_json(receipt)
    rebuilt = checked.audit(project)
    require(canonical_replay(saved) == canonical_replay(rebuilt), "complete checked audit replay differs")
    require(saved["FinalRoutedADF"] == {"Path": str(final), "SHA256": FINAL_SHA256},
            "fixed checked receipt ADF binding differs")
    require(saved["AuditPassed"] is True and saved["AllReportedNativeTimingChecksMet"] is True
            and saved["TimingAccepted"] is False and saved["HardwareReleaseAllowed"] is False,
            "offline audit acceptance flags differ")
    watched = {str(Path(name).resolve()): digest for name, digest in saved["EvidenceSHA256"].items()}
    watched.update({str(receipt): AUDIT_SHA256, str(final): FINAL_SHA256, str(Path(__file__).resolve()): sha(__file__)})
    check_hashes(watched)
    return saved, watched


def generation_tail(work_alias, python_alias, config_sha256):
    require(re.fullmatch(r"[0-9a-f]{64}", config_sha256) is not None, "config digest required")
    path = lambda name: paths.tcl_path(work_alias + "/" + name)
    return "\n".join([
        "report_timing -force_to_run -input_db_file " + path("audited-final.adf")
        + " -delay_type min_max -max_path 1000 -nworst 4 -report_exception TRUE",
        "# Runtime-only CPU admission precedes offline generation from the same ADF.",
        "if {[info script] ne {}} {",
        "    set audit_result [exec " + paths.tcl_path(python_alias) + " " + path("pre-bit-audit.py")
        + " {" + config_sha256 + "}]",
        "    puts $audit_result",
        "    if {[string trim $audit_result] ne {CHECKED_PRE_BIT_NATIVE_AUDIT_PASS " + FINAL_SHA256
        + "}} {error {Checked pre-bit audit marker absent or different}}",
        "    gen_bit_stream -force_to_run -input_db_file " + path("audited-final.adf")
        + " -scbv {High Voltage} -unused_io_status UNUSED",
        "    puts {CHECKED_OFFLINE_AUDITED_BITSTREAM_COMPLETE}", "    flush stdout", "}", ""])


def runtime_gate():
    return """from pathlib import Path
import sys
work=Path(__file__).resolve().parent
project=work.parents[2]
sys.path.insert(0,str(project/'tools'))
import prepare_checked_board1080_bitstream as tool
if len(sys.argv)!=2:
 raise ValueError('one expected configuration hash is required')
tool.runtime_audit(work,sys.argv[1])
print('CHECKED_PRE_BIT_NATIVE_AUDIT_PASS '+tool.FINAL_SHA256)
"""


def tcl_prefix(original):
    anchor = "if {[file exists "
    require(original.count(anchor) == 1, "unique final snapshot anchor required")
    prefix = original[:original.index(anchor)]
    require("gen_bit_stream" not in prefix and "report_timing" not in prefix, "unexpected source Tcl stages")
    return prefix.replace("# No bitstream generation or hardware command is present.",
                          "# Offline artifact generation only; no hardware command is present.")


def timing_gate(project, report, exceptions):
    """Reparse new STA and preserve every final reported row and clock load."""
    final_dir = project / Path(FINAL).parent
    tables, clocks = [], []
    for path in (final_dir / "board1080_top.rtr", report):
        with path.open(encoding="utf-8-sig", errors="replace") as stream:
            table, clock = checked.native.parse_summaries(stream)
        tables.append(table)
        clocks.append(clock)
    require(tables[0] == tables[1] and clocks[0] == clocks[1], "new native timing rows or clocks differ from fixed final")
    baseline = project / "build/board1080-timing/checked-hold-sta-1029-a/board1080_top.rtr"
    with baseline.open(encoding="utf-8-sig", errors="replace") as stream:
        hold, _ = checked.native.parse_summaries(stream)
    totals, count, _, hdmi = checked.compare_summaries(hold, tables[1])
    require(count == 124 and len(hdmi) == 14, "checked retained summary inventory differs")
    expected, inventory, entries = checked.fresh.expected_paths(baseline)
    parsed = []
    for path in (final_dir / "board1080_top_exception.rtr", exceptions):
        with path.open(encoding="utf-8-sig", errors="replace") as stream:
            parsed.append(checked.native.parse_false_paths(stream))
    old_counts = checked.native.validate_exception_sets(parsed[0], expected)
    counts = checked.native.validate_exception_sets(parsed[1], expected)
    require(counts == old_counts, "new exact false-path variant inventory differs")
    return {"AllReportedNativeTimingChecksMet": True, "AllTenTimingTypesAndCornersChecked": True,
            "All124RetainedRowsUnchanged": True, "All14HDMIConfigurationRowsUnchanged": True,
            "NativeClockDefinitionsAndLoadsUnchanged": True, "ExactExceptionPathEffectsVerified": True,
            "NoDataSetupOrHoldFalsePaths": True, "CornerSummaries": totals, "FalsePathCounts": counts,
            "BaselineInventorySHA256": inventory["Input"]["SHA256"], "BaselineEntryPaths": entries}


def runtime_audit(work, config_sha256):
    work = Path(work).resolve()
    project = work.parents[2]
    require(work.parent == project / "build/board1080-timing" and work.name.startswith("checked-bit-"),
            "checked bitstream work directory required")
    config_path = work / "pre-bit-inputs.json"
    require(sha(config_path) == config_sha256, "runtime config SHA256 differs from executed Tcl")
    config = read_json(config_path)
    require(config["Schema"] == CONFIG_SCHEMA and config["FinalADFSHA256"] == FINAL_SHA256
            and config["AuditSHA256"] == AUDIT_SHA256, "runtime candidate identity differs")
    check_hashes(config["InputSHA256"])
    require(sha(project / AUDIT) == AUDIT_SHA256 and sha(project / FINAL) == sha(work / "audited-final.adf") == FINAL_SHA256,
            "runtime fixed ADF/receipt mismatch")
    roles = profile.validate_profile(project)
    inputs = profile.expected_inputs(project, roles)
    require(all(config["InputSHA256"].get(str((project / name).resolve())) == digest for name, digest in inputs.items()),
            "runtime config omits checked source closure")
    require(all(config["InputSHA256"].get(str(Path(name).resolve())) == digest
                for name, digest in read_json(project / AUDIT)["EvidenceSHA256"].items()),
            "runtime config omits admitted native evidence")
    source_plan = read_json(work / "source-plan.json")
    require(source_plan["InputSHA256"] == inputs and source_plan["Schema"] == profile.SCHEMA,
            "source preparation closure differs")
    for row in source_plan["CompiledInputs"]:
        compiled = work / "compiled" / row["Source"]
        require(config["InputSHA256"].get(str(compiled)) == row["CompiledSHA256"], "compiled input not bound")
    require((work / "plan.json").read_bytes() == (work / "source-plan.json").read_bytes()
            and (work / "timing.tcl").read_bytes() == (work / "original-timing.tcl").read_bytes(),
            "original preparation overwritten")
    require((work / "pre-bit-audit.py").read_text(encoding="ascii") == runtime_gate(), "runtime gate script differs")
    expected_tcl = tcl_prefix((work / "original-timing.tcl").read_text(encoding="ascii")) + generation_tail(
        config["WorkAlias"], config["PythonAlias"], config_sha256)
    require((work / "bitstream.tcl").read_text(encoding="ascii") == expected_tcl, "runtime export Tcl differs")
    plan = read_json(work / "bitstream-plan.json")
    check_hashes(plan["InputSHA256"])
    expected_hashes = dict(config["InputSHA256"])
    expected_hashes.update({str(config_path): config_sha256, str(work / "bitstream.tcl"): sha(work / "bitstream.tcl")})
    require(plan["Schema"] == SCHEMA and plan["InputSHA256"] == expected_hashes
            and plan["HardwareReleaseAllowed"] is False and plan["PhysicalTimingReady"] is False,
            "runtime export plan binding differs")
    start = read_json(work / "execution-start.json")
    command = [str(Path(start["Executable"]).resolve()), *start["Arguments"]]
    require(command == plan["CommandToRunSeparately"] and start.get("HardwareAccessed") is False,
            "actual offline invocation differs")
    begin = checked.common.stamp(start["StartedUTC"])
    now = datetime.now(timezone.utc).timestamp()
    require(begin < now, "invalid native execution start")
    report = work / "report_timing/board1080_top.rtr"
    exceptions = report.with_name("board1080_top_exception.rtr")
    before = {}
    for path in (report, exceptions):
        require(path.is_file() and begin - 2 <= path.stat().st_mtime <= now + 2, "missing or stale new native report")
        before[str(path)] = sha(path)
    with report.open(encoding="utf-8-sig", errors="replace") as stream:
        header = "".join(next(stream) for _ in range(15))
    require("version 2023.2-SP3 <build 154097>" in header and "PG2L100H" in header
            and "FBG676" in header and "board1080_top" in header, "new native report identity differs")
    result = timing_gate(project, report, exceptions)
    final_log = project / "build/board1080-timing/checked-final-sta-1029-a/native-console.log"
    expected_io = checked.native.io_warnings(final_log)
    actual_io = checked.native.io_warnings(work / "run.log")
    require(expected_io == actual_io, "new external IO warning inventory differs")
    check_hashes(config["InputSHA256"])
    check_hashes(expected_hashes)
    check_hashes(before)
    require(sha(config_path) == config_sha256 and sha(work / "audited-final.adf") == FINAL_SHA256, "runtime input drift")
    result.update(Schema="board1080-checked-pre-bit-native-audit-v1", RecordedUTC=datetime.now(timezone.utc).isoformat(),
        AuditPassed=True, FinalADFSHA256=FINAL_SHA256, SourceAuditSHA256=AUDIT_SHA256,
        PreparedInputsSHA256=expected_hashes, NewReportsSHA256=before, ExecutionStart=start,
        ExternalIOWarningsUnchanged=True, MissingInputDelayPorts=sum(k == "4086" for k, _ in actual_io),
        MissingOutputDelayPorts=sum(k == "4087" for k, _ in actual_io),
        TimingAccepted=False, PhysicalTimingReady=False, HardwareReleaseAllowed=False, HardwareAccessed=False,
        BitstreamGenerated=False, Scope="New STA runtime gate only; generation occurs after this receipt")
    serialized = json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    with (work / "pre-bit-audit.json").open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(serialized)
    return result


def prepare(project, work_dir, *, repo_alias="P:/", pds_shell="D:/pango/PDS_2023.2/bin/pds_shell.exe",
            python_executable=None):
    project = Path(project).resolve()
    output = paths.fresh_work_dir(project, work_dir)
    require(re.fullmatch(r"checked-bit-[A-Za-z0-9_-]+", output.name), "checked-bit-* directory required")
    alias = paths.validate_repo_alias(project, repo_alias)
    python = Path(python_executable or project.parent / ".venv/Scripts/python.exe").resolve()
    require(python.is_file(), "Python executable must exist")
    python_alias = paths.alias_path(project, alias, python)
    saved, watched = admit(project)
    watched[str(python)] = sha(python)
    # Preserve the original full-flow declarations and preparation manifest.
    source_plan = profile.prepare(project, output, repo_alias=repo_alias, pds_shell=pds_shell)
    work_alias = source_plan["AliasWorkDirectory"]
    for old, new in (("plan.json", "source-plan.json"), ("timing.tcl", "original-timing.tcl")):
        with (output / new).open("xb") as stream:
            stream.write((output / old).read_bytes())
    for name, data in (("audited-final.adf", (project / FINAL).read_bytes()),
                       ("source-native-audit.json", (project / AUDIT).read_bytes()),
                       ("pre-bit-audit.py", runtime_gate().encode("ascii"))):
        with (output / name).open("xb") as stream:
            stream.write(data)
    require(sha(output / "audited-final.adf") == FINAL_SHA256, "ADF changed during preparation copy")
    watched.update({str((project / name).resolve()): digest for name, digest in source_plan["InputSHA256"].items()})
    watched[str(Path(source_plan["PDS"]["Executable"]).resolve())] = source_plan["PDS"]["ExecutableSHA256"]
    for row in source_plan["CompiledInputs"]:
        watched[str(output / "compiled" / row["Source"])] = row["CompiledSHA256"]
    for name in ("plan.json", "timing.tcl", "source-plan.json", "original-timing.tcl", "audited-final.adf",
                 "source-native-audit.json", "pre-bit-audit.py"):
        watched[str(output / name)] = sha(output / name)
    check_hashes(watched)
    config = dict(Schema=CONFIG_SCHEMA, FinalADFSHA256=FINAL_SHA256, AuditSHA256=AUDIT_SHA256,
                  WorkAlias=work_alias, PythonAlias=python_alias, InputSHA256=watched)
    raw = (json.dumps(config, indent=2, ensure_ascii=True, allow_nan=False) + "\n").encode("ascii")
    with (output / "pre-bit-inputs.json").open("xb") as stream:
        stream.write(raw)
    config_sha = paths.sha_bytes(raw)
    script = tcl_prefix((output / "original-timing.tcl").read_text(encoding="ascii")) + generation_tail(work_alias, python_alias, config_sha)
    with (output / "bitstream.tcl").open("x", encoding="ascii", newline="\n") as stream:
        stream.write(script)
    hashes = {**watched, str(output / "pre-bit-inputs.json"): config_sha,
              str(output / "bitstream.tcl"): sha(output / "bitstream.tcl")}
    check_hashes(hashes)
    plan = dict(Schema=SCHEMA, PreparedUTC=datetime.now(timezone.utc).isoformat(), Scope="PrepareOnlyOfflineCheckedADFExport",
        PreparedOnly=True, EDAExecuted=False, BitstreamRequested=True, HardwareAccessed=False,
        HardwareReleaseAllowed=False, PhysicalTimingReady=False, TimingAccepted=False, FreshSourcePNRClaimed=False,
        WorkDirectory=str(output), AliasWorkDirectory=work_alias, InputSHA256=hashes,
        SourcePlan={"Path": str(output / "source-plan.json"), "SHA256": sha(output / "source-plan.json")},
        OriginalTimingTcl={"Path": str(output / "original-timing.tcl"), "SHA256": sha(output / "original-timing.tcl")},
        SourceClosureCount=len(source_plan["InputSHA256"]), SourceCount=source_plan["RoleCounts"]["ManifestSources"],
        FinalRoutedADF={"Path": str(project / FINAL), "SHA256": FINAL_SHA256}, SourceAuditSHA256=AUDIT_SHA256,
        SameADFForSTAAndBitstream=True, PreBitAuditRequired=True, NoHardwareOrFlashCommands=True,
        PDS=source_plan["PDS"], PythonExecutable={"Path": str(python), "SHA256": sha(python)},
        Tcl={"Path": work_alias + "/bitstream.tcl", "SHA256": sha(output / "bitstream.tcl")},
        CommandToRunSeparately=[source_plan["PDS"]["Executable"], "-file", work_alias + "/bitstream.tcl",
                                "-work_dir", work_alias, "-project_name", "board1080_top"],
        ExpectedOutput=work_alias + "/generate_bitstream/board1080_top.sbit",
        Limitations=["Preparation executes no EDA; PDS may skip declared source stages when loading the explicit final ADF.",
                     "The runtime gate validates a new native report before generation; no bitstream success is claimed here.",
                     "External IO, reset safety, CDC, pullups and hardware stability remain unaccepted."])
    with (output / "bitstream-plan.json").open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(plan, indent=2, ensure_ascii=False, allow_nan=False) + "\n")
    return plan


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--repo-alias", default="P:/")
    parser.add_argument("--pds-shell", default="D:/pango/PDS_2023.2/bin/pds_shell.exe")
    parser.add_argument("--python-executable", type=Path)
    args = parser.parse_args(argv)
    plan = prepare(PROJECT, args.work_dir, repo_alias=args.repo_alias, pds_shell=args.pds_shell,
                   python_executable=args.python_executable)
    print(json.dumps({"PreparedOnly": True, "EDAExecuted": False, "HardwareReleaseAllowed": False,
                      "Plan": str(Path(plan["WorkDirectory"]) / "bitstream-plan.json")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
