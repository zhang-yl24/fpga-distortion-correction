"""Source-only current720 raw derivative; never launches EDA or hardware."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import prepare_camera720_sensor as sensor

PROJECT = ROOT = Path(__file__).resolve().parents[1]
TARGET = "raw_camera_capture_cam2_current720"
TOP = "board/" + TARGET + ".v"
MANIFEST = "board/" + TARGET + "-sources.json"
PARENT_TOP = "board/raw_camera_capture_cam2_delay.v"
PARENT_MANIFEST = "board/raw_camera_capture_cam2_delay-sources.json"
PARENT_SHA = "175b3e8aab66e7f28dcfccb1dd36e239f154d933b2d8f76b4e6753c21d5fdcc4"
PREVIEW = "rtl/experimental/camera720_raw_preview.v"
RAW_CONTRACT = {"protocol": "PGFRAME1", "payload_role": "native_raw",
                "geometry_applied": False, "image_size": [1280, 720]}
REPLACEMENTS = {
    PARENT_TOP: TOP,
    "rtl/camera_preview.v": PREVIEW,
    "rtl/experimental/ov5640_cadence_upright_init.v": sensor.INIT,
    "board/ov5640_cadence_trial_commands.vh": sensor.ROM,
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def parent():
    require(sha(PROJECT / PARENT_MANIFEST) == PARENT_SHA, "accepted raw parent manifest changed")
    value = json.loads((PROJECT / PARENT_MANIFEST).read_text(encoding="utf-8"))
    for name, digest in value["SourceSHA256"].items():
        require(sha(PROJECT / name) == digest, "accepted raw parent source changed: " + name)
    sensor.verify()
    return value


def replace_once(text, old, new):
    require(text.count(old) == 1, "raw720 parent anchor differs: " + old[:80])
    return text.replace(old, new)


def expected_top():
    parent()
    text = (PROJECT / PARENT_TOP).read_text(encoding="utf-8")
    start = text.index("module raw_camera_capture_cam2_delay(")
    text = ("// Independent current720 native raw candidate; requires its own physical signoff.\n"
            "// Full1280x720 RGB565_LE PGFRAME1; preview samples160x90 and enlarges8x.\n"
            "// Camera mode/optical acceptance is not inherited from VGA. No geometry processing.\n"
            + text[start:])
    text = replace_once(text, "module raw_camera_capture_cam2_delay(", "module " + TARGET + "(")
    text = replace_once(text, "raw_camera_capture pipeline(",
                        "raw_camera_capture #(.WIDTH(1280),.HEIGHT(720)) pipeline(")
    first = text.index("    ov5640_cadence_upright_init #(")
    last = text.index("    assign cam_complete=", first)
    text = text[:first] + """    // Authorize only after configured mode and two complete fresh720 frames.
    // The synchronized authorization feeds warmup/new requests, never transaction reset.
    ov5640_current720_frontend camera(.ref_clk(clk_27m),.pclk(cam_pclk),.rst_n(rst_n),
        .vsync_active(!cam_vsync),.href_active(!cam_href),
        .cam_rst_n(cam_rst_n),.cam_scl(cam_scl),.cam_sda(cam_sda),
        .sensor_id(sensor_id),.raw_authorize(camera_ready),.failed(camera_failed),.fault(cam_errors),
        .failed_address(camera_failed_address),.observed_value(camera_observed),.expected_value(camera_expected));
