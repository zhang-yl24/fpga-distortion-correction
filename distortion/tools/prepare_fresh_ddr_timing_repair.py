"""Prepare (never execute) the separately admitted 2026-10-29 fresh DDR repair.

This profile deliberately does not widen the historical fixed-ADF preparer.
Every native variant remains in its replayed evidence; preparation is not timing
acceptance, a reset-exception safety proof, or permission to release hardware.
"""
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
import argparse
import json
import re

import audit_ddr_recovery_variants as variants
import prepare_ddr_timing_repair as old

closure, entry, native = old.closure, old.entry, old.native
require = old.require
PROJECT = Path(__file__).resolve().parents[1]
SELF = Path(__file__).resolve()
SOURCE_SHA256 = "0f6101036b3c3981544e032ec93c3ad2b5468c79e55fa4f8f6a8014265fb15be"
REPORT_SHA256 = "fc4aa4c1fb0a7c661c2031e15bf6f14ca72d9bfb4d1ecf9c04cab870401508a1"
ENTRY_SHA256 = "3379c4bda4af52ed1809bb80c6ab995ba8dae69f1d12d4c041b72df85fa24d74"
EXPORT_PLAN = "build/board1080-timing/fresh-entry-1029-e/export-plan.json"
EXPORT_PLAN_SHA256 = "f1bb004cc1496f4cc76f7f00f1d014cfe40741a0ba85a3f9587db99798690027"
ADMISSION = "results/board1080-fresh-admission-20261029.json"
ROUTE_LOG = "build/ddr-timing-repair/fresh-1029-admission-b/query.log"
ROUTE_LOG_SHA256 = "9f3309254b7b5586af65272bb1ed405cf1e63db4053f4fdbc3a0f690d84338e4"
ORIGINAL_ROUTE = ["CR3 of CLMA_357_619", "S_CR3 of SRB_354_618",
                  "ZDNE[0] of SRB_354_618", "IDNE[0] of SRB_360_624",
                  "S_B2 of SRB_360_624", "TX_DATA[2] of IOLHR_364_624"]
ENTRY_WRAPPER_KEYS = {"Input", "InputADF", "AuditToolSHA256", "ExportPlan"}


def project_file(project, value):
    path = Path(value)
    return old.project_file(project, path if path.is_absolute() else Path(project) / path)


def load_json(project, path):
    path = project_file(project, path)
    return path, json.loads(path.read_text(encoding="utf-8-sig"))


def watch(path, digest, watched, label):
    path = Path(path).resolve()
    require(path.is_file() and closure.sha(path) == digest, label + " hash mismatch: " + str(path))
    require(path not in watched or watched[path] == digest, "conflicting bound input hashes")
    watched[path] = digest
    return path


def source_bytes(project, value):
    source = project_file(project, value)
    require(source.suffix.lower() == ".adf", "source must be an ADF")
    data = source.read_bytes()
    require(closure.sha_bytes(data) == SOURCE_SHA256, "source differs from the pinned fresh ADF")
    return source, data


def load_variants(project, value, watched):
    evidence_path, claimed = load_json(project, value)
    report = project_file(project, claimed["Input"]["Path"])
    require(claimed["Input"]["SHA256"] == REPORT_SHA256, "recovery evidence is not the fresh native report")
    watch(report, REPORT_SHA256, watched, "native report")
    rebuilt = variants.audit_file(report)
    require(claimed == rebuilt, "recovery variant evidence differs from full native replay")
    groups = defaultdict(set)
    for row in rebuilt["Corners"]["slow"]["Checks"]:
        groups[row["Source"]].add(row["Endpoint"])
    require(sorted(map(len, groups.values())) == [1, 7, 14, 104], "fresh IP pin inventory differs")
    watch(evidence_path, closure.sha(evidence_path), watched, "variant evidence")
    return dict(groups), rebuilt, evidence_path


