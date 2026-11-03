"""Regression contracts for a native parser that cannot borrow another cell."""
from pathlib import Path
import sys

import pytest

REPO = Path(__file__).resolve().parents[4]
sys.path[:0] = [str(REPO / "distortion/tools"), str(REPO / ".venv/Lib/site-packages")]
import hdmi_camera_fisheye_fill8r3s3_vendor_startup_bounded_b as provider

PARENT = "native/group[0]/target"


def cell(parameters='.FF0_RS("RESET")', ports='.RS(reset)', attribute=""):
    return attribute + "gopSRL2 /* exact native operator */ #(" + parameters + ") \\" + PARENT + " (" + ports + ");\n"


def test_exact_cell_never_borrows_preceding_operator_or_parameters():
    foreign = 'gopCCS #(.LRS_EN("TRUE"),.RS_MODE("ASYNC")) \\foreign (.RS(other));\n'
    parsed = provider.native_route_cell(foreign + cell(), PARENT)
    assert parsed["Primitive"] == "gopSRL2"
    assert parsed["Parameters"] == {"FF0_RS": '"RESET"'}
    assert "LRS_EN" not in parsed["Parameters"] and "RS_MODE" not in parsed["Parameters"]
    assert parsed["Ports"] == {"RS": "reset"}


def test_actual_native_leading_attributes_and_literal_indexed_parent():
    parsed = provider.native_route_cell(cell(attribute='(* syn_encoding="onehot" *)    '), PARENT)
    assert parsed["Primitive"] == "gopSRL2"


@pytest.mark.parametrize("route", [
    cell() + cell(),
    cell(parameters='.LRS_EN("TRUE"), .LRS_EN("FALSE")'),
    cell(ports='.RS(reset), .RS(other)'),
    cell(parameters='.LRS_EN("TRUE") unparsed'),
    cell(ports='.RS(reset) unparsed'),
    cell(parameters='.LRS_EN(nested(value))'),
    "(INSTANCE \\" + PARENT + " (VIEWREF OPER))",
])
def test_duplicate_or_unsupported_cell_shape_is_rejected(route):
    with pytest.raises(ValueError):
        provider.native_route_cell(route, PARENT)


def test_absent_exact_parent_is_rejected():
    with pytest.raises(ValueError, match="one exact startup native parent"):
        provider.native_route_cell(cell(), PARENT + "_other")


def test_same_line_foreign_header_cannot_supply_target_primitive():
    foreign = 'gopCCS #(.LRS_EN("FALSE")) \\foreign (.RS(other)); '
    parsed = provider.native_route_cell(foreign + cell(parameters='.LRS_EN("TRUE")'), PARENT)
    assert parsed["Primitive"] == "gopSRL2"
    assert parsed["Parameters"] == {"LRS_EN": '\"TRUE\"'}
    assert parsed["Ports"] == {"RS": "reset"}


def test_same_line_duplicate_exact_parent_is_rejected():
    with pytest.raises(ValueError, match="one exact startup native parent"):
        provider.native_route_cell(cell().rstrip() + ' ' + cell(), PARENT)
