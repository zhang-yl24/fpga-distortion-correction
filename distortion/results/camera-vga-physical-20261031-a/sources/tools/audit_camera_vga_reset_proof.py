"""Bind fresh camera reset scope, native matches and the actual reset graph.

The resulting approval is limited to applying this exact proposal to an
isolated candidate copy for diagnostic STA. It never grants final timing,
physical CDC, bitstream or hardware acceptance. This tool does not run EDA.
"""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import json
import re
import shutil

import audit_camera_vga_reset_netlist as graph
import prepare_camera_vga_reset_scope as scope
import prepare_ddr_native_reset_scope as native

require, sha = scope.require, scope.sha
ROOT = scope.PROJECT / "work/camera-vga-output"


def add_watch(watched, path, digest):
    path = Path(path).resolve()
    require(path not in watched or watched[path] == digest, "conflicting artifact hash: " + str(path))
    require(path.is_file() and sha(path) == digest, "artifact drift: " + str(path))
    watched[path] = digest


def read_receipt(path, schema, expected_adf, watched, stages):
    path = Path(path).resolve()
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    require(value.get("Schema") == schema and value.get("ExecutionPassed") is True and
            value.get("ExitCode") == 0 and value.get("TimedOut") is False and
            value.get("InputDrift") == [] and value.get("Diagnostics") == [] and
            value.get("CompletionMarker") is True and value.get("InputADFUnchanged") is True and
            value.get("ActualStages") == stages and value.get("HardwareAccessed") is False and
            value.get("BitstreamRequested") is False, "native receipt did not complete cleanly")
    require(value.get("SourceADFSHA256") == value.get("ResultADFSHA256") == expected_adf,
            "native evidence uses another ADF or changed it")
    add_watch(watched, path, sha(path))
    add_watch(watched, value["SourceADF"], expected_adf)
    for name, digest in value["InputSHA256"].items():
        add_watch(watched, name, digest)
    for name, digest in value["Artifacts"].items():
        artifact = (path.parent / name).resolve()
        require(artifact.is_relative_to(path.parent), "native artifact escapes receipt directory")
        add_watch(watched, artifact, digest)
    return value


def exact_queries(queries, log):
    records = native.parse_native_matches(log)
    proof, expected = [], set()
    for query in queries:
        for role, pattern, names in (
                ("source", query["FromRegex"], ["t:" + query["Source"]]),
                ("targets", query["ToRegex"], ["t:" + x for x in query["Targets"]])):
            require(pattern not in expected, "duplicate query regex")
            expected.add(pattern)
            matches = [r for r in records if r["Pattern"] == pattern]
            require(len(matches) == 1, "native query missing or duplicated")
            row = matches[0]
            require(row["Count"] == len(names) and set(row["NativeNames"]) == set(names),
                    "native exact names/count differs: " + query["Source"] + ":" + role)
            proof.append({"Source": query["Source"], "Role": role, "NativeEvidence": row})
    require(len(records) == len(expected) and {r["Pattern"] for r in records} == expected,
            "unexpected native query records")
    return proof


def verify_vendor(path, watched):
    path = Path(path).resolve()
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    require(value.get("Schema") == "camera-vga-reset-vendor-reference-v1" and
            value.get("Status") == "pass" and value.get("AllBytesIdentical") is True and
            value.get("GlobalClockGroupsImported") is False and value.get("ConstraintsApplied") is False,
            "vendor source evidence does not pass")
    roles = scope.candidate.validate()
    expected = {str((scope.PROJECT / name).resolve()) for name in
                [scope.candidate.paths.IDF, *roles["IDFExpandedSources"]]}
    require({row["CandidatePath"] for row in value["Files"]} == expected and
            len(value["Files"]) == len(expected), "vendor evidence omits/duplicates current IDF ownership")
    for row in value["Files"]:
        add_watch(watched, row["CandidatePath"], row["SHA256"])
        add_watch(watched, row["VendorPath"], row["SHA256"])
    add_watch(watched, value["CandidateManifest"], value["CandidateManifestSHA256"])
    add_watch(watched, value["VendorFDC"]["Path"], value["VendorFDC"]["SHA256"])
    fdc = Path(value["VendorFDC"]["Path"]).read_text(encoding="utf-8-sig")
    for clock in ("rst_clk", "phy_dq_clk_0", "phy_dq_clk_1"):
        command = f"set_clock_groups -name {clock} -asynchronous -group [get_clocks {{{clock}}}]"
        require(sum(line.strip() == command for line in fdc.splitlines()) == 1,
                "same-config vendor reset clock relationship missing")
    add_watch(watched, path, sha(path))
    return value