def load_entry(project, value, source, watched):
    audit_path, claimed = load_json(project, value)
    netlist = project_file(project, claimed["Input"]["Path"])
    require(claimed["Input"]["SHA256"] == ENTRY_SHA256, "entry netlist is not the pinned fresh export")
    watch(netlist, ENTRY_SHA256, watched, "entry netlist")
    require(claimed["Input"].get("Bytes") == netlist.stat().st_size, "entry netlist byte count differs")
    bound_adf = project_file(project, claimed["InputADF"]["Path"])
    require(claimed["InputADF"]["SHA256"] == SOURCE_SHA256, "entry audit InputADF differs")
    watch(bound_adf, SOURCE_SHA256, watched, "entry InputADF")
    require(claimed.get("AuditToolSHA256") == closure.sha(Path(entry.__file__)), "entry auditor changed since evidence")
    rebuilt = entry.audit_text(netlist.read_text(encoding="utf-8"))
    result = {key: val for key, val in claimed.items() if key not in ENTRY_WRAPPER_KEYS}
    require(result == rebuilt, "entry audit differs from full functional replay")
    require(rebuilt["Status"] == "pass" and rebuilt["FirstStageFunctionalFanout"] == 1 and
            rebuilt["OutputLoadCount"] == 11, "fresh entry synchronizer inventory differs")
    watch(audit_path, closure.sha(audit_path), watched, "entry audit")
    return audit_path, rebuilt


def load_export_inputs(project, watched):
    plan_path, plan = load_json(project, EXPORT_PLAN)
    watch(plan_path, EXPORT_PLAN_SHA256, watched, "fresh export plan")
    require(plan["AuthorityADFSHA256"] == SOURCE_SHA256, "export authority ADF differs")
    inputs = {project_file(project, name): digest for name, digest in plan["InputSHA256"].items()}
    require(len(inputs) == len(plan["InputSHA256"]), "duplicate export input identities")
    roles = closure.validate_manifest(project)
    require(len(roles["SourceSHA256"]) == 109, "fresh build must bind 109 source files")
    for name, digest in {**roles["SourceSHA256"], **roles["ConstraintSHA256"], **roles["AuxiliarySHA256"]}.items():
        path = project_file(project, name)
        require(inputs.get(path) == digest, "source/constraint is not bound by fresh export plan: " + name)
    for name, digest in old.PROFILE_HASHES.items():
        watch(project_file(project, name), digest, watched, "fresh source/constraint profile")
    for path, digest in inputs.items():
        watch(path, digest, watched, "fresh export input")
    return plan_path, roles


def load_route_evidence(project, watched):
    admission_path, admission = load_json(project, ADMISSION)
    require(admission["NewADFSHA256"] == SOURCE_SHA256 and admission["InputADFUnchanged"] is True,
            "route admission source differs")
    require(admission["ObservedReturnCode"] == 0 and
            admission["OriginalDataBranchRouteVerified"] == ORIGINAL_ROUTE and
            admission["KnownDriverAndLoadPresentAtExpectedSites"] is True, "route/site admission differs")
    require(admission["SourceEndpointPairsSHA256"] == variants.PAIR_SHA256, "route admission pin inventory differs")
    log = project_file(project, ROUTE_LOG)
    watch(log, ROUTE_LOG_SHA256, watched, "read-only route query log")
    hashes = admission["EvidenceSHA256"]
    require(hashes.get("distortion/" + ROUTE_LOG) == ROUTE_LOG_SHA256, "route log lacks admission binding")
    # Bind all original native query artifacts, without treating historical tool
    # snapshots as current code or making the partial admission a release proof.
    prefix = "distortion/build/ddr-timing-repair/fresh-1029-admission-b/"
    for name, digest in hashes.items():
        if name.startswith(prefix):
            watch(project_file(project, name.removeprefix("distortion/")), digest, watched, "route evidence")
    text = log.read_text(encoding="utf-8-sig", errors="strict")
    match = re.search(r"route for net _N173 :\s*\n(.*?)Executing : show -design_net _N173 successfully.", text, re.S)
    require(match and [line.strip() for line in match.group(1).splitlines() if line.strip()] == ORIGINAL_ROUTE,
            "native original branch route differs")
    require("Site CLMA_357_619 (6) :" in text and "Site IOLHR_364_624 (1) :" in text and
            "adj_wrdq_5[52]/LUT6_inst_perm (gopLUT6 using impl_devCL6 , devCL6)" in text and
            "dq_loop[6].u_iobuf_dq/opit_1 (gopIOL using impl , devIOL)" in text, "native driver/load sites differ")
    require(not re.search(r"(?m)^\s*(?:E:|F:|ERROR:|FATAL:)", text), "native route query reported an error")
    watch(admission_path, closure.sha(admission_path), watched, "partial admission")
    return admission_path


