"""Derive and prove only current upright reset scope; no EDA or hardware.

Reuse the frozen camera inventory/graph algorithms through explicit top-header
adapters. No historical route names, endpoint lists, or target totals enter.
The output approves no hardware release and applies no constraint.
"""
from pathlib import Path
import argparse
import hashlib
import json
import re
import tempfile

import prepare_raw_camera_reset as prep
import run_raw_camera_reset_inspect as inspect
import prepare_raw_camera_reset_scope as scope
import audit_raw_camera_reset_netlist as graph

SELF = Path(__file__).resolve()
PLAN_SCHEMA = "raw-camera-reset-scope-v1"
PROOF_SCHEMA = "raw-camera-reset-proof-v1"
require, sha = scope.require, scope.sha
DESIGN = re.compile(r"\| Design\s*:\s*(\S+)\s*")
MATCH = re.compile(r"^I: Timing-5001: The pattern '(.*)' in command '(.*)' match (\d+) objects below: (.*)$")


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def watch(watched, path, digest=None):
    path = Path(path).absolute()
    require(path == path.resolve() and path.is_file(), "canonical existing artifact required: " + str(path))
    actual = sha(path)
    require(digest is None or actual == digest, "artifact drift: " + str(path))
    require(path not in watched or watched[path] == actual, "conflicting artifact identity")
    watched[path] = actual
    return path


def watch_tools(watched):
    for module in (prep, inspect, scope, graph, graph.syntax):
        watch(watched, module.__file__)
    watch(watched, SELF)


def parse_report(report):
    paths, summaries = scope.parse_report(report)
    return paths, summaries, {"Adapter": "none; exact raw target and native paths", "OriginalTop": prep.TARGET}


def adapt_netlist(text):
    require(re.findall(r"(?m)^module\s+(\w+)\b", text) == [prep.TARGET], "one raw target required")
    return text


def exact_queries(queries, log):
    """Only Timing-5001 syntax; no old PAIRS/DRIVERS module is imported."""
    records = []
    for line in Path(log).read_text(encoding="utf-8-sig", errors="replace").splitlines():
        match = MATCH.fullmatch(line)
        if not match or not match[2].startswith("get_pins "):
            continue
        pattern, command, count, names = match[1], match[2], int(match[3]), match[4].split()
        require(count == len(names) == len(set(names)), "native count/list mismatch")
        require(all(n.startswith("t:") and scope.SAFE.fullmatch(n[2:]) and
                    not any(p in ("", ".", "..") for p in n[2:].split("/")) for n in names), "unsafe native pin name")
        # Native Timing-5001 removes Tcl braces when no quoting is required.
        prefix = "get_pins -hierarchical -regexp "
        require(command in (prefix + pattern, prefix + "{" + pattern + "}"), "unexpected native query command")
        records.append({"Pattern": pattern, "Command": command, "Count": count, "NativeNames": names})
    proof, patterns = [], set()
    for query in queries:
        for role, pattern, names in (("source", query["FromRegex"], [query["Source"]]),
                                     ("targets", query["ToRegex"], query["Targets"])):
            require(pattern not in patterns, "duplicate proposed regex")
            patterns.add(pattern)
            rows = [r for r in records if r["Pattern"] == pattern]
            require(len(rows) == 1, "native query missing or duplicated")
            require(rows[0]["Count"] == len(names) and set(rows[0]["NativeNames"]) == {"t:" + n for n in names},
                    "native exact names/count differ")
            proof.append({"Source": query["Source"], "Role": role, "NativeEvidence": rows[0]})
    require(len(records) == len(patterns), "unexpected native pin query")
    return proof


