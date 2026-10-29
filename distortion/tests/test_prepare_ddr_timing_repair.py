"""Exercise binding, narrow scope and PDS parse/runtime separation without EDA."""
from pathlib import Path
import copy
import hashlib
import json
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import prepare_ddr_timing_repair as tool


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def native_fixture(project):
    original = Path(__file__).resolve().parents[1] / "results/board1080-native-recovery-20261029.json"
    data = json.loads(original.read_text(encoding="utf-8"))
    lines = ["| Design : board1080_top\n", "| Device : PG2L100H\n",
             "| Speed Grade : -6\n", "| Package : FBG676\n"]
    for corner in ("slow", "fast"):
        lines.append("Recovery Summary(" + corner.title() + " Corner):\n")
        for group in data["SixClockPairs"]:
            row = group["Corners"][corner]
            lines.append(f"{group['LaunchClock']} {group['CaptureClock']} {row['WNS']} {row['TNS']} {row['Failing']} {row['Total']}\n")
    for row in data["FullNativeRecoveryPaths"]:
        lines.extend([
            f"Startpoint  : {row['Source']}\n", f"Endpoint    : {row['Endpoint']}\n",
            f"Path Group  : {row['CaptureClock']}\n", f"Path Type   : max ({row['Corner']} corner)\n",
            "Path Class  : async timing path\n",
            f" Clock {row['LaunchClock']} ({row['LaunchEdge']} edge) 0.000\n",
            f" Clock {row['CaptureClock']} ({row['CaptureEdge']} edge) 0.000\n",
            " Recovery time -0.100\n", f" Slack ({row['SlackState']}) {row['Slack']}\n"])
    report = project / "native.rtr"
    report.write_text("".join(lines), encoding="utf-8")
    data["Input"] = {"Path": str(report), "SHA256": sha(report)}
    evidence = project / "native.json"
    evidence.write_text(json.dumps(data), encoding="utf-8")
    groups = {}
    for row in data["ExactCandidatePairs"] + data["ExcludedPendingCPD"]:
        groups.setdefault(row["Source"], set()).add(row["Endpoint"])
    return evidence, report, groups


def matches(groups):
    groups = dict(groups)
    groups[tool.ENTRY_SOURCE] = {tool.ENTRY_TARGET}
    return [{"Count": len(names), "NativeNames": ["t:" + name for name in names]}
            for source, targets in groups.items() for names in ([source], sorted(targets))]


@pytest.fixture
def prepared_inputs(tmp_path, monkeypatch):
    project = tmp_path / "repo/distortion"
    project.mkdir(parents=True)
    source = project / "original.adf"
    source.write_bytes(b"CPU fixture baseline, never an executable database")
    monkeypatch.setattr(tool, "BASELINE_SHA256", sha(source))
    evidence, report, groups = native_fixture(project)
    export = project / "entry-sim.v"
    export.write_text("CPU fixture checked by the separately tested entry auditor", encoding="ascii")
    monkeypatch.setattr(tool, "ENTRY_EXPORT_SHA256", sha(export))
    result = {"Status": "pass", "FirstStageFunctionalFanout": 1, "OutputLoadCount": 14}
    audit = project / "entry.json"
    audit.write_text(json.dumps({**result, "Input": {"Path": str(export), "SHA256": sha(export)}}))
    monkeypatch.setattr(tool.entry, "audit_text", lambda _: result)
    log = project / "query.log"
    records = matches(groups)
    log.write_text("\n".join("I: Timing-5001: The pattern 'exact' in command 'get_pins -hierarchical -regexp exact' "
                             f"match {record['Count']} objects below: " + " ".join(record["NativeNames"])
                             for record in records) + "\n", encoding="ascii")
    hdl, fdc = project / "rtl/source.v", project / "board/source.fdc"
    hdl.parent.mkdir(); fdc.parent.mkdir()
    hdl.write_text("module source; endmodule\n", encoding="ascii")
    fdc.write_text("# original diagnostic constraints\n", encoding="ascii")
    roles = {"SourceSHA256": {"rtl/source.v": sha(hdl)},
             "ConstraintSHA256": {"board/source.fdc": sha(fdc)}, "AuxiliarySHA256": {}}
    monkeypatch.setattr(tool, "PROFILE_HASHES", {"board/source.fdc": sha(fdc)})
    monkeypatch.setattr(tool.closure, "validate_manifest", lambda _: roles)
    monkeypatch.setattr(tool.closure, "validate_repo_alias", lambda _project, alias: tool.closure.alias_format(alias))
    executable = project / "pds_shell.exe"
    executable.write_bytes(b"CPU fixture: never execute")
    output = project / "build/ddr-timing-repair/candidate"
    return {"project": project, "source": source, "evidence": evidence, "report": report,
            "audit": audit, "log": log, "groups": groups, "executable": executable,
            "output": output, "roles": roles, "hdl": hdl}


