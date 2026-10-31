"""Prepare an isolated ready-at-start/trained-polarity HDMI source candidate.

No EDA, timing exceptions, bitstream generation or hardware operation occurs.
Old observer evidence remains bound to the old target and is not reused as STA.
"""
from pathlib import Path
import argparse
import json
import re

import prepare_hdmi_input_diagnostic as cdc

ROOT = cdc.ROOT
TARGET = "hdmi_uart_trained_diag"
REPLACEMENTS = {
    "board/hdmi_uart_input_diag.v": "board/hdmi_uart_trained_diag.v",
    "rtl/experimental/ms72xx_observed_ctl.v": "rtl/experimental/ms72xx_ready_observed_ctl.v",
    "rtl/experimental/ms7200_1080p30_ctl.v": "rtl/experimental/ms7200_1080p30_ready_ctl.v",
    "rtl/experimental/hdmi1080_input_status_cdc.v": "rtl/experimental/hdmi1080_input_status_trained.v",
}


def prepare(work):
    work = Path(work).resolve()
    if not work.name.startswith("trained-pds-"):
        raise ValueError("fresh trained-pds-* work directory required")
    for source in REPLACEMENTS.values():
        if not (ROOT / source).is_file():
            raise ValueError("isolated candidate source missing: " + source)
    # Check that the candidate still declares exactly the audited source-level
    # synchronizer families. Physical preservation/mapping needs a new audit.
    trained = (ROOT / REPLACEMENTS[cdc.SYNCHRONIZER_SOURCES["input_status"]]).read_text(encoding="utf-8")
    declarations = {}
    for match in re.finditer(r'\(\*(.*?)\*\)\s*reg\s*\[(\d+):0\]\s*([^;]+);', trained, re.S):
        if not re.search(r'\bsyn_preserve\s*=\s*1\b', match[1]):
            continue
        for item in match[3].split(","):
            name = item.split("=", 1)[0].strip()
            if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name) or name in declarations:
                raise ValueError("ambiguous trained synchronizer declaration")
            declarations[name] = int(match[2]) + 1
    if declarations != dict(cdc.SYNCHRONIZER_REGISTERS["input_status"]):
        raise ValueError("trained candidate synchronizer whitelist changed")
    plan = cdc.prepare(work)
    script = (work / "build.tcl").read_text(encoding="utf-8")
    for old, new in REPLACEMENTS.items():
        before = (ROOT / old).as_posix()
        if script.count(before) != 1:
            raise ValueError("candidate source anchor changed: " + old)
        script = script.replace(before, (ROOT / new).as_posix())
        del plan["InputSHA256"][old]
        plan["InputSHA256"][new] = cdc.original.sha(ROOT / new)
    script = script.replace("compile -top_module " + cdc.TOP, "compile -top_module " + TARGET)
    # Compile frozen copies; bind both live source and copied source bytes.
    copies = {}
    for source in re.findall(r"(?m)^add_design \{([^{}]+)\}$", script):
        source = Path(source)
        name = source.relative_to(ROOT).as_posix()
        destination = work / "frozen-inputs" / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(source.read_bytes())
        script = script.replace(source.as_posix(), destination.as_posix())
        copies[destination.relative_to(work).as_posix()] = cdc.original.sha(destination)
    if len(copies) != 12:
        raise ValueError("twelve independent diagnostic source copies required")
    (work / "build.tcl").write_text(script, encoding="utf-8", newline="\n")
    plan.update(Schema="hdmi-trained-diagnostic-build-v1", Target=TARGET,
                CandidateChanges=["complete successful first ready poll admission", "two complete stable DE lines before polarity lock"],
                FrozenInputSHA256=copies, FrozenSourceCount=len(copies),
                PDSExecuted=False, NativeMappingVerified=False, NativeSTAVerified=False,
                ExistingObserverADFOrBitstreamReused=False,
                Limits="Source preparation only. This target requires its own PDS build, mapped CDC/pin checks, exact scoped timing audit and bound bitstream; old observer STA or physical exceptions do not authorize this candidate.")
    plan["Command"][-1] = TARGET
    plan["InputSHA256"]["tools/prepare_hdmi_trained_diagnostic.py"] = cdc.original.sha(__file__)
    plan["TclSHA256"] = cdc.original.sha(work / "build.tcl")
    (work / "build-plan.json").write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
    return plan


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workdir", type=Path, required=True)
    args = parser.parse_args()
    result = prepare(args.workdir)
    print(json.dumps(dict(PreparedOnly=True, Target=TARGET, SourceCount=result["FrozenSourceCount"],
                          HardwareAccessed=False, BitstreamRequested=False)))
