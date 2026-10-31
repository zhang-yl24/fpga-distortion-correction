"""Export one exact scoped trained-observer database after a fresh STA gate."""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time

ROOT = Path(r"D:\GravityLRT\thu\semester_4.5\FPGAchina\fpga-distortion-correction\distortion")
VIS = Path(__file__).resolve().parent
SOURCE = ROOT / "build/hdmi-uart-diagnostic/trained-pds-1030-a"
WORK = ROOT / "build/hdmi-uart-diagnostic/trained-bit-1030-a"
REVIEW = ROOT / "build/hdmi-uart-diagnostic/trained-review-1030-a"
TARGET = "hdmi_uart_trained_diag"
# The new independent mapped/scoped review pins this exact database.
SCOPED_ADF = REVIEW / "scoped-cdc/input.adf"
SCOPED_REPORT = REVIEW / "scoped-cdc/hdmi_uart_trained_diag.rtr"
SCOPED_EXCEPTIONS = REVIEW / "scoped-cdc/hdmi_uart_trained_diag_exception.rtr"
ADF_SHA256 = "88a6d04e25fa6de3d280d1458a06ef2ded506f1b6768476ae94dc7ce45fab399"
SCOPE_REVIEW = REVIEW / "scoped-cdc/scoped-cdc-review.json"
SCOPE_REVIEW_SHA256 = "f8f96e8dd74ed88af5e7d0b113f2eabaf1d358066011dd760ea1edf70f6995ea"
HELPER_SHA256 = {
    "tools/audit_hdmi_trained_native.py": "b3b38a66a9589b6f9236822479024fc13173cf33dcb6e5a7d9dfacee30dae4ed",
    "tools/prepare_hdmi_input_bitstream.py": "3cd73238792d44cf4bef8b7930cb50983a05826b46a53dcb5d5ff21fe2743915",
    "tools/audit_ddr_final_timing.py": "f0275c5e5e8c6b08c1a8d8a88d5ab1b941459876ea5e3c30f4bea61f5f677a3c",
    "tools/prepare_ddr_native_recovery_constraints.py": "a50f1cbf6bc2f1173a52fe3d53286ea70b3dedd3e364a10c267f5a2a0cad8c0c",
    "tools/verify_hdmi_input_bitstream.py": "eecd3866907b4731cd5dfe4269d2c122dfa82c6b653cc0968b0a98206e11bce1",
}
sys.path.insert(0, str(ROOT / "tools"))
import audit_hdmi_trained_native as native


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(value, message):
    if not value:
        raise ValueError(message)


def save(path, value):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")


def literal(path):
    text = Path(path).resolve().as_posix()
    require(not any(c in text for c in "{}\r\n"), "unsafe Tcl path")
    return "{" + text + "}"


def verify_inputs(plan):
    require(plan["ADF_SHA256"] == ADF_SHA256 and sha(WORK / "audited-final.adf") == ADF_SHA256,
            "fixed scoped ADF changed")
    require(sha(SCOPE_REVIEW) == SCOPE_REVIEW_SHA256, "independent scope review changed")
    for name, wanted in plan["InputSHA256"].items():
        require(sha(name) == wanted, "bound input changed: " + name)
    require(Path(plan["WorkDirectory"]).resolve() == WORK.resolve() and plan["Target"] == TARGET,
            "bit export plan identity differs")
    expected = source_bindings()
    require(all(plan["InputSHA256"].get(name) == wanted for name, wanted in expected.items()),
            "runtime source/evidence closure differs from the independent review")
    for name, wanted in HELPER_SHA256.items():
        require(sha(ROOT / name) == wanted and plan["InputSHA256"].get(str(ROOT / name)) == wanted,
                "fixed audit helper changed: " + name)


