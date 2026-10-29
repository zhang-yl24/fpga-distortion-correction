"""Exercise fresh native-text coverage, exact exceptions and immutable inputs."""
from decimal import Decimal
from pathlib import Path
import json
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import audit_fresh_ddr_timing as tool


def internal_rows():
    root = Path(__file__).resolve().parents[1]
    evidence = json.loads((root / "results/board1080-native-recovery-20261029.json").read_text())
    paths = []
    for row in evidence["FullNativeRecoveryPaths"]:
        row = dict(row, SlackNS=str(row["Slack"]))
        paths.append(row)
        if row["CaptureEdge"] == "falling":
            alternate = dict(row, CaptureEdge="rising",
                             SlackNS=str(Decimal(row["SlackNS"]) + Decimal("0.050")))
            alternate["SlackState"] = "VIOLATED" if Decimal(alternate["SlackNS"]) < 0 else "MET"
            paths.append(alternate)
    return paths, evidence["SixClockPairs"]


def entry(corner):
    return {"Source":tool.native.ENTRY_SOURCE, "Endpoint":tool.native.ENTRY_TARGET,
            "LaunchClock":"board27", "CaptureClock":"rst_clk",
            "LaunchEdge":"rising", "CaptureEdge":"rising", "Corner":corner,
            "SlackState":"VIOLATED", "SlackNS":"-0.010"}


def block(row, kind="recovery", exception=False):
    mode = "max" if kind in ("setup", "recovery") else "min"
    text = (f"Startpoint  : {row['Source']}\nEndpoint    : {row['Endpoint']}\n"
            f"Path Group  : {row['CaptureClock']}\nPath Type   : {mode} ({row['Corner']} corner)\n"
            f"Path Class  : {'false timing path' if exception else 'async timing path'}\n")
    if exception:
        text += "Timing Exception  :  False Path\n"
    text += (f" Clock {row['LaunchClock']} ({row['LaunchEdge']} edge) 0.000\n"
             f" CLMA_1_1/Q0 tco 0.123 0.456 r {row['Source'].rsplit('/',1)[0]}/Q\n"
             f" Clock {row['CaptureClock']} ({row['CaptureEdge']} edge) 0.000\n")
    if exception:
        text += " Slack (MET) infinity\n"
    else:
        text += f" Recovery time 0.017\n Slack ({row['SlackState']}) {row['SlackNS']}\n"
    return text


def summaries(groups, candidate=False):
    text = "Clock Summary:\n core 8.0 Declared 1 1 source\nClock Groups:\n"
    for corner in ("slow", "fast"):
        for kind in ("Setup", "Hold", "Recovery", "Removal", "Minimum Pulse Width"):
            text += f"{kind} Summary({corner.title()} Corner):\n"
            text += " core 1.000 0.000 0 5\n" if kind.startswith("Minimum") else " core core 1.000 0.000 0 5\n"
            if kind == "Hold":
                text += (" ddrphy_sysclk phy_dq_sysclk_1 0.021 0.000 0 420\n" if candidate
                         else " ddrphy_sysclk phy_dq_sysclk_1 -0.222 -0.222 1 420\n")
            elif kind in ("Recovery", "Removal") and not candidate:
                for group in groups:
                    native = group["Corners"][corner]
                    values = ((native["WNS"], native["TNS"], native["Failing"], native["Total"])
                              if kind == "Recovery" else (0.5, 0, 0, native["Total"]))
                    text += f" {group['LaunchClock']} {group['CaptureClock']} " + " ".join(map(str, values)) + "\n"
                text += " board27 rst_clk -0.010 -0.010 1 1\n" if kind == "Recovery" else " board27 rst_clk 0.5 0 0 1\n"
    return text


def exception_text(rows=()):
    text = ""
    for corner in ("slow", "fast"):
        for kind in ("setup", "hold", "recovery", "removal"):
            text += f"| Exception type  : set_false_path({kind})\n| {corner.title()} Corner\n"
            relevant = [p for p in rows if p["Corner"] == corner] if kind in ("recovery", "removal") else []
            text += "".join(block(p, kind, True) for p in relevant) or "No such exception path.\n"
    return text


