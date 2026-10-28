"""Synthetic checker tests only; these fixtures are not physical acceptance."""
import copy
import hashlib
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
import assess_1080_evidence as e


def ident():
    return {"camera_id": "synthetic-camera", "lens_id": "synthetic-lens", "profile_id": "synthetic-profile",
            "capture_mode_id": "synthetic-native1080", "image_size": [1920, 1080], "pixel_format": "RGB565_LE"}


def requirements():
    # Deliberately tiny synthetic test thresholds, never official/physical targets.
    return {"threshold_origin": "operator_engineering", "target_new_frame_fps": 1.,
            "minimum_fps_window_seconds": 2., "maximum_sample_gap_seconds": 1.,
            "minimum_stability_window_seconds": 2., "maximum_temperature_c": 60.,
            "maximum_external_latency_ms": 10., "minimum_latency_events": 2,
            "minimum_temperature_samples": 3, "maximum_line_deviation_px": 1.,
            "minimum_detail_score": .2, "detail_score_unit": "synthetic_score"}


def frame_record():
    rows = []
    for display, frame in enumerate((0, 1, 1, 2, 2)):
        rows.append({"timestamp_ns": display * 500000000, "display_id": display, "frame_id": frame,
                     "source_timestamp_ns": frame * 500000000, "is_repeat": display in (2, 4),
                     "native_pixel_sha256": hashlib.sha256(("synthetic-pixels-"+str(frame)).encode()).hexdigest()})
    return {"identity": ident(), "clock_id": "synthetic-output-clock", "source_clock_id": "synthetic-source-clock",
            "window_start_ns": 0, "window_end_ns": 2000000000, "samples": rows}


def stable_record():
    rows = []
    for i in range(3):
        rows.append({"timestamp_ns": i*1000000000, "captured_frames": 10+i, "processed_frames": 10+i,
                     "display_frames": 20+2*i, "ddr_errors": 0, "frame_errors": 0, "fault_count": 0,
                     "fault_flags": 0, "temperature_valid": True, "temperature_alarm": False, "temperature_c": 40.+i})
    return {"identity": ident(), "clock_id": "synthetic-monitor", "temperature_method": "sensor_adc_approximate",
            "window_start_ns": 0, "window_end_ns": 2000000000, "samples": rows}


def latency_record():
    return {"identity": ident(), "method": "external_same_source_event", "scope": "source_event_to_output_observation",
            "external_observer": "synthetic-camera-model-not-a-real-instrument", "clock_id": "synthetic-observer",
            "samples": [{"event_id": "synthetic-A", "input_event_ns": 0, "output_event_ns": 5000000},
                        {"event_id": "synthetic-B", "input_event_ns": 1000000000, "output_event_ns": 1006000000}]}


def manifest():
    return {"schema": 1, "evidence_kind": "synthetic_tool_test", "run_id": "synthetic-unit-test-only",
            "identity": ident(), "requirements": requirements(), "throughput": frame_record(),
            "stability": stable_record(), "external_latency": latency_record()}


