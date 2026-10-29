"""Complete synthetic check fixtures and native-name evidence; no EDA."""
from pathlib import Path
from collections import Counter
import copy
import io
import json
import re
import sys
import xml.etree.ElementTree as ET

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import prepare_ddr_native_reset_scope as tool


def checks():
    values = {"slow": [], "fast": []}
    source = {name: data[0] + "/actual_alias/CLK" for name, data in tool.DRIVERS.items()}
    dqs = [tool.PREFIX + f"ddrphy_slice_top/generated[{i}].ddc/cell/RST" for i in range(7)]
    dqs += [tool.PREFIX + f"ddrphy_slice_top/generated[{i}].io/cell/OSR_IOLHR" for i in range(65)]
    dqs += [tool.PREFIX + f"ddrphy_slice_top/generated[{i}].io/cell/ISR_IOLHR" for i in range(32)]
    iol = [tool.PREFIX + f"ddrphy_slice_top/generated[{i}].ts/cell/TSR" for i in range(14)]
    training = [tool.PREFIX + f"ddrphy_slice_top/generated[{i}].ddc/cell/RST_TRAINING_N" for i in range(7)]
    for corner in values:
        def add(family, target, capture):
            launch = "ddrphy_sysclk" if family == "training_reset" else "rst_clk"
            values[corner].append({"Launch Clock": launch, "Capture Clock": capture,
                                   "Start Point": source[family], "End Point": target, "Slack": "-0.5"})
        for number, targets, ts in [(0, dqs[:28], iol[:6]), (1, dqs[28:], iol[6:])]:
            for capture in [f"phy_dq_clk_{number}", f"phy_dq_sysclk_{number}"]:
                for target in targets:
                    add("dqs_reset", target, capture)
                for target in ts:
                    add("iol_reset", target, capture)
        for i, target in enumerate(training):
            add("training_reset", target, "phy_dq_clk_0" if i < 3 else "phy_dq_clk_1")
        add("cpd_reset", tool.PREFIX + "u_ddrphy_cpd/cpd_inst/RST", "phy_dq_sysclk_0")
        if corner == "fast":
            for row in [r for r in values[corner] if r["Capture Clock"] == "phy_dq_sysclk_0"][:11]:
                row["Slack"] = "0.25"
    return values


def xml_bytes(values):
    root = ET.Element("tables")
    for corner in ["slow", "fast"]:
        for name, headers in [("recovery", ["Launch Clock", "Capture Clock", "Failing Endpoints", "Total Endpoints"]),
                              ("path_recovery", ["Launch Clock", "Capture Clock", "Start Point", "End Point", "Slack"])]:
            table = ET.SubElement(root, "table", id=f"report_timing_{corner}_{name}")
            head = ET.SubElement(table, "column_headers")
            for header in headers:
                ET.SubElement(head, "data").text = header
            if name == "path_recovery":
                rows = values[corner]
            else:
                rows = []
                for pair, total in tool.PAIRS.items():
                    count = sum(float(r["Slack"]) < 0 for r in values[corner]
                                if (r["Launch Clock"], r["Capture Clock"]) == pair)
                    rows.append(dict(zip(headers, [*pair, str(count), str(total)])))
            for row in rows:
                element = ET.SubElement(table, "row")
                for header in headers:
                    ET.SubElement(element, "data").text = row[header]
    return ET.tostring(root, encoding="utf-8")


def native_records(groups, *, cpd=False):
    result = []
    for family, group in groups.items():
        if family == "cpd_reset" and not cpd:
            continue
        for names in [[group["SourceClockPin"]], group["Targets"]]:
            pattern = tool.reference.exact_regex(names)
            result.append({"Pattern": pattern, "Command": "get_pins -hierarchical -regexp " + pattern,
                           "Count": len(names), "NativeNames": ["t:" + n for n in names]})
    return result


