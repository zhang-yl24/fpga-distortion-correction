"""Prepare a repair recipe for one exact routed board1080 database.

This tool does not execute PDS. It copies the bound baseline, prepares four
IP reset scopes and the independently audited entry RDC, and changes one data
branch through measured device pins. Separate PDS processes must save and then
reload the copy; live timing after new exceptions is unreliable in this PDS.
The recipe is deliberately limited to the observed baseline SHA256. A rebuilt
or changed database needs a fresh path/route audit, not a hash override.
"""
from pathlib import Path
from collections import defaultdict
from datetime import datetime, timezone
import argparse
import hashlib
import json
import re

import audit_ddr_entry_reset_netlist as entry
import prepare_board1080_timing as closure
import prepare_ddr_ip_reset_constraints as reference
import prepare_ddr_native_recovery_constraints as recovery
import prepare_ddr_native_reset_scope as native


PROJECT = Path(__file__).resolve().parents[1]
SELF = Path(__file__).resolve()
BASELINE_SHA256 = "c146885f90da22cae61d106f0768529c98f3d2e55f8604315328e61700d4e3fc"
ENTRY_EXPORT_SHA256 = "1ccb8f9e90362319064b6db51e88882043b3cdac2331e853326f7b1d99d88113"
PAIR_IDENTITY_SHA256 = "3b618334e27a72bcd8636dedcc1e9d82f32db47645e3469ba8b577b136f8a92f"
PROFILE_HASHES = {
    "board/board1080-rowpipe-sources.json": "7aa056eeb40f1cbce938ecc2c59b00500f8fa3d15b787243c987288e68bb05c9",
    "board/board1080-ddr-ioclk-priority.rcf": "981934688d526e8d686635859d811070752570a34738548154d544e41be48516",
}
DEVICE = {"Family": "Logos2", "Device": "PG2L100H", "Speedgrade": "-6", "Package": "FBG676"}
ENTRY_SOURCE = "power_ready/opit_0_inv_L6Q_perm/CLK"
ENTRY_TARGET = ("u_ddr3_test_h/u_ddrphy_top/u_ddrphy_rst_seq_rstn_sync/"
                "sig_async_r1[0]/opit_0_srl/RS")
NET = "_N173"
BRANCH = "TX_DATA[2]:IOLHR_364_624"
WAYPOINTS = "ZDNE[0]:SRB_342_582>IDNE[0]:SRB_348_588;"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def project_file(project, value):
    project, value = Path(project).resolve(), Path(value).resolve()
    require(value.is_relative_to(project) and value.is_file(), "input must be a file inside distortion")
    return value


def source_bytes(project, source):
    source = project_file(project, source)
    require(source.suffix.lower() == ".adf", "routed source must be an ADF")
    data = source.read_bytes()
    require(closure.sha_bytes(data) == BASELINE_SHA256,
            "source ADF differs from the audited baseline; no hash override is supported")
    return source, data


def load_native_evidence(project, evidence_path):
    evidence_path = project_file(project, evidence_path)
    evidence = json.loads(evidence_path.read_text(encoding="utf-8-sig"))
    report = project_file(project, evidence["Input"]["Path"])
    require(closure.sha(report) == evidence["Input"]["SHA256"], "native report SHA256 differs from evidence")
    with report.open(encoding="utf-8-sig") as stream:
        header = "".join(next(stream, "") for _ in range(12))
    for key, value in (("Design", "board1080_top"), ("Device", "PG2L100H"),
                       ("Speed Grade", "-6"), ("Package", "FBG676")):
        require(re.search(r"(?m)^\| " + re.escape(key) + r"\s*:\s*" + re.escape(value) + r"\s*$", header),
                "native report device/design does not match the bound baseline")
    with report.open(encoding="utf-8-sig") as stream:
        paths, summaries = recovery.parse_lines(stream)
    rebuilt, _ = recovery.build(paths, summaries, include_cpd=True)
    canonical = json.dumps(sorted((p["Source"], p["Endpoint"]) for p in rebuilt["ExactCandidatePairs"]),
                           separators=(",", ":")).encode("ascii")
    require(closure.sha_bytes(canonical) == PAIR_IDENTITY_SHA256,
            "native reset identities differ from this exact repair profile")
    claimed = evidence.get("FullNativeRecoveryPaths", [])
    identity = lambda row: (row["Corner"], recovery.identity(row), row["Slack"])
    require(len(claimed) == 488 and sorted(map(identity, claimed)) == sorted(map(identity, paths)),
            "curated native paths differ from the bound complete report")
    groups = defaultdict(set)
    for pair in rebuilt["ExactCandidatePairs"]:
        groups[pair["Source"]].add(pair["Endpoint"])
    require(sorted(map(len, groups.values())) == [1, 7, 14, 104], "four exact IP driver inventories required")
    return dict(groups), {evidence_path: closure.sha(evidence_path), report: closure.sha(report)}


