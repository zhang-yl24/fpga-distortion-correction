"""Prepare isolated readiness re-entry candidate with the existing UART V3."""
from pathlib import Path
import argparse
import json
import prepare_hdmi_interval_diagnostic as interval

ROOT=interval.ROOT
TARGET="hdmi_uart_rearm_diag"
REPLACEMENTS={
    "board/hdmi_uart_interval_diag.v":"board/hdmi_uart_rearm_diag.v",
    "rtl/experimental/ms72xx_ready_observed_ctl.v":"rtl/experimental/ms72xx_rearm_observed_ctl.v",
    "rtl/experimental/ms7200_1080p30_ready_ctl.v":"rtl/experimental/ms7200_1080p30_rearm_ctl.v",
}

def prepare(work):
    work=Path(work).resolve()
    plan=interval.prepare(work)
    script=(work/"build.tcl").read_text(encoding="utf-8")
    frozen=dict(plan["FrozenInputSHA256"])
    sha=interval.activity.trained.cdc.original.sha
    for old,new in REPLACEMENTS.items():
        oldrel,newrel="frozen-inputs/"+old,"frozen-inputs/"+new
        before,after=(work/oldrel).as_posix(),(work/newrel).as_posix()
        if script.count(before)!=1 or oldrel not in frozen:
            raise ValueError("source anchor changed: "+old)
        dest=work/newrel;dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_bytes((ROOT/new).read_bytes())
        script=script.replace(before,after)
        del frozen[oldrel];frozen[newrel]=sha(dest)
        del plan["InputSHA256"][old];plan["InputSHA256"][new]=sha(ROOT/new)
    script=script.replace("compile -top_module "+interval.TARGET,"compile -top_module "+TARGET)
    (work/"build.tcl").write_text(script,encoding="utf-8",newline="\n")
    plan.update(Schema="hdmi-rearm-diagnostic-build-v1",Target=TARGET,FrozenInputSHA256=frozen,
        CandidateChanges=["complete status poll entering ready02 from any non02 state executes unchanged receiver settings"],
        ExistingObserverADFOrBitstreamReused=False,PDSExecuted=False,NativeMappingVerified=False,NativeSTAVerified=False,
        Limits="Experimental readiness-entry policy. All register values, UART V3 and input observer remain the interval candidate's behavior; own native implementation and bitstream evidence are required. Not proof of physical lock or root cause.")
    plan["Command"][-1]=TARGET
    plan["InputSHA256"]["tools/prepare_hdmi_rearm_diagnostic.py"]=sha(__file__)
    plan["TclSHA256"]=sha(work/"build.tcl")
    assert len(frozen)==12 and len(plan["InputSHA256"])==19
    (work/"build-plan.json").write_text(json.dumps(plan,indent=2)+"\n",encoding="utf-8")
    return plan

if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workdir",type=Path,required=True)
    args=parser.parse_args()
    plan=prepare(args.workdir)
    print(json.dumps(dict(Target=TARGET,PreparedOnly=True,SourceCount=12,InputCount=19,HardwareAccessed=False)))
