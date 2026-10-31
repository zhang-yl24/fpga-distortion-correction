"""Prepare a source-bound HDMI observer SRAM plan without accessing hardware.

The output contains separate scan/program Tcl files for a later board session.
This tool has no execution mode; a plan does not confirm a device or DONE.
"""
from datetime import datetime, timezone
from pathlib import Path
import argparse
import json

import prepare_hdmi_input_bitstream as bit_export
import program_native_raw as hw
import verify_hdmi_input_bitstream as verification

ROOT = Path(__file__).resolve().parents[1]
APPROVED = ROOT / "build/offline-20261024"
TARGET = "hdmi_uart_input_diag"


def require(value, message):
    if not value:
        raise ValueError(message)


def bound_inputs(bit_work, verified):
    plan = json.loads((bit_work / "bitstream-plan.json").read_text(encoding="utf-8"))
    project = Path(plan["ProjectRoot"]).resolve()
    require(project == ROOT.resolve(), "bit export project root differs")
    require(Path(plan["WorkDirectory"]).resolve() == bit_work, "bit export work directory differs")
    bindings = {}
    for base, entries in ((project, plan["ProjectInputSHA256"]),
                          (bit_work, plan["WorkInputSHA256"]),
                          (bit_work, verified["EvidenceSHA256"])):
        for name, wanted in entries.items():
            path = bit_export.inside(base, name)
            require(hw.sha(path) == wanted, "verified input changed: " + str(path))
            key = str(path)
            require(key not in bindings or bindings[key] == wanted, "conflicting input binding")
            bindings[key] = wanted
    bindings[str(bit_work / "bitstream-plan.json")] = hw.sha(bit_work / "bitstream-plan.json")
    for name in ("tools/prepare_hdmi_input_program.py", "tools/verify_hdmi_input_bitstream.py",
                 "tools/program_native_raw.py"):
        path = ROOT / name
        bindings[str(path)] = hw.sha(path)
    return bindings


def prepare(bit_work, workdir, *, pds_bin=None, frequency="1MHz"):
    bit_work, work = Path(bit_work).resolve(), Path(workdir).resolve()
    require(work.parent == APPROVED.resolve() and work.name.startswith("hdmi-input-program-"),
            "new hdmi-input-program-* child of build/offline-20261024 required")
    require(work.parent.is_dir() and not work.exists(), "plan directory must be new in an existing parent")
    require(frequency in hw.FREQUENCIES, "unsupported JTAG frequency")
    verified = verification.verify(bit_work)
    require(verified.get("Schema") == "hdmi-input-bitstream-verification-v1" and
            verified.get("Passed") is True and verified.get("Target") == TARGET,
            "exact input-observer bitstream verification required")
    bit = bit_work / "generate_bitstream" / (TARGET + ".sbit")
    require(Path(verified["Bitstream"]["Path"]).resolve() == bit,
            "verified bitstream path differs")
    require(bit.stat().st_size == verified["Bitstream"]["Bytes"] and
            hw.sha(bit) == verified["Bitstream"]["SHA256"], "verified bitstream changed")
    require(verified["FinalADFSHA256"] == bit_export.ADF_SHA256, "verified final ADF differs")
    bindings = bound_inputs(bit_work, verified)
    bindings[str(bit)] = verified["Bitstream"]["SHA256"]
    pds = hw.resolve_pds_bin(pds_bin)
    scripts = hw._scripts({"bitstream_path": str(bit)}, frequency)
    work.mkdir()
    for stage, text in scripts.items():
        with (work / (stage + ".tcl")).open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
    # Recheck the closure after preparation; no device operation follows.
    require(all(hw.sha(path) == wanted for path, wanted in bindings.items()),
            "bound input changed during plan preparation")
    require(hw.sha(bit) == verified["Bitstream"]["SHA256"], "bitstream changed during preparation")
    result = {
        "Schema": "hdmi-input-sram-plan-v1", "Target": TARGET,
        "PreparedUTC": datetime.now(timezone.utc).isoformat(),
        "WorkDirectory": str(work), "BitstreamWorkDirectory": str(bit_work),
        "PDSBin": str(pds), "Frequency": frequency,
        "Operation": "volatile_sram_only", "ExpectedDevice": hw.DEVICE,
        "ExpectedDeviceID": hw.DEVICE_ID, "CableIndex": 0, "ServerPort": hw.PORT,
        "Bitstream": verified["Bitstream"], "FinalADFSHA256": verified["FinalADFSHA256"],
        "BoundInputSHA256": bindings, "OfflineVerification": verified,
        "Tcl": {stage: {"Path": str(work / (stage + ".tcl")),
                        "SHA256": hw.sha(work / (stage + ".tcl"))} for stage in scripts},
        "HardwareAccessed": False, "Executed": False, "ProgrammingAttempted": False,
        "DoneConfirmed": False, "FlashWritten": False, "ExecutionSupported": False,
        "InputObserverIncluded": True, "DDRIncluded": False, "CameraIncluded": False,
        "SharedPeripheralResetG25": True, "HardwareReleaseAllowed": False,
        "Limits": "Offline files and SRAM command plan only. Before any later program operation, reverify inputs and scan the expected device/ID with an owned JTAG server. This plan neither accesses hardware nor proves DONE, real input pixels, external AC, physical CDC, DDR, corrected display, temperature or long-run behavior.",
    }
    with (work / "plan.json").open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write("\n")
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bit-work", type=Path, required=True)
    parser.add_argument("--workdir", type=Path, required=True)
    parser.add_argument("--pds-bin", type=Path)
    parser.add_argument("--frequency", choices=hw.FREQUENCIES, default="1MHz")
    args = parser.parse_args(argv)
    try:
        result = prepare(args.bit_work, args.workdir, pds_bin=args.pds_bin, frequency=args.frequency)
    except (ValueError, OSError, KeyError) as error:
        parser.error(str(error))
    print(json.dumps({"Target": result["Target"], "WorkDirectory": result["WorkDirectory"],
                      "HardwareAccessed": False, "ExecutionSupported": False,
                      "BitstreamSHA256": result["Bitstream"]["SHA256"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
