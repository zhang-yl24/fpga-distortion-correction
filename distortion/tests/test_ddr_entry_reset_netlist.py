"""Reject unsafe/ambiguous reset connectivity; synthetic public-format fixtures."""
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import audit_ddr_entry_reset_netlist as tool


def fixture():
    prefix = tool.PREFIX
    params = '.GRS_EN("TRUE"), .SET_RESET("RESET"), .LRS_EN("TRUE"), .INIT(1\'b0)'
    middle = r"\site/middle"
    pll_clock = "\\" + prefix + "rst_gpll_clkout0"
    declarations = [middle, tool.OUTPUT, tool.LOCK, tool.RST_CLOCK, pll_clock,
                    "clk_leaf", "clear", "nt_reset_n", "power_ready", "reset_ibuf_net"]
    cells = [
        'V_IBUF reset_ibuf (.O(reset_ibuf_net), .I(reset_n));',
        'V_BUF reset_buffer (.Z(nt_reset_n), .I(reset_ibuf_net));',
        f'V_GPLL \\{prefix}rst_clk_gpll/GPLL (.LOCK({tool.LOCK} ), .CLKOUT0({pll_clock} ), .RST(clear));',
        f'V_USCM #(.USCM_MODE("BUF_A")) clock_mux (.CLKOUT({tool.RST_CLOCK} ), .CLK0({pll_clock} ), .CLK1(), .SEL());',
        f'V_BUF clock_buffer (.Z(clk_leaf), .I({tool.RST_CLOCK} ));',
        'V_LUT6CARRY #(.INIT(64\'h0F0F0F0FFFFFFFFF), .I5_TO_LUT("TRUE")) reset_lut '
        '(.Z(clear), .I0(1\'b1), .I1(1\'b1), .I2(power_ready), .I3(1\'b1), .I4(1\'b1), .I5(nt_reset_n));',
        f'V_FFASYN #({params}) power_ff (.Q(power_ready), .CE(1\'b1), .CK(board27), .D(power_d), .SR(key_clear));',
        f'V_FFASYN #({params}) \\{tool.SYNC}stage1 (.Q({middle} ), .CE(1\'b1), .CK(clk_leaf), .D({tool.LOCK} ), .SR(clear));',
        f'V_FFASYN #({params}) \\{tool.SYNC}stage2 (.Q({tool.OUTPUT} ), .CE(1\'b1), .CK(clk_leaf), .D({middle} ), .SR(clear));',
        f'V_INV \\{prefix}ddrphy_reset_ctrl/reset_inv (.Z(local_clear), .I({tool.OUTPUT} ));',
    ]
    return "\n".join(["module board1080_top;", *(f"wire {net} ;" for net in declarations),
                      *cells, "endmodule", ""])


def test_shared_clear_and_clock_are_valid_two_stage_structure():
    result = tool.audit_text(fixture())
    assert result["Status"] == "pass"
    assert result["FirstStageFunctionalFanout"] == 1
    assert result["RawClearFunction"] == "~(reset_n & power_ready)"
    assert result["OutputLoadCount"] == 1
    assert result["AnalogMTBFProven"] is False
    assert result["TimingExceptionApplied"] is False


@pytest.mark.parametrize("before,after,reason", [
    (".CE(1'b1)", ".CE(1'b0)", "CE"),
    ('.SET_RESET("RESET")', '.SET_RESET("SET")', "clear"),
    ('.LRS_EN("TRUE")', '.LRS_EN("FALSE")', "clear"),
    (".INIT(1'b0)", ".INIT(1'b1)", "clear"),
    (".INIT(64'h0F0F0F0FFFFFFFFF)", ".INIT(64'h0000000000000000)", "raw clear"),
    (".RST(clear)", ".RST(other_reset)", "PLL reset"),
    ('.USCM_MODE("BUF_A")', '.USCM_MODE("MUX")', "clock mux"),
    (".I2(power_ready)", f".I2({tool.LOCK} )", "LOCK"),
    (r"stage2 (.Q", r"stage1 (.Q", "duplicate cell"),
    (".CE(1'b1)", ".CE(1'b1), .CE(1'b1)", "duplicate named"),
])
def test_wrong_controls_or_ambiguous_export_are_rejected(before, after, reason):
    with pytest.raises(ValueError, match=reason):
        tool.audit_text(fixture().replace(before, after))


def test_first_stage_fanout_is_rejected():
    extra = r"V_BUF extra (.Z(bad), .I(\site/middle ));"
    with pytest.raises(ValueError, match="functional fanout"):
        tool.audit_text(fixture().replace("endmodule", extra + "\nendmodule"))


def test_hidden_continuous_assign_is_rejected():
    extra = r"assign bad = \site/middle ;"
    with pytest.raises(ValueError, match="unparsed references"):
        tool.audit_text(fixture().replace("endmodule", extra + "\nendmodule"))


def test_clear_alias_or_second_driver_is_rejected():
    extra = "assign clear = unrelated;"
    with pytest.raises(ValueError, match="unparsed references"):
        tool.audit_text(fixture().replace("endmodule", extra + "\nendmodule"))


