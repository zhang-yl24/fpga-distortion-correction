"""Archive completed tile8 stage B without EDA, providers, or hardware access.

Run only after the original physical/release workers and saved-wire verifier
have succeeded. Every new package file is exclusive; stage A is immutable.
This tool checks saved receipts and hashes, not physical acceptance anew.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
WORK = REPO / "distortion/work/hdmi-camera-fisheye-tile8-20261103-a"
S3 = REPO / "distortion/work/hdmi-camera-fisheye-fill8r3s3-20261103-a"
PACKAGE = REPO / "distortion/results/hdmi-camera-fisheye-tile8-20261103-a"
TARGET = "hdmi_camera_fisheye_top"
REVISION = "tile8v2-bounded-b"
MAXIMUM_COPY = 4 * 1024 * 1024
BIT_BYTES = 3791112
METRIC = "unique_presented_frames_per_second"
COMPARISON = HERE / "live-fps-comparison-tile8-a.json"
DESTINATION = "evidence/release-b"
OUTPUT_NAMES = (
    "approved-evidence-sources-b.json", "status-snapshot-b.json",
    "selected-bit-board-fps-index-b.json", "README-stage-b.md",
    "copy-receipt-b.json", "portable-evidence-manifest-b.json",
    "package-scaffold-manifest-b.json",
)
EXPECTED_SOURCES = {
    WORK / "physical-release-provider-source-manifest-a.json":
        "a198f18308b81a11a5b95796b8882330dd2a44469d4acbb815329bbe24301d8c",
    WORK / "release-prewarm-wrapper-source-manifest-a.json":
        "6b31463fd5300d97bc3ee923bb0d058a5e20b37caffef1652ece56134c4067de",
    WORK / "prewarm_release_v2_a.py":
        "5c0e5d84dc3ad53e480def5d950012682b2f71223a198e52c4e283306fa7c84c",
    WORK / "run_release_v2_a.py":
        "98755d2073e9dfad3a1bc6400ab40688ed1729ac2e3554b526d5e2f4a7cb2152",
    WORK / "release-input-manifest-v2-a.json":
        "2d9c3f5815edf53e9703e782f7a09b328565cef7da9568a31c3f80959469ca5e",
    HERE / "verify_tile8_vs_s3_fps.py":
        "08f1246eb524259a2fed065e12ddc264dc37834fac4bd88547c3fa629c7c9626",
    S3 / "verify_live_fps_v2_a.py":
        "d1ddd2730dd038b6dcb4116444a0973036e2a09bfa3b8f8ed46d622fc6dbf758",
    REPO / "distortion/tools/hdmi_camera_fisheye_fps.py":
        "3c44b93436c8420f4fe8194f7d19060caaeae8b6a6ab295402c351fb760734fd",
    REPO / "distortion/tools/measure_hdmi_fisheye_fps.py":
        "deb9da1b02f55deb750baa09c4b4a01675beec5d76c325855d83cd994c389cc5",
    PACKAGE / "copy_evidence.py":
        "343a97d16a574c00a61752ab2dd2fbe6a0fc48bf3576cce376b06aaaa71995de",
    PACKAGE / "verify_archive_portable.py":
        "fbc88e25ede5a9af7e710708d8e2e03e685b9bf9a1f426b6cc657fbda9301d7c",
}
PHYSICAL_FLAGS = (
    "Passed", "STAAllTenPassed", "NativeWarningsReviewed",
    "SourceDiagnosticReviewPassed", "NetlistEquivalent",
    "AllFFPlacementsEquivalent", "RoutesUnchanged", "ResetAccepted",
    "SourceSamplingIsolatedVerified", "VendorDDRClockResetAccepted",
    "FrameBoundaryViewSelectionAccepted", "FisheyeProfileAccepted", "UserCDCAccepted",
)
ROLES = ("MapperSimulation", "SystemSimulation", "IOSimulation", "Profile")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def utc():
    return datetime.now(timezone.utc).isoformat()


def canonical(path):
    path = Path(path).absolute()
    require(path == path.resolve() and path.is_relative_to(REPO),
            "Source must be canonical and inside this repository: " + str(path))
    return path


def local_io(path):
    """Support long Windows evidence paths without importing an EDA module."""
    text = str(Path(path).absolute())
    if os.name == "nt" and not text.startswith("\\\\?\\"):
        text = "\\\\?\\UNC\\" + text[2:] if text.startswith("\\\\") else "\\\\?\\" + text
    return Path(text)


def sha(path):
    digest = hashlib.sha256()
    with local_io(path).open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def ref(path):
    path = canonical(path)
    require(local_io(path).is_file(), "Missing completed evidence: " + str(path))
    return {"Path": str(path), "SHA256": sha(path)}


def sized_ref(path):
    return {**ref(path), "Bytes": local_io(path).stat().st_size}


def read(path):
    return json.loads(local_io(path).read_text(encoding="utf-8-sig"))


def verify_ref(record):
    path = canonical(record["Path"])
    require(record["SHA256"] == sha(path), "Saved reference SHA changed: " + str(path))
    if "Bytes" in record:
        require(record["Bytes"] == local_io(path).stat().st_size, "Saved reference size changed: " + str(path))
    return path


def require_flags(value, names, description):
    for name in names:
        require(value.get(name) is True, description + ": " + name + " must be true")


def require_schema(value, expected, description):
    require(value.get("Schema") == expected, description + " schema differs")


def check(keys, value=True):
    return {"Keys": list(keys), "Equals": value}


def write_json(path, value):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def package_snapshot():
    return {path.relative_to(PACKAGE).as_posix(): sized_ref(path)
            for path in sorted(PACKAGE.rglob("*")) if path.is_file()}


def assert_old_package_unchanged(before):
    for relative, expected in before.items():
        require(sized_ref(PACKAGE / relative) == expected,
                "Historical package file changed: " + relative)


def verify_candidate(comparison, work, label):
    block = comparison["Candidate" if label == "tile8" else "Baseline"]
    require(block.get("Candidate") == label and Path(block["WorkDirectory"]) == work,
            "Comparison candidate/work identity differs: " + label)
    paths = {
        "BitVerification": work / "bit-v2-a/verification.json",
        "ProgramReceipt": work / "program-v2-a/receipt.json",
        "FPSReceipt": work / "fps-corrected-v2-a/receipt.json",
        "Wire": work / "fps-corrected-v2-a/wire.bin",
    }
    for key, path in paths.items():
        require(block["Evidence"][key] == ref(path), "Compared evidence changed: " + label + "/" + key)
    bit, program, fps = (read(paths[key]) for key in ("BitVerification", "ProgramReceipt", "FPSReceipt"))
    require(bit.get("Verified") is True and bit.get("Target") == program.get("Target") == TARGET,
            "Bit verification or target differs: " + label)
    require_flags(program, ("Passed", "DoneConfirmed", "ExpectedDeviceAndIDConfirmed"), label + " SRAM")
    require(program.get("FlashWritten") is False and program.get("CleanupErrors") == [],
            "SRAM Flash/cleanup evidence differs: " + label)
    require(fps.get("passed") is True and fps.get("uart_transmit_bytes") == 0
            and fps.get("port") == "COM7" and fps.get("crc_rejected_packets") == 0
            and fps.get("discarded_bytes") == 0, "Saved FPS receipt failed: " + label)
    require(fps["program_receipt"] == {"path": str(paths["ProgramReceipt"]), "sha256": sha(paths["ProgramReceipt"])},
            "FPS/program receipt link differs: " + label)
    require(fps["wire"] == {"path": str(paths["Wire"]), "sha256": sha(paths["Wire"])},
            "FPS/wire link differs: " + label)
    selected_bit = work / "bit-v2-a/generate_bitstream/hdmi_camera_fisheye_top.sbit"
    require(bit["Bitstream"] == program["Bitstream"] == fps["bitstream"] == block["Bitstream"],
            "Bit identity chain differs: " + label)
    require(verify_ref(bit["Bitstream"]) == selected_bit and bit["Bitstream"]["Bytes"] == BIT_BYTES,
            "Selected bit differs: " + label)
    require(bit["FinalADFSHA256"] == program["FinalADFSHA256"] == fps["final_adf_sha256"] == block["FinalADFSHA256"],
            "ADF identity chain differs: " + label)
    require_flags(block, ("WireReparsed", "CorrectedModeThroughout"), label + " saved reparse")
    require(block.get("HardwareAccessedByVerifier") is False, "Reparser accessed hardware")
    require(block["NominalClockSummary"] == fps["nominal_clock_summary"]
            and block["IndependentHostSummary"] == fps["independent_host_summary"],
            "Compared FPS summaries differ: " + label)
    nominal, host = block["NominalClockSummary"], block["IndependentHostSummary"]
    require(nominal["counter_delta"]["scan_blank_frames"] == 0
            and host["clock_cross_check_within_3percent"] is True,
            "Blank frames or host clock acceptance differs: " + label)
    frames = fps["frames"]
    require(len(frames) >= 10 and len(frames) == block["SampleCount"] == nominal["sample_count"],
            "Saved sample count differs: " + label)
    require(all(frame["corrected_requested"] and frame["status_valid"]
                and not frame["failed"] and not frame["fault"] for frame in frames),
            "Saved corrected mode/status failed: " + label)
    require(all(((b["sequence"] - a["sequence"]) & 0xffffffff) == 1 for a, b in zip(frames, frames[1:])),
            "Saved sequence is discontinuous: " + label)
    require(block["FirstSequence"] == frames[0]["sequence"] and block["LastSequence"] == frames[-1]["sequence"],
            "Comparison sequence endpoints differ: " + label)
    require(nominal[METRIC] > 0 and host["host_timed_rates"][METRIC] > 0,
            "Unique frame rate must be positive: " + label)
    return block, bit, program, fps, paths


def validate_completed():
    for path, digest in EXPECTED_SOURCES.items():
        require(sha(path) == digest, "Reviewed source SHA changed: " + str(path))
    comparison = read(COMPARISON)
    require_schema(comparison, "hdmi-camera-fisheye-tile8-vs-s3-saved-fps-comparison-v1", "Comparison")
    require(comparison.get("Passed") is True and comparison.get("HardwareAccessedByVerifier") is False
            and comparison.get("InputFilesModified") is False, "Saved independent comparison has not passed")
    require(comparison["Verifier"] == ref(HERE / "verify_tile8_vs_s3_fps.py")
            and comparison["PreservedReparser"] == ref(S3 / "verify_live_fps_v2_a.py"),
            "Compared verifier identity differs")
    expected_libraries = [ref(REPO / "distortion/tools/hdmi_camera_fisheye_fps.py"),
                          ref(REPO / "distortion/tools/measure_hdmi_fisheye_fps.py")]
    require(comparison["VerifiedLibraries"] == expected_libraries, "Compared FPS library identities differ")
    candidate = verify_candidate(comparison, WORK, "tile8")
    baseline = verify_candidate(comparison, S3, "S3")
    for prefix, key in (("Host", "IndependentHostSummary"), ("Nominal", "NominalClockSummary")):
        old = baseline[0][key]
        new = candidate[0][key]
        if prefix == "Host":
            old, new = old["host_timed_rates"], new["host_timed_rates"]
        ratio = new[METRIC] / old[METRIC]
        require(math.isclose(comparison[prefix + "UniqueFrameRateRatio"], ratio, rel_tol=1e-12)
                and math.isclose(comparison[prefix + "UniqueFrameRateImprovementPercent"], (ratio - 1) * 100, rel_tol=1e-12, abs_tol=1e-12),
                "Compared improvement calculation differs: " + prefix)
    proof_path = WORK / "final-proof-v2-a.json"
    proof = read(proof_path)
    require_schema(proof, "hdmi-camera-fisheye-tile8v2-final-physical-proof-v1", "Final physical proof")
    require(proof.get("Target") == TARGET, "Physical proof target differs")
    require_flags(proof, PHYSICAL_FLAGS, "Final physical proof")
    pins, cdc = proof["Pins"], proof["DataCDC"]
    require(all(pins.get(key) == 144 for key in ("DeclaredTopPorts", "NativeRoutedPorts", "NativeActivePorts"))
            and pins.get("UnusedPads") == [] and pins.get("NativeElectricalParametersVerified") is True,
            "Final native pin acceptance is incomplete")
    require(cdc.get("InterstageTimingAccepted") is True and cdc.get("Missing") == [] and cdc.get("Violations") == [],
            "Final user CDC acceptance is incomplete")
    require(proof.get("NativeAcceptance") and proof.get("SourcePartitions"), "Final acceptance partitions missing")
    require(proof["FinalADF"]["SHA256"] == candidate[1]["FinalADFSHA256"], "Physical/bit ADF differs")
    verify_ref(proof["FinalADF"])
    ready = read(WORK / "physical-to-release-v2-go-a.json")
    require_flags(ready, ("PriorWorkerEnded", "PDriveReleased", "UserAuthorizedVolatileSRAM", "UserNotifiedBeforeExecution"), "Release handoff")
    require(ready.get("ProviderRevision") == REVISION and ready["PhysicalProof"] == ref(proof_path)
            and ready["ProviderSourceManifest"] == ref(WORK / "physical-release-provider-source-manifest-a.json"),
            "Release handoff proof/revision differs")
    require(ready.get("NotificationUTC"), "Actual hardware notification time missing")
    datetime.fromisoformat(ready["NotificationUTC"].replace("Z", "+00:00"))
    roles = read(WORK / "release-input-manifest-v2-a.json")
    require(roles.get("Passed") is True and roles.get("InputDrift") == [], "Selected role manifest failed")
    request = read(WORK / "bit-request-v2-a.json")
    require_schema(request, "hdmi-camera-fisheye-tile8v2-bitstream-request-v1", "Actual bit request")
    require(request["Target"] == TARGET and request["PhysicalProof"] == ref(proof_path), "Actual bit request target/proof differs")
    for name in ROLES:
        require(ready[name] == roles[name] == request[name], "Released role identity differs: " + name)
        verify_ref(ready[name])
    require((WORK / "release-prewarm-bit-request-v2-a.snapshot.json").read_bytes()
            == (WORK / "bit-request-v2-a.json").read_bytes()
            == (WORK / "release-prewarm-recreated-request-check-a.json").read_bytes(),
            "Actual/prewarmed bit request bytes differ")
    prewarm = read(WORK / "release-prewarm-authority-a.json")
    transition = read(WORK / "release-prewarm-authorized-transition-a.json")
    require(prewarm.get("Passed") is True and prewarm.get("InputDrift") == []
            and prewarm.get("HardwareAccessed") is False and prewarm.get("EDAExecuted") is False,
            "Public CPU prewarm has not passed")
    require(prewarm["ExactRequest"] == request and prewarm["RequestSHA256"] == sha(WORK / "bit-request-v2-a.json"),
            "Prewarm request identity differs")
    require(transition.get("Passed") is True and transition.get("FreshRuntimeGateStillRequired") is True
            and transition["RootReleaseGo"] == ref(WORK / "physical-to-release-v2-go-a.json")
            and transition["PrewarmReceipt"] == ref(WORK / "release-prewarm-authority-a.json"),
            "Actual authorized prewarm transition differs")
    execution = read(WORK / "bit-v2-a/execution-result.json")
    require(execution.get("ExitCode") == 0 and execution.get("TimedOut") is False
            and execution.get("InputDrift") == [] and execution.get("Diagnostics") == []
            and execution.get("EDAExecuted") is True and execution.get("HardwareAccessed") is False
            and execution.get("Cleanup", {}).get("Complete") is True and not execution.get("Error"),
            "Actual bit execution is incomplete or failed")
    gate = read(WORK / "bit-v2-a/pre-bit-audit.json")
    require(gate.get("GatePassed") is True and gate["FinalADFSHA256"] == candidate[1]["FinalADFSHA256"],
            "Actual fresh runtime gate failed")
    require_flags(candidate[1]["FreshSTA"], ("STAAllTenPassed", "ClockAndSummaryIdentityPreserved", "AllExceptionPathsPreserved"), "Bit fresh STA")
    plan = read(WORK / "program-v2-a/plan.json")
    require(plan.get("Operation") == "volatile_sram_only" and plan.get("FlashWritten") is False
            and plan["Bitstream"] == candidate[1]["Bitstream"]
            and candidate[2]["PlanSHA256"] == sha(WORK / "program-v2-a/plan.json"), "Selected volatile SRAM plan differs")
    require_flags(candidate[2], ("UserNotifiedBeforeExecution", "HardwareAccessed", "ProgrammingAttempted"), "Actual SRAM execution")
    duration = (datetime.fromisoformat(candidate[3]["ended_utc"]) - datetime.fromisoformat(candidate[3]["started_utc"])).total_seconds()
    require(duration >= 30, "Actual corrected UART measurement lasted less than 30 seconds")
    return {"Comparison": comparison, "Candidate": candidate, "Baseline": baseline,
            "Proof": proof, "Ready": ready, "Roles": roles, "MeasurementDurationSeconds": duration}


def make_inventory(facts):
    entries = []
    sources = set()
    destinations = set()

    def add(path, relative, checks=(), reference=False):
        path = canonical(path)
        if str(path) in sources:
            return
        record = sized_ref(path)
        sources.add(str(path))
        mode = "reference" if reference or record["Bytes"] > MAXIMUM_COPY else "copy"
        row = {"ID": "stage-b-" + str(len(entries) + 1).zfill(3), "Mode": mode, "Source": record,
               "Reason": "Completed immutable tile8 stage B evidence; archive performs no EDA or hardware access"}
        if mode == "copy":
            target = DESTINATION + "/" + relative
            require(target not in destinations and not (PACKAGE / target).exists(), "Archive target already exists: " + target)
            destinations.add(target)
            row["Destination"] = target
        if checks:
            value = read(path)
            for condition in checks:
                observed = value
                for key in condition["Keys"]:
                    observed = observed[key]
                require(observed == condition["Equals"], "Completed JSON check failed: " + str(path))
            row["JSONChecks"] = list(checks)
        entries.append(row)

    proof = facts["Proof"]
    add(WORK / "final-proof-v2-a.json", "physical/final-proof.json", [check([name]) for name in PHYSICAL_FLAGS])
    for key in ("Application", "FinalExport", "FinalRoute"):
        add(verify_ref(proof[key]), "physical/" + key.lower() + "-receipt.json", [check(["ExecutionPassed"])])
    for number, record in enumerate(proof["FinalQueries"]):
        add(verify_ref(record), f"physical/final-query-{number:02}.json", [check(["ExecutionPassed"])])
    for key in ("FinalADF", "FreshSTAReport", "FreshSTAExceptions"):
        add(verify_ref(proof[key]), "physical/" + key, reference=True)
    for name in (
        "physical-to-release-v2-go-a.json", "release-input-manifest-v2-a.json",
        "release-prewarm-authority-a.json", "release-prewarm-authorized-transition-a.json",
        "release-prewarm-bit-request-v2-a.snapshot.json", "release-prewarm-recreated-request-check-a.json",
        "bit-request-v2-a.json",
    ):
        add(WORK / name, "handoff/" + name)
    add(COMPARISON, "independent-tile8-vs-S3-comparison.json", [check(["Passed"])])
    for label, block in (("tile8", facts["Candidate"]), ("S3", facts["Baseline"])):
        _, verified, program, _, paths = block
        prefix = "" if label == "tile8" else "baseline-S3/"
        for key, path in paths.items():
            name = {"BitVerification": "bit-verification.json", "ProgramReceipt": "program-receipt.json",
                    "FPSReceipt": "corrected-fps-receipt.json", "Wire": "corrected-wire.bin"}[key]
            add(path, prefix + name)
        add(verify_ref(verified["Bitstream"]), prefix + TARGET + ".sbit", reference=(label == "S3"))
        if label == "tile8":
            for relative, digest in verified["EvidenceSHA256"].items():
                require(not Path(relative).is_absolute() and ".." not in Path(relative).parts, "Bit evidence path escaped")
                path = WORK / "bit-v2-a" / relative
                require(sha(path) == digest, "Verified bit artifact SHA changed: " + relative)
                add(path, "bit/" + relative, reference=Path(relative).suffix.lower() in (".adf", ".rtr"))
            add(WORK / "program-v2-a/plan.json", "program/plan.json")
            for name, digest in program.get("Logs", {}).items():
                require(Path(name).name == name, "Program log path escaped")
                path = WORK / "program-v2-a" / name
                require(sha(path) == digest, "Program log SHA changed: " + name)
                add(path, "program/" + name)
            for name in ("scan.tcl", "program.tcl"):
                add(WORK / "program-v2-a" / name, "program/" + name)
    for path in EXPECTED_SOURCES:
        prefix = "source/"
        if path.parent == PACKAGE:
            continue
        name = path.name
        if path.parent == S3:
            name = "S3-" + name
        add(path, prefix + name)
    add(Path(__file__).resolve(), "source/archive_tile8_stage_b.py")
    provider = read(WORK / "physical-release-provider-source-manifest-a.json")
    for path, digest in provider["InputSHA256"].items():
        source = Path(path)
        if source.suffix.lower() not in (".py", ".v", ".vh", ".sdc", ".fdc"):
            continue
        source = canonical(source)
        require(sha(source) == digest, "Frozen provider source SHA changed: " + str(source))
        # The unchanged copy tool uses ordinary paths. Keep new destinations
        # short while retaining the exact original path in the source manifest.
        archive_name = hashlib.sha256(str(source).encode("utf-8")).hexdigest()[:16] + source.suffix
        add(source, "source/frozen-provider/" + archive_name)
    for name in ("release-prewarm-wrapper-peer-review-a.json", "selected-four-role-binding-proof-a.json"):
        add(WORK / name, "source/" + name, [check(["Passed"])])
    return entries


def build_index(facts, manifest_ref, timestamp):
    block, bit, program, fps, paths = facts["Candidate"]
    summary, host = block["NominalClockSummary"], block["IndependentHostSummary"]
    comparison = facts["Comparison"]
    return {
        "Schema": "hdmi-camera-fisheye-tile8v2-selected-bit-board-fps-archive-index-v1",
        "Passed": True, "Stage": "B", "SnapshotUTC": timestamp, "ProviderRevision": REVISION,
        "SelectedBitstream": bit["Bitstream"], "FinalADFSHA256": bit["FinalADFSHA256"],
        "FinalPhysicalProof": sized_ref(WORK / "final-proof-v2-a.json"),
        "BitVerification": sized_ref(paths["BitVerification"]),
        "ProgramPlan": sized_ref(WORK / "program-v2-a/plan.json"),
        "ProgramReceipt": sized_ref(paths["ProgramReceipt"]), "FPSReceipt": sized_ref(paths["FPSReceipt"]),
        "Wire": sized_ref(paths["Wire"]), "IndependentComparison": sized_ref(COMPARISON),
        "SourcesManifest": manifest_ref,
        "ProviderSourceManifest": sized_ref(WORK / "physical-release-provider-source-manifest-a.json"),
        "WrapperSourceManifest": sized_ref(WORK / "release-prewarm-wrapper-source-manifest-a.json"),
        "ReparserSource": sized_ref(S3 / "verify_live_fps_v2_a.py"),
        "ProgramPassed": program["Passed"], "DONEConfirmed": program["DoneConfirmed"],
        "ExpectedDeviceAndIDConfirmed": program["ExpectedDeviceAndIDConfirmed"],
        "FlashWritten": program["FlashWritten"], "CleanupErrors": program["CleanupErrors"],
        "BitwiseConfigurationReadbackPerformed": program["BitwiseConfigurationReadbackPerformed"],
        "CandidateMode": "corrected", "CorrectedSampleCount": block["SampleCount"],
        "MeasurementElapsedSeconds": facts["MeasurementDurationSeconds"],
        "HardwareWindowSeconds": summary["hardware_window_seconds"], "HostWindowSeconds": host["host_window_seconds"],
        "FirstSequence": block["FirstSequence"], "LastSequence": block["LastSequence"],
        "FrameCounterDeltas": block["FrameCounterDeltas"],
        "ProcessedFPS": summary["processed_frames_per_second"], "UniqueFPS": summary[METRIC],
        "HostUniqueFPS": host["host_timed_rates"][METRIC], "RefreshHz": summary["scan_refreshes_per_second"],
        "RepeatHz": summary["scan_repeat_frames_per_second"],
        "BlankFramesAddedInWindow": summary["counter_delta"]["scan_blank_frames"],
        "FaultSamples": sum(bool(frame["fault"] or frame["failed"]) for frame in fps["frames"]),
        "CRCRejectedPackets": fps["crc_rejected_packets"], "DiscardedBytes": fps["discarded_bytes"],
        "UARTTransmitBytes": fps["uart_transmit_bytes"], "LastProcessCycles": block["LastProcessCycles"],
        "NominalLastProcessMS": block["NominalLastProcessMS"], "HostClockLastProcessMS": block["HostClockLastProcessMS"],
        "PerSampleCacheTotals": block["PerSampleCacheTotals"], "PerSampleCacheMissFraction": block["PerSampleCacheMissFraction"],
        "BaselineCandidate": "S3", "BaselineUniqueFPS": facts["Baseline"][0]["NominalClockSummary"][METRIC],
        "BaselineHostUniqueFPS": facts["Baseline"][0]["IndependentHostSummary"]["host_timed_rates"][METRIC],
        "HostUniqueFPSRatio": comparison["HostUniqueFrameRateRatio"],
        "HostUniqueFPSImprovementPercent": comparison["HostUniqueFrameRateImprovementPercent"],
        "NominalUniqueFPSRatio": comparison["NominalUniqueFrameRateRatio"],
        "NominalUniqueFPSImprovementPercent": comparison["NominalUniqueFrameRateImprovementPercent"],
        "WireReparsed": block["WireReparsed"], "VisualFeedbackReceived": False,
        "OpticalLatencyMeasured": False, "HardwareAccessedByArchiver": False,
        "Limits": comparison["Limits"],
    }


def run_checked(script, *arguments):
    """Only the two reviewed package-local, offline archive tools are callable."""
    require(script in (PACKAGE / "copy_evidence.py", PACKAGE / "verify_archive_portable.py"),
            "Unexpected subprocess tool")
    require(sha(script) == EXPECTED_SOURCES[script], "Offline archive tool SHA changed")
    result = subprocess.run([sys.executable, "-B", str(script), *arguments],
                            cwd=str(REPO), check=True, capture_output=True, text=True,
                            encoding="utf-8", creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if result.stdout.strip():
        print(result.stdout.strip(), flush=True)
    require(not result.stderr.strip(), "Offline archive tool wrote stderr: " + result.stderr)


def main():
    require(not any((PACKAGE / name).exists() for name in OUTPUT_NAMES)
            and not (PACKAGE / DESTINATION).exists(), "Stage B already started; existing files will not be overwritten")
    facts = validate_completed()
    entries = make_inventory(facts)
    timestamp = utc()
    before = package_snapshot()
    require(before, "Existing stage A package missing")
    require(not any((PACKAGE / name).exists() for name in OUTPUT_NAMES)
            and not (PACKAGE / DESTINATION).exists(), "Another stage B owner started during preflight")
    # This first exclusive output is also the persistent stage B ownership claim.
    sources_path = PACKAGE / "approved-evidence-sources-b.json"
    sources = {
        "Schema": "hdmi-camera-fisheye-tile8-approved-evidence-sources-v1",
        "ApprovedCompletedEvidenceOnly": True, "SnapshotUTC": timestamp, "Stage": "B",
        "ProviderRevision": REVISION, "MaximumSingleCopyBytes": MAXIMUM_COPY,
        "SourceFilesOrFrozen431MayBeModified": False, "ActivePhysicalFilesIncluded": False,
        "Tile8BitstreamIncluded": True, "Archiver": sized_ref(Path(__file__).resolve()),
        "Entries": entries,
    }
    write_json(sources_path, sources)
    index = build_index(facts, sized_ref(sources_path), timestamp)
    write_json(PACKAGE / "selected-bit-board-fps-index-b.json", index)
    status = {
        "Schema": "hdmi-camera-fisheye-tile8-results-status-v1", "SnapshotUTC": timestamp,
        "Stage": "B: completed final physical, bitstream, volatile SRAM, corrected UART FPS and independent saved-wire comparison",
        "ProviderRevision": REVISION, "FullFinalPhysicalProofCompleted": True,
        "Tile8BitGenerated": True, "Tile8SRAMProgrammed": True, "Tile8HardwareFPSMeasured": True,
        "IndependentSavedWireComparisonPassed": True, "Tile8VisualFeedbackReceived": False,
        "SelectedBitstream": index["SelectedBitstream"], "FinalADFSHA256": index["FinalADFSHA256"],
        "CorrectedUniqueFPS": index["UniqueFPS"], "HostCorrectedUniqueFPS": index["HostUniqueFPS"],
        "S3BaselineHostUniqueFPS": index["BaselineHostUniqueFPS"],
        "HostUniqueFPSImprovementPercent": index["HostUniqueFPSImprovementPercent"],
        "FlashWritten": False, "SourcesManifest": sized_ref(sources_path),
        "SelectedIndex": sized_ref(PACKAGE / "selected-bit-board-fps-index-b.json"),
        "HistoricalStageAFiles": list(before.values()),
        "PackagingHardwareAccessed": False, "PackagingEDAExecuted": False,
        "ExternalPublishOrCommitPerformed": False,
        "Limits": facts["Comparison"]["Limits"],
    }
    write_json(PACKAGE / "status-snapshot-b.json", status)
    reference_count = sum(row["Mode"] == "reference" for row in entries)
    readme = f"""# tile8 鱼眼矫正：阶段 B\n\n阶段 B 保存本轮真实最终物理证明、选定位流、易失 SRAM 下载、COM7 默认矫正测率和独立保存字节复解码。阶段 A 原件保留。归档时间（UTC）：{timestamp}。\n\n| 指标 | 本轮 tile8 | S3 基线 |\n| --- | ---: | ---: |\n| 矫正新画面 FPS（名义时钟） | {index['UniqueFPS']:.6f} | {index['BaselineUniqueFPS']:.6f} |\n| 矫正新画面 FPS（主机到达时间） | {index['HostUniqueFPS']:.6f} | {index['BaselineHostUniqueFPS']:.6f} |\n\n主机计时新画面 FPS 相对 S3 改变 {index['HostUniqueFPSImprovementPercent']:+.3f}%。本次测率调用持续 {index['MeasurementElapsedSeconds']:.3f} 秒，保存 {index['CorrectedSampleCount']} 个样本；计数器窗口 {index['HardwareWindowSeconds']:.6f} 秒，主机样本窗口 {index['HostWindowSeconds']:.6f} 秒。处理 FPS 为 {index['ProcessedFPS']:.6f}，扫描刷新为 {index['RefreshHz']:.6f} Hz。\n\nSRAM 下载回执通过、DONE 与器件 ID 确认；未写 Flash。原始串口字节重新解码通过，CRC 拒绝和丢弃均为 0，测量窗口新增空白帧为 0。选定位流 SHA256：`{index['SelectedBitstream']['SHA256']}`；最终 ADF SHA256：`{index['FinalADFSHA256']}`。\n\n[状态](status-snapshot-b.json)、[位流与板上测率索引](selected-bit-board-fps-index-b.json)、[明确来源清单](approved-evidence-sources-b.json)、[复制回执](copy-receipt-b.json)、[独立比较](evidence/release-b/independent-tile8-vs-S3-comparison.json)。本轮尚无用户视觉反馈、光学延迟、长期稳定性或原图／KEY1 切换验收；S3 的历史视觉反馈仅属于 S3。\n\n大型物理报告、ADF 及超过 4 MiB 的证明仅作精确引用，共 {reference_count} 项；原始来源路径和 SHA 忠实保留。随包文件可离线校验，但本包未包含完整 EDA 安装、全部报告和夹具，不可据此独立重新推导物理接受。\n\n```powershell\npython verify_archive_portable.py --manifest portable-evidence-manifest-b.json\n```\n\n具备原始 work 证据的开发机还可运行：\n\n```powershell\npython copy_evidence.py --sources approved-evidence-sources-b.json --verify-only\n```\n\n阶段 B 归档只复制和校验已完成证据，不运行 EDA、不访问硬件、不创建提交或对外发布。\n"""
    with (PACKAGE / "README-stage-b.md").open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(readme)
    run_checked(PACKAGE / "copy_evidence.py", "--sources", sources_path.name, "--receipt", "copy-receipt-b.json")
    run_checked(PACKAGE / "copy_evidence.py", "--sources", sources_path.name, "--verify-only")
    assert_old_package_unchanged(before)
    bundled_paths = [PACKAGE / name for name in OUTPUT_NAMES
                     if name not in ("portable-evidence-manifest-b.json", "package-scaffold-manifest-b.json")]
    bundled_paths.extend(PACKAGE / row["Destination"] for row in entries if row["Mode"] == "copy")
    bundled_paths.extend((PACKAGE / "copy_evidence.py", PACKAGE / "verify_archive_portable.py"))
    bundled = [{"Path": path.relative_to(PACKAGE).as_posix(), "SHA256": sha(path), "Bytes": path.stat().st_size}
               for path in sorted(set(bundled_paths))]
    portable_path = PACKAGE / "portable-evidence-manifest-b.json"
    write_json(portable_path, {
        "Schema": "hdmi-camera-fisheye-tile8-portable-archive-v1", "Passed": True,
        "CreatedUTC": utc(), "Stage": "B", "BundledFiles": bundled,
        "ReferenceOnlyFiles": [row["Source"] for row in entries if row["Mode"] == "reference"],
        "Limits": "Saved file integrity only; large physical artifacts referenced, not bundled. No EDA or hardware access.",
    })
    run_checked(PACKAGE / "verify_archive_portable.py", "--manifest", portable_path.name)
    assert_old_package_unchanged(before)
    write_json(PACKAGE / "package-scaffold-manifest-b.json", {
        "Schema": "hdmi-camera-fisheye-tile8-results-scaffold-manifest-v1", "Passed": True,
        "CreatedUTC": utc(), "Stage": "B", "Archiver": sized_ref(Path(__file__).resolve()),
        "SourcesManifest": sized_ref(sources_path), "CopyReceipt": sized_ref(PACKAGE / "copy-receipt-b.json"),
        "PortableManifest": sized_ref(portable_path), "BundledFiles": len(bundled),
        "CopiedEvidenceCount": sum(row["Mode"] == "copy" for row in entries),
        "ReferenceOnlyEvidenceCount": reference_count, "HistoricalStageAFilesUnchanged": True,
        "HistoricalStageAFiles": list(before.values()), "SourceFilesModified": False,
        "Frozen431ManifestUnchanged": True, "EDAOrGateExecuted": False, "HardwareAccessed": False,
        "GitOrExternalPublicationPerformed": False,
    })
    assert_old_package_unchanged(before)
    print(json.dumps({"Passed": True, "Stage": "B", "Package": str(PACKAGE),
                      "StageAFilesVerifiedUnchanged": len(before), "UniqueFPS": index["UniqueFPS"],
                      "HostUniqueFPS": index["HostUniqueFPS"], "HostImprovementPercent": index["HostUniqueFPSImprovementPercent"],
                      "HardwareAccessed": False, "EDAExecuted": False}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
