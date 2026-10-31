"""Compare the native two-corner DDR candidate against its strict baseline.

Only a single data hold clock-pair improvement and the 244 exact internal reset
checks plus the separately audited entry RDC exception are allowed. This is a
native report audit, not external IO/CDC or hardware sign-off.
"""
from pathlib import Path
from collections import Counter
from datetime import datetime, timezone
import argparse
import hashlib
import json
import math
import re

import prepare_ddr_native_recovery_constraints as recovery


ENTRY_SOURCE = "power_ready/opit_0_inv_L6Q_perm/CLK"
ENTRY_TARGET = recovery.IP + "u_ddrphy_rst_seq_rstn_sync/sig_async_r1[0]/opit_0_srl/RS"
ENTRY_PAIR = ("board27", "rst_clk")
HOLD_PAIR = ("ddrphy_sysclk", "phy_dq_sysclk_1")
KINDS = ("setup", "hold", "recovery", "removal", "mpw")
HEADER = re.compile(r"^(Setup|Hold|Recovery|Removal|Minimum Pulse Width) Summary\((Slow|Fast) Corner\):\s*$")
NUM = r"[-+]?\d+(?:\.\d+)?"
ROW = re.compile(r"^\s*(\S+)\s+(\S+)\s+(" + NUM + r")\s+(" + NUM + r")\s+(\d+)\s+(\d+)\s*$")
MPW_ROW = re.compile(r"^\s*(\S+)\s+(" + NUM + r")\s+(" + NUM + r")\s+(\d+)\s+(\d+)\s*$")
EX_HEADER = re.compile(r"^\| Exception type\s*:\s*(\S+)\s*$")
EX_KIND = re.compile(r"set_false_path\((setup|hold|recovery|removal)\)\Z")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    return recovery.sha(path)


def normalize(line):
    return " ".join(line.split())


def parse_summaries(lines):
    """Stop before detailed paths so net-delay rows cannot become MPW rows."""
    tables, clocks, current = {}, [], None
    in_clocks = False
    for line in lines:
        if line.startswith("Startpoint"):
            break
        if line.strip() == "Clock Summary:":
            in_clocks = True
            continue
        if in_clocks:
            if line.strip().startswith("Clock Groups:"):
                in_clocks = False
            elif line.strip() and not set(line.strip()) <= set("-=*"):
                clocks.append(normalize(line))
        match = HEADER.fullmatch(line.rstrip("\r\n"))
        if match:
            kind = {"Minimum Pulse Width": "mpw"}.get(match[1], match[1].lower())
            current = (match[2].lower(), kind)
            require(current not in tables, "duplicate native summary table")
            tables[current] = {}
            continue
        if current is None:
            continue
        match = (MPW_ROW if current[1] == "mpw" else ROW).fullmatch(line)
        if not match:
            continue
        values = list(match.groups())
        names = tuple(values[:1] if current[1] == "mpw" else values[:2])
        raw = values[1:] if current[1] == "mpw" else values[2:]
        row = {"WorstSlackNS": float(raw[0]), "TotalNegativeSlackNS": float(raw[1]),
               "FailingChecks": int(raw[2]), "TotalChecks": int(raw[3])}
        require(all(math.isfinite(row[k]) for k in ("WorstSlackNS", "TotalNegativeSlackNS")),
                "non-finite summary slack")
        require(names not in tables[current], "duplicate native summary row")
        tables[current][names] = row
    require(set(tables) == {(c, k) for c in ("slow", "fast") for k in KINDS},
            "all ten native summary tables are required")
    require(all(tables.values()) and clocks, "native summaries or clocks are empty")
    return tables, clocks


