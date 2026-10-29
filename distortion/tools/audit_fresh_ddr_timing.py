"""Audit a fresh board1080 repair with all 251 native reset variants retained.

The historical 244-record auditor stays frozen. This fresh profile first proves
the seven dual-capture-edge records against native summaries, then compares the
same exact 245 logical IP/entry checks with the candidate exception report.
This is a CPU report audit, not reset safety, board IO or hardware acceptance.
"""
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import argparse
import hashlib
import json
import re

import audit_ddr_final_timing as native
import audit_ddr_recovery_variants as variants


require = native.require
sha = native.sha
# This auditor admits only the independently executed fresh repair profile.
FINAL_ADF_SHA256 = "b7ee4ac251b5d97c6887ef1fd7aeacf22d8a6ce93be821ca4255823f03c74f5c"


def entry_paths(report):
    """Read the exact entry checks and preserve their native provenance."""
    entries, block, start_line = [], [], 0

    def finish():
        if not block or block[0].split(":", 1)[1].strip() != native.ENTRY_SOURCE:
            return
        text = "".join(block)
        if not re.search(r"(?m)^Endpoint\s*:\s*" + re.escape(native.ENTRY_TARGET) + r"\s*$", text):
            return
        if not re.search(r"(?m)^ Recovery time\s", text):
            return
        value = native.path_record(block)
        require(value["PathClass"] == "async timing path",
                "entry is not an asynchronous reset check")
        require(re.search(r"(?m)^Path Type\s*:\s*max \(" + value["Corner"] + r" corner\)\s*$", text),
                "entry recovery must be a maximum path")
        require((value["LaunchClock"], value["CaptureClock"]) == native.ENTRY_PAIR,
                "entry clock pair changed")
        require(value["LaunchEdge"] == "rising", "entry launch clock edge changed")
        slack = re.findall(r"^ Slack \((MET|VIOLATED)\)\s+(" + native.NUM + r")\s*$", text, re.MULTILINE)
        transition = re.findall(r"^ \S+\s+tco\s+" + native.NUM + r"\s+" + native.NUM
                                + r"\s+([rf])\s+\S+\s*$", text, re.MULTILINE)
        require(len(slack) == len(transition) == 1, "entry needs one slack and source transition")
        state, raw = slack[0]
        require((state == "VIOLATED") == variants.negative(raw), "entry slack state contradicts value")
        body = []
        for line in block:
            if line.strip() and not set(line.strip()) <= set("=-*"):
                body.append(native.normalize(line))
            if line.startswith(" Slack"):
                break
        value.update(SlackState=state, SlackNS=raw, LaunchDataTransition=transition[0],
                     NativeReportLine=start_line,
                     NativePathSHA256=hashlib.sha256("\n".join(body).encode("utf-8")).hexdigest())
        entries.append(value)

    with Path(report).open(encoding="utf-8-sig", errors="replace") as stream:
        for lineno, line in enumerate(stream, 1):
            if line.startswith("Startpoint"):
                finish()
                block, start_line = [line], lineno
            elif block:
                block.append(line)
    finish()
    require(Counter(p["Corner"] for p in entries) == {"slow": 1, "fast": 1},
            "one exact entry recovery path per corner required")
    return entries


def expected_paths(report):
    """Retain edge variants while proving the exact logical check inventory."""
    inventory = variants.audit_file(report)
    expected = {}
    for corner in variants.CORNERS:
        rows = [row for check in inventory["Corners"][corner]["Checks"]
                for row in check["NativeVariants"]]
        expected[corner] = {native.path_identity(row) for row in rows}
        require(len(rows) == len(expected[corner]) == 251,
                "fresh baseline must retain all 251 distinct clock-edge variants")
    entries = entry_paths(report)
    for row in entries:
        expected[row["Corner"]].add(native.path_identity(row))
    require(all(len(rows) == 252 and len({row[:4] for row in rows}) == 245
                for rows in expected.values()), "expected 244 internal plus one entry logical check")
    require(sha(report) == inventory["Input"]["SHA256"], "baseline changed during entry audit")
    return expected, inventory, entries


