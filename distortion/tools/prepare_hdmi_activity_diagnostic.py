"""Prepare an isolated HDMI observer candidate that exposes monitor freshness."""
from pathlib import Path
import argparse
import json

import prepare_hdmi_trained_diagnostic as trained

ROOT = trained.ROOT
TARGET = "hdmi_uart_activity_diag"
REPLACEMENTS = {
    "board/hdmi_uart_trained_diag.v": "board/hdmi_uart_activity_diag.v",
    "rtl/experimental/hdmi1080_input_status_trained.v":
        "rtl/experimental/hdmi1080_input_status_activity_trained.v",
    "rtl/experimental/hdmi_diag_uart.v": "rtl/experimental/hdmi_diag_uart_v2.v",
}


def prepare(work):
    work = Path(work).resolve()
    if not work.name.startswith("trained-pds-"):
        raise ValueError("fresh trained-pds-* work directory required")
    plan = trained.prepare(work)
    script = (work / "build.tcl").read_text(encoding="utf-8")
    frozen = dict(plan["FrozenInputSHA256"])
    for old, new in REPLACEMENTS.items():
        old_path, new_path = ROOT / old, ROOT / new
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
        frozen[new_rel] = trained.cdc.original.sha(destination)
        del plan["InputSHA256"][old]
        plan["InputSHA256"][new] = trained.cdc.original.sha(new_path)
    if len(frozen) != 12:
        raise ValueError("twelve frozen PDS inputs required")
    script = script.replace("compile -top_module " + trained.TARGET,
                            "compile -top_module " + TARGET)
    (work / "build.tcl").write_text(script, encoding="utf-8", newline="\n")
    plan.update(Schema="hdmi-activity-diagnostic-build-v1", Target=TARGET,
                CandidateChanges=["expose existing PCLK/VS/DE/frame/snapshot freshness to version 2 UART packets"],
                FrozenInputSHA256=frozen, FrozenSourceCount=len(frozen),
                PDSExecuted=False, NativeMappingVerified=False, NativeSTAVerified=False,
                ExistingObserverADFOrBitstreamReused=False,
                Limits="Source preparation only. Requires its own PDS build, mapped CDC/pin checks, exact scoped timing audit and bound SRAM bitstream. Freshness reports activity within existing observer windows; it is not a PHY-lock or pixel-payload measurement.")
    plan["Command"][-1] = TARGET
    plan["InputSHA256"]["tools/prepare_hdmi_activity_diagnostic.py"] = trained.cdc.original.sha(__file__)
    plan["TclSHA256"] = trained.cdc.original.sha(work / "build.tcl")
    (work / "build-plan.json").write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
    return plan


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workdir", type=Path, required=True)
    args = parser.parse_args()
    result = prepare(args.workdir)
    print(json.dumps(dict(PreparedOnly=True, Target=TARGET, SourceCount=result["FrozenSourceCount"],
                          HardwareAccessed=False, BitstreamRequested=False)))