def path_record(lines, *, expected_kind=None):
    text = "".join(lines)
    def exactly(pattern, name):
        values = re.findall(pattern, text, re.MULTILINE)
        require(len(values) == 1, "missing or ambiguous path " + name)
        return values[0]
    source = exactly(r"^Startpoint\s*:\s*(\S+)\s*$", "source")
    target = exactly(r"^Endpoint\s*:\s*(\S+)\s*$", "endpoint")
    group = exactly(r"^Path Group\s*:\s*(\S+)\s*$", "group")
    typ = exactly(r"^Path Type\s*:\s*(max|min) \((slow|fast) corner\)\s*$", "type")
    cls = exactly(r"^Path Class\s*:\s*(.+?)\s*$", "class")
    clocks = re.findall(r"^ Clock (\S+) \((rising|falling) edge\)", text, re.MULTILINE)
    require(len(clocks) == 2, "exception path must contain both clock edges")
    require(group == clocks[1][0], "path group differs from capture clock")
    if expected_kind:
        require(typ[0] == ("max" if expected_kind in ("setup", "recovery") else "min"),
                "exception type and min/max path differ")
        require(cls == "false timing path" and "Timing Exception  :  False Path" in text,
                "false-path report has a non-false path")
    value = {"Source": source, "Endpoint": target, "LaunchClock": clocks[0][0],
            "CaptureClock": clocks[1][0], "LaunchEdge": clocks[0][1], "CaptureEdge": clocks[1][1],
            "Corner": typ[1], "PathClass": cls}
    if expected_kind:
        # -nworst 4 reports both source-Q transitions for an otherwise identical
        # clock/pin path. They are distinct native paths, not duplicate checks.
        transitions = re.findall(r"^ \S+\s+tco\s+" + NUM + r"\s+" + NUM
                                 + r"\s+([rf])\s+\S+", text, re.MULTILINE)
        require(len(transitions) == 1, "false path needs one explicit source data transition")
        value["LaunchDataTransition"] = transitions[0]
        # PDS can also report min/max capture-delay variants with identical
        # clock edges and Q transition. Retain their actual path bodies, while
        # rejecting a literal duplicated native record.
        body = []
        for line in lines:
            if line.strip() and not set(line.strip()) <= set("=-*"):
                body.append(normalize(line))
            if line.startswith(" Slack"):
                break
        value["NativePathSignature"] = hashlib.sha256("\n".join(body).encode("utf-8")).hexdigest()
    return value


def path_identity(path):
    return tuple(path[k] for k in ("Source", "Endpoint", "LaunchClock", "CaptureClock", "LaunchEdge", "CaptureEdge"))


def expected_paths(report):
    with Path(report).open(encoding="utf-8-sig", errors="replace") as stream:
        paths, summaries = recovery.parse_lines(stream)
    proof, _ = recovery.build(paths, summaries, include_cpd=True)
    expected = {corner: {path_identity(p) for p in paths if p["Corner"] == corner}
                for corner in ("slow", "fast")}
    # Entry edges are read from the strict native report, not guessed.
    entries, block = [], []
    def finish():
        if block and block[0].split(":", 1)[1].strip() == ENTRY_SOURCE:
            text = "".join(block)
            if re.search(r"(?m)^Endpoint\s*:\s*" + re.escape(ENTRY_TARGET) + r"\s*$", text) and re.search(r"(?m)^ Recovery time\s", text):
                value = path_record(block)
                require(value["PathClass"] == "async timing path", "entry is not an asynchronous reset check")
                require((value["LaunchClock"], value["CaptureClock"]) == ENTRY_PAIR, "entry clock pair changed")
                entries.append(value)
    with Path(report).open(encoding="utf-8-sig", errors="replace") as stream:
        for line in stream:
            if line.startswith("Startpoint"):
                finish()
                block = [line]
            elif block:
                block.append(line)
    finish()
    require(Counter(p["Corner"] for p in entries) == {"slow": 1, "fast": 1},
            "one exact entry recovery path per corner required")
    for value in entries:
        expected[value["Corner"]].add(path_identity(value))
    require(all(len(v) == 245 for v in expected.values()), "expected 244 internal plus one entry check")
    return expected, proof


def parse_false_paths(lines):
    sections, section, pending_type, block = {}, None, None, []
    def finish():
        if block and section is not None:
            value = path_record(block, expected_kind=section[1])
            require(value["Corner"] == section[0], "exception path corner differs from section")
            sections[section].append(value)
    for line in lines:
        header = EX_HEADER.fullmatch(line.rstrip("\r\n"))
        if header:
            finish()
            block, section = [], None
            match = EX_KIND.fullmatch(header[1])
            pending_type = match[1] if match else None
            continue
        if pending_type:
            corner = re.fullmatch(r"\| (Slow|Fast) Corner\s*", line)
            if corner:
                section = (corner[1].lower(), pending_type)
                require(section not in sections, "duplicate false-path section")
                sections[section] = []
                pending_type = None
                continue
        if section is None:
            continue
        if line.startswith("Startpoint"):
            finish()
            block = [line]
        elif block:
            block.append(line)
    finish()
    require(set(sections) == {(c, k) for c in ("slow", "fast")
                             for k in ("setup", "hold", "recovery", "removal")},
            "all eight false-path exception sections required")
    return sections


