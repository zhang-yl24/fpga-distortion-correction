"""Synthetic CPU-only fixtures; no PDS execution or hardware access."""
from copy import deepcopy
from pathlib import Path
import json
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import prepare_checked_board1080_bitstream as tool


@pytest.fixture
def synthetic_admission(tmp_path, monkeypatch):
    project = tmp_path / "repo/distortion"
    final, receipt = project / tool.FINAL, project / tool.AUDIT
    final.parent.mkdir(parents=True)
    receipt.parent.mkdir(parents=True)
    final.write_bytes(b"Synthetic ADF; not native evidence")
    monkeypatch.setattr(tool, "FINAL_SHA256", tool.sha(final))
    result = {"Synthetic": True, "RecordedUTC": "synthetic timestamp",
              "AuditPassed": True, "AllReportedNativeTimingChecksMet": True,
              "TimingAccepted": False, "HardwareReleaseAllowed": False,
              "FinalRoutedADF": {"Path": str(final), "SHA256": tool.FINAL_SHA256},
              "EvidenceSHA256": {str(final): tool.FINAL_SHA256}, "Proof": {"all_fields": "checked"}}
    receipt.write_text(json.dumps(result))
    monkeypatch.setattr(tool, "AUDIT_SHA256", tool.sha(receipt))
    calls = []
    def replay(project):
        calls.append(project)
        value = deepcopy(result)
        value["RecordedUTC"] = "different synthetic time"
        return value
    monkeypatch.setattr(tool.checked, "audit", replay)
    return project, result, calls


def test_admission_replays_every_field_except_timestamp(synthetic_admission):
    project, result, calls = synthetic_admission
    saved, hashes = tool.admit(project)
    assert calls == [project] and saved == result
    assert hashes[str(project / tool.FINAL)] == tool.FINAL_SHA256


def synthetic_removed_rows():
    return [{"Corner": "slow", "Kind": "recovery", "Clocks": ["rst_clk", "phy_dq_clk_0"],
             "Before": {"Synthetic": True, "TotalChecks": 34}},
            {"Corner": "slow", "Kind": "recovery", "Clocks": ["board27", "rst_clk"],
             "Before": {"Synthetic": True, "TotalChecks": 1}}]


def test_canonicalize_only_confirmed_unordered_removed_rows():
    rows = synthetic_removed_rows()
    assert tool.canonical_replay({"RemovedResetSummaryRows": rows}) == tool.canonical_replay(
        {"RemovedResetSummaryRows": list(reversed(rows))})
    assert tool.canonical_replay({"OtherOrderedList": [1, 2]}) != tool.canonical_replay({"OtherOrderedList": [2, 1]})


def test_removed_row_duplicate_identity_is_rejected():
    rows = synthetic_removed_rows()
    with pytest.raises(ValueError, match="duplicate removed-reset"):
        tool.canonical_replay({"RemovedResetSummaryRows": rows + [deepcopy(rows[0])]})


def test_removed_row_numeric_or_extra_field_change_still_differs():
    before = {"RemovedResetSummaryRows": synthetic_removed_rows()}
    after = deepcopy(before)
    after["RemovedResetSummaryRows"][0]["Before"]["TotalChecks"] = 35
    assert tool.canonical_replay(before) != tool.canonical_replay(after)
    after = deepcopy(before)
    after["RemovedResetSummaryRows"][0]["ForgedField"] = True
    assert tool.canonical_replay(before) != tool.canonical_replay(after)


def test_admission_rejects_any_replayed_field_change(synthetic_admission, monkeypatch):
    project, result, _ = synthetic_admission
    changed = deepcopy(result)
    changed["Proof"]["all_fields"] = "forged"
    monkeypatch.setattr(tool.checked, "audit", lambda p: changed)
    with pytest.raises(ValueError, match="complete checked audit replay differs"):
        tool.admit(project)


@pytest.mark.parametrize("which", ["FINAL", "AUDIT"])
def test_admission_rejects_changed_fixed_files(synthetic_admission, which):
    project, _, _ = synthetic_admission
    (project / getattr(tool, which)).write_bytes(b"Synthetic tampering")
    with pytest.raises(ValueError, match="changed"):
        tool.admit(project)


def test_input_drift_rejected(tmp_path):
    path = tmp_path / "synthetic.v"
    path.write_text("Synthetic original")
    hashes = {str(path): tool.sha(path)}
    path.write_text("Synthetic modified")
    with pytest.raises(ValueError, match="SHA256 drift"):
        tool.check_hashes(hashes)


