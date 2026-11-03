"""Offline verification of the frozen C release; no serial port or FPGA access.

Run with Python 3.10+ from any directory. Historical absolute paths are provenance
only: every input is resolved inside this checkout.
"""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath, PureWindowsPath
import subprocess
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
EVIDENCE = REPO / "distortion/results/hdmi-camera-fisheye-live-20261103-a"
BIT = HERE / "bitstreams/hdmi_camera_fisheye_top_C.sbit"
PROFILE = HERE / "evidence/profile-a/profile.json"
BIT_SHA = "8c43a77d9ddce72dc7015ef7f63aabe37ab6758dd698e2e811b669c5aa5ba047"
ADF_SHA = "7b21d06112eda0213bd60780d971e90a9da492d7a29daac09eda11d388f96310"
PROFILE_ID = "ed59f83e3cfbc77b"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bound(root, name):
    require(isinstance(name, str) and "\\" not in name,
            "manifest requires a relative POSIX path: " + str(name))
    relative = PurePosixPath(name)
    require(not relative.is_absolute() and ".." not in relative.parts,
            "path escapes release: " + name)
    path = (root / relative).resolve()
    require(path.is_relative_to(root.resolve()), "path escapes release: " + name)
    return path


def verify_files(root, files):
    require(isinstance(files, dict) and files, "empty file manifest")
    for name, entry in files.items():
        path = bound(root, name)
        require(path.is_file(), "missing file: " + name)
        require(path.stat().st_size == entry.get("Bytes", entry.get("bytes")),
                "byte count differs: " + name)
        require(sha(path) == entry.get("SHA256", entry.get("sha256")),
                "SHA256 differs: " + name)


def bit_header(path):
    data = path.read_bytes()[:512]
    start = data.find(b"\x00\x01a")
    require(start >= 0, "missing Pango bitstream header")
    position = start + 2
    result = {}
    for tag, name in zip(b"abcdef", ("Design", "Device", "Date", "Time", "Generator", "Version")):
        require(data[position] == tag, "invalid bitstream header tag")
        length = int.from_bytes(data[position + 1:position + 3], "big")
        position += 3
        require(length > 0 and position + length <= len(data), "invalid bitstream header length")
        result[name] = data[position:position + length].rstrip(b"\0").decode("ascii")
        position += length
    return result


def verify_program():
    program_path = EVIDENCE / "program-c/receipt.json"
    program = read(program_path)
    verification = read(EVIDENCE / "bit-c/verification.json")
    require(sha(BIT) == BIT_SHA and BIT.stat().st_size == 3791112,
            "released bitstream is not the board C image")
    header = bit_header(BIT)
    for evidence in (program, verification):
        require(evidence["Bitstream"]["SHA256"] == BIT_SHA
                and evidence["Bitstream"]["Bytes"] == BIT.stat().st_size
                and evidence["Bitstream"]["Header"] == header
                and evidence["FinalADFSHA256"] == ADF_SHA,
                "bitstream/ADF identity disagrees with original evidence")
    require(program["Target"] == "hdmi_camera_fisheye_top"
            and program["Passed"] is True and program["DoneConfirmed"] is True
            and program["ExpectedDeviceAndIDConfirmed"] is True
            and program["FlashWritten"] is False and program["CleanupErrors"] == [],
            "program receipt does not confirm the successful C SRAM download")
    require(verification["Verified"] is True
            and verification["FreshSTA"]["STAAllTenPassed"] is True,
            "original bitstream verification did not pass")
    return program_path, program


def verify_calibration(program_path):
    root = HERE / "calibration"
    assets = read(root / "assets-sha256.json")
    files = {entry["path"]: entry for entry in assets["files"]}
    require(len(files) == len(assets["files"]), "duplicate calibration asset")
    verify_files(root, files)
    calibration = read(root / "calibration.json")
    original = read(root / "originals/new-lens-fisheye-1080-c.json")
    for key in ("model", "native_size", "K_native", "D_normalized", "distortion_order"):
        require(calibration[key] == original[key], "portable calibration differs: " + key)
    parameters_sha = sha(root / "originals/new-lens-fisheye-1080-c.json")
    require(parameters_sha[:16] == PROFILE_ID, "calibration ProfileID differs")
    for entry in calibration["originals"].values():
        require(sha(bound(root, entry["path"])) == entry["sha256"],
                "portable calibration original identity differs")
    deployed = calibration["deployed_baseline"]
    require(deployed["bitstream_sha256"] == BIT_SHA and deployed["profile_id"] == PROFILE_ID
            and deployed["program_receipt_sha256"] == sha(program_path)
            and deployed["user_observation_sha256"] == sha(EVIDENCE / "user-observation.json"),
            "calibration deployment evidence differs")
    profile = read(PROFILE)
    require(sha(PROFILE) == calibration["deployed_projection_source"]["sha256"]
            and profile["Passed"] is True
            and profile["Calibration"]["SHA256"] == parameters_sha
            and profile["SourceKNative"] == calibration["K_native"]
            and profile["DNormalized"] == calibration["D_normalized"]
            and profile["OutputKNative"] == calibration["rectification"]["K_output_native"],
            "portable output projection is not the deployed profile")
    for name, digest in profile["GeneratedFiles"].items():
        path = REPO / "distortion/board" / PureWindowsPath(name).name
        require(sha(path) == digest, "deployed profile generated header differs: " + path.name)
    return {"assets_verified": len(files), "model": calibration["model"],
            "native_size": calibration["native_size"], "profile_id": PROFILE_ID}


