"""Bounded two-file scatter4 RTL test; no synthesis or hardware interfaces."""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import hashlib
import json
import re
import time
from run_gamma_pipeline_d5_sim import tool

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ("rtl/experimental/ddr_compact_neighbour_cache_scatter4.v",
           "tests/tb_scatter4_neighbour_cache.sv", "tools/run_scatter4_directed_sim.py",
           "tools/run_gamma_pipeline_d5_sim.py")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workdir", type=Path, required=True)
    args = parser.parse_args()
    work = args.workdir.resolve()
    approved = (ROOT / "build/offline-20261024").resolve()
    if not work.is_dir() or not work.is_relative_to(approved) or any(work.iterdir()):
        parser.error("existing empty directory below approved scratch required")
    before = {name: sha(ROOT / name) for name in SOURCES}
    report = dict(Passed=False, HardwareAccessed=False, PDSAccessed=False,
                  SourceSHA256=before, Commands=[], MaximumSeconds=180,
                  StartedUtc=datetime.now(timezone.utc).isoformat())
    deadline = time.monotonic() + 180
    bin_dir = Path("E:/Vivado/Vivado/2017.4/bin")
    stages = (("xvlog.bat", ["--sv", *[str(ROOT / n) for n in SOURCES[:2]]], "compile"),
              ("xelab.bat", ["tb_scatter4_neighbour_cache", "-s", "scatter4_directed"], "elaborate"),
              ("xsim.bat", ["scatter4_directed", "-runall", "-log", "simulation.log"], "simulate"))
    try:
        for exe, arguments, stage in stages:
            item = dict(Stage=stage, NativeArgv=[str(bin_dir / exe), *arguments], ReturnCode=None)
            report["Commands"].append(item)
            try:
                tool(bin_dir, exe, arguments, work, deadline, stage)
                item["ReturnCode"] = 0
            except Exception as exc:
                match = re.search(r"failed, exit=(-?\d+)", str(exc))
                if match:
                    item["ReturnCode"] = int(match.group(1))
                raise
        log = (work / "simulation.log").read_text(encoding="utf-8", errors="replace")
        if ("PASS SCATTER4 independent directed regression:" not in log or
                re.search(r"(?im)^\s*(?:fatal|error):", log)):
            raise ValueError("mandatory directed completion absent or RTL fatal/error present")
        report.update(Passed=True, PassLines=[n for n in log.splitlines() if n.startswith("PASS")],
                      Coverage=[n for n in log.splitlines() if n.startswith("SCATTER4 coverage")])
    except (Exception, KeyboardInterrupt) as exc:
        report["Error"] = type(exc).__name__ + ": " + str(exc)
    finally:
        report["SourceSHA256After"] = {n: sha(ROOT / n) for n in SOURCES}
        if report["SourceSHA256After"] != before:
            report.update(Passed=False, SourceDrift=True)
        report["LogSHA256"] = {p.name: sha(p) for p in work.glob("*.log")}
        report["EndedUtc"] = datetime.now(timezone.utc).isoformat()
        with (work / "directed-result.json").open("x", encoding="utf-8") as out:
            json.dump(report, out, indent=2)
            out.write("\n")
    print(json.dumps(report, indent=2))
    return 0 if report["Passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