def receipt_status(value, mode, adf_sha):
    stages = [] if mode == "query" else ["Report Timing", "Generate Netlist"]
    events = [[stage, event] for stage in stages for event in ("started", "done")]
    require(value.get("Schema") == inspect.SCHEMA and value.get("Target") == prep.TARGET
            and value.get("Mode") == mode and value.get("ExecutionPassed") is True
            and value.get("ExitCode") == 0 and value.get("TimedOut") is False
            and value.get("StoppedForUnexpectedStage") is False and not value.get("Error")
            and value.get("InputDrift") == [] and value.get("Diagnostics") == []
            and value.get("CompletionMarker") is True and value.get("InputADFUnchanged") is True
            and value.get("Cleanup", {}).get("Complete") is True
            and value.get("ExpectedActualStages") == stages and value.get("ActualEvents") == events
            and value.get("HardwareAccessed") is False and value.get("BitstreamRequested") is False
            and value.get("EDAExecuted") is True and value.get("SourceADFSHA256") == adf_sha,
            "upright inspection receipt is not clean or has wrong identity")


def inspection_receipt(path, mode, build_plan, adf, adf_sha, watched):
    path = watch(watched, path)
    require(path.name == "result.json" and path.parent.parent == prep.WORK, "exact upright inspection result required")
    value = read(path)
    receipt_status(value, mode, adf_sha)
    require(re.fullmatch(r"[0-9a-f]{64}", value.get("StagePlanSHA256", "")) is not None,
            "receipt must bind its exact inspection stage-plan hash")
    stage_path = watch(watched, path.parent / "stage-plan.json", value.get("StagePlanSHA256"))
    stage = read(stage_path)
    expected, tcl, bound = inspect.recipe(build_plan, adf, adf_sha, path.parent, mode,
                                         value.get("QueryBody"), value["MaximumSeconds"])
    require(set(stage) == set(expected) | {"PreparedUTC"} and isinstance(stage["PreparedUTC"], str)
            and stage["PreparedUTC"] and {k: v for k, v in stage.items() if k != "PreparedUTC"} == expected,
            "inspection stage plan differs from current upright recipe")
    require(all(value.get(k) == v for k, v in stage.items()), "receipt differs from bound inspection plan")
    for p, h in bound.items():
        watch(watched, p, h)
    require((path.parent / "stage.tcl").read_bytes() == tcl.encode("ascii"), "executed inspection Tcl drift")
    watch(watched, path.parent / "input.adf", adf_sha)
    watch(watched, path.parent / "executor-snapshot.py", sha(inspect.SELF))
    require(isinstance(value.get("Artifacts"), dict), "missing native artifact inventory")
    for name, digest in value["Artifacts"].items():
        artifact = (path.parent / name).absolute()
        require(artifact.is_relative_to(path.parent), "native artifact escapes receipt")
        watch(watched, artifact, digest)
    for name in ("stage.tcl", "stdout.log", "stderr.log"):
        require(name in value["Artifacts"], "native core artifact is unbound")
    return value


