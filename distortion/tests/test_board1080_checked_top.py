"""Keep isolated checked top changes bounded and reject unsafe receipts."""
from pathlib import Path
import csv
import json
import sys
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import prepare_board1080_checked_top as top
import run_board1080_checked_control_sim as runner


def test_exact_top_transformation_keeps_ddr_and_data_path():
    audit = top.audit()
    assert audit["Edits"] == 10
    assert audit["DDRAndPipelineBodyUnchanged"] is True
    assert audit["ProductionManifestChanged"] is False
    candidate = (top.ROOT / top.CANDIDATE).read_text()
    original = (top.ROOT / top.BASELINE).read_text()
    for anchor, ending in (("    ddr3_test u_ddr3_test_h(", "    (* async_reg=\"true\" *) reg [1:0] ref_reset"),
                           ("    wire pipeline_reset_n=", "    assign led=")):
        assert candidate[candidate.index(anchor):candidate.index(ending)] == original[original.index(anchor):original.index(ending)]
    assert "inout hd_scl" in candidate and "!hdmi_failed_ref[1]" in candidate
    assert "else if(pipeline_release && !board_failed)" in candidate


@pytest.mark.parametrize("mutation", ("ddr_reset", "runtime_reset", "startup_gate", "priority", "scl_pushpull", "baseline"))
def test_unapproved_top_or_reference_changes_cannot_audit(tmp_path, mutation):
    base = tmp_path / top.BASELINE
    base.parent.mkdir(parents=True)
    base.write_bytes((top.ROOT / top.BASELINE).read_bytes())
    new = tmp_path / top.CANDIDATE
    text = (top.ROOT / top.CANDIDATE).read_bytes()
    if mutation == "baseline": base.write_bytes(base.read_bytes() + b"\r\n")
    else:
        before, after = {
            "ddr_reset": (b".resetn(global_reset_n)", b".resetn(pipeline_reset_n)"),
            "runtime_reset": (b"global_reset_n && pipeline_release;", b"global_reset_n && pipeline_release && !board_failed;"),
            "startup_gate": (b"!board_failed && !hdmi_failed_ref[1]", b"!board_failed"),
            "priority": (b"else if(pipeline_release && !board_failed)", b"if(pipeline_release && !board_failed)"),
            "scl_pushpull": (b"inout hd_scl", b"output hd_scl"),
        }[mutation]
        assert before in text
        text = text.replace(before, after, 1)
    new.write_bytes(text)
    with pytest.raises(ValueError): top.audit(tmp_path)


def save_rows(path, rows):
    with (path / "checked-control-events.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=("event", "case", "global_reset_n", "pipeline_reset_n",
            "board_failed", "board_fault", "led7", "physical_stub_awvalid", "capture_admit", "scan_enable", "external_fault", "ddr_reset_n"))
        writer.writeheader();writer.writerows(rows)


@pytest.fixture
def receipt(tmp_path):
    summary = {"Passed": True, "StartupFailureCases": 2, "LateFailureHeldAWCases": 1, "CommonResets": 3,
        "ColdPowerReferenceCycles": 1048579, "ActualCheckedTopExecuted": True, "TestOnlyIPStubs": True,
        "PipelineResetMonotonic": True, "DDRResetPreserved": True, "PhysicalI2CVerified": False,
        "ActualSystemDatapathVerified": False, "HardwareAccessed": False}
    rows = []
    for event, case in runner.EXPECTED_EVENTS:
        reset = event == "common_reset_clears"
        healthy = event in ("healthy_admitted", "common_reset_recovery")
        runtime = event.startswith("late_") or event == "first_failure_preserved"
        rows.append(dict(event=event, case=str(case), global_reset_n=str(int(not reset)),
            pipeline_reset_n=str(int(healthy or runtime)), board_failed=str(int(not reset and not healthy)),
            board_fault="a7" if not reset and not healthy else "00", led7=str(int(not reset and not healthy)),
            physical_stub_awvalid=str(int(runtime)), capture_admit=str(int(healthy)), scan_enable=str(int(healthy)),
            external_fault=str(int(runtime)), ddr_reset_n=str(int(not reset))))
    save_rows(tmp_path, rows)
    (tmp_path / "summary.json").write_text(json.dumps(summary))
    return tmp_path, summary, rows


def test_accepts_complete_control_receipt(receipt):
    path, summary, rows = receipt
    assert runner.validate_results(path) == (summary, rows)


@pytest.mark.parametrize("mutation", ("missing_case", "startup_release", "aw_withdraw", "runtime_reset",
    "wrong_fault", "led_hidden", "admissions_continue", "ddr_reset", "hardware_claim", "datapath_claim"))
def test_rejects_unsafe_control_or_scope_claim(receipt, mutation):
    path, summary, rows = receipt
    if mutation == "missing_case": rows.pop()
    elif mutation == "hardware_claim": summary["HardwareAccessed"] = True
    elif mutation == "datapath_claim": summary["ActualSystemDatapathVerified"] = True
    elif mutation == "startup_release": rows[0]["pipeline_reset_n"] = "1"
    else:
        key, value = {"aw_withdraw": ("physical_stub_awvalid", "0"), "runtime_reset": ("pipeline_reset_n", "0"),
            "wrong_fault": ("board_fault", "a5"), "led_hidden": ("led7", "0"),
            "admissions_continue": ("capture_admit", "1"), "ddr_reset": ("ddr_reset_n", "0")}[mutation]
        rows[6][key] = value
    save_rows(path, rows);(path / "summary.json").write_text(json.dumps(summary))
    with pytest.raises(ValueError): runner.validate_results(path)


def test_control_runner_cannot_overwrite_or_escape_owned_output(tmp_path):
    with pytest.raises(ValueError, match="budget"): runner.run(tmp_path, 999)
    with pytest.raises(ValueError, match="fresh existing"): runner.run(tmp_path, 120)
