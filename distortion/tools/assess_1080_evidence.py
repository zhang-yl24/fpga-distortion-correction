"""Check hash-bound offline measurement records; never authorize hardware.

PASS means the supplied records meet explicitly declared engineering thresholds.
It is not independent optical, STA, hardware-origin or competition acceptance.
Synthetic records exercise the checker only: real evidence remains UNMEASURED.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import struct

IDENTITY = ("camera_id", "lens_id", "profile_id", "capture_mode_id")
CHECKS = ("native_input", "calibration", "quality", "throughput", "external_latency", "stability")
MAX_JSON_BYTES = 16 * 1024 * 1024
MAX_SAMPLES = 100000
FALSE_FLAGS = {"HardwareReleaseAllowed": False, "NewLensCorrectionVerified": False,
               "CalibrationAccepted": False, "PreBitGateExecutionProven": False,
               "RealHardwareAcceptancePassed": False}


class MissingEvidence(ValueError):
    pass


def obj(value, name):
    if not isinstance(value, dict):
        raise ValueError(name + " must be an object")
    return value


def text(value, name):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(name + " must be a nonempty string")
    return value


def integer(value, name, minimum=0):
    if type(value) is not int or value < minimum:
        raise ValueError(name + " must be an integer >= " + str(minimum))
    return value


def number(value, name, minimum=0, positive=False):
    if type(value) not in (int, float) or not math.isfinite(value) or value < minimum or (positive and value == 0):
        raise ValueError(name + " must be finite and " + ("> 0" if positive else ">= " + str(minimum)))
    return value


def boolean(value, name):
    if type(value) is not bool:
        raise ValueError(name + " must be a boolean")
    return value


def digest(value, name):
    if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdefABCDEF" for c in value):
        raise ValueError(name + " must be SHA256 hex")
    return value.lower()


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read_json(path):
    path = Path(path)
    if path.stat().st_size > MAX_JSON_BYTES:
        raise ValueError("JSON exceeds bounded 16MiB input size")
    return json.loads(path.read_text(encoding="utf-8-sig"),
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError("nonfinite JSON: " + value)))


def identity(value):
    value = obj(value, "identity")
    result = {key: text(value.get(key), key) for key in IDENTITY}
    size = value.get("image_size")
    if not isinstance(size, list) or len(size) != 2:
        raise ValueError("identity.image_size must be [width,height]")
    result["image_size"] = [integer(v, "image_size", 1) for v in size]
    if value.get("pixel_format") != "RGB565_LE":
        raise ValueError("this evidence schema requires RGB565_LE")
    result["pixel_format"] = value["pixel_format"]
    return result


class Context:
    def __init__(self, manifest, base_dir):
        self.manifest = obj(manifest, "manifest")
        if type(manifest.get("schema")) is not int or manifest["schema"] != 1:
            raise ValueError("schema must be integer 1")
        self.kind = manifest.get("evidence_kind")
        if self.kind not in ("synthetic_tool_test", "physical_observation"):
            raise ValueError("explicit synthetic_tool_test or physical_observation required")
        self.run_id = text(manifest.get("run_id"), "run_id")
        self.ident = identity(manifest.get("identity"))
        if self.ident["image_size"] != [1920, 1080]:
            raise ValueError("1080 evidence requires native image_size=[1920,1080]; upscaled VGA is not accepted")
        self.base = Path(base_dir).resolve()
        self.references = []
        self.req = obj(manifest.get("requirements"), "requirements")
        if self.req.get("threshold_origin") != "operator_engineering":
            raise ValueError("threshold_origin must explicitly be operator_engineering; these are not official score lines")
        for name in ("target_new_frame_fps", "minimum_fps_window_seconds", "maximum_sample_gap_seconds",
                     "minimum_stability_window_seconds", "maximum_external_latency_ms"):
            number(self.req.get(name), name, positive=True)
        number(self.req.get("maximum_temperature_c"), "maximum_temperature_c", minimum=-273.15)
        for name in ("maximum_line_deviation_px", "minimum_detail_score"):
            number(self.req.get(name), name)
        for name in ("minimum_latency_events", "minimum_temperature_samples"):
            integer(self.req.get(name), name, 2)
        text(self.req.get("detail_score_unit"), "detail_score_unit")

    def same_mode(self, value):
        if identity(value) != self.ident:
            raise ValueError("camera/lens/profile/capture mode/size/format differ")

    def reference(self, value, name, base=None):
        if value is None:
            raise MissingEvidence(name + " artifact is missing")
        value = obj(value, name)
        path = Path(text(value.get("path"), name + ".path"))
        path = (Path(base or self.base) / path).resolve() if not path.is_absolute() else path.resolve()
        expected = digest(value.get("sha256"), name + ".sha256")
        if not path.is_file():
            raise MissingEvidence(name + " file is absent: " + str(path))
        actual = sha(path)
        if actual != expected:
            raise ValueError(name + " SHA256 mismatch")
        self.references.append({"name": name, "path": str(path), "sha256": actual})
        return path

    def data(self, section, name):
        section = obj(section, name)
        if "record" in section:
            return obj(read_json(self.reference(section["record"], name + ".record")), name + " record")
        if self.kind == "synthetic_tool_test":
            return section
        raise MissingEvidence(name + " requires a hash-bound external record, not inline declarations")


def _samples(data):
    samples = data.get("samples")
    if not isinstance(samples, list) or len(samples) < 2 or len(samples) > MAX_SAMPLES:
        raise ValueError("samples must contain 2..100000 explicit observations")
    return [obj(row, "sample") for row in samples]


def _window(data, times, minimum_seconds, maximum_gap_seconds):
    start = integer(data.get("window_start_ns"), "window_start_ns")
    end = integer(data.get("window_end_ns"), "window_end_ns")
    if end <= start or times[0] != start or times[-1] != end:
        raise ValueError("observations must cover both declared window boundaries")
    gaps = [b-a for a, b in zip(times, times[1:])]
    if any(gap <= 0 for gap in gaps):
        raise ValueError("timestamps must strictly increase")
    if max(gaps) > maximum_gap_seconds * 1e9:
        raise ValueError("measurement samples are missing or maximum gap exceeded")
    seconds = (end-start)/1e9
    if seconds < minimum_seconds:
        raise ValueError("observed measurement window is too short")
    return seconds


def throughput(data, requirements):
    """Pure record arithmetic; repeated scanout is never counted as a new frame."""
    text(data.get("clock_id"), "output clock_id")
    text(data.get("source_clock_id"), "source_clock_id")
    rows = _samples(data)
    times = [integer(row.get("timestamp_ns"), "timestamp_ns") for row in rows]
    seconds = _window(data, times, requirements["minimum_fps_window_seconds"], requirements["maximum_sample_gap_seconds"])
    previous = None
    fresh_hashes = set()
    repeats = transitions = 0
    for row in rows:
        frame = integer(row.get("frame_id"), "frame_id")
        display = integer(row.get("display_id"), "display_id")
        captured = integer(row.get("source_timestamp_ns"), "source_timestamp_ns")
        repeated = boolean(row.get("is_repeat"), "is_repeat")
        pixels = digest(row.get("native_pixel_sha256"), "native_pixel_sha256")
        if previous is not None:
            pf, pd, pc, ph = previous
            if display <= pd or frame < pf or captured < pc:
                raise ValueError("frame/display IDs or source timestamps rolled back")
            if display != pd+1:
                raise ValueError("display observations are missing")
            if frame == pf:
                if not repeated or captured != pc or pixels != ph:
                    raise ValueError("repeated display must preserve source frame ID/timestamp/pixels")
                repeats += 1
            else:
                if repeated or captured <= pc:
                    raise ValueError("new source frame needs increasing ID/time and is_repeat=false")
                if frame != pf+1:
                    raise ValueError("new-frame observations are missing")
                transitions += 1
        elif repeated:
            raise ValueError("first sample is the baseline source frame, not a repeat")
        if previous is None or frame != previous[0]:
            if pixels in fresh_hashes:
                raise MissingEvidence("new IDs repeat pixel content: static scene or frozen source is unresolved; use a visible changing stimulus")
            fresh_hashes.add(pixels)
        previous = frame, display, captured, pixels
    new_fps = transitions / seconds
    if new_fps < requirements["target_new_frame_fps"]:
        raise ValueError("new-frame rate is below the declared engineering target")
    return {"window_seconds": seconds, "new_frame_transitions": transitions,
            "new_frame_fps": new_fps, "display_refresh_fps": (len(rows)-1)/seconds,
            "repeated_displays": repeats, "distinct_native_pixel_hashes": len(fresh_hashes),
            "note": "Source/output clock names do not establish external end-to-end latency."}


def stability(data, requirements):
    text(data.get("clock_id"), "clock_id")
    method = data.get("temperature_method")
    if method not in ("sensor_adc_approximate", "external_thermometer"):
        raise ValueError("temperature_method must identify approximate ADC or external thermometer")
    rows = _samples(data)
    if len(rows) < requirements["minimum_temperature_samples"]:
        raise ValueError("too few temperature/counter samples")
    times = [integer(row.get("timestamp_ns"), "timestamp_ns") for row in rows]
    seconds = _window(data, times, requirements["minimum_stability_window_seconds"], requirements["maximum_sample_gap_seconds"])
    counters = ("captured_frames", "processed_frames", "display_frames", "ddr_errors", "frame_errors", "fault_count")
    previous = None
    temperatures = []
    for row in rows:
        current = [integer(row.get(key), key) for key in counters]
        if previous is not None and any(a < b for a, b in zip(current, previous)):
            raise ValueError("a cumulative counter rolled back; reset/wrap is not silently accepted")
        if any(current[i] != 0 for i in (3, 4, 5)) or integer(row.get("fault_flags"), "fault_flags") != 0:
            raise ValueError("DDR/frame error or fault was observed")
        if not boolean(row.get("temperature_valid"), "temperature_valid") or boolean(row.get("temperature_alarm"), "temperature_alarm"):
            raise ValueError("temperature is invalid or alarmed")
        temperatures.append(number(row.get("temperature_c"), "temperature_c", minimum=-273.15))
        previous = current
    if rows[-1]["processed_frames"] <= rows[0]["processed_frames"]:
        raise ValueError("no new processing occurred during the stability window")
    if max(temperatures) > requirements["maximum_temperature_c"]:
        raise ValueError("temperature exceeds the declared engineering limit")
    return {"window_seconds": seconds, "samples": len(rows), "temperature_method": method,
            "minimum_temperature_c": min(temperatures), "maximum_temperature_c": max(temperatures),
            "note": "Counter telemetry alone does not prove distinct output images; throughput evidence is separate."}


def external_latency(data, requirements):
    if data.get("method") != "external_same_source_event" or data.get("scope") != "source_event_to_output_observation":
        raise ValueError("pipeline cycles/common clock timestamps are not an external end-to-end event measurement")
    text(data.get("external_observer"), "external_observer")
    text(data.get("clock_id"), "external observer clock_id")
    rows = _samples(data)
    if len(rows) < requirements["minimum_latency_events"]:
        raise ValueError("too few independent external events")
    names, inputs, outputs, latencies = set(), [], [], []
    for row in rows:
        name = text(row.get("event_id"), "event_id")
        if name in names:
            raise ValueError("duplicate external event_id")
        names.add(name)
        a = integer(row.get("input_event_ns"), "input_event_ns")
        b = integer(row.get("output_event_ns"), "output_event_ns")
        if b < a:
            raise ValueError("output event precedes input event")
        inputs.append(a); outputs.append(b); latencies.append((b-a)/1e6)
    if any(b <= a for a, b in zip(inputs, inputs[1:])) or any(b <= a for a, b in zip(outputs, outputs[1:])):
        raise ValueError("external event timestamps must strictly increase")
    if max(latencies) > requirements["maximum_external_latency_ms"]:
        raise ValueError("external end-to-end delay exceeds the declared limit")
    return {"events": len(rows), "minimum_latency_ms": min(latencies), "maximum_latency_ms": max(latencies)}


def native_input(section, ctx):
    ctx.same_mode(section.get("identity"))
    raw = ctx.reference(section.get("raw"), "native raw")
    image = ctx.reference(section.get("image"), "native original image")
    meta_path = ctx.reference(section.get("metadata"), "native metadata")
    meta = obj(read_json(meta_path), "native metadata")
    if meta.get("source_kind") not in ("physical_native_camera", "physical_hdmi_receiver") or meta.get("hardware_accessed") is not True:
        raise ValueError("replay/simulation or unknown source is not a physical native-input record")
    if meta.get("geometry_applied") is not False or meta.get("upstream_raw_contract_hash_bound") is not True or meta.get("upstream_payload_role") != "native_raw":
        raise ValueError("native geometry/role contract is not verified")
    binding = obj(meta.get("identity_binding"), "native metadata identity_binding")
    if any(binding.get(key) != ctx.ident[key] for key in IDENTITY):
        raise ValueError("native metadata identity differs")
    w, h = ctx.ident["image_size"]
    if [meta.get("width"), meta.get("height")] != [w, h] or meta.get("pixel_format") != "RGB565_LE" or raw.stat().st_size != w*h*2:
        raise ValueError("native mode/size/raw-byte count differ")
    contract = obj(obj(meta.get("build_binding"), "build_binding").get("raw_capture_contract"), "raw_capture_contract")
    if contract.get("payload_role") != "native_raw" or contract.get("geometry_applied") is not False or contract.get("image_size") != [w, h]:
        raise ValueError("hash-bound build raw contract differs from the declared native mode")
    if digest(meta.get("raw_sha256"), "metadata raw_sha256") != sha(raw) or digest(meta.get("image_sha256"), "metadata image_sha256") != sha(image):
        raise ValueError("native metadata pixel-file SHA differs")
    with image.open("rb") as stream:
        header = stream.read(24)
    if len(header) != 24 or header[:8] != b"\x89PNG\r\n\x1a\n" or struct.unpack(">II", header[16:24]) != (w, h):
        raise ValueError("native original PNG dimensions/signature differ")
    return {"source_kind": meta["source_kind"], "image_size": [w, h],
            "identity_basis": "Hash-bound operator declaration; not independent sensor/eye or electrical identity verification.",
            "pixel_equivalence_rechecked": False}


def calibration(section, ctx):
    profile_path = ctx.reference(section.get("profile"), "calibration profile")
    dataset_path = ctx.reference(section.get("dataset_manifest"), "calibration dataset")
    profile, dataset = read_json(profile_path), read_json(dataset_path)
    for value in (profile, dataset):
        if any(value.get(key) != ctx.ident[key] for key in IDENTITY) or value.get("image_size") != ctx.ident["image_size"]:
            raise ValueError("calibration identity/mode/size differs; old VGA calibration cannot qualify 1080")
    if profile.get("model") != "fisheye" or profile.get("provenance") != "real_chessboard_captures":
        raise ValueError("real fisheye calibration provenance is missing")
    if profile.get("development_only", False) is not False or any(profile.get(key) is not True for key in
            ("passed", "candidate_ready_for_profile_review", "independent_spatial_coverage_passed")):
        raise ValueError("development/incomplete profile is not accepted calibration evidence")
    k, d = profile.get("K"), profile.get("D")
    if not isinstance(k, list) or len(k) != 3 or any(not isinstance(row, list) or len(row) != 3 for row in k):
        raise ValueError("profile K must be a finite 3x3 matrix")
    for row in k:
        for value in row:
            number(value, "profile K", minimum=-math.inf)
    if k[0][0] <= 0 or k[1][1] <= 0 or k[2] != [0, 0, 1]:
        raise ValueError("profile K has invalid focal lengths/homogeneous row")
    if not isinstance(d, list) or len(d) != 4:
        raise ValueError("profile D must contain four finite fisheye coefficients")
    for value in d:
        number(value, "profile D", minimum=-math.inf)
    for field, maximum in (("training_rms_px", .5), ("held_out_mean_rms_px", .5), ("held_out_max_rms_px", 1.)):
        if number(profile.get(field), field) > maximum:
            raise ValueError(field + " exceeds the existing calibrator gate")
    if profile.get("observations_inside_declared_forward_scope") is not True or obj(profile.get("domain_audit"), "domain_audit").get("supported_forward_domain_passed") is not True:
        raise ValueError("profile domain/observed-scope evidence is incomplete")
    canonical = hashlib.sha256(json.dumps(dataset, sort_keys=True, allow_nan=False).encode()).hexdigest()
    if profile.get("source_dataset_manifest_sha256") != canonical:
        raise ValueError("profile is not bound to this dataset")
    capture_audit = obj(profile.get("capture_audit"), "capture_audit")
    if capture_audit.get("all_physical_capture_records") is not True or capture_audit.get("manifest_sha256") != canonical:
        raise ValueError("calibration lacks the existing hash-bound physical capture audit")
    views = dataset.get("views")
    if not isinstance(views, list):
        raise ValueError("explicit calibration views required")
    hashes, poses = set(), {}
    split_hashes = {"train": set(), "held_out": set()}
    counts = {"train": 0, "held_out": 0}
    training_poses = set()
    for view in views:
        view = obj(view, "view")
        split = view.get("split")
        if split not in ("train", "held_out", "model_selection"):
            raise ValueError("explicit calibration split required")
        value = digest(view.get("sha256"), "view sha256")
        pose = text(view.get("pose_id"), "pose_id")
        if value in hashes or pose in poses and poses[pose] != split:
            raise ValueError("duplicate image or train/held-out pose leakage")
        hashes.add(value); poses[pose] = split
        if split in counts:
            counts[split] += 1
            split_hashes[split].add(value)
        if split == "train":
            training_poses.add(pose)
        ctx.reference({"path": view.get("path"), "sha256": value}, "calibration original image", dataset_path.parent)
        ctx.reference({"path": view.get("metadata_path"), "sha256": view.get("metadata_sha256")}, "calibration original metadata", dataset_path.parent)
    if counts["train"] < 12 or counts["held_out"] < 3 or len(training_poses) < 12:
        raise ValueError("existing minimum 12 distinct train poses + 3 held-out views is unmet")
    for split, field in (("train", "training_image_sha256"), ("held_out", "held_out_image_sha256")):
        declared = profile.get(field)
        if not isinstance(declared, list) or len(declared) != len(split_hashes[split]) or {digest(value, field) for value in declared} != split_hashes[split]:
            raise ValueError("profile " + field + " differs from the original dataset split")
    coverage = obj(profile.get("source_image_3x3_corner_counts"), "coverage")
    for split, minimum in (("train", 15), ("held_out", 3)):
        rows = coverage.get(split)
        if not isinstance(rows, list) or len(rows) != 3 or any(not isinstance(row, list) or len(row) != 3 for row in rows):
            raise ValueError("full source-image 3x3 coverage evidence required")
        if any(integer(value, "corner count") < minimum for row in rows for value in row):
            raise ValueError("source-image edge/3x3 coverage is incomplete")
    return {**counts, "distinct_training_poses": len(training_poses),
            "note": "Reuses existing calibrator evidence; does not refit, weaken gates, accept optics or grant hardware release."}


def quality(section, ctx):
    ctx.same_mode(section.get("identity"))
    original = ctx.reference(section.get("original"), "optical original")
    corrected = ctx.reference(section.get("corrected"), "same-source corrected image")
    metadata = read_json(ctx.reference(section.get("capture_metadata"), "optical capture metadata"))
    if metadata.get("hardware_accessed") is not True or metadata.get("geometry_applied") is not False or metadata.get("source_kind") not in ("physical_native_camera", "physical_hdmi_receiver"):
        raise ValueError("optical original has no untouched physical capture record")
    if metadata.get("image_sha256") != sha(original) or [metadata.get("width"), metadata.get("height")] != ctx.ident["image_size"]:
        raise ValueError("optical original is not bound to native same-mode metadata")
    binding = obj(metadata.get("identity_binding"), "optical metadata identity")
    if any(binding.get(key) != ctx.ident[key] for key in IDENTITY):
        raise ValueError("optical capture identity/mode differs")
    report = read_json(ctx.reference(section.get("measurement_record"), "line/detail measurement record"))
    ctx.same_mode(report.get("identity"))
    for key in ("chart_id", "lighting_id", "exposure_id"):
        if text(section.get(key), key) != text(report.get(key), "measurement " + key):
            raise ValueError("optical chart/illumination/exposure differ")
    if report.get("source_image_sha256") != sha(original) or report.get("corrected_image_sha256") != sha(corrected):
        raise ValueError("optical measurement is not bound to both same-source images")
    for key in ("line_protocol", "detail_protocol", "reviewer"):
        text(report.get(key), key)
    if report.get("detail_score_unit") != ctx.req["detail_score_unit"]:
        raise ValueError("detail score unit differs from the declared threshold")
    line = number(report.get("line_max_deviation_px"), "line_max_deviation_px")
    detail = number(report.get("detail_score"), "detail_score")
    if line > ctx.req["maximum_line_deviation_px"] or detail < ctx.req["minimum_detail_score"]:
        raise ValueError("line/detail record is below the declared engineering thresholds")
    return {"line_max_deviation_px": line, "detail_score": detail,
            "note": "Record checks only; no image analysis/SFR/MTF recomputation or professional optical acceptance is performed."}


def assess(manifest, *, base_dir):
    ctx = Context(manifest, base_dir)
    numeric = {}
    for name in CHECKS:
        section = manifest.get(name)
        if section is None:
            numeric[name] = {"status": "UNMEASURED", "reason": "required evidence section is missing"}
            continue
        try:
            section = obj(section, name)
            if name in ("throughput", "external_latency", "stability"):
                data = ctx.data(section, name)
                ctx.same_mode(data.get("identity"))
                values = globals()[name](data, ctx.req)
            else:
                values = globals()[name](section, ctx)
            numeric[name] = {"status": "PASS", "details": values}
        except MissingEvidence as error:
            numeric[name] = {"status": "UNMEASURED", "reason": str(error)}
        except (ValueError, TypeError, KeyError, OSError) as error:
            numeric[name] = {"status": "FAIL", "reason": str(error)}
    synthetic = ctx.kind == "synthetic_tool_test"
    real = {name: ({"status": "UNMEASURED", "reason": "synthetic_tool_test is not physical evidence"}
                   if synthetic else dict(result)) for name, result in numeric.items()}
    statuses = [value["status"] for value in real.values()]
    status = "FAIL" if "FAIL" in statuses else "UNMEASURED" if "UNMEASURED" in statuses else "PASS_RECORD_CHECKS"
    return {"schema": 1, "created_utc": datetime.now(timezone.utc).isoformat(), "run_id": ctx.run_id,
            "evidence_kind": ctx.kind, "identity": ctx.ident, "requirements": ctx.req,
            "threshold_basis": "Explicit operator engineering targets; no official judging approval is inferred.",
            "record_checks": numeric, "real_evidence_checks": real, "evidence_record_status": status,
            "real_acceptance_status": "UNMEASURED", **FALSE_FLAGS,
            "artifacts_verified": ctx.references, "hardware_accessed": False, "hardware_plan_generated": False,
            "limits": "File/hash, identity and record arithmetic only. Does not authenticate human assertions, verify STA/bitstreams, run optical analysis, calibrate lenses, prove physical fps, authorize power/programming or replace independent review. Simulation CRC/processor clocks never substitute for physical evidence."}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output", type=Path, required=True, help="new file in an existing parent directory")
    args = parser.parse_args(argv)
    if not args.output.parent.is_dir() or args.output.exists():
        parser.error("output must be a new file with an existing parent; no directories are created")
    try:
        result = assess(read_json(args.manifest), base_dir=args.manifest.resolve().parent)
        result["manifest"] = {"path": str(args.manifest.resolve()), "sha256": sha(args.manifest)}
        result["tool_sha256"] = sha(Path(__file__))
        with args.output.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(result, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write("\n")
    except (ValueError, OSError) as error:
        parser.error(str(error))
    print(json.dumps({"evidence_record_status": result["evidence_record_status"], "real_acceptance_status": "UNMEASURED", **FALSE_FLAGS}))
    return 0 if result["evidence_record_status"] == "PASS_RECORD_CHECKS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