def audit(plan_path, report_receipt, query_receipt, export_receipt, vendor_path, output):
    plan_path, output = Path(plan_path).resolve(), Path(output).resolve()
    require(output.parent == ROOT.resolve() and not output.exists(), "fresh work-root proof directory required")
    plan = json.loads(plan_path.read_text(encoding="utf-8-sig"))
    require(plan.get("Schema") == "camera-vga-reset-scope-proposal-v1" and plan.get("Complete") is True and
            plan.get("ConstraintsApplied") is False, "scope plan is not complete/unapplied")
    watched = {}
    add_watch(watched, plan_path, sha(plan_path))
    add_watch(watched, scope.__file__, plan["ToolSHA256"])
    for name, digest in plan["FilesSHA256"].items():
        path = (plan_path.parent / name).resolve()
        require(path.is_relative_to(plan_path.parent), "scope artifact escaped directory")
        add_watch(watched, path, digest)
    add_watch(watched, plan["Report"]["Path"], plan["Report"]["SHA256"])
    adf = plan["SourceADF"]["SHA256"]
    add_watch(watched, plan["SourceADF"]["Path"], adf)
    add_watch(watched, plan["CandidateManifest"]["Path"], plan["CandidateManifest"]["SHA256"])
    report_native = read_receipt(report_receipt, "camera-vga-isolated-query-v1", adf, watched, [])
    require(Path(plan["Report"]["Path"]) in watched and
            report_native["Artifacts"].get(Path(plan["Report"]["Path"]).name) == plan["Report"]["SHA256"],
            "scope report is not bound by native ADF receipt")
    paths, summaries = scope.parse_report(plan["Report"]["Path"])
    inventory = scope.audit_inventory(paths, summaries)
    queries, body, fdc = scope.query_scope(inventory)
    require(queries == plan["NativeQueries"] and
            (plan_path.parent / "query-body.tcl").read_text(encoding="ascii") == body and
            (plan_path.parent / "proposed-scope.fdc").read_text(encoding="ascii") == fdc,
            "proposal differs from freshly parsed current STA")
    query_native = read_receipt(query_receipt, "camera-vga-isolated-query-v1", adf, watched, [])
    native_body = query_native.get("Body", "")
    command_lines = [line.strip() for line in native_body.splitlines()]
    timing_initialization = [i for i, line in enumerate(command_lines)
                             if line.startswith("mpnr_report_timing ") and "-delay_type min_max" in line]
    first_query = next((i for i, line in enumerate(command_lines) if line.startswith("get_pins ")), -1)
    require(timing_initialization and 0 <= timing_initialization[0] < first_query,
            "exact native queries require prior timing-context initialization")
    actual_commands = [line.strip() for line in native_body.splitlines() if line.strip().startswith("get_pins ")]
    expected_commands = [line for line in body.splitlines() if line.startswith("get_pins ")]
    require(actual_commands == expected_commands, "executed native pin commands differ from proposal")
    log = Path(query_receipt).resolve().parent / "stdout.log"
    require(log in watched, "native query log is not hash-bound")
    name_proof = exact_queries(queries, log)
    export = read_receipt(export_receipt, "camera-vga-functional-export-v1", adf, watched,
                          ["Report Timing", "Generate Netlist"])
    require(export.get("NativeNetlistWithFFloc") is True, "actual placed functional netlist missing")
    netlist = Path(export["Netlist"]["Path"]).resolve()
    require(netlist in watched and sha(netlist) == export["Netlist"]["SHA256"] and
            netlist.stat().st_size == export["Netlist"]["Bytes"], "native netlist binding differs")
    graph_result = graph.audit_text(netlist.read_text(encoding="utf-8-sig"), queries)
    vendor = verify_vendor(vendor_path, watched)
    for module in (graph, graph.syntax, native, scope.candidate):
        add_watch(watched, module.__file__, sha(module.__file__))
    add_watch(watched, __file__, sha(__file__))
    proof = {"Schema": "camera-vga-reset-proof-v1", "CreatedUTC": datetime.now(timezone.utc).isoformat(),
             "SourceADF": plan["SourceADF"]["Path"], "SourceADFSHA256": adf,
             "NativeQueriesVerified": True, "EntryConnectivityVerified": True,
             "InternalConnectivityVerified": True, "VendorSameConfigurationVerified": True,
             "ReportNativeADFBindingVerified": True, "TimingExceptionApproved": True,
             "ApprovalScope": "Only these exact current reset pairs on an isolated copy of the bound ADF, followed by full native STA and exception-effect audit.",
             "NativeQueries": queries, "NativeNameProof": name_proof, "ResetGraph": graph_result,
             "NativeQueryContext": {"TimingInitializedBeforeGetPins": True,
                                    "InitializationCommand": command_lines[timing_initialization[0]],
                                    "Receipt": str(Path(query_receipt).resolve()),
                                    "Requirement": "Initialize timing with mpnr_report_timing before get_pins on a freshly loaded ADF."},
             "VendorReference": {"Path": str(Path(vendor_path).resolve()), "SHA256": sha(vendor_path)},
             "SourceScopePlan": {"Path": str(plan_path), "SHA256": sha(plan_path)},
             "ScopePlan": {"Path": str(output / "plan.json"), "SHA256": sha(plan_path)},
             "ProposedFDC": {"Path": str(output / "proposed-scope.fdc"),
                             "SHA256": sha(plan_path.parent / "proposed-scope.fdc")},
             "ConstraintsApplied": False, "TimingAccepted": False, "CDCPhysicalAccepted": False,
             "HardwareAccessed": False, "HardwareReleaseAllowed": False, "InputSHA256": {},
             "Limits": ["Functional connectivity and vendor lineage do not prove analog metastability MTBF.",
                        "Data hold paths remain timed and require physical repair; no data exception is authorized.",
                        "No clock-group waiver or general reset, camera, FIFO or control-path false path is approved."]}
    require(all(sha(path) == digest for path, digest in watched.items()), "bound evidence changed during audit")
    output.mkdir()
    for name in ("plan.json", *plan["FilesSHA256"]):
        shutil.copyfile(plan_path.parent / name, output / name)
        add_watch(watched, output / name, sha(plan_path.parent / name))
    proof["InputSHA256"] = {str(path): digest for path, digest in sorted(watched.items(), key=lambda x: str(x[0]))}
    with (output / "proof.json").open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(proof, stream, indent=2); stream.write("\n")
    return proof


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("plan", type=Path)
    p.add_argument("--report-receipt", type=Path, required=True)
    p.add_argument("--query-receipt", type=Path, required=True)
    p.add_argument("--export-receipt", type=Path, required=True)
    p.add_argument("--vendor-proof", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    a = p.parse_args()
    result = audit(a.plan, a.report_receipt, a.query_receipt, a.export_receipt, a.vendor_proof, a.output_dir)
    print(json.dumps({key: result[key] for key in ("SourceADFSHA256", "NativeQueriesVerified",
                      "EntryConnectivityVerified", "InternalConnectivityVerified", "TimingExceptionApproved",
                      "ScopePlan", "ProposedFDC")}))


if __name__ == "__main__":
    main()