def write_native(path, records):
    lines = ["PDS_PIN_RAW @tcicmdresult36"]
    for record in records:
        lines.append("I: Timing-5001: The pattern '" + record["Pattern"] + "' in command '" + record["Command"]
                     + "' match " + str(record["Count"]) + " objects below: " + " ".join(record["NativeNames"]))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_complete_two_corner_streaming_extract_and_four_driver_inventory():
    expected = checks()
    extracted = tool.extract_checks(io.BytesIO(xml_bytes(expected)))
    assert extracted == expected
    grouped = tool.group_checks(extracted)
    assert len(grouped) == 4
    assert sum(len(value["Targets"]) for value in grouped.values()) == 126
    assert {k: len(v["ChecksByCorner"]["slow"]) for k, v in grouped.items()} == {
        "dqs_reset": 208, "iol_reset": 28, "training_reset": 7, "cpd_reset": 1}
    assert sum(float(r["Slack"]) < 0 for r in extracted["fast"]) == 233
    assert len(tool.inventory_tsv(extracted).splitlines()) == 489


@pytest.mark.parametrize("mutation", ["truncated", "duplicate", "corner_identity"])
def test_partial_or_duplicate_reports_are_not_called_complete(mutation):
    values = checks()
    if mutation == "truncated":
        values["slow"].pop()
    elif mutation == "duplicate":
        values["slow"][0] = copy.deepcopy(values["slow"][1])
    else:
        values["fast"][0]["End Point"] += "_different"
    with pytest.raises(ValueError):
        tool.extract_checks(io.BytesIO(xml_bytes(values)))


@pytest.mark.parametrize("mutation", ["self_source", "self_target", "entry", "D", "TX_DATA[2]", "wrong_family", "unknown_driver"])
def test_source_endpoint_scope_and_families_fail_closed(mutation):
    values = checks()
    for corner in values:
        row = values[corner][0]
        if mutation == "self_source":
            row["Start Point"] = "system/reset/opit/CLK"
        elif mutation == "self_target":
            row["End Point"] = "system/data/RST"
        elif mutation == "entry":
            row["End Point"] = tool.PREFIX + "u_ddrphy_rst_seq_rstn_sync/entry/RS"
        elif mutation == "unknown_driver":
            row["Start Point"] = tool.PREFIX + "unknown/driver/opit/CLK"
        elif mutation == "wrong_family":
            row["End Point"] = row["End Point"].rsplit("/", 1)[0] + "/TSR"
        else:
            row["End Point"] = row["End Point"].rsplit("/", 1)[0] + "/" + mutation
    with pytest.raises(ValueError):
        tool.group_checks(values)


def test_native_object_records_validate_exact_slash_names_not_opaque_count(tmp_path):
    groups = tool.group_checks(checks())
    records = native_records(groups)
    log = tmp_path / "native.log"
    write_native(log, records)
    assert tool.parse_native_matches(log) == records
    fdc, proof, emitted = tool.make_scope(groups, records)
    assert emitted == ["dqs_reset", "iol_reset", "training_reset"]
    assert len(proof) == 6
    assert fdc.count("\nset_false_path ") == 3
    assert "get_clocks" not in fdc and "set_clock_groups" not in fdc
    assert ":CLK" not in fdc and ":RST" not in fdc and "llength" not in fdc
    for family in emitted:
        assert len(groups[family]["Targets"]) in [104, 14, 7]
    assert "cpd_rstn" not in fdc


def test_fourth_cpd_cut_requires_explicit_native_source_and_target_proof():
    groups = tool.group_checks(checks())
    with pytest.raises(ValueError, match="cpd_reset"):
        tool.make_scope(groups, native_records(groups), include_cpd=True)
    fdc, proof, emitted = tool.make_scope(groups, native_records(groups, cpd=True), include_cpd=True)
    assert len(emitted) == 4 and len(proof) == 8
    assert "cpd_rstn" in fdc and "u_ddrphy_cpd/cpd_inst/RST" in fdc


