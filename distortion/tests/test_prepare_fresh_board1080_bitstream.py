"""Fresh native receipt/source closure and runtime gate tests; no EDA."""
from pathlib import Path
import copy
import json
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import prepare_fresh_board1080_bitstream as tool


@pytest.fixture
def evidence(tmp_path, monkeypatch):
    project = tmp_path / "repo/distortion"
    final = project / "build/repaired/input.adf"
    final.parent.mkdir(parents=True)
    final.write_bytes(b"fresh repaired fixture")
    monkeypatch.setattr(tool, "FINAL_ADF_SHA256", tool.closure.sha(final))
    args = {}
    for family, parent, log in (("baseline", project/"build/baseline", "query.log"),
                                ("candidate", final.parent/"report", "stdout.log")):
        parent.mkdir(parents=True, exist_ok=True)
        for kind, name in (("report","board1080_top.rtr"),
                           ("exceptions","board1080_top_exception.rtr"),("log",log)):
            path = parent/name
            path.write_text(f"CPU fixture {family} {kind}\n")
            args[family+"_"+kind] = path
    helpers = [project/"tools"/f"audit{i}.py" for i in range(4)]
    helpers[0].parent.mkdir()
    for path in helpers:
        path.write_text("# CPU-only helper fixture\n")
    monkeypatch.setattr(tool, "audit_tools", lambda: helpers)
    result = {"Schema":"board1080-fresh-ddr-final-native-audit-v1",
              **{key:True for key in tool.PASS_FLAGS},
              "HardwareReleaseAllowed":False, "PhysicalTimingReady":False,
              "FinalRoutedADF":{"Path":str(final),"SHA256":tool.closure.sha(final)},
              "ToolsSHA256":{str(path):tool.closure.sha(path) for path in helpers},
              "InputsSHA256":{str(path):tool.closure.sha(path) for path in [final,*args.values()]},
              "FalsePathCounts":{"checked":245},
              "CornerSummaries":{"all10":"pass"},
              "ExternalIOWarningEvidence":{"Identical":True},
              "BaselineRecoveryVariantEvidence":{"raw_per_corner":251},
              "BaselineEntryPaths":["entry slow","entry fast"],
              "InternalResetChecksPerCorner":244,
              "EntryResetChecksPerCorner":1,
              "BaselineInternalNativeVariantsPerCorner":251}
    receipt = project/"audit.json"
    receipt.write_text(json.dumps(result))
    calls = []
    def native(**kwargs):
        calls.append(kwargs)
        return copy.deepcopy(result)
    monkeypatch.setattr(tool.timing, "audit", native)
    return project, final, receipt, result, calls


def test_fresh_receipt_replays_exact_reports_query_log_and_four_audit_tools(evidence):
    project, final, receipt, evidence, calls = evidence
    args, watched = tool.native_arguments(project, final, receipt)
    assert len(calls) == 1
    assert args["baseline_log"].name == "query.log"
    assert args["candidate_log"].name == "stdout.log"
    assert calls[0]["expected_adf_sha256"] == tool.FINAL_ADF_SHA256
    assert len(watched) == 12


@pytest.mark.parametrize("mutation", ("old_schema","old_adf","failed","hardware","binding",
                                     "tool_hash","missing_tool","extra_tool","report_changed",
                                     "query_log_missing","curated_variants","curated_entries","summary"))
def test_wrong_profile_or_forged_evidence_rejects(evidence, mutation):
    project, final, receipt, result, calls = evidence
    data = copy.deepcopy(result)
    if mutation == "old_schema":
        data["Schema"] = "board1080-ddr-final-native-audit-v1"
    elif mutation == "old_adf":
        final.write_bytes(b"old candidate")
    elif mutation == "failed":
        data["AuditPassed"] = False
    elif mutation == "hardware":
        data["HardwareReleaseAllowed"] = True
    elif mutation == "binding":
        data["FinalRoutedADF"]["Path"] = str(final.with_name("other.adf"))
    elif mutation == "tool_hash":
        data["ToolsSHA256"][next(iter(data["ToolsSHA256"]))] = "0"*64
    elif mutation == "missing_tool":
        data["ToolsSHA256"].pop(next(iter(data["ToolsSHA256"])))
    elif mutation == "extra_tool":
        data["ToolsSHA256"][str(project/"extra.py")] = "0"*64
    elif mutation == "report_changed":
        (final.parent/"report/board1080_top.rtr").write_text("changed")
    elif mutation == "query_log_missing":
        data["InputsSHA256"].pop(str(project/"build/baseline/query.log"))
    elif mutation == "curated_variants":
        data["BaselineRecoveryVariantEvidence"] = {}
    elif mutation == "curated_entries":
        data["BaselineEntryPaths"] = []
    else:
        data["CornerSummaries"] = {}
    receipt.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        tool.native_arguments(project, final, receipt)


