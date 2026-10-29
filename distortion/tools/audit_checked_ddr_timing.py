"""Audit only the checked-1029 route repair and exact reset-scope candidate.

CPU audit of native evidence; no EDA, hardware, caller-selected ADF or hash.
The hold-only report is the baseline, so every retained timing row must stay
identical, including the new HDMI configuration/reset clocks and both hold rows.
"""
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
import argparse
import json
import re

import audit_ddr_final_timing as native
import audit_fresh_ddr_timing as fresh
import audit_ddr_entry_reset_netlist as entry
import audit_hdmi30_build as common
import prepare_board1080_checked as profile
import prepare_ddr_timing_repair as scopes
import prepare_ddr_native_reset_scope as pins

ROOT = Path(__file__).resolve().parents[1]
ORIGINAL = "c411d60712ba01ea9356553a69516d316aa68dc8fa67505f7b962d610dec4029"
HOLD = "eb4a20abf54c135677dda7075b93144aefb98dc7c953f785bdf4ef077d91eee2"
FINAL = "857bf183e52cbd96fb9f378f5087f4c55aba66b22f8488822b7e2dc92450c142"
RECEIPTS = {
    "full-build": "abaedd37ba2caa755f46a1aadbc8f19993eaabc329ebd4fa5ced182fd0fe87f7",
    "hold-route-only": "7ba4ad115c35d313a23f4ed647d60be7f914af19c8474719c2333cce1810110b",
    "entry-rdc": "56c899f624ec7897f3add6dffecbd1027118b4ad8b4ed589f5a199d8adf5ff13",
    "route-query": "958df18affe40d2af0a10df3a26de1e64b6eb656ff024c31b4145b4347ae1c97",
    "native-diagnostics": "c5ceb683dadff4d563084f3fa6a5b9563c1cec4100ef345eb772bdf90496c36d",
}
require, sha, read_json = native.require, native.sha, common.read_json
ARCH = "set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG676"
REPORT = "mpnr_report_timing -force_to_run -delay_type min_max -max_path 1000 -nworst 4 -report_exception TRUE"


def compare_summaries(baseline, candidate):
    """Pure check: only the seven exact reset clock-pair rows may disappear."""
    keys = {(c, k) for c in ("slow", "fast") for k in native.KINDS}
    require(set(baseline) == set(candidate) == keys, "all ten summary types required")
    reset_pairs = dict(native.recovery.PAIRS)
    reset_pairs[native.ENTRY_PAIR] = 1
    totals, preserved, removed, hdmi = {}, 0, [], []
    for key in sorted(keys):
        corner, kind = key
        old, now = baseline[key], candidate[key]
        cuts = set(reset_pairs) if kind in ("recovery", "removal") else set()
        require(cuts <= set(old), "baseline reset group missing")
        require(now and set(now) == set(old) - cuts, "unexpected added/removed summary row")
        for pair in cuts:
            require(old[pair]["TotalChecks"] == reset_pairs[pair], "reset group count differs")
            removed.append({"Corner": corner, "Kind": kind, "Clocks": list(pair), "Before": old[pair]})
        for pair, row in now.items():
            require(row == old[pair], "retained timing row changed: " + str((key, pair)))
            require(row["FailingChecks"] == 0 and row["WorstSlackNS"] >= 0
                    and row["TotalNegativeSlackNS"] == 0, "remaining native timing failure")
            preserved += 1
            if any("cfg_clk" in clock for clock in pair):
                hdmi.append({"Corner": corner, "Kind": kind, "Clocks": list(pair), **row})
        totals[corner + "_" + kind] = {
            "WorstSlackNS": min(row["WorstSlackNS"] for row in now.values()),
            "FailingChecks": sum(row["FailingChecks"] for row in now.values()),
            "TimedChecks": sum(row["TotalChecks"] for row in now.values()),
            "RemovedResetChecks": sum(old[pair]["TotalChecks"] for pair in cuts)}
    require(hdmi, "checked HDMI configuration timing evidence absent")
    return totals, preserved, removed, hdmi


def expected_script(directory, kind):
    alias = "P:/distortion/build/board1080-timing/" + directory
    start = [ARCH, "add_design {" + alias + "/dummy.v}", "if {[info script] ne {}} {",
             "    mpnr -input {" + alias + "/input.adf}"]
    if kind == "scope":
        body = ["    puts {CHECKED_EXACT_RESET_SCOPE_BEGIN}",
                "    source {" + alias + "/scope-reset.fdc}", "    save_adif",
                "    puts {CHECKED_EXACT_RESET_SAVED_PENDING_INDEPENDENT_STA}"]
    else:
        label = "HOLD" if kind == "hold" else "FINAL"
        body = ["    puts {CHECKED_" + label + "_RELOAD_ROUTE}",
                "    show -design_net {_N55}", "    show -design_net {_N63}",
                "    " + REPORT, "    puts {CHECKED_" + label + "_INDEPENDENT_STA_COMPLETE}"]
    return "\n".join(start + body + ["    flush stdout", "}"]) + "\n"


