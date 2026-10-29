"""Tiny synthetic CPU contracts; no retained DDR artifacts, EDA or hardware."""
from pathlib import Path
import json
import sys
import xml.etree.ElementTree as ET

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import audit_ddr_reference as audit


def idf(path, *, width="32", version="1.10"):
    root = ET.Element("ip_inst")
    header = ET.SubElement(root, "header")
    for key, value in {"name": "synthetic HMIC", "version": version, "device": "PG2L100H"}.items():
        ET.SubElement(header, key).text = value
    params = ET.SubElement(root, "param_list")
    for key, value in {"MEM_TYPE": "DDR3", "MEM_DQ_WIDTH": width, "BANK_NUM": "2",
                       "MEM_ADDR_WIDTH": "15", "MEM_BANK_WIDTH": "3", "CTRL_ADDR_WIDTH": "28",
                       "CLKIN_FREQ": "125.000", "DFI_CLK_PERIOD": "8000"}.items():
        param = ET.SubElement(params, "param")
        ET.SubElement(param, "name").text = key
        ET.SubElement(param, "value").text = value
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)


def timing(path, *, current=False):
    root = ET.Element("tables")

    def add(name, headers, rows):
        table = ET.SubElement(root, "table", id=name)
        headings = ET.SubElement(table, "column_headers")
        for header in headers:
            ET.SubElement(headings, "data").text = header
        for values in rows:
            row = ET.SubElement(table, "row")
            for value in values:
                ET.SubElement(row, "data").text = str(value)
        return table

    for kind in audit.KINDS:
        mpw = kind.endswith("mpw")
        slack = "WPWS" if mpw else "WHS(ns)" if kind.endswith(("hold", "removal")) else "WNS(ns)"
        headers = (["Clock", slack, "Failing End Point", "Total End Point"] if mpw else
                   ["Launch Clock", "Capture Clock", slack, "Failing Endpoints", "Total Endpoints"])
        rows = [["ddrphy_sysclk", "1", "0", "10"]] if mpw else [["ddrphy_sysclk", "ddrphy_sysclk", "1", "0", "10"]]
        if current and kind.endswith("recovery"):
            rows += [[a, b, "-1", count, count] for (a, b), count in zip(audit.EXCLUDED_DDR_PAIRS, (34, 3, 35, 84, 4, 84))]
            rows += [["board27", "rst_clk", "-1", 1, 1]]
        add("report_timing_"+kind, headers, rows)
    add("report_timing_clock_summary", ["Clock Name", "Period"],
        [["free_clk", "20"], ["ref_clk", "8"], ["ddrphy_sysclk", "8"]])
    rows = [["ddrphy_sysclk", "ddrphy_sysclk", "Timed", "10", "10"]]
    rows += [[a, b, "Asynchronous Groups", n, n] for (a, b), n in zip(audit.EXCLUDED_DDR_PAIRS, (34, 3, 35, 84, 4, 84))]
    add("report_clock_interaction", ["Launch Clock", "Capture Clock", "Inter-Clock Constrains",
                                      "Total End Point(TNS)", "Total End Point(THS)"], rows)
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)