""" + text[last:]
    return replace_once(text, "camera_preview picture(", "camera720_raw_preview picture(").encode("utf-8")


def expected_manifest():
    baseline = parent()
    names = [REPLACEMENTS.get(n, n) for n in baseline["source_files"]]
    idx = names.index(sensor.INIT) + 1
    names[idx:idx] = [sensor.FRONTEND, sensor.MONITOR]
    names.append(sensor.SEQUENCE)
    require(len(names) == len(set(names)), "duplicate current720 raw source")
    # The IDF recursively owns its .v/.vp files; add it once, never duplicate its children.
    explicit = [n for n in names if n.endswith((".v", ".idf"))
                and not n.startswith("platform/video_base/ipcore/ddr3_test/")]
    explicit.insert(explicit.index("board/hdmi_tx_init.v"),
                    "platform/video_base/ipcore/ddr3_test/ddr3_test.idf")
    return {
        "Schema": "camera720-current-raw-source-v1", "Target": TARGET,
        "Status": "source_prepared_not_built", "BaseTop": {"Path": PARENT_TOP, "SHA256": sha(PROJECT / PARENT_TOP)},
        "ParentManifest": {"Path": PARENT_MANIFEST, "SHA256": PARENT_SHA},
        "RawCaptureContract": RAW_CONTRACT, "source_files": names, "ExplicitDesigns": explicit,
        "SourceSHA256": {n: sha(PROJECT / n) for n in names},
        "SensorModeReference": {"Path": sensor.SEQUENCE, "SHA256": sha(PROJECT / sensor.SEQUENCE)},
        "SensorModeEquivalence": {"Resolution": [1280, 720], "InitModule": "ov5640_current720_init",
            "FrontendModule": "ov5640_current720_frontend", "RegisterActionCount": 403,
            "Register3820": "41", "Register3821": "07", "VSYNCInverted": True, "HREFInverted": True,
            "Transport": "PGFRAME1 UART 921600", "GeometryApplied": False, "CompleteGoodFramesRequired": 2},
        "Preview": {"Module": "camera720_raw_preview", "Decimation": 8, "StoredSize": [160, 90],
            "WordsPerFrame": 14400, "WordsPerBank": 16384, "Banks": 2, "HDMIScan": [1280, 720],
            "RawPixelsDownsampled": False},
        "RegisteredStartup": baseline["RegisteredStartup"], "InputDelay": baseline["InputDelay"],
        "ReferenceConstraints": baseline["ReferenceConstraints"],
        "ConstraintStatus": "Reference only; new720 monitor and preview require independent physical IO/CDC/timing review",
        "Admission": {"WarmupMS": 8000, "ContinuousReadyRequired": True,
            "LossOfAuthorizationStopsNewRequests": True, "InFlightTransactionResetByAuthorization": False,
            "AutonomousRepeatedFrames": True, "HostCommandProtocol": None},
        "Changes": ["Current720 frontend/403-command source instead of VGA initializer",
            "1280x720 full raw pipeline parameters", "Fixed8x preview with bounded160x90 bank storage",
            "Registered power startup and1500ps input delay inherited byte-for-byte"],
        "HardwareAccessed": False, "EDAExecuted": False, "BitstreamGenerated": False, "BoardProgrammed": False,
        "Limits": "Source-only derivative. Full raw and preview digital tests do not inherit physical timing or optical acceptance. "
                  "Autonomous repeated raw captures; closing UART does not disarm FPGA. UART is debug export, not video FPS.",
    }


def validate_sources():
    require((PROJECT / TOP).read_bytes() == expected_top(), "raw720 top differs from exact derivative")
    manifest = json.loads((PROJECT / MANIFEST).read_text(encoding="utf-8"))
    require(manifest == expected_manifest(), "current720 raw source manifest changed")
    return {"Manifest": manifest, "Sources": manifest["source_files"],
            "SourceSHA256": manifest["SourceSHA256"], "ExplicitDesigns": manifest["ExplicitDesigns"]}


verify = validate_sources


def prepare():
    payload = expected_top()
    path = PROJECT / TOP
    if path.exists():
        require(path.read_bytes() == payload, "refuse overwriting different raw720 top")
    else:
        path.write_bytes(payload)
    manifest = expected_manifest()
    path = PROJECT / MANIFEST
    if path.exists():
        require(json.loads(path.read_text(encoding="utf-8")) == manifest, "refuse overwriting different raw720 manifest")
    else:
        with path.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(manifest, indent=2) + "\n")
    return validate_sources()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare", action="store_true")
    args = parser.parse_args()
    result = prepare() if args.prepare else validate_sources()
    print(json.dumps({"Passed": True, "Target": TARGET, "SourceCount": len(result["Sources"]),
                      "ExplicitDesignCount": len(result["ExplicitDesigns"]), "HardwareAccessed": False}))


if __name__ == "__main__":
    main()
