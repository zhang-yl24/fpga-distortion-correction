"""CPU-only negative tests for the camera reset proposal's coverage gate."""
from copy import deepcopy
from pathlib import Path
import hashlib
import unittest

import prepare_camera_vga_reset_scope as scope


def fixture():
    source = scope.IP + "ddrphy_reset_ctrl/ddrphy_iol_rst/fresh_cell/CLK"
    targets = [scope.SLICE + f"i_ca_group[{i}].u_tserdes_ca0/fresh_oserdes/TSR" for i in range(2)]
    paths, summaries = [], {}
    for corner in ("slow", "fast"):
        summaries[(corner, "rst_clk", "phy_dq_clk_0")] = {"WNS": "-1.000", "TNS": "-1.500", "Failing": 2, "Total": 2}
        for index, target in enumerate(targets):
            paths.append({"Source": source, "Endpoint": target, "LaunchClock": "rst_clk",
                          "CaptureClock": "phy_dq_clk_0", "Corner": corner, "Family": "iol_reset",
                          "LaunchEdge": "rising", "CaptureEdge": "rising", "LaunchDataTransition": "r",
                          "SlackNS": "-1.000" if index == 0 else "-0.500", "SlackState": "VIOLATED",
                          "NativeReportLine": index + 1,
                          "NativePathSHA256": hashlib.sha256((corner + target).encode()).hexdigest()})
    return paths, summaries


class CameraResetScopeTests(unittest.TestCase):
    def test_current_report_controls_counts_and_exact_query_names(self):
        paths, summaries = fixture()
        result = scope.audit_inventory(paths, summaries)
        queries, body, fdc = scope.query_scope(result)
        self.assertTrue(result["Complete"])
        self.assertEqual([q["ExpectedTargetCount"] for q in queries], [2])
        self.assertIn("fresh_cell", body)
        self.assertNotIn("set_clock_groups", fdc)
        self.assertNotIn("104", body)

    def test_missing_corner_endpoint_rejected(self):
        paths, summaries = fixture()
        with self.assertRaisesRegex(ValueError, "incomplete current recovery inventory"):
            scope.audit_inventory(paths[:-1], summaries)

    def test_duplicate_variant_rejected(self):
        paths, summaries = fixture()
        with self.assertRaisesRegex(ValueError, "duplicate native"):
            scope.audit_inventory(paths + [deepcopy(paths[0])], summaries)

    def test_data_endpoint_is_never_an_exception(self):
        paths, summaries = fixture()
        paths[0]["Endpoint"] = paths[0]["Endpoint"].replace("/TSR", "/D")
        with self.assertRaisesRegex(ValueError, "non-reset target"):
            scope.audit_inventory(paths, summaries)

    def test_summary_tns_mismatch_rejected(self):
        paths, summaries = fixture()
        summaries[("slow", "rst_clk", "phy_dq_clk_0")]["TNS"] = "-1.499"
        with self.assertRaisesRegex(ValueError, "incomplete current recovery inventory"):
            scope.audit_inventory(paths, summaries)

    def test_unscoped_recovery_failure_rejected(self):
        paths, summaries = fixture()
        summaries[("slow", "board27", "camera_pclk")] = {"WNS": "-1", "TNS": "-1", "Failing": 1, "Total": 1}
        with self.assertRaisesRegex(ValueError, "outside the proposed"):
            scope.audit_inventory(paths, summaries)

    def test_ddc_missing_falling_edge_rejected(self):
        paths, summaries = fixture()
        for path in paths:
            path["Source"] = scope.IP + "ddrphy_reset_ctrl/ddrphy_dqs_rst/fresh_cell/CLK"
            path["Endpoint"] = path["Endpoint"].replace("u_tserdes_ca0/fresh_oserdes/TSR", "u_ddc_ca/ddc_inst/RST")
            path["Family"] = "dqs_reset"
        with self.assertRaisesRegex(ValueError, "capture-edge variant"):
            scope.audit_inventory(paths, summaries)

    def test_incomplete_cannot_generate_fdc(self):
        paths, summaries = fixture()
        result = scope.audit_inventory(paths[:-1], summaries, require_complete=False)
        with self.assertRaisesRegex(ValueError, "incomplete inventory"):
            scope.query_scope(result)

    def test_actual_initial_report_rejected_without_old_endpoint_fallback(self):
        report = Path(__file__).resolve().parents[1] / "work/camera-vga-output/pds-20261031-a/report_timing/camera_vga_output_top.rtr"
        paths, summaries = scope.parse_report(report)
        with self.assertRaises(ValueError):
            scope.audit_inventory(paths, summaries)
        result = scope.audit_inventory(paths, summaries, require_complete=False)
        self.assertFalse(result["Complete"])
        self.assertTrue(result["IncompleteGroups"])


if __name__ == "__main__":
    unittest.main()