@pytest.fixture
def inputs(tmp_path):
    reference, project = tmp_path / "synthetic-reference", tmp_path / "synthetic-project"
    current = project / audit.IP_RELATIVE
    for path in (reference, current, reference / "pnr/report_timing", project / "board"):
        path.mkdir(parents=True, exist_ok=True)
    idf(reference / "ddr3_test.idf")
    idf(current / "ddr3_test.idf")
    for name in ("unit.vp", "wrapper.v"):
        # This is deliberately plain synthetic material; no vendor body fixture.
        data = ("SYNTHETIC HASH-ONLY SOURCE " + name).encode()
        (reference/name).write_bytes(data)
        (current/name).write_bytes(data)
    names = [(audit.IP_RELATIVE/name).as_posix() for name in ("ddr3_test.idf", "unit.vp", "wrapper.v")]
    manifest = project / "board/board1080-cdc-reset-sources.json"

    def bind():
        manifest.write_text(json.dumps({"source_files": names,
            "SourceSHA256": {name: audit.sha(project/name) for name in names}}), encoding="utf-8")

    bind()
    fdc = """# synthetic constraints, not a board or a waiver
create_clock -name {ref_clk} [get_ports {ref_clk_p}] -period {8.0}
create_clock -name {free_clk} [get_ports {free_clk}] -period {20}
create_generated_clock -name {ddrphy_sysclk} -source [get_ports {ref_clk_p}] [get_pins {I_ips_ddr_top.u_ddrphy_top.ddrphy_gpll/clkout0}] -divide_by {1}
set_multicycle_path 2 -from [get_clocks {ddrphy_sysclk}] -to [get_clocks {phy_dq_sysclk_0}]
set_clock_uncertainty {0.4} -from [get_clocks {ddrphy_sysclk}] -to [get_clocks {phy_dq_sysclk_0}]
define_attribute {i:I_ips_ddr_top.u_ddrphy_top.ddrphy_reset_ctrl.ddrphy_ioclk_gate[0]} {PAP_LOC} {CLMA_357_354:FF3}
set_clock_groups -name rst_clk -asynchronous -group [get_clocks {rst_clk}]
"""
    (reference / "pnr/ddr_test.fdc").write_text(fdc, encoding="utf-8")
    current_fdc = project / "board/board1080-cdc-reset-diagnostic.fdc"
    current_fdc.write_text(fdc.replace("I_ips_ddr_top", "u_ddr3_test_h").replace("ref_clk_p", "clk_p")
                           .replace("free_clk", "board27"), encoding="utf-8")
    timing(reference / "pnr/report_timing/rtr.db")

    def run(**kwargs):
        return audit.audit_reference(reference, project, expected_source_count=2, expected_vp_count=1, **kwargs)

    return {"reference": reference, "project": project, "current": current, "manifest": manifest,
            "current_fdc": current_fdc, "bind": bind, "run": run, "root": tmp_path}


def test_complete_synthetic_audit_counts_hashes_and_no_hardware_acceptance(inputs):
    result = inputs["run"]()
    assert result["IDF"]["BytesIdentical"] and result["IDF"]["AllParametersIdentical"]
    assert result["IDF"]["HeaderIdentical"]
    assert result["SourceClosure"]["SynthesisSourceCount"] == 2
    assert result["SourceClosure"]["EncryptedVPCount"] == 1
    assert result["SourceClosure"]["AllSourceBytesIdentical"]
    assert result["SourceClosure"]["AllCurrentManifestBindingsMatch"]
    summary = result["ReferenceTiming"]
    assert set(summary["TimingSummaryCounts"]) == set(audit.KINDS)
    assert all(counts == {"Groups": 1, "FailingGroups": 0, "FailedChecks": 0, "TotalChecks": 10}
               for counts in summary["TimingSummaryCounts"].values())
    assert summary["ExactSixExcludedDDRClockPairsObserved"]
    assert summary["ExcludedDDRTNSChecks"] == summary["ExcludedDDRTHSChecks"] == 244
    assert summary["ClocksWithoutFullSameClockSetupHold"] == ["board27", "ref_clk"]
    assert result["Scope"] == "ReferenceOnly" and result["CurrentEndpointIdentityUnverified"]
    assert result["DiagnosticOnly"]
    for name in ("HardwareReleaseAllowed", "PhysicalTimingReady", "CurrentRecoveryResolved",
                 "CurrentEndpointIdentityProven", "HardwareAccessed", "EDAStarted"):
        assert result[name] is False


@pytest.mark.parametrize("kind", audit.KINDS)
def test_each_of_ten_timing_summary_tables_is_required(inputs, kind):
    path = inputs["reference"] / "pnr/report_timing/rtr.db"
    tree = ET.parse(path)
    root = tree.getroot()
    root.remove(next(t for t in root if t.get("id") == "report_timing_"+kind))
    tree.write(path)
    with pytest.raises(ValueError, match="timing table"):
        inputs["run"]()


@pytest.mark.parametrize("table", ["report_timing_clock_summary", "report_clock_interaction"])
def test_clock_coverage_tables_are_required(inputs, table):
    path = inputs["reference"] / "pnr/report_timing/rtr.db"
    tree = ET.parse(path)
    tree.getroot().remove(next(t for t in tree.getroot() if t.get("id") == table))
    tree.write(path)
    with pytest.raises(ValueError, match="timing table"):
        inputs["run"]()


