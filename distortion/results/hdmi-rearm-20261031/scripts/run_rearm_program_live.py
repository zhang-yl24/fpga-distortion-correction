"""Validate or execute the frozen rearm SRAM plan and collect UART immediately."""
from pathlib import Path
import argparse
import importlib.util
import json
import sys

VIS=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location("rearm_exact_program",VIS/"program_rearm.py")
program=importlib.util.module_from_spec(spec);spec.loader.exec_module(program)

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("--execute",action="store_true")
    args=parser.parse_args()
    if not (program.WORK/"plan.json").exists():program.prepare()
    plan=program.validate()
    if not args.execute:
        print(json.dumps(dict(ValidationPassed=True,Target=plan["Target"],BoundInputCount=len(plan["Validation"]["BoundInputSHA256"]),
            Bitstream=plan["Validation"]["Bitstream"],Operation=plan["Operation"],HardwareAccessed=False)));return 0
    result=program.execute(90)
    print(json.dumps({key:result.get(key) for key in ("Passed","Target","DoneConfirmed","FlashWritten","CleanupErrors","Error")}),flush=True)
    if not result["Passed"]:return 1
    sys.path.insert(0,str(program.ROOT/"tools"));import hdmi_status
    live=program.ROOT/"results/hdmi-rearm-live-20261031";live.mkdir()
    capture=hdmi_status.capture(live/"live-status-a.json",port="COM7",seconds=10)
    keys=("sequence","flags","cfg_error","input_fault","width","height","pclk_edges","good_frames","bad_frames","vs_edge_count_ref","monitor_freshness_mask")
    print(json.dumps(dict(CapturePassed=capture["passed"],Packets=capture["accepted_packets"],Rejected=capture["rejected_packets"],
        First={k:capture["frames"][0][k] for k in keys} if capture["frames"] else None,
        Last={k:capture["frames"][-1][k] for k in keys} if capture["frames"] else None,Error=capture.get("error"))))
    return 0 if capture["passed"] else 1

if __name__=="__main__":raise SystemExit(main())