class AssessEvidenceTests(unittest.TestCase):
    def test_repeated_refresh_is_not_new_frame_fps(self):
        result = e.throughput(frame_record(), requirements())
        self.assertEqual(result["new_frame_fps"], 1.)
        self.assertEqual(result["display_refresh_fps"], 2.)
        self.assertEqual(result["repeated_displays"], 2)

    def test_frame_timestamp_display_rollback_or_missing_sample_rejected(self):
        mutations = (("frame_id", 0), ("display_id", 0), ("source_timestamp_ns", 0), ("timestamp_ns", 0),
                     ("frame_id", 4), ("display_id", 4))
        for key, value in mutations:
            with self.subTest(key=key, value=value):
                data = frame_record(); data["samples"][3][key] = value
                with self.assertRaises(ValueError):
                    e.throughput(data, requirements())

    def test_short_window_missing_boundaries_and_gaps_cannot_pass(self):
        for key, value in (("minimum_fps_window_seconds", 3.), ("maximum_sample_gap_seconds", .25)):
            with self.subTest(key=key):
                req = requirements(); req[key] = value
                with self.assertRaises(ValueError):
                    e.throughput(frame_record(), req)
        data = frame_record(); data["window_end_ns"] += 1
        with self.assertRaises(ValueError):
            e.throughput(data, requirements())

    def test_new_ids_with_repeated_pixels_are_unmeasured_not_proven_frozen(self):
        data = frame_record()
        data["samples"][3]["native_pixel_sha256"] = data["samples"][0]["native_pixel_sha256"]
        with self.assertRaises(e.MissingEvidence):
            e.throughput(data, requirements())

    def test_refresh_fps_cannot_satisfy_new_frame_target(self):
        req = requirements(); req["target_new_frame_fps"] = 1.5
        with self.assertRaisesRegex(ValueError, "new-frame rate"):
            e.throughput(frame_record(), req)

    def test_strong_type_nonfinite_and_official_threshold_claim_rejected(self):
        for key, value in (("target_new_frame_fps", True), ("maximum_temperature_c", float("nan")),
                           ("minimum_latency_events", 2.), ("threshold_origin", "officially_approved")):
            with self.subTest(key=key):
                data = manifest(); data["requirements"][key] = value
                with self.assertRaises(ValueError):
                    e.assess(data, base_dir=TOOLS)
        data = frame_record(); data["samples"][1]["timestamp_ns"] = True
        with self.assertRaises(ValueError):
            e.throughput(data, requirements())

    def test_stability_good_and_counter_faults_rejected(self):
        self.assertEqual(e.stability(stable_record(), requirements())["maximum_temperature_c"], 42.)
        for key, value in (("processed_frames", 9), ("ddr_errors", 1), ("frame_errors", 1), ("fault_count", 1), ("fault_flags", 1)):
            with self.subTest(key=key):
                data = stable_record(); data["samples"][1][key] = value
                with self.assertRaises(ValueError):
                    e.stability(data, requirements())

    def test_invalid_alarm_overtemperature_or_missing_samples_rejected(self):
        for key, value in (("temperature_valid", False), ("temperature_alarm", True), ("temperature_c", 61.)):
            with self.subTest(key=key):
                data = stable_record(); data["samples"][1][key] = value
                with self.assertRaises(ValueError):
                    e.stability(data, requirements())
        data = stable_record(); data["samples"].pop(1)
        with self.assertRaises(ValueError):
            e.stability(data, requirements())

    def test_external_latency_requires_real_method_not_shared_ns_or_core_cycles(self):
        self.assertEqual(e.external_latency(latency_record(), requirements())["maximum_latency_ms"], 6.)
        for method in ("pipeline_cycles", "same_clock_nanoseconds"):
            with self.subTest(method=method):
                data = latency_record(); data["method"] = method
                with self.assertRaises(ValueError):
                    e.external_latency(data, requirements())
        data = latency_record(); data["samples"][1]["event_id"] = "synthetic-A"
        with self.assertRaises(ValueError):
            e.external_latency(data, requirements())

    def test_synthetic_numeric_pass_never_promotes_real_acceptance_flags(self):
        data = manifest(); data.update({key: True for key in e.FALSE_FLAGS})
        result = e.assess(data, base_dir=TOOLS)
        self.assertEqual(result["record_checks"]["throughput"]["status"], "PASS")
        self.assertTrue(all(value["status"] == "UNMEASURED" for value in result["real_evidence_checks"].values()))
        self.assertEqual(result["real_acceptance_status"], "UNMEASURED")
        self.assertTrue(all(result[key] is False for key in e.FALSE_FLAGS))
        for key in ("HardwareReleaseAllowed", "NewLensCorrectionVerified", "CalibrationAccepted", "PreBitGateExecutionProven"):
            self.assertIs(result[key], False)
        self.assertFalse(result["hardware_plan_generated"])

    def test_optical_original_missing_or_wrong_mode_cannot_pass(self):
        data = manifest(); data["quality"] = {"identity": ident()}
        result = e.assess(data, base_dir=TOOLS)
        self.assertEqual(result["record_checks"]["quality"]["status"], "UNMEASURED")
        data["quality"]["identity"]["capture_mode_id"] = "different-synthetic-mode"
        result = e.assess(data, base_dir=TOOLS)
        self.assertEqual(result["record_checks"]["quality"]["status"], "FAIL")

    def test_hash_tampering_rejected_and_physical_inline_is_unmeasured(self):
        context = e.Context(manifest(), TOOLS)
        with self.assertRaisesRegex(ValueError, "SHA256 mismatch"):
            context.reference({"path": str(Path(__file__)), "sha256": "0"*64}, "synthetic tamper negative")
        data = manifest(); data["evidence_kind"] = "physical_observation"
        result = e.assess(data, base_dir=TOOLS)
        self.assertEqual(result["real_evidence_checks"]["throughput"]["status"], "UNMEASURED")
        self.assertNotEqual(result["evidence_record_status"], "PASS_RECORD_CHECKS")

    def test_existing_real_vga_development_profile_does_not_qualify_1080(self):
        path = TOOLS.parent/"build/offline-20261024/gp200-cam2-development-fisheye-profile-K320-20261026.json"
        if not path.is_file():
            self.skipTest("local historical calibration artifact is not present")
        data = manifest()
        ref = {"path": str(path), "sha256": e.sha(path)}
        data["calibration"] = {"profile": ref, "dataset_manifest": ref}
        result = e.assess(data, base_dir=TOOLS)
        self.assertEqual(result["record_checks"]["calibration"]["status"], "FAIL")
        self.assertFalse(result["CalibrationAccepted"])

    def test_upscaled_vga_or_missing_requirements_rejected(self):
        data = manifest(); data["identity"]["image_size"] = [640, 480]
        with self.assertRaises(ValueError):
            e.assess(data, base_dir=TOOLS)
        data = manifest(); del data["requirements"]["minimum_stability_window_seconds"]
        with self.assertRaises(ValueError):
            e.assess(data, base_dir=TOOLS)

    def test_true_profile_markers_cannot_hide_bad_parameters_rms_or_domain(self):
        # In-memory forged negative fixture, explicitly synthetic; never saved as a real profile.
        dataset = {**ident(), "views": [], "synthetic_tool_fixture": True}
        profile = {**ident(), "synthetic_tool_fixture": True, "model": "fisheye",
                   "provenance": "real_chessboard_captures", "development_only": False,
                   "passed": True, "candidate_ready_for_profile_review": True,
                   "independent_spatial_coverage_passed": True, "K": [[1000., 0., 959.5], [0., 1000., 539.5], [0., 0., 1.]],
                   "D": [0., 0., 0., 0.], "training_rms_px": .1, "held_out_mean_rms_px": .1,
                   "held_out_max_rms_px": .2, "observations_inside_declared_forward_scope": True,
                   "domain_audit": {"supported_forward_domain_passed": True}}
        for field, value, reason in (("K", None, "profile K"), ("D", [0., float("nan"), 0., 0.], "profile D"),
                                     ("training_rms_px", 2., "training_rms_px"),
                                     ("observations_inside_declared_forward_scope", False, "domain")):
            with self.subTest(field=field):
                data = manifest(); bad = copy.deepcopy(profile); bad[field] = value
                data["calibration"] = {"profile": {}, "dataset_manifest": {}}
                with patch.object(e.Context, "reference", return_value=Path(__file__)), patch.object(e, "read_json", side_effect=[bad, dataset]):
                    result = e.assess(data, base_dir=TOOLS)
                self.assertEqual(result["record_checks"]["calibration"]["status"], "FAIL")
                self.assertIn(reason, result["record_checks"]["calibration"]["reason"])
                self.assertFalse(result["PreBitGateExecutionProven"])


if __name__ == "__main__":
    unittest.main()
