"""Validate, or explicitly execute, one bound HDMI observer SRAM plan.

Default operation is read-only validation. --execute performs a device scan,
checks the expected ID, configures volatile SRAM once and confirms DONE.
Only this invocation's JTAG processes are stopped; no Flash command exists.
"""
from datetime import datetime, timezone
from pathlib import Path
import argparse
import json
import math

import prepare_hdmi_input_program as program

hw = program.hw
require = program.require


def validate(plan_path):
    path = Path(plan_path).resolve()
    before = hw.sha(path)
    work = path.parent
    require(path.name == "plan.json" and work.parent == program.APPROVED.resolve() and
            work.name.startswith("hdmi-input-program-"), "fixed observer plan directory required")
    plan = json.loads(path.read_text(encoding="utf-8-sig"))
    for name, wanted in (("Schema", "hdmi-input-sram-plan-v1"), ("Target", program.TARGET),
                         ("Operation", "volatile_sram_only"), ("ExpectedDevice", hw.DEVICE),
                         ("ExpectedDeviceID", hw.DEVICE_ID), ("CableIndex", 0), ("ServerPort", hw.PORT)):
        require(type(plan.get(name)) is type(wanted) and plan[name] == wanted,
                "observer plan identity differs: " + name)
    require(Path(plan["WorkDirectory"]).resolve() == work, "plan work directory differs")
    require(plan["Frequency"] in hw.FREQUENCIES, "unsupported JTAG frequency")
    for name in ("HardwareAccessed", "Executed", "ProgrammingAttempted", "DoneConfirmed", "FlashWritten"):
        require(plan.get(name) is False, "prepared plan must remain unexecuted: " + name)
    bit_work = Path(plan["BitstreamWorkDirectory"]).resolve()
    verified = program.verification.verify(bit_work)
    require(verified["Passed"] is True and verified["Target"] == program.TARGET and
            verified["FinalADFSHA256"] == program.bit_export.ADF_SHA256,
            "observer bitstream verification failed")
    require(verified["Bitstream"] == plan["Bitstream"], "verified bitstream differs from plan")
    require(plan["FinalADFSHA256"] == program.bit_export.ADF_SHA256, "plan ADF differs")
    bindings = program.bound_inputs(bit_work, verified)
    bit = Path(verified["Bitstream"]["Path"]).resolve()
    bindings[str(bit)] = verified["Bitstream"]["SHA256"]
    require(bindings == plan["BoundInputSHA256"], "plan source or evidence binding differs")
    require(all(hw.sha(name) == wanted for name, wanted in bindings.items()), "bound input changed")
    require(set(plan["Tcl"]) == {"scan", "program"}, "exact scan and program scripts required")
    for stage, text in hw._scripts({"bitstream_path": str(bit)}, plan["Frequency"]).items():
        entry = plan["Tcl"][stage]
        script = Path(entry["Path"]).resolve()
        require(script == work / (stage + ".tcl") and hw.sha(script) == entry["SHA256"] and
                script.read_text(encoding="utf-8") == text, "fixed SRAM-only Tcl changed: " + stage)
    hw.resolve_pds_bin(plan["PDSBin"])
    require(hw.sha(path) == before, "plan changed during validation")
    return plan


def execute(plan_path, *, timeout_seconds=90.0):
    require(type(timeout_seconds) in (int, float) and math.isfinite(timeout_seconds) and
            0 < timeout_seconds <= 300, "timeout must be finite and in (0, 300]")
    path = Path(plan_path).resolve()
    plan = validate(path)
    work = path.parent
    require(not (work / "receipt.json").exists() and not list(work.glob("*.log")),
            "plan has prior execution outputs; prepare a fresh plan")
    plan_sha, executor_sha = hw.sha(path), hw.sha(__file__)
    adapter = dict(workdir=str(work), pds_bin=plan["PDSBin"], frequency=plan["Frequency"],
                   tcl={stage: dict(path=entry["Path"], sha256=entry["SHA256"])
                        for stage, entry in plan["Tcl"].items()})
    result = dict(Schema="hdmi-input-sram-execution-v1", Target=program.TARGET,
                  StartedUTC=datetime.now(timezone.utc).isoformat(), PlanSHA256=plan_sha,
                  ExecutorSHA256=executor_sha, WorkDirectory=str(work),
                  Bitstream=plan["Bitstream"], FinalADFSHA256=plan["FinalADFSHA256"],
                  Passed=False, Executed=True, HardwareAccessed=False, ProgrammingAttempted=False,
                  DoneConfirmed=False, FlashWritten=False, HardwareReleaseAllowed=False,
                  ServerRestartedAfterScan=False,
                  Limits="This SRAM configuration event and DONE only; no input pixels, DDR, distortion, physical CDC/AC, thermal or stability acceptance.")
    owned = []

    def recheck():
        require(hw.sha(path) == plan_sha and hw.sha(__file__) == executor_sha,
                "plan or executor changed during execution")
        require(validate(path) == plan, "bound plan changed during execution")

    try:
        require(not hw.listening_pids(hw.PORT), "JTAG server port is occupied; no process started or stopped")
        pds = Path(plan["PDSBin"])
        server = hw._start_owned([str(pds / "cdt_js.exe"), "-port", str(hw.PORT),
                                  "-work_dir", str(work)], work, owned, "server")
        result["HardwareAccessed"] = True
        hw._await_owned_server(server)
        hw._owned_server_check(server)
        hw._check_scan(hw._client(adapter, "scan", owned, timeout_seconds))
        recheck()
        scanned = server
        server = hw._program_server_after_scan(server, adapter, owned)
        result["ServerRestartedAfterScan"] = server is not scanned
        hw._owned_server_check(server)
        recheck()
        result["ProgrammingAttempted"] = True
        hw._check_program(hw._client(adapter, "program", owned, timeout_seconds))
        result["DoneConfirmed"] = True
        recheck()
        result["Passed"] = True
    except Exception as error:
        result["Error"] = type(error).__name__ + ": " + str(error)
    finally:
        result["OwnedPIDs"] = [process.pid for process in owned]
        stopped, errors = hw._stop_owned(owned)
        result["TerminatedOwnedPIDs"], result["CleanupErrors"] = stopped, errors
        if errors:
            result["Passed"] = False
        result["Logs"] = {source.name: hw.sha(source) for source in sorted(work.glob("*.log")) if source.is_file()}
        result["EndedUTC"] = datetime.now(timezone.utc).isoformat()
        hw._new_json(work / "receipt.json", result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=float, default=90.0)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.execute:
            result = execute(args.plan, timeout_seconds=args.timeout_seconds)
            print(json.dumps(result, indent=2, allow_nan=False))
            return 0 if result["Passed"] else 1
        plan = validate(args.plan)
        print(json.dumps(dict(ValidationPassed=True, Target=plan["Target"], HardwareAccessed=False,
                              BitstreamSHA256=plan["Bitstream"]["SHA256"])))
        return 0
    except (ValueError, OSError, KeyError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    raise SystemExit(main())
