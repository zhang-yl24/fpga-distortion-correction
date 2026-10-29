"""Binding and pre-bit runtime gate tests; never start PDS or hardware."""
from pathlib import Path
import copy
import hashlib
import json
import sys

import pytest

TOOLS = str(Path(__file__).resolve().parents[1] / "tools")
sys.path.insert(0, TOOLS)
try:
    import prepare_board1080_bitstream as tool
finally:
    sys.path.remove(TOOLS)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


@pytest.fixture
def evidence(tmp_path, monkeypatch):
    project = tmp_path / "repo/distortion"
    project.mkdir(parents=True)
    final = project / "build/repaired/input.adf"
    final.parent.mkdir(parents=True)
    final.write_bytes(b"CPU-only repaired ADF fixture")
    monkeypatch.setattr(tool, "FINAL_ADF_SHA256", sha(final))
    args = {}
    for family, parent in (("baseline", project / "build/baseline"), ("candidate", final.parent / "report")):
        parent.mkdir(parents=True, exist_ok=True)
        for kind, name in (("report", "board1080_top.rtr"), ("exceptions", "board1080_top_exception.rtr"), ("log", "stdout.log")):
            path = parent / name
            path.write_text(f"CPU-only {family} {kind} native fixture\n", encoding="ascii")
            args[family + "_" + kind] = path
    result = {"Schema": "board1080-ddr-final-native-audit-v1", **{key: True for key in tool.PASS_FLAGS},
              "HardwareReleaseAllowed": False, "PhysicalTimingReady": False,
              "FinalRoutedADF": {"Path": str(final), "SHA256": sha(final)},
              "ToolSHA256": sha(tool.timing.__file__), "FalsePathCounts": {"tested": 245},
              "CornerSummaries": {"ten_tables": "pass"}, "ExternalIOWarningEvidence": {"Identical": True},
              "InputsSHA256": {str(path): sha(path) for path in [final, *args.values()]}}
    audit = project / "audit.json"
    audit.write_text(json.dumps(result), encoding="utf-8")
    calls = []
    def audit_native(**kwargs):
        calls.append(kwargs)
        return copy.deepcopy(result)
    monkeypatch.setattr(tool.timing, "audit", audit_native)
    return project, final, audit, result, calls


def test_passed_receipt_is_recomputed_from_both_bound_native_report_sets(evidence):
    project, final, receipt, result, calls = evidence
    args, watched = tool.native_arguments(project, final, receipt)
    assert len(calls) == 1
    assert calls[0]["final_adf"] == final
    assert args["candidate_report"].parent == final.parent / "report"
    assert args["baseline_report"].parent == project / "build/baseline"
    assert watched[final] == result["FinalRoutedADF"]["SHA256"]


@pytest.mark.parametrize("mutation", ("wrong_adf", "stale_report", "false_flag", "forged_summary", "wrong_binding", "changed_tool"))
def test_stale_or_forged_receipt_is_rejected(evidence, mutation):
    project, final, receipt, result, calls = evidence
    if mutation == "wrong_adf":
        final.write_bytes(b"another ADF")
    elif mutation == "stale_report":
        (final.parent / "report/board1080_top.rtr").write_text("changed")
    else:
        value = json.loads(receipt.read_text())
        if mutation == "false_flag":
            value["ExactExceptionPathEffectsVerified"] = False
        elif mutation == "forged_summary":
            value["CornerSummaries"] = {"forged": True}
        elif mutation == "wrong_binding":
            value["FinalRoutedADF"]["Path"] = str(final.with_name("other.adf"))
        else:
            value["ToolSHA256"] = "0" * 64
        receipt.write_text(json.dumps(value))
    with pytest.raises(ValueError):
        tool.native_arguments(project, final, receipt)


def tcl_runtime(monkeypatch, *, runtime, response="pass", error=False):
    tk = pytest.importorskip("tkinter")
    try:
        tcl = tk.Tcl()
    except tk.TclError as exc:
        pytest.skip(str(exc))
    calls = []
    tcl.eval("rename info original_info")
    tcl.eval("proc info {command args} {if {$command eq {script}} {return {" + ("runtime.tcl" if runtime else "")
             + "}}; return [uplevel 1 [linsert $args 0 original_info $command]]}")
    for name in ("report_timing", "gen_bit_stream"):
        tcl.createcommand(name, lambda *args, _name=name: calls.append((_name, args)) or "")
    def run_audit(*args):
        calls.append(("exec", args))
        if error:
            return tcl.call("error", "native pre-bit audit failed")
        return "PRE_BIT_NATIVE_AUDIT_PASS " + tool.FINAL_ADF_SHA256 if response == "pass" else response
    tcl.createcommand("exec", run_audit)
    tcl.eval("rename puts original_puts")
    tcl.createcommand("puts", lambda *args: "")
    return tcl, calls


def test_initial_pds_parse_does_not_audit_or_generate(monkeypatch):
    tcl, calls = tcl_runtime(monkeypatch, runtime=False)
    tcl.eval(tool.generation_tail("P:/distortion/build/board1080-timing/fresh", "P:/.venv/Scripts/python.exe"))
    assert [name for name, _ in calls] == ["report_timing"]


@pytest.mark.parametrize("failure", ("wrong_marker", "audit_error"))
def test_runtime_audit_failure_never_reaches_bit_generation(monkeypatch, failure):
    tcl, calls = tcl_runtime(monkeypatch, runtime=True, response="not the expected audit marker", error=failure == "audit_error")
    with pytest.raises(Exception):
        tcl.eval(tool.generation_tail("P:/distortion/build/board1080-timing/fresh", "P:/.venv/Scripts/python.exe"))
    assert [name for name, _ in calls] == ["report_timing", "exec"]


def test_runtime_success_uses_the_same_adf_after_audit(monkeypatch):
    tcl, calls = tcl_runtime(monkeypatch, runtime=True)
    tcl.eval(tool.generation_tail("P:/distortion/build/board1080-timing/fresh", "P:/.venv/Scripts/python.exe"))
    assert [name for name, _ in calls] == ["report_timing", "exec", "gen_bit_stream"]
    report, _, bit = calls
    assert report[1][report[1].index("-input_db_file") + 1] == bit[1][bit[1].index("-input_db_file") + 1]
    assert "High Voltage" in bit[1] and "UNUSED" in bit[1]
    assert "-max_path" in report[1] and "1000" in report[1] and "4" in report[1]


def test_runtime_python_gate_is_ascii_and_rechecks_inputs_after_native_audit():
    gate = tool.runtime_gate()
    gate.encode("ascii")
    compile(gate, "pre-bit-audit.py", "exec")
    assert gate.count("verify()") == 3  # declaration and before/after native audit
    assert "with (work/'pre-bit-audit.json').open('x'" in gate
    assert "gen_bit_stream" not in gate


def test_actual_local_audit_when_available():
    project = Path(__file__).resolve().parents[1]
    final = project / "build/ddr-timing-repair/reproduced-c/input.adf"
    receipt = project / "results/board1080-ddr-final-20261029.json"
    if not final.is_file() or not receipt.is_file():
        pytest.skip("local ADF is not distributed")
    frozen = json.loads(receipt.read_text(encoding="utf-8-sig"))
    bound_inputs = [Path(frozen["FinalRoutedADF"]["Path"]),
                    *(Path(name) for name in frozen["InputsSHA256"])]
    if any(not path.is_file() for path in bound_inputs):
        pytest.skip("frozen local audit inputs unavailable after workspace rename; receipt is not rebased")
    args, watched = tool.native_arguments(project, final, receipt)
    assert len(watched) >= 8 and args["candidate_report"].is_file()