def validate_exception_sets(sections, expected):
    counts = {}
    for (corner, kind), values in sections.items():
        actual = [path_identity(p) for p in values]
        variants = [identity + (p["LaunchDataTransition"], p["NativePathSignature"])
                    for identity, p in zip(actual, values)]
        require(all(p["LaunchDataTransition"] in ("r", "f") for p in values),
                "invalid source data transition")
        require(len(set(variants)) == len(variants), "duplicate exception path identity")
        # A false path has no critical edge; the native reporter can choose a
        # different edge representative than the timed worst path. The check
        # identity is exact pins + launch/capture clocks. Retain every actual
        # edge variant, but do not confuse them with additional reset checks.
        actual_checks = {p[:4] for p in actual}
        wanted = set() if kind in ("setup", "hold") else {p[:4] for p in expected[corner]}
        require(actual_checks == wanted,
                f"unexpected or missing {corner} {kind} exception paths: "
                f"extra={len(actual_checks-wanted)} missing={len(wanted-actual_checks)}")
        allowed_launch = {p[:4]: p[4] for p in expected[corner]}
        require(all(p[4] == allowed_launch[p[:4]] and p[5] in ("rising", "falling") for p in actual),
                "exception launch edge differs from its actual source clock pin")
        counts[corner + "_" + kind] = {
            "UniqueClockAndPinChecks": len(actual_checks), "ReportedPathVariants": len(actual),
            "DistinctClockEdgeVariants": len(set(actual)), "DistinctNativePathVariants": len(set(variants))}
    return counts


def compare_summaries(baseline, candidate):
    changes, totals = [], {}
    removed_pairs = set(recovery.PAIRS) | {ENTRY_PAIR}
    for key, old_rows in baseline.items():
        corner, kind = key
        now = candidate[key]
        allowed_removed = removed_pairs if kind in ("recovery", "removal") else set()
        expected_rows = set(old_rows) - allowed_removed
        require(set(now) == expected_rows, "unexpected added/removed native summary row: " + str(key))
        for pair in expected_rows:
            before, after = old_rows[pair], now[pair]
            if kind == "hold" and pair == HOLD_PAIR:
                require(before["FailingChecks"] == 1 and before["WorstSlackNS"] < 0,
                        "baseline must have the known single PHY hold failure")
                require(after["FailingChecks"] == 0 and after["WorstSlackNS"] >= 0 and
                        after["TotalChecks"] == before["TotalChecks"],
                        "PHY hold improvement is not a preserved passing check")
                changes.append({"Corner": corner, "Check": kind, "ClockPair": list(pair),
                                "Before": before, "After": after})
            else:
                require(after == before, "unrelated timing row changed: " + str((key, pair)))
        if allowed_removed:
            require(all(old_rows[p]["TotalChecks"] == (1 if p == ENTRY_PAIR else recovery.PAIRS[p])
                        for p in allowed_removed), "removed reset group count differs from exact evidence")
        require(all(r["FailingChecks"] == 0 and r["WorstSlackNS"] >= 0 and
                    r["TotalNegativeSlackNS"] == 0.0 for r in now.values()),
                "candidate still has a native timing failure")
        totals[corner + "_" + kind] = {
            "WorstSlackNS": min(r["WorstSlackNS"] for r in now.values()),
            "FailingChecks": sum(r["FailingChecks"] for r in now.values()),
            "TimedChecks": sum(r["TotalChecks"] for r in now.values()),
            "RemovedResetChecks": sum(old_rows[p]["TotalChecks"] for p in allowed_removed)}
    require(len(changes) == 2, "both corner hold comparisons required")
    return changes, totals


def io_warnings(path):
    values = set()
    pattern = re.compile(r"^W: Timing-(4086|4087): Port '([^']+)' is not constrained,")
    with Path(path).open(encoding="utf-8-sig", errors="replace") as stream:
        for line in stream:
            match = pattern.match(line)
            if match:
                values.add((match[1], match[2]))
    require(values, "native missing-IO warning evidence is empty")
    return values