def load_entry_evidence(project, audit_path):
    audit_path = project_file(project, audit_path)
    audit = json.loads(audit_path.read_text(encoding="utf-8-sig"))
    netlist = project_file(project, audit["Input"]["Path"])
    require(closure.sha(netlist) == audit["Input"]["SHA256"] == ENTRY_EXPORT_SHA256,
            "entry functional export SHA256 differs from the audited source")
    result = entry.audit_text(netlist.read_text(encoding="utf-8"))
    require(audit.get("Status") == result["Status"] == "pass" and
            audit.get("FirstStageFunctionalFanout") == result["FirstStageFunctionalFanout"] == 1 and
            audit.get("OutputLoadCount") == result["OutputLoadCount"] == 14,
            "entry two-stage connectivity proof differs from the audited structure")
    return {audit_path: closure.sha(audit_path), netlist: closure.sha(netlist)}


def make_scopes(groups, records):
    require(sorted(map(len, groups.values())) == [1, 7, 14, 104], "four exact IP driver inventories required")
    full = dict(groups)
    full[ENTRY_SOURCE] = {ENTRY_TARGET}
    lines = ["# Prepared-only candidate; PDS execution and native exception audit remain separate.",
             "# Four IP reset drivers (244 checks), plus independent entry RDC (one check).",
             "# No clock groups, setup/hold data exceptions, or Tcl handle-size assumptions."]
    queries = []
    for source, targets in sorted(full.items()):
        targets = sorted(targets)
        for role, expected in (("from", [source]), ("to", targets)):
            expected = {"t:" + name for name in expected}
            matches = [record for record in records if set(record["NativeNames"]) == expected]
            require(matches, "missing exact native object-name evidence for " + source + ":" + role)
            require(all(record["Count"] == len(expected) for record in matches), "native object count differs")
        from_pattern, to_pattern = reference.exact_regex([source]), reference.exact_regex(targets)
        lines.append("set_false_path -from [get_pins -hierarchical -regexp {" + from_pattern
                     + "}] -to [get_pins -hierarchical -regexp {" + to_pattern + "}]")
        queries.append({"Source": source, "Targets": targets, "ExpectedFromCount": 1,
                        "ExpectedTargetCount": len(targets), "EntryRDC": source == ENTRY_SOURCE})
    return "\n".join(lines) + "\n", queries


def make_scripts(alias_work):
    path = lambda name: closure.tcl_path(alias_work + "/" + name)
    common = ("set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG676\n"
              "add_design " + path("dummy.v") + "\n")
    repair = common + "\n".join([
        "# info script is empty during PDS initial parsing; mutating operations run only later.",
        "if {[info script] ne {}} {",
        "    mpnr -input " + path("input.adf"),
        "    puts {DDR_REPAIR_ORIGINAL_ROUTE}",
        "    show -design_net {_N173}",
        "    source " + path("scope-reset.fdc"),
        "    unroute -branch {_N173:TX_DATA[2]:IOLHR_364_624;}",
        "    manual_route -net {_N173} -branch {TX_DATA[2]:IOLHR_364_624} -pins {" + WAYPOINTS + "}",
        "    puts {DDR_REPAIR_CANDIDATE_ROUTE}",
        "    show -design_net {_N173}",
        "    save_adif",
        "    puts {DDR_REPAIR_SAVED_PENDING_TIMING_AND_EXCEPTION_AUDIT}",
        "    flush stdout", "}", ""])
    report = common + "\n".join([
        "# Run in a NEW PDS process after the repair command finishes successfully.",
        "if {[info script] ne {}} {",
        "    file copy " + path("input.adf") + " " + path("pre-sta-repaired.adf"),
        "    mpnr -input " + path("input.adf"),
        "    show -design_net {_N173}",
        "    mpnr_report_timing -force_to_run -delay_type min_max -max_path 1000 -nworst 4 -report_exception TRUE",
        "    puts {DDR_REPAIR_REPORT_COMPLETE_PENDING_INDEPENDENT_AUDIT}",
        "    flush stdout", "}", ""])
    return repair, report


def fresh_output(project, value):
    root = Path(project).resolve() / "build/ddr-timing-repair"
    output = Path(value).absolute()
    require(root.resolve() == root and output.resolve() == output and output.parent == root and
            re.fullmatch(r"[A-Za-z0-9_-]+", output.name), "output must be a direct, nonlinked child of build/ddr-timing-repair")
    require(not output.exists() or output.is_dir() and not any(output.iterdir()), "output must be fresh or empty")
    return output


