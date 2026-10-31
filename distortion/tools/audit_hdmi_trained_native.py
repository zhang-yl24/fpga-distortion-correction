"""Compare exact native reports for hdmi_uart_trained_diag, offline only.

This checks the caller's baseline and regenerated report pair. A runtime
launcher must separately bind that baseline, source closure, ADF and pin map.
No PDS, constraints, bitstream generation or hardware operation occurs here.
"""
from collections import Counter
from pathlib import Path
import argparse
import json
import re

import audit_ddr_final_timing as timing
from prepare_hdmi_input_bitstream import exception_inventory, read_text, require, sha

TARGET = "hdmi_uart_trained_diag"
FALSE_IDENTITY = ("Source", "Endpoint", "LaunchClock", "CaptureClock",
                  "LaunchEdge", "CaptureEdge", "LaunchDataTransition")


def report_summaries(path):
    with Path(path).open(encoding="utf-8-sig", errors="replace") as stream:
        tables, clocks = timing.parse_summaries(stream)
    for rows in tables.values():
        for row in rows.values():
            require(row["FailingChecks"] == 0 and row["TotalNegativeSlackNS"] == 0
                    and row["WorstSlackNS"] >= 0 and row["TotalChecks"] > 0,
                    "native timing check failed or is empty")
    with Path(path).open(encoding="utf-8-sig", errors="replace") as stream:
        header = "".join(line for _, line in zip(range(220), stream))
    summaries = re.findall(r"(?m)^Design Summary\s*:\s*(.+?)\s*$", header)
    require(summaries == ["All Constraints Met."],
            "native all-constraints-met declaration missing or ambiguous")
    for key, expected in (("Design", TARGET), ("Device", "PG2L100H"),
                          ("Speed Grade", "-6"), ("Package", "FBG676")):
        values = re.findall(r"(?m)^\| " + re.escape(key) + r"\s*:\s*(\S+)\s*$", header)
        require(values == [expected], "native report design/device mismatch: " + key)
    return tables, clocks


def compare(baseline_report, baseline_exceptions, report, exceptions):
    """Require identical passing native summaries and exact scoped exceptions."""
    baseline = report_summaries(baseline_report)
    current = report_summaries(report)
    require(current == baseline, "native summary or clock inventory changed")
    # The unchanged parser requires all 24 tables, exactly 167 8ns MaxDelay
    # entries and hold false paths per corner, four recovery/removal false
    # paths, zero setup false paths, and no other exception types.
    old_sections, old_false, old_max = exception_inventory(baseline_exceptions)
    sections, false, maxima = exception_inventory(exceptions)
    require(sections == old_sections, "native exception table counts changed")
    require(set(false) == set(old_false), "native false-path table inventory changed")
    for key, rows in false.items():
        identities = lambda paths: Counter(tuple(p[name] for name in FALSE_IDENTITY) for p in paths)
        require(identities(rows) == identities(old_false[key]),
                "native false-path identities changed")
    order = lambda path: (path["Corner"], path["Endpoint"], path["Source"])
    require(sorted(maxima, key=order) == sorted(old_max, key=order),
            "native MaxDelay identities or values changed")
    paths = dict(BaselineReport=baseline_report, BaselineExceptions=baseline_exceptions,
                 Report=report, Exceptions=exceptions)
    return dict(Schema="hdmi-trained-native-comparison-v1", Target=TARGET, AuditPassed=True,
                AllTenTimingTypesPassed=True, NativeSummariesAndClocksUnchanged=True,
                ExactFalsePathsUnchanged=True, AllMaxDelayChecksUnchanged=True,
                MaxDelayCountPerCorner={c: sum(p["Corner"] == c for p in maxima) for c in ("slow", "fast")},
                FalsePathCountPerCorner={c: {k: len(false[(c, k)]) for k in ("setup", "hold", "recovery", "removal")} for c in ("slow", "fast")},
                WorstSlackNS={c: {k: min(row["WorstSlackNS"] for row in current[0][(c, k)].values()) for k in timing.KINDS} for c in ("slow", "fast")},
                ReportSHA256={name: sha(path) for name, path in paths.items()},
                HardwareAccessed=False, HardwareReleaseAllowed=False,
                Limits="Native report comparison only. Caller must bind baseline reports to the exact source, ADF, execution and pins; no external AC, complete CDC or hardware acceptance.")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("baseline-report", "baseline-exceptions", "report", "exceptions", "output"):
        parser.add_argument("--" + name, required=True, type=Path)
    args = parser.parse_args(argv)
    if args.output.exists() or not args.output.parent.is_dir():
        parser.error("output must be a new file in an existing directory")
    result = compare(args.baseline_report, args.baseline_exceptions, args.report, args.exceptions)
    with args.output.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps(dict(AuditPassed=True, Target=TARGET, Output=str(args.output))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