@pytest.mark.parametrize("change", ["geometry", "header"])
def test_idf_full_parameters_and_header_differences_are_visible(inputs, change):
    idf(inputs["current"] / "ddr3_test.idf", width="16" if change == "geometry" else "32",
        version="1.7" if change == "header" else "1.10")
    inputs["bind"]()
    result = inputs["run"]()["IDF"]
    assert not result["BytesIdentical"]
    if change == "geometry":
        assert result["DifferingParameters"] == ["MEM_DQ_WIDTH"]
        assert result["ReferenceParametersSHA256"] != result["CurrentParametersSHA256"]
    else:
        assert not result["HeaderIdentical"]
        assert result["ReferenceHeaderSHA256"] != result["CurrentHeaderSHA256"]


def test_hash_mismatch_and_manifest_binding_mismatch_are_distinct(inputs):
    (inputs["current"] / "unit.vp").write_bytes(b"SYNTHETIC CHANGED SOURCE")
    result = inputs["run"]()["SourceClosure"]
    assert not result["AllSourceBytesIdentical"]
    assert not result["AllCurrentManifestBindingsMatch"]
    inputs["bind"]()
    result = inputs["run"]()["SourceClosure"]
    assert not result["AllSourceBytesIdentical"] and result["AllCurrentManifestBindingsMatch"]


@pytest.mark.parametrize("side", ["reference", "current"])
def test_missing_compiled_source_is_rejected(inputs, side):
    (inputs[side] / "unit.vp").unlink()
    with pytest.raises(ValueError, match="source missing"):
        inputs["run"]()


def test_expected_source_and_vp_counts_are_enforced(inputs):
    with pytest.raises(ValueError, match="closure count"):
        audit.audit_reference(inputs["reference"], inputs["project"])


def test_clock_group_differences_do_not_become_timing_waivers(inputs):
    path = inputs["current_fdc"]
    path.write_text("\n".join(line for line in path.read_text().splitlines() if not line.startswith("set_clock_groups")))
    result = inputs["run"]()
    categories = result["Constraints"]["Categories"]
    assert all(categories[k]["Identical"] for k in ("DDRClocks", "DDRGeneratedClocks", "DDRMulticycle", "DDRUncertainty", "DDRPAP_LOC"))
    assert categories["AsyncGroups"]["OnlyReference"] == ["set_clock_groups -name rst_clk -asynchronous -group [get_clocks rst_clk]"]
    assert not categories["AsyncGroups"]["Identical"] and not result["CurrentRecoveryResolved"]


def test_support_clock_period_difference_is_not_normalized_away(inputs):
    path = inputs["current_fdc"]
    path.write_text(path.read_text().replace("-period {20}", "-period {37.037037}"))
    assert not inputs["run"]()["Constraints"]["Categories"]["SupportClocks"]["Identical"]


def test_current_xml_and_adf_must_be_supplied_together(inputs):
    with pytest.raises(ValueError, match="provided together"):
        inputs["run"](current_xml=inputs["root"] / "missing.xml")
    with pytest.raises(ValueError, match="provided together"):
        inputs["run"](current_final_adf=inputs["root"] / "missing.adf")


def test_current_recovery_count_match_never_proves_endpoint_identity(inputs):
    xml, adf = inputs["root"] / "synthetic-current.xml", inputs["root"] / "synthetic-final.adf"
    timing(xml, current=True)
    adf.write_bytes(b"SYNTHETIC ADF HASH FIXTURE; NOT A REAL ROUTED DESIGN")
    result = inputs["run"](current_xml=xml, current_final_adf=adf)
    assert result["CurrentFinalADF"]["SHA256"] == audit.sha(adf)
    assert result["CurrentTiming"]["TimingSummaryCounts"]["slow_recovery"]["FailedChecks"] == 245
    comparison = result["RecoveryCountComparison"]
    assert comparison["CountMatchNotEndpointIdentityProven"]
    assert all(v["AllCountsMatch"] for v in comparison["CornerComparisons"].values())
    assert not result["CurrentRecoveryResolved"] and not result["CurrentEndpointIdentityProven"]
    assert not result["CurrentXMLToADFBindingIndependentlyVerified"]


def test_cli_never_overwrites_existing_output(tmp_path):
    path = tmp_path / "existing.json"
    path.write_bytes(b"preserved synthetic evidence")
    with pytest.raises(SystemExit):
        audit.main(["--output", str(path)])
    assert path.read_bytes() == b"preserved synthetic evidence"
