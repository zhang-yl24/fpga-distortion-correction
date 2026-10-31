"""Prepare/validate one fixed trained-observer SRAM plan; --execute is explicit.

No PDS build, UART, Flash or alternative target operation is implemented.
Execution owns its JTAG server and never repeats an already claimed plan.
"""
from datetime import datetime, timezone
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import math
import re
import sys

ROOT = Path(r"D:\GravityLRT\thu\semester_4.5\FPGAchina\fpga-distortion-correction\distortion")
VIS = Path(__file__).resolve().parent
SOURCE = ROOT / "build/hdmi-uart-diagnostic/trained-pds-1030-a"
BIT_WORK = ROOT / "build/hdmi-uart-diagnostic/trained-bit-1030-a"
WORK = ROOT / "build/offline-20261024/hdmi-trained-program-1030-a"
TARGET = "hdmi_uart_trained_diag"
BIT = BIT_WORK / "generate_bitstream" / (TARGET + ".sbit")
EXPORTER = VIS / "run_trained_bitstream.py"
SOURCE_PLAN_SHA256 = "e36869cee3dea1e8c94010fa0e0e9b0e0fd8eedc8b86aa01333f709308cadaa5"
SOURCE_EXECUTION_SHA256 = "9ebdbf3faa980d75ab986696f81b606c728fd31b82cd3afdea3b175139c5ed62"
# Root fills these only from the completed exact new export, then freezes this
# script before preparing its plan. PENDING always fails before hardware.
BIT_SHA256 = "174324853d6e294c6e2aa5a03af72a0195d063b3f7ce8460abfa6dd024919d81"
ADF_SHA256 = "88a6d04e25fa6de3d280d1458a06ef2ded506f1b6768476ae94dc7ce45fab399"
EXPORTER_SHA256 = "5443a7df43ca6607ad400a646b96f3497bde15813cb9a6e89d4bf26bf11ce77e"
SCOPE_REVIEW_SHA256 = "f8f96e8dd74ed88af5e7d0b113f2eabaf1d358066011dd760ea1edf70f6995ea"
FINAL_DIRECT = ROOT / "build/hdmi-uart-diagnostic/trained-review-1030-a/final-functional-export/connectivity-review.json"
FINAL_DIRECT_SHA256 = "45647ea89e143fd4cce28865be20fd7f336a331029625a7427f8c7028d843b61"
FREQUENCY = "1MHz"
sys.path.insert(0, str(ROOT / "tools"))
import program_native_raw as hw


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(value, message):
    if not value:
        raise ValueError(message)


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def save(path, result):
    with Path(path).open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(result, indent=2, allow_nan=False) + "\n")


def inside(base, name):
    base = Path(base).resolve()
    path = (base / name).resolve()
    require(path.is_relative_to(base), "bound path escapes root")
    return path


