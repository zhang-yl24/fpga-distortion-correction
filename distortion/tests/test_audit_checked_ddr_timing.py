"""Synthetic CPU fixtures; none is an authoritative native build result."""
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import json
import os
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import audit_checked_ddr_timing as audit


def synthetic_summaries():
    row = dict(WorstSlackNS=0.1, TotalNegativeSlackNS=0.0, FailingChecks=0, TotalChecks=5)
    baseline = {(corner, kind): {("cfg_clk", "cfg_clk"): dict(row)}
                for corner in ("slow", "fast") for kind in audit.native.KINDS}
    for (corner, kind), rows in baseline.items():
        if kind in ("recovery", "removal"):
            for pair, count in {**audit.native.recovery.PAIRS, audit.native.ENTRY_PAIR: 1}.items():
                rows[pair] = dict(row, TotalChecks=count, FailingChecks=count,
                                  WorstSlackNS=-0.1, TotalNegativeSlackNS=-count / 10)
    candidate = deepcopy(baseline)
    for (_, kind), rows in candidate.items():
        if kind in ("recovery", "removal"):
            for pair in set(audit.native.recovery.PAIRS) | {audit.native.ENTRY_PAIR}:
                del rows[pair]
    return baseline, candidate


def test_synthetic_exact_reset_effects_keep_all_hdmi_rows():
    totals, preserved, removed, hdmi = audit.compare_summaries(*synthetic_summaries())
    assert len(totals) == preserved == len(hdmi) == 10
    assert len(removed) == 28
    assert totals["fast_recovery"]["RemovedResetChecks"] == 245
    assert totals["slow_hold"]["RemovedResetChecks"] == 0


@pytest.mark.parametrize("kind", audit.native.KINDS)
def test_reject_any_retained_hdmi_timing_change(kind):
    baseline, candidate = synthetic_summaries()
    candidate[("fast", kind)][("cfg_clk", "cfg_clk")]["WorstSlackNS"] += 0.001
    with pytest.raises(ValueError, match="retained timing row changed"):
        audit.compare_summaries(baseline, candidate)


def test_reject_extra_reset_or_data_exception_effect():
    baseline, candidate = synthetic_summaries()
    del candidate[("slow", "setup")][("cfg_clk", "cfg_clk")]
    with pytest.raises(ValueError, match="summary row"):
        audit.compare_summaries(baseline, candidate)


def test_reject_remaining_failure_even_if_identical():
    baseline, candidate = synthetic_summaries()
    for tables in (baseline, candidate):
        tables[("fast", "hold")][("cfg_clk", "cfg_clk")]["FailingChecks"] = 1
    with pytest.raises(ValueError, match="remaining native timing failure"):
        audit.compare_summaries(baseline, candidate)


def test_reject_wrong_reset_cardinality():
    baseline, candidate = synthetic_summaries()
    baseline[("slow", "recovery")][audit.native.ENTRY_PAIR]["TotalChecks"] = 2
    with pytest.raises(ValueError, match="reset group count"):
        audit.compare_summaries(baseline, candidate)


def test_reject_missing_timing_type():
    baseline, candidate = synthetic_summaries()
    del candidate[("fast", "mpw")]
    with pytest.raises(ValueError, match="all ten"):
        audit.compare_summaries(baseline, candidate)


def test_reject_changed_receipt_before_candidate_admission(tmp_path):
    directory = tmp_path / "results"
    directory.mkdir()
    (directory / "board1080-checked-full-build-20261029.json").write_text('{"Synthetic":true}')
    with pytest.raises(ValueError, match="hash"):
        audit.audit(tmp_path)


def test_serialization_failure_leaves_no_output(tmp_path, monkeypatch):
    destination = tmp_path / "synthetic.json"
    monkeypatch.setattr(audit, "audit", lambda: {"Synthetic": True, "EvidenceSHA256": {Path("bad"): "hash"}})
    with pytest.raises(TypeError):
        audit.main(["--output", str(destination)])
    assert not destination.exists()


def test_serialized_evidence_and_exclusive_output(tmp_path, monkeypatch):
    destination = tmp_path / "synthetic.json"
    result = {"Synthetic": True, "RetainedSummaryRows": 10, "EvidenceSHA256": {str(tmp_path / "input"): "hash"}}
    monkeypatch.setattr(audit, "audit", lambda: result)
    assert audit.main(["--output", str(destination)]) == 0
    assert json.loads(destination.read_text()) == result
    with pytest.raises(FileExistsError):
        audit.main(["--output", str(destination)])


