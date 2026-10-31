"""Local actual-export review and mutations of safety-critical reset edges."""
from pathlib import Path
import json
import sys
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import audit_processed_output_entry_netlist as audit


@pytest.fixture(scope="module")
def actual():
    root = Path(__file__).resolve().parents[1]
    export = root / "build/processed-output/export-baseline-20261031-a/generate_netlist/processed_output_top_sim.v"
    plan = root / "results/processed-output-reset-20261031-b/plan.json"
    if not export.is_file() or not plan.is_file():
        pytest.skip("actual PDS export is a local provenance-bound artifact")
    return export.read_text(), json.loads(plan.read_text())["NativeQueries"]


def change_cell(text, name, old, new, before=False):
    position = text.index(name)
    start = text.rfind("V_", 0, position) if before else position
    end = text.index(";", position) + 1
    chunk = text[start:end]
    assert old in chunk
    return text[:start] + chunk.replace(old, new, 1) + text[end:]


def test_actual_two_equivalent_roots_and_all_internal_pin_edges(actual):
    text, queries = actual
    result = audit.audit_text(text, queries)
    assert result["DistinctEquivalentClearRootCount"] == 2
    assert result["FirstStageFunctionalFanout"] == 1
    assert result["OutputLoadCount"] == 10
    assert result["InternalFunctionalTargetsVerified"] == 126
    assert result["TimingExceptionApplied"] is False


@pytest.mark.parametrize("mutation,reason", [
    ("pll_clear_function", "truth table"),
    ("pll_clear_dependency", "unexpected dependency"),
    ("second_stage_clear", "share clock and clear"),
    ("first_stage_extra_alias", "unparsed alias"),
    ("cpd_reset_disconnected", "actual direct reset target"),
])
def test_actual_critical_mutations_are_rejected(actual, mutation, reason):
    text, queries = actual
    if mutation == "pll_clear_function":
        text = change_cell(text, "N104_inv_copy/gateop_perm/FYA/LUT6CARRY", "64'h00FF00FFFFFFFFFF", "64'h0000000000000000", before=True)
    elif mutation == "pll_clear_dependency":
        text = change_cell(text, "N104_inv_copy/gateop_perm/FYA/LUT6CARRY", ".I3 (power_ready)", ".I3 (other_signal)")
    elif mutation == "second_stage_clear":
        text = change_cell(text, "u_ddrphy_rst_seq_rstn_sync/sig_async_r1[0]/opit_0_srl/FFAPP3/FF", ".SR (N104_inv)", ".SR (N104_inv_1)")
    elif mutation == "first_stage_extra_alias":
        text = text.replace("endmodule", "assign unexpected = \\CLMA_327_696/ntQ3 ;\nendmodule", 1)
    else:
        text = change_cell(text, "u_ddrphy_cpd/cpd_inst/CPD", ".RST (\\u_ddr3_test_h/u_ddrphy_top/ddrphy_cpd_rstn )", ".RST (wrong_reset)")
    with pytest.raises(ValueError, match=reason):
        audit.audit_text(text, queries)
