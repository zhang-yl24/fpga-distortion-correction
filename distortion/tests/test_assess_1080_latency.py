"""Independent synthetic event-contract tests, never physical latency evidence."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
import assess_1080_evidence as e


def fixture():
    """Known event differences: 4, 5, 10ms; arbitrary unique text IDs, no frame-ID schema."""
    identity = {"camera_id": "synthetic-camera", "lens_id": "synthetic-lens",
                "profile_id": "synthetic-profile", "capture_mode_id": "synthetic-1080",
                "image_size": [1920, 1080], "pixel_format": "RGB565_LE"}
    requirements = {"threshold_origin": "operator_engineering", "target_new_frame_fps": 1.,
                    "minimum_fps_window_seconds": 1., "maximum_sample_gap_seconds": 1.,
                    "minimum_stability_window_seconds": 1., "maximum_temperature_c": 60.,
                    "maximum_external_latency_ms": 10., "minimum_latency_events": 3,
                    "minimum_temperature_samples": 2, "maximum_line_deviation_px": 1.,
                    "minimum_detail_score": .2, "detail_score_unit": "synthetic_score"}
    record = {"evidence_kind": "synthetic_tool_test", "synthetic_tool_fixture": True,
              "identity": copy.deepcopy(identity), "method": "external_same_source_event",
              "scope": "source_event_to_output_observation", "external_observer": "synthetic-observer-no-instrument",
              "clock_id": "synthetic-external-clock", "samples": [
                  {"event_id": "synthetic-blue", "input_event_ns": 1000000000, "output_event_ns": 1004000000},
                  {"event_id": "synthetic-mark-A", "input_event_ns": 1001000000, "output_event_ns": 1006000000},
                  {"event_id": "synthetic-label-Z", "input_event_ns": 1002000000, "output_event_ns": 1012000000}]}
    return {"schema": 1, "evidence_kind": "synthetic_tool_test", "synthetic_tool_fixture": True,
            "run_id": "synthetic-latency-contract-only", "identity": identity,
            "requirements": requirements, "external_latency": record}


class LatencyContractTests(unittest.TestCase):
    def check_result(self, data, status, reason=None, base_dir=TOOLS):
        result = e.assess(data, base_dir=base_dir)
        check = result["record_checks"]["external_latency"]
        self.assertEqual(check["status"], status, check)
        if reason:
            self.assertIn(reason, check["reason"])
        self.assertEqual(result["real_acceptance_status"], "UNMEASURED")
        self.assertTrue(all(v["status"] == "UNMEASURED" for v in result["real_evidence_checks"].values()))
        self.assertTrue(all(result[k] is False for k in e.FALSE_FLAGS))
        self.assertFalse(result["hardware_accessed"])
        self.assertFalse(result["hardware_plan_generated"])
        return check

    def test_known_external_events_and_exact_declared_limit_are_accepted_only_as_synthetic(self):
        check = self.check_result(fixture(), "PASS")
        self.assertEqual(check["details"], {"events": 3, "minimum_latency_ms": 4., "maximum_latency_ms": 10.})

    def test_output_before_input_rejected(self):
        data = fixture(); data["external_latency"]["samples"][0]["output_event_ns"] = 999999999
        self.check_result(data, "FAIL", "output event precedes input event")

    def test_each_event_time_must_increase_even_when_every_delay_is_within_limit(self):
        for field, values in (("input_event_ns", (1000000000, 999000000)),
                              ("output_event_ns", (1004000000, 1003000000))):
            for value in values:
                with self.subTest(field=field, value=value):
                    data = fixture(); rows = data["external_latency"]["samples"]
                    rows[1][field] = value
                    self.assertTrue(all(0 <= row["output_event_ns"]-row["input_event_ns"] <= 10000000 for row in rows))
                    self.check_result(data, "FAIL", "timestamps must strictly increase")

    def test_one_nanosecond_over_declared_limit_rejected(self):
        data = fixture(); data["external_latency"]["samples"][-1]["output_event_ns"] += 1
        self.check_result(data, "FAIL", "delay exceeds the declared limit")

    def test_missing_event_fields_are_invalid_records_not_missing_evidence(self):
        for field in ("event_id", "input_event_ns", "output_event_ns"):
            with self.subTest(field=field):
                data = fixture(); del data["external_latency"]["samples"][1][field]
                self.check_result(data, "FAIL", field)

    def test_event_timestamp_types_are_not_parsed_or_coerced(self):
        for field in ("input_event_ns", "output_event_ns"):
            for value in (None, "1001000000", "not-a-time", True, 1001000000., -1, [], {}):
                with self.subTest(field=field, value=value):
                    data = fixture(); data["external_latency"]["samples"][1][field] = value
                    self.check_result(data, "FAIL", field + " must be an integer")

    def test_nonfinite_event_timestamps_rejected(self):
        for field in ("input_event_ns", "output_event_ns"):
            for value in (float("nan"), float("inf"), float("-inf")):
                with self.subTest(field=field, value=str(value)):
                    data = fixture(); data["external_latency"]["samples"][1][field] = value
                    self.check_result(data, "FAIL", field + " must be an integer")

    def test_missing_or_invalid_method_scope_observer_and_clock_rejected(self):
        for field in ("method", "scope", "external_observer", "clock_id"):
            with self.subTest(missing=field):
                data = fixture(); del data["external_latency"][field]
                self.check_result(data, "FAIL")
        for field in ("scope", "external_observer", "clock_id"):
            with self.subTest(invalid=field):
                data = fixture(); data["external_latency"][field] = " "
                self.check_result(data, "FAIL")

    def test_minimum_event_count_is_enforced_separately_from_sample_shape(self):
        data = fixture(); data["external_latency"]["samples"].pop()
        self.check_result(data, "FAIL", "too few independent external events")
        for rows in (None, {}, [], [fixture()["external_latency"]["samples"][0]], [None, None, None]):
            with self.subTest(rows=rows):
                data = fixture(); data["external_latency"]["samples"] = rows
                self.check_result(data, "FAIL")

    def test_invalid_event_ids_rejected_without_inventing_numeric_id_order(self):
        # Duplicate-ID rejection already has a direct test in test_assess_1080_evidence.
        for value in (None, "", " ", 1, True, []):
            with self.subTest(value=value):
                data = fixture(); data["external_latency"]["samples"][1]["event_id"] = value
                self.check_result(data, "FAIL", "event_id must be a nonempty string")

    def test_latency_record_identity_matches_the_manifest(self):
        for field, value in (("camera_id", "wrong-camera"), ("lens_id", "wrong-lens"),
                             ("profile_id", "wrong-profile"), ("capture_mode_id", "wrong-mode"),
                             ("image_size", [640, 480]), ("pixel_format", "RGB888")):
            with self.subTest(field=field):
                data = fixture(); data["external_latency"]["identity"][field] = value
                self.check_result(data, "FAIL")

    def test_absent_evidence_is_unmeasured_but_present_bad_records_fail(self):
        for section in (None, {"record": None}, {"record": {"path": "missing-synthetic.json", "sha256": "0"*64}}):
            with self.subTest(section=section):
                data = fixture(); data["external_latency"] = section
                self.check_result(data, "UNMEASURED")
        data = fixture(); del data["external_latency"]
        self.check_result(data, "UNMEASURED")
        self.check_result({**fixture(), "external_latency": {}}, "FAIL")
        with tempfile.TemporaryDirectory(prefix="synthetic-latency-") as folder:
            base = Path(folder); path = base / "synthetic-record.json"
            records = (json.dumps(fixture()["external_latency"]), "{broken-json", "[]", "{}",
                       json.dumps({**fixture()["external_latency"], "samples": [
                           {"event_id": "synthetic-nonfinite", "input_event_ns": float("nan"), "output_event_ns": 0}]}))
            for index, content in enumerate(records):
                with self.subTest(file_record=index):
                    path.write_text(content, encoding="utf-8")
                    data = fixture(); data["external_latency"] = {"record": {"path": path.name, "sha256": e.sha(path)}}
                    check = self.check_result(data, "PASS" if index == 0 else "FAIL", base_dir=base)
                    if index == 4: self.assertIn("nonfinite JSON", check["reason"])

    def test_large_epoch_with_small_delays_does_not_invent_an_absolute_clock_limit(self):
        data = fixture()
        for row in data["external_latency"]["samples"]:
            row["input_event_ns"] += 10**1000
            row["output_event_ns"] += 10**1000
        self.assertEqual(self.check_result(data, "PASS")["details"]["maximum_latency_ms"], 10.)
        # Scale the integer difference before converting to float: this quotient
        # is finite even though converting the nanosecond difference first is not.
        data = fixture(); data["requirements"]["maximum_external_latency_ms"] = 1e304
        for row in data["external_latency"]["samples"]:
            row["output_event_ns"] = row["input_event_ns"] + 10**309
        self.assertEqual(self.check_result(data, "PASS")["details"]["maximum_latency_ms"], 1e303)

    def test_unrepresentable_delay_is_a_failed_record_not_an_uncaught_exception(self):
        data = fixture(); data["external_latency"]["samples"][-1]["output_event_ns"] = 10**1000
        self.check_result(data, "FAIL", "delay exceeds the declared limit")


if __name__ == "__main__":
    unittest.main()