def load_native_query(project, log_value, result_value, source, evidence, groups, watched):
    require(result_value is not None, "fresh native_query_result binding is required")
    result_path, result = load_json(project, result_value)
    log = project_file(project, log_value)
    require(result.get("Schema") == "fresh-native-pin-query-v1" and result.get("Passed") is True and
            result.get("ExitCode") == 0 and result.get("InputDrift") == [] and result.get("Diagnostics") == [],
            "native query did not finish cleanly without input drift")
    require(all(result.get(key) is False for key in ("ConstraintsApplied", "ADFSaved", "HardwareAccessed")),
            "native query must be read-only")
    require(project_file(project, result["SourceADF"]) == source and result["SourceADFSHA256"] == SOURCE_SHA256,
            "native query source ADF differs")
    require(project_file(project, result["QueryLog"]) == log, "native query log identity differs")
    watch(log, result["QueryLogSHA256"], watched, "native pin query log")
    inputs = {Path(name).resolve(): digest for name, digest in result["InputSHA256"].items()}
    require(inputs.get(source) == SOURCE_SHA256 and inputs.get(evidence) == closure.sha(evidence),
            "native query lacks source/evidence input binding")
    for path, digest in inputs.items():
        watch(path, digest, watched, "native query input")
    text = log.read_text(encoding="utf-8-sig", errors="strict")
    require("FRESH_EXACT_PIN_QUERY_COMPLETE" in text and
            not re.search(r"(?m)^\s*(?:E:|F:|ERROR:|FATAL:)", text), "native pin query is incomplete or has errors")
    records = native.parse_native_matches(log)
    fdc, queries = old.make_scopes(groups, records)
    require(result.get("NativeRecords") == records and result.get("ExactQueries") == queries,
            "native query records differ from replay")
    watch(result_path, closure.sha(result_path), watched, "native query result")
    return fdc, queries, result_path


