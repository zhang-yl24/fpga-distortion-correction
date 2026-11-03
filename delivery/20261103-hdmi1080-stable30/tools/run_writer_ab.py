"""Offline byte-exact writer A/B and fault regression. No hardware access."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time

PACKAGE = Path(__file__).resolve().parents[1]
ROOT = PACKAGE.parents[1]
BASELINE = ROOT / "delivery/20261103-hdmi1080-demo-source/native/source/rtl"


def run_command(argv, cwd, name, timeout=180):
    result = subprocess.run([str(x) for x in argv], cwd=cwd, capture_output=True,
                            text=True, errors="replace", timeout=timeout)
    (cwd / f"{name}.log").write_text(result.stdout + result.stderr, encoding="utf-8")
    if result.returncode:
        raise RuntimeError(f"{name} returned {result.returncode}; see {cwd / (name+'.log')}")
    return result.stdout + result.stderr


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--vivado-bin", type=Path, default=None)
    parser.add_argument("--only", choices=("baseline", "candidate"))
    args = parser.parse_args()
    work = args.work.resolve()
    work.mkdir(parents=True, exist_ok=False)
    vivado = args.vivado_bin or (Path(os.environ["FPGA_VIVADO_BIN"]) if "FPGA_VIVADO_BIN" in os.environ else None)
    iverilog, vvp = shutil.which("iverilog"), shutil.which("vvp")
    if not (iverilog and vvp) and not vivado:
        raise SystemExit("Set --vivado-bin, FPGA_VIVADO_BIN, or install iverilog + vvp")
    report = {"passed": False, "hardware_accessed": False, "pds_accessed": False,
              "source_sha256": {}, "cases": [], "comparison": []}
    started = time.monotonic()
    for variant in ("baseline", "candidate"):
        if args.only and args.only != variant:
            continue
        directory = work / variant
        directory.mkdir(exist_ok=False)
        source = BASELINE / "experimental/ddr_adaptive_result_writer.v" if variant == "baseline" else PACKAGE / "rtl/ddr_adaptive_result_writer.v"
        bench = PACKAGE / "tests/tb_writer_pingpong.sv"
        header = BASELINE / "video_crc32.vh"
        for path in (source, bench, header):
            report["source_sha256"][str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
        writer = re.sub(r'`include "[^"]*video_crc32.vh"', '`include "video_crc32.vh"', source.read_text(encoding="utf-8-sig"))
        (directory / "writer.v").write_text(writer, encoding="utf-8")
        shutil.copyfile(bench, directory / bench.name)
        shutil.copyfile(header, directory / header.name)
        if iverilog and vvp:
            run_command([iverilog,"-g2012","-s","tb_writer_pingpong","-o","sim.vvp","writer.v",bench.name],directory,"compile")
        else:
            run_command([vivado / "xvlog.bat","--sv","writer.v",bench.name],directory,"compile")
            run_command([vivado / "xelab.bat","tb_writer_pingpong","-s","writer_snapshot"],directory,"elaborate")
        cases = [(case,0) for case in (range(15) if variant == "candidate" else range(4))] + [(0,1),(1,1),(11,1)]
        for case, tile in cases:
            name=f"case-{case}-tile-{tile}"
            if iverilog and vvp:
                text=run_command([vvp,"sim.vvp",f"+CASE{case}",f"+TILE{tile}"],directory,name)
            else:
                text=run_command([vivado / "xsim.bat","writer_snapshot","-runall","-testplusarg",f"CASE{case}","-testplusarg",f"TILE{tile}"],directory,name)
            if "PASS writer" not in text or re.search(r"(?im)^\s*(fatal|error):",text):
                raise RuntimeError(f"{variant} {name} did not pass; see {directory / (name+'.log')}")
            metrics=[{k:int(v,16) if k=="crc" else int(v) for k,v in re.findall(r"(\w+)=([0-9a-fA-F]+)",line)}
                     for line in text.splitlines() if line.startswith("METRIC ")]
            report["cases"].append({"variant":variant,"case":case,"tile":tile,"passed":True,"metrics":metrics})
            print(f"PASS {variant} case={case} tile={tile} {metrics}",flush=True)
    for case in range(4):
        rows={r["variant"]:r for r in report["cases"] if r["case"]==case and r["tile"]==0}
        if "baseline" in rows and "candidate" in rows:
            baseline,candidate=rows["baseline"]["metrics"][0],rows["candidate"]["metrics"][0]
            report["comparison"].append({"case":case,"baseline_cycles":baseline["cycles"],"candidate_cycles":candidate["cycles"],
                "cycles_saved":baseline["cycles"]-candidate["cycles"],"baseline_input_stalls":baseline["input_stalls"],"candidate_input_stalls":candidate["input_stalls"]})
    report.update(passed=True,elapsed_seconds=round(time.monotonic()-started,3))
    (work / "writer-ab.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report["comparison"],indent=2))


if __name__ == "__main__":
    main()

