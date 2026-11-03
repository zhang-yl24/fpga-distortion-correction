"""Verify the exact source/IP inputs of the board-running fill8 R3 seed3 bitstream; no EDA."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def require(ok, message):
    if not ok:
        raise ValueError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def bound_file(root, name):
    relative = PurePosixPath(name)
    require(not relative.is_absolute() and ".." not in relative.parts
            and ":" not in name and "\\" not in name, "invalid relative input: " + name)
    path = root.joinpath(*relative.parts).resolve()
    require(path.is_relative_to(root.resolve()) and path.is_file(), "missing input: " + str(path))
    return path


def check_hash(path, expected):
    require(digest(path.read_bytes()) == expected, "SHA256 differs: " + str(path))


def replay_changes(data, changes):
    for change in changes:
        if change["Kind"] == "BoundHeaderIncludeRelocation":
            old, new = change["Original"].encode(), change["Compiled"].encode()
        elif change["Kind"] == "SelectedDigitalTimingOnly":
            old = ("parameter integer %s=%s" % (change["Parameter"], change["Original"])).encode()
            new = ("parameter integer %s=%s" % (change["Parameter"], change["Compiled"])).encode()
        else:
            raise ValueError("unknown released source transformation")
        require(data.count(old) == change["ReplacementCount"], "source transformation count differs")
        data = data.replace(old, new)
    return data


def relocated_bytes(entry, released_bytes, compiled_root):
    data = released_bytes
    for change in entry["BuildChanges"]:
        if change["Kind"] == "BoundHeaderIncludeRelocation":
            old = change["Compiled"].encode()
            new = (compiled_root / change["Header"]).as_posix().encode()
            require(data.count(old) == change["ReplacementCount"], "compiled include count differs")
            data = data.replace(old, new)
    return data


def verify(repo=REPO, prepared=None):
    repo = Path(repo).resolve()
    manifest = read(HERE / "source-manifest.json")
    require(manifest["Schema"] == "hdmi-camera-fisheye-fill8r3s3-portable-source-v1", "wrong source schema")
    provenance = {}
    for role, reference in manifest["Provenance"].items():
        path = bound_file(HERE, reference["Path"])
        check_hash(path, reference["SHA256"])
        provenance[role] = path
    build = read(provenance["BuildPlan"])
    bit = read(provenance["BitstreamPlan"])
    verification = read(provenance["BitstreamVerification"])
    require(bit["BuildPlan"]["SHA256"] == digest(provenance["BuildPlan"].read_bytes()), "bit/build plan link differs")
    require(verification["EvidenceSHA256"]["bitstream-plan.json"] == digest(provenance["BitstreamPlan"].read_bytes()), "bit verification link differs")
    require(verification["Verified"] is True and verification["Target"] == build["Target"] == manifest["Target"], "release target differs")
    require(verification["Bitstream"]["SHA256"] == manifest["ReleasedBitstream"]["SHA256"]
            and verification["Bitstream"]["Bytes"] == manifest["ReleasedBitstream"]["Bytes"]
            and verification["FinalADFSHA256"] == bit["FinalADFSHA256"] == manifest["ReleasedBitstream"]["FinalADFSHA256"], "released artifact identity differs")
    selected_bit = bound_file(repo, manifest["ReleasedBitstream"]["RepositoryPath"])
    require(selected_bit.stat().st_size == manifest["ReleasedBitstream"]["Bytes"], "selected bit length differs")
    check_hash(selected_bit, manifest["ReleasedBitstream"]["SHA256"])
    require(len(manifest["Files"]) == 110 and manifest["PlacementSeed"] == 3
            and manifest["ForcePlaceRoute"] is True, "selected source/seed boundary differs")
    transformed = [entry for entry in manifest["Files"] if entry["BuildChanges"]]
    require(len(transformed) == manifest["ExpectedCompiledTransformFileCount"] == 6
            and sum(change["Kind"] == "BoundHeaderIncludeRelocation" for entry in transformed for change in entry["BuildChanges"]) == 5
            and sum(change["Kind"] == "SelectedDigitalTimingOnly" for entry in transformed for change in entry["BuildChanges"]) == 1,
            "selected six-file/five-include/one-timing transformation inventory differs")
    original = read(bound_file(repo, manifest["SourceManifest"]))
    require(original["source_files"] == build["SourceFiles"], "source ordering differs")
    require([entry["Source"] for entry in manifest["Files"]] == ["distortion/" + name for name in build["SourceFiles"]], "source inventory differs")
    require(len(build["CompiledInputs"]) == len(manifest["Files"]), "compiled input count differs")
    released = {}
    for entry, original_entry in zip(manifest["Files"], build["CompiledInputs"]):
        name = original_entry["Source"]
        require(entry["Source"] == "distortion/" + name and entry["SourceSHA256"] == original_entry["OriginalSHA256"] == original["SourceSHA256"][name]
                and entry["CompiledSHA256"] == original_entry["CompiledSHA256"]
                and entry["BuildChanges"] == original_entry["Changes"], "build source record differs: " + name)
        canonical = bound_file(repo, entry["Source"])
        check_hash(canonical, entry["SourceSHA256"])
        original_path = str(PureWindowsPath(build["ProjectRoot"]) / PurePosixPath(name))
        require(bit["InputSHA256"].get(original_path) == entry["SourceSHA256"]
                and bit["InputSHA256"].get(original_entry["CompiledPath"]) == entry["CompiledSHA256"], "source not bound by bitstream plan: " + name)
        data = canonical.read_bytes()
        if "FrozenCompiled" in entry:
            frozen = bound_file(HERE, entry["FrozenCompiled"])
            check_hash(frozen, entry["CompiledSHA256"])
            require(replay_changes(data, entry["BuildChanges"]) == frozen.read_bytes(), "compiled transformation differs: " + name)
            data = frozen.read_bytes()
        else:
            require(not entry["BuildChanges"] and entry["SourceSHA256"] == entry["CompiledSHA256"], "missing compiled snapshot: " + name)
        require(digest(data) == entry["CompiledSHA256"], "compiled source differs: " + name)
        released[name] = data
    for entry in manifest["AdditionalInputs"]:
        check_hash(bound_file(repo, entry["Source"]), entry["SHA256"])
    require(digest(bound_file(repo, manifest["SourceManifest"]).read_bytes()) == build["Manifest"]["SHA256"], "selected S3 manifest differs")
    expected_additional = {manifest["SourceManifest"]: build["Manifest"]["SHA256"],
                           "distortion/" + original["RouteConstraint"]: original["RouteConstraintSHA256"]}
    require({entry["Source"]: entry["SHA256"] for entry in manifest["AdditionalInputs"]} == expected_additional, "additional input roles differ")
    rcf = original["RouteConstraint"]
    rcf_sha = original["RouteConstraintSHA256"]
    require(bit["InputSHA256"][str(PureWindowsPath(build["ProjectRoot"]) / PurePosixPath(rcf))] == rcf_sha
            and build["PreparedSHA256"][str(PureWindowsPath(build["WorkDirectory"]) / "compiled" / PurePosixPath(rcf))] == rcf_sha,
            "RCF not bound to original build/bit inputs")
    idf_name = "platform/video_base/ipcore/ddr3_test/ddr3_test.idf"
    idf = ET.fromstring(released[idf_name])
    expanded = [(PurePosixPath(idf_name).parent / node.attrib["pathname"]).as_posix()
                for node in idf.findall("./file_list/source/file")]
    require(expanded == build["SourceRoles"]["IDFExpandedSources"] and all(name in released for name in expanded), "DDR IDF source closure differs")
    native_prefix = build["CompiledInputs"][0]["NativeCompiledPath"][:-len(build["CompiledInputs"][0]["Source"])]
    tcl = provenance["BuildTcl"].read_bytes()
    require(digest(tcl) == build["PreparedSHA256"][str(PureWindowsPath(build["WorkDirectory"]) / "build.tcl")], "original Tcl not bound by build plan")
    pnr = re.findall(rb"^pnr ([^\r\n]+)$", tcl, re.M)
    require(pnr == [b"-force_to_run -gplace_seed 3 -optimize_multi_corner_timing -fix_hold_violation -fix_hold_violation_iterations 50 -fix_hold_violation_threshold 100 -fix_hold_violation_in_route TRUE"],
            "selected forced placement-seed3 command differs")
    designs = re.findall(rb"^add_design \{([^}]+)\}$", tcl, re.M)
    require(designs == [(native_prefix + name).encode() for name in build["SourceRoles"]["ExplicitDesigns"]], "explicit PDS design roles differ")
    constraints = re.findall(rb"^add_constraint \{([^}]+)\}$", tcl, re.M)
    require(constraints == [(native_prefix + name).encode() for name in [original["Constraint"], original["RouteConstraint"]]], "PDS constraint roles differ")
    if prepared is not None:
        prepared = Path(prepared).resolve()
        receipt = read(prepared / "rebuild-plan.json")
        require(receipt["Schema"] == "hdmi-camera-fisheye-fill8r3s3-relocated-build-v1"
                and receipt["Target"] == manifest["Target"]
                and receipt["OriginalBuildPlanSHA256"] == manifest["Provenance"]["BuildPlan"]["SHA256"]
                and receipt["ReleasedBitstreamSHA256"] == manifest["ReleasedBitstream"]["SHA256"]
                and receipt["EDAExecuted"] is False and receipt["HistoricalTimingSignoffInherited"] is False,
                "prepared receipt identity/boundary differs")
        require(receipt["SourceManifestSHA256"] == digest((HERE / "source-manifest.json").read_bytes()), "prepared release identity differs")
        expected = {}
        for entry in manifest["Files"]:
            name = entry["Source"].removeprefix("distortion/")
            data = relocated_bytes(entry, released[name], prepared / "compiled")
            path = bound_file(prepared / "compiled", name)
            require(path.read_bytes() == data, "prepared source differs: " + name)
            expected[name] = digest(data)
        rcf = original["RouteConstraint"]
        data = bound_file(repo, "distortion/" + rcf).read_bytes()
        require(bound_file(prepared / "compiled", rcf).read_bytes() == data, "prepared RCF differs")
        expected[rcf] = digest(data)
        actual = {p.relative_to(prepared / "compiled").as_posix() for p in (prepared / "compiled").rglob("*") if p.is_file()}
        require(actual == set(expected) and receipt["PreparedSHA256"] == expected, "prepared closure inventory differs")
        expected_tcl = tcl.replace(native_prefix.rstrip("/").encode(), (prepared / "compiled").as_posix().encode())
        require((prepared / "build.tcl").read_bytes() == expected_tcl, "prepared Tcl differs")
        require(receipt["BuildTclSHA256"] == digest(expected_tcl), "prepared Tcl receipt differs")
    return manifest, build, original, released, tcl, native_prefix


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--prepared", type=Path)
    args = parser.parse_args()
    manifest, build, _, _, _, _ = verify(args.repo, args.prepared)
    print(json.dumps({"verified": True, "source_files": len(manifest["Files"]),
                      "ddr_ip_sources": len(build["SourceRoles"]["IDFExpandedSources"]),
                      "released_bitstream_sha256": manifest["ReleasedBitstream"]["SHA256"],
                      "prepared_verified": args.prepared is not None}, indent=2))


if __name__ == "__main__":
    main()