def prepare(project, source_adf, variant_evidence, entry_audit, native_log, out_dir, *,
            native_query_result=None, repo_alias="P:/", pds_shell="D:/pango/PDS_2023.2/bin/pds_shell.exe"):
    project = Path(project).resolve()
    source, data = source_bytes(project, source_adf)
    output = old.fresh_output(project, out_dir)
    watched = {source: SOURCE_SHA256}
    groups, recovered, evidence_path = load_variants(project, variant_evidence, watched)
    audit_path, entry_result = load_entry(project, entry_audit, source, watched)
    export_path, roles = load_export_inputs(project, watched)
    admission_path = load_route_evidence(project, watched)
    fdc, queries, query_path = load_native_query(project, native_log, native_query_result, source, evidence_path, groups, watched)
    for helper in (SELF, Path(old.__file__), Path(variants.__file__), Path(closure.__file__),
                   Path(entry.__file__), Path(native.__file__), Path(old.reference.__file__), Path(old.recovery.__file__)):
        watch(helper, closure.sha(helper), watched, "preparation helper")
    tool = Path(pds_shell).resolve()
    require(tool.is_file(), "PDS executable must exist; preparation does not execute it")
    watch(tool, closure.sha(tool), watched, "PDS executable")
    alias = closure.validate_repo_alias(project, repo_alias)
    work_alias = closure.alias_path(project, alias, output)
    repair, report = old.make_scripts(work_alias)
    payloads = {"input.adf": data, "scope-reset.fdc": fdc.encode("ascii"),
                "dummy.v": b"module ddr_diagnostic_dummy(input a, output y); assign y=a; endmodule\n",
                "repair.tcl": repair.encode("ascii"), "report.tcl": report.encode("ascii")}
    # Recheck AFTER every parser and helper before producing any mutable clone.
    for path, digest in watched.items():
        require(path.is_file() and closure.sha(path) == digest, "bound input changed during preparation: " + str(path))
    plan = {"Schema": "fresh-ddr-timing-repair-preparation-v1", "PreparedUTC": datetime.now(timezone.utc).isoformat(),
            "PreparedOnly": True, "EDAExecuted": False, "HardwareAccessed": False,
            "BitstreamRequested": False, "TimingAccepted": False, "HardwareReleaseAllowed": False,
            "Device": old.DEVICE, "ExpectedPDSVersion": closure.PDS_VERSION, "PDSVersionVerified": False,
            "SourceADF": str(source), "SourceADFSHA256": SOURCE_SHA256,
            "CloneADF": work_alias + "/input.adf", "OriginalMustRemainUnchanged": True,
            "Net": old.NET, "Branch": old.BRANCH, "Waypoints": old.WAYPOINTS,
            "InternalResetChecksPerCorner": 244, "InternalExactSourceEndpointPairs": 126,
            "IndependentEntryChecksPerCorner": 1, "ExactQueries": queries,
            "FreshEvidence": {"VariantAudit": str(evidence_path), "EntryAudit": str(audit_path),
                              "ExportPlan": str(export_path), "RouteAdmission": str(admission_path),
                              "NativeQueryResult": str(query_path), "SourceFiles": len(roles["SourceSHA256"]),
                              "NativeVariantsPerCorner": 251, "LogicalChecksPerCorner": 244,
                              "EntryOutputLoads": entry_result["OutputLoadCount"],
                              "SourceEndpointPairsSHA256": recovered["SourceEndpointPairsSHA256"]},
            "InputSHA256": {str(path): digest for path, digest in watched.items()},
            "FilesSHA256": {name: closure.sha_bytes(content) for name, content in payloads.items()},
            "CommandsRunSeparatelyInOrder": [[str(tool), "-file", work_alias + "/" + name + ".tcl",
                                               "-work_dir", work_alias + "/" + name, "-project_name",
                                               "ddr_diagnostic"] for name in ("repair", "report")],
            "RequiredRuntimeChecks": [
                "Recheck all bound inputs and original ADF hash before and after execution.",
                "Repair must run on the clone, show only the intended branch detour, and save without errors.",
                "Use a separate new PDS process for timing and exception reports; verify clone against pre-sta-repaired.adf.",
                "Independently audit both corners, all ten timing types and 244 IP plus one entry logical exceptions.",
                "No setup/hold data cuts, global clock exclusions, hardware release or timing acceptance follow from preparation.",
                "External IO, CDC/RDC protocol, analog MTBF and physical hardware validation remain separate."]}
    output.mkdir(parents=True, exist_ok=True)
    (output / "repair").mkdir()
    (output / "report").mkdir()
    for name, content in payloads.items():
        with (output / name).open("xb") as stream:
            stream.write(content)
    with (output / "plan.json").open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(plan, stream, indent=2, ensure_ascii=False)
        stream.write("\n")
    return plan


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("source-adf", "variant-evidence", "entry-audit", "native-query-log", "native-query-result", "out-dir"):
        parser.add_argument("--" + name, required=True, type=Path)
    parser.add_argument("--repo-alias", default="P:/")
    parser.add_argument("--pds-shell", default="D:/pango/PDS_2023.2/bin/pds_shell.exe")
    args = parser.parse_args(argv)
    try:
        result = prepare(PROJECT, args.source_adf, args.variant_evidence, args.entry_audit, args.native_query_log,
                         args.out_dir, native_query_result=args.native_query_result,
                         repo_alias=args.repo_alias, pds_shell=args.pds_shell)
    except (ValueError, OSError, KeyError, UnicodeError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    print(json.dumps({"PreparedOnly": True, "EDAExecuted": False, "TimingAccepted": False,
                      "SourceADFSHA256": result["SourceADFSHA256"], "Plan": str(args.out_dir / "plan.json")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
