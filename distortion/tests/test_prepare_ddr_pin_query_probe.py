"""Exercise generated Tcl in-process with mocked queries, never PDS or hardware."""
from pathlib import Path
import json
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import prepare_ddr_pin_query_probe as probe


def objects():
    values = {"Sources": {}, "CandidateTargets": {}}
    for family, (parent, _, _) in probe.reset.SOURCES.items():
        values["Sources"][family] = {"ActualClockPin": parent + "/actual_alias:CLK"}
        pin = {"dqs_reset": "ISR_IOLHR", "iol_reset": "TSR", "training_reset": "RST_TRAINING_N"}[family]
        values["CandidateTargets"][family] = [probe.reset.SLICE_PREFIX + f"mock_group[{i}].{family}/cell:{pin}"
                                               for i in range(probe.reset.EXPECTED_GROUPS[family])]
    return values


def interpreter(tmp_path, expected, *, returned="exact", map_exists=True):
    tk = pytest.importorskip("tkinter")
    try:
        tcl = tk.Tcl()
    except tk.TclError as exc:
        pytest.skip(f"Tcl runtime unavailable: {exc}")
    log = tmp_path / "runtime-query.log"
    stdout, queries = [], []
    _, request = probe.reset.make_fdc(expected)
    by_regex = {}
    for family, query in zip(probe.reset.SOURCES, request):
        by_regex[query["FromRegex"]] = [expected["Sources"][family]["ActualClockPin"]]
        by_regex[query["ToRegex"]] = expected["CandidateTargets"][family]

    def query(*args):
        assert args[:2] == ("-hierarchical", "-regexp") and len(args) == 3
        queries.append(args[2])
        if returned == "error":
            return tcl.call("error", "synthetic get_pins unavailable in this context")
        if returned == "opaque":
            return "_opaque_handle_1"  # A valid 1-item list still must fail exact-name checking.
        if returned == "invalid_list":
            return "{unterminated"
        values = list(by_regex[args[2]])
        if returned == "duplicate":
            values.append(values[0])
        if returned == "wrong_name":
            values[0] = "outside_ip/misrendered:CLK"
        return tcl.call("list", *values)

    def files(operation, *args):
        assert args == ("P:/distortion/build/fresh/device_map/board1080_top_map.adf",)
        if operation == "exists":
            return "1" if map_exists else "0"
        assert operation == "mtime"
        return "12345"

    def opens(path, mode):
        assert path == "P:/distortion/build/fresh/ddr-pin-query-probe.log" and mode == "a"
        return tcl.call("original_open", str(log), mode)

    def puts(*args):
        if len(args) == 1:
            stdout.append(args[0])
            return ""
        return tcl.call("original_puts", *args)

    for command in ("file", "open", "puts"):
        tcl.eval(f"rename {command} original_{command}")
    tcl.createcommand("get_pins", query)
    tcl.createcommand("file", files)
    tcl.createcommand("open", opens)
    tcl.createcommand("puts", puts)
    return tcl, log, stdout, queries


def script(mode="audit-only"):
    return probe.make_probe(objects(), "P:/distortion/build/fresh/device_map/board1080_top_map.adf",
                            "P:/distortion/build/fresh/ddr-pin-query-probe.log", "a" * 64, mode=mode)


def test_initial_recipe_parse_without_map_defers_all_queries_and_file_writes(tmp_path):
    tcl, log, stdout, queries = interpreter(tmp_path, objects(), map_exists=False)
    tcl.eval(script())
    assert not queries and not log.exists()
    assert any("DEFERRED_NO_MAP" in row for row in stdout)
    assert not any("EXACT_QUERY_NAMES_MATCHED" in row for row in stdout)


def test_exact_runtime_queries_record_all_161_full_names_and_candidate_hash(tmp_path):
    tcl, log, stdout, queries = interpreter(tmp_path, objects())
    tcl.eval(script("strict"))
    text = log.read_text(encoding="utf-8")
    assert len(queries) == 6
    assert sum(row.startswith("ACTUAL ") for row in text.splitlines()) == 161
    assert sum(row.startswith("EXACT_NAME_SET ") and row.endswith(" 1") for row in text.splitlines()) == 6
    assert "a" * 64 in text and "NOT_APPLIED" in text
    assert any("EXACT_QUERY_NAMES_MATCHED NOT_APPLIED" in row for row in stdout)
    assert "RAW " in text and "COUNT dqs_reset:to 137 137" in text


@pytest.mark.parametrize("returned", ["opaque", "invalid_list", "duplicate", "wrong_name", "error"])
def test_audit_only_records_unknown_semantics_without_blocking_control_flow(tmp_path, returned):
    tcl, log, stdout, queries = interpreter(tmp_path, objects(), returned=returned)
    tcl.eval(script())  # audit-only MUST catch the error and continue.
    assert len(queries) == 6
    text = log.read_text(encoding="utf-8")
    assert "NOT_APPLIED" in text
    assert any("PDS_DDR_PIN_PROBE FAILED NOT_APPLIED" in row for row in stdout)
    assert not any("EXACT_QUERY_NAMES_MATCHED" in row for row in stdout)
    assert "QUERY_ERROR" in text if returned == "error" else "RAW " in text


