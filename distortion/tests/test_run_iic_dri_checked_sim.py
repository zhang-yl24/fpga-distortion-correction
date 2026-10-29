"""Reject incomplete or misleading checked-I2C native simulation evidence."""
from pathlib import Path
import csv
import json
import sys
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import run_iic_dri_checked_sim as tool


def save_rows(path, rows):
    with (path / "iic-checked-cases.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=("id", "name", "expected_error", "observed_error",
            "read_data", "byte_over_count", "start_count", "stop_count", "elapsed_cycles"))
        writer.writeheader(); writer.writerows(rows)


@pytest.fixture
def receipt(tmp_path):
    summary = {"Passed": True, "Cases": len(tool.EXPECTED), "ClockHz": 10_000_000,
               "ConfiguredMaximumI2CHz": 400_000, "ActualDriverExecuted": True,
               "ParameterRejections": 8, "WideTimingArithmeticChecked": True,
               "OpenDrainSlaveModel": True, "HardwareAccessed": False,
               "MinimumSCLLowNs": 1400, "MinimumSCLHighNs": 1600,
               "MeasuredLowPhases": 84, "MeasuredHighPhases": 83}
    rows = [dict(id=str(i), name=name, expected_error=str(error), observed_error=str(error),
                 read_data=f"{read_data or 0:02x}", byte_over_count=str(over),
                 start_count=str(starts), stop_count=str(stops), elapsed_cycles="1000")
            for i, (name, error, over, starts, stops, read_data) in enumerate(tool.EXPECTED, 1)]
    (tmp_path / "summary.json").write_text(json.dumps(summary))
    save_rows(tmp_path, rows)
    return tmp_path, summary, rows


def test_requires_complete_wire_driver_case_receipt(receipt):
    path, summary, rows = receipt
    assert tool.validate_results(path) == (summary, rows)


@pytest.mark.parametrize("mutation", (
    "missing_case", "wrong_order", "wrong_error", "failed_completion", "wrong_read_data",
    "missing_stop", "false_start_stuck_bus", "unbounded_latency", "missing_repeat_start"))
def test_rejects_incomplete_or_incorrect_wire_results(receipt, mutation):
    path, _, rows = receipt
    if mutation == "missing_case": rows.pop()
    elif mutation == "wrong_order": rows[0], rows[1] = rows[1], rows[0]
    elif mutation == "wrong_error": rows[4]["observed_error"] = "0"
    elif mutation == "failed_completion": rows[5]["byte_over_count"] = "1"
    elif mutation == "wrong_read_data": rows[1]["read_data"] = "5a"
    elif mutation == "missing_stop": rows[3]["stop_count"] = "0"
    elif mutation == "false_start_stuck_bus": rows[8]["start_count"] = "1"
    elif mutation == "missing_repeat_start": rows[1]["start_count"] = "1"
    else: rows[8]["elapsed_cycles"] = "999999"
    save_rows(path, rows)
    with pytest.raises(ValueError): tool.validate_results(path)


@pytest.mark.parametrize("key,value", (
    ("HardwareAccessed", True), ("ActualDriverExecuted", False), ("OpenDrainSlaveModel", False),
    ("ParameterRejections", 0), ("WideTimingArithmeticChecked", False),
    ("MinimumSCLLowNs", 1280), ("MinimumSCLHighNs", 500), ("MeasuredLowPhases", 0),
    ("MinimumSCLLowNs", 1400.0), ("Passed", 1)))
def test_rejects_unsupported_scope_and_unmeasured_timing(receipt, key, value):
    path, summary, _ = receipt
    summary[key] = value
    (path / "summary.json").write_text(json.dumps(summary))
    with pytest.raises(ValueError): tool.validate_results(path)


def test_bounds_and_owned_output_location_checked_before_native_execution(tmp_path):
    with pytest.raises(ValueError, match="budget"): tool.run(tmp_path, 1000)
    with pytest.raises(ValueError, match="fresh existing"): tool.run(tmp_path, 120)
