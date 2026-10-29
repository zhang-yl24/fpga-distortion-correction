"""Check that incomplete or altered emitted register traces cannot pass."""
from pathlib import Path
import csv
import json
import sys
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import run_board1080_hdmi30_sim as tool


@pytest.fixture
def outputs(tmp_path):
    summary = {"Passed": True, "Epochs": 2, "InitialWritesPerEpoch": 300,
               "EDIDWritesPerEpoch": 264, "SettingWritesPerEpoch": 7,
               "ResetReplayPassed": True, "VariableBusyDelaysExercised": True,
               "ActualControllerExecuted": True, "PhysicalI2CVerified": False}
    (tmp_path / "summary.json").write_text(json.dumps(summary))
    rows = []
    commands = tool.edid.command_rows(tool.ROOT / tool.CONTROLLER)
    for epoch in (1, 2):
        entries = [(-1, 1, 3, 0x5A, 0), (-1, 0, 3, 0x5A, 0x5A)]
        entries += [(index, 1, addr, data, 0) for index, addr, data in commands[:300]]
        entries += [(-1, 0, 0x209C + i % 4, 0, 2 if i == 6 else 0) for i in range(8)]
        entries += [(index, 1, addr, data, 0) for index, addr, data in commands[304:311]]
        for number, (index, write, addr, data, response) in enumerate(entries):
            rows.append(dict(epoch=str(epoch), index=str(index), write=str(write), addr=f"{addr:04x}",
                             data=f"{data:02x}", response=f"{response:02x}", busy_cycles=str(12 + number % 5 * 7)))
    save_rows(tmp_path, rows)
    return tmp_path, summary, rows


def save_rows(path, rows):
    with (path / "hdmi30-commands.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=("epoch", "index", "write", "addr", "data", "response", "busy_cycles"))
        writer.writeheader(); writer.writerows(rows)


def test_full_two_epoch_controller_trace_is_required(outputs):
    path, _, rows = outputs
    summary, actual = tool.validate_results(path)
    assert summary["ActualControllerExecuted"] and actual == rows
    assert summary["PhysicalI2CVerified"] is False


@pytest.mark.parametrize("mutation", ("missing_edid", "wrong_edid", "missing_setting", "extra_write", "no_reset", "no_busy", "wrong_id", "wrong_status"))
def test_missing_or_changed_bus_requests_cannot_pass(outputs, mutation):
    path, _, rows = outputs
    target = next(row for row in rows if row["index"] == "54")
    if mutation == "missing_edid": rows.remove(target)
    elif mutation == "wrong_edid": target["data"] = f"{int(target['data'],16)^1:02x}"
    elif mutation == "missing_setting": rows.remove(next(row for row in rows if row["index"] == "310"))
    elif mutation == "extra_write": rows.append(dict(target))
    elif mutation == "no_reset": rows[:] = [row for row in rows if row["epoch"] == "1"]
    elif mutation == "no_busy":
        for row in rows: row["busy_cycles"] = "12"
    elif mutation == "wrong_id": next(row for row in rows if row["write"] == "0")["response"] = "00"
    else: next(row for row in rows if row["addr"] == "209c")["addr"] = "209d"
    save_rows(path, rows)
    with pytest.raises(ValueError): tool.validate_results(path)


def test_test_model_cannot_claim_physical_i2c_acceptance(outputs):
    path, summary, _ = outputs
    summary["PhysicalI2CVerified"] = True
    (path / "summary.json").write_text(json.dumps(summary))
    with pytest.raises(ValueError, match="scope"):
        tool.validate_results(path)


@pytest.mark.parametrize("mutation", ("never_ready", "reads_after_settings", "epochs_interleaved", "delay_reordered"))
def test_global_order_and_ready_transition_are_required(outputs, mutation):
    path, _, rows = outputs
    if mutation == "never_ready":
        for row in rows:
            if row["write"] == "0" and row["addr"] != "0003":
                row["response"] = "00"
    elif mutation == "reads_after_settings":
        rows.sort(key=lambda row: (row["epoch"], -int(row["write"])))
    elif mutation == "epochs_interleaved":
        midpoint = len(rows) // 2
        rows[1], rows[midpoint] = rows[midpoint], rows[1]
    else:
        rows[0]["busy_cycles"], rows[1]["busy_cycles"] = rows[1]["busy_cycles"], rows[0]["busy_cycles"]
    save_rows(path, rows)
    with pytest.raises(ValueError, match="ordered"):
        tool.validate_results(path)


def test_vectors_are_exclusive_and_include_every_command_and_byte(tmp_path):
    hashes = tool.write_vectors(tmp_path)
    assert len((tmp_path / "edid_expected.hex").read_text().splitlines()) == 256
    assert len((tmp_path / "commands_expected.hex").read_text().splitlines()) == 311
    assert all(tool.edid.sha(tmp_path / name) == digest for name, digest in hashes.items())
    with pytest.raises(FileExistsError): tool.write_vectors(tmp_path)


def test_invalid_runtime_budget_and_existing_output_are_rejected(tmp_path):
    with pytest.raises(ValueError, match="budget"): tool.run(tmp_path, 999)
    with pytest.raises(ValueError, match="fresh existing"): tool.run(tmp_path, 120)