def audit(baseline_report, baseline_exceptions, candidate_report, candidate_exceptions,
          final_adf, expected_adf_sha256, *, baseline_log=None, candidate_log=None):
    require(re.fullmatch(r"[0-9a-f]{64}", expected_adf_sha256) is not None,
            "explicit final ADF SHA256 required")
    final_adf = Path(final_adf)
    require(final_adf.suffix.lower() == ".adf" and sha(final_adf) == expected_adf_sha256,
            "final ADF hash mismatch")
    files = [baseline_report, baseline_exceptions, candidate_report, candidate_exceptions, final_adf]
    before = {str(Path(p).resolve()): sha(p) for p in files}
    with Path(baseline_report).open(encoding="utf-8-sig", errors="replace") as stream:
        base, base_clocks = parse_summaries(stream)
    with Path(candidate_report).open(encoding="utf-8-sig", errors="replace") as stream:
        current, current_clocks = parse_summaries(stream)
    require(base_clocks == current_clocks, "native clock definitions/loads changed")
    changes, totals = compare_summaries(base, current)
    expected, inventory = expected_paths(baseline_report)
    with Path(baseline_exceptions).open(encoding="utf-8-sig", errors="replace") as stream:
        old_exceptions = parse_false_paths(stream)
    require(all(not values for values in old_exceptions.values()), "baseline already has false-path cuts")
    with Path(candidate_exceptions).open(encoding="utf-8-sig", errors="replace") as stream:
        actual = parse_false_paths(stream)
    counts = validate_exception_sets(actual, expected)
    require((baseline_log is None) == (candidate_log is None), "both IO logs are required together")
    io = None
    if baseline_log is not None:
        files += [baseline_log, candidate_log]
        for p in (baseline_log, candidate_log):
            before[str(Path(p).resolve())] = sha(p)
        warnings = io_warnings(baseline_log)
        require(warnings == io_warnings(candidate_log), "missing external IO warning set changed")
        io = {"Identical": True, "UniqueInputPorts": sum(k == "4086" for k, _ in warnings),
              "UniqueOutputPorts": sum(k == "4087" for k, _ in warnings),
              "Ports": [{"Code": k, "Port": p} for k, p in sorted(warnings)]}
    require(all(sha(p) == digest for p, digest in before.items()), "input changed during audit")
    return {"Schema": "board1080-ddr-final-native-audit-v1", "RecordedUTC": datetime.now(timezone.utc).isoformat(),
            "AuditPassed": True, "AllReportedNativeTimingChecksMet": True,
            "AllTenTimingTypesAndCornersChecked": True, "NativeClockDefinitionsUnchanged": True,
            "ExactExceptionPathEffectsVerified": True, "InternalResetChecksPerCorner": 244,
            "EntryResetChecksPerCorner": 1, "FalsePathCounts": counts,
            "NoDataSetupOrHoldFalsePaths": True, "NativeRecoveryInventoryPairs": inventory["FullUniqueSourceEndpointPairs"],
            "HoldPairImprovements": changes, "CornerSummaries": totals,
            "AllOtherSummaryRowsUnchanged": True, "ExternalIOWarningEvidence": io,
            "InputsSHA256": before, "ToolSHA256": sha(__file__),
            "FinalRoutedADF": {"Path": str(final_adf.resolve()), "SHA256": expected_adf_sha256},
            "HardwareAccessed": False, "BitstreamRequested": False,
            "ExternalIOAccepted": False, "CDCProtocolAndSkewAccepted": False,
            "HardwareReleaseAllowed": False, "PhysicalTimingReady": False,
            "Limitations": ["The report audit does not validate board IO AC budgets, analog MTBF, CDC bus skew, DDR training hardware, or board stability.",
                            "Internal reset and entry RDC checks are intentionally scoped exceptions; they are not positive-slack recovery paths.",
                            "Exception checks are identified by exact source pin, endpoint pin and both clocks; a false path may use a different capture-edge representative than a timed worst path."]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ("baseline-report", "baseline-exceptions", "candidate-report", "candidate-exceptions", "final-adf", "output"):
        parser.add_argument("--" + flag, type=Path, required=True)
    parser.add_argument("--expected-adf-sha256", required=True)
    parser.add_argument("--baseline-log", type=Path)
    parser.add_argument("--candidate-log", type=Path)
    args = parser.parse_args()
    result = audit(args.baseline_report, args.baseline_exceptions, args.candidate_report,
                   args.candidate_exceptions, args.final_adf, args.expected_adf_sha256,
                   baseline_log=args.baseline_log, candidate_log=args.candidate_log)
    with args.output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(result, stream, indent=2, ensure_ascii=False)
        stream.write("\n")
    print(json.dumps({"AuditPassed": True, "NativeTimingMet": True,
                      "ExactExceptionPathEffectsVerified": True, "HardwareReleaseAllowed": False}))


if __name__ == "__main__":
    main()