@pytest.fixture
def files(tmp_path, monkeypatch):
    rows, groups = internal_rows()
    rows += [entry(c) for c in ("slow", "fast")]
    payload = {"baseline.rtr":summaries(groups) + "".join(block(p) for p in rows),
               "baseline_exception.rtr":exception_text(),
               "candidate.rtr":summaries(groups, candidate=True),
               "candidate_exception.rtr":exception_text(rows), "final.adf":"fixture ADF bytes"}
    for name, data in payload.items():
        (tmp_path / name).write_text(data, encoding="utf-8")
    monkeypatch.setattr(tool, "FINAL_ADF_SHA256", tool.sha(tmp_path / "final.adf"))
    return [tmp_path / name for name in payload]


def test_other_adf_rejected_even_with_its_correct_hash(files, tmp_path):
    other = tmp_path / "unrepaired.adf"
    other.write_bytes(b"unrepaired candidate with its own valid SHA256")
    with pytest.raises(ValueError, match="pinned fresh repaired candidate"):
        tool.audit(*files[:-1], other, tool.sha(other))


def run(files, **kwargs):
    return tool.audit(*files, tool.sha(files[-1]), **kwargs)


def replace(path, old, new, count=-1):
    text = path.read_text(encoding="utf-8")
    assert old in text
    path.write_text(text.replace(old, new, count), encoding="utf-8")


def test_complete_native_audit_preserves_every_variant_and_never_releases_hardware(files):
    result = run(files)
    assert result["AuditPassed"] and result["AllTenTimingTypesAndCornersChecked"]
    assert result["AllOtherSummaryRowsUnchanged"] and result["NoDataSetupOrHoldFalsePaths"]
    assert result["InternalResetChecksPerCorner"] == 244
    assert result["BaselineInternalNativeVariantsPerCorner"] == 251
    assert len(result["BaselineEntryPaths"]) == 2
    assert all(p["NativeReportLine"] > 1 and len(p["NativePathSHA256"]) == 64
               for p in result["BaselineEntryPaths"])
    inventory = result["BaselineRecoveryVariantEvidence"]
    for corner in ("slow", "fast"):
        checks = inventory["Corners"][corner]["Checks"]
        assert len(checks) == 244
        assert sum(len(p["NativeVariants"]) for p in checks) == 251
        assert result["FalsePathCounts"][corner+"_recovery"]["UniqueClockAndPinChecks"] == 245
        assert result["FalsePathCounts"][corner+"_recovery"]["ReportedPathVariants"] == 252
        assert result["CornerSummaries"][corner+"_recovery"]["RemovedResetChecks"] == 245
    assert len(result["InputsSHA256"]) == 5 and len(result["ToolsSHA256"]) == 4
    assert result["HardwareReleaseAllowed"] is result["PhysicalTimingReady"] is False


@pytest.mark.parametrize("mutation", ("changed_clock", "unrelated_summary", "still_failing_hold",
                                     "baseline_cut", "missing_exception", "duplicate_exception",
                                     "wrong_capture_clock", "wrong_launch_edge", "data_exception"))
def test_native_scope_or_summary_errors_reject(files, mutation):
    if mutation == "changed_clock":
        replace(files[2], "core 8.0 Declared", "core 7.0 Declared")
    elif mutation == "unrelated_summary":
        replace(files[2], "core core 1.000", "core core 0.900", 1)
    elif mutation == "still_failing_hold":
        replace(files[2], "0.021 0.000 0 420", "-0.001 -0.001 1 420", 1)
    elif mutation == "baseline_cut":
        files[1].write_text(exception_text([entry("slow")]))
    elif mutation in ("missing_exception", "duplicate_exception"):
        text = files[3].read_text()
        start = text.index("Startpoint")
        end = text.index("Startpoint", start+1)
        record = text[start:end]
        # Choose entry (a single-edge logical check) for the missing case.
        if mutation == "missing_exception":
            record = block(entry("slow"), exception=True)
            assert record in text
            text = text.replace(record, "", 1)
        else:
            text = text[:start] + record + text[start:]
        files[3].write_text(text)
    elif mutation == "wrong_capture_clock":
        replace(files[3], "Path Group  : phy_dq_clk_0", "Path Group  : alien_clock", 1)
        replace(files[3], " Clock phy_dq_clk_0", " Clock alien_clock", 1)
    elif mutation == "wrong_launch_edge":
        replace(files[3], " Clock rst_clk (rising edge)", " Clock rst_clk (falling edge)", 1)
    else:
        replace(files[3], "No such exception path.\n", block(entry("slow"), kind="setup", exception=True), 1)
    with pytest.raises(ValueError):
        run(files)