def verify_telemetry(program_path, program):
    sys.path.insert(0, str(REPO / "distortion/tools"))
    import hdmi_camera_fisheye_fps as protocol
    from measure_hdmi_fisheye_fps import arrival_summary
    results = []
    for name, expected_mode, expected_samples in (
        ("fps-corrected-c", True, 30), ("fps-raw-c", False, 30),
        ("fps-corrected-return-c", True, 12),
    ):
        folder = EVIDENCE / name
        receipt = read(folder / "receipt.json")
        wire = folder / "wire.bin"
        require(receipt["passed"] is True and receipt["uart_transmit_bytes"] == 0
                and receipt["program_receipt"]["sha256"] == sha(program_path)
                and receipt["bitstream"] == program["Bitstream"]
                and receipt["final_adf_sha256"] == ADF_SHA
                and sha(wire) == receipt["wire"]["sha256"],
                "telemetry firmware/wire binding differs: " + name)
        for absolute, digest in receipt["host_tools"].items():
            local = REPO / "distortion/tools" / PureWindowsPath(absolute).name
            require(sha(local) == digest, "historical decoder bytes differ: " + local.name)
        parser = protocol.Parser()
        frames = parser.feed(wire.read_bytes())
        require(parser.rejected == receipt["crc_rejected_packets"] == 0
                and parser.discarded == receipt["discarded_bytes"] == 0
                and len(parser.buffer) == 0 and len(frames) == expected_samples
                and len(frames) == len(receipt["frames"]),
                "incomplete/invalid telemetry stream: " + name)
        for decoded, saved in zip(frames, receipt["frames"]):
            require(decoded == {key: value for key, value in saved.items()
                                if key != "host_elapsed_seconds"},
                    "saved frame differs from decoded wire: " + name)
            require(decoded["status_valid"] and not decoded["failed"]
                    and decoded["fault"] == 0 and decoded["corrected_requested"] == expected_mode,
                    "telemetry pipeline/mode fault: " + name)
        require(all((b["sequence"] - a["sequence"]) & 0xffffffff == 1
                    for a, b in zip(frames, frames[1:])), "telemetry sequence gap: " + name)
        summary = protocol.summarize(frames)
        require(summary == receipt["nominal_clock_summary"], "historical nominal summary differs: " + name)
        host = arrival_summary(receipt["frames"])
        require(host == receipt["independent_host_summary"]
                and host["clock_cross_check_within_3percent"], "host arrival summary differs: " + name)
        # At 1 Hz each increment fits uint32, even when the complete window does
        # not. Summing adjacent modulo deltas recovers the lost complete wrap.
        totals = {key: sum((b[key] - a[key]) & 0xffffffff
                          for a, b in zip(frames, frames[1:]))
                  for key in protocol.COUNTERS if key != "last_process_cycles"}
        require(totals["scan_blank_frames"] == 0, "blank frames increased: " + name)
        require(all(b["core_ticks"] - a["core_ticks"] == protocol.CORE_HZ
                    for a, b in zip(frames, frames[1:])), "sample interval differs from 1 second: " + name)
        if name == "fps-raw-c":
            require(totals["cache_hits"] == 7196827263
                    and totals["cache_misses"] == 14094025
                    and totals["scan_repeat_frames"] == 0, "raw full-window counter totals differ")
        results.append({"window": name, "samples": len(frames),
                        "seconds": summary["hardware_window_seconds"],
                        "corrected": expected_mode,
                        "processed_fps": summary["processed_frames_per_second"],
                        "unique_fps": summary["unique_presented_frames_per_second"],
                        "refresh_hz": summary["scan_refreshes_per_second"],
                        "host_observed_core_mhz": host["observed_core_mhz_from_uart_arrival"],
                        "summed_cache_hits": totals["cache_hits"],
                        "summed_cache_misses": totals["cache_misses"],
                        "summed_cache_miss_fraction": totals["cache_misses"] /
                            (totals["cache_hits"] + totals["cache_misses"]),
                        "blank_frame_increment": totals["scan_blank_frames"],
                        "historical_summary_reproduced": True})
    return results


def verify():
    manifest = read(HERE / "release-manifest.json")
    files = manifest.get("Files", manifest.get("files"))
    verify_files(REPO, files)
    required = [BIT, PROFILE, HERE / "verify_release.py", HERE / "verify_source.py",
                HERE / "source-manifest.json", HERE / "calibration/assets-sha256.json",
                EVIDENCE / "program-c/receipt.json", EVIDENCE / "bit-c/verification.json"]
    required += [EVIDENCE / name / file for name in
                 ("fps-corrected-c", "fps-raw-c", "fps-corrected-return-c")
                 for file in ("receipt.json", "wire.bin")]
    require(all(path.relative_to(REPO).as_posix() in files for path in required),
            "release manifest omits a required release input")
    process = subprocess.run([sys.executable, "-B", str(HERE / "verify_source.py")],
                             cwd=REPO, capture_output=True, text=True)
    require(process.returncode == 0, "source verification failed: " + process.stderr.strip())
    source = json.loads(process.stdout)
    require(source["verified"] is True and source["released_bitstream_sha256"] == BIT_SHA,
            "source closure does not bind the C bitstream")
    program_path, program = verify_program()
    return {"verified": True, "manifest_files": len(files), "source": source,
            "bitstream_sha256": BIT_SHA, "calibration": verify_calibration(program_path),
            "telemetry": verify_telemetry(program_path, program),
            "hardware_accessed_by_verifier": False,
            "scope": "Frozen C evidence replay; no new build, physical sign-off, optical or live-board inference."}


if __name__ == "__main__":
    argparse.ArgumentParser(description=__doc__).parse_args()
    try:
        print(json.dumps(verify(), indent=2, allow_nan=False))
    except (OSError, ValueError, KeyError, TypeError, IndexError) as error:
        print(json.dumps({"verified": False, "error": str(error)}, indent=2), file=sys.stderr)
        raise SystemExit(1)