@pytest.fixture
def source_profile(tmp_path, monkeypatch):
    project = tmp_path/"distortion"
    source_dir = project/"rtl"
    source_dir.mkdir(parents=True)
    plan_path = project/tool.SOURCE_PLAN
    plan_path.parent.mkdir(parents=True)
    originals, compiled, hashes = {}, [], {}
    for index in range(109):
        name = f"rtl/source{index}.v"
        source = project/name
        source.write_text(f"module m{index}; endmodule\n")
        copy_path = plan_path.parent/"compiled"/name
        copy_path.parent.mkdir(parents=True, exist_ok=True)
        copy_path.write_bytes(source.read_bytes())
        originals[name] = hashes[name] = tool.closure.sha(source)
        compiled.append({"Source":name,"OriginalSHA256":hashes[name],
                         "CompiledSHA256":tool.closure.sha(copy_path)})
    adf = plan_path.parent/"place_route/board1080_top_pnr.adf"
    adf.parent.mkdir()
    adf.write_bytes(b"fresh source fixture")
    monkeypatch.setattr(tool, "SOURCE_ADF_SHA256",tool.closure.sha(adf))
    data = {"Schema":"board1080-timing-preparation-v1","InputSHA256":hashes,"CompiledInputs":compiled}
    plan_path.write_text(json.dumps(data))
    monkeypatch.setattr(tool, "SOURCE_PLAN_SHA256",tool.closure.sha(plan_path))
    roles = {"SourceSHA256":originals,"ConstraintSHA256":{},"AuxiliarySHA256":{}}
    return project, plan_path, data, roles


def test_source_profile_binds_originals_compiled_copies_and_routed_adf(source_profile):
    project, plan_path, data, roles = source_profile
    watched = tool.bind_source_closure(project,roles)
    assert len(watched) == 220
    assert plan_path in watched


@pytest.mark.parametrize("mutation",("source","compiled","adf","current_roles","missing_compiled","plan"))
def test_source_profile_rejects_drift_or_missing_coverage(source_profile, monkeypatch, mutation):
    project, plan_path, data, roles = source_profile
    if mutation == "source":
        (project/"rtl/source0.v").write_text("changed")
    elif mutation == "compiled":
        (plan_path.parent/"compiled/rtl/source0.v").write_text("changed")
    elif mutation == "adf":
        (plan_path.parent/"place_route/board1080_top_pnr.adf").write_bytes(b"changed")
    elif mutation == "current_roles":
        roles["SourceSHA256"]["rtl/source0.v"] = "0"*64
    elif mutation == "missing_compiled":
        data["CompiledInputs"].pop()
        plan_path.write_text(json.dumps(data))
        monkeypatch.setattr(tool, "SOURCE_PLAN_SHA256",tool.closure.sha(plan_path))
    else:
        plan_path.write_text("{}")
    with pytest.raises(ValueError):
        tool.bind_source_closure(project,roles)


def tcl_runtime(runtime, response="pass", error=False):
    tk = pytest.importorskip("tkinter")
    try:
        tcl = tk.Tcl()
    except tk.TclError as exc:
        pytest.skip(str(exc))
    calls = []
    tcl.eval("rename info original_info")
    tcl.eval("proc info {command args} {if {$command eq {script}} {return {" + ("runtime.tcl" if runtime else "")
             + "}}; return [uplevel 1 [linsert $args 0 original_info $command]]}")
    for name in ("report_timing","gen_bit_stream"):
        tcl.createcommand(name,lambda *args,_name=name:calls.append((_name,args)) or "")
    def run(*args):
        calls.append(("exec",args))
        if error:
            return tcl.call("error","fresh audit failed")
        return "PRE_BIT_NATIVE_AUDIT_PASS " + tool.FINAL_ADF_SHA256 if response == "pass" else response
    tcl.createcommand("exec",run)
    tcl.eval("rename puts original_puts")
    tcl.createcommand("puts",lambda *args:"")
    return tcl,calls


def test_initial_parse_never_executes_audit_or_generation():
    tcl,calls = tcl_runtime(False)
    tcl.eval(tool.generation_tail("P:/work","P:/python.exe"))
    assert [name for name,_ in calls] == ["report_timing"]


@pytest.mark.parametrize("failure",("old_profile_marker","audit_error"))
def test_failed_gate_cannot_generate_bitstream(failure):
    tcl,calls = tcl_runtime(True,response="PRE_BIT_NATIVE_AUDIT_PASS "+tool.previous.FINAL_ADF_SHA256,
                            error=failure == "audit_error")
    with pytest.raises(Exception):
        tcl.eval(tool.generation_tail("P:/work","P:/python.exe"))
    assert [name for name,_ in calls] == ["report_timing","exec"]


def test_success_uses_same_adf_and_fresh_hash_after_audit():
    tcl,calls = tcl_runtime(True)
    tcl.eval(tool.generation_tail("P:/work","P:/python.exe"))
    assert [name for name,_ in calls] == ["report_timing","exec","gen_bit_stream"]
    report,_,bit = calls
    assert report[1][report[1].index("-input_db_file")+1] == bit[1][bit[1].index("-input_db_file")+1]
    assert "1000" in report[1] and "4" in report[1]


def test_python_gate_reaudits_fresh_profile_and_rechecks_all_hashes():
    gate = tool.runtime_gate()
    compile(gate,"pre-bit-audit.py","exec")
    gate.encode("ascii")
    assert "import audit_fresh_ddr_timing as timing" in gate
    assert gate.count("verify()") == 3
    assert "with (work/'pre-bit-audit.json').open('x'" in gate
    assert "gen_bit_stream" not in gate
    assert "import audit_ddr_final_timing as timing" in tool.previous.runtime_gate()


def test_actual_local_fresh_binding_when_available():
    project = Path(__file__).resolve().parents[1]
    final = project/"build/ddr-timing-repair/fresh-repaired-1029-a/input.adf"
    receipt = final.parent/"final-audit-pinned.json"
    if not receipt.is_file():
        pytest.skip("native build is not distributed")
    arguments,watched = tool.native_arguments(project,final,receipt)
    assert arguments["baseline_log"].name == "query.log"
    assert len(watched) == 12
    assert len(tool.bind_source_closure(project,tool.closure.validate_manifest(project))) == 224
