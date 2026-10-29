"""Fail closed on missing/native scope changes; no EDA or hardware."""
from pathlib import Path
import copy
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import audit_ddr_final_timing as tool


def row(slack=1.0, failed=0, count=5):
    return {"WorstSlackNS": slack, "TotalNegativeSlackNS": min(slack, 0.0),
            "FailingChecks": failed, "TotalChecks": count}


def summary_fixture():
    baseline, candidate = {}, {}
    for corner in ("slow", "fast"):
        for kind in tool.KINDS:
            key = (corner, kind)
            baseline[key] = {("core", "core"): row()}
            if kind == "hold":
                baseline[key][tool.HOLD_PAIR] = row(-0.222, 1, 420)
            elif kind in ("recovery", "removal"):
                baseline[key].update({pair: row(0.5, 0, count) for pair, count in tool.recovery.PAIRS.items()})
                baseline[key][tool.ENTRY_PAIR] = row(0.5, 0, 1)
            candidate[key] = copy.deepcopy(baseline[key])
            if kind == "hold":
                candidate[key][tool.HOLD_PAIR] = row(0.021, 0, 420)
            elif kind in ("recovery", "removal"):
                for pair in set(tool.recovery.PAIRS) | {tool.ENTRY_PAIR}:
                    del candidate[key][pair]
    return baseline, candidate


def test_only_the_intended_hold_and_reset_rows_change():
    baseline, candidate = summary_fixture()
    changes, totals = tool.compare_summaries(baseline, candidate)
    assert len(changes) == 2
    assert totals["slow_recovery"]["RemovedResetChecks"] == 245
    assert totals["fast_hold"]["FailingChecks"] == 0


@pytest.mark.parametrize("mutation", ("remove_data", "add_cut", "change_setup", "new_failure", "wrong_reset_count", "negative_tns"))
def test_unrelated_or_missing_checks_reject(mutation):
    baseline, candidate = summary_fixture()
    if mutation == "remove_data":
        del candidate[("slow", "hold")][tool.HOLD_PAIR]
    elif mutation == "add_cut":
        candidate[("fast", "recovery")][("other", "clock")] = row()
    elif mutation == "change_setup":
        candidate[("slow", "setup")][("core", "core")] = row(0.9)
    elif mutation == "new_failure":
        candidate[("fast", "hold")][tool.HOLD_PAIR] = row(-0.001, 1, 420)
    elif mutation == "wrong_reset_count":
        baseline[("slow", "recovery")][tool.ENTRY_PAIR]["TotalChecks"] = 2
    else:
        candidate[("fast", "hold")][tool.HOLD_PAIR]["TotalNegativeSlackNS"] = -0.001
    with pytest.raises(ValueError):
        tool.compare_summaries(baseline, candidate)


def check(source="ip/source/CLK", target="ip/endpoint/RST", capture="phy", edge="falling"):
    return (source, target, "rst", capture, "rising", edge)


def record(identity, corner="slow"):
    return dict(zip(("Source", "Endpoint", "LaunchClock", "CaptureClock", "LaunchEdge", "CaptureEdge"), identity),
                Corner=corner, PathClass="false timing path", LaunchDataTransition="r", NativePathSignature="fixture")


def exception_fixture():
    expected = {c: {check(), check(capture="phy_div")} for c in ("slow", "fast")}
    sections = {(c, k): [] for c in ("slow", "fast") for k in ("setup", "hold", "recovery", "removal")}
    for (corner, kind) in sections:
        if kind in ("recovery", "removal"):
            sections[(corner, kind)] = [record(p, corner) for p in expected[corner]]
    return sections, expected


def test_false_paths_require_each_capture_clock_variant():
    sections, expected = exception_fixture()
    counts = tool.validate_exception_sets(sections, expected)
    assert counts["slow_recovery"]["UniqueClockAndPinChecks"] == 2
    sections[("slow", "recovery")].pop()
    with pytest.raises(ValueError, match="missing=1"):
        tool.validate_exception_sets(sections, expected)


def test_capture_edge_representative_can_change_after_false_path():
    sections, expected = exception_fixture()
    sections[("slow", "recovery")][0]["CaptureEdge"] = "rising"
    assert tool.validate_exception_sets(sections, expected)


def test_native_source_rise_and_fall_paths_are_distinct_variants_of_one_check():
    sections, expected = exception_fixture()
    second = copy.deepcopy(sections[("slow", "recovery")][0])
    second["LaunchDataTransition"] = "f"
    sections[("slow", "recovery")].append(second)
    count = tool.validate_exception_sets(sections, expected)["slow_recovery"]
    assert count["UniqueClockAndPinChecks"] == 2
    assert count["ReportedPathVariants"] == 3
    assert count["DistinctNativePathVariants"] == 3


