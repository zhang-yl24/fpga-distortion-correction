"""CPU-only exact-object contracts; no PDS, hardware or vendor body fixtures."""
from pathlib import Path
import copy
import json
import re
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import prepare_ddr_ip_reset_constraints as tool


def cells():
    values = {}
    for family, (parent, primitive, _) in tool.SOURCES.items():
        values[parent + "/actual_map_alias_0"] = {"Primitive": primitive, "Pins": {"CLK": "1", "D": "1"}}
    for i in range(4):
        name = tool.SLICE_PREFIX + f"i_dqs_group[{i}].ddrphy_data_slice/u_ddc_dq/ddc_inst_PHY"
        values[name] = {"Primitive": "gopDDRPHY", "Pins": {"RST": "1", "RST_TRAINING_N": "1"}}
    for i in range(3):
        name = tool.SLICE_PREFIX + f"i_ca_group[{i}].u_ddc_ca/ddc_inst"
        values[name] = {"Primitive": "gopDQSL", "Pins": {"RST": "1", "RST_TRAINING_N": "1"}}
    for primitive, count, stem in [("gopTSERDES", 14, "ts"), ("gopIOL", 65, "io"),
                                    ("gopDDRPHY_IOCLKDIV", 2, "div"), ("gopPPLL", 2, "pll")]:
        for i in range(count):
            name = tool.SLICE_PREFIX + f"synthetic_group[{i}].{stem}/opit_0"
            values[name] = {"Primitive": primitive,
                            "Pins": {pin: "1" for pin in tool.EXPECTED_PIN_NAMES[primitive]}}
    return values


