"""Synthetic file contracts only: no captures, fitted parameters or optical measurements.

Physical-looking fields below are deliberately hypothetical assertions required to
exercise record checks. Every manifest and artifact is labelled synthetic.
"""
import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unittest
import zlib

from test_assess_1080_evidence import e, ident, manifest, frame_record, latency_record, stable_record


def png(size, label):
    def chunk(kind, data):
        return (struct.pack(">I", len(data)) + kind + data +
                struct.pack(">I", zlib.crc32(kind + data)))
    w, h = size
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) +
            chunk(b"tEXt", b"evidence_kind\0synthetic_tool_test:" + label.encode()) +
            chunk(b"IDAT", zlib.compress((b"\0" + b"\0" * (w * 3)) * h)) + chunk(b"IEND", b""))


class ArtifactContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="synthetic-1080-record-test-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)

    def save(self, name, data):
        path = self.base / name
        if isinstance(data, bytes):
            path.write_bytes(data)
        else:
            path.write_text(json.dumps(data, allow_nan=False), encoding="utf-8")
        return {"path": path.name, "sha256": e.sha(path)}

    def metadata(self, image):
        return {"synthetic_tool_fixture": True, "evidence_kind": "synthetic_tool_test",
                "note": "Hypothetical declarations for checker tests, no physical capture.",
                "source_kind": "physical_native_camera", "hardware_accessed": True,
                "geometry_applied": False, "identity_binding": ident(),
                "width": 1920, "height": 1080, "pixel_format": "RGB565_LE",
                "image_sha256": image["sha256"], "upstream_raw_contract_hash_bound": True,
                "upstream_payload_role": "native_raw", "build_binding": {"raw_capture_contract": {
                    "protocol": "PGFRAME1", "payload_role": "native_raw",
                    "geometry_applied": False, "image_size": [1920, 1080]}}}

    def quality_manifest(self, original=None, corrected=None):
        original = png((1920, 1080), "original") if original is None else original
        corrected = png((1920, 1080), "corrected") if corrected is None else corrected
        a = self.save("synthetic-original.png", original)
        b = self.save("synthetic-corrected.png", corrected)
        meta = self.save("synthetic-metadata.json", self.metadata(a))
        measurement = {"synthetic_tool_fixture": True, "identity": ident(), "chart_id": "synthetic-chart",
                       "lighting_id": "synthetic-light", "exposure_id": "synthetic-exposure",
                       "source_image_sha256": a["sha256"], "corrected_image_sha256": b["sha256"],
                       "line_protocol": "synthetic record only", "detail_protocol": "synthetic record only",
                       "reviewer": "unit-test", "detail_score_unit": "synthetic_score",
                       "line_max_deviation_px": .1, "detail_score": .5}
        data = manifest()
        data["quality"] = {"identity": ident(), "original": a, "corrected": b, "capture_metadata": meta,
                           "measurement_record": self.save("synthetic-measurement.json", measurement),
                           **{k: measurement[k] for k in ("chart_id", "lighting_id", "exposure_id")}}
        return data

    def calibration_manifest(self, mutate=None):
        dataset = {**ident(), "synthetic_tool_fixture": True, "views": []}
        for i in range(15):
            image = self.save(f"synthetic-view-{i}.png", png((1920, 1080), f"view-{i}"))
            metadata = self.metadata(image)
            view = {"path": image["path"], "sha256": image["sha256"], "pose_id": f"pose-{i}",
                    "split": "train" if i < 12 else "held_out"}
            if mutate:
                mutate(i, view, metadata)
            meta_ref = self.save(f"synthetic-view-{i}.json", metadata)
            view.update(metadata_path=meta_ref["path"], metadata_sha256=meta_ref["sha256"])
            dataset["views"].append(view)
        canonical = hashlib.sha256(json.dumps(dataset, sort_keys=True, allow_nan=False).encode()).hexdigest()
        profile = {**ident(), "synthetic_tool_fixture": True, "model": "fisheye",
                   "provenance": "real_chessboard_captures", "development_only": False,
                   "passed": True, "candidate_ready_for_profile_review": True,
                   "independent_spatial_coverage_passed": True,
                   "K": [[1000., 0., 959.5], [0., 1000., 539.5], [0., 0., 1.]], "D": [.01, -.001, 0., 0.],
                   "training_rms_px": .1, "held_out_mean_rms_px": .1, "held_out_max_rms_px": .2,
                   "observations_inside_declared_forward_scope": True,
                   "domain_audit": {"supported_forward_domain_passed": True},
                   "source_dataset_manifest_sha256": canonical,
                   "capture_audit": {"all_physical_capture_records": True, "manifest_sha256": canonical},
                   "training_image_sha256": [v["sha256"] for v in dataset["views"][:12]],
                   "held_out_image_sha256": [v["sha256"] for v in dataset["views"][12:]],
                   "source_image_3x3_corner_counts": {"train": [[15]*3 for _ in range(3)],
                                                       "held_out": [[3]*3 for _ in range(3)]}}
        data = manifest()
        data["calibration"] = {"profile": self.save("synthetic-profile.json", profile),
                               "dataset_manifest": self.save("synthetic-dataset.json", dataset)}
        return data

    def result(self, data, check, expected, reason=None):
        result = e.assess(data, base_dir=self.base)
        self.assertEqual(result["record_checks"][check]["status"], expected, result["record_checks"][check])
        if reason:
            self.assertIn(reason, result["record_checks"][check]["reason"])
        self.assertEqual(result["real_acceptance_status"], "UNMEASURED")
        self.assertTrue(all(v["status"] == "UNMEASURED" for v in result["real_evidence_checks"].values()))
        self.assertTrue(all(result[k] is False for k in e.FALSE_FLAGS))
        self.assertFalse(result["hardware_accessed"])
        self.assertFalse(result["hardware_plan_generated"])

    def test_complete_quality_records_remain_synthetic(self):
        self.result(self.quality_manifest(), "quality", "PASS")

    def test_either_actual_quality_image_size_cannot_be_overridden_by_metadata(self):
        for which in ("original", "corrected"):
            with self.subTest(which=which):
                self.result(self.quality_manifest(**{which: png((640, 480), which)}), "quality", "FAIL", "PNG dimensions")

    def test_corrupt_or_truncated_png_ihdr_rejected_with_consistent_hashes(self):
        valid = png((1920, 1080), "header-negative")
        bad_crc = bytearray(valid); bad_crc[29] ^= 1
        bad_chunk = bytearray(valid); bad_chunk[12] = ord("x")
        for data in (b"not a PNG", valid[:24], bytes(bad_crc), bytes(bad_chunk)):
            with self.subTest(header=data[:16]):
                self.result(self.quality_manifest(corrected=data), "quality", "FAIL", "PNG IHDR")

    def test_complete_calibration_records_remain_synthetic(self):
        self.result(self.calibration_manifest(), "calibration", "PASS")

    def test_per_view_source_and_geometry_override_aggregate_profile_true(self):
        for key, value in (("source_kind", "synthetic_tool_test"), ("hardware_accessed", False), ("geometry_applied", True)):
            with self.subTest(key=key):
                def change(i, view, meta):
                    if i == 14: meta[key] = value
                self.result(self.calibration_manifest(change), "calibration", "FAIL", "untouched physical")

    def test_last_heldout_metadata_identity_mismatch_rejected(self):
        for key in e.IDENTITY:
            with self.subTest(key=key):
                def change(i, view, meta):
                    if i == 14: meta["identity_binding"][key] = "wrong-synthetic-identity"
                self.result(self.calibration_manifest(change), "calibration", "FAIL", "identity/mode")

    def test_last_heldout_metadata_mode_size_and_pixel_hash_rejected(self):
        for key, value, reason in (("width", 640, "size/pixel format"), ("height", 480, "size/pixel format"),
                                   ("width", True, "capture width"), ("pixel_format", "RGB888", "size/pixel format"),
                                   ("image_sha256", "0"*64, "PNG hash")):
            with self.subTest(key=key):
                def change(i, view, meta):
                    if i == 14: meta[key] = value
                self.result(self.calibration_manifest(change), "calibration", "FAIL", reason)

    def test_missing_per_view_metadata_and_raw_contract_cannot_pass(self):
        for key, value in (("build_binding", {}), ("upstream_payload_role", "corrected"),
                           ("upstream_raw_contract_hash_bound", False)):
            with self.subTest(key=key):
                def change(i, view, meta):
                    if i == 14: meta[key] = value
                self.result(self.calibration_manifest(change), "calibration", "FAIL", "native raw contract")
        data = self.calibration_manifest()
        (self.base / "synthetic-view-14.json").unlink()
        self.result(data, "calibration", "UNMEASURED")

    def test_small_calibration_image_cannot_use_native_metadata(self):
        def change(i, view, meta):
            if i == 14:
                image = self.save(view["path"], png((1, 1), "small-calibration"))
                view["sha256"] = meta["image_sha256"] = image["sha256"]
        self.result(self.calibration_manifest(change), "calibration", "FAIL", "PNG dimensions")

    def test_actual_image_and_pose_leakage_still_rejected(self):
        # Same bytes at distinct names, or reused pose ID, despite valid new hashes.
        for same_pixels in (True, False):
            with self.subTest(same_pixels=same_pixels):
                def change(i, view, meta):
                    if i != 14: return
                    if same_pixels:
                        image = self.save(view["path"], (self.base / "synthetic-view-0.png").read_bytes())
                        view["sha256"] = meta["image_sha256"] = image["sha256"]
                    else:
                        view["pose_id"] = "pose-0"
                self.result(self.calibration_manifest(change), "calibration", "FAIL", "leakage")

    def test_explicit_synthetic_artifacts_cannot_be_relabelled_physical(self):
        # In-memory false physical labels are negative inputs, never saved as observations.
        for check, factory in (("quality", self.quality_manifest), ("calibration", self.calibration_manifest)):
            with self.subTest(check=check):
                data = factory(); data["evidence_kind"] = "physical_observation"
                result = e.assess(data, base_dir=self.base)
                self.assertEqual(result["record_checks"][check]["status"], "FAIL")
                self.assertIn("explicitly declares synthetic", result["record_checks"][check]["reason"])
                self.assertTrue(all(result[k] is False for k in e.FALSE_FLAGS))

    def test_synthetic_numeric_record_files_cannot_be_relabelled_physical(self):
        for check, factory in (("throughput", frame_record), ("external_latency", latency_record), ("stability", stable_record)):
            with self.subTest(check=check):
                record = factory(); record["synthetic_tool_fixture"] = True
                data = manifest(); data["evidence_kind"] = "physical_observation"
                data[check] = {"record": self.save("synthetic-" + check + ".json", record)}
                result = e.assess(data, base_dir=self.base)
                self.assertEqual(result["record_checks"][check]["status"], "FAIL")
                self.assertIn("explicitly declares synthetic", result["record_checks"][check]["reason"])
                self.assertTrue(all(result[k] is False for k in e.FALSE_FLAGS))


if __name__ == "__main__":
    unittest.main()