def test_distinct_capture_delay_variants_do_not_become_extra_clock_checks():
    sections, expected = exception_fixture()
    second = copy.deepcopy(sections[("slow", "recovery")][0])
    second["NativePathSignature"] = "second native capture-delay body"
    sections[("slow", "recovery")].append(second)
    count = tool.validate_exception_sets(sections, expected)["slow_recovery"]
    assert count["UniqueClockAndPinChecks"] == 2
    assert count["DistinctNativePathVariants"] == 3


@pytest.mark.parametrize("mutation", ("data_endpoint", "duplicate", "launch_edge", "setup_cut"))
def test_false_path_scope_errors_reject(mutation):
    sections, expected = exception_fixture()
    if mutation == "data_endpoint":
        sections[("slow", "recovery")][0]["Endpoint"] = "ip/data/TX_DATA[2]"
    elif mutation == "duplicate":
        sections[("slow", "recovery")].append(copy.deepcopy(sections[("slow", "recovery")][0]))
    elif mutation == "launch_edge":
        sections[("slow", "recovery")][0]["LaunchEdge"] = "falling"
    else:
        sections[("slow", "setup")] = [record(check())]
    with pytest.raises(ValueError):
        tool.validate_exception_sets(sections, expected)


def path_block(kind="recovery", corner="slow", capture="phy", edge="falling"):
    mode = "max" if kind in ("setup", "recovery") else "min"
    return f"""Startpoint  : ip/source/CLK
Endpoint    : ip/endpoint/RST
Path Group  : {capture}
Path Type   : {mode} ({corner} corner)
Path Class  : false timing path
Timing Exception  :  False Path
 Clock rst (rising edge) 0.000
 CLMA_1_1/Q0 tco 0.123 0.456 r ip/source/Q
 Clock {capture} ({edge} edge) 0.000
 Slack (MET) infinity
"""


def test_exception_parser_accepts_infinite_slack_and_wrapped_clocks():
    text = ""
    for corner in ("slow", "fast"):
        for kind in ("setup", "hold", "recovery", "removal"):
            text += f"| Exception type  : set_false_path({kind})\n| {corner.title()} Corner\n"
            text += path_block(kind, corner) if kind in ("recovery", "removal") else "No such exception path.\n"
    parsed = tool.parse_false_paths(text.splitlines(keepends=True))
    assert len(parsed) == 8
    assert parsed[("slow", "recovery")][0]["CaptureEdge"] == "falling"
    assert parsed[("slow", "recovery")][0]["LaunchDataTransition"] == "r"
    with pytest.raises(ValueError, match="all eight"):
        tool.parse_false_paths(text.splitlines(keepends=True)[:8])


def test_summary_parser_stops_before_detailed_net_rows():
    text = "Clock Summary:\n core 8.0 Declared 1 1 source\n Clock Groups:\n"
    for corner in ("Slow", "Fast"):
        for kind in ("Setup", "Hold", "Recovery", "Removal", "Minimum Pulse Width"):
            text += f"{kind} Summary({corner} Corner):\n"
            text += " core 0.1 0.000 0 5\n" if kind.startswith("Minimum") else " core core 0.1 0.000 0 5\n"
    text += "Startpoint : ip/CLK\n net (fanout=2) 0.279 1.639 input_status/net\n"
    tables, clocks = tool.parse_summaries(text.splitlines(keepends=True))
    assert len(tables) == 10 and clocks
    assert set(tables[("fast", "mpw")]) == {("core",)}
    with pytest.raises(ValueError, match="all ten"):
        tool.parse_summaries(text.splitlines(keepends=True)[:4])


def test_local_nworst1_report_cannot_prove_all_clock_check_variants():
    root = Path(__file__).resolve().parents[1] / "build/ddr-fix-20261029"
    report = root / "persist-all-p/reload/board1080_top_exception.rtr"
    baseline = root / "mpnr-base-g/board1080_top.rtr"
    if not report.is_file() or not baseline.is_file():
        pytest.skip("local native output is not distributed")
    expected, _ = tool.expected_paths(baseline)
    with report.open() as stream:
        sections = tool.parse_false_paths(stream)
    assert len(sections[("slow", "recovery")]) == 127
    with pytest.raises(ValueError, match="missing"):
        tool.validate_exception_sets(sections, expected)