def source_bindings():
    """Re-anchor the mutable export plan to the independently pinned review."""
    require(re.fullmatch(r"[0-9a-f]{64}", ADF_SHA256) and
            re.fullmatch(r"[0-9a-f]{64}", SCOPE_REVIEW_SHA256), "review constants are not finalized")
    require(sha(SCOPE_REVIEW) == SCOPE_REVIEW_SHA256, "independent scope review changed")
    review = json.loads(SCOPE_REVIEW.read_text(encoding="utf-8"))
    for key, wanted in dict(Schema="trained-input-scoped-cdc-review-v1", Target=TARGET,
                           AuditPassed=True, AllTenTimingTypesPassed=True,
                           SourceADFSHA256=sha(SOURCE / ("place_route/" + TARGET + "_pnr.adf")),
                           ScopedADFSHA256=ADF_SHA256, HardwareReleaseAllowed=False,
                           MaxDelayCountPerCorner={"slow":167,"fast":167},
                           FalsePathCountPerCorner={c:dict(setup=0,hold=167,recovery=4,removal=4) for c in ("slow","fast")}).items():
        require(type(review.get(key)) is type(wanted) and review[key] == wanted,
                "independent scope review field differs: " + key)
    evidence = review["EvidenceSHA256"]
    require(isinstance(evidence, dict) and evidence, "scope evidence closure missing")
    for path in (SOURCE / "build-plan.json", SOURCE / "execution.json",
                 SOURCE / ("place_route/" + TARGET + "_pnr.adf"),
                 SOURCE / ("place_route/" + TARGET + "_prr_route_optimize.prt"),
                 SCOPED_ADF, SCOPED_REPORT, SCOPED_EXCEPTIONS):
        require(evidence.get(str(path)) == sha(path), "required independent evidence binding missing: " + str(path))
    require(all(sha(path) == wanted for path, wanted in evidence.items()), "independent review evidence changed")
    build = json.loads((SOURCE / "build-plan.json").read_text(encoding="utf-8"))
    execution = json.loads((SOURCE / "execution.json").read_text(encoding="utf-8"))
    require(build["Target"] == TARGET and len(build["Pins"]) == 46 and
            execution.get("Passed") is True and type(execution.get("ReturnCode")) is int and
            execution["ReturnCode"] == 0 and execution["PlanSHA256"] == sha(SOURCE / "build-plan.json") and
            execution.get("SourceDrift") == [] and execution.get("PlanUnchanged") is True,
            "source build identity/execution differs")
    bindings = dict(evidence)
    bindings.update({str(ROOT / name):wanted for name,wanted in build["InputSHA256"].items()})
    bindings.update({str(SOURCE / name):wanted for name,wanted in build["FrozenInputSHA256"].items()})
    bindings[str(SOURCE / "build.tcl")] = build["TclSHA256"]
    bindings[str(SOURCE / "hdmi_uart_diag.fdc")] = build["FDCSHA256"]
    bindings.update({str(ROOT / name):wanted for name,wanted in HELPER_SHA256.items()})
    for name,wanted in execution["LogSHA256"].items():
        bindings[str(SOURCE / name)] = wanted
    for path in (SCOPE_REVIEW, Path(__file__), Path(build["Command"][0]),
                 ROOT.parent / ".venv/Scripts/python.exe"):
        bindings[str(path)] = sha(path)
    require(all(sha(name) == wanted for name,wanted in bindings.items()), "source drift before export")
    return bindings


def audit():
    plan = json.loads((WORK / "export-plan.json").read_text(encoding="utf-8"))
    verify_inputs(plan)
    result = native.compare(SCOPED_REPORT, SCOPED_EXCEPTIONS,
                            WORK / "report_timing" / (TARGET + ".rtr"),
                            WORK / "report_timing" / (TARGET + "_exception.rtr"))
    verify_inputs(plan)
    save(WORK / "pre-bit-audit.json", dict(Passed=True, NativeAudit=result, ADF_SHA256=ADF_SHA256,
        InputSHA256=plan["InputSHA256"], ReportSHA256=sha(WORK / "report_timing" / (TARGET + ".rtr")),
        ExceptionSHA256=sha(WORK / "report_timing" / (TARGET + "_exception.rtr")),
        CheckedUTC=datetime.now(timezone.utc).isoformat(), HardwareAccessed=False, HardwareReleaseAllowed=False))
    print("TRAINED_PRE_BIT_PASS " + ADF_SHA256)