def test_second_stage_clear_mismatch_is_rejected():
    text = fixture().replace(r".D(\site/middle ), .SR(clear)",
                             r".D(\site/middle ), .SR(other_clear)")
    with pytest.raises(ValueError, match="different clears"):
        tool.audit_text(text)


def test_second_stage_clock_mismatch_is_rejected():
    text = "\n".join(line.replace(".CK(clk_leaf)", ".CK(other_clock)")
                     if "stage2 " in line else line for line in fixture().splitlines())
    with pytest.raises(ValueError, match="different clocks"):
        tool.audit_text(text)


def buffered_fixture():
    extra = [*(f"wire raw_{name} ;" for name in "abc"),
             'V_BUF buffer_a (.Z(raw_a), .I(clear));',
             'V_BUF buffer_b (.Z(raw_b), .I(raw_a));',
             'V_BUF buffer_c (.Z(raw_c), .I(clear));',
             *(f"V_FFASYN sink_{name} (.Q(q_{name}), .CE(1'b1), .CK(board27), "
               f".D(1'b0), .SR(raw_{name}));" for name in "abc")]
    return fixture().replace("endmodule", "\n".join([*extra, "endmodule"]))


def test_identity_buffer_tree_has_only_reset_loads_and_audited_references():
    result = tool.audit_text(buffered_fixture())
    assert result["Status"] == "pass"
    assert result["FirstStageFunctionalFanout"] == 1
    assert result["RawClearBufferCount"] == 3
    assert {cell["Name"] for cell in result["RawClearBuffers"]} == {
        "buffer_a", "buffer_b", "buffer_c"}
    assert {net: result["CriticalNetReferenceCounts"][net] for net in
            ("raw_a", "raw_b", "raw_c")} == {"raw_a": 4, "raw_b": 3, "raw_c": 3}
    assert "RawClearBuffers" not in tool.audit_text(fixture())


@pytest.mark.parametrize("extra,reason", [
    ("V_BUF extra (.Z(raw_b), .I(unrelated));", "unexpected driver or use"),
    ("V_BUF extra (.Z(clear), .I(unrelated));", "unexpected driver or use"),
    ("V_FFASYN extra (.Q(raw_b), .SR(unrelated));", "unexpected driver or use"),
    ("V_FFASYN extra (.Q(q), .D(raw_b));", "unexpected driver or use"),
    ("V_INV extra (.Z(q), .I(raw_b));", "unexpected driver or use"),
    ("V_GPLL extra (.RST(raw_b));", "unexpected driver or use"),
    ("V_BUF extra (.Z(raw_b), .I(raw_c));", "unexpected driver or use|reused or cyclic"),
    ("assign raw_b = unrelated;", "unparsed references"),
    ("assign hidden_load = raw_b;", "unparsed references"),
])
def test_buffered_clear_extra_drivers_loads_and_aliases_are_rejected(extra, reason):
    with pytest.raises(ValueError, match=reason):
        tool.audit_text(buffered_fixture().replace("endmodule", extra + "\nendmodule"))


@pytest.mark.parametrize("before,after,reason", [
    (".Z(raw_b), .I(raw_a)", ".Z(raw_a), .I(raw_a)", "unexpected driver or use|reused or cyclic"),
    (".Z(raw_b), .I(raw_a)", ".Z(clear), .I(raw_a)", "unexpected driver or use|reused or cyclic"),
    (".I(raw_a)", ".I(~raw_a)", "non-direct connection"),
    (".Z(raw_b)", ".Z({raw_b})", "output is invalid"),
    ("V_BUF buffer_b", "V_BUF #(.MODE(1)) buffer_b", "parameters or ports"),
    (".Z(raw_b), .I(raw_a)", ".Z(raw_b), .I(raw_a), .EN(1'b1)", "parameters or ports"),
    (".SR(raw_b)", ".SR(unrelated)", "no reset loads"),
    (".SR(raw_b)", ".SR(~raw_b)", "non-direct connection"),
])
def test_invalid_buffer_tree_connections_are_rejected(before, after, reason):
    with pytest.raises(ValueError, match=reason):
        tool.audit_text(buffered_fixture().replace(before, after))


def test_real_local_official_export_when_available():
    netlist = Path(__file__).resolve().parents[1] / (
        "build/board1080-timing/ccoff-1029-a/generate_netlist/board1080_top_sim.v")
    if not netlist.is_file():
        pytest.skip("local PDS output is not distributed")
    result = tool.audit_text(netlist.read_text(encoding="utf-8"))
    assert result["FirstStageFunctionalFanout"] == 1
    assert result["OutputLoadCount"] == 14


def test_real_local_control_chain_export_when_available():
    netlist = Path(__file__).resolve().parents[1] / (
        "build/board1080-timing/fresh-entry-1029-e/generate_netlist/board1080_top_sim.v")
    if not netlist.is_file():
        pytest.skip("local PDS output is not distributed")
    result = tool.audit_text(netlist.read_text(encoding="utf-8"))
    assert result["FirstStageFunctionalFanout"] == 1
    assert result["OutputLoadCount"] == 11
    assert result["RawClearBufferCount"] == 9