def check_execution(work, kind, watched):
    """Bind local execution records; these are not remote attestations."""
    script = "scope.tcl" if kind == "scope" else "query.tcl"
    project = {"scope": "checked_reset_scope", "hold": "checked_hold_sta", "final": "checked_final_sta"}[kind]
    alias = "P:/distortion/build/board1080-timing/" + work.name
    start = read_json(common.bind(watched, work / "execution-start.json"))
    end = read_json(common.bind(watched, work / "execution-complete.json"))
    require(start["Executable"].replace("\\", "/") == "D:/pango/PDS_2023.2/bin/pds_shell.exe", "unexpected executable")
    common.bind(watched, start["Executable"])
    require(start["Arguments"] == ["-file", alias + "/" + script, "-work_dir", alias,
                                   "-project_name", project], "native invocation differs")
    require(start.get("HardwareAccessed") is False and end.get("HardwareAccessed") is False,
            "hardware scope missing")
    require(type(end.get("NativeReturnCode")) is int and end["NativeReturnCode"] == 0,
            "native execution failed")
    require(start["StartedUTC"] == end["StartedUTC"], "execution start mismatch")
    begin, finish = common.stamp(start["StartedUTC"]), common.stamp(end["EndedUTC"])
    require(begin < finish, "execution interval invalid")
    common.bind(watched, work / script)
    require((work / script).read_text(encoding="utf-8-sig") == expected_script(work.name, kind),
            "unexpected executed Tcl")
    marker = "CHECKED_EXACT_RESET_SAVED_PENDING_INDEPENDENT_STA" if kind == "scope" else (
        "CHECKED_" + ("HOLD" if kind == "hold" else "FINAL") + "_INDEPENDENT_STA_COMPLETE")
    for filename in ("native-console.log", "run.log"):
        path = common.bind(watched, work / filename)
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        require(begin - 2 <= path.stat().st_mtime <= finish + 2, "stale native log")
        require(not re.search(r"(?m)^(?:E:|F:|ERROR\b|FATAL\b)", text), "native fatal diagnostic")
        if filename == "native-console.log":
            require(text.splitlines().count(marker) == 1, "native completion marker missing/duplicate")
        else:
            require("#Build: Fabric Compiler 2023.2-SP3, Build 154097," in text, "native version differs")
        commands = re.findall(r"^Executing : (.+?) successfully\.$", text, re.MULTILINE)
        names = Counter(command.split()[0] for command in commands)
        wanted = {"set_arch": 1, "add_design": 1, "mpnr": 1}
        wanted.update({"get_pins": 10, "set_false_path": 5, "save_adif": 1} if kind == "scope"
                      else {"show": 2, "mpnr_report_timing": 1})
        require(names == wanted, "unexpected/missing native commands")
        require(commands[:3] == [ARCH, "add_design " + alias + "/dummy.v", "mpnr -input " + alias + "/input.adf"],
                "native load command/order changed")
        require(commands[-1] == ("save_adif" if kind == "scope" else REPORT), "native completion order changed")
    return {"Start": start, "Complete": end, "Begin": begin, "End": finish}


