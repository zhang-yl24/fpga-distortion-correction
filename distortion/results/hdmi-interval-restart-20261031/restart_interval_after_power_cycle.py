"""Fresh one-attempt V3 SRAM plan after user-reported board power loss."""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import sys

VIS=Path(__file__).resolve().parent
EXECUTOR=VIS/"program_interval.py"
EXECUTOR_SHA256="0c2c42913aca6f0ebaa51671a1a1953d5d9ee30700cbcea7e8ea0c7e8cee5f20"
if hashlib.sha256(EXECUTOR.read_bytes()).hexdigest()!=EXECUTOR_SHA256:
    raise ValueError("frozen V3 executor changed")
spec=importlib.util.spec_from_file_location("interval_power_cycle_executor",EXECUTOR)
program=importlib.util.module_from_spec(spec)
spec.loader.exec_module(program)
program.WORK=program.ROOT/"build/offline-20261024/hdmi-interval-program-1030-b"

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute",action="store_true")
    args=parser.parse_args()
    if not (program.WORK/"plan.json").exists():
        program.prepare()
    plan=program.validate()
    if not args.execute:
        print(json.dumps(dict(ValidationPassed=True,Target=plan["Target"],
            BoundInputCount=len(plan["Validation"]["BoundInputSHA256"]),
            WorkDirectory=str(program.WORK),Bitstream=plan["Validation"]["Bitstream"],
            Operation=plan["Operation"],HardwareAccessed=False,FlashWritten=False)))
        return 0
    result=program.execute(90)
    print(json.dumps({key:result.get(key) for key in ("Target","Passed","ExpectedDeviceAndIDConfirmed", "ProgrammingAttempted","DoneConfirmed","FlashWritten","CleanupErrors","Error")}),flush=True)
    if not result["Passed"]:
        return 1
    sys.path.insert(0,str(program.ROOT/"tools"))
    import hdmi_status
    output=program.ROOT/"results/hdmi-interval-live-20261030/live-status-b-after-power-cycle.json"
    capture=hdmi_status.capture(output,port="COM7",seconds=10)
    first=capture["frames"][0] if capture["frames"] else None
    last=capture["frames"][-1] if capture["frames"] else None
    keys=("sequence","flags","cfg_error","input_fault","width","height","pclk_edges","good_frames","bad_frames","vs_edge_count_ref","monitor_freshness_mask")
    print(json.dumps(dict(CapturePassed=capture["passed"],Packets=capture["accepted_packets"],Rejected=capture["rejected_packets"],
        First={k:first[k] for k in keys} if first else None,
        Last={k:last[k] for k in keys} if last else None,Error=capture.get("error"),Output=str(output))))
    return 0 if capture["passed"] else 1

if __name__=="__main__":raise SystemExit(main())