def vendor_provenance(path, watched):
    """Rehash same-config vendor bytes against NEW candidate ownership roles."""
    path = watch(watched, path)
    value = read(path)
    require(value.get("Schema") == "camera-vga-reset-vendor-reference-v1"
            and value.get("Status") == "pass" and value.get("AllBytesIdentical") is True
            and value.get("GlobalClockGroupsImported") is False and value.get("ConstraintsApplied") is False,
            "vendor source reference is not byte-equivalent evidence")
    roles = prep.validate_sources()
    expected = {(prep.PROJECT / name).resolve() for name in roles["Sources"] if name.startswith("platform/video_base/ipcore/ddr3_test/")}
    rows = value.get("Files", [])
    require(len(rows) == len(expected) and {Path(r["CandidatePath"]).resolve() for r in rows} == expected,
            "vendor file coverage differs from current upright IDF-expanded roles")
    for row in rows:
        vendor = Path(row["VendorPath"]).absolute()
        require(vendor.is_relative_to(prep.PROJECT.parent / "vendor/reference/ddr"), "vendor file outside reference DDR tree")
        watch(watched, row["CandidatePath"], row["SHA256"])
        watch(watched, vendor, row["SHA256"])
    fdc_path = watch(watched, value["VendorFDC"]["Path"], value["VendorFDC"]["SHA256"])
    fdc = fdc_path.read_text(encoding="utf-8-sig")
    for clock in ("rst_clk", "phy_dq_clk_0", "phy_dq_clk_1"):
        command = f"set_clock_groups -name {clock} -asynchronous -group [get_clocks {{{clock}}}]"
        require(sum(line.strip() == command for line in fdc.splitlines()) == 1, "vendor clock relationship missing")
    manifest = watch(watched, prep.PROJECT / prep.MANIFEST)
    return {"SourceReference": {"Path": str(path), "SHA256": sha(path)},
            "CandidateManifest": {"Path": str(manifest), "SHA256": sha(manifest)},
            "ActualIDFAndExpandedBodyCount": len(expected), "AllBytesRehashedIdentical": True,
            "DDRBodyComparison": {"CandidateTop": prep.TOP, "ReferenceTop": prep.BASE_TOP, "TopDifferencesLimitedToNamesInitAndRegisteredStartup": True}, "GlobalClockGroupsImported": False,
            "OldCandidateApprovalInherited": False, "VendorFDC": value["VendorFDC"]}


def bind_build(build_plan, adf, watched):
    build_plan, adf = Path(build_plan).absolute(), Path(adf).absolute()
    _, bound = inspect.bind(build_plan, adf, sha(adf))
    for path, digest in bound.items():
        watch(watched, path, digest)
    watch_tools(watched)
    return build_plan, adf


def inventory(report, allow_incomplete=False):
    paths, summaries, adapter = parse_report(report)
    result = scope.audit_inventory(paths, summaries, require_complete=not allow_incomplete)
    return result, adapter


def summary(inv):
    return {"Complete": inv["Complete"], "LogicalChecksByCorner": {c: r["LogicalChecks"] for c, r in inv["Corners"].items()},
            "NativeVariantsByCorner": {c: r["NativeVariants"] for c, r in inv["Corners"].items()},
            "FailingChecksByCorner": {c: r["FailingChecks"] for c, r in inv["Corners"].items()},
            "HistoricalEndpointInventoryUsed": False}


def save(directory, result, payloads, watched, filename):
    directory = prep.work_path(directory)
    require(not directory.exists(), "fresh upright evidence directory required")
    require(all(sha(p) == h for p, h in watched.items()), "evidence changed during audit")
    result["ToolSHA256"] = {str(p): h for p, h in watched.items() if p.suffix == ".py"}
    result["InputSHA256"] = {str(p): h for p, h in sorted(watched.items(), key=lambda x: str(x[0]))}
    result["FilesSHA256"] = {n: hashlib.sha256(data.encode()).hexdigest() for n, data in payloads.items()}
    directory.mkdir()
    for name, data in payloads.items():
        with (directory / name).open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(data)
    with (directory / filename).open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    return result