def exporter():
    for name, value in (("bitstream", BIT_SHA256), ("ADF", ADF_SHA256),
                        ("exporter", EXPORTER_SHA256), ("scope review", SCOPE_REVIEW_SHA256)):
        require(re.fullmatch(r"[0-9a-f]{64}", value) is not None, "fixed " + name + " hash is not frozen")
    require(sha(EXPORTER) == EXPORTER_SHA256, "fixed export runner changed")
    spec = importlib.util.spec_from_file_location("trained_exact_export", EXPORTER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    require(module.TARGET == TARGET and module.WORK.resolve() == BIT_WORK.resolve() and
            module.ADF_SHA256 == ADF_SHA256 and module.SCOPE_REVIEW_SHA256 == SCOPE_REVIEW_SHA256,
            "fixed exporter identity differs")
    return module


def verify_export():
    module = exporter()
    require(sha(SOURCE / "build-plan.json") == SOURCE_PLAN_SHA256 and
            sha(SOURCE / "execution.json") == SOURCE_EXECUTION_SHA256, "source build identity changed")
    build = read_json(SOURCE / "build-plan.json")
    execution = read_json(SOURCE / "execution.json")
    require(build["Target"] == TARGET and build["FrozenSourceCount"] == 12 and len(build["Pins"]) == 46 and
            execution["Target"] == TARGET and execution["Passed"] is True and type(execution["ReturnCode"]) is int and
            execution["ReturnCode"] == 0 and execution["SourceDrift"] == [] and execution["PlanUnchanged"] is True,
            "source build did not pass its exact bindings")
    bindings = {str(inside(ROOT, name)): wanted for name, wanted in build["InputSHA256"].items()}
    bindings.update({str(inside(SOURCE, name)): wanted for name, wanted in build["FrozenInputSHA256"].items()})
    require(len(build["InputSHA256"]) == 16 and len(build["FrozenInputSHA256"]) == 12,
            "source closure count differs")
    for name, wanted in execution["LogSHA256"].items():
        bindings[str(inside(SOURCE, name))] = wanted
    plan = read_json(BIT_WORK / "export-plan.json")
    module.verify_inputs(plan)
    require(plan["Target"] == TARGET and plan["ADF_SHA256"] == ADF_SHA256 and
            Path(plan["WorkDirectory"]).resolve() == BIT_WORK.resolve(), "export plan identity differs")
    for name, wanted in plan["InputSHA256"].items():
        path = Path(name).resolve()
        require(str(path) not in bindings or bindings[str(path)] == wanted, "conflicting export source binding")
        bindings[str(path)] = wanted
    result = read_json(BIT_WORK / "export-result.json")
    require(result["Target"] == TARGET and result["Passed"] is True and type(result["ReturnCode"]) is int and
            result["ReturnCode"] == 0 and result["ADF_SHA256"] == ADF_SHA256 and
            result["Command"] == plan["Command"] and result["HardwareAccessed"] is False and
            result["FlashWritten"] is False and not result.get("Error"), "export did not pass")
    expected_events = ['Process "Report Timing" started.', 'Process "Report Timing" done.',
                       "TRAINED_PRE_BIT_PASS " + ADF_SHA256, 'Process "Generate Bitstream" started.',
                       'Process "Generate Bitstream" done.', 'TRAINED_BITSTREAM_COMPLETE']
    text = (BIT_WORK / "native-stdout.log").read_text(encoding="utf-8", errors="replace")
    events = [line for line in text.splitlines() if line.startswith("Process ") or line.startswith("TRAINED_")]
    require(events == expected_events and result["ActualEvents"] == events, "actual export order differs")
    require(not re.search(r"(?im)^\s*(?:[EF]:|ERROR\b|FATAL\b|Traceback\b)", text) and
            not (BIT_WORK / "native-stderr.log").read_bytes().strip(), "native export emitted an error")
    commands = list(re.finditer(r"(?m)^Executing : gen_bit_stream ([^\r\n]+)$", text))
    commands = [item for item in commands if not item[1].endswith(" successfully.")]
    require(len(commands) == 1 and text.index(expected_events[2]) < commands[0].start() < text.index(expected_events[3]),
            "bit command must execute after the native gate and before actual generation")
    command = commands[0][1]
    actual_adf = re.findall(r"-input_db_file\s+(?:\{([^{}]+)\}|(\S+))", command)
    require(len(actual_adf) == 1 and Path(actual_adf[0][0] or actual_adf[0][1]).resolve() == BIT_WORK / "audited-final.adf" and
            "-scbv {High Voltage}" in command and "-unused_io_status UNUSED" in command,
            "fixed SRAM bit export arguments differ")
    report = BIT_WORK / "report_timing" / (TARGET + ".rtr")
    exceptions = BIT_WORK / "report_timing" / (TARGET + "_exception.rtr")
    native = module.native.compare(module.SCOPED_REPORT, module.SCOPED_EXCEPTIONS, report, exceptions)
    audit = read_json(BIT_WORK / "pre-bit-audit.json")
    require(audit["Passed"] is True and audit["NativeAudit"] == native and audit["ADF_SHA256"] == ADF_SHA256 and
            audit["InputSHA256"] == plan["InputSHA256"] and audit["ReportSHA256"] == sha(report) and
            audit["ExceptionSHA256"] == sha(exceptions) and audit["HardwareAccessed"] is False,
            "runtime pre-bit audit binding differs")
    require(sha(module.SCOPE_REVIEW) == SCOPE_REVIEW_SHA256, "fixed scoped review changed")
    bit = result["Bitstream"]
    require(Path(bit["Path"]).resolve() == BIT and bit["SHA256"] == BIT_SHA256 and
            type(bit["Bytes"]) is int and bit["Bytes"] == 3_791_112 and BIT.stat().st_size == bit["Bytes"] and
            sha(BIT) == BIT_SHA256 and bit["Header"]["Design"] == TARGET and
            bit["Header"]["Device"] == "Logos2-PG2L100H--6-FBG676", "fixed new bitstream identity differs")
    for name, wanted in result["EvidenceSHA256"].items():
        bindings[str(inside(BIT_WORK, name))] = wanted
    require(sha(FINAL_DIRECT) == FINAL_DIRECT_SHA256, "final scoped-ADF direct functional proof changed")
    proof = read_json(FINAL_DIRECT)
    require(proof["Schema"] == "trained-final-adf-functional-review-v1" and proof["AuditPassed"] is True and
            proof["Target"] == TARGET and proof["ScopedADFSHA256"] == ADF_SHA256 and
            proof["OriginalADFSHA256"] == "4a3c40ccd467c09038b8629f7d3158eba9399e01c2dc2c55876af6131a79715b" and
            proof["EntireFunctionalGraphUnchanged"] is True and proof["AllRegisterLocationsUnchanged"] is True and
            proof["Pins46AndDirectionsUnchanged"] is True and proof["NetlistTopPortsUnchanged"] is True and
            proof["VerifiedFFCount"] == 161 and proof["VerifiedStageLinks"] == 81 and
            proof["SameSiteStageLinks"] == 81 and proof["InputDrift"] == [] and
            proof["HardwareAccessed"] is False, "final scoped-ADF connectivity or pin review did not pass")
    for name, wanted in proof["EvidenceSHA256"].items():
        path = Path(name).resolve()
        require(path.is_absolute() and (str(path) not in bindings or bindings[str(path)] == wanted),
                "conflicting final direct proof binding")
        bindings[str(path)] = wanted
    bindings[str(FINAL_DIRECT.resolve())] = FINAL_DIRECT_SHA256
    for path in (SOURCE / "build-plan.json", SOURCE / "execution.json", BIT_WORK / "export-plan.json",
                 BIT_WORK / "pre-bit-audit.json", BIT_WORK / "export-result.json", module.SCOPE_REVIEW,
                 BIT_WORK / "audited-final.adf", BIT, EXPORTER, Path(__file__), ROOT / "tools/program_native_raw.py",
                 ROOT / "tools/native_camera_capture.py", ROOT / "tools/camera_eye_pin_audit.py",
                 ROOT / "tools/frame_protocol.py"):
        bindings[str(Path(path).resolve())] = sha(path)
    require(sha(BIT_WORK / "audited-final.adf") == ADF_SHA256, "bit input database changed")
    require(all(sha(name) == wanted for name, wanted in bindings.items()), "source or evidence changed")
    return dict(Target=TARGET, Bitstream=bit, ADF_SHA256=ADF_SHA256, NativeAudit=native,
                FinalDirectProofSHA256=FINAL_DIRECT_SHA256,
                BoundInputSHA256=bindings, PDSBin=str(hw.resolve_pds_bin(Path(build["Command"][0]).parent)))


def prepare():
    require(WORK.parent.resolve() == (ROOT / "build/offline-20261024").resolve(), "fixed work parent differs")
    require(not WORK.exists(), "program work directory already exists; default will validate an existing plan")
    validation = verify_export()
    scripts = hw._scripts({"bitstream_path": str(BIT)}, FREQUENCY)
    WORK.mkdir()
    for name, content in scripts.items():
        with (WORK / (name + ".tcl")).open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
    require(all(sha(name) == wanted for name, wanted in validation["BoundInputSHA256"].items()),
            "input changed during plan preparation")
    plan = dict(Schema="hdmi-trained-sram-plan-v1", Target=TARGET, WorkDirectory=str(WORK),
                PreparedUTC=datetime.now(timezone.utc).isoformat(), Frequency=FREQUENCY,
                Operation="volatile_sram_only", ExpectedDevice=hw.DEVICE, ExpectedDeviceID=hw.DEVICE_ID,
                Validation=validation, HardwareAccessed=False, Executed=False, DoneConfirmed=False,
                FlashWritten=False, HardwareReleaseAllowed=False,
                Tcl={name: dict(Path=str(WORK / (name + ".tcl")), SHA256=sha(WORK / (name + ".tcl"))) for name in scripts},
                Limits="Experimental trained HDMI diagnostic SRAM event only; no external AC, full CDC/MTBF, temperature, real pixel payload, DDR or distortion acceptance.")
    save(WORK / "plan.json", plan)
    return plan


def validate():
    plan = read_json(WORK / "plan.json")
    require(plan["Schema"] == "hdmi-trained-sram-plan-v1" and plan["Target"] == TARGET and
            Path(plan["WorkDirectory"]).resolve() == WORK.resolve() and plan["Frequency"] == FREQUENCY and
            plan["Operation"] == "volatile_sram_only" and plan["ExpectedDevice"] == hw.DEVICE and
            plan["ExpectedDeviceID"] == hw.DEVICE_ID and plan["HardwareAccessed"] is False and
            plan["Executed"] is False and plan["DoneConfirmed"] is False and plan["FlashWritten"] is False,
            "fixed plan identity differs")
    require(plan["Validation"] == verify_export(), "current export/source binding differs from prepared plan")
    require(set(plan["Tcl"]) == {"scan", "program"}, "only scan and program Tcl allowed")
    for name, content in hw._scripts({"bitstream_path": str(BIT)}, FREQUENCY).items():
        item = plan["Tcl"][name]
        path = Path(item["Path"]).resolve()
        require(path == WORK / (name + ".tcl") and sha(path) == item["SHA256"] and
                path.read_text(encoding="utf-8") == content, "SRAM-only Tcl changed")
    return plan


def execute(timeout_seconds=90.0):
    require(type(timeout_seconds) in (int, float) and math.isfinite(timeout_seconds) and
            80 <= timeout_seconds <= 120, "bounded programming timeout must be 80..120 seconds")
    plan = validate()
    require(not (WORK / "receipt.json").exists() and not (WORK / "execution-claim.json").exists() and
            not list(WORK.glob("*.log")), "this plan has previous execution outputs; no repeated hardware attempt")
    plan_sha, script_sha = sha(WORK / "plan.json"), sha(__file__)
    save(WORK / "execution-claim.json", dict(Target=TARGET, PlanSHA256=plan_sha,
         ClaimedUTC=datetime.now(timezone.utc).isoformat(), Reason="Exclusive one-attempt claim before any device access."))
    adapter = dict(workdir=str(WORK), pds_bin=plan["Validation"]["PDSBin"], frequency=FREQUENCY,
                   tcl={name: dict(path=item["Path"], sha256=item["SHA256"]) for name, item in plan["Tcl"].items()})
    result = dict(Schema="hdmi-trained-sram-execution-v1", Target=TARGET, PlanSHA256=plan_sha,
                  ExecutorSHA256=script_sha, StartedUTC=datetime.now(timezone.utc).isoformat(),
                  WorkDirectory=str(WORK), Bitstream=plan["Validation"]["Bitstream"],
                  ADF_SHA256=ADF_SHA256, Passed=False, Executed=True, HardwareAccessed=False,
                  ProgrammingAttempted=False, DoneConfirmed=False, FlashWritten=False,
                  ServerRestartedAfterScan=False, HardwareReleaseAllowed=False,
                  Limits="This one SRAM configuration event and fresh post-program DONE only. No physical input pixels, DDR, distortion, temperature, long-run or external AC/CDC acceptance.")
    owned = []
    def recheck():
        require(sha(WORK / "plan.json") == plan_sha and sha(__file__) == script_sha and validate() == plan,
                "plan, executor or bound export changed during execution")
    try:
        require(not hw.listening_pids(hw.PORT), "JTAG server port occupied; no foreign process may be used or stopped")
        pds = Path(adapter["pds_bin"])
        server = hw._start_owned([str(pds / "cdt_js.exe"), "-port", str(hw.PORT), "-work_dir", str(WORK)],
                                 WORK, owned, "server")
        result["HardwareAccessed"] = True
        hw._await_owned_server(server)
        hw._owned_server_check(server)
        hw._check_scan(hw._client(adapter, "scan", owned, timeout_seconds))
        result["ExpectedDeviceAndIDConfirmed"] = True
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
        result["Logs"] = {path.name: sha(path) for path in sorted(WORK.glob("*.log"))}
        result["EndedUTC"] = datetime.now(timezone.utc).isoformat()
        save(WORK / "receipt.json", result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--timeout-seconds", type=float, default=90.0)
    args = parser.parse_args(argv)
    try:
        if not (WORK / "plan.json").exists():
            prepare()
        result = execute(args.timeout_seconds) if args.execute else validate()
        print(json.dumps(result, indent=2, allow_nan=False))
        return 0 if not args.execute or result["Passed"] else 1
    except (ValueError, OSError, KeyError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    raise SystemExit(main())