@pytest.fixture
def synthetic_execution(tmp_path, monkeypatch):
    work = tmp_path / "checked-final-sta-1029-a"
    work.mkdir()
    alias = "P:/distortion/build/board1080-timing/" + work.name
    begin = datetime.now(timezone.utc).timestamp() - 10
    iso = lambda stamp: datetime.fromtimestamp(stamp, timezone.utc).isoformat()
    start = {"Synthetic": True, "StartedUTC": iso(begin), "HardwareAccessed": False,
             "Executable": "D:/pango/PDS_2023.2/bin/pds_shell.exe",
             "Arguments": ["-file", alias + "/query.tcl", "-work_dir", alias,
                           "-project_name", "checked_final_sta"]}
    end = {"Synthetic": True, "StartedUTC": iso(begin), "EndedUTC": iso(begin + 5),
           "NativeReturnCode": 0, "HardwareAccessed": False}
    (work / "execution-start.json").write_text(json.dumps(start), encoding="utf-8-sig")
    (work / "execution-complete.json").write_text(json.dumps(end), encoding="utf-8-sig")
    (work / "query.tcl").write_text(audit.expected_script(work.name, "final"))
    commands = [audit.ARCH, "add_design " + alias + "/dummy.v", "mpnr -input " + alias + "/input.adf",
                "show -design_net _N55", "show -design_net _N63", audit.REPORT]
    text = "\n".join("Executing : " + c + " successfully." for c in commands) + "\n"
    (work / "native-console.log").write_text(text + "CHECKED_FINAL_INDEPENDENT_STA_COMPLETE\n")
    (work / "run.log").write_text("#Build: Fabric Compiler 2023.2-SP3, Build 154097, Synthetic\n" + text)
    for path in work.iterdir():
        os.utime(path, (begin + 3, begin + 3))
    original_bind = audit.common.bind
    monkeypatch.setattr(audit.common, "bind", lambda watched, path, digest=None:
                        Path(path) if str(path) == start["Executable"] else original_bind(watched, path, digest))
    return work


def test_synthetic_execution_checks_bom_and_exact_invocation(synthetic_execution):
    result = audit.check_execution(synthetic_execution, "final", {})
    assert result["Start"]["Synthetic"] is True
    assert result["Complete"]["NativeReturnCode"] == 0


@pytest.mark.parametrize("field,value,message", [
    ("NativeReturnCode", 1, "native execution failed"),
    ("NativeReturnCode", False, "native execution failed"),
    ("HardwareAccessed", True, "hardware scope"),
    ("StartedUTC", "2000-01-01T00:00:00Z", "start mismatch"),
])
def test_reject_bad_execution_receipt(synthetic_execution, field, value, message):
    path = synthetic_execution / "execution-complete.json"
    data = audit.read_json(path)
    data[field] = value
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match=message):
        audit.check_execution(synthetic_execution, "final", {})


def test_reject_tcl_injected_broad_exception(synthetic_execution):
    path = synthetic_execution / "query.tcl"
    path.write_text(path.read_text() + "set_false_path -from [all_clocks]\n")
    with pytest.raises(ValueError, match="executed Tcl"):
        audit.check_execution(synthetic_execution, "final", {})


@pytest.mark.parametrize("mutation,message", [("missing", "missing native commands"),
                                                ("stale", "stale native log"),
                                                ("fatal", "native fatal diagnostic")])
def test_reject_missing_native_stage_or_stale_log(synthetic_execution, mutation, message):
    path = synthetic_execution / "native-console.log"
    text = path.read_text()
    stamp = path.stat().st_mtime
    if mutation == "missing":
        text = "\n".join(line for line in text.splitlines() if "mpnr_report_timing" not in line) + "\n"
    elif mutation == "fatal":
        text += "E: Synthetic failure\n"
    path.write_text(text)
    os.utime(path, (stamp, stamp - 100 if mutation == "stale" else stamp))
    with pytest.raises(ValueError, match=message):
        audit.check_execution(synthetic_execution, "final", {})