def prepare(values):
    return tool.prepare(values["project"], values["source"], values["evidence"], values["audit"],
                        values["log"], values["output"], pds_shell=values["executable"])


def test_exact_bound_copy_and_separate_commands(prepared_inputs):
    values = prepared_inputs
    original = values["source"].read_bytes()
    result = prepare(values)
    assert values["source"].read_bytes() == original
    assert (values["output"] / "input.adf").read_bytes() == original
    assert result["EDAExecuted"] is False and result["TimingAccepted"] is False
    assert result["InternalExactSourceEndpointPairs"] == 126
    assert result["InternalResetChecksPerCorner"] == 244
    assert result["IndependentEntryChecksPerCorner"] == 1
    assert len(result["CommandsRunSeparatelyInOrder"]) == 2
    assert len(result["ExactQueries"]) == 5
    for name, digest in result["FilesSHA256"].items():
        assert sha(values["output"] / name) == digest
    repair = (values["output"] / "repair.tcl").read_text(encoding="ascii")
    report = (values["output"] / "report.tcl").read_text(encoding="ascii")
    assert "save_adif\n" in repair and "save_adif -file_name" not in repair
    assert "mpnr_report_timing" not in repair
    assert "manual_route" not in report and "save_adif" not in report
    assert "-max_path 1000 -nworst 4 -report_exception TRUE" in report
    assert "file copy" in report and "pre-sta-repaired.adf" in report
    assert "ZDNE[0]:SRB_342_582>IDNE[0]:SRB_348_588;" in repair
    assert str(values["source"]) not in repair
    assert "gen_bit_stream" not in repair + report


def test_wrong_adf_hash_rejects_before_output(prepared_inputs):
    values = prepared_inputs
    values["source"].write_bytes(b"different build or wrong net mapping")
    with pytest.raises(ValueError, match="audited baseline"):
        prepare(values)
    assert not values["output"].exists()


def test_source_outside_project_rejected(prepared_inputs):
    values = prepared_inputs
    outside = values["project"].parent / "outside.adf"
    outside.write_bytes(values["source"].read_bytes())
    with pytest.raises(ValueError, match="inside distortion"):
        tool.source_bytes(values["project"], outside)


def test_non_adf_rejected_even_with_matching_bytes(prepared_inputs):
    values = prepared_inputs
    wrong = values["source"].with_suffix(".prr")
    wrong.write_bytes(values["source"].read_bytes())
    with pytest.raises(ValueError, match="must be an ADF"):
        tool.source_bytes(values["project"], wrong)


def test_report_device_mismatch_rejected(prepared_inputs):
    values = prepared_inputs
    report = values["report"]
    report.write_text(report.read_text().replace("PG2L100H", "PG2L200H"))
    evidence = json.loads(values["evidence"].read_text())
    evidence["Input"]["SHA256"] = sha(report)
    values["evidence"].write_text(json.dumps(evidence))
    with pytest.raises(ValueError, match="device/design"):
        prepare(values)


def test_native_report_hash_mismatch_rejected(prepared_inputs):
    values = prepared_inputs
    with values["report"].open("a") as stream:
        stream.write("changed native evidence\n")
    with pytest.raises(ValueError, match="report SHA256"):
        prepare(values)


def test_curated_scope_change_cannot_hide_behind_report_hash(prepared_inputs):
    values = prepared_inputs
    evidence = json.loads(values["evidence"].read_text())
    evidence["FullNativeRecoveryPaths"][0]["Endpoint"] = tool.ENTRY_TARGET
    values["evidence"].write_text(json.dumps(evidence))
    with pytest.raises(ValueError, match="curated native paths differ"):
        prepare(values)