def audit(baseline_report, baseline_exceptions, candidate_report, candidate_exceptions,
          final_adf, expected_adf_sha256, *, baseline_log=None, candidate_log=None):
    """Same call contract as the historical final audit, fresh profile only."""
    require(re.fullmatch(r"[0-9a-f]{64}", expected_adf_sha256) is not None,
            "explicit final ADF SHA256 required")
    require(expected_adf_sha256 == FINAL_ADF_SHA256,
            "final ADF hash mismatch: not the pinned fresh repaired candidate")
    final_adf = Path(final_adf).resolve()
    require(final_adf.suffix.lower() == ".adf" and sha(final_adf) == expected_adf_sha256,
            "final ADF hash mismatch")
    require((baseline_log is None) == (candidate_log is None), "both IO logs are required together")
    files = [baseline_report, baseline_exceptions, candidate_report, candidate_exceptions, final_adf]
    if baseline_log is not None:
        files += [baseline_log, candidate_log]
    before = {str(Path(p).resolve()): sha(p) for p in files}
    helpers = [Path(__file__), Path(native.__file__), Path(variants.__file__),
               Path(variants.recovery.__file__)]
    tools = {str(p.resolve()): sha(p) for p in helpers}
    with Path(baseline_report).open(encoding="utf-8-sig", errors="replace") as stream:
        baseline, baseline_clocks = native.parse_summaries(stream)
    with Path(candidate_report).open(encoding="utf-8-sig", errors="replace") as stream:
        candidate, candidate_clocks = native.parse_summaries(stream)
    require(baseline_clocks == candidate_clocks, "native clock definitions/loads changed")
    changes, totals = native.compare_summaries(baseline, candidate)
    expected, inventory, entries = expected_paths(baseline_report)
    require(inventory["Input"]["SHA256"] == before[str(Path(baseline_report).resolve())],
            "baseline changed before variant audit")
    for path in entries:
        summary = baseline[(path["Corner"], "recovery")][native.ENTRY_PAIR]
        slack = variants.number(path["SlackNS"])
        require(summary["TotalChecks"] == 1 and
                summary["FailingChecks"] == int(path["SlackState"] == "VIOLATED") and
                variants.number(summary["WorstSlackNS"]) == slack and
                variants.number(summary["TotalNegativeSlackNS"]) == min(0, slack),
                "entry path slack or failure count differs from native summary")
    with Path(baseline_exceptions).open(encoding="utf-8-sig", errors="replace") as stream:
        prior = native.parse_false_paths(stream)
    require(all(not rows for rows in prior.values()), "baseline already has false-path cuts")
    with Path(candidate_exceptions).open(encoding="utf-8-sig", errors="replace") as stream:
        actual = native.parse_false_paths(stream)
    counts = native.validate_exception_sets(actual, expected)
    io = None
    if baseline_log is not None:
        warnings = native.io_warnings(baseline_log)
        require(warnings == native.io_warnings(candidate_log), "missing external IO warning set changed")
        io = {"Identical": True, "UniqueInputPorts": sum(k == "4086" for k, _ in warnings),
              "UniqueOutputPorts": sum(k == "4087" for k, _ in warnings),
              "Ports": [{"Code": k, "Port": p} for k, p in sorted(warnings)]}
    require(all(sha(p) == digest for p, digest in before.items()), "input changed during audit")
    require(all(sha(p) == digest for p, digest in tools.items()), "audit implementation changed during audit")
    return {"Schema": "board1080-fresh-ddr-final-native-audit-v1",
            "RecordedUTC": datetime.now(timezone.utc).isoformat(),
            "AuditPassed": True, "AllReportedNativeTimingChecksMet": True,
            "AllTenTimingTypesAndCornersChecked": True, "NativeClockDefinitionsUnchanged": True,
            "ExactExceptionPathEffectsVerified": True, "InternalResetChecksPerCorner": 244,
            "EntryResetChecksPerCorner": 1, "BaselineInternalNativeVariantsPerCorner": 251,
            "FalsePathCounts": counts, "NoDataSetupOrHoldFalsePaths": True,
            "NativeRecoveryInventoryPairs": 126, "HoldPairImprovements": changes,
            "CornerSummaries": totals, "AllOtherSummaryRowsUnchanged": True,
            "BaselineRecoveryVariantEvidence": inventory, "BaselineEntryPaths": entries,
            "ExternalIOWarningEvidence": io, "InputsSHA256": before, "ToolsSHA256": tools,
            "FinalRoutedADF": {"Path": str(final_adf), "SHA256": expected_adf_sha256},
            "HardwareAccessed": False, "BitstreamRequested": False, "ExternalIOAccepted": False,
            "CDCProtocolAndSkewAccepted": False, "HardwareReleaseAllowed": False,
            "PhysicalTimingReady": False,
            "Limitations": [
                "This report audit does not establish reset safety, board IO AC budgets, analog MTBF, CDC bus skew, DDR training or board stability.",
                "Internal reset and entry RDC are intentionally scoped exceptions, not positive-slack recovery paths.",
                "All baseline edge variants are preserved; a false path may use a different capture-edge representative of the same exact pin-and-clock check."]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ("baseline-report", "baseline-exceptions", "candidate-report",
                 "candidate-exceptions", "final-adf", "output"):
        parser.add_argument("--" + flag, type=Path, required=True)
    parser.add_argument("--expected-adf-sha256", required=True)
    parser.add_argument("--baseline-log", type=Path)
    parser.add_argument("--candidate-log", type=Path)
    args = parser.parse_args(argv)
    result = audit(args.baseline_report, args.baseline_exceptions, args.candidate_report,
                   args.candidate_exceptions, args.final_adf, args.expected_adf_sha256,
                   baseline_log=args.baseline_log, candidate_log=args.candidate_log)
    with args.output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(result, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write("\n")
    print(json.dumps({"AuditPassed": True, "NativeTimingMet": True,
                      "ExactExceptionPathEffectsVerified": True, "HardwareReleaseAllowed": False}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