def write_netlist(path, values):
    lines = ["Port", "synthetic;1", ""]
    for name, value in values.items():
        lines.extend(["Inst", name + ";" + value["Primitive"], "Pin"])
        lines.extend(pin + ";" + mode for pin, mode in value["Pins"].items())
        lines.append("")
    lines.extend(["Net", "synthetic;", "", "Clock", "synthetic;1000", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def test_real_final_inventory_and_reference_bindings():
    netlist = tool.PROJECT / "build/board1080-timing/holdfix-full-20261028-e/place_route/board1080_top_route_optimize.netlist"
    if not netlist.is_file():
        pytest.skip("local E build artifact not distributed in this checkout")
    inv = tool.inventory(tool.parse_netlist(netlist))
    assert inv["RawResetInstanceCount"] == 90 and inv["RawResetPinCount"] == 162
    assert inv["CandidateTargetCount"] == 158
    assert {key: len(v) for key, v in inv["CandidateTargets"].items()} == tool.EXPECTED_GROUPS
    assert len(inv["ExcludedPLLAndDividerPins"]) == 4
    assert inv["All244ChecksMatched"] is False
    bindings = tool.bind_inputs(tool.PROJECT, tool.closure.DEFAULT_MANIFEST, tool.VENDOR_FDC, tool.AUDIT)
    assert tool.VENDOR_FDC in bindings
    assert "distortion/" + tool.closure.IDF in bindings
    assert sum(n.startswith("distortion/" + tool.closure.IP + "/") and n.endswith(".vp") for n in bindings) == 71
    assert "distortion/tools/prepare_ddr_ip_reset_constraints.py" in bindings


def test_synthetic_inventory_uses_actual_aliases_and_exact_source_domains(tmp_path):
    netlist = tmp_path / "synthetic.netlist"
    expected = cells()
    write_netlist(netlist, expected)
    parsed = tool.parse_netlist(netlist)
    assert parsed == expected
    inv = tool.inventory(parsed)
    assert inv["PrimitiveCounts"] == tool.EXPECTED_PRIMITIVES
    assert inv["RawResetPinCount"] == 162
    assert sum(map(len, inv["CandidateTargets"].values())) == 158
    assert inv["Sources"]["training_reset"]["SourceClockDomain"] == "ddrphy_sysclk"
    assert inv["Sources"]["dqs_reset"]["SourceClockDomain"] == "rst_clk"
    assert all(v["ActualInstance"].endswith("actual_map_alias_0") for v in inv["Sources"].values())


def test_exact_regex_preserves_brackets_and_dots():
    obj = tool.SLICE_PREFIX + "i_ca_group[0].u_ddc_ca/ddc_inst:RST"
    pattern = tool.exact_regex([obj])
    assert pattern.startswith("^(") and pattern.endswith(")$")
    assert re.fullmatch(pattern, obj)
    assert not re.fullmatch(pattern, obj.replace("[0]", "0"))
    assert not re.fullmatch(pattern, obj.replace(".u_ddc", "Xu_ddc"))
    assert not re.fullmatch(pattern, "prefix/" + obj)
    assert not re.fullmatch(pattern, obj + "/other")


def test_fdc_has_three_ip_pin_only_cuts_without_entry_clocks_or_data():
    values = cells()
    values["system/not_ddr/opit_0"] = {"Primitive": "gopIOL", "Pins": {"ISR_IOLHR": "1", "OSR_IOLHR": "1"}}
    values[tool.IP_PREFIX + "u_ddrphy_rst_seq_rstn_sync/entry"] = {"Primitive": "gopSRL2", "Pins": {"RS": "1", "CLK": "1"}}
    name = next(n for n, v in values.items() if v["Primitive"] == "gopIOL" and n.startswith(tool.SLICE_PREFIX))
    values[name]["Pins"]["TX_DATA[2]"] = "1"
    inv = tool.inventory(values)
    fdc, queries = tool.make_fdc(inv)
    commands = [line for line in fdc.splitlines() if line and not line.startswith("#")]
    assert len(commands) == 3 and all(line.startswith("set_false_path -from [get_pins -hierarchical -regexp {") for line in commands)
    assert all(word not in "\n".join(commands) for word in ["get_clocks", "set_clock_groups", "board27", "free_clk", "TX_DATA", "system/", "rst_seq_rstn_sync"])
    assert [q["ExpectedTargetObjects"] for q in queries] == [137, 14, 7]
    for family, query in zip(tool.SOURCES, queries):
        assert re.fullmatch(query["FromRegex"], inv["Sources"][family]["ActualClockPin"])
        assert all(re.fullmatch(query["ToRegex"], pin) for pin in inv["CandidateTargets"][family])
        assert query["PDSCollectionMatchingVerified"] is False
    assert all(pin.endswith(":TSR") for pin in inv["CandidateTargets"]["iol_reset"])
    assert all(pin.endswith(":RST_TRAINING_N") for pin in inv["CandidateTargets"]["training_reset"])


@pytest.mark.parametrize("mutation", ["source_missing", "source_duplicate", "source_type", "source_clock",
                                      "source_prefix", "target_type", "target_missing", "target_clock_direction"])
def test_bad_source_and_family_inventories_are_rejected(mutation):
    values = cells()
    source = tool.SOURCES["dqs_reset"][0] + "/actual_map_alias_0"
    target = next(n for n, v in values.items() if v["Primitive"] == "gopIOL")
    if mutation == "source_missing":
        del values[source]
    elif mutation == "source_duplicate":
        values[tool.SOURCES["dqs_reset"][0] + "/another"] = copy.deepcopy(values[source])
    elif mutation == "source_type":
        values[source]["Primitive"] = "gopLUT6"
    elif mutation == "source_clock":
        values[source]["Pins"].pop("CLK")
    elif mutation == "source_prefix":
        values[source.replace(tool.IP_PREFIX, "system/")] = values.pop(source)
    elif mutation == "target_type":
        values[target]["Primitive"] = "gopUnknown"
    elif mutation == "target_missing":
        del values[target]
    else:
        values[target]["Pins"]["ISR_IOLHR"] = "2"
    with pytest.raises(ValueError):
        tool.inventory(values)


@pytest.mark.parametrize("duplicate", ["instance", "pin"])
def test_parser_rejects_duplicate_records(tmp_path, duplicate):
    path = tmp_path / "bad.netlist"
    data = "Port\n\nInst\ncell;gopQ\nPin\nCLK;1\n"
    data += "CLK;1\n" if duplicate == "pin" else "\nInst\ncell;gopQ\nPin\nCLK;1\n"
    path.write_text(data, encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate"):
        tool.parse_netlist(path)


def test_encrypted_or_binary_inputs_and_unsafe_objects_are_rejected(tmp_path):
    path = tmp_path / "body.vp"
    path.write_bytes(b"HASH-ONLY SYNTHETIC")
    with pytest.raises(ValueError, match="readable .netlist"):
        tool.parse_netlist(path)
    for name in ["system/outside", tool.IP_PREFIX + "../escape", tool.IP_PREFIX + "bad{name}"]:
        with pytest.raises(ValueError):
            tool.pin_object(name, "RST")
    with pytest.raises(ValueError, match="data or unapproved"):
        tool.pin_object(tool.IP_PREFIX + "data", "TX_DATA[2]")


def test_prepare_writes_only_fresh_separate_candidate_and_plan(tmp_path, monkeypatch):
    project = tmp_path / "distortion"
    netlist = project / "build/source/synthetic_route_optimize.netlist"
    write_netlist(netlist, cells())
    primary = project / "board/main.fdc"
    primary.parent.mkdir()
    primary.write_bytes(b"primary constraint remains frozen")
    monkeypatch.setattr(tool, "bind_inputs", lambda *args: {"distortion/board/main.fdc": tool.closure.sha(primary)})
    output = project / "build/ddr-ip-reset-constraints/candidate-a"
    before = primary.read_bytes()
    plan = tool.prepare(project, netlist, output)
    assert plan["DiagnosticOnly"] and plan["NotApplied"] and not plan["EDAStarted"]
    assert plan["InventorySourceStage"] == "FinalPNR"
    assert not plan["MapStageObjectMatchingVerified"] and not plan["All244ChecksMatched"]
    assert sorted(x.name for x in output.iterdir()) == ["plan.json", "scope-reset.fdc"]
    assert primary.read_bytes() == before
    assert tool.closure.sha(output / "scope-reset.fdc") == plan["CandidateFDC"]["SHA256"]
    assert json.loads((output / "plan.json").read_text(encoding="utf-8"))["Objects"]["CandidateTargetCount"] == 158
    with pytest.raises(ValueError, match="fresh child"):
        tool.prepare(project, netlist, output)
    with pytest.raises(ValueError, match="fresh child"):
        tool.prepare(project, netlist, primary)
    with pytest.raises(ValueError, match="fresh child"):
        tool.prepare(project, netlist, tmp_path / "escaped")
