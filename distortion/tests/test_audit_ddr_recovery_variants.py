"""Preserve all raw timing evidence while counting logical checks exactly once."""
from pathlib import Path
from decimal import Decimal
import copy
import hashlib
import json
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import audit_ddr_recovery_variants as tool


def fixture():
    """Use the committed actual check inventory, adding alternate DDC edges."""
    path = Path(__file__).resolve().parents[1] / "results/board1080-native-recovery-20261029.json"
    baseline = json.loads(path.read_text(encoding="utf-8"))
    result = []
    for index, row in enumerate(baseline["FullNativeRecoveryPaths"]):
        value = {key:row[key] for key in (*tool.KEYS, "LaunchEdge", "CaptureEdge", "Corner", "SlackState")}
        value.update(SlackNS=str(row["Slack"]), LaunchDataTransition="r", NativeReportLine=1+index*100,
                     NativePathSHA256=hashlib.sha256(str(index).encode()).hexdigest())
        result.append(value)
        if row["CaptureEdge"] == "falling":
            alternate = dict(value, CaptureEdge="rising", SlackNS=str(Decimal(value["SlackNS"])+Decimal("0.050")),
                             NativeReportLine=value["NativeReportLine"]+50,
                             NativePathSHA256=hashlib.sha256(("alt"+str(index)).encode()).hexdigest())
            alternate["SlackState"] = "VIOLATED" if Decimal(alternate["SlackNS"]) < 0 else "MET"
            result.append(alternate)
    summaries = {(corner, group["LaunchClock"], group["CaptureClock"]):data
                 for group in baseline["SixClockPairs"] for corner, data in group["Corners"].items()}
    return result, summaries


def test_full_profile_retains_all_variants_and_reconstructs_summaries():
    paths, summaries = fixture()
    proof = tool.audit(paths, summaries)
    assert proof["AuditPassed"] is True
    assert len(proof["Groups"]) == 12
    for corner, expected_failed in (("slow",244),("fast",233)):
        item = proof["Corners"][corner]
        assert item["LogicalCheckCount"] == 244
        assert item["NativeVariantCount"] == 251
        assert item["FailingChecks"] == expected_failed
        assert len(item["DualCaptureEdgeChecks"]) == 7
        assert sum(len(check["NativeVariants"]) for check in item["Checks"]) == 251
        assert len({(p["Source"],p["Endpoint"]) for p in item["Checks"]}) == 126
    assert proof["EntryRDCAudited"] is False
    assert proof["TimingExceptionApproved"] is False
    assert proof["ConstraintsApplied"] is False
    assert proof["HardwareReleaseAllowed"] is False
    assert len(paths) == 502  # audit does not deduplicate its caller's evidence


def test_same_endpoint_at_different_capture_clocks_stays_two_checks():
    paths, summaries = fixture()
    proof = tool.audit(paths, summaries)
    checks = proof["Corners"]["slow"]["Checks"]
    target = next(p["Endpoint"] for p in checks if p["Endpoint"].endswith("/OSR_IOLHR"))
    matched = [p for p in checks if p["Endpoint"] == target]
    assert len(matched) == 2
    assert len({p["CaptureClock"] for p in matched}) == 2


@pytest.mark.parametrize("mutation", ("missing_alternate_edge", "missing_nonnegative", "duplicate_record",
                                     "replace_edge_with_duplicate", "wrong_launch", "wrong_endpoint",
                                     "data_endpoint", "missing_corner", "invalid_transition"))
def test_evidence_loss_or_identity_change_rejects(mutation):
    paths, summaries = fixture()
    if mutation == "missing_alternate_edge":
        paths.pop(1)
    elif mutation == "missing_nonnegative":
        paths.remove(next(p for p in paths if p["Corner"] == "fast" and p["SlackState"] == "MET"))
    elif mutation == "duplicate_record":
        paths.append(copy.deepcopy(paths[0]))
    elif mutation == "replace_edge_with_duplicate":
        first = next(p for p in paths if p["CaptureEdge"] == "falling")
        alternate = next(p for p in paths if p is not first and all(p[k] == first[k] for k in (*tool.KEYS,"Corner")))
        alternate["CaptureEdge"] = "falling"
    elif mutation == "wrong_launch":
        paths[0]["LaunchEdge"] = "falling"
    elif mutation == "wrong_endpoint":
        paths[0]["Endpoint"] = tool.recovery.SLICE+"unexpected/RST"
    elif mutation == "data_endpoint":
        paths[0]["Endpoint"] = tool.recovery.SLICE+"unexpected/TX_DATA[2]"
    elif mutation == "missing_corner":
        paths[:] = [p for p in paths if p["Corner"] == "slow"]
    else:
        paths[0]["LaunchDataTransition"] = "unknown"
    with pytest.raises(ValueError):
        tool.audit(paths, summaries)


