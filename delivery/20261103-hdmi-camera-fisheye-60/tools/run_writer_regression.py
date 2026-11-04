"""Run raster and double-stripe writer handshake, payload and recovery checks."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import subprocess

PACKAGE = Path(__file__).resolve().parents[1]
REPO = PACKAGE.parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work", type=Path, required=True, help="new short output directory")
    parser.add_argument("--vivado-bin", type=Path, required=True)
    args = parser.parse_args()
    work = args.work.resolve()
    if work.exists():
        raise ValueError("Choose a new work directory")
    work.mkdir(parents=True)
    source_files = [PACKAGE / "rtl/ddr_adaptive_result_writer.v", PACKAGE / "tests/cache_writer_pingpong.sv",
                    PACKAGE / "tests/tb_stripe_writer.sv", PACKAGE / "tests/tb_writer_fault_collision.sv",
                    REPO / "distortion/rtl/video_crc32.vh"]
    hashes = {}
    for source in source_files:
        payload = source.read_bytes()
        (work / source.name).write_bytes(payload)
        hashes[source.relative_to(REPO).as_posix()] = hashlib.sha256(payload).hexdigest()
    stripe32 = (work / "tb_stripe_writer.sv").read_text().replace(
        "module tb_stripe_writer #(parameter TILE_W=8);", "module tb_stripe_writer32 #(parameter TILE_W=32);")
    (work / "tb_stripe_writer32.sv").write_text(stripe32, encoding="utf-8", newline="\n")
    commands = []

    def run(tool, arguments, label, pass_marker=None):
        command = [str(args.vivado_bin.resolve() / (tool + ".bat")), *arguments]
        process = subprocess.run(command, cwd=work, capture_output=True, text=True, timeout=120)
        output = process.stdout + process.stderr
        (work / (label + ".log")).write_text(output, encoding="utf-8")
        passed = process.returncode == 0 and "Fatal:" not in output and "ERROR:" not in output
        if pass_marker is not None:
            passed &= pass_marker in output
        commands.append({"label": label, "command": command, "returncode": process.returncode, "passed": passed})
        if not passed:
            raise RuntimeError("Failed " + label + "; inspect " + str(work / (label + ".log")))
        return [line for line in output.splitlines() if line.startswith("METRIC")]

    run("xvlog", ["--sv", "ddr_adaptive_result_writer.v", "cache_writer_pingpong.sv", "tb_stripe_writer.sv", "tb_stripe_writer32.sv", "tb_writer_fault_collision.sv"], "compile")
    for name, snapshot in [("tb_writer_pingpong", "raster"), ("tb_stripe_writer", "stripe8"), ("tb_stripe_writer32", "stripe32"), ("tb_writer_fault_collision", "collision")]:
        run("xelab", [name, "-mt", "2", "-s", snapshot], "elaborate-" + snapshot)
    cases = []
    selections = [("raster", case, 0) for case in range(15)]
    selections += [("raster", case, 1) for case in [0, 1, 2, 3, 11]]
    selections += [("stripe" + str(width), case, 1) for width in [8, 32] for case in [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 11, 12, 13, 14, 15]]
    for snapshot, case, tile in selections:
        label = f"{snapshot}-case-{case}-tile-{tile}"
        marker = "PASS writer" if snapshot == "raster" else "PASS stripe writer"
        metrics = run("xsim", [snapshot, "-testplusarg", "CASE" + str(case), "-testplusarg", "TILE" + str(tile), "-runall"], label, marker)
        cases.append({"snapshot": snapshot, "case": case, "tile_mode": tile, "passed": True, "metrics": metrics})
        print(json.dumps(cases[-1]), flush=True)
    collision_metrics = run("xsim", ["collision", "-runall"], "fault-collisions", "PASS writer fault collisions checks=10")
    report = {"schema": "fisheye60-writer-regression-v1", "passed": True, "case_count": len(cases),
              "fault_collision_count": 10, "fault_collision_metrics": collision_metrics,
              "source_sha256": hashes, "commands": commands, "cases": cases,
              "checks": ["pixel values and independent raster CRC", "AW/W address and payload stability",
                         "backpressure with both stripes occupied", "tag and transport faults retain committed writes",
                         "reset during partial stripe, pending AW and pending W", "multiple frames and mode changes"],
              "scope": "Digital writer unit verification. No native timing or hardware validation."}
    (work / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"passed": True, "cases": len(cases), "report": str(work / "report.json")}))


if __name__ == "__main__":
    main()
