"""Prepare checked-build native STA/export probes; NEVER execute PDS or hardware.

An independently audited completed checked build is mandatory. This creates
new plans only, with copied ADF bytes and the complete current source closure.
"""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import json
import re

import audit_checked_build as build
import prepare_board1080_checked as checked

PROJECT = Path(__file__).resolve().parents[1]
sha, require = build.sha, build.require


def json_bytes(value):
    return (json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")


def fresh_work(project, path):
    work = checked.timing.fresh_work_dir(project, path)
    require(re.fullmatch(r"checked-[A-Za-z0-9_-]+", work.name) is not None,
            "probe output must be a fresh checked-* directory")
    return work


def recheck(inputs):
    for name, digest in inputs.items():
        path = Path(name)
        require(path.is_file() and sha(path) == digest, "bound probe input changed: " + str(path))


def render_query_tcl(alias):
    p = checked.timing.tcl_path
    return ("# Prepared read-only native query; no constraint or routing edits.\n"
            "set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG676\n"
            "add_design " + p(alias + "/dummy.v") + "\n"
            "if {[info script] ne {}} {\n"
            "    mpnr -input " + p(alias + "/input.adf") + "\n"
            "    mpnr_report_timing -force_to_run -delay_type min_max -max_path 1000 -nworst 4 -report_exception TRUE\n"
            "    puts {CHECKED_NATIVE_REPORT_COMPLETE}\n    flush stdout\n}\n")


def render_export_tcl(original, alias):
    p = checked.timing.tcl_path
    suffix = ("if {[file exists " + p(alias + "/place_route/board1080_top_pnr.adf") + "]} {\n"
              "    file copy " + p(alias + "/place_route/board1080_top_pnr.adf") + " "
              + p(alias + "/pre-sta-final.adf") + "\n}\n"
              "report_timing -force_to_run -delay_type min_max -max_path 20\n")
    require(original.endswith(suffix) and original.count(suffix) == 1,
            "original checked Tcl final-stage suffix differs")
    return (original[:-len(suffix)]
            + "report_timing -force_to_run -input_db_file " + p(alias + "/input.adf")
            + " -delay_type min_max -max_path 5\n"
            + "if {[info script] ne {}} {\n    gen_netlist -force_to_run -input_db_file "
            + p(alias + "/input.adf") + " -func_sim_only\n"
            + "    puts {CHECKED_FUNCTIONAL_NETLIST_COMPLETE}\n    flush stdout\n}\n")


def prepare(project, source_build, query_work, export_work):
    project, source_build = Path(project).resolve(), Path(source_build).resolve()
    # Do not trust a cached JSON claim or a supplied expected ADF hash.
    # A currently unfinished/changed source build must fail before any write.
    audited = build.audit(project, source_build)
    require(audited.get("Schema") == "board1080-checked-full-build-audit-v1"
            and audited.get("ProcessSucceeded") is True and audited.get("NativeReturnCode") == 0
            and audited.get("ADFUnchangedAcrossSTA") is True, "checked full-build audit did not pass")
    query, export = fresh_work(project, query_work), fresh_work(project, export_work)
    require(len({source_build, query, export}) == 3, "source/query/export directories must be distinct")
    source = Path(audited["FinalRoutedADF"]["Path"]).resolve()
    digest = audited["FinalRoutedADF"]["SHA256"]
    require(source == source_build / "place_route/board1080_top_pnr.adf"
            and re.fullmatch(r"[0-9a-f]{64}", digest), "audited source ADF identity differs")
    source_plan = json.loads((source_build / "plan.json").read_text(encoding="utf-8-sig"))
    require(audited["WorkDirectory"] == str(source_build) and
            audited["InputSHA256"] == source_plan["InputSHA256"], "source build closure differs")
    bound = {str(Path(name).resolve()): value for name, value in audited["EvidenceSHA256"].items()}
    require(bound.get(str(source)) == digest, "source ADF missing from audited evidence")
    for name, value in audited["InputSHA256"].items():
        path = checked.timing.inside(project, name)
        require(bound.get(str(path.resolve())) == value, "source closure missing from audited evidence")
    for path in (Path(__file__), Path(build.__file__), Path(checked.__file__)):
        actual = sha(path)
        require(str(path.resolve()) not in bound or bound[str(path.resolve())] == actual,
                "audited preparation helper changed")
        bound[str(path.resolve())] = actual
    recheck(bound)
    data = source.read_bytes()
    require(checked.timing.sha_bytes(data) == digest, "source ADF changed while copying")
    # This invokes the real checked preparation guards, copies all109 sources,
    # and preserves its original plan.json and timing.tcl verbatim.
    prepared = checked.prepare(project, export, repo_alias=source_plan["RepoAlias"],
                               pds_shell=source_plan["PDS"]["Executable"])
    require(prepared["InputSHA256"] == audited["InputSHA256"], "export/source closure differs")
    require(prepared["PDS"] == source_plan["PDS"], "export/source executable identity differs")
    alias = prepared["RepoAlias"]
    query_alias = checked.timing.alias_path(project, alias, query)
    export_alias = prepared["AliasWorkDirectory"]
    original = (export / "timing.tcl").read_bytes()
    require(checked.timing.sha_bytes(original) == prepared["Tcl"]["SHA256"], "prepared Tcl changed")
    query_tcl = render_query_tcl(query_alias).encode("ascii")
    export_tcl = render_export_tcl(original.decode("ascii"), export_alias).encode("ascii")
    recheck(bound)
    audit_bytes = json_bytes(audited)
    query_files = {"input.adf": data, "dummy.v": b"module checked_native_probe_dummy(input a, output y); assign y=a; endmodule\n",
                   "query.tcl": query_tcl, "source-build-audit.json": audit_bytes}
    export_files = {"input.adf": data, "original-generated.tcl": original,
                    "export.tcl": export_tcl, "source-build-audit.json": audit_bytes}
    require(not any(query.iterdir()), "query directory became nonempty during preparation")
    for directory, files in ((query, query_files), (export, export_files)):
        for name, payload in files.items():
            with (directory / name).open("xb") as stream:
                stream.write(payload)
    common = dict(PreparedUTC=datetime.now(timezone.utc).isoformat(), PreparedOnly=True, EDAExecuted=False,
        HardwareAccessed=False, BitstreamRequested=False, TimingAccepted=False, PhysicalTimingReady=False,
        HardwareReleaseAllowed=False, ConstraintsApplied=False, ADFSaved=False,
        SourceBuild=str(source_build), SourceADF=str(source), SourceADFSHA256=digest,
        SourceClosureSHA256=audited["InputSHA256"], InputSHA256=bound,
        SourceBuildAuditSHA256=checked.timing.sha_bytes(audit_bytes),
        ExpectedPDSVersion=audited["PDSVersion"], NewCheckedEvidenceRequired=True)
    exe = prepared["PDS"]["Executable"]
    plans = []
    for directory, work_alias, script, schema in ((query, query_alias, "query.tcl", "checked-native-probe-preparation-v1"),
                                                  (export, export_alias, "export.tcl", "checked-functional-export-preparation-v1")):
        files = {p.relative_to(directory).as_posix(): sha(p) for p in directory.rglob("*") if p.is_file()}
        plan = dict(common, Schema=schema, WorkDirectory=str(directory), AliasWorkDirectory=work_alias,
            ActualTcl={"Path": work_alias + "/" + script, "SHA256": files[script]}, FilesSHA256=files,
            InputADF={"Path": work_alias + "/input.adf", "SHA256": digest},
            CommandToRunSeparately=[exe, "-file", work_alias + "/" + script, "-work_dir", work_alias,
                                   "-project_name", "board1080_top" if script=="export.tcl" else "checked_native_probe"],
            RequiredRuntimeChecks=["Recheck all bound inputs/copies before and after execution.",
                "Require native exit zero, expected completion marker, and no E:/F:/ERROR:/FATAL: diagnostics.",
                "Verify original and copied ADF hashes unchanged; never accept evidence from another candidate.",
                "Audit both corners/all ten timing kinds, new recovery inventory, and exported functional connectivity."])
        if script == "export.tcl":
            plan.update(OriginalPreparedPlan={"Path": str(export / "plan.json"), "SHA256": files["plan.json"]},
                OriginalGeneratedTcl={"Path": str(export / "original-generated.tcl"), "SHA256": files["original-generated.tcl"]},
                OriginalPlanUnmodified=True, OriginalTclUnmodified=True,
                ExactTclTransformation="Keep complete checked source/stage prefix; replace final snapshot/report suffix with explicit input-ADF report and guarded functional export.",
                ExpectedExecutedStages=["Report Timing", "Generate Netlist"],
                ActualExecutedStagesVerified=False, ExpandedSTA=False,
                Limitation="PDS retains real source/stage context; execute separately and reject unexpected compile/synthesis/place/route stages.")
        else:
            plan.update(ExpandedSTA=True, MaxPath=1000, NWorst=4, ReportExceptions=True,
                ExactPinQueriesPrepared=False, HistoricalNetOrRouteReused=False)
        recheck(bound)
        require(all(sha(directory / name)==value for name,value in files.items()), "prepared copy changed")
        filename = "export-plan.json" if script=="export.tcl" else "query-plan.json"
        with (directory / filename).open("xb") as stream:
            stream.write(json_bytes(plan))
        plans.append(plan)
    return {"Query": plans[0], "Export": plans[1]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("source-build", "query-work", "export-work"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args(argv)
    result = prepare(PROJECT, args.source_build, args.query_work, args.export_work)
    print(json.dumps({"PreparedOnly": True, "EDAExecuted": False,
        "SourceADFSHA256": result["Query"]["SourceADFSHA256"],
        "QueryPlan": str(args.query_work / "query-plan.json"),
        "ExportPlan": str(args.export_work / "export-plan.json")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