def test_strict_unknown_collection_fails_closed_even_when_handle_count_is_one(tmp_path):
    tcl, log, stdout, _ = interpreter(tmp_path, objects(), returned="opaque")
    with pytest.raises(Exception, match="exact expected names"):
        tcl.eval(script("strict"))
    text = log.read_text(encoding="utf-8")
    assert "COUNT dqs_reset:from 1 1" in text
    assert "EXACT_NAME_SET dqs_reset:from 0" in text
    assert any("FAILED NOT_APPLIED" in row for row in stdout)


def test_script_has_no_collection_extension_commands_or_scope_loading():
    text = script()
    statements = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))
    for command in ("sizeof_collection", "get_object_name", "foreach_in_collection", "add_constraint",
                    "set_false_path", "pnr ", "gen_bit_stream"):
        assert command not in statements
    assert "catch" in text and "llength" in text and "lsearch -exact" in text


@pytest.fixture
def candidate(tmp_path, monkeypatch):
    project = tmp_path / "distortion"
    folder = project / "build/ddr-ip-reset-constraints/source"
    folder.mkdir(parents=True)
    inventory = folder / "synthetic.netlist"
    inventory.write_text("synthetic metadata for mocked parser", encoding="utf-8")
    values = objects()
    monkeypatch.setattr(probe.reset, "parse_netlist", lambda path: {})
    monkeypatch.setattr(probe.reset, "inventory", lambda parsed: values)
    content, queries = probe.reset.make_fdc(values)
    fdc = folder / "scope-reset.fdc"
    fdc.write_bytes(content.encode("ascii"))
    plan = {"Schema": "ddr-ip-reset-constraints-candidate-v1", "DiagnosticOnly": True, "NotApplied": True,
            "InputSHA256RepoRelative": {inventory.relative_to(tmp_path).as_posix(): probe.reset.closure.sha(inventory)},
            "InventorySource": inventory.relative_to(tmp_path).as_posix(), "Objects": values, "Queries": queries,
            "CandidateFDC": {"Path": fdc.relative_to(tmp_path).as_posix(), "SHA256": probe.reset.closure.sha(fdc)}}
    path = folder / "plan.json"
    path.write_text(json.dumps(plan), encoding="utf-8")
    helpers = project / "tools"
    helpers.mkdir()
    for name in ("probe.py", "reset.py"):
        (helpers / name).write_text("synthetic helper identity", encoding="ascii")
    monkeypatch.setattr(probe, "SELF", helpers / "probe.py")
    monkeypatch.setattr(probe.reset, "__file__", str(helpers / "reset.py"))
    monkeypatch.setattr(probe.reset.closure, "validate_repo_alias", lambda project, alias: probe.reset.closure.alias_format(alias))
    return project, path, plan, fdc


def test_prepare_binds_candidate_inputs_without_applying_scope(candidate):
    project, path, _, _ = candidate
    output = project / "build/ddr-ip-query-probes/fresh-a"
    result = probe.prepare(project, path, project / "build/fullflow/fresh-a", output)
    assert result["Mode"] == "audit-only" and result["NotApplied"]
    assert not result["LoadCandidateAutomatically"] and not result["PDSReturnSerializationVerified"]
    assert not result["EDAStarted"] and not result["All244ChecksMatched"]
    assert result["ExpectedGroups"] == [{"Family": family, "FromCount": 1, "ToCount": count}
                                         for family, count in probe.reset.EXPECTED_GROUPS.items()]
    assert probe.reset.closure.sha(output / "query-probe.tcl") == result["Probe"]["SHA256"]
    assert result["RecommendedFinalReportCommand"].endswith("-max_path 250 -nworst 1")
    with pytest.raises(ValueError, match="fresh child"):
        probe.prepare(project, path, project / "build/fullflow/fresh-a", output)


@pytest.mark.parametrize("mutation", ["fdc", "query", "input", "inventory"])
def test_candidate_tampering_rejected_before_output(candidate, mutation):
    project, path, plan, fdc = candidate
    if mutation == "fdc":
        fdc.write_text("set_clock_groups -asynchronous\n", encoding="ascii")
    elif mutation == "input":
        plan["InputSHA256RepoRelative"][plan["InventorySource"]] = "0" * 64
    elif mutation == "query":
        plan["Queries"][0]["FromRegex"] = "global.*"
    else:
        plan["Objects"] = {}
    path.write_text(json.dumps(plan), encoding="utf-8")
    output = project / "build/ddr-ip-query-probes/rejected"
    with pytest.raises(ValueError):
        probe.prepare(project, path, project / "build/fullflow/rejected", output)
    assert not output.exists()


def test_existing_map_and_escaped_output_rejected(candidate):
    project, path, _, _ = candidate
    flow = project / "build/fullflow/previous"
    mapped = flow / "device_map/board1080_top_map.adf"
    mapped.parent.mkdir(parents=True)
    mapped.write_bytes(b"synthetic existing DB")
    with pytest.raises(ValueError, match="fresh fullflow"):
        probe.prepare(project, path, flow, project / "build/ddr-ip-query-probes/rejected")
    with pytest.raises(ValueError, match="fresh child"):
        probe.prepare(project, path, project / "build/fullflow/fresh", project.parent / "outside")


@pytest.mark.parametrize("value", [True, 20, 249, 10001, "250"])
def test_complete_failure_report_cap_is_explicit_and_bounded(value):
    with pytest.raises(ValueError, match="250..10000"):
        probe.report_command(value)