def prepare(project, source_adf, evidence, entry_audit, native_log, out_dir, *, repo_alias="P:/",
            pds_shell="D:/pango/PDS_2023.2/bin/pds_shell.exe"):
    project = Path(project).resolve()
    source, data = source_bytes(project, source_adf)
    groups, watched = load_native_evidence(project, evidence)
    watched.update(load_entry_evidence(project, entry_audit))
    native_log = project_file(project, native_log)
    records = native.parse_native_matches(native_log)
    fdc, queries = make_scopes(groups, records)
    watched[native_log] = closure.sha(native_log)
    watched[source] = BASELINE_SHA256
    roles = closure.validate_manifest(project)
    for name, digest in PROFILE_HASHES.items():
        path = closure.inside(project, name)
        require(closure.sha(path) == digest, "source/constraint profile differs from the exact routed baseline")
        watched[path] = digest
    for name, digest in {**roles["SourceSHA256"], **roles["ConstraintSHA256"], **roles["AuxiliarySHA256"]}.items():
        watched[closure.inside(project, name)] = digest
    for helper in (SELF, Path(closure.__file__), Path(reference.__file__), Path(recovery.__file__),
                   Path(entry.__file__), Path(native.__file__)):
        watched[helper.resolve()] = closure.sha(helper)
    tool = Path(pds_shell).resolve()
    require(tool.is_file(), "PDS executable must exist; preparation does not execute it")
    watched[tool] = closure.sha(tool)
    alias = closure.validate_repo_alias(project, repo_alias)
    output = fresh_output(project, out_dir)
    work_alias = closure.alias_path(project, alias, output)
    repair, report = make_scripts(work_alias)
    dummy = b"module ddr_diagnostic_dummy(input a, output y); assign y=a; endmodule\n"
    for path, digest in watched.items():
        require(closure.sha(path) == digest, "bound input changed during preparation: " + str(path))
    commands = [[str(tool), "-file", work_alias + "/" + name + ".tcl", "-work_dir",
                 work_alias + "/" + name, "-project_name", "ddr_diagnostic"] for name in ("repair", "report")]
    plan = {"Schema": "ddr-timing-repair-preparation-v1", "PreparedUTC": datetime.now(timezone.utc).isoformat(),
            "PreparedOnly": True, "EDAExecuted": False, "HardwareAccessed": False,
            "BitstreamRequested": False, "TimingAccepted": False, "HardwareReleaseAllowed": False,
            "Device": DEVICE, "ExpectedPDSVersion": closure.PDS_VERSION, "PDSVersionVerified": False,
            "SourceADF": str(source), "SourceADFSHA256": BASELINE_SHA256,
            "CloneADF": work_alias + "/input.adf", "OriginalMustRemainUnchanged": True,
            "Net": NET, "Branch": BRANCH, "Waypoints": WAYPOINTS,
            "InternalResetChecksPerCorner": 244, "InternalExactSourceEndpointPairs": 126,
            "IndependentEntryChecksPerCorner": 1, "ExactQueries": queries,
            "InputSHA256": {str(path): digest for path, digest in watched.items()},
            "FilesSHA256": {"input.adf": BASELINE_SHA256, "scope-reset.fdc": closure.sha_bytes(fdc.encode("ascii")),
                            "dummy.v": closure.sha_bytes(dummy),
                            "repair.tcl": closure.sha_bytes(repair.encode("ascii")),
                            "report.tcl": closure.sha_bytes(report.encode("ascii"))},
            "CommandsRunSeparatelyInOrder": commands,
            "RequiredRuntimeChecks": [
                "Recheck all bound inputs and original ADF hash before and after execution.",
                "First command must finish without native errors and show the intended branch detour.",
                "save_adif writes the loaded CLONE in place; it must never load the original for mutation.",
                "Second command must use a new PDS process; compare clone hash with pre-sta-repaired.adf.",
                "Audit exact native query names and all false-path identities:244 IP plus one entry per corner; no setup/hold data cuts.",
                "Inspect both corners and all ten timing types; tool exit or preparation success is not acceptance.",
                "External IO timing, CDC/RDC protocol and hardware validation remain separate."]}
    output.mkdir(parents=True, exist_ok=True)
    (output / "repair").mkdir()
    (output / "report").mkdir()
    payloads = {"input.adf": data, "dummy.v": dummy,
                "scope-reset.fdc": fdc.encode("ascii"), "repair.tcl": repair.encode("ascii"), "report.tcl": report.encode("ascii")}
    for name, content in payloads.items():
        with (output / name).open("xb") as stream:
            stream.write(content)
    with (output / "plan.json").open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(plan, stream, indent=2, ensure_ascii=False)
        stream.write("\n")
    return plan


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-adf", required=True, type=Path)
    parser.add_argument("--native-evidence", required=True, type=Path)
    parser.add_argument("--entry-audit", required=True, type=Path)
    parser.add_argument("--native-query-log", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--repo-alias", default="P:/")
    parser.add_argument("--pds-shell", default="D:/pango/PDS_2023.2/bin/pds_shell.exe")
    args = parser.parse_args(argv)
    try:
        plan = prepare(PROJECT, args.source_adf, args.native_evidence, args.entry_audit,
                       args.native_query_log, args.out_dir, repo_alias=args.repo_alias, pds_shell=args.pds_shell)
    except (ValueError, OSError, KeyError, UnicodeError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    print(json.dumps({"PreparedOnly": True, "EDAExecuted": False, "TimingAccepted": False,
                      "SourceADFSHA256": plan["SourceADFSHA256"], "Plan": str(args.out_dir / "plan.json")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