@pytest.mark.parametrize("mutation", ("missing", "duplicate", "clock", "launch", "class", "slack", "min"))
def test_entry_rdc_requires_one_exact_native_maximum_path_each_corner(files, mutation):
    original = block(entry("slow"))
    changed = original
    if mutation == "missing":
        changed = ""
    elif mutation == "duplicate":
        changed += original
    elif mutation == "clock":
        changed = changed.replace("Clock board27", "Clock alien")
    elif mutation == "launch":
        changed = changed.replace("Clock board27 (rising edge)", "Clock board27 (falling edge)")
    elif mutation == "class":
        changed = changed.replace("async timing path", "false timing path")
    elif mutation == "slack":
        changed = changed.replace("Slack (VIOLATED) -0.010", "Slack (MET) -0.010")
    else:
        changed = changed.replace("Path Type   : max", "Path Type   : min")
    replace(files[0], original, changed, 1)
    with pytest.raises(ValueError):
        tool.expected_paths(files[0])


def test_reject_missing_alternate_edge_instead_of_deduplicating(files):
    rows, _ = internal_rows()
    row = next(p for p in rows if p["CaptureEdge"] == "falling")
    replace(files[0], block(row), "", 1)
    with pytest.raises(ValueError, match="251"):
        run(files)


def test_final_adf_hash_is_explicit_and_cannot_be_replaced(files):
    with pytest.raises(ValueError, match="hash mismatch"):
        tool.audit(*files, "0"*64)


def test_entry_slack_must_reconstruct_its_native_summary(files):
    replace(files[0], "board27 rst_clk -0.010 -0.010 1 1",
            "board27 rst_clk -0.020 -0.020 1 1", 1)
    with pytest.raises(ValueError, match="entry path slack"):
        run(files)


def test_input_changed_after_initial_hash_is_rejected(files, monkeypatch):
    compare = tool.native.compare_summaries
    def mutate(*args):
        result = compare(*args)
        files[-1].write_text("different candidate ADF")
        return result
    monkeypatch.setattr(tool.native, "compare_summaries", mutate)
    with pytest.raises(ValueError, match="input changed"):
        run(files)


def test_io_logs_must_be_supplied_together_and_unchanged(files, tmp_path):
    baseline = tmp_path / "baseline.log"
    candidate = tmp_path / "candidate.log"
    text = "W: Timing-4086: Port 'input_port' is not constrained, no input delay.\n"
    baseline.write_text(text)
    candidate.write_text(text)
    with pytest.raises(ValueError, match="both IO logs"):
        run(files, baseline_log=baseline)
    result = run(files, baseline_log=baseline, candidate_log=candidate)
    assert result["ExternalIOWarningEvidence"]["Identical"] is True
    candidate.write_text(text.replace("input_port", "other_input"))
    with pytest.raises(ValueError, match="IO warning set changed"):
        run(files, baseline_log=baseline, candidate_log=candidate)


def test_local_fresh_report_binds_all_251_internal_variants_and_both_entries():
    report = Path(__file__).resolve().parents[1] / "build/ddr-timing-repair/fresh-1029-admission-b/board1080_top.rtr"
    if not report.is_file():
        pytest.skip("local native report is not distributed")
    expected, inventory, entries = tool.expected_paths(report)
    assert all(len(rows) == 252 and len({p[:4] for p in rows}) == 245 for rows in expected.values())
    assert inventory["AuditPassed"]
    assert len(entries) == 2
