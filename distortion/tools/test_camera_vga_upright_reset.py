"""Small CPU-only tests for the upright identity and coverage adapter."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import audit_camera_vga_upright_reset as audit


def fixture():
    source = audit.scope.IP + "ddrphy_reset_ctrl/ddrphy_iol_rst/new_ff/CLK"
    paths, summaries = [], {}
    for corner in ("slow", "fast"):
        summaries[(corner, "rst_clk", "phy_dq_clk_0")] = {"WNS": "-1.000", "TNS": "-1.500", "Failing": 2, "Total": 2}
        for index in range(2):
            target = audit.scope.SLICE + f"i_ca_group[{index}].u_tserdes_ca0/new_serializer/TSR"
            paths.append({"Source": source, "Endpoint": target, "LaunchClock": "rst_clk", "CaptureClock": "phy_dq_clk_0",
                          "Corner": corner, "Family": "iol_reset", "LaunchEdge": "rising", "CaptureEdge": "rising",
                          "LaunchDataTransition": "r", "SlackNS": "-1.000" if index == 0 else "-0.500",
                          "SlackState": "VIOLATED", "NativeReportLine": index + 1,
                          "NativePathSHA256": corner + str(index)})
    return paths, summaries


def receipt(mode="query"):
    stages = [] if mode == "query" else ["Report Timing", "Generate Netlist"]
    return {"Schema": audit.inspect.SCHEMA, "Target": audit.prep.TARGET, "Mode": mode,
            "ExecutionPassed": True, "ExitCode": 0, "TimedOut": False, "StoppedForUnexpectedStage": False,
            "InputDrift": [], "Diagnostics": [], "CompletionMarker": True, "InputADFUnchanged": True,
            "Cleanup": {"Complete": True}, "ExpectedActualStages": stages,
            "ActualEvents": [[s, e] for s in stages for e in ("started", "done")],
            "HardwareAccessed": False, "BitstreamRequested": False, "EDAExecuted": True, "SourceADFSHA256": "fresh"}


class UprightResetTests(unittest.TestCase):
    def test_new_actual_counts_not_historical_totals(self):
        inventory = audit.scope.audit_inventory(*fixture())
        queries, _, fdc = audit.scope.query_scope(inventory)
        self.assertEqual(audit.summary(inventory)["LogicalChecksByCorner"], {"slow": 2, "fast": 2})
        self.assertEqual([q["ExpectedTargetCount"] for q in queries], [2])
        self.assertIn("new_ff", fdc)
        self.assertNotIn("set_clock_groups", fdc)

    def test_missing_new_endpoint_blocks_proposal(self):
        paths, summaries = fixture()
        with self.assertRaises(ValueError):
            audit.scope.audit_inventory(paths[:-1], summaries)
        incomplete = audit.scope.audit_inventory(paths[:-1], summaries, require_complete=False)
        with self.assertRaises(ValueError):
            audit.scope.query_scope(incomplete)

    def test_data_pin_cannot_enter_reset_scope(self):
        paths, summaries = fixture()
        paths[0]["Endpoint"] = paths[0]["Endpoint"].replace("/TSR", "/D")
        with self.assertRaises(ValueError):
            audit.scope.audit_inventory(paths, summaries)

    def test_report_adapter_changes_only_design_token(self):
        text = "| Design : camera_vga_upright_top\nStartpoint : fresh_N999/CLK\nEndpoint : a/upright/D\n"
        captured = []
        def reader(path):
            captured.append(Path(path).read_text())
            return [], {}
        with tempfile.TemporaryDirectory() as temp:
            report = Path(temp) / "new.rtr"
            report.write_text(text)
            with patch.object(audit.scope, "parse_report", side_effect=reader):
                _, _, adapter = audit.parse_report(report)
            self.assertEqual(report.read_text(), text)
        self.assertEqual(captured, [text.replace("| Design : camera_vga_upright_top", "| Design : camera_vga_output_top")])
        self.assertEqual(adapter["HeaderReplacements"], 1)

    def test_old_or_duplicate_report_identity_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            report = Path(temp) / "wrong.rtr"
            for text in ("| Design : camera_vga_output_top\n", "| Design : camera_vga_upright_top\n" * 2):
                report.write_text(text)
                with self.assertRaises(ValueError):
                    audit.parse_report(report)

    def test_netlist_adapter_preserves_actual_net_and_cell_names(self):
        text = "module camera_vga_upright_top\n(input a);\nV_FFASYN fresh_cell (.Q(_Nnew));\nendmodule\n"
        self.assertEqual(audit.adapt_netlist(text), text.replace("module camera_vga_upright_top", "module camera_vga_output_top"))
        for wrong in (text.replace("camera_vga_upright_top", "camera_vga_output_top"), text + text):
            with self.assertRaises(ValueError):
                audit.adapt_netlist(wrong)

    def test_native_exact_names_not_just_counts(self):
        queries, _, _ = audit.scope.query_scope(audit.scope.audit_inventory(*fixture()))
        lines = []
        for query in queries:
            for pattern, names in ((query["FromRegex"], [query["Source"]]), (query["ToRegex"], query["Targets"])):
                lines.append("I: Timing-5001: The pattern '" + pattern + "' in command 'get_pins -hierarchical -regexp {" + pattern
                             + "}' match " + str(len(names)) + " objects below: " + " ".join("t:" + n for n in names))
        with tempfile.TemporaryDirectory() as temp:
            log = Path(temp) / "stdout.log"
            log.write_text("\n".join(lines))
            self.assertEqual(len(audit.exact_queries(queries, log)), 2)
            pattern = queries[0]["FromRegex"]
            unquoted = lines.copy()
            unquoted[0] = unquoted[0].replace("-regexp {" + pattern + "}", "-regexp " + pattern)
            log.write_text("\n".join(unquoted))
            self.assertEqual(len(audit.exact_queries(queries, log)), 2)
            bad = lines.copy()
            bad[0] = bad[0].rsplit("t:", 1)[0] + "t:old_ff/CLK"
            for mutated in (bad, lines[:-1], lines + [lines[0]]):
                log.write_text("\n".join(mutated))
                with self.assertRaises(ValueError):
                    audit.exact_queries(queries, log)

    def test_clean_new_receipt_identity(self):
        audit.receipt_status(receipt(), "query", "fresh")
        audit.receipt_status(receipt("export"), "export", "fresh")

    def test_old_schema_wrong_adf_or_unclean_receipt_rejected(self):
        for key, value in (("Schema", "camera-vga-isolated-query-v1"), ("Target", "camera_vga_output_top"),
                           ("SourceADFSHA256", "old"), ("ExecutionPassed", False), ("InputDrift", ["source"]),
                           ("Diagnostics", ["error"]), ("StoppedForUnexpectedStage", True), ("CompletionMarker", False),
                           ("InputADFUnchanged", False), ("Cleanup", {"Complete": False}), ("BitstreamRequested", True)):
            candidate = receipt()
            candidate[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                audit.receipt_status(candidate, "query", "fresh")

    def test_export_stage_events_not_inherited(self):
        candidate = receipt("export")
        candidate["ActualEvents"] = []
        with self.assertRaises(ValueError):
            audit.receipt_status(candidate, "export", "fresh")


if __name__ == "__main__":
    unittest.main()