def test_changed_scope_identity_rejects_an_otherwise_complete_report(prepared_inputs):
    values = prepared_inputs
    report = values["report"]
    original = next(iter(values["groups"].values()))
    target = next(pin for pin in original if pin.endswith("/opit_1/OSR_IOLHR"))
    changed = target.replace("/opit_1/", "/other_actual_cell/")
    report.write_text(report.read_text().replace(target, changed))
    evidence = json.loads(values["evidence"].read_text())
    evidence["Input"]["SHA256"] = sha(report)
    for row in evidence["FullNativeRecoveryPaths"]:
        if row["Endpoint"] == target:
            row["Endpoint"] = changed
    values["evidence"].write_text(json.dumps(evidence))
    with pytest.raises(ValueError, match="exact repair profile"):
        prepare(values)


@pytest.mark.parametrize("kind", ["missing", "wrong_name", "wrong_count"])
def test_incomplete_native_name_proof_rejected(prepared_inputs, kind):
    values = prepared_inputs
    records = matches(values["groups"])
    if kind == "missing":
        records.pop()
    elif kind == "wrong_name":
        records[0]["NativeNames"] = ["t:outside/reset/CLK"]
    else:
        records[0]["Count"] = 2
    with pytest.raises(ValueError, match="native object"):
        tool.make_scopes(values["groups"], records)


def test_changed_source_closure_rejected(prepared_inputs):
    values = prepared_inputs
    values["hdl"].write_text("module source; wire new_logic; endmodule\n")
    with pytest.raises(ValueError, match="bound input changed"):
        prepare(values)
    assert not values["output"].exists()


def test_new_matching_manifest_cannot_rebind_old_routed_profile(prepared_inputs):
    values = prepared_inputs
    changed = values["project"] / "board/source.fdc"
    changed.write_text("# changed constraints, even if a new manifest records them\n")
    values["roles"]["ConstraintSHA256"]["board/source.fdc"] = sha(changed)
    with pytest.raises(ValueError, match="exact routed baseline"):
        prepare(values)
    assert not values["output"].exists()


@pytest.mark.parametrize("name", ["../outside", "nested/candidate", "bad name"])
def test_unsafe_output_rejected(prepared_inputs, name):
    values = prepared_inputs
    with pytest.raises(ValueError, match="direct, nonlinked"):
        tool.fresh_output(values["project"], values["output"].parent / name)


def test_existing_work_is_not_reused(prepared_inputs):
    values = prepared_inputs
    values["output"].mkdir(parents=True)
    (values["output"] / "retained.log").write_text("keep")
    with pytest.raises(ValueError, match="fresh or empty"):
        prepare(values)
    assert (values["output"] / "retained.log").read_text() == "keep"


def test_pds_initial_parse_runs_no_mutating_native_commands():
    tkinter = pytest.importorskip("tkinter")
    try:
        tcl = tkinter.Tcl()
    except tkinter.TclError as exc:
        pytest.skip(str(exc))
    calls = []
    for command in ("set_arch", "add_design", "mpnr", "unroute", "manual_route", "save_adif", "mpnr_report_timing"):
        tcl.createcommand(command, lambda *args, _name=command: calls.append((_name, args)) or "")
    repair, report = tool.make_scripts("P:/distortion/build/ddr-timing-repair/test")
    tcl.eval(repair)
    tcl.eval(report)
    assert [name for name, _ in calls] == ["set_arch", "add_design", "set_arch", "add_design"]


def test_scope_contains_only_reset_destinations(prepared_inputs):
    values = prepared_inputs
    fdc, queries = tool.make_scopes(values["groups"], matches(values["groups"]))
    assert fdc.count("set_false_path -from") == 5
    assert "get_clocks" not in fdc and "set_clock_groups" not in fdc
    assert ":CLK" not in fdc and "TX_DATA" not in fdc
    assert sorted(q["ExpectedTargetCount"] for q in queries) == [1, 1, 7, 14, 104]
    assert sum(q["EntryRDC"] for q in queries) == 1
