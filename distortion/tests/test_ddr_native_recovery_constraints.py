"""Completeness, scope and native slash-name tests; never invoke PDS."""
from pathlib import Path
import copy
import json
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import prepare_ddr_native_recovery_constraints as tool


def evidence():
    path = Path(__file__).resolve().parents[1] / "results/board1080-native-recovery-20261029.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    summaries = {(corner, group["LaunchClock"], group["CaptureClock"]): data
                 for group in value["SixClockPairs"] for corner, data in group["Corners"].items()}
    return value["FullNativeRecoveryPaths"], summaries


def test_complete_native_evidence_generates_authorized_subset():
    paths, summaries = evidence()
    result, fdc = tool.build(paths, summaries)
    assert len(paths) == 488 and len(result["FastNonnegativeChecks"]) == 11
    assert result["CandidateChecksPerCorner"] == 243
    assert result["FullUniqueSourceEndpointPairs"] == 126
    assert result["CandidateUniqueSourceEndpointPairs"] == 125
    assert result["All244CandidateCoverage"] is False
    assert fdc.count("set_false_path -from") == 125
    assert tool.CPD_SOURCE not in fdc and tool.CPD_TARGET not in fdc
    assert "/CLK$}]" in fdc and r"\[0\]" in fdc
    assert ":CLK" not in fdc and "get_clocks" not in fdc
    assert "llength" not in "\n".join(line for line in fdc.splitlines() if not line.startswith("#"))
    assert "Timing-5001" in fdc


def test_explicit_cpd_opt_in_keeps_its_own_actual_source():
    paths, summaries = evidence()
    result, fdc = tool.build(paths, summaries, include_cpd=True)
    assert result["CandidateChecksPerCorner"] == 244
    assert result["CandidateUniqueSourceEndpointPairs"] == 126
    assert result["ExcludedPendingCPD"] == []
    assert result["CPDIncluded"] is True
    assert fdc.count("set_false_path -from") == 126
    assert tool.CPD_SOURCE in fdc and tool.CPD_TARGET in fdc


def test_cpd_opt_in_requires_a_boolean():
    paths, summaries = evidence()
    with pytest.raises(ValueError, match="boolean"):
        tool.build(paths, summaries, include_cpd=1)


def test_missing_nonnegative_fast_check_is_rejected():
    paths, summaries = evidence()
    paths.remove(next(p for p in paths if p["Corner"] == "fast" and p["Slack"] >= 0))
    with pytest.raises(ValueError, match="all 244"):
        tool.build(paths, summaries)


def test_duplicate_path_cannot_hide_missing_endpoint():
    paths, summaries = evidence()
    slow = [p for p in paths if p["Corner"] == "slow"]
    paths[paths.index(slow[1])] = copy.deepcopy(slow[0])
    with pytest.raises(ValueError, match="duplicate recovery"):
        tool.build(paths, summaries)


def test_same_count_different_corner_endpoints_is_rejected():
    paths, summaries = evidence()
    path = next(p for p in paths if p["Corner"] == "fast" and p["Endpoint"].endswith("/OSR_IOLHR"))
    path["Endpoint"] = tool.SLICE + "unexpected/opit_1/OSR_IOLHR"
    with pytest.raises(ValueError, match="identity sets differ"):
        tool.build(paths, summaries)


@pytest.mark.parametrize("target", [tool.SLICE + "data/TX_DATA[2]", "outside/reset/RST",
                                   tool.SLICE + "not_tsr/TSR"])
def test_data_or_wrong_source_family_is_rejected(target):
    paths, summaries = evidence()
    path = next(p for p in paths if "/ddrphy_dqs_rst/" in p["Source"])
    path["Endpoint"] = target
    with pytest.raises(ValueError, match="wrong reset source family"):
        tool.build(paths, summaries)


def test_summary_does_not_prove_missing_paths():
    paths, summaries = evidence()
    summaries[("slow", "rst_clk", "phy_dq_clk_0")]["Total"] += 1
    with pytest.raises(ValueError, match="summary/path count"):
        tool.build(paths, summaries)


def test_unexpected_cpd_mapping_is_rejected():
    paths, summaries = evidence()
    path = next(p for p in paths if p["Source"].startswith(tool.CPD_SOURCE + "/"))
    path["Endpoint"] = tool.SLICE + "other/RST"
    with pytest.raises(ValueError, match="unexpected CPD"):
        tool.build(paths, summaries)


def test_parser_retains_nonnegative_wrapped_capture_clock():
    text = """Startpoint  : u_ddr3_test_h/u_ddrphy_top/source/opit_0/CLK
Endpoint    : u_ddr3_test_h/u_ddrphy_top/target/RST
Path Group  : phy_dq_sysclk_0
Path Type   : max (fast corner)
Path Class  : async timing path
 Clock rst_clk (rising edge)      0.000
 Clock phy_dq_sysclk_0 (rising edge)
                                2.000
 Recovery time                 -0.125
 Slack (MET)                    0.067
"""
    paths, _ = tool.parse_lines(text.splitlines(keepends=True))
    assert len(paths) == 1 and paths[0]["Slack"] == 0.067
    with pytest.raises(ValueError, match="slack state"):
        tool.parse_lines(text.replace("Slack (MET)", "Slack (VIOLATED)").splitlines(keepends=True))


def test_exception_baseline_requires_no_existing_false_paths():
    text = "".join(f"| Exception type  : set_false_path({kind})\n| {corner} Corner\n"
                   "No such exception path.\n" for corner in ("Slow", "Fast")
                   for kind in ("setup", "hold", "recovery", "removal"))
    assert len(tool.exception_baseline(text)) == 8
    with pytest.raises(ValueError, match="already contains"):
        tool.exception_baseline(text.replace("No such exception path.", "Startpoint : bad", 1))


def test_complete_local_native_report_when_available():
    report = Path(__file__).resolve().parents[1] / "build/ddr-fix-20261029/mpnr-base-g/board1080_top.rtr"
    if not report.is_file():
        pytest.skip("local native STA output is not distributed")
    with report.open(encoding="utf-8-sig") as stream:
        paths, summaries = tool.parse_lines(stream)
    result, _ = tool.build(paths, summaries)
    assert result["CandidateChecksPerCorner"] == 243
