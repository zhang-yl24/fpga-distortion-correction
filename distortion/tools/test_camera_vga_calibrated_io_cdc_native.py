"""CPU checks for complete actual pair/Gray/site evidence, without native EDA."""
from pathlib import Path
import tempfile
import unittest

import audit_camera_vga_calibrated_io_cdc_native as audit


def query(source="new/meta/CLK", endpoint="new/sample/D", clock="board27"):
    return {"Source": source, "Endpoint": endpoint, "Clock": clock, "Label": source}


def rows(queries):
    return [{"Source": q["Source"], "Endpoint": q["Endpoint"], "Corner": corner, "Kind": kind, "SlackNS": 0.1}
            for q in queries for corner in ("slow", "fast") for kind in ("setup", "hold")]


class NativeCompletionTests(unittest.TestCase):
    def test_batch_preserves_actual_pairs_without_historical_counts(self):
        queries = [query(), query("new/cam_meta/CLK", "new/cam_sample/D", "camera_pclk"),
                   query("system/new/reset_sync[0]/ff/CLK", "system/new/reset_sync[1]/ff/D", "ddrphy_sysclk"),
                   query("system/new/reset_sync[0]/ff/CLK", "system/new/reset_sync[1]/replica/D", "ddrphy_sysclk")]
        plan = {"Queries": queries, "GrayCoverageQueries": [{"Source": "fifo/gray7/CLK", "Endpoint": "fifo/meta7/D"}], "IOSites": ["IO_1_2"]}
        body, groups = audit.batch_body(plan)
        expected = {(q["Source"], q["Endpoint"]) for q in queries + plan["GrayCoverageQueries"]}
        observed = {(q["Source"], q["Endpoint"]) for group in groups for q in group["ExpectedPairs"]}
        self.assertEqual(expected, observed)
        self.assertEqual(len(groups), 4)
        self.assertIn("-max_path 1000 -nworst 8", body)
        self.assertEqual(len(audit.inspect.query_commands(body)), 6)

    def test_batch_rejects_injected_native_command(self):
        plan = {"Queries": [query(endpoint="name}; save_adif;")], "GrayCoverageQueries": [], "IOSites": []}
        with self.assertRaises(ValueError):
            audit.batch_body(plan)

    def test_every_exact_pair_needs_four_cases(self):
        queries = [query(), query(endpoint="new/another/D")]
        complete = rows(queries)
        self.assertEqual(len(audit.syntax.coverage(complete, queries)), 4)
        for mutated in (complete[:-1], [r for r in complete if r["Kind"] != "hold"]):
            with self.assertRaises(ValueError):
                audit.syntax.coverage(mutated, queries)

    def test_cross_product_pair_cannot_replace_expected_pair(self):
        queries = [query("a/CLK", "b/D"), query("c/CLK", "d/D")]
        values = rows(queries)
        values[-1] = {**values[-1], "Source": "a/CLK"}
        with self.assertRaises(ValueError):
            audit.syntax.coverage(values, queries)

    def test_gray_source_period_and_complete_corners(self):
        old = {"GrayBitSynchronizers": [{"Group": "fifo", "NativeEndpoint": "fifo/meta/D", "Source": "fifo/gray/FF0/FF"}],
               "GrayPhysicalGroups": [{"Group": "fifo", "Corner": c, "Paths": [], "Constraint": {"BoundNS": 8.0}, "SourcePeriodNS": 8.0}
                                      for c in ("slow", "fast")]}
        records = [{"Source": "fifo/gray/CLK", "Endpoint": "fifo/meta/D", "Corner": c, "BoundNS": 8.0,
                    "SlackNS": 7.0, "ArrivalNS": 1.0} for c in ("slow", "fast")]
        self.assertTrue(all(g["CoverageComplete"] for g in audit.complete_gray(old, records)))
        with self.assertRaises(ValueError):
            audit.complete_gray(old, records[:1])
        with self.assertRaises(ValueError):
            audit.complete_gray(old, [{**r, "ArrivalNS": 8.0} for r in records])
        with self.assertRaises(ValueError):
            audit.complete_gray(old, [{**r, "Source": "old/CLK"} for r in records])
        with self.assertRaises(ValueError):
            audit.complete_gray({**old, "GrayPhysicalGroups": old["GrayPhysicalGroups"][:1]}, records)

    def test_preexisting_gray_paths_are_also_rechecked(self):
        old = {"GrayBitSynchronizers": [{"Group": "fifo", "NativeEndpoint": "fifo/meta/D", "Source": "fifo/gray/FF0/FF"}],
               "GrayPhysicalGroups": [{"Group": "fifo", "Corner": c, "Constraint": {"BoundNS": 8.0}, "SourcePeriodNS": 8.0,
                    "Paths": [{"Source": "fifo/gray/CLK", "Endpoint": "fifo/meta/D", "Corner": c, "BoundNS": 8.0,
                               "SlackNS": -0.01, "ArrivalNS": 8.01}]} for c in ("slow", "fast")]}
        with self.assertRaises(ValueError):
            audit.complete_gray(old, [])

    def test_final_native_site_names_are_exact(self):
        pins = {"PinInventory": [{"Port": "cam_data[5]", "Site": "IO_1_2",
                                   "FinalPrimitiveConnections": [{"NativeInstance": "new_input"}]}]}
        audit.io.apply_native_sites(pins, "Site IO_1_2 (1) :\n\tnew_input (IBUF)\n")
        self.assertTrue(pins["FinalNativeSiteMappingPassed"])
        with self.assertRaises(ValueError):
            audit.io.apply_native_sites(pins, "Site IO_1_2 (1) :\n\told_input (IBUF)\n")


if __name__ == "__main__":
    unittest.main()
