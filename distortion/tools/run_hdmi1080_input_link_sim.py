"""One bounded small input/shared-write integration, with a core PROXY."""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import hashlib
import json
import re
import time
from run_gamma_pipeline_d5_sim import tool

ROOT=Path(__file__).resolve().parents[1]
NAMES=("rtl/video_async_fifo.v", "rtl/ddr_write_arbiter.v",
       "rtl/experimental/hdmi1080_capture_cdc.v", "rtl/experimental/hdmi1080_input_dma.v",
       "rtl/experimental/hdmi1080_input_write_link.v", "tests/tb_hdmi1080_input_write_link.sv",
       "tools/run_hdmi1080_input_link_sim.py", "tools/run_gamma_pipeline_d5_sim.py")


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workdir",type=Path,required=True)
    args=parser.parse_args();work=args.workdir.resolve()
    approved=(ROOT/"build/offline-20261024/parallel-1031-20261027-a/integration").resolve()
    if not work.is_dir() or not work.is_relative_to(approved) or any(work.iterdir()):
        parser.error("existing empty integration directory required")
    before={n:sha(ROOT/n) for n in NAMES}
    record=dict(Passed=False,HardwareAccessed=False,PDSAccessed=False,CoreIsProxy=True,
                MaximumSeconds=120,MaximumSystemCycles=200000,Dimensions=[32,16],
                SourceSHA256=before,Commands=[],StartedUtc=datetime.now(timezone.utc).isoformat())
    deadline=time.monotonic()+120;bin_dir=Path("E:/Vivado/Vivado/2017.4/bin")
    try:
        stages=(("xvlog.bat",["--sv",*[str(ROOT/n) for n in NAMES if n.endswith((".v",".sv"))]],"compile"),
                ("xelab.bat",["tb_hdmi1080_input_write_link","-s","hdmi1080_write_link"],"elaborate"),
                ("xsim.bat",["hdmi1080_write_link","-runall","-log","simulation.log"],"simulate"))
        for exe,arguments,stage in stages:
            entry=dict(Stage=stage,NativeArgv=[str(bin_dir/exe),*arguments],ReturnCode=None)
            record["Commands"].append(entry)
            try:
                tool(bin_dir,exe,arguments,work,deadline,stage);entry["ReturnCode"]=0
            except Exception as exc:
                match=re.search(r"failed, exit=(-?\d+)",str(exc))
                if match:entry["ReturnCode"]=int(match.group(1))
                raise
        log=(work/"simulation.log").read_text(encoding="utf-8",errors="replace")
        if "PASS hdmi1080 input write link:" not in log or re.search(r"(?im)^\s*(fatal|error):",log):
            raise ValueError("small-link completion absent or RTL error/fatal")
        record.update(Passed=True,PassLines=[s for s in log.splitlines() if s.startswith(("PASS","INPUT_LINK_COVERAGE"))])
    except (Exception,KeyboardInterrupt) as exc:
        record["Error"]=type(exc).__name__+": "+str(exc)
    finally:
        record["SourceSHA256After"]={n:sha(ROOT/n) for n in NAMES}
        if before!=record["SourceSHA256After"]:record.update(Passed=False,SourceDrift=True)
        record["LogSHA256"]={p.name:sha(p) for p in work.glob("*.log")}
        record["EndedUtc"]=datetime.now(timezone.utc).isoformat()
        with (work/"input-write-link-result.json").open("x",encoding="utf-8") as out:
            json.dump(record,out,indent=2);out.write("\n")
    print(json.dumps(record,indent=2))
    return 0 if record["Passed"] else 1


if __name__=="__main__":
    raise SystemExit(main())