def prepare(build_plan, adf, report, output, report_receipt=None, allow_incomplete=False):
    watched = {}
    build_plan, adf = bind_build(build_plan, adf, watched)
    report = watch(watched, report)
    native_bound = False
    if report_receipt:
        mode = read(report_receipt).get("Mode")
        require(mode in ("query", "export"), "invalid report receipt mode")
        receipt = inspection_receipt(report_receipt, mode, build_plan, adf, sha(adf), watched)
        root = Path(report_receipt).absolute().parent
        require(report.is_relative_to(root) and receipt["Artifacts"].get(report.relative_to(root).as_posix()) == sha(report),
                "scope report missing from native receipt")
        native_bound = True
    else:
        require(report == build_plan.parent / "report_timing" / (prep.TARGET + ".rtr"),
                "initial report must be the current build's exact report_timing path")
    inv, adapter = inventory(report, allow_incomplete)
    queries, body, fdc = scope.query_scope(inv) if inv["Complete"] else ([], "", "")
    plan = {"Schema": PLAN_SCHEMA, "Target": prep.TARGET, "CreatedUTC": prep.utc(),
            "Status": "prepared_unapplied" if inv["Complete"] else "incomplete_no_proposal",
            "BuildPlan": str(build_plan), "SourceADF": str(adf), "SourceADFSHA256": sha(adf),
            "Report": {"Path": str(report), "SHA256": sha(report)}, "ReportReceipt": str(report_receipt) if report_receipt else None,
            "ReportNativeADFBindingVerified": native_bound, "ReportAdapter": adapter,
            "NativeQueries": queries, "UniqueSourceEndpointPairs": sum(len(q["Targets"]) for q in queries),
            **summary(inv), "ConstraintsApplied": False, "TimingExceptionApproved": False,
            "TimingAccepted": False, "HardwareAccessed": False, "HardwareReleaseAllowed": False,
            "EDAExecuted": False, "Limits": "Initial build report hash is recorded after execution unless a clean inspection receipt binds it. Proof must rederive scope from a receipt-bound current native report."}
    payloads = {"recovery-inventory.json": json.dumps(inv, indent=2) + "\n"}
    if inv["Complete"]:
        payloads.update({"query-body.tcl": body, "proposed-scope.fdc": fdc})
    return save(output, plan, payloads, watched, "plan.json")


