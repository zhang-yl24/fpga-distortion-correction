"""Compare saved tile8 and S3 corrected UART evidence; never access hardware."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
S3_WORK = REPO / "distortion/work/hdmi-camera-fisheye-fill8r3s3-20261103-a"
TILE8_WORK = REPO / "distortion/work/hdmi-camera-fisheye-tile8-20261103-a"
VERIFIER = S3_WORK / "verify_live_fps_v2_a.py"
VERIFIER_SHA256 = "d1ddd2730dd038b6dcb4116444a0973036e2a09bfa3b8f8ed46d622fc6dbf758"
TOOL_HASHES = {
    REPO / "distortion/tools/hdmi_camera_fisheye_fps.py":
        "3c44b93436c8420f4fe8194f7d19060caaeae8b6a6ab295402c351fb760734fd",
    REPO / "distortion/tools/measure_hdmi_fisheye_fps.py":
        "deb9da1b02f55deb750baa09c4b4a01675beec5d76c325855d83cd994c389cc5",
}
COUNTER_NAMES = (
    "source_frames", "captured_frames", "processed_frames",
    "unique_presented_frames", "scan_refreshes", "scan_good_frames",
    "scan_repeat_frames", "scan_blank_frames",
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def ref(path):
    path = Path(path).resolve()
    return {"Path": str(path), "SHA256": sha(path)}


def load_verified_reparser():
    require(__debug__, "Run without -O: the preserved verifier uses assertions")
    require(sha(VERIFIER) == VERIFIER_SHA256, "S3 reparser source SHA256 changed")
    for path, expected in TOOL_HASHES.items():
        require(sha(path) == expected, "FPS library source SHA256 changed: " + str(path))
    spec = importlib.util.spec_from_file_location("saved_s3_fps_reparser_for_tile8", VERIFIER)
    require(spec is not None and spec.loader is not None, "Cannot load the saved S3 reparser")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    require(Path(module.protocol.__file__).resolve() ==
            (REPO / "distortion/tools/hdmi_camera_fisheye_fps.py").resolve(),
            "Unexpected protocol module loaded")
    require(Path(module.measurement.__file__).resolve() ==
            (REPO / "distortion/tools/measure_hdmi_fisheye_fps.py").resolve(),
            "Unexpected measurement module loaded")
    return module


def inspect_saved_candidate(reparser, work, label):
    paths = {
        "BitVerification": work / "bit-v2-a/verification.json",
        "ProgramReceipt": work / "program-v2-a/receipt.json",
        "FPSReceipt": work / "fps-corrected-v2-a/receipt.json",
        "Wire": work / "fps-corrected-v2-a/wire.bin",
    }
    missing = [str(path) for path in paths.values() if not path.is_file()]
    require(not missing, label + " saved evidence is incomplete: " + "; ".join(missing))
    before = {name: ref(path) for name, path in paths.items()}
    verified, program, receipt = (read(paths[key]) for key in
                                  ("BitVerification", "ProgramReceipt", "FPSReceipt"))
    require(verified.get("Verified") is True, label + " bit verification has not passed")
    require(verified.get("Target") == program.get("Target") == "hdmi_camera_fisheye_top",
            label + " target identity differs")
    require(verified["Bitstream"] == program["Bitstream"] == receipt["bitstream"],
            label + " bitstream identity differs across generation/program/measurement")
    require(verified["FinalADFSHA256"] == program["FinalADFSHA256"] == receipt["final_adf_sha256"],
            label + " final ADF identity differs")
    selected_bit = work / "bit-v2-a/generate_bitstream/hdmi_camera_fisheye_top.sbit"
    require(Path(program["Bitstream"]["Path"]).resolve() == selected_bit.resolve(),
            label + " receipt names another candidate's bitstream")
    require(selected_bit.is_file() and selected_bit.stat().st_size == program["Bitstream"]["Bytes"],
            label + " selected bitstream missing or size changed")
    require(Path(receipt["wire"]["path"]).resolve() == paths["Wire"].resolve(),
            label + " UART wire is outside the selected measurement")
    recorded_tools = {Path(name).resolve(): digest for name, digest in receipt["host_tools"].items()}
    require(recorded_tools == {path.resolve(): digest for path, digest in TOOL_HASHES.items()},
            label + " measurement library identity differs")
    # Calling reparse performs saved-byte decoding and counter calculations only.
    # Never call the imported main(), measure(), receive(), or hardware providers.
    reparsed = reparser.reparse(work, "program-v2-a", "fps-corrected-v2-a")
    require({name: ref(path) for name, path in paths.items()} == before,
            label + " evidence changed during read-only verification")
    nominal, host = reparsed["Summary"], reparsed["Host"]
    first, last = receipt["frames"][0], receipt["frames"][-1]
    return {
        "Candidate": label, "WorkDirectory": str(work),
        "Evidence": before, "Bitstream": program["Bitstream"],
        "FinalADFSHA256": program["FinalADFSHA256"],
        "TelemetryIdentity": {"ProfileID": first["profile_id"], "BuildID": first["build_id"]},
        "SampleCount": reparsed["Samples"],
        "FirstSequence": first["sequence"], "LastSequence": last["sequence"],
        "FirstCounters": {name: first[name] for name in COUNTER_NAMES},
        "LastCounters": {name: last[name] for name in COUNTER_NAMES},
        "FrameCounterDeltas": {name: nominal["counter_delta"][name] for name in COUNTER_NAMES},
        "NominalClockSummary": nominal, "IndependentHostSummary": host,
        "LastProcessCycles": nominal["last_process_cycles"],
        "NominalLastProcessMS": 1000 * nominal["last_process_seconds"],
        "HostClockLastProcessMS": host["last_process_ms_using_observed_clock"],
        "PerSampleCacheTotals": reparsed["PerSampleCacheTotals"],
        "PerSampleCacheMissFraction": reparsed["MissFraction"],
        "WireReparsed": reparsed["WireReparsed"],
        "CorrectedModeThroughout": True, "HardwareAccessedByVerifier": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=HERE / "live-fps-comparison-tile8-a.json")
    args = parser.parse_args()
    output = args.output.resolve()
    require(output.parent == HERE and not output.exists(),
            "Output must be a fresh filename in this verifier's isolated directory")
    reparser = load_verified_reparser()
    # Check the new candidate first; absent tile8 evidence is an error, never a zero or S3 fallback.
    candidate = inspect_saved_candidate(reparser, TILE8_WORK, "tile8")
    baseline = inspect_saved_candidate(reparser, S3_WORK, "S3")
    metric = "unique_presented_frames_per_second"
    old_host = baseline["IndependentHostSummary"]["host_timed_rates"][metric]
    new_host = candidate["IndependentHostSummary"]["host_timed_rates"][metric]
    old_nominal = baseline["NominalClockSummary"][metric]
    new_nominal = candidate["NominalClockSummary"][metric]
    require(old_host > 0 and old_nominal > 0, "S3 baseline rate must be positive for a ratio")
    value = {
        "Schema": "hdmi-camera-fisheye-tile8-vs-s3-saved-fps-comparison-v1",
        "Passed": True, "CheckedUTC": datetime.now(timezone.utc).isoformat(),
        "Verifier": ref(Path(__file__)), "PreservedReparser": ref(VERIFIER),
        "VerifiedLibraries": [ref(path) for path in TOOL_HASHES],
        "Baseline": baseline, "Candidate": candidate,
        "HostUniqueFrameRateRatio": new_host / old_host,
        "HostUniqueFrameRateImprovementPercent": (new_host / old_host - 1) * 100,
        "NominalUniqueFrameRateRatio": new_nominal / old_nominal,
        "NominalUniqueFrameRateImprovementPercent": (new_nominal / old_nominal - 1) * 100,
        "HardwareAccessedByVerifier": False, "InputFilesModified": False,
        "Limits": [
            "Saved digital UART telemetry; unique frames are complete new DDR result IDs.",
            "Input timing, processing FPS, unique-presented FPS and HDMI scan refresh remain separate metrics.",
            "Shared telemetry build/profile IDs do not uniquely identify the binary; generation, SRAM and measurement SHA links bind each candidate.",
            "Host arrival timing includes USB/UART buffering and scheduling uncertainty and is not frequency-counter calibration.",
            "No camera-to-screen optical latency, optical exposure FPS, visual quality, long-run stability, or raw/KEY1 mode-switch acceptance is inferred.",
            "Per-sample modulo-32 cache totals are reported separately; preserved nominal summaries are not rewritten.",
        ],
    }
    with output.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps({"Passed": True, "BaselineUniqueFPS": old_host,
                      "CandidateUniqueFPS": new_host,
                      "ImprovementPercent": value["HostUniqueFrameRateImprovementPercent"],
                      "Output": str(output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
