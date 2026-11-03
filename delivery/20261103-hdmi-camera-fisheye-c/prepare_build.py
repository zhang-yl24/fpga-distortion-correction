"""Prepare a relocated copy of released C build inputs and Tcl; never run EDA."""
import argparse
import json
import os
from pathlib import Path

from verify_source import HERE, REPO, bound_file, digest, relocated_bytes, require, verify


def prepare(repo, output):
    repo, output = Path(repo).resolve(), Path(output).resolve()
    require(not output.exists(), "output already exists; select a new empty build directory")
    require(not any(c in output.as_posix() for c in "{}\r\n\x00"), "output path cannot be represented safely in Tcl")
    manifest, build, original, released, tcl, native_prefix = verify(repo)
    compiled = output / "compiled"
    if os.name == "nt":
        longest = max(len(str(compiled / entry["Source"].removeprefix("distortion/"))) for entry in manifest["Files"])
        require(longest < 260, "build path exceeds Windows/PDS MAX_PATH; select a shorter --output directory (for example .bld)")
    prepared_hashes = {}
    output.mkdir(parents=True)
    for entry in manifest["Files"]:
        name = entry["Source"].removeprefix("distortion/")
        data = relocated_bytes(entry, released[name], compiled)
        destination = compiled / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
        prepared_hashes[name] = digest(data)
    rcf = original["RouteConstraint"]
    destination = compiled / rcf
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(bound_file(repo, "distortion/" + rcf).read_bytes())
    prepared_hashes[rcf] = digest(destination.read_bytes())
    relocated_tcl = tcl.replace(native_prefix.rstrip("/").encode(), compiled.as_posix().encode())
    require(native_prefix.encode() not in relocated_tcl, "old native path remains in generated Tcl")
    (output / "build.tcl").write_bytes(relocated_tcl)
    receipt = {
        "Schema": "hdmi-camera-fisheye-c-relocated-build-v1",
        "Target": manifest["Target"],
        "SourceManifestSHA256": digest((HERE / "source-manifest.json").read_bytes()),
        "OriginalBuildPlanSHA256": manifest["Provenance"]["BuildPlan"]["SHA256"],
        "ReleasedBitstreamSHA256": manifest["ReleasedBitstream"]["SHA256"],
        "PreparedSHA256": prepared_hashes,
        "BuildTclSHA256": digest(relocated_tcl),
        "CompilerVersionOfReleasedBuild": "PDS 2023.2-SP3 build 154097",
        "CommandTemplate": ["<PDS-install>/bin/pds_shell.exe", "-file", (output / "build.tcl").as_posix(),
                            "-work_dir", output.as_posix(), "-project_name", manifest["Target"]],
        "Relocations": "Only the five bound Verilog include paths and Tcl compiled-root paths are relocated. The released compiled INPUT_TIMING_CONFIGURED=1 is preserved.",
        "EDAExecuted": False,
        "HardwareAccessed": False,
        "HistoricalTimingSignoffInherited": False,
        "NewBuildRequiresIndependentValidation": True,
    }
    (output / "rebuild-plan.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8", newline="\n")
    verify(repo, output)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--output", type=Path, required=True, help="new build directory, must not exist")
    args = parser.parse_args()
    receipt = prepare(args.repo, args.output)
    print(json.dumps({"prepared": True, "source_files": len(receipt["PreparedSHA256"]),
                      "build_tcl": str(args.output.resolve() / "build.tcl"),
                      "eda_executed": False, "historical_timing_signoff_inherited": False}, indent=2))


if __name__ == "__main__":
    main()