def prove(plan_path, query_receipt, export_receipt, vendor_path, output, report=None):
    watched = {}
    plan_path = watch(watched, plan_path)
    plan = read(plan_path)
    require(plan.get("Schema") == PLAN_SCHEMA and plan.get("Target") == prep.TARGET and plan.get("Complete") is True
            and plan.get("ConstraintsApplied") is False and plan.get("TimingExceptionApproved") is False,
            "complete unapplied upright scope plan required")
    for name, digest in plan["InputSHA256"].items():
        watch(watched, name, digest)
    for name, digest in plan["FilesSHA256"].items():
        child = plan_path.parent / name
        require(child.resolve().is_relative_to(plan_path.parent), "scope artifact escaped")
        watch(watched, child, digest)
    build_plan, adf = bind_build(plan["BuildPlan"], plan["SourceADF"], watched)
    require(sha(adf) == plan["SourceADFSHA256"], "scope ADF drift")
    original, _ = inventory(plan["Report"]["Path"])
    old_queries, body, fdc = scope.query_scope(original)
    require(old_queries == plan["NativeQueries"] and (plan_path.parent / "query-body.tcl").read_text() == body
            and (plan_path.parent / "proposed-scope.fdc").read_text() == fdc, "scope proposal changed")
    query = inspection_receipt(query_receipt, "query", build_plan, adf, sha(adf), watched)
    export = inspection_receipt(export_receipt, "export", build_plan, adf, sha(adf), watched)
    actual_body = Path(query["QueryBody"]).read_text(encoding="ascii")
    actual_commands, scope_commands = inspect.query_commands(actual_body), inspect.query_commands(body)
    require(actual_commands[:len(scope_commands)] == scope_commands and
            all(c.startswith(("show -design_net ", ".switch_db ", "dump_net ", "puts "))
                for c in actual_commands[len(scope_commands):]), "executed reset commands differ from exact scope")
    names = exact_queries(old_queries, Path(query_receipt).parent / "stdout.log")
    report = Path(report).absolute() if report else Path(export_receipt).absolute().parent / "report_timing" / (prep.TARGET + ".rtr")
    matches = []
    for receipt_path, receipt in ((query_receipt, query), (export_receipt, export)):
        root = Path(receipt_path).absolute().parent
        if report.is_relative_to(root) and receipt["Artifacts"].get(report.relative_to(root).as_posix()) == sha(report):
            matches.append(str(Path(receipt_path).absolute()))
    require(len(matches) == 1, "fresh complete report is not uniquely receipt-bound")
    current, adapter = inventory(report)
    queries, newbody, newfdc = scope.query_scope(current)
    require(queries == old_queries and newbody == body and newfdc == fdc, "fresh native reset inventory differs from proposal")
    netlist = Path(export["Netlist"]["Path"]).absolute()
    expected_netlist = Path(export_receipt).absolute().parent / "generate_netlist" / (prep.TARGET + "_sim.v")
    require(export.get("NativeNetlistWithFFloc") is True and netlist == expected_netlist and netlist in watched
            and sha(netlist) == export["Netlist"]["SHA256"] and netlist.stat().st_size == export["Netlist"]["Bytes"],
            "actual placed upright netlist is not bound")
    reset_graph = graph.audit_text(adapt_netlist(netlist.read_text(encoding="utf-8-sig")), queries)
    require(reset_graph["HeaderOnlyAdapter"] == prep.TARGET + " to board1080_top for strict V_* parsing", "raw graph adapter differs")
    vendor = vendor_provenance(vendor_path, watched)
    result = {"Schema": PROOF_SCHEMA, "Target": prep.TARGET, "CreatedUTC": prep.utc(), "Status": "pass",
              "SourceADF": str(adf), "SourceADFSHA256": sha(adf), "ScopePlan": {"Path": str(plan_path), "SHA256": sha(plan_path)},
              "NativeQueries": queries, "NativeNameProof": names, "ResetGraph": reset_graph, "VendorProvenance": vendor,
              "NativeQueriesVerified": True, "EntryConnectivityVerified": True, "InternalConnectivityVerified": True,
              "VendorSameConfigurationVerified": True, "ReportNativeADFBindingVerified": True,
              "CurrentReport": {"Path": str(report), "SHA256": sha(report), "Receipt": matches[0]}, "ReportAdapter": adapter,
              "CurrentNetlist": export["Netlist"], **summary(current), "UniqueSourceEndpointPairs": sum(len(q["Targets"]) for q in queries),
              "ScopeAuditPassed": True, "TimingExceptionApproved": False, "ConstraintsApplied": False,
              "TimingAccepted": False, "CDCPhysicalAccepted": False, "HardwareAccessed": False,
              "HardwareReleaseAllowed": False, "EDAExecuted": False,
              "Limits": "Audit only: exact current reset scope and native connectivity. Any isolated application needs separate explicit execution, full STA and exception-effect proof. No data false paths, clock-group waiver, MTBF or hardware release."}
    return save(output, result, {"current-recovery-inventory.json": json.dumps(current, indent=2) + "\n",
                                 "proposed-scope.fdc": fdc}, watched, "proof.json")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_subparsers(dest="mode", required=True)
    prepare_parser = modes.add_parser("prepare")
    for name in ("build-plan", "adf", "report", "output-dir"):
        prepare_parser.add_argument("--" + name, type=Path, required=True)
    prepare_parser.add_argument("--report-receipt", type=Path)
    prepare_parser.add_argument("--allow-incomplete", action="store_true")
    prove_parser = modes.add_parser("prove")
    for name in ("scope-plan", "query-receipt", "export-receipt", "vendor-proof", "output-dir"):
        prove_parser.add_argument("--" + name, type=Path, required=True)
    prove_parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    if args.mode == "prepare":
        result = prepare(args.build_plan, args.adf, args.report, args.output_dir, args.report_receipt, args.allow_incomplete)
    else:
        result = prove(args.scope_plan, args.query_receipt, args.export_receipt, args.vendor_proof, args.output_dir, args.report)
    print(json.dumps({k: result[k] for k in ("Schema", "Status", "Complete", "LogicalChecksByCorner", "NativeVariantsByCorner",
                      "UniqueSourceEndpointPairs", "ScopeAuditPassed", "TimingExceptionApproved", "HardwareReleaseAllowed") if k in result}))


if __name__ == "__main__":
    main()