def tcl_runtime(runtime=True, response=None, error=False):
    tk = pytest.importorskip("tkinter")
    try:
        tcl = tk.Tcl()
    except tk.TclError as exc:
        pytest.skip(str(exc))
    calls = []
    tcl.eval("rename info original_info")
    tcl.eval("proc info {command args} {if {$command eq {script}} {return {" + ("synthetic.tcl" if runtime else "")
             + "}}; return [uplevel 1 [linsert $args 0 original_info $command]]}")
    for name in ("report_timing", "gen_bit_stream"):
        tcl.createcommand(name, lambda *args, _name=name: calls.append((_name, args)) or "")
    def run(*args):
        calls.append(("exec", args))
        if error:
            return tcl.call("error", "Synthetic gate failure")
        return response if response is not None else "CHECKED_PRE_BIT_NATIVE_AUDIT_PASS " + tool.FINAL_SHA256
    tcl.createcommand("exec", run)
    tcl.eval("rename puts original_puts")
    tcl.createcommand("puts", lambda *args: "")
    return tcl, calls


def tail():
    return tool.generation_tail("P:/distortion/build/board1080-timing/checked-bit-synthetic", "P:/.venv/Scripts/python.exe", "a" * 64)


def test_initial_parse_never_audits_or_generates():
    tcl, calls = tcl_runtime(runtime=False)
    tcl.eval(tail())
    assert [name for name, _ in calls] == ["report_timing"]


@pytest.mark.parametrize("response,error", [("wrong marker", False), (None, True),
    ("prefix CHECKED_PRE_BIT_NATIVE_AUDIT_PASS " + tool.FINAL_SHA256, False)])
def test_runtime_gate_failure_blocks_bitstream(response, error):
    tcl, calls = tcl_runtime(response=response, error=error)
    with pytest.raises(Exception):
        tcl.eval(tail())
    assert [name for name, _ in calls] == ["report_timing", "exec"]


def test_same_adf_is_reported_audited_then_generated():
    tcl, calls = tcl_runtime()
    tcl.eval(tail())
    assert [name for name, _ in calls] == ["report_timing", "exec", "gen_bit_stream"]
    report, gate, bit = [args for _, args in calls]
    assert report[report.index("-input_db_file") + 1] == bit[bit.index("-input_db_file") + 1]
    assert gate[-1] == "a" * 64
    assert "High Voltage" in bit and "UNUSED" in bit


def test_runtime_gate_is_ascii_and_contains_no_generation():
    raw = tool.runtime_gate()
    raw.encode("ascii")
    compile(raw, "synthetic-pre-bit-audit.py", "exec")
    assert "runtime_audit(work,sys.argv[1])" in raw and "gen_bit_stream" not in raw


def test_gate_rejects_wrong_config_hash_before_parsing(tmp_path):
    work = tmp_path / "distortion/build/board1080-timing/checked-bit-synthetic"
    work.mkdir(parents=True)
    (work / "pre-bit-inputs.json").write_text('{"Synthetic":true}')
    with pytest.raises(ValueError, match="config SHA256"):
        tool.runtime_audit(work, "0" * 64)


def test_prefix_requires_exact_unique_snapshot():
    with pytest.raises(ValueError, match="unique final snapshot"):
        tool.tcl_prefix("Synthetic unrelated Tcl")


@pytest.fixture
def synthetic_prepare(synthetic_admission, monkeypatch):
    project, result, _ = synthetic_admission
    work = project / "build/board1080-timing/checked-bit-synthetic"
    work.mkdir()
    python = project.parent / ".venv/Scripts/python.exe"
    python.parent.mkdir(parents=True)
    python.write_bytes(b"Synthetic Python executable")
    pds = project / "synthetic-pds.exe"
    pds.write_bytes(b"Synthetic PDS executable")
    source = project / "synthetic.v"
    source.write_text("Synthetic source")
    monkeypatch.setattr(tool.paths, "validate_repo_alias", lambda project, alias: "P:/")
    def prepare(p, w, **kwargs):
        compiled = w / "compiled/synthetic.v"
        compiled.parent.mkdir()
        compiled.write_bytes(source.read_bytes())
        alias = tool.paths.alias_path(p, "P:/", w)
        script = "# Synthetic declarations\ncompile -top_module board1080_top\nif {[file exists {P:/dummy.adf}]} {\n}\nreport_timing synthetic\n"
        plan = {"Synthetic": True, "Schema": tool.profile.SCHEMA, "AliasWorkDirectory": alias,
                "InputSHA256": {"synthetic.v": tool.sha(source)}, "RoleCounts": {"ManifestSources": 1},
                "CompiledInputs": [{"Source": "synthetic.v", "CompiledSHA256": tool.sha(source)}],
                "PDS": {"Executable": str(pds), "ExecutableSHA256": tool.sha(pds)}}
        (w / "timing.tcl").write_text(script, encoding="ascii")
        (w / "plan.json").write_text(json.dumps(plan))
        return plan
    monkeypatch.setattr(tool.profile, "prepare", prepare)
    return project, work, python, pds


