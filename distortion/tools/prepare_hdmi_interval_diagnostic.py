"""Prepare a separate diagnostic exposing the existing synchronized VS count."""
from pathlib import Path
import argparse
import json

import prepare_hdmi_activity_diagnostic as activity

ROOT = activity.ROOT
TARGET = "hdmi_uart_interval_diag"
REPLACEMENTS = {
    "board/hdmi_uart_activity_diag.v": "board/hdmi_uart_interval_diag.v",
    "rtl/experimental/hdmi1080_input_status_activity_trained.v":
        "rtl/experimental/hdmi1080_input_status_interval_trained.v",
    "rtl/experimental/hdmi_diag_uart_v2.v": "rtl/experimental/hdmi_diag_uart_v3.v",
    "rtl/experimental/dvp_mode_admission_monitor_cdc.v":
        "rtl/experimental/dvp_mode_admission_monitor_activity_cdc.v",
}


def prepare(work):
    work = Path(work).resolve()
    plan = activity.prepare(work)
    script = (work / "build.tcl").read_text(encoding="utf-8")
    frozen = dict(plan["FrozenInputSHA256"])
    for old, new in REPLACEMENTS.items():
        new_path = ROOT / new
        if not new_path.is_file():
            raise ValueError("isolated candidate source missing: " + new)
        old_rel, new_rel = "frozen-inputs/" + old, "frozen-inputs/" + new
        old_abs, new_abs = (work / old_rel).as_posix(), (work / new_rel).as_posix()
        if script.count(old_abs) != 1 or old_rel not in frozen:
            raise ValueError("frozen source anchor changed: " + old)
        destination = work / new_rel
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(new_path.read_bytes())
        script = script.replace(old_abs, new_abs)
        del frozen[old_rel]
        frozen[new_rel] = activity.trained.cdc.original.sha(destination)
        del plan["InputSHA256"][old]
        plan["InputSHA256"][new] = activity.trained.cdc.original.sha(new_path)
    if len(frozen) != 12:
        raise ValueError("twelve frozen PDS inputs required")
    script = script.replace("compile -top_module " + activity.TARGET,
                            "compile -top_module " + TARGET)
    (work / "build.tcl").write_text(script, encoding="utf-8", newline="\n")
    plan.update(Schema="hdmi-interval-diagnostic-build-v1", Target=TARGET,
                CandidateChanges=["expose already synchronized 16-bit VS rising-edge count in UART V3 bytes 53:54"],
                FrozenInputSHA256=frozen, FrozenSourceCount=len(frozen),
                PDSExecuted=False, NativeMappingVerified=False, NativeSTAVerified=False,
                ExistingObserverADFOrBitstreamReused=False,
                Limits="Source preparation only. Requires own PDS, mapped CDC/pins, scoped timing and bound SRAM bitstream. VS count is normalized after polarity training and wraps at 65536; not PHY lock or pixel proof.")
    plan["Command"][-1] = TARGET
    plan["InputSHA256"]["tools/prepare_hdmi_interval_diagnostic.py"] = activity.trained.cdc.original.sha(__file__)
    plan["TclSHA256"] = activity.trained.cdc.original.sha(work / "build.tcl")
    (work / "build-plan.json").write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
    return plan


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workdir", type=Path, required=True)
    args = parser.parse_args()
    result = prepare(args.workdir)
    print(json.dumps(dict(PreparedOnly=True, Target=TARGET, SourceCount=result["FrozenSourceCount"],
                          HardwareAccessed=False, BitstreamRequested=False)))
