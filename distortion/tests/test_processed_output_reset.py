"""The top-name adapter must not weaken the existing reset checks."""
from pathlib import Path
import sys
import copy

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import audit_processed_output_reset as tool
import prepare_processed_output_reset_scope as scope
import audit_processed_output_reset_query as query_audit
from test_ddr_entry_reset_netlist import fixture


def candidate_fixture():
    return fixture().replace("module board1080_top;", "module processed_output_top;")


def test_valid_candidate_uses_strict_checker_without_changing_input():
    text = candidate_fixture()
    before = text
    result = tool.audit_entry_text(text)
    assert text == before
    assert result["Status"] == "pass"
    assert result["FirstStageFunctionalFanout"] == 1
    assert result["TopDeclarationAdapter"]["OnlyModuleDeclarationTokenChangedInMemory"]
    assert result["TimingExceptionApplied"] is False


@pytest.mark.parametrize("text", [fixture(), candidate_fixture() + "module other;\nendmodule\n",
                                 "// module processed_output_top;\n" + fixture()])
def test_different_or_ambiguous_actual_top_is_rejected(text):
    with pytest.raises(ValueError, match="one actual processed_output_top"):
        tool.audit_entry_text(text)


def test_comment_does_not_become_a_declaration():
    assert tool.audit_entry_text("/* module other; */\n" + candidate_fixture())["Status"] == "pass"


@pytest.mark.parametrize("before,after,reason", [
    (".CE(1'b1)", ".CE(1'b0)", "CE"),
    (".RST(clear)", ".RST(other_reset)", "PLL reset"),
    ("endmodule", "assign bad = \\site/middle ;\nendmodule", "unparsed references"),
    ("endmodule", "V_BUF extra (.Z(bad), .I(\\site/middle ));\nendmodule", "functional fanout"),
])
def test_entry_connectivity_rejections_survive_adapter(before, after, reason):
    with pytest.raises(ValueError, match=reason):
        tool.audit_entry_text(candidate_fixture().replace(before, after))


def entry_report():
    blocks = ["| Design : processed_output_top\n"]
    for corner in ("slow", "fast"):
        blocks.append(f"Recovery Summary({corner.title()} Corner):\n board27 rst_clk -1.000 -1.000 1 1\n"
                      f"Removal Summary({corner.title()} Corner):\n")
    for corner in ("slow", "fast"):
        blocks.append(f"Startpoint : {scope.ENTRY_SOURCE}\nEndpoint : {scope.ENTRY_TARGET}\n"
                      f"Path Group : rst_clk\nPath Type : max ({corner} corner)\n"
                      "Path Class : async timing path\n Clock board27 (rising edge)\n"
                      " Clock rst_clk (rising edge)\n Recovery time 0.1\n Slack (VIOLATED) -1.000\n")
    return "".join(blocks)


def test_entry_both_corners_match_summary_and_do_not_include_other_groups():
    text = entry_report() + "Startpoint : unrelated\nPath Group : pixel_clk\n Recovery time 0.1\n"
    assert {p["Corner"] for p in scope.entry_checks(text)} == {"slow", "fast"}


@pytest.mark.parametrize("before,after,reason", [
    ("-1.000 -1.000 1 1", "-1.000 -1.000 1 2", "summary does not match"),
    ("-1.000 -1.000 1 1", "-1.001 -1.001 1 1", "summary does not match"),
    ("max (fast corner)", "max (slow corner)", "one entry check per corner"),
    (scope.ENTRY_TARGET, scope.ENTRY_TARGET.replace("/RS", "/D"), "entry pins differ"),
    ("processed_output_top", "board1080_top", "not for processed_output_top"),
])
def test_entry_partial_wrong_or_summary_mismatch_rejects(before, after, reason):
    with pytest.raises(ValueError, match=reason):
        scope.entry_checks(entry_report().replace(before, after))


def queries_fixture():
    queries, records = [], []
    for group, count in enumerate((1, 1, 7, 14, 104)):
        source = f"group{group}/source/CLK"
        targets = [f"group{group}/load{i}/RST" for i in range(count)]
        item = {"Source": source, "Targets": targets, "ExpectedFromCount": 1,
                "ExpectedTargetCount": count, "FromRegex": f"group{group}from",
                "ToRegex": f"group{group}to", "ExpectedNativeFromNames": ["t:" + source],
                "ExpectedNativeToNames": ["t:" + target for target in targets], "EntryRDC": group == 0}
        queries.append(item)
        records.extend([{ "Pattern": item["FromRegex"], "Count": 1, "NativeNames": item["ExpectedNativeFromNames"]},
                        { "Pattern": item["ToRegex"], "Count": count, "NativeNames": item["ExpectedNativeToNames"]}])
    return copy.deepcopy(queries), copy.deepcopy(records)


def test_exact_query_matches_retain_all_132_native_objects():
    queries, records = queries_fixture()
    result = query_audit.match_queries(queries, records)
    assert len(result) == 10
    assert sum(p["NativeEvidence"]["Count"] for p in result) == 132


@pytest.mark.parametrize("mutation", ["missing", "extra", "wrong_name", "wrong_count", "wrong_pattern"])
def test_native_query_missing_extra_or_wrong_evidence_is_rejected(mutation):
    queries, records = queries_fixture()
    if mutation == "missing":
        records.pop()
    elif mutation == "extra":
        records.append(copy.deepcopy(records[0]))
    elif mutation == "wrong_name":
        records[0]["NativeNames"] = ["t:wrong/source/CLK"]
    elif mutation == "wrong_count":
        records[-1]["Count"] = 103
    else:
        records[0]["Pattern"] = "wrong"
    with pytest.raises(ValueError):
        query_audit.match_queries(queries, records)