def run():
    require(sha(SCOPED_ADF) == ADF_SHA256 and sha(SCOPE_REVIEW) == SCOPE_REVIEW_SHA256,
            "reviewed scoped database identity differs")
    native.compare(SCOPED_REPORT, SCOPED_EXCEPTIONS, SCOPED_REPORT, SCOPED_EXCEPTIONS)
    build = json.loads((SOURCE / "build-plan.json").read_text(encoding="utf-8"))
    require(build["Target"] == TARGET and len(build["Pins"]) == 46, "source target/pins differ")
    bindings = source_bindings()
    require(all(sha(name) == wanted for name, wanted in bindings.items()), "source drift before export")
    WORK.mkdir()
    shutil.copyfile(SCOPED_ADF, WORK / "audited-final.adf")
    prefix = (SOURCE / "build.tcl").read_text(encoding="utf-8").split("report_timing -force_to_run", 1)[0]
    tcl = prefix + "report_timing -force_to_run -input_db_file " + literal(WORK / "audited-final.adf") + " -delay_type min_max -max_path 1000 -nworst 1 -report_exception TRUE\n"
    tcl += "if {[info script] ne {}} {\n set checked [exec " + literal(ROOT.parent / ".venv/Scripts/python.exe") + " " + literal(__file__) + " --audit]\n puts $checked\n if {[string first {TRAINED_PRE_BIT_PASS " + ADF_SHA256 + "} $checked] < 0} {error {native gate did not pass}}\n gen_bit_stream -force_to_run -input_db_file " + literal(WORK / "audited-final.adf") + " -scbv {High Voltage} -unused_io_status UNUSED\n puts {TRAINED_BITSTREAM_COMPLETE}\n flush stdout\n}\n"
    (WORK / "export.tcl").write_text(tcl, encoding="utf-8", newline="\n")
    bindings[str(WORK / "export.tcl")] = sha(WORK / "export.tcl")
    command = [build["Command"][0], "-file", str(WORK / "export.tcl"), "-work_dir", str(WORK), "-project_name", TARGET]
    plan = dict(Target=TARGET, WorkDirectory=str(WORK), ADF_SHA256=ADF_SHA256,
                InputSHA256=bindings, Command=command, HardwareAccessed=False)
    save(WORK / "export-plan.json", plan)
    result = dict(Target=TARGET, StartedUTC=datetime.now(timezone.utc).isoformat(), Passed=False,
                  Command=command, ADF_SHA256=ADF_SHA256, HardwareAccessed=False, FlashWritten=False)
    started = time.monotonic()
    try:
        verify_inputs(plan)
        with (WORK / "native-stdout.log").open("xb") as out, (WORK / "native-stderr.log").open("xb") as err:
            process = subprocess.Popen(command, cwd=WORK, stdout=out, stderr=err,
                                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            result["OwnedPID"] = process.pid
            try:
                result["ReturnCode"] = process.wait(timeout=240)
            except subprocess.TimeoutExpired:
                stopped = subprocess.run([str(Path(os.environ["SystemRoot"]) / "System32/taskkill.exe"),
                                          "/PID", str(process.pid), "/T", "/F"], capture_output=True, timeout=15)
                (WORK / "owned-timeout-stop.log").write_bytes(stopped.stdout + stopped.stderr)
                result["ReturnCode"] = process.wait(timeout=15)
                raise TimeoutError("owned PDS export exceeded 240 seconds")
        require(result["ReturnCode"] == 0, "native export exit was not zero")
        verify_inputs(plan)
        text = (WORK / "native-stdout.log").read_text(encoding="utf-8", errors="replace")
        events = [line for line in text.splitlines() if line.startswith("Process ") or line.startswith("TRAINED_")]
        require(events == ['Process "Report Timing" started.', 'Process "Report Timing" done.',
                           "TRAINED_PRE_BIT_PASS " + ADF_SHA256, 'Process "Generate Bitstream" started.',
                           'Process "Generate Bitstream" done.', 'TRAINED_BITSTREAM_COMPLETE'], "actual export order differs")
        require(not re.search(r"(?im)^\s*(?:[EF]:|ERROR\b|FATAL\b)", text), "native error in export")
        require(not (WORK / "native-stderr.log").read_bytes().strip(), "native stderr not empty")
        # The native Process events alone do not identify the generated ADF.
        # Check the actual generation command and the native generation report.
        import verify_hdmi_input_bitstream as header
        commands = re.findall(r"(?m)^Executing\s*:\s*(gen_bit_stream\s+.+)$", text)
        commands = [cmd for cmd in commands if not cmd.endswith(" successfully.")]
        require(len(commands) == 1, "one actual generation command required")
        header.input_adf(commands[0], WORK)
        bgr = WORK / "generate_bitstream" / (TARGET + ".bgr")
        generation = bgr.read_text(encoding="utf-8", errors="replace")
        require("Generating Programming File done." in generation and
                not re.search(r"(?im)^\s*(?:[EF]:|ERROR\b|FATAL\b)", generation), "native generation report failed")
        commands = re.findall(r"(?m)^Flow Command:\s*(gen_bit_stream\s+.+)$", generation)
        require(len(commands) == 1, "native generation report command differs")
        header.input_adf(commands[0], WORK)
        checked = json.loads((WORK / "pre-bit-audit.json").read_text(encoding="utf-8"))
        fresh = native.compare(SCOPED_REPORT, SCOPED_EXCEPTIONS,
                               WORK / "report_timing" / (TARGET + ".rtr"),
                               WORK / "report_timing" / (TARGET + "_exception.rtr"))
        require(checked.get("Passed") is True and checked.get("NativeAudit") == fresh and
                checked.get("ADF_SHA256") == ADF_SHA256 and checked.get("InputSHA256") == plan["InputSHA256"] and
                checked.get("ReportSHA256") == sha(WORK / "report_timing" / (TARGET + ".rtr")) and
                checked.get("ExceptionSHA256") == sha(WORK / "report_timing" / (TARGET + "_exception.rtr")),
                "saved pre-bit gate differs from fresh native audit")
        audit_time = datetime.fromisoformat(checked["CheckedUTC"])
        require(datetime.fromisoformat(result["StartedUTC"]) <= audit_time <= datetime.now(timezone.utc),
                "pre-bit audit time outside this export execution")
        require((WORK / "generate_bitstream" / (TARGET + ".sbit")).stat().st_mtime >=
                (WORK / "pre-bit-audit.json").stat().st_mtime, "bitstream predates runtime audit")
        bit = WORK / "generate_bitstream" / (TARGET + ".sbit")
        require(bit.stat().st_size == 3_791_112, "unexpected bitstream length")
        # Parse all fixed header fields with the prior reader using only an
        # exact new-target substitution, without changing that reader's code.
        data = bit.read_bytes()
        old = TARGET.encode() + b"\0"
        new = header.prepare.TARGET.encode() + b"\0"
        encoded = b"a" + len(old).to_bytes(2, "big") + old
        replacement = b"a" + len(new).to_bytes(2, "big") + new
        require(data.count(encoded) == 1, "new-target bitstream design header differs")
        fields = header.bitstream_header(data.replace(encoded, replacement, 1))
        fields["Design"] = TARGET
        verify_inputs(plan)
        result.update(Passed=True, Bitstream=dict(Path=str(bit), SHA256=sha(bit), Bytes=bit.stat().st_size, Header=fields), ActualEvents=events)
    except Exception as error:
        result["Error"] = type(error).__name__ + ": " + str(error)
    result["ElapsedSeconds"] = round(time.monotonic() - started, 3)
    result["EndedUTC"] = datetime.now(timezone.utc).isoformat()
    result["EvidenceSHA256"] = {str(p.relative_to(WORK)):sha(p) for p in WORK.rglob("*") if p.is_file() and p.suffix in (".json", ".log", ".tcl", ".bgr", ".sbit", ".rtr")}
    save(WORK / "export-result.json", result)
    print(json.dumps(result))
    return 0 if result["Passed"] else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit", action="store_true")
    args = parser.parse_args()
    if args.audit:
        audit()
    else:
        raise SystemExit(run())
