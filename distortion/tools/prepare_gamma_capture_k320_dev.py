"""Prepare one isolated K320 development frozen-triplet target; never hardware.

Default is a read-only plan. --stage writes only previously absent candidate
files in existing source directories. No stable/global/main-private file edits.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
TARGET = "gamma_capture_k320_dev"
BASE = "gamma_capture_settled_d5"
FROZEN = "rtl/experimental/gamma_frozen_k320_dev.v"
CAL = f"board/{TARGET}-calibration.vh"
DOMAIN = f"board/{TARGET}-domain.vh"
BINDING = f"board/{TARGET}-profile-binding.json"
PROFILE = "build/offline-20261024/gp200-cam2-development-fisheye-profile-K320-20261026.json"
AUDIT = "build/offline-20261024/gp200-cam2-development-mapping-K320-canonical-20261026.json"
GROUP_SEED = int("70595dd", 16)  # First 28 bits of the pinned profile SHA; not authentication.
ORIGINAL_CONVERTER_SHA256 = "de9219662f4c144766adb29383c013cea7092b2a6b589aa1dd8d20913b4d2d12"
ANCHORS = {
    "board/gamma_capture_settled_d5.v": "15dc481fa42296c34026f726fedc2e69f48f10efa2baaed1534fa86188688abf",
    "board/gamma_capture_settled_d5.fdc": "e3867585adf49f717e233ba15422122be1c0cebf9c8ed03b7d03243833eb9c78",
    "board/gamma_capture_settled_d5-pins.json": "886c51cf850b42d77e8cf3eb2c1ae74829b72d8e3ed9e2ee9d78c4f950e639e2",
    "board/gamma_capture_settled_d5-sources.json": "2f032373984b3f30602418a6b44115e1d80b4504f28fc2eb86b936e44f015e23",
    "board/build-gamma_capture_settled_d5.tcl": "21354a8c82c10db82dbe544e5f89cd802c6af95a5db65f062b83f431e1340d91",
    "rtl/experimental/gamma_frozen_capture.v": "96295de6f97da894a501a997f39023e3b75aa9e82ba7a4338c770846738adb6f",
    "tests/tb_gamma_frozen_native.sv": "92611f6173a24b581ef743be995dd1cfe4cf65cb997c6ace7b49ce67611798e5",
    PROFILE: "70595ddd4eb29e7f2d7c0ddbde9c5e1e06235661abff66c146a04e92a63b3a08",
    AUDIT: "26f8c040be48100a8cdd198918c8e3de25f2119323f355fc32069311b27bbe33",
}
LIMITS = ("Actual-data development parameters only: 11 train/5 held-out, incomplete spatial coverage, "
          "constrained exploratory fisheye fit and bounded Brown approximation. Calibration is not accepted. "
          "Zero-angle, one immutable input, two bypass warmup passes, three CRC packets and one-shot hold. "
          "Independent numerical capture probe; not continuous-main validation, measured FOV, optical quality, "
          "physical fps or resource acceptance. PGFRAME1 carries no build/camera identity; a future physical "
          "run needs an independently source-bound SRAM/DONE session and fixed heartbeat recovery.")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def replace_one(text, old, new):
    if text.count(old) != 1:
        raise ValueError("Expected exactly one clone anchor: " + old)
    return text.replace(old, new)


def json_bytes(record):
    return (json.dumps(record, indent=2, allow_nan=False) + "\n").encode()


def expected():
    for name, digest in ANCHORS.items():
        if sha(ROOT / name) != digest:
            raise ValueError("Frozen clone/profile input changed: " + name)
    # R0 obtained these bytes from real_parameters(..., True), without staging
    # any main header. R1 validates the fixed canonical inputs independently;
    # a later unrelated main-cache helper edit cannot alter this candidate.
    profile = json.loads((ROOT / PROFILE).read_text(encoding="utf-8-sig"))
    audit = json.loads((ROOT / AUDIT).read_text(encoding="utf-8-sig"))
    if (profile.get("model") != "fisheye" or profile.get("development_only") is not True
            or profile.get("image_size") != [640, 480] or profile.get("passed") is not False
            or profile.get("candidate_ready_for_profile_review") is not False
            or profile.get("independent_spatial_coverage_passed") is not False
            or audit.get("passed") is not True or audit.get("candidate_ready_for_profile_review") is not False
            or audit.get("source_profile_development_only") is not True
            or audit.get("source_profile_file_sha256") != ANCHORS[PROFILE]
            or audit.get("sample_stride") != 1 or audit.get("full_requested_frames_checked") is not True
            or audit.get("output_K") != [[320, 0, 319.5], [0, 320, 239.5], [0, 0, 1]]):
        raise ValueError("Need exact numeric-passed, calibration-unaccepted K320 inputs")
    config = audit["integer_config"]
    guard = audit["required_radius_guard_q22_for_checked_rays"]
    widths = [24]*6+[32]*7
    if (len(config) != 13 or any(type(v) is not int or not -(1 << (b-1)) <= v < (1 << (b-1)) for v, b in zip(config, widths))
            or config[11:] != [0, 0] or guard != 6530716
            or guard != max(row["maximum_normalized_radius_squared_q22"] for row in audit["frames"])+2):
        raise ValueError("K320 signed register or radius contract changed")
    names = "OUT_CX OUT_CY SRC_CX SRC_CY SRC_FX SRC_FY INV_FX INV_FY K1 K2 K3 P1 P2".split()
    header = "// Actual-data DEVELOPMENT ONLY fit; calibration not accepted.\n"
    header += "".join(f"localparam signed [{b-1}:0] CAL_{n}={b}'sh{v&((1<<b)-1):0{b//4}x};\n" for n, v, b in zip(names, config, widths))
    domain = f"// Radius covers explicitly audited rays/angles only; outside is masked.\nlocalparam ROT_MAX_R2_Q22=32'd{guard};\n"
    pbytes = {CAL: header.encode(), DOMAIN: domain.encode()}
    if [hashlib.sha256(v).hexdigest() for v in pbytes.values()] != [
            "84ecd158328c1e3cf34855a4d8e5d01600402dfea48d87c9231a73549ab0d580",
            "ff6a7cd926cef2d5762f48385b509e0d0c631d58eacd85858d8ce3d556e2d0fc"]:
        raise ValueError("Private register bytes differ from original read-only conversion")
    identity = {k: profile[k] for k in ("camera_id", "lens_id", "profile_id", "capture_mode_id")}
    if any(not isinstance(v, str) or not v for v in identity.values()):
        raise ValueError("Four nonempty source identities required")
    binding = dict(schema=1, Target=TARGET, Revision="R1", ParameterOrigin="actual_data_exploratory_fisheye_brown_approximation",
                   Profile=str(ROOT / PROFILE), ProfileSHA256=ANCHORS[PROFILE], MappingAudit=str(ROOT / AUDIT),
                   MappingAuditSHA256=ANCHORS[AUDIT], Identity=identity, ImageSize=[640, 480],
                   IntegerConfig=config, RadiusGuardQ22=guard, DevelopmentOnly=True, CalibrationAccepted=False,
                   HardwareReleaseAllowed=False, Eye="CAM2", OneShot=True, AngleDegrees=0,
                   Engine="adaptive_gamma_frame_engine", EngineINDEX_BITS=4,
                   CacheSource="rtl/experimental/ddr_adaptive_cache.v",
                   Protocol="PGFRAME1", UartBaud=921600, TripletKinds=["raw", "bypass", "gamma"],
                   GroupSeed=GROUP_SEED, GroupSeedHex=f"{GROUP_SEED:07X}",
                   GroupSeedDerivation="First 28 bits of canonical profile SHA; build/transaction label only, not authentication or exposure/sensor proof",
                   PacketIDs=[GROUP_SEED << 4, (GROUP_SEED << 4) | 1, f"{(GROUP_SEED << 4) | 2} | (gamma_mode << 2)"],
                   DisplayRotationClockwiseDegrees=180, NativePixelsTransformed=False,
                   ContinuousMainValidated=False, OpticalAcceptanceComplete=False, Limits=LIMITS)
    binding["PrivateParameterSHA256"] = {n: hashlib.sha256(v).hexdigest() for n, v in pbytes.items()}
    binding["ReferenceSHA256"] = dict(ANCHORS)
    binding["OriginalParameterGeneration"] = {"API": "prepare_gamma_pipeline_d5.real_parameters(profile, audit, True)",
                                               "SourceSHA256AtR0Generation": ORIGINAL_CONVERTER_SHA256,
                                               "CurrentConverterSourceIsNotAnInputDependency": True,
                                               "R1Validation": "Pinned canonical profile/audit plus independent signed-register serialization, exact R0 private-byte hashes"}
    top = (ROOT / f"board/{BASE}.v").read_text()
    top = replace_one(top, "module " + BASE + "(", "module " + TARGET + "(")
    top = replace_one(top, "gamma_frozen_capture #", "gamma_frozen_k320_dev #")
    top = replace_one(top, ".MAX_RADIUS_Q22(ROT_MAX_R2_Q22))", f".MAX_RADIUS_Q22(ROT_MAX_R2_Q22),.GROUP_SEED(28'h{GROUP_SEED:07x}))")
    for old, new in (("board/calibration-trial.vh", CAL), ("board/rotation-domain.vh", DOMAIN)):
        top = replace_one(top, "/" + old + '"', "/" + new + '"')
    top = "// K320 DEVELOPMENT ONLY one-shot same-source numerical probe; calibration not accepted.\n" + top
    frozen = (ROOT / "rtl/experimental/gamma_frozen_capture.v").read_text()
    frozen = replace_one(frozen, "module gamma_frozen_capture #", "module gamma_frozen_k320_dev #")
    frozen = replace_one(frozen, "BANK_STRIDE=262144,MAX_RADIUS_Q22=0)(", f"BANK_STRIDE=262144,MAX_RADIUS_Q22=0,parameter [27:0] GROUP_SEED=28'h{GROUP_SEED:07x})(")
    frozen = replace_one(frozen, "pair_id<=0;", "pair_id<={4'd0,GROUP_SEED}-32'd1;")
    frozen = replace_one(frozen,
                         "capture_active<=0;export_enable<=0;state<=0;reset_wait<=0;pairs_completed<=pairs_completed+1'b1;",
                         "capture_active<=0;export_enable<=0;state<=12;reset_wait<=0;pairs_completed<=pairs_completed+1'b1;")
    frozen = replace_one(frozen, "                8:state<=8;", "                12:state<=12; // One-shot: no second capture without FPGA reset.\n                8:state<=8;")
    mapping = {f"board/{BASE}{suffix}": f"board/{TARGET}{suffix}" for suffix in (".v", ".fdc", "-pins.json", "-sources.json")}
    mapping.update({f"board/build-{BASE}.tcl": f"board/build-{TARGET}.tcl",
                    "rtl/experimental/gamma_frozen_capture.v": FROZEN,
                    "board/calibration-trial.vh": CAL, "board/rotation-domain.vh": DOMAIN})
    names = [mapping.get(n, n) for n in json.loads((ROOT / f"board/{BASE}-sources.json").read_text())]
    names.extend((BINDING, PROFILE, AUDIT, "tools/prepare_gamma_capture_k320_dev.py"))
    if len(names) != len(set(names)):
        raise ValueError("Duplicate candidate source")
    tcl = (ROOT / f"board/build-{BASE}.tcl").read_text()
    for old, new in mapping.items():
        tcl = tcl.replace("/" + old + "}", "/" + new + "}")
    tcl = replace_one(tcl, "-top_module " + BASE, "-top_module " + TARGET)
    return {**pbytes, BINDING: json_bytes(binding), FROZEN: frozen.encode(),
            f"board/{TARGET}.v": top.encode(),
            f"board/{TARGET}.fdc": (ROOT / f"board/{BASE}.fdc").read_bytes(),
            f"board/{TARGET}-pins.json": (ROOT / f"board/{BASE}-pins.json").read_bytes(),
            f"board/{TARGET}-sources.json": json_bytes(names),
            f"board/build-{TARGET}.tcl": tcl.encode()}


def verify():
    files = expected()
    for name, payload in files.items():
        if (ROOT / name).read_bytes() != payload:
            raise ValueError("Exact isolated candidate changed: " + name)
    names = json.loads(files[f"board/{TARGET}-sources.json"])
    pins = json.loads(files[f"board/{TARGET}-pins.json"])
    if len(pins) != 128 or len(set(pins.values())) != 128 or pins.get("cam_data[5]") != "AA23":
        raise ValueError("Expected original settled-D5 128-pin map with AA23")
    excluded = {"board/calibration-trial.vh", "board/rotation-domain.vh", "rtl/experimental/gamma_frozen_capture.v"}
    if excluded.intersection(names) or any("pipeline_parity_cache" in n or "compact" in n for n in names):
        raise ValueError("Wrong parameter/cache implementation selected")
    return {"Target": TARGET, "HardwareAccessed": False, "PDSAccessed": False,
            "SourceSHA256": {n: sha(ROOT / n) for n in names},
            "ProfileBinding": json.loads(files[BINDING]), "Pins": pins,
            "Limits": LIMITS}


def stage():
    files = expected()
    if any((ROOT / n).exists() for n in files):
        raise ValueError("Refuse to overwrite any existing candidate file")
    if any(not (ROOT / n).parent.is_dir() for n in files):
        raise ValueError("Only existing source directories may be used")
    for name, payload in files.items():
        with (ROOT / name).open("xb") as stream:
            stream.write(payload)
    return verify()


def advance_r1():
    """Explicit, source-checked revision of this owned unbuilt candidate only."""
    work = ROOT / "build/offline-20261024/gamma-k320-triplet-sim-20261026"
    archive = work / "r0-source-snapshot.zip"
    if sha(archive) != "60763ff7f0b779cc5b70341a2eaadda2a3f12233544d6d43259cd62154200151":
        raise ValueError("Original R0 candidate snapshot changed")
    files = expected()
    with zipfile.ZipFile(archive) as source:
        for name in files:
            if (ROOT / name).read_bytes() != source.read(name):
                raise ValueError("Only the exact saved R0 candidate may advance: " + name)
    for name, payload in files.items():
        (ROOT / name).write_bytes(payload)
    return verify()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", action="store_true")
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--advance-r1", action="store_true")
    args = parser.parse_args()
    result = advance_r1() if args.advance_r1 else stage() if args.stage else verify() if args.verify else {
        "Target": TARGET, "HardwareAccessed": False, "PDSAccessed": False,
        "FilesWouldBeCreated": list(expected()), "DevelopmentOnly": True,
        "CalibrationAccepted": False, "Limits": LIMITS}
    print(json.dumps(result, indent=2, allow_nan=False))
