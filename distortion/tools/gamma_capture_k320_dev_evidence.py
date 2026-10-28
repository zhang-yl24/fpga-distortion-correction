"""Read-only bridge gate for this exact independent development triplet target.

R0 actual native replay and R1 dark/Gamma1 replay are separate evidence.
No PDS/device API; no promotion of the unaccepted calibration.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

import prepare_gamma_capture_k320_dev as candidate
import read_gamma_capture_k320_dev as reader
from frame_protocol import FrameParser
from gamma_triplets import GammaTripletAssembler
from frozen_gamma_analysis import geometry, analyze

ROOT = candidate.ROOT
APPROVED = ROOT / "build/offline-20261024"
R0 = APPROVED / "gamma-k320-triplet-sim-20261026"
R1 = APPROVED / "gamma-k320-triplet-r1-dark-20261026"
FINAL = APPROVED / "gamma-k320-dev-simulation-bridge-final-20261026.json"
R1_REPORT_SHA256 = "158c58c20f48b4c734c64deb89cda5430488974172615be82aff3044ee56bee4"
HELPER_PATHS = ("tools/gamma_capture_k320_dev_evidence.py", "tools/prepare_gamma_capture_k320_dev.py",
                "tools/read_gamma_capture_k320_dev.py", "tools/frame_protocol.py", "tools/gamma_triplets.py",
                "tools/frozen_gamma_analysis.py", "tools/evaluate-tone-pair.py", "model/reference.py")
PINNED = {
    R0 / "r0-source-snapshot.zip": "60763ff7f0b779cc5b70341a2eaadda2a3f12233544d6d43259cd62154200151",
    R0 / "gamma-k320-triplet-simulation.json": "ac4f097c2d4d54f853617f7d2d296ba5dedc86312938240b9866b6bea4f1df96",
    R0 / "actual-t01/r0-actual-mathematics-audit.json": "9f8177f3d895b88bcf68ebadddc5473fcc282474beedad653a900680787cbfdf",
    R0 / "r1-source-delta-audit.json": "282ffaf4ca7121500afa26908e74e9a981be5d7c57ce039394b4e5260c649845",
    R0 / "actual-t01/simulation.log": "ab0e9da5f2a07cf7b82e8f12d890c3b37b4df596028e65a7ff01fac13e7aa665",
    ROOT / "output/project/gamma-k320-dev-sensor-mode-comparison-20261026.json": "0353b7c8113fdf3c5b5ae754a8b5a9c8db932e6507be8e7572a7d19e02f329b4",
}


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def _verified_inputs():
    require(R1_REPORT_SHA256 is not None, "R1 actual simulation proof is still pending registration")
    prepared = candidate.verify()
    pins = dict(PINNED)
    pins[R1 / "gamma-k320-triplet-simulation.json"] = R1_REPORT_SHA256
    require(all(candidate.sha(p) == h for p, h in pins.items()), "Pinned proof bytes changed")
    original = read(R0 / "gamma-k320-triplet-simulation.json")
    actual = read(R0 / "actual-t01/r0-actual-mathematics-audit.json")
    delta = read(R0 / "r1-source-delta-audit.json")
    dark = read(R1 / "gamma-k320-triplet-simulation.json")
    require(original["Passed"] is False and actual["OriginalOverallPassed"] is False
            and actual["SourceClosurePassed"] is False and actual["ActualT01ArithmeticPassed"] is True,
            "Do not promote R0 source-closure failure to whole-source success")
    require(dark["Passed"] is True and dark["SourceUnchanged"] is True
            and dark["SourceSHA256"] == dark["SourceSHA256After"]
            and dark["RequestedSuites"] == "synthetic-dark" and dark["R1ActualSourceSimulationExecuted"] is False,
            "Need completed R1 dark-only source-bound simulation")
    for name, digest in dark["SourceSHA256"].items():
        path = (ROOT/name).resolve()
        require(path.is_relative_to(ROOT.resolve()) and candidate.sha(path) == digest,
                "R1 executed dependency changed: " + name)
    require(all(dark["SourceSHA256"].get(n) == h for n, h in prepared["SourceSHA256"].items()),
            "R1 proof does not cover this current independent candidate")
    binding = prepared["ProfileBinding"]
    with zipfile.ZipFile(R0 / "r0-source-snapshot.zip") as source:
        old_binding = json.loads(source.read(candidate.BINDING))
        for key in ("IntegerConfig", "RadiusGuardQ22", "Identity", "ProfileSHA256", "MappingAuditSHA256"):
            require(old_binding[key] == binding[key], "R0/R1 actual math binding changed: " + key)
        for name in (candidate.CAL, candidate.DOMAIN):
            require(source.read(name) == (ROOT/name).read_bytes(), "Private register bytes changed")
        frozen = (ROOT/candidate.FROZEN).read_text()
        frozen = frozen.replace(f",parameter [27:0] GROUP_SEED=28'h{candidate.GROUP_SEED:07x}", "")
        frozen = frozen.replace("pair_id<={4'd0,GROUP_SEED}-32'd1;", "pair_id<=0;")
        require(frozen.encode() == source.read(candidate.FROZEN), "R0/R1 frozen body differs beyond seed")
        top = f"board/{candidate.TARGET}.v"
        normalized = (ROOT/top).read_text().replace(f",.GROUP_SEED(28'h{candidate.GROUP_SEED:07x})", "")
        require(normalized.encode() == source.read(top), "R0/R1 top differs beyond explicit seed")
        require(hashlib.sha256(source.read("derived-testbench.sv")).hexdigest() == dark["DerivedTB"]["SHA256"],
                "Full native testbench changed between actual and dark cases")
        for name, digest in delta["SameSharedFPGASourceSHA256"].items():
            require(hashlib.sha256(source.read(name)).hexdigest() == digest == candidate.sha(ROOT/name),
                    "Shared FPGA body changed: " + name)
    actual_wire = (R0 / "actual-t01/export.bin").read_bytes()
    require(candidate.sha(R0 / "actual-t01/export.bin") == actual["WireSHA256"] and len(actual_wire) == 1843332,
            "R0 full actual wire changed")
    parser, assembler = FrameParser(), GammaTripletAssembler()
    frames = parser.feed(actual_wire)
    require(len(frames) == 3 and not (parser.buffer or parser.rejected or parser.discarded), "R0 full frame CRC parse failed")
    triple = None
    for frame in frames:
        triple = assembler.feed(frame)
    require(triple is not None and triple.group_id == 1, "R0 was not the original group1")
    coords, mask = geometry(binding["IntegerConfig"], radius_bound=binding["RadiusGuardQ22"])
    checked, _ = analyze(triple, coords, mask, "synthetic_same_source")
    capture = actual["InputCapture"]
    require(checked["passed"] and checked["crc32"] == actual["Analysis"]["crc32"]
            and triple.raw.payload == Path(capture["raw_path"]).read_bytes()
            and candidate.sha(capture["raw_path"]) == capture["raw_sha256"]
            and candidate.sha(capture["metadata_path"]) == capture["metadata_sha256"],
            "R0 actual raw/golden provenance or exact pixel analysis failed")
    dark_case = dark["Suites"]["synthetic-dark"]
    require(candidate.sha(R1 / "synthetic-dark/export.bin") == dark_case["WireSHA256"]
            and candidate.sha(R1 / "synthetic-dark/simulation.log") == dark_case["LogSHA256"], "R1 wire/log changed")
    dark_checked, _, dark_triple = reader.check_wire((R1 / "synthetic-dark/export.bin").read_bytes())
    require(dark_checked["passed"] and dark_checked["mode"] == 1 and dark_triple.group_id == candidate.GROUP_SEED
            and dark_checked["crc32"] == dark_case["Golden"]["CRC32"], "R1 dark/Gamma1/seed numerical validation failed")
    return {"Passed": True, "Target": candidate.TARGET, "PreparedSourceCount": len(prepared["SourceSHA256"]),
            "SourceSHA256": prepared["SourceSHA256"], "InputProofSHA256": {str(p): h for p, h in pins.items()},
            "R0Scope": "One actual bound T01 input through R0 full VGA RTL; exact raw/bypass/Gamma0 pixels. Whole R0 source closure remains false.",
            "R1Scope": "One full VGA synthetic dark input through R1 RTL, exact Gamma1 pixels and seeded PGFRAME1 packets. R1 actual input is NOT directly re-simulated.",
            "SourceBridge": "Exact same private13 bytes/guard and shared FPGA arithmetic; only seed declaration/reset initial ID and top seed binding differ.",
            "ActualInputCRC32": checked["crc32"], "R1DarkCRC32": dark_checked["crc32"], "GroupSeed": candidate.GROUP_SEED,
            "ModeSourceComparison": "source-equivalent to original guarded CAM2 native input, not measured register equality",
            "DirectR1ActualSimulationPassed": False, "OfflineSourceProofReady": True,
            "HardwareAccessed": False, "PDSAccessed": False, "CalibrationAccepted": False, "HardwareReleaseAllowed": False,
            "DevelopmentOnly": True, "ContinuousMainValidated": False, "Limits": candidate.LIMITS}


def verify_simulation():
    """Return fixed proof Path/SHA plus checked R0/R1 scopes; never writes."""
    expected = _verified_inputs()
    require(read(FINAL) == expected, "Final bridge record changed or is not current")
    return {"Path": str(FINAL), "SHA256": candidate.sha(FINAL), **expected}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--record-final", action="store_true")
    args = parser.parse_args()
    if args.record_final:
        expected = _verified_inputs()
        with FINAL.open("x", encoding="utf-8") as out:
            json.dump(expected, out, indent=2, allow_nan=False); out.write("\n")
    result = verify_simulation()
    print(json.dumps({"Passed": result["Passed"], "Path": result["Path"], "SHA256": result["SHA256"]}))