def test_prepare_preserves_original_plan_tcl_and_binds_all_copies(synthetic_prepare):
    project, work, python, pds = synthetic_prepare
    plan = tool.prepare(project, work, python_executable=python, pds_shell=str(pds))
    assert (work / "plan.json").read_bytes() == (work / "source-plan.json").read_bytes()
    assert (work / "timing.tcl").read_bytes() == (work / "original-timing.tcl").read_bytes()
    assert "gen_bit_stream" not in (work / "timing.tcl").read_text()
    assert "gen_bit_stream" in (work / "bitstream.tcl").read_text()
    assert plan["HardwareReleaseAllowed"] is False and plan["EDAExecuted"] is False
    assert plan["CommandToRunSeparately"][2].endswith("/bitstream.tcl")
    tool.check_hashes(plan["InputSHA256"])
    assert json.loads((work / "bitstream-plan.json").read_text()) == plan
    with pytest.raises(ValueError, match="fresh existing child"):
        tool.prepare(project, work, python_executable=python, pds_shell=str(pds))


@pytest.fixture
def synthetic_timing(tmp_path, monkeypatch):
    project = tmp_path / "distortion"
    final_dir = project / Path(tool.FINAL).parent
    final_dir.mkdir(parents=True)
    hold = project / "build/board1080-timing/checked-hold-sta-1029-a/board1080_top.rtr"
    hold.parent.mkdir()
    report, exceptions = tmp_path / "new.rtr", tmp_path / "new_exception.rtr"
    for path in (final_dir / "board1080_top.rtr", final_dir / "board1080_top_exception.rtr", hold, report, exceptions):
        path.write_text("Synthetic CPU native parser stub fixture")
    table = {("slow", "setup"): {("cfg_clk", "cfg_clk"): {"Synthetic": True}}}
    state = {"tables": [deepcopy(table), deepcopy(table), deepcopy(table)], "clocks": [["SyntheticClock"]] * 3,
             "counts": [{"Synthetic": 245}, {"Synthetic": 245}]}
    def summaries(stream):
        return state["tables"].pop(0), state["clocks"].pop(0)
    monkeypatch.setattr(tool.checked.native, "parse_summaries", summaries)
    monkeypatch.setattr(tool.checked, "compare_summaries", lambda *args: ({"Synthetic": True}, 124, [], [{}] * 14))
    monkeypatch.setattr(tool.checked.fresh, "expected_paths", lambda p: ({"Synthetic": True}, {"Input": {"SHA256": "a" * 64}}, []))
    monkeypatch.setattr(tool.checked.native, "parse_false_paths", lambda s: {"Synthetic": True})
    monkeypatch.setattr(tool.checked.native, "validate_exception_sets", lambda *args: state["counts"].pop(0))
    return project, report, exceptions, state


def test_runtime_timing_gate_retains_new_report_inventory(synthetic_timing):
    project, report, exceptions, _ = synthetic_timing
    result = tool.timing_gate(project, report, exceptions)
    assert result["All124RetainedRowsUnchanged"] is True
    assert result["All14HDMIConfigurationRowsUnchanged"] is True


@pytest.mark.parametrize("change", ["row", "clock", "exception"])
def test_runtime_timing_gate_rejects_new_report_drift(synthetic_timing, change):
    project, report, exceptions, state = synthetic_timing
    if change == "row":
        state["tables"][1][("slow", "setup")][("cfg_clk", "cfg_clk")]["Synthetic"] = False
    elif change == "clock":
        state["clocks"][1] = ["ChangedSyntheticClock"]
    else:
        state["counts"][1] = {"Synthetic": 244}
    with pytest.raises(ValueError, match="differ"):
        tool.timing_gate(project, report, exceptions)