@pytest.mark.parametrize("field", ("WNS","TNS","Total","Failing"))
def test_native_summary_must_match_reconstructed_worst_per_check(field):
    paths, summaries = fixture()
    row = summaries[("slow","rst_clk","phy_dq_clk_0")]
    row[field] += 1 if field in ("Total","Failing") else 0.001
    with pytest.raises(ValueError, match="summary"):
        tool.audit(paths, summaries)


def test_missing_summary_group_rejects():
    paths, summaries = fixture()
    summaries.pop(next(iter(summaries)))
    with pytest.raises(ValueError, match="twelve"):
        tool.audit(paths, summaries)


def block(slack="-1.000", state="VIOLATED"):
    return f"""Startpoint  : {tool.recovery.IP}ddrphy_reset_ctrl/ddrphy_dqs_rst/opit_0_inv/CLK
Endpoint    : {tool.recovery.SLICE}i_ca_group[0].u_ddc_ca/ddc_inst/RST
Path Group  : phy_dq_clk_0
Path Type   : max (slow corner)
Path Class  : async timing path
 Clock rst_clk (rising edge) 0.000
 CLMA_1_1/Q0 tco 0.123 0.456 r source/Q
 Clock phy_dq_clk_0 (falling edge)
                            0.500
 Recovery time              0.017
 Slack ({state})            {slack}
"""


def test_parser_retains_line_transition_raw_slack_and_signature():
    paths, _ = tool.parse_lines(("header\n"+block()).splitlines(keepends=True))
    assert len(paths) == 1
    row = paths[0]
    assert row["NativeReportLine"] == 2
    assert row["LaunchDataTransition"] == "r"
    assert row["CaptureEdge"] == "falling"
    assert row["SlackNS"] == "-1.000"
    assert len(row["NativePathSHA256"]) == 64


def test_negative_zero_is_not_misreported_as_a_passing_check():
    paths, _ = tool.parse_lines(block("-0.000","VIOLATED").splitlines(keepends=True))
    assert tool.negative(paths[0]["SlackNS"])
    with pytest.raises(ValueError, match="contradicts"):
        tool.parse_lines(block("-0.000","MET").splitlines(keepends=True))


@pytest.mark.parametrize("mutation", ("missing_slack","missing_transition","wrong_kind","ambiguous_source","contradiction"))
def test_parser_does_not_accept_truncated_or_ambiguous_selected_record(mutation):
    text = block()
    if mutation == "missing_slack":
        text = text[:text.index(" Slack")]
    elif mutation == "missing_transition":
        text = text.replace("tco","td")
    elif mutation == "wrong_kind":
        text = text.replace("async timing path","false timing path")
    elif mutation == "ambiguous_source":
        text = text.replace("Endpoint","Startpoint : another/source\nEndpoint")
    else:
        text = text.replace("VIOLATED","MET")
    with pytest.raises(ValueError):
        tool.parse_lines(text.splitlines(keepends=True))


def test_parser_detects_duplicate_summary_rows():
    text = "Recovery Summary(Slow Corner):\n rst_clk phy_dq_clk_0 -1.000 -1.000 1 1\n"
    with pytest.raises(ValueError, match="duplicate recovery summary"):
        tool.parse_lines((text+text).splitlines(keepends=True))


def test_fresh_local_native_report_when_available():
    report = Path(__file__).resolve().parents[1]/"build/ddr-timing-repair/fresh-1029-admission-b/board1080_top.rtr"
    if not report.is_file():
        pytest.skip("large local native timing evidence is not distributed")
    result = tool.audit_file(report)
    assert result["AuditPassed"] is True
    assert result["Corners"]["fast"]["NonnegativeChecks"] == 11
    assert result["Corners"]["slow"]["NativeVariantCount"] == 251
    assert len(result["Input"]["SHA256"]) == 64