def test_native_count_mismatch_or_unverified_colon_alias_rejected(tmp_path):
    groups = tool.group_checks(checks())
    records = native_records(groups)
    records[0]["NativeNames"] = [records[0]["NativeNames"][0].rsplit("/", 1)[0] + ":CLK"]
    log = tmp_path / "colon.log"
    write_native(log, records)
    with pytest.raises(ValueError, match="slash-pin"):
        tool.parse_native_matches(log)
    records = native_records(groups)
    records[0]["Count"] = 2
    write_native(log, records)
    with pytest.raises(ValueError, match="count/list"):
        tool.parse_native_matches(log)


def test_true_126_target_objects_exceed_the_three_driver_125_fdc():
    groups = tool.group_checks(checks())
    primary = [v for k, v in groups.items() if k != "cpd_reset"]
    assert sum(len(v["Targets"]) for v in primary) == 125
    assert sum(len(v["ChecksByCorner"]["slow"]) for v in primary) == 243
    assert groups["cpd_reset"]["Targets"] == [tool.PREFIX + "u_ddrphy_cpd/cpd_inst/RST"]


def test_prepare_new_artifacts_keeps_input_and_primary_fdc_unchanged(tmp_path, monkeypatch):
    project = tmp_path / "distortion"
    inputs = project / "build/input"
    inputs.mkdir(parents=True)
    xml = inputs / "rtr.db"
    xml.write_bytes(xml_bytes(checks()))
    log = inputs / "query.log"
    write_native(log, native_records(tool.group_checks(checks())))
    primary = project / "board/primary.fdc"
    primary.parent.mkdir()
    primary.write_bytes(b"immutable primary FDC")
    helpers = project / "tools"
    helpers.mkdir()
    for name in ["tool.py", "reference.py"]:
        (helpers / name).write_bytes(b"synthetic helper identity")
    monkeypatch.setattr(tool, "SELF", helpers / "tool.py")
    monkeypatch.setattr(tool.reference, "__file__", str(helpers / "reference.py"))
    monkeypatch.setattr(tool.reference, "bind_inputs", lambda *args: {"distortion/board/primary.fdc": tool.reference.closure.sha(primary)})
    output = project / "build/ddr-native-reset-scope/candidate"
    before = primary.read_bytes(), xml.read_bytes(), log.read_bytes()
    plan = tool.prepare(project, xml, log, output)
    assert plan["NotApplied"] and not plan["EDAStarted"]
    assert plan["ActualUniqueTargets"] == 126 and plan["ActualDriverFamilies"] == 4
    assert plan["EmittedCheckCountPerCorner"] == 243 and plan["EmittedUniqueTargetCount"] == 125
    assert not plan["CPDIncluded"] and len(plan["CPDExcludedChecks"]) == 1
    assert sorted(p.name for p in output.iterdir()) == ["inventory.tsv", "native-reset-scope.fdc", "plan.json"]
    assert tool.reference.closure.sha(output / "native-reset-scope.fdc") == plan["CandidateFDC"]["SHA256"]
    assert tool.reference.closure.sha(output / "inventory.tsv") == plan["InventoryTSV"]["SHA256"]
    assert (primary.read_bytes(), xml.read_bytes(), log.read_bytes()) == before
    with pytest.raises(ValueError, match="fresh child"):
        tool.prepare(project, xml, log, output)
    with pytest.raises(ValueError, match="fresh child"):
        tool.prepare(project, xml, log, primary)


def test_real_native_query_log_and_curated_complete_rows_when_available():
    result = tool.PROJECT / "results/board1080-controlchain-20261029.json"
    log = tool.PROJECT / "build/ddr-fix-20261029/mpnr-scope-j/stdout.log"
    if not result.is_file() or not log.is_file():
        pytest.skip("local native probe evidence not distributed")
    r = json.loads(result.read_text(encoding="utf-8"))
    values = {c: r["Recovery"]["Inventory"][c]["DetailedPHYRows"] for c in ["slow", "fast"]}
    groups = tool.group_checks(values)
    fdc, proof, emitted = tool.make_scope(groups, tool.parse_native_matches(log))
    assert len(proof) == 6 and len(emitted) == 3 and ":CLK" not in fdc
    assert sum(len(g["Targets"]) for g in groups.values()) == 126