def audit(project=ROOT):
    project = Path(project).resolve()
    base = project / "build/board1080-timing"
    hold, scope, final = [base / name for name in (
        "checked-hold-sta-1029-a", "checked-reset-1029-a", "checked-final-sta-1029-a")]
    watched = {}

    def bind(path, digest=None):
        path = Path(path).resolve()
        if path in watched:
            require(digest is None or watched[path] == digest, "inconsistent evidence hash")
            return path
        return common.bind(watched, path, digest)

    def bind_map(values, root=project):
        require(isinstance(values, dict) and values, "empty evidence binding")
        for filename, digest in values.items():
            bind(root / filename, digest)

    receipts = {}
    for name, digest in RECEIPTS.items():
        path = bind(project / "results" / ("board1080-checked-" + name + "-20261029.json"), digest)
        receipts[name] = read_json(path)
        if "EvidenceSHA256" in receipts[name]:
            bind_map(receipts[name]["EvidenceSHA256"])
    full, route, rdc = [receipts[k] for k in ("full-build", "hold-route-only", "entry-rdc")]
    roles = profile.validate_profile(project)
    closure = profile.expected_inputs(project, roles)
    require(full["ProcessSucceeded"] is True and full["InputSHA256"] == closure,
            "original checked source closure differs")
    bind_map(closure)
    require(route["AuditPassed"] and route["DataHoldRepairVerified"] and route["AddedTimingExceptions"] is False,
            "hold-only baseline was not independently admitted")
    require(route["SavedCandidateADF"]["SHA256"] == HOLD and route["OriginalSourceADF"]["SHA256"] == ORIGINAL,
            "hold-only receipt candidate differs")
    require(rdc["SourceADF"]["SHA256"] == ORIGINAL and rdc["ExportProvenanceReceiptBound"] is True,
            "entry netlist source provenance differs")
    bind(rdc["Input"]["Path"], rdc["Input"]["SHA256"])
    replay = entry.audit_text(Path(rdc["Input"]["Path"]).read_text(encoding="utf-8-sig"))
    require(all(rdc.get(k) == v for k, v in replay.items()), "entry connectivity replay differs")
    require(rdc["SynchronizedOutputResetTree"]["OnlyResetLoads"] is True, "entry output has non-reset consumers")
    bind(base / "checked-1029-a/place_route/board1080_top_pnr.adf", ORIGINAL)
    bind(base / "checked-hold-1029-a/input.adf", HOLD)
    bind(hold / "input.adf", HOLD)
    bind(scope / "input.adf", FINAL)
    bind(final / "input.adf", FINAL)

    plans = []
    for directory, filename, schema, source, digest in (
        (hold, "query-plan.json", "checked-route-only-independent-sta-v1", base / "checked-hold-1029-a/input.adf", HOLD),
        (scope, "scope-plan.json", "checked-reset-scope-trial-v1", hold / "input.adf", HOLD),
        (final, "query-plan.json", "checked-reset-independent-sta-v1", scope / "input.adf", FINAL)):
        plan = read_json(bind(directory / filename))
        require(plan["Schema"] == schema and Path(plan["SourceADF"]).resolve() == source.resolve()
                and plan["SourceADFSHA256"] == digest and plan["OriginalADFSHA256"] == ORIGINAL,
                "candidate plan identity mismatch")
        require(plan.get("HardwareAccessed") is False, "plan hardware scope missing")
        bind_map(plan["InputSHA256"])
        bind_map(plan["PreparedFileSHA256"])
        require(all(plan["InputSHA256"].get(str((project / p).resolve())) == value for p, value in closure.items()),
                "plan does not bind complete current source closure")
        required = [directory / "dummy.v", directory / ("scope.tcl" if directory == scope else "query.tcl")]
        required += [directory / "scope-reset.fdc"] if directory == scope else [directory / "input.adf"]
        require(set(plan["PreparedFileSHA256"]) == {str(p.resolve()) for p in required}, "prepared-file set differs")
        plans.append(plan)
    executions = [check_execution(path, kind, watched) for path, kind in ((hold, "hold"), (scope, "scope"), (final, "final"))]
    require(executions[0]["End"] < executions[1]["Begin"] < executions[1]["End"] < executions[2]["Begin"],
            "independent execution order differs")
    require(executions[1]["Begin"] - 2 <= (scope / "input.adf").stat().st_mtime <= executions[1]["End"] + 2,
            "saved scoped ADF is stale")

    report_paths = [d / "board1080_top.rtr" for d in (hold, final)]
    tables, clocks = [], []
    for directory, execution, report in zip((hold, final), (executions[0], executions[2]), report_paths):
        for name in ("board1080_top.rtr", "board1080_top_exception.rtr"):
            path = bind(directory / name)
            require(execution["Begin"] - 2 <= path.stat().st_mtime <= execution["End"] + 2, "stale native timing artifact")
            with path.open(encoding="utf-8-sig", errors="replace") as stream:
                header = "".join(next(stream) for _ in range(15))
            if name == "board1080_top.rtr":
                require("version 2023.2-SP3 <build 154097>" in header and "PG2L100H" in header
                        and "FBG676" in header and "board1080_top" in header, "native report identity differs")
            else:
                # PDS's exception file has no device/version banner. Its own
                # path, time and content are bound to this completed reload.
                require("| Exception type  :" in header and "| Slow Corner" in header,
                        "native exception report header absent")
        with report.open(encoding="utf-8-sig", errors="replace") as stream:
            table, clock = native.parse_summaries(stream)
        tables.append(table)
        clocks.append(clock)
    require(clocks[0] == clocks[1], "native clock definitions/loads changed")
    totals, preserved, removed, hdmi = compare_summaries(*tables)
    expected, inventory, entries = fresh.expected_paths(report_paths[0])
    groups = defaultdict(set)
    for row in expected["slow"]:
        if row[0] != native.ENTRY_SOURCE:
            groups[row[0]].add(row[1])
    query_log = bind(base / "checked-route-1029-a/native-console.log")
    records = pins.parse_native_matches(query_log)
    require(records == receipts["route-query"]["NativePinRecords"], "native exact pin query changed")
    fdc, queries = scopes.make_scopes(groups, records)
    # This fixed scope was serialized by Windows write_text with CRLF.
    # Require those exact bytes; do not normalize arbitrary whitespace or Tcl.
    require((scope / "scope-reset.fdc").read_bytes() == fdc.replace("\n", "\r\n").encode("utf-8")
            and plans[1]["ExactQueries"] == queries,
            "executed reset scope differs from exact native pin inventory")
    for value in entries:
        summary = tables[0][(value["Corner"], "recovery")][native.ENTRY_PAIR]
        slack = fresh.variants.number(value["SlackNS"])
        require(summary["TotalChecks"] == 1 and summary["FailingChecks"] == int(value["SlackState"] == "VIOLATED")
                and fresh.variants.number(summary["WorstSlackNS"]) == slack
                and fresh.variants.number(summary["TotalNegativeSlackNS"]) == min(0, slack), "entry summary/path differs")
    sections = []
    for directory in (hold, final):
        with (directory / "board1080_top_exception.rtr").open(encoding="utf-8-sig", errors="replace") as stream:
            sections.append(native.parse_false_paths(stream))
    require(all(not values for values in sections[0].values()), "hold-only baseline already contains exceptions")
    counts = native.validate_exception_sets(sections[1], expected)
    warnings = native.io_warnings(hold / "native-console.log")
    require(warnings == native.io_warnings(final / "native-console.log"), "external IO warning set changed")
    require(("4086", "hd_scl") in warnings, "new SCL input coverage warning disappeared")
    tools = [Path(__file__), Path(native.__file__), Path(fresh.__file__), Path(entry.__file__),
             Path(scopes.__file__), Path(pins.__file__), Path(fresh.variants.__file__), Path(native.recovery.__file__)]
    for path in tools:
        bind(path)
    require(all(sha(path) == digest for path, digest in watched.items()), "evidence drift during audit")
    return {"Schema": "board1080-checked-ddr-final-native-audit-v1",
            "RecordedUTC": datetime.now(timezone.utc).isoformat(), "AuditPassed": True,
            "AllReportedNativeTimingChecksMet": True, "AllTenTimingTypesAndCornersChecked": True,
            "HoldOnlyBaselineSHA256": HOLD, "OriginalSourceADFSHA256": ORIGINAL,
            "FinalRoutedADF": {"Path": str(final / "input.adf"), "SHA256": FINAL},
            "IndependentExecutionChainVerified": True, "Executions": executions,
            "ExactExceptionPathEffectsVerified": True, "ExactNativePinQueries": queries,
            "InternalResetChecksPerCorner": 244, "EntryResetChecksPerCorner": 1,
            "BaselineInternalNativeVariantsPerCorner": 251, "FalsePathCounts": counts,
            "NoDataSetupOrHoldFalsePaths": True, "NativeClockDefinitionsAndLoadsUnchanged": True,
            "AllRetainedSummaryRowsUnchanged": True, "RetainedSummaryRows": preserved,
            "RemovedResetSummaryRows": removed, "HDMIConfigurationTimingRowsUnchanged": hdmi,
            "CornerSummaries": totals, "BaselineRecoveryVariantEvidence": inventory,
            "BaselineEntryPaths": entries, "EntryConnectivityReplayMatched": True,
            "SourceClosureCount": len(closure), "EvidenceSHA256": {str(p): h for p, h in watched.items()},
            "ExternalIOWarningEvidence": {"Identical": True, "UniqueInputPorts": sum(k == "4086" for k, _ in warnings),
                "UniqueOutputPorts": sum(k == "4087" for k, _ in warnings),
                "Ports": [{"Code": k, "Port": p} for k, p in sorted(warnings)]},
            "TimingAccepted": False, "PhysicalTimingReady": False, "HardwareReleaseAllowed": False,
            "HardwareAccessed": False, "BitstreamRequested": False, "ExternalIOAccepted": False,
            "Limitations": ["Only this fixed checked candidate and its local execution/hash chain are admitted; local receipts are not cryptographic execution attestations.",
                "Reset exceptions are exact scoped exclusions, not positive-slack reset recovery/removal measurements or analog reset safety acceptance.",
                "MPNR reload produced native RTR and exception reports; no new XML report or routed pin report is claimed.",
                "External IO AC budgets, CDC/skew, pullups, DDR training and hardware stability remain unaccepted."]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    result = audit()
    serialized = json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    with args.output.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(serialized)
    print(json.dumps({"AuditPassed": True, "AllReportedNativeTimingChecksMet": True,
                      "HardwareReleaseAllowed": False, "RetainedSummaryRows": result["RetainedSummaryRows"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
